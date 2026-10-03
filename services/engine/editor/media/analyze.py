"""Media Intelligence Pipeline for video clips.

metadata → frame sampling → per-frame metrics → shot boundaries → per-shot scores → tags.
Results are cached by content fingerprint + analyzer version, so a file is never analyzed twice.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .. import db
from ..logging import get_logger, log
from . import frames as F
from .audio import analyze_audio
from .probe import probe
from .semantics import camera_motion, sample_detections, shot_profile

logger = get_logger("analyze")
VERSION = "video-v20"  # v7: correct colour/geometry sampling, vision provider, semantic profile, usability/creative scores

MODES = {
    # sample fps, analysis width, face/person sampling interval (s)
    "fast": (4.0, 192, 2.0),
    "quality": (8.0, 320, 0.75),
    "emergency": (2.0, 160, 0.0),
}


def _blend_fit(frames: np.ndarray, i0: int, i1: int, sharp: np.ndarray | None = None) -> tuple[bool, int]:
    """Is frames[i0+1 .. i1-1] a cross-dissolve from frames[i0] to frames[i1]?  Each interior frame (8×8-block luma)
    is fitted as (1-a)*pre + a*post. A dissolve fits with a blend weight `a` that rises steadily through intermediate
    values; a hard cut only has a≈0 or 1; camera / subject motion fits badly or gives flat / jumping weights.
    Calibrated on real footage (release check C): a real 1 s dissolve rises 0.14→0.86 with residual 0.24; walking
    people give flat weights (residual 1.2) or a jump to 1.0. Returns (is_dissolve, intermediate frames)."""
    n = len(frames)
    i0, i1 = max(0, i0), min(n - 1, i1)
    if i1 - i0 < 3:
        return False, 0
    h, w = frames.shape[1:3]
    bs = 8
    H, W = h // bs * bs, w // bs * bs

    def g(k: int) -> np.ndarray:
        return frames[k, :H, :W].astype(np.float32).mean(axis=2).reshape(H // bs, bs, W // bs, bs).mean(axis=(1, 3))

    pre, post = g(i0), g(i1)
    span = post - pre
    den = float((span * span).sum())
    if den <= 0 or float(np.abs(span).mean()) < 10.0:  # endpoints too similar to tell a blend from anything else
        return False, 0
    alphas, res = [], []
    for k in range(i0 + 1, i1):
        f = g(k)
        a = float(np.clip(((f - pre) * span).sum() / den, 0.0, 1.0))
        r = f - (pre + a * span)
        res.append(float(np.sqrt((r * r).mean())) / (float(np.sqrt(den / span.size)) + 1e-6))
        alphas.append(a)
    mids = sum(0.1 < a < 0.9 for a in alphas)
    inner = [a for a in alphas if 0.05 < a < 0.95]
    rising = len(inner) >= 3 and all(b - a > 0.02 for a, b in zip(inner, inner[1:]))
    coverage = float((np.abs(span) > 12).mean())  # a dissolve replaces the whole picture; a walking subject does not
    if not (float(np.mean(res)) < 0.45 and rising and mids >= 3 and coverage >= 0.5):
        return False, mids
    if sharp is not None and len(sharp) == n:
        # a whip pan / fast camera swing smears the picture (sharpness collapses below both ends); a dissolve overlays
        # two sharp pictures (sharpness stays between them)
        ends = min(float(sharp[i0]), float(sharp[i1]))
        if ends > 0 and float(np.min(sharp[i0 + 1:i1])) < 0.5 * ends:
            return False, mids
    # the two endpoints must be different pictures: same-scene motion (pan, moving car, head turn) keeps its edge
    # structure under a shift (measured 0.63–0.89), two different shots do not (real dissolve ≤ 0.18)
    return _edge_similarity(frames[i0], frames[i1]) < 0.45, mids


def _active_span(d: np.ndarray, lo: int, hi: int, floor: float) -> tuple[int, int]:
    """Extend a transition window outwards while consecutive frames keep changing (distance above the noise floor)."""
    n = len(d)
    lo, hi = max(0, lo), min(n - 1, hi)
    while lo > 0 and d[lo] > floor:
        lo -= 1
    while hi < n - 1 and d[hi + 1] > floor:
        hi += 1
    return lo, hi


def _edge_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Best correlation of 4×4-max-pooled gradient magnitude over shifts of ±8 pooled cells (±32 px at 256 px).
    Real footage (release check C): same-scene motion 0.63–0.76 (moving car, head turn), real dissolve ≤ 0.18."""
    def edges(img: np.ndarray) -> np.ndarray:
        g = img.astype(np.float32).mean(axis=2)
        e = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
        hh, ww = e.shape[0] // 4 * 4, e.shape[1] // 4 * 4
        return e[:hh, :ww].reshape(hh // 4, 4, ww // 4, 4).max(axis=(1, 3))

    e0, e1 = edges(a), edges(b)
    best = -1.0
    for dy in range(-8, 9):
        for dx in range(-8, 9):
            x0 = e0[max(0, dy):e0.shape[0] + min(0, dy), max(0, dx):e0.shape[1] + min(0, dx)].ravel()
            x1 = e1[max(0, -dy):e1.shape[0] + min(0, -dy), max(0, -dx):e1.shape[1] + min(0, -dx)].ravel()
            if x0.std() > 0 and x1.std() > 0:
                best = max(best, float(np.corrcoef(x0, x1)[0, 1]))
    return best


def detect_shots(m: dict[str, np.ndarray], times: np.ndarray, fps: float, min_shot: float = 0.6, frames: np.ndarray | None = None) -> list[dict]:
    """Hard cuts: histogram distance spikes above an adaptive threshold.
    Gradual transitions (fades/dissolves): sustained run of moderate distances or luma ramps to/from black."""
    n = len(times)
    if n == 0:
        return []
    d = m["hist_d"]
    d2 = m.get("struct_d", np.zeros(n, np.float32))
    med = float(np.median(d[1:])) if n > 2 else 0.0
    mad = float(np.median(np.abs(d[1:] - med))) if n > 2 else 0.0
    thr = max(0.28, med + 8 * mad)
    # Hard cuts = an ISOLATED spike in both colour-histogram change and exposure-invariant structure change, relative to
    # the local neighbourhood (±6 samples incl. immediate neighbours). Continuous fast motion (a car crossing, a person
    # passing the lens) changes every frame and is not a spike; an auto-exposure step changes colour but not structure.
    # Calibrated on real footage (docs/REAL_FOOTAGE_HARDENING.md): 23/29 known cuts vs 13/29 for a global threshold.
    cuts: list[tuple[int, str]] = []
    last = 0
    for i in range(1, n):
        nb = [j for j in range(max(1, i - 6), min(n, i + 7)) if j != i]
        b1 = float(np.median(d[nb])) if nb else 0.0
        b2 = float(np.median(d2[nb])) if nb else 0.0
        locmax = d[i] >= d[max(1, i - 1):i + 2].max()
        strong = d[i] > thr and d[i] > 2 * b1
        spike = d[i] > max(0.07, 4 * b1) and d2[i] > max(0.05, 2 * b2)
        if locmax and (strong or spike) and (times[i] - times[last]) >= min_shot:
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
            k = max(1, int(round(fps)))
            dip = float(lum[i:j].min()) if j > i else float(lum[i])
            # a real dip comes from (or goes to) clearly brighter picture; footage that merely hovers around the
            # near-black threshold is a dark shot, not a fade
            brighter = max(float(lum[max(0, i - k):i].max(initial=0)), float(lum[j:min(n, j + k)].max(initial=0)))
            if brighter >= max(0.08, 3 * dip) and all(abs(times[mid] - times[c]) > min_shot for c, _ in cuts):
                cuts.append((mid, "fade"))
            i = j
        i += 1
    # a hard boundary that is really a fade: luma ramps monotonically up from (or down to) near-black across it
    # ("cut to black, fade up"). A cut between a bright and a dark shot is a single step, not a ramp.
    for k, (c, kind) in enumerate(cuts):
        if kind != "cut":
            continue
        up = lum[max(0, c - 3):min(n, c + 3)]
        lo = int(np.argmin(up))
        rise = up[lo:]
        fall = up[:lo + 1]
        ramp_up = up[lo] <= 0.06 and len(rise) >= 3 and bool(np.all(np.diff(rise[:4]) > 0.01)) and rise[min(3, len(rise) - 1)] >= 3 * max(up[lo], 0.01)
        ramp_dn = up[lo] <= 0.06 and len(fall) >= 3 and bool(np.all(np.diff(fall[-4:]) < -0.01)) and fall[-min(4, len(fall))] >= 3 * max(up[lo], 0.01)
        if ramp_up or ramp_dn:
            cuts[k] = (c, "fade")
    # one fade through black is one transition: boundaries on the same luma ramp down to / up from the dip merge into
    # the darkest one
    merged: list[tuple[int, str]] = []
    for c, kind in sorted(cuts):
        if merged and kind == "fade" and merged[-1][1] == "fade":
            p = merged[-1][0]
            seg_l = lum[p:c + 1]
            # same ramp if the luma between the two boundaries never rises back above the brighter of them by much
            if c - p <= 2 * max(1, int(round(fps))) and float(seg_l.min()) <= 0.06 and float(seg_l.max()) <= max(lum[p], lum[c]) + 0.02:
                merged[-1] = (p if lum[p] <= lum[c] else c, "fade")
                continue
        merged.append((c, kind))
    cuts = merged
    # dissolve: window of moderate distances whose sum exceeds the cut threshold — and, when frames are available,
    # the frames inside it must actually be a steadily rising blend of the frames around it (continuous motion is not
    # a dissolve); with that proof the window only needs a sustained median change, not a minimum at every sample
    win = max(3, int(round(fps * 0.6)))
    last_dissolve_end = -1
    spans: list[tuple[int, int]] = []  # sample ranges covered by a gradual transition
    for i in range(1, n - win):
        if i <= last_dissolve_end:  # one dissolve, not one per overlapping window
            continue
        seg = d[i:i + win]
        sustained = (float(np.median(seg)) if frames is not None else float(seg.min())) > med + 2 * mad + 0.02
        if seg.sum() > thr * 1.6 and seg.max() < thr and sustained:
            c = i + win // 2
            if frames is not None:
                ok, _ = _blend_fit(frames, i - 1, i + win, m.get("sharp"))
                if not ok:
                    continue
            if all(abs(times[c] - times[k]) > min_shot for k, _ in cuts):
                cuts.append((c, "dissolve"))
                spans.append(_active_span(d, i - 1, i + win, med + 2 * mad + 0.02))
                last_dissolve_end = i + win
    # fades span their whole luma ramp down to / up from the dip
    for c, kind in cuts:
        if kind == "fade":
            lo_, hi_ = c, c
            while lo_ > 0 and lum[lo_ - 1] > lum[lo_] + 0.003:
                lo_ -= 1
            while hi_ < n - 1 and lum[hi_ + 1] > lum[hi_] + 0.003:
                hi_ += 1
            spans.append((lo_, hi_))

    def inside(c: int) -> bool:
        return any(lo_ < c <= hi_ for lo_, hi_ in spans)

    # a spike inside a fade's ramp or a dissolve's span is part of that transition, not a separate cut
    cuts = [(c, kind) for c, kind in cuts if kind != "cut" or not inside(c)]
    if frames is not None:
        # a remaining "cut" spike that is really a fast cross-dissolve between very different pictures (proved by the
        # blend fit); if its blend overlaps a transition already found, it is part of that one
        w = max(2, int(round(fps * 0.5)))
        out: list[tuple[int, str]] = []
        for c, kind in sorted(cuts):
            if kind == "cut":
                for lo_, hi_ in ((c - w - 1, c + w), (c - 2 * w, c + 1), (c - 1, c + 2 * w)):
                    if _blend_fit(frames, lo_, hi_, m.get("sharp"))[0]:
                        if any(lo_ <= b and a <= hi_ for a, b in spans):
                            kind = ""  # absorbed
                        else:
                            kind = "dissolve"
                            spans.append(_active_span(d, lo_, hi_, med + 2 * mad + 0.02))
                        break
            if kind:
                out.append((c, kind))
        cuts = out
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

    ratios = [f["edge_ratio"] for f in faces if f.get("edge_ratio") is not None]
    if ratios:  # 640 px content-normalised edge sharpness (see semantics.edge_sharpness)
        sharpness = _norm(float(np.median(ratios)), 0.27, 0.5)
    else:  # emergency mode / no detection frames: low-res Laplacian (resolution- and content-dependent; weaker)
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
    # focus vs motion blur: low sharpness with little motion = out of focus; with high motion = motion blur
    sharp_series = m["sharp"][sl]
    focus_cv = float(np.std(np.log10(sharp_series + 1)) / (np.mean(np.log10(sharp_series + 1)) + 1e-6)) if b - a > 3 else 0.0
    near_black = float((m["luma"][sl] < 0.07).mean())
    lum_d = np.abs(np.diff(m["luma"][sl])) if b - a > 2 else np.zeros(0)
    exposure_jumps = int((lum_d > 0.12).sum())
    obstructed = float(((m["luma"][sl] < 0.25) & (m["sharp"][sl] < 15) & (m["contrast"][sl] < 0.06)).mean())
    if sharpness < 0.3:
        issues.append("blurry")
    blur_kind = ("motion_blur" if motion_s > 0.5 else "out_of_focus") if sharpness < 0.3 else None
    if luma < 0.15 or dark > 0.4:
        issues.append("underexposed")
    if bright > 0.25 or (luma > 0.85 and (bright > 0.1 or contrast < 0.03)):  # clipped, or washed out (no tonal range left)
        issues.append("overexposed")
    if stability < 0.45:
        issues.append("shaky")
    if black_ratio > 0.5:
        issues.append("black")
    if frozen_ratio > 0.9 and dur > 1.0:
        issues.append("frozen")
    if dur < 0.5:
        issues.append("too_short")
    if dur > 120:
        issues.append("very_long")
    if near_black > 0.5 and "black" not in issues and "underexposed" not in issues:
        issues.append("near_black")
    if focus_cv > 0.35 and b - a > 6:
        issues.append("focus_hunting")
    if exposure_jumps >= 2:
        issues.append("exposure_jumps")
    if obstructed > 0.3:
        issues.append("obstructed")
    if audio.get("has_audio") and audio.get("clipping_runs", 0) > 0.001:
        issues.append("clipped_audio")
    if audio.get("has_audio") and audio.get("snr_db", 99) < 6 and speech_t / dur > 0.3:
        issues.append("noisy_audio")
    # USABILITY: can this shot be placed in an edit at all? (technical imperfection ≠ unusable)
    usability = 1.0 - black_ratio
    usability *= 1 - 0.8 * frozen_ratio if dur > 1.0 else 1.0
    usability *= 0.3 if dur < 0.6 else (0.7 if dur < 1.0 else 1.0)
    usability *= 0.3 if luma < 0.06 else (0.4 if luma > 0.94 else 1.0)
    usability *= 0.5 if stability < 0.15 else 1.0
    usability *= 1 - 0.8 * obstructed
    usability = float(np.clip(usability, 0, 1))
    # CREATIVE: what the shot can contribute — framing, subject interest, motion interest, colour, complexity
    subject_interest = float(np.clip(0.6 * face_vis + 0.25 * min(1.0, people / 3) + 0.15 * min(1.0, colorful * 2), 0, 1))
    creative = float(np.clip(0.25 * composition + 0.25 * subject_interest + 0.2 * np.exp(-((motion_s - 0.4) / 0.35) ** 2)
                             + 0.15 * _norm(colorful, 0.08, 0.45) + 0.15 * contrast_s, 0, 1))
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
    if ratios and float(np.median(ratios)) > 0.68:
        tags.append("screen_recording")  # heuristic: synthetic, noise-free edges (real camera footage measured ≤ 0.64)
    return {
        "start": round(start, 3), "end": round(end, 3), "duration": round(dur, 3),
        "metrics": {
            "luma": round(luma, 4), "contrast": round(contrast, 4), "laplacian_var": round(sharp, 2), "dark_clip": round(dark, 4),
            "bright_clip": round(bright, 4), "motion": round(motion, 5), "jitter": round(jitter, 4), "pan_px": round(pan, 2),
            "tilt_px": round(tilt, 2), "saturation": round(sat, 4), "colorfulness": round(colorful, 4), "black_ratio": round(black_ratio, 3),
            "frozen_ratio": round(frozen_ratio, 3), "edge_ratio": round(float(np.median(ratios)), 3) if ratios else None, "temperature": round(float(m["temp"][sl].mean()), 4),
            "tint": round(float(m["tint"][sl].mean()), 4), "face_fraction": round(face_frac, 3), "face_area": round(face_size, 4),
            "people": round(people, 2), "speech_seconds": round(speech_t, 2), "focus_variation": round(focus_cv, 3),
            "near_black_ratio": round(near_black, 3), "blur_kind": blur_kind, "exposure_jumps": exposure_jumps, "obstructed_ratio": round(obstructed, 3),
        },
        "scores": {
            "quality_score": round(quality, 3), "sharpness_score": round(sharpness, 3), "composition_score": round(composition, 3),
            "motion_score": round(motion_s, 3), "exposure_score": round(exposure, 3), "face_visibility_score": round(face_vis, 3),
            "audio_score": round(audio_s, 3), "emotional_score": round(emotional, 3), "energy_score": round(energy, 3),
            "stability_score": round(stability, 3), "cinematic_score": round(cinematic, 3),
            "uniqueness_score": 1.0,  # set at project level by `apply_uniqueness`
            "usability_score": round(usability, 3), "creative_score": round(creative, 3),
        },
        "issues": issues,
        "tags": tags,
    }


HARD_ISSUES = {"black", "frozen", "too_short", "obstructed"}  # never used unless nothing else exists
SOFT_PENALTY = {"out_of_focus": 0.2, "motion_blur": 0.12, "blurry": 0.2, "underexposed": 0.12, "overexposed": 0.12, "shaky": 0.1,
                "near_black": 0.15, "focus_hunting": 0.06, "exposure_jumps": 0.05, "clipped_audio": 0.04, "noisy_audio": 0.03,
                "duplicate": 0.25, "black": 0.6, "frozen": 0.3, "too_short": 0.3, "obstructed": 0.4, "very_long": 0.0}


def overall(scores: dict, issues: list[str]) -> float:
    """Edit score = technical QUALITY + USABILITY + CREATIVE value. Technical issues are penalties, not vetoes: a slightly
    soft but well-framed, people-rich, unique shot can outrank a sharp empty one."""
    q = scores["quality_score"]
    u = scores.get("usability_score", 1.0)
    c = scores.get("creative_score", scores.get("cinematic_score", 0.5))
    s = (0.32 * q + 0.22 * u + 0.30 * c + 0.08 * scores["uniqueness_score"] + 0.08 * scores["energy_score"])
    for i in issues:
        s -= SOFT_PENALTY.get(i, 0.05)
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
    shots_raw = detect_shots(m, fs.times, fs.fps, frames=fs.rgb)
    # people / faces / objects from the vision provider on 640 px frames (every `face_every` s + each shot's midpoint)
    det_samples: list[dict] = []
    provider, semantic = "none", False
    if face_every > 0 and len(fs.rgb):
        from ..vision import get_vision_provider

        det_samples, provider = sample_detections(path, meta, shots_raw, face_every)
        semantic = get_vision_provider().semantic
    face_samples = [{"t": d["t"], "edge_ratio": d.get("edge_ratio"), "n": len(d["faces"]), "max_area": max((f[2] * f[3] for f in d["faces"]), default=0.0), "people": d["people"],
                     "boxes": [f[:4] for f in d["faces"][:4]]} for d in det_samples]
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
            dhash=str(F.dhash(fs.rgb[mid])), hist=[round(float(x), 5) for x in m["hists"][mid]], thumbs=_thumbs(fs.rgb, a, b), rgb_thumb=_rgb_thumb(fs.rgb, a, b),
            faces=[f["boxes"] for f in fsamp if f["boxes"]][:1],
            text_bands=F.text_likelihood(fs.rgb[mid]),
        )
        reliable = float((m["pc_resp"][a:b] > 0)[1:].mean()) >= 0.5 if b - a > 3 else False
        prof = shot_profile(det_samples, provider, semantic, sc["metrics"], sc["scores"], sc["start"], sc["end"],
                            camera_motion(sc["metrics"], sc["scores"]["stability_score"], reliable))
        prof["orientation"] = meta.get("orientation")
        sc["semantic"] = prof
        sc["tags"] = list(dict.fromkeys(sc["tags"] + [x["label"] for x in prof["subjects"]] +
                                        ([prof["shot_size"]] if prof["shot_size"] != "unknown" else []) +
                                        [v for v in prof["scene_type"].values() if v != "unknown"]))
        if prof["shot_size"] in ("closeup", "extreme_closeup", "medium", "wide"):  # detector framing replaces the face-area guess
            sc["tags"] = [t for t in sc["tags"] if t not in ("closeup", "medium", "wide") or t == prof["shot_size"]]
            if prof["shot_size"] == "extreme_closeup":
                sc["tags"].append("closeup")
        sc["overall_edit_score"] = overall(sc["scores"], sc["issues"])
        shots.append(sc)
    result = {
        "version": VERSION, "mode": mode, "meta": meta, "audio": audio, "shots": shots, "vision_provider": provider,
        "speech_detector": audio.get("speech_detector"),
        "summary": {
            "n_shots": len(shots),
            "mean_luma": round(float(m["luma"].mean()), 4) if len(fs.rgb) else 0,
            "mean_saturation": round(float(m["sat"].mean()), 4) if len(fs.rgb) else 0,
            "mean_temperature": round(float(m["temp"].mean()), 4) if len(fs.rgb) else 0,
            "mean_tint": round(float(m["tint"].mean()), 4) if len(fs.rgb) else 0,
            "mean_contrast": round(float(m["contrast"].mean()), 4) if len(fs.rgb) else 0,
            "best_score": max((s["overall_edit_score"] for s in shots), default=0),
            "usable_shots": sum(1 for s in shots if not (set(s["issues"]) & HARD_ISSUES)),
            "clean_shots": sum(1 for s in shots if not s["issues"]),
        },
    }
    if fingerprint:
        db.cache_put(fingerprint, "video", f"{VERSION}:{mode}", result)
    log(logger, "analyzed video", file=path.name, shots=len(shots), mode=mode)
    return result


