# T30 Speed Ramp Dominance - Sound Design Sheet

Timeline: 144 frames @ 24 fps (6.00s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | riser | Short aggressive riser (0-22) |
| 4 | 0.17s | whoosh | Hyper-fast pass-by whoosh |
| 22 | 0.92s | impact | Hard impact / brake slam |
| 22 | 0.92s | sub | Sub drop into slow motion |
| 23 | 0.96s | swell | Slow-motion tonal swell (hold) |
| 40 | 1.67s | heartbeat | Slowed heartbeat pulse |
| 106 | 4.42s | rwhoosh | Reverse suck before exit |
| 110 | 4.58s | whoosh | Exit rush |
| 126 | 5.25s | tail | Tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
