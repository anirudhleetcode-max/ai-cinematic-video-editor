"""Procedural transition engine built on FFmpeg `xfade`.

Native xfade transitions are exposed directly; additional families (zoom, spin, whip, RGB split,
glitch, flash, film burn, light leak, kaleidoscope, blur) are implemented as `xfade=transition=custom`
per-pixel expressions. In xfade, `P` runs 1→0, so `Q = 1-P` is forward progress; `E` is the eased Q."""
from __future__ import annotations

from .base import Definition, Registry, e, f, num

TRANSITIONS = Registry("transition")

EASINGS = {
    "linear": "Q",
    "ease_in_out": "(Q*Q*(3-2*Q))",
    "ease_out": "(1-(1-Q)*(1-Q))",
    "ease_in": "(Q*Q)",
    "expo_out": "(1-pow(2,-10*Q))",
}

DUR = f("duration", 0.6, 0.1, 2.5, 0.1)
EASE = e("easing", "ease_in_out", *EASINGS)


def _native(name: str):
    return lambda p: {"transition": name}


def _reg(id_, name, cat, params, build, tags=(), desc="", cost=1.0):
    TRANSITIONS.register(Definition(id_, name, cat, tuple(params), tuple(tags), desc, cost, build))


# ---- cut / crossfade / dips / fades ----------------------------------------------------------
_reg("cut", "Cut", "cut", [], lambda p: {"transition": None}, ("minimal", "clean", "invisible"), "Hard cut — usually the right choice.")
_reg("crossfade", "Crossfade", "crossfade", [DUR], _native("fade"), ("subtle", "cinematic", "emotional", "soft"))
_reg("dissolve", "Dissolve", "crossfade", [DUR], _native("dissolve"), ("subtle", "vintage", "dreamy"))
_reg("fade_fast", "Fast Fade", "fade", [DUR], _native("fadefast"), ("subtle",))
_reg("fade_slow", "Slow Fade", "fade", [DUR], _native("fadeslow"), ("emotional", "slow"))
_reg("fade_grays", "Fade Through Grey", "fade", [DUR], _native("fadegrays"), ("documentary", "memory"))
_reg("dip_to_black", "Dip to Black", "dip", [DUR], _native("fadeblack"), ("chapter", "emotional", "ending", "cinematic"))
_reg("dip_to_white", "Dip to White", "dip", [DUR], _native("fadewhite"), ("dreamy", "wedding", "flash", "memory"))
for d_ in ("left", "right", "up", "down"):
    _reg(f"wipe_{d_}", f"Wipe {d_.title()}", "wipe", [DUR], _native(f"wipe{d_}"), ("graphic", "clean"))
    _reg(f"slide_{d_}", f"Slide {d_.title()}", "slide", [DUR], _native(f"slide{d_}"), ("dynamic", "energetic"))
    _reg(f"push_{d_}", f"Smooth Push {d_.title()}", "push", [DUR], _native(f"smooth{d_}"), ("dynamic", "modern", "clean"))
    _reg(f"cover_{d_}", f"Cover {d_.title()}", "push", [DUR], _native(f"cover{d_}"), ("dynamic", "modern"))
    _reg(f"reveal_{d_}", f"Reveal {d_.title()}", "push", [DUR], _native(f"reveal{d_}"), ("dynamic", "modern"))
for d_ in ("tl", "tr", "bl", "br"):
    _reg(f"wipe_diag_{d_}", f"Diagonal Wipe {d_.upper()}", "wipe", [DUR], _native(f"wipe{d_}"), ("graphic",))
    _reg(f"diag_{d_}", f"Diagonal {d_.upper()}", "shape", [DUR], _native(f"diag{d_}"), ("graphic",))
for n_, t_ in (("circle_open", "circleopen"), ("circle_close", "circleclose"), ("circle_crop", "circlecrop"), ("rect_crop", "rectcrop"),
               ("vert_open", "vertopen"), ("vert_close", "vertclose"), ("horz_open", "horzopen"), ("horz_close", "horzclose")):
    _reg(n_, n_.replace("_", " ").title(), "shape" if "circle" in n_ or "rect" in n_ else "mask", [DUR], _native(t_), ("graphic", "mask", "shape"))
