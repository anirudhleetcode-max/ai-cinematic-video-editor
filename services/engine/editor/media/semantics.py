"""Shot semantics: detector samples → ShotSemanticProfile.

Every field of the profile carries its provenance:
  measured   — computed directly from pixels / samples (brightness, motion, colours, complexity, speech time)
  model      — produced by a detection model (DeepVisionProvider: YuNet faces, NanoDet COCO objects)
  classic    — produced by OpenCV's classic detectors (Haar faces, HOG people) — no object semantics
  heuristic  — explicit rules over measured values (setting, time of day, shot size, emotional proxy)
  unavailable — no provider in this installation can produce it (e.g. objects without the deep provider)
"""
from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from ..config import get_settings
from .frames import dhash as _dhash
from ..vision import SUBJECT_OF, get_vision_provider, scene_heuristics


def _frame_at(path: Path, meta: dict, t: float, width: int) -> np.ndarray | None:
    from ..render.colorspace import source_to_rgb
    from .frames import _infer_height

    s = get_settings()
    h = _infer_height(meta, width)
    p = subprocess.run([s.ffmpeg, "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", str(path), "-frames:v", "1", "-an",
                        "-vf", source_to_rgb(meta, width, h), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=120)
    if p.returncode != 0 or len(p.stdout) < width * h * 3:
        return None
    return np.frombuffer(p.stdout[: width * h * 3], np.uint8).reshape(h, width, 3)


def sample_detections(path: Path, meta: dict, shots: list[dict], every: float, width: int = 640) -> tuple[list[dict], str]:
    """Run the vision provider on frames every `every` seconds plus each shot's midpoint if it got no grid sample.
    Returns (samples, provider name). Frames are decoded at `width` px — detectors need more than the 192 px
    analysis frames (faces were effectively invisible to the old 192 px Haar pass)."""
    from .frames import sample_frames

    prov = get_vision_provider()
    out: list[dict] = []
    dur = float(meta.get("duration") or 0)
    fs = sample_frames(path, 1.0 / every, width, meta=meta) if dur > every else None
    frames = list(zip(fs.times, fs.rgb)) if fs is not None else []
    have = [False] * len(shots)
    for t, _ in frames:
        for k, sh in enumerate(shots):
            if sh["start"] <= t < sh["end"]:
                have[k] = True
    for k, sh in enumerate(shots):
        if not have[k]:
            fr = _frame_at(path, meta, (sh["start"] + sh["end"]) / 2, width)
            if fr is not None:
                frames.append(((sh["start"] + sh["end"]) / 2, fr))
    for t, fr in sorted(frames, key=lambda x: x[0]):
        v = prov.detect(fr)
        labels = [lbl for lbl, _, _ in v.objects]
        out.append({"t": round(float(t), 3), "faces": [list(map(lambda x: round(x, 4), f)) for f in v.faces[:8]],
                    "objects": [[lbl, sc, [round(x, 4) for x in box]] for lbl, sc, box in v.objects[:24]],
                    "people": v.people, "scene": scene_heuristics(fr, labels), "colors": dominant_colors(fr), "edge_ratio": edge_sharpness(fr),
                    "dhash": str(_dhash(fr))})
    return out, prov.name


def edge_sharpness(rgb: np.ndarray) -> float | None:
    """Content-normalised sharpness: mean |Laplacian| / mean gradient magnitude on the strongest 3 % of edges of a
    ~640 px frame. Blur lowers the ratio regardless of how much texture the scene has (calibrated on real footage:
    defocused 1080p ≈ 0.21, sharp real clips 0.39–0.64). None when the frame has too few edges to judge."""
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    mag = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
    e = mag > max(float(np.percentile(mag, 97)), 20.0)
    if e.sum() < 50:
        return None
    lap = np.abs(cv2.Laplacian(g, cv2.CV_32F, ksize=3))
    return float(lap[e].mean() / mag[e].mean())


def dominant_colors(rgb: np.ndarray, k: int = 3) -> list[dict]:
    small = cv2.resize(rgb, (64, 36), interpolation=cv2.INTER_AREA).reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, lab, cen = cv2.kmeans(small, k, None, crit, 2, cv2.KMEANS_PP_CENTERS)
    cnt = np.bincount(lab.ravel(), minlength=k) / len(lab)
    order = np.argsort(-cnt)
    return [{"hex": "#%02x%02x%02x" % tuple(int(c) for c in cen[i]), "share": round(float(cnt[i]), 3)} for i in order]


def _bell(x: float, mid: float, width: float) -> float:
    return float(np.exp(-((x - mid) / width) ** 2))


def shot_profile(samples: list[dict], provider: str, semantic: bool, metrics: dict, scores: dict, start: float, end: float,
                 camera: dict) -> dict:
    """ShotSemanticProfile (see schemas.ShotSemanticProfile) for one shot."""
    ss = [s for s in samples if start <= s["t"] < end] or ([min(samples, key=lambda s: abs(s["t"] - (start + end) / 2))] if samples else [])
    n = max(1, len(ss))
    face_counts = [len(s["faces"]) for s in ss]
    face_h = [max((f[3] for f in s["faces"]), default=0.0) for s in ss]
    person_h = [max((o[2][3] for o in s["objects"] if o[0] == "person"), default=0.0) for s in ss]
    people = int(np.median([s["people"] for s in ss])) if ss else 0
    subj = Counter()
    for s in ss:
        for cat in {SUBJECT_OF.get(o[0]) for o in s["objects"] if o[1] >= (0.4 if o[0] == "person" else 0.5)} - {None}:
            subj[cat] += 1
        if s["faces"]:
            subj["faces"] += 1
    subjects = [{"label": k, "frequency": round(v / n, 2)} for k, v in subj.most_common() if v / n >= 0.3]
    obj = Counter()
    for s in ss:
        for lab in {o[0] for o in s["objects"] if o[1] >= (0.4 if o[0] == "person" else 0.5)}:
            obj[lab] += 1
    objects = [{"label": k, "frequency": round(v / n, 2)} for k, v in obj.most_common(8) if v / n >= 0.3] if semantic else []
    if people >= 2:
        subjects.append({"label": "group" if people < 6 else "crowd", "frequency": 1.0})
    # shot size from the largest face (or person box) height — standard framing conventions
    fh, ph = float(np.max(face_h)) if face_h else 0.0, float(np.max(person_h)) if person_h else 0.0
    if fh > 0.45:
        size = "extreme_closeup"
    elif fh > 0.2 or ph > 0.95:
        size = "closeup"
    elif fh > 0.08 or ph > 0.55:
        size = "medium"
    elif fh > 0 or ph > 0:
        size = "wide"
    else:
        size = "unknown"  # no subject to measure framing against
    settings = Counter(s["scene"]["setting"] for s in ss)
    tod = Counter(s["scene"]["time_of_day"] for s in ss)
    colors: dict[str, float] = {}
    for s in ss:
        for c in s["colors"]:
            colors[c["hex"]] = colors.get(c["hex"], 0) + c["share"] / n
    complexity = float(np.mean([s["scene"]["edge_density"] for s in ss])) if ss else 0.0
    emotional = float(np.clip(0.55 * min(1.0, fh * 3) + 0.25 * (1 - scores.get("motion_score", 0.5)) + 0.2 * (1.0 if face_counts and max(face_counts) else 0.0), 0, 1))
    det_src = "model" if semantic else "classic"
    return {
        "subjects": subjects,
        "objects": objects,
        "people_count": people,
        "faces": int(max(face_counts)) if face_counts else 0,
        "shot_size": size,
        "scene_type": {"setting": settings.most_common(1)[0][0] if settings else "unknown", "time_of_day": tod.most_common(1)[0][0] if tod else "unknown"},
        "camera_motion": camera,
        "dominant_colors": [{"hex": k, "share": round(v, 3)} for k, v in sorted(colors.items(), key=lambda kv: -kv[1])[:3]],
        "brightness": metrics.get("luma"),
        "energy": scores.get("energy_score"),
        "visual_complexity": round(complexity, 3),
        "composition": scores.get("composition_score"),
        "emotional_proxy": round(emotional, 3),
        "speech_presence": round(min(1.0, metrics.get("speech_seconds", 0) / max(1e-3, end - start)), 3),
        "technical_quality": scores.get("quality_score"),
        "orientation": None,
        "samples": len(ss),
        "provider": provider,
        "provenance": {"subjects": det_src if semantic else "classic (faces/people only; objects unavailable)",
                       "objects": "model (COCO-80 detector classes)" if semantic else "unavailable (deep vision models not installed)", "people_count": det_src,
                       "faces": det_src, "shot_size": "heuristic", "scene_type": "heuristic", "camera_motion": "measured",
                       "dominant_colors": "measured", "brightness": "measured", "energy": "measured", "visual_complexity": "measured",
                       "composition": "measured", "emotional_proxy": "heuristic (face size + stillness; not emotion recognition)",
                       "speech_presence": "measured", "technical_quality": "measured"},
    }


def camera_motion(metrics: dict, stability: float, reliable: bool) -> dict:
    pan, tilt, motion = metrics.get("pan_px", 0.0), metrics.get("tilt_px", 0.0), metrics.get("motion", 0.0)
    if not reliable:
        kind = "unknown"
    elif stability < 0.45:
        kind = "handheld_shaky"
    elif abs(pan) > 15 or abs(tilt) > 15:
        kind = "pan" if abs(pan) >= abs(tilt) else "tilt"
    elif motion < 0.004:
        kind = "static"
    else:
        kind = "static_with_subject_motion" if stability > 0.8 else "handheld"
    return {"type": kind, "pan_px": pan, "tilt_px": tilt}
