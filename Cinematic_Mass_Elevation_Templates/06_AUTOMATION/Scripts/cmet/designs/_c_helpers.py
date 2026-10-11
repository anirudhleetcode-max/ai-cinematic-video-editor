"""Helpers shared by templates T21-T30 only (preview + Fusion snippets)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import fcomp as F
from ..fusion import ctl

F32 = np.float32


# ------------------------------------------------------------------ preview --
def frac(x):
    return x - math.floor(x)


def flat(sprite, color, gain=1.0):
    rgb = np.empty((sprite.h, sprite.w, 3), F32)
    rgb[...] = K.col(color) * gain
    return rgb


def vband(sprite, top, bottom):
    """Vertical colour ramp over the title ink box (sprite-sized RGB)."""
    hh = sprite.h
    y = (np.arange(hh, dtype=F32) - sprite.ink[1]) / max(1.0, sprite.ink_h)
    y = np.clip(y, 0, 1)[:, None, None]
    g = K.col(top)[None, None, :] * (1 - y) + K.col(bottom)[None, None, :] * y
    return np.repeat(g, sprite.w, axis=1).astype(F32)


def inner_edge(sprite, width_cap=0.04):
    """Ring just inside the letter edge (neon tube / holo edge)."""
    w0 = max(1.5, width_cap * sprite.cap_px)
    d = sprite.dist
    return (np.clip(1 - np.abs(d - w0) / w0, 0, 1) ** 0.8 * sprite.mask).astype(F32)


def shift_rows(img, y0, y1, dx):
    y0, y1 = max(0, int(y0)), min(img.shape[0], int(y1))
    if y1 <= y0 or abs(dx) < 0.5:
        return
    img[y0:y1] = np.roll(img[y0:y1], int(round(dx)), axis=1)


def glitch_slices(img, amount, seed, k=1.0, n=5):
    """Purposeful horizontal slice displacement (amount 0..1)."""
    if amount <= 0.02:
        return img
    img = img.copy()
    r = np.random.default_rng(seed)
    H = img.shape[0]
    for _ in range(n):
        y = r.uniform(0.25, 0.75) * H
        h = r.uniform(4, 34) * k
        shift_rows(img, y, y + h, r.choice([-1, 1]) * r.uniform(15, 70) * k * amount)
    return img


def rgb_split(img, px, dy=0.0):
    """Shift red right / blue left by px pixels."""
    if abs(px) < 0.3 and abs(dy) < 0.3:
        return img
    H, W = img.shape[:2]
    out = img.copy()
    for ch, s in ((0, 1.0), (2, -1.0)):
        M = np.float32([[1, 0, px * s], [0, 1, dy * s]])
        out[..., ch] = cv2.warpAffine(img[..., ch], M, (W, H), borderMode=cv2.BORDER_REPLICATE)
    return out


def scanlines(H, W, period, phase=0.0, strength=0.3):
    y = np.arange(H, dtype=F32)
    s = 1 - strength * (0.5 + 0.5 * np.sin((y / period + phase) * 2 * math.pi))
    return np.repeat(s[:, None], W, axis=1)


def lines_buf(H, W, segs, color, width=1.0, k=1.0, intens=None):
    """segs: list of ((x0,y0),(x1,y1)) in pixels. Additive AA lines."""
    buf = np.zeros((H, W, 3), F32)
    c = K.col(color)
    for i, (a, b) in enumerate(segs):
        I = 1.0 if intens is None else float(intens[i])
        if I <= 0.004:
            continue
        cv2.line(buf, (int(a[0] * 4), int(a[1] * 4)), (int(b[0] * 4), int(b[1] * 4)),
                 tuple(float(v) for v in c * I), max(1, int(round(width * k))), cv2.LINE_AA, shift=2)
    return buf


def rect_outline(buf, x0, y0, x1, y1, color, w=1, corner=None):
    """Draw a rectangle outline (or only L-shaped corners of length `corner`)."""
    c = tuple(float(v) for v in K.col(color))
    p = lambda x, y: (int(x * 4), int(y * 4))
    if corner is None:
        cv2.rectangle(buf, p(x0, y0), p(x1, y1), c, w, cv2.LINE_AA, shift=2)
        return buf
    L = corner
    for (x, y, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        cv2.line(buf, p(x, y), p(x + sx * L, y), c, w, cv2.LINE_AA, shift=2)
        cv2.line(buf, p(x, y), p(x, y + sy * L), c, w, cv2.LINE_AA, shift=2)
    return buf


def title_rect_px(c, sp, scale=1.0, cam_zoom=1.0):
    """Approximate on-screen ink box of the title at rest (pixels)."""
    hx, hy = c.hero()
    s = scale * cam_zoom
    cx, cy = c.W / 2 + hx * cam_zoom, c.H / 2 + hy * cam_zoom
    return cx - sp.ink_w * s / 2, cy - sp.ink_h * s / 2, cx + sp.ink_w * s / 2, cy + sp.ink_h * s / 2


def place_rgba(c, L, cam, rgb, a, sp, scale=1.0, rot=(0, 0, 0), off=(0, 0, 0), opacity=1.0, add=False):
    c.place(L, cam, rgb, a, sp, scale, rot=rot, off=off, opacity=opacity, add=add)


# ------------------------------------------------------------------- Fusion --
def chain(masks):
    """Union-chain a list of mask tools (each mask's EffectMask = previous)."""
    for prev, m in zip(masks, masks[1:]):
        m.conn("EffectMask", prev, "Mask")
    return masks[-1]


def seg_mask(g, name, p0, p1, border=0.0015, soft=0.0015):
    return F.polyline_mask(g, name, [p0, p1], border=border, soft=soft)


def streak_noise(g, name, c1, c2, stretch=30.0, scale=12.0, seethe=0.4, center=None):
    """Horizontal interference streaks: FastNoise stretched by a Transform."""
    n = F.noise(g, name, c1, c2, detail=3, scale=scale, seethe_rate=seethe, contrast=2.4, center=center)
    t = g.add("Transform", f"{name}Stretch")
    t.conn("Input", n)
    t.set(UseSizeAndAspect=0, XSize=stretch, YSize=1.0, Edges=1)
    return t


def channel(g, name, inp, ch):
    """Isolate one RGB channel (ColorCorrector master channel gains)."""
    t = g.add("ColorCorrector", name)
    t.conn("Input", inp)
    gains = {"R": (1, 0, 0), "G": (0, 1, 0), "B": (0, 0, 1)}[ch]
    t.set(MasterRedGain=gains[0], MasterGreenGain=gains[1], MasterBlueGain=gains[2])
    return t


def accent_rect(g, name, center, w, h, border=None, soft=0.0, gain=1.0, angle=0.0):
    """Accent-coloured rectangle (outline if border is given). Returns the solid."""
    s = F.accent_solid(g, f"{name}Color", gain)
    m = F.rect(g, f"{name}Shape", center, w, h, soft, angle=angle)
    if border is not None:
        m.set(BorderWidth=border)
    F.masked(s, m)
    return s, m


def sub_window(start, end, fin=16, fout=12):
    from ..fusion import window
    return window(start, end, fin, fout)


def ex_expr():
    from ..fusion import prog
    return prog(ctl("ExitStart"), ctl("ExitDuration"))
