# v4 quality-control report

**Deliverable:** `output/v4/cinematic_doodle_music_edit_v4.mp4`. The machine-readable results are in `output/v4/qc_results.json`, produced by `edit/v4/qc.py`. Every number below comes from an actual run.

## Measured results (delivery file)

| Check | Result |
|---|---|
| Size and bitrate | 159,230,571 bytes, 11.25 Mbps overall (two-pass at 11 Mbps from the master) |
| Video | H.264 High, 1920×1080, 30/1 fps, yuv420p, 113.200 s |
| Frames decoded | **3,396 / 3,396** |
| Audio | AAC, 48 kHz, stereo, 113.200 s, starting at 0.000. Mean −29.3 dB, peak −0.6 dB, the same as the source track. |
| Audio sync | The audio is the source track trimmed from 0 s with no offset, and the video timeline is frame-identical to v1–v3, which were lip-sync checked. Audio and video durations match exactly (113.200 s). |
| Black frames (`blackdetect`, d ≥ 0.1 s) | 0–0.23 s and 113.03–113.17 s. These are only the designed fade-up and the end of the fade-out. |
| Frozen footage (`freezedetect`, d ≥ 1 s) | **None** |
| Silences (−50 dB, ≥ 1.5 s) | Start at 18.52 s and 26.14 s, the song's own near-silent break. `silencedetect` on `source.mov` gives the same start times. |
| Brightness jumps (frame-to-frame change > 12 levels) | 52.77 s and 54.2 s: the same jumps exist in the source (12.2 and 13.1 levels; movement in the shot). 79.63–79.80 s: the scene cut plus the designed warm flare. 101.07 s: the scene cut. **No unintended brightness flashes.** |
| SSIM vs the 210 MB master (CRF 16) | 0.9878 (19.1 dB) |
| Automated checks | resolution, frame rate, all frames decode, duration, audio present, audio full length, no freezes, black only at fades: **all passed** |

## Prototype and review process
1. **Stills at key moments** (full resolution). These revealed four defects, all fixed before the full render:
   - The first paint version looked like glossy neon tubes. It was rebuilt with a watercolour body, about 22 dry-brush bristles, granulation, wet edges and broken highlights.
   - An outline glow halo surrounded the people. The glow was reduced to a 1 px blur at 0.22.
   - The face-protection ellipses reached onto the wall and made an egg-shaped band around each head. They were tightened to 0.5w × 0.62h.
   - White scribbles were illegible on the ivory wall. Strokes were thickened, the ink shadow raised to 0.5 alpha, and "Hi" enlarged and moved.
2. **Segmentation experiment.** PP-HumanSeg was tested as a semantic gate on the hug frames. It removed the body of the partly out-of-frame figure, so it was rejected.
3. **Edge-evidence check.** Colour segmentation counts some warm-lit wall as person in the hug. The outline is therefore drawn only where the image actually shows an edge (colour contrast ≥ 24 across the contour, with hysteresis that ignores dips shorter than 24 points). The false line through the wall is gone.
4. **Three full-resolution motion prototypes** (opening 6–12 s, meeting 52–58 s, climax 86–99 s), reviewed as frame strips with change statistics, plus 8-frame full-resolution crop sequences of the outline on a hair edge. Crown gaps in the outline that came and went were fixed with hysteresis.
5. **First full render, then QC.** Detached outline fragments appeared around motion-blurred hands, and an interior trace followed the undershirt neckline. Investigating them uncovered a sign error: the contour normals pointed inward. Three fixes followed:
   - normals oriented outward per contour
   - an outer-envelope filter (points where a 31 px-closed matte is occupied just outside are skipped)
   - a minimum run of 40 points per stroke

   Verified on four hard frames, then the whole film was re-rendered. The render manifest records the code commit (`c5c7639`).
6. **Final file checks.** QC was run on the encoded delivery file. Opening, climax and ending strips, face comparisons and the difficult-mask frames were all regenerated from the delivery file (`output/v4/review/`).

## Visual verification (from the delivery file)

| Check | Result |
|---|---|
| **Faces** (`qc_face_fidelity.jpg`) | Source vs v4 side by side: identical features, expressions and texture. The only differences are the global grade and the 30% skin softening carried over from v3. |
| **Difficult masks** (`qc_difficult_masks.jpg`) | Hair flip (50.6 s), raised arm (84.3 s), embrace (94.5 s), after the hug (98.9 s): the world sits behind hair and arms, the outline follows outer edges, and no illustration crosses a face. |
| **Paint** | At full resolution the strokes show bristle streaks, dry-brush gaps, granulation and ragged edges. They stay behind the people. The climax arcs frame the embrace without crossing a face or body. |
| **Golden auras** | Subtle broken rings above the heads, appearing only in their four windows. They follow the smoothed tracked faces and fade when tracking confidence drops. |
| **Story continuity** | The act strips and the 18-frame sheet confirm that the v3 story order holds, with the v4 events at their timeline times: "Hi" at the meeting, arcs at the meeting and climax, a heart over the echo hug, the window sparkle. |
| **Ending** | The world settles, the last stroke dissolves, and the image fades cleanly to black. |

## Known limitations
- **Outline on the warm wall:** the warm-lit wall (saturation around 46–89) still enters the person matte in parts of the hug. The edge-evidence check removes the outline there, but the illustrated world is also slightly cut back in those small wall patches.
- **Outline on motion blur:** the outline follows the outer silhouette, including real motion-blurred arms. In the fastest moves (hair flips, waving hands) it traces the blur edge, which can look busy for a few frames. It no longer breaks into detached fragments.
- **Outline gaps:** it occasionally leaves short gaps where hair meets the wall with very low contrast.
- **No real depth:** compositing is 2D layering behind a person matte. There is no depth estimation.
- **Paint density at the climax:** during 93–97 s, up to six strokes overlap in the upper third. This frames the embrace intentionally, but it is the busiest part of the film.
- **Not included:** pop-culture characters (no licensed assets) and Pixabay assets (network-blocked). All artwork is original.
- **Render cost:** about 33 minutes on 4 CPU cores. Chunks are resumable, and changing configuration or timeline values requires a re-render.
