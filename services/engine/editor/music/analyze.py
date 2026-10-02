"""Music intelligence: BPM, beats, downbeats, energy curve, sections, drops, build-ups.

Uses librosa's beat tracker and a structural segmentation over beat-synchronous chroma + MFCC."""
from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

from .. import db
from ..logging import get_logger, log
from ..media.audio import load_mono

logger = get_logger("music")
VERSION = "music-v3"
SR = 22050


def _energy_changepoints(e: np.ndarray, hop: float, win: float = 4.0, thr: float = 0.12, spacing: float = 6.0) -> list[float]:
    w = int(win / hop)
    if len(e) < 2 * w + 1:
        return []
    score = np.array([abs(e[i:i + w].mean() - e[i - w:i].mean()) for i in range(w, len(e) - w)])
    pts: list[float] = []
    for i in np.argsort(-score):
        if score[i] < thr:
            break
        t = (i + w) * hop
        if all(abs(t - p) >= spacing for p in pts):
            pts.append(t)
    return sorted(pts)


def _sections(y: np.ndarray, sr: int, beat_frames: np.ndarray, hop: int, duration: float, energy_pts: list[float] | None = None) -> list[dict]:
    if len(beat_frames) < 16:
        return [{"start": 0.0, "end": round(duration, 3)}]
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop, n_mfcc=13)
    feat = np.vstack([librosa.util.normalize(chroma, axis=0), librosa.util.normalize(mfcc, axis=1)])
    sync = librosa.util.sync(feat, beat_frames, aggregate=np.median)
    k = int(np.clip(round(duration / 20), 3, 10))
    bounds = librosa.segment.agglomerative(sync, k)
    bt = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)
    struct = [float(bt[min(b, len(bt) - 1)]) for b in bounds if b > 0]
    # energy change points are authoritative; structural boundaries fill gaps >= 8 s away from them
    pts = list(energy_pts or [])
    for t in struct:
        if all(abs(t - p) >= 8.0 for p in pts) and 4.0 < t < duration - 4.0:
            pts.append(t)
    # snap to nearest beat
    pts = [float(bt[np.argmin(np.abs(bt - t))]) for t in pts]
    times = sorted({0.0, *pts, duration})
    out = []
    for a, b in zip(times[:-1], times[1:]):
        if b - a >= 2.0:
            out.append({"start": round(a, 3), "end": round(b, 3)})
        elif out:
            out[-1]["end"] = round(b, 3)
    return out or [{"start": 0.0, "end": round(duration, 3)}]


