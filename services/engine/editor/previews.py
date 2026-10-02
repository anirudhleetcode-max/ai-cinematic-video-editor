"""Real rendered previews for creative-library entries (effects, transitions, colour presets, text
styles/animations, motion presets), generated on demand from a built-in procedural sample and cached."""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

from .config import get_settings
from .proc import run
from .registry import REGISTRIES
from .registry.color import grade, preset_params
from .registry.effects import render_effect
from .registry.motion import camera_at
from .registry.transitions import _ease, transition_spec

W, H = 384, 216


def _sample(seed: int = 0) -> np.ndarray:
    """Procedural 'scene': sky gradient, sun, hills, and a figure — enough tonal range to show a look."""
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    sky = np.stack([0.35 + 0.4 * (1 - y / H), 0.45 + 0.3 * (1 - y / H), 0.75 - 0.2 * (y / H)], -1)
    sun = np.exp(-(((x - W * (0.72 - 0.4 * seed)) / 30) ** 2 + ((y - H * 0.3) / 30) ** 2))[..., None] * np.array([1.0, 0.85, 0.5])
    img = np.clip(sky + sun * 0.9, 0, 1)
    hill = y > H * 0.62 + 18 * np.sin(x / 47 + seed * 2)
    img[hill] = np.stack([0.22 + 0.1 * np.sin(x / 9), 0.42 + 0.05 * np.cos(y / 7), 0.2 + 0 * x], -1)[hill]
    cv2.circle(img, (int(W * (0.32 + 0.3 * seed)), int(H * 0.5)), 16, (0.85, 0.62, 0.5), -1)
    cv2.rectangle(img, (int(W * (0.32 + 0.3 * seed)) - 14, int(H * 0.5) + 14), (int(W * (0.32 + 0.3 * seed)) + 14, int(H * 0.85)), (0.75, 0.15, 0.2), -1)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def _write(img: np.ndarray, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    return out


def preview(kind: str, item_id: str) -> Path:
    if kind not in REGISTRIES:
        raise KeyError(kind)
    REGISTRIES[kind].get(item_id)  # validates id
    out = get_settings().cache_dir / "previews" / kind / f"{item_id}.png"
    if out.exists():
        return out
    a = _sample(0)
    if kind == "color-presets":
        g = (grade(a.astype(np.float32) / 255, preset_params(item_id)) * 255).astype(np.uint8)
        return _write(np.hstack([a[:, : W // 2], g[:, W // 2:]]), out)
    if kind == "transitions":
        b = _sample(1)
        spec, p, _ = transition_spec(item_id, {})
        if not spec:
            return _write(np.hstack([a[:, : W // 2], b[:, W // 2:]]), out)
        if spec["engine"] == "numpy":
            f = spec["fn"](a.astype(np.float32) / 255, b.astype(np.float32) / 255, _ease(0.5, spec["easing"]), p)
            return _write((np.clip(f, 0, 1) * 255).astype(np.uint8), out)
        st = get_settings()
        pa, pb = out.with_suffix(".a.png"), out.with_suffix(".b.png")
        _write(a, pa), _write(b, pb)
        run([st.ffmpeg, "-v", "error", "-y", "-loop", "1", "-t", "1", "-r", "10", "-i", str(pa), "-loop", "1", "-t", "1", "-r", "10", "-i", str(pb),
             "-filter_complex", f"[0:v]format=yuv420p[a];[1:v]format=yuv420p[b];[a][b]xfade=transition={spec['transition']}:duration=1:offset=0,select=eq(n\\,5)",
             "-frames:v", "1", str(out)])
        pa.unlink(missing_ok=True), pb.unlink(missing_ok=True)
        return out
    if kind == "effects":
        st = get_settings()
        src = out.with_suffix(".src.png")
        _write(a, src)
        g = "[0:v]format=yuv420p[v0];" + render_effect(item_id, {}, {"w": W, "h": H, "dur": 1.0, "fps": 10}, "v0", "o")
        run([st.ffmpeg, "-v", "error", "-y", "-loop", "1", "-t", "1", "-r", "10", "-i", str(src), "-filter_complex", g, "-map", "[o]", "-frames:v", "1", str(out)])
        src.unlink(missing_ok=True)
        return out
    if kind == "motion-presets":
        frames = []
        for u in (0.0, 0.5, 1.0):
            z, dx, dy, rot = camera_at(item_id, u, {"intensity": 1.0, "_dur": 3.0})
            M = cv2.getRotationMatrix2D((W / 2 - dx * W, H / 2 - dy * H), -rot, z)
            frames.append(cv2.warpAffine(a, M, (W, H), borderMode=cv2.BORDER_REFLECT)[:, :: 1])
        strip = np.hstack([cv2.resize(f, (W // 3, H // 3)) for f in frames])
        canvas = np.zeros_like(a)
        canvas[H // 3: H // 3 + strip.shape[0], : strip.shape[1]] = strip
        return _write(canvas, out)
    if kind in ("text-styles", "text-animations"):
        from .render.text_ass import AssBuilder
        from .schemas import TextItem

        st = get_settings()
        b = AssBuilder(W * 2, H * 2)
        style = item_id if kind == "text-styles" else "premium_title"
        anim = item_id if kind == "text-animations" else "static"
        b.add(TextItem(id="p", text="Your Story", start=0, end=2, style=style, animation=anim, position="center", params={"in_dur": 1.0}))
        out.parent.mkdir(parents=True, exist_ok=True)
        ass = b.write(out.with_suffix(".ass"))
        bg = out.with_suffix(".bg.png")
        _write(cv2.resize((a * 0.55).astype(np.uint8), (W * 2, H * 2)), bg)
        run([st.ffmpeg, "-v", "error", "-y", "-loop", "1", "-t", "2", "-r", "10", "-i", str(bg), "-vf",
             f"ass='{ass.as_posix()}':fontsdir='{st.fonts_dir.as_posix()}',select=eq(n\\,7),scale={W}:-2", "-frames:v", "1", str(out)])
        ass.unlink(missing_ok=True), bg.unlink(missing_ok=True)
        return out
    # audio presets: no visual preview
    raise KeyError(f"no preview for {kind}")
