# v8: background removal that keeps fast-moving hair and body parts

**Video:** `output/v8/cute_doodle_reference_style_v8.mp4`. 1920×1080, 30 fps, H.264, with the original AAC soundtrack. 113.2 s, 99.3 MB. QC: 3,396/3,396 frames decode, no freezes, black only at the fades, SSIM 0.987 vs the CRF 17 master; all automated checks passed. The before and after comparison is in `review/v7_vs_v8_fast_motion.jpg`. The results are in `qc_results.json`.

v8 keeps everything from v7: the stable outline 18 px off the body, the animated doodle stickers, 14 beat-cut backgrounds, the colour intro and the slow-motion hug. v5–v7 are unchanged.

## The problem
The v5–v7 cut-out counted only colourful (skin, maroon tops) or dark (hair) pixels as person. When the singers move fast, their hair and hands are motion-blurred into a mid-grey smear over the grey wall, so those pixels were classed as wall and removed. Hair flips lost whole locks, and a quick hand lost its edges.

## The fix (`edit/v8/render_v8.py`)
- **Wall light map:** each frame, the visible wall's brightness is measured and filled in behind the people, so the wall's lighting gradient and the camera's exposure changes are followed.
- **Motion-blur matting:** a pixel darker than the wall behind it is partly person, and how much darker sets its opacity. Blurred hair is kept as semi-transparent hair, the way the real footage looks, instead of being cut away. Soft wall shadows (about 85% of wall brightness) are above the ramp start and stay background.
- **Only near the people:** the search is limited to about 90 px around the colour matte, so marks on the wall away from them are never picked up. Isolated specks are dropped.
- **White clothing:** gaps enclosed by the bodies that are brighter than the wall (the white undershirt) are filled. Real wall seen through an arm loop in the hug is not brighter, so it stays open.

The final matte is the union of the v7 matte and the blur matte. A clean-plate (empty wall) approach was tested first and rejected: the camera moves, and about half of the wall is never visible.

## Known limitations
- **Shadows on the wall:** the girls' darkest shadows on the wall, right next to their bodies, can still be included in the cut-out (as in v5–v7).
- **Warm-lit wall:** during the hug (about 80–100 s), some warm-lit wall can remain inside the cut-out.
