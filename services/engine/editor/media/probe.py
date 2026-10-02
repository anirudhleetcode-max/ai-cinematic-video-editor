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
        dw, dh = (h, w) if abs(rot) % 180 == 90 else (w, h)
        meta.update(
            width=w, height=h, display_width=dw, display_height=dh, rotation=rot,
            fps=_fps(v.get("avg_frame_rate")) or _fps(v.get("r_frame_rate")),
            vcodec=v.get("codec_name"), pix_fmt=v.get("pix_fmt"),
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


def make_proxy(path: Path, out: Path, height: int = 360, fps: int = 15) -> Path:
    """Low-res, low-fps proxy used for analysis and preview decisions (originals are used for final render)."""
    s = get_settings()
    out.parent.mkdir(parents=True, exist_ok=True)
    run([s.ffmpeg, "-v", "error", "-y", "-i", str(path), "-vf", f"scale=-2:{height},fps={fps}", "-c:v", "libx264",
         "-preset", "ultrafast", "-crf", "30", "-an", str(out)], timeout=3600)
    return out
