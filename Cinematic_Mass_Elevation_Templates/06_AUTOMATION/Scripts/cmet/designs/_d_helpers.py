"""Small helpers shared by templates T31-T39 only (atmosphere planes with true
camera parallax, flat-colour subtitles, Fusion fog/haze layers)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import fcomp as F
from ..fusion import ctl, prog, window

F32 = np.float32


# ------------------------------------------------------------------ preview --
def plane(H, W, t, scale=1.5, drift=(0.01, 0.0), seed=1, zoom=1.0, pan=(0.0, 0.0), beta=2.3, evolve=0.03,
          stretch=(1.0, 1.0), angle=0.0, res=4):
    """Animated soft noise plane in [0,1] (computed at 1/res resolution).

    `zoom` scales the plane about frame centre and `pan` offsets it (in frame
    heights): give near planes a larger zoom/pan than far planes to get real
    camera parallax between atmosphere layers."""
    hs, ws = max(8, H // res), max(8, W // res)
    a = K.fft_noise(256, beta, seed)
    b = K.fft_noise(256, beta, seed + 101)
    u = 0.5 + 0.5 * math.sin(t * evolve * 2 * math.pi)
    sc = scale / max(zoom, 1e-3)
    ox = drift[0] * t + pan[0] * 0.5 * sc
    oy = drift[1] * t + pan[1] * 0.5 * sc
    n1 = K.sample(a, hs, ws, sc, ox, oy, angle, stretch)
    n2 = K.sample(b, hs, ws, sc * 1.13, ox * 1.3 + 0.37, oy * 1.3 + 0.11, angle, stretch)
    n = n1 * (1 - u) + n2 * u
    return cv2.resize(n, (W, H), interpolation=cv2.INTER_CUBIC)


def shaped(n, lo=0.35, hi=0.85, gamma=1.0):
    v = np.clip((n - lo) / max(hi - lo, 1e-4), 0, 1)
    return v if gamma == 1.0 else v ** gamma


def small_grid(H, W, res=4):
    return K.grid(max(8, H // res), max(8, W // res))


def up(m, H, W):
    return cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)


def cone(H, W, origin, direction, spread, length=2.5, softness=0.6, res=4):
    """Light-cone mask computed at reduced resolution."""
    from .. import elements as E
    m = E.light_cone(max(8, H // res), max(8, W // res), origin, direction, spread, length, softness)
    return up(m, H, W)


def over(img, color, dens):
    """Participating-media layer: occludes what is behind and adds its own light."""
    d = np.clip(dens, 0, 1)[..., None]
    return img * (1 - d) + d * np.asarray(color, F32)


def over_lit(img, rgb, dens):
    d = np.clip(dens, 0, 1)[..., None]
    return img * (1 - d) + rgb * d


def flat(sprite, color):
    rgb = np.empty((sprite.h, sprite.w, 3), F32)
    rgb[...] = K.col(color)
    return rgb


def sprite_noise(sprite, scale, seed=5, beta=1.8, ox=0.0, oy=0.0):
    """Noise texture sampled over a title sprite (for dissolve / frost reveals)."""
    return K.sample(K.fft_noise(256, beta, seed), sprite.h, sprite.w, scale * sprite.h / 1080.0 * 2, ox, oy)


def glow(img, sigma, gain):
    return img + K.blur(img, sigma) * gain


# ------------------------------------------------------------------- Fusion --
def f_fog(g, name, bg, c1, c2, scale, zoom_expr, drift=(0.0006, 0.0), blend="1", mode="Screen", detail=5,
          contrast=1.4, brightness=0.0, seethe=0.03, mask=None, aspect=None):
    """FastNoise atmosphere plane in its own Transform (zoom = parallax).
    mode="Normal" makes it a participating medium: noise colour 1 is given
    zero alpha, so dense fog occludes what is behind and thin fog does not."""
    n = F.noise(g, f"{name}Noise", c1, c2, detail=detail, scale=scale, seethe_rate=seethe, contrast=contrast,
                brightness=brightness, center=f"Point(0.5 + time*{drift[0]}, 0.5 + time*{drift[1]})")
    if mode == "Normal":
        n.set(Color1Alpha=0.0)
    if mask is not None:
        F.masked(n, mask)
    z = F.xf(g, f"{name}Depth", n, size=zoom_expr, edges=1)
    if aspect is not None:
        z.set(Aspect=aspect)
    return F.merge(g, name, bg, z, mode=mode, blend=blend)


def f_sub(g, p, font, style, color, y_off, t_in, t_out, size=0.03, tracking=1.5, scene=None, name="Subtitle"):
    sub, subp = F.subtitle_text(g, name, p["SUBTITLE"], font, style, size, tracking, color=color, y_off=y_off)
    return F.merge(g, f"{name}Merge", scene, subp, blend=window(t_in, t_out, 18, 12))
