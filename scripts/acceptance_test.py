"""Final acceptance test (spec §76): 50 clips + 3 songs + 1 reference → plan → preview → render → QC → valid MP4,
then the three revisions, each verified to modify the existing plan (not rebuild from scratch).

Usage: python scripts/acceptance_test.py [--clips 50] [--out docs/acceptance_report.json]
All media is synthetic (no copyrighted material). Every number in the report is measured."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine"))

PROMPT = ("Create a 60-second professional cinematic event highlight. Analyze the reference and follow its pacing, color mood, typography "
          "philosophy, and transition style without copying its footage. Select the best clips, remove poor-quality shots, begin with a strong "
          "hook, synchronize cuts to the supplied music, use slower emotional shots where appropriate, build energy toward the climax, add "
          "tasteful motion and transitions, apply consistent professional color grading, add elegant event typography, duck music under "
          "speech, and finish with a strong branded ending.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=int, default=50)
    ap.add_argument("--out", default=str(ROOT / "docs" / "acceptance_report.json"))
    ap.add_argument("--data", default=None, help="data dir (default: temp)")
    args = ap.parse_args()
    work = Path(args.data or tempfile.mkdtemp(prefix="acceptance-"))
    os.environ.setdefault("EDITOR_DATA_DIR", str(work / "data"))
    from editor import service as S, testmedia
    from editor.hw import diagnostics
    from editor.schemas import EditPlan

    rep: dict = {"prompt": PROMPT, "environment": {k: v for k, v in diagnostics().items() if k not in ("cpu_percent",)}, "steps": []}
    t_all = time.perf_counter()

    def step(name, **kw):
        rep["steps"].append({"step": name, **kw})
        print(f"[{time.perf_counter() - t_all:7.1f}s] {name}: {json.dumps(kw, default=str)[:300]}", flush=True)

    t = time.perf_counter()
    ds = testmedia.make_dataset(work / "media", n_clips=args.clips, n_songs=3, with_reference=True, clip_seconds=(3.0, 8.0), w=1280, h=720, seed=11)
    step("generate_synthetic_media", seconds=round(time.perf_counter() - t, 1), clips=len(ds["clips"]), songs=len(ds["songs"]), note="DEMO data (synthetic)")

    p = S.create_project("Acceptance Event 2026")
    t = time.perf_counter()
    for c in ds["clips"]:
        with open(c, "rb") as fh:
            S.add_asset(p["id"], c.name, fh)
    for s_ in ds["songs"]:
        with open(s_, "rb") as fh:
            S.add_asset(p["id"], s_.name, fh, "music")
    with open(ds["reference"], "rb") as fh:
        S.add_asset(p["id"], "reference.mp4", fh, "reference")
    with open(ds["logo"], "rb") as fh:
        S.add_asset(p["id"], "logo.png", fh, "logo")
    step("upload", seconds=round(time.perf_counter() - t, 1), assets=len(S.list_assets(p["id"])))

    t = time.perf_counter()
    an = S.analyze_project(p["id"], "fast")
    step("analyze", seconds=round(time.perf_counter() - t, 1), shots=an["shots"], usable=an["usable_shots"], rejected=an["rejected"], duplicates=an["duplicate_groups"])
    ref = S.get_project(p["id"])["settings"]["reference_profile"]
    step("reference_analysis", median_shot=ref["median_shot_duration"], cuts_per_minute=ref["cuts_per_minute"], transition_frequency=ref["transition_frequency"],
         bpm=(ref.get("music") or {}).get("bpm"))

    t = time.perf_counter()
    v1 = S.create_edit_plan(p["id"], PROMPT, "fast")
    plan1 = EditPlan.model_validate(v1["plan"])
    step("edit_plan", seconds=round(time.perf_counter() - t, 2), segments=len(plan1.timeline), duration=plan1.duration, sections=[s.name for s in plan1.story_structure],
         ending=plan1.ending.type, reference_used=plan1.reference_profile_used, transitions=sum(1 for s in plan1.timeline if s.transition_in.id != "cut"),
         music=[(m.asset_id, round(m.out_start, 1), round(m.out_end, 1)) for m in plan1.music], color=plan1.color_grade.preset)
    rejected_used = []
    assets = {a["id"]: a for a in __import__("editor.db", fromlist=["query"]).query("SELECT id, analysis FROM assets WHERE project_id=?", (p["id"],))}
    for s_ in plan1.timeline:
        sh = next(x for x in assets[s_.asset_id]["analysis"]["shots"] if x["index"] == s_.shot_index)
        if set(sh["issues"]) & {"blurry", "black", "duplicate", "shaky", "underexposed", "overexposed", "frozen"}:
            rejected_used.append((s_.asset_id, sh["issues"]))
    step("clip_selection_check", poor_quality_shots_used=len(rejected_used))

    t = time.perf_counter()
    pv = S.render_version(p["id"], v1["id"], preview=True)
    step("preview", seconds=round(time.perf_counter() - t, 1), qc=pv["report"]["qc"]["passed"], size=pv["report"]["size_bytes"])
    t = time.perf_counter()
    f1 = S.render_version(p["id"], v1["id"], preview=False)
    q = f1["report"]["qc"]
    step("final_render", seconds=round(time.perf_counter() - t, 1), qc_passed=q["passed"], failures=q["failures"], warnings=q.get("warnings"),
         duration=q["probe"]["duration"], resolution=f"{q['probe']['width']}x{q['probe']['height']}", vcodec=q["probe"]["vcodec"], acodec=q["probe"].get("acodec"),
         lufs=f1["report"]["audio"].get("integrated_lufs"), true_peak=f1["report"]["audio"].get("true_peak_db"), encoder=f1["report"].get("encoder"),
         timings=f1["report"]["timings"], path=f1["path"])

    # ---- revisions
    t = time.perf_counter()
    v2 = S.revise(p["id"], "Make it more energetic and reduce the intro to 3 seconds.")
    plan2 = EditPlan.model_validate(v2["plan"])
    intro = next(s for s in plan2.story_structure if s.name in ("opening", "intro"))
    kept = sum(1 for a, b in zip(plan1.timeline, plan2.timeline) if (a.asset_id, a.shot_index) == (b.asset_id, b.shot_index))
    r2 = S.render_version(p["id"], v2["id"])
    step("revision_1_energetic_intro3", seconds=round(time.perf_counter() - t, 1), ops=[c["op"] for c in v2["changes"]], segments_before=len(plan1.timeline),
         segments_after=len(plan2.timeline), intro_seconds=round(intro.end - intro.start, 3), picks_kept=kept, qc=r2["report"]["qc"]["passed"],
         segments_cached=r2["report"]["segments_cached"])

    t = time.perf_counter()
    v3 = S.revise(p["id"], "Make the colors warmer.")
    plan3 = EditPlan.model_validate(v3["plan"])
    same_tl = [x.model_dump() for x in plan3.timeline] == [x.model_dump() for x in plan2.timeline]
    r3 = S.render_version(p["id"], v3["id"])
    step("revision_2_warmer", seconds=round(time.perf_counter() - t, 1), ops=[c["op"] for c in v3["changes"]], timeline_unchanged=same_tl,
         temperature_before=plan2.color_grade.overrides.get("temperature", 0), temperature_after=plan3.color_grade.overrides.get("temperature"),
         segments_cached=r3["report"]["segments_cached"], of=len(plan3.timeline), qc=r3["report"]["qc"]["passed"])

    t = time.perf_counter()
    v4 = S.revise(p["id"], "Use song 2 for the final section.")
    plan4 = EditPlan.model_validate(v4["plan"])
    songs = [a for a in S.build_context(p["id"], "").songs]
    final_song = plan4.music[-1].asset_id
    r4 = S.render_version(p["id"], v4["id"])
    step("revision_3_song2_final", seconds=round(time.perf_counter() - t, 1), ops=[c["op"] for c in v4["changes"]],
         music_plan=[(next(a.filename for a in songs if a.id == m.asset_id), round(m.out_start, 1), round(m.out_end, 1)) for m in plan4.music],
         final_section_song=next(a.filename for a in songs if a.id == final_song), color_kept=plan4.color_grade.overrides.get("temperature") == plan3.color_grade.overrides.get("temperature"),
         qc=r4["report"]["qc"]["passed"])

    checks = {
        "valid_mp4_with_qc": q["passed"],
        "duration_60s": abs(q["probe"]["duration"] - 60) < 0.3,
        "1080p": (q["probe"]["width"], q["probe"]["height"]) == (1920, 1080),
        "no_poor_quality_shots": not rejected_used,
        "reference_used": plan1.reference_profile_used,
        "branded_ending": plan1.ending.type in ("logo", "logo_title") and bool(plan1.ending.logo_asset_id),
        "rev1_more_shots": len(plan2.timeline) > len(plan1.timeline),
        "rev1_intro_3s": abs((intro.end - intro.start) - 3.0) < 0.01,
        "rev1_keeps_picks": kept >= 0.5 * len(plan1.timeline),
        "rev2_color_only": same_tl and (plan3.color_grade.overrides.get("temperature", 0) > plan2.color_grade.overrides.get("temperature", 0)),
        "rev2_incremental_render": r3["report"]["segments_cached"] == len(plan3.timeline),
        "rev3_song2_in_final": final_song == songs[1].id,
        "rev3_keeps_color": plan4.color_grade.overrides.get("temperature") == plan3.color_grade.overrides.get("temperature"),
        "all_renders_qc": all(x["report"]["qc"]["passed"] for x in (pv, f1, r2, r3, r4)),
    }
    rep["checks"] = checks
    rep["passed"] = all(checks.values())
    rep["total_seconds"] = round(time.perf_counter() - t_all, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rep, indent=2, default=str))
    print(json.dumps(checks, indent=1))
    print("ACCEPTANCE", "PASS" if rep["passed"] else "FAIL", f"in {rep['total_seconds']}s →", args.out)
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
