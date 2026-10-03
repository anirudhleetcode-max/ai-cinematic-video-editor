# Cutroom product contract

The canonical values live in `services/engine/editor/contract.py`. `services/engine/tests/test_contract.py` checks
that this document and the code agree.

## Input
| Kind | Accepted | Validation |
|---|---|---|
| Video clips | `.mp4 .mov .mkv .avi .webm .m4v` — H.264, HEVC, VP9, AV1, ProRes, MJPEG, MPEG-4 (legacy codecs warned); any resolution up to 4K and beyond; 10–120 fps; CFR or VFR; portrait, landscape and rotation-tagged; square or anamorphic pixels; 8 or 10 bit; BT.709 / BT.601 / BT.2020; limited or full range; SDR / HLG / PQ | FFprobe and decode-window check; corrupt or truncated files are rejected with the reason |
| Images | `.png .jpg .jpeg .webp` | decoded by FFmpeg |
| Music, voice-over, SFX | `.mp3 .wav .aac .m4a .flac .ogg`; any sample rate or channel layout (resampled to 48 kHz stereo) | FFprobe and decode-window check |
| Reference video | as video clips | analysed for style only; its footage is never used |
| Logo | an image (PNG with alpha recommended) | — |
| LUT | `.cube` 3D, size 2–65, ≤ 8 MB | parsed and checked before FFmpeg reads it |
| Limits | 4096 MB per file (`EDITOR_MAX_UPLOAD_MB`), per-user quota (`EDITOR_USER_QUOTA_GB`, 50 GB), sources up to 3 h | — |

Filenames are never trusted: names are sanitised, content is probed, and the declared MIME type is ignored.
Multiple audio streams: the first is used. No audio stream: treated as silent.

## Output
| Property | Value |
|---|---|
| Container | MP4, `+faststart` (progressive playback) |
| Video | H.264, `yuv420p`, BT.709 primaries / transfer / matrix, limited range, tagged; square pixels |
| Aspect ratios | 16:9 → 1920×1080 · 9:16 → 1080×1920 · 1:1 → 1080×1080 · 4:5 → 1080×1350 (21:9 → 1920×822 also available) |
| Frame rate | 30 fps (constant) |
| Preview | same pipeline, long side 640 px, draft quality, proxies for sources above 720p |
| Quality ladder | constant quality. Final: CRF 28 / 21 / 17 (draft / standard / high), x264 presets ultrafast / veryfast / medium. Mezzanines: CRF 26 / 16 / 12. Fast mode = standard, Quality mode = high, Emergency mode = draft |
| Audio | AAC 320 kb/s, 48 kHz, stereo |
| Loudness | −14 LUFS for social / streaming platforms (Reels, TikTok, Shorts, YouTube); −16 LUFS otherwise; true-peak ceiling −1 dBTP; QC tolerance ±1 LU |
| Duration | as requested (3 s – 30 min); QC tolerance ±0.25 s |

## Workflow
Upload → analyse → prompt → EditPlan (validated, repaired) → preview → natural-language revisions (versioned,
incremental) → final render → QC and reviews → download. All long work runs as server-side jobs that survive the
browser closing.
