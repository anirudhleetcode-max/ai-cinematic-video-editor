"""v5: reference-reel style edit.

The look of the supplied reference reel: the singers are cut out in black and
white with a sparkly mint-teal doodle outline (offset from the body), placed on
full-frame illustrated backgrounds that hard-cut on the beat. The first beats
stay in colour on the real wall with a few glitter stickers, like the reference
intro. All backgrounds are generated procedurally (no external assets).
"""
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "v3"))
os.environ.setdefault("EDIT_SAT", "58")
from common import FPS, N_OUT, SLOW_A, SLOW_B, W, H, WORK, person_mask, read_frames  # noqa: E402

AN = np.load(os.path.join(WORK, "v3_analysis.npz"))
FACES = AN["faces"]
with open(os.path.join(WORK, "beats.json")) as fh:
    _a = json.load(fh)["audio"]
BEATS = np.array(_a["beats"])
INTRO_END = float(BEATS[np.argmin(np.abs(BEATS - 3.6))])      # colour intro, like the reference


def rng(seed):
    return np.random.default_rng(seed)


# ---------------------------------------------------------------- background library
def star_pts(cx, cy, r, rot=0.0, inner=0.45, jitter=0.0, g=None):
    pts = []
    for i in range(10):
        rr = r * (1 if i % 2 == 0 else inner) * (1 + (g.normal(0, jitter) if g is not None else 0))
        a = -math.pi / 2 + rot + i * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return np.array(pts, np.int32)


def heart_pts(cx, cy, s):
    t = np.linspace(0, 2 * np.pi, 80)
    x = 16 * np.sin(t) ** 3
    y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
    return np.stack([cx + x * s / 16, cy + y * s / 16], 1).astype(np.int32)


def bgr(h):
    h = h.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def paper_grain(img, amt, seed):
    n = rng(seed).normal(0, amt, img.shape[:2]).astype(np.float32)
    n = cv2.GaussianBlur(n, (0, 0), 0.8)
    return np.clip(img.astype(np.float32) + n[..., None], 0, 255).astype(np.uint8)


def bg_swirls(s=1):
    g = rng(s)
    img = np.full((H, W, 3), bgr("#14204a"), np.uint8)
    cols = [bgr("#2b5fae"), bgr("#7fb6e6"), bgr("#f2f2e8"), bgr("#e9c54a"), bgr("#1d3f86"), bgr("#a9d3f0")]
    for _ in range(70):
        cx, cy, R = g.uniform(-60, W + 60), g.uniform(-60, H + 60), g.uniform(50, 150)
        r = R
        k = 0
        while r > 6:
            cv2.circle(img, (int(cx), int(cy)), int(r), cols[(k + int(cx)) % len(cols)], max(3, int(R / 14)), cv2.LINE_AA)
            r -= R / 6.5
            k += 1
    for _ in range(40):
        cx, cy = g.uniform(0, W), g.uniform(0, H)
        cv2.circle(img, (int(cx), int(cy)), int(g.uniform(6, 14)), bgr("#f5d76e"), -1, cv2.LINE_AA)
    return paper_grain(img, 6, s)


def bg_cream_doodles(s=2):
    g = rng(s)
    img = np.full((H, W, 3), bgr("#fbf3dc"), np.uint8)
    ink = bgr("#7a5c2e")
    for _ in range(36):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(18, 46)
        p = star_pts(cx, cy, r, g.uniform(0, 1), 0.42, 0.06, g)
        cv2.fillPoly(img, [p], bgr("#f4c542"), cv2.LINE_AA)
        cv2.polylines(img, [p], True, ink, 2, cv2.LINE_AA)
    for _ in range(10):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(40, 80)
        cv2.circle(img, (int(cx), int(cy)), int(r), ink, 2, cv2.LINE_AA)
        cv2.ellipse(img, (int(cx), int(cy)), (int(r * 1.8), int(r * 0.45)), -18, 0, 360, ink, 2, cv2.LINE_AA)
    for _ in range(14):
        cx, cy = g.uniform(0, W), g.uniform(0, H)
        th = np.linspace(0, 4 * np.pi, 80)
        rr = th * 3.2
        p = np.stack([cx + rr * np.cos(th), cy + rr * np.sin(th)], 1).astype(np.int32)
        cv2.polylines(img, [p], False, bgr("#e2a93b"), 3, cv2.LINE_AA)
    for _ in range(80):
        cx, cy = g.uniform(0, W), g.uniform(0, H)
        cv2.line(img, (int(cx) - 6, int(cy)), (int(cx) + 6, int(cy)), bgr("#e8b34a"), 2, cv2.LINE_AA)
        cv2.line(img, (int(cx), int(cy) - 6), (int(cx), int(cy) + 6), bgr("#e8b34a"), 2, cv2.LINE_AA)
    return paper_grain(img, 4, s)