for n_, t_ in (("slice_hl", "hlslice"), ("slice_hr", "hrslice"), ("slice_vu", "vuslice"), ("slice_vd", "vdslice")):
    _reg(n_, f"Slice {n_[-2:].upper()}", "mask", [DUR], _native(t_), ("graphic", "energetic"))
for n_, t_ in (("wind_hl", "hlwind"), ("wind_hr", "hrwind"), ("wind_vu", "vuwind"), ("wind_vd", "vdwind")):
    _reg(n_, f"Wind {n_[-2:].upper()}", "distortion", [DUR], _native(t_), ("energetic", "texture"))
_reg("radial", "Radial Wipe", "radial", [DUR], _native("radial"), ("graphic", "clock"))
_reg("squeeze_h", "Squeeze Horizontal", "distortion", [DUR], _native("squeezeh"), ("playful",))
_reg("squeeze_v", "Squeeze Vertical", "distortion", [DUR], _native("squeezev"), ("playful",))
_reg("morph", "Morph (distance)", "morph", [DUR], _native("distance"), ("smooth", "abstract"))
_reg("pixel_dissolve", "Pixelize", "glitch", [DUR], _native("pixelize"), ("digital", "glitch", "tech"))
_reg("hblur", "Horizontal Blur", "blur", [DUR], _native("hblur"), ("motion", "energetic"))
_reg("zoom_in_native", "Zoom In (native)", "zoom", [DUR], _native("zoomin"), ("energetic", "impact"))


# ---- procedural (numpy/OpenCV) families --------------------------------------------------------
# These render only the overlap frames: fn(a, b, q, params) -> frame, where a/b are float32 RGB frames
# in [0,1] and q is eased forward progress 0..1. See render/transitions.py for the frame loop.
import cv2  # noqa: E402
import numpy as np  # noqa: E402


def _ease(q: float, kind: str) -> float:
    return {"linear": q, "ease_in_out": q * q * (3 - 2 * q), "ease_out": 1 - (1 - q) ** 2, "ease_in": q * q,
            "expo_out": 1 - 2 ** (-10 * q)}[kind]


def _affine(img, m):
    h, w = img.shape[:2]
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def _scale_about_center(img, s):
    h, w = img.shape[:2]
    return _affine(img, cv2.getRotationMatrix2D((w / 2, h / 2), 0, s))


def _np_zoom(a, b, q, p):
    k = p["amount"]
    if p["direction"] == "out":
        sa, sb = 1 / (1 + k * q), 1 / (1 + k * (1 - q))
    else:
        sa, sb = 1 + k * q, 1 + k * (1 - q)
    w = np.clip((q - 0.4) / 0.2, 0, 1)
    ra = cv2.GaussianBlur(_scale_about_center(a, sa), (0, 0), 0.1 + 6 * q * (1 - q))
    rb = cv2.GaussianBlur(_scale_about_center(b, sb), (0, 0), 0.1 + 6 * q * (1 - q))
    return ra * (1 - w) + rb * w


def _np_spin(a, b, q, p):
    h, wd = a.shape[:2]
    ang = p["angle"]
    ma = cv2.getRotationMatrix2D((wd / 2, h / 2), ang * q, 1 + 0.15 * np.sin(np.pi * q))
    mb = cv2.getRotationMatrix2D((wd / 2, h / 2), -ang * (1 - q), 1 + 0.15 * np.sin(np.pi * q))
    w = np.clip((q - 0.35) / 0.3, 0, 1)
    return _affine(a, ma) * (1 - w) + _affine(b, mb) * w


def _motion_blur_h(img, k):
    k = int(max(1, k))
    return cv2.blur(img, (k, 1)) if k > 1 else img


