# T07 Explosive Arrival - Sound Design Sheet

Timeline: 144 frames @ 24 fps (6.00s). Cue frames assume default timing; if you move `ImpactFrame`/`ExitStart`, move the matching cues by the same amount.

| Frame | Time | Cue | Notes |
|---|---|---|---|
| 0 | 0.00s | atmos | Tense low room tone |
| 4 | 0.17s | heartbeat | Single heavy pulse |
| 8 | 0.33s | riser | Short charge riser (8-24) |
| 22 | 0.92s | rwhoosh | Reverse suck into the blast |
| 24 | 1.00s | impact | Detonation boom |
| 24 | 1.00s | sub | Sub-bass drop |
| 25 | 1.04s | debris | Debris + glass scatter |
| 26 | 1.08s | fire | Fireball roar / burning tail |
| 60 | 2.50s | crackle | Embers crackle |
| 110 | 4.58s | whoosh | Fly-through whoosh |
| 120 | 5.00s | tail | Explosion reverb tail |

The preview MP4's audio is a procedural mix of these cues produced by `cmet/sfx.py` (synthesised from oscillators and filtered noise - no samples or third-party recordings). Replace with your own licensed library for final delivery if preferred.
