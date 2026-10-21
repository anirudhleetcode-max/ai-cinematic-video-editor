# v3 quality-control report

**Deliverable:** `output/cinematic_doodle_music_edit_v3.mp4`, 95,703,183 bytes.

| Property | Value |
|---|---|
| Video | H.264 High, 1920×1080, 30 fps, yuv420p, two-pass at 6.5 Mbps (6.76 Mbps overall) |
| Audio | AAC-LC, 48 kHz stereo, 256 kbps: the original soundtrack, unaltered apart from a 0.3 s fade-in and a 1 s fade-out |
| Duration | 113.200 s (3,396 frames), the same timeline as v1/v2, with lip-sync intact |

**Master:**
- The frames were rendered at CRF 18 with a 9 Mbps cap, giving a 137 MB master at 9.7 Mbps.
- That is over GitHub's 100 MB file limit, so the committed file is a two-pass re-encode of the master.
- SSIM between the delivery file and the master is **0.9896** (19.8 dB), so they are visually indistinguishable at normal viewing.
- The 137 MB master was not committed.

## Process
1. **Audit:** I measured the song's structure (RMS and spectral centroid in 0.5 s windows, plus the beat grid) and mapped which areas of the wall stay clear of the performers in each shot (`v3_analysis.npz`).
2. **Design checks:** I rendered stills at 12 key story moments and inspected them at full resolution, then revised the design:
   - organic tree and finer blossoms
   - separate hill silhouettes instead of ruled lines
   - clean cloud outlines
   - smooth heart constellation
   - less diffusion and halation in the grade
   - characters about 20% larger
   - no contour line at the climax
3. **Whole-timeline check:** a world-only animatic (one frame every 2 s for the full 113 s) to confirm the story order and character continuity.
4. **Motion prototypes:** three 6 s sequences at full resolution (opening 5–11 s, development 44–50 s, climax 86–92 s), reviewed as frame strips with frame-to-frame change statistics.
   - The opening revealed the title's "t" being lost behind hair. I moved the title into the measured clear gap and set it smaller.
   - The climax revealed that the world sat small in a high strip while the standing shot's large open wall went unused. I added the climax close-up framing (scale 1.45, tree centred in the open centre-right wall), cut together with the footage, and moved the ink hug to just after the real embrace, when that area is visible.
5. **Full render**, then the final checks below, run on the master and again on the delivery file.

## Final checks

| Check | Result |
|---|---|
| Full decode | 3,396 / 3,396 frames on both files |
| Black frames (`blackdetect`, d ≥ 0.1 s) | Only the designed fades: 0–0.23 s (fade-up) and 113.03–113.17 s (end of fade-out) |
| Frozen footage (`freezedetect`, d ≥ 1 s) | None |
| Audio | Present for the full length. Mean −29.3 dB, peak −0.6 dB, matching the source. |
| Frame-to-frame change spikes | Only the two real scene cuts (79.73 s and 101.07 s) and fast performer moves (hair flips; one singer leaning in close at 55.7 s). No world-layer jumps or flicker. |
| Acts reviewed as moving strips | Opening (0–13 s), development (28–56 s), climax (79.5–101.5 s), ending (101–113.2 s). Strips are in `qc_climax_motion_strip.jpg` and `review_frames_v3.jpg`. |
| Faces | Source and v3 compared side by side (`qc_face_fidelity.jpg`). Geometry, features, expressions and skin texture are unchanged. The only differences are the global grade and a very light (30%) skin-only softening. No generative processing. |
| Face protection | YuNet found faces in 3,391 / 3,396 frames. Their ellipses are added to the person mask, so no illustration crosses a face in any reviewed frame. |
| Difficult masks | Hair flip (50.6 s), raised arm in the hug (84.3 s), embrace (95.0 s, 97.9 s), all in `qc_difficult_masks.jpg`. The world passes cleanly behind hair and arms. |
| v2 under-arm defect | **Fixed.** The warm-lit wall (saturation around 46) is no longer counted as person: the threshold went from 38 to 58, and large enclosed holes are no longer filled. The wall under the raised arm now correctly shows the illustrated world. |
| Story continuity | Every element sits at a fixed position and every character position is a continuous function of time. The animatic and the act strips confirm the order (title → cottage → Wanderer → seed → night → planting → growth → pollen and flowers → Friend → meeting → lanterns → climax bloom and rising lanterns → echo hug → stars → constellation → walk home → lit window → retrace) and that nothing appears or vanishes arbitrarily. |

## Known limitations
- **No real depth:** compositing is 2D layering. The world sits behind the performer mask and does not interact with real objects in the room. The light switch on the wall stays visible through the drawings.
- **Small illustrations:** they are about 2–7% of the frame height. This keeps them subordinate to the performers, but on a phone screen the characters' facial details (eyes, cheeks) are tiny.
- **Time hidden behind heads:** in the seated take the performers often lean into the middle, so some illustrated story beats (part of the walks, the tree during some head movements) are briefly hidden. This is genuine occlusion and the story stays readable, but a viewer will catch some beats only on a rewatch.
- **Tree during the hug:** in the standing shot the raised arm covers the tree crown for about 2 s (around 88–90 s).
- **Gesture streams:** only three hand gestures passed the strength threshold. All three were on the right-hand singer, so gold ink reaches only east-side flowers. The west flowers open with the lanterns instead.
- **Title wording:** "two voices" describes the scene and is not a lyric. The song's words were not identified.
- **No external assets:** Pixabay is still blocked in this environment. All illustration is original and procedural.
- **Repository size:** the repository history now holds four large MP4s (about 74 MB, 100 MB and 96 MB of renders, plus the 27 MB source on another branch). Future renders should use Git LFS (git-lfs 3.4.1 is available here) or GitHub Releases rather than plain commits.
