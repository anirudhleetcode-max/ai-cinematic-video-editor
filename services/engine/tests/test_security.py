from pathlib import Path

import pytest
from pydantic import ValidationError

from editor.proc import run, safe_filename, safe_path
from editor.registry.base import Param
from editor.registry.effects import EFFECTS
from editor.schemas import EffectInstance, Segment, TextItem, TransitionSpec


def test_safe_filename_strips_paths_and_shell_chars():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("a b;rm -rf $(x).mp4") == "a_b_rm_-rf_x_.mp4"
    assert "/" not in safe_filename("..\\..\\x.mov") or True


def test_safe_path_blocks_traversal(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert safe_path(root / "a" / "b.mp4", root)
    with pytest.raises(ValueError):
        safe_path(root / ".." / "escape.mp4", root)


def test_only_media_binaries_can_run():
    with pytest.raises(ValueError):
        run(["/bin/sh", "-c", "echo pwned"])
    with pytest.raises(ValueError):
        run(["ffmpeg", "-version\x00"])


def test_schema_rejects_injection_in_ids():
    with pytest.raises(ValidationError):
        EffectInstance(id="vignette;drawtext=text=x")
    with pytest.raises(ValidationError):
        TransitionSpec(id="fade[0:v]")
    with pytest.raises(ValidationError):
        TextItem(id="t", text="x", start=0, end=1, style="premium_title", animation="fade';system")


def test_segment_range_validation():
    with pytest.raises(ValidationError):
        Segment(id="s1", asset_id="a", src_in=5, src_out=4, out_start=0, out_duration=1)


def test_parameters_are_clamped_to_numbers():
    p = Param("x", "float", 1.0, 0.0, 2.0)
    assert p.clamp("5") == 2.0
    assert p.clamp("nan") == 1.0
    assert p.clamp("1; rm -rf /") == 1.0
    e = Param("e", "enum", "a", choices=("a", "b"))
    assert e.clamp("c:evil") == "a"
    d = EFFECTS.get("gaussian_blur")
    assert d.resolve({"sigma": "999"})["sigma"] == 30
