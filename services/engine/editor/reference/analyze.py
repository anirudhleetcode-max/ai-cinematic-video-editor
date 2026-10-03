"""Reference-video analysis → ReferenceStyleProfile.

Only *style characteristics* are extracted (pacing, colour statistics, motion behaviour, transition
frequency, text placement, music energy). No reference footage is ever used in the output.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .. import db
from ..logging import get_logger, log
from ..media import frames as F
from ..media.analyze import detect_shots
from ..media.probe import probe
from ..music.analyze import analyze_music

logger = get_logger("reference")
VERSION = "ref-v2"


def _dominant_colors(rgb_frames: np.ndarray, k: int = 5) -> list[dict]:
    px = rgb_frames.reshape(-1, 3).astype(np.float32)
    if len(px) > 60000:
        px = px[np.random.default_rng(0).choice(len(px), 60000, replace=False)]
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
    _, labels, centers = cv2.kmeans(px, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k) / len(labels)
    order = np.argsort(-counts)
    return [{"hex": "#%02x%02x%02x" % tuple(int(c) for c in centers[i]), "weight": round(float(counts[i]), 3)} for i in order]


def analyze_reference(path: Path, fingerprint: str | None = None) -> dict:
    if fingerprint:
        hit = db.cache_get(fingerprint, "reference", VERSION)
        if hit:
            return hit
    meta = probe(path)
    sfps = 10.0
    fs = F.sample_frames(path, sfps, 256, meta=meta)
    m = F.frame_metrics(fs)
    shots = detect_shots(m, fs.times, fs.fps, min_shot=0.25)
    dur = meta.get("duration") or (len(fs.times) / sfps)
    lens = np.array([s["end"] - s["start"] for s in shots]) if shots else np.array([dur])
    trans = [s["in_transition"] for s in shots[1:]]
    n_cuts = max(1, len(shots) - 1)
    # camera motion: global translation magnitude and zoom (flow divergence) on a subsample
    zooms, pans = [], []
    for i in range(1, len(fs.rgb), 3):
        a = cv2.cvtColor(fs.rgb[i - 1], cv2.COLOR_RGB2GRAY)
        b = cv2.cvtColor(fs.rgb[i], cv2.COLOR_RGB2GRAY)
        flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        h, w = a.shape
        ys, xs = np.mgrid[0:h, 0:w]
        rx, ry = xs - w / 2, ys - h / 2
        r = np.hypot(rx, ry) + 1e-6
        radial = (flow[..., 0] * rx + flow[..., 1] * ry) / r
        zooms.append(float(radial.mean()))
        pans.append(float(np.hypot(flow[..., 0].mean(), flow[..., 1].mean())))
    zooms_a, pans_a = np.array(zooms or [0.0]), np.array(pans or [0.0])
    # slow motion proxy: repeated (near-identical) consecutive frames despite visible content motion elsewhere
    dup_frames = float((m["motion"][1:] < 0.0008).mean()) if len(m["motion"]) > 1 else 0.0
    # pacing over time (cuts per 10 s) → intro/outro behaviour
    starts = np.array([s["start"] for s in shots])
    bins = np.arange(0, dur + 10, 10)
    cut_hist = np.histogram(starts[1:], bins=bins)[0] if len(starts) > 1 else np.zeros(1)
    # text: sample ~12 frames
    tb = {"top": [], "middle": [], "bottom": []}
    for i in np.linspace(0, len(fs.rgb) - 1, min(12, len(fs.rgb))).astype(int) if len(fs.rgb) else []:
        for k, v in F.text_likelihood(fs.rgb[i]).items():
            tb[k].append(v)
    text = {k: round(float(np.mean(v)) if v else 0.0, 3) for k, v in tb.items()}
    music = analyze_music(path) if meta.get("has_audio") else None
    beat_alignment = None
    if music and music.get("beats") and len(shots) > 2:
        beats = np.array(music["beats"])
        offs = [float(np.min(np.abs(beats - s["start"]))) for s in shots[1:]]
        beat_alignment = round(float(np.mean(np.array(offs) < 0.1)), 3)
    w, h = meta.get("display_width") or 16, meta.get("display_height") or 9
    ar = w / h
    aspect = "9:16" if ar < 0.7 else "4:5" if ar < 0.9 else "1:1" if ar < 1.1 else "16:9"
    profile = {
        "version": VERSION,
        "duration": round(dur, 3),
        "aspect_ratio": aspect,
        "n_shots": len(shots),
        "avg_shot_duration": round(float(lens.mean()), 3),
        "median_shot_duration": round(float(np.median(lens)), 3),
        "shot_length_p10": round(float(np.percentile(lens, 10)), 3),
        "shot_length_p90": round(float(np.percentile(lens, 90)), 3),
        "shot_length_hist": np.histogram(lens, bins=[0, 0.5, 1, 1.5, 2, 3, 4, 6, 10, 1e9])[0].tolist(),
        "cuts_per_minute": round(n_cuts / max(dur, 1e-3) * 60, 2),
        "transition_frequency": round(sum(1 for t in trans if t != "cut") / n_cuts, 3),
        "transition_types": {k: trans.count(k) for k in set(trans)},
        "dominant_colors": _dominant_colors(fs.rgb[:: max(1, len(fs.rgb) // 40)]) if len(fs.rgb) else [],
        "brightness": round(float(m["luma"].mean()), 4),
        "contrast": round(float(m["contrast"].mean()), 4),
        "saturation": round(float(m["sat"].mean()), 4),
        "temperature": round(float(m["temp"].mean()), 4),
        "tint": round(float(m["tint"].mean()), 4),
        "dark_clip": round(float(m["dark_clip"].mean()), 4),
        "bright_clip": round(float(m["bright_clip"].mean()), 4),
        "camera_motion": round(float(pans_a.mean()), 4),
        "zoom_behavior": round(float(np.mean(np.abs(zooms_a))), 4),
        "zoom_in_ratio": round(float((zooms_a > 0.05).mean()), 3),
        "motion_intensity": round(float(m["motion"].mean()), 5),
        "slow_motion_estimate": round(dup_frames, 3),
        "pacing_curve": cut_hist.tolist(),
        "intro_style": "slow_open" if len(cut_hist) > 1 and cut_hist[0] < cut_hist.mean() * 0.7 else "fast_open",
        "outro_style": "fade_out" if len(m["luma"]) > 5 and m["luma"][-3:].mean() < 0.06 else "hard_end",
        "text_presence": text,
        "text_position": max(text, key=text.get) if max(text.values()) > 0.05 else "none",
        "music": {"bpm": music.get("bpm"), "energy_mean": round(float(np.mean(music["energy"])), 3) if music.get("energy") else None,
                  "sections": len(music.get("sections", []))} if music and music.get("ok") else None,
        "beat_alignment": beat_alignment,
        "heuristic_fields": ["text_presence", "text_position", "slow_motion_estimate", "intro_style", "outro_style"],
    }
    if fingerprint:
        db.cache_put(fingerprint, "reference", VERSION, profile)
    log(logger, "reference analyzed", shots=len(shots), cpm=profile["cuts_per_minute"])
    return profile
