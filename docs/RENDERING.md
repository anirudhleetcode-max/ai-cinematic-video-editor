# Rendering

`render/engine.py::render_plan(plan, assets, out, work, progress, preview)`

## Stages

1. **Segments** (`render/segments.py`, thread pool, 2 FFmpeg threads each). Per segment, one FFmpeg graph does:
   trim → stabilise (`deshake`) → speed (`setpts`) or speed ramp (10 piecewise-constant pieces, concatenated) →
   optional `minterpolate` (quality mode slow motion) → `fps` → technical grade (17³ LUT) → cover-scale → crop
   (static) — or hands raw frames to numpy for camera motion (`warpAffine`, sub-pixel) → per-segment effects →
   frame-exact `tpad`/`trim` → split into **head** / **body** / **tail** (head/tail = transition overlap frames,
   lossless FFV1; body = x264). Segment audio is rendered separately at the output speed (`atempo` chain),
   exactly `out_duration` long. Fallback levels on failure: drop effects → drop motion/stabilisation/interpolation
   → plain trim.
2. **Transitions** (`render/transitions.py`): tail(A) + head(B) → xfade (native) or numpy (procedural) → short
   clip; failure → midpoint cut.
3. **Audio mix** (`render/audio_mix.py`, 48 kHz float): dialogue assembled with equal-power crossfades on overlaps
   and 12 ms micro-fades on cuts → dialogue chain → music bed (windows, fades, crossfades between songs) → ducking
   automation from the processed dialogue envelope (−depth dB, 250 ms hold, attack/release one-pole) → SFX and
   voice-over → end fade → soft limiter → **two-pass EBU R128 loudnorm** (measured, linear) → loudness re-measured
   for the report.
4. **Final pass**: concat (body + transition pieces) → creative LUT → finishing (sharpen/vignette/grain) → global
   effects → end card (dark backdrop, logo fade-in) → libass text/captions → exact frame count → encode with the
   best *verified* encoder (NVENC/QSV/AMF/VideoToolbox/VAAPI) and automatic **CPU fallback** → AAC 320 kb/s,
   48 kHz stereo, −1 dBTP limiter → MP4 `+faststart`. Progress comes from FFmpeg’s own `out_time` counter.
5. **QC** (`qc/check.py`).

## Caching & incremental rendering

* Segment pieces are cached under `projects/<id>/work/segment_cache/<hash>` where the hash covers everything that
  affects their pixels (spec minus timing-only fields, source fingerprint, overlap lengths, resolution, fps,
  quality, mode). A colour-only revision therefore re-runs **only** the final pass (verified in tests and in the
  acceptance report: all segments reused).
* Transition clips are cached by a content hash of their inputs and parameters.
* Analysis results are cached by file fingerprint, so re-uploading or re-analysing is instant.

## Modes

| | Fast | Quality | Emergency |
|---|---|---|---|
| Analysis sampling | 4 fps @ 192 px | 8 fps @ 320 px, people detector | 2 fps @ 160 px, no faces |
| Slow motion | frame repetition | `minterpolate` (MCI) | frame repetition |
| Encode | x264 `veryfast` CRF 21 / HW | x264 `medium` CRF 17 / HW | x264 `ultrafast` CRF 28 |
| Transition budget | from bible | from bible | ≤ 10 % |

Preview renders use the same pipeline at 640 px (long side), draft quality and proxies when available.

## Quality control & auto-fix

Checks: file exists, valid MP4, full decode (playable), duration (±0.25 s), resolution, frame rate, codec, audio
present, black frames (`blackdetect`, excluding intended end card/dips/fades), frozen frames (`freezedetect`,
excluding freezes/photos), accidental silence (`silencedetect`), clipping (`astats` peak), text safe area, missing
clips. Auto-fix: clipping → re-limit audio only (video stream copied); other failures → re-render without global
effects; render exceptions → CPU encoder, then no effects/motion. `EDITOR_QC_MAX_RETRIES` bounds the loop. The full
report (timings per stage, encoder, fallbacks, loudness, cache reuse, peak RSS) is stored with the render.

## Export

`ExportSpec`: width/height (even), fps, `h264`/`hevc`, quality ladder, audio bitrate, HW preference. Resolutions per
aspect: 16:9 1920×1080, 9:16 1080×1920, 1:1 1080×1080, 4:5 1080×1350, 21:9 1920×822; `POST /projects/{id}/render`
accepts overrides (e.g. `{"width":3840,"height":2160}` for 4K, `{"vcodec":"hevc"}`).
