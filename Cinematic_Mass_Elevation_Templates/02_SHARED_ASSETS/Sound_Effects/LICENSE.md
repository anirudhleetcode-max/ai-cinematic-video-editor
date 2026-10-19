# Sound effects - origin and licence

Every file in this folder, and every audio track in the preview videos, was **synthesised from scratch** by
`06_AUTOMATION/Scripts/cmet/sfx.py` (sine/square oscillators, FFT-filtered random noise, envelopes and a
synthetic noise-burst reverb). No recordings, samples, sound libraries, film audio or dialogue were used.

They are original material created for this project and may be used, modified and redistributed with the
templates without restriction (treat as CC0 / public domain dedication). Regenerate them with:

```
python 06_AUTOMATION/Scripts/make_sfx_library.py
```

| File | Use |
|---|---|
| impact_heavy.wav | Main hit: pitched-down sine boom + transient + saturation |
| sub_drop.wav | Sub-bass accent under impacts |
| metal_hit.wav | Inharmonic metallic strike (steel, forged, titanium titles) |
| whoosh.wav / reverse_whoosh.wav | Transitions; reverse whoosh leads into an impact |
| riser_3s.wav | Tension build (noise band + gliding tone) |
| debris.wav | Granular debris / fragments scatter |
| shimmer.wav | Light-sweep sparkle |
| tail.wav | Low atmospheric decay |
| thunder.wav | Crack + low rolling rumble |
| electric_crackle.wav | Electrical arcs |
| digital_tone.wav / glitch.wav | Hologram / sci-fi accents |
| swell.wav | Warm pad swell for emotional/majestic titles |
| ice_crackle.wav | Frost formation tinkles |
| hammer.wav | Forge hammer strike |
| heartbeat.wav | Double sub thump for tension |

Per-template cue timing (frames and seconds) is in each template's `documentation/sound_design.md`.
These are serviceable temp/placeholder sounds; for a final mix you may substitute your own licensed library.
