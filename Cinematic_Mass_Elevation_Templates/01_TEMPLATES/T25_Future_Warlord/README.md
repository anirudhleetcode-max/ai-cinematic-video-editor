# T25 - Future Warlord

**Category:** E - Sci-Fi and Futuristic Motion Graphics  |  **Duration:** 228 frames (9.50s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A tactical unveiling: armoured blast shutters part inside a targeting visor to reveal the warlord's name.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 46 | A restrained HUD boots (brackets search, then lock onto a recessed bay); the bay's twin armoured shutters unlock with a small jolt. |
| Impact / reveal | ~96 | At the impact frame the shutters slam open, the title pushes forward out of the recess under a hard top light; dust shakes off the frame and the HUD settles to quiet corner brackets. |
| Hero hold | 96 - 186 | Stable, readable title. Camera: Static tripod with a heavy slam shake; the HUD is a stable visor overlay (unaffected by shake). |
| Exit | 186 - 212 | The shutters slam closed again and the HUD powers down line by line. |

**Material / look:** Matte military ceramic lettering; brushed gunmetal shutters with accent hazard stripes; HUD in ACCENT.

**Techniques:** HUD bracket lock-on, reticle, mechanical shutters, staged unlock, slam shake, dust shake-off, visor overlay

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T25_Future_Warlord.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T25_Future_Warlord.comp` | Flat Fusion **composition** (101 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T25_Future_Warlord.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T25 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Black Ops One Regular** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Fusion notes and limitations

- HUD elements (BracketFrame*, Reticle*, RangeTicks) follow the Accent colour; their brightness is the 'HUD' merges' Blend.
- Shutter plates are RectangleMask-driven solids (ShutterTop/ShutterBottom) clipped to the bay.

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
