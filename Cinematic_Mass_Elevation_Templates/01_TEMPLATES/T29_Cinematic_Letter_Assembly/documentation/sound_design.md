# T29 Cinematic Letter Assembly - Sound Design Sheet

Timeline: 180 frames @ 24 fps (7.50s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Warm room tone |
| 8 | 0.33s | whoosh | First letters fly in |
| 20 | 0.83s | shimmer | Soft ticks per landing |
| 40 | 1.67s | whoosh | Mid letters |
| 76 | 3.17s | rwhoosh | Centre letter approach |
| 82 | 3.42s | impact | Soft lock-in hit |
| 83 | 3.46s | shimmer | Sheen sweep |
| 140 | 5.83s | whoosh | Letters lift away |
| 160 | 6.67s | tail | Airy tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
