# T10 - Shockwave Dominance

**Category:** B - Fire, Explosions and Impact  |  **Duration:** 156 frames (6.50s @ 24 fps)  |  **Depth:** 2.5D

![thumbnail](preview/thumbnail.jpg)

A title that lands like a strike: everything around it is pushed outward by a radial shockwave.

## Animation structure

| Phase | Default frames | What happens |
|---|---|---|
| Build-up | 0 - 15 | A short inhale (the air darkens and haze is pulled inward), then the title slams down from in front of the camera, accelerating into its mark with zoom blur. |
| Impact / reveal | ~26 | Radial impact: a crisp crimson ring, a wide pressure-haze ring and a refraction band travel outward independently of the title; light rays stream from behind the letters. |
| Hero hold | 26 - 124 | Stable, readable title. Camera: Hard zoom kick and short violent shake at the strike, then a slow dominant push-in. |
| Exit | 124 - 150 | Implosion: a ring collapses back inward while the title compresses into a point of light. |

**Material / look:** Polished dark chrome with crimson rim and floor reflection tint, hard drop shadow on the haze.

**Techniques:** accelerating slam with zoom blur, inhale anticipation, independent shockwave ring(s), refraction displacement band, volumetric rays through letter gaps, implosion exit

**Depth model:** **2.5D** (layered 2D compositing: masks, offset extrusion stack, parallax, light passes). No 3D geometry.

## Files

| File | Purpose |
|---|---|
| `source/T10_Shockwave_Dominance.setting` | Fusion **macro** (editable title with published controls). Install as an Edit-page title or drag into the Fusion page. |
| `source/T10_Shockwave_Dominance.comp` | Flat Fusion **composition** (79 tools) for Fusion Studio / Resolve Fusion page import. Final node: `Letterbox`. |
| `preview/T10_Shockwave_Dominance.mp4` | 1920x1080 preview from the Python **reference renderer** (see note below). |
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
python 06_AUTOMATION/Scripts/render_title.py T10 --set MAIN_TITLE="YOUR TITLE" --set SUBTITLE="YOUR LINE" --out my_title.mp4
```

Default font: **Teko SemiBold** (OFL, bundled in `02_SHARED_ASSETS/Fonts/` - install it before opening the macro, or pick any installed font in the Inspector).

## Fusion notes and limitations

- The shockwave is fully independent of the title: ShockRingPrimary / ShockRingHaze (expanding EllipseMask rings) and ShockRefraction (Displace driven by RefractRingShape) all key off Impact Frame and scale with Impact Intensity. Move their Center inputs together to relocate the impact point.

## Check in Resolve (unconfirmed input names)

These inputs are set in the macro but their names could not be confirmed against documentation. Fusion ignores unknown inputs when it loads a file, so if one is wrong only that setting falls back to its default. Check these first when you open the template:

`Displace.Foreground`, `pEmitter.Transform3DOp.Translate.Y`, `pRender.Height`, `pRender.UseFrameFormatSettings`, `pRender.Width`, `pTurbulence.XStrength`, `pTurbulence.YStrength`, `pTurbulence.ZStrength`

## Verification status (honest)

| Level | Status |
|---|---|
| Fusion source parses as Lua table (real Lua interpreter) | PASS |
| Graph structure (connections, expression references, published controls) | PASS |
| Opened / rendered inside DaVinci Resolve or Fusion | **NOT TESTED (DaVinci Resolve/Fusion not available in the build environment)** |
| Preview video rendered and checked (ffprobe, duration, size, non-black) | PASS |

The preview was rendered by this project's Python reference renderer, which implements the same design, timing and controls but is **not** Fusion. Expect the Fusion render to differ in detail (noise character, particle look, glow falloff). See `COMPATIBILITY_REPORT.md` at the project root.
