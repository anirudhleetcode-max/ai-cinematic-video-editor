"""Editing metadata for effects and transitions — what each one is *for*, so the director can choose (or refuse) them.

effects:      style, recommended_intensity (0..1 of the parameter range), recommended_pacing, recommended_energy (lo, hi),
              recommended_shot_types, role (accent | look | utility), performance_cost (from the definition)
transitions:  style, energy (lo, hi), duration_range (s), movement (what the shots should be doing),
              recommended_shot_types, performance_cost
"""
from __future__ import annotations

ANY = ["any"]

# ---- effects --------------------------------------------------------------------------------------------------------
EFFECT_META: dict[str, dict] = {
    "gaussian_blur": dict(style="soft", role="utility", recommended_intensity=0.3, recommended_pacing=["slow", "medium"], recommended_energy=(0.0, 0.5), recommended_shot_types=ANY),
    "directional_blur": dict(style="energetic", role="accent", recommended_intensity=0.3, recommended_pacing=["fast", "very_fast"], recommended_energy=(0.6, 1.0), recommended_shot_types=["wide", "medium"]),
    "motion_blur": dict(style="smooth", role="accent", recommended_intensity=0.3, recommended_pacing=["fast"], recommended_energy=(0.5, 1.0), recommended_shot_types=["moving"]),
    "box_blur": dict(style="soft", role="utility", recommended_intensity=0.2, recommended_pacing=["slow"], recommended_energy=(0.0, 0.4), recommended_shot_types=ANY),
    "zoom_blur": dict(style="energetic", role="accent", recommended_intensity=0.4, recommended_pacing=["fast", "very_fast"], recommended_energy=(0.75, 1.0), recommended_shot_types=["medium", "closeup"]),
    "soft_glow": dict(style="cinematic", role="look", recommended_intensity=0.3, recommended_pacing=["slow", "medium"], recommended_energy=(0.0, 0.6), recommended_shot_types=["closeup", "medium"]),
    "bloom": dict(style="cinematic", role="look", recommended_intensity=0.35, recommended_pacing=["medium", "fast"], recommended_energy=(0.4, 1.0), recommended_shot_types=["night", "stage"]),
    "neon_glow": dict(style="stylised", role="look", recommended_intensity=0.4, recommended_pacing=["fast"], recommended_energy=(0.6, 1.0), recommended_shot_types=["night"]),
    "halation": dict(style="film", role="look", recommended_intensity=0.3, recommended_pacing=ANY, recommended_energy=(0.0, 1.0), recommended_shot_types=ANY),
    "lens_distortion": dict(style="subtle", role="look", recommended_intensity=0.3, recommended_pacing=ANY, recommended_energy=(0.0, 1.0), recommended_shot_types=["wide"]),
    "barrel": dict(style="stylised", role="accent", recommended_intensity=0.3, recommended_pacing=["fast"], recommended_energy=(0.6, 1.0), recommended_shot_types=["wide"]),
    "fisheye": dict(style="extreme", role="accent", recommended_intensity=0.4, recommended_pacing=["very_fast"], recommended_energy=(0.8, 1.0), recommended_shot_types=["action"]),
    "chromatic_aberration": dict(style="music", role="accent", recommended_intensity=0.25, recommended_pacing=["fast", "very_fast"], recommended_energy=(0.7, 1.0), recommended_shot_types=ANY),
    "wave": dict(style="dream", role="accent", recommended_intensity=0.3, recommended_pacing=["slow"], recommended_energy=(0.0, 0.4), recommended_shot_types=ANY),
    "light_leak": dict(style="film", role="accent", recommended_intensity=0.3, recommended_pacing=["slow", "medium"], recommended_energy=(0.2, 0.7), recommended_shot_types=["wide", "medium"]),
    "flash": dict(style="energetic", role="accent", recommended_intensity=0.5, recommended_pacing=["fast", "very_fast"], recommended_energy=(0.75, 1.0), recommended_shot_types=ANY),
    "exposure_pulse": dict(style="music", role="accent", recommended_intensity=0.3, recommended_pacing=["fast"], recommended_energy=(0.65, 1.0), recommended_shot_types=ANY),
    "glow_pulse": dict(style="music", role="accent", recommended_intensity=0.3, recommended_pacing=["medium", "fast"], recommended_energy=(0.5, 1.0), recommended_shot_types=ANY),
    "flare": dict(style="cinematic", role="accent", recommended_intensity=0.3, recommended_pacing=["slow", "medium"], recommended_energy=(0.2, 0.7), recommended_shot_types=["outdoor", "wide"]),
    "film_grain": dict(style="film", role="look", recommended_intensity=0.25, recommended_pacing=ANY, recommended_energy=(0.0, 1.0), recommended_shot_types=ANY),
    "vignette": dict(style="cinematic", role="look", recommended_intensity=0.3, recommended_pacing=ANY, recommended_energy=(0.0, 1.0), recommended_shot_types=ANY),
    "scanlines": dict(style="retro", role="look", recommended_intensity=0.3, recommended_pacing=["fast"], recommended_energy=(0.5, 1.0), recommended_shot_types=ANY),
    "vhs": dict(style="retro", role="look", recommended_intensity=0.4, recommended_pacing=ANY, recommended_energy=(0.0, 1.0), recommended_shot_types=ANY),
    "glitch": dict(style="glitch", role="accent", recommended_intensity=0.4, recommended_pacing=["very_fast"], recommended_energy=(0.8, 1.0), recommended_shot_types=ANY),
    "pixelate": dict(style="glitch", role="accent", recommended_intensity=0.3, recommended_pacing=["very_fast"], recommended_energy=(0.8, 1.0), recommended_shot_types=ANY),
    "sharpen": dict(style="clean", role="utility", recommended_intensity=0.3, recommended_pacing=ANY, recommended_energy=(0.0, 1.0), recommended_shot_types=ANY),
    "letterbox": dict(style="cinematic", role="look", recommended_intensity=1.0, recommended_pacing=ANY, recommended_energy=(0.0, 1.0), recommended_shot_types=ANY),
    "black_white": dict(style="classic", role="look", recommended_intensity=1.0, recommended_pacing=ANY, recommended_energy=(0.0, 1.0), recommended_shot_types=ANY),
    "mirror": dict(style="stylised", role="accent", recommended_intensity=1.0, recommended_pacing=["fast"], recommended_energy=(0.6, 1.0), recommended_shot_types=["symmetrical"]),
}

