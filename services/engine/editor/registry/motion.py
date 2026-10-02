"""Camera-motion presets. Each preset is a function of normalised time u∈[0,1] returning an affine
camera (zoom, centre offset, rotation). The renderer applies it per frame with sub-pixel warps,
so moves are smooth (no integer-step jitter)."""
from __future__ import annotations

import math

from .base import Definition, Registry, e, f

MOTION_PRESETS = Registry("motion_preset")


def ease_in_out(u: float) -> float:
    return u * u * (3 - 2 * u)


def _mk(fn):
    return fn


def _reg(id_, name, tags, fn, params=(), desc=""):
    MOTION_PRESETS.register(Definition(id_, name, "motion", (f("intensity", 0.5, 0, 1, 0.1), *params), tuple(tags), desc, 1.2, fn))


def _none(u, p):
    return 1.0, 0.0, 0.0, 0.0


def _push(u, p):
    return 1.0 + 0.12 * p["intensity"] * ease_in_out(u), 0.0, 0.0, 0.0


def _pull(u, p):
    return 1.0 + 0.12 * p["intensity"] * (1 - ease_in_out(u)), 0.0, 0.0, 0.0


def _pan(sign_x, sign_y):
    def fn(u, p):
        z = 1.0 + 0.1 * p["intensity"]
        span = (z - 1) / z / 2  # max offset that stays inside the frame
        k = (ease_in_out(u) - 0.5) * 2 * span
        return z, sign_x * k, sign_y * k, 0.0
    return fn


def _ken_burns(u, p):
    z = 1.04 + 0.12 * p["intensity"] * ease_in_out(u)
    span = (z - 1) / z / 2 * 0.8
    return z, (ease_in_out(u) - 0.5) * span, (0.5 - ease_in_out(u)) * span * 0.6, 0.0


def _handheld(u, p):
    t = u * p.get("_dur", 3.0)
    a = 0.006 * p["intensity"]
    dx = a * (math.sin(t * 1.3) + 0.5 * math.sin(t * 3.1 + 1.0) + 0.25 * math.sin(t * 7.3 + 2.0))
    dy = a * (math.sin(t * 1.7 + 0.5) + 0.5 * math.sin(t * 2.9 + 2.2) + 0.25 * math.sin(t * 6.1))
    rot = 0.25 * p["intensity"] * math.sin(t * 1.1 + 0.3)
    return 1.04 + 0.03 * p["intensity"], dx, dy, rot


def _shake(u, p):
    t = u * p.get("_dur", 1.0)
    a = 0.015 * p["intensity"] * math.exp(-3 * u)
    return 1.06, a * math.sin(t * 47), a * math.cos(t * 39), 0.8 * p["intensity"] * math.sin(t * 31) * math.exp(-3 * u)


def _orbit(u, p):
    z = 1.08 + 0.06 * p["intensity"]
    span = (z - 1) / z / 2 * 0.7
    return z, span * math.sin(u * math.pi * 0.8 - 0.4), 0.0, 2.0 * p["intensity"] * (ease_in_out(u) - 0.5)


def _whip(u, p):
    z = 1.08
    span = (z - 1) / z / 2
    k = ease_in_out(min(1, u * 1.4))
    return z, (k - 0.5) * 2 * span, 0.0, 0.0


def _drift(u, p):
    z = 1.03 + 0.04 * p["intensity"] * u
    return z, 0.01 * p["intensity"] * (u - 0.5), 0.0, 0.0


_reg("none", "Static", ("static", "none"), _none)
_reg("push_in", "Push In", ("cinematic", "emotional", "focus", "subtle"), _push)
_reg("pull_out", "Pull Out", ("reveal", "establishing", "ending"), _pull)
_reg("pan_left", "Pan Left", ("pan", "travel"), _pan(-1, 0))
_reg("pan_right", "Pan Right", ("pan", "travel"), _pan(1, 0))
_reg("tilt_up", "Tilt Up", ("tilt", "reveal"), _pan(0, -1))
_reg("tilt_down", "Tilt Down", ("tilt",), _pan(0, 1))
_reg("ken_burns", "Ken Burns", ("photo", "documentary", "memory"), _ken_burns)
_reg("handheld", "Handheld", ("documentary", "organic", "vlog"), _handheld)
_reg("shake", "Impact Shake", ("impact", "hype", "beat"), _shake)
_reg("orbit", "Orbit (simulated)", ("dynamic", "product"), _orbit, desc="2D approximation of an orbit: lateral drift with counter-rotation.")
_reg("whip", "Whip Move", ("energetic", "fast"), _whip)
_reg("drift", "Subtle Drift", ("subtle", "cinematic", "parallax"), _drift, desc="Slow scale+drift; simulates a gentle parallax push.")


def camera_at(preset: str, u: float, params: dict) -> tuple[float, float, float, float]:
    d = MOTION_PRESETS.get(preset if MOTION_PRESETS.has(preset) else "none")
    p = d.resolve(params)
    p["_dur"] = float(params.get("_dur", 3.0))
    return d.render(u, p)
