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
from ..proc import MediaCommandError, run
from ..registry.color import write_cube
from ..registry.effects import render_effect
from ..registry.motion import camera_at
from ..schemas import Segment

logger = get_logger("render.segment")
MEZZ_VERSION = "mz4"
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


def x264_mezz_args(quality: str) -> list[str]:
    crf = {"draft": 26, "standard": 16, "high": 12}[quality]
    preset = {"draft": "ultrafast", "standard": "veryfast", "high": "faster"}[quality]
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-g", "48", "-bf", "0", "-threads", "2"]


def frames_for(seconds: float, fps: float) -> int:
    return max(0, int(round(seconds * fps)))


def job_key(j: SegJob) -> str:
    spec = j.seg.model_dump(exclude={"out_start", "reason", "beat_index", "section", "id", "audio_gain_db", "keep_audio", "transition_in"})
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


def _ramp_pieces(ramp: list[tuple[float, float]], out_dur: float, n: int = 10) -> list[tuple[float, float, float]]:
    """Piecewise-constant approximation of a speed curve: returns [(src_start, src_end, rate)] (source seconds, relative)."""
    xs = np.array([p for p, _ in ramp])
    ys = np.array([r for _, r in ramp])
    edges = np.linspace(0, 1, n + 1)
    src_t = 0.0
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        r = float(np.interp((a + b) / 2, xs, ys))
        seg_src = r * (b - a) * out_dur
        out.append((src_t, src_t + seg_src, r))
        src_t += seg_src
    return out


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
    if s.stabilize and fallback_level < 2 and not s.image:
        pre.append("deshake=rx=24:ry=24:edge=mirror")
    pre.append("setsar=1")
    if s.speed.ramp and fallback_level < 2 and not s.image:
        pieces = _ramp_pieces(s.speed.ramp, s.out_duration)
        chains.append(f"[{cur}]{','.join(pre)},split={len(pieces)}" + "".join(f"[rp{i}]" for i in range(len(pieces))))
        for i, (a, b, r) in enumerate(pieces):
            chains.append(f"[rp{i}]trim=start={a:.4f}:end={b:.4f},setpts=(PTS-STARTPTS)/{r:.5f}[rq{i}]")
        chains.append("".join(f"[rq{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=1:a=0[spd]")
        cur = "spd"
        post = [f"fps={fps}"]
    else:
        rate = s.speed.rate if not s.image else 1.0
        post = pre + [f"setpts=(PTS-STARTPTS)/{rate:.5f}"]
        if s.speed.interpolate and rate < 0.95 and fallback_level < 1:
            post.append(f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
        else:
            post.append(f"fps={fps}")
    # technical grade (per-shot normalisation) as a small LUT
    t = s.technical
    tech = {"exposure": t.exposure, "gamma": t.gamma, "temperature": t.temperature, "tint": t.tint, "saturation": t.saturation, "contrast": t.contrast}
    if any(abs(tech[k] - d) > 1e-3 for k, d in (("exposure", 0), ("gamma", 1), ("temperature", 0), ("tint", 0), ("saturation", 1), ("contrast", 1))):
        lut = write_cube(tmp / "tech.cube", tech, size=17)
        post.append(f"lut3d=file='{lut.as_posix()}':interp=tetrahedral")
    # cover-scale (+ headroom for camera motion), then either crop (static) or hand off to numpy motion
    motion = s.motion.preset != "none" and fallback_level < 2
    sw, sh = j.src_w, j.src_h
    cover = max(j.out_w / sw, j.out_h / sh) * s.crop.zoom
    head = 1.0
    if motion:
        head = min(1.25, max(1.0, 1.0 / cover if cover < 1 else 1.0))  # extra resolution if the source has it
    cw, ch = int(math.ceil(sw * cover * head / 2) * 2), int(math.ceil(sh * cover * head / 2) * 2)
    post.append(f"scale={cw}:{ch}:flags=lanczos")
    if not motion:
        x = int(np.clip(s.crop.cx * cw - j.out_w / 2, 0, cw - j.out_w))
        y = int(np.clip(s.crop.cy * ch - j.out_h / 2, 0, ch - j.out_h))
        post.append(f"crop={j.out_w}:{j.out_h}:{x}:{y}")
    freeze = s.speed.freeze_end + 2.0 / fps + (1.0 if s.image else 0.0)
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
    g = f";[{final_label}]trim=end_frame={N},setpts=PTS-STARTPTS,format=yuv420p,split={len(pieces)}" + "".join(f"[o{i}]" for i in range(len(pieces)))
    args: list[str] = []
    for i, (name, a, b) in enumerate(pieces):
        g += f";[o{i}]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[p{name}]"
        if name == "body":
            args += ["-map", f"[p{name}]", *x264_mezz_args(quality), "-an", str(out[name])]
        else:  # overlap frames kept lossless for the transition stage
            args += ["-map", f"[p{name}]", "-c:v", "ffv1", "-level", "3", "-an", str(out[name])]
    return g, args


def _render_motion(j: SegJob, s: Segment, inp: list[str], graph: str, N: int, cw: int, ch: int, out: dict, nh: int, nt: int, fallback_level: int) -> None:
    """Decode → numpy sub-pixel camera warp per frame → encode (effects + split)."""
    st = get_settings()
    dec = subprocess.Popen([st.ffmpeg, "-v", "error", "-nostdin", *inp, "-filter_complex", graph, "-map", "[vcore]", "-frames:v", str(N),
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
    try:
        assert dec.stdout is not None and enc.stdin is not None
        while i < N:
            buf = dec.stdout.read(fsz)
            if len(buf) < fsz:
                if last is None:
                    break
                frame = last
            else:
                frame = np.frombuffer(buf, np.uint8).reshape(ch, cw, 3)
                last = frame
            u = i / max(1, N - 1)
            z, dx, dy, rot = camera_at(s.motion.preset, u, params)
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
    af = f"{_atempo_chain(s.speed.rate)},aresample={SR},apad,atrim=end_sample={n}"
    run([st.ffmpeg, "-v", "error", "-y", "-ss", f"{s.src_in:.3f}", "-t", f"{src_len + 0.3:.3f}", "-i", str(j.src), "-vn", "-ac", "2", "-af", af,
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
    render_audio(j, s, audio)
    done.write_text(json.dumps({"key": key, "fallbacks": fallbacks}))
    return SegResult(s.id, out["head"] if nh else None, out["body"], out["tail"] if nt else None, audio, N, nh, nt, False, fallbacks)
