# Assets and where they are used

| Asset | Content | Used |
|---|---|---|
| `WhatsApp Video 17.14.48.mp4` (70.0 s, 848×478) — **take A** | Hook, intro, problem, pain point, solution, features, recommendations | Source 9.35–69.55 s → output 0:00–1:00.2. The first 9.35 s is dropped: pre-roll plus an off-camera "Okay? Ready? Start." |
| `WhatsApp Video 17.14.30.mp4` (24.4 s) — **take B** | Impact, vision, close | Whole clip → output 1:00.2–1:24.6 |

No B-roll, screenshots, logos, product recordings, script or music were supplied. So:

* Every supporting visual is original motion graphics built from what she says. The product interface in "How it works" is a **concept visualisation** of the three features she names. It is labelled "CONCEPT INTERFACE" on screen, and you can turn the label off in `studio/src/config.ts`. Replace it with real screen recordings if you have them.
* The music (ambient D-major pads, soft pentatonic plucks, a low drone) and all SFX (whooshes, ticks, click, low impact, chimes) are synthesized in `pipeline/audio_mix.py`. No third-party audio is used, so there are no licensing issues.
* Fonts: Manrope and Instrument Serif (both SIL OFL), via @fontsource.
* Models used for processing: Real-ESRGAN general-x4v3 (upscale), RVM ResNet50 (matting), DeepFilterNet3 (speech denoise), Parakeet-TDT 0.6B and Whisper medium.en (transcription).
