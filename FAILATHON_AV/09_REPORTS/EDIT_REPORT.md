# FAILATHON AV — Edit Report

Generated 2026-10-06 20:55 by `08_SCRIPTS/failathon_autoedit.py`.

| Item | Value |
|---|---|
| Project | FAILATHON_AV |
| DaVinci Resolve | not used for the render. Build the project with `08_SCRIPTS/FAILATHON_AV_RESOLVE_SCRIPT.py` on a machine that has Resolve |
| Timeline | 1920x1080, 30 fps |
| BGM | `BGM_FAILATHON.mp3`, 73.316 s, 129.2 BPM, peak 0.0 dBFS, gain applied -1.0 dB |
| Source files | 17 (17 video, 0 photo), total 1.6 min of video |
| Grades | A=5 B=5 C=5 D=2; duplicates 0; rejected/broken 0 |
| Clips used / unused | 16 / 1 |
| Final duration | 73.316 s |
| Cuts | 65 (66 shots; avg 1.11 s, min 0.43 s, max 5.83 s) |
| Transitions | 12 designed transitions (flash/shake impacts on drops, whip blur on section changes), all other edits are hard cuts on beats |
| Speed ramps | 9 ramps, 1 constant slow-motion shots |
| Titles | 6: E-CELL PRESENTS, FAILATHON, FAIL FAST, BUILD BOLD, RISE HIGHER, FAILATHON |
| SFX | 15 events (boom, impact, riser, whoosh) |
| Export | H.264 High, CRF 16, yuv420p, 30 fps, AAC 320 kbps 48 kHz, faststart |

## Pacing by section
- **intro**: 7 shots, avg 2.29 s
- **drop**: 25 shots, avg 0.63 s
- **peak**: 10 shots, avg 0.69 s
- **build**: 11 shots, avg 0.96 s
- **breathe**: 12 shots, avg 1.53 s
- **finale**: 1 shots, avg 5.83 s

## Beat sync method
librosa beat_track (dynamic programming over onset strength). The beat grid sets every cut point, and each shot is 1, 2, 4 or 8 beats long.
The shot length follows the music's energy on that beat: about 1 beat in the 8 beats after a drop and on high-energy bars, 2–4 beats in calmer passages, and long shots in the intro.
Drops are the largest rises in 1-second RMS energy: 16.04s, 30.81s, 44.61s, 51.92s.
Each drop gets a cut, a white flash, a decaying camera shake, a 6% punch-in, an impact SFX and, where planned, a title slam.
A riser starts 2 s before each of the first two drops. Shot boundaries are rounded to whole frames at 30 fps.

## Shot selection
Each file is analysed from keyframes sampled at 2 fps, scaled down to 192x108. The script measures sharpness (Laplacian variance), exposure, contrast and motion, then ranks the clips into grades A–D.
Near-duplicates are found by comparing perceptual hashes (dHash) at 20/50/80% through each clip; only the best-scoring copy of each duplicate group is kept.
The shot order follows the event: capture time, or the `--order` keywords. A/B clips are moved onto the drops (swapped within ±3 slots), and the best video is held back for the slow-motion finale.

## Colour
Pass 1 corrects exposure per clip, using its measured brightness.
Pass 2 applies the same gentle look to every shot: S-curve, teal shadows / warm highlights, +7% contrast, a small saturation lift and a light vignette.
There is no LUT, and skin tones are protected because the hue shift is small.

## Audio
The BGM is the master track. Its gain is only ever lowered, to give -1 dBFS peak headroom, and it is never cut or replaced.
The SFX are synthesised by the script (whoosh, impact, boom, riser) and kept 8–11 dB below the BGM. A limiter at -1 dBFS sits on the mix, with a 0.6 s fade-out at the end.
Original camera audio is muted.

## Validation
See VALIDATION_REPORT.md: **PASS**.

## Known limitations / not automated
- No `.drp` is produced by this script. A genuine `.drp` can only be exported by DaVinci Resolve: run `FAILATHON_AV_RESOLVE_SCRIPT.py` inside Resolve, which builds the project and calls `ExportProject`.
- Shot selection is based on measured image quality, not on what is in the frame (no face or object recognition). Check the contact sheet and swap shots in Resolve if needed.
- Speed ramps and grades are baked into the graded shot files on timeline V1. The Resolve script also builds a second timeline from the untouched source media for regrading.
- Titles are pre-rendered ProRes 4444 clips with alpha (same look in the MP4 and in Resolve). Text+ versions are added for editing where the Resolve API allows.
