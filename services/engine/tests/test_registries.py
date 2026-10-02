import numpy as np

from editor.proc import run
from editor.registry import REGISTRIES, library_stats, search_library
from editor.registry.color import COLOR_PRESETS, grade, preset_params, write_cube
from editor.registry.effects import EFFECTS, render_effect
from editor.registry.transitions import TRANSITIONS, transition_spec
from editor.render.text_ass import AssBuilder
from editor.schemas import TextItem


def test_every_effect_renders():
    ctx = {"w": 160, "h": 90, "dur": 0.5, "fps": 10}
    for d in EFFECTS.all():
        g = render_effect(d.id, {}, ctx, "0:v", "o")
        run(["ffmpeg", "-v", "error", "-f", "lavfi", "-t", "0.5", "-i", "testsrc2=s=160x90:r=10", "-filter_complex", g, "-map", "[o]", "-f", "null", "-"])


def test_every_transition_resolves_and_numpy_ones_run():
    a = np.random.default_rng(0).random((36, 64, 3)).astype(np.float32)
    b = np.random.default_rng(1).random((36, 64, 3)).astype(np.float32)
    for d in TRANSITIONS.all():
        spec, p, dur = transition_spec(d.id, {})
        if spec.get("engine") == "numpy":
            out = spec["fn"](a, b, 0.5, p)
            assert out.shape == a.shape and np.isfinite(out).all()


def test_native_transitions_render():
    for tid in ("crossfade", "dip_to_black", "wipe_left", "circle_open", "slice_hl", "radial", "morph"):
        spec, _, dur = transition_spec(tid, {})
        run(["ffmpeg", "-v", "error", "-f", "lavfi", "-t", "1", "-i", "testsrc2=s=160x90:r=10", "-f", "lavfi", "-t", "1", "-i", "mandelbrot=s=160x90:r=10",
             "-filter_complex", f"[0:v][1:v]xfade=transition={spec['transition']}:duration=0.5:offset=0.3[o]", "-map", "[o]", "-f", "null", "-"])


def test_color_identity_and_luts(tmp_path):
    x = np.random.default_rng(0).random((500, 3)).astype(np.float32)
    assert np.allclose(grade(x, {}), x, atol=1e-4)
    warm = grade(x, {"temperature": 0.5})
    assert warm[:, 0].mean() > x[:, 0].mean() and warm[:, 2].mean() < x[:, 2].mean()
    for d in COLOR_PRESETS.all()[:6]:
        cube = write_cube(tmp_path / f"{d.id}.cube", preset_params(d.id), size=9)
        run(["ffmpeg", "-v", "error", "-f", "lavfi", "-t", "0.1", "-i", "testsrc2=s=64x36", "-vf", f"lut3d=file='{cube}'", "-f", "null", "-"])


def test_text_wraps_inside_safe_area():
    for w, h in ((1920, 1080), (1080, 1920)):
        b = AssBuilder(w, h)
        b.add(TextItem(id="t", text="An extremely long event title that would never fit on a single line of a vertical video", start=0, end=2, style="bold_impact"))
        assert not b.violations


def test_library_scale_and_search():
    st = library_stats()
    assert st["effects"]["parameter_configurations"] > 1000 and st["transitions"]["parameter_configurations"] > 1000
    assert {r["kind"] for r in search_library("cinematic transitions")} <= {"transitions", "templates"}
    assert any(r["id"] == "social_caption" for r in search_library("instagram captions"))
    assert len(REGISTRIES) == 7
