# v5: reference-reel style (cute doodle background swap)

**Video:** `output/v5/cute_doodle_reference_style_v5.mp4`. 1920×1080, 30 fps, H.264, with the original AAC soundtrack. 113.2 s, 99.5 MB (two-pass 6.75 Mbps). QC: 3,396/3,396 frames decode, no freezes, black only at the fades, SSIM 0.989 vs the CRF 17 master; all automated checks passed. The frame-to-frame brightness jumps it lists are the designed background cuts on the beat. The results are in `qc_results.json`.

## The look, matched to the supplied reference reel
- **Colour intro (first ~3.7 s):** the real shot, with glitter blue stars and gold hearts popping in.
- **Black-and-white cut-out:** after the intro, both singers are cut out in black and white with gentle contrast. Faces are not altered: the image is the source frame converted to grey.
- **Sparkly mint-teal outline:** a glittering doodle trace sits a few pixels off the body, and its glitter re-sparkles every 3 frames.
- **14 illustrated backgrounds that hard-cut on the beat:**
  - every beat in the energetic sections and the slow-motion climax
  - every second beat in the gentler sections
  - slow changes through the song's quiet break

  Each background has a slow push-in and a small pop on the cut.

  The backgrounds are: navy swirls, cream space doodles, rainbow stripes, navy doodles, sky and clouds, rainbow heart rings, pale stars, big gold stars, glitter star night, wavy rainbow, watercolour stars, pink flowers, embroidery stripes and cloud pattern.
- **Same timeline as v1–v4:** the slow-motion hug climax and the fade to black at the end are unchanged.

## Assets
All backgrounds and stickers are drawn procedurally in `edit/v5/render_v5.py`. No external or copyrighted artwork is used.

## Known limitations
- The cut-out uses colour-based segmentation, not depth. In the hug (about 80–100 s), small patches of warm-lit wall can stay inside the cut-out as grey areas.
- The fastest hair flips can make the outline trace motion blur.

## Reproduce
```
export EDIT_WORK=/scratch EDIT_SOURCE=/scratch/source.mov   # same work dir as v4 (slowmo plate, beats, analysis)
cd edit/v5 && python3 render_v5.py                          # ~4 cores, chunked
```
Then mux the original audio and encode the delivery, as in `edit/v4/pipeline.py`.
