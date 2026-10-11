# T09 Ashes of Power - Sound Design Sheet

Timeline: 204 frames @ 24 fps (8.50s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Dry hollow wind bed |
| 0 | 0.00s | wind | Ash-laden wind |
| 8 | 0.33s | riser | Granular riser while ash converges (8-96) |
| 40 | 1.67s | debris | Fine sand trickle |
| 90 | 3.75s | rwhoosh | Air drawn in |
| 96 | 4.00s | impact | Compaction thud |
| 96 | 4.00s | sub | Low sub |
| 97 | 4.04s | debris | Dust puff |
| 166 | 6.92s | debris | Crumble / sand pour |
| 186 | 7.75s | tail | Wind tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