def bg_stripes(s=3):
    cols = [bgr(c) for c in ("#d6312b", "#f08a24", "#f6c933", "#2d5fb8", "#f4ead0", "#e8483c", "#3a8fd6")]
    img = np.zeros((H, W, 3), np.uint8)
    w = 58
    for i in range(W // w + 1):
        img[:, i * w:(i + 1) * w] = cols[i % len(cols)]
    return paper_grain(img, 7, s)


def bg_navy_doodles(s=4):
    g = rng(s)
    img = np.full((H, W, 3), bgr("#232c5c"), np.uint8)
    wht = bgr("#f2f3fa")
    for _ in range(26):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(16, 40)
        cv2.circle(img, (int(cx), int(cy)), int(r), wht, 3, cv2.LINE_AA)
    for _ in range(40):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(10, 22)
        cv2.polylines(img, [star_pts(cx, cy, r, g.uniform(0, 1))], True, wht, 2, cv2.LINE_AA)
    for _ in range(14):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(14, 26)
        cv2.ellipse(img, (int(cx), int(cy)), (int(r), int(r)), 0, 60, 300, wht, 3, cv2.LINE_AA)
    for _ in range(120):
        cv2.circle(img, (int(g.uniform(0, W)), int(g.uniform(0, H))), 2, wht, -1, cv2.LINE_AA)
    return paper_grain(img, 5, s)


def bg_sky(s=5):
    g = rng(s)
    y = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array(bgr("#6f9fd8"), np.float32), np.array(bgr("#a9c9ee"), np.float32)
    img = np.broadcast_to(top * (1 - y) + bot * y, (H, W, 3)).astype(np.uint8).copy()
    for _ in range(18):
        cx, cy = g.uniform(0, W), g.uniform(0, H * 0.7)
        cv2.polylines(img, [star_pts(cx, cy, g.uniform(8, 16), g.uniform(0, 1))], True, (255, 255, 255), 2, cv2.LINE_AA)
    for _ in range(8):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H * 0.6), g.uniform(10, 18)
        cv2.ellipse(img, (int(cx), int(cy)), (int(r), int(r)), 0, 70, 290, (255, 255, 255), 3, cv2.LINE_AA)
    for k in range(16):
        cx = k * 140 + g.uniform(-30, 30)
        for j in range(4):
            cv2.circle(img, (int(cx + j * 40), int(H - 40 + g.uniform(-25, 15))), int(g.uniform(45, 75)),
                       bgr("#f4f8ff"), -1, cv2.LINE_AA)
    return paper_grain(img, 4, s)


def bg_heart_rings(s=6):
    img = np.full((H, W, 3), bgr("#3b57b5"), np.uint8)
    cols = [bgr(c) for c in ("#d93a2f", "#f5b52e", "#3b57b5", "#f07d2a", "#f5b52e", "#d93a2f")]
    cx, cy = W // 2, H // 2 + 60
    for i, sc in enumerate(range(1500, 60, -110)):
        cv2.fillPoly(img, [heart_pts(cx, cy - sc * 0.15, sc)], cols[i % len(cols)], cv2.LINE_AA)
    return paper_grain(img, 6, s)


