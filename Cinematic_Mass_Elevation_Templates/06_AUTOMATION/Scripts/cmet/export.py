"""Export a template's deliverables (sources, docs, manifest) and previews."""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import cv2
import numpy as np

from . import sfx
from .base import PARAM_SCHEMA, FPS, render, Ctx
from .fusion_ref import TOOLS, input_evidence
from .luacheck import parse, tools_of
from .typo import FONTS

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
TPL = os.path.join(ROOT, "01_TEMPLATES")
VERSION = "1.0.0"

CONTROL_DOC = {
    "AnimStart": "Frame where the build-up/reveal animation starts.",
    "AnimDuration": "Length of the title reveal in frames.",
    "ImpactFrame": "Frame of the main impact; flashes, shake, bursts and rings key off this.",
    "HoldDuration": "Hero-hold length (frames).",
    "ExitStart": "Frame where the exit begins.",
    "ExitDuration": "Exit length in frames.",
    "BackgroundIntensity": "Scales environment lights/atmosphere.",
    "ParticleIntensity": "Scales particle emission (0 disables particles).",
    "GlowStrength": "Scales glows, rim light and light sweeps.",
    "ShadowStrength": "Scales the title's drop/contact shadow.",
    "ImpactIntensity": "Scales impact flash / shockwave.",
    "ShakeAmount": "Scales the impact camera shake (0 disables).",
    "TextScale": "Overall title scale.",
    "TextPosX": "Title centre X (0 = left edge, 1 = right edge).",
    "TextPosY": "Title centre Y (0 = bottom, 1 = top).",
    "TextRotation": "Title rotation in degrees.",
    "ExtrusionDepth": "Depth of the extrusion stack / Text3D extrusion (0 = flat).",
    "BevelAmount": "Bevel size multiplier (3D templates).",
    "MotionBlurAmount": "Scales directional/motion blur on fast moves.",
    "Letterbox": "Blend of the 2.39:1 letterbox bars (0 = off).",
}


def tdir(d):
    return os.path.join(TPL, f"{d.ID}_{d.SLUG}")


def secs(f):
    return f"{f / FPS:.2f}s"


def build_sources(d, p=None):
    """Write .setting and .comp; return info dict incl. parse results."""
    p = p or d.params()
    g = d.build_graph(p)
    base = tdir(d)
    os.makedirs(os.path.join(base, "source"), exist_ok=True)
    macro_name = f"{d.ID}_{d.SLUG}"
    mt = g.macro_text(macro_name)
    ct = g.comp_text()
    sp = os.path.join(base, "source", f"{macro_name}.setting")
    cp = os.path.join(base, "source", f"{macro_name}.comp")
    open(sp, "w", encoding="utf-8").write(mt)
    open(cp, "w", encoding="utf-8").write(ct)
    info = {"graph": g, "setting": sp, "comp": cp}
    info["tool_types"] = sorted({t.tid for t in g.tools.values()})
    info["tool_count"] = len(g.tools)
    info["controls"] = g.control_names()
    info["published"] = [(x.name, x.tool.name, x.inp, x.page) for x in g.published]
    return info


