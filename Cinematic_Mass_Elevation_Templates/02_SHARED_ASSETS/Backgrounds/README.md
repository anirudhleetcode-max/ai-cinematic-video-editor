# Backgrounds

There are deliberately **no baked background images** here. Every template's environment is generated
procedurally and animated, so nothing is a static wallpaper and nothing has to be linked as media:

* **In Fusion**: gradient `Background` nodes, animated `FastNoise` layers (drifting `Center`, `SeetheRate`),
  masked light sources (`Background` + `EllipseMask`), particle systems (`pEmitter`/`pRender`). Find them in
  each composition's first node rows (`Env*`, `Fog*`, `Cloud*`, `Haze*`, `Horizon*` tools).
* **In the reference renderer**: `cmet/elements.py` (fog, smoke, clouds, stars, nebula, rain, caustics,
  light cones, HUD) and `cmet/core.py` (gradients, noise fields, god rays).

To use your own plate instead, add a Fusion *Loader* (or MediaIn) and merge it under the title branch in
place of the template's environment branch (see 07_DOCUMENTATION/Template_Editing_Guide.md).
