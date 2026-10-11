# T32 - Rain and Steel

**Category:** G - Atmospheric and Environmental Cinema  |  **Duration:** 192 frames (8.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A rain-soaked industrial yard at night: wet steel lettering waits in the dark until the floodlights hit.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 31 | The title cranes up from below the eye-line in near darkness, rain falling through cold ambient light. |
| Impact / reveal | ~64 | Three overhead floodlights clunk on in sequence (with a short electrical flicker) - rain turns into lit streaks, the wet steel lights up and its reflection appears on the flooded floor. |
| Hero hold | 64 - 150 | Stable, readable title. Camera: Restrained slow lateral truck (wall, rain and floor at different parallax); tiny clunk shake only. |
| Exit | 150 - 184 | The floodlights cut out one by one; the last silhouette fades with the rain. |

**Material / look:** Dark brushed wet steel: hard top specular, running water streaks over the faces, mirror-wet floor.

**Techniques:** procedural corrugated steel wall, three-depth rain, volumetric floodlight cones, running water specular streaks, rippled floor reflection, rain splash rings

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T32_Rain_And_Steel.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T32_Rain_And_Steel.comp` | Flat Fusion **composition** (79 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T32_Rain_And_Steel.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T32 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Russo One Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
