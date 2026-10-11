# T14 - Forged in Fire

**Category:** C - 3D Metal and Premium Materials  |  **Duration:** 228 frames (9.50s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A dark smithy: a glowing blank of iron is hammered, strike by strike, into razor-sharp letterforms.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 39 | A soft, swollen, dull-red billet in the rough shape of the title heats up in the dark; three hammer strikes (left, right, centre) each flatten it, sharpen the edges and throw sparks. |
| Impact / reveal | ~112 | The final strike on the impact frame locks the crisp forged title at white-orange heat; glowing seams pulse, then the metal cools in a controlled way to dark hammered iron with ember-red seams. |
| Hero hold | 112 - 184 | Stable, readable title. Camera: Static, heavy framing with a hard jolt on every strike and a slow creep-in during cooling. |
| Exit | 184 - 220 | The last heat drains from the seams and quench steam rolls over the cold iron until it is gone. |

**Material / look:** Hammered dark iron (concrete-grain bump, flat chamfer) with emissive heat driven by a blackbody ramp; edge and crack seams stay hot longest; forge underlight from below.

**Techniques:** 2.5D extrusion stack, multi-strike timing, progressive sharpening, spark bursts, emissive heat ramp, glowing seams, controlled cooling, quench steam

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T14_Forged_In_Fire.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T14_Forged_In_Fire.comp` | Flat Fusion **composition** (74 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T14_Forged_In_Fire.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T14 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Staatliches Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

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
