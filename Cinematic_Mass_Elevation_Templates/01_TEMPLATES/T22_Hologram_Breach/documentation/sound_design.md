# T22 Hologram Breach - Sound Design Sheet

Timeline: 192 frames @ 24 fps (8.00s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Lab room tone / server hum |
| 4 | 0.17s | digital | Emitter power-on chirp |
| 12 | 0.50s | swell | Beam swell (frames 12-76) |
| 18 | 0.75s | glitch | Segment materialise ticks |
| 44 | 1.83s | glitch | Interference burst |
| 70 | 2.92s | rwhoosh | Reverse air into lock |
| 76 | 3.17s | impact | Soft digital lock hit |
| 77 | 3.21s | shimmer | Lock-in scan shimmer |
| 150 | 6.25s | digital | Projector cut |
| 160 | 6.67s | tail | Hum tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
