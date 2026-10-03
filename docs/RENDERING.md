# Rendering

`render/engine.py::render_plan(plan, assets, out, work, progress, preview)`

## Stages

1. **Segments** (`render/segments.py`, thread pool, 2 FFmpeg threads each). Per segment, one FFmpeg graph does:
   trim → deinterlace if needed → stabilise (off / light `deshake` / standard and strong: two-pass **vid.stab**,
   motion file cached with the segment) → speed (`setpts`), or a **continuous speed ramp** (the source is decoded at
   a constant rate high enough for the fastest part, then each output frame maps to its exact source time from
   the integrated speed curve; slow parts use frame blending in Fast mode and DIS optical-flow interpolation in
   Quality mode, with no duplicated frames) → optional `minterpolate` (Quality-mode slow motion) → `fps` →
   **source normalisation** into RGB (own matrix / range, HDR tone-map, square pixels; docs/COLOR.md) and
   cover-scale → technical grade (17³ LUT) → crop (static), or raw frames to numpy for camera motion
   (`warpAffine`, sub-pixel) → per-segment effects →
   frame-exact `tpad`/`trim` → split into **head** / **body** / **tail** (head/tail = transition overlap frames,
   lossless FFV1; body = x264). Segment audio is rendered separately at the output speed (`atempo` chain),
   exactly `out_duration` long, **always read from the original file** (preview proxies are video-only); dialogue
   clips flagged as clipped get `adeclip`. Fallback levels on failure: drop effects → drop motion / stabilisation /
   interpolation → plain trim; unreadable audio → silence (reported).
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
6. **Measured reviews** (final renders, `qc/review.py`): colour continuity measured on the output, the Reference
   Match Report and the review checklist (story, pacing, shot selection, variety, transitions, colour, audio, text,
   motion, ending, technical), each with the values that decided it.

## Caching & incremental rendering

* Segment pieces are cached under `projects/<id>/work/segment_cache/<hash>` where the hash covers everything that
  affects their pixels (spec minus timing-only fields, source fingerprint, overlap lengths, resolution, fps,
  quality, mode). A colour-only revision therefore re-runs **only** the final pass (verified in tests and in the
  acceptance report: all segments reused).
* Transition clips are cached by a content hash of their inputs and parameters.
* The **audio mix** is cached by a hash of the audio plan, music, SFX, voice-over, segment audio content and timing,
  and source fingerprints. A colour, text or ending revision reuses the mix as well as every segment.
* Every FFmpeg run has a timeout (`EDITOR_PROCESS_TIMEOUT`); filter paths are escaped for Windows drive letters.
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
