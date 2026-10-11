"""Core image/maths primitives for the CMET reference preview renderer.

All images are float32 numpy arrays in display-referred space where 1.0 is
nominal white; values above 1.0 are allowed (highlights) and are rolled off
by `finish.tonemap`. RGB images are HxWx3, masks are HxW.
"""
from __future__ import annotations

import math
from functools import lru_cache

import cv2
import numpy as np

F32 = np.float32


# --------------------------------------------------------------------------
# Timing / easing
# --------------------------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(t, start, dur):
    """Linear 0..1 progress of t through [start, start+dur]."""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return clamp((t - start) / dur)


def smooth(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def smoother(u):
    u = clamp(u)
    return u * u * u * (u * (u * 6 - 15) + 10)


def ease_out(u, p=3.0):
    u = clamp(u)
    return 1 - (1 - u) ** p


def ease_in(u, p=3.0):
    u = clamp(u)
    return u ** p


def ease_in_out(u, p=3.0):
    u = clamp(u)
    return 0.5 * (2 * u) ** p if u < 0.5 else 1 - 0.5 * (2 - 2 * u) ** p


def expo_out(u):
    u = clamp(u)
    return 1.0 if u >= 1 else 1 - 2 ** (-10 * u)


def back_out(u, s=1.70158):
    u = clamp(u) - 1
    return u * u * ((s + 1) * u + s) + 1


def elastic_settle(u, freq=3.0, damp=5.0):
    """Overshoot-and-settle curve: 0 -> 1 with damped oscillation."""
    u = clamp(u)
    return 1 - math.exp(-damp * u) * math.cos(freq * 2 * math.pi * u)


def pulse(t, t0, attack=0.04, decay=0.35):
    """Impact envelope: fast rise at t0 then exponential decay."""
    if t < t0:
        return 0.0
    dt = t - t0
    if dt < attack:
        return dt / attack
    return math.exp(-(dt - attack) / max(decay, 1e-4))


def window(t, a, b, fade_in=0.3, fade_out=0.3):
    """Trapezoid envelope that is 1 between a and b."""
    return clamp(prog(t, a - fade_in, fade_in)) * (1 - prog(t, b, fade_out))


def lerp(a, b, u):
    return a + (b - a) * u


def lerp3(a, b, u):
    return tuple(lerp(x, y, u) for x, y in zip(a, b))


def hash01(i, seed=0):
    """Deterministic pseudo random in [0,1) for integer i."""
    x = math.sin(i * 12.9898 + seed * 78.233) * 43758.5453
    return x - math.floor(x)


def shake(t, amp, freq=11.0, seed=1):
    """Smooth pseudo-random 2D shake offset (normalised units)."""
    x = (math.sin(t * freq * 1.31 + seed) * 0.6 + math.sin(t * freq * 2.71 + seed * 3.1) * 0.3
         + math.sin(t * freq * 5.17 + seed * 7.7) * 0.1)
    y = (math.sin(t * freq * 1.13 + seed * 2.3) * 0.6 + math.sin(t * freq * 2.93 + seed * 5.3) * 0.3
         + math.sin(t * freq * 4.79 + seed * 1.9) * 0.1)
    return amp * x, amp * y


# --------------------------------------------------------------------------
# Colour helpers
# --------------------------------------------------------------------------
def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], F32)


def col(c):
    if isinstance(c, str):
        return hexc(c)
    return np.asarray(c, F32)


def luma(img):
    return img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722


# --------------------------------------------------------------------------
# Buffers / grids
# --------------------------------------------------------------------------
def blank(h, w, c=3):
    return np.zeros((h, w, c), F32) if c else np.zeros((h, w), F32)


@lru_cache(maxsize=16)
def grid(h, w):
    """Normalised coordinate grids. x in [-aspect, aspect], y in [-1, 1] (y down)."""
    ys, xs = np.mgrid[0:h, 0:w].astype(F32)
    nx = (xs - w / 2) / (h / 2)
    ny = (ys - h / 2) / (h / 2)
    return nx, ny


@lru_cache(maxsize=16)
def pixgrid(h, w):
    ys, xs = np.mgrid[0:h, 0:w].astype(F32)
    return xs, ys


def vgrad(h, w, top, bottom, gamma=1.0):
    t = np.linspace(0, 1, h, dtype=F32) ** gamma
    g = col(top)[None, :] * (1 - t[:, None]) + col(bottom)[None, :] * t[:, None]
    return np.repeat(g[:, None, :], w, axis=1)