def bg_pale_stars(s=7):
    g = rng(s)
    img = np.full((H, W, 3), bgr("#fbf8d2"), np.uint8)
    for _ in range(16):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(18, 40)
        c = [bgr("#2f6b46"), bgr("#7f8a3a"), bgr("#c49a2c")][int(g.integers(3))]
        p = star_pts(cx, cy, r, g.uniform(0, 1), 0.45, 0.08, g)
        cv2.fillPoly(img, [p], c, cv2.LINE_AA)
    for _ in range(6):
        cx, cy = g.uniform(0, W), g.uniform(0, H)
        th = np.linspace(0, 4.5 * np.pi, 90)
        rr = th * 3.5
        cv2.polylines(img, [np.stack([cx + rr * np.cos(th), cy + rr * np.sin(th)], 1).astype(np.int32)], False,
                      bgr("#7f8a3a"), 4, cv2.LINE_AA)
    return paper_grain(img, 4, s)


def bg_big_stars(s=8):
    g = rng(s)
    img = np.full((H, W, 3), bgr("#fbe7d0"), np.uint8)
    blk = bgr("#1b1b1b")
    for _ in range(9):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(26, 60)
        c = bgr("#1f3f8f") if g.random() < 0.5 else bgr("#d5262b")
        cv2.circle(img, (int(cx), int(cy)), int(r), c, -1, cv2.LINE_AA)
        cv2.circle(img, (int(cx), int(cy)), int(r), blk, 5, cv2.LINE_AA)
    for _ in range(6):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(90, 230)
        p = star_pts(cx, cy, r, g.uniform(-0.4, 0.4), 0.5)
        cv2.fillPoly(img, [p], bgr("#f6b91d"), cv2.LINE_AA)
        cv2.polylines(img, [p], True, blk, 8, cv2.LINE_AA)
    return paper_grain(img, 4, s)


def bg_glitter_stars(s=9):
    g = rng(s)
    base = np.array(bgr("#1e3b8c"), np.float32)
    noise = g.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
    tex = cv2.resize(noise, (W, H))
    img = np.clip(base[None, None] * (1 + 0.25 * tex[..., None]), 0, 255).astype(np.uint8)
    sp = g.random((H, W)) > 0.985
    img[sp] = bgr("#9fc4ff")
    for _ in range(10):
        cx, cy = g.uniform(0, W), g.uniform(0, H)
        th = np.linspace(0, 3 * np.pi, 70)
        rr = th * 8
        cv2.polylines(img, [np.stack([cx + rr * np.cos(th), cy + rr * np.sin(th)], 1).astype(np.int32)], False,
                      bgr("#3f63c4"), 6, cv2.LINE_AA)
    for _ in range(70):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(14, 34)
        cv2.fillPoly(img, [star_pts(cx, cy, r, g.uniform(0, 1), 0.48)], bgr("#ffd93b"), cv2.LINE_AA)
    return img


