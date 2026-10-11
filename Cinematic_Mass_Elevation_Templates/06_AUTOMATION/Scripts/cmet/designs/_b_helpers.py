"""Small helpers shared by the T11-T20 design modules only (not a public API).

Preview side: extruded/flat title placement honouring TEXT_POSITION/ROTATION and
EXTRUSION_DEPTH, floor reflections, glints, subtitle colouring.
Fusion side: font-name lookup, subtitle merge, mirrored-floor reflection.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from .. import core as K
from .. import fcomp as F
from ..base import subtitle
from ..fusion import ctl, window
from ..typo import FONTS, place_extruded, place_sprite

F32 = np.float32


# --------------------------------------------------------------- preview --
def put_title(c, L, cam, rgb, a, sp, scale=1.0, rot=(0, 0, 0), off=(0, 0, 0), depth=0.0, side=(0.05, 0.05, 0.05),
              slices=12, side_light=None, opacity=1.0, box=None):
    """Place the (optionally extruded) title. `depth` in pixels, already
    multiplied by EXTRUSION_DEPTH by the caller. Applies TEXT_POSITION and
    TEXT_ROTATION like Ctx.place."""
    hx, hy = c.hero()
    rot = (rot[0], rot[1], rot[2] + c.p["TEXT_ROTATION"])
    pos = (hx + off[0], hy + off[1], off[2])
    box = box or (0, 0, sp.w, sp.h)
    if opacity <= 0.002:
        return
    if depth > 0.5:
        place_extruded(L, cam, rgb, a, box, sp.anchor, pos, scale, rot, depth, side, slices=slices,
                       side_light=side_light, opacity=opacity)
    else:
        place_sprite(L, cam, rgb, a, box, sp.anchor, pos, scale, rot, None, opacity)


def layer_bbox(L, thr=0.02):
    ys = np.nonzero(L.a.max(1) > thr)[0]
    xs = np.nonzero(L.a.max(0) > thr)[0]
    if len(ys) == 0:
        return None
    return xs[0], ys[0], xs[-1], ys[-1]


def floor_reflection(img, L, y_floor, strength=0.35, fall=0.18, soft=4.0, k=1.0):
    """Mirror the title layer about the horizontal line y_floor (pixels) and add
    it below as a glossy-floor reflection that fades with distance."""
    H, W = L.a.shape
    y_floor = float(y_floor)
    if strength <= 0:
        return img
    M = np.float32([[1, 0, 0], [0, -1, 2 * y_floor]])
    r = cv2.warpAffine(L.rgb, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    ra = cv2.warpAffine(L.a, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    ys = np.arange(H, dtype=F32)
    d = np.clip((ys - y_floor) / (fall * H), 0, None)
    w = (np.exp(-d * 2.2) * (ys > y_floor)).astype(F32) * strength
    r = K.blur(r, soft * k)
    ra = K.blur(ra, soft * k)
    return img * (1 - (ra * w[:, None] * 0.6)[..., None]) + r * w[:, None, None]


def glint(H, W, x, y, size, color, intensity, rays=4, angle=0.0, thin=0.012):
    """Star-shaped specular glint (pixel coords)."""
    if intensity <= 0.003:
        return np.zeros((H, W, 3), F32)
    r = int(size * 1.2) + 4
    x0, y0 = int(max(0, x - r)), int(max(0, y - r))
    x1, y1 = int(min(W, x + r)), int(min(H, y + r))
    out = np.zeros((H, W, 3), F32)
    if x1 <= x0 or y1 <= y0:
        return out
    ys, xs = np.mgrid[y0:y1, x0:x1].astype(F32)
    dx, dy = (xs - x) / size, (ys - y) / size
    d = np.sqrt(dx * dx + dy * dy) + 1e-4
    m = np.exp(-(d / 0.06) ** 2) * 1.5 + np.exp(-d / 0.25) * 0.25
    for i in range(rays):
        a = angle + math.pi * i / rays
        ca, sa = math.cos(a), math.sin(a)
        along = dx * ca + dy * sa
        across = -dx * sa + dy * ca
        m = m + np.exp(-(across / (thin + 0.01 * np.abs(along))) ** 2) * np.clip(1 - np.abs(along), 0, 1) ** 2.5
    out[y0:y1, x0:x1] = m[..., None] * K.col(color)[None, None, :] * intensity
    return out


def sub_color(c, mix_acc=0.2, base=0.7):
    acc = K.col(c.p["ACCENT_COLOR"])
    return np.clip(base * (1 - mix_acc) + acc * mix_acc * base * 1.2, 0, 1.2)


def add_sub(c, img, cam, t_in, t_out, color, y_rel=0.82, tracking=0.35, rel=0.22, grow=0.04):
    return subtitle(c, img, cam, t_in, t_out, color, y_rel=y_rel, tracking=tracking, rel=rel, grow=grow)


def flat(sh, color):
    out = np.empty((sh[0], sh[1], 3), F32)
    out[...] = K.col(color)
    return out


# ---------------------------------------------------------------- Fusion --
def fam(key):
    f = FONTS.get(key, FONTS["anton"])
    return f[2], f[3]


def fusion_subtitle(g, scene, p, size=0.03, tracking=1.4, color=(0.75, 0.72, 0.68), y_off=-0.14, t_in=None,
                    t_out=None, fin=18, fout=12):
    sf, ss = fam(p["SUB_FONT_FAMILY"])
    sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], sf, ss, size, tracking, color=color, y_off=y_off)
    t_in = t_in or f"{ctl('ImpactFrame')} + 10"
    t_out = t_out or f"{ctl('ExitStart')} - 4"
    return F.merge(g, "SubtitleMerge", scene, subp, blend=window(t_in, t_out, fin, fout))


def fusion_floor_reflection(g, name, scene, title_img, base_off=0.1, blend="0.3"):
    """Vertically mirrored, blurred and graded copy of the title merged under it
    (glossy floor). The mirror axis sits `base_off` (normalised height) below the
    title centre, i.e. at CONTROLS.TextPosY - base_off. FlipVert mirrors about the
    frame centre, so the Transform centre is shifted by 2*axis - 1 (+0.5)."""
    fl = g.add("Transform", f"{name}Flip")
    fl.conn("Input", title_img)
    fl.set(FlipVert=1, Edges=0)
    fl.expr("Center", f"Point(0.5, 2*({ctl('TextPosY')} - {base_off}) - 0.5)", [0.5, 0.5])
    b = F.blur(g, f"{name}Soft", fl, 5)
    fade = F.ellipse(g, f"{name}Fade", (0.5, 0.5 - base_off - 0.12), 1.6, 0.26, 0.25)
    dim = F.bc(g, f"{name}Dim", b, gain=0.6)
    F.masked(dim, fade)
    return F.merge(g, name, scene, dim, mode="Screen", blend=blend)
