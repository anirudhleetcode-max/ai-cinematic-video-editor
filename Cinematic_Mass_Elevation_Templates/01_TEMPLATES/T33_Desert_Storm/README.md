# T33 - Desert Storm

**Category:** G - Atmospheric and Environmental Cinema  |  **Duration:** 180 frames (7.50s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A towering haboob sweeps across the dunes; when it passes, a sandstone monument title is standing there.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 48 | A rolling wall of sand crosses the frame from right to left; the title is uncovered behind its leading edge, letter by letter, with a sand-blasted edge. |
| Impact / reveal | ~48 | Gust peak as the wall front passes the title centre: sand streak burst, short shake, the sun breaks through. |
| Hero hold | 48 - 134 | Stable, readable title. Camera: Low-angle composition (low horizon, keystoned title looming up) with a slow lateral drift over parallax dunes. |
| Exit | 134 - 174 | A second dust front returns and erodes the letters into wind-blown sand from right to left. |

**Material / look:** Warm weathered sandstone, low sun rim from the right, dusty ambient fill.

**Techniques:** advancing dust wall with density front, 3 parallax dust planes, parallax dune ridges, sun god rays through dust, erosion reveal / exit, keystone low-angle title

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T33_Desert_Storm.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T33_Desert_Storm.comp` | Flat Fusion **composition** (67 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T33_Desert_Storm.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T33 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Staatliches Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Check in Resolve (unconfirmed input names)

These inputs are set in the macro but their names could not be confirmed against documentation. Fusion ignores unknown inputs when it loads a file, so if one is wrong only that setting falls back to its default. Check these first when you open the template:

`CornerPositioner.BottomLeft`, `CornerPositioner.BottomRight`, `CornerPositioner.TopLeft`, `CornerPositioner.TopRight`, `pEmitter.Transform3DOp.Translate.Y`, `pRender.Height`, `pRender.UseFrameFormatSettings`, `pRender.Width`, `pTurbulence.XStrength`, `pTurbulence.YStrength`, `pTurbulence.ZStrength`

## Verification status (honest)

| Level | Status |
|---|---|
| A. Fusion source structure (real Lua parse, connections, expressions, published controls) | PASS / PASS |
| B. Standalone Python preview (ffprobe, duration, size, motion, exposure) | PASS |
| C. Composition loads in DaVinci Resolve | **BLOCKED** |
| D. Renders in DaVinci Resolve | **BLOCKED** |
| E. Text and controls editable in Resolve | **BLOCKED** |
| F. Visual comparison Resolve vs. preview | **BLOCKED** |

Resolve status: BLOCKED - not tested in DaVinci Resolve: no Resolve connection in the environment of run cloud_build_env_20261011 (see 06_AUTOMATION/Validation/resolve_test_results.json). To test it on your machine, see `06_AUTOMATION/Resolve/README.md`.

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
