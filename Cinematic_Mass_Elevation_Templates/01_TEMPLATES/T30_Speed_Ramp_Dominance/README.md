# T30 - Speed Ramp Dominance

**Category:** F - Cinematic Typography and Camera Movement  |  **Duration:** 144 frames (6.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

Pure momentum: the title rockets in from the vanishing point and slams into an almost-frozen slow-motion hold.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 13 | A hyper-fast approach from the vanishing point through rushing speed lines, with zoom/directional blur proportional to velocity, then a hard speed-ramp deceleration. |
| Impact / reveal | ~22 | At the impact frame the title brakes to a near standstill: red edge flash, anamorphic streak, speed lines freeze and drift; a slow-motion creep carries the long, readable hold. |
| Hero hold | 22 - 110 | Stable, readable title. Camera: Forward rush with impact jolt; then a barely-moving slow-motion creep. |
| Exit | 110 - 126 | Reverse ramp: the title accelerates away into the vanishing point with zoom blur as the lines rush again. |

**Material / look:** Gloss white enamel with red (ACCENT) rim and impact accent.

**Techniques:** speed ramp curve, velocity-scaled zoom blur, radial speed lines, impact freeze, anamorphic streak, slow-motion creep, reverse ramp exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T30_Speed_Ramp_Dominance.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T30_Speed_Ramp_Dominance.comp` | Flat Fusion **composition** (41 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T30_Speed_Ramp_Dominance.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T30 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Russo One Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Fusion notes and limitations

- Motion blur: 'Motion Blur Amount' scales the DirectionalBlur (Zoom type) length on the title and on the speed-line field.

## Check in Resolve (unconfirmed input names)

These inputs are set in the macro but their names could not be confirmed against documentation. Fusion ignores unknown inputs when it loads a file, so if one is wrong only that setting falls back to its default. Check these first when you open the template:

`DirectionalBlur.EffectMask`

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
