# T02 - Thunder God

**Category:** A - Dark Mass Elevation  |  **Duration:** 192 frames (8.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

Storm-powered hero introduction: the title pushes through mist inside a living thunderstorm.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 42 | Title travels forward through drifting mist while electrical light crawls behind the letterforms. |
| Impact / reveal | ~80 | A branching lightning strike behind the title flash-lights the scene and the clouds; edge arcs crackle. |
| Hero hold | 80 - 154 | Stable, readable title. Camera: Slow forward dolly with a small shock pulse (zoom kick) at the strike. |
| Exit | 154 - 188 | Storm calms, the title dissolves back into the clouds through a noise-driven dissolve. |

**Material / look:** Gunmetal with cool sky reflections and electric-blue rim; lightning drawn behind the title only.

**Techniques:** layered storm clouds, procedural lightning, cloud internal flashes, mist pass-through, edge arcs, noise dissolve

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T02_Thunder_God.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T02_Thunder_God.comp` | Flat Fusion **composition** (59 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T02_Thunder_God.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
| `preview/thumbnail.jpg` | Hero-hold frame. |
| `configuration/render_profile.json` | Preview / 4K final render settings. |
| `configuration/default_params.json` | Reference-renderer defaults (edit + render with `render_title.py`). |
| `documentation/parameters.md` | Every published control and what it drives. |
| `documentation/sound_design.md` | Cue sheet (frames + seconds). |
| `manifest.json` | Machine-readable description and verification status. |

## Change the title text

**In Resolve (Edit page title):** select the clip, open the Inspector > *Title* tab > **Main Title** field. Font, size, letter spacing, line spacing, alignment and colour are next to it. Timing and look sliders (Impact Frame, Exit Start, Glow, Particles, Shake, ...) are on the same page under *Controls*.

**In the Fusion page:** select `MainTitle` (TextPlus) and edit *Styled Text*.

**Reference renderer (no Resolve needed):**
```
python 06_AUTOMATION/Scripts/render_title.py T02 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Bebas Neue Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
