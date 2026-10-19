"""Procedural sound-design synthesiser.

Every sound here is synthesised from scratch with numpy (oscillators,
filtered noise, envelopes). No samples, recordings or third-party audio are
used, so the output is original material and is released with this project
(see 02_SHARED_ASSETS/Sound_Effects/LICENSE.md).
"""
from __future__ import annotations

import math
import wave

import numpy as np

SR = 48000


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def band(x, lo, hi):
    """FFT band-pass (brick-wall with soft edges)."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    w = np.ones_like(f)
    if lo > 0:
        w *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi < SR / 2:
        w *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * w, n)


def env_ad(n, a, d, curve=4.0):
    t = np.arange(n) / SR
    e = np.where(t < a, t / max(a, 1e-4), np.exp(-(t - a) / max(d, 1e-4) * curve / 4))
    return e


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


def reverb(x, size=1.8, mix=0.25, seed=3):
    n = int(size * SR)
    ir = _noise(n, seed) * np.exp(-np.arange(n) / SR * 6.0 / size)
    ir = band(ir, 120, 7000)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    L = len(x) + n
    y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[: len(x) + n]
    out = np.zeros(len(y))
    out[: len(x)] += x * (1 - mix)
    out += y * mix
    return out


# ---------------------------------------------------------------- voices --
def impact(seed=1, dur=2.5, weight=1.0):
    t = _t(dur)
    f = 32 + 90 * np.exp(-t * 9)
    ph = 2 * np.pi * np.cumsum(f) / SR
    boom = np.sin(ph) * np.exp(-t * 2.2 / weight)
    click = band(_noise(len(t), seed), 800, 9000) * np.exp(-t * 60)
    body = band(_noise(len(t), seed + 1), 60, 900) * np.exp(-t * 7)
    x = np.tanh((boom * 1.4 + click * 0.5 + body * 0.6) * 1.8)
    return reverb(x, 2.2, 0.22, seed)


def sub_drop(seed=2, dur=3.0):
    t = _t(dur)
    f = 55 * np.exp(-t * 0.8) + 25
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.2) * np.minimum(t * 40, 1)


def metal_hit(seed=3, dur=3.0, base=180.0):
    t = _t(dur)
    ratios = [1, 2.32, 2.76, 4.07, 5.4, 6.8, 8.93]
    x = sum(np.sin(2 * np.pi * base * r * t + i) * np.exp(-t * (1.2 + i * 0.9)) / (1 + i * 0.5)
            for i, r in enumerate(ratios))
    click = band(_noise(len(t), seed), 2000, 12000) * np.exp(-t * 80)
    x = x * 0.6 + click * 0.6 + impact(seed, dur, 0.6)[: len(t)] * 0.6
    return reverb(x, 2.5, 0.3, seed)


def whoosh(seed=4, dur=1.4, reverse=False):
    t = _t(dur)
    n = _noise(len(t), seed)
    lo = band(n, 200, 1200)
    hi = band(n, 1500, 6000)
    u = t / dur
    e = np.sin(np.pi * u) ** 3
    x = (lo * (1 - u) + hi * u) * e
    if reverse:
        x = x[::-1] * np.linspace(0.2, 1, len(x)) ** 2
    return x


def riser(seed=5, dur=3.0):
    t = _t(dur)
    u = t / dur
    f = 80 * (1 + 6 * u ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * 0.15
    n = _noise(len(t), seed)
    nn = band(n, 300, 900) * (1 - u) + band(n, 1500, 8000) * u
    return (tone + nn * 0.7) * u ** 2.2


def atmos(seed=6, dur=8.0, dark=1.0):
    t = _t(dur)
    d = (np.sin(2 * np.pi * 41 * t) * 0.5 + np.sin(2 * np.pi * 61.7 * t) * 0.3) * (0.7 + 0.3 * np.sin(t * 0.7))
    air = band(_noise(len(t), seed), 80, 900 if dark else 2500) * (0.6 + 0.4 * np.sin(t * 0.43 + 1))
    fade = np.minimum(t / 1.0, 1) * np.minimum((dur - t) / 1.0, 1)
    return (d * 0.5 + air * 0.6) * fade


def debris(seed=7, dur=2.0, density=60):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    x = np.zeros(n)
    for i in range(density):
        p = int(r.exponential(0.4) * SR)
        if p >= n - 2000:
            continue
        L = r.integers(300, 1600)
        g = band(r.standard_normal(L), r.uniform(1500, 3000), r.uniform(5000, 10000)) * np.exp(-np.arange(L) / L * 6)
        x[p:p + L] += g * r.uniform(0.2, 1) * math.exp(-p / SR * 1.5)
    return reverb(x, 1.0, 0.2, seed)


def shimmer(seed=8, dur=2.5, base=880.0):
    t = _t(dur)
    x = sum(np.sin(2 * np.pi * base * r * t * (1 + 0.003 * np.sin(t * (5 + i)))) / (i + 1)
            for i, r in enumerate([1, 1.5, 2, 3, 4.01]))
    return reverb(x * np.sin(np.pi * np.minimum(t / dur, 1)) ** 2 * 0.4, 2.0, 0.4, seed)


def tail(seed=9, dur=3.5):
    t = _t(dur)
    x = band(_noise(len(t), seed), 40, 500) * np.exp(-t * 1.2) * np.minimum(t * 8, 1)
    return reverb(x, 2.5, 0.4, seed)


def thunder(seed=10, dur=4.0):
    t = _t(dur)
    crack = band(_noise(len(t), seed), 1000, 9000) * np.exp(-t * 25)
    roll = band(_noise(len(t), seed + 1), 30, 300) * (np.exp(-t * 0.9) * (0.6 + 0.4 * np.sin(t * 7) ** 2))
    return reverb(np.tanh((crack * 0.8 + roll * 1.6) * 1.5), 3.0, 0.35, seed)


def crackle(seed=11, dur=1.5, rate=90):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    x = np.zeros(n)
    for i in range(int(rate * dur)):
        p = r.integers(0, n - 400)
        L = r.integers(40, 300)
        x[p:p + L] += r.standard_normal(L) * np.exp(-np.arange(L) / L * 5) * r.uniform(0.2, 1)
    x = band(x, 2500, 14000)
    hum = np.sin(2 * np.pi * 100 * _t(dur)) * 0.15
    return (x + hum) * np.minimum(_t(dur) * 10, 1) * np.minimum((dur - _t(dur)) * 4, 1)


def fire(seed=12, dur=4.0):
    t = _t(dur)
    roar = band(_noise(len(t), seed), 60, 700) * (0.6 + 0.4 * np.abs(np.sin(t * 3.1)))
    return roar * 0.8 + crackle(seed, dur, 40) * 0.5


def wind(seed=13, dur=6.0, hi=2500):
    t = _t(dur)
    n = _noise(len(t), seed)
    return band(n, 150, hi) * (0.5 + 0.5 * np.sin(t * 0.9) ** 2) * np.minimum(t, 1) * np.minimum(dur - t, 1)


def digital(seed=14, dur=1.2, notes=(880, 1320, 1760)):
    t = _t(dur)
    x = np.zeros(len(t))
    seg = len(t) // len(notes)
    for i, f in enumerate(notes):
        s = slice(i * seg, (i + 1) * seg)
        tt = t[: seg]
        x[s] = np.sign(np.sin(2 * np.pi * f * tt)) * 0.25 * np.exp(-tt * 12)
    return reverb(band(x, 300, 9000), 0.8, 0.25, seed)


def glitch(seed=15, dur=0.8):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    x = np.zeros(n)
    p = 0
    while p < n:
        L = min(int(r.uniform(0.01, 0.06) * SR), n - p)
        f = r.choice([220, 440, 1200, 3000, 60])
        tt = np.arange(L) / SR
        x[p:p + L] = (np.sign(np.sin(2 * np.pi * f * tt)) if r.random() < 0.5 else r.standard_normal(L)) * 0.4
        p += L + int(r.uniform(0, 0.03) * SR)
    return x[:n]


def swell(seed=16, dur=4.0, root=110.0, bright=1.0):
    t = _t(dur)
    chord = [1, 1.5, 2, 2.5, 3]
    x = sum(np.sin(2 * np.pi * root * r * t + i) * (1 + 0.2 * np.sin(t * (0.5 + i * 0.2))) / (1 + i)
            for i, r in enumerate(chord))
    e = np.sin(np.pi * np.minimum(t / dur, 1)) ** 1.5
    return reverb(x * e * 0.4, 3.0, 0.45, seed)


def ice(seed=17, dur=2.0):
    r = np.random.default_rng(seed)
    n = int(dur * SR)
    x = np.zeros(n)
    for i in range(70):
        p = int(r.uniform(0, dur * 0.85) * SR)
        f = r.uniform(2000, 6000)
        L = int(0.05 * SR)
        tt = np.arange(L) / SR
        x[p:p + L] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 70) * r.uniform(0.1, 0.6)
    return reverb(x, 1.5, 0.35, seed)


def water(seed=18, dur=6.0):
    t = _t(dur)
    rumble = band(_noise(len(t), seed), 20, 250) * 0.8
    r = np.random.default_rng(seed)
    b = np.zeros(len(t))
    for i in range(25):
        p = int(r.uniform(0, dur - 0.2) * SR)
        L = int(0.08 * SR)
        tt = np.arange(L) / SR
        f = r.uniform(300, 900) * (1 + tt * 6)
        b[p:p + L] += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 40) * 0.3
    return (rumble + b) * np.minimum(t, 1) * np.minimum(dur - t, 1)


def rain_snd(seed=19, dur=8.0):
    t = _t(dur)
    return band(_noise(len(t), seed), 1500, 11000) * 0.25 * np.minimum(t, 1) * np.minimum(dur - t, 1)


def hammer(seed=20, dur=1.6):
    return metal_hit(seed, dur, 320) * 0.8


def heartbeat(seed=21, dur=1.2):
    t = _t(dur)
    def thump(t0):
        tt = np.clip(t - t0, 0, None)
        return np.sin(2 * np.pi * 50 * tt) * np.exp(-tt * 18) * (t >= t0)
    return thump(0) + thump(0.28) * 0.7


VOICES = {
    "impact": impact, "sub": sub_drop, "metal": metal_hit, "whoosh": whoosh,
    "rwhoosh": lambda seed=4: whoosh(seed, 1.2, True), "riser": riser, "atmos": atmos, "debris": debris,
    "shimmer": shimmer, "tail": tail, "thunder": thunder, "crackle": crackle, "fire": fire, "wind": wind,
    "digital": digital, "glitch": glitch, "swell": swell, "ice": ice, "water": water, "rain": rain_snd,
    "hammer": hammer, "heartbeat": heartbeat,
}
# aliases used in cue sheets
ALIAS = {"reverse_whoosh": "rwhoosh", "sub_bass": "sub", "metallic_hit": "metal", "electrical": "crackle",
         "atmosphere": "atmos"}

GAINS = {"atmos": 0.35, "riser": 0.35, "whoosh": 0.45, "rwhoosh": 0.45, "impact": 0.9, "sub": 0.6, "debris": 0.4,
         "shimmer": 0.25, "tail": 0.4, "thunder": 0.7, "crackle": 0.25, "metal": 0.6, "fire": 0.35, "wind": 0.3,
         "digital": 0.3, "glitch": 0.3, "swell": 0.4, "ice": 0.35, "water": 0.4, "rain": 0.35, "hammer": 0.55,
         "heartbeat": 0.6}


def mix(cues, total_frames, fps=24, seed=0):
    """cues: list of (frame, kind[, label]). Riser lasts until the next impact-like cue."""
    n = int(total_frames / fps * SR) + 1
    L = np.zeros(n)
    R = np.zeros(n)
    frames_impact = sorted(f for f, k, *_ in cues if ALIAS.get(k, k) in ("impact", "metal", "thunder", "hammer"))
    for i, (f, kind, *_) in enumerate(cues):
        k = ALIAS.get(kind, kind)
        if k not in VOICES:
            continue
        start = int(f / fps * SR)
        sd = seed * 31 + i
        if k == "riser":
            nxt = [x for x in frames_impact if x > f]
            d = ((nxt[0] - f) / fps) if nxt else 2.5
            s = riser(sd, max(0.5, d))
        elif k in ("atmos", "wind", "rain", "water", "fire"):
            d = max(1.0, (total_frames - f) / fps)
            s = VOICES[k](sd, d) if k != "atmos" else atmos(sd, d)
        else:
            s = VOICES[k](sd)
        s = norm(s) * GAINS.get(k, 0.4)
        pan = 0.5 + 0.25 * math.sin(i * 1.7)
        end = min(n, start + len(s))
        if start >= n:
            continue
        L[start:end] += s[: end - start] * math.sqrt(1 - pan)
        R[start:end] += s[: end - start] * math.sqrt(pan)
    st = np.stack([L, R], 1)
    peak = np.max(np.abs(st)) + 1e-9
    st = np.tanh(st / peak * 1.2) * 0.85
    return st


def write_wav(path, st):
    data = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
