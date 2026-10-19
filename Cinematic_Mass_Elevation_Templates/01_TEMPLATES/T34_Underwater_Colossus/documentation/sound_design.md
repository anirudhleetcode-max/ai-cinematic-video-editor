# T34 Underwater Colossus - Sound Design Sheet

Timeline: 240 frames @ 24 fps (10.00s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | water | Deep underwater ambience, muffled pressure |
| 0 | 0.00s | atmos | Whale-like low drone |
| 12 | 0.50s | swell | Slow rising swell under the ascent |
| 110 | 4.58s | rwhoosh | Muffled reverse surge |
| 124 | 5.17s | sub | Deep muffled thoom as it settles |
| 126 | 5.25s | debris | Silt plume hiss (soft) |
| 140 | 5.83s | shimmer | Caustic light shimmer |
| 190 | 7.92s | swell | Descending swell |
| 220 | 9.17s | tail | Long underwater tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
