"""Procedural environment elements and finishing for the reference renderer."""
from __future__ import annotations

import math

import cv2
import numpy as np

from .core import (F32, col, blur, blur_h, fbm_field, fft_noise, sample, grid, soft_spot, luma, hash01,
                   clamp, pixgrid)


# --------------------------------------------------------------------------
# Particles (3D points projected with simple perspective + camera zoom)
# --------------------------------------------------------------------------
class Particles:
    """A deterministic field of particles with per-particle random attributes.

    Positions are in normalised screen units (x in [-asp, asp], y in [-1,1])
    at depth z (1 = title plane, <1 nearer, >1 farther).
    """

    def __init__(self, n, seed=0, spread=(2.2, 1.3), z=(0.5, 3.0)):
        r = np.random.default_rng(seed)
        self.n = n
        self.x0 = r.uniform(-spread[0], spread[0], n).astype(F32)
        self.y0 = r.uniform(-spread[1], spread[1], n).astype(F32)
        self.z = r.uniform(z[0], z[1], n).astype(F32)
        self.r = r.random(n).astype(F32)
        self.r2 = r.random(n).astype(F32)
        self.r3 = r.random(n).astype(F32)
        self.phase = r.uniform(0, 2 * math.pi, n).astype(F32)

    def drift(self, t, vel=(0.0, -0.05), turb=0.05, freq=0.6, wrap=(2.4, 1.5)):
        x = self.x0 + vel[0] * t * (0.5 + self.r) + turb * np.sin(t * freq * (0.6 + self.r2) + self.phase)
        y = self.y0 + vel[1] * t * (0.5 + self.r) + turb * np.cos(t * freq * 0.8 * (0.6 + self.r3) + self.phase * 1.3)
        x = (x + wrap[0]) % (2 * wrap[0]) - wrap[0]
        y = (y + wrap[1]) % (2 * wrap[1]) - wrap[1]
        return x, y


def project(x, y, z, W, H, zoom=1.0, pan=(0.0, 0.0)):
    """Normalised (x,y,z) -> pixel coords and per-particle scale."""
    s = zoom / np.maximum(z, 0.05)
    px = W / 2 + (x * s + pan[0]) * H / 2
    py = H / 2 + (y * s + pan[1]) * H / 2
    return px, py, s


def splat(buf, px, py, radius, color, intensity, streak=None, aa=True):
    """Draw soft dots (or streaks) into buf (HxWx3, additive)."""
    H, W = buf.shape[:2]
    c = col(color)
    lt = cv2.LINE_AA if aa else cv2.LINE_8
    for i in range(len(px)):
        I = float(intensity[i]) if np.ndim(intensity) else float(intensity)
        if I <= 0.003:
            continue
        x, y = float(px[i]), float(py[i])
        r = float(radius[i]) if np.ndim(radius) else float(radius)
        if x < -50 or y < -50 or x > W + 50 or y > H + 50:
            continue
        cc = tuple(float(v) for v in (c * I))
        if streak is not None:
            dx, dy = float(streak[0][i]), float(streak[1][i])
            cv2.line(buf, (int(x * 4), int(y * 4)), (int((x - dx) * 4), int((y - dy) * 4)), cc,
                     max(1, int(round(r))), lt, shift=2)
        else:
            cv2.circle(buf, (int(x * 4), int(y * 4)), max(1, int(r * 4)), cc, -1, lt, shift=2)
    return buf


