# T39 Final Boss - Sound Design Sheet

Timeline: 156 frames @ 24 fps (6.50s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Abyssal drone |
| 0 | 0.00s | heartbeat | Heavy heartbeat (continues through the hold) |
| 4 | 0.17s | riser | Tension riser (frames 4-28) |
| 18 | 0.75s | whoosh | Fast incoming whoosh |
| 28 | 1.17s | impact | Massive impact + distorted sub |
| 28 | 1.17s | metal | Iron slam |
| 29 | 1.21s | debris | Debris / grit |
| 30 | 1.25s | tail | Impact tail |
| 130 | 5.42s | rwhoosh | Snap-back suck |
| 138 | 5.75s | sub | Final sub drop |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
