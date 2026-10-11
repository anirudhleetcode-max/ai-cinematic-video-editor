# T39 - Final Boss

**Category:** H - Signature Hero Elevations  |  **Duration:** 156 frames (6.50s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

The last enemy arrives: a massive dark-iron title slams out of the abyss and holds, breathing red.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 23 | A long ominous build (smoke, heartbeat red underlight), then a very fast 10-frame launch from deep space straight at the lens with zoom motion blur. |
| Impact / reveal | ~28 | Hard impact: short violent shake, layered smoke blasts outward, red underlight flares; then a dead-stable hero hold. |
| Hero hold | 28 - 130 | Stable, readable title. Camera: Aggressive low three-quarter perspective on the extruded title; locked-off after a short impact shake. |
| Exit | 130 - 148 | The red light cuts and the title is yanked back into the abyss in a fast pull. |

**Material / look:** Pitted dark iron, deep 2.5D extrusion, blood-red underlight and rim pulsing with a heartbeat.

**Techniques:** fast z-launch with zoom blur, deep perspective extrusion, 3-layer smoke with radial blast, heartbeat-driven underlight, short impact shake, snap-back exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T39_Final_Boss.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T39_Final_Boss.comp` | Flat Fusion **composition** (74 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T39_Final_Boss.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T39 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Black Ops One Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
