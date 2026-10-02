"""Benchmark the full pipeline on synthetic media and store REAL measurements in the database
(visible at /benchmarks in the web app) and in docs/benchmarks.json.

Usage: python scripts/benchmark.py --sizes 10 25 50 100 200 --output-seconds 60 [--mode fast]
Measures: analysis, planning, render, total wall time; peak RSS; mean CPU %; disk used; QC result."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine"))


class Sampler(threading.Thread):
    """Samples CPU % and RSS of this process tree (ffmpeg children included) every 0.5 s."""

    def __init__(self):
        super().__init__(daemon=True)
        self.stop_ = False
        self.cpu: list[float] = []
        self.rss_peak = 0
        self.proc = psutil.Process()

    def run(self):
        psutil.cpu_percent(None)
        while not self.stop_:
            self.cpu.append(psutil.cpu_percent(0.5))
            try:
                procs = [self.proc, *self.proc.children(recursive=True)]
                self.rss_peak = max(self.rss_peak, sum(p.memory_info().rss for p in procs if p.is_running()))
            except psutil.Error:
                pass


def dir_mb(p: Path) -> float:
    return round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 2**20, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 25, 50, 100, 200])
    ap.add_argument("--output-seconds", type=float, default=60)
    ap.add_argument("--mode", default="fast", choices=["fast", "quality", "emergency"])
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    base = Path(tempfile.mkdtemp(prefix="bench-"))
    os.environ.setdefault("EDITOR_DATA_DIR", str(ROOT / "data"))  # results go to the app DB
    from editor import db, service as S, testmedia
    from editor.hw import diagnostics

    env = diagnostics()
    results = []
    for n in args.sizes:
        media = base / f"m{n}"
        t = time.perf_counter()
        ds = testmedia.make_dataset(media, n_clips=n, n_songs=3, with_reference=True, clip_seconds=(3.0, 8.0), w=args.width, h=args.height, seed=n)
        gen_s = time.perf_counter() - t
        p = S.create_project(f"Benchmark {n} clips ({args.mode})")
        for c in ds["clips"]:
            with open(c, "rb") as fh:
                S.add_asset(p["id"], c.name, fh)
        for s in ds["songs"]:
            with open(s, "rb") as fh:
                S.add_asset(p["id"], s.name, fh, "music")
        with open(ds["reference"], "rb") as fh:
            S.add_asset(p["id"], "reference.mp4", fh, "reference")
        with open(ds["logo"], "rb") as fh:
            S.add_asset(p["id"], "logo.png", fh, "logo")
        proj_dir = Path(os.environ["EDITOR_DATA_DIR"]) / "projects" / p["id"]
        sampler = Sampler()
        sampler.start()
        t0 = time.perf_counter()
        S.analyze_project(p["id"], args.mode)
        t1 = time.perf_counter()
        prompt = (f"Create a {int(args.output_seconds)}-second cinematic event highlight. Follow the reference pacing, best clips only, strong hook, "
                  "cut to the beat, build energy toward the climax, subtle transitions, consistent grade, elegant typography, duck music under speech, "
                  "and finish with the event logo.")
        v = S.create_edit_plan(p["id"], prompt, args.mode)
        t2 = time.perf_counter()
        r = S.render_version(p["id"], v["id"], preview=False)
        t3 = time.perf_counter()
        sampler.stop_ = True
        sampler.join(2)
        m = {
            "n_clips": len(ds["clips"]), "mode": args.mode, "source_resolution": f"{args.width}x{args.height}", "output_seconds": args.output_seconds,
            "analysis_s": round(t1 - t0, 1), "planning_s": round(t2 - t1, 2), "render_s": round(t3 - t2, 1), "total_s": round(t3 - t0, 1),
            "render_breakdown": r["report"]["timings"], "peak_rss_mb": round(sampler.rss_peak / 2**20, 1),
            "cpu_percent_avg": round(sum(sampler.cpu) / max(1, len(sampler.cpu)), 1), "disk_mb": dir_mb(proj_dir),
            "qc_passed": r["report"]["qc"]["passed"], "encoder": r["report"].get("encoder"), "gpu": env.get("gpu"), "cpu_count": env.get("cpu_count"),
            "synthetic_media_generation_s": round(gen_s, 1), "data": "synthetic DEMO media",
        }
        db.insert("benchmarks", id=db.new_id("bm"), label=f"{n} clips · {args.output_seconds:.0f}s · {args.mode}", n_clips=len(ds["clips"]), metrics=m, created=time.time())
        results.append(m)
        print(json.dumps(m), flush=True)
        if not args.keep:
            S.delete_project(p["id"])
            shutil.rmtree(media, ignore_errors=True)
    out = ROOT / "docs" / "benchmarks.json"
    prev = json.loads(out.read_text()) if out.exists() else []
    out.write_text(json.dumps(prev + [{"environment": {k: env[k] for k in ("os", "cpu_count", "ram_total_gb", "gpu", "encoders", "ffmpeg")}, "runs": results,
                                       "when": time.strftime("%Y-%m-%d %H:%M")}], indent=2))
    shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
