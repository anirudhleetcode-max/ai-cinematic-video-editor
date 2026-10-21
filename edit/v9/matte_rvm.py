"""v9 matte pass: neural human matting for every frame.

Runs Robust Video Matting (Lin et al., 2021; MobileNetV3 and ResNet50 ONNX
releases) over the whole timeline. RVM is recurrent: it carries its memory
from frame to frame, which keeps the matte stable and lets it keep
motion-blurred hair and hands. The memory is reset at each scene cut.

The two models' alphas are combined with a per-pixel max: the wall is
rejected by both, and a body part that one model makes faint (a fast hand)
is kept by the other. Tiny detached specks are removed. The alpha is written
losslessly (FFV1, 8-bit grey) per render chunk, covering that chunk's render
preroll, so render_v9.py reads frame-exact mattes.

Usage: EDIT_WORK=... EDIT_SOURCE=... python3 matte_rvm.py [chunk ...]
"""
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np
import onnxruntime as ort

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from common import N_OUT, SLOW_A, SLOW_B, W, H, WORK, read_frames  # noqa: E402

MODELS = ["rvm_mb3.onnx", "rvm_r50.onnx"]
MODEL_DIR = os.environ.get("RVM_DIR", os.path.join(WORK, "models"))
CHUNKS = 8
PREROLL = 20          # must match the render's outline preroll
WARMUP = 40           # frames of RVM memory warm-up before the first written frame
DOWNSAMPLE = 0.25     # RVM's recommended ratio for 1080p


def chunk_ranges():
    edges = np.linspace(0, N_OUT, CHUNKS + 1).astype(int)
    out = []
    for k in range(CHUNKS):
        a, b = int(edges[k]), int(edges[k + 1])
        scene = max(c for c in (0, SLOW_A, SLOW_B) if c <= a)
        out.append((k, a, b, max(scene, a - PREROLL)))
    return out


def alpha_path(k):
    return os.path.join(WORK, f"v9_alpha_{k:02d}.mkv")


def clean(alpha):
    a = np.where(alpha < 0.04, 0, alpha)
    m = (a > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n > 2:
        small = np.zeros(n, bool)
        small[1:] = st[1:, 4] < W * H * 0.002
        a = np.where(small[lab] & (a > 0), 0, a)
    return a


def run_chunk(args):
    k, a, b, pre = args
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    sess = [ort.InferenceSession(os.path.join(MODEL_DIR, m), so, providers=["CPUExecutionProvider"]) for m in MODELS]
    scene = max(c for c in (0, SLOW_A, SLOW_B) if c <= pre)
    start = max(scene, pre - WARMUP)
    tmp = alpha_path(k) + ".tmp.mkv"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}",
                            "-r", "30", "-i", "-", "-c:v", "ffv1", "-level", "3", "-threads", "1", tmp],
                           stdin=subprocess.PIPE)
    zero = np.zeros((1, 1, 1, 1), np.float32)
    rec = [[zero] * 4 for _ in sess]
    dr = np.array([DOWNSAMPLE], np.float32)
    for i, fr in enumerate(read_frames(start, b)):
        f = start + i
        if f in (SLOW_A, SLOW_B):
            rec = [[zero] * 4 for _ in sess]
        x = (cv2.cvtColor(fr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255).transpose(2, 0, 1)[None]
        al = None
        for j, s in enumerate(sess):
            _, pha, *r = s.run(None, {"src": x, "r1i": rec[j][0], "r2i": rec[j][1], "r3i": rec[j][2],
                                      "r4i": rec[j][3], "downsample_ratio": dr})
            rec[j] = r
            al = pha[0, 0] if al is None else np.maximum(al, pha[0, 0])
        if f >= pre:
            enc.stdin.write((clean(al) * 255 + 0.5).astype(np.uint8).tobytes())
    enc.stdin.close()
    enc.wait()
    os.replace(tmp, alpha_path(k))
    return k


def main():
    want = [int(x) for x in sys.argv[1:]] or list(range(CHUNKS))
    jobs = [c for c in chunk_ranges() if c[0] in want]
    with Pool(4) as pool:
        for k in pool.imap_unordered(run_chunk, jobs):
            print("alpha chunk", k, "done", flush=True)


if __name__ == "__main__":
    main()
