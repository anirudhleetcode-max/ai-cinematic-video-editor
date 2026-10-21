"""v6: v5's reference-reel look with a thicker, body-accurate outline and
animated doodle stickers on every background.

Changes from v5 (v5 is untouched and reused for backgrounds and the cut schedule):
  * Outline: the colour matte is refined against the frame itself with a fast
    guided filter (edges snap to hair, arms and shoulders), then the outline is
    drawn at full resolution from a distance transform: a thick sparkly
    mint-teal band a few pixels off the true silhouette, with a soft drop
    shadow so it reads like a sticker cut.
  * Stickers: hand-drawn doodle stickers (stars, hearts, sparkles, flowers,
    smileys, clouds, moons) with white sticker borders float, wobble, spin and
    bounce on the beat behind the singers; their lines "boil" like
    hand-animated drawings. Each background cut brings a new set that pops in.
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "v5"))
import render_v5 as v5  # noqa: E402
from render_v5 import (BEATS, FACES, FPS, H, INTRO_END, N_OUT, SLOW_A, SLOW_B, SWITCH, TEAL, TEAL_D,  # noqa: E402
                       W, WORK, bgr, bg_index, get_bg, heart_pts, person_mask, read_frames, rng, star_pts,
                       stickers_intro)

GAP = 6          # px between silhouette and outline (1080p)
THICK = 22       # outline thickness (1080p)


# ---------------------------------------------------------------- matte
def box(x, r):
    return cv2.blur(x, (2 * r + 1, 2 * r + 1))


def guided(I, p, r=6, eps=2e-3):
    """Grey-guide guided filter (He et al.): matte edges follow image edges."""
    mI, mp = box(I, r), box(p, r)
    a = (box(I * p, r) - mI * mp) / (box(I * I, r) - mI * mI + eps)
    b = mp - a * mI
    return box(a, r), box(b, r)


def body_matte(img, f, ema):
    small = cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA)
    m = person_mask(small)
    for x, y, w, h in FACES[f]:
        if w > 0:
            cv2.ellipse(m, (int((x + w / 2) / 2), int((y + h / 2) / 2)), (int(w * 0.25), int(h * 0.31)), 0, 0, 360, 255, -1)
    m = m.astype(np.float32) / 255
    ema = m if ema is None else 0.35 * ema + 0.65 * m          # less lag on fast moves than v5
    mb = (ema > 0.5).astype(np.uint8) * 255
    mb = cv2.morphologyEx(mb, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    # fast guided filter: coefficients at 960, applied with the 1080p guide
    I = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    a, b = guided(I, mb.astype(np.float32) / 255)
    Ifull = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    a = cv2.resize(a, (W, H), interpolation=cv2.INTER_LINEAR)
    b = cv2.resize(b, (W, H), interpolation=cv2.INTER_LINEAR)
    alpha = np.clip(a * Ifull + b, 0, 1)
    # keep the refined edge but never stray far from the colour matte
    coarse = cv2.GaussianBlur(cv2.resize(mb, (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), 3).astype(np.float32) / 255
    alpha = np.where(np.abs(alpha - coarse) > 0.6, coarse, alpha)
    alpha = np.clip((alpha - 0.5) * 2.2 + 0.5, 0, 1)            # crisp, anti-aliased cut edge
    body = (alpha > 0.5).astype(np.uint8)
    # fill small enclosed gaps (white undershirt at the neckline read as wall),
    # counting the bottom frame edge as body; big gaps (wall seen through an
    # arm loop in the hug) stay open
    pad = cv2.copyMakeBorder(body, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    pad[-1, :] = 1
    inv = (1 - pad).astype(np.uint8)
    cv2.floodFill(inv, None, (0, 0), 0)
    holes = inv[1:-1, 1:-1]
    n, lab, st, _ = cv2.connectedComponentsWithStats(holes)
    small = np.isin(lab, [i for i in range(1, n) if st[i, 4] < W * H * 0.015])
    body[small] = 1
    alpha = np.maximum(alpha, small.astype(np.float32))
    body = cv2.morphologyEx(body, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    return alpha, body, ema


# ---------------------------------------------------------------- stickers
PAL = ["#ffd23f", "#ff7eb6", "#7ad7f0", "#b28dff", "#ff9f43", "#5fd3b4", "#ff5e7e", "#9be15d"]
KINDS = ["star", "heart", "sparkle", "flower", "smiley", "cloud", "moon", "star", "heart", "sparkle"]
SPR = 220                      # sprite canvas
INK = bgr("#2b2340")


def _poly_kind(kind, c, s, g, j):
    """Shape polygons for one 'boil' variant (j = jitter px)."""
    def jit(p):
        # smooth, low-frequency wobble (hand-drawn boil), not per-point noise
        n = len(p)
        ctrl = g.normal(0, j, (9, 2))
        u = np.arange(n) * 8.0 / n
        xp = np.arange(10)
        c2 = np.vstack([ctrl, ctrl[:1]])
        d = np.stack([np.interp(u, xp, c2[:, 0]), np.interp(u, xp, c2[:, 1])], 1)
        return (p + d).astype(np.int32)
    if kind == "star":
        return [jit(star_pts(c, c, s, 0, 0.48).astype(np.float32))]
    if kind == "heart":
        return [jit(heart_pts(c, c + 6, s * 0.95).astype(np.float32))]
    if kind == "sparkle":
        pts = []
        for i in range(8):
            r = s if i % 2 == 0 else s * 0.22
            a = -math.pi / 2 + i * math.pi / 4
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        return [jit(np.array(pts, np.float32))]
    if kind == "cloud":
        t = np.linspace(0, 2 * np.pi, 120)
        r = s * (0.62 + 0.1 * np.abs(np.sin(3 * t)))
        return [jit(np.stack([c + 1.35 * r * np.cos(t), c + 0.8 * r * np.sin(t)], 1).astype(np.float32))]
    if kind == "moon":                                          # crescent: outer arc + inner arc
        t = np.linspace(0.75, 2 * np.pi - 0.75, 70)
        outer = np.stack([c - s * np.cos(t), c - s * np.sin(t)], 1)
        a0 = math.acos(np.clip((s * math.cos(0.75) - 0.45 * s) / (0.82 * s), -1, 1))
        t2 = np.linspace(2 * np.pi - a0, a0, 50)
        inner = np.stack([c - 0.45 * s - 0.82 * s * np.cos(t2), c - 0.82 * s * np.sin(t2)], 1)
        return [jit(np.vstack([outer, inner]).astype(np.float32))]
    t = np.linspace(0, 2 * np.pi, 100)                          # smiley / flower base disc
    return [jit(np.stack([c + s * 0.8 * np.cos(t), c + s * 0.8 * np.sin(t)], 1).astype(np.float32))]


def make_sprite(kind, col, seed, j):
    g = rng(seed)
    c, s = SPR // 2, SPR * 0.33
    fill = np.zeros((SPR, SPR, 3), np.uint8)
    a = np.zeros((SPR, SPR), np.uint8)
    polys = _poly_kind(kind, c, s, g, j)
    if kind == "flower":
        for k in range(5):
            ang = k * 2 * math.pi / 5 + 0.3
            px, py = int(c + s * 0.55 * math.cos(ang)), int(c + s * 0.55 * math.sin(ang))
            cv2.circle(fill, (px, py), int(s * 0.45), bgr(col), -1, cv2.LINE_AA)
            cv2.circle(a, (px, py), int(s * 0.45), 255, -1, cv2.LINE_AA)
        for k in range(5):
            ang = k * 2 * math.pi / 5 + 0.3
            px, py = int(c + s * 0.55 * math.cos(ang)), int(c + s * 0.55 * math.sin(ang))
            cv2.circle(fill, (px, py), int(s * 0.45), INK, 4, cv2.LINE_AA)
        cv2.circle(fill, (c, c), int(s * 0.32), bgr("#ffd23f"), -1, cv2.LINE_AA)
        cv2.circle(fill, (c, c), int(s * 0.32), INK, 4, cv2.LINE_AA)
    else:
        cv2.fillPoly(fill, polys, bgr(col), cv2.LINE_AA)
        cv2.fillPoly(a, polys, 255, cv2.LINE_AA)
        # soft highlight like a glossy sticker
        hl = np.zeros_like(a)
        cv2.ellipse(hl, (int(c - s * 0.3), int(c - s * 0.35)), (int(s * 0.22), int(s * 0.12)), -30, 0, 360, 255, -1, cv2.LINE_AA)
        fill = np.where((hl > 0)[..., None] & (a > 0)[..., None], (fill * 0.4 + 255 * 0.6).astype(np.uint8), fill)
        cv2.polylines(fill, polys, True, INK, 5, cv2.LINE_AA)
    if kind == "smiley":
        cv2.circle(fill, (int(c - s * 0.28), int(c - s * 0.12)), int(s * 0.09), INK, -1, cv2.LINE_AA)
        cv2.circle(fill, (int(c + s * 0.28), int(c - s * 0.12)), int(s * 0.09), INK, -1, cv2.LINE_AA)
        cv2.ellipse(fill, (c, int(c + s * 0.08)), (int(s * 0.35), int(s * 0.25)), 0, 20, 160, INK, 5, cv2.LINE_AA)
        for sx in (-1, 1):
            cv2.circle(fill, (int(c + sx * s * 0.5), int(c + s * 0.15)), int(s * 0.1), bgr("#ff9bb8"), -1, cv2.LINE_AA)
    if kind in ("cloud", "heart"):
        for sx in (-1, 1):                                      # cute little face
            cv2.circle(fill, (int(c + sx * s * 0.22), int(c)), int(s * 0.06), INK, -1, cv2.LINE_AA)
        cv2.ellipse(fill, (c, int(c + s * 0.1)), (int(s * 0.1), int(s * 0.07)), 0, 0, 180, INK, 3, cv2.LINE_AA)
    # white sticker border + soft shadow
    border = cv2.dilate(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)))
    border = cv2.GaussianBlur(border, (0, 0), 0.8)
    shadow = cv2.GaussianBlur(np.roll(np.roll(border, 6, 0), 4, 1), (0, 0), 4)
    rgb = np.full((SPR, SPR, 3), 255, np.float32)
    af = (a.astype(np.float32) / 255)[..., None]
    rgb = rgb * (1 - af) + fill.astype(np.float32) * af
    out = np.zeros((SPR, SPR, 4), np.float32)
    bA = border.astype(np.float32) / 255
    sA = shadow.astype(np.float32) / 255 * 0.28
    out[..., :3] = rgb * bA[..., None]                          # premultiplied
    out[..., 3] = bA + sA * (1 - bA)
    out[..., :3] += 0                                           # shadow is black: adds alpha only
    return out


SPRITES = {}


def sprite(kind, ci, var):
    key = (kind, ci, var)
    if key not in SPRITES:
        SPRITES[key] = make_sprite(kind, PAL[ci], sum(map(ord, kind)) * 100 + ci * 10 + var, 3.0)
    return SPRITES[key]


def segment_stickers(k):
    """A fresh set of stickers for background segment k, kept out of the face zone."""
    g = rng(1000 + k)
    n = int(g.integers(6, 9))
    out = []
    for i in range(n):
        side = i % 3
        if side == 0:
            x, y = g.uniform(80, 520), g.uniform(80, 1000)
        elif side == 1:
            x, y = g.uniform(1400, 1840), g.uniform(80, 1000)
        else:
            x, y = g.uniform(500, 1420), g.uniform(60, 220)
        out.append(dict(kind=KINDS[int(g.integers(len(KINDS)))], ci=int(g.integers(len(PAL))),
                        x=x, y=y, size=g.uniform(0.8, 1.45), vx=g.uniform(-30, 30), vy=g.uniform(-25, 10),
                        ph=g.uniform(0, 6.28), spin=g.uniform(-0.35, 0.35), delay=0.04 * i))
    return out


_seg_cache = {}


def beat_bounce(t):
    k = int(np.searchsorted(BEATS, t, side="right")) - 1
    if k < 0:
        return 0.0
    return math.exp(-(t - BEATS[k]) * 7.0)


def draw_stickers(out, t, f, k, seg_t):
    if k not in _seg_cache:
        _seg_cache[k] = segment_stickers(k)
    bounce = beat_bounce(t)
    var = (f // 4) % 3                                           # line boil, 7.5 fps like hand animation
    for s in _seg_cache[k]:
        p = seg_t - s["delay"]
        if p <= 0:
            continue
        pop = 1.0 + 0.25 * math.sin(min(p / 0.22, 1) * math.pi) if p < 0.22 else 1.0
        grow = min(1.0, p / 0.12)
        sc = s["size"] * grow * pop * (1 + 0.1 * bounce)
        x = s["x"] + s["vx"] * seg_t + 14 * math.sin(1.7 * t + s["ph"])
        y = s["y"] + s["vy"] * seg_t + 10 * math.sin(2.3 * t + s["ph"] * 1.3) - 12 * bounce
        ang = math.degrees(s["spin"] * seg_t + 0.18 * math.sin(2.1 * t + s["ph"]))
        spr = sprite(s["kind"], s["ci"], var)
        M = cv2.getRotationMatrix2D((SPR / 2, SPR / 2), ang, sc)
        half = int(SPR * sc * 0.75) + 2
        x0, y0 = int(x) - half, int(y) - half
        M[0, 2] += half - SPR / 2
        M[1, 2] += half - SPR / 2
        warped = cv2.warpAffine(spr, M, (2 * half, 2 * half), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + 2 * half), min(H, y0 + 2 * half)
        if xb <= xa or yb <= ya:
            continue
        wv = warped[ya - y0:yb - y0, xa - x0:xb - x0]
        roi = out[ya:yb, xa:xb]
        roi[:] = roi * (1 - wv[..., 3:4]) + wv[..., :3]


# ---------------------------------------------------------------- frame
def render_frame(img, f, ema):
    t = f / FPS
    alpha, body, ema = body_matte(img, f, ema)
    if t < INTRO_END:
        out = img.copy()
        stickers_intro(out, t)
        return out, ema

    k, bi = bg_index(t)
    seg_t = t - SWITCH[k]
    z = 1.02 + 0.03 * min(1.0, seg_t / 3.0)
    if seg_t < 0.1:
        z += 0.025 * (1 - seg_t / 0.1)
    M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
    out = cv2.warpAffine(get_bg(bi), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    draw_stickers(out, t, f, k, seg_t)

    # outline band from the true silhouette (distance outside the body)
    d = cv2.distanceTransform((1 - body).astype(np.uint8), cv2.DIST_L2, 5)
    ring = np.clip(d - GAP + 0.5, 0, 1) * np.clip(GAP + THICK - d + 0.5, 0, 1)
    shadow = np.clip(GAP + THICK + 7 - d, 0, 7) / 7 * (d > GAP + THICK - 1)
    out *= 1 - 0.3 * shadow[..., None]
    g = rng(f // 3)
    sparkle = cv2.resize(g.random((H // 3, W // 3)).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)
    col = TEAL[None, None] * (0.82 + 0.36 * sparkle[..., None]) + (sparkle[..., None] > 0.92) * 80
    col = np.where(sparkle[..., None] < 0.1, TEAL_D[None, None], col)
    # thin white rim on both edges of the band gives the cut-sticker crispness
    rim = (np.clip(1.6 - np.abs(d - GAP - 0.8), 0, 1) + np.clip(1.6 - np.abs(d - GAP - THICK + 0.8), 0, 1)) * 0.55
    col = col * (1 - rim[..., None]) + 255 * rim[..., None]
    ra = ring[..., None]
    out = out * (1 - ra) + np.clip(col, 0, 255) * ra

    # black-and-white subjects on top
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
    prefix = sys.argv[3] if len(sys.argv) > 3 else "v6chunk"
    v5.build_backgrounds()
    n = max(1, min(8, (b - a) // 30))
    edges = np.linspace(a, b, n + 1).astype(int)
    with Pool(4) as pool:
        paths = pool.map(render_chunk, [(k, edges[k], edges[k + 1], prefix) for k in range(n)])
    with open(os.path.join(WORK, f"{prefix}.txt"), "w") as fh:
        fh.write("".join(f"file '{p}'\n" for p in paths))
    print("chunks done")


if __name__ == "__main__":
    main()
