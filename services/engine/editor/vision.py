"""Vision providers: what is *in* a frame.

    VisionProvider          interface: detect(frame_rgb) -> FrameVision
    OpenCVProvider          classic, always available: Haar frontal faces + HOG pedestrians. It detects faces and
                            upright people only — it has NO semantic understanding of objects or scenes.
    DeepVisionProvider      optional, local ONNX models run by OpenCV DNN (scripts/download_vision_models.py):
                            YuNet faces + NanoDet-Plus COCO-80 objects (people, vehicles, food, sports gear, screens…).
    get_vision_provider()   the best provider whose models are actually present (deterministic fallback = OpenCV).

Everything here is local; no frame ever leaves the machine. Scene attributes that no model provides (indoor/outdoor,
day/night, nature, buildings) are computed by explicit heuristics in `scene_heuristics` and labelled "heuristic".
"""
from __future__ import annotations

import math
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from .config import get_settings

COCO = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light", "fire hydrant", "stop sign",
        "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
        "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
        "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
        "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv",
        "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
        "scissors", "teddy bear", "hair drier", "toothbrush"]
# COCO label → editing subject category (only categories a COCO detector can actually see)
SUBJECT_OF = {
    "person": "people", **{k: "vehicles" for k in ("bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat")},
    **{k: "animals" for k in ("bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe")},
    **{k: "food" for k in ("banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "bowl", "wine glass",
                           "cup", "fork", "knife", "spoon", "dining table")},
    **{k: "sports" for k in ("frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
                             "tennis racket")},
    **{k: "screen" for k in ("tv", "laptop", "cell phone", "keyboard", "mouse", "remote")},
    **{k: "products" for k in ("bottle", "handbag", "backpack", "suitcase", "umbrella", "tie", "vase", "clock", "book", "teddy bear")},
    **{k: "street" for k in ("traffic light", "fire hydrant", "stop sign", "parking meter", "bench")},
    **{k: "interior" for k in ("chair", "couch", "bed", "toilet", "sink", "refrigerator", "microwave", "oven", "toaster", "potted plant")},
}


@dataclass
class FrameVision:
    faces: list[tuple[float, float, float, float, float]] = field(default_factory=list)  # normalised x, y, w, h, score
    objects: list[tuple[str, float, tuple[float, float, float, float]]] = field(default_factory=list)  # label, score, box
    people: int = 0
    provider: str = ""


class VisionProvider:
    name = "base"
    semantic = False  # True only when the provider recognises object categories

    def detect(self, rgb: np.ndarray) -> FrameVision:  # pragma: no cover - interface
        raise NotImplementedError


