# T02 Thunder God - Sound Design Sheet

Timeline: 192 frames @ 24 fps (8.00s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Storm bed: wind + distant rumble |
| 0 | 0.00s | wind | Wind layer |
| 30 | 1.25s | thunder | Distant thunder roll (cloud flash) |
| 66 | 2.75s | crackle | Electrical crackle behind letters |
| 76 | 3.17s | rwhoosh | Reverse air suck into strike |
| 80 | 3.33s | thunder | Lightning strike crack + boom |
| 80 | 3.33s | sub | Sub-bass accent |
| 120 | 5.00s | crackle | Edge arc crackle |
| 154 | 6.42s | tail | Storm tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