def _thumbs(rgb: np.ndarray, a: int, b: int) -> str:
    """Exposure-invariant 16×9 structure thumbnails at 25/50/75 % of the shot, quantised to bytes (hex)."""
    import cv2

    out = bytearray()
    for q in (0.25, 0.5, 0.75):
        i = min(b - 1, a + int((b - a) * q))
        g = cv2.resize(cv2.cvtColor(rgb[i], cv2.COLOR_RGB2GRAY), (16, 9), interpolation=cv2.INTER_AREA).astype(np.float32)
        g = (g - g.mean()) / (g.std() + 2.0)
        out += bytes(np.clip((g + 3) / 6 * 255, 0, 255).astype(np.uint8).ravel())
    return out.hex()


def _rgb_thumb(rgb: np.ndarray, a: int, b: int) -> str:
    """16×9 RGB thumbnail averaged over 3 frames of the shot (hex) — used to simulate grading decisions."""
    import cv2

    idx = sorted({min(b - 1, a + int((b - a) * q)) for q in (0.25, 0.5, 0.75)})
    t = np.mean([cv2.resize(rgb[i], (16, 9), interpolation=cv2.INTER_AREA).astype(np.float32) for i in idx], axis=0)
    return bytes(np.clip(t, 0, 255).astype(np.uint8).ravel()).hex()


