# Particles

Particles are generated, not stored as media:

* **Fusion**: `pEmitter -> pTurbulence -> pRender -> SoftGlow` chains created by `fcomp.particles()`.
  Emission rate is tied to the macro's **Particle Intensity** control (`CONTROLS.ParticleIntensity`; 0 turns
  particles off). Impact bursts emit only for a few frames around **Impact Frame**.
* **Reference renderer**: `elements.Particles` + `particle_layer()` (3D positions, depth-scaled size,
  depth-of-field blur for out-of-focus particles, flicker, motion streaks).
