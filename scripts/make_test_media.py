"""Generate a synthetic, copyright-free test/DEMO dataset (clips with known defects, songs with known BPM, a
reference video with a known rhythm, and a logo).  Usage: python scripts/make_test_media.py out_dir [--clips 20]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "engine"))
from editor import testmedia  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--clips", type=int, default=20)
ap.add_argument("--songs", type=int, default=3)
ap.add_argument("--width", type=int, default=1280)
ap.add_argument("--height", type=int, default=720)
a = ap.parse_args()
d = testmedia.make_dataset(Path(a.out), n_clips=a.clips, n_songs=a.songs, w=a.width, h=a.height)
print(f"DEMO dataset written to {a.out}: {len(d['clips'])} clips, {len(d['songs'])} songs, reference={bool(d['reference'])}, logo")
