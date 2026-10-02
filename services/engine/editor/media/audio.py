"""Clip audio analysis: loudness envelope, silence, speech-activity detection, clipping."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import stft

from ..config import get_settings

SR = 16000
HOP = 0.02  # 20 ms analysis frames


def load_mono(path: Path, sr: int = SR, start: float = 0.0, duration: float | None = None) -> np.ndarray:
    s = get_settings()
    cmd = [s.ffmpeg, "-v", "error", "-nostdin"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    p = subprocess.run(cmd, capture_output=True, timeout=1800)
    if p.returncode != 0:
        return np.zeros(0, np.float32)
    return np.frombuffer(p.stdout, np.float32).copy()


def _segments(mask: np.ndarray, hop: float, min_len: float) -> list[list[float]]:
    segs, start = [], None
    for i, m in enumerate(np.append(mask, False)):
        if m and start is None:
            start = i
        elif not m and start is not None:
            if (i - start) * hop >= min_len:
                segs.append([round(start * hop, 3), round(i * hop, 3)])
            start = None
    return segs


def _merge(segs: list[list[float]], gap: float) -> list[list[float]]:
    out: list[list[float]] = []
    for a, b in segs:
        if out and a - out[-1][1] <= gap:
            out[-1][1] = b
        else:
            out.append([a, b])
    return out


def analyze_audio(path: Path) -> dict:
    y = load_mono(path)
    if y.size < SR * 0.1:
        return {"has_audio": False, "rms_db": [], "speech": [], "silence": [], "speech_ratio": 0.0,
                "mean_db": -120.0, "peak": 0.0, "clipping": 0.0, "energy": 0.0}
    n = int(SR * HOP)
    frames = y[: len(y) // n * n].reshape(-1, n)
    rms = np.sqrt((frames ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    # speech activity: energy in the voice band, spectral flatness (voice is not flat), and
    # syllabic modulation (4–8 Hz) of the voice-band envelope.
    f, _, Z = stft(y, fs=SR, nperseg=512, noverlap=512 - n, boundary=None)
    P = np.abs(Z) ** 2
    m = min(P.shape[1], len(db))
    P, db_m = P[:, :m], db[:m]
    voice = P[(f >= 300) & (f <= 3400)].sum(0)
    total = P.sum(0) + 1e-12
    band_ratio = voice / total
    flat = np.exp(np.log(P + 1e-12).mean(0)) / (P.mean(0) + 1e-12)
    noise_floor = np.percentile(db_m, 10)
    env = np.log(voice + 1e-12)
    win = int(1.0 / HOP)
    mod = np.zeros(m)
    if m > win:
        from scipy.signal import butter, sosfiltfilt

        sos = butter(2, [3, 9], btype="band", fs=1 / HOP, output="sos")
        bp = sosfiltfilt(sos, env - env.mean())
        mod = np.convolve(np.abs(bp), np.ones(win) / win, mode="same")
    mod_thr = max(0.3, np.percentile(mod, 60)) if m > win else 0.0
    speech_mask = (db_m > noise_floor + 9) & (db_m > -50) & (band_ratio > 0.55) & (flat < 0.3) & (mod >= mod_thr * 0.8)
    speech = _merge(_segments(speech_mask, HOP, 0.25), 0.35)
    speech = [s for s in speech if s[1] - s[0] >= 0.5]
    silence = _segments(db < max(-50.0, noise_floor + 3), HOP, 0.5)
    dur = len(y) / SR
    sp = sum(b - a for a, b in speech)
    step = max(1, int(0.1 / HOP))
    return {
        "has_audio": True,
        "rms_db": [round(float(v), 1) for v in db[::step]],
        "rms_hop": HOP * step,
        "speech": speech,
        "silence": silence,
        "speech_ratio": round(sp / dur, 3) if dur else 0.0,
        "mean_db": round(float(20 * np.log10(np.sqrt((y ** 2).mean()) + 1e-9)), 2),
        "peak": round(float(np.abs(y).max()), 4),
        "clipping": round(float((np.abs(y) > 0.99).mean()), 5),
        "energy": round(float(np.clip((np.percentile(db, 90) + 50) / 40, 0, 1)), 3),
    }
