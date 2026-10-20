"""v4 effect engines, layered on top of the v3 illustrated world.

  Config            config.json + `--set key.path=value` overrides
  MusicTimeline     timeline.json (authored events, kept out of the code)
  FaceTracker       identity-stable, smoothed, confidence-gated head anchors
  ContourEngine     temporally stable hand-drawn white silhouette outline
  PaintStrokeEngine textured blue brush strokes (bristles, pigment body,
                    highlight edge, splatter, dissolve into flecks)
  FX                golden auras, gold particles, hand-drawn stars,
                    shooting stars, white scribbles ("Hi", arrows, bursts...)

Everything is a deterministic function of (t, frame data); there is no
hidden per-frame state, so chunks render independently and reproducibly.
"""
import copy
import json
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "v3"))
import world as Wd  # noqa: E402

W, H, FPS = 1920, 1080, 30


# ---------------------------------------------------------------- config
def load_config(overrides=()):
    with open(os.path.join(HERE, "config.json")) as fh:
        cfg = json.load(fh)
    for ov in overrides:
        key, _, val = ov.partition("=")
        try:
            v = json.loads(val)
        except json.JSONDecodeError:
            v = val
        node = cfg
        parts = key.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = v
    return cfg


def overrides_from_env():
    raw = os.environ.get("EDIT_V4_SET", "")
    return [s for s in raw.split(";") if s.strip()]


CFG = load_config(overrides_from_env())


class MusicTimeline:
    def __init__(self, path=os.path.join(HERE, "timeline.json")):
        with open(path) as fh:
            self.data = json.load(fh)
        for k, v in self.data.get("story", {}).items():
            setattr(Wd.K, k, v)

    def outline_alpha(self, t):
        return Wd.keyed(t, [tuple(k) for k in self.data["outline"]["keys"]])

    def outline_redraw(self, t):
        prog = 1.0
        for t0, d in self.data["outline"]["redraw"]:
            if t0 <= t < t0 + d:
                prog = min(prog, Wd.ease((t - t0) / d))
        return prog

    def section(self, t):
        for s in self.data["sections"]:
            if s["t0"] <= t < s["t1"]:
                return s["name"]
        return ""


TL = MusicTimeline()


def beat_env(t, tau=0.18):
    """Decaying pulse after each downbeat (used sparingly: aura breathing)."""
    k = int(np.searchsorted(Wd.DOWN, t)) - 1
    return math.exp(-(t - Wd.DOWN[k]) / tau) if k >= 0 else 0.0


# ---------------------------------------------------------------- face tracking
def track_faces(faces, cuts):
    """faces: (N, 2, 4) boxes in 1920px (w == 0 -> none), unordered.
    Returns centre (N,2,2), size (N,2) and confidence (N,2) for two identity-
    stable tracks (0 = left person, 1 = right person at the start of a shot)."""
    n = len(faces)
    cen = np.zeros((n, 2, 2), np.float32)
    size = np.zeros((n, 2), np.float32)
    conf = np.zeros((n, 2), np.float32)
    pc, ps, pk = None, None, np.zeros(2)
    for i in range(n):
        dets = [b for b in faces[i] if b[2] > 0]
        dc = [np.array([b[0] + b[2] / 2, b[1] + b[3] / 2]) for b in dets]
        dsz = [float(b[2]) for b in dets]
        if pc is None or i in cuts:
            if len(dets) == 2 or (pc is None and dets):
                order = np.argsort([c[0] for c in dc])
                pc = [dc[order[0]], dc[order[-1]]] if len(dets) == 2 else [dc[0], dc[0] + [400, 0]]
                ps = [dsz[order[0]], dsz[order[-1]]] if len(dets) == 2 else [dsz[0], dsz[0]]
                pk = np.array([1.0, 1.0 if len(dets) == 2 else 0.0])
            elif pc is None:
                continue
        matched = [None, None]
        if len(dets) == 2:
            d0 = np.linalg.norm(dc[0] - pc[0]) + np.linalg.norm(dc[1] - pc[1])
            d1 = np.linalg.norm(dc[1] - pc[0]) + np.linalg.norm(dc[0] - pc[1])
            matched = [0, 1] if d0 <= d1 else [1, 0]
        elif len(dets) == 1:
            j = int(np.argmin([np.linalg.norm(dc[0] - pc[k]) for k in range(2)]))
            matched[j] = 0
        for k in range(2):
            m = matched[k]
            ok = m is not None and np.linalg.norm(dc[m] - pc[k]) < 1.1 * max(ps[k], 60)
            if ok:
                pc[k] = 0.62 * pc[k] + 0.38 * dc[m]
                ps[k] = 0.8 * ps[k] + 0.2 * dsz[m]
            pk[k] += ((1.0 if ok else 0.0) - pk[k]) * (0.3 if ok else 0.12)
            cen[i, k], size[i, k], conf[i, k] = pc[k], ps[k], pk[k]
    return cen, size, conf


