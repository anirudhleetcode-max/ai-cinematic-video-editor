# T34 - Underwater Colossus

**Category:** G - Atmospheric and Environmental Cinema  |  **Duration:** 240 frames (10.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A sunken monument of colossal stone letters rises out of the deep into the light from the surface.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 68 | Slow-motion ascent: the title rises from below the frame and out of the depth haze, the water colour clearing off it as it approaches. |
| Impact / reveal | ~124 | It settles at the impact frame - a slow silt plume billows out from its base and the caustic light from the surface lands on the faces. |
| Hero hold | 124 - 190 | Stable, readable title. Camera: Weightless slow drift and gentle push; marine snow and haze planes drift at different depths; refraction wobble. |
| Exit | 190 - 236 | The colossus sinks back into the dark while the light shafts dim and the haze closes. |

**Material / look:** Algae-tinted weathered stone with animated caustic light projected onto the letter faces.

**Techniques:** surface light shafts, projected caustics on the title, marine snow with depth of field, layered blue-green haze, silt plume, refraction wobble, slow-motion ascent

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T34_Underwater_Colossus.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T34_Underwater_Colossus.comp` | Flat Fusion **composition** (65 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T34_Underwater_Colossus.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T34 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Anton Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

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
