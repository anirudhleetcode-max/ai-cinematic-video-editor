# v4: "The Seed of Light", the world awakens. Treatment

## Idea
The two friends sing in front of a plain wall. Over the song, the wall turns out to be a sheet of paper, and a hand-drawn world wakes up on it, behind them.
- **The story:** two small ink characters live out a friendship that runs in parallel with the real one, and reaches its peak at the same moment as the real hug.
- **The pen:** a white pen traces the two real friends, as if the artist drawing the world is also drawing them.
- **Blue paint:** streaks of blue pigment move through the air of the world like weather.
- **Gold:** small fragments of warm light (auras, sparks, lanterns) mark the moments of greatest warmth.

## Visual hierarchy
These rules decide every placement in `edit/v4/timeline.json`:
1. **The real people.** Their faces, gestures and embrace are never covered. Every illustration sits behind the person matte. The only things above them are the thin white pen outline, which sits outside their silhouettes, and the light finishing.
2. **The illustrated story:** cottages, path, tree, the two characters, lanterns.
3. **Large environmental effects:** blue paint strokes and the climax wash.
4. **Small accents:** gold sparks, hand-drawn stars, white scribbles, shooting stars.

## What v4 adds to v3
v3 is kept as the foundation: its world, story, characters, grade and masks are reused unchanged unless noted. v4 adds:

| Element | Design | Depth and blend |
|---|---|---|
| **White pen outline** | About 3 px white, with line weight varying ±35%. It sits 2.5 px outside the silhouette, wobbles by about 1.1 px with the noise tied to screen position (so it doesn't swim), and sometimes gets a faint second trace. It draws itself on at 7.4 s and again at each scene cut. It is only drawn where the image shows a real edge, so it never runs through flat wall. A faint ink shadow helps it read on the ivory wall. | Above the people. Normal blend, very restrained glow. |
| **Blue paint streaks** | 17 choreographed strokes in midnight, indigo, cobalt, azure and pale cyan, with occasional white. Each one is: a watercolour body with ragged edges; about 22 independent bristles with dry-brush gaps; pigment granulation; darker wet edges; broken pale highlights; splatter at the wet head; and a dissolve into drifting flecks. The texture is fixed per stroke, so deposited paint never flickers. There are two kinds: sweeps, which deposit paint, and accelerating streaks, which travel and shed sparks. | Behind the people. Body multiplied into the wall, bristles blended normally. |
| **Golden auras** | Seven broken, hand-drawn gold arcs and four inner ticks above each head, rotating slowly and breathing gently on the downbeat, with sparks drifting up. Anchored to tracked, smoothed faces with a confidence value. When tracking is lost, the aura fades instead of jumping. Shown in four windows only: the strong return, the strong section, the embrace, and the outro. | Behind the people. Additive light plus a faint ink line. |
| **Gold particles** | Motes rising from the blossoming tree crown through the climax, and a slow ring of motes around the pair at their meeting. | Behind the people. Additive. |
| **Hand-drawn stars** | 12 irregular five-point stars (ink outline and gold wash), each with its own rotation and twinkle, appearing one by one at nightfall. Four shooting stars: three in the silent break and one in the outro. | Behind the people. Multiply and additive. |
| **White scribbles** | A sparkle burst at the cottage door, a "!" over the Wanderer when the seed falls, a burst where the seed lands, an arrow to the sprout, motion dashes as the Friend waves, a handwritten **"Hi"** with a tiny heart at the meeting, a loose spiral, a small heart over the echo hug, and a sparkle at the lit window. Each draws itself on, holds, then fades. | Behind the people. White with an ink shadow. |
| **Characters** | Scaled from 1.22× to 1.36× so the story reads better. | — |
| **Camera** | The constant breathing zoom is removed. Only the slow-motion hug keeps a gentle push-in, motivated by the slow motion. | — |

## Palette
- **Warm ivory wall:** the paper.
- **Navy ink:** all line work.
- **Coral:** the Wanderer and the west cottage.
- **Teal:** the Friend and the east cottage.
- **Gold:** the light motif (seed, pollen, lanterns, auras, stars).
- **Blue paint, the new voice of the music:** midnight and indigo for depth, cobalt for body, azure and pale cyan for the brightest moments.

Gold and blue are complementary and sit against the warm wall without changing skin tones. The grade is the v3 look-up table and is never applied selectively to faces.

## Music
The timeline uses the measured song sections:
- hushed intro 0–7.5 s
- first phrase to 18.2 s
- near-silent break to 27.9 s
- strong return to 38 s
- dip to 44 s
- build to 55.5 s
- airy passage to 69.5 s
- strong section to 77.5 s
- breath to 79.7 s
- **climax 79.7–101.1 s** (the slow-motion hug, the brightest and loudest stretch)
- outro to 113.2 s

The beat grid (about 80.75 bpm, 153 beats) is re-derived by `pipeline.py prep` and matches v3 exactly.

Effects are placed on phrase starts and downbeats in the strong sections, never on every beat:
- The paint enters at the first phrase, sweeps in on the downbeat of the strong return, streaks at the 34 s peak, rises with the build, arcs over the meeting, drifts through the airy passage, and streaks three times through the strong section.
- The silent break gets no paint, only night and shooting stars.

## The climax as a sequence
| Stage | Time | What happens |
|---|---|---|
| A: Anticipation | 79.7–84 s | The cut to the standing shot comes with a warm flare, and the world cuts to its close-up. Two dark brush strokes rise along the outer edges of the frame (left at 80.6 s, right at 81.5 s). The lanterns let go. Gold motes start rising from the tree. |
| B: Expansion | 84–88 s | The tree finishes growing and its blossoms open in waves. The watercolour wash spreads out from the tree. A broad cobalt-to-azure arc sweeps over the top of the frame (87.6 s). |
| C: The embrace | 88–97.7 s | Golden auras appear above both real heads. A pale inner arc follows (89.6 s). As the friends embrace, two azure strokes sweep down the upper corners towards them (93.3 s and 93.6 s), framing the hug without crossing it. The lanterns climb through the sky behind them and petals fall. The faces and the embrace stay clear. |
| D: Illustrated echo | 98.1–100.7 s | The ink pair hugs under the blooming tree, with a small white heart above them. |
| E: Release | 97.7–101.1 s | The lanterns become stars and the paint dissolves into flecks. The auras fade, and a warm flare carries the cut back to the seated shot. |

## Ending
- The heart constellation is drawn in.
- The pair walks home hand in hand and goes inside. The window glows and a small sparkle appears at it.
- A last midnight brush stroke crosses the sky and dissolves as the path is retraced in gold.
- Everything fades to black with the final chord.

## Not included, and why
- **Pop-culture characters** (SpongeBob, Patrick, Deadpool, Naruto, a unicorn): there are no licensed or user-supplied assets, and copyrighted artwork won't be pulled from the web. Everything in v4 is original.
- **ML person segmentation:** PP-HumanSeg (OpenCV Zoo) was tested on the hardest hug frames. It misclassified the dark, partly out-of-frame figure badly enough to delete her body, so colour segmentation was kept. The edge-evidence check on the outline compensates for the warm-wall false positives that colour segmentation produces.
