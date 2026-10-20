# Asset credits: `cinematic_doodle_music_edit_v3.mp4`

## Illustration and animation
All of it was written for this project: the illustrated world, its characters, the line work, the washes, the lights and the motion. It is drawn by `edit/v3/world.py` and `edit/v3/render_v3.py`. No third-party artwork, stock animation or clip art is in the video.

Pixabay (the source the brief suggested for animation assets) was checked again during this pass. It is still blocked by this environment's network policy (the proxy refuses `pixabay.com` with HTTP 403), so no Pixabay asset was downloaded or used.

## Third-party components

| Component | Used for | Source | License |
|---|---|---|---|
| Caveat typeface (variable) | The handwritten "two voices" title | Google Fonts repository, `ofl/caveat`, by Impallari Type | SIL Open Font License 1.1 |
| YuNet face detection model (`face_detection_yunet_2023mar.onnx`, 232 KB) | Finding faces, so the illustrated world can never be drawn over a face. It is used only for protection masks, never to alter a face. | OpenCV Zoo, `models/face_detection_yunet` (github.com/opencv/opencv_zoo) | MIT |
| OpenCV, NumPy, Pillow, FFmpeg/x264 | Image processing and encoding | Upstream projects | Apache-2.0 / BSD / HPND / LGPL-GPL respectively |

## Source material
The footage and song audio are `input/source.mov`, supplied by the repository owner. The original audio is used unaltered, apart from a 0.3 s fade-in and a 1 s fade-out.
