# Developer Authoring Guide - writing a template design

Every template is ONE Python module: `06_AUTOMATION/Scripts/cmet/designs/tNN.py`.
It defines BOTH implementations of the same design:

1. `fusion(self, g, p)` - builds the **editable Fusion node graph** (the primary deliverable). It is
   serialised to `source/TNN_Slug.setting` (macro with published controls) and `.comp`.
2. `frame(self, c)` - the **reference preview renderer** (NumPy/OpenCV) that produces the 1080p preview
   MP4 and thumbnails, and lets users render customised titles without Resolve.

The two must express the same design: same entrance mechanism, impact timing, environment, exit.
Pixel-exact equality is impossible (different engines) and is not claimed.

Study `designs/t01.py` (Obsidian Impact) and `designs/t02.py` (Thunder God) first - they are the reference
implementations.

## Module skeleton

```python
from .. import core as K, elements as E, fcomp as F
from ..base import Design, comp, drop_shadow, apply_shake, subtitle, flat_rgb
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01, shake
from ..typo import Material, place_extruded, plane_points, place_sprite, fragments, warp_to

class T05(Design):
    ID = "T05"; NAME = "Shattered Monolith"; SLUG = "Shattered_Monolith"
    CATEGORY = "A - Dark Mass Elevation"
    CONCEPT = "..."; ENTRANCE = "..."; REVEAL = "..."; CAMERA = "..."; MATERIAL = "..."; EXIT = "..."
    TECHNIQUES = ["...", "..."]
    TRUE_3D = False            # True only if the Fusion graph uses F.text3d_rig (Text3D/Renderer3D)
    DURATION_FRAMES = 192      # 144..240 (6-10 s @ 24 fps); vary rhythm between templates
    DEFAULTS = dict(MAIN_TITLE="...", SUBTITLE="...", FONT_FAMILY="anton", TEXT_COLOR="#...",
                    ACCENT_COLOR="#...", ANIMATION_START=.., ANIMATION_DURATION=.., IMPACT_FRAME=..,
                    HOLD_DURATION=.., EXIT_START=.., EXIT_DURATION=..)
    SOUND = [(frame, "kind", "description"), ...]   # kinds: see cmet/sfx.py VOICES
    FUSION_NOTES = []          # optional: things a user must edit manually in Fusion

    def frame(self, c): ...    # returns HxWx3 float32 image (display-referred, may exceed 1)
    def fusion(self, g, p): ...

DESIGN = T05()
```

## Preview renderer API (`frame(self, c)`)

`c` is a `base.Ctx`:
- `c.t` seconds, `c.fr` frame, `c.W/c.H`, `c.k = H/1080` (scale all pixel sizes by it), `c.p` params
  (read via `c.p["KEY"]` - reads are tracked and reported in the manifest; **every parameter you document
  as functional must actually be read**).
- Timing (seconds): `c.start`, `c.reveal`, `c.impact`, `c.exit_start`, `c.exit_dur`, `c.dur`,
  `c.reveal_u(delay=0, dur=None)` (0..1), `c.exit_u()` (0..1), `c.hit(attack, decay)` impact envelope
  (already scaled by IMPACT_INTENSITY), `c.shake(amp, decay, freq)` (already scaled by SHAKE_AMOUNT).
- Title: `c.title(boost=1.0)` -> `TextSprite` (mask, glyphs, ink box, anchor, cap_px). `boost>1` rasterises
  larger for extreme scale-ups (T26). `c.sub(key="SUBTITLE")` for subtitle/tagline sprites.
- Material shading: `sh = c.shaded(Material(...))`; `rgb, a = sh.shade(light=(lx,ly,lz), rim_gain=..,
  rim_dir=(0,-1), sweep=(pos,width,angle,gain), base=colour, emissive=HxWx3, light_gain=..,
  env_shift=..)`. `sh.u`, `sh.v` are title-normalised coords (-0.5..0.5), `sh.edge` edge mask,
  `sh.h` bevel height. Always pass `base=K.col(p["TEXT_COLOR"])` (or a function of it) so TEXT_COLOR works.
  `Material` fields: base, spec, spec_power, spec_gain, diffuse, ambient, metal (env reflection weight),
  env_sky/env_horizon/env_ground/env_sharp, bevel (in cap heights), bevel_round, texture
  (none|stone|concrete|brushed|grain|obsidian|ice|facets), tex_amount, bump (keep small, <=0.05), rim, seed.
- Placement / camera: `cam = c.cam(zoom=.., fov_scale=1.6, pan=(px,py), roll=.., tilt=.., yaw=..)`;
  `L = c.layer()`; `c.place(L, cam, rgb, a, sprite, scale, rot=(rx,ry,rz), off=(x,y,z), opacity, add=False)`
  (z>0 = farther away). Composite: `img = comp(bg, L)`. Shadow: `bg = drop_shadow(bg, L, strength, offset, soft, c.k)`.
  - Real perspective extrusion (3D look): `place_extruded(L, cam, rgb, a, (0,0,sp.w,sp.h), sp.anchor,
    (hx,hy,z), scale, rot, depth_px, side_colour, slices=10..24)`.
  - Per-glyph animation: iterate `sp.glyphs` (box, center); use `place_sprite(L, cam, rgb, a, g.box,
    sp.anchor, pos, scale, rot, local=(dx,dy,dz,rx,ry,rz,s,gcx,gcy), opacity)` with `pos=(hx,hy,0)`.
  - Fragments: `fragments(sprite, n, seed)` -> list of (box, centre, mask); place each crop with
    `place_sprite(..., local=...)` (multiply `a` by the fragment mask).
