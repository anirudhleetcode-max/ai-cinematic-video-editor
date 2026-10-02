"""Audio presets (FFmpeg filter chains for dialogue) and the procedural SFX synthesiser."""
from __future__ import annotations

import numpy as np

from .base import Definition, Registry, f

AUDIO_PRESETS = Registry("audio_preset")


def _ap(id_, name, tags, chain, desc=""):
    AUDIO_PRESETS.register(Definition(id_, name, "audio", (f("gain_db", 0.0, -20, 12, 1),), tuple(tags), desc, 1.0, lambda p, _c=chain: _c))


_ap("dialogue_clean", "Dialogue — Clean", ("dialogue", "speech", "default"),
    "highpass=f=80,afftdn=nr=10:nf=-45,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=2.5,deesser=i=0.3,"
    "acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2", "Noise reduction, mud cut, presence lift, de-ess, 3:1 compression.")
_ap("dialogue_broadcast", "Dialogue — Broadcast", ("dialogue", "podcast", "voiceover"),
    "highpass=f=90,afftdn=nr=12:nf=-42,equalizer=f=200:t=q:w=1:g=-3,equalizer=f=4000:t=q:w=1:g=3,deesser=i=0.4,"
    "acompressor=threshold=-24dB:ratio=4:attack=5:release=80:makeup=4", "Denser, louder voice for voice-over.")
_ap("dialogue_light", "Dialogue — Light Touch", ("dialogue", "natural", "documentary"),
    "highpass=f=70,afftdn=nr=6:nf=-50,acompressor=threshold=-18dB:ratio=2:attack=10:release=150", "Minimal processing.")
_ap("ambience", "Ambience Bed", ("ambient", "background"), "highpass=f=60,lowpass=f=12000,acompressor=threshold=-25dB:ratio=2", "Location sound bed.")
_ap("none", "No processing", ("raw",), "anull")

SFX_KINDS = ("whoosh", "impact", "hit", "riser", "downer", "click", "pop", "sweep", "transition", "ambient", "shimmer")


def synth_sfx(kind: str, sr: int = 48000, seed: int = 0, length: float | None = None) -> np.ndarray:
    """Procedurally generated, royalty-free SFX (mono float32)."""
    rng = np.random.default_rng(seed)

    def env(n, a, d):
        t = np.arange(n) / sr
        return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))

    def lp(x, cut):
        a = np.exp(-2 * np.pi * cut / sr)
        y = np.empty_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc = (1 - a) * v + a * acc
            y[i] = acc
        return y

    if kind in ("whoosh", "transition", "sweep"):
        L = length or (0.7 if kind != "sweep" else 1.0)
        n = int(L * sr)
        noise = rng.standard_normal(n)
        t = np.linspace(0, 1, n)
        # time-varying low-pass via STFT band mask (fast) instead of sample loop
        S = np.fft.rfft(noise)
        out = np.zeros(n)
        segs = 16
        for k in range(segs):
            a, b = k * n // segs, (k + 1) * n // segs
            cut = 300 + 5000 * np.sin(np.pi * (k + 0.5) / segs) ** 2
            seg = noise[a:b] * np.hanning(b - a)
            Sf = np.fft.rfft(seg)
            fr = np.fft.rfftfreq(b - a, 1 / sr)
            Sf[fr > cut] *= 0.05
            out[a:b] += np.fft.irfft(Sf, b - a)
        y = out * np.sin(np.pi * t) ** 2
        del S
    elif kind in ("impact", "hit"):
        L = length or (1.4 if kind == "impact" else 0.5)
        n = int(L * sr)
        t = np.arange(n) / sr
        f0 = 55 + 90 * np.exp(-t * 12)
        body = np.sin(2 * np.pi * np.cumsum(f0) / sr) * env(n, 0.002, 0.35 if kind == "impact" else 0.12)
        crack = lp(rng.standard_normal(min(n, int(0.08 * sr))), 3000) * env(min(n, int(0.08 * sr)), 0.0005, 0.02)
        y = body
        y[: len(crack)] += crack * 0.8
    elif kind == "riser":
        L = length or 2.0
        n = int(L * sr)
        t = np.arange(n) / sr
        f = 200 * (1 + 4 * (t / L) ** 2)
        tone = np.sin(2 * np.pi * np.cumsum(f) / sr) * 0.4
        noise = rng.standard_normal(n) * 0.3
        y = (tone + noise * (t / L)) * (t / L) ** 2
    elif kind == "downer":
        L = length or 1.5
        n = int(L * sr)
        t = np.arange(n) / sr
        f = 600 * np.exp(-t * 2.5) + 40
        y = np.sin(2 * np.pi * np.cumsum(f) / sr) * env(n, 0.01, 0.6)
    elif kind in ("click", "pop"):
        n = int((length or 0.06) * sr)
        t = np.arange(n) / sr
        y = np.sin(2 * np.pi * (1800 if kind == "click" else 700) * t) * np.exp(-t * (90 if kind == "click" else 45))
    elif kind == "shimmer":
        n = int((length or 1.8) * sr)
        t = np.arange(n) / sr
        y = sum(np.sin(2 * np.pi * fr * t) * a for fr, a in ((1760, 1), (2637, 0.5), (3520, 0.3))) * env(n, 0.003, 0.5)
    else:  # ambient
        n = int((length or 4.0) * sr)
        y = lp(rng.standard_normal(n), 800) * 0.5
    y = np.asarray(y, np.float32)
    return y / (np.abs(y).max() + 1e-9) * 0.9
