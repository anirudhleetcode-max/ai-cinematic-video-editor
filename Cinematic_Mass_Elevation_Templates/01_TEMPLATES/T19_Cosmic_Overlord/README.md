# T19 - Cosmic Overlord

**Category:** D - Mythic, Epic and Fantasy  |  **Duration:** 236 frames (9.83s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A sovereign title assembles like a constellation above a planet while a star rises over its limb.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 66 | A slow camera approach through three parallax star layers and drifting nebula; the letters drift in from deep space as points of light, linked by fading constellation lines, and lock into place. |
| Impact / reveal | ~118 | On the impact frame the star crests the planet's limb: the atmosphere ignites, a restrained anamorphic flare crosses the frame and the metal letters catch a warm sunrise rim. |
| Hero hold | 118 - 192 | Stable, readable title. Camera: Continuous forward dolly (star layers expand at different rates = parallax), gentle drift. |
| Exit | 192 - 226 | The camera keeps travelling: it flies through the title, which swells past the lens as stars stretch. |

**Material / look:** Dark blue-steel with cool space reflections and a warm sunrise rim from below; glyphs are born as emissive star points that cool into metal.

**Techniques:** 3-layer star parallax, animated nebula, planet limb + atmosphere, constellation assembly, per-glyph depth convergence, sunrise flare, fly-through exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T19_Cosmic_Overlord.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T19_Cosmic_Overlord.comp` | Flat Fusion **composition** (64 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T19_Cosmic_Overlord.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T19 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Audiowide Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Fusion notes and limitations

- Per-glyph constellation convergence is approximated in Fusion by a point-cell dissolve plus scale/blur convergence of the whole title (TextPlus has no per-character transforms without a Follower modifier).
- Star layers are pEmitter fields rendered by pRender and scaled by expressions for parallax.

## Check in Resolve (unconfirmed input names)

These inputs are set in the macro but their names could not be confirmed against documentation. Fusion ignores unknown inputs when it loads a file, so if one is wrong only that setting falls back to its default. Check these first when you open the template:

`pRender.Height`, `pRender.UseFrameFormatSettings`, `pRender.Width`

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
