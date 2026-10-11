#!/usr/bin/env python3
"""Six-frame strips from rendered previews for visual review:
   python strip.py T01 T02 ... -o out.jpg   (frames at 15/40/50/60/80/96% unless --frames)"""
import argparse, glob, os, subprocess, sys
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ap = argparse.ArgumentParser(); ap.add_argument("ids", nargs="+"); ap.add_argument("-o", required=True)
ap.add_argument("--fr", default="0.15,0.38,0.47,0.6,0.8,0.96")
a = ap.parse_args()
rows = []
for tid in a.ids:
    vids = glob.glob(os.path.join(ROOT, "01_TEMPLATES", f"{tid.upper()}_*", "preview", f"{tid.upper()}_*.mp4"))
    vids = [v for v in vids if "_preview_" not in v]
    if not vids:
        continue
    v = vids[0]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", v],
                               capture_output=True, text=True).stdout or 0)
    tiles = []
    for f in [float(x) for x in a.fr.split(",")]:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * f:.3f}", "-i", v, "-frames:v", "1", "-f", "rawvideo",
                              "-pix_fmt", "bgr24", "-s", "320x180", "-"], capture_output=True).stdout
        tiles.append(np.frombuffer(raw, np.uint8).reshape(180, 320, 3) if len(raw) == 320 * 180 * 3 else np.zeros((180, 320, 3), np.uint8))
    r = np.hstack(tiles)
    cv2.putText(r, tid.upper(), (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)
    rows.append(r)
cv2.imwrite(a.o, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
