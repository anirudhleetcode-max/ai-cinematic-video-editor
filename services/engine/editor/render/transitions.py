"""Transition clips built from the tail of shot A and the head of shot B (same frame count n).
Native FFmpeg xfade for built-in transitions; numpy/OpenCV for procedural families. On any failure
the transition degrades to a hard cut at its midpoint (duration preserved)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from ..config import get_settings
from ..logging import get_logger, log
from ..proc import MediaCommandError, run
from ..registry.transitions import _ease, transition_spec
from .segments import x264_mezz_args

logger = get_logger("render.transition")


def _read_frames(path: Path, w: int, h: int) -> np.ndarray:
    st = get_settings()
    p = subprocess.run([st.ffmpeg, "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=600)
    if p.returncode != 0:
        raise MediaCommandError(["ffmpeg"], p.returncode, p.stderr.decode("utf-8", "replace"))
    n = len(p.stdout) // (w * h * 3)
    return np.frombuffer(p.stdout[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)


def _encode_frames(frames, out: Path, w: int, h: int, fps: float, quality: str) -> None:
    st = get_settings()
    enc = subprocess.Popen([st.ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
                            *x264_mezz_args(quality), "-an", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert enc.stdin is not None
    for f in frames:
        enc.stdin.write(np.ascontiguousarray(f).tobytes())
    enc.stdin.close()
    enc.wait()
    if enc.returncode != 0:
        raise MediaCommandError(["ffmpeg"], enc.returncode, enc.stderr.read().decode() if enc.stderr else "")


def render_transition(tid: str, params: dict, tail_a: Path, head_b: Path, out: Path, w: int, h: int, fps: float, quality: str) -> tuple[Path, str | None]:
    """Returns (path, fallback_note)."""
    spec, p, dur = transition_spec(tid, params)
    try:
        if spec.get("engine") == "xfade":
            st = get_settings()
            n_dur = dur
            run([st.ffmpeg, "-v", "error", "-y", "-i", str(tail_a), "-i", str(head_b), "-filter_complex",
                 f"[0:v][1:v]xfade=transition={spec['transition']}:duration={n_dur:.4f}:offset=0,format=yuv420p[v]", "-map", "[v]",
                 *x264_mezz_args(quality), "-an", str(out)], timeout=600)
            return out, None
        a = _read_frames(tail_a, w, h)
        b = _read_frames(head_b, w, h)
        n = min(len(a), len(b))
        fn, easing = spec["fn"], spec["easing"]

        def gen():
            for i in range(n):
                q = _ease((i + 0.5) / n, easing)
                fa = a[i].astype(np.float32) / 255.0
                fb = b[i].astype(np.float32) / 255.0
                yield (np.clip(fn(fa, fb, q, p), 0, 1) * 255 + 0.5).astype(np.uint8)

        _encode_frames(gen(), out, w, h, fps, quality)
        return out, None
    except Exception as e:  # never let a transition break the render
        log(logger, "transition failed; using midpoint cut", tid=tid, error=str(e)[:300])
        a = _read_frames(tail_a, w, h)
        b = _read_frames(head_b, w, h)
        n = min(len(a), len(b))
        _encode_frames((a[i] if i < n // 2 else b[i] for i in range(n)), out, w, h, fps, quality)
        return out, f"{tid} → cut ({type(e).__name__})"
