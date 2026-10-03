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
VERSION = "ref-v13"  # v3: adaptive cut detection, colour-correct sampling


def _dominant_colors(rgb_frames: np.ndarray, k: int = 5) -> list[dict]:
    px = rgb_frames.reshape(-1, 3).astype(np.float32)
    if len(px) > 60000:
        px = px[np.random.default_rng(0).choice(len(px), 60000, replace=False)]
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
    _, labels, centers = cv2.kmeans(px, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k) / len(labels)
    order = np.argsort(-counts)
    return [{"hex": "#%02x%02x%02x" % tuple(int(c) for c in centers[i]), "weight": round(float(counts[i]), 3)} for i in order]


def grade_profile(frames: np.ndarray) -> dict:
    """ReferenceGradeProfile: measurable look of a set of RGB frames — luma distribution, saturation distribution,
    shadow / highlight colour casts, dominant hue. These numbers drive the grade mapping onto the user's footage."""
    if not len(frames):
        return {}
    px = np.concatenate([cv2.resize(f, (96, 54), interpolation=cv2.INTER_AREA).reshape(-1, 3) for f in frames]).astype(np.float32) / 255
    luma = px @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mx, mn = px.max(1), px.min(1)
    sat = np.where(mx > 1e-3, (mx - mn) / np.maximum(mx, 1e-3), 0)

    def cast(mask: np.ndarray) -> dict:
        if mask.sum() < 50:
            return {"temperature": 0.0, "tint": 0.0, "share": round(float(mask.mean()), 3)}
        c = px[mask].mean(0)
        return {"temperature": round(float(c[0] - c[2]), 4), "tint": round(float(c[1] - (c[0] + c[2]) / 2), 4), "share": round(float(mask.mean()), 3),
                "rgb": [round(float(x), 3) for x in c]}

    hsv = cv2.cvtColor((px.reshape(1, -1, 3) * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).reshape(-1, 3).astype(np.float32)
    w = hsv[:, 1] / 255 * (hsv[:, 2] / 255)
    ang = hsv[:, 0] / 180 * 2 * np.pi
    hue = (np.degrees(np.arctan2((w * np.sin(ang)).sum(), (w * np.cos(ang)).sum())) % 360) if w.sum() > 1 else None
    return {"luma_p5": round(float(np.percentile(luma, 5)), 4), "luma_p50": round(float(np.percentile(luma, 50)), 4),
            "luma_p95": round(float(np.percentile(luma, 95)), 4), "contrast_spread": round(float(np.percentile(luma, 95) - np.percentile(luma, 5)), 4),
            "saturation_p50": round(float(np.percentile(sat, 50)), 4), "saturation_p90": round(float(np.percentile(sat, 90)), 4),
            "shadows": cast(luma < 0.25), "midtones": cast((luma >= 0.25) & (luma <= 0.7)), "highlights": cast(luma > 0.7),
            "dominant_hue_deg": round(float(hue), 1) if hue is not None else None,
            "warmth": round(float((px[:, 0] - px[:, 2]).mean()), 4)}


def _text_timeline(fs, sfps: float) -> list[dict]:
    """Heuristic on-screen text intervals (band + relative size) from the stroke-density detector, ~2 samples/s."""
    step = max(1, int(round(sfps / 2)))
    present = []
    for i in range(0, len(fs.rgb), step):
        tl = F.text_likelihood(fs.rgb[i])
        band = max(tl, key=tl.get)
        present.append((float(fs.times[i]), band if tl[band] > 0.12 else None, tl[band]))
    events, cur = [], None
    for t, band, sc in present:
        if band and (cur is None or cur["band"] != band):
            if cur:
                events.append(cur)
            cur = {"start": round(t, 2), "end": round(t + 0.5, 2), "band": band, "coverage": round(sc, 3)}
        elif band and cur:
            cur["end"] = round(t + 0.5, 2)
            cur["coverage"] = round(max(cur["coverage"], sc), 3)
        elif not band and cur:
            events.append(cur)
            cur = None
    if cur:
        events.append(cur)
    return [e for e in events if e["end"] - e["start"] >= 1.0][:50]


def _light_music(path: Path) -> dict:
    """Music energy curve exactly as music.analyze defines it (RMS dB → 0..1 at 2 Hz), without beat tracking."""
    import librosa

    from ..media.audio import load_mono

    y = load_mono(path, sr=22050)
    if y.size < 22050:
        return {"ok": False}
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=22050, hop_length=512)
    grid = np.arange(0, len(y) / 22050, 0.5)
    e = np.interp(grid, t, librosa.amplitude_to_db(rms, ref=np.max))
    e = (e - e.min()) / (e.max() - e.min() + 1e-9)
    return {"ok": True, "bpm": None, "energy": [float(v) for v in e], "sections": [], "beats": []}