def _thumb_array(h: str | None) -> np.ndarray | None:
    if not h:
        return None
    return np.frombuffer(bytes.fromhex(h), np.uint8).astype(np.float32).reshape(3, 144) / 255 * 6 - 3


DUP_MAX = 0.10   # max per-position structure difference for "the same footage" (calibrated on real duplicate pairs)
ANGLE_MAX = 0.35  # same camera set-up, different moment


def apply_uniqueness(analyses: dict[str, dict], dup_bits: int = 6) -> list[list[str]]:
    """Project-level duplicate / same-angle detection across every shot of every clip.

    duplicate  — structure thumbnails at 25/50/75 % all within DUP_MAX (same footage: re-encodes, retimed copies,
                 overlapping takes). The highest-scoring copy stays clean; the others get the "duplicate" issue.
    same angle — same camera set-up at a different moment (mid-frame dHash ≤ 10 bits and thumbnails ≤ ANGLE_MAX):
                 recorded as `angle_group` for variety decisions; never a rejection.
    Uniqueness = 1 − similarity to the most similar other shot. Mutates scores; returns duplicate groups."""
    items = []
    for aid, an in analyses.items():
        for sh in an.get("shots", []):
            sh["issues"] = [x for x in sh["issues"] if x != "duplicate"]  # recomputed from scratch for the current asset set
            items.append((f"{aid}:{sh['index']}", int(sh["dhash"]), _thumb_array(sh.get("thumbs")), sh))
    n = len(items)
    if not n:
        return []
    T = np.stack([t if t is not None else np.full((3, 144), np.nan, np.float32) for _, _, t, _ in items])
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    dup_pairs: list[tuple[int, int]] = []
    for i in range(n):
        d = np.nanmean(np.abs(T[i][None] - T), axis=2)  # (n, 3) per-position difference
        dmax = np.nanmax(d, axis=1)
        dmax[i] = np.inf
        sim = np.clip(1 - dmax / 0.6, 0, 1)
        sim = np.nan_to_num(sim, nan=0.0)
        shi = items[i][3]
        shi["scores"]["uniqueness_score"] = round(float(np.clip(1 - sim.max(), 0, 1) * 1.5), 3) if n > 1 else 1.0
        shi["scores"]["uniqueness_score"] = min(1.0, shi["scores"]["uniqueness_score"])
        shi["similarity_max"] = round(float(sim.max()), 3) if n > 1 else 0.0
        for j in np.where(dmax <= DUP_MAX)[0]:
            if j > i:
                dup_pairs.append((i, int(j)))
        for j in np.where(dmax <= ANGLE_MAX)[0]:
            if F.hamming(items[i][1], items[j][1]) <= 10:
                parent[find(i)] = find(int(j))
    # duplicate groups (connected components of dup pairs); keep the best-scoring member clean
    dparent = list(range(n))

    def dfind(x: int) -> int:
        while dparent[x] != x:
            dparent[x] = dparent[dparent[x]]
            x = dparent[x]
        return x

    for i, j in dup_pairs:
        dparent[dfind(i)] = dfind(j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(dfind(i), []).append(i)
    dups = []
    for g in groups.values():
        for i in g:
            items[i][3]["duplicate_of"] = None
        if len(g) < 2:
            continue
        keep = max(g, key=lambda i: items[i][3]["overall_edit_score"])
        dups.append([items[keep][0]] + [items[i][0] for i in g if i != keep])
        for i in g:
            sh = items[i][3]
            if i != keep:
                sh["duplicate_of"] = items[keep][0]
                if "duplicate" not in sh["issues"]:
                    sh["issues"].append("duplicate")
    for i, (k, _, _, sh) in enumerate(items):
        sh["angle_group"] = f"g{find(i)}"
        sh["overall_edit_score"] = overall(sh["scores"], sh["issues"])
    return dups
