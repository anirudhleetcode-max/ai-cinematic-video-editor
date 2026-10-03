"""Cutroom product contract — the single source of truth for input / output parameters.

Every module that needs one of these values imports it from here (schemas defaults, director, renderer, mixer, QC,
probe). docs/PRODUCT_SPEC.md documents the same values for humans; tests/test_contract.py checks they agree.
"""
from __future__ import annotations

# ---------------------------------------------------------------- input
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"})
AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
LUT_EXTENSIONS = frozenset({".cube"})
MAX_UPLOAD_MB_DEFAULT = 4096           # per file (EDITOR_MAX_UPLOAD_MB)
MAX_LUT_MB = 8
MAX_SOURCE_SECONDS = 3 * 3600          # longer sources are rejected at ingest
MAX_OUTPUT_SECONDS = 1800              # EditPlan.duration upper bound

# ---------------------------------------------------------------- output
ASPECT_RESOLUTIONS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "21:9": (1920, 822)}
SUPPORTED_ASPECTS = ("16:9", "9:16", "1:1", "4:5")  # 21:9 is available but not part of the supported contract
DEFAULT_ASPECT = "16:9"
OUTPUT_FPS = 30.0
PREVIEW_LONG_SIDE = 640
PROXY_HEIGHT = 360
PROXY_FPS = 15
VIDEO_CODEC = "h264"                   # yuv420p, BT.709 limited range, tagged; MP4 +faststart
PIXEL_FORMAT = "yuv420p"
# constant-quality ladder (CRF for libx264/libx265; hardware encoders map it in hw.encoder_args)
FINAL_CRF = {"draft": 28, "standard": 21, "high": 17}
FINAL_PRESET = {"draft": "ultrafast", "standard": "veryfast", "high": "medium"}
MEZZANINE_CRF = {"draft": 26, "standard": 16, "high": 12}
MEZZANINE_PRESET = {"draft": "ultrafast", "standard": "veryfast", "high": "faster"}
MODE_QUALITY = {"fast": "standard", "quality": "high", "emergency": "draft"}

# ---------------------------------------------------------------- audio
AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 2
AUDIO_CODEC = "aac"
AUDIO_BITRATE_K = 320
TRUE_PEAK_CEILING_DB = -1.0
LOUDNESS_TOLERANCE_LU = 1.0            # QC / review: |integrated − target| must stay within this
SOCIAL_PLATFORMS = ("instagram_reel", "tiktok", "shorts", "youtube")
LOUDNESS_TARGET_SOCIAL = -14.0         # LUFS (streaming / social platforms)
LOUDNESS_TARGET_DEFAULT = -16.0        # LUFS (general delivery)


def loudness_target(platform: str | None) -> float:
    return LOUDNESS_TARGET_SOCIAL if (platform or "") in SOCIAL_PLATFORMS else LOUDNESS_TARGET_DEFAULT


def resolution_for(aspect: str) -> tuple[int, int]:
    return ASPECT_RESOLUTIONS.get(aspect, ASPECT_RESOLUTIONS[DEFAULT_ASPECT])


def preview_size(width: int, height: int) -> tuple[int, int]:
    s = PREVIEW_LONG_SIDE / max(width, height)
    return int(width * s) // 2 * 2, int(height * s) // 2 * 2