def analyze_reference(path: Path, fingerprint: str | None = None, sample_fps: float = 10.0, light: bool = False) -> dict:
    """light=True (used to measure our own outputs for the Reference Match Report): lower sampling rate, music energy from
    RMS only (no beat tracking), fewer optical-flow samples. Same measurement definitions, cheaper."""
    if fingerprint:
        hit = db.cache_get(fingerprint, "reference", VERSION)
        if hit:
            return hit
    meta = probe(path)
    sfps = sample_fps
    fs = F.sample_frames(path, sfps, 256, meta=meta)
    m = F.frame_metrics(fs)
    shots = detect_shots(m, fs.times, fs.fps, min_shot=0.25, frames=fs.rgb)
    dur = meta.get("duration") or (len(fs.times) / sfps)
    lens = np.array([s["end"] - s["start"] for s in shots]) if shots else np.array([dur])
    trans = [s["in_transition"] for s in shots[1:]]
    n_cuts = max(1, len(shots) - 1)
    # camera motion: global translation magnitude and zoom (flow divergence) on a subsample
    zooms, pans = [], []
    for i in range(1, len(fs.rgb), 3 if not light else 12):
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
    music = (_light_music(path) if light else analyze_music(path)) if meta.get("has_audio") else None
    beat_alignment = None
    if music and music.get("beats") and len(shots) > 2:
        beats = np.array(music["beats"])
        offs = [float(np.min(np.abs(beats - s["start"]))) for s in shots[1:]]
        beat_alignment = round(float(np.mean(np.array(offs) < 0.1)), 3)
    grade = grade_profile(fs.rgb[:: max(1, len(fs.rgb) // 60)]) if len(fs.rgb) else {}
    # intro / outro: first and last shot lengths and measured fade-in / fade-out (luma ramps from/to black)
    lum = m["luma"]
    fade_in = 0.0
    if len(lum) > 3 and lum[0] < 0.08:
        k = int(np.argmax(lum > 0.5 * float(np.median(lum))))
        fade_in = round(float(fs.times[k] - fs.times[0]), 2)
    fade_out = 0.0
    if len(lum) > 3 and lum[-1] < 0.08:
        k = len(lum) - 1 - int(np.argmax(lum[::-1] > 0.5 * float(np.median(lum))))
        fade_out = round(float(fs.times[-1] - fs.times[k]), 2)
    # text timing + size (heuristic detector) at ~2 samples/s
    text_events = _text_timeline(fs, sfps)
    # audio dynamics (measured on the reference's own soundtrack)
    dyn = None
    if meta.get("has_audio"):
        from ..media.audio import load_mono

        ya = load_mono(path, sr=16000)
        if ya.size > 16000:
            fr = ya[: len(ya) // 1600 * 1600].reshape(-1, 1600)
            rdb = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
            act = rdb[rdb > -60]
            if act.size:
                dyn = {"rms_p10_db": round(float(np.percentile(act, 10)), 1), "rms_p95_db": round(float(np.percentile(act, 95)), 1),
                       "dynamic_range_db": round(float(np.percentile(act, 95) - np.percentile(act, 10)), 1)}
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
        "grade": grade,
        "first_shot_seconds": round(float(lens[0]), 3) if len(lens) else None,
        "last_shot_seconds": round(float(lens[-1]), 3) if len(lens) else None,
        "fade_in_seconds": fade_in, "fade_out_seconds": fade_out,
        "text_events": text_events,
        "audio_dynamics": dyn,
        "heuristic_fields": ["text_presence", "text_position", "text_events", "slow_motion_estimate", "intro_style", "outro_style"],
        "provenance": {
            "measured": ["duration", "n_shots", "avg_shot_duration", "median_shot_duration", "shot_length_p10", "shot_length_p90", "shot_length_hist",
                         "cuts_per_minute", "pacing_curve", "brightness", "contrast", "saturation", "temperature", "tint", "dark_clip", "bright_clip",
                         "grade", "dominant_colors", "camera_motion", "zoom_behavior", "motion_intensity", "first_shot_seconds", "last_shot_seconds",
                         "fade_in_seconds", "fade_out_seconds", "music", "beat_alignment", "audio_dynamics"],
            "inferred": ["transition_frequency", "transition_types", "intro_style", "outro_style", "slow_motion_estimate", "text_presence",
                         "text_position", "text_events"],
            "unavailable": ["font identity", "exact text content", "exact LUT / grading operations", "speed-ramp curves", "per-shot effects"],
            "notes": "transitions are classified from frame statistics (cut / fade / dissolve), not from edit metadata; text is a stroke-density "
                     "heuristic (no OCR); slow motion is estimated from repeated frames",
        },
    }
    if fingerprint:
        db.cache_put(fingerprint, "reference", VERSION, profile)
    log(logger, "reference analyzed", shots=len(shots), cpm=profile["cuts_per_minute"])
    return profile
