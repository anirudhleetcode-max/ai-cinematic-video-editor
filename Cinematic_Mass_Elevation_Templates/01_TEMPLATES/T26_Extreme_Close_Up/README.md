# T26 - Extreme Close-Up

**Category:** F - Cinematic Typography and Camera Movement  |  **Duration:** 200 frames (8.33s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A macro study of the lettering: we start inside the lacquered surface of one letter and pull out to the name.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 56 | Extreme macro crop on the bevel of the first letter with shallow depth of field and a raking edge light; the camera dollies backward on a long eased move while the tilt flattens out. |
| Impact / reveal | ~112 | The pull-back lands exactly on the impact frame with a tiny settle; focus snaps crisp and the edge light flares. |
| Hero hold | 112 - 168 | Stable, readable title. Camera: Backward dolly from 6.5x with perspective tilt/yaw unwinding to frontal; macro DOF opening to full focus. |
| Exit | 168 - 194 | Rack focus: the title defocuses into soft bokeh and the light fades. |

**Material / look:** Deep crimson gloss lacquer with fine grain, warm bevel highlights and a travelling specular glint.

**Techniques:** boosted raster close-up, backward dolly, 2.5D perspective tilt, macro depth of field, travelling glint, focus snap, rack-focus exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T26_Extreme_Close_Up.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T26_Extreme_Close_Up.comp` | Flat Fusion **composition** (45 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T26_Extreme_Close_Up.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T26 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Bebas Neue Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Fusion notes and limitations

- Fusion zooms the vector Text+ itself (Size/Center driven by expressions) so the close-up stays crisp; use 'Text Scale' to resize the final title. The preview also tilts/yaws the camera for perspective, which the 2D Fusion graph approximates with a slight rotation.

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
