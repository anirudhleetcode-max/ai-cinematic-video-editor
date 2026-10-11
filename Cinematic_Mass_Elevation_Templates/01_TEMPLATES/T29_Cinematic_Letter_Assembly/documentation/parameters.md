# T29 Cinematic Letter Assembly - Parameter Reference

## A. Fusion macro controls (DaVinci Resolve Inspector)

These are the controls published on the macro. Every timing/look slider listed here is referenced by at least one expression in the composition (unreferenced controls are removed automatically at build time), so each one drives the animation.

| Inspector label | Page | Drives (tool.input) |
|---|---|---|
| Animation Start (frames) | Timing | `CONTROLS.AnimStart` |
| Reveal Duration (frames) | Timing | `CONTROLS.AnimDuration` |
| Impact Frame | Timing | `CONTROLS.ImpactFrame` |
| Exit Start (frame) | Timing | `CONTROLS.ExitStart` |
| Exit Duration (frames) | Timing | `CONTROLS.ExitDuration` |
| Background Intensity | Look | `CONTROLS.BackgroundIntensity` |
| Particle Intensity | Look | `CONTROLS.ParticleIntensity` |
| Glow Strength | Look | `CONTROLS.GlowStrength` |
| Shadow Strength | Look | `CONTROLS.ShadowStrength` |
| Text Scale | Look | `CONTROLS.TextScale` |
| Text Position X | Look | `CONTROLS.TextPosX` |
| Text Position Y | Look | `CONTROLS.TextPosY` |
| Text Rotation | Look | `CONTROLS.TextRotation` |
| Motion Blur Amount | Look | `CONTROLS.MotionBlurAmount` |
| Letterbox (2.39:1) | Look | `CONTROLS.Letterbox` |
| Stagger Interval (frames) | Timing | `CONTROLS.StaggerFrames` |
| Accent Color | Look | `ACCENT.TopLeftRed` |
| Accent Color | Look | `ACCENT.TopLeftGreen` |
| Accent Color | Look | `ACCENT.TopLeftBlue` |
| Main Title | Text | `MainTitle.StyledText` |
| Main Title Font | Text | `MainTitle.Font` |
| Main Title Style | Text | `MainTitle.Style` |
| Main Title Size | Text | `MainTitle.Size` |
| Main Title Letter Spacing | Text | `MainTitle.CharacterSpacing` |
| Main Title Line Spacing | Text | `MainTitle.LineSpacing` |
| Main Title Alignment | Text | `MainTitle.HorizontalJustificationNew` |
| Main Title Color | Text | `MainTitle.Red1` |
| Main Title Color | Text | `MainTitle.Green1` |
| Main Title Color | Text | `MainTitle.Blue1` |
| Subtitle | Text | `Subtitle.StyledText` |
| Subtitle Font | Text | `Subtitle.Font` |
| Subtitle Style | Text | `Subtitle.Style` |
| Subtitle Size | Text | `Subtitle.Size` |
| Subtitle Letter Spacing | Text | `Subtitle.CharacterSpacing` |
| Subtitle Line Spacing | Text | `Subtitle.LineSpacing` |
| Subtitle Alignment | Text | `Subtitle.HorizontalJustificationNew` |
| Subtitle Color | Text | `Subtitle.Red1` |
| Subtitle Color | Text | `Subtitle.Green1` |
| Subtitle Color | Text | `Subtitle.Blue1` |

### Timing/look control meanings

- **CONTROLS.AnimStart** - Frame where the build-up/reveal animation starts.
- **CONTROLS.AnimDuration** - Length of the title reveal in frames.
- **CONTROLS.ImpactFrame** - Frame of the main impact; flashes, shake, bursts and rings key off this.
- **CONTROLS.ExitStart** - Frame where the exit begins.
- **CONTROLS.ExitDuration** - Exit length in frames.
- **CONTROLS.BackgroundIntensity** - Scales environment lights/atmosphere.
- **CONTROLS.ParticleIntensity** - Scales particle emission (0 disables particles).
- **CONTROLS.GlowStrength** - Scales glows, rim light and light sweeps.
- **CONTROLS.ShadowStrength** - Scales the title's drop/contact shadow.
- **CONTROLS.TextScale** - Overall title scale.
- **CONTROLS.TextPosX** - Title centre X (0 = left edge, 1 = right edge).
- **CONTROLS.TextPosY** - Title centre Y (0 = bottom, 1 = top).
- **CONTROLS.TextRotation** - Title rotation in degrees.
- **CONTROLS.MotionBlurAmount** - Scales directional/motion blur on fast moves.
- **CONTROLS.Letterbox** - Blend of the 2.39:1 letterbox bars (0 = off).
- **CONTROLS.StaggerFrames** - 

