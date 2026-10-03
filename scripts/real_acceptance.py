"""Real-footage acceptance test (protocol: docs/REAL_FOOTAGE_HARDENING.md §Test strategy).

Put real media in tests/real_media/event01/ — either in sub-folders
    clips/  music/  reference/  logo/
or all in one folder (videos → clips, audio → music, images → logo, a video whose path contains "reference" → reference).
Filenames are never assumed. Then:

    python scripts/real_acceptance.py                       # uses tests/real_media/event01
    python scripts/real_acceptance.py --assemble            # first builds event01 from the downloaded real library

--assemble (needs scripts/fetch_real_media.py --all and scripts/make_real_variants.py) splits the real library recordings
into ~50 camera-style clips, adds the derived format variants (4K, HLG, rotated phone MOV, VFR, anamorphic, …), 3 real
songs and a *style-known* reference montage cut from real footage (1.2 s shots, warm grade) whose measured profile can
be checked against how it was made. The logo is a generated PNG (labelled).

Every number in the report is measured on this machine in this run.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine"))
EVENT = ROOT / "tests" / "real_media" / "event01"
LIB = ROOT / "tests" / "real_media" / "library"
DER = ROOT / "tests" / "real_media" / "derived"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"}
AUDIO_EXT = {".mp3", ".wav", ".aac", ".m4a", ".flac", ".ogg"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}

PROMPT = ("Create a 60-second professional cinematic event highlight. Analyze the reference and follow its pacing, color mood, "
          "typography philosophy, and transition style without copying its footage. Select the best clips, remove poor-quality shots, "
          "begin with a strong hook, synchronize cuts to the supplied music, use slower emotional shots where appropriate, build energy "
          "toward the climax, add tasteful motion and transitions, apply consistent professional color grading, add elegant event "
          "typography, duck music under speech, and finish with a strong branded ending.")
REVISIONS = ["Make it more energetic and reduce the intro to 3 seconds.", "Make the colors warmer.", "Use song 2 for the final section."]


class Sampler(threading.Thread):
    """CPU % (system) and peak RSS of this process tree (FFmpeg children included), every 0.5 s."""

    def __init__(self):
        super().__init__(daemon=True)
        self.stop_, self.cpu, self.rss_peak, self.proc = False, [], 0, psutil.Process()

    def run(self):
        psutil.cpu_percent(None)
        while not self.stop_:
            self.cpu.append(psutil.cpu_percent(0.5))
            try:
                self.rss_peak = max(self.rss_peak, sum(p.memory_info().rss for p in [self.proc, *self.proc.children(recursive=True)] if p.is_running()))
            except psutil.Error:
                pass


def ff(*a: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-nostdin", *a], check=True)


def dur(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout
    try:
        return float(out.strip())
    except ValueError:
        return 0.0


def assemble(target: Path) -> dict:
    """Build an event folder from the real library (see module docstring)."""
    if not (LIB / "video").exists() or not (DER / "MANIFEST.json").exists():
        raise SystemExit("run scripts/fetch_real_media.py --all and scripts/make_real_variants.py first")
    for sub in ("clips", "music", "reference", "logo"):
        (target / sub).mkdir(parents=True, exist_ok=True)
    clips = target / "clips"
    n = 0
    # 1) camera-style clips: long real recordings split into 6–12 s takes (stream copy would cut on keyframes; re-encode
    #    keeps exact boundaries and the original codec family)
    for v in sorted((LIB / "video").iterdir()):
        L = dur(v)
        if v.suffix == ".mkv" or L < 16:
            shutil.copy2(v, clips / v.name)
            n += 1
            continue
        k = min(3, int(L // 14))
        for i in range(k):
            st = 2 + i * (L - 4) / k
            ln = min(12.0, (L - 4) / k - 0.5)
            out = clips / f"{v.stem}_take{i + 1}.mp4"
            if not out.exists():
                ff("-ss", f"{st:.2f}", "-i", str(v), "-t", f"{ln:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", out.as_posix())
            n += 1
    # 2) user phone clips if present
    for v in sorted((ROOT / "tests" / "real_media" / "user").glob("*")) if (ROOT / "tests" / "real_media" / "user").exists() else []:
        if v.suffix.lower() in VIDEO_EXT:
            shutil.copy2(v, clips / v.name)
            n += 1
    # 3) derived format variants (real picture, changed container / timing / orientation / metadata)
    for it in json.loads((DER / "MANIFEST.json").read_text()):
        f = ROOT / "tests" / "real_media" / it["file"]
        if f.suffix.lower() in VIDEO_EXT and "long_5min" not in f.name:
            shutil.copy2(f, clips / ("derived_" + f.name))
            n += 1
    # 4) three real songs (different formats)
    for src, name in ((DER / "audio" / "vibe_ace.mp3", "song_a.mp3"), (DER / "audio" / "sugar_plum_fairy.flac", "song_b.flac"),
                      (LIB / "music" / "hungarian_dance_5.ogg", "song_c.ogg")):
        shutil.copy2(src, target / "music" / name)
    # 5) style-known reference: 30 × 1.2 s real shots, warm grade, real music, a lower-third title
    ref = target / "reference" / "reference_montage.mp4"
    if not ref.exists():
        srcs = [p for p in sorted(clips.glob("*_take*.mp4"))][:30]
        tmpd = Path(tempfile.mkdtemp())
        parts = []
        for i, p in enumerate(srcs):
            o = tmpd / f"p{i:02d}.mp4"
            ff("-ss", "1.0", "-i", str(p), "-t", "1.2", "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30,setsar=1,"
               "colorbalance=rs=0.10:gs=0.02:bs=-0.10:rm=0.06:bm=-0.06,eq=saturation=1.15:contrast=1.08", "-an", "-c:v", "libx264", "-crf", "18", o.as_posix())
            parts.append(o)
        lst = tmpd / "l.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
        font = ROOT / "packages" / "fonts" / "Montserrat_700Bold.ttf"
        font = font if font.exists() else next((ROOT / "packages" / "fonts").glob("*.ttf"))
        ff("-f", "concat", "-safe", "0", "-i", lst.as_posix(), "-i", str(LIB / "music" / "vibe_ace.ogg"),
           "-vf", f"drawtext=fontfile='{font.as_posix()}':text='SUMMER EVENT':fontsize=46:fontcolor=white:x=(w-tw)/2:y=h*0.80:enable='between(t,1,5)'",
           "-map", "0:v", "-map", "1:a", "-shortest", "-c:v", "libx264", "-crf", "18", "-c:a", "aac", ref.as_posix())
        (target / "reference" / "HOW_MADE.json").write_text(json.dumps({"shot_seconds": 1.2, "shots": len(parts), "cuts_per_minute": 50.0,
                                                                          "transitions": "hard cuts only", "grade": "warm (colorbalance +R −B)",
                                                                          "text": "one centred title, lower area, 1–5 s"}, indent=1))
    # 6) logo (generated, labelled)
    logo = target / "logo" / "logo_generated.png"
    if not logo.exists():
        ff("-f", "lavfi", "-i", "color=c=black@0.0:s=600x200,format=rgba", "-vf",
           f"drawtext=fontfile='{(ROOT / 'packages' / 'fonts').as_posix()}/{next((ROOT / 'packages' / 'fonts').glob('*.ttf')).name}':text='EVENT01':"
           "fontsize=120:fontcolor=white:x=(w-tw)/2:y=(h-th)/2", "-frames:v", "1", logo.as_posix())
    return {"clips": n}


def discover(folder: Path) -> dict[str, list[Path]]:
    roles: dict[str, list[Path]] = {"clip": [], "music": [], "reference": [], "logo": []}
    for p in sorted(x for x in folder.rglob("*") if x.is_file() and not x.name.startswith(".")):
        ext, parts = p.suffix.lower(), {q.lower() for q in p.relative_to(folder).parts[:-1]}
        if ext in VIDEO_EXT:
            roles["reference" if ("reference" in parts or "reference" in p.stem.lower()) else "clip"].append(p)
        elif ext in AUDIO_EXT:
            roles["music"].append(p)
        elif ext in IMAGE_EXT:
            roles["logo" if ("logo" in parts or "logo" in p.stem.lower() or not roles["logo"]) else "clip"].append(p)
    return roles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", default=str(EVENT))
    ap.add_argument("--assemble", action="store_true")
    ap.add_argument("--data", default=None, help="engine data dir (default: temp)")
    ap.add_argument("--mode", default="fast", choices=["fast", "quality", "emergency"])
    ap.add_argument("--duration", type=float, default=60.0)
    ap.add_argument("--no-revisions", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "docs" / "real_acceptance_report.json"))
    args = ap.parse_args()
    folder = Path(args.event)
    if args.assemble:
        assemble(folder)
    if not folder.exists():
        print(f"{folder} does not exist — add real media or use --assemble")
        return 1
    roles = discover(folder)
    if not roles["clip"]:
        print("no clips found")
        return 1
    os.environ.setdefault("EDITOR_DATA_DIR", args.data or tempfile.mkdtemp(prefix="real-accept-"))
    from editor import db, service as S
    from editor.hw import diagnostics
    from editor.schemas import EditPlan

    rep: dict = {"event": str(folder.relative_to(ROOT)) if folder.is_relative_to(ROOT) else str(folder), "prompt": PROMPT, "mode": args.mode,
                 "environment": {k: v for k, v in diagnostics().items() if k in ("ffmpeg", "cpu_count", "ram_total_gb", "gpu", "encoders", "selected_encoder",
                                                                                  "hardware_encoding")} | {"os": platform.platform(), "python": platform.python_version()},
                 "inputs": {k: len(v) for k, v in roles.items()}, "steps": {}, "measured": True}
    sampler = Sampler()
    sampler.start()
    t_all = time.perf_counter()

    def step(name: str, **kw):
        rep["steps"][name] = kw
        print(f"[{time.perf_counter() - t_all:7.1f}s] {name}: {json.dumps(kw, default=str)[:400]}", flush=True)

    p = S.create_project(f"Real acceptance {folder.name}")
    t = time.perf_counter()
    rejected_uploads = []
    for role, files in roles.items():
        for f in files:
            try:
                with open(f, "rb") as fh:
                    S.add_asset(p["id"], f.name, fh, role)
            except ValueError as e:
                rejected_uploads.append({"file": f.name, "reason": str(e)[:200]})
    step("upload", seconds=round(time.perf_counter() - t, 2), accepted=len(S.list_assets(p["id"])), rejected=rejected_uploads)

    t = time.perf_counter()
    an = S.analyze_project(p["id"], args.mode)
    step("analysis", seconds=round(time.perf_counter() - t, 2), **{k: an.get(k) for k in ("shots", "usable_shots", "rejected", "duplicate_groups", "cached", "proxies")})
    ref = (S.get_project(p["id"])["settings"] or {}).get("reference_profile")
    if ref:
        how = folder / "reference" / "HOW_MADE.json"
        step("reference_profile", median_shot=ref.get("median_shot_duration"), cuts_per_minute=ref.get("cuts_per_minute"),
             transition_frequency=ref.get("transition_frequency"), color=ref.get("color"), known=json.loads(how.read_text()) if how.exists() else None)

    t = time.perf_counter()
    prompt = PROMPT.replace("60-second", f"{int(args.duration)}-second")
    v1 = S.create_edit_plan(p["id"], prompt, args.mode)
    plan1 = EditPlan.model_validate(v1["plan"])
    rows = {a["id"]: a for a in db.query("SELECT id, filename, analysis FROM assets WHERE project_id=?", (p["id"],))}
    used = [(s.asset_id, s.shot_index) for s in plan1.timeline]
    # repeated FOOTAGE = the same source frames shown twice (overlapping ranges of one clip); using two different
    # moments of a long take is normal editing and is reported separately
    repeated_footage = []
    for i, a_ in enumerate(plan1.timeline):
        for b_ in plan1.timeline[i + 1:]:
            if a_.asset_id == b_.asset_id and min(a_.src_out, b_.src_out) - max(a_.src_in, b_.src_in) > 0.1:
                repeated_footage.append([a_.id, b_.id])
    bad_used = []
    for aid, si in used:
        sh = next((x for x in (rows[aid]["analysis"] or {}).get("shots", []) if x["index"] == si), None)
        if sh and set(sh["issues"]) & {"black", "duplicate", "frozen", "too_short"}:
            bad_used.append({"file": rows[aid]["filename"], "issues": sh["issues"]})
    step("planning", seconds=round(time.perf_counter() - t, 3), segments=len(plan1.timeline), unique_shots=len(set(used)),
         same_take_reused=len(used) - len(set(used)), repeated_footage=repeated_footage, distinct_source_files=len({a for a, _ in used}), sections=[s.name for s in plan1.story_structure],
         unusable_shots_used=bad_used, reference_used=plan1.reference_profile_used, ending=plan1.ending.type)

    t = time.perf_counter()
    pv = S.render_version(p["id"], v1["id"], preview=True)
    step("preview", seconds=round(time.perf_counter() - t, 2), qc=pv["report"]["qc"]["passed"], qc_failures=pv["report"]["qc"]["failures"])
    t = time.perf_counter()
    f1 = S.render_version(p["id"], v1["id"], preview=False)
    q = f1["report"]["qc"]
    step("final_render", seconds=round(time.perf_counter() - t, 2), qc_passed=q["passed"], qc_failures=q["failures"], qc_warnings=q.get("warnings"),
         duration=q["probe"].get("duration"), resolution=f"{q['probe'].get('width')}x{q['probe'].get('height')}", fps=q["probe"].get("fps"),
         vcodec=q["probe"].get("vcodec"), acodec=q["probe"].get("acodec"), lufs=f1["report"]["audio"].get("integrated_lufs"),
         true_peak=f1["report"]["audio"].get("true_peak_db"), encoder=f1["report"].get("encoder"), timings=f1["report"]["timings"],
         segments_cached=f1["report"].get("segments_cached"), fallbacks=f1["report"].get("fallbacks"), output=f1["path"],
         reference_match=f1["report"].get("reference_match"), review=f1["report"].get("review"))
    renders = [pv, f1]
    if not args.no_revisions:
        for k, text in enumerate(REVISIONS, 1):
            t = time.perf_counter()
            v = S.revise(p["id"], text)
            noop = bool(v["changes"]) and all(c.get("noop") for c in v["changes"])
            r = None if noop else S.render_version(p["id"], v["id"])
            if r:
                renders.append(r)
            step(f"revision_{k}", text=text, seconds=round(time.perf_counter() - t, 2), ops=[c["op"] for c in v["changes"]], noop=noop,
                 qc=r["report"]["qc"]["passed"] if r else None, segments_cached=r["report"].get("segments_cached") if r else None,
                 segments=len(v["plan"]["timeline"]))
    sampler.stop_ = True
    sampler.join(2)
    rep["resources"] = {"peak_rss_mb": round(sampler.rss_peak / 2**20, 1), "cpu_percent_avg": round(sum(sampler.cpu) / max(1, len(sampler.cpu)), 1),
                        "cache": db.cache_stats(), "gpu": rep["environment"].get("gpu"), "hardware_encoding": rep["environment"].get("hardware_encoding")}
    rep["total_seconds"] = round(time.perf_counter() - t_all, 1)
    checks = {
        "all_inputs_accounted_for": rep["steps"]["upload"]["accepted"] + len(rejected_uploads) == sum(rep["inputs"].values()),
        "final_qc_passed": q["passed"],
        "duration_ok": abs((q["probe"].get("duration") or 0) - args.duration) < 0.3,
        "resolution_1080p": (q["probe"].get("width"), q["probe"].get("height")) == (1920, 1080),
        "no_unusable_shots_used": not bad_used,
        "no_repeated_footage": not repeated_footage,
        "all_renders_qc": all(r["report"]["qc"]["passed"] for r in renders),
    }
    rep["checks"], rep["passed"] = checks, all(checks.values())
    Path(args.out).write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(checks, indent=1))
    print("REAL ACCEPTANCE", "PASS" if rep["passed"] else "FAIL", f"in {rep['total_seconds']}s →", args.out)
    return 0 if rep["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