def bg_wavy_rainbow(s=10):
    g = rng(s)
    cols = [bgr(c) for c in ("#e63b2e", "#f39a2b", "#f7d53b", "#4cb34f", "#2f7fd1", "#7b4bb5", "#e64f9a", "#2bb5c9")]
    img = np.zeros((H, W, 3), np.uint8)
    xs = np.arange(W)
    band = 54
    for i in range(-2, H // band + 3):
        y0 = i * band + 22 * np.sin(xs * 0.006 + i * 0.4)
        top = np.stack([xs, y0], 1)
        bot = np.stack([xs[::-1], (y0 + band + 2)[::-1]], 1)
        p = np.vstack([top, bot]).astype(np.int32)
        cv2.fillPoly(img, [p], cols[i % len(cols)], cv2.LINE_AA)
        cv2.polylines(img, [top.astype(np.int32)], False, bgr("#1e1e2a"), 3, cv2.LINE_AA)
    sp = g.random((H, W)) > 0.97
    img[sp] = np.clip(img[sp].astype(int) + 60, 0, 255).astype(np.uint8)
    return img


def bg_watercolor_stars(s=11):
    g = rng(s)
    img = np.full((H, W, 3), bgr("#d9e8e2"), np.uint8).astype(np.float32)
    for _ in range(34):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(20, 60)
        c = [bgr(x) for x in ("#e9a23b", "#d65a6f", "#4a87c9", "#2f4f6f", "#e7c84a", "#c94f5a")][int(g.integers(6))]
        lay = np.zeros((H, W), np.uint8)
        cv2.fillPoly(lay, [star_pts(cx, cy, r, g.uniform(0, 1), 0.45, 0.07, g)], 255, cv2.LINE_AA)
        a = cv2.GaussianBlur(lay, (0, 0), 2.5).astype(np.float32)[..., None] / 255 * 0.85
        img = img * (1 - a) + np.array(c, np.float32) * a
    return paper_grain(np.clip(img, 0, 255).astype(np.uint8), 5, s)


def bg_pink_flowers(s=12):
    g = rng(s)
    img = np.full((H, W, 3), bgr("#fbd9e6"), np.uint8)
    for _ in range(40):
        cx, cy, r = g.uniform(0, W), g.uniform(0, H), g.uniform(10, 22)
        c = [bgr("#f2a9c4"), bgr("#ffffff"), bgr("#f7c2d6")][int(g.integers(3))]
        for k in range(5):
            a = k * 2 * math.pi / 5
            cv2.circle(img, (int(cx + r * 0.9 * math.cos(a)), int(cy + r * 0.9 * math.sin(a))), int(r * 0.7), c, -1, cv2.LINE_AA)
        cv2.circle(img, (int(cx), int(cy)), int(r * 0.45), bgr("#f6d36b"), -1, cv2.LINE_AA)
    return paper_grain(img, 3, s)


def bg_embroidery(s=13):
    g = rng(s)
    cols = [bgr(c) for c in ("#e05a3a", "#f2b84b", "#7fbf6a", "#5aa3d9", "#d96aa8", "#f4ead8")]
    img = np.zeros((H, W, 3), np.uint8)
    w = 90
    for i in range(W // w + 1):
        img[:, i * w:(i + 1) * w] = cols[i % len(cols)]
        if i % 2 == 0:
            for y in range(30, H, 70):
                cx = i * w + w // 2
                for k in range(6):
                    a = k * math.pi / 3
                    cv2.circle(img, (int(cx + 14 * math.cos(a)), int(y + 14 * math.sin(a))), 9, cols[(i + 2) % 5], -1, cv2.LINE_AA)
                cv2.circle(img, (cx, y), 7, bgr("#fff1c9"), -1, cv2.LINE_AA)
        else:
            for y in range(0, H, 10):
                cv2.line(img, (i * w + 8, y), (i * w + w - 8, y + 6), cols[(i + 3) % 6], 2, cv2.LINE_AA)
    tex = rng(s).normal(0, 10, (H, W)).astype(np.float32)
    return np.clip(img.astype(np.float32) + tex[..., None], 0, 255).astype(np.uint8)


def bg_clouds(s=14):
    g = rng(s)
    img = np.full((H, W, 3), bgr("#d8dfe6"), np.uint8)
    for row in range(5):
        y = int(120 + row * 220 + g.uniform(-40, 40))
        for k in range(14):
            cx = int(k * 150 + g.uniform(-40, 40))
            r = int(g.uniform(55, 95))
            cv2.circle(img, (cx, y), r, bgr("#f7f8fa"), -1, cv2.LINE_AA)
            cv2.circle(img, (cx, y), r, bgr("#7d8794"), 2, cv2.LINE_AA)
            for j in range(3):
                cv2.ellipse(img, (cx, y + 10), (int(r * (0.8 - 0.2 * j)), int(r * (0.5 - 0.12 * j))), 0, 200, 340,
                            bgr("#9aa3ad"), 2, cv2.LINE_AA)
    return paper_grain(img, 4, s)


GENERATORS = [bg_swirls, bg_cream_doodles, bg_stripes, bg_navy_doodles, bg_sky, bg_heart_rings, bg_pale_stars,
              bg_big_stars, bg_glitter_stars, bg_wavy_rainbow, bg_watercolor_stars, bg_pink_flowers,
              bg_embroidery, bg_clouds]
BG_DIR = os.path.join(WORK, "v5_bgs")


def build_backgrounds():
    os.makedirs(BG_DIR, exist_ok=True)
    for i, fn in enumerate(GENERATORS):
        p = os.path.join(BG_DIR, f"bg_{i:02d}.png")
        if not os.path.exists(p):
            big = fn()
            cv2.imwrite(p, big)


# ---------------------------------------------------------------- edit decisions
def switch_times():
    """Background hard-cuts on the beat: every beat in energetic sections,
    every second beat in the gentle ones, held through the silent break."""
    out = [INTRO_END]
    for b in BEATS:
        if b <= INTRO_END + 0.2 or b >= N_OUT / FPS - 0.3:
            continue
        if 18.2 <= b < 27.9:                     # near-silent break: slow changes
            if b - out[-1] >= 2.9:
                out.append(b)
            continue
        step = 1 if (28 <= b < 38 or 44 <= b < 56 or 69.5 <= b < 101.1) else 2
        k = int(np.argmin(np.abs(BEATS - b)))
        if step == 1 or k % 2 == 0:
            out.append(b)
    for c in (SLOW_A / FPS, SLOW_B / FPS):
        out.append(c)
    return np.array(sorted(set(round(x, 3) for x in out)))


SWITCH = switch_times()
ORDER = rng(55).permutation(np.tile(np.arange(len(GENERATORS)), 20))
# avoid the same background twice in a row
for i in range(1, len(ORDER)):
    if ORDER[i] == ORDER[i - 1]:
        ORDER[i] = (ORDER[i] + 3) % len(GENERATORS)


def bg_index(t):
    k = int(np.searchsorted(SWITCH, t, side="right")) - 1
    return k, int(ORDER[k % len(ORDER)])


_bg_cache = {}


def get_bg(i):
    if i not in _bg_cache:
        _bg_cache[i] = cv2.imread(os.path.join(BG_DIR, f"bg_{i:02d}.png"))
    return _bg_cache[i]


# ---------------------------------------------------------------- frame
TEAL = np.array(bgr("#5fd3b4"), np.float32)
TEAL_D = np.array(bgr("#2fa58a"), np.float32)


def stickers_intro(out, t):
    """Glitter stickers on the real wall during the colour intro."""
    g = rng(77)
    for k in range(7):
        cx = [120, 280, 1650, 1790, 220, 1560, 900][k]
        cy = [140, 760, 120, 520, 450, 820, 80][k]
        r = [70, 55, 80, 60, 40, 50, 38][k]
        pop = min(1.0, max(0.0, (t - 0.25 * k) / 0.25))
        if pop <= 0:
            continue
        sc = r * (1 + 0.15 * math.sin(min(1, pop) * math.pi))
        p = star_pts(cx, cy + 4 * math.sin(t * 3 + k), sc, 0.2 * math.sin(t + k), 0.48)
        cv2.fillPoly(out, [p], bgr("#2f5fd0"), cv2.LINE_AA)
        cv2.polylines(out, [p], True, (255, 255, 255), 6, cv2.LINE_AA)
        sp = g.integers(0, 2 * int(sc), (40, 2)) - int(sc)
        for (dx, dy) in sp:
            if dx * dx + dy * dy < (sc * 0.5) ** 2:
                cv2.circle(out, (int(cx + dx), int(cy + dy)), 2, bgr("#9fc0ff"), -1)
    for k in range(4):
        cx, cy = [430, 1480, 600, 1330][k], [120, 150, 900, 930][k]
        cv2.fillPoly(out, [heart_pts(cx, cy + 5 * math.sin(t * 2 + k), 46)], bgr("#c9a83a"), cv2.LINE_AA)


def render_frame(img, f, ema):
    t = f / FPS
    m = person_mask(cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA))
    for x, y, w, h in FACES[f]:
        if w > 0:
            cv2.ellipse(m, (int((x + w / 2) / 2), int((y + h / 2) / 2)), (int(w * 0.25), int(h * 0.31)), 0, 0, 360, 255, -1)
    m = m.astype(np.float32) / 255
    ema = m if ema is None else 0.5 * ema + 0.5 * m
    mb = (ema > 0.5).astype(np.uint8) * 255
    mb = cv2.morphologyEx(mb, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))

    if t < INTRO_END:                                             # colour intro on the real wall
        out = img.copy()
        stickers_intro(out, t)
        return out, ema

    k, bi = bg_index(t)
    bg = get_bg(bi)
    seg_t = t - SWITCH[k]
    z = 1.02 + 0.03 * min(1.0, seg_t / 3.0)                       # gentle push on each background
    if seg_t < 0.1:                                               # tiny pop on the cut
        z += 0.025 * (1 - seg_t / 0.1)
    M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
    bgz = cv2.warpAffine(bg, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # black-and-white subjects with gentle contrast (the reference look)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray = np.clip((gray - 128) * 1.12 + 132, 0, 255)
    alpha = cv2.GaussianBlur(cv2.resize(mb, (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), 1.2).astype(np.float32)[..., None] / 255
    out = bgz.astype(np.float32) * (1 - alpha) + gray[..., None] * alpha

    # sparkly mint-teal outline, offset from the body (doodle sticker trace)
    inner = cv2.dilate(mb, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
    outer = cv2.dilate(mb, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23)))
    ring = cv2.GaussianBlur(cv2.subtract(outer, inner), (0, 0), 1.0)
    ring = cv2.resize(ring, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
    g = rng(f // 3)                                               # glitter re-sparkles every 3 frames
    sparkle = g.random((H // 2, W // 2)).astype(np.float32)
    sparkle = cv2.resize(sparkle, (W, H), interpolation=cv2.INTER_NEAREST)
    col = TEAL[None, None] * (0.8 + 0.4 * sparkle[..., None]) + (sparkle[..., None] > 0.93) * 70
    col = np.where((sparkle[..., None] < 0.12), TEAL_D[None, None], col)
    ra = ring[..., None]
    out = out * (1 - ra) + np.clip(col, 0, 255) * ra

    # flash frame on the slow-motion cut (soft)
    for c in (SLOW_A, SLOW_B):
        d = abs(f - c + 0.5)
        if d < 4:
            out = out * (1 - 0.25 * (1 - d / 4)) + 255 * 0.25 * (1 - d / 4)
    tail = N_OUT / FPS - t
    if tail < 1.0:
        out = out * max(0.0, tail)
    return np.clip(out, 0, 255).astype(np.uint8), ema


def render_chunk(args):
    k, a, b, prefix = args
    path = os.path.join(WORK, f"{prefix}_{k:02d}.mp4")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                            "-pix_fmt", "yuv420p", "-threads", "2", path], stdin=subprocess.PIPE)
    scene = max(c for c in (0, SLOW_A, SLOW_B) if c <= a)
    pre = max(scene, a - 4)
    ema = None
    for i, fr in enumerate(read_frames(pre, b)):
        f = pre + i
        if f in (SLOW_A, SLOW_B):
            ema = None
        out, ema = render_frame(fr, f, ema)
        if f >= a:
            enc.stdin.write(out.tobytes())
    enc.stdin.close()
    enc.wait()
    return path


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else N_OUT
    prefix = sys.argv[3] if len(sys.argv) > 3 else "v5chunk"
    build_backgrounds()
    n = max(1, min(8, (b - a) // 30))
    edges = np.linspace(a, b, n + 1).astype(int)
    with Pool(4) as pool:
        paths = pool.map(render_chunk, [(k, edges[k], edges[k + 1], prefix) for k in range(n)])
    with open(os.path.join(WORK, f"{prefix}.txt"), "w") as fh:
        fh.write("".join(f"file '{p}'\n" for p in paths))
    print("switches:", len(SWITCH), "chunks done")


if __name__ == "__main__":
    main()
