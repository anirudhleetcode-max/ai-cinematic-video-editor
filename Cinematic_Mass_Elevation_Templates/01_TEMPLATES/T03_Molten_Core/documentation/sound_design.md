# T03 Molten Core - Sound Design Sheet

Timeline: 216 frames @ 24 fps (9.00s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Deep volcanic rumble bed |
| 0 | 0.00s | fire | Low lava crackle / hiss |
| 14 | 0.58s | riser | Grinding sub riser while the title rises (14-76) |
| 70 | 2.92s | rwhoosh | Reverse heat suck into the seat |
| 76 | 3.17s | impact | Heavy iron seat impact |
| 76 | 3.17s | sub | Sub-bass drop |
| 77 | 3.21s | debris | Ember / grit scatter |
| 98 | 4.08s | shimmer | Heat shimmer as the glow crawls the edges |
| 150 | 6.25s | swell | Cooling hiss swell |
| 186 | 7.75s | tail | Rumble tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