# ---- transitions ------------------------------------------------------------------------------------------------------
_T_CAT = {  # category → (style, energy range, duration range, movement)
    "cut": ("cut", (0.0, 1.0), (0.0, 0.0), "any"),
    "crossfade": ("subtle", (0.0, 0.6), (0.4, 1.5), "any"),
    "fade": ("subtle", (0.0, 0.5), (0.5, 1.5), "any"),
    "dip": ("chapter", (0.0, 0.6), (0.6, 1.6), "any"),
    "wipe": ("graphic", (0.3, 0.8), (0.3, 0.9), "any"),
    "slide": ("dynamic", (0.5, 1.0), (0.3, 0.7), "lateral_motion"),
    "push": ("dynamic", (0.45, 1.0), (0.3, 0.8), "lateral_motion"),
    "shape": ("graphic", (0.3, 0.8), (0.4, 1.0), "any"),
    "mask": ("graphic", (0.3, 0.8), (0.4, 1.0), "any"),
    "radial": ("graphic", (0.3, 0.7), (0.5, 1.0), "any"),
    "distortion": ("stylised", (0.5, 1.0), (0.3, 0.7), "any"),
    "morph": ("subtle", (0.2, 0.6), (0.5, 1.2), "similar_framing"),
}
_T_ID = {  # procedural families and specific overrides
    "zoom": ("energetic", (0.65, 1.0), (0.3, 0.6), "towards_subject"), "zoom_out": ("energetic", (0.6, 1.0), (0.3, 0.6), "any"),
    "spin": ("energetic", (0.75, 1.0), (0.3, 0.6), "any"), "whip": ("energetic", (0.7, 1.0), (0.2, 0.45), "lateral_motion"),
    "blur_dissolve": ("subtle", (0.1, 0.6), (0.4, 1.0), "any"), "rgb_split": ("glitch", (0.75, 1.0), (0.2, 0.5), "any"),
    "glitch": ("glitch", (0.8, 1.0), (0.2, 0.45), "any"), "flash": ("energetic", (0.75, 1.0), (0.15, 0.4), "any"),
    "film_burn": ("film", (0.3, 0.8), (0.5, 1.2), "any"), "light_leak": ("film", (0.2, 0.7), (0.5, 1.2), "any"),
    "kaleidoscope": ("extreme", (0.8, 1.0), (0.4, 0.8), "any"), "pixel_dissolve": ("glitch", (0.6, 1.0), (0.3, 0.6), "any"),
    "fade_slow": ("emotional", (0.0, 0.4), (0.8, 2.0), "any"), "dip_to_white": ("dreamy", (0.2, 0.8), (0.4, 1.2), "any"),
}


def effect_meta(d) -> dict:
    m = dict(EFFECT_META.get(d.id, dict(style="other", role="accent", recommended_intensity=0.3, recommended_pacing=ANY,
                                          recommended_energy=(0.0, 1.0), recommended_shot_types=ANY)))
    m["performance_cost"] = d.performance_cost
    m["recommended_energy"] = list(m["recommended_energy"])
    return m


def transition_meta(d) -> dict:
    fam = next((k for k in _T_ID if d.id == k or d.id.startswith(k + "_")), None)
    style, energy, dur, move = _T_ID[fam] if fam else _T_CAT.get(d.category, ("other", (0.0, 1.0), (0.3, 1.0), "any"))
    shot_types = ["any"] if move == "any" else (["moving"] if move == "lateral_motion" else (["similar framing"] if move == "similar_framing" else ["medium", "closeup"]))
    return {"style": style, "energy": list(energy), "duration_range": list(dur), "movement": move, "recommended_shot_types": shot_types,
            "performance_cost": d.performance_cost, "first_class_cut": d.id == "cut"}


DENSITY = {  # EffectDensity → (fraction of segments that may carry an accent effect, transition budget multiplier)
    "minimal": (0.0, 0.4), "low": (0.06, 0.8), "medium": (0.14, 1.0), "high": (0.28, 1.4), "extreme": (0.5, 2.0),
}
