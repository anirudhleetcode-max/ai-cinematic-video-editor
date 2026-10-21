# v6: thicker, body-accurate outline and animated doodle stickers

**Video:** `output/v6/cute_doodle_reference_style_v6.mp4`. 1920×1080, 30 fps, H.264, with the original AAC soundtrack. 113.2 s, 99.3 MB. QC: 3,396/3,396 frames decode, no freezes, black only at the fades, SSIM 0.986 vs the CRF 17 master; all automated checks passed. The results are in `qc_results.json`.

v6 keeps the v5 reference-reel look: colour sticker intro, black-and-white cut-out, 14 illustrated backgrounds cutting on the beat, and the slow-motion hug. v5 is unchanged.

## What changed
- **Outline accuracy:** the colour matte is refined against the frame itself with a guided filter, so its edge snaps to the real hair, arm and shoulder edges. The outline is then built at full 1080p resolution from a distance transform of the true silhouette, so it follows the body shape at a constant distance.
  - The temporal smoothing reacts faster than in v5, so the outline keeps up with quick moves.
  - Small false gaps (the white undershirt at the neckline) are filled, so no stray outline appears inside a body.
  - Real gaps, such as wall seen through the arm loop in the hug, keep their outline.
- **Thicker outline:** a 22 px sparkly mint-teal band (v5 was about 10 px), 6 px off the body, with thin white rims and a soft drop shadow, so it reads like a sticker cut.
- **Animated doodle stickers:** every background cut brings a new set of 6–8 stickers that pop in and then move behind the singers. The set is drawn from seven designs (stars, hearts, sparkles, flowers, smileys, clouds and moons), each with a white sticker border, ink outline and glossy highlight; some have little faces.
  - **Motion:** they float, wobble, slowly spin and bounce on every beat.
  - **Hand-drawn feel:** their lines "boil" at 7.5 fps, like hand-drawn animation.

## Assets
Everything is drawn procedurally in `edit/v6/render_v6.py` and `edit/v5/render_v5.py`. No external or copyrighted artwork is used.

## Known limitations
- The matte is colour-based. In the hug (about 80–100 s), some warm-lit wall can remain inside the cut-out.
- Very fast hair flips are motion-blurred in the source, so the outline traces the blur.