def _np_whip(a, b, q, p):
    h, w = a.shape[:2]
    sgn = -1 if p["direction"] == "left" else 1
    blur = p["blur"] * (w / 640) * np.sin(np.pi * q) * 3
    if q < 0.5:
        img, dx = a, sgn * w * q
    else:
        img, dx = b, sgn * w * (q - 1)
    m = np.float32([[1, 0, dx], [0, 1, 0]])
    return _motion_blur_h(_affine(img, m), blur)


def _np_blur(a, b, q, p):
    sig = 0.1 + p["radius"] * (a.shape[1] / 640) * np.sin(np.pi * q)
    return cv2.GaussianBlur(a, (0, 0), sig) * (1 - q) + cv2.GaussianBlur(b, (0, 0), sig) * q


def _shift(ch, dx):
    return np.roll(ch, int(round(dx)), axis=1)


def _np_rgb(a, b, q, p):
    d = p["shift"] * (a.shape[1] / 640) * np.sin(np.pi * q)
    m = a * (1 - q) + b * q
    out = m.copy()
    out[..., 0] = _shift(m[..., 0], d)
    out[..., 2] = _shift(m[..., 2], -d)
    return out


def _np_glitch(a, b, q, p):
    rng = np.random.default_rng(int(q * 1000))
    src = (a if q < 0.5 else b).copy()
    h, w = src.shape[:2]
    blk = max(2, int(p["block"] * h / 360))
    amp = p["strength"] * w * np.sin(np.pi * q)
    for y in range(0, h, blk):
        if rng.random() < 0.35:
            src[y:y + blk] = np.roll(src[y:y + blk], int(rng.uniform(-amp, amp)), axis=1)
    if rng.random() < 0.5:
        src[..., 0] = np.roll(src[..., 0], int(amp * 0.1), axis=1)
    return src


def _np_flash(a, b, q, p):
    peak = max(0.0, 1 - abs(q - 0.5) * p["sharpness"]) * p["strength"]
    return np.clip(a * (1 - q) + b * q + peak, 0, 1)


def _np_burn(a, b, q, p):
    h, w = a.shape[:2]
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    grad = 0.5 + 0.5 * np.sin(x * np.pi * 2 + q * 6)
    peak = max(0.0, 1 - abs(q - 0.5) * 2.2) * p["strength"]
    warm = np.array([1.0, 0.55, 0.2], np.float32)
    return np.clip(a * (1 - q) + b * q + peak * grad * warm, 0, 1)


def _np_leak(a, b, q, p):
    h, w = a.shape[:2]
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :, None]
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    cx = p["position"] + 0.3 * (q - 0.5)
    blob = np.exp(-(((x - cx) / 0.35) ** 2 + ((y - 0.4) / 0.6) ** 2))
    warm = np.array([1.0, 0.62, 0.3], np.float32)
    return np.clip(a * (1 - q) + b * q + p["strength"] * np.sin(np.pi * q) * blob * warm, 0, 1)


