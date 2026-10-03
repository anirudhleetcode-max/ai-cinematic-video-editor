"""FFprobe metadata extraction, thumbnails and proxy generation."""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

from ..config import get_settings
from ..proc import run

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AUDIO_EXT = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def kind_for(filename: str) -> str | None:
    ext = Path(filename).suffix.lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in IMAGE_EXT:
        return "image"
    return None


def _fps(s: str | None) -> float:
    try:
        f = Fraction(s or "0")
        return float(f) if f > 0 else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe(path: Path) -> dict:
    s = get_settings()
    out = run([s.ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], timeout=60).stdout
    data = json.loads(out or b"{}")
    fmt = data.get("format", {})
    v = next((x for x in data.get("streams", []) if x.get("codec_type") == "video" and not x.get("disposition", {}).get("attached_pic")), None)
    a = next((x for x in data.get("streams", []) if x.get("codec_type") == "audio"), None)
    meta: dict = {
        "duration": float(fmt.get("duration") or (v or a or {}).get("duration") or 0.0),
        "bitrate": int(fmt.get("bit_rate") or 0),
        "format": fmt.get("format_name"),
        "size": int(fmt.get("size") or 0),
        "has_video": v is not None,
        "has_audio": a is not None,
    }
    if v:
        w, h = int(v.get("width") or 0), int(v.get("height") or 0)
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        if "rotate" in (v.get("tags") or {}):
            rot = int(v["tags"]["rotate"])
        try:
            sn, sd_ = (int(x) for x in (v.get("sample_aspect_ratio") or "1:1").split(":"))
            sar = sn / sd_ if sn > 0 and sd_ > 0 else 1.0
        except ValueError:
            sar = 1.0
        dw, dh = (int(round(w * sar)), h) if sar >= 1 else (w, int(round(h / sar)))
        dw, dh = dw + dw % 2, dh + dh % 2
        if abs(rot) % 180 == 90:
            dw, dh = dh, dw
        trc = v.get("color_transfer") or "unknown"
        meta.update(
            width=w, height=h, display_width=dw, display_height=dh, rotation=rot, sar=round(sar, 4),
            fps=_fps(v.get("avg_frame_rate")) or _fps(v.get("r_frame_rate")),
            vcodec=v.get("codec_name"), pix_fmt=v.get("pix_fmt"),
            color_space=v.get("color_space") or "unknown", color_range=v.get("color_range") or "unknown", color_transfer=trc,
            hdr={"smpte2084": "PQ", "arib-std-b67": "HLG"}.get(trc),
            orientation="portrait" if dh > dw else ("square" if dh == dw else "landscape"),
        )
    if a:
        meta.update(acodec=a.get("codec_name"), sample_rate=int(a.get("sample_rate") or 0), channels=int(a.get("channels") or 0))
    return meta


def thumbnail(path: Path, out: Path, at: float, width: int = 480) -> Path:
    s = get_settings()
    out.parent.mkdir(parents=True, exist_ok=True)
    run([s.ffmpeg, "-v", "error", "-y", "-ss", f"{max(0.0, at):.3f}", "-i", str(path), "-frames:v", "1",
         "-vf", f"scale={width}:-2", "-q:v", "4", str(out)], timeout=60)
    return out


def image_thumbnail(path: Path, out: Path, width: int = 480) -> Path:
    s = get_settings()
    out.parent.mkdir(parents=True, exist_ok=True)
    run([s.ffmpeg, "-v", "error", "-y", "-i", str(path), "-vf", f"scale={width}:-2", "-q:v", "4", str(out)], timeout=60)
    return out


def make_proxy(path: Path, out: Path, height: int = 360, fps: int = 15, meta: dict | None = None) -> Path:
    """Low-res, low-fps preview proxy, normalised to square pixels, BT.709 limited range SDR (HDR tone-mapped), so the
    preview renderer can treat every proxy identically. Originals are always used for the final render."""
    from ..render.colorspace import TAGS, TO_YUV420, source_to_rgb

    s = get_settings()
    m = meta or probe(path)
    dw, dh = m.get("display_width") or m.get("width") or 640, m.get("display_height") or m.get("height") or 360
    w = max(2, int(round(dw * height / max(1, dh) / 2)) * 2)
    out.parent.mkdir(parents=True, exist_ok=True)
    run([s.ffmpeg, "-v", "error", "-y", "-i", str(path), "-vf", f"fps={fps},{source_to_rgb(m, w, height)},setsar=1,{TO_YUV420}",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", *TAGS, "-an", str(out)], timeout=3600)
    return out
