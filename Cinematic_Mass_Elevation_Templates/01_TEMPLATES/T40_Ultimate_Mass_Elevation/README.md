# T40 - Ultimate Mass Elevation

**Category:** H - Signature Hero Elevation  |  **Duration:** 240 frames (10.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

Flagship: a distant light on a dark horizon grows into volumetric shafts that the title cuts through; a single controlled detonation of light crowns the hero, who then holds in burnished bronze.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 75 | Near-black opening with drifting haze and a far horizon light; slow dolly; the title rises from below the horizon as a backlit silhouette, its letters casting light shafts toward the camera. |
| Impact / reveal | ~114 | Impact: the horizon light flares into an anamorphic streak, the bronze surface ignites (rim + key), a soft pressure ring and a restrained ember burst, short camera shake, then a premium light sweep. |
| Hero hold | 114 - 196 | Stable, readable title. Camera: Continuous slow dolly-in with a slight rise; one brief decaying shake at impact; still during the hold. |
| Exit | 196 - 232 | The light collapses: a horizontal light slit closes over the title like a shutter, leaving a final anamorphic line that shrinks to a point and fades out. |

**Material / look:** Burnished bronze (brushed metal, warm environment reflection, gold rim) with 2.5D perspective extrusion.

**Techniques:** horizon light source, occluded volumetric shafts, silhouette rise, perspective extrusion, anamorphic flare, pressure ring, ember burst, light sweep, light-slit shutter exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T40_Ultimate_Mass_Elevation.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T40_Ultimate_Mass_Elevation.comp` | Flat Fusion **composition** (95 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T40_Ultimate_Mass_Elevation.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T40 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Cinzel Black** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
