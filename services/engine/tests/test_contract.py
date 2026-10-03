"""The documented product contract (docs/PRODUCT_SPEC.md) and the code agree, and defaults come from one place."""
from pathlib import Path

from editor import contract as C

SPEC = (Path(__file__).resolve().parents[3] / "docs" / "PRODUCT_SPEC.md").read_text()


def test_spec_matches_contract():
    for aspect in C.SUPPORTED_ASPECTS:
        w, h = C.ASPECT_RESOLUTIONS[aspect]
        assert f"{aspect} → {w}×{h}" in SPEC
    for ext in sorted(C.VIDEO_EXTENSIONS | C.AUDIO_EXTENSIONS | C.IMAGE_EXTENSIONS):
        assert ext in SPEC, ext
    assert f"{int(C.OUTPUT_FPS)} fps" in SPEC and f"long side {C.PREVIEW_LONG_SIDE} px" in SPEC
    assert f"AAC {C.AUDIO_BITRATE_K} kb/s, {C.AUDIO_SAMPLE_RATE // 1000} kHz" in SPEC
    assert f"{C.LOUDNESS_TARGET_SOCIAL:.0f} LUFS".replace("-", "−") in SPEC and f"{C.LOUDNESS_TARGET_DEFAULT:.0f} LUFS".replace("-", "−") in SPEC
    assert "CRF 28 / 21 / 17" in SPEC and tuple(C.FINAL_CRF.values()) == (28, 21, 17)


def test_defaults_come_from_contract():
    from editor.director.agents import RESOLUTIONS
    from editor.media.probe import AUDIO_EXT, VIDEO_EXT
    from editor.schemas import AudioPlan, ExportSpec

    assert RESOLUTIONS is C.ASPECT_RESOLUTIONS
    assert VIDEO_EXT == set(C.VIDEO_EXTENSIONS) and AUDIO_EXT == set(C.AUDIO_EXTENSIONS)
    assert AudioPlan().true_peak_db == C.TRUE_PEAK_CEILING_DB and AudioPlan().target_lufs == C.LOUDNESS_TARGET_DEFAULT
    assert ExportSpec().audio_bitrate_k == C.AUDIO_BITRATE_K
    assert C.preview_size(1920, 1080) == (640, 360) and C.preview_size(1080, 1920) == (360, 640)


def test_source_duration_limit_enforced(monkeypatch, dataset):
    import pytest

    from editor import service as S

    monkeypatch.setattr(C, "MAX_SOURCE_SECONDS", 1)
    pid = S.create_project("limit")["id"]
    with open(dataset["clips"][0], "rb") as fh, pytest.raises(ValueError, match="source limit"):
        S.add_asset(pid, "long.mp4", fh)
    assert S.list_assets(pid) == []
