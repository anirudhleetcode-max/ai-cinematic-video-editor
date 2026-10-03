"""Real-footage performance benchmark: 60-second, 5-minute and 10-minute edits from the same real project.

  python scripts/real_benchmark.py [--event tests/real_media/event01] [--durations 60 300 600] [--mode fast]

Analysis runs once (it is per-source and cached); each output length is then planned, previewed (640 px proxy render),
rendered at 1080p and quality-checked. Every number written is MEASURED in this run on this machine; nothing is
extrapolated. Results: docs/real_benchmarks.json (+ printed table).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine"))
sys.path.insert(0, str(ROOT / "scripts"))

from real_acceptance import Sampler, discover  # noqa: E402

PROMPT = ("Create a {d}-second professional cinematic event highlight. Follow the reference pacing and colour mood, select the best clips, "
          "remove poor-quality shots, begin with a strong hook, cut to the music, build energy toward the climax, tasteful transitions, "
          "consistent grading, duck music under speech, and finish with a branded ending.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default=str(ROOT / "tests" / "real_media" / "event01"))
    ap.add_argument("--durations", type=float, nargs="+", default=[60, 300, 600])
    ap.add_argument("--mode", default="fast", choices=["fast", "quality", "emergency"])
    ap.add_argument("--data", default=None)
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "docs" / "real_benchmarks.json"))
    args = ap.parse_args()
    os.environ.setdefault("EDITOR_DATA_DIR", args.data or tempfile.mkdtemp(prefix="real-bench-"))
    from editor import db, service as S
    from editor.hw import diagnostics

    roles = discover(Path(args.event))
    env = {k: v for k, v in diagnostics().items() if k in ("cpu_count", "ram_total_gb", "gpu", "platform_class", "encoders", "selected_encoder",
                                                          "hardware_encoding", "ffmpeg")} | {"os": platform.platform(), "cpu_model": _cpu_model()}
    out = {"label": "MEASURED", "event": args.event, "mode": args.mode, "environment": env, "inputs": {k: len(v) for k, v in roles.items()}, "runs": []}
    p = S.create_project("Real benchmark")
    t = time.perf_counter()
    for role, files in roles.items():
        for f in files:
            try:
                with open(f, "rb") as fh:
                    S.add_asset(p["id"], f.name, fh, role)
            except ValueError:
                pass
    out["upload_s"] = round(time.perf_counter() - t, 2)
    src_seconds = sum((a["meta"] or {}).get("duration", 0) for a in db.query("SELECT meta FROM assets WHERE project_id=? AND role='clip'", (p["id"],)))
    out["source_footage_seconds"] = round(src_seconds, 1)
    from collections import Counter

    metas = [a["meta"] or {} for a in db.query("SELECT meta FROM assets WHERE project_id=? AND role='clip'", (p["id"],))]
    out["source_codecs"] = dict(Counter(str(m.get("vcodec")) for m in metas))
    out["source_resolutions"] = dict(Counter(f"{m.get('width')}x{m.get('height')}" for m in metas))
    smp = Sampler()
    smp.start()
    t = time.perf_counter()
    an = S.analyze_project(p["id"], args.mode)
    out["analysis"] = {"seconds": round(time.perf_counter() - t, 2), "shots": an["shots"], "usable_shots": an["usable_shots"],
                       "peak_rss_mb": round(smp.rss_peak / 2**20, 1)}
    print(f"analysis {out['analysis']}", flush=True)
    for d in args.durations:
        smp.rss_peak, smp.cpu = 0, []
        run: dict = {"output_seconds": d, "label": "MEASURED"}
        t0 = time.perf_counter()
        t = time.perf_counter()
        v = S.create_edit_plan(p["id"], PROMPT.format(d=int(d)), args.mode)
        run["planning_s"] = round(time.perf_counter() - t, 3)
        keys = [(s["asset_id"], s["shot_index"]) for s in v["plan"]["timeline"]]
        run["segments"], run["repeated_shots"] = len(keys), len(keys) - len(set(keys))
        if not args.no_preview:
            t = time.perf_counter()
            pv = S.render_version(p["id"], v["id"], preview=True)
            run["preview_s"] = round(time.perf_counter() - t, 2)
            run["preview_qc"] = pv["report"]["qc"]["passed"]
        t = time.perf_counter()
        r = S.render_version(p["id"], v["id"], preview=False)
        run["final_render_s"] = round(time.perf_counter() - t, 2)
        rep = r["report"]
        q = rep["qc"]
        run.update(render_breakdown=rep.get("timings"), qc_passed=q["passed"], qc_failures=q["failures"], encoder=rep.get("encoder"),
                   output={k: q["probe"].get(k) for k in ("duration", "width", "height", "fps", "vcodec", "acodec")},
                   loudness_lufs=(rep.get("audio") or {}).get("integrated_lufs"), segments_cached=rep.get("segments_cached"),
                   review=(rep.get("review") or {}).get("summary"), reference_similarity=(rep.get("reference_match") or {}).get("overall_similarity"))
        run["output_size_bytes"] = Path(r["path"]).stat().st_size
        run["total_s"] = round(time.perf_counter() - t0, 2)
        run["peak_rss_mb"] = round(smp.rss_peak / 2**20, 1)
        run["cpu_percent_avg"] = round(sum(smp.cpu) / max(1, len(smp.cpu)), 1)
        out["runs"].append(run)
        print(json.dumps(run, default=str)[:600], flush=True)
        Path(args.out).write_text(json.dumps(out, indent=1, default=str))
    smp.stop_ = True
    Path(args.out).write_text(json.dumps(out, indent=1, default=str))
    print(f"\n{'output':>8} {'planning':>9} {'preview':>8} {'render':>8} {'total*':>8} {'QC':>4}  (*excl. one-off analysis {out['analysis']['seconds']}s)")
    for r_ in out["runs"]:
        print(f"{r_['output_seconds']:>7.0f}s {r_['planning_s']:>8.2f}s {r_.get('preview_s', 0):>7.1f}s {r_['final_render_s']:>7.1f}s {r_['total_s']:>7.1f}s "
              f"{'pass' if r_['qc_passed'] else 'FAIL':>4}")
    return 0


def _cpu_model() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
