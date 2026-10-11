# T12 Chrome Dominion - Sound Design Sheet

Timeline: 180 frames @ 24 fps (7.50s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Studio room tone |
| 12 | 0.50s | metal | Strip light 1 clunk |
| 24 | 1.00s | metal | Strip light 2 |
| 36 | 1.50s | metal | Strip light 3 |
| 40 | 1.67s | whoosh | Heavy pivot whoosh |
| 60 | 2.50s | riser | Short riser |
| 74 | 3.08s | impact | Chrome slab lands - hard impact |
| 74 | 3.08s | metal | Metallic ring |
| 78 | 3.25s | shimmer | Reflection sweep shimmer |
| 140 | 5.83s | rwhoosh | Reverse whoosh fall-back |
| 152 | 6.33s | metal | Lights off clunks |
| 160 | 6.67s | tail | Tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
