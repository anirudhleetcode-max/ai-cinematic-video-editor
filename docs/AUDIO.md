# Audio

## Analysis (per clip, `media/audio.py`, `media/vad.py`)
| Signal | Method | Provenance |
|---|---|---|
| Speech regions | **Silero VAD v5** (local ONNX, `scripts/download_models.py`) when installed; otherwise the DSP detector (voice-band energy, flatness, syllabic modulation) | the analysis records `speech_detector` |
| Silence | frames ≥ 0.5 s below max(−50 dB, noise floor + 3 dB) | measured |
| Noise floor, SNR | 10th percentile of frame RMS; p90 − p10 | measured |
| Clipping | max(share of samples above 0.99 FS at 48 kHz, share inside flat-topped runs) — lossy codecs turn flat tops into overshoot | measured |
| Sound type (speech / music / crowd_ambient / mixed / silence) | speech share, tonal share (low spectral flatness), broadband share | heuristic |

Measured on real audio (this repository's harness):

| Audio | Speech detected by Silero VAD | Speech detected by the old DSP detector |
|---|---|---|
| LibriSpeech readings | 86–91 % | 0 % |
| your phone presenter clips | 87–97 % | 0–1 % |
| music (4 tracks) | 0–2 % | 0 % |

The old detector had been tuned on synthetic speech only.

## Planning (`director/agents.py::audio_engineer`)
* **Dialogue priority:** a shot keeps its audio as **dialogue** when VAD speech covers more than 40 % of its range
  at normal speed. Speech intervals are mapped into output time (`AudioPlan.speech_regions`).
* Other clip audio is **ambience** (kept only when there is no music), otherwise muted.
* Speed-ramped segments never carry dialogue. Ramps are not placed on speech shots, and ramped clip audio is muted
  under the music.
* Clips whose source measures as clipped get `adeclip`.

## Mix (`render/audio_mix.py`)
1. Dialogue clips are **level-matched**: each clip's speech RMS is brought to `dialogue_target_db` (−20 dBFS,
   capped at ±9 dB), so speakers recorded at different distances don't jump.
2. The dialogue chain: high-pass, FFT noise reduction, EQ, de-esser, compression.
3. **Automation curves**, not hard cuts: inside speech regions (padded by 150 ms), music ducks −12 dB, ambience
   −8 dB and SFX −6 dB, with attack/release smoothing. The report includes ducked seconds and speech seconds.
4. Music bed (best window or multi-song crossfades), SFX, voice-over.
5. End fade, soft limiter, two-pass EBU R128 loudnorm (linear) to the platform target (−14 / −16 LUFS, −1 dBTP).
   Loudness is re-measured.
6. Final mux: AAC 320 kb/s with a −1 dBTP limiter. QC's clipping check can trigger an audio-only re-limit.

The mix is **cached** by a hash of exactly what it depends on: the audio plan, music, SFX and voice-over, segment
audio content and timing, and source fingerprints. A colour, text or ending revision reuses it.
