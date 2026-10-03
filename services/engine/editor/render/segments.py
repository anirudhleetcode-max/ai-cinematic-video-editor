"""Per-segment rendering: trim → speed / speed-ramp → stabilise → technical grade → reframe & camera
motion → effects → frame-exact mezzanine split into head / body / tail pieces.

Pieces are cached by a hash of everything that affects their pixels, so revisions only re-render the
segments that actually changed."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..config import get_settings
from ..logging import get_logger, log
from ..proc import MediaCommandError, ff_path, run
from ..registry.color import write_cube
from ..registry.effects import render_effect
from ..registry.motion import camera_at
from ..schemas import Segment
from .colorspace import TAGS, TO_YUV420, source_to_rgb

logger = get_logger("render.segment")
MEZZ_VERSION = "mz6"  # mz5: explicit source matrix/range → RGB working space → BT.709 tagged mezzanines
SR = 48000


@dataclass
class SegJob:
    seg: Segment
    src: Path
    fingerprint: str
    has_audio: bool
    src_w: int
    src_h: int
    head: float  # overlap with previous segment (s)
    tail: float  # overlap with next segment (s)
    out_w: int
    out_h: int
    fps: float
    quality: str
    cache_dir: Path
    mode: str
    src_meta: dict | None = None
    audio_src: Path | None = None  # original file: preview proxies are video-only


@dataclass
class SegResult:
    seg_id: str
    head: Path | None
    body: Path | None
    tail: Path | None
    audio: Path
    n_frames: int
    n_head: int
    n_tail: int
    cached: bool
    fallbacks: list[str]


def ramp_sampling_fps(out_fps: float, max_rate: float) -> float:
    return float(min(240.0, max(out_fps, out_fps * max(1.0, max_rate))))


def x264_mezz_args(quality: str) -> list[str]:
    crf = {"draft": 26, "standard": 16, "high": 12}[quality]
    preset = {"draft": "ultrafast", "standard": "veryfast", "high": "faster"}[quality]
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-g", "48", "-bf", "0", "-threads", "2", *TAGS]


def frames_for(seconds: float, fps: float) -> int:
    return max(0, int(round(seconds * fps)))


def job_key(j: SegJob) -> str:
    spec = j.seg.model_dump(exclude={"out_start", "reason", "beat_index", "section", "id", "audio_gain_db", "keep_audio", "transition_in", "audio_role"})
    blob = json.dumps({"v": MEZZ_VERSION, "spec": spec, "fp": j.fingerprint, "h": round(j.head, 3), "t": round(j.tail, 3), "w": j.out_w, "hh": j.out_h,
                       "fps": j.fps, "q": j.quality, "m": j.mode}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def _atempo_chain(rate: float) -> str:
    parts = []
    r = rate
    while r < 0.5:
        parts.append("atempo=0.5")
        r /= 0.5
    while r > 2.0:
        parts.append("atempo=2.0")
        r /= 2.0
    parts.append(f"atempo={r:.5f}")
    return ",".join(parts)


def ramp_time_map(ramp: list[tuple[float, float]], out_dur: float, n_frames: int) -> tuple[np.ndarray, np.ndarray]:
    """Continuous speed curve → source time (s, relative to src_in) and instantaneous rate for every output frame.
    rate(u) is piecewise-linear in normalised output time u; source time is its exact integral."""
    xs = np.array([p for p, _ in ramp], np.float64)
    ys = np.array([r for _, r in ramp], np.float64)
    fine = np.linspace(0.0, 1.0, max(2, n_frames * 8 + 1))
    r = np.interp(fine, xs, ys)
    cum = np.concatenate([[0.0], np.cumsum((r[1:] + r[:-1]) / 2 * np.diff(fine))]) * out_dur
    u = (np.arange(n_frames) + 0.5) / max(1, n_frames)
    return np.interp(u, fine, cum), np.interp(u, xs, ys)


def ramp_source_length(ramp: list[tuple[float, float]], out_dur: float) -> float:
    t, _ = ramp_time_map(ramp, out_dur, 2048)
    return float(t[-1]) + out_dur / 2048


def stabilize_mode(s: Segment) -> str:
    if not s.stabilize:
        return "off"
    return s.stabilize_mode or "light"


def stabilize_filter(s: Segment, tmp: Path) -> str:
    """OFF / LIGHT (single-pass deshake) / STANDARD / STRONG (two-pass vid.stab when FFmpeg has it, else a wider deshake).
    The vid.stab motion file comes from `vidstab_detect` (run before the main graph, cached with the segment)."""
    mode = stabilize_mode(s)
    trf = tmp / "stab.trf"
    if mode in ("standard", "strong") and trf.exists():
        smooth = 12 if mode == "standard" else 30
        return f"vidstabtransform=input={ff_path(trf)}:smoothing={smooth}:zoom=0:optzoom=1:interpol=bilinear,unsharp=5:5:0.6:3:3:0.0"
    r = 16 if mode == "light" else 32
    return f"deshake=rx={r}:ry={r}:edge=mirror"


def vidstab_detect(j: "SegJob", s: Segment, tmp: Path) -> bool:
    """Pass 1 of two-pass stabilisation over exactly the source range the segment uses."""
    from ..hw import has_filter

    if stabilize_mode(s) not in ("standard", "strong") or s.image or not has_filter("vidstabdetect"):
        return False
    trf = tmp / "stab.trf"
    if trf.exists():
        return True
    st = get_settings()
    shake = 6 if stabilize_mode(s) == "standard" else 9
    src_len = s.src_out - s.src_in
    try:
        run([st.ffmpeg, "-v", "error", "-y", "-nostdin", "-ss", f"{s.src_in:.3f}", "-t", f"{src_len + 0.5:.3f}", "-i", str(j.src), "-an",
             "-vf", f"vidstabdetect=shakiness={shake}:accuracy=12:result={ff_path(trf)}", "-f", "null", "-"], timeout=1800)
    except (MediaCommandError, subprocess.TimeoutExpired):
        trf.unlink(missing_ok=True)
        return False
    return trf.exists()


def _video_core(j: SegJob, s: Segment, tmp: Path, fallback_level: int) -> tuple[list[str], str, int]:
    """Builds the decode filter graph. Returns (input args, filter_complex ending in [vout], frame count)."""
    fps = j.fps
    N = frames_for(s.out_duration, fps)
    inp: list[str] = []
    if s.image:
        inp = ["-loop", "1", "-framerate", str(fps), "-t", f"{s.out_duration + 1:.3f}", "-i", str(j.src)]
    else:
        src_len = s.src_out - s.src_in
        inp = ["-ss", f"{s.src_in:.3f}", "-t", f"{src_len + 0.5:.3f}", "-i", str(j.src)]
    chains: list[str] = []
    cur = "0:v"
    pre = []
    meta = j.src_meta or {}
    if not s.image and (meta.get("inspection") or {}).get("field_order") not in (None, "progressive", "unknown"):
        pre.append("bwdif=mode=send_frame")
    if s.stabilize and fallback_level < 2 and not s.image:
        pre.append(stabilize_filter(s, tmp))
    if not pre:
        pre.append("null")
    ramp = bool(s.speed.ramp) and fallback_level < 2 and not s.image
    if ramp:
        # continuous ramp: decode the source range at a constant sampling rate high enough for the fastest part,
        # then remap time per output frame in numpy (segments._render_motion)
        max_rate = max(r for _, r in s.speed.ramp)
        post = pre + [f"fps={ramp_sampling_fps(fps, max_rate):.3f}"]
    else:
        rate = s.speed.rate if not s.image else 1.0
        post = pre + [f"setpts=(PTS-STARTPTS)/{rate:.5f}"]
        if s.speed.interpolate and rate < 0.95 and fallback_level < 1:
            post.append(f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
        else:
            post.append(f"fps={fps}")
    # cover-scale (+ headroom for camera motion) straight into the RGB working space with the source's own matrix /
    # range (or HDR tone-mapping); then the per-shot technical grade LUT, then crop (static) or numpy camera motion
    motion = (s.motion.preset != "none" and fallback_level < 2) or ramp
    sw, sh = j.src_w, j.src_h
    cover = max(j.out_w / sw, j.out_h / sh) * s.crop.zoom
    head = 1.0
    if motion:
        head = min(1.25, max(1.0, 1.0 / cover if cover < 1 else 1.0))  # extra resolution if the source has it
    cw, ch = int(math.ceil(sw * cover * head / 2) * 2), int(math.ceil(sh * cover * head / 2) * 2)
    post.append(source_to_rgb(meta, cw, ch, image=bool(s.image)))
    post.append("setsar=1")
    t = s.technical
    tech = {"exposure": t.exposure, "gamma": t.gamma, "temperature": t.temperature, "tint": t.tint, "saturation": t.saturation, "contrast": t.contrast}
    if any(abs(tech[k] - d) > 1e-3 for k, d in (("exposure", 0), ("gamma", 1), ("temperature", 0), ("tint", 0), ("saturation", 1), ("contrast", 1))):
        lut = write_cube(tmp / "tech.cube", tech, size=17)
        post.append(f"lut3d=file={ff_path(lut)}:interp=tetrahedral")
    if not motion:
        x = int(np.clip(s.crop.cx * cw - j.out_w / 2, 0, cw - j.out_w))
        y = int(np.clip(s.crop.cy * ch - j.out_h / 2, 0, ch - j.out_h))
        post.append(f"crop={j.out_w}:{j.out_h}:{x}:{y}")
    freeze = s.speed.freeze_end + 2.0 / fps + (1.0 if s.image else 0.0) + (0.5 if ramp else 0.0)
    post.append(f"tpad=stop_mode=clone:stop_duration={freeze:.3f}")
    chains.append(f"[{cur}]{','.join(post)}[vcore]")
    return inp, ";".join(chains), N, motion, (cw, ch)


def _effects_chain(s: Segment, j: SegJob, label_in: str, fallback_level: int) -> tuple[str, str]:
    if fallback_level >= 1 or not s.effects:
        return "", label_in
    ctx = {"w": j.out_w, "h": j.out_h, "dur": s.out_duration, "fps": j.fps}
    parts, cur = [], label_in
    for k, e in enumerate(s.effects):
        nxt = f"fx{k}"
        parts.append(render_effect(e.id, dict(e.params), ctx, cur, nxt))
        cur = nxt
    return ";".join(parts), cur


def _split_outputs(final_label: str, N: int, nh: int, nt: int, out: dict[str, Path], quality: str) -> tuple[str, list[str]]:
    pieces = []
    if nh:
        pieces.append(("head", 0, nh))
    pieces.append(("body", nh, N - nt))
    if nt:
        pieces.append(("tail", N - nt, N))
    g = f";[{final_label}]trim=end_frame={N},setpts=PTS-STARTPTS,{TO_YUV420},split={len(pieces)}" + "".join(f"[o{i}]" for i in range(len(pieces)))
    args: list[str] = []
    for i, (name, a, b) in enumerate(pieces):
        g += f";[o{i}]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[p{name}]"
        if name == "body":
            args += ["-map", f"[p{name}]", *x264_mezz_args(quality), "-an", str(out[name])]
        else:  # overlap frames kept lossless for the transition stage
            args += ["-map", f"[p{name}]", "-c:v", "ffv1", "-level", "3", *TAGS, "-an", str(out[name])]
    return g, args


def _render_motion(j: SegJob, s: Segment, inp: list[str], graph: str, N: int, cw: int, ch: int, out: dict, nh: int, nt: int, fallback_level: int) -> None:
    """Decode → numpy sub-pixel camera warp per frame → encode (effects + split)."""
    st = get_settings()
    ramp = bool(s.speed.ramp) and fallback_level < 2 and not s.image
    if ramp:
        F = ramp_sampling_fps(j.fps, max(r for _, r in s.speed.ramp))
        src_t, inst_rate = ramp_time_map(s.speed.ramp, s.out_duration, N)
        need_idx = src_t * F
        n_src = int(math.ceil(need_idx[-1])) + 2
        flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST) if (j.mode == "quality" and fallback_level == 0) else None
    else:
        n_src = N
    dec = subprocess.Popen([st.ffmpeg, "-v", "error", "-nostdin", *inp, "-filter_complex", graph, "-map", "[vcore]", "-frames:v", str(n_src),
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    fx_graph, fx_out = _effects_chain(s, j, "0:v", fallback_level)
    split_g, out_args = _split_outputs(fx_out if fx_graph else "0:v", N, nh, nt, out, j.quality)
    full = (fx_graph + split_g) if fx_graph else split_g.lstrip(";")
    enc = subprocess.Popen([st.ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{j.out_w}x{j.out_h}", "-r", str(j.fps), "-i", "-",
                            "-filter_complex", full, *out_args], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    W, H = j.out_w, j.out_h
    sc = min(cw / W, ch / H)
    fsz = cw * ch * 3
    params = {**s.motion.params, "intensity": s.motion.intensity, "_dur": s.out_duration}
    i = 0
    last = None
    buf_frames: dict[int, np.ndarray] = {}
    read_idx = 0
    blended = 0

    def src_frame(idx: int) -> np.ndarray | None:
        """Sequential reader with a small window (frames are only ever requested in non-decreasing order)."""
        nonlocal read_idx, last
        while read_idx <= idx:
            raw = dec.stdout.read(fsz)
            if len(raw) < fsz:
                return last
            last = np.frombuffer(raw, np.uint8).reshape(ch, cw, 3)
            buf_frames[read_idx] = last
            buf_frames.pop(read_idx - 3, None)
            read_idx += 1
        return buf_frames.get(idx, last)

    try:
        assert dec.stdout is not None and enc.stdin is not None
        while i < N:
            if ramp:
                pos = float(need_idx[i])
                i0 = int(math.floor(pos))
                frac = pos - i0
                fa = src_frame(i0)
                fb = src_frame(i0 + 1) if frac > 0.02 else fa
                if fa is None:
                    break
                if fb is None or fb is fa or inst_rate[i] >= 0.9 or frac <= 0.02:
                    frame = fa if frac < 0.5 or fb is None else fb  # normal/fast speed: nearest source frame
                elif flow is not None:
                    # quality mode: motion-compensated interpolation (DIS optical flow, both directions)
                    ga, gb = cv2.cvtColor(fa, cv2.COLOR_RGB2GRAY), cv2.cvtColor(fb, cv2.COLOR_RGB2GRAY)
                    fab = flow.calc(ga, gb, None)
                    hgt, wid = ga.shape
                    gx, gy = np.meshgrid(np.arange(wid, dtype=np.float32), np.arange(hgt, dtype=np.float32))
                    wa = cv2.remap(fa, gx - frac * fab[..., 0], gy - frac * fab[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                    wb = cv2.remap(fb, gx + (1 - frac) * fab[..., 0], gy + (1 - frac) * fab[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                    frame = cv2.addWeighted(wa, 1 - frac, wb, frac, 0)
                    blended += 1
                else:
                    frame = cv2.addWeighted(fa, 1 - frac, fb, frac, 0)  # slow parts: frame blending, no duplicated frames
                    blended += 1
            else:
                raw = dec.stdout.read(fsz)
                if len(raw) < fsz:
                    if last is None:
                        break
                    frame = last
                else:
                    frame = np.frombuffer(raw, np.uint8).reshape(ch, cw, 3)
                    last = frame
            u = i / max(1, N - 1)
            z, dx, dy, rot = camera_at(s.motion.preset, u, params) if s.motion.preset != "none" else (1.0, 0.0, 0.0, 0.0)
            k = sc / max(z, 1e-3)
            hw, hh = W * k / 2, H * k / 2
            cxp = float(np.clip(s.crop.cx * cw + dx * cw, hw, cw - hw))
            cyp = float(np.clip(s.crop.cy * ch + dy * ch, hh, ch - hh))
            th = math.radians(rot)
            a, b = k * math.cos(th), k * math.sin(th)
            M = np.float32([[a, -b, cxp - a * W / 2 + b * H / 2], [b, a, cyp - b * W / 2 - a * H / 2]])
            outf = cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)
            enc.stdin.write(outf.tobytes())
            i += 1
        enc.stdin.close()
    finally:
        dec.kill()
        dec.wait()
        enc.wait()
    if enc.returncode != 0 or i < N:
        err = enc.stderr.read().decode("utf-8", "replace") if enc.stderr else ""
        raise MediaCommandError(["ffmpeg"], enc.returncode or 1, f"motion render wrote {i}/{N} frames: {err[-400:]}")


def render_audio(j: SegJob, s: Segment, path: Path) -> Path:
    """Segment audio at the output speed, exactly out_duration long (silence if none/muted)."""
    st = get_settings()
    n = int(round(s.out_duration * SR))
    if s.image or not j.has_audio or s.speed.ramp:
        run([st.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-t", f"{s.out_duration:.4f}", "-c:a", "pcm_s16le", str(path)])
        return path
    src_len = s.src_out - s.src_in
    af = ("adeclip," if "declip" in s.audio_repair else "") + f"{_atempo_chain(s.speed.rate)},aresample={SR},apad,atrim=end_sample={n}"
    run([st.ffmpeg, "-v", "error", "-y", "-ss", f"{s.src_in:.3f}", "-t", f"{src_len + 0.3:.3f}", "-i", str(j.audio_src or j.src), "-vn", "-ac", "2", "-af", af,
         "-c:a", "pcm_s16le", str(path)], timeout=600)
    return path


def render_segment(j: SegJob) -> SegResult:
    s = j.seg
    key = job_key(j)
    d = j.cache_dir / key
    nh, nt = frames_for(j.head, j.fps), frames_for(j.tail, j.fps)
    N = frames_for(s.out_duration, j.fps)
    nt = min(nt, max(0, N - nh - 1))
    out = {"head": d / "head.mkv", "body": d / "body.mp4", "tail": d / "tail.mkv"}
    audio = d / "audio.wav"
    done = d / "done.json"
    if done.exists():
        meta = json.loads(done.read_text())
        return SegResult(s.id, out["head"] if nh else None, out["body"], out["tail"] if nt else None, audio, N, nh, nt, True, meta.get("fallbacks", []))
    d.mkdir(parents=True, exist_ok=True)
    fallbacks: list[str] = []
    st = get_settings()
    vidstab_detect(j, s, d)
    for level in (0, 1, 2):
        try:
            inp, graph, N2, motion, (cw, ch) = _video_core(j, s, d, level)
            if motion:
                _render_motion(j, s, inp, graph, N, cw, ch, out, nh, nt, level)
            else:
                fx_graph, fx_out = _effects_chain(s, j, "vcore", level)
                split_g, out_args = _split_outputs(fx_out, N, nh, nt, out, j.quality)
                g = graph + (";" + fx_graph if fx_graph else "") + split_g
                run([st.ffmpeg, "-v", "error", "-y", "-nostdin", *inp, "-filter_complex", g, *out_args], timeout=3600)
            break
        except (MediaCommandError, subprocess.TimeoutExpired) as e:
            msg = ["effects removed", "motion/stabilisation/interpolation removed", "plain trim"][level]
            fallbacks.append(f"level{level + 1}: {msg} ({str(e)[:160]})")
            log(logger, "segment render failed; falling back", seg=s.id, level=level, error=str(e)[:300])
            if level == 2:
                raise
    try:
        render_audio(j, s, audio)
    except (MediaCommandError, subprocess.TimeoutExpired) as e:  # never let one clip's audio fail the film
        fallbacks.append(f"audio: source audio unreadable for this range → silence ({str(e)[:120]})")
        silent = SegJob(**{**j.__dict__, "has_audio": False})
        render_audio(silent, s, audio)
    done.write_text(json.dumps({"key": key, "fallbacks": fallbacks}))
    return SegResult(s.id, out["head"] if nh else None, out["body"], out["tail"] if nt else None, audio, N, nh, nt, False, fallbacks)
