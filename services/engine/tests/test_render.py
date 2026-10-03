import subprocess
from pathlib import Path

from editor import service as S
from editor.qc.check import quality_check
from editor.schemas import EditPlan


def test_generate_render_qc_and_incremental_cache(project):
    v = S.create_edit_plan(project["id"], 'A 10-second energetic highlight titled "TEST", cut to the beat, subtle transitions, fade out.')
    r = S.render_version(project["id"], v["id"], preview=False)
    rep = r["report"]
    assert rep["qc"]["passed"], rep["qc"]["failures"]
    m = rep["qc"]["probe"]
    assert m["vcodec"] == "h264" and m["acodec"] == "aac" and m["sample_rate"] == 48000 and m["channels"] == 2
    assert abs(m["duration"] - 10) < 0.2 and (m["width"], m["height"]) == (1920, 1080)
    assert -17 < rep["audio"]["integrated_lufs"] < -13
    # colour revision → every segment reused from cache, only the final pass re-runs
    v2 = S.revise(project["id"], "Make the colors warmer.")
    r2 = S.render_version(project["id"], v2["id"], preview=True)
    r3 = S.render_version(project["id"], v2["id"], preview=True)
    assert r3["report"]["segments_cached"] == len(EditPlan.model_validate(v2["plan"]).timeline)
    assert r2["report"]["qc"]["passed"]


def test_qc_detects_black_frames(tmp_path, project):
    v = S.latest_version(project["id"])
    plan = EditPlan.model_validate(v["plan"])
    bad = tmp_path / "black.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r=30:d={plan.duration}", "-f", "lavfi",
                    "-i", f"sine=f=440:d={plan.duration}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(bad)], check=True)
    qc = quality_check(bad, plan, True, [])
    assert not qc["passed"] and "no_black_frames" in qc["failures"]
    qc2 = quality_check(tmp_path / "missing.mp4", plan, True, [])
    assert qc2["failures"] == ["file_exists"]


def test_delivered_true_peak_and_loudness_are_measured(tmp_path):
    """QC measures the delivered file (after AAC), not the pre-encode mix: a full-scale tone must read ≈ 0 dBTP."""
    import subprocess

    from editor.qc.check import delivered_loudness

    hot, soft = tmp_path / "hot.mp4", tmp_path / "soft.mp4"
    for f, vol in ((hot, "7.9"), (soft, "0.5")):  # lavfi sine is 1/8 full scale
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=320x240:d=4", "-f", "lavfi", "-i",
                        "sine=frequency=997:sample_rate=48000:duration=4", "-af", f"volume={vol}", "-c:v", "libx264", "-c:a", "aac", "-b:a", "320k",
                        "-shortest", str(f)], check=True)
    lh, th = delivered_loudness(hot)
    ls, ts = delivered_loudness(soft)
    assert th is not None and th > -1.0, th  # would fail the −1 dBTP ceiling
    assert ts is not None and ts < -15, ts
    assert lh is not None and ls is not None and lh - ls > 15
