# v7: calm, stable outline set further from the body

**Video:** `output/v7/cute_doodle_reference_style_v7.mp4`. 1920×1080, 30 fps, H.264, with the original AAC soundtrack. 113.2 s, 99.3 MB. QC: 3,396/3,396 frames decode, no freezes, black only at the fades, SSIM 0.987 vs the CRF 17 master; all automated checks passed. The results are in `qc_results.json`.

v7 keeps everything from v6: the colour sticker intro, the black-and-white guided-filter cut-out, 14 beat-cut backgrounds, the animated doodle stickers and the slow-motion hug. v5 and v6 are unchanged.

## What changed: the outline
In v6 the outline was drawn from each frame's matte, so hair wisps, motion-blur fringes and frame-to-frame matte noise made it wriggle whenever the singers moved. In v7 the outline has its own silhouette:
- **5-frame temporal median:** removes matte pixels that flip on and off.
- **Wide spatial smoothing:** the band follows the body's shape (head, shoulders, arms), not individual hair strands or blur.
- **Adaptive temporal blend:** small sways and matte noise barely move the outline, while big moves (a raised arm, a lean, the hug) are followed within a few frames.
- **Threshold hysteresis:** the edge doesn't bounce back and forth.
- **Further from the body:** an 18 px gap (v6: 6 px) and a 26 px sparkly mint-teal band (v6: 22 px), with white rims and a soft shadow.

## Measured stability
Band flicker is the fraction of band pixels that switch and switch back within 2 frames, measured on the outline geometry:

| Section | v6 | v7 |
|---|---|---|
| 48–53 s (hair flips, dancing) | 0.252 | 0.056 |
| 84–89 s (hug approach) | 0.081 | 0.043 |
| 100–105 s (after the hug) | 0.036 | 0.016 |

## Known limitations
- **Fast moves:** the outline follows big moves with a short delay, so in the fastest gestures a hand can pass in front of the band for a few frames before it catches up.
- **Hug wall patches:** the cut-out is still colour-based, so warm-lit wall can remain inside it during the hug (about 80–100 s).