## B. Reference renderer parameters (`render_title.py`)

Used by the Python reference renderer that produced the preview (also usable for customised renders without Resolve). Defaults for this template:

| Parameter | Default | Meaning |
|---|---|---|
| `MAIN_TITLE` | "ASCENDANT" | Main title text (use \n for a line break) |
| `SUBTITLE` | "A STORY IN NINE LETTERS" | Secondary line under the title |
| `OPTIONAL_TAGLINE` | "" | Small tagline / credit line |
| `FONT_FAMILY` | "cinzel_bold" | Font key (see 02_SHARED_ASSETS/Fonts/README.md) |
| `SUB_FONT_FAMILY` | "teko" | Subtitle/tagline font key |
| `FONT_SIZE` | 0.0 | Cap height as fraction of frame height (0 = auto-fit to width) |
| `TITLE_WIDTH` | 0.7 | Auto-fit target width as fraction of frame width |
| `LETTER_SPACING` | 0.12 | Extra letter spacing in em |
| `LINE_SPACING` | 1.0 | Line spacing multiplier |
| `TEXT_ALIGNMENT` | "center" | left | center | right (multi-line titles) |
| `TEXT_POSITION_X` | 0.5 | Title centre X (0..1, left to right) |
| `TEXT_POSITION_Y` | 0.5 | Title centre Y (0..1, bottom to top, Fusion convention) |
| `TEXT_SCALE` | 1.0 | Overall title scale |
| `TEXT_ROTATION` | 0.0 | Title rotation in degrees |
| `TEXT_COLOR` | "#EDE6D8" | Primary text / material tint colour |
| `ACCENT_COLOR` | "#C9A46A" | Accent colour (light, energy, particles) |
| `SHADOW_STRENGTH` | 0.55 | Drop/contact shadow strength 0..1 |
| `GLOW_STRENGTH` | 1.0 | Glow / bloom strength multiplier |
| `EXTRUSION_DEPTH` | 1.0 | Extrusion depth multiplier (0 = flat) |
| `BEVEL_AMOUNT` | 1.0 | Bevel width multiplier |
| `ANIMATION_START` | 8 | Frame where the title animation begins |
| `ANIMATION_DURATION` | 28 | Reveal duration in frames |
| `IMPACT_FRAME` | 82 | Frame of the main impact / reveal accent |
| `HOLD_DURATION` | 56 | Hero hold length in frames (informational marker) |
| `EXIT_START` | 140 | Frame where the exit begins |
| `EXIT_DURATION` | 28 | Exit length in frames |
| `BACKGROUND_INTENSITY` | 1.0 | Environment brightness multiplier |
| `PARTICLE_INTENSITY` | 1.0 | Particle count/brightness multiplier (0 disables) |
| `MOTION_BLUR_AMOUNT` | 1.0 | Motion blur multiplier for fast moves |
| `IMPACT_INTENSITY` | 1.0 | Impact flash / shockwave strength |
| `SHAKE_AMOUNT` | 1.0 | Camera shake multiplier (0 disables) |
| `LETTERBOX` | 1.0 | 2.39:1 letterbox amount (0 = full frame) |
| `DURATION` | 180 | Total length in frames |
| `QUALITY` | "preview" | preview | final |

Parameters this template's preview renderer actually reads are listed in `manifest.json` under `reference_renderer.parameters_used`; others have no effect for this design.

## C. Manual-edit notes

- Per-letter animation: the preview animates every glyph on its own 3D arc. Fusion's per-character Text+ Follower could not be verified offline, so the Fusion graph keeps ONE editable Text+ and staggers 8 vertical slices ('LetterSlot0..7', RectangleMask slots across the title width) instead. For other title lengths, adjust the slot masks' Center/Width to match the letters.
- Extra control 'Stagger Interval (frames)' (StaggerFrames) sets the base interval between arrivals; the designed rhythm multiplies it per slot. 'Reveal Duration' (AnimDuration) is the travel time of each letter/slot. In the preview the interval is the design default STAGGER_FRAMES (4).
