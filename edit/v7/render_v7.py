"""v7: v6 with a calm, stable outline set further from the body.

v6 drew the outline straight from each frame's matte, so every hair wisp,
motion-blur fringe and per-frame matte change made the band wriggle while the
singers moved. v7 keeps the v6 cut-out (accurate guided-filter matte) but
derives the outline from its own silhouette:
  * spatially smoothed (Gaussian on the matte, then re-thresholded) so the
    band follows the body's shape, not hair strands or blur fringes;
  * temporally stabilised: a 5-frame median removes flip-flopping matte
    pixels, an adaptive blend ignores small sways but follows big moves, and
    threshold hysteresis stops the edge bouncing (band flicker measured about
    5x lower than v6 on the 48-53 s hair-flip section);
  * drawn further out: 18 px gap from the body, 26 px band.
"""
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "v6"))
import render_v6 as v6  # noqa: E402
from render_v6 import (FPS, H, INTRO_END, N_OUT, SLOW_A, SLOW_B, SWITCH, TEAL, TEAL_D, W, WORK,  # noqa: E402
                       bg_index, body_matte, draw_stickers, get_bg, read_frames, rng, stickers_intro)

GAP = 18          # px between the (smoothed) silhouette and the band, 1080p
THICK = 26        # band thickness, 1080p
SW, SH = 960, 540  # outline field resolution


def outline_field(body, prev):
    """Calm silhouette for the outline: (median history, smoothed field, on/off state).

    A 5-frame temporal median removes matte pixels that flip and flip back,
    a wide blur drops hair wisps and blur fringes, an adaptive blend ignores
    small changes but follows big moves, and hysteresis on the threshold
    stops the edge bouncing.
    """
    m = cv2.resize(body.astype(np.float32), (SW, SH), interpolation=cv2.INTER_AREA)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    hist, field, on = prev if prev is not None else ([], None, None)
    hist = (hist + [m])[-5:]
    m = cv2.GaussianBlur(np.median(np.array(hist), 0).astype(np.float32), (0, 0), 8.0)
    if field is None:
        field = m
    else:
        k = 0.03 + 0.27 * np.clip((np.abs(m - field) - 0.08) / 0.6, 0, 1)
        field = field + k * (m - field)
    on = field > 0.5 if on is None else np.where(on, field > 0.45, field > 0.55)
    return hist, field, on


def render_frame(img, f, state):
    t = f / FPS
    ema, field = state if state is not None else (None, None)
    alpha, body, ema = body_matte(img, f, ema)
    field = outline_field(body, field)
    if t < INTRO_END:
        out = img.copy()
        stickers_intro(out, t)
        return out, (ema, field)

    k, bi = bg_index(t)
    seg_t = t - SWITCH[k]
    z = 1.02 + 0.03 * min(1.0, seg_t / 3.0)
    if seg_t < 0.1:
        z += 0.025 * (1 - seg_t / 0.1)
    M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
    out = cv2.warpAffine(get_bg(bi), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    draw_stickers(out, t, f, k, seg_t)

    # band from the stable silhouette; the field is upsampled smoothly so the
    # band edge has no stair-steps
    on = cv2.GaussianBlur(field[2].astype(np.float32), (0, 0), 1.5)
    sil = cv2.resize(on, (W, H), interpolation=cv2.INTER_CUBIC) > 0.5
    d = cv2.distanceTransform((~sil).astype(np.uint8), cv2.DIST_L2, 5)
    ring = np.clip(d - GAP + 0.5, 0, 1) * np.clip(GAP + THICK - d + 0.5, 0, 1)
    shadow = np.clip(GAP + THICK + 7 - d, 0, 7) / 7 * (d > GAP + THICK - 1)
    out *= 1 - 0.3 * shadow[..., None]
    g = rng(f // 3)
    sparkle = cv2.resize(g.random((H // 3, W // 3)).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)
    col = TEAL[None, None] * (0.82 + 0.36 * sparkle[..., None]) + (sparkle[..., None] > 0.92) * 80
    col = np.where(sparkle[..., None] < 0.1, TEAL_D[None, None], col)
    rim = (np.clip(1.6 - np.abs(d - GAP - 0.8), 0, 1) + np.clip(1.6 - np.abs(d - GAP - THICK + 0.8), 0, 1)) * 0.55
    col = col * (1 - rim[..., None]) + 255 * rim[..., None]
    ra = ring[..., None]
    out = out * (1 - ra) + np.clip(col, 0, 255) * ra

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray = np.clip((gray - 128) * 1.12 + 132, 0, 255)
    a3 = alpha[..., None]
    out = out * (1 - a3) + gray[..., None] * a3

    for c in (SLOW_A, SLOW_B):
        dd = abs(f - c + 0.5)
        if dd < 4:
            out = out * (1 - 0.25 * (1 - dd / 4)) + 255 * 0.25 * (1 - dd / 4)
    tail = N_OUT / FPS - t
    if tail < 1.0:
        out = out * max(0.0, tail)
    return np.clip(out, 0, 255).astype(np.uint8), (ema, field)


def render_chunk(args):
    k, a, b, prefix = args
    path = os.path.join(WORK, f"{prefix}_{k:02d}.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                            "-pix_fmt", "yuv420p", "-threads", "2", path], stdin=subprocess.PIPE)
    scene = max(c for c in (0, SLOW_A, SLOW_B) if c <= a)
    pre = max(scene, a - 20)                               # longer preroll: the outline field settles
    state = None
    for i, fr in enumerate(read_frames(pre, b)):
        f = pre + i
        if f in (SLOW_A, SLOW_B):
            state = None
        out, state = render_frame(fr, f, state)
        if f >= a:
            enc.stdin.write(out.tobytes())
    enc.stdin.close()
    enc.wait()
    return path


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else N_OUT
    prefix = sys.argv[3] if len(sys.argv) > 3 else "v7chunk"
    v6.v5.build_backgrounds()
    n = max(1, min(8, (b - a) // 30))
    edges = np.linspace(a, b, n + 1).astype(int)
    with Pool(4) as pool:
        paths = pool.map(render_chunk, [(k, edges[k], edges[k + 1], prefix) for k in range(n)])
    with open(os.path.join(WORK, f"{prefix}.txt"), "w") as fh:
        fh.write("".join(f"file '{p}'\n" for p in paths))
    print("chunks done")


if __name__ == "__main__":
    main()
