"""Deep media inspection for real-world files: what the file *is*, what is unusual about it, and how the engine
must normalise it. Every field is measured from FFprobe/FFmpeg output — nothing is guessed from the filename.

Checks: container/stream validity, decode errors (sampled windows), variable frame rate (packet timestamps),
rotation (display matrix / legacy tag), pixel aspect ratio, pixel format / bit depth / chroma, colour range,
colour primaries / transfer (HDR: PQ / HLG), unusual or legacy codecs, missing / multiple audio streams,
odd dimensions, extreme frame rates and durations.
"""
from __future__ import annotations

import json
import re
from fractions import Fraction
from pathlib import Path

import numpy as np

from ..config import get_settings
import subprocess

from ..proc import MediaCommandError, run

ProcError = (MediaCommandError, subprocess.TimeoutExpired, OSError)

COMMON_VCODECS = {"h264", "hevc", "vp9", "av1", "prores", "mjpeg", "dnxhd", "mpeg4", "vp8", "mpeg2video"}
LEGACY_VCODECS = {"msmpeg4v1", "msmpeg4v2", "msmpeg4v3", "wmv1", "wmv2", "wmv3", "h263", "flv1", "mpeg1video", "theora", "cinepak", "rawvideo"}
COMMON_PIXFMT = {"yuv420p", "yuvj420p", "nv12"}
HDR_TRANSFER = {"smpte2084": "PQ", "arib-std-b67": "HLG"}


def _frac(s: str | None) -> float:
    try:
        f = Fraction(s or "0")
        return float(f) if f > 0 else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def _bit_depth(pix_fmt: str) -> int:
    m = re.search(r"p(\d{2})(le|be)?$", pix_fmt or "")
    return int(m.group(1)) if m else 8


def _chroma(pix_fmt: str) -> str:
    for c in ("444", "422", "420", "411", "440"):
        if c in (pix_fmt or ""):
            return c
    return "rgb" if (pix_fmt or "").startswith(("rgb", "bgr", "gbr", "argb", "rgba", "bgra")) else ("gray" if "gray" in (pix_fmt or "") else "other")


def frame_timing(path: Path, n_packets: int = 900) -> dict:
    """Measure frame-interval regularity from the first `n_packets` video packet timestamps."""
    s = get_settings()
    try:
        out = run([s.ffprobe, "-v", "error", "-select_streams", "v:0", "-read_intervals", f"%+#{n_packets}",
                   "-show_entries", "packet=pts_time,dts_time", "-of", "csv=p=0", str(path)], timeout=60).stdout.decode()
    except ProcError:
        return {"measured": False}
    ts = []
    for line in out.splitlines():
        parts = [p for p in line.split(",") if p and p != "N/A"]
        if parts:
            try:
                ts.append(float(parts[0]))
            except ValueError:
                pass
    if len(ts) < 8:
        return {"measured": False, "packets": len(ts)}
    d = np.diff(np.sort(np.array(ts)))
    d = d[d > 0]
    if len(d) < 4:
        return {"measured": False, "packets": len(ts)}
    med = float(np.median(d))
    # VFR = a meaningful share of intervals deviating from the median by > 15 % (dropped/duplicated frames on a
    # CFR stream show up as isolated 2× intervals; phones produce continuous irregularity)
    dev = np.abs(d - med) / med
    irregular = float((dev > 0.15).mean())
    return {"measured": True, "packets": len(ts), "median_interval": round(med, 6), "fps_from_timestamps": round(1 / med, 3),
            "interval_cv": round(float(d.std() / d.mean()), 4), "irregular_fraction": round(irregular, 4),
            "vfr": bool(irregular > 0.05), "min_interval": round(float(d.min()), 6), "max_interval": round(float(d.max()), 6)}


