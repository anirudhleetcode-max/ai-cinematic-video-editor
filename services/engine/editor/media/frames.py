"""Low-resolution frame sampling + per-frame visual metrics.

Frames are decoded by ffmpeg straight into numpy (rawvideo pipe) at a small size and sampling rate,
so analysis cost is independent of the source resolution.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..config import get_settings


@dataclass
class FrameSet:
    times: np.ndarray  # (N,)
    rgb: np.ndarray  # (N, H, W, 3) uint8
    fps: float  # sampling rate


def sample_frames(path: Path, sample_fps: float, width: int = 256, start: float = 0.0, duration: float | None = None,
                  height: int | None = None, meta: dict | None = None) -> FrameSet:
    """Decode frames at `sample_fps` into a (N, H, W, 3) RGB array. Rotation is applied (FFmpeg autorotate), pixels are
    squared using the display size, and the source's own colour matrix/range is used (HDR is tone-mapped) so that
    the measured statistics describe what the viewer actually sees."""
    from ..render.colorspace import source_to_rgb

    s = get_settings()
    m = meta if meta is not None else _probe_meta(path)
    h = height or _infer_height(m, width)
    vf = f"fps={sample_fps},{source_to_rgb(m, width, h)}"
    cmd = [s.ffmpeg, "-v", "error", "-nostdin"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.run(cmd, capture_output=True, timeout=1800)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[-500:])
    raw = p.stdout
    fsz = width * h * 3
    n = len(raw) // fsz if fsz else 0
    arr = np.frombuffer(raw[: n * fsz], np.uint8).reshape(n, h, width, 3) if n else np.zeros((0, h, width, 3), np.uint8)
    return FrameSet(times=start + np.arange(n) / sample_fps, rgb=arr, fps=sample_fps)


def _probe_meta(path: Path) -> dict:
    from .probe import probe

    return probe(path)


def _infer_height(m: dict, width: int) -> int:
    w = m.get("display_width") or m.get("width") or 16
    h = m.get("display_height") or m.get("height") or 9
    hh = int(round(width * h / w))
    return max(2, hh + (hh % 2))


def hsv_hist(rgb: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, [16, 4, 4], [0, 180, 0, 256, 0, 256]).flatten()
    return h / (h.sum() + 1e-9)


def dhash(rgb: np.ndarray) -> int:
    g = cv2.cvtColor(cv2.resize(rgb, (9, 8), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int(sum(1 << i for i, b in enumerate(bits) if b))


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def frame_metrics(fs: FrameSet) -> dict[str, np.ndarray]:
    """Per-frame arrays: luma mean/std, sharpness, clipping, saturation, colorfulness, motion,
    global translation (for shake), histogram distance to previous frame."""
    n = len(fs.rgb)
    out = {k: np.zeros(n, np.float32) for k in
           ("luma", "contrast", "sharp", "dark_clip", "bright_clip", "sat", "colorful", "motion", "dx", "dy", "pc_resp", "hist_d", "temp", "tint")}
    hists = []
    prev_g = None
    for i, f in enumerate(fs.rgb):
        g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
        gf = g.astype(np.float32) / 255.0
        out["luma"][i] = gf.mean()
        out["contrast"][i] = gf.std()
        out["sharp"][i] = cv2.Laplacian(g, cv2.CV_32F).var()
        out["dark_clip"][i] = (g < 10).mean()
        out["bright_clip"][i] = (g > 245).mean()
        hsv = cv2.cvtColor(f, cv2.COLOR_RGB2HSV)
        out["sat"][i] = hsv[..., 1].mean() / 255.0
        r, gg, b = [f[..., c].astype(np.float32) for c in range(3)]
        rg, yb = r - gg, 0.5 * (r + gg) - b
        out["colorful"][i] = (np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)) / 255.0
        out["temp"][i] = (r.mean() - b.mean()) / 255.0  # warm(+)/cool(-)
        out["tint"][i] = (gg.mean() - 0.5 * (r.mean() + b.mean())) / 255.0
        hh = hsv_hist(f)
        hists.append(hh)
        if prev_g is not None:
            out["motion"][i] = np.abs(gf - prev_g).mean()
            dx, dy, coh = global_shift(prev_g, gf)
            out["dx"][i], out["dy"][i], out["pc_resp"][i] = dx, dy, coh
            out["hist_d"][i] = 0.5 * np.abs(hh - hists[-2]).sum()  # total variation distance in [0,1]
        prev_g = gf
    out["hists"] = np.array(hists, np.float32) if hists else np.zeros((0, 256), np.float32)
    return out


def global_shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Camera (global) translation between two grey frames in [0,1] with a confidence score.

    Dense Farneback optical flow; the camera shift is the median flow vector and confidence is the
    fraction of textured pixels moving with it. Moving subjects or animated graphics on a static camera
    leave the median near zero; genuine camera motion/shake moves (almost) the whole frame coherently."""
    a8 = (a * 255).astype(np.uint8)
    b8 = (b * 255).astype(np.uint8)
    flow = cv2.calcOpticalFlowFarneback(a8, b8, None, 0.5, 5, 13, 3, 5, 1.1, 0)
    gy, gx = np.gradient(a)
    tex = np.hypot(gx, gy) > 0.02
    if tex.mean() < 0.05:
        return 0.0, 0.0, 0.0
    fx, fy = flow[..., 0][tex], flow[..., 1][tex]
    mx, my = float(np.median(fx)), float(np.median(fy))
    coh = float(np.mean(np.hypot(fx - mx, fy - my) < 1.5))
    return mx, my, coh


