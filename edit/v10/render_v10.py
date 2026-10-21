"""v10: a 10-second scene-cut music edit on the reference reel's song.

The edit is driven entirely by edl.json (scenes, source ranges, worlds,
subject treatments, outlines, transitions) and music.json (the song's beat
and accent map). Pipeline:
  1. Each scene is rendered over its frame range, plus any transition
     overlap, into a uint8 frame store (WORK/v10/scene_<id>.npy).
  2. The editor assembles the 300 output frames from the stores, applying
     the transitions, and encodes them. The reference audio is stream-copied
     unchanged.

Subject mattes are the v9 Robust Video Matting alphas (edit/v9/matte_rvm.py).
The S3 brush strokes are v4's PaintStroke engine; S6 uses the v4 render
frames as they are.

Usage: EDIT_WORK=... EDIT_SOURCE=... python3 render_v10.py [scene ids...]
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
sys.path.insert(0, os.path.join(HERE, "..", "v4"))
sys.path.insert(0, os.path.join(HERE, "..", "v7"))
sys.path.insert(0, os.path.join(HERE, "..", "v9"))
from common import W, H, WORK, read_frames  # noqa: E402
import engine as E4  # noqa: E402
import world as Wd  # noqa: E402
from matte_rvm import alpha_path, chunk_ranges  # noqa: E402
from render_v7 import outline_field  # noqa: E402

FPS = 30
EDL = json.load(open(os.path.join(HERE, "edl.json")))
OUT = os.path.join(WORK, "v10")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
V4_VIDEO = os.path.join(REPO, "output", "v4", "cinematic_doodle_music_edit_v4.mp4")
os.makedirs(OUT, exist_ok=True)


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)


INK, PAPER, GOLD, CORAL, DUSK = hexc("#1d2340"), hexc("#f3ead8"), hexc("#d9a84e"), hexc("#e0705a"), hexc("#7fa3c6")
SEPIA_INK, SEPIA_PAPER = hexc("#2a1f1a"), hexc("#f1e6d2")


def rng(s):
    return np.random.default_rng(s)


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- frame access
def scene_range(sc):
    """Frames a scene must be rendered for (its own range plus transition overlaps)."""
    a, b = sc["start"], sc["end"]
    for tr in EDL["transitions"]:
        if tr.get("to") == sc["id"]:
            a = min(a, tr["at"] - tr.get("frames_before", 0))
        if tr.get("from") == sc["id"]:
            b = max(b, tr["at"] + tr.get("frames_after", 0))
    return max(0, a), min(EDL["frames"], b)


def src_of(sc, k):
    return sc["src_in"] + (k - sc["start"])


def read_alpha(f0, n):
    """Alpha frames for timeline frames [f0, f0+n) from the v9 matte chunks."""
    out = []
    f = f0
    while len(out) < n:
        k, a, b, pre = [c for c in chunk_ranges() if c[3] <= f < c[2]][-1]
        m = min(n - len(out), b - f)
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", alpha_path(k), "-vf",
                            f"select=between(n\\,{f - pre}\\,{f - pre + m - 1})", "-vsync", "0",
                            "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
        arr = np.frombuffer(p, np.uint8).reshape(-1, H, W)
        if len(arr) != m:
            raise RuntimeError(f"alpha read {f}+{m}: got {len(arr)}")
        out.extend(arr.astype(np.float32) / 255)
        f += m
    return out


def read_v4(f0, n):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", V4_VIDEO, "-vf",
                        f"select=between(n\\,{f0}\\,{f0 + n - 1})", "-vsync", "0",
                        "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True).stdout
    arr = np.frombuffer(p, np.uint8).reshape(-1, H, W, 3)
    if len(arr) != n:
        raise RuntimeError(f"v4 read {f0}+{n}: got {len(arr)}")
    return list(arr)


# ---------------------------------------------------------------- textures
def paper(base, seed, grain=4.0, mottle=2.5):
    g = rng(seed)
    low = cv2.GaussianBlur(g.normal(0, 1, (H // 16, W // 16)).astype(np.float32), (0, 0), 5)
    low = cv2.resize(low / (low.std() + 1e-6), (W, H), interpolation=cv2.INTER_CUBIC)
    fine = cv2.GaussianBlur(g.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.7)
    img = base[None, None] + (low * mottle + fine * grain)[..., None]
    fib = np.zeros((H, W), np.float32)
    for _ in range(900):
        x, y = g.uniform(0, W), g.uniform(0, H)
        a = g.uniform(0, math.pi)
        L = g.uniform(6, 26)
        cv2.line(fib, (int(x), int(y)), (int(x + L * math.cos(a)), int(y + L * math.sin(a))), 1.0, 1, cv2.LINE_AA)
    img -= cv2.GaussianBlur(fib, (0, 0), 0.6)[..., None] * 6
    return np.clip(img, 0, 255)


def grade(img, lift=(6, 4, 2), contrast=1.08, sat=1.0, warm=0.0):
    x = img.astype(np.float32)
    if sat != 1.0:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)[..., None]
        x = g + (x - g) * sat
    x = (x - 128) * contrast + 128 + np.array(lift, np.float32)
    x += np.array([-warm * 0.6, warm * 0.1, warm], np.float32)
    return np.clip(x, 0, 255)


def vignette(strength=0.28):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    return (1 - strength * np.clip(r - 0.55, 0, 1) ** 1.4)[..., None]


VIG = vignette()


def film_grain(f, amt=3.0):
    n = rng(9000 + f).normal(0, amt, (H // 2, W // 2)).astype(np.float32)
    return cv2.resize(n, (W, H), interpolation=cv2.INTER_LINEAR)[..., None]


def bezier(pts, n=200):
    return E4.bezier(pts, n)


class Ink:
    """Accumulates strokes of one colour in a single alpha layer, blended once."""

    def __init__(self):
        self.a = np.zeros((H, W), np.float32)

    def line(self, pts, width, alpha=1.0):
        p = np.round(np.asarray(pts, np.float64) * 4).astype(np.int32)
        n = len(p)
        if n < 2:
            return
        for i in range(n - 1):
            u = i / max(1, n - 2)
            w = max(1, int(round(width * (0.45 + 0.55 * math.sin(math.pi * min(1.0, u + 0.02))))))   # tapered ends
            cv2.line(self.a, tuple(p[i]), tuple(p[i + 1]), float(alpha), w, cv2.LINE_AA, shift=2)

    def fill(self, pts, alpha=1.0):
        cv2.fillPoly(self.a, [np.round(np.asarray(pts) * 4).astype(np.int32)], float(alpha), cv2.LINE_AA, shift=2)

    def blend(self, img, col):
        a = np.clip(self.a, 0, 1)[..., None]
        img[:] = img * (1 - a) + col[None, None] * a


def ink_line(img, pts, col, width, alpha=1.0):
    lay = Ink()
    lay.line(pts, width, alpha)
    lay.blend(img, col)


# ---------------------------------------------------------------- outlines
def stable_band(field_on, gap, width):
    on = cv2.GaussianBlur(field_on.astype(np.float32), (0, 0), 1.5)
    sil = cv2.resize(on, (W, H), interpolation=cv2.INTER_CUBIC) > 0.5
    d = cv2.distanceTransform((~sil).astype(np.uint8), cv2.DIST_L2, 5)
    band = np.clip(d - gap + 0.5, 0, 1) * np.clip(gap + width - d + 0.5, 0, 1)
    return band, d


def draw_outline(bg, kind, field_on, f, reveal=1.0):
    if kind == "none":
        return bg
    if kind == "ink_double":
        b1, d = stable_band(field_on, 9, 3)
        b2 = np.clip(d - 17 + 0.5, 0, 1) * np.clip(17 + 1.6 - d + 0.5, 0, 1)
        brk = cv2.resize(rng(77).random((H // 24, W // 24)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        b2 = b2 * (brk > 0.35)                                   # second line is broken, like a quick sketch
        m = (b1 * 0.9 + b2 * 0.6)
        if reveal < 1:
            m = m * (np.arange(H, dtype=np.float32)[:, None] < reveal * H * 1.15)
        a = m[..., None]
        return bg * (1 - a) + SEPIA_INK[None, None] * a
    if kind == "white_hairline":
        b, _ = stable_band(field_on, 12, 3)
        a = (b * 0.85)[..., None]
        return bg * (1 - a) + np.array([245, 245, 250], np.float32)[None, None] * a
    if kind == "paper_cut":
        b, d = stable_band(field_on, 0, 15)
        sh = np.clip(1 - np.abs(d - 19) / 6, 0, 1) * (d > 14)
        bg = bg * (1 - 0.28 * sh[..., None])
        a = b[..., None]
        return bg * (1 - a) + PAPER[None, None] * a
    if kind == "gold_line":
        b, _ = stable_band(field_on, 14, 4)
        glow = cv2.GaussianBlur(b, (0, 0), 6)
        bg = bg + (glow * 0.35)[..., None] * GOLD[None, None]
        a = (b * 0.95)[..., None]
        return np.clip(bg * (1 - a) + hexc("#f2cf7a")[None, None] * a, 0, 255)
    raise ValueError(kind)


# ---------------------------------------------------------------- subject treatments
def subject(img, kind, f):
    if kind == "sepia_duotone":
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
        g = np.clip((g - 0.5) * 1.15 + 0.53, 0, 1) ** 0.95
        return SEPIA_INK[None, None] * (1 - g[..., None]) + SEPIA_PAPER[None, None] * g[..., None]
    if kind == "bw_contrast":
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        g = np.clip((g - 128) * 1.25 + 134, 0, 255)
        return np.repeat(g[..., None], 3, 2)
    if kind == "bw_warm":
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        g = np.clip((g - 128) * 1.12 + 132, 0, 255)[..., None]
        return np.clip(g + np.array([-6, 0, 8], np.float32), 0, 255)
    if kind == "golden_colour":
        x = grade(img, lift=(4, 6, 10), contrast=1.05, sat=0.88, warm=10)
        return x
    raise ValueError(kind)


# ---------------------------------------------------------------- worlds
_cache = {}


def cached(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def leaf(wash, ink, base, ang, size, alpha):
    t = np.linspace(0, 1, 24)
    tip = base + size * np.array([math.cos(ang), math.sin(ang)])
    nrm = np.array([-math.sin(ang), math.cos(ang)]) * size * 0.32
    mid = base + (tip - base) * t[:, None]
    bulge = np.sin(t * math.pi)[:, None]
    side1, side2 = mid + nrm * bulge, mid - nrm * bulge
    wash.fill(np.vstack([side1, side2[::-1]]), 0.35 * alpha)
    ink.line(side1, 2, 0.9 * alpha)
    ink.line(side2, 2, 0.9 * alpha)
    ink.line(mid[:18], 1, 0.6 * alpha)


def world_ink_paper(t, f):
    base = cached("paper_ink", lambda: paper(hexc("#f1e6d2"), 21, 4, 3))
    img = base.copy()
    ink, hatch, wash = Ink(), Ink(), Ink()
    drift = t * 9.0
    u = ease(t / 0.9)                                            # the drawings draw themselves on
    for k, (y0, amp, ph) in enumerate(((760, 40, 0.3), (840, 30, 1.7), (930, 22, 2.9))):   # hatched hills
        xs = np.linspace(-40, W + 40, 120)
        ys = y0 + amp * np.sin(xs / 260 + ph) + 10 * np.sin(xs / 90 + ph * 2)
        n = int(len(xs) * min(1.0, u * 1.3 - k * 0.12))
        dx = drift * (0.5 + 0.2 * k)
        if n > 2:
            ink.line(np.stack([xs[:n] + dx, ys[:n]], 1), 2, 0.75)
            for x, y in zip(xs[:n:3], ys[:n:3]):
                hatch.line([(x + dx, y + 6), (x + 14 + dx, y + 26)], 1, 0.35)
    if u > 0.2:                                                  # hatched sun
        a = ease((u - 0.2) / 0.5)
        c = (1640 + drift * 0.3, 170)
        th = np.linspace(0, 2 * math.pi * a, 80)
        ink.line(np.stack([c[0] + 62 * np.cos(th - 1.2), c[1] + 62 * np.sin(th - 1.2)], 1), 2, 0.85)
        for i in range(-60, 61, 11):
            h = math.sqrt(max(0, 62 ** 2 - i ** 2))
            hatch.line([(c[0] + i, c[1] - h * 0.2), (c[0] + i - 8, c[1] + h * 0.85)], 1, 0.3 * a)
    for x0, seed in ((150, 1), (320, 2), (1770, 3), (1600, 4)):  # botanical stems at both sides
        g = rng(seed)
        sx = x0 + drift * 0.8
        pts = [(sx, H + 20), (sx + g.uniform(-80, 80), 700), (sx + g.uniform(-120, 120), 420),
               (sx + g.uniform(-60, 60), g.uniform(160, 300))]
        path = bezier(pts, 160)
        n = int(len(path) * min(1.0, u * 1.1))
        if n > 2:
            ink.line(path[:n], 3, 0.9)
        for j in range(9):
            uu = 0.15 + j * 0.09
            if uu * len(path) > n:
                break
            p = path[int(uu * (len(path) - 1))]
            ang = (-0.6 if j % 2 else -2.5) + g.normal(0, 0.2)
            leaf(wash, ink, p, ang, 46 + g.uniform(-10, 14), ease((n / len(path) - uu) * 6))
    wash.blend(img, hexc("#b98d5e"))
    hatch.blend(img, SEPIA_INK)
    ink.blend(img, SEPIA_INK)
    return img


def world_indigo(t, f):
    base = cached("paper_indigo", lambda: paper(hexc("#1b2140"), 31, 3, 2.5))
    img = base.copy()
    cfg = E4.load_config()
    body, pnt, light = Wd.Layer(), Wd.Layer(), Wd.Layer()
    specs = [
        dict(id="a", t0=0.0, dur=0.42, kind="sweep", width=120, pts=[[1980, 120], [1300, 40], [600, 260], [-60, 170]],
             colors=["cobalt", "azure", "pale_cyan"], hold=5, dissolve=1, seed=41),
        dict(id="b", t0=0.38, dur=0.36, kind="sweep", width=80, pts=[[-60, 980], [500, 860], [1300, 1010], [1980, 900]],
             colors=["indigo", "azure", "white"], hold=5, dissolve=1, seed=42),
        dict(id="c", t0=0.62, dur=0.4, kind="sweep", width=36, pts=[[1980, 300], [1500, 260], [1100, 340], [700, 300]],
             colors=["azure", "pale_cyan"], hold=5, dissolve=1, seed=43),
    ]
    for s in specs:
        E4.PaintStroke(s, cfg).draw(body, pnt, light, t)
    ba = body.a.astype(np.float32)[..., None] / 255
    img = img * (1 - ba * 0.9) + body.col.astype(np.float32) * ba * 0.9       # pigment body (over: the paper is dark)
    pa = pnt.a.astype(np.float32)[..., None] / 255
    img = img * (1 - pa) + pnt.col.astype(np.float32) * pa
    la = light.a.astype(np.float32)[..., None] / 255
    lc = light.col.astype(np.float32) * la
    img = img + lc * 0.8 + cv2.GaussianBlur(lc, (0, 0), 6) * 1.2
    return np.clip(img, 0, 255)


def panel(i):
    g = rng(500 + i)
    if i == 0:                                                   # gold constellation on navy
        img = paper(INK, 51, 3, 4)
        pts = [(g.uniform(80, W - 80), g.uniform(60, H - 60)) for _ in range(26)]
        for a, b in zip(pts[::2], pts[1::2]):
            if math.dist(a, b) < 520:
                ink_line(img, [a, b], GOLD, 3, 0.6)
        for (x, y) in pts:
            s = g.uniform(12, 30)
            for ang in (0, math.pi / 2):
                ink_line(img, [(x - s * math.cos(ang), y - s * math.sin(ang)), (x + s * math.cos(ang), y + s * math.sin(ang))], GOLD, 4, 0.95)
            cv2.circle(img, (int(x), int(y)), 5, tuple(float(v) for v in GOLD), -1, cv2.LINE_AA)
        return img
    if i == 1:                                                   # coral with cream sun rays + halftone
        img = paper(CORAL, 52, 3, 5)
        c = np.array([W / 2, H * 1.05])
        lay = np.zeros((H, W), np.float32)
        for k in range(18):
            a0 = math.pi + k * math.pi / 18
            poly = np.array([c, c + 2400 * np.array([math.cos(a0), math.sin(a0)]),
                             c + 2400 * np.array([math.cos(a0 + math.pi / 36), math.sin(a0 + math.pi / 36)])])
            cv2.fillPoly(lay, [np.round(poly).astype(np.int32)], 1.0, cv2.LINE_AA)
        img = img * (1 - 0.22 * lay[..., None]) + PAPER[None, None] * 0.22 * lay[..., None]
        for y in range(20, H, 26):
            for x in range(20 + (y // 26 % 2) * 13, W, 26):
                r = 5.5 * max(0.0, (y - H * 0.55) / (H * 0.45))
                if r > 0.8:
                    cv2.circle(img, (x, y), int(round(r)), tuple(float(v) for v in hexc("#b9503f")), -1, cv2.LINE_AA)
        return img
    if i == 2:                                                   # Bauhaus arcs on cream
        img = paper(PAPER, 53, 3, 5)
        for (cx, cy, r, col, a0, a1) in ((0, 0, 420, INK, 0, 90), (W, H, 520, CORAL, 180, 270), (W, 0, 300, GOLD, 90, 180),
                                         (0, H, 260, DUSK, 270, 360), (W * 0.12, H * 0.62, 90, GOLD, 0, 360)):
            cv2.ellipse(img, (int(cx), int(cy)), (r, r), 0, a0, a1, tuple(float(v) for v in col), -1, cv2.LINE_AA)
        for k in range(5):
            cv2.ellipse(img, (W, H), (600 + k * 34, 600 + k * 34), 0, 180, 270, tuple(float(v) for v in INK), 2, cv2.LINE_AA)
        return img
    if i == 3:                                                   # white line waves on dusty blue
        img = paper(DUSK, 54, 3, 5)
        xs = np.linspace(0, W, 200)
        for y0 in range(-20, H + 40, 34):
            ys = y0 + 14 * np.sin(xs / 140 + y0 * 0.05)
            ink_line(img, np.stack([xs, ys], 1), np.array([248, 246, 240], np.float32), 2, 0.75)
        return img
    if i == 4:                                                   # navy halftone on gold
        img = paper(GOLD, 55, 3, 5)
        c = np.array([W * 0.8, H * 0.3])
        for y in range(18, H, 30):
            for x in range(18 + (y // 30 % 2) * 15, W, 30):
                r = 9 * (1 - min(1, math.dist((x, y), c) / 1300))
                if r > 0.8:
                    cv2.circle(img, (x, y), int(round(r)), tuple(float(v) for v in INK), -1, cv2.LINE_AA)
        return img
    img = paper(INK, 56, 3, 4)                                   # concentric cream arcs on ink
    for k in range(26):
        r = 120 + k * 58
        cv2.ellipse(img, (0, 0), (r, r), 0, 0, 90, tuple(float(v) for v in PAPER), 2 if k % 4 else 4, cv2.LINE_AA)
    cv2.circle(img, (int(W * 0.86), int(H * 0.2)), 70, tuple(float(v) for v in CORAL), -1, cv2.LINE_AA)
    return img


def world_panels(t, f, sc):
    cuts = [sc["start"]] + sc["panel_cuts"]
    i = max(j for j, c in enumerate(cuts) if c <= f)
    img = cached(f"panel{i}", lambda: panel(i))
    age = f - cuts[i]
    z = 1.0 + 0.035 * (1 - ease(age / 4.0))                      # settles into place on each cut
    if z > 1.0001:
        M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
        img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return img.astype(np.float32)


def cloud_layer(seed, n, ymin, ymax, scale, col, rim):
    g = rng(seed)
    m = np.zeros((H, W * 2), np.float32)
    for _ in range(n):
        cx, cy = g.uniform(0, W * 2), g.uniform(ymin, ymax)
        for _ in range(int(g.integers(5, 9))):
            cv2.ellipse(m, (int(cx + g.normal(0, 90 * scale)), int(cy + g.normal(0, 22 * scale))),
                        (int(g.uniform(70, 150) * scale), int(g.uniform(32, 60) * scale)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    m = cv2.GaussianBlur(m, (0, 0), 16 * scale)
    m = np.clip(m * 1.4, 0, 1) * 0.8
    edge = np.clip(m - cv2.GaussianBlur(np.roll(m, 14, 0), (0, 0), 5), 0, 1)
    return m, edge, col, rim


def world_sky(t, f):
    def base():
        yy = np.linspace(0, 1, H)[:, None, None]
        stops = [(0.0, hexc("#22305a")), (0.45, hexc("#5d5486")), (0.75, hexc("#e2a184")), (1.0, hexc("#f6d49a"))]
        img = np.zeros((H, 1, 3), np.float32)
        for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
            s = np.clip((yy - y0) / (y1 - y0), 0, 1)
            img = np.where((yy >= y0) & (yy <= y1), c0 + (c1 - c0) * s, img)
        img = np.repeat(img, W, 1)
        yv, xv = np.mgrid[0:H, 0:W].astype(np.float32)
        sun = np.exp(-(((xv - W * 0.2) / 520) ** 2 + ((yv - H * 0.18) / 420) ** 2))
        img = img + sun[..., None] * hexc("#ffe2a8") * 0.55
        return paper(np.zeros(3, np.float32), 61, 2.5, 3) + img
    img = cached("sky", base).copy()
    layers = cached("clouds", lambda: [cloud_layer(71, 9, 120, 420, 1.3, hexc("#8a7fb0"), hexc("#ffd9a0")),
                                       cloud_layer(72, 8, 420, 700, 1.0, hexc("#f0b9a0"), hexc("#fff0c8")),
                                       cloud_layer(73, 7, 720, 1000, 0.8, hexc("#fbe3c0"), hexc("#ffffff"))])
    for k, (m, edge, col, rim) in enumerate(layers):
        sh = int(t * (14 + 22 * k)) % W                           # parallax: nearer layers drift faster
        mm, ee = m[:, sh:sh + W], edge[:, sh:sh + W]
        img = img * (1 - mm[..., None] * 0.85) + col[None, None] * mm[..., None] * 0.85
        img = img + rim[None, None] * ee[..., None] * 0.35
    # soft light beams from the sun
    yv, xv = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4
    ang = np.arctan2(yv - H * 0.18, xv - W * 0.2)
    beams = (0.5 + 0.5 * np.sin(ang * 9 + t * 0.6)) ** 3 * np.exp(-np.hypot(xv - W * 0.2, yv - H * 0.18) / 1300)
    beams = cv2.resize(beams.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    beams = cv2.GaussianBlur(beams, (0, 0), 18)
    img = img + beams[..., None] * hexc("#fff0c8") * 0.12
    return np.clip(img, 0, 255)


PETALS = [(rng(900 + i).uniform(0, W), rng(900 + i).uniform(-H, H), rng(900 + i).uniform(26, 44),
           rng(900 + i).uniform(0, 6.28), rng(900 + i).uniform(60, 130)) for i in range(46)]


def draw_petals(img, t, front=False):
    for i, (x0, y0, s, ph, v) in enumerate(PETALS):
        if (i % 7 == 0) != front:          # every 7th petal is reserved for an (unused) foreground layer
            continue
        y = (y0 + v * t + H) % (H * 2) - H * 0.5
        x = x0 + 40 * math.sin(t * 1.3 + ph) + 20 * t
        ang = ph + t * 1.8
        sc = s * (1.8 if front else 1.0)
        pts = []
        for k in range(16):
            a = k / 16 * 2 * math.pi
            r = sc * (0.55 + 0.45 * math.cos(a)) ** 0.7
            pts.append((x + r * math.cos(a + ang) * 1.0, y + r * math.sin(a + ang) * 0.55))
        lay = np.zeros((H, W), np.float32)
        cv2.fillPoly(lay, [np.round(np.array(pts) * 4).astype(np.int32)], 1.0, cv2.LINE_AA, shift=2)
        if front:
            lay = cv2.GaussianBlur(lay, (0, 0), 3.5)
        col = hexc("#fbe4e0") if i % 3 else hexc("#fff6ea")
        a = (lay * (0.75 if front else 0.9))[..., None]
        img[:] = img * (1 - a) + col[None, None] * a


# ---------------------------------------------------------------- scenes
def gold_line_s1(img, t, al):
    """Gold ink line drawn on the wall, behind the girls (matte), leading the eye to the brush reveal."""
    u = ease((t - 0.25) / 0.85)
    if u <= 0:
        return img
    path = bezier([(-40, 120), (560, 40), (1200, 200), (1960, 90)], 220)
    n = max(2, int(len(path) * u))
    lay = img.copy()
    ink_line(lay, path[:n], GOLD, 5, 0.9)
    glow = cv2.GaussianBlur(np.clip(lay - img, 0, 255), (0, 0), 6)
    lined = np.clip(lay + glow * 0.6, 0, 255)
    a = al[..., None]
    return lined * (1 - a) + img * a


def render_scene(sid):
    sc = [s for s in EDL["scenes"] if s["id"] == sid][0]
    a, b = scene_range(sc)
    s0, n = src_of(sc, a), b - a
    store = np.lib.format.open_memmap(os.path.join(OUT, f"scene_{sid}.npy"), "w+", np.uint8, (n, H, W, 3))
    if sc["world"] == "v4_render":
        for i, fr in enumerate(read_v4(s0, n)):
            x = grade(fr, lift=(2, 3, 5), contrast=1.03, warm=4)
            store[i] = np.clip(x, 0, 255).astype(np.uint8)
        store.flush()
        return sid, a, b
    frames = list(read_frames(s0, s0 + n))
    alphas = read_alpha(s0, n)
    field = None
    for i in range(n):
        k = a + i
        t = (k - sc["start"]) / FPS                               # scene-local time (negative in a lead-in overlap)
        fr = frames[i]
        if sc["world"] == "cinematic_original":
            out = grade(fr, lift=(5, 3, 0), contrast=1.1, sat=0.95, warm=5) * VIG
            z = 1.0 + 0.012 * (k / 33.0)                          # a slow push, 1.2% over the scene
            M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
            out = cv2.warpAffine(out, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            al = cv2.warpAffine(alphas[i], M, (W, H), flags=cv2.INTER_LINEAR)
            out = gold_line_s1(out, t, al) + film_grain(k, 2.5)
            store[i] = np.clip(out, 0, 255).astype(np.uint8)
            continue
        al = alphas[i]
        field = outline_field((al > 0.5).astype(np.uint8), field)
        tt = max(0.0, t)
        if sc["world"] == "ink_paper":
            bg = world_ink_paper(tt, k)
        elif sc["world"] == "indigo_paint":
            bg = world_indigo(tt, k)
        elif sc["world"] == "graphic_panels":
            bg = world_panels(tt, k, sc)
        elif sc["world"] == "dream_sky":
            bg = world_sky(tt, k)
            draw_petals(bg, tt)
        else:
            raise ValueError(sc["world"])
        reveal = ease(tt / 0.4) if sc["outline"] == "ink_double" else 1.0
        bg = draw_outline(bg, sc["outline"], field[2], k, reveal)
        subj = subject(fr, sc["subject"], k)
        a3 = al[..., None]
        out = bg * (1 - a3) + subj * a3
        if sc["world"] == "dream_sky":
            out = out + cv2.GaussianBlur(np.clip(out - 200, 0, 255), (0, 0), 12) * 0.35   # gentle bloom
        out = out * (0.9 + 0.1 * VIG) + film_grain(k, 2.0)
        store[i] = np.clip(out, 0, 255).astype(np.uint8)
    store.flush()
    return sid, a, b


# ---------------------------------------------------------------- editor
def brush_mask(p, seed=5):
    """Diagonal brush-stroke wipe: everything behind the stroke's leading edge, ragged like bristles."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    s = (xx * 0.86 + yy * 0.5)
    L = W * 0.86 + H * 0.5
    g = rng(seed)
    rag = (cv2.resize(g.normal(0, 1, (H // 60, 1)).astype(np.float32), (1, H), interpolation=cv2.INTER_CUBIC) * 34
           + cv2.resize(g.normal(0, 1, (H // 12, 1)).astype(np.float32), (1, H), interpolation=cv2.INTER_CUBIC) * 7)
    edge = p * (L + 260) - 130 + rag                             # broad wobble plus fine bristle texture
    mask = np.clip((edge - s) / 6 + 0.5, 0, 1)
    band = np.clip(1 - np.abs(s - edge + 55) / 55, 0, 1) * (p > 0) * (p < 1)
    return mask, band


def assemble():
    stores = {}
    for sc in EDL["scenes"]:
        a, b = scene_range(sc)
        stores[sc["id"]] = (np.load(os.path.join(OUT, f"scene_{sc['id']}.npy"), mmap_mode="r"), a)

    def get(sid, k):
        arr, a = stores[sid]
        return arr[k - a].astype(np.float32)

    trs = {t["at"]: t for t in EDL["transitions"]}
    fade = [t for t in EDL["transitions"] if t["type"] == "fade_out"][0]
    tmp = os.path.join(OUT, "v10_video.tmp.mkv")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "14",
                            "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    log = []
    for k in range(EDL["frames"]):
        cur = [s for s in EDL["scenes"] if s["start"] <= k < s["end"]][0]
        out = get(cur["id"], k)
        for at, tr in trs.items():
            if tr["type"] == "brush_reveal" and at - tr["frames_before"] <= k < at + tr["frames_after"]:
                p = (k - (at - tr["frames_before"]) + 1) / (tr["frames_before"] + tr["frames_after"])
                m, band = brush_mask(p)
                A, B = get(tr["from"], k), get(tr["to"], k)
                out = A * (1 - m[..., None]) + B * m[..., None]
                out = out * (1 - band[..., None] * 0.9) + PAPER[None, None] * band[..., None] * 0.9
            if tr["type"] == "light_transition" and at - tr["frames_before"] <= k < at + tr["frames_after"]:
                d = (k - at + 0.5) / (tr["frames_before"] if k < at else tr["frames_after"])
                lvl = 0.55 * (1 - abs(d)) ** 1.5
                yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4
                rad = np.exp(-np.hypot(xx - W * 0.2, yy - H * 0.15) / 1400)
                rad = cv2.resize(rad.astype(np.float32), (W, H))[..., None]
                out = out + (hexc("#ffd58a")[None, None] * rad * lvl) + (255 - out) * rad * lvl * 0.35
        if k >= fade["at"]:
            out = out * (1 - (k - fade["at"] + 1) / fade["frames"])
        enc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
        log.append((k, cur["id"], src_of(cur, k)))
    enc.stdin.close()
    enc.wait()
    final_v = os.path.join(OUT, "v10_video.mkv")
    os.replace(tmp, final_v)
    with open(os.path.join(OUT, "frame_log.json"), "w") as fh:
        json.dump(log, fh)
    return final_v


def main():
    want = sys.argv[1:] or [s["id"] for s in EDL["scenes"]]
    with Pool(min(4, len(want))) as pool:
        for sid, a, b in pool.imap_unordered(render_scene, want):
            print("scene", sid, "frames", a, b, flush=True)
    if not sys.argv[1:]:
        print("assembled", assemble())


if __name__ == "__main__":
    main()
