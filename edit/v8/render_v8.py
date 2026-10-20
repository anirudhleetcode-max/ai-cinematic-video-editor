"""v8: v7 with a background removal that keeps fast-moving hair and limbs.

In v5-v7 the cut-out only counted saturated or dark pixels as person. When
the singers move fast, hair and hands are motion-blurred into a mid-grey
smear over the grey wall, so those pixels were treated as wall and cut away.

v8 adds a motion-blur aware matte:
  * Wall light map: every frame, the brightness of the visible wall is
    measured and filled in behind the people (normalised convolution), so
    the wall's gradient and exposure changes are followed.
  * Blur matting: a pixel darker than the wall behind it is partly person,
    and how much darker sets its opacity (alpha = (wall - pixel) / (wall -
    hair)). Blurred hair comes out semi-transparent, the way it looks in the
    real footage, instead of disappearing. Soft wall shadows sit above the
    ramp start and stay background.
  * Only near the people (within ~90 px of the colour matte), so marks on
    the wall far from them are never picked up.
  * White clothing read as wall: enclosed gaps brighter than the wall (the
    white undershirt) are filled; real wall seen through an arm loop is not
    brighter, so it stays open.
The final matte is the union of the v7 matte and the blur matte. The outline
and everything else are v7's.
"""
import os
import sys
from multiprocessing import Pool

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "v7"))
import render_v7 as v7  # noqa: E402
from render_v7 import H, N_OUT, W, WORK  # noqa: E402
import render_v6 as v6  # noqa: E402

SAT_T = 58
RATIO_START = 0.80      # darker than 80% of the wall -> starts to be person (shadows are ~0.85)
RATIO_FULL = 0.42       # at 42% of the wall brightness -> fully opaque hair
NEAR_PX = 90            # search band around the colour matte (1080p)


def wall_light(small_hsv, person_small):
    """Wall brightness behind every pixel, filled in from the visible wall."""
    V = small_hsv[..., 2].astype(np.float32)
    S = small_hsv[..., 1]
    wall = (S < SAT_T * 0.8) & (V > 70) & (cv2.dilate(person_small, np.ones((15, 15), np.uint8)) == 0)
    w = wall.astype(np.float32)
    num, den = cv2.GaussianBlur(V * w, (0, 0), 25), cv2.GaussianBlur(w, (0, 0), 25)
    num2, den2 = cv2.GaussianBlur(V * w, (0, 0), 90), cv2.GaussianBlur(w, (0, 0), 90)
    glob = float(np.median(V[wall])) if wall.sum() > 500 else 150.0
    far = np.where(den2 > 1e-3, num2 / np.maximum(den2, 1e-6), glob)
    near = num / np.maximum(den, 1e-6)
    t = np.clip(den / 0.15, 0, 1)                         # trust the local estimate where wall is close
    return near * t + far * (1 - t)


def blur_matte(img, coarse_full):
    small = cv2.resize(img, (480, 270), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    ps = cv2.resize(coarse_full, (480, 270), interpolation=cv2.INTER_NEAREST)
    wl = cv2.resize(wall_light(hsv, ps), (W, H), interpolation=cv2.INTER_LINEAR)
    V = img.max(axis=2).astype(np.float32)
    V = cv2.GaussianBlur(V, (0, 0), 1.0)
    ratio = V / np.maximum(wl, 1.0)
    a = np.clip((RATIO_START - ratio) / (RATIO_START - RATIO_FULL), 0, 1)
    r = NEAR_PX // 4                                      # search band, computed at 480x270
    near = cv2.dilate(ps, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2))
    a *= cv2.resize(near, (W, H), interpolation=cv2.INTER_NEAREST) > 0
    # drop isolated specks (noise, wall texture) but keep connected strands
    keep = cv2.morphologyEx((a > 0.25).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(keep)
    big = np.zeros(n, bool)
    big[1:] = st[1:, 4] > 400
    mask = big[lab]
    mask = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    return cv2.GaussianBlur(a * mask, (0, 0), 1.6), ratio      # soften speckle in thin strands


def fill_bright_holes(body, ratio):
    """Fill gaps enclosed by the bodies (bottom edge counts as body) that are
    brighter than the wall: white clothing (the undershirt) read as wall.
    Real wall seen through an arm loop is not brighter, so it stays open."""
    small = cv2.resize(body, (480, 270), interpolation=cv2.INTER_NEAREST)
    pad = cv2.copyMakeBorder(small, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    pad[-1, :] = 1
    inv = (1 - pad).astype(np.uint8)
    cv2.floodFill(inv, None, (0, 0), 0)
    holes = inv[1:-1, 1:-1]
    n, lab, st, _ = cv2.connectedComponentsWithStats(holes)
    if n <= 1:
        return np.zeros(body.shape, bool)
    rs = cv2.resize(ratio, (480, 270), interpolation=cv2.INTER_AREA)
    fill = np.zeros(n, bool)
    for i in range(1, n):
        if st[i, 4] < 480 * 270 * 0.08 and np.median(rs[lab == i]) > 1.12:
            fill[i] = True
    out = fill[lab].astype(np.uint8)
    out = cv2.dilate(out, np.ones((3, 3), np.uint8))
    return cv2.resize(out, (W, H), interpolation=cv2.INTER_LINEAR) > 0


def body_matte(img, f, ema):
    alpha, body, ema = v6.body_matte(img, f, ema)
    ba, ratio = blur_matte(img, body)
    alpha = np.maximum(alpha, ba)
    body = (alpha > 0.5).astype(np.uint8)
    holes = fill_bright_holes(body, ratio)
    if holes.any():
        alpha = np.maximum(alpha, cv2.GaussianBlur(holes.astype(np.float32), (0, 0), 1.5))
        body = (alpha > 0.5).astype(np.uint8)
    return alpha, body, ema


v7.body_matte = body_matte          # v7's render_frame looks this name up at call time


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else N_OUT
    prefix = sys.argv[3] if len(sys.argv) > 3 else "v8chunk"
    v6.v5.build_backgrounds()
    n = max(1, min(8, (b - a) // 30))
    edges = np.linspace(a, b, n + 1).astype(int)
    with Pool(4) as pool:
        paths = pool.map(v7.render_chunk, [(k, edges[k], edges[k + 1], prefix) for k in range(n)])
    with open(os.path.join(WORK, f"{prefix}.txt"), "w") as fh:
        fh.write("".join(f"file '{p}'\n" for p in paths))
    print("chunks done")


if __name__ == "__main__":
    main()
