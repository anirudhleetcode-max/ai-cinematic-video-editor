# v10: scene-cut music edit on the reference reel's song

**Video:** `output/v10/cinematic_doodle_music_edit_v10.mp4`
- 31,108,065 bytes (31.1 MB)
- 1920×1080, 30 fps, H.264 High, yuv420p, **10.000 s, 300 frames**
- Audio: the reference reel's own track (HE-AAC, 44.1 kHz stereo), **stream-copied and bit-identical**

The version is named **v10** because `output/v5` already holds an earlier reference-style video. v4, v5–v9 and the source footage are unchanged.

## 1. Soundtrack (from the reference reel)

| Item | Result |
|---|---|
| Song title and artist | **Not identified.** The environment's network blocks the identification services (AcoustID and MusicBrainz return a proxy 403), and no title is guessed. |
| Identity confirmed? | The *identity* is unconfirmed. The *audio* is confirmed to be exactly the reel's: the decoded PCM of v10's audio has the same MD5 (`b0152035873e9004a6564d3c533838a7`) as the reel's. |
| Range used | **0.000–10.000 s of the reel**, which is all of it. The reel contains only this 10 s excerpt, and its music begins at its first frame. Whether that is the start of the original song can't be determined without the full track. |
| Offset in v10 | 0.000 s. The audio and video both start at 0. |
| Processing | None: no re-encode, pitch, speed, volume or fades. The excerpt ends at 10.0 s, as in the reel, with near-silence in its final 20 ms, so there is no click. |
| Not the source song | Compared with your source video's song: at the best-matching offset, the log-mel correlation is 0.204, the same as unrelated offsets (median 0.193), and the waveform correlation is 0.016. They are different songs; they only share a tempo grid (159 vs 80.7 BPM). |
| Why 10 s | Only 10 s of the song exist in the reel, and the brief rules out looping or stretching. You chose the 10 s edit using the exact reference audio. Lip-sync to this song is not possible, because the girls sing the source song. |
| Rights | The song's copyright holder is unknown. Extracting it from a reel gives **no permission to publish**, so check licensing before posting publicly. |

The extracted audio is in the working directory: `$EDIT_WORK/v10/ref_audio.m4a`. It is not committed (unknown rights; it is already embedded in the MP4).

## 2. Musical timing map (`edit/v10/music.json`)

| Measure | Value |
|---|---|
| Tempo | **159 BPM** (beat 0.377 s), steady throughout |
| Bar downbeats | 0.36, 1.85, 3.36, 4.85, 6.36, 7.85, 9.34 s |
| Strongest accents | 0.69, **1.10**, 1.47, 2.97, **3.35**, **4.05** (the strongest of all, off-beat), 4.47, 7.47, **8.57**, 9.71 s |
| Energy | Constant: RMS between −9 and −23 dB per 0.1 s, with no breaks or silences. The emotional shape therefore comes from the picture: calm, playful, reveal, burst, climax, embrace. |

The reference reel itself is one continuous shot: a 2.1 s colour intro, then a background swap every 5–7 frames (on eighth notes) behind a black-and-white cut-out. v10 keeps that piece-to-piece idea, but as six art-directed scenes with real footage cuts. The rapid swaps are used only once, as a designed burst (S4).

## 3. Edit decision list (`edit/v10/edl.json`, which the renderer reads)

Each scene's source time is on the project timeline (`edit/common.py`), where 79.77–101.07 s is the existing slow-motion plate.

| # | Out (s) | Dur | Source | Cut motivated by | World | Subject | Mood |
|---|---|---|---|---|---|---|---|
| S1 | 0.00–1.10 | 1.10 | 3.60–4.70 | Song pickup to the first accent (1.10) | Cinematic original: grade, vignette, 1.2% push, film grain, gold ink line on the wall behind the girls | Colour | Calm, intimate |
| S2 | 1.10–2.97 | 1.87 | 14.80–16.67 | Accent at 1.10; held a phrase plus a beat so the laugh plays uncut | Ink and paper: botanical ink drawings and hatched hills draw themselves on, with parallax | Sepia duotone, double ink outline | Playful, warm |
| S3 | 2.97–4.03 | 1.07 | 35.30–36.37 | Onset at 2.97; first paint stroke lands on 3.35 as the hands open | Indigo paper with three v4 textured brush strokes | High-contrast black and white, white hairline | Dramatic reveal |
| S4 | 4.03–6.37 | 2.33 | 48.90–51.23 | Strongest accent (4.05); world changes on beats 4.48, 4.85, 5.22, 5.60, 5.98 | Six designed panels: gold constellation, coral sun rays, Bauhaus arcs, line waves, halftone, concentric arcs | Warm black and white, paper-cut border | Energetic |
| S5 | 6.37–8.57 | 2.20 | 89.20–91.40 (slow motion) | Bar downbeat 6.37, start of the final phrase | Painted dusk sky, three parallax cloud layers, light beams, falling petals | Golden colour grade, gold line | Climactic, dreamy |
| S6 | 8.57–10.00 | 1.43 | 95.00–96.43 (slow motion) | Accent 8.57: from the reach to the embrace | **The v4 climax frames, preserved** (blue paint arcs, white pen outline) with a warm grade | v4 render | Emotional resolution |

The shot lengths vary deliberately: 1.10, 1.87, 1.07, 2.33 (cut into 0.37–0.43 s panels), 2.20 and 1.43 s.

## 4. Transition report