def decode_check(path: Path, duration: float, has_video: bool, windows: int = 3, seconds: float = 1.0) -> dict:
    """Decode short windows (start / middle / end) and check that each one actually yields frames and no decoder
    errors. A truncated file with an intact index probes fine but decodes nothing past the cut — this catches it."""
    s = get_settings()
    starts = [0.0] if duration <= seconds * windows else [0.0, max(0.0, duration / 2 - seconds / 2), max(0.0, duration - seconds - 0.25)][:windows]
    sel, entry = ("v:0", "frame=pts_time") if has_video else ("a:0", "frame=pts_time")
    errors, empty, details, decoded = 0, 0, [], []
    for st in starts:
        try:
            p = run([s.ffprobe, "-v", "error", "-select_streams", sel, "-read_intervals", f"{st:.3f}%+{seconds:.3f}", "-show_entries", entry,
                     "-of", "csv=p=0", str(path)], timeout=120, check=False)
        except ProcError as e:
            errors += 1
            details.append(f"@{st:.1f}s: {str(e)[:160]}")
            continue
        n = sum(1 for ln in p.stdout.decode("utf-8", "replace").splitlines() if ln.strip())
        decoded.append(n)
        err = [ln for ln in p.stderr.decode("utf-8", "replace").splitlines() if ln.strip()]
        if p.returncode != 0 or err:
            errors += max(1, len(err))
            details.append(f"@{st:.1f}s: {(err[0] if err else f'exit {p.returncode}')[:160]}")
        if n == 0:
            empty += 1
            details.append(f"@{st:.1f}s: no frames decoded")
    return {"windows": len(starts), "frames_per_window": decoded, "errors": errors, "empty_windows": empty, "details": details[:5]}


