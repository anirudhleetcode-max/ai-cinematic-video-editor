"""Synthetic test-media generator (no copyrighted material).

Produces video clips with known properties (sharp / blurry / dark / shaky / duplicate / black-frame /
speech-like audio), music tracks with known BPM and section structure, and a reference video with a
known cutting rhythm and grade. Used by tests, the benchmark and DEMO mode.
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import soundfile as sf

from .config import get_settings
from .proc import run

SOURCES = [
    "testsrc2=s={w}x{h}:r={fps}",
    "mandelbrot=s={w}x{h}:r={fps}",
    "life=s={w}x{h}:r={fps}:mold=10:ratio=0.1:death_color=#2b2b40:life_color=#e0b060",
    "cellauto=s={w}x{h}:r={fps}:rule=110",
    "gradients=s={w}x{h}:r={fps}:speed=0.04:nb_colors=4",
    "smptehdbars=s={w}x{h}:r={fps}",
    "rgbtestsrc=s={w}x{h}:r={fps}",
]


def _speech_like(seconds: float, sr: int = 48000, seed: int = 0) -> np.ndarray:
    """Syllable-modulated harmonic signal with formant-like resonances — reads as 'speech' to VAD-style
    detectors (energy in 300–3400 Hz, syllabic 4–5 Hz modulation, pauses)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    f0 = 140 + 25 * np.sin(2 * np.pi * 0.7 * t)
    phase = 2 * np.pi * np.cumsum(f0) / sr
    sig = sum(np.sin(k * phase) * (1 / k) * (1 + 0.8 * np.exp(-((k * 140 - f) ** 2) / 4e4))
              for k in range(1, 25) for f in (700,)) / 6
    syll = (0.5 + 0.5 * np.sin(2 * np.pi * 4.3 * t)) ** 2
    gate = np.ones_like(t)
    for _ in range(int(seconds / 2)):
        s = rng.uniform(0, seconds - 0.4)
        gate[int(s * sr):int((s + rng.uniform(0.2, 0.4)) * sr)] = 0
    return (sig * syll * gate * 0.3).astype(np.float32)


def make_clip(out: Path, seconds: float, kind: str = "normal", seed: int = 0, w: int = 1280, h: int = 720,
              fps: int = 30, speech: bool = False, src_index: int | None = None) -> Path:
    s = get_settings()
    rnd = random.Random(seed)
    src = SOURCES[src_index if src_index is not None else rnd.randrange(len(SOURCES))].format(w=w, h=h, fps=fps)
    vf = []
    # give each clip some camera-like motion so motion analysis has signal
    zx = rnd.choice(["iw*0.05*sin(t*0.6)", "iw*0.08*t/10", "0"])
    vf.append(f"crop=iw*0.85:ih*0.85:iw*0.075+{zx}:ih*0.075,scale={w}:{h}")
    if kind == "blurry":
        vf.append("gblur=sigma=9")
    elif kind == "dark":
        vf.append("eq=brightness=-0.42:contrast=0.6")
    elif kind == "overexposed":
        vf.append("eq=brightness=0.45:contrast=0.5")
    elif kind == "shaky":
        vf = [f"crop=iw*0.8:ih*0.8:iw*0.1+iw*0.07*sin(t*23):ih*0.1+ih*0.07*cos(t*17),scale={w}:{h}"]
    elif kind == "warm":
        vf.append("colorbalance=rs=0.25:gs=0.05:bs=-0.25:rm=0.2:bm=-0.2")
    elif kind == "cool":
        vf.append("colorbalance=rs=-0.2:bs=0.25:rm=-0.15:bm=0.2")
    if kind == "blackframes":
        vf.append(f"fade=t=out:st={seconds * 0.5:.2f}:d=0.2,fade=t=in:st={seconds * 0.5 + 1.0:.2f}:d=0.2")
    vf.append("format=yuv420p")
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".tmp.wav")
    if speech:
        sf.write(wav, _speech_like(seconds, seed=seed), 48000)
    else:
        sr = 48000
        n = int(seconds * sr)
        amb = np.random.default_rng(seed).standard_normal(n).astype(np.float32) * 0.01
        sf.write(wav, amb, sr)
    run([s.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", src, "-i", str(wav), "-t", f"{seconds:.3f}",
         "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k", "-shortest", str(out)], timeout=600)
    wav.unlink(missing_ok=True)
    return out