# ---------------------------------------------------------------- outline
def _pos_noise(p, t, f1=0.021, f2=0.017, f3=0.011):
    x, y = p[:, 0], p[:, 1]
    return (np.sin(x * f1 + t * 0.55) + np.sin(y * f2 - t * 0.45) + np.sin((x + y) * f3 + t * 0.3)) / 3


class ContourEngine:
    """Hand-drawn white outline that hugs the silhouette.

    Noise is keyed on screen position (not arc length), so a still edge stays
    still and a moving edge carries its wobble with it - no swimming or flicker.
    """

    def __init__(self, cfg):
        self.c = cfg["outline"]

    def contours(self, mask, scale):
        cs, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        mh, mw = mask.shape
        out = []
        for c in cs:
            if cv2.contourArea(c) < mask.size * 0.01:
                continue
            p = c[:, 0, :].astype(np.float64)
            border = (p[:, 0] <= 2) | (p[:, 0] >= mw - 3) | (p[:, 1] <= 2) | (p[:, 1] >= mh * 0.9)   # bottom band: furniture
            r = 5
            k = np.exp(-0.5 * (np.arange(-r, r + 1) / 2.2) ** 2)
            k /= k.sum()
            ext = np.vstack([p[-r:], p, p[:r]])
            ps = np.stack([np.convolve(ext[:, d], k, "valid") for d in range(2)], 1) * scale + scale / 2
            d = np.roll(ps, -2, 0) - np.roll(ps, 2, 0)
            nrm = np.stack([d[:, 1], -d[:, 0]], 1)
            nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
            out.append((ps, nrm, border))
        return out

    @staticmethod
    def edge_evidence(img_small, ps, nrm, k):
        """Colour contrast across the contour, sampled from a blurred half-res
        frame. False mask edges running through flat wall have almost none."""
        hh, ww = img_small.shape[:2]

        def sample(q):
            x = np.clip((q[:, 0] / k).astype(int), 0, ww - 1)
            y = np.clip((q[:, 1] / k).astype(int), 0, hh - 1)
            return img_small[y, x].astype(np.float32)
        d = np.linalg.norm(sample(ps - nrm * 7) - sample(ps + nrm * 9), axis=1)
        r = 6
        return np.convolve(np.concatenate([d[-r:], d, d[:r]]), np.ones(2 * r + 1) / (2 * r + 1), "valid")

    def draw(self, white, ink, mask, scale, t, alpha, prog, img_small=None):
        c = self.c
        if alpha <= 0 or not c["enabled"]:
            return
        col = tuple(int(v) for v in c["color_bgr"])
        for ps, nrm, border in self.contours(mask, scale):
            if img_small is not None:
                ev = self.edge_evidence(img_small, ps, nrm, W / img_small.shape[1])
                border = border | (ev < c.get("min_edge_contrast", 30))
            n = _pos_noise(ps, t)
            q = ps + nrm * (c["offset_px"] + c["jitter_px"] * n)[:, None]
            wv = c["width_px"] * (1 + c["width_variation"] * _pos_noise(ps * 0.7 + 300, t * 0.6, 0.013, 0.019, 0.007))
            runs, cur = [], []
            for i in range(len(q)):
                if not border[i]:
                    cur.append(i)
                elif cur:
                    runs.append(cur)
                    cur = []
            if cur:
                if runs and not border[0]:
                    runs[0] = cur + runs[0]
                else:
                    runs.append(cur)
            for r in runs:
                if len(r) < 10:
                    continue
                r = r[:max(2, int(len(r) * prog))]
                pts = q[r]
                # soft ink shadow just outside, so white reads on the ivory wall
                ink.line(pts + nrm[r] * 3.2, Wd.INK, alpha * c["shadow_alpha"], 3)
                th = np.clip(np.round(wv[r]), 1, 8).astype(int)
                s = 0
                for i in range(1, len(r) + 1):
                    if i == len(r) or th[i] != th[s]:
                        if i - s >= 1:
                            white.line(pts[max(0, s - 1):i], col, alpha, int(th[s]))
                        s = i
                # occasional secondary trace, like a second pass of the pen
                sec = _pos_noise(ps[r] * 0.5 + 900, 0.0, 0.009, 0.011, 0.005) > 0.25
                if sec.any():
                    q2 = q[r] + nrm[r] * 5.5
                    start = None
                    for i in range(len(r) + 1):
                        on = i < len(r) and sec[i]
                        if on and start is None:
                            start = i
                        if not on and start is not None:
                            if i - start > 6:
                                white.line(q2[start:i], col, alpha * c["secondary_alpha"], 1)
                            start = None


