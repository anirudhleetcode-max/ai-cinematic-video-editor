"""Media Intelligence Pipeline for video clips.

metadata → frame sampling → per-frame metrics → shot boundaries → per-shot scores → tags.
Results are cached by content fingerprint + analyzer version, so a file is never analyzed twice.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .. import db
from ..logging import get_logger, log
from . import frames as F
from .audio import analyze_audio
from .probe import probe

logger = get_logger("analyze")
VERSION = "video-v6"  # v6: rotation/SAR/matrix/HDR-correct frame sampling

MODES = {
    # sample fps, analysis width, face/person sampling interval (s)
    "fast": (4.0, 192, 2.0),
    "quality": (8.0, 320, 0.75),
    "emergency": (2.0, 160, 0.0),
}


def detect_shots(m: dict[str, np.ndarray], times: np.ndarray, fps: float, min_shot: float = 0.6) -> list[dict]:
    """Hard cuts: histogram distance spikes above an adaptive threshold.
    Gradual transitions (fades/dissolves): sustained run of moderate distances or luma ramps to/from black."""
    n = len(times)
    if n == 0:
        return []
    d = m["hist_d"]
    med = float(np.median(d[1:])) if n > 2 else 0.0
    mad = float(np.median(np.abs(d[1:] - med))) if n > 2 else 0.0
    thr = max(0.28, med + 8 * mad)
    cuts: list[tuple[int, str]] = []
    last = 0
    for i in range(1, n):
        if d[i] > thr and (times[i] - times[last]) >= min_shot:
            cuts.append((i, "cut"))
            last = i
    # gradual: luma passing through near-black (dip / fade) not already a cut
    lum = m["luma"]
    i = 1
    while i < n - 1:
        if lum[i] < 0.04 and lum[i - 1] >= 0.04:
            j = i
            while j < n - 1 and lum[j] < 0.04:
                j += 1
            mid = (i + j) // 2
            if all(abs(times[mid] - times[c]) > min_shot for c, _ in cuts):
                cuts.append((mid, "fade"))
            i = j
        i += 1
    # dissolve: window of 3+ moderate distances whose sum exceeds the cut threshold
    win = max(3, int(round(fps * 0.6)))
    for i in range(1, n - win):
        seg = d[i:i + win]
        if seg.sum() > thr * 1.6 and seg.max() < thr and seg.min() > med + 2 * mad + 0.02:
            c = i + win // 2
            if all(abs(times[c] - times[k]) > min_shot for k, _ in cuts):
                cuts.append((c, "dissolve"))
    cuts.sort()
    bounds = [0] + [c for c, _ in cuts] + [n]
    kinds = ["start"] + [k for _, k in cuts]
    shots = []
    for k in range(len(bounds) - 1):
        a, b = bounds[k], bounds[k + 1]
        if b <= a:
            continue
        shots.append({"i0": a, "i1": b, "start": float(times[a]), "end": float(times[b - 1] + 1 / fps), "in_transition": kinds[k]})
    return shots


def _norm(x: float, lo: float, hi: float) -> float:
    return float(np.clip((x - lo) / (hi - lo + 1e-9), 0, 1))


def score_shot(m: dict, a: int, b: int, faces: list[dict], audio: dict, start: float, end: float, composition: float) -> dict:
    sl = slice(a, b)
    luma, contrast = float(m["luma"][sl].mean()), float(m["contrast"][sl].mean())
    sharp = float(np.median(m["sharp"][sl]))
    dark, bright = float(m["dark_clip"][sl].mean()), float(m["bright_clip"][sl].mean())
    motion = float(m["motion"][sl][1:].mean()) if b - a > 1 else 0.0
    dx, dy = m["dx"][sl], m["dy"][sl]
    # shake = high-frequency jitter of the global (median optical-flow) translation, normalised to a
    # 192px-wide, 4 fps sampling grid. Only frames with enough texture to measure motion count.
    tex = m["pc_resp"][sl] > 0
    reliable = b - a > 3 and float(tex[1:].mean()) >= 0.5
    if reliable:
        j2 = np.abs(np.diff(dx, 2)) + np.abs(np.diff(dy, 2))
        valid = tex[2:] & tex[1:-1]
        jitter = float(j2[valid].mean()) if valid.any() else 0.0
        jitter *= (192.0 / m["_width"]) * (m["_fps"] / 4.0) ** 0.5
    else:
        jitter = 0.0
    pan = float(np.sum(dx[1:])) if b - a > 1 else 0.0
    tilt = float(np.sum(dy[1:])) if b - a > 1 else 0.0
    black_ratio = float((m["luma"][sl] < 0.03).mean())
    frozen_ratio = float((m["motion"][sl][1:] < 0.0005).mean()) if b - a > 2 else 0.0
    sat, colorful = float(m["sat"][sl].mean()), float(m["colorful"][sl].mean())
    face_frac = float(np.mean([1.0 if f["n"] else 0.0 for f in faces])) if faces else 0.0
    face_size = float(np.mean([f["max_area"] for f in faces])) if faces else 0.0
    people = float(np.mean([f.get("people", 0) for f in faces])) if faces else 0.0
    sp = [s for s in audio.get("speech", []) if s[1] > start and s[0] < end]
    speech_t = sum(min(e, end) - max(s, start) for s, e in sp)
    dur = max(1e-3, end - start)

    sharpness = _norm(np.log10(sharp + 1), 1.3, 2.7)
    exposure = float(np.clip(1 - abs(luma - 0.47) / 0.4, 0, 1) * (1 - min(1, 3 * (dark + bright))))
    contrast_s = float(np.clip(1 - abs(contrast - 0.22) / 0.2, 0, 1))
    stability = float(np.clip(1 - (jitter - 1.0) / 5.0, 0, 1)) if reliable else 0.75
    motion_s = _norm(motion, 0.003, 0.06)
    face_vis = float(np.clip(face_frac * (0.5 + 4 * face_size), 0, 1))
    audio_s = float(np.clip(audio.get("energy", 0) * (1 - 50 * audio.get("clipping", 0)), 0, 1)) if audio.get("has_audio") else 0.0
    energy = float(np.clip(0.55 * motion_s + 0.25 * audio_s + 0.2 * _norm(colorful, 0.1, 0.5), 0, 1))
    emotional = float(np.clip(0.5 * face_vis + 0.25 * (1 - motion_s) + 0.25 * _norm(face_size, 0.02, 0.15), 0, 1))
    quality = float(np.clip(0.4 * sharpness + 0.3 * exposure + 0.15 * stability + 0.15 * contrast_s, 0, 1))
    cinematic = float(np.clip(0.3 * contrast_s + 0.25 * stability + 0.25 * composition + 0.2 * _norm(sat, 0.15, 0.55), 0, 1))
    issues = []
    if sharpness < 0.3:
        issues.append("blurry")
    if luma < 0.15 or dark > 0.4:
        issues.append("underexposed")
    if luma > 0.85 or bright > 0.35:
        issues.append("overexposed")
    if stability < 0.45:
        issues.append("shaky")
    if black_ratio > 0.5:
        issues.append("black")
    if frozen_ratio > 0.9 and dur > 1.0:
        issues.append("frozen")
    if dur < 0.5:
        issues.append("too_short")
    tags = []
    tags.append("closeup" if face_size > 0.06 else ("medium" if face_size > 0.015 else "wide"))
    if face_frac > 0.3:
        tags.append("faces")
    if people >= 3 or (face_frac > 0.3 and np.mean([f["n"] for f in faces]) >= 3):
        tags.append("crowd")
    if people >= 1:
        tags.append("people")
    tags.append("high_motion" if motion_s > 0.6 else ("static" if motion_s < 0.15 else "moving"))
    if abs(pan) > 15:
        tags.append("pan_right" if pan < 0 else "pan_left")
    if speech_t / dur > 0.3:
        tags.append("speech")
    tags.append("bright" if luma > 0.6 else ("dark" if luma < 0.3 else "midtone"))
    if colorful > 0.35:
        tags.append("colorful")
    return {
        "start": round(start, 3), "end": round(end, 3), "duration": round(dur, 3),
        "metrics": {
            "luma": round(luma, 4), "contrast": round(contrast, 4), "laplacian_var": round(sharp, 2), "dark_clip": round(dark, 4),
            "bright_clip": round(bright, 4), "motion": round(motion, 5), "jitter": round(jitter, 4), "pan_px": round(pan, 2),
            "tilt_px": round(tilt, 2), "saturation": round(sat, 4), "colorfulness": round(colorful, 4), "black_ratio": round(black_ratio, 3),
            "frozen_ratio": round(frozen_ratio, 3), "temperature": round(float(m["temp"][sl].mean()), 4),
            "tint": round(float(m["tint"][sl].mean()), 4), "face_fraction": round(face_frac, 3), "face_area": round(face_size, 4),
            "people": round(people, 2), "speech_seconds": round(speech_t, 2),
        },
        "scores": {
            "quality_score": round(quality, 3), "sharpness_score": round(sharpness, 3), "composition_score": round(composition, 3),
            "motion_score": round(motion_s, 3), "exposure_score": round(exposure, 3), "face_visibility_score": round(face_vis, 3),
            "audio_score": round(audio_s, 3), "emotional_score": round(emotional, 3), "energy_score": round(energy, 3),
            "stability_score": round(stability, 3), "cinematic_score": round(cinematic, 3),
            "uniqueness_score": 1.0,  # set at project level by `apply_uniqueness`
        },
        "issues": issues,
        "tags": tags,
    }


def overall(scores: dict, issues: list[str]) -> float:
    s = (0.28 * scores["quality_score"] + 0.14 * scores["cinematic_score"] + 0.12 * scores["energy_score"]
         + 0.1 * scores["emotional_score"] + 0.1 * scores["composition_score"] + 0.1 * scores["uniqueness_score"]
         + 0.08 * scores["face_visibility_score"] + 0.08 * scores["stability_score"])
    penalty = {"blurry": 0.35, "underexposed": 0.25, "overexposed": 0.25, "shaky": 0.2, "black": 0.6, "frozen": 0.3, "too_short": 0.15}
    for i in issues:
        s -= penalty.get(i, 0.1)
    return round(float(np.clip(s, 0, 1)), 3)


def analyze_video(path: Path, mode: str = "fast", fingerprint: str | None = None) -> dict:
    """Full analysis of one clip (cached)."""
    if fingerprint:
        hit = db.cache_get(fingerprint, "video", f"{VERSION}:{mode}")
        if hit:
            return hit
    meta = probe(path)
    sfps, width, face_every = MODES.get(mode, MODES["fast"])
    fs = F.sample_frames(path, sfps, width, meta=meta)
    m = F.frame_metrics(fs)
    m["_width"], m["_fps"] = width, sfps
    audio = analyze_audio(path) if meta.get("has_audio") else {"has_audio": False, "speech": [], "silence": []}
    shots_raw = detect_shots(m, fs.times, fs.fps)
    # faces/people sampled at intervals (detection on a larger frame for reliability)
    face_samples: list[dict] = []
    if face_every > 0 and len(fs.rgb):
        step = max(1, int(round(face_every * sfps)))
        for i in range(0, len(fs.rgb), step):
            fr = fs.rgb[i]
            boxes = F.detect_faces(fr)
            area = max((w * h for _, _, w, h in boxes), default=0) / (fr.shape[0] * fr.shape[1])
            ppl = F.detect_people(fr) if mode == "quality" else 0
            face_samples.append({"t": float(fs.times[i]), "n": len(boxes), "max_area": area, "people": ppl,
                                 "boxes": [[round(x / fr.shape[1], 3), round(y / fr.shape[0], 3), round(w / fr.shape[1], 3), round(h / fr.shape[0], 3)] for x, y, w, h in boxes[:4]]})
    shots = []
    for k, sh in enumerate(shots_raw):
        a, b = sh["i0"], sh["i1"]
        fsamp = [f for f in face_samples if sh["start"] <= f["t"] < sh["end"]]
        mid = (a + b) // 2
        comp = F.composition_score(fs.rgb[mid]) if len(fs.rgb) else 0.0
        sc = score_shot(m, a, b, fsamp, audio, sh["start"], min(sh["end"], meta["duration"] or sh["end"]), comp)
        # best moment inside the shot: sharp + some motion, avoid edges
        inner = slice(a + (b - a) // 6, max(a + (b - a) // 6 + 1, b - (b - a) // 6))
        best_i = a + (b - a) // 6 + int(np.argmax(m["sharp"][inner] * (0.5 + m["motion"][inner] * 20))) if b - a > 2 else a
        sc.update(
            index=k, in_transition=sh["in_transition"], best_moment=round(float(fs.times[min(best_i, len(fs.times) - 1)]), 3),
            dhash=str(F.dhash(fs.rgb[mid])), hist=[round(float(x), 5) for x in m["hists"][mid]],
            faces=[f["boxes"] for f in fsamp if f["boxes"]][:1],
            text_bands=F.text_likelihood(fs.rgb[mid]),
        )
        sc["overall_edit_score"] = overall(sc["scores"], sc["issues"])
        shots.append(sc)
    result = {
        "version": VERSION, "mode": mode, "meta": meta, "audio": audio, "shots": shots,
        "summary": {
            "n_shots": len(shots),
            "mean_luma": round(float(m["luma"].mean()), 4) if len(fs.rgb) else 0,
            "mean_saturation": round(float(m["sat"].mean()), 4) if len(fs.rgb) else 0,
            "mean_temperature": round(float(m["temp"].mean()), 4) if len(fs.rgb) else 0,
            "mean_tint": round(float(m["tint"].mean()), 4) if len(fs.rgb) else 0,
            "mean_contrast": round(float(m["contrast"].mean()), 4) if len(fs.rgb) else 0,
            "best_score": max((s["overall_edit_score"] for s in shots), default=0),
            "usable_shots": sum(1 for s in shots if not s["issues"]),
        },
    }
    if fingerprint:
        db.cache_put(fingerprint, "video", f"{VERSION}:{mode}", result)
    log(logger, "analyzed video", file=path.name, shots=len(shots), mode=mode)
    return result


def apply_uniqueness(analyses: dict[str, dict], dup_bits: int = 6) -> list[list[str]]:
    """Project-level duplicate / near-duplicate detection across every shot of every clip.
    Uses perceptual hash Hamming distance + colour-histogram similarity. Mutates uniqueness scores.
    Returns groups of duplicate shot keys ("asset_id:shot_index")."""
    items = []
    for aid, an in analyses.items():
        for sh in an.get("shots", []):
            items.append((f"{aid}:{sh['index']}", int(sh["dhash"]), np.array(sh["hist"], np.float32), sh))
    groups: dict[str, list[str]] = {}
    for i, (ki, hi, Hi, shi) in enumerate(items):
        best = 0.0
        for j, (kj, hj, Hj, _) in enumerate(items):
            if i == j:
                continue
            hsim = 1 - F.hamming(hi, hj) / 64
            csim = 1 - 0.5 * float(np.abs(Hi - Hj).sum())
            sim = 0.6 * hsim + 0.4 * csim
            best = max(best, sim)
            if F.hamming(hi, hj) <= dup_bits and csim > 0.85 and j > i:
                groups.setdefault(ki, [ki]).append(kj)
        shi["scores"]["uniqueness_score"] = round(float(np.clip((1 - best) * 3, 0, 1)), 3)
        shi["similarity_max"] = round(best, 3)
        shi["overall_edit_score"] = overall(shi["scores"], shi["issues"])
    dups = list(groups.values())
    dup_set = {k for g in dups for k in g[1:]}
    for k, _, _, sh in items:
        sh["duplicate_of"] = next((g[0] for g in dups if k in g[1:]), None)
        if k in dup_set and "duplicate" not in sh["issues"]:
            sh["issues"].append("duplicate")
            sh["overall_edit_score"] = overall(sh["scores"], sh["issues"])
    return dups
