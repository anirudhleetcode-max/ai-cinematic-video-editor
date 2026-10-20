"""Pass 2: render the doodle music edit in parallel chunks.

The original frames are always the base image; every graphic is drawn on a
separate overlay layer and composited on top, and doodles are masked out
wherever a person is, so faces are never painted over or regenerated.
"""
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from common import (CORAL, FPS, H, LAVENDER, N_OUT, PALETTE, PINK, SLOW_A,
                    SLOW_B, W, WHITE, WORK, YELLOW, person_mask, read_frames)

FONT = os.path.join(os.path.dirname(__file__), "assets", "Caveat.ttf")
PLUM = (90, 40, 110)
MW, MH = 480, 270          # mask resolution (1/4)
PREROLL = 6

with open(os.path.join(WORK, "plan.json")) as fh:
    PLAN = json.load(fh)
EVENTS = PLAN["events"]
BEATS = np.array(PLAN["audio"]["beats"])
PH = PLAN["audio"]["downbeat_phase"]
DOWN = BEATS[PH::4]


# ------------------------------------------------------------- grading
def build_luts():
    x = np.arange(256) / 255.0
    base = 0.045 + 0.93 * x                          # lifted, airy blacks
    base = base + 0.035 * np.sin(np.pi * x) * (x - 0.5)  # gentle S
    r = base + 0.025 * x ** 2                        # warm highlights
    g = base - 0.008 * (1 - x) ** 2
    b = base + 0.04 * (1 - x) ** 2 - 0.012 * x ** 2  # lavender shadows
    to = lambda c: np.clip(c * 255, 0, 255).astype(np.uint8)
    return to(b), to(g), to(r)