| At | Type | Reason |
|---|---|---|
| 1.10 s (f33) | **Brush reveal** (f27–35) | The gold line drawn in S1 leads into a cream brush stroke with a painterly torn edge. It wipes diagonally and completes on the accent. |
| 2.97 s (f89) | **Hard cut** | On the onset; the change from warm sepia to indigo carries the impact. |
| 4.03 s (f121) | **Motion-matched cut** | Her hands open outward at the end of S3, and the hair flip continues that outward motion. On the strongest accent. |
| 4.47, 4.87, 5.23, 5.60, 5.97 s | **Panel cuts** within S4 | One per beat, with a 4-frame settle (3.5% scale) on each. The subject is one continuous shot, so it never jumps. |
| 6.37 s (f191) | **Light transition** (f185–196) | A warm gold light from the sun's direction swells to 55% (never white, never full-frame) and clears into the sky. |
| 8.57 s (f257) | **Hard cut** | On the accent: the reach becomes the embrace. |
| 9.73–10.00 s (f292–299) | **Fade out** | The excerpt ends at 10.0 s, and the picture resolves to black over the last two eighth notes. |

Short dissolves were deliberately not used; no transition needed one.

## 5. Synchronization check (measured on the delivery file)

- **Cut timing:** every planned cut frame is within **±14 ms** of its beat or accent, less than half a frame (16.7 ms):

  | Cut frame | 33 | 89 | 121 | 134 | 146 | 157 | 168 | 179 | 191 | 257 |
  |---|---|---|---|---|---|---|---|---|---|---|
  | Offset (ms) | −3 | −5 | −13 | −3 | +14 | +9 | −2 | −12 | +11 | −1 |
- **Cut detection** (histogram change) finds exactly the planned hard and panel cuts. The other differences are the designed gradual events:
  - frame 33 is not detected, because it is the gradual brush reveal
  - frame 186 is detected: the start of the light swell
  - frame 299 is detected: the end of the fade

## 6. Technical QC (on `cinematic_doodle_music_edit_v10.mp4`; raw data in `qc_frames.json`)

| Check | Result |
|---|---|
| Resolution, frame rate | 1920×1080, 30/1 |
| Duration | Video 10.000 s, 300 frames, all decoded. Audio 9.984 s, identical to the reel's own audio duration. |
| Audio | Present, starts at 0.000, bit-identical to the reference. Mean −16.0 dB, peak −3.3 dB, no silences. |
| Black frames | Only frame 299, the last frame of the designed fade |
| Frozen frames (`freezedetect`, ≥0.3 s) and near-still frames | None |
| Identical consecutive frames (including at every cut) | None |
| Frame-to-source log | `$EDIT_WORK/v10/frame_log.json` maps every output frame to its scene and source frame |

## 7. Visual review

Two caveats on how this was reviewed:
- **Playback:** I can't watch video at normal speed in this environment. The edit was reviewed from the decoded delivery frames: an every-0.2 s rhythm strip of the whole edit (`review/edit_rhythm_strip.jpg`) and the frames before, at and after every cut and transition (`review/cut_boundaries_1.jpg`, `cut_boundaries_2.jpg`, `brush_reveal_T1.jpg`).
- **Earlier problems:** problems found and fixed before delivery are listed in the next table.

| Found in preview | Fix |
|---|---|
| The S1 gold line crossed the girls' bodies | Moved to the wall and placed behind them using the matte |
| The S3 strokes read as dashed stripes | Gave them a full pigment body |
| The S5 foreground petals crossed a face | Removed the foreground petals; only petals behind the girls remain |
| The S5 starburst sun rays and hard cloud blobs looked cartoonish | Replaced with soft beams and diffuse clouds |
| Paper mottling too blotchy; constellation too faint | Reduced the mottling; strengthened the gold lines |
| The brush-reveal edge was a fine saw-tooth | Changed to a broad painterly wobble with fine bristle texture |

**Faces and identity:** the girls are never re-generated, warped or rescaled. The only changes are colour treatments (grade, sepia duotone, black and white) and the S1 1.2% push, which is applied to the whole frame. Their mattes are the v9 neural (Robust Video Matting) alphas.

## 8. Known limitations

- **No song title:** see section 1. Publication rights are unknown.
- **Lip-sync:** the girls sing the source song, so their mouths do not match this music.
- **Length:** 10 s, because only 10 s of the song exist in the reel.
- **Motion blur:** S4's hair flips are motion-blurred in the source. The cut-out keeps the blur (semi-transparent hair), and the paper-cut border follows the blurred silhouette.
- **The S6 v4 frames** carry v4's own limitations: the white outline is jagged in places, and small wall patches remain inside the v4 cut-out in the hug.
- **S3 paint strokes:** these use v4's bristle renderer, which shows some streaky dry-brush texture on the dark paper.

## 9. v4 compared with v10

| | v4 | v10 |
|---|---|---|
| Structure | One continuous 113 s timeline in a single world (the ink world on the real wall) | **Six distinct scenes** from six source moments, with 10 cuts and transitions |
| Music | Source song (the girls sing it) | **The reference reel's song**, bit-exact |
| Editing | Effects timed to the music inside one shot | Cuts on beats and accents, phrase-aware shot lengths, five transition types |
| Worlds | Ink landscape, paint, gold auras | Cinematic original, ink and paper, indigo paint, graphic panels, dusk sky, plus the v4 climax |
| Matte | Colour rules | v9 neural matting |
| Reused from v4 | n/a | Paint-stroke engine (S3) and the climax frames (S6) |

## Reproduce

```
export EDIT_WORK=/scratch EDIT_SOURCE=/scratch/source.mov   # same work dir as v9 (mattes: edit/v9/matte_rvm.py)
cd edit/v10 && python3 render_v10.py                         # renders the 6 scenes in parallel, then assembles
ffmpeg -i $EDIT_WORK/v10/v10_video.mkv -i <reference reel> -map 0:v -map 1:a -c copy -movflags +faststart out.mp4
```
