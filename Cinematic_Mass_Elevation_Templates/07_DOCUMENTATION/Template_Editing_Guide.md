# Template Editing Guide

## How every template is built (Fusion)

Every composition follows the same layout, top to bottom in the Node Editor:

1. **CONTROLS** (top left) is an identity Transform that carries the user controls. Its *Controls* tab
   holds the timing sliders (Animation Start, Reveal Duration, Impact Frame, Exit Start, Exit Duration) and
   the look sliders (intensities, text position/scale/rotation, extrusion, letterbox). These are the same
   controls the macro publishes to the Edit-page Inspector.
2. **ACCENT** is a small solid colour. Every accent-coloured light, rim, ring and particle reads its colour
   from here through expressions, so you only change the accent in one place.
3. **Environment rows** (`Env*`, `Fog*`, `Cloud*`, `Haze*`, `Horizon*`, `*Glow`, particles) build the
   background. These are procedural nodes; there is no media.
4. **Title rows**: `MainTitle` (Text+, or `*Text3D` in 3D templates) feeds the material passes
   (`*Reflect`, rims, sweeps, extrusion). `TitlePlacement`/`Title*` transforms apply TEXT_POSITION /
   SCALE / ROTATION and the entrance motion.
5. **Impact rows** hold the flash, rings, bursts, flares and shake. All of them key off `CONTROLS.ImpactFrame`.
6. **Subtitle / Tagline** are separate Text+ nodes with their own placement.
7. **Camera + finish**: `Camera` (push + shake), then `Vignette`, `Grain`, `Letterbox`. The last node is the output.

## Animation is expression-driven

Motion is written as Simple Expressions that read the CONTROLS sliders, not as fixed keyframes. For example,
the title scale in T01 is:

```
CONTROLS.TextScale * (0.62 + 0.38*(1 - pow(1 - min(max((time - (CONTROLS.AnimStart)) / max(CONTROLS.AnimDuration, 1), 0), 1), 4)))
```

As a result:
- Moving **Impact Frame** re-times every effect tied to it at once: the flash, rim ignition, burst, ring and shake.
- Moving **Exit Start / Exit Duration** re-times the exit.
- To hand-animate a parameter instead, right-click it and choose *Remove Expression*, then keyframe as usual.
  That parameter stops following CONTROLS; everything else keeps working.

Any control that no expression uses is removed automatically when the file is built. So every slider you see
does drive something. Each template's `documentation/parameters.md` lists what each control drives.

## Common edits

| Goal | Where |
|---|---|
| Change title / subtitle text | Inspector *Title* tab, or the `MainTitle` / `Subtitle` / `Tagline` Text+ nodes |
| Change font | Inspector *Main Title Font/Style*. Install the bundled fonts first (see Fonts README). |
| Text colour | *Main Title Color* (feeds the material base; the material passes tint on top of it) |
| Accent colour (lights, rims, particles) | *Accent Color* (the `ACCENT` node) |
| Make the impact earlier/later | *Impact Frame* |
| Longer hero hold | Increase *Exit Start*, then lengthen the clip |
| Quieter / louder effects | *Background / Particle / Glow / Impact Intensity*, *Camera Shake* (0 turns it off) |
| Remove letterbox | *Letterbox* = 0 |
| Flatter title | *Extrusion Depth* = 0 (2.5D stack, or Text3D extrusion in 3D templates) |
| Different background | Replace the environment branch: merge your MediaIn/Loader under `TitleOver*` |
| Disable debris/particles | *Particle Intensity* = 0 |

## 3D templates (T11, T12, T13, T15, T28)

These use genuine 3D geometry: `Text3D` (extruded and bevelled) → `MtlBlinn` material → `Merge3D` with a
`Camera3D`, lights and `Renderer3D` (OpenGL). Edit the text on the `*Text3D` node, or use *Main Title (3D)*
in the Inspector. Extrusion and bevel follow *Extrusion Depth* and *Bevel Amount*. Material colour is
published as *Material Color*. If rendering is slow, lower `RendererOpenGL.Supersampling` on the renderer node.

## Reference renderer equivalents

The previews come from `06_AUTOMATION/Scripts/cmet/designs/tNN.py`. That module renders the same design and
timing with Python. Its parameters (see `configuration/default_params.json`) mirror the Fusion controls:
MAIN_TITLE ↔ Main Title, IMPACT_FRAME ↔ Impact Frame, ACCENT_COLOR ↔ Accent Color, and so on.
