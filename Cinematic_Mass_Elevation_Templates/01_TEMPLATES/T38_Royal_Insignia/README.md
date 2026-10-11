# T38 - Royal Insignia

**Category:** H - Signature Hero Elevations  |  **Duration:** 196 frames (8.17s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

An original heraldic insignia - rings, ticks, laurel arcs, chevron crest - assembles piece by piece around the title.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 43 | Ordered assembly: rings sweep on, ticks and beads click around the dial, laurel leaves bloom up both sides, chevrons slide in, banner rules extend - while the whole emblem settles its rotation. |
| Impact / reveal | ~80 | At the impact frame the emblem locks: a gold glint sweeps it, the title appears on the banner with a light sweep. |
| Hero hold | 80 - 156 | Stable, readable title. Camera: Near-static premium framing with a very slow push; dust motes drift in the light. |
| Exit | 156 - 190 | The emblem rotates and expands past the camera while dissolving; the title fades a beat later. |

**Material / look:** Polished gold insignia (ACCENT), embossed with a soft top light; ivory-silver title; deep royal velvet.

**Techniques:** procedural emblem from primitives, staggered assembly, emboss shading, counter-rotating rings, light sweep / glint, independent emblem scale & rotation controls

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T38_Royal_Insignia.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T38_Royal_Insignia.comp` | Flat Fusion **composition** (119 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T38_Royal_Insignia.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T38 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Cinzel Decorative Black** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | FAIL: preview missing or truncated |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
