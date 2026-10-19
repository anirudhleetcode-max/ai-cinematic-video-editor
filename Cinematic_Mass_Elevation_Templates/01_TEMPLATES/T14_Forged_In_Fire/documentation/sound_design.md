# T14 Forged in Fire - Sound Design Sheet

Timeline: 228 frames @ 24 fps (9.50s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Forge roar bed |
| 0 | 0.00s | fire | Coal bed crackle |
| 14 | 0.58s | swell | Heat swell |
| 64 | 2.67s | hammer | Strike 1 |
| 64 | 2.67s | debris | Spark spray |
| 88 | 3.67s | hammer | Strike 2 |
| 88 | 3.67s | debris | Spark spray |
| 106 | 4.42s | rwhoosh | Wind-up |
| 112 | 4.67s | hammer | Final strike |
| 112 | 4.67s | impact | Heavy anvil impact |
| 112 | 4.67s | sub | Sub drop |
| 140 | 5.83s | water | Quench hiss / steam |
| 184 | 7.67s | tail | Cooling metal ticks + tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
