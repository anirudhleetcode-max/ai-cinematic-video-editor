# T25 Future Warlord - Sound Design Sheet

Timeline: 228 frames @ 24 fps (9.50s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Hangar room tone |
| 6 | 0.25s | digital | HUD boot blips |
| 34 | 1.42s | digital | Target lock beeps |
| 60 | 2.50s | metal | Clamp release clunk (unlock jolt) |
| 64 | 2.67s | riser | Hydraulic riser (64-96) |
| 96 | 4.00s | metal | Shutter slam open |
| 96 | 4.00s | impact | Heavy impact |
| 97 | 4.04s | debris | Dust/grit falling |
| 186 | 7.75s | hammer | Shutters slam closed |
| 190 | 7.92s | digital | HUD power-down |
| 200 | 8.33s | tail | Hangar tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
