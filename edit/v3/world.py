"""The Seed of Light: the illustrated world drawn on the wall behind the singers.

Everything here is a pure function of time t (seconds on the output timeline),
so any frame can be rendered independently and in parallel. Story timing is
authored against the measured song structure and snapped to the beat grid.

Two drawing layers:
  ink   - navy line work + watercolour washes, composited by MULTIPLY into the
          wall so it inherits the wall's light and texture
  light - things that emit light (windows, seed, pollen, lanterns, stars),
          composited ADDITIVELY with a soft glow
"""
import json
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FPS = 30
WORK = os.environ.get("EDIT_WORK", "")
HERE = os.path.dirname(__file__)

# ---------------------------------------------------------------- palette (BGR)
INK = (84, 46, 38)          # navy ink
INK_SOFT = (150, 118, 112)  # distant lavender-grey ink
CORAL = (104, 124, 226)
CORAL_WASH = (176, 186, 246)
TEAL = (138, 128, 34)
TEAL_WASH = (200, 196, 150)
LAV_WASH = (226, 206, 214)
GOLD = (80, 188, 238)
GOLD_WASH = (170, 222, 248)
EMERALD = (104, 148, 62)
EMERALD_WASH = (180, 214, 168)
CREAM = (226, 242, 252)
LIGHT_GOLD = (110, 205, 255)
LIGHT_WARM = (150, 215, 255)
LIGHT_CREAM = (215, 240, 255)


# ---------------------------------------------------------------- timing helpers
def _beats():
    try:
        with open(os.path.join(WORK, "plan_v2.json")) as fh:
            a = json.load(fh)["audio"]
        b = np.array(a["beats"])
        return b, b[a["downbeat_phase"]::4]
    except Exception:  # pragma: no cover - fallback grid at 81 bpm
        b = np.arange(0.67, 114, 60 / 80.75)
        return b, b[2::4]


BEATS, DOWN = _beats()


def snap(t, grid=None):
    g = BEATS if grid is None else grid
    return float(g[np.argmin(np.abs(g - t))])


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ramp(t, t0, t1):
    return ease((t - t0) / max(1e-6, t1 - t0))


def env(t, t0, t1, fin=0.6, fout=0.6):
    return min(ramp(t, t0, t0 + fin), 1 - ramp(t, t1 - fout, t1))


