# T17 - Celestial Ascent

**Category:** D - Mythic, Epic and Fantasy  |  **Duration:** 210 frames (8.75s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A heavenly reveal high above the cloud sea: the title descends through luminous clouds into sunlight.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 53 | The camera climbs out of a bank of glowing cloud; layered clouds stream past the lens while the pale title descends slowly from above into frame, half-veiled by passing vapour. |
| Impact / reveal | ~96 | On the impact frame the sun crests directly behind the letters: volumetric shafts of light fan out around the title and its edges ignite with a warm-white rim. |
| Hero hold | 96 - 162 | Stable, readable title. Camera: Measured vertical ascent (cloud layers parallax downward), slow push; no shake. |
| Exit | 162 - 204 | The title keeps ascending up and out of frame into the light while the clouds close beneath the camera. |

**Material / look:** Backlit alabaster/ivory stone with soft specular, strong warm-white rim from the sun behind, gentle 2.5D depth; atmospheric scattering softens the far cloud sea.

**Techniques:** layered cloud parallax, volumetric god rays (radial smear of occluded sun), backlit rim, cloud pass-through, descending title, ascend-out exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T17_Celestial_Ascent.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T17_Celestial_Ascent.comp` | Flat Fusion **composition** (56 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T17_Celestial_Ascent.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T17 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Cinzel Bold** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Fusion notes and limitations

- God rays are made with a Zoom-type DirectionalBlur of the sun disc masked by the inverted title and cloud alpha (no dedicated Rays tool is used, for compatibility). Move SunCore/RaysSmear centre together if you reposition the title.

## Check in Resolve (unconfirmed input names)

These inputs are set in the macro but their names could not be confirmed against documentation. Fusion ignores unknown inputs when it loads a file, so if one is wrong only that setting falls back to its default. Check these first when you open the template:

`pEmitter.Transform3DOp.Translate.Y`, `pRender.Height`, `pRender.UseFrameFormatSettings`, `pRender.Width`, `pTurbulence.XStrength`, `pTurbulence.YStrength`, `pTurbulence.ZStrength`

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