_face = None


def detect_faces(rgb: np.ndarray) -> list[tuple[int, int, int, int]]:
    """OpenCV Haar frontal-face detector (bundled with opencv, no download)."""
    global _face
    if _face is None:
        _face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    g = cv2.equalizeHist(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
    faces = _face.detectMultiScale(g, scaleFactor=1.15, minNeighbors=5, minSize=(max(12, g.shape[1] // 25),) * 2)
    return [tuple(map(int, f)) for f in faces] if len(faces) else []


_hog = None


def detect_people(rgb: np.ndarray) -> int:
    """OpenCV HOG pedestrian detector; returns count of confident person boxes."""
    global _hog
    if _hog is None:
        _hog = cv2.HOGDescriptor()
        _hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if g.shape[1] < 160:
        return 0
    rects, weights = _hog.detectMultiScale(g, winStride=(8, 8), padding=(4, 4), scale=1.08)
    return int(sum(1 for w in np.ravel(weights) if w > 0.6)) if len(rects) else 0


def composition_score(rgb: np.ndarray) -> float:
    """Saliency (gradient-energy) centroid closeness to rule-of-thirds power points, in [0,1]."""
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    mag = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    tot = mag.sum()
    if tot <= 1e-6:
        return 0.0
    h, w = g.shape
    ys, xs = np.mgrid[0:h, 0:w]
    cx, cy = (mag * xs).sum() / tot / w, (mag * ys).sum() / tot / h
    pts = [(a, b) for a in (1 / 3, 2 / 3) for b in (1 / 3, 2 / 3)] + [(0.5, 0.5)]
    d = min(np.hypot(cx - a, cy - b) for a, b in pts)
    return float(np.clip(1 - d / 0.35, 0, 1))


def text_likelihood(rgb: np.ndarray) -> dict[str, float]:
    """Heuristic overlay-text detector: dense, horizontally-aligned high-contrast strokes.
    Returns a score per vertical band (top/middle/bottom). Heuristic — documented as such."""
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    grad = cv2.morphologyEx(g, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, g.shape[1] // 30), 1)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed)
    h, w = g.shape
    bands = {"top": 0.0, "middle": 0.0, "bottom": 0.0}
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if ww > w * 0.08 and 0.015 * h < hh < 0.15 * h and ww / max(hh, 1) > 2.5 and area / (ww * hh) > 0.45:
            band = "top" if y + hh / 2 < h / 3 else ("middle" if y + hh / 2 < 2 * h / 3 else "bottom")
            bands[band] += ww * hh / (w * h)
    return {k: float(min(1.0, v * 8)) for k, v in bands.items()}
