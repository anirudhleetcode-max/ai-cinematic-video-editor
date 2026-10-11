#!/usr/bin/env python3
"""Full acceptance test suite for the 40-template collection.

Run after `build.py validate`, `qa.py` and `catalog.py`:
    python run_tests.py            -> 06_AUTOMATION/Validation/test_results.{json,md}; exit 1 on any failure

Checks per template: identity (ID/name/category vs. the brief), Fusion source structure (re-run), manifest
completeness, preview playable (full decode), 1920x1080, exact frame count/duration, audio stream, motion,
no unexpected black middle section, exposure, entrance/hold/exit behaviour, documentation of every
published control and template-specific parameter, template-specific parameters actually change output.
Collection checks: 40 unique templates, catalog/contact sheet/strips complete without duplicates, no
machine-specific paths, no leftover temp/partial files, no running build processes.
"""
from __future__ import annotations

import datetime
import importlib
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cmet import validate as V  # noqa: E402
from cmet.base import Ctx  # noqa: E402
from cmet.export import ROOT, TPL  # noqa: E402

EXPECTED = {
    1: ("Obsidian Impact", "A"), 2: ("Thunder God", "A"), 3: ("Molten Core", "A"), 4: ("Black Steel Reckoning", "A"),
    5: ("Shattered Monolith", "A"), 6: ("Inferno Reveal", "B"), 7: ("Explosive Arrival", "B"),
    8: ("Ember Storm", "B"), 9: ("Ashes of Power", "B"), 10: ("Shockwave Dominance", "B"),
    11: ("Golden Emperor", "C"), 12: ("Chrome Dominion", "C"), 13: ("Titanium Edge", "C"),
    14: ("Forged in Fire", "C"), 15: ("Diamond Cut", "C"), 16: ("Ancient Titan", "D"),
    17: ("Celestial Ascent", "D"), 18: ("Dark Sorcery", "D"), 19: ("Cosmic Overlord", "D"),
    20: ("Phoenix Reborn", "D"), 21: ("Neon Overdrive", "E"), 22: ("Hologram Breach", "E"),
    23: ("Digital Awakening", "E"), 24: ("Quantum Split", "E"), 25: ("Future Warlord", "E"),
    26: ("Extreme Close-Up", "F"), 27: ("Low-Angle Titan", "F"), 28: ("Rotating Monolith", "F"),
    29: ("Cinematic Letter Assembly", "F"), 30: ("Speed Ramp Dominance", "F"), 31: ("Midnight Fog", "G"),
    32: ("Rain and Steel", "G"), 33: ("Desert Storm", "G"), 34: ("Underwater Colossus", "G"),
    35: ("Frozen Kingdom", "G"), 36: ("Hero Silhouette", "H"), 37: ("Legacy Reveal", "H"),
    38: ("Royal Insignia", "H"), 39: ("Final Boss", "H"), 40: ("Ultimate Mass Elevation", "H"),
}
REQUIRED_MANIFEST = ["id", "name", "category", "version", "aspect_ratio", "default_resolution", "frame_rate",
                     "duration_seconds", "duration_frames", "editable_text", "editable_colors", "editable_timing",
                     "true_3d", "uses_2_5d", "external_plugins_required", "external_assets_required",
                     "fusion_macro", "fusion_composition", "preview", "thumbnail", "readme", "render_profile",
                     "verification", "design", "fusion_published_controls", "sound_cues"]


def grab(path, t, W=320, H=180):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-s", f"{W}x{H}", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W).astype(np.float32) if len(raw) == W * H else None


