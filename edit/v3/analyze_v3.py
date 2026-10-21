"""v3 analysis: refined person masks, face boxes and hand-gesture events.

Writes $EDIT_WORK/v3_analysis.npz:
  masks  (N, 135, 240) uint8  - smoothed person mask (sat > 58 | dark), faces unioned
  faces  (N, 2, 4) float32    - up to two face boxes per frame in 1920x1080 px (0 = none)
  top    (N, 2, 2) float32    - topmost mask point per half (hand-raise tracking)
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("EDIT_SAT", "58")
import common  # noqa: E402
from common import N_OUT, SLOW_A, SLOW_B, WORK, person_mask, read_frames  # noqa: E402

LW, LH = 240, 135
MODEL = os.path.join(os.path.dirname(__file__), "assets", "face_detection_yunet_2023mar.onnx")


def face_detector():
    return cv2.FaceDetectorYN.create(MODEL, "", (640, 360), 0.6, 0.3, 5000)


def faces_of(det, frame):
    _, f = det.detect(cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA))
    out = np.zeros((2, 4), np.float32)
    if f is not None:
        f = sorted(f, key=lambda r: -r[14])[:2]
        for i, r in enumerate(f):
            out[i] = r[:4] * 3.0
    return out


def face_ellipses(mask, faces, scale):
    """Union generous ellipses around detected faces into a mask (safety net)."""
    for x, y, w, h in faces:
        if w <= 0:
            continue
        cx, cy = (x + w / 2) * scale, (y + h / 2) * scale
        cv2.ellipse(mask, (int(cx), int(cy)), (int(w * 0.75 * scale), int(h * 0.85 * scale)), 0, 0, 360, 255, -1)
    return mask


def main():
    assert common.SAT_T == 58
    det = face_detector()
    masks = np.zeros((N_OUT, LH, LW), np.uint8)
    faces = np.zeros((N_OUT, 2, 4), np.float32)
    top = np.zeros((N_OUT, 2, 2), np.float32)
    ema = None
    for i, fr in enumerate(read_frames(0, N_OUT, 960, 540)):
        faces[i] = faces_of(det, fr)
        m = person_mask(cv2.resize(fr, (480, 270), interpolation=cv2.INTER_AREA))
        m = face_ellipses(m, faces[i], 480 / 1920)
        m = cv2.resize(m, (LW, LH), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        ema = m if (ema is None or i in (SLOW_A, SLOW_B)) else 0.5 * ema + 0.5 * m
        mb = (ema > 0.5).astype(np.uint8)
        masks[i] = mb
        for h in range(2):
            sub = mb[:, h * LW // 2:(h + 1) * LW // 2]
            ys, xs = np.nonzero(sub)
            if len(ys):
                j = np.argmin(ys)
                top[i, h] = (xs[j] + h * LW // 2, ys[j])
            else:
                top[i, h] = (h * LW // 2 + LW // 4, LH)
        if i % 500 == 0:
            print("analysed", i, flush=True)
    np.savez_compressed(os.path.join(WORK, "v3_analysis.npz"), masks=masks, faces=faces, top=top)
    print("faces found in", int((faces[:, :, 2] > 0).any(1).sum()), "of", N_OUT, "frames")


if __name__ == "__main__":
    main()
