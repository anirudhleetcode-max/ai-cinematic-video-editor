"""Template framework: parameters, render context, render pipeline."""
from __future__ import annotations

import json
import math
import os
import subprocess
import time as _time

import cv2
import numpy as np

from . import core as K
from . import elements as E
from .typo import TextSprite, Material, ShadedText, Cam, Layer, place_sprite, plane_points, FONTS, needs_shaping
from .fusion import Graph

FPS = 24

# Parameter schema: key -> (default, description, kind)
PARAM_SCHEMA = {
    "MAIN_TITLE": ("TITLE", "Main title text (use \\n for a line break)", "text"),
    "SUBTITLE": ("", "Secondary line under the title", "text"),
    "OPTIONAL_TAGLINE": ("", "Small tagline / credit line", "text"),
    "FONT_FAMILY": ("anton", "Font key (see 02_SHARED_ASSETS/Fonts/README.md)", "font"),
    "SUB_FONT_FAMILY": ("teko", "Subtitle/tagline font key", "font"),
    "FONT_SIZE": (0.0, "Cap height as fraction of frame height (0 = auto-fit to width)", "float"),
    "TITLE_WIDTH": (0.62, "Auto-fit target width as fraction of frame width", "float"),
    "LETTER_SPACING": (0.06, "Extra letter spacing in em", "float"),
    "LINE_SPACING": (1.0, "Line spacing multiplier", "float"),
    "TEXT_ALIGNMENT": ("center", "left | center | right (multi-line titles)", "choice"),
    "TEXT_POSITION_X": (0.5, "Title centre X (0..1, left to right)", "float"),
    "TEXT_POSITION_Y": (0.5, "Title centre Y (0..1, bottom to top, Fusion convention)", "float"),
    "TEXT_SCALE": (1.0, "Overall title scale", "float"),
    "TEXT_ROTATION": (0.0, "Title rotation in degrees", "float"),
    "TEXT_COLOR": ("#FFFFFF", "Primary text / material tint colour", "color"),
    "ACCENT_COLOR": ("#FF8A2A", "Accent colour (light, energy, particles)", "color"),
    "SHADOW_STRENGTH": (0.7, "Drop/contact shadow strength 0..1", "float"),
    "GLOW_STRENGTH": (1.0, "Glow / bloom strength multiplier", "float"),
    "EXTRUSION_DEPTH": (1.0, "Extrusion depth multiplier (0 = flat)", "float"),
    "BEVEL_AMOUNT": (1.0, "Bevel width multiplier", "float"),
    "ANIMATION_START": (0, "Frame where the title animation begins", "frame"),
    "ANIMATION_DURATION": (48, "Reveal duration in frames", "frame"),
    "IMPACT_FRAME": (84, "Frame of the main impact / reveal accent", "frame"),
    "HOLD_DURATION": (48, "Hero hold length in frames (informational marker)", "frame"),
    "EXIT_START": (150, "Frame where the exit begins", "frame"),
    "EXIT_DURATION": (30, "Exit length in frames", "frame"),
    "BACKGROUND_INTENSITY": (1.0, "Environment brightness multiplier", "float"),
    "PARTICLE_INTENSITY": (1.0, "Particle count/brightness multiplier (0 disables)", "float"),
    "MOTION_BLUR_AMOUNT": (1.0, "Motion blur multiplier for fast moves", "float"),
    "IMPACT_INTENSITY": (1.0, "Impact flash / shockwave strength", "float"),
    "SHAKE_AMOUNT": (1.0, "Camera shake multiplier (0 disables)", "float"),
    "LETTERBOX": (1.0, "2.39:1 letterbox amount (0 = full frame)", "float"),
    "DURATION": (192, "Total length in frames", "frame"),
    "QUALITY": ("preview", "preview | final", "choice"),
}


