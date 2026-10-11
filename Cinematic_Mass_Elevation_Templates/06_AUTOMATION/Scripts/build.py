#!/usr/bin/env python3
"""CMET build pipeline.

  python build.py sources  [T01 T02 ...]   write Fusion .setting/.comp + docs
  python build.py previews [T01 ...] [--jobs 4]   render 1080p previews + thumbnails
  python build.py validate [T01 ...]        validate and (re)write manifest.json files
  python build.py catalog                   contact sheet + HTML/Markdown catalog
  python build.py all [--jobs 4]            everything

Templates that have no design module yet are skipped and reported.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime
import importlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from cmet import export as X  # noqa: E402
from cmet import validate as V  # noqa: E402
from cmet.base import FPS  # noqa: E402

ROOT = X.ROOT
TMP = os.path.join(ROOT, "06_AUTOMATION", "Validation", "_tmp")
STATE = os.path.join(ROOT, "06_AUTOMATION", "Validation", "build_state.json")


def design_ids():
    out = []
    for i in range(1, 41):
        mod = f"t{i:02d}"
        if os.path.exists(os.path.join(HERE, "cmet", "designs", f"{mod}.py")):
            out.append(f"T{i:02d}")
    return out


def load(tid):
    return importlib.import_module(f"cmet.designs.t{int(tid[1:]):02d}").DESIGN


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=1, sort_keys=True)


RESOLVE_CANON = os.path.join(ROOT, "06_AUTOMATION", "Validation", "resolve_test_results.json")


def _resolve_canon():
    if os.path.exists(RESOLVE_CANON):
        return json.load(open(RESOLVE_CANON, encoding="utf-8")).get("templates", {})
    return {}


def resolve_levels(tid):
    r = _resolve_canon().get(tid)
    if not r:
        return {"status": "NOT TESTED", "C_load": "NOT TESTED", "D_render": "NOT TESTED", "E_edit": "NOT TESTED",
                "F_visual": "NOT TESTED", "run_id": None}
    lv = r.get("levels", {})
    return {"status": r.get("status"), "run_id": r.get("run_id"),
            **{k: lv.get(k, {}).get("status", "NOT TESTED") for k in ("C_load", "D_render", "E_edit", "F_visual")},
            "detail": (lv.get("C_load", {}).get("detail") or "")[:200]}


def resolve_summary(tid):
    r = resolve_levels(tid)
    if r["status"] == "BLOCKED":
        return ("BLOCKED - not tested in DaVinci Resolve: no Resolve connection in the environment of run %s "
                "(see 06_AUTOMATION/Validation/resolve_test_results.json)" % r["run_id"])
    if r["status"] in ("PASS", "FAIL"):
        return "%s in DaVinci Resolve (run %s): load %s, render %s, edit %s" % (r["status"], r["run_id"], r["C_load"],
                                                                                 r["D_render"], r["E_edit"])
    return "NOT TESTED in DaVinci Resolve"


def cmd_sources(ids):
    res = {}
    for tid in ids:
        d = load(tid)
        info = X.build_sources(d)
        X.write_docs(d, info)
        # copies for the Resolve import folder
        name = f"{d.ID}_{d.SLUG}"
        shutil.copy(info["setting"], os.path.join(ROOT, "05_RESOLVE_IMPORT", "Fusion_Macros", f"{name}.setting"))
        shutil.copy(info["comp"], os.path.join(ROOT, "05_RESOLVE_IMPORT", "Fusion_Compositions", f"{name}.comp"))
        res[tid] = {"tools": info["tool_count"], "controls": len(info["controls"]), "published": len(info["published"])}
        print(f"{tid} sources: {info['tool_count']} tools, {len(info['published'])} published controls")
    return res


def _render_one(tid):
    import cv2
    cv2.setNumThreads(1)
    d = load(tid)
    t0 = time.time()
    out, st = X.render_preview(d, TMP)
    return tid, {"path": os.path.relpath(out, ROOT), "seconds": round(time.time() - t0, 1), "rc": st["rc"],
                 "params_read": st["params_read"], "thumb_frame": st["thumb_frame"],
                 "rendered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}


def cmd_previews(ids, jobs):
    state = load_state()
    with cf.ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(_render_one, t): t for t in ids}
        for f in cf.as_completed(futs):
            tid = futs[f]
            try:
                tid, info = f.result()
                state.setdefault(tid, {})["preview"] = info
                print(f"{tid} preview rendered in {info['seconds']}s rc={info['rc']}", flush=True)
            except Exception as e:  # keep going on failure
                state.setdefault(tid, {})["preview"] = {"error": repr(e)}
                print(f"{tid} preview FAILED: {e!r}", flush=True)
            save_state(state)
    shutil.rmtree(TMP, ignore_errors=True)


def cmd_validate(ids):
    state = load_state()
    summary = {}
    for tid in ids:
        d = load(tid)
        p = d.params()
        name = f"{d.ID}_{d.SLUG}"
        base = X.tdir(d)
        src = V.check_source(os.path.join(base, "source", f"{name}.setting"),
                             os.path.join(base, "source", f"{name}.comp"))
        pv_path = os.path.join(base, "preview", f"{name}.mp4")
        pst = state.get(tid, {}).get("preview", {})
        hero = pst.get("thumb_frame", p["IMPACT_FRAME"] + 30)
        if os.path.exists(pv_path):
            prv = V.check_preview(pv_path, p["DURATION"], hero_frame=hero)
        else:
            prv = {"ok": False, "errors": ["not rendered"], "warnings": []}
        thumb = os.path.join(base, "preview", "thumbnail.jpg")
        g = d.build_graph(p)
        manifest = {
            "id": d.ID, "name": d.NAME, "slug": d.SLUG, "category": d.CATEGORY, "version": X.VERSION,
            "concept": d.CONCEPT,
            "aspect_ratio": "16:9", "default_resolution": "3840x2160", "preview_resolution": "1920x1080",
            "frame_rate": FPS, "duration_frames": p["DURATION"], "duration_seconds": round(p["DURATION"] / FPS, 3),
            "phases": {"build_up": [0, p["ANIMATION_START"] + p["ANIMATION_DURATION"]],
                       "impact_frame": p["IMPACT_FRAME"],
                       "hero_hold": [p["IMPACT_FRAME"], p["EXIT_START"]],
                       "exit": [p["EXIT_START"], p["EXIT_START"] + p["EXIT_DURATION"]]},
            "editable_text": True, "editable_colors": True, "editable_timing": True,
            "true_3d": bool(d.TRUE_3D), "uses_2_5d": not d.TRUE_3D,
            "depth_note": ("Fusion source uses Text3D/Renderer3D geometry; the preview approximates the extruded "
                           "solid with perspective-projected slices." if d.TRUE_3D else
                           "2.5D layered compositing (no 3D geometry)."),
            "external_plugins_required": False,
            "external_assets_required": False,
            "font_dependencies": sorted({X.FONTS.get(p["FONT_FAMILY"], X.FONTS["anton"])[2],
                                         X.FONTS.get(p["SUB_FONT_FAMILY"], X.FONTS["teko"])[2]}),
            "font_note": "OFL fonts bundled in 02_SHARED_ASSETS/Fonts; install them or choose any installed font.",
            "fusion_macro": f"source/{name}.setting",
            "fusion_composition": f"source/{name}.comp",
            "fusion_output_tool": g.output.name,
            "fusion_tool_count": len(g.tools),
            "fusion_tool_types": sorted({t.tid for t in g.tools.values()}),
            "fusion_controls": g.control_names(),
            "fusion_published_controls": [x.name for x in g.published],
            "preview": f"preview/{name}.mp4" if os.path.exists(pv_path) else None,
            "thumbnail": "preview/thumbnail.jpg" if os.path.exists(thumb) else None,
            "readme": "README.md",
            "parameters": "documentation/parameters.md",
            "sound_design": "documentation/sound_design.md",
            "render_profile": "configuration/render_profile.json",
            "default_params": "configuration/default_params.json",
            "sound_cues": [{"frame": f, "seconds": round(f / FPS, 3), "cue": k, "note": n} for f, k, n in d.SOUND],
            "techniques": d.TECHNIQUES,
            "design": {"entrance": d.ENTRANCE, "reveal": d.REVEAL, "camera": d.CAMERA, "material": d.MATERIAL,
                       "exit": d.EXIT},
            "fusion_notes": list(d.FUSION_NOTES),
            "extra_parameters": {k: {"default": v[0], "description": v[1]} for k, v in d.EXTRA_PARAMS.items()},
            "unconfirmed_fusion_inputs": src.get("unconfirmed_inputs", []),
            "reference_renderer": {"module": f"06_AUTOMATION/Scripts/cmet/designs/t{int(d.ID[1:]):02d}.py",
                                   "parameters_used": pst.get("params_read", [])},
            "verification": {
                "lua_parse": "PASS" if not any("parse" in e for e in src["errors"]) else "FAIL",
                "structure": "PASS" if src["ok"] else "FAIL: " + "; ".join(src["errors"][:5]),
                "source_details": {k: v for k, v in src.items() if k not in ("ok",)},
                "preview": "PASS" if prv.get("ok") else "FAIL: " + "; ".join(prv.get("errors", [])[:5]),
                "preview_details": {k: v for k, v in prv.items() if k != "ok"},
                "resolve_tested": resolve_summary(tid),
                "resolve": resolve_levels(tid),
                "validated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            },
        }
        json.dump(manifest, open(os.path.join(base, "manifest.json"), "w"), indent=2, ensure_ascii=False)
        json.load(open(os.path.join(base, "manifest.json")))  # round-trip check
        open(os.path.join(base, "README.md"), "w").write(X.readme(d, {"tool_count": len(g.tools), "graph": g},
                                                                  manifest))
        summary[tid] = {"source": src["ok"], "preview": prv.get("ok", False),
                        "errors": src["errors"] + prv.get("errors", []),
                        "warnings": src.get("warnings", []) + prv.get("warnings", [])}
        flag = "OK " if src["ok"] and prv.get("ok") else "ERR"
        print(f"{flag} {tid} source={'PASS' if src['ok'] else 'FAIL'} preview={'PASS' if prv.get('ok') else 'FAIL'}"
              f" {summary[tid]['errors'][:3]} {summary[tid]['warnings'][:2]}")
    state = load_state()
    state["_validation"] = {**state.get("_validation", {}), **summary}
    save_state(state)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sources", "previews", "validate", "catalog", "all"])
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    avail = design_ids()
    ids = [i.upper() for i in a.ids] or avail
    missing = [i for i in ids if i not in avail]
    if missing:
        print("no design module yet for:", missing)
    ids = [i for i in ids if i in avail]
    if a.cmd in ("sources", "all"):
        cmd_sources(ids)
    if a.cmd in ("previews", "all"):
        cmd_previews(ids, a.jobs)
    if a.cmd in ("validate", "all"):
        cmd_validate(ids)
    if a.cmd in ("catalog", "all"):
        import catalog
        catalog.main()


if __name__ == "__main__":
    main()