def write_docs(d, info, p=None):
    p = p or d.params()
    base = tdir(d)
    g = info["graph"]
    name = f"{d.ID}_{d.SLUG}"
    os.makedirs(os.path.join(base, "documentation"), exist_ok=True)
    os.makedirs(os.path.join(base, "configuration"), exist_ok=True)
    dur = p["DURATION"]
    # render profile -----------------------------------------------------
    prof = {
        "template": d.ID,
        "frame_rate": FPS,
        "duration_frames": dur,
        "profiles": {
            "preview": {"width": 1920, "height": 1080, "codec": "H.264 (libx264, CRF 20, yuv420p)",
                        "container": "mp4", "audio": "AAC 160k (procedural cue mix)"},
            "final_4k": {"width": 3840, "height": 2160, "codec": "Apple ProRes 422 HQ (prores_ks profile 3)",
                         "container": "mov", "audio": "PCM 16-bit 48 kHz"},
            "final_1080": {"width": 1920, "height": 1080, "codec": "Apple ProRes 422 HQ", "container": "mov"},
        },
        "resolve_render_settings": {"Format": "QuickTime", "Codec": "Apple ProRes 422 HQ or H.264",
                                    "Resolution": "3840x2160 (UHD) or timeline resolution",
                                    "FrameRate": FPS, "Timeline length": f"{dur} frames ({dur / FPS:.2f}s)"},
    }
    json.dump(prof, open(os.path.join(base, "configuration", "render_profile.json"), "w"), indent=2)
    defaults = {k: p[k] for k in PARAM_SCHEMA}
    json.dump(defaults, open(os.path.join(base, "configuration", "default_params.json"), "w"), indent=2,
              ensure_ascii=False)

    # parameters.md ---------------------------------------------------------
    L = [f"# {d.ID} {d.NAME} - Parameter Reference", "",
         "## A. Fusion macro controls (DaVinci Resolve Inspector)", "",
         "These are the controls published on the macro. Every timing/look slider listed here is referenced by "
         "at least one expression in the composition (unreferenced controls are removed automatically at build "
         "time), so each one drives the animation.", "",
         "| Inspector label | Page | Drives (tool.input) |", "|---|---|---|"]
    for (label, tool, inp, page) in info["published"]:
        L.append(f"| {label} | {page} | `{tool}.{inp}` |")
    L += ["", "### Timing/look control meanings", ""]
    for cid in info["controls"]:
        L.append(f"- **CONTROLS.{cid}** - {CONTROL_DOC.get(cid, '')}")
    L += ["", "## B. Reference renderer parameters (`render_title.py`)", "",
          "Used by the Python reference renderer that produced the preview (also usable for customised "
          "renders without Resolve). Defaults for this template:", "",
          "| Parameter | Default | Meaning |", "|---|---|---|"]
    for k, (dflt, desc, kind) in PARAM_SCHEMA.items():
        v = p[k]
        vs = json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v)
        L.append(f"| `{k}` | {vs} | {desc} |")
    L += ["", "Parameters this template's preview renderer actually reads are listed in `manifest.json` under "
               "`reference_renderer.parameters_used`; others have no effect for this design.", ""]
    if d.FUSION_NOTES:
        L += ["## C. Manual-edit notes", ""] + [f"- {n}" for n in d.FUSION_NOTES] + [""]
    open(os.path.join(base, "documentation", "parameters.md"), "w").write("\n".join(L))

    # sound_design.md -------------------------------------------------------
    S = [f"# {d.ID} {d.NAME} - Sound Design Sheet", "",
         f"Timeline: {dur} frames @ {FPS} fps ({dur / FPS:.2f}s). Cue frames assume default timing; if you move "
         "`ImpactFrame`/`ExitStart`, move the matching cues by the same amount.", "",
         "| Frame | Time | Cue | Notes |", "|---|---|---|---|"]
    for f, kind, label in d.SOUND:
        S.append(f"| {f} | {secs(f)} | {kind} | {label} |")
    S += ["", "The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised "
              "from oscillators and filtered noise - no samples or third-party recordings). Replace with your "
              "own licensed library for final delivery if preferred.", ""]
    open(os.path.join(base, "documentation", "sound_design.md"), "w").write("\n".join(S))


