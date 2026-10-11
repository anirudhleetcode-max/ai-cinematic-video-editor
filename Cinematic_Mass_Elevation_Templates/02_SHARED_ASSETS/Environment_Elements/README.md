# Environment elements

Procedural building blocks shared by the templates (implemented once, reused everywhere):

| Element | Fusion component (`cmet/fcomp.py`) | Preview component (`cmet/elements.py` / `core.py`) |
|---|---|---|
| Atmosphere / fog / haze | `noise()` + `ellipse()` band, `merge(..., "Screen")` | `fog()`, `smoke()`, `fbm_field()` |
| Light sources | `light_spot()` | `soft_spot()`, `light_cone()`, `god_rays()` |
| Lightning | `polyline_mask()` stroke + `softglow()` | `bolt_points()` + `draw_lines()` |
| Shockwave | `shock_ring()` (animated EllipseMask BorderWidth) | `ring()` + `shockwave_displace()` |
| Light sweep | `light_sweep()` (rotated RectangleMask x title matte) | `ShadedText.shade(sweep=...)` |
| Rim / bevel light | `edge_light()` | `ShadedText.shade(rim_gain=...)` |
| 2.5D extrusion | `extrusion_stack()` | `place_extruded()` |
| Genuine 3D text | `text3d_rig()` (Text3D, MtlBlinn, lights, Camera3D, Renderer3D) | `place_extruded()` slice projection |
| Camera push / shake | `camera_rig()` | `Cam`, `apply_shake()` |
| Letterbox / vignette / grain | `finish()` | `Ctx.finish()` |
| Cracks / frost | `polyline_mask()` | `crack_lines()` + `draw_partial()` |
