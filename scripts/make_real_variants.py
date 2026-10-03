"""Derive format/edge-case variants from the REAL media library (scripts/fetch_real_media.py).

The picture and sound are real recordings; only the container / codec / frame rate / orientation / metadata (or a
clearly named degradation such as added shake or blur) is changed, so the engine can be tested against formats the
library does not contain (4K, 120 fps, rotation-tagged phone video, HDR-tagged HEVC, VFR, anamorphic, …).
Every output is listed in tests/real_media/derived/MANIFEST.json with what was changed and what the engine should
detect. These files are labelled DERIVED everywhere they are reported.

  python scripts/make_real_variants.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "tests" / "real_media" / "library"
OUT = ROOT / "tests" / "real_media" / "derived"


def ff(*args: str) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-nostdin", *args]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{p.stderr[-800:]}")


def main() -> int:
    v, m, s = LIB / "video", LIB / "music", LIB / "speech"
    need = [v / "classroom.mp4", v / "worker-zone-detection.mp4", v / "fruit-and-vegetable-detection.mp4", v / "people-detection.mp4",
            v / "store-aisle-detection.mp4", m / "vibe_ace.ogg", s / "librispeech_198-209-0000.ogg"]
    missing = [str(p) for p in need if not p.exists()]
    if missing:
        print("missing library files — run scripts/fetch_real_media.py --all first:\n  " + "\n  ".join(missing))
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audio").mkdir(exist_ok=True)
    x264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    aac = ["-c:a", "aac", "-b:a", "160k"]
    items: list[dict] = []

    def add(name: str, changed: str, expect: dict, *args: str) -> None:
        out = OUT / name
        if not out.exists():
            ff(*args, str(out))
        items.append({"file": f"derived/{name}", "derived_from_real": True, "changed": changed, "expect": expect})
        print("ok", name)

    cls, wz, fruit, ppl, store = (str(v / n) for n in ("classroom.mp4", "worker-zone-detection.mp4", "fruit-and-vegetable-detection.mp4",
                                                         "people-detection.mp4", "store-aisle-detection.mp4"))
    speech, song = str(s / "librispeech_198-209-0000.ogg"), str(m / "vibe_ace.ogg")
    # --- resolution / frame rate --------------------------------------------------------------------------
    add("uhd_4k_30.mp4", "upscaled 1080p→2160p (lanczos)", {"width": 3840, "height": 2160, "fps": 30},
        "-i", cls, "-t", "12", "-vf", "scale=3840:2160:flags=lanczos", *x264, "-an")
    add("uhd_4k_hevc10_hlg.mp4", "4K HEVC 10-bit tagged BT.2020/HLG (metadata HDR; picture is SDR-derived)",
        {"hdr": True, "transfer": "arib-std-b67", "bit_depth": 10},
        "-i", wz, "-t", "8", "-vf", "scale=3840:2160,format=yuv420p10le", "-c:v", "libx265", "-preset", "ultrafast", "-crf", "24",
        "-x265-params", "log-level=error:colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc", "-color_primaries", "bt2020",
        "-color_trc", "arib-std-b67", "-colorspace", "bt2020nc", "-tag:v", "hvc1", "-an")
    add("fps_24.mp4", "re-timed to 24 fps", {"fps": 24}, "-i", wz, "-t", "10", "-vf", "fps=24", *x264, *aac)
    add("fps_25.mkv", "re-timed to 25 fps, MKV", {"fps": 25, "container": "matroska"}, "-i", wz, "-ss", "10", "-t", "10", "-vf", "fps=25", *x264, *aac)
    add("fps_50.mp4", "re-timed to 50 fps", {"fps": 50}, "-i", fruit, "-t", "10", "-vf", "fps=50", *x264)
    add("fps_120.mp4", "re-timed 59.94→120 fps (frame repetition, like a high-frame-rate phone export)", {"fps": 120},
        "-i", fruit, "-ss", "20", "-t", "8", "-vf", "fps=120", *x264)
    # --- orientation ------------------------------------------------------------------------------------------
    add("phone_portrait_rotated.mov", "landscape-stored frames + 90° display-matrix rotation (iPhone-style portrait MOV)",
        {"rotation": 90, "display_width": 1080, "display_height": 1920, "orientation": "portrait"},
        "-display_rotation", "90", "-i", wz, "-t", "10", "-c", "copy")
    add("vertical_native_1080x1920.mp4", "centre crop to native 9:16 (no rotation metadata)", {"width": 1080, "height": 1920, "orientation": "portrait"},
        "-i", wz, "-ss", "30", "-t", "10", "-vf", "crop=608:1080,scale=1080:1920", *x264, *aac)
    add("anamorphic_sar43.mp4", "1440×1080 with 4:3 pixel aspect (HDV-style anamorphic)", {"sar": "4:3", "display_width": 1920},
        "-i", cls, "-t", "8", "-vf", "scale=1440:1080,setsar=4/3", *x264)
    # --- containers / codecs ----------------------------------------------------------------------------------
    add("container.webm", "VP9/Opus WebM", {"vcodec": "vp9"}, "-i", ppl, "-t", "8", "-c:v", "libvpx-vp9", "-b:v", "1M", "-deadline", "realtime",
        "-cpu-used", "8", "-c:a", "libopus")
    add("container.m4v", "H.264/AAC M4V", {"vcodec": "h264"}, "-i", ppl, "-ss", "10", "-t", "8", *x264, *aac)
    add("container_mjpeg.avi", "MJPEG/PCM AVI", {"vcodec": "mjpeg"}, "-i", store, "-t", "6", "-c:v", "mjpeg", "-q:v", "4", "-pix_fmt", "yuvj420p",
        "-c:a", "pcm_s16le")
    add("prores_422.mov", "ProRes 422 MOV (camera/NLE mezzanine)", {"vcodec": "prores"}, "-i", store, "-ss", "20", "-t", "4",
        "-c:v", "prores_ks", "-profile:v", "2", "-c:a", "pcm_s16le")
    # --- timing / streams ---------------------------------------------------------------------------------
    add("vfr_jitter.mp4", "variable frame rate (irregular timestamps, phone-style)", {"vfr": True},
        "-i", wz, "-t", "10", "-vf", "setpts='PTS+0.012*sin(N*1.7)/TB'", "-fps_mode", "vfr", *x264, *aac)
    add("multi_audio.mkv", "two audio streams (music + speech)", {"audio_streams": 2},
        "-i", ppl, "-i", song, "-i", speech, "-t", "10", "-map", "0:v", "-map", "1:a", "-map", "2:a", *x264, *aac)
    add("speech_over_real_video.mp4", "real video + real LibriSpeech narration as its audio", {"speech": True},
        "-i", ppl, "-i", speech, "-map", "0:v", "-map", "1:a", "-shortest", *x264, *aac)
    # --- degradations (clearly named) ---------------------------------------------------------------------------
    add("degraded_dark.mp4", "exposure lowered (eq brightness −0.3, gamma 0.6)", {"issue": "underexposed"},
        "-i", ppl, "-t", "6", "-vf", "eq=brightness=-0.3:gamma=0.6", *x264)
    add("degraded_bright.mp4", "exposure raised (eq brightness +0.4)", {"issue": "overexposed"},
        "-i", ppl, "-ss", "10", "-t", "6", "-vf", "eq=brightness=0.4:contrast=0.8", *x264)
    add("degraded_blur.mp4", "defocus blur (gblur σ=6)", {"issue": "blurry"}, "-i", wz, "-ss", "20", "-t", "6", "-vf", "gblur=sigma=6", *x264)
    add("degraded_shaky.mp4", "hand-held shake added (random crop offsets)", {"issue": "shaky"},
        "-i", wz, "-ss", "40", "-t", "8", "-vf",
        "crop=1600:900:160+120*sin(t*13)*cos(t*7.3):90+70*sin(t*11.1+1),scale=1920:1080", *x264)
    add("degraded_clipped_audio.mp4", "speech boosted +24 dB (hard clipping)", {"issue": "clipped_audio"},
        "-i", ppl, "-i", speech, "-map", "0:v", "-map", "1:a", "-t", "8", "-af", "volume=24dB,alimiter=limit=1:level=false", *x264, "-c:a", "aac", "-b:a", "192k")
    add("near_duplicate_a.mp4", "segment 0–8 s of worker-zone", {"near_duplicate_of": "near_duplicate_b.mp4"}, "-i", wz, "-ss", "50", "-t", "8", *x264)
    add("near_duplicate_b.mp4", "segment 1–9 s of the same shot, re-encoded", {"near_duplicate_of": "near_duplicate_a.mp4"},
        "-i", wz, "-ss", "51", "-t", "8", "-vf", "eq=brightness=0.02", *x264)
    add("long_5min.mp4", "5-minute clip (looped classroom + people + store, re-encoded)", {"duration": 300},
        "-stream_loop", "-1", "-i", cls, "-t", "300", "-vf", "scale=1280:720,fps=30", *x264, "-an")
    add("very_short_0p4s.mp4", "0.4 s clip", {"issue": "too_short"}, "-i", ppl, "-ss", "5", "-t", "0.4", *x264)
    # corrupted: a truncated MP4 (moov atom lost) and a text file renamed to .mp4
    trunc = OUT / "corrupt_truncated.mp4"
    if not trunc.exists():
        data = Path(wz).read_bytes()
        trunc.write_bytes(data[: len(data) // 3])
    items.append({"file": "derived/corrupt_truncated.mp4", "derived_from_real": True, "changed": "first third of the file only",
                  "expect": {"corrupt": True}})
    fake = OUT / "corrupt_not_video.mp4"
    fake.write_text("this is not a video file\n" * 20)
    items.append({"file": "derived/corrupt_not_video.mp4", "derived_from_real": False, "changed": "text file with .mp4 extension",
                  "expect": {"corrupt": True}})
    # --- audio formats --------------------------------------------------------------------------------------
    for ext, args in {"mp3": ["-c:a", "libmp3lame", "-q:a", "2"], "wav": ["-c:a", "pcm_s16le"], "aac": ["-c:a", "aac", "-b:a", "192k", "-f", "adts"],
                      "m4a": ["-c:a", "aac", "-b:a", "192k"], "flac": ["-c:a", "flac"]}.items():
        src = {"mp3": "vibe_ace", "wav": "sugar_plum_fairy", "aac": "hungarian_dance_5", "m4a": "vibe_ace", "flac": "sugar_plum_fairy"}[ext]
        add(f"audio/{src}.{ext}", f"transcoded to {ext}", {"kind": "audio"}, "-i", str(m / f"{src}.ogg"), "-vn", *args)
    (OUT / "MANIFEST.json").write_text(json.dumps(items, indent=1))
    print(f"{len(items)} derived files → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