# ---------------------------------------------------------------- paint
def bezier(pts, n=220):
    p = np.asarray(pts, np.float64)
    u = np.linspace(0, 1, n)[:, None]
    return ((1 - u) ** 3) * p[0] + 3 * ((1 - u) ** 2) * u * p[1] + 3 * (1 - u) * u * u * p[2] + (u ** 3) * p[3]


class PaintStroke:
    """One persistent, choreographed brush stroke.

    Texture is built from static per-stroke randomness (seeded), so the paint
    deposited on the wall never flickers: only the travelling head, the dry
    tail and the final dissolve change over time.
      body      watercolour wash with ragged edges        -> MULTIPLY layer
      bristles  ~22 streaks, colour-varied, dry-brush gaps -> OVER layer
      wet edge  broken darker line along both edges        -> OVER layer
      granules  static pigment specks inside the stroke    -> OVER layer
      lights    broken pale highlights, head glow, sheds   -> ADD layer
    """

    def __init__(self, spec, cfg):
        self.s = spec
        self.pal = cfg["paint"]["palette_bgr"]
        self.cfg = cfg["paint"]
        self.path = bezier(spec["pts"], 260)
        self.arc = Wd.arclen(self.path)
        self.L = self.arc[-1]
        d = np.gradient(self.path, axis=0)
        self.tan = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-9)
        self.nrm = np.stack([-self.tan[:, 1], self.tan[:, 0]], 1)
        g = np.random.default_rng(spec["seed"])
        nb = int(cfg["paint"]["bristles"] * 1.4)
        v = np.linspace(-0.5, 0.5, nb) + g.normal(0, 0.012, nb)
        self.bv = v
        self.bf = g.uniform(0.012, 0.05, (nb, 3))
        self.bp = g.uniform(0, 6.28, (nb, 3))
        self.ba = g.uniform(0.45, 0.95, nb)
        self.bstart = np.abs(v) * g.uniform(0.0, 0.25, nb)
        self.bend = 1 - (np.abs(v) * 2) ** 1.5 * g.uniform(0.05, 0.45, nb)
        names = spec["colors"]
        self.bcol = []
        for k in range(nb):
            edge = abs(v[k]) * 2
            if g.random() < 0.12:
                self.bcol.append("pale_cyan" if "white" not in names else "white")
            else:
                idx = int(np.clip(edge * len(names) + g.normal(0, 0.6), 0, len(names) - 1))
                self.bcol.append(names[idx])
        self.edge_nz = g.uniform(0, 6.28, 4)
        self.gran = [(g.uniform(0, 1), g.uniform(-0.45, 0.45), g.uniform(0.6, 1.5)) for _ in range(int(spec["width"] * 5))]
        self.splat = [(g.uniform(0.03, 0.98), g.normal(0, 0.95), g.uniform(1.0, 3.4), g.uniform(0, 1))
                      for _ in range(int(16 + spec["width"] * 0.5))]
        self.flecks = [(g.uniform(0, 1), g.normal(0, 0.6), g.uniform(-30, 30), g.uniform(10, 50),
                        g.uniform(0.9, 2.6)) for _ in range(70)]
        self.t_end = spec["t0"] + spec["dur"] + spec["hold"] + spec["dissolve"]

    def color(self, name):
        return tuple(int(v) for v in self.pal[name])

    def active(self, t):
        return self.s["t0"] <= t <= self.t_end

    def head(self, t):
        s = self.s
        u = Wd.clamp01((t - s["t0"]) / s["dur"])
        return u * u * (1.6 - 0.6 * u) if s["kind"] == "accel" else Wd.ease(u) * 0.85 + u * 0.15

    def width_at(self, uabs):
        w = self.s["width"]
        press = np.clip(uabs * 14, 0.35, 1.0)                        # brush lands
        lift = 1 - 0.55 * np.clip((uabs - 0.78) / 0.22, 0, 1) ** 1.3  # brush lifts, dry end
        swell = 1 + 0.12 * np.sin(uabs * 9 + self.edge_nz[0])
        return w * press * lift * swell

    def draw(self, body, paint, light, t):
        if not self.active(t):
            return
        s = self.s
        uh = self.head(t)
        tdis = s["t0"] + s["dur"] + s["hold"]
        dis = Wd.clamp01((t - tdis) / s["dissolve"])
        ut = 0.0
        if s["kind"] == "accel":                                      # a travelling streak, not a deposit
            ut = max(0.0, uh - 0.45) + 0.55 * Wd.clamp01((t - s["t0"] - s["dur"]) / 0.6)
        ut = max(ut, Wd.ease(dis) * uh)
        fade = (1 - 0.6 * dis) * self.cfg["intensity"]
        if uh - ut > 0.004:
            self._paint(body, paint, light, t, ut, uh, fade)
        self._flecks(paint, t, dis, uh)

    def _paint(self, body, paint, light, t, ut, uh, fade):
        s = self.s
        n = len(self.path) - 1
        i0, i1 = int(ut * n), max(int(uh * n), 1)
        P, N, A = self.path[i0:i1 + 1], self.nrm[i0:i1 + 1], self.arc[i0:i1 + 1]
        uabs = A / self.L
        wid = self.width_at(uabs)
        # watercolour body with ragged, noisy edges (multiply into the wall)
        e1 = 0.5 + 0.09 * np.sin(A * 0.045 + self.edge_nz[1]) + 0.06 * np.sin(A * 0.13 + self.edge_nz[2])
        e2 = 0.5 + 0.09 * np.sin(A * 0.05 + self.edge_nz[3]) + 0.06 * np.sin(A * 0.11 + self.edge_nz[0])
        poly = np.vstack([P + N * (wid * e1)[:, None], (P - N * (wid * e2)[:, None])[::-1]])
        body.fill(poly, self.color(s["colors"][min(1, len(s["colors"]) - 1)]), 0.55 * fade)
        # bristles
        rel_all = uabs
        for k in range(len(self.bv)):
            v = self.bv[k]
            q = P + N * (wid * v)[:, None]
            nz = (np.sin(A * self.bf[k, 0] + self.bp[k, 0]) + 0.6 * np.sin(A * self.bf[k, 1] + self.bp[k, 1])
                  + 0.35 * np.sin(A * self.bf[k, 2] * 4 + self.bp[k, 2]))
            dry = -0.9 + 1.9 * np.clip((rel_all - 0.55) / 0.45, 0, 1) + 1.1 * abs(v)
            on = (nz > dry) & (rel_all >= self.bstart[k]) & (rel_all <= self.bend[k])
            th = max(1, int(round(wid.mean() / len(self.bv) * 2.1)))
            col = self.color(self.bcol[k])
            a = self.ba[k] * fade
            st = None
            for i in range(len(q) + 1):
                o = i < len(q) and on[i]
                if o and st is None:
                    st = i
                if not o and st is not None:
                    if i - st >= 2:
                        paint.line(q[st:i], col, a, th)
                    st = None
        # darker wet edges, broken
        dark = self.color("midnight")
        for sign, e in ((1, e1), (-1, e2)):
            q = P + N * (sign * wid * e * 0.96)[:, None]
            on = np.sin(A * 0.07 + sign * 2 + self.edge_nz[2]) > -0.1
            st = None
            for i in range(len(q) + 1):
                o = i < len(q) and on[i]
                if o and st is None:
                    st = i
                if not o and st is not None:
                    if i - st >= 3:
                        paint.line(q[st:i], dark, 0.55 * fade, 1)
                    st = None
        # pigment granulation (static specks)
        for (u, v, r) in self.gran:
            if not (ut <= u <= uh):
                continue
            j = int(u * n)
            p = self.path[j] + self.nrm[j] * v * self.width_at(np.array([u]))[0]
            paint.dot(p, r, dark, 0.45 * fade)
        # broken pale highlights (very restrained light)
        hl = self.color("pale_cyan")
        on = np.sin(A * 0.035 + self.edge_nz[1] * 2) > 0.35
        q = P + N * (wid * 0.18)[:, None]
        st = None
        for i in range(len(q) + 1):
            o = i < len(q) and on[i]
            if o and st is None:
                st = i
            if not o and st is not None:
                if i - st >= 4:
                    paint.line(q[st:i], hl, 0.55 * fade, 1)
                    light.line(q[st:i], hl, self.cfg["highlight_light"] * 0.5 * fade, 1)
                st = None
        # wet head, splatter, shed sparks
        if t < s["t0"] + s["dur"] + 0.3:
            hp = self.path[i1]
            paint.dot(hp, max(2.0, wid[-1] * 0.3), self.color(s["colors"][-1]), 0.7 * fade)
            light.dot(hp, max(2.0, wid[-1] * 0.35), self.color("azure"), 0.18 * fade)
        for (us, off, r, ph) in self.splat:
            if us > uh or us < ut:
                continue
            j = int(us * n)
            age = (uh - us) * self.L / 500.0
            a = fade * Wd.clamp01(1.6 - age)
            p = self.path[j] + self.nrm[j] * off * s["width"] * 0.75 + self.tan[j] * ph * 7
            paint.dot(p, r, self.color(s["colors"][int(ph * len(s["colors"])) % len(s["colors"])]), 0.85 * a)
        if s["kind"] == "accel" and uh < 1:
            hp = self.path[i1]
            for k in range(12):
                tt = (t * 2.6 + k / 12) % 1
                p = hp - self.tan[i1] * tt * 110 + self.nrm[i1] * math.sin(k * 2.1 + t * 3) * 20 * tt
                light.dot(p, 1.5, hl, 0.55 * (1 - tt) * fade)

    def _flecks(self, paint, t, dis, uh):
        if dis <= 0:
            return
        for (u, off, vx, vy, r) in self.flecks:
            u = u * uh
            age = dis - u * 0.85
            if age <= 0 or age > 0.6:
                continue
            j = int(u * (len(self.path) - 1))
            a = 1 - age / 0.6
            p = self.path[j] + self.nrm[j] * off * self.s["width"] * 0.5 + np.array([vx, vy]) * age * 1.6
            paint.dot(p, r * (1 - age * 0.8), self.color(self.s["colors"][-1]), 0.8 * a * self.cfg["intensity"])


