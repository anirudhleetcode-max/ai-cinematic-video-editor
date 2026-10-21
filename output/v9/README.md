# v9: neural background removal on every frame

**Video:** `output/v9/cute_doodle_reference_style_v9.mp4`. 1920×1080, 30 fps, H.264, with the original AAC soundtrack. 113.2 s, 99.3 MB. QC: 3,396/3,396 frames decode, no freezes, black only at the fades, SSIM 0.986 vs the CRF 17 master; all automated checks passed. The QC results are in `qc_results.json`.

v9 keeps the v7/v8 look: the stable sparkly outline set off the body, animated doodle stickers, 14 beat-cut backgrounds, the colour intro and the slow-motion hug. v5–v8 are unchanged.

## The problem
v5–v8 separated the girls from the wall with colour rules: colourful or dark pixels were person, and grey pixels were wall. During the hug, the warm-lit wall and the girls' shadows on it look like that too, so grey patches of wall were cut out with them (for example at 1:29), and the outline was drawn around them.

## The fix
`edit/v9/matte_rvm.py` runs **Robust Video Matting** (Lin et al., 2021; the official MobileNetV3 and ResNet50 ONNX releases), a neural network trained to matte people in video, on all 3,396 frames.
- **Temporal memory:** RVM carries its memory from frame to frame, so the matte is stable and keeps motion-blurred hair and hands. The memory is reset at each scene cut, with a 40-frame warm-up before every chunk.
- **Two models combined:** a per-pixel maximum. Both reject the wall and shadows, and a fast body part that one model makes faint is kept by the other.
- **Cleanup and storage:** tiny detached specks are removed. The alpha is stored losslessly (FFV1) and read frame-exactly by `edit/v9/render_v9.py`.
- **Faces:** they are never altered; the matte only decides what is in front of the background.

`review/v9_matte_check.jpg` shows the matte on magenta at 24 moments (including 49.3 s, 52 s, the whole hug 80–100 s, and 89 s). It contains no wall or shadow, and the hair and hands are complete. The fastest arm moves (for example 91 s) are semi-transparent, because that is the real motion blur in the footage.

`review/v8_vs_v9.jpg` compares v8 and v9 in the delivery files at 84.3, 89, 94.5, 97, 49.3 and 52 s: the wall patches and shadows in v8 are gone in v9.

## Reproduce
The model weights are not committed (the ResNet50 file is 107 MB). Download the official releases into `$EDIT_WORK/models/`:
```
https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx  -> rvm_mb3.onnx
https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50_fp32.onnx    -> rvm_r50.onnx
cd edit/v9 && python3 matte_rvm.py && python3 render_v9.py
```
RVM is GPL-3.0 licensed. It is used here as a tool to produce the mattes; its code and weights are not redistributed.

## Cost
The matte pass took 17 minutes on 4 CPU cores. The render then reuses the stored mattes.
