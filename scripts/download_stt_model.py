"""Download a free offline speech-to-text model (NVIDIA Parakeet-TDT 0.6B v2, int8, via the sherpa-onnx project releases on
GitHub) for automatic subtitles. ~480 MB. Then set EDITOR_STT_MODEL_DIR to the printed folder and `pip install sherpa-onnx`.
Usage: python scripts/download_stt_model.py [dest_dir]"""
import sys
import tarfile
import urllib.request
from pathlib import Path

URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2"
dest = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data" / "models")
dest.mkdir(parents=True, exist_ok=True)
arc = dest / "parakeet.tar.bz2"
if not arc.exists():
    print("downloading", URL)
    urllib.request.urlretrieve(URL, arc)
with tarfile.open(arc) as t:
    t.extractall(dest)
arc.unlink()
model = next(p for p in dest.iterdir() if p.is_dir() and "parakeet" in p.name)
print(f"\nDone. Set:\n  EDITOR_STT_MODEL_DIR={model}\nand install:  pip install sherpa-onnx")
