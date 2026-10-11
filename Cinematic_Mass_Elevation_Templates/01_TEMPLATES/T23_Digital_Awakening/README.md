# T23 - Digital Awakening

**Category:** E - Sci-Fi and Futuristic Motion Graphics  |  **Duration:** 216 frames (9.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A system boots: scattered data points and procedural lines organise themselves into a stable wordmark.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 51 | Hundreds of disorganised points and short data lines drift in depth, then converge in a left-to-right wave onto a lattice inside the letterforms, forming a wireframe of the title. |
| Impact / reveal | ~104 | At the impact frame the point-lattice resolves block-by-block into the solid wordmark with an edge pulse. |
| Hero hold | 104 - 178 | Stable, readable title. Camera: Slow drift-in with depth parallax on the background node lattice. |
| Exit | 178 - 208 | Decompile: the wordmark de-resolves block-by-block back into points that float upward and dissipate. |

**Material / look:** Clean white emissive face with a mint inner edge; mint data points and lines on a deep navy void.

**Techniques:** glyph-sampled point cloud, plexus lines, data streaks, block resolve, node lattice, decompile exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T23_Digital_Awakening.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T23_Digital_Awakening.comp` | Flat Fusion **composition** (53 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T23_Digital_Awakening.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T23 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Orbitron Medium** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
