"""v2 renderer: doodle universe, thicker glowing outlines, soft beauty grade.

Reuses the v1 sprite library (render.py) and adds new doodles, a hand-drawn
frame, drifting light leaks and a skin-only softening/warmth pass. Faces are
never reshaped: the beauty pass only blends a gentle edge-preserving smooth
and a peach tint into skin pixels of the original frame.
"""
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

import render as R
from common import (FPS, H, LAVENDER, N_OUT, PALETTE, PEACH, PINK, SLOW_A,
                    SLOW_B, W, WHITE, WORK, YELLOW, BABY_BLUE, MINT,
                    person_mask, read_frames)

with open(os.path.join(WORK, "plan_v2.json")) as fh:
    PLAN = json.load(fh)
EVENTS = PLAN["events"]
F0 = np.array([e["f0"] for e in EVENTS])
F1 = F0 + np.array([e["life"] for e in EVENTS])
R.GRAIN = [g * 0.75 for g in R.GRAIN]            # finer, lighter grain
MW, MH = R.MW, R.MH
CREAM = (235, 245, 255)


INK = (70, 25, 85)                                # deep plum ink border


class BoldLayer(R.Layer):
    """Doodle layer with bold strokes: widths x2 and a dark ink rim behind
    every stroke so saturated doodles stay readable on light and dark areas."""
    bold = True

    def poly(self, pts, color, alpha, thick=3, closed=True, fill=False):
        if not self.bold:
            return R.Layer.poly(self, pts, color, alpha, thick, closed, fill)
        t = 0 if thick <= 0 else (thick * 2 if thick >= 2 else 2)
        if fill and t == 0:
            t = 2                                  # filled shapes get an ink edge too
        if t > 0:
            R.Layer.poly(self, pts, INK, alpha * 0.9, t + 4, closed, False)
        if fill:
            R.Layer.poly(self, pts, color, alpha, 0, closed, True)
        if thick > 0:
            R.Layer.poly(self, pts, color, alpha, t, closed, False)

    def circle(self, c, r, color, alpha, thick=-1):
        if self.bold and r >= 4:
            R.Layer.circle(self, c, r + (2 if thick < 0 else 0), INK, alpha * 0.9,
                           thick if thick < 0 else thick * 2 + 4)
        R.Layer.circle(self, c, r, color, alpha, thick if thick < 0 else max(2, thick * 2))


def reveal_poly(L, pts, prog, color, alpha, thick):
    n = max(2, int(len(pts) * min(1.0, prog)))
    L.poly(pts[:n], color, alpha, thick=thick, closed=False)


def env(e, f):
    age = f - e["f0"]
    life = e["life"]
    return age, age / FPS, min(1.0, (life - age) / (0.5 * FPS), age / 6 + 0.15)