def particle_layer(H, W, P: Particles, x, y, color, base_size=2.0, intensity=1.0, zoom=1.0, focus=1.0,
                   dof=0.0, flicker=0.0, t=0.0, streak=None, pan=(0.0, 0.0), glow=1.5, fade=None):
    """Render particles with depth-scaled size and optional depth-of-field
    (out-of-focus particles drawn larger/fainter on a blurred pass)."""
    px, py, s = project(x, y, P.z, W, H, zoom, pan)
    k = H / 1080.0
    size = base_size * k * s * (0.5 + P.r)
    I = intensity * np.clip(1.2 / P.z, 0.15, 1.5) * (0.5 + 0.5 * P.r2)
    if flicker:
        I = I * (1 - flicker + flicker * (0.5 + 0.5 * np.sin(t * 9 * (0.5 + P.r3) + P.phase)))
    if fade is not None:
        I = I * fade
    sharp = np.zeros((H, W, 3), F32)
    soft = np.zeros((H // 2, W // 2, 3), F32)
    if dof > 0:
        defocus = np.abs(P.z - focus) * dof
        infocus = defocus < 0.6
    else:
        infocus = np.ones(P.n, bool)
        defocus = np.zeros(P.n, F32)
    idx = np.nonzero(infocus)[0]
    st = None
    if streak is not None:
        st = (streak[0][idx] * s[idx] * H / 2, streak[1][idx] * s[idx] * H / 2)
    splat(sharp, px[idx], py[idx], size[idx], color, I[idx], st)
    idx2 = np.nonzero(~infocus)[0]
    if len(idx2):
        rr = (size[idx2] + defocus[idx2] * 6 * k) / 2
        splat(soft, px[idx2] / 2, py[idx2] / 2, rr, color, I[idx2] * 0.5 / (1 + defocus[idx2]))
        soft = cv2.GaussianBlur(soft, (0, 0), 1.2)
        sharp += cv2.resize(soft, (W, H), interpolation=cv2.INTER_LINEAR)
    if glow > 0:
        sharp = sharp + blur(sharp, glow * 3 * k) * 1.2
    return sharp


# --------------------------------------------------------------------------
# Atmospheres
# --------------------------------------------------------------------------
def fog(H, W, t, color, density=0.5, scale=1.6, speed=(0.012, 0.0), seed=1, warp=0.1, height=None,
        contrast=1.6):
    n = fbm_field(H, W, t, scale, speed, seed, beta=2.4, evolve=0.03, warp=warp)
    n = np.clip((n - 0.5) * contrast + 0.5, 0, 1)
    if height is not None:
        _, ny = grid(H, W)
        a, b = height  # band centre, softness
        n = n * np.exp(-((ny - a) / b) ** 2)
    return n[..., None] * col(color)[None, None, :] * density


def smoke(H, W, t, color, density=0.6, scale=2.2, rise=0.03, seed=4, light=None):
    n = fbm_field(H, W, t, scale, (0.004, rise), seed, beta=2.0, evolve=0.06, warp=0.6)
    n = np.clip((n - 0.45) * 2.2, 0, 1) ** 1.3
    out = n[..., None] * col(color)[None, None, :] * density
    if light is not None:
        lx, ly, lr, lc = light
        out = out * (0.4 + 1.6 * soft_spot(H, W, lx, ly, lr)[..., None] * col(lc)[None, None, :])
    return out


def clouds(H, W, t, top, bottom, seed=3, scale=1.4, speed=0.01, light_dir=(0.0, -1.0), contrast=2.0):
    n = (fbm_field(H, W, t, scale, (speed, speed * 0.2), seed, beta=2.4, evolve=0.02, warp=0.08) * 0.65
         + fbm_field(H, W, t, scale * 2.3, (speed * 1.6, speed * 0.3), seed + 9, beta=2.0, evolve=0.03, warp=0.05) * 0.35)
    sh = np.roll(n, (int(light_dir[1] * 18 * H / 1080), int(light_dir[0] * 18 * H / 1080)), (0, 1))
    lit = np.clip((n - sh) * 1.8 + 0.5, 0, 1)
    lit = blur(lit, 6 * H / 1080)
    d = np.clip((n - 0.42) * contrast, 0, 1)
    c = col(bottom)[None, None, :] * (1 - lit[..., None]) + col(top)[None, None, :] * lit[..., None]
    return c * d[..., None], d


def stars(H, W, n=900, seed=7, t=0.0, twinkle=0.3, zoom=1.0, drift=(0.0, 0.0)):
    r = np.random.default_rng(seed)
    x = r.uniform(-2.2, 2.2, n)
    y = r.uniform(-1.3, 1.3, n)
    z = r.uniform(0.6, 4, n)
    b = r.random(n) ** 3
    ph = r.uniform(0, 6.28, n)
    buf = np.zeros((H, W, 3), F32)
    px, py, s = project(x + drift[0] * t / z, y + drift[1] * t / z, z, W, H, zoom)
    I = (0.15 + 1.5 * b) * (1 - twinkle + twinkle * (0.5 + 0.5 * np.sin(t * 3 + ph)))
    rad = np.clip(0.6 + b * 1.8, 0.6, 2.5) * H / 1080
    tint = np.where(b[:, None] > 0.5, np.array([[0.8, 0.9, 1.0]]), np.array([[1.0, 0.92, 0.85]]))
    for i in range(n):
        cv2.circle(buf, (int(px[i] * 4), int(py[i] * 4)), max(1, int(rad[i] * 4)),
                   tuple(float(v) for v in tint[i] * I[i]), -1, cv2.LINE_AA, shift=2)
    return buf + blur(buf, 2.5 * H / 1080) * 0.8


def nebula(H, W, t, c1, c2, c3, seed=11, scale=1.2):
    a = fbm_field(H, W, t, scale, (0.004, 0.002), seed, beta=2.8, evolve=0.01, warp=0.8)
    b = fbm_field(H, W, t, scale * 1.7, (-0.003, 0.001), seed + 3, beta=2.2, evolve=0.01, warp=0.5)
    a = np.clip((a - 0.45) * 2.2, 0, 1) ** 1.5
    b = np.clip((b - 0.5) * 2.5, 0, 1) ** 2
    return (a[..., None] * col(c1) + b[..., None] * col(c2) + (a * b)[..., None] * col(c3)).astype(F32)


def rain(H, W, t, n=700, angle=12, speed=2.6, length=0.09, seed=21, color=(0.7, 0.75, 0.8), intensity=0.35,
         zoom=1.0):
    r = np.random.default_rng(seed)
    x0 = r.uniform(-2.4, 2.4, n)
    y0 = r.uniform(-1.2, 1.2, n)
    z = r.uniform(0.4, 3.0, n)
    v = speed * (0.8 + 0.4 * r.random(n))
    a = math.radians(angle)
    y = (y0 + v * t / z * 0.6 + 1.3) % 2.6 - 1.3
    x = x0 + math.tan(a) * (y - y0)
    buf = np.zeros((H, W, 3), F32)
    px, py, s = project(x, y, z, W, H, zoom)
    L = length * H / 2 * s
    c = col(color)
    for i in range(n):
        I = intensity * min(1.3, 1.1 / z[i])
        dx, dy = math.sin(a) * L[i], math.cos(a) * L[i]
        cv2.line(buf, (int(px[i] * 4), int(py[i] * 4)), (int((px[i] - dx) * 4), int((py[i] - dy) * 4)),
                 tuple(float(q) for q in c * I), 1, cv2.LINE_AA, shift=2)
    near = blur(buf, 1.0)
    return near


def bolt_points(p0, p1, seed=0, depth=6, rough=0.22, branches=3):
    """Midpoint displacement lightning. Returns list of polylines (Nx2)."""
    r = np.random.default_rng(seed)

    def sub(a, b, d, rough):
        pts = [np.array(a), np.array(b)]
        for _ in range(d):
            new = [pts[0]]
            for i in range(len(pts) - 1):
                p, q = pts[i], pts[i + 1]
                m = (p + q) / 2
                dv = q - p
                nrm = np.array([-dv[1], dv[0]])
                m = m + nrm * r.normal(0, rough)
                new += [m, q]
            pts = new
            rough *= 0.55
        return np.array(pts)

    main = sub(p0, p1, depth, rough)
    lines = [main]
    for b in range(branches):
        i = int(r.uniform(0.2, 0.7) * len(main))
        s = main[i]
        dirv = main[min(i + 8, len(main) - 1)] - s
        ang = math.atan2(dirv[1], dirv[0]) + r.choice([-1, 1]) * r.uniform(0.4, 0.9)
        L = np.linalg.norm(np.array(p1) - np.array(p0)) * r.uniform(0.15, 0.35)
        e = s + L * np.array([math.cos(ang), math.sin(ang)])
        lines.append(sub(s, e, depth - 2, rough * 0.8))
    return lines


def draw_lines(H, W, lines, color, width=2.0, glow=1.0, intensity=1.0, core=(1, 1, 1)):
    buf = np.zeros((H, W, 3), F32)
    k = H / 1080
    for j, ln in enumerate(lines):
        w = width * k * (1.0 if j == 0 else 0.6)
        pts = (ln * 4).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(buf, [pts], False, tuple(float(v) for v in col(core) * intensity), max(1, int(round(w))),
                      cv2.LINE_AA, shift=2)
    g1 = blur(buf, 4 * k)
    g2 = blur(buf, 18 * k)
    g3 = blur(buf, 60 * k)
    c = col(color)[None, None, :]
    return buf + (g1 * 1.5 + g2 * 1.4 + g3 * 1.0) * c * glow


def ring(H, W, cx, cy, radius, width, aspect=1.0):
    nx, ny = grid(H, W)
    d = np.sqrt(((nx - cx) / aspect) ** 2 + (ny - cy) ** 2)
    return np.exp(-((d - radius) / max(width, 1e-4)) ** 2).astype(F32)


def shockwave_displace(img, cx, cy, radius, width, amount):
    """Radial refraction band (pixels displaced outward around a ring)."""
    H, W = img.shape[:2]
    nx, ny = grid(H, W)
    dx, dy = nx - cx, ny - cy
    d = np.sqrt(dx * dx + dy * dy) + 1e-5
    band = np.exp(-((d - radius) / width) ** 2) * np.sign(d - radius)
    off = band * amount * H / 2
    xs, ys = pixgrid(H, W)
    return cv2.remap(img, xs - (dx / d * off).astype(F32), ys - (dy / d * off).astype(F32),
                     interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def crack_lines(seed, origin, n=6, length=0.6, segs=14, jitter=0.5):
    """Branching crack polylines in normalised coords from origin."""
    r = np.random.default_rng(seed)
    lines = []
    for i in range(n):
        a = 2 * math.pi * i / n + r.normal(0, 0.3)
        p = np.array(origin, float)
        pts = [p.copy()]
        step = length / segs
        for s in range(segs):
            a += r.normal(0, jitter)
            p = p + step * np.array([math.cos(a), math.sin(a)]) * r.uniform(0.6, 1.3)
            pts.append(p.copy())
            if r.random() < 0.15:
                b = a + r.choice([-1, 1]) * r.uniform(0.5, 1.2)
                q = p.copy()
                br = [q.copy()]
                for _ in range(segs // 3):
                    b += r.normal(0, jitter)
                    q = q + step * 0.8 * np.array([math.cos(b), math.sin(b)])
                    br.append(q.copy())
                lines.append(np.array(br))
        lines.append(np.array(pts))
    return lines


def draw_partial(H, W, lines, frac, color, width=1.5, to_px=None):
    """Draw each normalised polyline up to fraction frac of its points."""
    buf = np.zeros((H, W, 3), F32)
    c = tuple(float(v) for v in col(color))
    for ln in lines:
        m = max(2, int(len(ln) * clamp(frac)))
        if frac <= 0:
            continue
        pts = ln[:m]
        px = (W / 2 + pts[:, 0] * H / 2) if to_px is None else to_px(pts)[0]
        py = (H / 2 + pts[:, 1] * H / 2) if to_px is None else to_px(pts)[1]
        arr = (np.stack([px, py], 1) * 4).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(buf, [arr], False, c, max(1, int(width * H / 1080)), cv2.LINE_AA, shift=2)
    return buf


def caustics(H, W, t, scale=3.0, seed=31, sharp=6.0):
    a = fbm_field(H, W, t, scale, (0.03, 0.02), seed, beta=1.8, evolve=0.15)
    b = fbm_field(H, W, t, scale * 1.3, (-0.025, 0.03), seed + 5, beta=1.8, evolve=0.12)
    ra = (1 - np.abs(a * 2 - 1)) ** sharp
    rb = (1 - np.abs(b * 2 - 1)) ** sharp
    return np.clip(ra + rb, 0, 1.5).astype(F32)


def light_cone(H, W, origin, direction_deg, spread_deg, length=2.5, softness=0.6):
    """Wedge-shaped light shaft mask from origin (normalised coords)."""
    nx, ny = grid(H, W)
    dx, dy = nx - origin[0], ny - origin[1]
    ang = np.degrees(np.arctan2(dy, dx))
    da = np.abs((ang - direction_deg + 180) % 360 - 180)
    d = np.sqrt(dx * dx + dy * dy)
    m = np.clip(1 - da / spread_deg, 0, 1) ** (1 + softness * 3)
    return (m * np.exp(-d / length)).astype(F32)


# --------------------------------------------------------------------------
# HUD
# --------------------------------------------------------------------------
def hud_layer(H, W, t, color, reveal=1.0, seed=3, rot=0.0, cx=0.0, cy=0.0, radius=0.62, alpha=1.0):
    buf = np.zeros((H, W, 3), F32)
    c = tuple(float(v) for v in col(color) * alpha)
    k = H / 1080
    ccx, ccy = int((W / 2 + cx * H / 2) * 4), int((H / 2 + cy * H / 2) * 4)
    R = radius * H / 2
    lt = cv2.LINE_AA
    # segmented outer ring
    for i in range(24):
        a0 = i * 15 + rot
        if hash01(i, seed) < 0.3:
            continue
        sweep = 10 * clamp(reveal * 1.4 - i / 30)
        if sweep <= 0:
            continue
        cv2.ellipse(buf, (ccx, ccy), (int(R * 4), int(R * 4)), 0, a0, a0 + sweep, c, max(1, int(2 * k)), lt, shift=2)
    # inner thin ring with ticks
    R2 = R * 0.86
    cv2.ellipse(buf, (ccx, ccy), (int(R2 * 4), int(R2 * 4)), 0, -rot * 0.5, -rot * 0.5 + 300 * clamp(reveal),
                tuple(v * 0.6 for v in c), max(1, int(1 * k)), lt, shift=2)
    for i in range(72):
        if i / 72 > reveal:
            break
        a = math.radians(i * 5 - rot * 0.5)
        l = 10 * k if i % 6 else 22 * k
        x0, y0 = ccx / 4 + math.cos(a) * R2, ccy / 4 + math.sin(a) * R2
        x1, y1 = ccx / 4 + math.cos(a) * (R2 - l), ccy / 4 + math.sin(a) * (R2 - l)
        cv2.line(buf, (int(x0 * 4), int(y0 * 4)), (int(x1 * 4), int(y1 * 4)), tuple(v * 0.7 for v in c), 1, lt,
                 shift=2)
    # corner brackets
    bw, bh = W * 0.42, H * 0.3
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = W / 2 + sx * bw * (0.7 + 0.3 * reveal)
            y = H / 2 + sy * bh * (0.7 + 0.3 * reveal)
            L = 40 * k * reveal
            p = [(x, y - sy * L), (x, y), (x - sx * L, y)]
            arr = (np.array(p) * 4).astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(buf, [arr], False, c, max(1, int(2 * k)), lt, shift=2)
    return buf + blur(buf, 3 * k) * 0.8


# --------------------------------------------------------------------------
# Finishing
# --------------------------------------------------------------------------
def tonemap(img, knee=0.78):
    x = np.maximum(img, 0)
    over = x > knee
    y = x.copy()
    y[over] = knee + (1 - knee) * (1 - np.exp(-(x[over] - knee) / (1 - knee)))
    return y


def grade(img, lift=(0, 0, 0), gain=(1, 1, 1), gamma=1.0, sat=1.0, shadows=None, highlights=None, contrast=1.0):
    out = img * col(gain)[None, None, :] + col(lift)[None, None, :] * (1 - np.clip(img, 0, 1))
    if contrast != 1.0:
        out = (out - 0.18) * contrast + 0.18
        out = np.maximum(out, 0)
    if gamma != 1.0:
        out = np.power(np.maximum(out, 0), 1 / gamma)
    L = luma(out)[..., None]
    if sat != 1.0:
        out = L + (out - L) * sat
    if shadows is not None:
        w = np.clip(1 - L * 2.5, 0, 1)
        out = out + w * col(shadows)[None, None, :]
    if highlights is not None:
        w = np.clip((L - 0.45) * 2, 0, 1)
        out = out + w * col(highlights)[None, None, :]
    return out


def vignette(img, strength=0.5, radius=1.25):
    H, W = img.shape[:2]
    nx, ny = grid(H, W)
    d = np.sqrt((nx / (W / H)) ** 2 + ny ** 2) / radius
    v = 1 - strength * np.clip(d, 0, 1.5) ** 2.2
    return img * np.clip(v, 0, 1)[..., None]


_grain_cache = {}


def grain(img, t, amount=0.035, fps=24):
    H, W = img.shape[:2]
    key = (H, W)
    if key not in _grain_cache:
        r = np.random.default_rng(99)
        frames = []
        for i in range(8):
            g = r.standard_normal((H // 2, W // 2)).astype(F32)
            g = cv2.resize(cv2.GaussianBlur(g, (0, 0), 0.6), (W, H), interpolation=cv2.INTER_LINEAR)
            frames.append(g)
        _grain_cache[key] = frames
    g = _grain_cache[key][int(t * fps) % 8]
    L = luma(np.clip(img, 0, 1))
    w = amount * (0.4 + 1.2 * L * (1 - L) * 2)
    return img + (g * w)[..., None]


def letterbox(img, ratio=2.39, amount=1.0):
    if amount <= 0:
        return img
    H, W = img.shape[:2]
    bar = int(round((H - W / ratio) / 2 * amount))
    if bar > 0:
        img = img.copy()
        img[:bar] = 0
        img[H - bar:] = 0
    return img


def chroma_ab(img, amount=0.002):
    if amount <= 0:
        return img
    H, W = img.shape[:2]
    out = img.copy()
    for ch, s in ((0, 1 + amount), (2, 1 - amount)):
        M = np.array([[s, 0, (1 - s) * W / 2], [0, s, (1 - s) * H / 2]], F32)
        out[..., ch] = cv2.warpAffine(img[..., ch], M, (W, H), flags=cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_REPLICATE)
    return out


def bloom(img, threshold=0.8, strength=0.6, radius=1.0):
    H = img.shape[0]
    k = H / 1080 * radius
    hi = np.maximum(img - threshold, 0)
    return img + (blur(hi, 6 * k) * 0.5 + blur(hi, 22 * k) * 0.35 + blur(hi, 70 * k) * 0.25) * strength


def streak(img, threshold=1.0, strength=0.3, length=120, color=(0.6, 0.75, 1.0)):
    H = img.shape[0]
    hi = np.maximum(luma(img) - threshold, 0)
    s = blur_h(hi, length * H / 1080)
    return img + s[..., None] * col(color)[None, None, :] * strength


def to_uint8(img):
    return (np.clip(img, 0, 1) ** (1.0) * 255 + 0.5).astype(np.uint8)
