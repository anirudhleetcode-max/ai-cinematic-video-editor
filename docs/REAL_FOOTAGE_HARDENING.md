# Real-footage hardening

This pass moved Cutroom from synthetic test media to real camera footage. Everything below is either measured
in this repository's harness or explicitly marked as a limitation.

## CURRENT STATE (before this pass)

Inspected: repository, engine (`services/engine/editor`), tests (27 engine, 12 web, browser e2e), synthetic
acceptance test (14/14), benchmark suite (11–201 synthetic clips), render pipeline, registries, colour, audio,
reference analyser, AI director, revision engine, caching, frontend and job queue.

All tests ran on **synthetic** media (`editor/testmedia.py`): lavfi patterns, synthetic tones and synthetic “speech”.
Nothing had been measured against camera footage, real music or real speech.

## WEAK POINTS (found by running real media)

| # | Finding on real media | Severity | Status |
|---|---|---|---|
| 1 | Every render shifted saturated colours by up to **25/255**. Conversions used BT.601 for RGB↔YUV while the untagged output is decoded as BT.709 by players (measured with colour patches) | high | fixed — `render/colorspace.py`, `tests/test_colorspace.py` |
| 2 | Speech detection found **0 %** speech in real speech (LibriSpeech, the user's own presenter clips); it was tuned on synthetic speech | high | fixed — optional Silero VAD (86–97 % on real speech, 0–2 % on music); DSP fallback kept and reported |
| 3 | Planning ran out of memory (**14 GB, OOM-killed**) on a real project: the music-extension loop never terminated when a song's high-energy re-entry point was near its end | critical | fixed — bounded loop + progress guarantee |
| 4 | Auto song choice could pick a song **shorter than the edit** although a long-enough song existed | medium | fixed |
| 5 | Preview renders crashed for real 1080p sources: preview proxies are video-only and the segment audio was read from the proxy | critical | fixed — audio always from the original; audio failures fall back to silence and are reported |
| 6 | Anamorphic (non-square pixel) sources were squashed during analysis; `setsar=1` relabelled pixels without rescaling | medium | fixed — SAR-aware display size everywhere |
| 7 | Full-range (`yuvj420p`, phones/webcams) and BT.601 (SD) sources were not converted | medium | fixed — per-source matrix and range |
| 8 | HDR (HLG/PQ) sources were not tone-mapped | medium | fixed — zscale + Hable tone-map when available; inspection warns otherwise |
| 9 | Cut detection missed **16 of 29** known cuts in a real montage (global threshold 0.28 vs real cuts ≈ 0.1) | high | fixed — locally adaptive two-signal detector (23/29; the 6 misses are same-camera cuts with almost identical frames) |
| 10 | 30 of 88 real shots were flagged “duplicate”: same fixed camera at a different moment was treated as duplicate footage | high | fixed — 3-position structure thumbnails: duplicates ≤ 0.10, same-angle groups for variety only |
| 11 | Blur detection was resolution-blind: a defocused 1080p clip measured sharp on 192 px analysis frames | high | fixed — content-normalised edge sharpness on 640 px frames (defocused 0.21 vs sharp real footage ≥ 0.39) |
| 12 | A white app screen recording was flagged “overexposed” (mean luma 0.89, almost no clipped pixels) | medium | fixed — overexposure = clipped or washed-out highlights; `screen_recording` tag |
| 13 | Faces were detected on 192 px frames (Haar) — effectively invisible; no object semantics | high | improved — 640 px detection; optional local ONNX provider (YuNet faces + NanoDet COCO-80) |
| 14 | Corrupt files: a truncated MP4 with an intact index was accepted | medium | fixed — sampled decode windows must yield frames |
| 15 | Music “chorus/verse” labels were guesses from energy only | medium | fixed — labels need evidence (phrase recurrence ≥ 50 % at cosine ≥ 0.7), otherwise “high/mid energy” |
| 16 | Effect budget existed but no effect was ever placed; transitions ignored energy/movement | medium | fixed — effects designer + metadata-aware transition director, cut-first |
| 17 | Speed ramps were stepped (10 constant pieces) | medium | fixed — continuous time-remap with frame blending (Fast) / DIS optical flow (Quality) |
| 18 | No authentication, ownership, quotas or timeouts | critical for deployment | fixed — see docs/DEPLOYMENT.md |

## CHANGES MADE

* **Real-media harness:** `scripts/fetch_real_media.py` downloads real, licensed footage, music and speech.
  `scripts/make_real_variants.py` derives the formats the library lacks (4K, HLG HEVC 10-bit, rotated phone MOV,
  native vertical, 24/25/50/120 fps, VFR, anamorphic, WebM/M4V/AVI/ProRes, multi-audio, degradations, corrupt files,
  MP3/WAV/AAC/M4A/FLAC). `scripts/real_media_report.py` inspects every file found under `tests/real_media/`.
  `scripts/real_acceptance.py` and `scripts/real_benchmark.py` run the full pipeline.
* **Ingest:** `editor/media/inspect.py` measures frame-rate variability from packet timestamps, rotation, pixel aspect,
  pixel format and bit depth, range, matrix, HDR transfer, legacy codecs, missing or multiple audio streams, and
  decode health. Corrupt uploads are rejected with the reason.
* **Normalisation:** each source is converted once, with its own matrix and range (HDR tone-mapped), into an RGB
  working space. Each output is converted once to tagged BT.709. Proxies and analysis frames use the same path.
* **Understanding:** `VisionProvider` (`editor/vision.py`), `ShotSemanticProfile` with per-field provenance
  (`editor/media/semantics.py`), quality / usability / creative scores, soft vs hard issues, and new issue types:
  near-black, focus hunting, exposure jumps, obstruction, clipped audio, noisy audio.
* **Editing:**
  * pacing engine (`director/pacing.py`)
  * beat relations: downbeat / on-beat / before / after
  * sequence-level clip selection with two-sided variety constraints
  * evidence-based music structure, impacts and silences
  * effect and transition metadata with EffectDensity
  * continuous speed ramps; stabilisation modes off / light / standard / strong, with two-pass vid.stab
* **Colour:**
  * closed-loop technical shot matching on per-shot colour thumbnails, plus neighbour smoothing
  * a ReferenceGradeProfile (luma and saturation distributions, shadow and highlight casts, hue) mapped to split
    toning and fade on a neutral base
  * colour continuity measured on every render
* **Audio:**
  * Silero VAD
  * dialogue and ambience roles
  * speech-region automation that ducks music, ambience and SFX
  * per-clip dialogue level matching
  * `adeclip` on clipped sources
  * a cached mix
* **Reference:** grade profile, text timeline, fades, audio dynamics, and measured / inferred / unavailable
  provenance. A **Reference Match Report** on every final render compares output and reference metric by metric.
* **Reliability:** plan repair and stricter validation, a review checklist on every final render, dependency-aware
  caches (segments, transitions, mix), vendor GPU detection separate from verified encoders, Windows-safe filter
  paths, process timeouts, retention cleanup, and authentication with ownership and limits.

## TEST STRATEGY

1. **Unit / integration (always):** `npm run test:engine` — synthetic media plus colour-accuracy tests, plan
   repair, revisions, security.
2. **Real media (when present):** `services/engine/tests/test_real_media.py` checks each derived variant against
   its MANIFEST expectations (rotation, SAR, HDR, VFR, multi-audio, codecs, corruption) and that every library
   file decodes. Skipped, never faked, when the media is absent.
3. **Real-footage acceptance:** `python scripts/real_acceptance.py [--assemble]` uses ~50–80 real clips, 3 real
   songs, a style-known reference made from real footage, and a logo. It measures inputs, usable and rejected
   clips, analysis / planning / preview / render time, output properties, loudness, QC, memory, CPU, GPU and cache
   use, the three spec revisions, the Reference Match Report and the review checklist.
4. **Real benchmark:** `python scripts/real_benchmark.py --durations 60 300 600` — see docs/BENCHMARKS.md.
5. **Your own project:** put media in `tests/real_media/event01/` (sub-folders `clips/ music/ reference/ logo/`,
   or one flat folder) and run step 3. Source media is never modified.

## KNOWN LIMITATIONS

* Object detection covers the 80 COCO categories only (no microphones, stages, buildings, nature, signage).
  Scene setting and time of day are explicit heuristics. Without the optional models, only faces and upright
  people (classic OpenCV) are detected.
* Emotional score is a proxy (face size and stillness), not emotion recognition.
* The reference text detector is a stroke-density heuristic (no OCR): it finds bands, not words. On the test
  montage it found the real title and one false event.
* Transition types in a reference are classified from frame statistics (cut / fade / dissolve), not read from
  edit metadata.
* HDR tone-mapping needs FFmpeg with zimg (`zscale`). The HLG test file is HDR-tagged SDR footage, so true
  HDR mastering was not evaluated.
* Windows support is implemented (path escaping, file replace retries, PowerShell GPU query, setup.ps1) but was
  **not run on Windows** in this environment.
* Hardware encoding is implemented and gated by test encodes, but no GPU was available here, so it is **not
  verified**.
* The real footage available here is surveillance-, demo- and phone-style material, not a professionally shot
  event. Results on DSLR, mirrorless or action-camera footage were not measured.
