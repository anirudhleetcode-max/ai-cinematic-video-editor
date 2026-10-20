# Cinematic doodle music edit: v3, "The Seed of Light"

The final file is `output/cinematic_doodle_music_edit_v3.mp4` (1920×1080, 30 fps, H.264 + AAC, 113.2 s, 95.7 MB).

v1 (`cute_doodle_music_edit.mp4`) and v2 (`cute_doodle_music_edit_v2.mp4`) are unchanged.

| Document | Contents |
|---|---|
| `TREATMENT.md` | Audit, concept, palette, geography and the full scene-by-scene storyboard |
| `QC_REPORT.md` | Process, validation results and known limitations |
| `ASSET_CREDITS.md` | Credits and licences |
| `review_frames_v3.jpg` | 18 frames across the timeline |
| `qc_climax_motion_strip.jpg` | The climax as a moving sequence |
| `qc_difficult_masks.jpg` | The hardest mask frames |
| `qc_face_fidelity.jpg` | Source vs v3 face comparison |

## Pipeline (`edit/v3/`)

| File | Role |
|---|---|
| `analyze_v3.py` | Refined person masks (saturation > 58 or dark, small-hole fill only), unioned with YuNet face ellipses. Also tracks hand raises. Cached to `v3_analysis.npz`. |
| `world.py` | The illustrated world, as a pure function of time: ink stroke engine (hand-drawn wobble, gentle line boil, draw-on progress, tapered ends), the character rig (walk cycle, anticipation and follow-through, scarf secondary motion), the environments, and the story timeline snapped to the measured beat grid. |
| `render_v3.py` | Filmic grade, then MULTIPLY-composited ink and washes, then ADDITIVE light, all masked behind the performers, then gesture particle streams, halation and diffusion, transitions, slow camera breathing and grain. Renders in parallel chunks. |
| `finalize_v3.sh` | Adds the original soundtrack, writing to a temp file and renaming only on success. |
| `review_motion.py` | QC: motion strips and frame-to-frame change statistics. |

## Reproduce
```
export EDIT_WORK=/scratch EDIT_SOURCE=/path/to/input/source.mov
# slowmo.mp4 must be in $EDIT_WORK (see output/README.md); plan_v2.json provides the beat grid
cd edit && python3 plan_v2.py                 # beat grid (shared with v2)
cd v3 && python3 analyze_v3.py && python3 render_v3.py && ./finalize_v3.sh
# delivery encode (under 100 MB):
ffmpeg -i master.mp4 -c:v libx264 -preset slow -b:v 6500k -pass 1 -an -f null /dev/null
ffmpeg -i master.mp4 -c:v libx264 -preset slow -b:v 6500k -maxrate 9M -bufsize 13M -pass 2 -c:a copy -movflags +faststart cinematic_doodle_music_edit_v3.mp4
```