def make_song(out: Path, seconds: float, bpm: float, seed: int = 0, sr: int = 44100, key: int = 0) -> Path:
    """Drum-machine track with intro (quiet) → build → drop (loud) → outro sections."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    y = np.zeros(n, np.float32)
    beat = 60.0 / bpm
    sections = [(0, 0.2, "intro"), (0.2, 0.45, "build"), (0.45, 0.8, "drop"), (0.8, 1.0, "outro")]

    def level(x: float) -> float:
        for a, b, name in sections:
            if a <= x < b:
                return {"intro": 0.25, "build": 0.55, "drop": 1.0, "outro": 0.35}[name]
        return 0.3

    kick_len = int(0.25 * sr)
    kt = np.arange(kick_len) / sr
    kick = (np.sin(2 * np.pi * (50 + 120 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 12)).astype(np.float32)
    hat = (rng.standard_normal(int(0.05 * sr)) * np.exp(-np.arange(int(0.05 * sr)) / sr * 80)).astype(np.float32) * 0.3
    i = 0
    while i * beat < seconds:
        at = int(i * beat * sr)
        lv = level(i * beat / seconds)
        k = kick * (1.0 if i % 4 == 0 else 0.75) * lv
        y[at:at + len(k)] += k[: n - at]
        h_at = int((i + 0.5) * beat * sr)
        if h_at < n and lv > 0.3:
            y[h_at:h_at + len(hat)] += hat[: n - h_at] * lv
        i += 1
    roots = [0, 5, 7, 3]
    for bar in range(int(seconds / (4 * beat)) + 1):
        a, b = int(bar * 4 * beat * sr), min(n, int((bar + 1) * 4 * beat * sr))
        if a >= n:
            break
        tt = t[a:b]
        r = 220 * 2 ** ((roots[bar % 4] + key) / 12)
        chord = sum(np.sin(2 * np.pi * r * m * tt) for m in (1, 1.26, 1.5)) / 3
        y[a:b] += (chord * 0.12 * level(a / n)).astype(np.float32)
    y /= max(1e-6, np.abs(y).max()) / 0.8
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, np.stack([y, y], 1), sr)
    return out


def make_reference(out: Path, seconds: float = 20.0, shot: float = 1.2, w: int = 1280, h: int = 720, seed: int = 7) -> Path:
    """Reference with a known rhythm: cuts every `shot` seconds, warm high-contrast grade, a fade every 5th cut."""
    s = get_settings()
    tmp = out.parent / f"_ref_parts_{seed}"
    tmp.mkdir(parents=True, exist_ok=True)
    parts = []
    nshots = int(seconds / shot)
    for i in range(nshots):
        p = tmp / f"p{i:03d}.mp4"
        src = SOURCES[(i * 3 + seed) % len(SOURCES)].format(w=w, h=h, fps=30)
        vf = f"eq=contrast=1.25:saturation=1.35,colorbalance=rm=0.12:bm=-0.12,format=yuv420p"
        if i % 5 == 4:
            vf += f",fade=t=in:st=0:d=0.3"
        run([s.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", src, "-t", f"{shot:.3f}", "-vf", vf,
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-an", str(p)], timeout=300)
        parts.append(p)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    song = make_song(tmp / "ref_song.wav", seconds, 124, seed=seed)
    run([s.ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(song),
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", "-shortest", str(out)], timeout=600)
    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()
    return out


def make_logo(out: Path, text: str = "LOGO") -> Path:
    s = get_settings()
    font = get_settings().fonts_dir / "Montserrat_800ExtraBold.ttf"
    out.parent.mkdir(parents=True, exist_ok=True)
    run([s.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black@0.0:s=600x200,format=rgba",
         "-vf", f"drawtext=fontfile='{font.as_posix()}':text={text}:fontsize=120:fontcolor=white:x=(w-tw)/2:y=(h-th)/2",
         "-frames:v", "1", str(out)], timeout=60)
    return out


def make_dataset(root: Path, n_clips: int = 12, n_songs: int = 2, with_reference: bool = True, clip_seconds: tuple[float, float] = (3.0, 7.0),
                 w: int = 1280, h: int = 720, seed: int = 1) -> dict:
    """Build a dataset with a realistic mix of good and bad shots. Returns paths grouped by role."""
    rnd = random.Random(seed)
    clips = []
    kinds = ["normal"] * 6 + ["warm", "cool", "blurry", "dark", "shaky", "overexposed", "blackframes"]
    for i in range(n_clips):
        kind = kinds[i % len(kinds)] if i >= 3 else "normal"
        dur = rnd.uniform(*clip_seconds)
        p = make_clip(root / "clips" / f"clip_{i:03d}_{kind}.mp4", dur, kind=kind, seed=seed * 1000 + i, w=w, h=h,
                      speech=(i % 4 == 1), src_index=i % len(SOURCES))
        clips.append(p)
    # one deliberate near-duplicate of clip 0
    if n_clips >= 4:
        clips.append(make_clip(root / "clips" / f"clip_{n_clips:03d}_duplicate.mp4", 3.0, kind="normal", seed=seed * 1000 + 0, w=w, h=h, src_index=0))
    songs = [make_song(root / "music" / f"song_{j + 1}.wav", rnd.uniform(70, 110), bpm=[96, 128, 110, 140, 84][j % 5], seed=seed + j, key=j * 2)
             for j in range(n_songs)]
    ref = make_reference(root / "reference" / "reference.mp4", 16.0, shot=1.2, w=w, h=h) if with_reference else None
    logo = make_logo(root / "brand" / "logo.png", "EVENT")
    return {"clips": clips, "songs": songs, "reference": ref, "logo": logo}
