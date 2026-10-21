# Asset credits: `cinematic_doodle_music_edit_v4.mp4`

## Artwork and animation
All of it is original to this project. That covers the illustrated world, both characters, the white pen outline, the blue paint strokes, the golden auras, particles, stars, shooting stars and white scribbles. Everything is drawn procedurally by `edit/v3/world.py`, `edit/v4/engine.py` and `edit/v4/render_v4.py`. No stock animation, clip art, emoji or third-party characters are used.

**Third-party characters:** the brief named SpongeBob, Patrick, Deadpool, Naruto and a unicorn. No licensed or user-supplied assets for them were available, so none were used.

**Pixabay:** blocked by this environment's network policy (proxy 403) in every attempt, so no Pixabay assets were used.

## Third-party components

| Component | Used for | Source | License |
|---|---|---|---|
| Caveat typeface | The "two voices" title (from v3) and the handwritten "Hi" | Google Fonts repository, `ofl/caveat`, by Impallari Type | SIL Open Font License 1.1 |
| YuNet face detector (`face_detection_yunet_2023mar.onnx`) | Face boxes for the face-protection matte and the tracked head anchors of the golden auras. Never used to alter a face. | OpenCV Zoo (github.com/opencv/opencv_zoo) | MIT |
| OpenCV 5.0.0, NumPy 2.5.3, Pillow 12.3.0, FFmpeg 6.1.1 / x264 | Processing and encoding | Upstream projects | Apache-2.0, BSD, HPND, LGPL/GPL |

**Evaluated and not used:** PP-HumanSeg (`human_segmentation_pphumanseg_2023mar.onnx`, OpenCV Zoo, Apache-2.0) was tested as a semantic gate for the person matte. It was rejected because it deleted the body of the partly out-of-frame figure in the hug. It is not shipped.

## Source material
The footage and song audio are `input/source.mov` (branch `claude/friendly-fermi-jn4h4o`, commit `b3437ef`), supplied by the repository owner. The original soundtrack is used unaltered, apart from a 0.3 s fade-in and a 1 s fade-out.