def keyed(t, keys):
    """Piecewise eased interpolation over [(t, value), ...]."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * ease((t - t0) / max(1e-6, t1 - t0))
    return keys[-1][1]


# ---------------------------------------------------------------- canvas
class Layer:
    def __init__(self):
        self.col = np.zeros((H, W, 3), np.uint8)
        self.a = np.zeros((H, W), np.uint8)

    def _poly(self, pts, color, alpha, thick, closed, fill):
        av = int(255 * clamp01(alpha))
        if av <= 0 or len(pts) < 2:
            return
        p = [np.round(np.asarray(pts, np.float64) * 4).astype(np.int32)]
        if fill:
            cv2.fillPoly(self.col, p, color, cv2.LINE_AA, shift=2)
            cv2.fillPoly(self.a, p, av, cv2.LINE_AA, shift=2)
        if thick > 0:
            cv2.polylines(self.col, p, closed, color, thick, cv2.LINE_AA, shift=2)
            cv2.polylines(self.a, p, closed, av, thick, cv2.LINE_AA, shift=2)

    def fill(self, pts, color, alpha):
        self._poly(pts, color, alpha, 0, True, True)

    def line(self, pts, color, alpha, thick=2, closed=False):
        self._poly(pts, color, alpha, thick, closed, False)

    def dot(self, c, r, color, alpha):
        av = int(255 * clamp01(alpha))
        if av <= 0:
            return
        cc = (int(round(c[0] * 4)), int(round(c[1] * 4)))
        rr = max(1, int(round(r * 4)))
        cv2.circle(self.col, cc, rr, color, -1, cv2.LINE_AA, shift=2)
        cv2.circle(self.a, cc, rr, av, -1, cv2.LINE_AA, shift=2)

    def ring(self, c, r, color, alpha, thick=2):
        av = int(255 * clamp01(alpha))
        if av <= 0:
            return
        cc = (int(round(c[0] * 4)), int(round(c[1] * 4)))
        cv2.circle(self.col, cc, max(1, int(r * 4)), color, thick, cv2.LINE_AA, shift=2)
        cv2.circle(self.a, cc, max(1, int(r * 4)), av, thick, cv2.LINE_AA, shift=2)


def arclen(p):
    d = np.linalg.norm(np.diff(p, axis=0), axis=1)
    return np.concatenate([[0], np.cumsum(d)])


def spline(P, n=24):
    """Catmull-Rom through control points."""
    P = np.asarray(P, np.float64)
    P = np.vstack([P[0] * 2 - P[1], P, P[-1] * 2 - P[-2]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for u in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    out.append(P[-2])
    return np.array(out)


def handdrawn(pts, seed, t, amp=0.9):
    """Low-frequency wobble along the normal, with a gentle 'boil' every 4 frames."""
    if len(pts) < 3:
        return pts
    s = arclen(pts)
    d = np.gradient(pts, axis=0)
    n = np.stack([-d[:, 1], d[:, 0]], 1)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    b = math.floor(t * 7.5)
    ph1 = (seed * 1.37) % 6.28 + 0.25 * math.sin(b * 1.9 + seed)
    ph2 = (seed * 2.71) % 6.28 + 0.25 * math.cos(b * 1.3 + seed)
    off = amp * (np.sin(s * 0.031 + ph1) + 0.5 * np.sin(s * 0.097 + ph2))
    return pts + n * off[:, None]


def partial(pts, prog):
    """First `prog` fraction (by length) of a polyline, with an interpolated tip."""
    if prog >= 1:
        return pts
    if prog <= 0:
        return pts[:0]
    s = arclen(pts)
    L = s[-1] * prog
    k = int(np.searchsorted(s, L))
    if k <= 0:
        return pts[:1]
    u = (L - s[k - 1]) / max(1e-9, s[k] - s[k - 1])
    tip = pts[k - 1] + (pts[k] - pts[k - 1]) * u
    return np.vstack([pts[:k], tip[None]])


def stroke(L, pts, color, alpha, w=2.0, prog=1.0, seed=0, t=0.0, amp=0.9, taper=True, closed=False):
    """Hand-drawn ink stroke: wobble, draw-on progress and tapered ends."""
    if prog <= 0 or alpha <= 0:
        return
    p = handdrawn(np.asarray(pts, np.float64), seed, t, amp) if amp > 0 else np.asarray(pts, np.float64)
    if closed:
        p = np.vstack([p, p[:1]])
    p = partial(p, prog)
    if len(p) < 2:
        return
    if not taper or w <= 1.2:
        L.line(p, color, alpha, max(1, int(round(w))))
        return
    u = np.linspace(0, 1, len(p))
    th = np.maximum(1, np.round(w * (0.45 + 0.55 * np.sin(np.pi * u) ** 0.6))).astype(int)
    start = 0
    for i in range(1, len(p) + 1):
        if i == len(p) or th[i] != th[start]:
            seg = p[max(0, start - 1):i]
            if len(seg) >= 2:
                L.line(seg, color, alpha, int(th[start]))
            start = i


def circle_pts(c, r, n=40, a0=0, a1=2 * math.pi):
    a = np.linspace(a0, a1, n)
    return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a)], 1)


# ---------------------------------------------------------------- geography
PATH_CTRL = [(-30, 478), (110, 462), (260, 448), (420, 428), (600, 392), (790, 372), (930, 390),
             (1040, 404), (1150, 392), (1320, 372), (1520, 396), (1690, 438), (1830, 456), (1960, 466)]
PATH = spline(PATH_CTRL, 30)
PATH_S = arclen(PATH)
PATH_LEN = PATH_S[-1]


def s_at_x(x):
    return float(PATH_S[np.argmin(np.abs(PATH[:, 0] - x))])


def path_pt(s):
    s = min(max(s, 0), PATH_LEN)
    k = int(np.searchsorted(PATH_S, s))
    k = min(max(k, 1), len(PATH) - 1)
    u = (s - PATH_S[k - 1]) / max(1e-9, PATH_S[k] - PATH_S[k - 1])
    return PATH[k - 1] + (PATH[k] - PATH[k - 1]) * u


S_WDOOR = s_at_x(205)
S_TREE = s_at_x(1040)
S_EDOOR = s_at_x(1745)
TREE_BASE = path_pt(S_TREE) + np.array([0, -2])
WEST_HOUSE = (150, 446)    # left wall x, ground y
EAST_HOUSE = (1690, 452)


# ---------------------------------------------------------------- key story times
class K:
    title = 0.8
    horizon = 3.4
    house_w = 5.0
    path_w = 6.3
    window_w = snap(8.0)
    a_out = window_w + 0.25
    seed_fall = snap(11.0)
    seed_land = seed_fall + 1.4
    a_kneel = 16.6
    night = 18.4
    plant = snap(28.3, DOWN)
    sprout = plant + 1.3
    pollen = snap(34.4, DOWN)
    house_e = 38.0
    window_e = snap(41.0)
    b_out = window_e + 1.0
    b_walk = snap(44.2, DOWN)
    meet = snap(54.0, DOWN)
    lanterns = 56.2
    lit0, lit1 = 60.0, 68.5
    dance2 = 70.0
    rest = 77.2
    climax = 79.73          # SLOW_A
    hug = 98.1             # the ink pair echoes the real embrace once it is visible again
    stars = 97.5
    seated = 101.07         # SLOW_B
    heart = 101.8
    walk_home = 103.4
    home = 109.6
    retrace = 110.4
    end = 113.2


# ---------------------------------------------------------------- environment pieces
_rng = np.random.default_rng(5)


def _hill(y0, amp, seed):
    g = np.random.default_rng(seed)
    xs = np.linspace(-40, W + 40, 90)
    ph = g.uniform(0, 6, 3)
    ys = y0 + amp * (0.6 * np.sin(xs * 0.0045 + ph[0]) + 0.3 * np.sin(xs * 0.011 + ph[1])
                     + 0.1 * np.sin(xs * 0.027 + ph[2]))
    return np.stack([xs, ys], 1)


HILL_FAR = _hill(232, 26, 1)
HILL_NEAR = _hill(288, 20, 2)


def _hills(seed, y0, n, hmin, hmax):
    g = np.random.default_rng(seed)
    out = []
    xs = np.sort(g.uniform(-60, W + 60, n))
    for x in xs:
        w = g.uniform(170, 330)
        h = g.uniform(hmin, hmax)
        u = np.linspace(-1, 1, 28)
        pts = np.stack([x + u * w / 2, y0 - h * (1 - u ** 2) ** 1.3 + g.normal(0, 0.6, len(u))], 1)
        out.append(pts)
    return out


HILLS_FAR = _hills(3, 262, 9, 28, 58)
HILLS_NEAR = _hills(4, 300, 8, 18, 36)
_HATCH = [(x, ) for x in np.linspace(30, W - 30, 70)]


def draw_horizon(ink, t):
    prog = ramp(t, K.horizon, K.horizon + 4.2)
    if prog <= 0:
        return
    drift = 5 * math.sin(t * 0.06)
    # hills are sketched outward from the title underline at the centre
    for layer, (hills, a, w, par) in enumerate(((HILLS_FAR, 0.30, 1.5, 0.5), (HILLS_NEAR, 0.42, 1.9, 1.0))):
        for j, hp in enumerate(hills):
            cx = hp[len(hp) // 2, 0]
            dist = abs(cx - 960) / 1100
            local = clamp01((prog - dist * 0.75) / 0.25)
            if local <= 0:
                continue
            p = hp + np.array([drift * par, 0])
            if layer == 1:
                ink.fill(p, LAV_WASH, 0.16 * local)
            stroke(ink, p if cx > 960 else p[::-1], INK_SOFT, a, w, local, 600 + 10 * layer + j, t, 0.5)
    # soft hatching under the near hills, sketched in after the lines
    hp = ramp(t, K.horizon + 2.5, K.horizon + 6.5)
    if hp > 0:
        for j, h in enumerate(HILLS_NEAR):
            for k in range(4, len(h) - 4, 3):
                if k / len(h) > hp:
                    break
                x, y = h[k]
                ink.line([(x + drift, y + 5), (x + drift - 6, y + 13)], INK_SOFT, 0.2, 1)


CLOUDS = [dict(x=330, y=120, s=1.0, v=5.0, seed=21), dict(x=1380, y=58, s=0.75, v=3.6, seed=22),
          dict(x=1640, y=175, s=0.85, v=4.4, seed=23)]


def cloud_pts(cx, cy, s, seed):
    g = np.random.default_rng(seed)
    lobes = [(-58, 6, 24), (-28, -12, 30), (8, -18, 34), (44, -6, 28), (70, 8, 20)]
    pts = []
    for lx, ly, r in lobes:
        r *= s * g.uniform(0.9, 1.1)
        pts.append(circle_pts((cx + lx * s, cy + ly * s), r, 14, math.pi * 1.0, math.pi * 2.0))
    top = np.concatenate(pts)
    base = np.array([(cx + 90 * s, cy + 22 * s), (cx - 82 * s, cy + 22 * s)])
    return np.vstack([top, base])


def _cloud_outline(s, seed):
    g = np.random.default_rng(seed)
    m = np.zeros((200, 300), np.uint8)
    for lx, ly, r in [(-58, 6, 24), (-28, -12, 30), (8, -18, 34), (44, -6, 28), (70, 8, 20)]:
        cv2.circle(m, (int(150 + lx * s), int(120 + ly * s)), int(r * s * g.uniform(0.9, 1.1)), 255, -1)
    cv2.rectangle(m, (int(150 - 82 * s), int(120)), (int(150 + 88 * s), int(120 + 20 * s)), 255, -1)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(np.float64)[::3]
    return c - np.array([150, 120])


_CLOUD_SHAPES = {c["seed"]: _cloud_outline(c["s"], c["seed"]) for c in CLOUDS}


def draw_clouds(ink, t):
    a = ramp(t, K.horizon + 2.0, K.horizon + 5.0) * (1 - 0.35 * ramp(t, K.night, K.night + 3) +
                                                      0.35 * ramp(t, K.plant - 1, K.plant + 2))
    if a <= 0:
        return
    for c in CLOUDS:
        span = W + 400
        x = (c["x"] + c["v"] * t + 200) % span - 200
        edge = clamp01(min(x + 160, W + 160 - x) / 200)
        p = _CLOUD_SHAPES[c["seed"]] + np.array([x, c["y"] + 4 * math.sin(t * 0.3 + c["seed"])])
        ink.fill(p, CREAM, 0.35 * a * edge)
        stroke(ink, p, INK_SOFT, 0.55 * a * edge, 1.8, 1.0, c["seed"], t, 0.5, closed=True)


STARS = [(float(_rng.uniform(40, W - 40)), float(_rng.uniform(25, 205)), float(_rng.uniform(0, 6))) for _ in range(24)]


def sparkle(light, x, y, r, color, a):
    light.line([(x - r, y), (x + r, y)], color, a, 1)
    light.line([(x, y - r), (x, y + r)], color, a, 1)
    light.dot((x, y), max(1.0, r * 0.28), color, a)


def draw_sky(ink, light, t):
    night = ramp(t, K.night, K.night + 3.0)
    if night <= 0:
        return
    # moon: gold crescent, drawn as two arcs and a wash
    mx, my, r = 1795, 92, 34
    mp = ramp(t, K.night + 0.5, K.night + 2.6)
    outer = circle_pts((mx, my), r, 40, math.radians(100), math.radians(380))
    inner = circle_pts((mx + 14, my - 6), r * 0.86, 40, math.radians(372), math.radians(108))
    shape = np.vstack([outer, inner])
    ink.fill(shape, GOLD_WASH, 0.55 * mp)
    stroke(ink, outer, INK, 0.75 * mp, 2.0, mp, 31, t, 0.4)
    stroke(ink, inner, INK, 0.55 * mp, 1.6, mp, 32, t, 0.4)
    light.fill(shape, LIGHT_GOLD, 0.18 * mp)
    for i, (x, y, ph) in enumerate(STARS):
        on = ramp(t, K.night + 1.0 + i * 0.32, K.night + 2.0 + i * 0.32)
        if on <= 0:
            continue
        tw = 0.55 + 0.45 * math.sin(t * (0.9 + 0.13 * (i % 5)) + ph)
        sparkle(light, x, y, 3.5 + 2.5 * tw, LIGHT_CREAM if i % 3 else LIGHT_GOLD, 0.5 * on * tw)


def draw_fireflies(light, t):
    a = env(t, K.night + 2, K.plant + 3, 2, 2) + 0.6 * env(t, K.walk_home - 1, K.end, 2, 1.5)
    if a <= 0:
        return
    for i in range(6):
        cx, cy = TREE_BASE[0] - 160 + i * 64, TREE_BASE[1] - 70
        x = cx + 40 * math.sin(t * (0.35 + 0.05 * i) + i * 2.1)
        y = cy + 28 * math.sin(t * (0.5 + 0.07 * i) + i)
        flick = 0.5 + 0.5 * math.sin(t * (2.0 + 0.3 * i) + i)
        light.dot((x, y), 2.4, LIGHT_GOLD, a * flick)


def draw_path(ink, t):
    # drawn from the west cottage eastward, ahead of the travellers
    s_end = keyed(t, [(K.path_w, 60.0), (K.path_w + 1.6, S_WDOOR + 160), (K.a_out + 1.0, S_WDOOR + 260),
                      (K.seed_land + 3.6, S_TREE + 40), (K.pollen + 0.5, S_TREE + 60),
                      (K.house_e + 1.5, S_EDOOR + 40), (K.house_e + 3.0, PATH_LEN)])
    if t < K.path_w:
        return
    k = int(np.searchsorted(PATH_S, s_end))
    p = PATH[:max(2, k)]
    stroke(ink, p, INK, 0.85, 2.4, 1.0, 41, t, 0.7)
    edge = p + np.array([0, 11])
    stroke(ink, edge[::3], INK, 0.32, 1.2, 1.0, 42, t, 0.9, taper=False)
    # grass tufts sway along the drawn path
    for i, s in enumerate(np.arange(40, s_end, 74)):
        x, y = path_pt(s)
        sw = 2.2 * math.sin(t * 1.4 + i * 0.9)
        for dx, h in ((-4, 9), (0, 13), (4, 8)):
            ink.line([(x + dx, y - 1), (x + dx * 1.6 + sw, y - h)], EMERALD, 0.55, 1)


def house(ink, light, t, left, ground, t0, roof_wash, window_on, seed, chimney_side=1):
    """Cottage sketched stroke by stroke: walls, roof, door, window, chimney smoke."""
    x0, y0 = left
    w, h = 108, 70
    walls = np.array([(x0, ground), (x0, ground - h), (x0 + w, ground - h), (x0 + w, ground)])
    roof = np.array([(x0 - 12, ground - h + 2), (x0 + w / 2, ground - h - 52), (x0 + w + 12, ground - h + 2)])
    door = np.array([(x0 + 40, ground), (x0 + 40, ground - 38), (x0 + 60, ground - 38), (x0 + 60, ground)])
    win = (x0 + 82, ground - 42)
    pw = ramp(t, t0, t0 + 0.9)
    pr = ramp(t, t0 + 0.6, t0 + 1.4)
    pd = ramp(t, t0 + 1.2, t0 + 1.8)
    if pw <= 0:
        return
    ink.fill(np.vstack([walls, roof[::-1][1:2]]), CREAM, 0.25 * pr)
    ink.fill(roof, roof_wash, 0.75 * pr)
    stroke(ink, walls, INK, 0.9, 2.4, pw, seed, t, 0.6)
    stroke(ink, roof, INK, 0.9, 2.6, pr, seed + 1, t, 0.6)
    for k in range(5):                                   # roof hatching
        u = (k + 1) / 6
        a = roof[0] + (roof[1] - roof[0]) * u
        ink.line([a, a + np.array([16, 9])], INK, 0.35 * pr, 1)
    stroke(ink, door, INK, 0.85, 2.0, pd, seed + 2, t, 0.4)
    wr = np.array([(win[0] - 10, win[1] - 10), (win[0] + 10, win[1] - 10), (win[0] + 10, win[1] + 10),
                   (win[0] - 10, win[1] + 10)])
    stroke(ink, wr, INK, 0.85, 1.8, pd, seed + 3, t, 0.3, closed=True)
    if pd >= 1:
        ink.line([(win[0], win[1] - 10), (win[0], win[1] + 10)], INK, 0.7, 1)
        ink.line([(win[0] - 10, win[1]), (win[0] + 10, win[1])], INK, 0.7, 1)
    if window_on > 0:
        ink.fill(wr, GOLD_WASH, 0.8 * window_on)
        light.fill(wr, LIGHT_WARM, 0.75 * window_on)
        light.dot(win, 22, LIGHT_WARM, 0.12 * window_on)
    # chimney + smoke curl
    cx = x0 + (w * 0.75 if chimney_side > 0 else w * 0.25)
    cy = ground - h - 26
    ch = np.array([(cx - 7, cy + 14), (cx - 7, cy - 8), (cx + 7, cy - 8), (cx + 7, cy + 18)])
    stroke(ink, ch, INK, 0.85, 1.8, pr, seed + 4, t, 0.3)
    if pr >= 1 and window_on > 0:
        for j in range(3):
            ph = (t * 0.25 + j / 3) % 1
            sx = cx + 10 * math.sin(ph * 6 + j) + ph * 18
            sy = cy - 12 - ph * 70
            ink.ring((sx, sy), 4 + ph * 8, INK_SOFT, 0.35 * window_on * (1 - ph), 1)
    return np.array([x0 + 50, ground])


# ---------------------------------------------------------------- the tree
def _branches():
    g = np.random.default_rng(77)
    out = []

    def grow(p, ang, length, depth, born, parent):
        idx = len(out)
        out.append(dict(p=p, ang=ang, len=length, depth=depth, born=born, parent=parent))
        if depth >= 6:
            return
        if depth == 0:
            kids = [(-0.08, 0.85)]                       # trunk continues, leaning slightly
        else:
            n = 2 if depth < 3 else int(g.integers(2, 4))
            kids = [((k - (n - 1) / 2) * g.uniform(0.42, 0.7) + g.normal(0, 0.12), g.uniform(0.6, 0.8))
                    for k in range(n)]
        for spread, lf in kids:
            grow(None, ang + spread, length * lf, depth + 1, born + g.uniform(0.07, 0.12), idx)
        if depth in (1, 2) and g.random() < 0.7:          # a side shoot for asymmetry
            grow(None, ang + g.choice([-1, 1]) * g.uniform(0.9, 1.2), length * 0.5, depth + 2,
                 born + 0.15, idx)

    grow(None, -math.pi / 2 + 0.05, 70, 0, 0.0, -1)
    return out


BRANCHES = _branches()
_TIP_IDX = [i for i, b in enumerate(BRANCHES) if b["depth"] >= 5]
_BLOSSOM = [(i, float(np.random.default_rng(i).uniform(0, 1))) for i in _TIP_IDX]


def tree_growth(t):
    steps = [(K.sprout - 0.3, 0.0), (K.sprout + 1.2, 0.12)]
    for k, d in enumerate([d for d in DOWN if K.sprout + 1.4 < d < K.pollen + 3.5]):
        steps.append((d, 0.12 + 0.07 * (k + 1)))
        steps.append((d + 0.6, 0.12 + 0.07 * (k + 1)))
    steps += [(K.pollen + 4.0, 0.45), (K.b_walk, 0.5), (K.meet, 0.7), (K.lit1, 0.8), (K.rest, 0.84),
              (K.climax + 2.0, 0.86), (K.climax + 7.0, 1.0)]
    steps.sort()
    return keyed(t, steps)


def tree_bloom(t):
    return keyed(t, [(K.lit0, 0.0), (K.rest, 0.3), (K.climax + 1.0, 0.32), (K.climax + 8.0, 1.0)])


def tree_geometry(t, g):
    pts = {}
    tips = []
    segs = []
    for i, b in enumerate(BRANCHES):
        if g <= b["born"]:
            continue
        f = clamp01((g - b["born"]) / 0.22)
        sway = 0.022 * b["depth"] * math.sin(t * 1.05 + b["depth"] * 0.8 + i * 0.3)
        start = TREE_BASE if b["parent"] < 0 else pts.get(b["parent"])
        if start is None:
            continue
        ang = b["ang"] + sway
        scale = 0.55 + 0.45 * clamp01(g * 1.3)
        end = start + np.array([math.cos(ang), math.sin(ang)]) * b["len"] * f * scale
        pts[i] = end
        segs.append((start, end, b["depth"], f))
        if b["depth"] >= 5:
            tips.append((i, end, f))
    return segs, tips


def draw_tree(ink, light, t):
    g = tree_growth(t)
    seed_glow = env(t, K.seed_land, K.sprout + 3.0, 0.2, 2.5)
    if seed_glow > 0:
        breathe = 0.75 + 0.25 * math.sin(t * 1.6)
        light.dot(TREE_BASE + np.array([0, -6]), 5, LIGHT_GOLD, 0.95 * seed_glow)
        light.dot(TREE_BASE + np.array([0, -6]), 16, LIGHT_GOLD, 0.22 * seed_glow * breathe)
    if g <= 0:
        return None
    segs, tips = tree_geometry(t, g)
    for k, (a, b, depth, f) in enumerate(segs):
        mid = (a + b) / 2 + np.array([5 * math.sin(k * 1.7), 2 * math.cos(k)])
        pts = spline([a, mid, b], 6)
        stroke(ink, pts, INK, 0.92, max(1.1, 6.0 - depth * 1.0), 1.0, 300 + k, t, 0.6)
    # leaves (emerald) along the outer twigs
    leaf_a = ramp(g, 0.35, 0.6)
    if leaf_a > 0:
        for i, p, f in tips:
            for j in range(2):
                ang = BRANCHES[i]["ang"] + (j - 0.5) * 1.4 + 0.15 * math.sin(t * 1.3 + i)
                c = p + np.array([math.cos(ang), math.sin(ang)]) * 7
                leaf = np.array([c + np.array([math.cos(ang), math.sin(ang)]) * 7 * f,
                                 c + np.array([-math.sin(ang), math.cos(ang)]) * 3.2 * f,
                                 c - np.array([math.cos(ang), math.sin(ang)]) * 7 * f,
                                 c - np.array([-math.sin(ang), math.cos(ang)]) * 3.2 * f])
                ink.fill(leaf, EMERALD_WASH, 0.85 * leaf_a)
                ink.line(np.vstack([leaf, leaf[:1]]), EMERALD, 0.7 * leaf_a, 1)
    # blossoms open in waves (buds first, full bloom at the climax)
    b = tree_bloom(t)
    if b > 0:
        for i, p, f in tips:
            phase = dict(_BLOSSOM)[i]
            o = clamp01((b - phase * 0.6) / 0.4)
            if o <= 0:
                continue
            r = 2.2 + 3.6 * o
            col_w = CORAL_WASH if i % 3 else GOLD_WASH
            for k in range(5):
                a = k * 2 * math.pi / 5 + i * 0.7 + 0.15 * math.sin(t + i)
                c = p + np.array([math.cos(a), math.sin(a)]) * r * 0.75
                ink.fill(circle_pts(c, r * 0.42, 8), col_w, 0.95 * o)
            ink.dot(p, 1.2 + 0.6 * o, CORAL, 0.8 * o)
            light.dot(p, 1.2 + 0.8 * o, LIGHT_GOLD, 0.5 * o)
    # warm glow in the crown, strongest at the climax
    glow = 0.25 * ramp(t, K.sprout, K.sprout + 4) * (1 - ramp(t, K.pollen + 5, K.pollen + 9)) \
        + 0.5 * env(t, K.climax, K.seated + 1.0, 4, 3)
    if glow > 0 and tips:
        crown = np.mean([p for _, p, _ in tips], axis=0)
        light.dot(crown, 70, LIGHT_WARM, 0.035 * glow)
    return tips


# ---------------------------------------------------------------- flowers
FLOWERS = [dict(x=x, side=side, col=col) for x, side, col in
           [(95, "w", CORAL_WASH), (300, "w", LAV_WASH), (395, "w", GOLD_WASH), (880, "w", CORAL_WASH),
            (965, "w", LAV_WASH), (1120, "e", GOLD_WASH), (1205, "e", CORAL_WASH), (1290, "e", LAV_WASH),
            (1610, "e", CORAL_WASH), (1655, "e", GOLD_WASH), (1855, "e", LAV_WASH)]]
for _f in FLOWERS:
    _f["s"] = s_at_x(_f["x"])


def pollen_front(t):
    return S_TREE + 175 * max(0.0, t - K.pollen - 0.4)


def draw_flower(ink, light, f, t, bloom):
    x, y = path_pt(f["s"])
    h = 18 + 10 * ((int(f["x"]) // 7) % 3)
    sway = 3 * math.sin(t * 1.2 + f["x"] * 0.01)
    grow = clamp01(bloom * 2)
    top = np.array([x + sway * grow, y - h * grow])
    stem = spline([(x, y), (x + sway * 0.4, y - h * 0.5 * grow), top], 6)
    stroke(ink, stem, EMERALD, 0.85, 1.6, 1.0, int(f["x"]), t, 0.3, taper=False)
    o = clamp01(bloom * 2 - 1)
    if o > 0:
        for k in range(5):
            a = k * 2 * math.pi / 5 - math.pi / 2 + 0.1 * math.sin(t + k)
            c = top + np.array([math.cos(a), math.sin(a)]) * 5.5 * o
            ink.fill(circle_pts(c, 4.2 * o, 10), f["col"], 0.95)
            ink.ring(c, 4.2 * o, INK, 0.45, 1)
        ink.dot(top, 2.6 * o, GOLD, 0.95)
        light.dot(top, 1.6, LIGHT_GOLD, 0.5 * o)


# ---------------------------------------------------------------- lanterns
def _catenary(a, b, sag, n=40):
    u = np.linspace(0, 1, n)
    p = np.outer(1 - u, a) + np.outer(u, b)
    p[:, 1] += sag * 4 * u * (1 - u)
    return p


STRING_A = _catenary(np.array([206.0, 330.0]), np.array([1000.0, 236.0]), 70)
STRING_B = _catenary(np.array([1080.0, 236.0]), np.array([1744.0, 336.0]), 66)
STRING = np.vstack([STRING_A, STRING_B])
_SA = arclen(STRING_A)
_SB = arclen(STRING_B)


def _lantern_slots():
    out = []
    for p, s in ((STRING_A, _SA), (STRING_B, _SB)):
        for u in np.linspace(0.12, 0.88, 7):
            k = int(np.searchsorted(s, s[-1] * u))
            out.append(p[min(k, len(p) - 1)])
    return out


LANTERNS = _lantern_slots()
# heart-shaped constellation the lanterns rise to
_th = np.linspace(0.15, 2 * math.pi - 0.15, len(LANTERNS), endpoint=True)
HEART_PTS = [(1040 + 9.2 * 16 * math.sin(a) ** 3,
              108 - 9.2 * (13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) * 0.62)
             for a in _th]
_order = np.argsort([p[0] for p in LANTERNS])
_horder = np.argsort([p[0] for p in HEART_PTS])
TARGET = {int(_order[i]): HEART_PTS[int(_horder[i])] for i in range(len(LANTERNS))}
LIT_T = [snap(K.lit0 + (K.lit1 - K.lit0) * i / (len(LANTERNS) - 1)) for i in range(len(LANTERNS))]


def lantern_shape(c, s=1.0):
    x, y = c
    body = np.array([(x - 7 * s, y), (x - 8 * s, y + 8 * s), (x - 6 * s, y + 16 * s), (x + 6 * s, y + 16 * s),
                     (x + 8 * s, y + 8 * s), (x + 7 * s, y)])
    return body


def draw_lanterns(ink, light, t):
    sp = ramp(t, K.lanterns, K.lanterns + 3.4)
    if sp <= 0:
        return
    string_a = 0.75 * (1 - ramp(t, K.climax + 1.0, K.climax + 5.0))
    if string_a > 0:
        stroke(ink, STRING_A, INK, string_a, 1.4, sp, 501, t, 0.4, taper=False)
        stroke(ink, STRING_B, INK, string_a, 1.4, sp, 502, t, 0.4, taper=False)
    # light pulses race along the string on each downbeat of the strong section
    for d in DOWN:
        if K.dance2 <= d <= K.rest:
            u = (t - d) / 0.9
            if 0 <= u <= 1:
                for p, path in ((STRING_A, None), (STRING_B, None)):
                    k = int(u * (len(p) - 1))
                    light.dot(p[k], 3.2, LIGHT_GOLD, 0.9 * (1 - u * 0.5))
                    light.dot(p[k], 10, LIGHT_GOLD, 0.15)
    for i, base in enumerate(LANTERNS):
        appear = ramp(t, K.lanterns + 0.6 + i * 0.18, K.lanterns + 1.0 + i * 0.18)
        if appear <= 0:
            continue
        lit = ramp(t, LIT_T[i], LIT_T[i] + 0.35)
        rel = K.climax + 0.6 + 0.62 * ((i * 5) % len(LANTERNS))
        rise = ease((t - rel) / 9.0) if t > rel else 0.0
        tx, ty = TARGET[i]
        x = base[0] + (tx - base[0]) * rise + 14 * math.sin(t * 0.7 + i) * rise * (1 - rise) * 4
        y = base[1] + 3 + (ty - base[1]) * rise
        star = ramp(t, K.stars + 0.15 * i, K.stars + 1.5 + 0.15 * i)
        la = appear * (1 - star)
        bob = 1.5 * math.sin(t * 1.3 + i) * (1 - rise)
        if la > 0:
            body = lantern_shape((x, y + bob), 1.0 - 0.35 * rise)
            ink.fill(body, CORAL_WASH if i % 2 else GOLD_WASH, 0.85 * la)
            ink.line(np.vstack([body, body[:1]]), INK, 0.8 * la, 1)
            ink.line([(x, y + bob - 4), (x, y + bob)], INK, 0.7 * la, 1)
            flick = 0.85 + 0.15 * math.sin(t * 7 + i * 2)
            if lit > 0:
                light.fill(body, LIGHT_WARM, 0.55 * lit * la * flick)
                light.dot((x, y + bob + 8), 18, LIGHT_GOLD, 0.10 * lit * la)
        if star > 0:
            tw = 0.6 + 0.4 * math.sin(t * 1.4 + i)
            sparkle(light, tx, ty, 4 + 3 * tw, LIGHT_CREAM, 0.85 * star)
    # the constellation: a fine line joins the stars into a heart
    cp = ramp(t, K.heart, K.heart + 4.0)
    if cp > 0:
        th = np.linspace(0, 2 * math.pi, 140)
        pts = np.stack([1040 + 9.2 * 16 * np.sin(th) ** 3,
                        108 - 9.2 * 0.62 * (13 * np.cos(th) - 5 * np.cos(2 * th) - 2 * np.cos(3 * th) - np.cos(4 * th))], 1)
        stroke(ink, pts, INK_SOFT, 0.6, 1.4, cp, 777, t, 0.3, taper=False)
        stroke(light, pts, LIGHT_CREAM, 0.30, 1.2, cp, 778, t, 0.3, taper=False)


# ---------------------------------------------------------------- pollen, seed, petals, wash
def draw_seed_fall(light, t):
    t0, t1 = K.seed_fall, K.seed_land
    if not (t0 <= t <= t1 + 1.2):
        return
    a = np.array([1880.0, -30.0])
    c = np.array([1460.0, 40.0])
    b = TREE_BASE + np.array([0, -6])

    def at(u):
        return (1 - u) ** 2 * a + 2 * (1 - u) * u * c + u * u * b
    if t <= t1:
        u = ease_out((t - t0) / (t1 - t0)) ** 1.2
        for j in range(14):                       # motion-blurred trail
            uj = max(0.0, u - j * 0.018)
            light.dot(at(uj), max(1.0, 4.2 - j * 0.28), LIGHT_GOLD, 0.95 * (1 - j / 14))
    else:
        u = (t - t1) / 1.2                         # landing ripple
        light.ring(b, 6 + 70 * ease_out(u), LIGHT_GOLD, 0.6 * (1 - u), 2)
        light.ring(b, 3 + 38 * ease_out(u), LIGHT_GOLD, 0.4 * (1 - u), 1)


_POLLEN = [(float(_rng.uniform(0, 2.6)), float(_rng.uniform(150, 210)), float(_rng.uniform(-60, -10)),
            float(_rng.uniform(0, 6))) for _ in range(34)]


def draw_pollen(light, t):
    for k, (dt, v, yo, ph) in enumerate(_POLLEN):
        t0 = K.pollen + dt
        if t < t0:
            continue
        s = S_TREE + v * (t - t0)
        if s > S_EDOOR + 40:
            continue
        x, y = path_pt(s)
        y += yo - 40 * math.exp(-(t - t0) * 1.5) + 8 * math.sin(t * 2 + ph)
        fade = min(1.0, (t - t0) * 2) * clamp01((S_EDOOR + 40 - s) / 120)
        for j in range(4):
            light.dot((x - j * 5, y + j * 0.6), 2.4 - j * 0.45, LIGHT_GOLD, 0.8 * fade * (1 - j / 4))


_PETALS = [(float(_rng.uniform(0, 9)), float(_rng.uniform(-1, 1)), float(_rng.uniform(0.4, 1.0)),
            float(_rng.uniform(0, 6))) for _ in range(30)]


def draw_petals(ink, t, tips):
    if not tips or t < K.climax + 6 or t > K.seated + 4:
        return
    crown = np.mean([p for _, p, _ in tips], axis=0)
    for dt, dirx, sp, ph in _PETALS:
        t0 = K.climax + 6 + dt
        u = t - t0
        if u < 0 or u > 7:
            continue
        x = crown[0] + dirx * 260 * sp * u ** 0.8 + 18 * math.sin(u * 1.7 + ph)
        y = crown[1] + 40 * u + 6 * u * u
        a = clamp01(u * 2) * clamp01((7 - u) / 1.5)
        rot = u * 2.2 + ph
        e = np.array([(x + 6 * math.cos(rot), y + 6 * math.sin(rot)),
                      (x - 3 * math.sin(rot), y + 3 * math.cos(rot)),
                      (x - 6 * math.cos(rot), y - 6 * math.sin(rot)),
                      (x + 3 * math.sin(rot), y - 3 * math.cos(rot))])
        ink.fill(e, CORAL_WASH, 0.9 * a)
        ink.line(np.vstack([e, e[:1]]), CORAL, 0.6 * a, 1)


_NOISE = cv2.GaussianBlur(np.random.default_rng(9).random((H // 8, W // 8)).astype(np.float32), (0, 0), 3)
_NOISE = (_NOISE - _NOISE.min()) / (_NOISE.max() - _NOISE.min())
_YY, _XX = np.mgrid[0:H // 8, 0:W // 8].astype(np.float32)


def climax_wash(t):
    """Watercolour bloom spreading from the tree at the climax (multiply wash)."""
    a = 0.16 * ramp(t, K.climax + 1.5, K.climax + 8) * (1 - 0.6 * ramp(t, K.seated - 1, K.seated + 2))
    if a <= 0:
        return None
    r = 80 + 900 * ease_out((t - K.climax - 1.5) / 9.0)
    xf = world_xform(t)
    if xf is None:
        cx, cy = TREE_BASE[0] / 8, (TREE_BASE[1] - 140) / 8
    else:
        c = (np.array([TREE_BASE[0], TREE_BASE[1] - 140]) - xf[0]) * xf[2] + xf[1]
        cx, cy = c[0] / 8, c[1] / 8
    d = np.sqrt((_XX - cx) ** 2 + ((_YY - cy) * 1.25) ** 2) * 8
    edge = np.clip((r - d) / 160 + (_NOISE - 0.5) * 1.2, 0, 1)
    tint = np.zeros((H // 8, W // 8, 3), np.float32)
    mix = np.clip((d / max(r, 1)), 0, 1)[..., None]
    tint[:] = np.array(GOLD_WASH, np.float32) * (1 - mix) + np.array(CORAL_WASH, np.float32) * mix
    return cv2.resize(edge * a, (W, H)), cv2.resize(tint, (W, H))


# ---------------------------------------------------------------- characters
CHAR_H = 64


def draw_character(ink, x, y, pose, scarf, scarf_wash, seed, t, partner_dx=0.0):
    """A small ink figure with a scarf. pose keys: walk (phase or None), d (facing),
    crouch, arms ('swing'|'up'|'dig'|'wave'|'hug'|'hold'|'rest'|'point'), jump,
    look (head tilt up 0..1), alpha, happy, sit."""
    a = pose.get("alpha", 1.0)
    if a <= 0:
        return
    d = pose.get("d", 1)
    Hh = CHAR_H
    crouch = pose.get("crouch", 0.0)
    sit = pose.get("sit", 0.0)
    y = y - pose.get("jump", 0.0)
    ph = pose.get("walk")
    bob = 1.6 * abs(math.sin(ph)) if ph is not None else 0.8 * math.sin(t * 2.2 + seed)
    hip = np.array([x, y - Hh * (0.42 - 0.16 * crouch - 0.2 * sit) - bob])
    neck = hip + np.array([d * (3 * crouch + (2 if ph is not None else 0)), -Hh * 0.30])
    head = neck + np.array([d * 2, -Hh * 0.15]) + np.array([0, -1.5 * pose.get("look", 0)])
    # legs
    legs = []
    for side in (-1, 1):
        if sit > 0:
            knee = hip + np.array([d * 12, -1])
            foot = knee + np.array([d * 4, 13])
        elif ph is not None:
            sw = 0.5 * math.sin(ph + (0 if side > 0 else math.pi))
            knee = hip + np.array([math.sin(sw) * 13 * d, 13 - 2 * crouch])
            lift = max(0.0, math.sin(ph + (0 if side > 0 else math.pi))) * 4
            foot = np.array([hip[0] + math.sin(sw * 1.3) * 20 * d, y - lift])
        else:
            spread = side * (4 + 6 * crouch)
            knee = hip + np.array([spread + d * 6 * crouch, 12 - 4 * crouch])
            foot = np.array([x + spread * 1.2, y])
        legs.append(np.array([hip, knee, foot]))
    for lg in legs:
        stroke(ink, lg, INK, a, 2.2, 1.0, seed, t, 0.15, taper=False)
    # body: soft teardrop
    body = np.array([hip + np.array([-7, 2]), neck + np.array([-5, 2]), neck + np.array([5, 2]),
                     hip + np.array([7, 2])])
    body = spline(np.vstack([body, body[:1]]), 6)
    ink.fill(body, CREAM, 0.95 * a)
    stroke(ink, body, INK, a, 2.0, 1.0, seed + 1, t, 0.25, taper=False)
    # arms
    sh = neck + np.array([0, 5])
    arms = pose.get("arms", "swing")
    for side in (-1, 1):
        if arms == "up":
            u = pose.get("arms_up", 1.0)
            hand = sh + np.array([side * (8 + 6 * u), -6 - 20 * u])
        elif arms == "wave" and side == d:
            hand = sh + np.array([d * 14, -22 + 4 * math.sin(t * 10)])
        elif arms == "point" and side == d:
            hand = sh + np.array([d * 22, -6])
        elif arms == "dig":
            hand = sh + np.array([d * 12, 14 + 4 * math.sin(t * 9 + side)])
        elif arms == "hug":
            hand = sh + np.array([d * (10 + side * 2), 4 - side * 3])
        elif arms == "hold" and side == d:
            hand = sh + np.array([np.clip(partner_dx * 0.5, -18, 18), 14])
        elif arms == "dance":
            u = 0.5 + 0.5 * math.sin(t * 5.4 + side * 1.6)
            hand = sh + np.array([side * (12 + 4 * u), -18 * u + 8 * (1 - u)])
        elif arms == "rest" or sit > 0:
            hand = sh + np.array([side * 6 + d * 4, 16])
        else:
            sw = 0.45 * math.sin(ph + (math.pi if side > 0 else 0)) if ph is not None else 0.0
            hand = sh + np.array([side * 3 + math.sin(sw) * 12 * d, 17])
        elbow = (sh + hand) / 2 + np.array([side * 4, 2])
        stroke(ink, np.array([sh, elbow, hand]), INK, a, 2.0, 1.0, seed + 5 + side, t, 0.1, taper=False)
    # head
    hc = head
    r = 9.5
    ink.fill(circle_pts(hc, r, 24), CREAM, a)
    stroke(ink, circle_pts(hc, r, 30), INK, a, 2.0, 1.0, seed + 2, t, 0.2, closed=True, taper=False)
    look = pose.get("look", 0)
    ex = hc + np.array([d * 3.4, -1.0 - 2.0 * look])
    if pose.get("happy", 0) > 0.5:
        ink.line([(ex[0] - 2, ex[1] + 0.5), (ex[0], ex[1] - 1.5), (ex[0] + 2, ex[1] + 0.5)], INK, a, 1)
    else:
        ink.dot(ex, 1.4, INK, a)
    ink.dot(hc + np.array([d * 6.5, 3.5]), 1.6, CORAL_WASH, 0.7 * a)   # cheek
    # hair: the Wanderer has a curl, the Friend a little bun
    if scarf == CORAL:
        curl = circle_pts(hc + np.array([-d * 1, -r - 2]), 3.2, 12, 0, 1.6 * math.pi)
        stroke(ink, curl, INK, a, 1.6, 1.0, seed + 3, t, 0.0, taper=False)
    else:
        ink.dot(hc + np.array([-d * 6, -r + 1]), 4.2, INK, a)
    # scarf with a trailing tail (follow-through)
    knot = neck + np.array([0, 2])
    ink.line([knot + np.array([-6, -1]), knot + np.array([6, -1])], scarf, a, 4)
    speed = 1.0 if ph is not None else 0.35
    tail = [knot]
    for k in range(1, 5):
        fl = math.sin(t * 6 - k * 0.9 + seed) * (1.5 + k) * speed
        tail.append(knot + np.array([-d * k * 5.5 * (0.5 + 0.5 * speed), k * 2.6 + fl]))
    stroke(ink, np.array(tail), scarf, a, 3.2, 1.0, seed + 4, t, 0.0)


def _walk(t, t0, t1, s0, s1):
    u = clamp01((t - t0) / max(1e-6, t1 - t0))
    # ease in/out on the walk so starts and stops have weight
    uu = u * u * (3 - 2 * u) * 0.35 + u * 0.65
    s = s0 + (s1 - s0) * uu
    return s


def wanderer(t):
    """Returns (s, pose) for the Wanderer (coral scarf)."""
    d_tree = S_TREE - 34
    if t < K.a_out:
        return None
    if t < K.a_out + 1.5:                                  # steps out and stretches
        u = (t - K.a_out) / 1.5
        return S_WDOOR, dict(d=1, arms="up", arms_up=math.sin(u * math.pi), alpha=ramp(t, K.a_out, K.a_out + 0.4),
                             happy=1)
    if t < K.seed_fall:
        s = _walk(t, K.a_out + 1.5, K.seed_fall, S_WDOOR, S_WDOOR + 130)
        return s, dict(d=1, walk=(s - S_WDOOR) / 7.0)
    if t < K.seed_land + 0.4:                              # stops, looks up at the falling light
        return S_WDOOR + 130, dict(d=1, look=ramp(t, K.seed_fall, K.seed_fall + 0.5), arms="point")
    if t < K.a_kneel:
        s = _walk(t, K.seed_land + 0.4, K.a_kneel, S_WDOOR + 130, d_tree)
        return s, dict(d=1, walk=(s - S_WDOOR) / 7.0)
    if t < K.night:
        return d_tree, dict(d=1, crouch=ramp(t, K.a_kneel, K.a_kneel + 0.5), look=0)
    if t < K.plant:                                        # night: sits by the seed, looks at the moon
        return d_tree, dict(d=1, sit=ramp(t, K.night, K.night + 0.8),
                            look=env(t, K.night + 4, K.plant - 1, 1.2, 1.2), arms="rest")
    if t < K.sprout:
        return d_tree + 8, dict(d=1, crouch=0.8, arms="dig")
    if t < K.sprout + 0.9:                                 # hops back in surprise
        u = (t - K.sprout) / 0.9
        s = d_tree + 8 - 18 * ease_out(u)
        return s, dict(d=1, jump=12 * math.sin(u * math.pi), arms="up", arms_up=0.6, happy=1)
    if t < K.meet - 0.6:
        pose = dict(d=1, look=0.5 * env(t, K.sprout + 1, K.pollen, 1, 1))
        if K.pollen <= t < K.pollen + 3.5:
            pose.update(arms="point", d=1, happy=1)
        elif K.b_walk <= t:
            pose.update(arms="dig" if (t - K.b_walk) % 4 < 1.6 else "swing")
        return d_tree - 10, pose
    return together(t, "a")


def friend(t):
    if t < K.b_out:
        return None
    d_tree = S_TREE + 34
    if t < K.b_walk:
        a = ramp(t, K.b_out, K.b_out + 0.4)
        arms = "wave" if t > K.b_out + 1.2 else "swing"
        return S_EDOOR, dict(d=-1, alpha=a, arms=arms, look=0.4 * env(t, K.b_out, K.b_walk, 0.4, 0.4), happy=1)
    if t < K.meet - 0.6:
        s = _walk(t, K.b_walk, K.meet - 0.6, S_EDOOR, d_tree)
        return s, dict(d=-1, walk=(S_EDOOR - s) / 7.0)
    return together(t, "b")


def together(t, who):
    """Shared choreography once they have met."""
    side = -1 if who == "a" else 1
    base = S_TREE + side * 34
    face = -side
    if t < K.meet + 0.9:                                   # greeting jump with anticipation
        u = (t - (K.meet - 0.6)) / 1.5
        crouch = 0.5 * math.sin(clamp01(u / 0.3) * math.pi) if u < 0.3 else 0.0
        jump = 16 * math.sin(clamp01((u - 0.3) / 0.7) * math.pi) if u >= 0.3 else 0.0
        return base, dict(d=face, crouch=crouch, jump=jump, arms="up", arms_up=0.8, happy=1)
    if t < K.lanterns + 3.5:
        return base, dict(d=face, happy=1, arms="point" if t > K.lanterns else "swing")
    if t < K.rest:                                         # dance: gentle, then livelier
        e = 0.5 if t < K.dance2 else 1.0
        bounce = abs(math.sin((t - K.lanterns) * math.pi * 80.75 / 60)) * 5 * e
        sway = math.sin((t - K.lanterns) * math.pi * 80.75 / 120) * 6 * e
        return base + sway * side, dict(d=face if (int((t - K.lanterns) / 2.97) % 2 == 0) else -face,
                                        jump=bounce, arms="dance", happy=1)
    if t < K.climax:                                       # rest under the tree, look up
        return base, dict(d=face, sit=ramp(t, K.rest, K.rest + 0.8), look=1.0, arms="rest")
    if t < K.hug - 1.0:                                    # stand and watch the lanterns rise
        return base, dict(d=face, look=1.0, arms="swing", happy=1)
    if t < K.hug + 2.6:                                    # the hug, echoing the real one
        s = base - side * 22 * ramp(t, K.hug - 1.0, K.hug)
        return s, dict(d=face, arms="hug" if t > K.hug - 0.3 else "swing", happy=1, walk=None)
    if t < K.walk_home:
        return base - side * 12, dict(d=face, look=0.8, arms="hold", happy=1)
    if t < K.home:                                         # walk home together, hand in hand
        s0 = base - side * 12
        s1 = S_WDOOR + (28 if who == "b" else 4)
        s = _walk(t, K.walk_home, K.home, s0, s1)
        return s, dict(d=-1, walk=(s0 - s) / 7.0, arms="hold", happy=1)
    a = 1 - ramp(t, K.home, K.home + 0.8)                  # step inside
    return S_WDOOR + (14 if who == "b" else 0), dict(d=-1, alpha=a, arms="hold")


class _Affine:
    """Proxy layer: p' = (p - src) * k + dst. Used for the climax close-up."""

    def __init__(self, L, src, dst, k):
        self.L, self.s, self.d, self.k = L, np.asarray(src, np.float64), np.asarray(dst, np.float64), k
        self.col, self.a = L.col, L.a

    def _t(self, pts):
        return (np.asarray(pts, np.float64) - self.s) * self.k + self.d

    def fill(self, pts, color, alpha):
        self.L.fill(self._t(pts), color, alpha)

    def line(self, pts, color, alpha, thick=2, closed=False):
        self.L.line(self._t(pts), color, alpha, max(1, int(round(thick * self.k))), closed)

    def dot(self, c, r, color, alpha):
        self.L.dot(self._t([c])[0], r * self.k, color, alpha)

    def ring(self, c, r, color, alpha, thick=2):
        self.L.ring(self._t([c])[0], r * self.k, color, alpha, max(1, int(round(thick * self.k))))


