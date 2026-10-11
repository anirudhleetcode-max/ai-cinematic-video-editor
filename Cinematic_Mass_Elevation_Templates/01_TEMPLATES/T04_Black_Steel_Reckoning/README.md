# T04 - Black Steel Reckoning

**Category:** A - Dark, Powerful Mass Elevation  |  **Duration:** 168 frames (7.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

Military-industrial and restrained: a slab of brushed steel lettering is machined into place.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 35 | Multi-stage mechanical move: lateral slide with motion blur -> hard stop -> beat -> forward seat -> two steel locking rails clamp the title. |
| Impact / reveal | ~60 | Short metallic impact pulse, slight camera recoil and a narrow specular highlight raking across the steel. |
| Hero hold | 60 - 134 | Stable, readable title. Camera: Slow lateral track that stops dead on the impact frame; small recoil kick, no drift afterwards. |
| Exit | 134 - 164 | The rails release and the title slides back and sideways out of the light into shadow. |

**Material / look:** Brushed steel face with flat chamfer, blackened metal sides and rails, restrained cold-silver highlights.

**Techniques:** staged mechanical timing, lateral motion blur, locking rails, volumetric light shafts, industrial pillar silhouettes, narrow specular rake, camera recoil

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T04_Black_Steel_Reckoning.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T04_Black_Steel_Reckoning.comp` | Flat Fusion **composition** (76 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T04_Black_Steel_Reckoning.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T04 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Black Ops One Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Check in Resolve (unconfirmed input names)

These inputs are set in the macro but their names could not be confirmed against documentation. Fusion ignores unknown inputs when it loads a file, so if one is wrong only that setting falls back to its default. Check these first when you open the template:

`pEmitter.Transform3DOp.Translate.Y`, `pRender.Height`, `pRender.UseFrameFormatSettings`, `pRender.Width`, `pTurbulence.XStrength`, `pTurbulence.YStrength`, `pTurbulence.ZStrength`

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