def readme(d, info, manifest):
    p = d.params()
    name = f"{d.ID}_{d.SLUG}"
    dur = p["DURATION"]
    fam = FONTS.get(p["FONT_FAMILY"], FONTS["anton"])
    three = ("**Genuine 3D** in the Fusion source (Text3D extrusion + Blinn material + lights + Camera3D + "
             "Renderer3D)." if d.TRUE_3D else "**2.5D** (layered 2D compositing: masks, offset extrusion stack, "
             "parallax, light passes). No 3D geometry.")
    ver = manifest["verification"]
    return f"""# {d.ID} - {d.NAME}

**Category:** {d.CATEGORY}  |  **Duration:** {dur} frames ({dur / FPS:.2f}s @ {FPS} fps)  |  **Depth:** {'3D' if d.TRUE_3D else '2.5D'}

![thumbnail](preview/thumbnail.jpg)

{d.CONCEPT}

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - {p['ANIMATION_START'] + p['ANIMATION_DURATION'] // 2} | {d.ENTRANCE} |
| Impact / reveal | ~{p['IMPACT_FRAME']} | {d.REVEAL} |
| Hero hold | {p['IMPACT_FRAME']} - {p['EXIT_START']} | Stable, readable title. Camera: {d.CAMERA} |
| Exit | {p['EXIT_START']} - {p['EXIT_START'] + p['EXIT_DURATION']} | {d.EXIT} |

**Material / look:** {d.MATERIAL}

**Techniques:** {', '.join(d.TECHNIQUES)}

**Depth model:** {three}

## Files

| File | Purpose |
|---|---|
| `source/{name}.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/{name}.comp` | Flat Fusion **composition** ({info['tool_count']} tools) for Fusion Studio / Resolve Fusion page import. Final node: `{info['graph'].output.name}`. |
| `preview/{name}.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
| `preview/thumbnail.jpg` | Hero-hold frame. |
| `configuration/render_profile.json` | Preview / 4K final render settings. |
| `configuration/default_params.json` | Reference-renderer defaults (edit + render with `render_title.py`). |
| `documentation/parameters.md` | Every published control and what it drives. |
| `documentation/sound_design.md` | Cue sheet (frames + seconds). |
| `manifest.json` | Machine-readable description and verification status. |

## Change the title text

**In Resolve (Edit page title):** select the clip, open the Inspector > *Title* tab > **Main Title** field. Font, size, letter spacing, line spacing, alignment and colour are next to it. Timing and look sliders (Impact Frame, Exit Start, Glow, Particles, Shake, ...) are on the same page under *Controls*.

**In the Fusion page:** select `MainTitle` (TextPlus{', or the Text3D node' if d.TRUE_3D else ''}) and edit *Styled Text*.

**Reference renderer (no Resolve needed):**
```
python 06_AUTOMATION/Scripts/render_title.py {d.ID} --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **{fam[2]} {fam[3]}** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | {ver['lua_parse']} |
| Graph structure (connections, expression references, published controls) | {ver['structure']} |
| Opened / rendered inside DaVinci Resolve or Fusion | **{ver['resolve_tested']}** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | {ver['preview']} |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
"""


def make_audio(d, path, p=None):
    p = p or d.params()
    st = sfx.mix(d.SOUND, p["DURATION"], FPS, seed=int(d.ID[1:]))
    sfx.write_wav(path, st)
    return path


def render_preview(d, tmp_dir, W=1920, H=1080, overrides=None, log=print):
    base = tdir(d)
    name = f"{d.ID}_{d.SLUG}"
    os.makedirs(os.path.join(base, "preview"), exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)
    p = d.params(overrides)
    wav = make_audio(d, os.path.join(tmp_dir, f"{name}.wav"), p)
    out = os.path.join(base, "preview", f"{name}.mp4")
    thumb_f = min(p["DURATION"] - 1, p["IMPACT_FRAME"] + 30)
    st = render(d, out, W, H, overrides, audio=wav, crf=23, stills={thumb_f}, log=log)
    im = st["stills"][thumb_f]
    th = cv2.resize(cv2.cvtColor(im, cv2.COLOR_RGB2BGR), (960, 540), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(base, "preview", "thumbnail.jpg"), th, [cv2.IMWRITE_JPEG_QUALITY, 90])
    st["thumb_frame"] = thumb_f
    return out, st
