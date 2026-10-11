#!/usr/bin/env python3
"""Project-level QA: per-template frame strips, aggregate verification,
private-path scan, disk usage, master Project_Manifest.json and
QUALITY_ASSURANCE_REPORT.md. Run after `build.py validate`."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cmet.export import ROOT, TPL  # noqa: E402
from cmet import validate as V  # noqa: E402

STRIPS = os.path.join(ROOT, "03_PREVIEWS", "Contact_Sheets", "per_template")


def strip(m):
    d = m["_dir"]
    pv = os.path.join(TPL, d, m["preview"]) if m.get("preview") else None
    if not pv or not os.path.exists(pv):
        return None
    ph = m["phases"]
    fps = m["frame_rate"]
    frames = [max(0, ph["build_up"][1] // 2), ph["impact_frame"] - 6, ph["impact_frame"] + 3,
              (ph["hero_hold"][0] + ph["hero_hold"][1]) // 2, ph["exit"][0] + (ph["exit"][1] - ph["exit"][0]) // 2,
              m["duration_frames"] - 2]
    tiles = []
    for f in frames:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{f / fps:.3f}", "-i", pv, "-frames:v", "1", "-f",
                              "rawvideo", "-pix_fmt", "bgr24", "-s", "384x216", "-"], capture_output=True).stdout
        if len(raw) == 384 * 216 * 3:
            tiles.append(np.frombuffer(raw, np.uint8).reshape(216, 384, 3))
    if not tiles:
        return None
    import cv2
    img = np.hstack(tiles)
    os.makedirs(STRIPS, exist_ok=True)
    out = os.path.join(STRIPS, f"{d}_strip.jpg")
    cv2.imwrite(out, img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return out


def strips_sheet(ms):
    """All templates' six-frame strips stacked in one comparable sheet."""
    import cv2
    rows = []
    for m in ms:
        p = os.path.join(STRIPS, f"{m['_dir']}_strip.jpg")
        if not os.path.exists(p):
            continue
        im = cv2.resize(cv2.imread(p), (6 * 240, 135), interpolation=cv2.INTER_AREA)
        lab = np.zeros((135, 260, 3), np.uint8)
        cv2.putText(lab, m["id"], (12, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (120, 190, 240), 2, cv2.LINE_AA)
        words = m["name"].upper().split()
        line, y = "", 85
        for w in words:
            if len(line) + len(w) > 16:
                cv2.putText(lab, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA)
                line, y = w, y + 22
            else:
                line = (line + " " + w).strip()
        cv2.putText(lab, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA)
        rows.append(np.hstack([lab, im]))
    if not rows:
        return None
    head = np.zeros((60, rows[0].shape[1], 3), np.uint8)
    hdr = ("BUILD-UP", "PRE-IMPACT", "IMPACT+3", "HERO HOLD", "EXIT", "END")
    for i, h in enumerate(hdr):
        cv2.putText(head, h, (260 + i * 240 + 10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1, cv2.LINE_AA)
    out = os.path.join(ROOT, "03_PREVIEWS", "Contact_Sheets", "contact_sheet_strips.jpg")
    cv2.imwrite(out, np.vstack([head] + rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
    return out


def resolve_checklist(ms):
    """Per-template manual test list for the first Resolve session."""
    L = ["# DaVinci Resolve manual test checklist", "",
         "Nothing in this library has been opened in DaVinci Resolve yet. Use this list during the first session.",
         "It is generated from the validated manifests by `qa.py`.", "",
         "For each template:",
         "1. Install it (see Import_Instructions.md), add it to a 24 fps timeline and trim it to the frame count shown.",
         "2. Check that the title text appears in the expected font. If it doesn't, install the fonts.",
         "3. Scrub the build-up, the impact frame, the hold and the exit, and compare them with the preview MP4.",
         "4. Edit *Main Title* and move *Impact Frame*; the effects should re-time.",
         "5. Check the listed unconfirmed inputs. If one of these settings is missing, set it by hand.",
         "", "| ID | Name | Frames | Impact | Depth | Unconfirmed inputs to check | Notes |", "|---|---|---|---|---|---|---|"]
    for m in ms:
        un = ", ".join(f"`{x}`" for x in m.get("unconfirmed_fusion_inputs", [])) or "-"
        notes = " ".join(m.get("fusion_notes", []))[:220].replace("|", "/")
        L.append(f"| {m['id']} | {m['name']} | {m['duration_frames']} | {m['phases']['impact_frame']} | "
                 f"{'3D' if m['true_3d'] else '2.5D'} | {un} | {notes or '-'} |")
    L.append("")
    open(os.path.join(ROOT, "05_RESOLVE_IMPORT", "Resolve_Test_Checklist.md"), "w", encoding="utf-8").write("\n".join(L))


def du(path):
    tot = 0
    for dp, dn, fn in os.walk(path):
        for f in fn:
            try:
                tot += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return tot


def main():
    ms = []
    for d in sorted(os.listdir(TPL)):
        mp = os.path.join(TPL, d, "manifest.json")
        if os.path.exists(mp):
            m = json.load(open(mp, encoding="utf-8"))
            m["_dir"] = d
            ms.append(m)
    for m in ms:
        strip(m)
    strips_sheet(ms)
    resolve_checklist(ms)
    n = len(ms)
    src_ok = [m for m in ms if m["verification"]["structure"] == "PASS"]
    lua_ok = [m for m in ms if m["verification"]["lua_parse"] == "PASS"]
    prv_ok = [m for m in ms if m["verification"]["preview"] == "PASS"]
    n3d = [m for m in ms if m["true_3d"]]
    ev = {"S": 0, "K": 0, "?": 0}
    for m in ms:
        for k, v in m["verification"]["source_details"].get("setting_input_evidence", {}).items():
            ev[k] = ev.get(k, 0) + v
    private = V.scan_private_paths()
    total = du(ROOT)
    free = shutil.disk_usage(ROOT).free
    cats = {}
    for m in ms:
        cats.setdefault(m["category"], []).append(m["id"])
    # master manifest ---------------------------------------------------------
    files = []
    for dp, dn, fn in os.walk(ROOT):
        if "__pycache__" in dp or "/_tmp" in dp:
            continue
        for f in fn:
            p = os.path.join(dp, f)
            files.append({"path": os.path.relpath(p, ROOT).replace(os.sep, "/"), "bytes": os.path.getsize(p)})
    files.sort(key=lambda x: x["path"])
    master = {
        "project": "Cinematic Mass Elevation Templates", "version": "1.0.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "template_count": n,
        "templates": [{"id": m["id"], "name": m["name"], "category": m["category"], "dir": f"01_TEMPLATES/{m['_dir']}",
                       "duration_frames": m["duration_frames"], "true_3d": m["true_3d"],
                       "fusion_macro": f"01_TEMPLATES/{m['_dir']}/{m['fusion_macro']}",
                       "fusion_composition": f"01_TEMPLATES/{m['_dir']}/{m['fusion_composition']}",
                       "preview": f"01_TEMPLATES/{m['_dir']}/{m['preview']}" if m.get("preview") else None,
                       "source_check": m["verification"]["structure"] == "PASS",
                       "preview_check": m["verification"]["preview"] == "PASS",
                       "resolve_tested": False} for m in ms],
        "totals": {"bytes": total, "files": len(files)},
        "files": files,
    }
    json.dump(master, open(os.path.join(ROOT, "00_PROJECT_FILES", "Project_Manifest.json"), "w"), indent=1,
              ensure_ascii=False)

    # QA report -----------------------------------------------------------------
    L = ["# Quality Assurance Report", "",
         f"Generated {master['generated_at']} by `06_AUTOMATION/Scripts/qa.py` from the validated manifests.", "",
         "## Three separate verification levels", "",
         "| Level | What was checked | Result |", "|---|---|---|",
         f"| 1. Source (static) | `.setting` and `.comp` parse in a real Lua 5.5 interpreter; every node connection "
         f"and expression reference resolves; every CONTROLS reference is a defined control; no unused/dead "
         f"published controls; editable text node present; time-based animation present; exit defined "
         f"(ExitStart referenced); only known tool IDs | Lua parse {len(lua_ok)}/{n}, structure {len(src_ok)}/{n} |",
         f"| 2. Preview (rendered) | MP4 exists and is not truncated; ffprobe-readable; 1920x1080; duration and "
         f"frame count match the template; audio present; not a static black screen; motion between samples; "
         f"hero frame <6% clipped and has contrast | {len(prv_ok)}/{n} |",
         f"| 3. DaVinci Resolve | Opened/rendered inside Resolve or Fusion | **0/{n} - not possible: Resolve/Fusion "
         f"were not installed in the build environment** |", "",
         "A valid source file, a rendered preview and an application-tested project are different things; only "
         "levels 1 and 2 were achieved here.", "",
         "## Per-template results", "",
         "| ID | Name | Depth | Tools | Published controls | Lua | Structure | Preview | Hero clipped | Title-area contrast | Notes |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in ms:
        v = m["verification"]
        sd = v["source_details"]
        pdd = v["preview_details"]
        notes = "; ".join((sd.get("warnings") or []) + (pdd.get("warnings") or []))[:120]
        L.append(f"| {m['id']} | {m['name']} | {'3D' if m['true_3d'] else '2.5D'} | {m['fusion_tool_count']} | "
                 f"{len(m['fusion_published_controls'])} | {v['lua_parse']} | "
                 f"{'PASS' if v['structure'] == 'PASS' else v['structure'][:60]} | "
                 f"{'PASS' if v['preview'] == 'PASS' else v['preview'][:60]} | "
                 f"{pdd.get('hero_blown_fraction', '-')} | {pdd.get('title_band_contrast', '-')} | {notes} |")
    L += ["", "## Identifier evidence in the Fusion sources", "",
          "Each input set in every macro was classified against `cmet/fusion_ref.py` (S = seen in real node "
          "text/docs, K = established usage not re-confirmed, ? = unconfirmed; Fusion drops unknown inputs on "
          "load, so a wrong name loses that one setting rather than breaking the file):", "",
          f"- S: {ev.get('S', 0)}, K: {ev.get('K', 0)}, ?: {ev.get('?', 0)} "
          f"({100 * ev.get('?', 0) / max(1, sum(ev.values())):.1f}% unconfirmed)", "",
          "## Visual review", "",
          "Every preview was reduced to a six-frame strip (build-up, pre-impact, impact+3, hold, exit, last frame) "
          "in `03_PREVIEWS/Contact_Sheets/per_template/` and the 40-up contact sheet "
          "`03_PREVIEWS/Contact_Sheets/contact_sheet_all.jpg`; these were inspected for missing/clipped text, "
          "blank frames, overexposure, clutter, broken framing and abrupt cuts. Findings are recorded in "
          "FINAL_REPORT.md.", "",
          "## Hygiene", "",
          f"- Machine-specific paths in shipped text files: {len(private)} " + (f"({', '.join(private[:5])})" if private else "(none)"),
          f"- Categories: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in sorted(cats.items())),
          f"- Genuine 3D (Text3D) templates: {', '.join(m['id'] for m in n3d) or 'none'}",
          f"- Project size: {total / 1e6:.1f} MB in {len(files)} files; free space at QA time: {free / 1e9:.1f} GB",
          ""]
    open(os.path.join(ROOT, "QUALITY_ASSURANCE_REPORT.md"), "w").write("\n".join(L))
    print(f"templates={n} lua={len(lua_ok)} structure={len(src_ok)} preview={len(prv_ok)} 3d={len(n3d)} "
          f"private_paths={len(private)} size={total / 1e6:.1f}MB")


if __name__ == "__main__":
    main()
