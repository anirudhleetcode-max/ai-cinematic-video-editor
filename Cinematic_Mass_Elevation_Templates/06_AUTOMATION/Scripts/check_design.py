#!/usr/bin/env python3
"""Quick check for one design while authoring:
    python check_design.py t05 [frames] [out.jpg]
Builds the Fusion graph, writes .setting/.comp to a temp dir, runs the full
source validator (real Lua parse + structure), then renders a still sheet."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib  # noqa: E402

from cmet import validate as V  # noqa: E402

mod = sys.argv[1].lower()
D = importlib.import_module(f"cmet.designs.{mod}").DESIGN
p = D.params()
g = D.build_graph(p)
tmp = tempfile.mkdtemp()
sp, cp = os.path.join(tmp, "x.setting"), os.path.join(tmp, "x.comp")
open(sp, "w").write(g.macro_text(f"{D.ID}_{D.SLUG}"))
open(cp, "w").write(g.comp_text())
r = V.check_source(sp, cp)
print(f"{D.ID} {D.NAME}: tools={len(g.tools)} controls={g.control_names()}")
print("source check:", "PASS" if r["ok"] else "FAIL", r["errors"], r["warnings"][:3])
print("input evidence:", r.get("setting_input_evidence"))
if len(sys.argv) > 2:
    frames = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(tmp, f"{mod}.jpg")
    subprocess.run([sys.executable, os.path.join(HERE, "stills.py"), mod, frames, out], check=True)
    print("stills:", out)