CLOSE_K = 1.45
CLOSE_DST = (1180.0, 560.0)


def world_xform(t):
    """Seated take: the world as drawn. Standing scene (79.7-101.1 s): a closer
    framing of the world centred on the tree, cut together with the footage."""
    if K.climax <= t < K.seated:
        return TREE_BASE, np.array(CLOSE_DST), CLOSE_K
    return None


class _Scaled:
    """Draws onto a layer with all geometry scaled about an anchor point."""

    def __init__(self, L, anchor, k):
        self.L, self.o, self.k = L, np.asarray(anchor, np.float64), k

    def _t(self, pts):
        return (np.asarray(pts, np.float64) - self.o) * self.k + self.o

    def fill(self, pts, color, alpha):
        self.L.fill(self._t(pts), color, alpha)

    def line(self, pts, color, alpha, thick=2, closed=False):
        self.L.line(self._t(pts), color, alpha, max(1, int(round(thick * self.k))), closed)

    def dot(self, c, r, color, alpha):
        self.L.dot(self._t([c])[0], r * self.k, color, alpha)

    def ring(self, c, r, color, alpha, thick=2):
        self.L.ring(self._t([c])[0], r * self.k, color, alpha, thick)


def draw_characters(ink, t):
    A = wanderer(t)
    B = friend(t)
    xa = path_pt(A[0])[0] if A else None
    xb = path_pt(B[0])[0] if B else None
    for st, scarf, wash, seed, other in ((A, CORAL, CORAL_WASH, 101, xb), (B, TEAL, TEAL_WASH, 202, xa)):
        if st is None:
            continue
        s, pose = st
        x, y = path_pt(s)
        draw_character(_Scaled(ink, (x, y - 1), 1.22), x, y - 1, pose, scarf, wash, seed, t,
                       (other - x) / 1.22 if other is not None else 0.0)


