"""v9: the v7/v8 look with neural background removal.

The person matte comes from matte_rvm.py (Robust Video Matting, two models
combined), read frame by frame from the lossless alpha files. It replaces
the colour-rule mattes of v5-v8, which counted warm-lit wall and wall
shadows as person in the hug and needed special handling for blurred hair.
Everything else (stable outline from v7, stickers from v6, backgrounds from
v5) is reused unchanged.

Usage: run matte_rvm.py first, then
       EDIT_WORK=... EDIT_SOURCE=... python3 render_v9.py
"""
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "v7"))
import render_v7 as v7  # noqa: E402
from render_v7 import FPS, H, N_OUT, SLOW_A, SLOW_B, W, WORK, read_frames  # noqa: E402
from matte_rvm import alpha_path, chunk_ranges  # noqa: E402

_cur = {}


def body_matte(img, f, ema):
    a = _cur["alpha"]
    return a, (a > 0.5).astype(np.uint8), ema


v7.body_matte = body_matte          # v7's render_frame looks this name up at call time


def read_alpha(k):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", alpha_path(k), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         stdout=subprocess.PIPE)
    n = W * H
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(H, W).astype(np.float32) / 255
    p.wait()


def render_chunk(args):
    k, a, b, pre = args
    path = os.path.join(WORK, f"v9chunk_{k:02d}.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                            "-pix_fmt", "yuv420p", "-threads", "2", path], stdin=subprocess.PIPE)
    state = None
    n = 0
    for i, (fr, al) in enumerate(zip(read_frames(pre, b), read_alpha(k))):
        f = pre + i
        if f in (SLOW_A, SLOW_B):
            state = None
        _cur["alpha"] = al
        out, state = v7.render_frame(fr, f, state)
        if f >= a:
            enc.stdin.write(out.tobytes())
            n += 1
    enc.stdin.close()
    enc.wait()
    if n != b - a:
        raise RuntimeError(f"chunk {k}: wrote {n} frames, expected {b - a}")
    return path


def main():
    v7.v6.v5.build_backgrounds()
    jobs = chunk_ranges()
    with Pool(4) as pool:
        paths = pool.map(render_chunk, jobs)
    with open(os.path.join(WORK, "v9chunk.txt"), "w") as fh:
        fh.write("".join(f"file '{p}'\n" for p in paths))
    print("chunks done")


if __name__ == "__main__":
    main()
