"""Speech activity detection.

SileroVAD (optional, local ONNX via onnxruntime — scripts/download_models.py) is used when its model file exists;
otherwise the DSP detector in editor.media.audio is used. The result always says which detector produced it.
"""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

_sess = None
_lock = threading.Lock()
SR = 16000
CHUNK, CTX = 512, 64


def model_path() -> Path:
    from ..vision import models_root

    return models_root() / "vad" / "silero_vad.onnx"


def available() -> bool:
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return model_path().exists()


def _session():
    global _sess
    with _lock:
        if _sess is None:
            import onnxruntime as ort

            so = ort.SessionOptions()
            so.intra_op_num_threads, so.inter_op_num_threads = 1, 1
            _sess = ort.InferenceSession(str(model_path()), sess_options=so, providers=["CPUExecutionProvider"])
        return _sess


def speech_probabilities(y16k: np.ndarray) -> np.ndarray:
    """Per-32 ms speech probability for mono float32 audio at 16 kHz (Silero VAD v5, stateful)."""
    sess = _session()
    state = np.zeros((2, 1, 128), np.float32)
    ctx = np.zeros((1, CTX), np.float32)
    n = len(y16k) // CHUNK
    out = np.zeros(n, np.float32)
    sr = np.array(SR, np.int64)
    for i in range(n):
        x = np.concatenate([ctx, y16k[i * CHUNK:(i + 1) * CHUNK].reshape(1, -1).astype(np.float32)], axis=1)
        p, state = sess.run(None, {"input": x, "state": state, "sr": sr})
        out[i] = float(p.reshape(-1)[0])
        ctx = x[:, -CTX:]
    return out


def speech_segments(y16k: np.ndarray, threshold: float = 0.5, min_speech: float = 0.25, min_gap: float = 0.3) -> tuple[list[list[float]], float]:
    """Speech intervals (seconds) with hysteresis (on ≥ threshold, off < threshold − 0.15) and the speech fraction."""
    p = speech_probabilities(y16k)
    hop = CHUNK / SR
    on, start, segs = False, 0.0, []
    for i, v in enumerate(p):
        t = i * hop
        if not on and v >= threshold:
            on, start = True, t
        elif on and v < threshold - 0.15:
            on = False
            segs.append([start, t])
    if on:
        segs.append([start, len(p) * hop])
    merged: list[list[float]] = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < min_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(list(s))
    merged = [[round(a, 3), round(b, 3)] for a, b in merged if b - a >= min_speech]
    frac = sum(b - a for a, b in merged) / max(1e-6, len(y16k) / SR)
    return merged, round(float(frac), 4)