# ---------------------------------------------------------------- title
_FONT = os.path.join(HERE, "..", "assets", "Caveat.ttf")
_title_cache = {}


def _title_sprite(text, size):
    if text not in _title_cache:
        font = ImageFont.truetype(_FONT, size)
        font.set_variation_by_axes([520])
        bb = font.getbbox(text)
        w, h = bb[2] - bb[0] + 40, bb[3] - bb[1] + 40
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).text((20 - bb[0], 20 - bb[1]), text, font=font, fill=255)
        _title_cache[text] = np.array(im)
    return _title_cache[text]


def draw_title(ink, t, cx=980, cy=128):
    if t < K.title or t > K.horizon + 4:
        return
    spr = _title_sprite("two voices", 68)
    h, w = spr.shape
    rev = ramp(t, K.title, K.title + 2.0)
    fade = 1 - ramp(t, K.horizon + 1.5, K.horizon + 3.6)
    cut = int(w * rev)
    a = spr.astype(np.float32) / 255 * fade * 0.92
    a[:, cut:] = 0
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    sub = ink.a[y0:y0 + h, x0:x0 + w]
    keep = a * 255 > sub
    ink.col[y0:y0 + h, x0:x0 + w][keep] = INK
    ink.a[y0:y0 + h, x0:x0 + w] = np.maximum(sub, (a * 255).astype(np.uint8))
    # the underline becomes the horizon
    up = ramp(t, K.title + 1.8, K.horizon + 0.2)
    if up > 0:
        y = cy + h / 2 - 6
        ul = np.array([(cx - 118, y + 2), (cx, y - 2), (cx + 118, y + 3)])
        stroke(ink, spline(ul, 10), INK, 0.85 * fade, 2.2, up, 901, t, 0.4)


