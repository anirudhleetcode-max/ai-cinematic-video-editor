"""Colour grading engine.

`grade()` is the single source of truth: a vectorised numpy implementation of the grading model.
It is baked into a 3D LUT (.cube) and applied by FFmpeg's `lut3d`, so preview thumbnails, LUT
export and the final render all use identical maths. Non-LUT operations (vignette, grain,
sharpening) are added as filters in the final pass.

Pipeline:  TechnicalGrade (per-shot normalisation)  →  CreativeGrade (preset)  →  finishing.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .base import Definition, Registry, f

COLOR_PRESETS = Registry("color_preset")

# Every grade parameter with its neutral value and bounds.
GRADE_PARAMS = {
    "exposure": (0.0, -2, 2), "contrast": (1.0, 0.5, 2.0), "pivot": (0.42, 0.2, 0.7),
    "highlights": (0.0, -1, 1), "shadows": (0.0, -1, 1), "whites": (0.0, -1, 1), "blacks": (0.0, -1, 1),
    "saturation": (1.0, 0, 2.5), "vibrance": (0.0, -1, 1), "temperature": (0.0, -1, 1), "tint": (0.0, -1, 1),
    "gamma": (1.0, 0.5, 2.0),
    "lift_r": (0.0, -0.2, 0.2), "lift_g": (0.0, -0.2, 0.2), "lift_b": (0.0, -0.2, 0.2),
    "gamma_r": (1.0, 0.6, 1.6), "gamma_g": (1.0, 0.6, 1.6), "gamma_b": (1.0, 0.6, 1.6),
    "gain_r": (1.0, 0.6, 1.5), "gain_g": (1.0, 0.6, 1.5), "gain_b": (1.0, 0.6, 1.5),
    "hue": (0.0, -180, 180),
    "split_shadow_hue": (190.0, 0, 360), "split_highlight_hue": (35.0, 0, 360), "split_amount": (0.0, 0, 1), "split_balance": (0.0, -1, 1),
    "orange_sat": (1.0, 0, 2), "blue_sat": (1.0, 0, 2), "green_sat": (1.0, 0, 2), "red_sat": (1.0, 0, 2),
    "fade": (0.0, 0, 0.3), "curve": (0.0, -1, 1),  # curve: +S-curve / -flatten
    "mono": (0.0, 0, 1),
    # finishing (not in LUT)
    "vignette": (0.0, 0, 1), "grain": (0.0, 0, 30), "sharpen": (0.0, 0, 2), "halation": (0.0, 0, 1),
}
FINISHING = ("vignette", "grain", "sharpen", "halation")


def clamp_params(p: dict) -> dict:
    out = {}
    for k, (d, lo, hi) in GRADE_PARAMS.items():
        v = p.get(k, d)
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = d
        out[k] = min(max(v, lo), hi)
    return out


def _luma(x: np.ndarray) -> np.ndarray:
    return x[..., 0] * 0.2126 + x[..., 1] * 0.7152 + x[..., 2] * 0.0722


def _hue_rgb(h_deg: float) -> np.ndarray:
    h = (h_deg % 360) / 60.0
    c = np.array([max(0, min(1, abs(h - 3) - 1)), max(0, min(1, 2 - abs(h - 2))), max(0, min(1, 2 - abs(h - 4)))], np.float32)
    return c - c.mean()


def _rgb_to_hsv(x):
    mx, mn = x.max(-1), x.min(-1)
    d = mx - mn + 1e-9
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / (mx + 1e-9), 0)
    return h, s, mx


def grade(x: np.ndarray, params: dict, intensity: float = 1.0) -> np.ndarray:
    """Apply the grading model to float RGB in [0,1] (any shape [..., 3])."""
    p = clamp_params(params)
    src = x.astype(np.float32)
    y = src.copy()
    y *= 2.0 ** p["exposure"]
    # white balance
    t, tn = p["temperature"], p["tint"]
    y *= np.array([1 + 0.12 * t, 1 - 0.06 * tn, 1 - 0.12 * t], np.float32)
    # lift / gamma / gain (per channel, CDL-like)
    lift = np.array([p["lift_r"], p["lift_g"], p["lift_b"]], np.float32)
    gain = np.array([p["gain_r"], p["gain_g"], p["gain_b"]], np.float32)
    gam = np.array([p["gamma_r"], p["gamma_g"], p["gamma_b"]], np.float32) * p["gamma"]
    y = np.clip(y * gain + lift * (1 - y), 0, None)
    y = np.power(np.clip(y, 0, 4), 1.0 / gam)
    # contrast around pivot + S-curve
    y = p["pivot"] + (y - p["pivot"]) * p["contrast"]
    if p["curve"]:
        yc = np.clip(y, 0, 1)
        s = yc * yc * (3 - 2 * yc)
        y = y + (s - yc) * p["curve"]
    # tonal ranges via luminance masks
    l = np.clip(_luma(y), 0, 1)[..., None]
    y = y + p["shadows"] * 0.25 * (1 - l) ** 2 + p["highlights"] * 0.25 * l ** 2 * (1 - l) * 2
    y = (y - p["blacks"] * -0.06) / (1 + p["whites"] * 0.12 + p["blacks"] * 0.06)
    y = y + p["whites"] * 0.1 * l ** 3
    # split toning
    if p["split_amount"]:
        l = np.clip(_luma(y), 0, 1)[..., None]
        bal = 0.5 + 0.25 * p["split_balance"]
        sh_w = np.clip((bal - l) / bal, 0, 1)
        hl_w = np.clip((l - bal) / (1 - bal), 0, 1)
        y = y + p["split_amount"] * 0.18 * (sh_w * _hue_rgb(p["split_shadow_hue"]) + hl_w * _hue_rgb(p["split_highlight_hue"]))
    # hue rotation (YIQ)
    if p["hue"]:
        a = np.deg2rad(p["hue"])
        yiq = np.array([[0.299, 0.587, 0.114], [0.596, -0.274, -0.322], [0.211, -0.523, 0.312]], np.float32)
        rot = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]], np.float32)
        m = np.linalg.inv(yiq) @ rot @ yiq
        y = y @ m.T.astype(np.float32)
    # saturation + vibrance + selective colour
    l = _luma(y)[..., None]
    chroma = y - l
    sat = np.sqrt((chroma ** 2).sum(-1, keepdims=True)) / 0.5
    vib = 1 + p["vibrance"] * (1 - np.clip(sat, 0, 1))
    factor = p["saturation"] * vib * (1 - p["mono"])
    if any(p[k] != 1.0 for k in ("orange_sat", "blue_sat", "green_sat", "red_sat")):
        h, _, _ = _rgb_to_hsv(np.clip(y, 0, 1))

        def band(c, w):
            d = np.minimum(np.abs(h - c), 360 - np.abs(h - c))
            return np.clip(1 - d / w, 0, 1)[..., None]

        sel = 1 + (p["orange_sat"] - 1) * band(30, 30) + (p["blue_sat"] - 1) * band(215, 40) + (p["green_sat"] - 1) * band(120, 40) + (p["red_sat"] - 1) * band(0, 20)
        factor = factor * sel
    y = l + chroma * factor
    # fade (lifted blacks / matte)
    y = y * (1 - p["fade"]) + p["fade"] * 0.9 * (1 - y) * 0.5 + p["fade"] * 0.5 * 0.3
    y = np.clip(y, 0, 1)
    if intensity != 1.0:
        y = np.clip(src + (y - src) * intensity, 0, 1)
    return y


def write_cube(path: Path, params: dict, intensity: float = 1.0, size: int = 33, pre: dict | None = None) -> Path:
    """Bake `pre` (technical) then `params` (creative) into a .cube 3D LUT."""
    r = np.linspace(0, 1, size, dtype=np.float32)
    # .cube order: red changes fastest
    b, g, rr = np.meshgrid(r, r, r, indexing="ij")
    rgb = np.stack([rr, g, b], -1).reshape(-1, 3)
    if pre:
        rgb = grade(rgb, pre)
    out = grade(rgb, params, intensity) if params else rgb
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        fh.write(f'TITLE "editor-engine"\nLUT_3D_SIZE {size}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
        np.savetxt(fh, out, fmt="%.6f")
    return path


def finishing_filters(params: dict, w: int, h: int, intensity: float = 1.0) -> list[str]:
    """Finishing filters scale with the grade intensity (intensity 0 = no grade at all, finishing included)."""
    p = clamp_params(params)
    k = max(0.0, min(1.5, intensity))
    for key in ("halation", "sharpen", "vignette", "grain"):
        p[key] = p[key] * k
    out = []
    if p["halation"] > 0:
        out.append(("halation", p["halation"]))
    fl = []
    if p["sharpen"] > 0:
        fl.append(f"unsharp=5:5:{p['sharpen']:.3f}:5:5:0")
    if p["vignette"] > 0:
        fl.append(f"vignette=angle={0.2 + 0.6 * p['vignette']:.3f}")
    if p["grain"] > 0:
        fl.append(f"noise=alls={int(p['grain'])}:allf=t+u")
    return fl


def _preset(id_, name, tags, desc, **params):
    defaults = clamp_params(params)
    COLOR_PRESETS.register(Definition(
        id_, name, "color", tuple(f(k, defaults[k], GRADE_PARAMS[k][1], GRADE_PARAMS[k][2]) for k in params), tuple(tags), desc, 1.0,
        lambda p, _d=defaults: {**_d, **p},
    ))


_preset("cinematic_neutral", "Cinematic Neutral", ("cinematic", "neutral", "clean"), "Gentle S-curve, controlled highlights, slight desaturation.",
        contrast=1.06, curve=0.25, highlights=-0.25, saturation=0.95, vibrance=0.1, vignette=0.15)
_preset("modern_film", "Modern Film", ("cinematic", "film"), "Soft roll-off, slight fade, warm highlights, cool shadows.",
        contrast=1.05, curve=0.3, fade=0.04, split_amount=0.25, split_shadow_hue=200, split_highlight_hue=38, saturation=0.92, grain=6, vignette=0.2)
_preset("warm_documentary", "Warm Documentary", ("documentary", "warm", "natural"), "Natural contrast with a warm bias.",
        temperature=0.25, contrast=1.04, saturation=1.02, vibrance=0.15, highlights=-0.15)
_preset("cool_documentary", "Cool Documentary", ("documentary", "cool", "natural"), "Neutral contrast with a cool bias.",
        temperature=-0.22, contrast=1.04, saturation=0.95, highlights=-0.15)
_preset("teal_orange", "Teal & Orange", ("cinematic", "blockbuster", "teal", "orange"), "Complementary split-tone; skin stays warm.",
        contrast=1.1, curve=0.35, split_amount=0.55, split_shadow_hue=192, split_highlight_hue=30, orange_sat=1.15, blue_sat=1.1, saturation=1.0, vignette=0.2)
_preset("golden_hour", "Golden Hour", ("warm", "golden", "travel", "wedding"), "Warm gain, lifted shadows, glowing highlights.",
        temperature=0.4, gain_r=1.06, gain_b=0.92, shadows=0.15, saturation=1.08, orange_sat=1.2, halation=0.25, vignette=0.15)
_preset("night_cinema", "Night Cinema", ("night", "moody", "cool", "cinematic"), "Deep blue shadows, crushed blacks, neon-friendly.",
        exposure=-0.15, contrast=1.15, blacks=0.3, temperature=-0.3, split_amount=0.4, split_shadow_hue=225, split_highlight_hue=45, saturation=0.9)
_preset("moody", "Moody", ("moody", "dark", "dramatic"), "Low-key, desaturated, heavy vignette.",
        exposure=-0.2, contrast=1.15, curve=0.4, saturation=0.75, highlights=-0.3, vignette=0.45, fade=0.03)
_preset("clean_commercial", "Clean Commercial", ("commercial", "bright", "corporate", "product"), "Bright, crisp, neutral whites.",
        exposure=0.1, contrast=1.05, whites=0.2, shadows=0.15, saturation=1.06, vibrance=0.2, sharpen=0.4)
_preset("soft_wedding", "Soft Wedding", ("wedding", "soft", "romantic", "pastel"), "Airy, lifted, soft pastel warmth.",
        exposure=0.15, contrast=0.9, fade=0.06, temperature=0.12, saturation=0.88, highlights=-0.25, halation=0.2)
_preset("concert", "Concert", ("concert", "music", "night", "vivid"), "Punchy contrast, saturated stage colours.",
        contrast=1.2, curve=0.35, saturation=1.25, vibrance=0.3, blacks=0.2, vignette=0.3)
_preset("sports", "Sports", ("sports", "energetic", "punchy"), "High clarity, punchy contrast and saturation.",
        contrast=1.15, saturation=1.15, vibrance=0.25, sharpen=0.6, whites=0.1)
_preset("corporate", "Corporate", ("corporate", "clean", "neutral"), "Neutral, accurate, slightly bright.",
        exposure=0.05, contrast=1.02, saturation=1.0, highlights=-0.1)
_preset("vintage_film", "Vintage Film", ("vintage", "retro", "film", "nostalgic"), "Faded blacks, warm cast, muted greens, grain.",
        fade=0.1, temperature=0.18, contrast=0.95, saturation=0.82, green_sat=0.7, grain=12, vignette=0.35, halation=0.2)
_preset("black_and_white", "Black & White", ("bw", "monochrome", "documentary", "classic"), "Rich contrast monochrome.",
        mono=1.0, contrast=1.18, curve=0.3, grain=6, vignette=0.25)
_preset("high_contrast", "High Contrast", ("contrast", "punchy", "bold"), "Strong S-curve and deep blacks.",
        contrast=1.3, curve=0.5, blacks=0.25, saturation=1.05)
_preset("pastel", "Pastel", ("pastel", "soft", "light"), "Lifted, low-contrast, pastel colour.",
        exposure=0.2, contrast=0.85, fade=0.08, saturation=0.8, vibrance=0.25, highlights=-0.2)
_preset("muted", "Muted", ("muted", "desaturated", "calm"), "Desaturated, soft contrast.", saturation=0.65, contrast=0.95, fade=0.04)
_preset("bleach_bypass", "Bleach Bypass", ("gritty", "war", "dramatic"), "Silver retention look: low saturation, high contrast.",
        saturation=0.45, contrast=1.3, curve=0.3, blacks=0.15, grain=10)
_preset("cyberpunk", "Cyberpunk", ("neon", "night", "tech", "music"), "Magenta highlights, teal shadows.",
        split_amount=0.7, split_shadow_hue=185, split_highlight_hue=310, saturation=1.2, contrast=1.15, temperature=-0.1)
_preset("natural", "Natural (technical only)", ("natural", "neutral", "none"), "No creative look — technical normalisation only.")


def preset_params(preset_id: str, overrides: dict | None = None) -> dict:
    d = COLOR_PRESETS.get(preset_id)
    return clamp_params(d.render({**(overrides or {})}))


def technical_correction(stats: dict, target: dict) -> dict:
    """Shot matching: map a clip's measured statistics (luma, temperature, tint, saturation, contrast)
    onto the project target. Values are deliberately conservative (partial correction)."""
    out: dict[str, float] = {}
    l, tl = max(1e-3, stats.get("luma", 0.45)), max(1e-3, target.get("luma", 0.45))
    out["exposure"] = float(np.clip(np.log2(tl / l) * 0.7, -1.0, 1.0))
    out["temperature"] = float(np.clip((target.get("temperature", 0) - stats.get("temperature", 0)) * 3.0, -0.6, 0.6))
    out["tint"] = float(np.clip((stats.get("tint", 0) - target.get("tint", 0)) * 4.0, -0.5, 0.5))
    s, ts = max(1e-3, stats.get("saturation", 0.3)), target.get("saturation", 0.3)
    out["saturation"] = float(np.clip(1 + (ts / s - 1) * 0.6, 0.6, 1.6))
    c, tc = max(1e-3, stats.get("contrast", 0.2)), target.get("contrast", 0.2)
    out["contrast"] = float(np.clip(1 + (tc / c - 1) * 0.5, 0.75, 1.35))
    return out
