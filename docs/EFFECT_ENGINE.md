# Effect, transition, typography, colour, audio & motion engines

All creative building blocks are **parameterised definitions** (`registry/base.py → Definition`) with
`id, name, category, parameters (typed, bounded, with grid steps), defaults, constraints, preview, render_function,
performance_cost`. Values from the AI/plan are clamped by `Definition.resolve()` before they reach a filter string,
so parameters are always numbers in range or whitelisted enums. Thousands of configurations come from parameter
grids — no asset files are duplicated. Counts below are reported by `/library/stats` (product of each parameter’s
grid size, summed per registry).

| Registry | Definitions | Parameter combinations | Endpoint |
|---|---:|---:|---|
| Effects | 29 | 70,132 | `GET /effects` |
| Transitions | 71 | 97,186 | `GET /transitions` |
| Text animations | 19 | 237,300 | `GET /text-animations` |
| Text styles | 16 | 4,660,992 | `GET /text-styles` |
| Colour presets | 21 (+ any parameter overrides) | — | `GET /color-presets` |
| Motion presets | 13 | 143 | `GET /motion-presets` |
| Audio presets | 5 | 165 | `GET /audio-presets` |
| Templates | 21 | — | `GET /templates` |

Every entry has a live-rendered preview: `GET /library/preview/{kind}/{id}` (PNG, cached).

## Effects (`registry/effects.py`)
Families: **blur** (gaussian, directional `dblur`, temporal motion blur `tmix`, box/lens, zoom/radial), **glow**
(soft glow, highlight bloom, neon, halation — blended in planar RGB), **distortion** (lens, barrel, fisheye,
chromatic aberration, wave/ripple via `geq`), **light** (procedural light leak and flare via `gradients`, flash,
exposure pulse, glow pulse), **stylise** (film grain, vignette, scanlines, VHS, glitch, pixelate, sharpen,
letterbox, black & white, mirror). Each renders an FFmpeg filter-graph fragment `[in]…[out]`; every effect is
render-tested at default/min/max parameters by the test suite.

## Transitions (`registry/transitions.py`)
* **Native** FFmpeg `xfade`: crossfade, dissolve, fades, dip to black/white, wipes (4 + 4 diagonal), slides, smooth
  pushes, cover/reveal, circle/rect crop, open/close masks, slices, wind, radial, squeeze, distance (morph),
  pixelize, hblur, zoom-in.
* **Procedural** (numpy/OpenCV, run only on the overlap frames): zoom through (in/out), spin/rotate, whip pan
  (motion-blurred), blur dissolve, RGB split, glitch (block displacement), flash, film burn, light leak,
  kaleidoscope, shape masks (diamond/bars/blinds). Each has easing (linear, ease-in/out, expo-out) and parameters.
* Failure policy: any transition failure degrades to a hard cut at its midpoint (duration preserved).

## Typography (`registry/text.py`, `render/text_ass.py`)
16 styles × 19 animations rendered through libass (ASS subtitles) with the bundled OFL fonts. Animations: fade,
fade-up, slide, scale, tracking reveal, typewriter, mask (clip-wipe) reveal, blur reveal, split reveal, bounce,
elastic, pop, kinetic word pop, word-by-word, character-by-character, line-by-line, karaoke. Text is **measured
with the real font metrics** (Pillow), auto-wrapped and kept inside platform safe areas (vertical formats reserve
top/bottom UI zones); violations are reported to QC. Captions: grouped by length/duration/punctuation, styles
`karaoke`, `word_highlight`, `bounce`, `pop`, `kinetic`, `minimal_documentary`, `cinematic_subtitle`; SRT + VTT export.

## Colour (`registry/color.py`)
One numpy grading model is the source of truth: exposure (stops), white balance (temperature/tint), lift/gamma/gain
per channel, contrast around a pivot + S-curve, shadows/highlights, whites/blacks, split toning, hue rotation,
saturation, vibrance, selective (orange/blue/green/red) saturation, fade, monochrome. It is baked into a 33³
`.cube` LUT and applied with `lut3d` (tetrahedral); finishing (vignette, grain, sharpen, halation) is added as
filters. Pipeline: **TechnicalGrade** (per-shot match to reference/project target, conservative partial correction)
→ **CreativeGrade** (preset) → finishing. 21 presets: Cinematic Neutral, Modern Film, Warm/Cool Documentary, Teal &
Orange, Golden Hour, Night Cinema, Moody, Clean Commercial, Soft Wedding, Concert, Sports, Corporate, Vintage Film,
Black & White, High Contrast, Pastel, Muted, Bleach Bypass, Cyberpunk, Natural. User `.cube` files can be uploaded.

## Motion (`registry/motion.py`)
Presets return `(zoom, dx, dy, rotation)` for normalised time; the renderer applies them per frame with sub-pixel
`warpAffine` (no integer zoompan jitter): static, push-in, pull-out, pan L/R, tilt U/D, Ken Burns, handheld,
impact shake, simulated orbit, whip, subtle drift.

## Audio & SFX (`registry/audio.py`)
Dialogue chains (FFmpeg): high-pass, FFT noise reduction (`afftdn`), mud cut, presence lift, de-esser, compression.
Procedural, royalty-free SFX: whoosh, transition, sweep, impact, hit, riser, downer, click, pop, shimmer, ambient.
User SFX/voice-over files are supported.
