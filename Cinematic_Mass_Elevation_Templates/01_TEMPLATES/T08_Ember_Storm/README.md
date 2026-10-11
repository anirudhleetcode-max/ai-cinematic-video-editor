# T08 - Ember Storm

**Category:** B - Fire, Explosions and Impact  |  **Duration:** 240 frames (10.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A slow, elegant reveal inside a storm of embers layered in depth - cinematic focus does the storytelling.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 59 | Rack focus: the shot opens focused on foreground embers with the title a soft glow behind smoke; focus pulls slowly to the title plane while the smoke thins. |
| Impact / reveal | ~118 | As focus locks, a gentle warm swell blooms behind the letters, the embers swirl and a satin sheen glides across. |
| Hero hold | 118 - 192 | Stable, readable title. Camera: Slow lateral crane with real parallax between three ember depth layers; selective focus (bokeh near and far). |
| Exit | 192 - 240 | Focus racks back to the near embers; the title melts into bokeh and fades with the storm. |

**Material / look:** Satin gold with soft warm reflections and an ember-orange rim; embers glow with flicker and bokeh.

**Techniques:** three-layer particle depth, animated focus distance (rack focus), bokeh / DOF, parallax crane, light swell, satin sweep

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T08_Ember_Storm.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T08_Ember_Storm.comp` | Flat Fusion **composition** (63 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T08_Ember_Storm.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T08 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Marcellus SC Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Check in Resolve (unconfirmed input names)

These inputs are set in the macro but their names could not be confirmed against documentation. Fusion ignores unknown inputs when it loads a file, so if one is wrong only that setting falls back to its default. Check these first when you open the template:

`pEmitter.Transform3DOp.Translate.Z`, `pRender.Height`, `pRender.UseFrameFormatSettings`, `pRender.Width`, `pTurbulence.XStrength`, `pTurbulence.YStrength`, `pTurbulence.ZStrength`

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
