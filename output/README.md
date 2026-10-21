# Cute doodle music edit

Final video: `output/cute_doodle_music_edit.mp4`. It is H.264 High + AAC-LC stereo at 1920×1080 and 30 fps, 113.2 s long (3,396 frames), about 74 MB at 5.2 Mbps.

The frames were first rendered at CRF 19, which came to 212 MB because film grain is costly to encode. The final file is that render re-encoded at CRF 21, capped at 5 Mbps, so it stays under GitHub's 100 MB file limit. `review_frames.jpg` shows 16 frames from across the edit.

The final file was checked as follows:
- All 3,396 frames decode.
- ffmpeg's `blackdetect` and `freezedetect` found no black or frozen segments.
- The audio is present for the full length (mean −29.2 dB, peak −0.2 dB).
- Face crops were compared with the source frames.

Source: `input/source.mov` from branch `claude/friendly-fermi-jn4h4o`, commit `b3437ef`. It is 1920×1080, 30 fps, 114.5 s, with stereo AAC audio.

## How it was made

Scripts are in `edit/`:

1. `analyze.py`: separates the people from the wall, measures head and hand movement, finds the beats in the song, and plans every doodle.
2. `render.py`: renders the frames in parallel.
3. `finalize.sh`: adds the original audio and encodes the final MP4.

Before those three run, ffmpeg's `minterpolate` filter (motion-compensated) builds the slow-motion hug clip.

## Edit decisions

- **Audio:** the original song runs uninterrupted from start to finish, and every singing shot stays in sync with it. The only changes are a 0.3 s fade-in and a 1 s fade-out.
- **Covered-lens shots removed:**
  - **79.8–88.2 s:** a hand covering the lens, then black. These frames are replaced by the hug and confetti scene (source 88.3–101.0 s) in optical-flow slow motion at about 0.6× speed, with a slow push-in and extra bloom. Nobody sings in this scene, so the slow motion doesn't affect lip-sync.
  - **From 113.2 s:** the lens is covered again, so the edit ends just before that.
- **Transitions:** the video fades in from a pastel cream, has soft sparkle flashes with shooting stars at the cuts into and out of the slow-motion section, and fades out to cream with "on repeat" written on screen.
- **On the beat:** a gentle 2% zoom pulse lands on each downbeat. Sparkles pop on beats, and floating hearts, notes and stars appear on downbeats.
- **Density:** the near-silent break in the song (about 18–28 s) is kept almost bare on purpose. The last minute is the most decorated.

## How the faces are kept intact

- The original frame is always the base image. No AI, face model or generative step is used anywhere.
- All graphics are drawn on a separate layer. Wherever a person is detected, that layer is erased (with a small margin), so doodles pass behind the people instead of over their faces.
- The colour grade is a gentle global curve applied to the whole frame equally: lifted lavender shadows, warm highlights, soft bloom, light grain and a slight vignette. There is no skin smoothing, reshaping or sharpening.

## The outline

- **Segmentation:** the people are separated from the plain grey wall by colour. They are saturated or dark; the wall is a flat, unsaturated grey. The mask is computed at quarter resolution, smoothed over time to stop flicker, and has its holes filled.
- **Gap:** the outline follows the edge of the mask pushed out by about 20 px, so there is always a visible gap between the line and the body.
- **Look:** two thin lines, a white-pink main stroke and a lavender sketch stroke. They wobble like hand-drawn lines, are redrawn every 3 frames, pulse on the beat, draw themselves in after each scene change, and carry small sparkles that travel along them.
- **Limitation:** when the two people overlap, one combined outline is drawn around both.

## Doodles

- **Library:** sparkles, four- and five-pointed stars, hearts (filled, outline, double and winged), music notes, fish with swaying tails and bubbles, butterflies with flapping wings, crescent moons, ringed planets, daisies, and shooting stars with motion-blurred trails.
- **Reactions to movement:** head movement or a hair flip makes sparkles appear at that person's head edge. A raised hand leaves a short star trail. When both people move together, a matching pair of hearts floats up between them.
- **Text:** three short handwritten captions in Caveat (SIL Open Font License), placed automatically on empty wall. They describe the scene ("two voices, one vibe", "bestie moments", "on repeat") and are not lyrics. The song's words weren't identified, so no lyrics are quoted.

## Reproduce

```
export EDIT_WORK=/some/scratch/dir EDIT_SOURCE=/path/to/source.mov
ffmpeg -i "$EDIT_SOURCE" -an -vf "trim=start_frame=2648:end_frame=3032,setpts=(PTS-STARTPTS)*639/384,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" \
  -frames:v 639 -c:v libx264 -crf 12 -pix_fmt yuv420p "$EDIT_WORK/slowmo.mp4"
cd edit && python3 analyze.py && python3 render.py && ./finalize.sh
```

Requires ffmpeg, Python 3, numpy, opencv-python-headless and Pillow.
