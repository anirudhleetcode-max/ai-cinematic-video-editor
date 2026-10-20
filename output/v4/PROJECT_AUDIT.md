# v4 project audit

Audited on 2026-10-20, before any v4 work began.

## Repository state

| Item | State |
|---|---|
| Branch | `claude/clever-franklin-la041i` (draft PR anirudhleetcode-max/ai-cinematic-video-editor#3) |
| HEAD | `f54147c`, the v3 deliverable. The working tree is clean. |
| Git store | `.git` is about 445 MB. Plain git history holds v1 (74 MB), v2 (100 MB) and v3 (96 MB). |
| Git LFS | git-lfs 3.4.1 is installed. It has not been used by this repository yet. |

## Source media

| Item | Value |
|---|---|
| Original footage | `input/source.mov`. It exists only on branch `claude/friendly-fermi-jn4h4o` (commit `b3437ef`, blob `ef61226b`), not on this branch. It is fetched with `git show b3437ef:input/source.mov`. |
| Format | H.264, 1920×1080, 30 fps (3,435 frames), 114.5 s, AAC stereo at 48 kHz. Not rotated. |
| Soundtrack | Embedded in `source.mov`. It is the only audio source, and every version uses it unaltered except for a short fade-in and fade-out. |
| Unusable footage | 79.8–88.2 s (lens covered) and from 113.2 s (lens covered again). v1–v3 replace the first gap with a motion-interpolated slow-motion version of the hug scene (source 88.3–101.0 s) and end the edit at 113.2 s. |

## Pipelines found

| Version | Entry points | Notes |
|---|---|---|
| shared | `edit/common.py` | The timeline mapping (output frames 0–3,395, the slow-motion window 2,393–3,032), the frame reader and the colour-based `person_mask`. `EDIT_SAT` (v1/v2 = 38, v3 = 58) and `EDIT_DARK_V` are set through environment variables. |
| v1 | `edit/analyze.py` → `edit/render.py` → `edit/finalize.sh` | Pastel sticker doodles. `analyze.analyse_audio()` is the beat tracker reused by every later version (about 80.7 bpm, 153 beats). |
| v2 | `edit/plan_v2.py` → `augment_v2.py` → `render_v2.py` → `finalize_v2.sh` | Dense, bold sticker universe. Writes `plan_v2.json`, which v3 reads for its beat grid. |
| v3 | `edit/v3/analyze_v3.py` → `render_v3.py` → `finalize_v3.sh` | The ink-world story. `world.py` holds the whole illustrated world as a pure function of t. `review_motion.py` builds QC strips. |

## v3 components

**Segmentation:**
- Colour-based: HSV saturation above 58 or value below 58, then morphological open and close, components larger than 2% of the frame kept, and only small holes (under 1.2%) filled.
- The mask is computed at 480×270 per frame and smoothed with a two-frame exponential moving average.
- YuNet face ellipses (OpenCV Zoo, MIT, `edit/v3/assets/face_detection_yunet_2023mar.onnx`) are added to the mask.
- **Assessment:** good against the plain wall, and the v2 under-arm defect is fixed. Too coarse for a crisp outline: at 480×270 one mask pixel covers about 4 output pixels. No ML segmentation model is installed (no MediaPipe, YOLO or torch), and the network blocks most model hosts. A crisper mask is achievable by running the same segmentation at 960×540 with edge-aware smoothing.

**Faces:** YuNet found faces in 3,391 of 3,396 frames (`v3_analysis.npz`: masks, faces, top). The two faces per frame are sorted by confidence, not by person, so identity tracking is still needed for any per-head effect.

**Illustrated world (`world.py`):**
- ink stroke engine (wobble, line boil, draw-on, tapered ends)
- character rig (two characters, walk, crouch, jump, dance, hug, hold, sit)
- cottages, path, hills, clouds, moon, stars, recursive tree with growth and bloom, flowers, lanterns with rise-to-heart constellation, pollen, petals, climax wash
- a close-up framing for the standing scene

All of this is pure functions of t, which makes them parallel-safe and reproducible. **Retain.**

**Compositing (`render_v3.py`):**
- filmic look-up tables, skin-only bilateral smoothing at 30%
- ink composited by multiply, light composited additively with glow, both inside a bounding box
- halation, diffusion, vignette, luma grain, camera breathing
- **Retain**, and extend with new layers.

**Timing:** story times are hard-coded in `world.K`, snapped to the beat grid. Not separated from code.

**Configuration:** constants are scattered through the code. There is no configuration file and no command-line overrides.

**Performance:**
- about 0.33–0.94 s per frame on one core
- full render about 17 minutes with 4 workers in 8 chunks, after the bounding-box optimisation
- chunks are not resumable

## Can v3 be reproduced?
Yes, with the steps documented in `output/v3/README.md`. It needs three intermediates that are not committed:
1. `slowmo.mp4`, made with ffmpeg `minterpolate`. It ends 3 frames short (636 of 639 frames); `read_frames` holds the last frame.
2. `plan_v2.json` for the beat grid. v3 only needs its `audio` key.
3. `v3_analysis.npz`, from `analyze_v3.py`.

v4 regenerates any missing intermediate automatically (`edit/v4/pipeline.py`).

## v3 weaknesses relative to the v4 brief
1. There is no persistent white silhouette outline, only a short cream trace at 7.4–10.8 s.
2. There is no blue paint system. The palette is navy ink with coral, teal and gold washes.
3. There are no golden head auras, no hand-drawn star shapes (only cross sparkles), no shooting stars, and no white scribble effects or "Hi" lettering.
4. The world is small: characters are about 2–7% of frame height. The climax is gentle rather than a culmination.
5. Timing lives in code. There is no configuration file and no rendering manifest.
6. Chunk renders are not resumable. The QC steps were run by hand.
7. Delivery was squeezed to 6.5 Mbps to fit GitHub's 100 MB limit. LFS is available but was not used.

## Third-party characters
The brief mentions SpongeBob, Patrick, Deadpool, Naruto and a unicorn. No licensed or user-supplied assets for these exist in the repository or anywhere in the workspace. Copyrighted character artwork will not be fetched from the web. v4 stays fully original. The rendering pipeline does not include a sticker system; if licensed assets are supplied later, they could be added as another layer.

## v4 plan
- **Directories:** `edit/v4/` for code, `config.json` and `timeline.json`; `output/v4/` for the deliverables and documents.
- **Reuse:** `world.py` (story, rig and environments), the masks and faces from `analyze_v3.py`, and the grade and bounding-box compositor.
- **New:**
  - a temporally stable white silhouette outline from 960×540 masks, with position-keyed noise rather than arc-length noise so it doesn't swim
  - a textured blue paint-streak engine: bristle ribbons, a pigment body, a white highlight edge, splatter and dissolve into flecks
  - golden head auras anchored to tracked, smoothed and confidence-gated faces
  - gold particles, hand-drawn stars and shooting stars
  - white scribble effects, including "Hi" at the meeting
  - a timeline file and a configuration file with command-line overrides
  - resumable chunks
  - a rendering manifest
  - automated QC (`qc.py`)
- **Stages:**
  1. validate the source
  2. audio and beats
  3. analysis cache
  4. prototype stills and motion tests at full resolution
  5. revise
  6. full render
  7. audio mux
  8. delivery encode (high quality, via LFS if pushing works, otherwise under 100 MB)
  9. QC on the delivery file