class PaintStrokeEngine:
    def __init__(self, cfg, timeline):
        self.on = cfg["paint"]["enabled"]
        self.strokes = [PaintStroke(s, cfg) for s in timeline.data["paint"]]

    def draw(self, body, paint, light, t):
        if not self.on:
            return
        for st in self.strokes:
            st.draw(body, paint, light, t)


# ---------------------------------------------------------------- FX
_FONT = os.path.join(HERE, "..", "assets", "Caveat.ttf")


def _hand_star(seed, n=5):
    g = np.random.default_rng(seed)
    pts = []
    for i in range(2 * n):
        r = (1.0 if i % 2 == 0 else 0.44) * g.uniform(0.86, 1.12)
        a = -math.pi / 2 + i * math.pi / n + g.normal(0, 0.05)
        pts.append((r * math.cos(a), r * math.sin(a)))
    return np.array(pts)


class FX:
    def __init__(self, cfg, timeline, face_track):
        self.cfg = cfg
        self.tl = timeline.data
        self.cen, self.size, self.conf = face_track
        g = np.random.default_rng(cfg["render"]["seed"])
        n = cfg["stars"]["count"]
        self.star_list = [dict(x=float(g.uniform(60, W - 60)), y=float(g.uniform(30, 220)), s=float(g.uniform(7, 12)),
                           seed=int(g.integers(1e6)), ph=float(g.uniform(0, 6)), on=18.8 + 0.55 * i)
                      for i in range(n)]
        self.motes = [(float(g.uniform(0, 18)), float(g.uniform(-1, 1)), float(g.uniform(30, 70)),
                       float(g.uniform(0, 6)), float(g.uniform(2.5, 4.5))) for _ in range(int(46 * cfg["particles"]["density"]))]
        self._hi = None

    # -- anchors in world space (then mapped through the climax close-up framing)
    def anchor(self, name, t):
        if name == "west_door":
            return Wd.path_pt(Wd.S_WDOOR)
        if name == "west_window":
            return np.array([Wd.WEST_HOUSE[0] + 82.0, Wd.WEST_HOUSE[1] - 42.0])
        if name == "tree_base":
            return np.array(Wd.TREE_BASE, np.float64)
        st = Wd.wanderer(t) if name == "wanderer" else Wd.friend(t)
        if st is None:
            return None
        return Wd.path_pt(st[0])

    def to_screen(self, p, t):
        xf = Wd.world_xform(t)
        if xf is None:
            return np.asarray(p, np.float64), 1.0
        return (np.asarray(p, np.float64) - xf[0]) * xf[2] + xf[1], xf[2]

    # -- golden head auras
    def aura(self, light, ink, t, f):
        c = self.cfg["aura"]
        if not c["enabled"]:
            return
        a_win = 0.0
        for w in self.tl["aura"]:
            a_win = max(a_win, Wd.env(t, w["t0"], w["t1"], 0.9, 1.2) * w["alpha"])
        if a_win <= 0:
            return
        col, acc = tuple(c["color_bgr"]), tuple(c["accent_bgr"])
        for k in range(2):
            cf = float(self.conf[f, k])
            if cf < 0.05:
                continue
            cx, cy = self.cen[f, k]
            w = float(self.size[f, k])
            hx, hy = cx, cy - 0.98 * w                                   # above the hair line
            rx, ry = 0.62 * w, 0.17 * w
            a = a_win * c["alpha"] * min(1.0, cf * 1.3)
            pulse = 1 + 0.05 * beat_env(t)
            rot = t * 0.35 + k * 1.3
            for j in range(7):                                           # broken, hand-drawn segments
                a0 = rot + j * 2 * math.pi / 7
                span = 0.55 + 0.12 * math.sin(j * 2.3 + k)
                th = np.linspace(a0, a0 + span, 12)
                pts = np.stack([hx + rx * pulse * np.cos(th), hy + ry * pulse * np.sin(th)], 1)
                pts += np.stack([np.sin(th * 3 + j) * 1.2, np.cos(th * 2 + j) * 0.8], 1)
                Wd.stroke(light, pts, col, a * 0.85, 2.2, 1.0, 40 + j, t, 0.0)
                Wd.stroke(ink, pts, Wd.GOLD, a * 0.55, 2.0, 1.0, 40 + j, t, 0.0)
            for j in range(4):                                           # short inner accent ticks
                ang = -math.pi / 2 + (j - 1.5) * 0.45 + 0.08 * math.sin(t + j)
                p0 = np.array([hx + rx * 0.62 * math.cos(ang), hy + ry * 0.9 * math.sin(ang) - 10])
                p1 = p0 + np.array([math.cos(ang), math.sin(ang)]) * 9
                light.line([p0, p1], acc, a * 0.6, 2)
            for j in range(5):                                           # sparks drifting off the halo
                ph = (t * 0.5 + j / 5 + k * 0.3) % 1
                ang = rot * 1.4 + j * 1.256
                p = np.array([hx + rx * math.cos(ang), hy + ry * math.sin(ang) - ph * 26])
                light.dot(p, 1.6, col, a * (1 - ph))

    # -- gold particles: crown motes at the climax, lantern trails, meeting motes
    def particles(self, light, t):
        if not self.cfg["particles"]["enabled"]:
            return
        K = Wd.K
        if K.climax - 1 <= t <= K.seated + 2:
            tips = Wd.tree_geometry(t, Wd.tree_growth(t))[1]
            if tips:
                for i, (dt, dx, vy, ph, life) in enumerate(self.motes):
                    t0 = K.climax + 1.5 + dt
                    u = t - t0
                    if u < 0 or u > life:
                        continue
                    base = tips[(i * 7) % len(tips)][1]
                    p = base + np.array([dx * 30 * u + 9 * math.sin(u * 1.8 + ph), -vy * u])
                    p, k = self.to_screen(p, t)
                    a = Wd.clamp01(u * 2) * Wd.clamp01((life - u) / 1.2)
                    for j in range(3):
                        light.dot(p + np.array([0, j * 4.0 * k]), (1.8 - j * 0.45) * k, Wd.LIGHT_GOLD,
                                  0.75 * a * (1 - j / 3))
        if K.meet - 0.2 <= t <= K.meet + 4.5:
            c = np.array(Wd.TREE_BASE) + np.array([0, -60])
            a = Wd.env(t, K.meet - 0.2, K.meet + 4.5, 0.6, 1.5)
            for j in range(8):
                ang = t * 1.1 + j * 0.785
                p = c + np.array([70 * math.cos(ang), 26 * math.sin(ang * 1.3)])
                light.dot(p, 1.6, Wd.LIGHT_GOLD, 0.7 * a)

    # -- hand-drawn stars and shooting stars
    def stars(self, ink, light, t):
        if not self.cfg["stars"]["enabled"]:
            return
        for st in self.star_list:
            on = Wd.ramp(t, st["on"], st["on"] + 1.2)
            if on <= 0:
                continue
            tw = 0.55 + 0.45 * math.sin(t * (0.6 + (st["seed"] % 7) * 0.09) + st["ph"])
            pts = Wd.xform_pts(_hand_star(st["seed"]), st["x"], st["y"], st["s"] * (0.9 + 0.12 * tw),
                               t * 0.12 + st["ph"])
            ink.fill(pts, Wd.GOLD_WASH, 0.75 * on)
            Wd.stroke(ink, pts, Wd.INK, 0.6 * on, 1.4, 1.0, st["seed"] % 997, t, 0.2, closed=True, taper=False)
            light.dot((st["x"], st["y"]), st["s"] * 0.9, Wd.LIGHT_GOLD, 0.1 * on * tw)
        for s in self.tl["shooting_stars"]:
            u = (t - s["t0"]) / 0.95
            if not (0 <= u <= 1.3):
                continue
            a, b = np.array(s["from"], float), np.array(s["to"], float)
            hu = Wd.ease_out(min(u, 1.0))
            for j in range(14):
                q = a + (b - a) * max(0.0, hu - j * 0.025)
                light.dot(q, max(0.8, 2.6 - j * 0.15), Wd.LIGHT_CREAM, (0.9 - j * 0.06) * Wd.clamp01(1.3 - u))

    # -- white scribbles
    def _hi_sprite(self):
        if self._hi is None:
            font = ImageFont.truetype(_FONT, 96)
            font.set_variation_by_axes([600])
            bb = font.getbbox("Hi")
            w, h = bb[2] - bb[0] + 16, bb[3] - bb[1] + 16
            im = Image.new("L", (w, h), 0)
            ImageDraw.Draw(im).text((8 - bb[0], 8 - bb[1]), "Hi", font=font, fill=255)
            self._hi = np.array(im)
        return self._hi

    def scribbles(self, white, ink, t):
        c = self.cfg["scribbles"]
        if not c["enabled"]:
            return
        for s in self.tl["scribbles"]:
            u = (t - s["t0"]) / s["dur"]
            if not (0 <= u <= 1):
                continue
            base = self.anchor(s["anchor"], t)
            if base is None:
                continue
            p, k = self.to_screen(base + np.array([s["dx"], s["dy"]]), t)
            sc = s["scale"] * k
            draw = Wd.clamp01(u / 0.35)
            a = 1 - Wd.clamp01((u - 0.75) / 0.25)
            paths = self._scribble_paths(s["kind"], p, sc, t, u)
            for pts, w in paths:
                Wd.stroke(ink, pts + np.array([1.5, 2.5]), Wd.INK, a * c["shadow_alpha"], w + 1.5, draw, 7, t, 0.4)
                Wd.stroke(white, pts, (252, 252, 255), a, w + 0.8, draw, 7, t, 0.4)
            if s["kind"] == "hi":
                self._blit_hi(white, ink, p + np.array([-20.0 * sc, -6 * sc]), draw, a)

    def _scribble_paths(self, kind, p, sc, t, u):
        out = []
        if kind == "burst":
            for j in range(7):
                ang = j * 2 * math.pi / 7 + 0.3
                r0, r1 = 12 * sc, (24 + 6 * (j % 2)) * sc
                out.append((np.array([p + np.array([math.cos(ang), math.sin(ang)]) * r0,
                                      p + np.array([math.cos(ang), math.sin(ang)]) * r1]), 2))
        elif kind == "exclaim":
            bob = 4 * math.sin(u * math.pi * 3) * (1 - u)
            out.append((np.array([p + [0, -22 * sc + bob], p + [1.5, 4 * sc + bob]]), 3))
            out.append((Wd.circle_pts(p + [1.5, 14 * sc + bob], 2.2 * sc, 8), 3))
        elif kind == "arrow":
            pts = Wd.spline([p, p + np.array([-30, 26]) * sc, p + np.array([-62, 58]) * sc], 10)
            out.append((pts, 2))
            hd = pts[-1]
            ang = math.atan2(pts[-1][1] - pts[-3][1], pts[-1][0] - pts[-3][0])
            for da in (2.6, -2.6):
                out.append((np.array([hd, hd + np.array([math.cos(ang + da), math.sin(ang + da)]) * 11 * sc]), 2))
        elif kind == "dashes":
            for j in range(3):
                q = p + np.array([0, j * 9]) * sc
                out.append((np.array([q, q + np.array([-18 + 4 * j, 0]) * sc]), 2))
        elif kind == "spiral":
            th = np.linspace(0, 3.4 * math.pi, 60)
            r = (3 + 16 * th / th[-1]) * sc
            out.append((np.stack([p[0] + r * np.cos(th + t * 0.6), p[1] + r * np.sin(th + t * 0.6)], 1), 2))
        elif kind in ("heart", "hi"):
            th = np.linspace(0, 2 * math.pi, 60)
            hs = (11 if kind == "heart" else 7) * sc
            q = p + (np.array([46.0, -4.0]) * sc if kind == "hi" else 0)
            hp = np.stack([q[0] + hs * 16 * np.sin(th) ** 3 / 16,
                           q[1] - hs * (13 * np.cos(th) - 5 * np.cos(2 * th) - 2 * np.cos(3 * th) - np.cos(4 * th)) / 16], 1)
            out.append((hp, 2))
            if kind == "heart":
                out.append((hp * 1.0 + np.array([3, -2]), 1))
        return out

    def _blit_hi(self, white, ink, p, draw, a):
        spr = self._hi_sprite()
        h, w = spr.shape
        x0, y0 = int(p[0] - w / 2), int(p[1] - h / 2)
        if x0 < 0 or y0 < 0 or x0 + w > W or y0 + h > H:
            return
        al = spr.astype(np.float32) / 255 * a
        al[:, int(w * draw):] = 0
        for L, col, dx, dy, k in ((ink, Wd.INK, 2, 3, self.cfg["scribbles"]["shadow_alpha"]), (white, (252, 252, 255), 0, 0, 1.0)):
            sub = L.a[y0 + dy:y0 + dy + h, x0 + dx:x0 + dx + w]
            v = (al * 255 * k).astype(np.uint8)
            m = v > sub
            L.col[y0 + dy:y0 + dy + h, x0 + dx:x0 + dx + w][m] = col
            L.a[y0 + dy:y0 + dy + h, x0 + dx:x0 + dx + w] = np.maximum(sub, v)


def xform_pts(pts, cx, cy, s, rot=0.0):
    c, sn = math.cos(rot), math.sin(rot)
    p = np.asarray(pts, np.float64)
    return np.stack([cx + (p[:, 0] * c - p[:, 1] * sn) * s, cy + (p[:, 0] * sn + p[:, 1] * c) * s], 1)


Wd.xform_pts = xform_pts