def draw_new(L, e, f):
    k = e["kind"]
    age, tau, fade = env(e, f)
    if age < 0 or age >= e["life"]:
        return
    t = f / FPS
    x = e["p0"][0] + e["v"][0] * tau
    y = e["p0"][1] + e["v"][1] * tau
    seed = int(e["f0"] * 17 + e["p0"][0]) & 0xFFFF
    boil = seed + (f // 3) % 3
    col = PALETTE[e.get("color", 0) % len(PALETTE)]
    s = e.get("size", 40)
    draw = min(1.0, tau / 1.1)                    # stroke-on animation
    beat = R.beat_env(t)
    if k == "tinystar":
        tw = 0.5 + 0.5 * math.sin(tau * (2.2 + seed % 5 * 0.6) + seed)
        a = fade * (0.35 + 0.65 * tw)
        sz = s * (0.7 + 0.3 * tw) * (1 + 0.25 * R.any_beat_env(t))
        if e.get("dot"):
            L.circle((x, y), max(1.2, sz * 0.28), col, a)
        else:
            L.poly(R.xform(R.STAR4, x, y, sz, tau * 0.6), col, a, thick=1, fill=True)
    elif k == "swirl":
        th = np.linspace(0, 4.2 * math.pi, 90)
        r = 0.08 + 0.92 * th / th[-1]
        pts = np.stack([r * np.cos(th + tau * 0.8), r * np.sin(th + tau * 0.8)], 1)
        pts = R.xform(R.jitter(pts, boil, 0.012), x, y, s * (1 + 0.06 * math.sin(tau * 2)))
        reveal_poly(L, pts, draw, col, fade, 3)
    elif k == "arrow":
        d = e.get("dir", 1)
        u = np.linspace(0, 1, 40)
        body = np.stack([u * 2 - 1, -0.45 * np.sin(u * math.pi) + 0.08 * np.sin(u * 9 + tau * 4)], 1)
        pts = R.xform(R.jitter(body, boil, 0.01), x, y, s, e.get("rot", 0) * 0.5, d)
        reveal_poly(L, pts, draw, col, fade, 3)
        if draw >= 1:
            hx, hy = pts[-1]
            ang = math.atan2(pts[-1][1] - pts[-4][1], pts[-1][0] - pts[-4][0])
            for da in (2.5, -2.5):
                L.poly(np.array([(hx, hy), (hx + 18 * math.cos(ang + da), hy + 18 * math.sin(ang + da))]),
                       col, fade, thick=3, closed=False)
    elif k == "wave":
        u = np.linspace(-1, 1, 60)
        for j, c in enumerate((col, WHITE)):
            amp = 0.18 + 0.08 * math.sin(tau * 2.5 + j)
            pts = np.stack([u, amp * np.sin(u * 7 - tau * 4 + j * 0.8) + j * 0.22], 1)
            reveal_poly(L, R.xform(pts, x, y, s), draw, c, fade * (1 - 0.35 * j), 3 - j)
    elif k == "soundwave":
        for j in range(7):
            hgt = 0.25 + 0.75 * abs(math.sin(tau * 5 + j * 1.3)) * (0.6 + 0.4 * beat)
            bx = x + (j - 3) * s * 0.22
            L.poly(np.array([(bx, y - hgt * s * 0.5), (bx, y + hgt * s * 0.5)]),
                   PALETTE[(e.get("color", 0) + j) % 6], fade, thick=5, closed=False)
    elif k in ("cloud", "cloud_big"):
        sc = s * (1.6 if k == "cloud_big" else 1)
        pts = []
        for cx, cy, r, a0, a1 in [(-0.6, 0.1, 0.38, 90, 270), (-0.2, -0.2, 0.45, 160, 340),
                                  (0.35, -0.15, 0.4, 200, 380), (0.7, 0.12, 0.32, 270, 450)]:
            a = np.radians(np.linspace(a0, a1, 14))
            pts.append(np.stack([cx + r * np.cos(a), cy + r * np.sin(a)], 1))
        outline = np.concatenate(pts + [np.array([(1.0, 0.42), (-0.95, 0.42)])])
        P = R.xform(R.jitter(outline, boil, 0.012), x + 6 * math.sin(tau), y + 4 * math.sin(tau * 1.3), sc)
        L.poly(P, WHITE, fade * 0.55 * min(1, draw * 2), thick=0, fill=True)
        reveal_poly(L, np.vstack([P, P[:1]]), draw, BABY_BLUE if k == "cloud" else LAVENDER, fade, 3)
    elif k in ("sun", "sun_big"):
        sc = s * (1.5 if k == "sun_big" else 0.8)
        L.circle((x, y), sc * 0.42 * min(1, draw * 1.5), YELLOW, fade * 0.95)
        L.circle((x, y), sc * 0.42 * min(1, draw * 1.5), WHITE, fade, thick=3)
        for j in range(10):
            a = j * math.pi / 5 + tau * 0.35
            r0, r1 = 0.58, 0.8 + 0.1 * math.sin(tau * 3 + j)
            if j / 10 < draw:
                L.poly(np.array([(x + sc * r0 * math.cos(a), y + sc * r0 * math.sin(a)),
                                 (x + sc * r1 * math.cos(a), y + sc * r1 * math.sin(a))]),
                       PEACH, fade, thick=3, closed=False)
    elif k == "rainbow":
        for j, c in enumerate((PINK, PEACH, YELLOW, MINT, BABY_BLUE, LAVENDER)):
            r = 1.0 - j * 0.11
            a = np.radians(np.linspace(180, 180 + 180 * draw, 50))
            pts = np.stack([r * np.cos(a), r * np.sin(a) * 0.9], 1)
            L.poly(R.xform(R.jitter(pts, boil + j, 0.006), x, y + s * 0.4, s * 1.2), c, fade * 0.9, thick=6,
                   closed=False)
        for side in (-1, 1):                      # little clouds at the feet
            for j in range(3):
                L.circle((x + side * s * 1.1 + j * 14 - 14, y + s * 0.42 - (j % 2) * 8), 15, WHITE, fade * 0.95)
    elif k == "bigmoon":
        e2 = dict(e, kind="moon", size=s * 0.9)
        R.draw_event(L, e2, f)
        for j in range(6):
            a = j * 1.05 + 0.3
            rr = s * (1.2 + 0.25 * (j % 2))
            tw = 0.5 + 0.5 * math.sin(tau * 3 + j)
            if j / 6 < draw:
                L.poly(R.xform(R.STAR5 if j % 2 else R.STAR4, x + rr * math.cos(a), y + rr * math.sin(a),
                               s * 0.13 * (0.6 + 0.4 * tw), tau), WHITE if j % 2 else YELLOW, fade, 1, fill=True)
    elif k in ("constellation", "constellation_big"):
        sc = s * (1.4 if k == "constellation_big" else 0.9)
        g = np.random.default_rng(seed)
        pts = np.cumsum(g.normal(0, 0.45, (6, 2)), 0)
        pts -= pts.mean(0)
        P = R.xform(pts, x, y, sc)
        n = 1 + draw * (len(P) - 1)
        for j in range(int(n)):
            L.poly(P[j:j + 2], LAVENDER, fade * 0.8, thick=2, closed=False)
        for j in range(len(P)):
            if j <= n:
                tw = 0.5 + 0.5 * math.sin(tau * 4 + j * 1.7)
                L.poly(R.xform(R.STAR4, P[j][0], P[j][1], 9 + 7 * tw, tau), WHITE, fade, 1, fill=True)
    elif k == "daisy":
        y += 8 * math.sin(tau * 1.6)
        sc = s * 0.85 * min(1.0, tau / 0.35)
        rot = tau * 0.5 + seed
        for side in (-1, 1):                      # green leaves
            leaf = R.ellipse_pts(side * 0.75, 0.75, 0.42, 0.17, side * 0.6, 20)
            L.poly(R.xform(leaf, x, y, sc), MINT, fade, 1, fill=True)
        pc = PALETTE[e.get("color", 0) % len(PALETTE)]
        for i in range(7):
            a = i * 2 * math.pi / 7 + rot
            pet = R.ellipse_pts(0.55 * math.cos(a), 0.55 * math.sin(a), 0.42, 0.22, a, 22)
            L.poly(R.xform(pet, x, y, sc), pc, fade, 1, fill=True)
        L.circle((x, y), sc * 0.27, YELLOW, fade)
        L.circle((x - sc * 0.08, y - sc * 0.08), sc * 0.08, WHITE, fade)
    elif k in ("heart", "dheart", "heart_wing"):
        R.draw_event(L, e, f)
        if (e["f0"] + int(e["p0"][0])) % 2 == 0:  # small trailing hearts
            for j in range(1, 3):
                tj = max(0.0, tau - 0.25 * j)
                hx = e["p0"][0] + e["v"][0] * tj + 10 * math.sin(tj * 2.2 + seed) - 18 * j
                hy = e["p0"][1] + e["v"][1] * tj + 28 * j
                P = R.xform(R.HEART, hx, hy, s * (0.35 - 0.08 * j), 0.2)
                L.poly(P, PALETTE[(e.get("color", 0) + j) % len(PALETTE)], fade * 0.9, 1, fill=True)
    elif k == "petal":
        x += 40 * math.sin(tau * 1.3 + seed)
        rot = tau * 1.8 + seed
        pts = R.ellipse_pts(0, 0, 1.0, 0.45, 0, 24)
        pts[:, 0] *= 0.5 + 0.5 * abs(math.cos(tau * 2 + seed))
        P = R.xform(pts, x, y, s, rot)
        L.poly(P, col, fade * 0.85, thick=0, fill=True)
        L.poly(P, WHITE, fade * 0.7, thick=1)
    elif k == "sparkle_ring":
        for j in range(8):
            a = j * math.pi / 4 + tau * 0.9
            rr = s * (0.6 + 0.4 * draw)
            tw = 0.5 + 0.5 * math.sin(tau * 6 + j)
            L.poly(R.xform(R.STAR4, x + rr * math.cos(a), y + rr * math.sin(a), 8 + 8 * tw, tau),
                   [WHITE, PINK, YELLOW, LAVENDER][j % 4], fade, 1, fill=True)
    else:
        R.draw_event(L, e, f)


# ------------------------------------------------------------- frame + leaks
def draw_frame(L, f):
    prog = min(1.0, f / 45.0)
    inset = 30
    tq = (f // 3) * 0.33
    top = np.stack([np.linspace(inset, W - inset, 120), np.full(120, inset)], 1)
    right = np.stack([np.full(70, W - inset), np.linspace(inset, H - inset, 70)], 1)
    bot = top[::-1].copy()
    bot[:, 1] = H - inset
    left = right[::-1].copy()
    left[:, 0] = inset
    path = np.concatenate([top, right, bot, left])
    arc = np.arange(len(path))
    nrm = np.zeros_like(path)
    nrm[:120, 1] = 1
    nrm[120:190, 0] = -1
    nrm[190:310, 1] = -1
    nrm[310:, 0] = 1
    wob = 2.2 * np.sin(arc * 0.21 + tq * 2) + 1.2 * np.sin(arc * 0.53 - tq * 3)
    P = path + nrm * wob[:, None]
    reveal_poly(L, P, prog, CREAM, 0.75, 2)
    P2 = path + nrm * (wob[:, None] * 0.7 + 7)
    reveal_poly(L, P2, prog, PINK, 0.45, 1)
    # corner accents: a tiny heart, star, swirl and moon that bob gently
    t = f / FPS
    corners = [(inset + 34, inset + 34), (W - inset - 34, inset + 34), (W - inset - 34, H - inset - 34),
               (inset + 34, H - inset - 34)]
    for j, (cx, cy) in enumerate(corners):
        b = 3 * math.sin(t * 2 + j)
        sc = 17 * prog * (1 + 0.15 * R.beat_env(t))
        if j == 0:
            P3 = R.xform(R.HEART, cx, cy + b, sc, -0.3)
            L.poly(P3, PINK, 0.9, 0, fill=True)
            L.poly(P3, WHITE, 0.9, 2)
        elif j == 1:
            P3 = R.xform(R.STAR5, cx, cy + b, sc, t * 0.5)
            L.poly(P3, YELLOW, 0.9, 0, fill=True)
            L.poly(P3, WHITE, 0.9, 2)
        elif j == 2:
            th = np.linspace(0, 3 * math.pi, 40)
            r = th / th[-1]
            L.poly(R.xform(np.stack([r * np.cos(th + t), r * np.sin(th + t)], 1), cx, cy + b, sc * 1.1),
                   LAVENDER, 0.9, 2, closed=False)
        else:
            L.poly(R.xform(R.STAR4, cx, cy + b, sc, t), WHITE, 0.9, 1, fill=True)


LW8, LH8 = W // 8, H // 8
_yy, _xx = np.mgrid[0:LH8, 0:LW8].astype(np.float32)


def light_leak(f):
    t = f / FPS
    acc = np.zeros((LH8, LW8, 3), np.float32)
    for j, (c, sp, ph) in enumerate([((150, 190, 255), 0.031, 0.0), ((230, 180, 255), 0.023, 2.1),
                                     ((170, 225, 255), 0.017, 4.0)]):
        cx = LW8 * (0.5 + 0.62 * math.sin(t * sp * 2 * math.pi + ph))
        cy = LH8 * (0.5 + 0.55 * math.cos(t * sp * 1.6 * math.pi + ph * 1.3))
        g = np.exp(-(((_xx - cx) / (LW8 * 0.28)) ** 2 + ((_yy - cy) / (LH8 * 0.35)) ** 2))
        acc += g[..., None] * np.array(c, np.float32)[None, None] * 0.11
    return cv2.resize(acc, (W, H))


# ------------------------------------------------------------- beauty
def beauty(img, mask_lo):
    """Skin-only soft glow: edge-preserving smoothing + peach warmth.

    Works on the original pixels; geometry is untouched and fine texture is
    kept because only the mid-frequency change of a half-res bilateral is
    blended back in.
    """
    half = cv2.resize(img, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    ycc = cv2.cvtColor(half, cv2.COLOR_BGR2YCrCb)
    skin = ((ycc[..., 1] > 135) & (ycc[..., 1] < 178) & (ycc[..., 2] > 80) & (ycc[..., 2] < 132)
            & (ycc[..., 0] > 60)).astype(np.float32)
    pm = cv2.resize(mask_lo, (W // 2, H // 2), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
    skin = cv2.GaussianBlur(skin * pm, (0, 0), 4)
    smooth = cv2.bilateralFilter(half, 7, 24, 5)
    delta = smooth.astype(np.float32) - half.astype(np.float32)
    delta = cv2.resize(delta, (W, H))
    sk = cv2.resize(skin, (W, H))[..., None]
    out = img.astype(np.float32) + delta * 0.6 * sk
    out = out * (1 + 0.045 * sk) + sk * np.array([2.0, 5.0, 9.0], np.float32)   # peach glow (BGR)
    return np.clip(out, 0, 255).astype(np.uint8)


# ------------------------------------------------------------- outline
def draw_outline(L, mask_lo, f, scene_start):
    t = f / FPS
    gap = cv2.dilate(mask_lo, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    cs, _ = cv2.findContours(gap, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    reveal = min(1.0, (f - scene_start) / 26.0)
    pulse = 0.85 + 0.15 * R.beat_env(t)
    sx = W / MW
    tq = (f // 3) * 0.33
    runs_all = []
    for c in cs:
        if cv2.contourArea(c) < 1500 or len(c) < 40:
            continue
        p = c[:, 0, :].astype(np.float64)[::2]
        on_border = (p[:, 0] <= 2) | (p[:, 0] >= MW - 3) | (p[:, 1] <= 2) | (p[:, 1] >= MH - 3)
        p = R.smooth_closed(p, 4.0) * sx + sx / 2
        d = np.roll(p, -1, 0) - np.roll(p, 1, 0)
        nrm = np.stack([d[:, 1], -d[:, 0]], 1)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
        arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
        for layer, (off, col, thick, alpha, ph) in enumerate(
                [(10, PINK, 8, 0.28, 0.4),                 # soft outer glow band
                 (0, (250, 242, 255), 4, 1.0, 0.0),        # main soft-white stroke
                 (8, (235, 170, 255), 3, 0.85, 1.7)]):     # pink-lavender accent
            wob = 2.0 * np.sin(arc * 0.04 + tq * 2 + ph) + 1.1 * np.sin(arc * 0.12 - tq * 3 + ph)
            q = p + nrm * (wob + off)[:, None]
            inside = ~on_border & (q[:, 0] > 6) & (q[:, 0] < W - 6) & (q[:, 1] > 6) & (q[:, 1] < H - 6)
            runs, cur = [], []
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
                if layer == 1:
                    runs_all.append(r)
    if runs_all:
        allp = np.concatenate(runs_all)
        for j in range(6):
            idx = int((j * 977 + f * (3 + j)) % len(allp))
            x, y = allp[idx]
            tw = 0.5 + 0.5 * math.sin(f * 0.35 + j * 1.9)
            L.poly(R.xform(R.STAR4, x, y, 10 + 10 * tw, f * 0.05), [WHITE, YELLOW, PINK][j % 3],
                   0.95 * reveal, thick=1, fill=True)


# ------------------------------------------------------------- frame
def render_frame(img, f, ema_mask, scene_start):
    t = f / FPS
    img = R.zoom(img, t, f)
    m = person_mask(cv2.resize(img, (MW, MH), interpolation=cv2.INTER_AREA)).astype(np.float32) / 255
    ema_mask = m if ema_mask is None else 0.55 * ema_mask + 0.45 * m
    mask_lo = (ema_mask > 0.5).astype(np.uint8) * 255

    img = beauty(img, mask_lo)
    base = R.grade(img, f) + light_leak(f)

    L = BoldLayer()
    L.bold = False
    draw_frame(L, f)
    L.bold = True
    active = np.nonzero((F0 <= f) & (f < F1))[0]
    for i in active:
        e = EVENTS[i]
        if e["kind"] != "text":
            draw_new(L, e, f)
    keep_out = cv2.dilate(mask_lo, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    keep_out = cv2.resize(cv2.GaussianBlur(keep_out, (0, 0), 1.5), (W, H)).astype(np.float32) / 255
    L.a = (L.a.astype(np.float32) * (1 - keep_out)).astype(np.uint8)
    L.bold = False
    draw_outline(L, mask_lo, f, scene_start)
    for i in active:
        if EVENTS[i]["kind"] == "text":
            R.draw_text(L, EVENTS[i], f)

    a = L.a.astype(np.float32)[..., None] / 255
    col = L.col.astype(np.float32)
    small = cv2.resize(col * a, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    glow = cv2.resize(cv2.GaussianBlur(small, (0, 0), 5), (W, H))
    out = base * (1 - a) + col * a + glow * 0.28
    tr = R.transition_amount(f)
    if tr > 0:
        out = out * (1 - tr) + R.CREAM * tr
    return np.clip(out, 0, 255).astype(np.uint8), ema_mask


def render_chunk(args):
    k, a, b = args
    path = os.path.join(WORK, f"v2chunk_{k:02d}.mp4")
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-maxrate", "6.5M", "-bufsize", "13M", "-pix_fmt", "yuv420p", "-threads", "2", path],
        stdin=subprocess.PIPE)
    scene = 0
    for c in (0, SLOW_A, SLOW_B):
        if c <= a:
            scene = c
    pre = max(scene, a - R.PREROLL)
    ema = None
    for i, fr in enumerate(read_frames(pre, b)):
        f = pre + i
        if f in (0, SLOW_A, SLOW_B):
            ema = None
            scene = f
        out, ema = render_frame(fr, f, ema, scene)
        if f >= a:
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
    with Pool(nproc) as pool:
        paths = pool.map(render_chunk, [(k, edges[k], edges[k + 1]) for k in range(n)])
    with open(os.path.join(WORK, "v2chunks.txt"), "w") as fh:
        for p in paths:
            fh.write(f"file '{p}'\n")
    print("chunks done")


if __name__ == "__main__":
    main()
