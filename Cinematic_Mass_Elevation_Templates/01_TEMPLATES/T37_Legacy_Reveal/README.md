# T37 - Legacy Reveal

**Category:** H - Signature Hero Elevations  |  **Duration:** 228 frames (9.50s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A quiet, premium tribute reveal for a name, an event or a dedication: warm light, soft bokeh, letters arriving one by one like a held breath.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 60 | Letter-by-letter fade with a gentle upward settle and slight tracking contraction; a gold hairline draws outward beneath. |
| Impact / reveal | ~100 | At the impact frame a slow warm light sweep glides across the letters and the scene gently brightens (no shake). |
| Hero hold | 100 - 180 | Stable, readable title. Camera: Very slow push-in with a subtle drift; bokeh and motes at different depths provide restrained parallax. |
| Exit | 180 - 224 | Everything softly lifts and dissolves into warm glow, letters fading last-to-first, to warm black. |

**Material / look:** Satin ivory serif with a soft gold edge light; gold ornamental rule.

**Techniques:** per-glyph staggered fade, gold hairline ornament, drifting bokeh layer, floating motes with depth of field, slow light sweep, warm light leak

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T37_Legacy_Reveal.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T37_Legacy_Reveal.comp` | Flat Fusion **composition** (81 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T37_Legacy_Reveal.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T37 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Marcellus SC Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
