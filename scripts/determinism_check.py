"""Determinism audit: every stage run twice from scratch must give identical results.

  python scripts/determinism_check.py [--out docs/determinism_report.json]

Stages: generated test media (decoded frame hashes), shot analysis (shots, issues, scores, tags), reference analysis,
retrieval, planning (timeline), render (output metadata and decoded frame hashes). Each repetition uses a fresh data
directory, so no cache is shared between the two runs.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHILD = r'''
import hashlib, json, subprocess, sys
from pathlib import Path
from editor import testmedia, service as S
from editor.media.analyze import analyze_video
from editor.reference.analyze import analyze_reference
from editor.retrieval import search

root = Path(sys.argv[1])
def fhash(p):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-map", "0:v", "-f", "framemd5", "-"], capture_output=True, text=True).stdout
    return hashlib.sha256("".join(l for l in out.splitlines(True) if not l.startswith("#")).encode()).hexdigest()[:16]
ds = testmedia.make_dataset(root / "media", n_clips=8, n_songs=1, with_reference=True, clip_seconds=(3.0, 4.0), w=640, h=360)
res = {"media": {p.name: fhash(p) for p in ds["clips"]}, "reference_media": fhash(ds["reference"])}
an = {}
for p in ds["clips"]:
    a = analyze_video(p, "fast")
    an[p.name] = [{"start": round(s["start"], 3), "end": round(s["end"], 3), "issues": sorted(s["issues"]), "tags": sorted(s["tags"]),
                   "scores": {k: round(v, 4) for k, v in sorted(s["scores"].items())}} for s in a["shots"]]
res["analysis"] = hashlib.sha256(json.dumps(an, sort_keys=True).encode()).hexdigest()[:16]
r = analyze_reference(ds["reference"])
res["reference"] = {k: r[k] for k in ("n_shots", "median_shot_duration", "cuts_per_minute", "transition_types")}
pr = S.create_project("det")
for p in ds["clips"]:
    with open(p, "rb") as fh: S.add_asset(pr["id"], p.name, fh, "clip")
with open(ds["songs"][0], "rb") as fh: S.add_asset(pr["id"], "song.wav", fh, "music")
S.analyze_project(pr["id"], "fast")
v = S.create_edit_plan(pr["id"], "A 10 second energetic recap cut to the beat", "fast")
names = {a["id"]: a["filename"] for a in S.list_assets(pr["id"])}
tl = [(names[s["asset_id"]], s["shot_index"], round(s["src_in"], 3), round(s["out_duration"], 3)) for s in v["plan"]["timeline"]]
res["plan"] = hashlib.sha256(json.dumps(tl).encode()).hexdigest()[:16]
res["plan_segments"] = len(tl)
from editor import db
res["retrieval"] = search([{"filename": names[a["id"]], "analysis": db.get("assets", a["id"])["analysis"]} for a in S.list_assets(pr["id"]) if a["role"] == "clip"], "wide shots")["n_matches"]
rr = S.render_version(pr["id"], v["id"], preview=False)
q = rr["report"]["qc"]["probe"]
res["render_metadata"] = {k: q.get(k) for k in ("duration", "width", "height", "fps", "vcodec", "acodec")}
res["render_frames"] = fhash(rr["path"])
print("RESULT " + json.dumps(res, sort_keys=True))
'''


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "docs" / "determinism_report.json"
    runs = []
    for i in range(2):
        d = Path(tempfile.mkdtemp(prefix=f"det{i}-"))
        env = {**os.environ, "EDITOR_DATA_DIR": str(d / "data"), "EDITOR_AI_PROVIDER": "deterministic"}
        p = subprocess.run([sys.executable, "-c", CHILD, str(d)], cwd=ROOT / "services" / "engine", env=env, capture_output=True, text=True, timeout=3600)
        line = next((l for l in p.stdout.splitlines() if l.startswith("RESULT ")), None)
        if not line:
            print(p.stderr[-3000:])
            return 2
        runs.append(json.loads(line[7:]))
    a, b = runs
    stages = sorted(set(a) | set(b))
    cmp = {k: {"identical": a.get(k) == b.get(k), "run1": a.get(k) if not isinstance(a.get(k), dict) or len(json.dumps(a.get(k))) < 300 else "(dict)",
               "run2": b.get(k) if not isinstance(b.get(k), dict) or len(json.dumps(b.get(k))) < 300 else "(dict)"} for k in stages}
    report = {"label": "MEASURED — two independent runs, fresh data directories", "stages": cmp, "all_identical": all(v["identical"] for v in cmp.values())}
    out.write_text(json.dumps(report, indent=1, default=str))
    for k, v in cmp.items():
        print(f"{'same' if v['identical'] else 'DIFF':>4}  {k}")
    print("DETERMINISTIC" if report["all_identical"] else "NONDETERMINISTIC STAGES FOUND")
    return 0 if report["all_identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