def _np_kaleido(a, b, q, p):
    h, w = a.shape[:2]
    k = np.sin(np.pi * q)
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    xm = w / 2 - np.abs(xs - w / 2) * p["mirror"]
    ym = h / 2 - np.abs(ys - h / 2) * p["mirror"]
    mx, my = (xs * (1 - k) + xm * k).astype(np.float32), (ys * (1 - k) + ym * k).astype(np.float32)
    ra = cv2.remap(a, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    rb = cv2.remap(b, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return ra * (1 - q) + rb * q


def _np_mask(a, b, q, p):
    h, w = a.shape[:2]
    xs, ys = np.meshgrid(np.linspace(0, 1, w, dtype=np.float32), np.linspace(0, 1, h, dtype=np.float32))
    if p["shape"] == "diamond":
        m = (np.abs(xs - 0.5) + np.abs(ys - 0.5)) <= q * 1.05
    elif p["shape"] == "bars":
        m = np.mod(xs * p["count"], 1) <= q
    else:
        m = np.mod(ys * p["count"], 1) <= q
    m = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.0)[..., None]
    return a * (1 - m) + b * m


def _proc(fn):
    return lambda p: {"engine": "numpy", "fn": fn, "easing": p.get("easing", "ease_in_out")}


_reg("zoom", "Zoom Through", "zoom", [DUR, f("amount", 0.6, 0.1, 2.0, 0.1), e("direction", "in", "in", "out"), EASE], _proc(_np_zoom),
     ("energetic", "impact", "hype", "dynamic"), cost=1.5)
_reg("spin", "Spin", "rotate", [DUR, f("angle", 90.0, 10, 360, 10), EASE], _proc(_np_spin), ("energetic", "playful", "rotate"), cost=1.5)
_reg("rotate", "Rotate Settle", "rotate", [DUR, f("angle", 20.0, 5, 60, 5), EASE], _proc(_np_spin), ("dynamic", "rotate"), cost=1.5)
_reg("whip", "Whip Pan", "whip", [f("duration", 0.35, 0.15, 1.0, 0.05), e("direction", "left", "left", "right"), f("blur", 18.0, 4, 60, 2), EASE], _proc(_np_whip),
     ("energetic", "hype", "fast", "travel", "sports"), cost=1.5)
_reg("blur_dissolve", "Blur Dissolve", "blur", [DUR, f("radius", 8.0, 2, 30, 1), EASE], _proc(_np_blur), ("subtle", "cinematic", "dreamy", "soft"), cost=1.5)
_reg("rgb_split", "RGB Split", "rgb_split", [DUR, f("shift", 12.0, 2, 40, 2), EASE], _proc(_np_rgb), ("glitch", "music", "hype", "tech"), cost=1.2)
_reg("glitch", "Glitch", "glitch", [f("duration", 0.4, 0.15, 1.2, 0.05), f("strength", 0.15, 0.02, 0.5, 0.02), f("block", 16.0, 4, 64, 4), EASE], _proc(_np_glitch),
     ("glitch", "digital", "hype", "tech", "music"), cost=1.2)
_reg("flash", "Flash", "flash", [f("duration", 0.3, 0.1, 1.0, 0.05), f("strength", 0.9, 0.2, 1, 0.1), f("sharpness", 4.0, 2, 10, 1), EASE], _proc(_np_flash),
     ("impact", "beat", "hype", "music", "energetic"))
_reg("film_burn", "Film Burn", "film_burn", [f("duration", 0.8, 0.3, 2.0, 0.1), f("strength", 0.8, 0.2, 1, 0.1), EASE], _proc(_np_burn),
     ("film", "vintage", "wedding", "warm"))
_reg("light_leak", "Light Leak", "light_leak", [f("duration", 0.9, 0.3, 2.5, 0.1), f("strength", 0.7, 0.2, 1, 0.1), f("position", 0.6, 0, 1, 0.1), EASE], _proc(_np_leak),
     ("film", "warm", "wedding", "travel", "dreamy"))
_reg("kaleidoscope", "Kaleidoscope", "kaleidoscope", [DUR, f("mirror", 1.0, 0.5, 2.0, 0.25), EASE], _proc(_np_kaleido), ("trippy", "music", "festival"), cost=1.5)
_reg("shape_mask", "Shape Mask", "mask", [DUR, e("shape", "diamond", "diamond", "bars", "blinds"), f("count", 8.0, 2, 24, 1), EASE], _proc(_np_mask),
     ("graphic", "mask", "shape", "modern"))


def transition_spec(trans_id: str, params: dict) -> tuple[dict, dict, float]:
    """Return (spec, resolved_params, duration). spec = {} for a hard cut, {"engine":"xfade","transition":..}
    for native FFmpeg transitions or {"engine":"numpy","fn":..,"easing":..} for procedural ones."""
    d = TRANSITIONS.get(trans_id)
    p = d.resolve(params)
    spec = d.render(p)
    if spec.get("engine") != "numpy" and spec.get("transition") is None:
        return {}, p, 0.0
    if spec.get("engine") != "numpy":
        spec = {"engine": "xfade", **spec}
    return spec, p, float(p.get("duration", 0.6))
