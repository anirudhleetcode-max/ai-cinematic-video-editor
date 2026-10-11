# T36 - Hero Silhouette

**Category:** H - Signature Hero Elevations  |  **Duration:** 168 frames (7.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A lone caped figure stands in smoke against a blinding backlight; the title racks into focus in front of it.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 33 | Rack focus: the title starts large, soft and dim in the foreground and pulls into focus while the backlight slowly rises behind the abstract figure silhouette. |
| Impact / reveal | ~60 | Backlight surge at the impact frame: light rays burst around the silhouette, smoke billows outward, title rim ignites. |
| Hero hold | 60 - 132 | Stable, readable title. Camera: Controlled crane-up and push; smoke, figure and light source at three parallax depths. |
| Exit | 132 - 164 | The backlight dies, the title racks back out of focus and the figure dissolves into the smoke. |

**Material / look:** Brushed silver title with warm backlit rim; procedural figure silhouette with light-wrapped edges.

**Techniques:** procedural figure silhouette (primitives), occluded god rays, lit volumetric smoke, rack focus, light wrap on silhouette edges, backlight surge

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T36_Hero_Silhouette.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T36_Hero_Silhouette.comp` | Flat Fusion **composition** (57 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T36_Hero_Silhouette.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T36 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Teko SemiBold** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
