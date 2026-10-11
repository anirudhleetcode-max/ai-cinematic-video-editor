# T20 - Phoenix Reborn

**Category:** D - Mythic, Epic and Fantasy  |  **Duration:** 156 frames (6.50s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

Renewal and power: a rising double spiral of living sparks becomes the title, which ignites reborn.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 35 | Two intertwined helices of glowing particles spiral up from the dark, widen at the top and then stream inward, each spark flying to its own point on the letterforms. |
| Impact / reveal | ~64 | On the impact frame the converged sparks ignite the title in a bright white-gold flash that throws two wing-like arcs of embers outward, then settles into a clean, readable gold hold. |
| Hero hold | 64 - 118 | Stable, readable title. Camera: Slow upward tilt following the spiral, small lift-and-settle at the ignition. |
| Exit | 118 - 150 | The title is reborn again as embers: it dissolves bottom-to-top into sparks that spiral up and away. |

**Material / look:** Radiant sun-gold metal with crimson rim light and a white-hot edge that cools after ignition; emissive particles with soft bloom.

**Techniques:** 3D helix particle spiral, per-particle target convergence, ignition flash, wing arcs, cooling edge heat, bottom-up ember dissolve exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T20_Phoenix_Reborn.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T20_Phoenix_Reborn.comp` | Flat Fusion **composition** (74 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T20_Phoenix_Reborn.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T20 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Bebas Neue Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Fusion notes and limitations

- The spiral is two pEmitters whose positions orbit the vertical axis by expression (helix); per-particle target convergence onto the glyphs is approximated by a radial zoom-in of the particle render plus the ignition flash (Fusion particles cannot target text pixels without extra tools).

## Check in Resolve (unconfirmed input names)

These inputs are set in the macro but their names could not be confirmed against documentation. Fusion ignores unknown inputs when it loads a file, so if one is wrong only that setting falls back to its default. Check these first when you open the template:

`pEmitter.Transform3DOp.Translate.X`, `pEmitter.Transform3DOp.Translate.Y`, `pEmitter.Transform3DOp.Translate.Z`, `pRender.Height`, `pRender.UseFrameFormatSettings`, `pRender.Width`, `pTurbulence.XStrength`, `pTurbulence.YStrength`, `pTurbulence.ZStrength`

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
