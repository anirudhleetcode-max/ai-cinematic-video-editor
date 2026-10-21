"""Motion QC: frame strips of a clip + per-frame change statistics.

usage: review_motion.py clip.mp4 out.jpg [step]
Writes a contact sheet (every `step` frames) and prints the largest
frame-to-frame differences so jumps / flicker / discontinuities stand out.
"""
import subprocess
import sys

import cv2
import numpy as np

clip, out = sys.argv[1], sys.argv[2]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 6
w, h = 480, 270
p = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                    "-pix_fmt", "bgr24", "-"], capture_output=True, check=True).stdout
fr = np.frombuffer(p, np.uint8).reshape(-1, h, w, 3)
d = np.abs(np.diff(fr.astype(np.int16), axis=0)).mean(axis=(1, 2, 3))
print(f"{len(fr)} frames; mean change {d.mean():.2f}; max {d.max():.2f} at frame {int(d.argmax()) + 1}")
print("top changes:", [(int(i) + 1, round(float(d[i]), 2)) for i in np.argsort(d)[-5:][::-1]])
sel = fr[::step]
cols = 5
rows = [np.hstack(list(sel[i:i + cols]) + [np.zeros_like(sel[0])] * (cols - len(sel[i:i + cols])))
        for i in range(0, len(sel), cols)]
cv2.imwrite(out, np.vstack(rows))
