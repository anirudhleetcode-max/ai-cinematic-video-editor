"""Download the optional local ONNX models (all free, permissively licensed, run fully offline).

  python scripts/download_models.py [--dest <data>/models]

  vision/ (editor.vision.DeepVisionProvider, run by OpenCV DNN — no PyTorch/TensorFlow):
    * YuNet face detector (face_detection_yunet_2023mar.onnx, ~0.23 MB) — MIT
    * NanoDet-Plus-m 416 COCO-80 object detector (object_detection_nanodet_2022nov.onnx, ~3.8 MB) — Apache-2.0
  vad/ (editor.media.vad, run by onnxruntime):
    * Silero VAD v5 (silero_vad.onnx, ~2.3 MB) — MIT
Without them the engine uses the classic OpenCV detectors and the DSP speech detector, and reports which was used.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
MODELS = {
    "vision/face_detection_yunet_2023mar.onnx": (BASE + "face_detection_yunet/face_detection_yunet_2023mar.onnx", "MIT"),
    "vision/object_detection_nanodet_2022nov.onnx": (BASE + "object_detection_nanodet/object_detection_nanodet_2022nov.onnx", "Apache-2.0"),
    "vad/silero_vad.onnx": ("https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx", "MIT"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    default = Path(os.environ.get("EDITOR_DATA_DIR", ROOT / "data")) / "models"
    ap.add_argument("--dest", default=str(default))
    dest = Path(ap.parse_args().dest)
    dest.mkdir(parents=True, exist_ok=True)
    for name, (url, lic) in MODELS.items():
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            tmp = out.with_suffix(".part")
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as fh:
                shutil.copyfileobj(r, fh)
            if tmp.stat().st_size < 10_000:  # a Git-LFS pointer instead of the model
                tmp.unlink()
                raise SystemExit(f"download of {name} returned a pointer file, not the model")
            tmp.replace(out)
        print(f"{name}: {out.stat().st_size / 1e6:.2f} MB, sha256 {hashlib.sha256(out.read_bytes()).hexdigest()[:16]}…, licence {lic}")
    (dest / "LICENSES.txt").write_text("\n".join(f"{n}: {lic} (OpenCV Zoo, {u})" for n, (u, lic) in MODELS.items()) + "\n")
    print(f"models in {dest} (the engine looks in <EDITOR_DATA_DIR>/models; override with EDITOR_MODELS_DIR)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