class OpenCVProvider(VisionProvider):
    """Haar frontal-face cascade + HOG upright-pedestrian detector (OpenCV built-ins)."""
    name = "opencv-classic"

    def __init__(self, people: bool = True):
        self.people = people
        self._lock = threading.Lock()
        self._face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, rgb: np.ndarray) -> FrameVision:
        h, w = rgb.shape[:2]
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        with self._lock:
            fs = self._face.detectMultiScale(cv2.equalizeHist(g), scaleFactor=1.15, minNeighbors=5, minSize=(max(12, w // 25),) * 2)
            faces = [(x / w, y / h, fw / w, fh / h, 1.0) for x, y, fw, fh in (fs if len(fs) else [])]
            people = 0
            objs = []
            if self.people and w >= 160:
                rects, weights = self._hog.detectMultiScale(g, winStride=(8, 8), padding=(4, 4), scale=1.08)
                for (x, y, rw, rh), sc in zip(rects if len(rects) else [], np.ravel(weights) if len(rects) else []):
                    if sc > 0.6:
                        people += 1
                        objs.append(("person", float(min(1.0, sc / 2)), (x / w, y / h, rw / w, rh / h)))
        return FrameVision(faces=faces, objects=objs, people=max(people, len(faces)), provider=self.name)


class DeepVisionProvider(VisionProvider):
    """YuNet faces + NanoDet-Plus (416, COCO-80) through cv2.dnn. CPU, ~20–40 ms per frame at 416²."""
    name = "onnx-yunet-nanodet"
    semantic = True
    SIZE = 416
    STRIDES = (8, 16, 32)
    REG_MAX = 7

    def __init__(self, model_dir: Path, score_thr: float = 0.4, nms_thr: float = 0.5):
        self.score_thr, self.nms_thr = score_thr, nms_thr
        self._lock = threading.Lock()
        self.net = cv2.dnn.readNet(str(model_dir / "object_detection_nanodet_2022nov.onnx"))
        self.face = cv2.FaceDetectorYN.create(str(model_dir / "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.7, 0.3, 50)
        self.anchors = []
        for st in self.STRIDES:
            n = int(math.ceil(self.SIZE / st))
            xv, yv = np.meshgrid(np.arange(n) * st, np.arange(n) * st)
            self.anchors.append(np.stack([xv.ravel() + 0.5 * (st - 1), yv.ravel() + 0.5 * (st - 1)], 1).astype(np.float32))
        self.mean = np.array([103.53, 116.28, 123.675], np.float32)
        self.std = np.array([57.375, 57.12, 58.395], np.float32)

    def _objects(self, rgb: np.ndarray) -> list[tuple[str, float, tuple[float, float, float, float]]]:
        h, w = rgb.shape[:2]
        s = self.SIZE / max(h, w)
        nh, nw = int(round(h * s)), int(round(w * s))
        canvas = np.zeros((self.SIZE, self.SIZE, 3), np.float32)
        canvas[:nh, :nw] = cv2.resize(rgb[..., ::-1], (nw, nh), interpolation=cv2.INTER_AREA)  # BGR, letterboxed top-left
        blob = cv2.dnn.blobFromImage((canvas - self.mean) / self.std)
        with self._lock:
            self.net.setInput(blob)
            outs = self.net.forward(self.net.getUnconnectedOutLayersNames())
        boxes, scores, labels = [], [], []
        proj = np.arange(self.REG_MAX + 1, dtype=np.float32)
        for k, st in enumerate(self.STRIDES):
            cls, reg = outs[2 * k][0], outs[2 * k + 1][0]
            best = cls.max(1)
            keep = best > self.score_thr
            if not keep.any():
                continue
            r = reg[keep].reshape(-1, 4, self.REG_MAX + 1)
            e = np.exp(r - r.max(-1, keepdims=True))
            d = (e / e.sum(-1, keepdims=True) @ proj) * st
            a = self.anchors[k][keep]
            x1, y1, x2, y2 = a[:, 0] - d[:, 0], a[:, 1] - d[:, 1], a[:, 0] + d[:, 2], a[:, 1] + d[:, 3]
            for i in range(len(a)):
                boxes.append([float(x1[i]), float(y1[i]), float(x2[i] - x1[i]), float(y2[i] - y1[i])])
                scores.append(float(best[keep][i]))
                labels.append(int(cls[keep][i].argmax()))
        if not boxes:
            return []
        idx = cv2.dnn.NMSBoxesBatched(boxes, scores, labels, self.score_thr, self.nms_thr)
        out = []
        for i in np.ravel(idx):
            x, y, bw, bh = boxes[i]
            x, y, bw, bh = x / s, y / s, bw / s, bh / s
            out.append((COCO[labels[i]], round(scores[i], 3), (max(0.0, x / w), max(0.0, y / h), min(1.0, bw / w), min(1.0, bh / h))))
        return out

    def detect(self, rgb: np.ndarray) -> FrameVision:
        h, w = rgb.shape[:2]
        objs = self._objects(rgb)
        with self._lock:
            self.face.setInputSize((w, h))
            _, fs = self.face.detect(np.ascontiguousarray(rgb[..., ::-1]))
        faces = [(float(f[0]) / w, float(f[1]) / h, float(f[2]) / w, float(f[3]) / h, float(f[-1])) for f in (fs if fs is not None else [])]
        people = sum(1 for lbl, _, _ in objs if lbl == "person")
        return FrameVision(faces=faces, objects=objs, people=max(people, len(faces)), provider=self.name)


def scene_heuristics(rgb: np.ndarray, labels: list[str] | None = None) -> dict:
    """Explicit, documented heuristics (NOT a scene classifier). Every output is labelled "heuristic":
    sky = bright, untextured, clearly blue pixels in the top third; vegetation = green-dominant textured pixels;
    night = low global luma with sparse bright point lights; indoor = interior objects detected (if a semantic
    provider ran) or no sky/vegetation at all. Overcast skies and white walls are deliberately not called sky."""
    small = cv2.resize(rgb, (160, 90), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    r, g, b = small[..., 0], small[..., 1], small[..., 2]
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    gy, gx = np.gradient(luma)
    tex = np.hypot(gx, gy)
    top = slice(0, 30)
    sky = ((tex[top] < 0.02) & (luma[top] > 0.35) & (b[top] > r[top] + 0.06) & (b[top] >= g[top])).mean()
    veg = ((g > r + 0.04) & (g > b + 0.02) & (tex > 0.015)).mean()
    lights = (luma > 0.85).mean()
    night = bool(luma.mean() < 0.22 and 0.0005 < lights < 0.08)
    interior = bool(labels and any(SUBJECT_OF.get(l) == "interior" or l in ("tv", "laptop", "dining table") for l in labels))
    outdoor = bool(sky > 0.15 or veg > 0.25 or (labels and any(SUBJECT_OF.get(l) in ("vehicles", "street") for l in labels)))
    setting = "outdoor" if outdoor and not interior else ("indoor" if interior or (sky < 0.02 and veg < 0.03) else "unknown")
    return {"sky_fraction": round(float(sky), 3), "vegetation_fraction": round(float(veg), 3), "setting": setting,
            "time_of_day": "night" if night else ("day" if luma.mean() > 0.3 or sky > 0.1 else "unknown"),
            "edge_density": round(float((tex > 0.04).mean()), 3), "source": "heuristic"}


_provider: VisionProvider | None = None
_plock = threading.Lock()


def models_root() -> Path:
    env = os.environ.get("EDITOR_MODELS_DIR")
    return Path(env) if env else get_settings().data_dir / "models"


def models_dir() -> Path:
    return models_root() / "vision"


def get_vision_provider() -> VisionProvider:
    """DeepVisionProvider if its model files exist (and EDITOR_VISION != 'opencv'), else OpenCVProvider."""
    global _provider
    with _plock:
        if _provider is None:
            d = models_dir()
            want = os.environ.get("EDITOR_VISION", "auto")
            if want != "opencv" and (d / "object_detection_nanodet_2022nov.onnx").exists() and (d / "face_detection_yunet_2023mar.onnx").exists():
                try:
                    _provider = DeepVisionProvider(d)
                except cv2.error:
                    _provider = OpenCVProvider()
            else:
                _provider = OpenCVProvider()
        return _provider


def reset_provider() -> None:
    global _provider
    with _plock:
        _provider = None