LUT_B, LUT_G, LUT_R = build_luts()
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIGNETTE = (1 - 0.10 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) ** 1.5)[..., None]
del yy, xx
_g = np.random.default_rng(3)
GRAIN = [_g.normal(0, 2.6, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]


def grade(img, f):
    out = cv2.merge([cv2.LUT(c, l) for c, l in zip(cv2.split(img), (LUT_B, LUT_G, LUT_R))])
    o = out.astype(np.float32)
    small = cv2.resize(out, (W // 4, H // 4), interpolation=cv2.INTER_AREA).astype(np.float32)
    lum = small.mean(2, keepdims=True)
    bright = small * np.clip((lum - 165) / 90, 0, 1)
    dreamy = SLOW_A <= f < SLOW_B
    bloom = cv2.GaussianBlur(bright, (0, 0), 9)
    glow = cv2.GaussianBlur(small, (0, 0), 14)
    k_bloom = 0.55 if dreamy else 0.38
    k_glow = 0.14 if dreamy else 0.08
    add = cv2.resize(bloom * k_bloom, (W, H)) + 0
    o = o + add
    gl = cv2.resize(glow, (W, H))
    o = 255 - (255 - o) * (1 - k_glow * gl / 255)      # soft screen glow
    o *= VIGNETTE
    gr = cv2.resize(GRAIN[f % len(GRAIN)], (W, H), interpolation=cv2.INTER_LINEAR)
    o += gr[..., None]
    return o


# ------------------------------------------------------------- helpers
def beat_env(t, beats=DOWN, tau=0.18):
    k = np.searchsorted(beats, t) - 1
    if k < 0:
        return 0.0
    return math.exp(-(t - beats[k]) / tau)


def any_beat_env(t):
    return beat_env(t, BEATS, 0.12)


def ease_back(x):
    c1, c3 = 1.70158, 2.70158
    x = min(1.0, max(0.0, x))
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


class Layer:
    def __init__(self):
        self.col = np.zeros((H, W, 3), np.uint8)
        self.a = np.zeros((H, W), np.uint8)

    def poly(self, pts, color, alpha, thick=3, closed=True, fill=False):
        p = [np.round(np.asarray(pts) * 4).astype(np.int32)]
        av = int(255 * max(0, min(1, alpha)))
        if av <= 0:
            return
        if fill:
            cv2.fillPoly(self.col, p, color, cv2.LINE_AA, shift=2)
            cv2.fillPoly(self.a, p, av, cv2.LINE_AA, shift=2)
        if thick > 0:
            cv2.polylines(self.col, p, closed, color, thick, cv2.LINE_AA, shift=2)
            cv2.polylines(self.a, p, closed, av, thick, cv2.LINE_AA, shift=2)

    def circle(self, c, r, color, alpha, thick=-1):
        av = int(255 * max(0, min(1, alpha)))
        cc = (int(round(c[0] * 4)), int(round(c[1] * 4)))
        cv2.circle(self.col, cc, int(round(r * 4)), color, thick, cv2.LINE_AA, shift=2)
        cv2.circle(self.a, cc, int(round(r * 4)), av, thick, cv2.LINE_AA, shift=2)


def jitter(pts, seed, amt):
    g = np.random.default_rng(seed)
    return pts + g.normal(0, amt, pts.shape)


def xform(pts, cx, cy, s, rot=0.0, flip=1):
    p = np.asarray(pts, np.float64).copy()
    p[:, 0] *= flip
    c, sn = math.cos(rot), math.sin(rot)
    x = p[:, 0] * c - p[:, 1] * sn
    y = p[:, 0] * sn + p[:, 1] * c
    return np.stack([cx + x * s, cy + y * s], 1)


T60 = np.linspace(0, 2 * np.pi, 64)
HEART = np.stack([16 * np.sin(T60) ** 3,
                  -(13 * np.cos(T60) - 5 * np.cos(2 * T60) - 2 * np.cos(3 * T60) - np.cos(4 * T60))], 1) / 17
STAR5 = np.array([(math.cos(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45),
                   math.sin(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45)) for i in range(10)])
STAR4 = np.array([(math.cos(i * math.pi / 4) * (1 if i % 2 == 0 else 0.2),
                   math.sin(i * math.pi / 4) * (1 if i % 2 == 0 else 0.2)) for i in range(8)])


def ellipse_pts(cx, cy, rx, ry, rot=0.0, n=40):
    t = np.linspace(0, 2 * np.pi, n)
    x, y = rx * np.cos(t), ry * np.sin(t)
    c, s = math.cos(rot), math.sin(rot)
    return np.stack([cx + x * c - y * s, cy + x * s + y * c], 1)


# ------------------------------------------------------------- sprites
def draw_event(L, e, f):
    age = f - e["f0"]
    if age < 0 or age >= e["life"]:
        return
    tau = age / FPS
    t = f / FPS
    life = e["life"]
    x = e["p0"][0] + e["v"][0] * tau + 0.5 * e["a"][0] * tau ** 2
    y = e["p0"][1] + e["v"][1] * tau + 0.5 * e["a"][1] * tau ** 2
    seed = int(e["f0"] * 31 + e["p0"][0]) & 0xFFFF
    boil = seed + (f // 3) % 3                   # hand-drawn line boil
    fade = min(1.0, (life - age) / (0.35 * FPS), age / 4 + 0.2)
    pop = ease_back(tau / 0.28)
    k = e["kind"]
    col = PALETTE[e.get("color", 0) % len(PALETTE)]
    size = e.get("size", 30) * (1 + 0.14 * beat_env(t))
    rot = e.get("rot", 0.0)

    if k in ("sparkle", "star4"):
        tw = 0.6 + 0.4 * math.sin(tau * 14 + seed)
        s = size * pop * (0.55 + 0.45 * tw) * (1 - max(0, age / life - 0.6) * 1.5)
        if s <= 1:
            return
        pts = xform(STAR4, x, y, s, rot=tau * 1.5)
        L.poly(pts, col, fade, thick=1, fill=True)
        L.circle((x, y), max(1.5, s * 0.12), WHITE, fade)
    elif k in ("heart", "heart_wing", "dheart"):
        x += 10 * math.sin(tau * 2.2 + seed)
        s = size * pop
        rr = rot + 0.12 * math.sin(tau * 3 + seed)
        hearts = [(x, y, s)] if k != "dheart" else [(x - s * 0.45, y, s * 0.8), (x + s * 0.5, y - s * 0.35, s * 0.6)]
        for i, (hx, hy, hs) in enumerate(hearts):
            pts = xform(jitter(HEART, boil + i, 0.025), hx, hy, hs, rot=rr)
            filled = (seed + i) % 3 != 0
            if filled:
                L.poly(pts, PALETTE[(e.get("color", 0) + i) % 6], fade * 0.95, thick=0, fill=True)
            L.poly(pts, WHITE, fade, thick=3)
        if k == "heart_wing":
            flap = 0.65 + 0.35 * math.sin(tau * 10)
            for side in (-1, 1):
                for j in range(3):
                    cx0 = side * (1.05 + 0.25 * j)
                    arc = np.array([(cx0 + side * 0.18 * math.cos(a), -0.35 + 0.1 * j - 0.22 * math.sin(a) * flap)
                                    for a in np.linspace(0, math.pi, 12)])
                    L.poly(xform(arc, x, y, s, rot=rr), WHITE, fade, thick=2, closed=False)
    elif k == "star5":
        s = size * pop
        pts = xform(jitter(STAR5, boil, 0.03), x, y, s, rot=rot + tau * 0.8)
        L.poly(pts, YELLOW, fade * 0.9, thick=0, fill=True)
        L.poly(pts, WHITE, fade, thick=3)
    elif k == "note":
        x += 12 * math.sin(tau * 2.5 + seed)
        s = size * pop
        rr = rot + 0.25 * math.sin(tau * 4 + seed)
        head = ellipse_pts(0, 0.62, 0.3, 0.21, -0.35)
        L.poly(xform(head, x, y, s, rr), col, fade, thick=0, fill=True)
        L.poly(xform(head, x, y, s, rr), WHITE, fade, thick=2)
        stem = np.array([(0.27, 0.56), (0.29, -0.85)])
        flag = np.array([(0.29, -0.85), (0.5, -0.65), (0.66, -0.4), (0.55, -0.15)])
        L.poly(xform(jitter(stem, boil, 0.02), x, y, s, rr), WHITE, fade, thick=3, closed=False)
        L.poly(xform(jitter(flag, boil, 0.02), x, y, s, rr), WHITE, fade, thick=3, closed=False)
    elif k == "fish":
        d = e.get("dir", 1)
        s = size
        y += 14 * math.sin(tau * 2.4 + seed)
        wig = 0.16 * math.sin(tau * 12 + seed)
        tt = np.linspace(0, 2 * np.pi, 48)
        body = np.stack([np.cos(tt), 0.5 * np.sin(tt) * (0.78 + 0.22 * np.cos(tt))], 1)
        tail = np.array([(-0.88, 0), (-1.45, -0.42 + wig), (-1.32, 0 + wig * 0.5), (-1.45, 0.42 + wig)])
        tilt = 0.08 * math.sin(tau * 2.4 + seed)
        L.poly(xform(jitter(tail, boil, 0.02), x, y, s, tilt, d), col, fade, thick=0, fill=True)
        L.poly(xform(jitter(tail, boil, 0.02), x, y, s, tilt, d), WHITE, fade, thick=3)
        L.poly(xform(jitter(body, boil, 0.015), x, y, s, tilt, d), col, fade, thick=0, fill=True)
        L.poly(xform(jitter(body, boil, 0.015), x, y, s, tilt, d), WHITE, fade, thick=3)
        gill = np.array([(0.3, -0.3), (0.2, 0), (0.3, 0.3)])
        L.poly(xform(gill, x, y, s, tilt, d), WHITE, fade, thick=2, closed=False)
        ex, ey = xform(np.array([(0.58, -0.1)]), x, y, s, tilt, d)[0]
        L.circle((ex, ey), s * 0.08, PLUM, fade)
        L.circle((ex - d * s * 0.025, ey - s * 0.03), s * 0.025, WHITE, fade)
        for b in range(3):                       # little bubbles
            ph = (tau * 0.9 + b / 3) % 1
            bx, by = xform(np.array([(1.25 + 0.15 * b, -0.3 - ph * 1.6)]), x, y, s, 0, d)[0]
            L.circle((bx, by), s * (0.07 + 0.03 * b), WHITE, fade * (1 - ph), thick=2)
    elif k == "butterfly":
        x += 30 * math.sin(tau * 1.3 + seed)
        y += 18 * math.sin(tau * 2.1 + seed)
        s = size * pop
        flap = 0.25 + 0.75 * abs(math.cos(tau * 7 + seed))
        rr = 0.2 * math.sin(tau * 1.5)
        c2 = PALETTE[(e.get("color", 0) + 2) % 6]
        for side in (-1, 1):
            up = ellipse_pts(side * 0.55, -0.35, 0.55, 0.42, side * 0.5)
            lo = ellipse_pts(side * 0.38, 0.35, 0.33, 0.28, -side * 0.4)
            for wing, cc in ((up, col), (lo, c2)):
                wing = wing.copy()
                wing[:, 0] *= flap
                pts = xform(jitter(wing, boil, 0.02), x, y, s, rr)
                L.poly(pts, cc, fade * 0.9, thick=0, fill=True)
                L.poly(pts, WHITE, fade, thick=2)
        L.poly(xform(np.array([(0, -0.55), (0, 0.6)]), x, y, s, rr), PLUM, fade, thick=4, closed=False)
        for side in (-1, 1):
            ant = np.array([(0, -0.55), (side * 0.15, -0.85), (side * 0.3, -0.95)])
            L.poly(xform(ant, x, y, s, rr), PLUM, fade, thick=2, closed=False)
    elif k == "moon":
        y += 10 * math.sin(tau * 1.4)
        s = size * pop
        a1 = np.radians(np.linspace(70, 290, 30))
        a2 = np.radians(np.linspace(285, 75, 30))
        pts = np.concatenate([np.stack([np.cos(a1), np.sin(a1)], 1),
                              np.stack([0.42 + 0.8 * np.cos(a2), 0.8 * np.sin(a2)], 1)])
        pts = xform(jitter(pts, boil, 0.02), x, y, s, rot=-0.3 + 0.1 * math.sin(tau))
        L.poly(pts, YELLOW, fade * 0.9, thick=0, fill=True)
        L.poly(pts, WHITE, fade, thick=3)
        for j, (dx, dy) in enumerate([(1.4, -0.6), (1.1, 0.9), (-0.2, -1.5)]):
            tw = 0.5 + 0.5 * math.sin(tau * 5 + j * 2)
            L.poly(xform(STAR4, x + dx * s, y + dy * s, s * 0.25 * (0.6 + 0.4 * tw), tau), WHITE,
                   fade, thick=1, fill=True)
    elif k == "planet":
        y += 10 * math.sin(tau * 1.2)
        s = size * pop * 0.85
        ring = ellipse_pts(0, 0, 1.25, 0.32, -0.35, 60)
        back = ring[ring[:, 1] < 0.0]
        front = ring[ring[:, 1] >= 0.0]
        L.poly(xform(back, x, y, s), WHITE, fade, thick=3, closed=False)
        globe = ellipse_pts(0, 0, 0.62, 0.62, 0, 40)
        L.poly(xform(jitter(globe, boil, 0.015), x, y, s), LAVENDER, fade, thick=0, fill=True)
        L.poly(xform(jitter(globe, boil, 0.015), x, y, s), WHITE, fade, thick=3)
        L.poly(xform(front, x, y, s), WHITE, fade, thick=3, closed=False)
        L.circle((x + s * 0.2, y - s * 0.2), s * 0.09, PINK, fade)
    elif k == "daisy":
        y += 8 * math.sin(tau * 1.6)
        s = size * pop * 0.8
        for i in range(8):
            a = i * math.pi / 4 + tau * 0.4
            pet = ellipse_pts(0.55 * math.cos(a), 0.55 * math.sin(a), 0.42, 0.18, a, 24)
            L.poly(xform(pet, x, y, s), WHITE, fade * 0.95, thick=0, fill=True)
            L.poly(xform(pet, x, y, s), LAVENDER, fade, thick=2)
        L.circle((x, y), s * 0.25, YELLOW, fade)
    elif k == "shooting":
        d = e.get("dir", 1)
        vx, vy = e["v"]
        n = math.hypot(vx, vy)
        ux, uy = vx / n, vy / n
        for j in range(10):                      # motion-blurred trail
            a = fade * (1 - j / 10) * 0.8
            L.poly(np.array([(x - ux * j * 22, y - uy * j * 22), (x - ux * (j + 1) * 22, y - uy * (j + 1) * 22)]),
                   [YELLOW, PINK, LAVENDER][j % 3], a, thick=max(1, 7 - j // 2), closed=False)
        L.poly(xform(STAR5, x, y, size, tau * 6), YELLOW, fade, thick=0, fill=True)
        L.poly(xform(STAR5, x, y, size, tau * 6), WHITE, fade, thick=2)


# ------------------------------------------------------------- text
_text_cache = {}


def text_sprite(s, size):
    key = (s, size)
    if key not in _text_cache:
        font = ImageFont.truetype(FONT, int(size))
        font.set_variation_by_axes([650])
        bbox = font.getbbox(s, stroke_width=6)
        w, h = bbox[2] - bbox[0] + 140, bbox[3] - bbox[1] + 40
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.text((20 - bbox[0], 20 - bbox[1]), s, font=font, fill=(255, 238, 246, 255),
                stroke_width=6, stroke_fill=(110, 40, 90, 255))
        arr = np.array(im)
        _text_cache[key] = (arr[..., [2, 1, 0]].copy(), arr[..., 3].copy(), w - 140)
    return _text_cache[key]


def draw_text(L, e, f):
    age = f - e["f0"]
    if age < 0 or age >= e["life"]:
        return
    col, a, tw = text_sprite(e["text"], e["size"])
    h, w = a.shape
    reveal = min(1.0, age / (0.9 * FPS))         # written left -> right
    fade = min(1.0, (e["life"] - age) / (0.5 * FPS))
    x0 = int(e["p0"][0])
    y0 = int(e["p0"][1] + 6 * math.sin(age / FPS * 2.4))
    cut = int(20 + tw * reveal)
    aa = a.astype(np.float32) * fade
    aa[:, cut:] = 0
    ramp = np.clip((cut - np.arange(w)) / 30.0, 0, 1)
    aa *= ramp[None, :]
    y1, x1 = min(H, y0 + h), min(W, x0 + w)
    sub_a = aa[: y1 - y0, : x1 - x0]
    reg_a = L.a[y0:y1, x0:x1].astype(np.float32)
    keep = sub_a > reg_a
    L.col[y0:y1, x0:x1][keep] = col[: y1 - y0, : x1 - x0][keep]
    L.a[y0:y1, x0:x1] = np.maximum(reg_a, sub_a).astype(np.uint8)
    # tiny doodle accent at the end of the written line
    if reveal >= 1:
        ex, ey = x0 + 20 + tw + 40, y0 + h * 0.45
        t = age / FPS
        if "bestie" in e["text"]:
            pts = xform(HEART, ex, ey, 26 * (1 + 0.15 * beat_env(f / FPS)), 0.2)
            L.poly(pts, PINK, fade, thick=0, fill=True)
            L.poly(pts, WHITE, fade, thick=3)
        else:
            for j in range(3):
                tw2 = 0.5 + 0.5 * math.sin(t * 6 + j * 2.1)
                L.poly(xform(STAR4, ex + j * 34, ey + (j % 2) * 22 - 10, 14 * (0.6 + 0.4 * tw2), t),
                       [YELLOW, WHITE, PINK][j], fade, thick=1, fill=True)


# ------------------------------------------------------------- outline
def smooth_closed(pts, sigma):
    n = len(pts)
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    out = np.empty_like(pts, dtype=np.float64)
    for d in range(2):
        ext = np.concatenate([pts[-r:, d], pts[:, d], pts[:r, d]]).astype(np.float64)
        out[:, d] = np.convolve(ext, k, "valid")
    return out


def draw_outline(L, mask_lo, f, scene_start):
    t = f / FPS
    gap = cv2.dilate(mask_lo, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    cs, _ = cv2.findContours(gap, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    reveal = min(1.0, (f - scene_start) / 26.0)
    pulse = 0.78 + 0.22 * beat_env(t)
    sx = W / MW
    tq = (f // 3) * 0.33                          # boil: redraw every 3 frames
    sparkle_pts = []
    for c in cs:
        if cv2.contourArea(c) < 1500 or len(c) < 40:
            continue
        p = c[:, 0, :].astype(np.float64)[::2]
        on_border = (p[:, 0] <= 2) | (p[:, 0] >= MW - 3) | (p[:, 1] <= 2) | (p[:, 1] >= MH - 3)
        p = smooth_closed(p, 3.0) * sx + sx / 2
        # outward normals
        d = np.roll(p, -1, 0) - np.roll(p, 1, 0)
        nrm = np.stack([d[:, 1], -d[:, 0]], 1)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
        arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
        for layer, (off, col, thick, alpha, ph) in enumerate(
                [(0, (245, 232, 255), 3, 0.95, 0.0), (7, LAVENDER, 2, 0.55, 1.7)]):
            wob = 2.6 * np.sin(arc * 0.045 + tq * 2 + ph) + 1.4 * np.sin(arc * 0.13 - tq * 3 + ph)
            q = p + nrm * (wob + off)[:, None]
            inside = ~on_border & (q[:, 0] > 6) & (q[:, 0] < W - 6) & (q[:, 1] > 6) & (q[:, 1] < H - 6)
            # split into runs that stay off the frame border
            runs = []
            cur = []
            for i in range(len(q)):
                if inside[i]:
                    cur.append(q[i])
                elif cur:
                    runs.append(cur)
                    cur = []
            if cur:
                if runs and inside[0]:
                    runs[0] = cur + runs[0]
                else:
                    runs.append(cur)
            for r in runs:
                r = np.array(r)
                if len(r) < 8:
                    continue
                n = max(2, int(len(r) * reveal))
                L.poly(r[:n], col, alpha * pulse, thick=thick, closed=False)
                if layer == 0:
                    sparkle_pts.append(r)
    # a few sparkles travelling along the outline
    if sparkle_pts:
        allp = np.concatenate(sparkle_pts)
        g = np.random.default_rng(1234)
        for j in range(4):
            idx = int((g.integers(len(allp)) + f * (3 + j)) % len(allp))
            x, y = allp[idx]
            tw = 0.5 + 0.5 * math.sin(f * 0.35 + j * 1.9)
            L.poly(xform(STAR4, x, y, 9 + 9 * tw, f * 0.05), [WHITE, YELLOW, PINK, WHITE][j],
                   0.9 * reveal, thick=1, fill=True)


# ------------------------------------------------------------- frame
def zoom(img, t, f):
    z = 1 + 0.022 * beat_env(t, tau=0.22)
    if SLOW_A <= f < SLOW_B:                      # slow push-in during slow motion
        z += 0.04 * (f - SLOW_A) / (SLOW_B - SLOW_A)
    if z <= 1.0005:
        return img
    M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


CREAM = np.array([250, 240, 255], np.float32)


def transition_amount(f):
    a = 0.0
    if f < 15:
        a = 1 - f / 15
    for c in (SLOW_A, SLOW_B):
        a = max(a, 0.55 * math.exp(-abs(f - c + 0.5) / 3.5))
    if f > N_OUT - 24:
        a = max(a, (f - (N_OUT - 24)) / 24)
    return a


def render_frame(img, f, ema_mask, scene_start):
    t = f / FPS
    img = zoom(img, t, f)
    m = person_mask(cv2.resize(img, (MW, MH), interpolation=cv2.INTER_AREA)).astype(np.float32) / 255
    ema_mask = m if ema_mask is None else 0.55 * ema_mask + 0.45 * m
    mask_lo = (ema_mask > 0.5).astype(np.uint8) * 255

    base = grade(img, f)

    L = Layer()
    for e in EVENTS:
        if e["f0"] > f:
            break
        if e["kind"] != "text":
            draw_event(L, e, f)
    # doodles never sit on top of a person: cut them out with a soft margin
    keep_out = cv2.dilate(mask_lo, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    keep_out = cv2.resize(cv2.GaussianBlur(keep_out, (0, 0), 1.5), (W, H)).astype(np.float32) / 255
    L.a = (L.a.astype(np.float32) * (1 - keep_out)).astype(np.uint8)
    draw_outline(L, mask_lo, f, scene_start)
    for e in EVENTS:
        if e["f0"] > f:
            break
        if e["kind"] == "text":
            draw_text(L, e, f)

    a = L.a.astype(np.float32)[..., None] / 255
    col = L.col.astype(np.float32)
    # soft colored glow around the doodles
    small = cv2.resize(col * a, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    glow = cv2.resize(cv2.GaussianBlur(small, (0, 0), 5), (W, H))
    out = base * (1 - a) + col * a
    out = out + glow * 0.55
    tr = transition_amount(f)
    if tr > 0:
        out = out * (1 - tr) + CREAM * tr
    return np.clip(out, 0, 255).astype(np.uint8), ema_mask


def render_chunk(args):
    k, a, b = args
    path = os.path.join(WORK, f"chunk_{k:02d}.mp4")
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "19",
         "-pix_fmt", "yuv420p", "-threads", "2", path], stdin=subprocess.PIPE)
    start = a
    for c in (0, SLOW_A, SLOW_B):
        if c <= a:
            scene = c
    pre = max(scene, a - PREROLL)
    ema = None
    for i, fr in enumerate(read_frames(pre, b)):
        f = pre + i
        if f in (0, SLOW_A, SLOW_B):
            ema = None
            scene = f
        out, ema = render_frame(fr, f, ema, scene)
        if f >= start:
            enc.stdin.write(out.tobytes())
        if f % 150 == 0:
            print(f"chunk {k}: frame {f}", flush=True)
    enc.stdin.close()
    enc.wait()
    if enc.returncode:
        raise RuntimeError(f"encoder failed for chunk {k}")
    return path


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else N_OUT
    nproc = int(os.environ.get("EDIT_PROCS", "4"))
    n = max(1, nproc * 2)
    edges = np.linspace(a, b, n + 1).astype(int)
    jobs = [(k, edges[k], edges[k + 1]) for k in range(n)]
    with Pool(nproc) as pool:
        paths = pool.map(render_chunk, jobs)
    with open(os.path.join(WORK, "chunks.txt"), "w") as fh:
        for p in paths:
            fh.write(f"file '{p}'\n")
    print("chunks done")


if __name__ == "__main__":
    main()
