"""Real-media tests. They run only when real media is present (python scripts/fetch_real_media.py &&
python scripts/make_real_variants.py); otherwise they are skipped — never faked with synthetic files."""
import json
from pathlib import Path

import pytest

REAL = Path(__file__).resolve().parents[3] / "tests" / "real_media"
MANIFEST = REAL / "derived" / "MANIFEST.json"
needs_real = pytest.mark.skipif(not MANIFEST.exists(), reason="real media not downloaded (scripts/fetch_real_media.py)")


def _items():
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else []


@needs_real
@pytest.mark.parametrize("item", _items(), ids=lambda it: it["file"])
def test_inspection_detects_expected_properties(item):
    from editor.media.inspect import inspect_media

    r = inspect_media(REAL / item["file"])
    P, ex, warn = r["props"], item["expect"], " ".join(r["warnings"])
    if ex.get("corrupt"):
        assert not r["ok"], r
        return
    assert r["ok"], r["issues"]
    for k in ("width", "height", "display_width", "display_height", "rotation", "orientation", "bit_depth"):
        if k in ex:
            assert abs(P[k] - ex[k]) <= 2 if isinstance(ex[k], int) else P[k] == ex[k], (k, P.get(k), ex[k])
    if "fps" in ex:
        assert abs(P["avg_fps"] - ex["fps"]) < 0.6, (P["avg_fps"], ex["fps"])
    if ex.get("vfr"):
        assert "variable_frame_rate" in warn
    if ex.get("hdr"):
        assert P["hdr"] == "HLG" and "hdr:HLG" in warn
    if "sar" in ex:
        assert P["sar"] == ex["sar"] and "non_square_pixels" in warn
    if "audio_streams" in ex:
        assert P["audio_streams"] == ex["audio_streams"] and "multiple_audio_streams" in warn
    if "vcodec" in ex:
        assert P["vcodec"] == ex["vcodec"]
    if ex.get("kind") == "audio":
        assert r["kind"] == "audio"


@needs_real
def test_real_library_files_all_decode():
    from editor.media.inspect import inspect_media

    lib = sorted((REAL / "library").rglob("*.*"))
    lib = [p for p in lib if p.suffix.lower() in {".mp4", ".mkv", ".avi", ".ogg"}]
    bad = [(p.name, r["issues"]) for p in lib for r in [inspect_media(p)] if not r["ok"]]
    assert lib and not bad, bad


@needs_real
def test_rotated_and_anamorphic_frames_have_display_geometry():
    from editor.media import frames as F
    from editor.media.probe import probe

    rot = REAL / "derived" / "phone_portrait_rotated.mov"
    ana = REAL / "derived" / "anamorphic_sar43.mp4"
    fr = F.sample_frames(rot, 1.0, 180, duration=2, meta=probe(rot))
    fa = F.sample_frames(ana, 1.0, 192, duration=2, meta=probe(ana))
    assert fr.rgb.shape[1] > fr.rgb.shape[2]  # portrait after rotation
    assert abs(fa.rgb.shape[2] / fa.rgb.shape[1] - 16 / 9) < 0.03  # 1440x1080 @ 4:3 SAR displays 16:9


@needs_real
def test_corrupt_uploads_are_rejected_with_reason():
    from editor import service as S

    p = S.create_project("corrupt uploads")
    for name in ("corrupt_truncated.mp4", "corrupt_not_video.mp4"):
        with open(REAL / "derived" / name, "rb") as fh, pytest.raises(ValueError, match="unusable media|could not read"):
            S.add_asset(p["id"], name, fh, "clip")