def analyze_music(path: Path, fingerprint: str | None = None) -> dict:
    if fingerprint:
        hit = db.cache_get(fingerprint, "music", VERSION)
        if hit:
            return hit
    y = load_mono(path, sr=SR)
    duration = len(y) / SR
    if duration < 1.0:
        return {"version": VERSION, "duration": duration, "bpm": 0.0, "beats": [], "downbeats": [], "sections": [], "energy": [], "ok": False}
    hop = 512
    onset = librosa.onset.onset_strength(y=y, sr=SR, hop_length=hop)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset, sr=SR, hop_length=hop, units="frames", trim=False)
    bpm = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=SR, hop_length=hop)
    # downbeats: choose the bar phase (of 4) with the strongest accumulated onset + low-frequency energy
    S = np.abs(librosa.stft(y, hop_length=hop, n_fft=2048))
    low = S[: int(150 / (SR / 2048))].sum(0)
    low = low / (low.max() + 1e-9)
    strength = onset[np.clip(beat_frames, 0, len(onset) - 1)] + 2 * low[np.clip(beat_frames, 0, len(low) - 1)]
    phase = int(np.argmax([strength[p::4].mean() if len(strength[p::4]) else 0 for p in range(4)])) if len(beats) >= 8 else 0
    downbeats = beats[phase::4]
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    rms_t = librosa.frames_to_time(np.arange(len(rms)), sr=SR, hop_length=hop)
    # energy curve at 2 Hz, normalised 0..1
    grid = np.arange(0, duration, 0.5)
    e = np.interp(grid, rms_t, librosa.amplitude_to_db(rms, ref=np.max))
    e = (e - e.min()) / (e.max() - e.min() + 1e-9)
    sections = _sections(y, SR, beat_frames, hop, duration, _energy_changepoints(np.convolve(e, np.ones(3) / 3, mode="same"), 0.5))
    for s in sections:
        mask = (grid >= s["start"]) & (grid < s["end"])
        s["energy"] = round(float(e[mask].mean()) if mask.any() else 0.0, 3)
    if sections:
        es = np.array([s["energy"] for s in sections])
        hi, lo = np.percentile(es, 67), np.percentile(es, 33)
        for i, s in enumerate(sections):
            s["level"] = "high" if s["energy"] >= hi else ("low" if s["energy"] <= lo else "mid")
            prev = sections[i - 1]["energy"] if i else s["energy"]
            s["label"] = ("intro" if i == 0 and s["energy"] < hi else "outro" if i == len(sections) - 1 and s["energy"] < hi
                          else "drop" if s["energy"] - prev > 0.18 else "chorus" if s["level"] == "high" else "verse" if s["level"] == "mid" else "breakdown")
    # drops: sharp energy rises; build-ups: windows of monotone energy increase before a drop
    de = np.diff(np.convolve(e, np.ones(4) / 4, mode="same"))
    drops = [round(float(grid[i + 1]), 2) for i in np.where(de > max(0.06, np.percentile(de, 98)))[0]]
    drops = [d for k, d in enumerate(drops) if k == 0 or d - drops[k - 1] > 4]
    builds = []
    for d in drops:
        a = d - 8
        seg = (grid >= a) & (grid < d)
        if seg.sum() > 4 and np.corrcoef(grid[seg], e[seg])[0, 1] > 0.6:
            builds.append([round(max(0, a), 2), d])
    result = {
        "version": VERSION, "ok": True, "duration": round(duration, 3), "bpm": round(bpm, 2),
        "beats": [round(float(b), 3) for b in beats], "downbeats": [round(float(b), 3) for b in downbeats],
        "beat_interval": round(60.0 / bpm, 4) if bpm else 0.0,
        "energy": [round(float(v), 3) for v in e], "energy_hop": 0.5,
        "sections": sections, "drops": drops, "buildups": builds,
        "quiet": [[s["start"], s["end"]] for s in sections if s.get("level") == "low"],
        "high_energy": [[s["start"], s["end"]] for s in sections if s.get("level") == "high"],
        "loudness_db": round(float(20 * np.log10(np.sqrt((y ** 2).mean()) + 1e-9)), 2),
    }
    if fingerprint:
        db.cache_put(fingerprint, "music", VERSION, result)
    log(logger, "analyzed music", file=path.name, bpm=result["bpm"], beats=len(beats), sections=len(sections))
    return result


def best_window(m: dict, length: float, prefer: str = "build_to_peak") -> tuple[float, float]:
    """Pick the start of the most suitable `length`-second window of a track.
    build_to_peak: maximise rising energy ending near a high section (typical highlight edit);
    calm: lowest variance; peak: highest mean energy. Window start snaps to a downbeat."""
    dur = m.get("duration", 0.0)
    if dur <= length + 0.5 or not m.get("energy"):
        return 0.0, min(dur, length)
    e = np.array(m["energy"])
    hop = m.get("energy_hop", 0.5)
    n = int(length / hop)
    best, best_s = -1e9, 0.0
    starts = m.get("downbeats") or m.get("beats") or list(np.arange(0, dur - length, 1.0))
    for s in starts:
        if s + length > dur:
            break
        i = int(s / hop)
        w = e[i:i + n]
        if len(w) < n * 0.9:
            continue
        if prefer == "calm":
            sc = -w.std() + 0.2 * w.mean()
        elif prefer == "peak":
            sc = w.mean()
        else:
            third = max(1, len(w) // 3)
            sc = 0.5 * w.mean() + 0.6 * (w[-third:].mean() - w[:third].mean()) + 0.3 * w[-third:].max()
        sc -= 0.02 * (s / max(dur, 1))  # mild preference for earlier windows
        if sc > best:
            best, best_s = sc, float(s)
    return round(best_s, 3), round(best_s + length, 3)
