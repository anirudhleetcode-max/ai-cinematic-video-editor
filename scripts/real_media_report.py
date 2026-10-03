"""Discover every media file under tests/real_media/ (any depth, any filename) and inspect it.

  python scripts/real_media_report.py [--root tests/real_media] [--out tests/real_media/REPORT.json]

For each file: FFprobe metadata, validation, corruption (sampled decode), unusual / legacy codecs, variable frame
rate (packet timestamps), rotation, pixel aspect, pixel format / bit depth, colour range / matrix, HDR, missing or
multiple audio streams — plus the normalisation the engine will apply. Nothing is assumed from filenames.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine"))

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm", ".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"}


def discover(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXT and not p.name.startswith("."))


def main() -> int:
    from editor.media.inspect import inspect_media

    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT / "tests" / "real_media"))
    ap.add_argument("--out", default=str(ROOT / "tests" / "real_media" / "REPORT.json"))
    args = ap.parse_args()
    root = Path(args.root)
    files = discover(root)
    if not files:
        print(f"no media found under {root} — see tests/real_media/README.md")
        return 1
    rows, warn_counts = [], Counter()
    t_all = time.perf_counter()
    for f in files:
        t = time.perf_counter()
        r = inspect_media(f)
        r["path"] = str(f.relative_to(root))
        r["inspect_seconds"] = round(time.perf_counter() - t, 3)
        rows.append(r)
        for w in r["warnings"]:
            warn_counts[w.split(":")[0]] += 1
        P = r["props"]
        dims = f"{P.get('display_width', '')}x{P.get('display_height', '')}" if r["kind"] == "video" else "audio"
        print(f"{'OK ' if r['ok'] else 'BAD'} {r['path'][:52]:52} {dims:>10} {str(P.get('avg_fps', '')):>7} "
              f"{', '.join(r['issues'] + r['warnings'])[:110]}")
    summary = {"files": len(rows), "ok": sum(r["ok"] for r in rows), "unusable": [r["path"] for r in rows if not r["ok"]],
               "video": sum(r["kind"] == "video" for r in rows), "audio": sum(r["kind"] == "audio" for r in rows),
               "warning_counts": dict(warn_counts), "seconds": round(time.perf_counter() - t_all, 2)}
    Path(args.out).write_text(json.dumps({"summary": summary, "files": rows}, indent=1, default=str))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
