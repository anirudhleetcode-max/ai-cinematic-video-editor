# Cute doodle music edit: v2

The final file is `output/cute_doodle_music_edit_v2.mp4`. The previous version, `output/cute_doodle_music_edit.mp4`, is unchanged. The checked specifications are in the "Output" section below.

v2 is re-rendered from the original source (`input/source.mov`, plus the same optical-flow slow-motion hug clip), not from the v1 MP4. v1 has its thin outline baked into the pixels, so it couldn't be upgraded directly. The timeline, the uninterrupted original audio and the lip-sync are the same as v1.

## What changed from v1

### Bold, thick, vibrant doodle art
- **Palette:** saturated colours throughout. Hot pink, vibrant lavender-purple, turquoise/aqua, coral red, lemon/golden yellow, warm orange, electric blue, purple and mint, with white highlights. Pastel tones were dropped as the main doodle colours.
- **Ink rim:** every doodle stroke is drawn over a deep-plum rim 4 px wider than the stroke. This keeps doodles readable on both the light wall and the dark hair and clothing.
- **Stroke widths:**
  - sparkle details: about 2–4 px
  - small lines: about 4–6 px
  - main doodle outlines: about 6–8 px
  - large illustrations: up to about 12 px (rainbow arcs)
  - plus the ink rim
- **Glow:** the doodle glow was lowered (strength 0.28) so the shapes stay crisp instead of turning into soft blobs.
- **Fish:** 27 fish in turquoise, coral, pink, purple, yellow and lavender. They have eyes, fins and swaying tails, give off a steady stream of bubbles, and swim both ways at different speeds along gently curving paths. Some swim in pairs, and new fish keep arriving every 4–8 s.
- **Flowers:** coloured petals, yellow centres with a white highlight, and green leaves. They turn slowly.
- **Hearts:** filled hearts in vibrant colours, often trailed by two smaller hearts.
- **Line art:** an extra bold squiggle, spiral, arrow or constellation draws itself onto empty wall every 2.6 s, then drifts and fades.

### A continuous doodle universe
About 2,300 planned animation events: v1 had about 520.

- **Background stars:** 72 slots of tiny stars and dots spread over the whole frame. Each twinkles at its own speed, drifts slowly and pulses lightly on every beat. A slot respawns elsewhere before its star fades, so roughly 70 are always alive.
- **Middle layer:** 14 slots that are always busy. Hearts float up, notes drift, butterflies flap along curved paths, daisies rotate and clouds drift. Swirls, curved arrows, wavy lines and constellations draw themselves stroke by stroke, and sound-wave bars bounce to the beat. Which kinds appear changes through the song:
  - calm opening: notes, swirls, clouds, constellations, suns
  - singing sections: notes, sound waves, hearts, arrows, butterflies
  - hug: hearts, winged hearts, butterflies, sparkle rings
- **Large illustrations:** ten larger pieces (rainbows, big moons with stars, suns, a big cloud, a big constellation) draw themselves on in the upper or lower corners at different points in the song.
- **Hug scene:** 36 soft pastel petals tumble down through it.
- **Ending:** extra hearts and stars gather before the final fade.
- **Frame:** a hand-drawn double frame (cream and pink) with a bobbing heart, star, swirl and sparkle in the corners. It draws itself on in the first 1.5 s.
- **Light leaks:** three slow, soft peach, pink and blue light leaks drift across the frame.
- **v1 elements kept:** beat sparkles, movement reactions, paired hearts, fish, shooting stars and captions are all still there.

Every doodle sits behind the people: the doodle layer is erased wherever a person is, with a small margin. So nothing ever covers eyes, mouths, faces or hands. The background fills up while the people stay the clear focus.

### Thicker, glowing outlines
- **Look:** a 4 px soft-white main stroke, a 3 px pink-lavender accent line about 8 px further out, and an 8 px translucent pink glow band, all softened by the overlay glow pass. The v1 outline was a 3 px line plus a 2 px sketch line at lower opacity.
- **Behaviour:** the line keeps a gap of about 20 px outside the body, wobbles gently like a hand-drawn line, is redrawn every 3 frames, pulses with the beat and carries 6 travelling sparkles.
- **Better mask before thickening:**
  - Hair is detected with a stricter darkness threshold (below 58 instead of 72), which drops most wall shadows.
  - Only small holes are filled now (under 1.2% of the frame), such as the white undershirt. Large wall areas enclosed by an arm loop stay background.
  - Contour smoothing is stronger (σ = 4 instead of 3), on top of the existing frame-to-frame smoothing.
- **Limitations:** when the two people touch, one merged outline goes around both. In parts of the hug scene the outline still takes in wall area next to the bodies, so it bulges out there.

### Soft beauty grade, with no change to face shape
- **Where it applies:** only on skin pixels (detected by skin colour and limited to the person mask, with feathered edges, so there are no rectangles).
- **Softening:** an edge-preserving filter is applied at half resolution, and only the change it makes is blended back at 60% strength. Fine skin texture from the original frame is kept.
- **Glow:** a gentle peach-pink warmth and a 4.5% brightness lift on skin.
- **Whole frame:** a pastel grade (lifted lavender shadows, warm highlights, soft highlight roll-off), bloom, a softer screen glow, finer grain than v1 (75% strength) and a light vignette.
- **No reshaping:** there is no reshaping, eye enlarging, face swapping or AI generation of any kind. Face geometry comes straight from the original frames.

### Music-driven motion
The beat grid is reused from v1 (about 81 bpm, 153 beats). It drives:
- the outline brightness
- the size pulse of hearts, stars, corner accents and background stars
- the sound-wave bars
- beat sparkles
- a gentle 2% zoom on each downbeat

## Asset credits
See `ASSET_CREDITS.md`. In short, Pixabay was unreachable from this environment (HTTP 403 from the network proxy), so no Pixabay asset was used. Every doodle is original and drawn procedurally. The caption font is Caveat (SIL OFL 1.1).

## Reproduce
```
export EDIT_WORK=/scratch EDIT_SOURCE=/path/to/source.mov   # slowmo.mp4 must be in $EDIT_WORK (see README.md)
cd edit && python3 plan_v2.py && python3 augment_v2.py && python3 render_v2.py && ./finalize_v2.sh
```

## Output

**File:** `output/cute_doodle_music_edit_v2.mp4`, 99,834,578 bytes (about 95 MiB, below GitHub's 100 MiB file limit).

| Property | Value |
|---|---|
| Video | H.264, 1920×1080, 30 fps, yuv420p, CRF 20 with a 6.5 Mbps cap |
| Audio | AAC, 48 kHz, stereo, 192 kbps: the original song with a 0.3 s fade-in and a 1 s fade-out |
| Duration | 113.200 s (3,396 frames), the same as v1 |

The final file was checked as follows:
- All 3,396 frames decode.
- ffmpeg's `blackdetect` and `freezedetect` found no black or frozen segments.
- The audio is present for the full length (mean −29.2 dB, peak −0.2 dB), with the same levels as v1.
- 16 frames from 0.5 s to 112.5 s were inspected (`review_frames_v2.jpg`):
  - the faces are unchanged and unobstructed
  - the outline is thicker and glowing
  - doodles are moving across the background in every sampled frame
- Full-resolution frames were also inspected during testing.
