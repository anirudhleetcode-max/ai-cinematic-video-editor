# T18 - Dark Sorcery

**Category:** D - Mythic, Epic and Fantasy  |  **Duration:** 192 frames (8.00s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

An occult invocation: a ritual circle of original runes ignites in swirling smoke and summons the title.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 44 | Smoke spirals inward around a vertical ritual circle whose rings trace on and whose runes ignite one by one; the letters condense out of the vortex through a spiral, edge-glowing dissolve. |
| Impact / reveal | ~82 | At the impact frame the circle flares, an energy ring pulses outward and the runes burn bright, then settle to a slow, breathing glow behind a smoked-silver title. |
| Hero hold | 82 - 146 | Stable, readable title. Camera: Locked-off with a slow creeping push and a subtle counter-rotation of the circle layers. |
| Exit | 146 - 180 | The circle collapses inward and the title is twisted into the vortex and swallowed by the smoke. |

**Material / look:** Smoked dark silver with violet rim light and faint inner glow along the edges; glowing runes and rings are emissive and drawn behind the title only.

**Techniques:** procedural original runes, concentric energy rings, polar smoke vortex, spiral dissolve, energy pulse ring, swirl-warp exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T18_Dark_Sorcery.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T18_Dark_Sorcery.comp` | Flat Fusion **composition** (88 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T18_Dark_Sorcery.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T18 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Marcellus SC Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Fusion notes and limitations

- The Fusion version draws 6 representative runes as PolylineMasks on a rotating Transform; the preview renders the full 29-rune circle. Add or reshape runes by editing the RuneN polylines.

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