def radial(h, w, cx, cy, radius, inner, outer, power=1.5, aspect=1.0):
    """Radial gradient. cx, cy, radius in normalised units (see grid)."""
    nx, ny = grid(h, w)
    d = np.sqrt(((nx - cx) / aspect) ** 2 + (ny - cy) ** 2) / max(radius, 1e-4)
    t = np.clip(d, 0, 1) ** power
    return col(inner)[None, None, :] * (1 - t[..., None]) + col(outer)[None, None, :] * t[..., None]


def soft_spot(h, w, cx, cy, rx, ry=None, power=2.0):
    """Soft elliptical falloff mask, 1 at centre -> 0."""
    ry = rx if ry is None else ry
    nx, ny = grid(h, w)
    d2 = ((nx - cx) / rx) ** 2 + ((ny - cy) / ry) ** 2
    return np.exp(-d2 * power).astype(F32)


# --------------------------------------------------------------------------
# Blur family
# --------------------------------------------------------------------------
def blur(img, sigma):
    """Gaussian blur; large sigmas are computed at reduced resolution."""
    if sigma <= 0.3:
        return img
    h, w = img.shape[:2]
    if sigma > 12:
        f = int(min(8, sigma / 6))
        small = cv2.resize(img, (max(1, w // f), max(1, h // f)), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (0, 0), sigma / f)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(img, (0, 0), sigma)


def blur_dir(img, length, angle_deg=0.0):
    """Directional (linear motion) blur of `length` pixels."""
    if length < 1.5:
        return img
    h, w = img.shape[:2]
    f = 1
    if length > 24:
        f = 2 if length < 80 else 4
        img_s = cv2.resize(img, (w // f, h // f), interpolation=cv2.INTER_AREA)
    else:
        img_s = img
    L = max(3, int(length / f) | 1)
    k = np.zeros((L, L), F32)
    c = L // 2
    a = math.radians(angle_deg)
    for i in range(L):
        s = i - c
        x = int(round(c + s * math.cos(a)))
        y = int(round(c + s * math.sin(a)))
        k[y, x] = 1
    k /= k.sum()
    out = cv2.filter2D(img_s, -1, k, borderType=cv2.BORDER_REPLICATE)
    if f > 1:
        out = cv2.resize(out, (w, h), interpolation=cv2.INTER_LINEAR)
    return out


def blur_h(img, sigma):
    """Horizontal-only blur (anamorphic streak)."""
    if sigma < 0.5:
        return img
    h, w = img.shape[:2]
    f = 4 if sigma > 40 else 1
    s = cv2.resize(img, (w // f, h // f), interpolation=cv2.INTER_AREA) if f > 1 else img
    s = cv2.GaussianBlur(s, (0, 1), sigmaX=sigma / f, sigmaY=0.01)
    s = cv2.GaussianBlur(s, (0, 0), sigmaX=sigma / f, sigmaY=0.6)
    return cv2.resize(s, (w, h), interpolation=cv2.INTER_LINEAR) if f > 1 else s


def zoom_blur(img, cx, cy, amount, steps=8):
    """Radial zoom blur around pixel centre (cx, cy). amount ~ 0.05..0.3."""
    if amount < 0.003:
        return img
    h, w = img.shape[:2]
    f = 2
    s = cv2.resize(img, (w // f, h // f), interpolation=cv2.INTER_AREA)
    acc = np.zeros_like(s)
    for i in range(steps):
        sc = 1 + amount * i / (steps - 1)
        M = np.array([[sc, 0, (1 - sc) * cx / f], [0, sc, (1 - sc) * cy / f]], F32)
        acc += cv2.warpAffine(s, M, (w // f, h // f), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    acc /= steps
    return cv2.resize(acc, (w, h), interpolation=cv2.INTER_LINEAR)


def god_rays(src, cx, cy, length=0.35, decay=0.93, steps=24, scale=4):
    """Volumetric light-shaft approximation: iterative radial smear of src
    (an occlusion/light image) towards pixel centre (cx, cy)."""
    h, w = src.shape[:2]
    s = cv2.resize(src, (w // scale, h // scale), interpolation=cv2.INTER_AREA)
    acc = s.copy()
    cur = s
    sh, sw = s.shape[:2]
    wsum = 1.0
    wt = 1.0
    sc = 1 + length / steps
    M = np.array([[1 / sc, 0, (1 - 1 / sc) * cx / scale], [0, 1 / sc, (1 - 1 / sc) * cy / scale]], F32)
    for _ in range(steps):
        cur = cv2.warpAffine(cur, M, (sw, sh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        wt *= decay
        acc += cur * wt
        wsum += wt
    acc /= wsum
    return cv2.resize(acc, (w, h), interpolation=cv2.INTER_LINEAR)


# --------------------------------------------------------------------------
# Compositing
# --------------------------------------------------------------------------
def over(dst, rgb, alpha, opacity=1.0):
    """Composite straight rgb with alpha over dst in place-free manner."""
    a = alpha[..., None] * opacity if alpha.ndim == 2 else alpha * opacity
    return dst * (1 - a) + rgb * a


def over_premul(dst, prgb, alpha, opacity=1.0):
    a = alpha[..., None] if alpha.ndim == 2 else alpha
    return dst * (1 - a * opacity) + prgb * opacity


def screen(a, b):
    return 1 - (1 - np.clip(a, 0, 1)) * (1 - np.clip(b, 0, 1)) + np.maximum(a - 1, 0) + np.maximum(b - 1, 0)


def tint(mask, c, gain=1.0):
    return mask[..., None] * (col(c) * gain)[None, None, :]


# --------------------------------------------------------------------------
# Procedural noise (periodic FFT noise, sampled with wrap-around)
# --------------------------------------------------------------------------
@lru_cache(maxsize=64)
def fft_noise(size=512, beta=2.0, seed=0, ridged=False):
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((size, size))
    fy = np.fft.fftfreq(size)[:, None]
    fx = np.fft.fftfreq(size)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    spec = np.fft.fft2(white) / (f ** (beta / 2.0))
    if beta >= 1.9:  # soft atmospherics: roll off the grain
        spec = spec * np.exp(-(f / (0.045 + 0.06 * (3.0 - min(beta, 3.0)))) ** 2)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    n = (n - n.mean()) / (n.std() * 3.2) + 0.5
    n = np.clip(n, 0, 1)
    if ridged:
        n = 1 - np.abs(n * 2 - 1)
    return n.astype(F32)


def sample(tex, h, w, scale=1.0, ox=0.0, oy=0.0, angle=0.0, stretch=(1.0, 1.0)):
    """Sample periodic texture to an h x w image.

    scale: how many texture periods span the frame height.
    ox, oy: offset in texture periods (animate these for drift).
    """
    th, tw = tex.shape[:2]
    nx, ny = grid(h, w)
    ca, sa = math.cos(angle), math.sin(angle)
    u = (nx * ca - ny * sa) * 0.5 * scale / stretch[0] + ox
    v = (nx * sa + ny * ca) * 0.5 * scale / stretch[1] + oy
    mx = (u * tw).astype(F32)
    my = (v * th).astype(F32)
    return cv2.remap(tex, mx, my, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def fbm_field(h, w, t, scale=2.0, speed=(0.02, 0.0), seed=0, beta=2.2, evolve=0.05, warp=0.0):
    """Animated soft noise field in [0,1], computed at quarter resolution."""
    hs, ws = max(8, h // 4), max(8, w // 4)
    a = fft_noise(256, beta, seed)
    b = fft_noise(256, beta, seed + 101)
    u = 0.5 + 0.5 * math.sin(t * evolve * 2 * math.pi)
    n1 = sample(a, hs, ws, scale, speed[0] * t, speed[1] * t)
    n2 = sample(b, hs, ws, scale * 1.13, speed[0] * t * 1.3 + 0.37, speed[1] * t * 1.3 + 0.11)
    n = n1 * (1 - u) + n2 * u
    if warp > 0:
        wn = sample(fft_noise(256, 2.5, seed + 7), hs, ws, scale * 0.7, t * 0.01, -t * 0.013)
        xs, ys = pixgrid(hs, ws)
        n = cv2.remap(n, xs + (wn - 0.5) * warp * ws, ys + (wn - 0.5) * warp * hs * 0.6,
                      interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)


def remap_offset(img, dx, dy):
    """Displace img by per-pixel offsets dx, dy (pixels)."""
    h, w = img.shape[:2]
    xs, ys = pixgrid(h, w)
    return cv2.remap(img, xs + dx, ys + dy, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
