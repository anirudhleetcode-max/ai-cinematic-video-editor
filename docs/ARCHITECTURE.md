# Architecture

```
 Browser (Next.js)  ──HTTP/SSE──▶  FastAPI (editor.api)  ──▶  Service layer (editor.service)
                                          │                         │
                                          ▼                         ▼
                                  Job queue (editor.jobs)     SQLite (editor.db)  +  Storage (editor.storage)
                                          │
              ┌───────────────────────────┼──────────────────────────────────────────┐
              ▼                           ▼                                          ▼
   Media intelligence           AI Editing Director                           Render engine
   media/ music/ reference/     director/ (parser, providers, agents,        render/ (segments, transitions,
   (cached by fingerprint)      planner, revise) → EditPlan (schemas.py)      audio_mix, text_ass, engine) → qc/
```

**Separation of concerns.** The web app is a thin client. The API never blocks on media work: analysis, planning
and rendering are jobs. Jobs run on in-process worker threads (`LocalJobQueue`), persisted in SQLite so a restart
re-queues interrupted work. The `JobQueue` interface is what a Redis/RQ/Celery backend would implement; the
`Storage` interface is what an S3-compatible backend would implement; SQL is plain and JSON-columned so
PostgreSQL (JSONB) is a dialect change.

## Data flow

1. **Upload** → `storage.save_upload` (sanitised filename, size cap, path confinement) → `media.probe` (FFprobe:
   duration, resolution, display size after rotation, fps, codecs, bitrate, channels, sample rate, orientation) →
   thumbnail → content fingerprint (size + first/last 4 MB SHA-256).
2. **Analyse** (parallel thread pool) → per-asset analysers, each cached in `analysis_cache` by
   `(fingerprint, analyzer, version)`: video → shots + scores; music → beats/sections/energy; reference →
   `ReferenceStyleProfile`. Then project-level duplicate detection and uniqueness scoring. Sources taller than
   720p get a 360p proxy for previews.
3. **Plan** → `director.planner.build_plan`: prompt → `StyleIntent` (deterministic parser, optionally refined by
   an LLM) → template → `CreativeBible` → agents → `EditPlan` → pre-render validation. Saved as a version.
4. **Render** → `render.engine.render_plan`: segments (parallel, cached) → transitions → audio mix → final pass →
   QC → auto-fix/retry (configurable). Saved as a render with a full report.
5. **Revise** → `director.revise.apply_revision` patches the stored plan (new version with parent + change domains).

## Media intelligence (what is measured, and how)

| Signal | Method |
|---|---|
| Shot boundaries | HSV-histogram total-variation distance with adaptive (median + 8·MAD) threshold; fades via luma dips; dissolves via sustained moderate distance |
| Sharpness / blur | Laplacian variance (log-normalised) |
| Exposure / contrast | mean luma, luma σ, % crushed (<10) and clipped (>245) pixels |
| Camera shake / pan | dense Farneback optical flow → median (global) motion; jitter = 2nd difference, normalised to 192 px / 4 fps |
| Motion / energy | mean absolute frame difference; combined with audio energy and colourfulness |
| Faces / people | OpenCV Haar frontal-face cascade (all modes); HOG pedestrian detector (quality mode) |
| Composition | gradient-energy centroid distance to rule-of-thirds points |
| Duplicates | 64-bit dHash Hamming distance + colour-histogram similarity across all shots of all clips |
| Speech / silence | voice-band (300–3400 Hz) energy ratio, spectral flatness, 3–9 Hz syllabic modulation; silence from noise floor |
| Black / frozen | luma < 0.03; inter-frame difference < 0.0005 |
| Text overlays (reference) | morphological-gradient stroke detection per vertical band (heuristic) |
| Music | librosa beat tracker (no trimming), downbeat phase from onset + low-frequency energy, energy-change-point + chroma/MFCC structural segmentation, drops/build-ups |

Each shot gets `quality, sharpness, composition, motion, exposure, face_visibility, audio, emotional, energy,
uniqueness, cinematic, stability` scores and an `overall_edit_score` with penalties for detected issues.
Heuristic tags (`wide/medium/closeup`, `faces`, `crowd`, `people`, `static/moving/high_motion`, `pan_left/right`,
`speech`, `bright/dark`, `colorful`) feed clip selection.

## Limitations

These are deliberate, documented boundaries — not hidden failures:

* **No deep-learning vision models.** Faces/people use classical OpenCV detectors; “semantic tags” are heuristic
  (shot scale, motion, faces, speech), not object recognition. A model provider can be added behind the same tags.
* **Speech-to-text is optional.** Captions require the free offline model (`scripts/download_stt_model.py`). Without
  it, caption requests are skipped and the plan says so.
* **Reference analysis** measures pacing, colour, motion, transition frequency and music precisely; text placement,
  intro/outro style and slow-motion frequency are heuristic estimates (listed in `heuristic_fields`).
* **Stabilisation** uses FFmpeg `deshake` (single pass). `vidstab` is available in many builds but not yet wired in.
* **Speed ramps** are piecewise-constant (10 pieces) with frame duplication/dropping; `minterpolate` optical-flow
  interpolation is used for constant slow motion in quality mode only (it is slow on CPU).
* **Camera motion** is 2-D (scale/translate/rotate); “orbit” and “parallax” are 2-D approximations.
* **Hardware encoding** is used when a test encode succeeds (NVENC/QSV/AMF/VideoToolbox/VAAPI); on CPU-only machines
  libx264 is used. Decoding and filtering run on the CPU.
* **Performance target.** The 25-minute target for a 5–10 minute edit from 50–200 clips depends on hardware.
  See [BENCHMARKS.md](BENCHMARKS.md) for what this machine actually measured.
* **Browser playback**: the H.264/AAC MP4 plays in Chrome, Edge, Safari and Firefox (with OS codecs). Open-source
  Chromium builds without proprietary codecs cannot play it in the page; the download is unaffected.
