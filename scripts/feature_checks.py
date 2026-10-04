"""Feature checks on REAL footage for the release feature matrix: each request is planned AND rendered, and the
delivered MP4 is measured. Records exactly what was produced, including when a capability is unavailable.

  python scripts/feature_checks.py --media DIR [--data DIR] [--out docs/feature_checks.json] [--frames DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine"))


def probe(p: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,pix_fmt:format=duration", "-of", "json", str(p)],
                         capture_output=True, text=True).stdout
    d = json.loads(out)
    v = next(s for s in d["streams"] if s.get("width"))
    return {"width": v["width"], "height": v["height"], "vcodec": v["codec_name"], "duration": round(float(d["format"]["duration"]), 3)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True)
    ap.add_argument("--data", default=None)
    ap.add_argument("--out", default=str(ROOT / "docs" / "feature_checks.json"))
    ap.add_argument("--frames", default=str(Path(tempfile.gettempdir()) / "cutroom-feature-frames"))
    a = ap.parse_args()
    os.environ.setdefault("EDITOR_DATA_DIR", a.data or tempfile.mkdtemp(prefix="feature-checks-"))
    from editor import service as S
    from editor.reference.analyze import analyze_reference

    frames = Path(a.frames)
    frames.mkdir(parents=True, exist_ok=True)
    p = S.create_project("feature checks")
    med = Path(a.media)
    for f in sorted(med.iterdir()):
        with open(f, "rb") as fh:
            S.add_asset(p["id"], f.name, fh, "music" if f.suffix in (".ogg", ".mp3", ".wav", ".flac", ".m4a") else None)
    S.analyze_project(p["id"], "fast")
    cases = {
        "aspect_9_16": ("A 10 second Instagram reel, vertical 9:16, energetic", lambda pl, pr: (pr["width"], pr["height"]) == (1080, 1920)),
        "aspect_1_1": ("A 10 second square 1:1 post for Instagram feed", lambda pl, pr: (pr["width"], pr["height"]) == (1080, 1080)),
        "aspect_4_5": ("A 10 second 4:5 portrait post for Instagram", lambda pl, pr: (pr["width"], pr["height"]) == (1080, 1350)),
        "speed_ramps_slowmo": ("A 12 second cinematic edit with slow motion and speed ramps", lambda pl, pr: any(
            s["speed"]["rate"] < 0.99 or s["speed"].get("ramp") for s in pl["timeline"])),
        "zoom_motion": ("A 12 second dynamic edit with slow push-in zooms and camera movement", lambda pl, pr: any(
            (s.get("motion") or {}).get("preset", "none") != "none" for s in pl["timeline"])),
        "transitions_dissolve": ("A 12 second calm edit with smooth dissolve transitions between every shot", lambda pl, pr: any(
            s["transition_in"]["id"] not in ("cut", "none") for s in pl["timeline"])),
        "title_text": ('A 10 second recap with the title "Field Test" at the start', lambda pl, pr: any("Field Test" in (t.get("text") or "") for t in pl["text"])),
        "captions": ("A 10 second recap with subtitles / captions of what people say", lambda pl, pr: bool(
            pl["captions"].get("enabled") and pl["captions"].get("words"))),
    }
    res: dict = {"label": "MEASURED on real footage", "media": sorted(f.name for f in med.iterdir()), "cases": {}}
    for name, (prompt, ok) in cases.items():
        t0 = time.time()
        try:
            v = S.create_edit_plan(p["id"], prompt, "fast")
            r = S.render_version(p["id"], v["id"], preview=False)
            pr = probe(Path(r["path"]))
            pl = v["plan"]
            row = {"prompt": prompt, "probe": pr, "qc_passed": r["report"]["qc"]["passed"], "segments": len(pl["timeline"]),
                   "seconds": round(time.time() - t0, 1), "requested_effect_present": bool(ok(pl, pr))}
            if name == "speed_ramps_slowmo":
                row["speed_segments"] = sum(1 for s in pl["timeline"] if s["speed"]["rate"] < 0.99 or s["speed"].get("ramp"))
            if name == "zoom_motion":
                row["motion_presets"] = sorted({(s.get("motion") or {}).get("preset", "none") for s in pl["timeline"]})
            if name == "transitions_dissolve":
                row["transition_types"] = sorted({s_["transition_in"]["id"] for s_ in pl["timeline"]})
                row["measured_in_output"] = analyze_reference(Path(r["path"]), light=True)["transition_types"]
            if name == "captions":
                row["captions_plan"] = {k: (len(v_) if k == "words" else v_) for k, v_ in pl["captions"].items()}
                row["note"] = [d for d in pl.get("decisions", []) if "caption" in d.lower() or "subtitle" in d.lower() or "transcri" in d.lower()][:3]
                if not pl["captions"].get("words") and any("no speech-to-text model" in n for n in row["note"]):
                    row["status"] = "UNAVAILABLE in this environment: no speech-to-text model installed (reported, not faked)"
            fr = frames / f"{name}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.5", "-i", r["path"], "-frames:v", "1", "-vf", "scale=-2:480", str(fr)])
            row["frame"] = str(fr)
            row["pass"] = row["qc_passed"] and row["requested_effect_present"]
        except Exception as e:  # noqa: BLE001 — recorded, not hidden
            row = {"prompt": prompt, "error": f"{type(e).__name__}: {e}"[:300], "pass": False}
        res["cases"][name] = row
        print(name, json.dumps({k: v_ for k, v_ in row.items() if k not in ("frame",)}, default=str)[:600], flush=True)
        Path(a.out).write_text(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
