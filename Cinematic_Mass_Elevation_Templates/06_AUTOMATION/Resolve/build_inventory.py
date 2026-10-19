#!/usr/bin/env python3
"""Build resolve_test_inventory.json: everything the in-Resolve harness needs per
template (paths, macro name, frames, phase frames, published input IDs, the text
inputs and test values), derived from the validated manifests and the actual
.setting files. Run from anywhere: python build_inventory.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "06_AUTOMATION", "Scripts"))
from cmet import luacheck  # noqa: E402


def main():
    tdir = os.path.join(ROOT, "01_TEMPLATES")
    out = []
    for d in sorted(os.listdir(tdir)):
        mp = os.path.join(tdir, d, "manifest.json")
        if not os.path.exists(mp):
            continue
        m = json.load(open(mp, encoding="utf-8"))
        sp = os.path.join(tdir, d, m["fusion_macro"])
        tree, _ = luacheck.parse(open(sp, encoding="utf-8").read())
        macro_name, macro = [(k, v) for k, v in tree["Tools"].items() if k != "__ctor"][0]
        ins = {k: v for k, v in macro["Inputs"].items() if k != "__ctor"}
        inner = {k: v for k, v in macro["Tools"].items() if k != "__ctor"}
        text_inputs = {k: v["SourceOp"] for k, v in ins.items() if v.get("Source") == "StyledText"}
        main_key = next((k for k in ("MainTitleText", "MainTitle3DText") if k in ins), None)
        sub_key = "SubtitleText" if "SubtitleText" in ins else None
        ctrl = {k: v["Source"] for k, v in ins.items() if v.get("SourceOp") == "CONTROLS"}
        probes = []
        seen = set()
        for tn, t in inner.items():
            if tn in seen or len(probes) >= 8:
                continue
            for inp, spec in (t.get("Inputs") or {}).items():
                if inp == "__ctor" or not isinstance(spec, dict):
                    continue
                ex = spec.get("Expression")
                if ex and "time" in ex and isinstance(spec.get("Value"), (int, float)):
                    probes.append({"tool": tn, "input": inp, "expression": ex})
                    seen.add(tn)
                    break
        ph = m["phases"]
        n = m["duration_frames"]
        out.append({
            "id": m["id"], "name": m["name"], "category": m["category"], "slug": m["slug"],
            "dir": f"01_TEMPLATES/{d}",
            "setting": f"01_TEMPLATES/{d}/{m['fusion_macro']}",
            "comp": f"01_TEMPLATES/{d}/{m['fusion_composition']}",
            "python_preview": f"01_TEMPLATES/{d}/{m['preview']}",
            "macro_name": macro_name,
            "output_tool": macro["Outputs"]["MainOutput1"]["SourceOp"],
            "inner_tool_count": len(inner),
            "duration_frames": n,
            "frames": {"build": max(1, ph["build_up"][1] // 2), "impact": ph["impact_frame"],
                       "impact_plus3": min(n - 1, ph["impact_frame"] + 3),
                       "hold": (ph["hero_hold"][0] + ph["hero_hold"][1]) // 2,
                       "exit_mid": (ph["exit"][0] + ph["exit"][1]) // 2, "end": n - 2},
            "published_inputs": {k: f"{v['SourceOp']}.{v['Source']}" for k, v in ins.items()},
            "control_inputs": ctrl,
            "expression_probes": probes,
            "main_title_input": main_key,
            "subtitle_input": sub_key,
            "text_inputs": text_inputs,
            "test_title": f"RESOLVE TEST {m['id']}",
            "true_3d": m["true_3d"],
            "fonts": m["font_dependencies"],
            "extra_parameters": list(m.get("extra_parameters", {}).keys()),
            "unconfirmed_inputs": m.get("unconfirmed_fusion_inputs", []),
        })
    inv = {"version": 1, "fps": 24, "width": 1920, "height": 1080, "templates": out}
    p = os.path.join(HERE, "resolve_test_inventory.json")
    json.dump(inv, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(out)} templates -> {os.path.relpath(p, ROOT)}")
    missing = [t["id"] for t in out if not t["main_title_input"]]
    if missing:
        print("WARNING: no main title input published for", missing)


if __name__ == "__main__":
    main()
