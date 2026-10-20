# Cinematic doodle music edit: v4, "The Seed of Light", the world awakens

| | |
|---|---|
| **Video** | `output/v4/cinematic_doodle_music_edit_v4.mp4`: 1920×1080, 30 fps, H.264 High, 11.25 Mbps, with the original AAC stereo soundtrack. 113.2 s, 159.2 MB, stored with Git LFS. |
| **Earlier versions** | v1, v2 and v3 (`output/*.mp4`, `output/cinematic_doodle_music_edit_v3.mp4`) and the source are unchanged. |

## Documents

| File | Contents |
|---|---|
| `PROJECT_AUDIT.md` | What existed, what was reused, and the weaknesses addressed |
| `TREATMENT.md` | Concept, hierarchy, palette, music structure, the climax as staged sequences, and the differences from v3 |
| `SHOT_BREAKDOWN.md` | Section-by-section breakdown of live action, world, paint, gold, scribbles and outline |
| `QC_REPORT.md` | Measured results, prototype findings and fixes, and known limitations |
| `qc_results.json` | Raw output of `edit/v4/qc.py` on the delivery file |
| `render_manifest.json` | Source hash, full configuration, timeline hash, model hash, library versions and the code commit |
| `ASSET_CREDITS.md` | Credits and licences |
| `review/` | 18-frame sheet, opening, climax and ending motion strips, face fidelity and difficult masks, all taken from the delivery file |

## Pipeline (`edit/v4/`), reusing `edit/v3/world.py` and `render_v3.py`

| File | Role |
|---|---|
| `config.json` | Every tunable value: outline, paint, aura, particles, stars, scribbles, segmentation, grade and render. Override any value with `EDIT_V4_SET="outline.width_px=4;paint.intensity=0.8"`. |
| `timeline.json` | All authored events, kept separate from the code: song sections, outline alpha and redraw keys, 17 paint strokes, aura windows, shooting stars and scribbles |
| `engine.py` | Config loading, `MusicTimeline`, face tracking (`track_faces`), `ContourEngine`, `PaintStrokeEngine`/`PaintStroke`, and `FX` (auras, particles, stars, shooting stars, scribbles) |
| `render_v4.py` | The compositor, with an explicit depth order and blend mode per layer (see its docstring), bounding-box compositing, resumable chunk rendering and the render manifest |
| `pipeline.py` | The stage driver: `prep`, `stills`, `proto`, `render`, `master`, `deliver`, `qc`, `all` |
| `qc.py` | Automated QC, with measured values only |

## Reproduce
```
export EDIT_WORK=/scratch          # intermediates; source fetched from commit b3437ef if missing
cd edit/v4
python3 pipeline.py prep           # source, slow-motion plate, beat grid, analysis cache
python3 pipeline.py render         # ~33 min on 4 cores; chunks are resumable
python3 pipeline.py master         # + original soundtrack
python3 pipeline.py deliver        # two-pass 11 Mbps
python3 pipeline.py qc
```

## Changes from v3
**Added:**
- the white pen outline (edge-aware, outer envelope only, temporally stable)
- textured blue paint strokes (17, choreographed to the song)
- golden auras on tracked heads
- gold particles
- hand-drawn stars and shooting stars
- white scribbles, including "Hi"
- characters 1.36× larger
- timeline and configuration files
- resumable rendering, a render manifest and automated QC

**Removed:** the constant camera breathing zoom.

**Kept from v3:** the story, world, grade, masks (now at 960×540 with tighter face fill) and the climax close-up framing.
