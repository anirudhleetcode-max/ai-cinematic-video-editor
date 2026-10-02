"""Automatic quality control of a rendered file (FFprobe + FFmpeg detectors)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..config import get_settings
from ..media.probe import probe
from ..schemas import EditPlan


def _detect(path: Path, vf: str | None, af: str | None, timeout: float = 1800) -> str:
    st = get_settings()
    cmd = [st.ffmpeg, "-hide_banner", "-nostats", "-i", str(path)]
    if vf:
        cmd += ["-vf", vf]
    else:
        cmd += ["-vn"]
    if af:
        cmd += ["-af", af]
    else:
        cmd += ["-an"]
    cmd += ["-f", "null", "-"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stderr


def _intervals(text: str, start_key: str, end_key: str) -> list[tuple[float, float]]:
    starts = [float(x) for x in re.findall(rf"{start_key}[:=]\s*([\d.]+)", text)]
    ends = [float(x) for x in re.findall(rf"{end_key}[:=]\s*([\d.]+)", text)]
    return list(zip(starts, ends + [float("inf")] * (len(starts) - len(ends))))


def allowed_static(plan: EditPlan) -> list[tuple[float, float]]:
    """Windows where black or frozen frames are intentional (end card, freezes, photos, dips)."""
    w = []
    if plan.ending.duration > 0:
        w.append((plan.duration - plan.ending.duration - 0.3, plan.duration + 1))
    for s in plan.timeline:
        if s.image:
            w.append((s.out_start - 0.2, s.out_start + s.out_duration + 0.2))
        if s.speed.freeze_end > 0:
            w.append((s.out_start + s.out_duration - s.speed.freeze_end - 0.3, s.out_start + s.out_duration + 0.3))
        if s.transition_in.id in ("dip_to_black", "dip_to_white"):
            w.append((s.out_start - 0.3, s.out_start + s.transition_in.duration + 0.3))
    w.append((plan.duration - 1.5, plan.duration + 1))  # final fade
    return w


def _outside(iv: tuple[float, float], allowed: list[tuple[float, float]]) -> bool:
    a, b = iv
    return not any(x <= a and b <= y for x, y in allowed)


def quality_check(path: Path, plan: EditPlan, expect_audio: bool, text_violations: list | None = None, draft: bool = False) -> dict:
    checks: list[dict] = []

    def add(name, ok, detail="", severity="error"):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "severity": severity})

    exists = path.exists() and path.stat().st_size > 1000
    add("file_exists", exists, f"{path.stat().st_size if path.exists() else 0} bytes")
    if not exists:
        return {"passed": False, "checks": checks, "failures": ["file_exists"]}
    try:
        m = probe(path)
        add("valid_mp4", "mp4" in (m.get("format") or "") and m.get("has_video"), m.get("format", ""))
    except Exception as e:  # noqa: BLE001
        add("valid_mp4", False, str(e)[:200])
        return {"passed": False, "checks": checks, "failures": ["valid_mp4"]}
    add("duration", abs(m["duration"] - plan.duration) <= max(0.25, 2 / plan.fps), f"{m['duration']:.3f}s vs planned {plan.duration:.3f}s")
    want_w, want_h = (plan.export.width, plan.export.height)
    add("resolution", (m.get("width"), m.get("height")) == (want_w, want_h) or draft, f"{m.get('width')}x{m.get('height')}")
    add("frame_rate", abs((m.get("fps") or 0) - plan.fps) < 0.6 or draft, f"{m.get('fps')}")
    add("video_codec", m.get("vcodec") in ("h264", "hevc"), m.get("vcodec", ""))
    add("audio_present", m.get("has_audio") or not expect_audio, f"{m.get('acodec')} {m.get('sample_rate')} Hz {m.get('channels')}ch")
    # playable: decode the whole file
    dec = _detect(path, "blackdetect=d=0.5:pix_th=0.06,freezedetect=n=0.002:d=2.0", "silencedetect=n=-55dB:d=2.5,astats=metadata=0:measure_overall=Peak_level")
    add("playable", "Error" not in dec and "Invalid" not in dec, "full decode" if "Error" not in dec else dec[-300:])
    allowed = allowed_static(plan)
    blacks = [iv for iv in _intervals(dec, "black_start", "black_end") if _outside(iv, allowed)]
    add("no_black_frames", not blacks, f"{len(blacks)} unexpected black intervals {blacks[:3]}")
    freezes = [iv for iv in _intervals(dec, "freeze_start", "freeze_end") if _outside(iv, allowed)]
    add("no_frozen_frames", not freezes, f"{len(freezes)} unexpected frozen intervals {freezes[:3]}", severity="warning")
    if m.get("has_audio"):
        sil = [iv for iv in _intervals(dec, "silence_start", "silence_end") if _outside(iv, allowed)]
        add("no_accidental_silence", not sil or not expect_audio, f"{len(sil)} silent stretches {sil[:3]}", severity="warning")
        pk = re.findall(r"Peak level dB:\s*(-?[\d.inf]+)", dec)
        peak = float(pk[-1]) if pk and pk[-1] not in ("-inf",) else -120.0
        add("no_clipping", peak <= -0.1, f"peak {peak:.2f} dBFS")
    add("text_safe_area", not text_violations, f"{len(text_violations or [])} text items outside safe area")
    missing = [s.id for s in plan.timeline if not s.asset_id]
    add("no_missing_clips", not missing, ",".join(missing))
    failures = [c["check"] for c in checks if not c["ok"] and c["severity"] == "error"]
    warnings = [c["check"] for c in checks if not c["ok"] and c["severity"] == "warning"]
    return {"passed": not failures, "checks": checks, "failures": failures, "warnings": warnings, "probe": m,
            "black_intervals": blacks, "frozen_intervals": freezes}