def inspect_media(path: Path, deep: bool = True) -> dict:
    """Return {"ok", "kind", "props", "issues", "warnings", "normalize"}. `issues` make the file unusable;
    `warnings` are handled by normalisation. Never raises for a bad file — corrupt input is a result, not a crash."""
    s = get_settings()
    rep: dict = {"file": path.name, "ok": True, "kind": None, "props": {}, "issues": [], "warnings": [], "normalize": {}}
    if not path.exists() or path.stat().st_size == 0:
        rep.update(ok=False, issues=["empty_or_missing_file"])
        return rep
    try:
        raw = run([s.ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], timeout=60).stdout
        data = json.loads(raw or b"{}")
    except (*ProcError, json.JSONDecodeError) as e:
        rep.update(ok=False, issues=["unreadable_container"], props={"error": str(e)[-300:]})
        return rep
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    vids = [x for x in streams if x.get("codec_type") == "video" and not (x.get("disposition") or {}).get("attached_pic")]
    auds = [x for x in streams if x.get("codec_type") == "audio"]
    duration = float(fmt.get("duration") or 0) or max((float(x.get("duration") or 0) for x in streams), default=0.0)
    P = rep["props"]
    P.update(container=fmt.get("format_name"), duration=round(duration, 3), size=int(fmt.get("size") or 0), bitrate=int(fmt.get("bit_rate") or 0),
             video_streams=len(vids), audio_streams=len(auds))
    if not vids and not auds:
        rep.update(ok=False, issues=["no_audio_or_video_streams"])
        return rep
    if duration <= 0.05:
        rep["issues"].append("zero_duration")
    rep["kind"] = "video" if vids else "audio"
    if vids:
        v = vids[0]
        w, h = int(v.get("width") or 0), int(v.get("height") or 0)
        rot = 0
        for sd in v.get("side_data_list") or []:
            if "rotation" in sd:
                rot = int(round(float(sd["rotation"])))
        if "rotate" in (v.get("tags") or {}):
            rot = int(v["tags"]["rotate"])
        rot = ((rot % 360) + 360) % 360
        sar = v.get("sample_aspect_ratio") or "1:1"
        try:
            sn, sd_ = (int(x) for x in sar.split(":"))
            sarf = sn / sd_ if sn > 0 and sd_ > 0 else 1.0
        except ValueError:
            sarf = 1.0
        disp_w, disp_h = (int(round(w * sarf)), h) if sarf >= 1 else (w, int(round(h / sarf)))
        if rot in (90, 270):
            disp_w, disp_h = disp_h, disp_w
        pix = v.get("pix_fmt") or ""
        nominal, avg = _frac(v.get("r_frame_rate")), _frac(v.get("avg_frame_rate"))
        trc, prim = v.get("color_transfer") or "unknown", v.get("color_primaries") or "unknown"
        rng = "full" if (v.get("color_range") == "pc" or pix.startswith("yuvj")) else ("limited" if v.get("color_range") == "tv" else "unknown")
        P.update(vcodec=v.get("codec_name"), profile=v.get("profile"), width=w, height=h, rotation=rot, sar=sar, sar_value=round(sarf, 4),
                 display_width=disp_w, display_height=disp_h,
                 orientation="portrait" if disp_h > disp_w else ("square" if disp_h == disp_w else "landscape"),
                 pix_fmt=pix, bit_depth=_bit_depth(pix), chroma=_chroma(pix), color_range=rng, color_primaries=prim,
                 color_transfer=trc, color_space=v.get("color_space") or "unknown", nominal_fps=round(nominal, 3), avg_fps=round(avg, 3),
                 hdr=HDR_TRANSFER.get(trc), field_order=v.get("field_order") or "unknown",
                 nb_frames=int(v.get("nb_frames") or 0))
        if v.get("codec_name") in LEGACY_VCODECS:
            rep["warnings"].append(f"legacy_codec:{v.get('codec_name')}")
        elif v.get("codec_name") not in COMMON_VCODECS:
            rep["warnings"].append(f"unusual_codec:{v.get('codec_name')}")
        if rot:
            rep["warnings"].append(f"rotation:{rot}")
            rep["normalize"]["rotation"] = "apply display matrix (FFmpeg autorotate) before any crop/scale"
        if abs(sarf - 1) > 0.01:
            rep["warnings"].append(f"non_square_pixels:{sar}")
            rep["normalize"]["sar"] = f"scale to square pixels ({disp_w}×{disp_h}) before framing"
        if pix not in COMMON_PIXFMT:
            rep["warnings"].append(f"pixel_format:{pix}")
            rep["normalize"]["pix_fmt"] = "convert to 8-bit 4:2:0 for the H.264 delivery path"
        if rng == "full":
            rep["warnings"].append("full_range")
            rep["normalize"]["range"] = "full → limited (tv) range conversion"
        if P["hdr"]:
            rep["warnings"].append(f"hdr:{P['hdr']}")
            rep["normalize"]["hdr"] = f"tone-map {P['hdr']}/BT.2020 → SDR BT.709"
        elif prim not in ("bt709", "unknown") or P["color_space"] not in ("bt709", "unknown"):
            rep["warnings"].append(f"colorspace:{prim}/{P['color_space']}")
            rep["normalize"]["colorspace"] = f"convert {P['color_space']} → bt709 matrix"
        if v.get("field_order") not in (None, "progressive", "unknown"):
            rep["warnings"].append(f"interlaced:{v.get('field_order')}")
            rep["normalize"]["deinterlace"] = "bwdif deinterlace"
        if w % 2 or h % 2:
            rep["warnings"].append("odd_dimensions")
        if w * h == 0:
            rep["issues"].append("invalid_dimensions")
        fps = avg or nominal
        if fps and (fps < 10 or fps > 121):
            rep["warnings"].append(f"extreme_fps:{fps:.2f}")
        if nominal and avg and abs(nominal - avg) / nominal > 0.01:
            rep["warnings"].append(f"fps_mismatch:nominal {nominal:.3f} vs average {avg:.3f}")
        if deep:
            t = frame_timing(path)
            P["timing"] = t
            if t.get("vfr"):
                rep["warnings"].append("variable_frame_rate")
                rep["normalize"]["vfr"] = "resample to constant output frame rate (fps filter) — never trust nominal fps"
        if not auds:
            rep["warnings"].append("no_audio")
    if auds:
        a = auds[0]
        P.update(acodec=a.get("codec_name"), sample_rate=int(a.get("sample_rate") or 0), channels=int(a.get("channels") or 0),
                 channel_layout=a.get("channel_layout"), audio_languages=[(x.get("tags") or {}).get("language", "und") for x in auds])
        if len(auds) > 1:
            rep["warnings"].append(f"multiple_audio_streams:{len(auds)}")
            rep["normalize"]["audio_stream"] = "use the first (default) audio stream"
        if P["sample_rate"] and P["sample_rate"] != 48000:
            rep["normalize"]["sample_rate"] = f"resample {P['sample_rate']} → 48000 Hz"
        if P["channels"] and P["channels"] > 2:
            rep["warnings"].append(f"multichannel_audio:{P['channels']}")
            rep["normalize"]["downmix"] = "downmix to stereo"
    if deep and not rep["issues"]:
        dc = decode_check(path, duration, bool(vids))
        P["decode_check"] = dc
        if dc["empty_windows"] == dc["windows"]:
            rep["issues"].append("undecodable")
        elif dc["empty_windows"]:
            rep["issues"].append("truncated_or_partially_undecodable")
        elif dc["errors"]:
            rep["warnings"].append(f"decode_errors:{dc['errors']}")
    rep["ok"] = not rep["issues"]
    return rep
