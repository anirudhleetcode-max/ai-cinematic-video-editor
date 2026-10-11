"""Automated validation. Results feed the manifests and QA report.

Three verification levels are kept separate:
  1. source  - file parses (real Lua), graph references resolve, controls live
  2. preview - media file exists, ffprobe-valid, right size/duration, not
               black/static/blown-out
  3. resolve - opened/rendered inside DaVinci Resolve. Always "NOT TESTED"
               here: Resolve is not installed in the build environment.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

import numpy as np

from .base import FPS
from .fusion_ref import TOOLS, ALLOWED_TOOL_EVIDENCE, input_evidence
from .luacheck import parse, tools_of

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
PRIVATE_PATH = re.compile(r"(/home/\w+|/tmp/claude|C:\\\\Users\\\\|C:/Users/|/Users/\w+/)")


def check_source(setting_path, comp_path):
    r = {"errors": [], "warnings": []}
    for kind, path in (("setting", setting_path), ("comp", comp_path)):
        if not os.path.exists(path):
            r["errors"].append(f"{kind} missing")
            continue
        src = open(path, encoding="utf-8").read()
        if PRIVATE_PATH.search(src):
            r["errors"].append(f"{kind} contains a machine-specific path")
        try:
            tree, ctor = parse(src)
        except SyntaxError as e:
            r["errors"].append(f"{kind} Lua parse error: {e}")
            continue
        tools = tools_of(tree)
        r[f"{kind}_tools"] = len(tools)
        names = set(tools)
        ev = {"S": 0, "K": 0, "?": 0}
        exprs = 0
        time_exprs = 0
        exit_refs = 0
        ctrl_defs = set()
        if "CONTROLS" in tools:
            uc = tools["CONTROLS"][2].get("UserControls", {})
            ctrl_defs = {k for k in uc if k != "__ctor"}
        for n, (tid, inputs, raw) in tools.items():
            if tid not in TOOLS:
                r["errors"].append(f"{kind}: unknown tool id {tid} ({n})")
                continue
            if TOOLS[tid][0] not in ALLOWED_TOOL_EVIDENCE:
                r["errors"].append(f"{kind}: low-evidence tool id {tid}")
            for inp, spec in inputs.items():
                if n == "CONTROLS" and inp in ctrl_defs:
                    continue
                e = input_evidence(tid, inp)
                ev[e] = ev.get(e, 0) + 1
                if not isinstance(spec, dict):
                    continue
                so = spec.get("SourceOp")
                if so is not None and so not in names:
                    r["errors"].append(f"{kind}: {n}.{inp} -> missing {so}")
                ex = spec.get("Expression")
                if ex:
                    exprs += 1
                    if "time" in ex:
                        time_exprs += 1
                    if "ExitStart" in ex:
                        exit_refs += 1
                    for a, b in re.findall(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)", ex):
                        if a not in names:
                            r["errors"].append(f"{kind}: expression in {n}.{inp} references missing {a}")
                        elif a == "CONTROLS" and b not in ctrl_defs:
                            r["errors"].append(f"{kind}: expression references undefined control {b}")
                    if ex.count("(") != ex.count(")"):
                        r["errors"].append(f"{kind}: unbalanced expression in {n}.{inp}")
                    if "^" in ex:
                        r["warnings"].append(f"{kind}: '^' used in {n}.{inp}")
        text_nodes = [n for n, (tid, inp, _) in tools.items()
                      if tid in ("TextPlus", "Text3D") and "StyledText" in inp]
        if not text_nodes:
            r["errors"].append(f"{kind}: no editable text node")
        if time_exprs < 3:
            r["errors"].append(f"{kind}: no time-based animation found")
        if exit_refs < 1:
            r["errors"].append(f"{kind}: exit animation not defined (no ExitStart reference)")
        r[f"{kind}_input_evidence"] = ev
        r[f"{kind}_expressions"] = exprs
        if kind == "setting":
            macro = [v for k, v in tree["Tools"].items() if k != "__ctor"][0]
            ins = {k: v for k, v in macro.get("Inputs", {}).items() if k != "__ctor"}
            r["published_controls"] = len(ins)
            for k, v in ins.items():
                if v.get("SourceOp") not in names:
                    r["errors"].append(f"published {k} -> missing tool {v.get('SourceOp')}")
            pub_ctrl = {v["Source"] for v in ins.values() if v.get("SourceOp") == "CONTROLS"}
            dead = pub_ctrl - ctrl_defs
            if dead:
                r["errors"].append(f"published controls without definition: {sorted(dead)}")
            unused = ctrl_defs - {b for t in tools.values() for s in t[1].values() if isinstance(s, dict)
                                  for a, b in re.findall(r"\b(CONTROLS)\.(\w+)", s.get("Expression", "") or "")}
            if unused:
                r["errors"].append(f"controls defined but unused: {sorted(unused)}")
            out = macro.get("Outputs", {}).get("MainOutput1", {})
            if out.get("SourceOp") not in names:
                r["errors"].append("macro output not connected")
            r["text_nodes"] = text_nodes
    r["ok"] = not r["errors"]
    return r


def ffprobe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)


def grab(path, t, W=480, H=270):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-s", f"{W}x{H}", "-"], capture_output=True).stdout
    if len(raw) != W * H:
        return None
    return np.frombuffer(raw, np.uint8).reshape(H, W).astype(np.float32)


def check_preview(path, frames, W=1920, H=1080, hero_frame=None):
    r = {"errors": [], "warnings": []}
    if not os.path.exists(path) or os.path.getsize(path) < 10000:
        r["errors"].append("preview missing or truncated")
        r["ok"] = False
        return r
    pr = ffprobe(path)
    if pr is None:
        r["errors"].append("ffprobe failed")
        r["ok"] = False
        return r
    v = [s for s in pr["streams"] if s["codec_type"] == "video"]
    a = [s for s in pr["streams"] if s["codec_type"] == "audio"]
    if not v:
        r["errors"].append("no video stream")
        r["ok"] = False
        return r
    v = v[0]
    r["codec"] = v["codec_name"]
    r["size"] = f"{v['width']}x{v['height']}"
    if (v["width"], v["height"]) != (W, H):
        r["errors"].append(f"size {r['size']} != {W}x{H}")
    dur = float(pr["format"]["duration"])
    r["duration"] = round(dur, 3)
    exp = frames / FPS
    if abs(dur - exp) > 0.15:
        r["errors"].append(f"duration {dur:.2f}s != expected {exp:.2f}s")
    nb = int(v.get("nb_frames", 0) or 0)
    r["frames"] = nb
    if nb and nb != frames:
        r["errors"].append(f"frame count {nb} != {frames}")
    r["audio"] = bool(a)
    r["bytes"] = os.path.getsize(path)
    ts = np.linspace(0.2, exp - 0.2, 9)
    imgs = [grab(path, t) for t in ts]
    if any(i is None for i in imgs):
        r["errors"].append("frame decode failed")
        r["ok"] = False
        return r
    means = [float(i.mean()) for i in imgs]
    r["sample_means"] = [round(m, 1) for m in means]
    if max(means) < 6:
        r["errors"].append("static black screen")
    diffs = [float(np.abs(imgs[i + 1] - imgs[i]).mean()) for i in range(len(imgs) - 1)]
    if max(diffs) < 0.5:
        r["errors"].append("no motion detected")
    hf = hero_frame if hero_frame is not None else frames // 2
    hero = grab(path, hf / FPS)
    if hero is not None:
        blown = float((hero > 250).mean())
        r["hero_blown_fraction"] = round(blown, 4)
        r["hero_contrast"] = round(float(hero.std()), 1)
        if blown > 0.06:
            r["errors"].append(f"hero frame overexposed ({blown:.1%} clipped)")
        if hero.std() < 8:
            r["errors"].append("hero frame has too little contrast (title unreadable?)")
        # central band must contain detail (the title)
        band = hero[int(270 * 0.3):int(270 * 0.7), int(480 * 0.15):int(480 * 0.85)]
        r["title_band_contrast"] = round(float(band.std()), 1)
        if band.std() < 10:
            r["warnings"].append("low contrast in title area at hero frame")
    r["ok"] = not r["errors"]
    return r


def scan_private_paths(root=ROOT):
    bad = []
    for dp, dn, fn in os.walk(root):
        if "__pycache__" in dp:
            continue
        for f in fn:
            if f.endswith((".md", ".json", ".setting", ".comp", ".html", ".ps1", ".py", ".sh")):
                p = os.path.join(dp, f)
                try:
                    s = open(p, encoding="utf-8").read()
                except Exception:
                    continue
                if f == "validate.py":
                    continue
                if PRIVATE_PATH.search(s):
                    bad.append(os.path.relpath(p, root))
    return bad
