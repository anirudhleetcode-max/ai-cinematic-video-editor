"""Download a small library of REAL, openly licensed media for real-footage testing.

Nothing downloaded here is committed (tests/real_media/ is git-ignored). Each file's source and licence are
written to tests/real_media/library/ATTRIBUTION.md.

  python scripts/fetch_real_media.py            # default set (~120 MB)
  python scripts/fetch_real_media.py --all      # every listed file (~260 MB)

Sources (all real recordings, not synthetic):
  * intel-iot-devkit/sample-videos — real camera footage, CC-BY-4.0
  * librosa/data — real music recordings and LibriSpeech speech (licence per file below)
  * opencv/opencv samples — real pedestrian footage (vtest.avi, BSD/Apache sample data)
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "tests" / "real_media" / "library"

INTEL = "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/"
LIBROSA = "https://raw.githubusercontent.com/librosa/data/main/audio/"
OPENCV = "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/"

# (url, relative destination, licence, attribution, in default set)
FILES: list[tuple[str, str, str, str, bool]] = [
    (INTEL + "people-detection.mp4", "video/people-detection.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "face-demographics-walking.mp4", "video/face-demographics-walking.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "face-demographics-walking-and-pause.mp4", "video/face-demographics-walking-and-pause.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "one-by-one-person-detection.mp4", "video/one-by-one-person-detection.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "person-bicycle-car-detection.mp4", "video/person-bicycle-car-detection.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "car-detection.mp4", "video/car-detection.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "bottle-detection.mp4", "video/bottle-detection.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "classroom.mp4", "video/classroom.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "head-pose-face-detection-female.mp4", "video/head-pose-face-detection-female.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "store-aisle-detection.mp4", "video/store-aisle-detection.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True),
    (INTEL + "fruit-and-vegetable-detection.mp4", "video/fruit-and-vegetable-detection.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", False),
    (INTEL + "worker-zone-detection.mp4", "video/worker-zone-detection.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", False),
    (INTEL + "head-pose-face-detection-male.mp4", "video/head-pose-face-detection-male.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", False),
    (INTEL + "bolt-detection.mp4", "video/bolt-detection.mp4", "CC-BY-4.0", "Intel IoT DevKit sample-videos", False),
    *[(INTEL + f"asl_gestures/{w}.mkv", f"video/asl_{w}.mkv", "CC-BY-4.0", "Intel IoT DevKit sample-videos", True)
      for w in ("again", "book", "help", "thanks", "walk", "school")],
    (OPENCV + "vtest.avi", "video/opencv_vtest.avi", "OpenCV sample data (BSD-3/Apache-2.0)", "OpenCV project", True),
    (LIBROSA + "Kevin_MacLeod_-_Vibe_Ace.hq.ogg", "music/vibe_ace.ogg", "CC-BY-4.0", "Kevin MacLeod — Vibe Ace (incompetech.com)", True),
    (LIBROSA + "Kevin_MacLeod_-_P_I_Tchaikovsky_Dance_of_the_Sugar_Plum_Fairy.hq.ogg", "music/sugar_plum_fairy.ogg", "CC-BY-4.0",
     "Kevin MacLeod — Dance of the Sugar Plum Fairy (incompetech.com)", True),
    (LIBROSA + "Hungarian_Dance_number_5_-_Allegro_in_F_sharp_minor_(string_orchestra).hq.ogg", "music/hungarian_dance_5.ogg", "CC-PDM-1.0",
     "Hungarian Dance No. 5 (public domain mark)", True),
    (LIBROSA + "admiralbob77_-_Choice_-_Drum-bass.hq.ogg", "music/choice_drum_bass.ogg", "CC-BY-NC-4.0 (testing only)", "admiralbob77 — Choice", False),
    (LIBROSA + "198-209-0000.hq.ogg", "speech/librispeech_198-209-0000.ogg", "CC-BY-4.0", "LibriSpeech (LibriVox reading)", True),
    (LIBROSA + "5703-47212-0000.hq.ogg", "speech/librispeech_5703-47212-0000.ogg", "CC-BY-4.0", "LibriSpeech (LibriVox reading)", True),
    (LIBROSA + "3436-172162-0000.hq.ogg", "speech/librispeech_3436-172162-0000.ogg", "CC-BY-4.0", "LibriSpeech (LibriVox reading)", True),
]


def fetch(url: str, out: Path, retries: int = 4) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 0:
        return out.stat().st_size
    tmp = out.with_suffix(out.suffix + ".part")
    for k in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as fh:
                shutil.copyfileobj(r, fh, 1 << 20)
            tmp.replace(out)
            return out.stat().st_size
        except OSError as e:  # network errors: back off and retry
            if k == retries - 1:
                raise
            print(f"  retry {k + 1} for {url}: {e}", file=sys.stderr)
            time.sleep(2 ** (k + 1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="also download the optional (larger / NC-licensed) files")
    args = ap.parse_args()
    rows, total = [], 0
    for url, rel, lic, who, default in FILES:
        if not (default or args.all):
            continue
        n = fetch(url, DEST / rel)
        total += n
        rows.append(f"| `{rel}` | {who} | {lic} | {url} |")
        print(f"{n / 1e6:7.1f} MB  {rel}")
    (DEST / "ATTRIBUTION.md").write_text("# Real test media — sources and licences\n\n| File | Author / source | Licence | URL |\n|---|---|---|---|\n"
                                         + "\n".join(rows) + "\n")
    print(f"done: {total / 1e6:.1f} MB in {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
