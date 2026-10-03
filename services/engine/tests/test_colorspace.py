"""End-to-end colour accuracy: known RGB patches encoded as BT.709, BT.601 (SD) and full-range sources must come out
of the full render pipeline (segments → concat → final pass, neutral grade) with the same RGB values when the
output is decoded the way players decode HD (BT.709, limited range)."""
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

PATCHES = [(200, 30, 30), (30, 180, 40), (40, 60, 210), (230, 200, 60), (128, 128, 128), (220, 170, 140)]


def _make_source(path: Path, w: int, h: int, matrix: str, rng: str, tag_space: str, tag_prim: str) -> None:
    img = np.zeros((h, w, 3), np.uint8)
    for i, c in enumerate(PATCHES):
        img[:, i * w // 6:(i + 1) * w // 6] = c
    png = path.with_suffix(".png")
    cv2.imwrite(str(png), img[..., ::-1])
    pix = "yuvj420p" if rng == "pc" else "yuv420p"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", "2", "-i", str(png),
                    "-vf", f"scale=out_color_matrix={matrix}:out_range={rng},format={pix}", "-c:v", "libx264", "-crf", "4",
                    "-colorspace", tag_space, "-color_primaries", tag_prim, "-color_trc", tag_prim if tag_prim != "smpte170m" else "smpte170m",
                    "-color_range", "pc" if rng == "pc" else "tv", str(path)], check=True)


def _decode_patches(path: Path, at: float) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.2f}", "-i", str(path), "-frames:v", "1",
                        "-vf", "scale=in_color_matrix=bt709:in_range=tv,format=rgb24", "-f", "rawvideo", "-"], capture_output=True, check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, check=True).stdout.strip().split(",")
    w, h = int(probe[0]), int(probe[1])
    a = np.frombuffer(p.stdout, np.uint8).reshape(h, w, 3).astype(int)
    return np.array([a[h // 2, int((i + 0.5) * w / 6)] for i in range(6)])


@pytest.mark.parametrize("kind", ["bt709", "bt601_sd", "full_range"])
def test_render_preserves_colour(tmp_path, kind):
    from editor import service as S
    from editor.director.context import ProjectContext  # noqa: F401  (import check)
    from editor.render.engine import render_plan
    from editor.schemas import CreativeBible, EditPlan, Ending, ExportSpec, Segment, StorySection

    src = tmp_path / f"{kind}.mp4"
    if kind == "bt709":
        _make_source(src, 1280, 720, "bt709", "tv", "bt709", "bt709")
    elif kind == "bt601_sd":
        _make_source(src, 720, 480, "bt601", "tv", "smpte170m", "smpte170m")
    else:
        _make_source(src, 1280, 720, "bt709", "pc", "bt709", "bt709")
    p = S.create_project(f"colour {kind}")
    with open(src, "rb") as fh:
        a = S.add_asset(p["id"], src.name, fh, "clip")
    sec = [StorySection(name="main", start=0, end=1.5)]
    plan = EditPlan(duration=1.5, bible=CreativeBible(style="test", color="neutral", typography="none", transition_philosophy="cuts", effect_philosophy="none", pacing="medium", music_strategy="none", story_structure=["main"]), story_structure=sec, ending=Ending(type="cut", duration=0),
                    timeline=[Segment(id="s0", asset_id=a["id"], src_in=0.2, src_out=1.7, out_start=0, out_duration=1.5, keep_audio=False)],
                    export=ExportSpec(width=640, height=360, quality="high", prefer_hw=False))
    plan.color_grade.intensity = 0.0
    plan.color_grade.match_shots = False
    out = tmp_path / "out.mp4"
    assets = S._asset_infos(p["id"])
    render_plan(plan, assets, out, tmp_path / "work")
    got = _decode_patches(out, 0.7)
    err = np.abs(got - np.array(PATCHES)).max()
    tags = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_space,color_primaries,color_transfer,color_range",
                           "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert tags.split(",")[:1] == ["tv"] or "bt709" in tags, tags
    assert err <= 6, f"{kind}: max channel error {err} (got {got.tolist()})"


def test_user_lut_is_applied(tmp_path):
    """An uploaded .cube LUT must actually change the render (it used to be validated and then ignored)."""
    from editor import service as S
    from editor.render.engine import render_plan
    from editor.schemas import CreativeBible, EditPlan, Ending, ExportSpec, Segment, StorySection

    src = tmp_path / "src.mp4"
    _make_source(src, 640, 360, "bt709", "tv", "bt709", "bt709")
    lut = tmp_path / "swap.cube"  # swaps red and blue channels
    rows = []
    n = 5
    for b in range(n):
        for g in range(n):
            for r in range(n):
                rows.append(f"{b / (n - 1):.4f} {g / (n - 1):.4f} {r / (n - 1):.4f}")
    lut.write_text(f"LUT_3D_SIZE {n}\n" + "\n".join(rows) + "\n")
    p = S.create_project("user lut")
    with open(src, "rb") as fh:
        a = S.add_asset(p["id"], src.name, fh, "clip")
    with open(lut, "rb") as fh:
        lut_a = S.add_asset(p["id"], lut.name, fh, "lut")
    sec = [StorySection(name="main", start=0, end=1.5)]
    plan = EditPlan(duration=1.5, bible=CreativeBible(style="t", color="n", typography="none", transition_philosophy="cuts", effect_philosophy="none",
                                                      pacing="medium", music_strategy="none", story_structure=["main"]),
                    story_structure=sec, ending=Ending(type="cut", duration=0),
                    timeline=[Segment(id="s0", asset_id=a["id"], src_in=0.2, src_out=1.7, out_start=0, out_duration=1.5, keep_audio=False)],
                    export=ExportSpec(width=640, height=360, quality="high", prefer_hw=False))
    plan.color_grade.intensity = 0.0
    plan.color_grade.lut_asset_id = lut_a["id"]
    out = tmp_path / "o.mp4"
    render_plan(plan, S._asset_infos(p["id"]), out, tmp_path / "w")
    got = _decode_patches(out, 0.7)
    want = np.array([(c[2], c[1], c[0]) for c in PATCHES])
    assert np.abs(got - want).max() <= 8, got.tolist()