- Environment (`cmet/elements.py`): `fog`, `smoke`, `clouds`, `stars`, `nebula`, `rain`, `Particles` +
  `particle_layer` (depth, DOF, flicker, streaks), `bolt_points` + `draw_lines`, `ring`,
  `shockwave_displace`, `crack_lines` + `draw_partial`, `caustics`, `light_cone`, `hud_layer`.
  Core (`cmet/core.py`): easing (`smooth`, `ease_out`, `ease_in`, `ease_in_out`, `expo_out`, `back_out`,
  `elastic_settle`), `prog`, `pulse`, `window`, `vgrad`, `radial`, `soft_spot`, `grid`, `blur`, `blur_dir`,
  `zoom_blur`, `god_rays`, `fbm_field`, `sample`/`fft_noise`, `remap_offset`.
- Finish: `img = apply_shake(c, img, amp, decay)` then
  `return c.finish(img, vignette=.., grain=.., bloom=(threshold, strength), grade=dict(...), ca=.., streak=(thr, str, len, colour))`
  (letterbox, GLOW_STRENGTH and tonemapping handled inside).
- Subtitle: `img = subtitle(c, img, cam, t_in, t_out, colour, y_rel=0.8)`.
- Parameters you must honour: MAIN_TITLE/SUBTITLE (via c.title/c.sub), FONT_FAMILY, TEXT_COLOR,
  ACCENT_COLOR, BACKGROUND_INTENSITY, PARTICLE_INTENSITY (scale particle counts; 0 = none), GLOW_STRENGTH,
  SHADOW_STRENGTH (if a shadow exists), IMPACT_INTENSITY/SHAKE_AMOUNT (via c.hit/c.shake), timing params via
  `c.start` etc., TEXT_POSITION/SCALE/ROTATION (handled by `c.place`/`c.hero`), EXTRUSION_DEPTH where
  extrusion exists, MOTION_BLUR_AMOUNT where motion blur exists, LETTERBOX (in finish).

Performance budget: <= 2.5 s per 1080p frame on one core. Cache static things in `c.cache`.

## Fusion API (`fusion(self, g, p)`)

- Start with `F.std_controls(g, p)`; add `F.accent_holder(g, p["ACCENT_COLOR"])` if anything uses
  `accent=True` / `F.accent_solid`.
- Expressions only (no keyframes): build them with `prog(start, dur)`, `e_out(u)`, `e_in(u)`,
  `e_inout(u)`, `decay(frame, frames)`, `step(frame)`, `window(a, b, fin, fout)`, `shake(...)`,
  `clamp01(x)`; refer to controls with `ctl("ImpactFrame")` etc. Allowed functions inside expressions:
  min, max, abs, sin, cos, exp, floor, pow, Point, time. **Never use `^`.**
- Components (`cmet/fcomp.py`): `solid`, `accent_solid`, `gradient_bg`, `noise` (FastNoise), `ellipse`,
  `rect`, `bitmap_mask`, `masked`, `merge` (mode: Normal/Screen/Multiply/Overlay/...), `xf` (Transform),
  `blur`, `softglow`, `dirblur`, `cc`, `bc`, `title_text`, `subtitle_text`, `fill_material`, `edge_light`,
  `extrusion_stack`, `impact_flash`, `light_spot`, `shock_ring`, `particles`, `polyline_mask`,
  `closed_poly_mask`, `shard_polys`, `light_sweep`, `camera_rig`, `title_placement`, `finish`,
  `text3d_rig` (genuine 3D), `exit_fade`.
- Only tool IDs present in `cmet/fusion_ref.py` may be used (validator enforces). If you need an input
  name not in the table, it is allowed but is counted as unconfirmed (`?`) evidence - prefer listed ones.
- The title must be a `TextPlus` created with `F.title_text(...)` (publishes text, font, size, spacing,
  alignment, colour) or a `Text3D` via `F.text3d_rig`. The macro output is `g.output = F.finish(...)`.
- Something must reference `ExitStart` (the exit), and several expressions must use `time`.
- Unused controls are pruned automatically, so only functional sliders are published.
- `g.at(col, row)` positions subsequent nodes in the flow view (keep graphs readable: one row per stage).

## Verify while authoring

```
cd 06_AUTOMATION/Scripts
python3 check_design.py t05 12,60,84,87,130,170 /path/to/sheet.jpg
```
This builds the graph, runs the real-Lua parse + structural validator, and renders a 3-column still sheet
(640x360 per frame) plus `_full.jpg` (last frame at 1080p). Look at the sheet; iterate. Check: title
readable in hero hold, not overexposed, effects restrained, distinct from other templates.

## Font keys

anton, bebas, blackops, russo, cinzel, cinzel_bold, cinzel_deco, audiowide, staatliches, marcellus,
orbitron, orbitron_med, teko, teko_light, telugu (Ramabhadra), telugu_sans (Noto Sans Telugu).
Fusion family/style names are in `cmet/typo.py FONTS` (use them in `F.title_text`).