class Params(dict):
    """dict that records which keys were read (to prove controls function)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.read = set()

    def __getitem__(self, k):
        self.read.add(k)
        return super().__getitem__(k)

    def get(self, k, d=None):
        self.read.add(k)
        return super().get(k, d)


class Ctx:
    def __init__(self, design, params, W, H):
        self.d = design
        self.p = params
        self.W, self.H = W, H
        self.fps = FPS
        self.cache = {}
        self.t = 0.0
        self.fr = 0
        self.k = H / 1080.0

    # timing (seconds) -----------------------------------------------------
    def T(self, key):
        return self.p[key] / self.fps

    @property
    def start(self):
        return self.T("ANIMATION_START")

    @property
    def reveal(self):
        return self.T("ANIMATION_DURATION")

    @property
    def impact(self):
        return self.T("IMPACT_FRAME")

    @property
    def exit_start(self):
        return self.T("EXIT_START")

    @property
    def exit_dur(self):
        return self.T("EXIT_DURATION")

    @property
    def dur(self):
        return self.T("DURATION")

    def exit_u(self):
        return K.prog(self.t, self.exit_start, self.exit_dur)

    def reveal_u(self, delay=0.0, dur=None):
        return K.prog(self.t, self.start + delay, dur if dur is not None else self.reveal)

    def hit(self, attack=0.03, decay=0.35, offset=0.0):
        return K.pulse(self.t, self.impact + offset, attack, decay) * self.p["IMPACT_INTENSITY"]

    def shake(self, amp, decay=0.4, freq=14.0, seed=1):
        e = K.pulse(self.t, self.impact, 0.01, decay) * self.p["SHAKE_AMOUNT"]
        sx, sy = K.shake(self.t, amp * e, freq, seed)
        return sx * self.H, sy * self.H

    # typography ----------------------------------------------------------
    def cap(self, key="MAIN_TITLE", font_key=None, boost=1.0):
        p = self.p
        font_key = font_key or p["FONT_FAMILY"]
        text = p[key]
        if p["FONT_SIZE"] > 0:
            cap = p["FONT_SIZE"] * self.H
        else:
            probe = self.cache.get(("probe", text, font_key))
            if probe is None:
                probe = TextSprite(text, font_key, 100, tracking=p["LETTER_SPACING"], pad=0.1,
                                   line_spacing=p["LINE_SPACING"], upper=self.d.UPPER)
                self.cache[("probe", text, font_key)] = probe
            lines = max(1, text.count("\n") + 1)
            cap = 100 * self.W * p["TITLE_WIDTH"] / max(1, probe.ink_w)
            cap = min(cap, self.H * (0.2 if lines == 1 else 0.13))
        return cap * p["TEXT_SCALE"] * boost

    def title(self, boost=1.0, font_key=None, pad=0.6):
        key = ("title", boost, font_key, pad)
        if key not in self.cache:
            p = self.p
            fk = font_key or p["FONT_FAMILY"]
            self.cache[key] = TextSprite(p["MAIN_TITLE"], fk, self.cap(boost=boost, font_key=fk),
                                         tracking=p["LETTER_SPACING"], line_spacing=p["LINE_SPACING"],
                                         align=p["TEXT_ALIGNMENT"], pad=pad, upper=self.d.UPPER)
        return self.cache[key]

    def sub(self, key="SUBTITLE", rel=0.22, tracking=0.35, font_key=None):
        ck = ("sub", key, rel, tracking, font_key)
        if ck not in self.cache:
            p = self.p
            txt = p[key]
            if not txt:
                self.cache[ck] = None
            else:
                cap = self.title().cap_px * rel
                cap = max(cap, 14 * self.k)
                self.cache[ck] = TextSprite(txt, font_key or p["SUB_FONT_FAMILY"], cap, tracking=tracking, pad=0.4,
                                            upper=not needs_shaping(txt))
        return self.cache[ck]

    def shaded(self, mat: Material, sprite=None, name="main"):
        key = ("shaded", name, id(sprite) if sprite is not None else None)
        if key not in self.cache:
            sp = sprite if sprite is not None else self.title()
            m = Material(**{**mat.__dict__})
            m.bevel = m.bevel * self.p["BEVEL_AMOUNT"]
            self.cache[key] = ShadedText(sp, m)
        return self.cache[key]

    def hero(self):
        """Pixel offset of the title centre from frame centre (y down)."""
        return ((self.p["TEXT_POSITION_X"] - 0.5) * self.W, (0.5 - self.p["TEXT_POSITION_Y"]) * self.H)

    def cam(self, **kw):
        return Cam(self.W, self.H, **kw)

    def place(self, layer, cam, rgb, a, sprite, scale=1.0, rot=(0, 0, 0), off=(0, 0, 0), opacity=1.0, add=False):
        hx, hy = self.hero()
        rot = (rot[0], rot[1], rot[2] + self.p["TEXT_ROTATION"])
        pos = (hx + off[0], hy + off[1], off[2])
        box = (0, 0, sprite.w, sprite.h)
        place_sprite(layer, cam, rgb, a, box, sprite.anchor, pos, scale, rot, None, opacity, add=add)

    def layer(self):
        return Layer(self.H, self.W)

    # finishing -------------------------------------------------------------
    def finish(self, img, vignette=0.45, grain=0.03, letterbox=True, bloom=(0.85, 0.5), grade=None, ca=0.0,
               streak=None):
        p = self.p
        if bloom:
            img = E.bloom(img, bloom[0], bloom[1] * p["GLOW_STRENGTH"])
        if streak:
            img = E.streak(img, streak[0], streak[1] * p["GLOW_STRENGTH"], streak[2], streak[3])
        if grade:
            img = E.grade(img, **grade)
        if ca:
            img = E.chroma_ab(img, ca)
        img = E.tonemap(img)
        if vignette:
            img = E.vignette(img, vignette)
        if grain:
            img = E.grain(img, self.t, grain)
        if letterbox:
            img = E.letterbox(img, 2.39, p["LETTERBOX"])
        return img


def comp(bg, layer: Layer, opacity=1.0):
    a = layer.a[..., None] * opacity
    return bg * (1 - a) + layer.rgb * opacity


def drop_shadow(bg, layer: Layer, strength, offset=(0, 12), soft=18, k=1.0):
    if strength <= 0:
        return bg
    a = layer.a
    sh = K.blur(a, soft * k)
    M = np.float32([[1, 0, offset[0] * k], [0, 1, offset[1] * k]])
    sh = cv2.warpAffine(sh, M, (a.shape[1], a.shape[0]))
    return bg * (1 - np.clip(sh * strength, 0, 0.95))[..., None]


class Design:
    """Base class for a template design."""
    ID = "T00"
    NAME = "Base"
    SLUG = "Base"
    CATEGORY = ""
    CONCEPT = ""
    ENTRANCE = ""
    REVEAL = ""
    CAMERA = ""
    MATERIAL = ""
    EXIT = ""
    TECHNIQUES: list = []
    TRUE_3D = False
    UPPER = True
    DEFAULTS: dict = {}
    SOUND: list = []  # (frame, kind, label)
    DURATION_FRAMES = 192
    FUSION_NOTES: list = []

    def params(self, overrides=None):
        p = {k: v[0] for k, v in PARAM_SCHEMA.items()}
        p["DURATION"] = self.DURATION_FRAMES
        p.update(self.DEFAULTS)
        if overrides:
            for k, v in overrides.items():
                if k not in PARAM_SCHEMA:
                    raise KeyError(f"unknown parameter {k}")
                p[k] = v
        return Params(p)

    # to be implemented
    def frame(self, c: Ctx):
        raise NotImplementedError

    def fusion(self, g: Graph, p):
        raise NotImplementedError

    # helpers -------------------------------------------------------------
    def build_graph(self, p, W=1920, H=1080):
        g = Graph(f"{self.ID}_{self.SLUG}", W, H, FPS, p["DURATION"])
        self.fusion(g, p)
        g.prune_controls()
        return g


def render(design: Design, out_path, W=1920, H=1080, overrides=None, frames=None, crf=20, audio=None,
           codec="h264", stills=None, log=print):
    """Render a template to a video file via ffmpeg. Returns stats dict."""
    p = design.params(overrides)
    c = Ctx(design, p, W, H)
    n = int(p["DURATION"])
    rng = range(n) if frames is None else frames
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", audio]
    if codec == "h264":
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", "-tune", "film"]
    elif codec == "prores":
        cmd += ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "160k", "-shortest"] if codec == "h264" else ["-c:a", "pcm_s16le"]
    cmd += [out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = _time.time()
    means = []
    still_imgs = {}
    for f in rng:
        c.fr = f
        c.t = f / FPS
        img = design.frame(c)
        if img.shape[:2] != (H, W):
            raise RuntimeError("frame size mismatch")
        u8 = E.to_uint8(img)
        means.append(float(u8.mean()))
        if stills and f in stills:
            still_imgs[f] = u8
        proc.stdin.write(u8.tobytes())
    proc.stdin.close()
    rc = proc.wait()
    dt = time_ = _time.time() - t0
    return {"rc": rc, "seconds": round(dt, 1), "frames": len(list(rng)), "mean_luma": means,
            "params_read": sorted(p.read), "stills": still_imgs}