# ---------------------------------------------------------------- compose a frame of the world
def render_world(t):
    ink0, light0 = Layer(), Layer()
    xf = world_xform(t)
    ink, light = (ink0, light0) if xf is None else (_Affine(ink0, *xf), _Affine(light0, *xf))
    draw_sky(ink, light, t)
    draw_clouds(ink, t)
    draw_horizon(ink, t)
    draw_title(ink, t)
    draw_lanterns(ink, light, t) if t < K.climax else None
    house(ink, light, t, WEST_HOUSE, WEST_HOUSE[1], K.house_w, CORAL_WASH,
          ramp(t, K.window_w, K.window_w + 0.6) * (0.8 + 0.2 * ramp(t, K.home + 0.4, K.home + 1.2)), 61, 1)
    house(ink, light, t, EAST_HOUSE, EAST_HOUSE[1], K.house_e, TEAL_WASH,
          ramp(t, K.window_e, K.window_e + 0.6), 71, -1)
    draw_path(ink, t)
    for f in FLOWERS:
        b = flower_bloom(f, t)
        if b > 0:
            draw_flower(ink, light, f, t, b)
    tips = draw_tree(ink, light, t)
    if t >= K.climax:
        draw_lanterns(ink, light, t)
    draw_seed_fall(light, t)
    draw_pollen(light, t)
    draw_fireflies(light, t)
    draw_petals(ink, t, tips)
    draw_characters(ink, t)
    draw_retrace(light, t)
    return ink0, light0


GESTURE_BLOOMS = {}          # flower index -> bloom start time (filled by the planner)


def flower_bloom(f, t):
    i = FLOWERS.index(f)
    if i in GESTURE_BLOOMS:
        t0 = GESTURE_BLOOMS[i]
    elif f["side"] == "e":
        t0 = K.pollen + 0.4 + (f["s"] - S_TREE) / 175
    else:                    # remaining west flowers open with the lanterns
        t0 = LIT_T[min(len(LIT_T) - 1, i * 2)]
    return ramp(t, t0, t0 + 1.4)


def draw_retrace(light, t):
    u = ramp(t, K.retrace, K.retrace + 1.6)
    if u <= 0 or u >= 1:
        return
    s = PATH_LEN * (1 - u)
    for j in range(16):
        p = path_pt(s + j * 9)
        light.dot(p, 3.0 - j * 0.15, LIGHT_GOLD, 0.85 * (1 - j / 16))