def test_template(i):
    res = {"id": f"T{i:02d}", "checks": {}, "errors": []}

    def check(name, ok, detail=""):
        res["checks"][name] = bool(ok)
        if not ok:
            res["errors"].append(f"{name}: {detail}".strip(": "))

    mod = f"cmet.designs.t{i:02d}"
    try:
        d = importlib.import_module(mod).DESIGN
    except Exception as e:  # noqa: BLE001
        check("design_module", False, repr(e))
        return res
    name, cat = EXPECTED[i]
    check("identity", d.ID == f"T{i:02d}" and d.NAME == name and d.CATEGORY.startswith(cat + " "),
          f"{d.ID}/{d.NAME}/{d.CATEGORY}")
    tdir = os.path.join(TPL, f"{d.ID}_{d.SLUG}")
    mp = os.path.join(tdir, "manifest.json")
    if not os.path.exists(mp):
        check("manifest", False, "missing")
        return res
    m = json.load(open(mp, encoding="utf-8"))
    missing = [k for k in REQUIRED_MANIFEST if k not in m or m[k] is None]
    check("manifest_complete", not missing, f"missing {missing}")
    check("manifest_identity", m.get("id") == d.ID and m.get("name") == d.NAME and m.get("category") == d.CATEGORY)
    p = d.params()
    check("manifest_duration", m.get("duration_frames") == p["DURATION"] and 144 <= p["DURATION"] <= 240,
          str(m.get("duration_frames")))
    # sources ----------------------------------------------------------
    src = V.check_source(os.path.join(tdir, m["fusion_macro"]), os.path.join(tdir, m["fusion_composition"]))
    check("fusion_structure", src["ok"], "; ".join(src["errors"][:3]))
    check("fusion_no_risky_expr", not src["warnings"], "; ".join(src["warnings"][:3]))
    if d.TRUE_3D:
        types = set(m.get("fusion_tool_types", []))
        check("true_3d_nodes", {"Text3D", "Renderer3D", "Camera3D"} <= types, str(types))
    for f in ("Fusion_Macros", "Fusion_Compositions"):
        ext = ".setting" if f == "Fusion_Macros" else ".comp"
        cp = os.path.join(ROOT, "05_RESOLVE_IMPORT", f, f"{d.ID}_{d.SLUG}{ext}")
        same = os.path.exists(cp) and open(cp, "rb").read() == open(
            os.path.join(tdir, m["fusion_macro" if ext == ".setting" else "fusion_composition"]), "rb").read()
        check(f"resolve_import_copy_{ext[1:]}", same, "missing or differs from template source")
    # preview ------------------------------------------------------------
    pv = os.path.join(tdir, m["preview"]) if m.get("preview") else None
    if not pv or not os.path.exists(pv):
        check("preview_exists", False)
        return res
    check("preview_exists", True)
    full = subprocess.run(["ffmpeg", "-v", "error", "-i", pv, "-f", "null", "-"], capture_output=True, text=True)
    check("preview_decodes_cleanly", full.returncode == 0 and not full.stderr.strip(), full.stderr[:200])
    pr = V.ffprobe(pv)
    vs = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
    aus = [s for s in pr["streams"] if s["codec_type"] == "audio"]
    check("preview_1080p", (vs["width"], vs["height"]) == (1920, 1080), f"{vs['width']}x{vs['height']}")
    nb = int(vs.get("nb_frames", 0))
    check("preview_frame_count", nb == p["DURATION"], f"{nb} vs {p['DURATION']}")
    check("preview_audio", bool(aus) and float(aus[0].get("duration", 0)) > p["DURATION"] / 24 - 0.3)
    fps = 24
    ph = m["phases"]
    frames = {"start": 1, "build": max(1, ph["build_up"][1] // 2), "impact": ph["impact_frame"],
              "hold": (ph["hero_hold"][0] + ph["hero_hold"][1]) // 2, "exit_mid": (ph["exit"][0] + ph["exit"][1]) // 2,
              "end": p["DURATION"] - 2}
    imgs = {k: grab(pv, f / fps) for k, f in frames.items()}
    check("preview_frames_readable", all(v is not None for v in imgs.values()))
    if all(v is not None for v in imgs.values()):
        mid = [grab(pv, t) for t in np.linspace(p["DURATION"] * 0.3 / fps, p["DURATION"] * 0.7 / fps, 6)]
        check("no_black_middle", min(float(x.mean()) for x in mid) > 3.0,
              f"min mean {min(float(x.mean()) for x in mid):.1f}")
        hold = imgs["hold"]
        check("hold_readable_contrast", hold.std() >= 8, f"std {hold.std():.1f}")
        check("hold_not_blown", float((hold > 250).mean()) < 0.06, f"{(hold > 250).mean():.3f}")
        d_entr = float(np.abs(imgs["start"] - hold).mean())
        d_exit = float(np.abs(imgs["end"] - hold).mean())
        check("entrance_visible", d_entr > 2.0, f"start-vs-hold diff {d_entr:.2f}")
        check("exit_visible", d_exit > 2.0, f"end-vs-hold diff {d_exit:.2f}")
        diffs = [float(np.abs(mid[j + 1] - mid[j]).mean()) for j in range(len(mid) - 1)]
        check("animation_changes", d_entr + d_exit + sum(diffs) > 6.0)
    # docs ----------------------------------------------------------------
    pm = open(os.path.join(tdir, "documentation", "parameters.md"), encoding="utf-8").read()
    undocumented = [c for c in dict.fromkeys(m["fusion_published_controls"]) if f"| {c} |" not in pm]
    check("controls_documented", not undocumented, f"{undocumented[:4]}")
    dp = json.load(open(os.path.join(tdir, "configuration", "default_params.json"), encoding="utf-8"))
    check("extra_params_documented", all(k in dp for k in d.EXTRA_PARAMS), str(list(d.EXTRA_PARAMS)))
    rd = open(os.path.join(tdir, "README.md"), encoding="utf-8").read()
    check("readme_text_and_status", "Change the title text" in rd and "D. Renders in DaVinci Resolve" in rd)
    check("sound_sheet", os.path.getsize(os.path.join(tdir, "documentation", "sound_design.md")) > 200)
    check("thumbnail", os.path.exists(os.path.join(tdir, "preview", "thumbnail.jpg")))
    # template-specific parameters actually change the output ----------------
    if d.EXTRA_PARAMS:
        # an effect may live only in part of the timeline (e.g. pre-lock flicker), so scan it
        changed = []
        for k, (dflt, _, kind) in d.EXTRA_PARAMS.items():
            alt = (dflt * 2 + 6) if kind == "frame" else (0.0 if dflt else 0.6) if kind == "float" else dflt
            if k.endswith("ROTATION"):
                alt = 35.0
            hit = False
            for fr in range(0, p["DURATION"], 6):
                frs = []
                for val in (dflt, alt):
                    c = Ctx(d, d.params({k: val}), 320, 180)
                    c.fr, c.t = fr, fr / 24
                    frs.append(d.frame(c))
                if float(np.abs(frs[0] - frs[1]).mean()) > 1e-3:
                    hit = True
                    break
            changed.append((k, hit))
        check("extra_params_functional", all(v for _, v in changed), str(changed))
    return res


def collection_checks(results):
    out = {}
    html = open(os.path.join(ROOT, "TEMPLATE_CATALOG.html"), encoding="utf-8").read()
    ids_html = re.findall(r'<span class="id">(T\d\d)</span>', html)
    out["catalog_html_40_unique"] = (sorted(ids_html) == [f"T{i:02d}" for i in range(1, 41)], f"{len(ids_html)} cards")
    links = re.findall(r'(?:href|src|data-video)="([^"#]+)"', html)
    broken = [l for l in links if not l.startswith(("http", "data:")) and l and not os.path.exists(os.path.join(ROOT, l))]
    out["catalog_links_resolve"] = (not broken, f"{len(broken)} broken: {broken[:3]}")
    md = open(os.path.join(ROOT, "TEMPLATE_CATALOG.md"), encoding="utf-8").read()
    ids_md = re.findall(r"^\| (T\d\d) \|", md, re.M)
    out["catalog_md_40_unique"] = (sorted(ids_md) == [f"T{i:02d}" for i in range(1, 41)], f"{len(ids_md)} rows")
    strips = os.listdir(os.path.join(ROOT, "03_PREVIEWS", "Contact_Sheets", "per_template"))
    out["strips_40"] = (len([s for s in strips if s.endswith("_strip.jpg")]) == 40, f"{len(strips)} strips")
    out["contact_sheet"] = (os.path.exists(os.path.join(ROOT, "03_PREVIEWS", "Contact_Sheets", "contact_sheet_all.jpg"))
                            and os.path.exists(os.path.join(ROOT, "03_PREVIEWS", "Contact_Sheets",
                                                            "contact_sheet_strips.jpg")), "")
    out["thumbnails_40"] = (len(os.listdir(os.path.join(ROOT, "03_PREVIEWS", "Thumbnails"))) == 40, "")
    out["resolve_import_40"] = (len(os.listdir(os.path.join(ROOT, "05_RESOLVE_IMPORT", "Fusion_Macros"))) == 40 and
                                len(os.listdir(os.path.join(ROOT, "05_RESOLVE_IMPORT", "Fusion_Compositions"))) == 40, "")
    pm = json.load(open(os.path.join(ROOT, "00_PROJECT_FILES", "Project_Manifest.json"), encoding="utf-8"))
    out["project_manifest_40"] = (pm["template_count"] == 40 and len({t["id"] for t in pm["templates"]}) == 40, "")
    priv = V.scan_private_paths()
    out["no_private_paths"] = (not priv, str(priv[:3]))
    leftovers = [os.path.join(dp, f) for dp, dn, fn in os.walk(ROOT) for f in fn
                 if f.endswith((".part", ".tmp")) or "/_tmp" in dp]
    out["no_partial_files"] = (not leftovers, str(leftovers[:3]))
    ps = subprocess.run(["pgrep", "-af", "python3 build.py (previews|validate)"], capture_output=True, text=True).stdout
    ps = [l for l in ps.splitlines() if "pgrep" not in l]
    out["no_running_builds"] = (not ps, str(ps[:2]))
    rc_p = os.path.join(ROOT, "06_AUTOMATION", "Validation", "resolve_test_results.json")
    if os.path.exists(rc_p):
        rc = json.load(open(rc_p, encoding="utf-8"))["templates"]
        mism = []
        for d in sorted(os.listdir(TPL)):
            mf = os.path.join(TPL, d, "manifest.json")
            if not os.path.exists(mf):
                continue
            mm = json.load(open(mf, encoding="utf-8"))
            claimed = (mm["verification"].get("resolve") or {}).get("status")
            actual = rc.get(mm["id"], {}).get("status", "NOT TESTED")
            if claimed != actual:
                mism.append(f"{mm['id']}: manifest {claimed} vs results {actual}")
            if actual == "PASS":
                ev = rc[mm["id"]]["levels"].get("D_render", {}).get("output")
                if not ev or not os.path.exists(os.path.join(ROOT, ev)):
                    mism.append(f"{mm['id']}: PASS without render evidence on disk")
        out["resolve_results_40"] = (len(rc) == 40, f"{len(rc)} entries")
        out["resolve_claims_match_evidence"] = (not mism, "; ".join(mism[:4]))
    else:
        out["resolve_results_40"] = (False, "resolve_test_results.json missing")
    out["no_fake_drp"] = (not any(f.endswith(".drp") for dp, dn, fn in os.walk(ROOT) for f in fn), "")
    return {k: {"ok": bool(v[0]), "detail": v[1]} for k, v in out.items()}


def main():
    results = [test_template(i) for i in range(1, 41)]
    coll = collection_checks(results)
    n_ok = sum(1 for r in results if not r["errors"])
    c_ok = all(v["ok"] for v in coll.values())
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    vd = os.path.join(ROOT, "06_AUTOMATION", "Validation")
    json.dump({"run_at": stamp, "templates": results, "collection": coll}, open(os.path.join(vd, "test_results.json"), "w"),
              indent=1)
    names = sorted({k for r in results for k in r["checks"]})
    L = [f"# Test results ({stamp})", "", f"Templates passing every check: **{n_ok}/40**. Collection checks: "
         f"**{'PASS' if c_ok else 'FAIL'}**.", "", "## Collection", "", "| Check | Result | Detail |", "|---|---|---|"]
    L += [f"| {k} | {'PASS' if v['ok'] else 'FAIL'} | {v['detail']} |" for k, v in coll.items()]
    L += ["", "## Per template", "", "| ID | Checks passed | Failures |", "|---|---|---|"]
    for r in results:
        L.append(f"| {r['id']} | {sum(r['checks'].values())}/{len(r['checks'])} | {'; '.join(r['errors']) or '-'} |")
    L += ["", "Checks run per template: " + ", ".join(names), ""]
    open(os.path.join(vd, "test_results.md"), "w").write("\n".join(L))
    for r in results:
        if r["errors"]:
            print(r["id"], r["errors"])
    for k, v in coll.items():
        if not v["ok"]:
            print("COLLECTION", k, v["detail"])
    print(f"templates passing: {n_ok}/40; collection: {'PASS' if c_ok else 'FAIL'}")
    sys.exit(0 if n_ok == 40 and c_ok else 1)


if __name__ == "__main__":
    main()
