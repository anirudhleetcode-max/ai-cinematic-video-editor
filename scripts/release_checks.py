"""Release-gate regression checks on REAL footage (docs/RELEASE_REPORT.md, Phase 7).

  python scripts/release_checks.py [--data DIR] [--out docs/release_checks.json] [--frames DIR]

A dialogue      presenter/pitch footage → phrase-led edit, no sub-second chopping, speech ducking, loudness
B negatives     "no dogs", "avoid people", "don't use dark clips", "avoid blurry footage" → excluded or relaxation reported
C transitions   real hard cuts / fade-in / fade-out / dissolve built from real clips; false transitions in normal footage
D LUT           a known channel-swap .cube changes the real render the way the LUT says
E colour        BT.709 / BT.601 / full range / limited range / phone + screen recording / HLG: neutral render vs a
                reference decode of the source (signed mean shift per channel)
F audio         dialogue + music + clip without audio + mixed sample rates → loudness, true peak, clipping

Every number comes from this run. Inputs derived on the fly (SD/BT.601, full-range, no-audio, transition test files)
are made from the real clips with FFmpeg and are labelled as derived.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "tests" / "real_media"
EVENT = REAL / "event01"
sys.path.insert(0, str(ROOT / "services" / "engine"))
sys.path.insert(0, str(ROOT / "scripts"))


def ff(*a: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def probe(path: Path, entries: str, stream: str = "v:0") -> list[str]:
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", entries, "-of", "csv=p=0", str(path)],
                          capture_output=True, text=True).stdout.strip().split(",")


def rgb_frame(path: Path, t: float, w: int, h: int, matrix: str, rng: str) -> np.ndarray:
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                        "-vf", f"scale={w}:{h}:in_color_matrix={matrix}:in_range={rng}:flags=area,format=rgb24", "-f", "rawvideo", "-"],
                       capture_output=True, check=True)
    if len(p.stdout) < w * h * 3:
        raise RuntimeError(f"no frame at {t:.2f}s in {path.name}")
    return np.frombuffer(p.stdout[: w * h * 3], np.uint8).reshape(h, w, 3).astype(float)


def loudness(path: Path) -> dict:
    p = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    tail = p.stderr[p.stderr.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", tail)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    s = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "astats=measure_overall=Peak_level+Number_of_samples:measure_perchannel=none",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    pk = re.search(r"Peak level dB:\s+(-?[\d.inf]+)", s)
    # samples at (or within 0.01 dB of) digital full scale
    clip = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "astats=measure_perchannel=Number_of_Inf+Peak_count:measure_overall=none",
                           "-f", "null", "-"], capture_output=True, text=True).stderr
    pc = [int(x) for x in re.findall(r"Peak count:\s+(\d+)", clip)]
    return {"integrated_lufs": float(i.group(1)) if i else None, "true_peak_dbtp": float(tp.group(1)) if tp else None,
            "sample_peak_db": float(pk.group(1)) if pk and pk.group(1) not in ("-inf", "inf") else None, "peak_count_per_channel": pc}


def save_frames(path: Path, dest: Path, label: str, times: list[float]) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for t in times:
        f = dest / f"{label}_{t:06.2f}.jpg"
        ff("-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "3", str(f))
        out.append(str(f))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    ap.add_argument("--out", default=str(ROOT / "docs" / "release_checks.json"))
    ap.add_argument("--frames", default=str(Path(tempfile.gettempdir()) / "cutroom-release-frames"))
    ap.add_argument("--only", nargs="*", default=None, help="subset of A B C D E F")
    a = ap.parse_args()
    os.environ.setdefault("EDITOR_DATA_DIR", a.data or tempfile.mkdtemp(prefix="release-checks-"))
    from editor import db, service as S
    from editor.director.context import ProjectContext  # noqa: F401
    from editor.render.engine import render_plan
    from editor.retrieval import shot_labels
    from editor.schemas import CreativeBible, EditPlan, Ending, ExportSpec, Segment, StorySection
    from real_acceptance import discover

    work = Path(tempfile.mkdtemp(prefix="release-work-"))
    frames = Path(a.frames)
    report: dict = {"label": "MEASURED on real footage (derived inputs labelled)", "started": time.time(), "checks": {}}
    want = set(a.only or "ABCDEF")
    roles = discover(EVENT)
    clips = sorted(roles["clip"])
    plain = [c for c in clips if not c.name.startswith("derived_")]

    def seconds(f: Path) -> float:
        try:
            return float(probe(f, "format=duration")[0])
        except (ValueError, IndexError):
            return 0.0

    long_clips = [c for c in plain if seconds(c) >= 8.0]  # transition / colour inputs need ≥ 5 s of material

    def save():
        Path(a.out).write_text(json.dumps(report, indent=1, default=str))

    def single_segment_render(pid: str, asset_id: str, src_in: float, dur: float, out: Path, lut_id: str | None = None) -> Path:
        plan = EditPlan(duration=dur, bible=CreativeBible(style="check", color="neutral", typography="none", transition_philosophy="cuts",
                                                          effect_philosophy="none", pacing="medium", music_strategy="none", story_structure=["main"]),
                        story_structure=[StorySection(name="main", start=0, end=dur)], ending=Ending(type="cut", duration=0),
                        timeline=[Segment(id="s0", asset_id=asset_id, src_in=src_in, src_out=src_in + dur, out_start=0, out_duration=dur, keep_audio=False)],
                        export=ExportSpec(width=640, height=360, quality="high", prefer_hw=False))
        plan.color_grade.intensity = 0.0
        plan.color_grade.match_shots = False
        if lut_id:
            plan.color_grade.lut_asset_id = lut_id
        render_plan(plan, S._asset_infos(pid), out, work / f"w_{out.stem}")
        return out

    # ------------------------------------------------------------------ A dialogue
    if "A" in want:
        t0 = time.time()
        p = S.create_project("release A dialogue")
        user = sorted((REAL / "user").glob("*.mp4"))
        for f in user:
            with open(f, "rb") as fh:
                S.add_asset(p["id"], f.name, fh, "clip")
        song = sorted((REAL / "library" / "music").glob("*.*"))[0]
        with open(song, "rb") as fh:
            S.add_asset(p["id"], song.name, fh, "music")
        S.analyze_project(p["id"], "fast")
        prompt = ("Create a 40-second pitch video. Keep the presenter's speech intelligible and complete, show the app demo, "
                  "duck the music under speech, clean natural colour.")
        v = S.create_edit_plan(p["id"], prompt, "fast")
        r = S.render_version(p["id"], v["id"], preview=False)
        tl = v["plan"]["timeline"]
        durs = [s["out_duration"] for s in tl]
        rep = r["report"]
        aud = rep.get("audio") or {}
        lo = loudness(Path(r["path"]))
        speech_s = float(aud.get("speech_seconds") or 0)
        res = {"editing_mode": v["plan"].get("editing_mode"), "segments": len(tl), "min_shot_s": round(min(durs), 2), "median_shot_s": round(float(np.median(durs)), 2),
               "sub_second_shots": sum(d < 1.0 for d in durs), "speech_seconds": speech_s, "ducked_seconds": aud.get("ducked_seconds"),
               "report_loudness_lufs": aud.get("integrated_lufs"), "measured": lo, "qc_passed": rep["qc"]["passed"],
               "review": (rep.get("review") or {}).get("summary"), "seconds": round(time.time() - t0, 1),
               "frames": save_frames(Path(r["path"]), frames, "A_dialogue", [0.5, 8, 16, 24, 32, 39])}
        res["pass"] = bool(res["editing_mode"] == "dialogue" and res["sub_second_shots"] == 0 and res["min_shot_s"] >= 2.0 and speech_s > 5
                           and res["qc_passed"] and lo["true_peak_dbtp"] is not None and lo["true_peak_dbtp"] <= -0.9)
        report["checks"]["A_dialogue"] = res
        print("A", json.dumps({k: v_ for k, v_ in res.items() if k != "frames"}, default=str), flush=True)
        save()

    # ------------------------------------------------------------------ B negative requests
    if "B" in want:
        t0 = time.time()
        p = S.create_project("release B negatives")
        for f in clips:
            try:
                with open(f, "rb") as fh:
                    S.add_asset(p["id"], f.name, fh, "clip")
            except ValueError:
                pass
        with open(sorted(roles["music"])[0], "rb") as fh:
            S.add_asset(p["id"], "song.mp3", fh, "music")
        S.analyze_project(p["id"], "fast")
        base = S.create_edit_plan(p["id"], "A 45 second energetic event recap cut to the music", "fast")
        shots = {}
        for row in db.query("SELECT id, analysis FROM assets WHERE project_id=? AND role='clip'", (p["id"],)):
            for i, sh in enumerate((row["analysis"] or {}).get("shots", [])):
                shots[(row["id"], sh.get("index", i))] = sh
        tests = {"no dogs": lambda sh: "dog" in shot_labels(sh),
                 "avoid people": lambda sh: bool(shot_labels(sh) & {"people", "faces", "person", "group", "crowd"}),
                 "don't use dark clips": lambda sh: "underexposed" in sh.get("issues", []) or "dark" in shot_labels(sh),
                 "avoid blurry footage": lambda sh: "blurry" in sh.get("issues", [])}
        out = {}
        for text, match in tests.items():
            matching = {k for k, sh in shots.items() if match(sh)}

            def used(plan):
                return [(s["asset_id"], s["shot_index"]) for s in plan["timeline"]]

            before = sum(k in matching for k in used(base["plan"]))
            v = S.revise(p["id"], text, base["id"])
            after_keys = used(v["plan"])
            after = sum(k in matching for k in after_keys)
            ops = [c for c in v["changes"] if c["op"] in ("prefer_query", "avoid_issue")]
            relaxed = any(c.get("relaxed") for c in ops)
            noop = bool(ops) and all(c.get("noop") for c in ops)
            alternatives = len(set(shots) - matching)
            ok = bool(ops) and (after == 0 or relaxed) and (not noop or not matching)
            out[text] = {"ops": [{k: c.get(k) for k in ("op", "issue", "labels", "weight", "noop", "reason", "relaxed")} for c in ops],
                         "matching_shots_in_footage": len(matching), "other_shots": alternatives, "segments_matching_before": before,
                         "segments_matching_after": after, "segments_after": len(after_keys), "relaxation_reported": relaxed, "pass": ok}
            print("B", text, json.dumps(out[text], default=str), flush=True)
        report["checks"]["B_negative_requests"] = {"results": out, "seconds": round(time.time() - t0, 1), "pass": all(x["pass"] for x in out.values())}
        save()

    # ------------------------------------------------------------------ C transitions
    if "C" in want:
        from editor.reference.analyze import analyze_reference

        t0 = time.time()
        A_, B_ = long_clips[0], long_clips[5]
        mk = work / "trans"
        mk.mkdir(exist_ok=True)
        norm = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p"
        a_, b_ = mk / "a.mp4", mk / "b.mp4"
        ff("-ss", "1", "-t", "4", "-i", str(A_), "-an", "-vf", norm, "-c:v", "libx264", "-crf", "16", str(a_))
        ff("-ss", "1", "-t", "4", "-i", str(B_), "-an", "-vf", norm, "-c:v", "libx264", "-crf", "16", str(b_))
        cases = {
            "hard_cut": ["-i", str(a_), "-i", str(b_), "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]"],
            "fade_out_then_in": ["-i", str(a_), "-i", str(b_), "-filter_complex",
                                 "[0:v]fade=t=out:st=3.4:d=0.6[x];[1:v]fade=t=in:st=0:d=0.6[y];[x][y]concat=n=2:v=1[v]", "-map", "[v]"],
            "fade_in_after_cut": ["-i", str(a_), "-i", str(b_), "-filter_complex", "[1:v]fade=t=in:st=0:d=0.5[y];[0:v][y]concat=n=2:v=1[v]", "-map", "[v]"],
            "dissolve": ["-i", str(a_), "-i", str(b_), "-filter_complex", "[0:v][1:v]xfade=transition=dissolve:duration=1.0:offset=3[v]", "-map", "[v]"],
        }
        res = {}
        for name, args in cases.items():
            f = mk / f"{name}.mp4"
            ff(*args, "-c:v", "libx264", "-crf", "16", str(f))
            r = analyze_reference(f, light=True)
            res[name] = {"transition_types": r["transition_types"], "n_shots": r["n_shots"]}
        res["hard_cut"]["pass"] = set(res["hard_cut"]["transition_types"]) <= {"cut"}
        res["fade_out_then_in"]["pass"] = res["fade_out_then_in"]["transition_types"].get("fade", 0) >= 1
        res["fade_in_after_cut"]["pass"] = res["fade_in_after_cut"]["transition_types"].get("fade", 0) >= 1
        res["dissolve"]["pass"] = (res["dissolve"]["transition_types"].get("dissolve", 0) + res["dissolve"]["transition_types"].get("fade", 0)) >= 1 \
            and res["dissolve"]["transition_types"].get("cut", 0) <= 1
        # the real reference montage (hard cuts only, by construction)
        ref = sorted(roles["reference"])[0]
        rr = analyze_reference(ref)
        res["real_reference_hard_cuts_only"] = {"transition_types": rr["transition_types"], "pass": set(rr["transition_types"]) <= {"cut"}}
        # false gradual transitions inside normal real footage
        false_tr, n_bound = 0, 0
        for c in plain[:20]:
            r = analyze_reference(c, light=True)
            n_bound += sum(r["transition_types"].values())
            false_tr += sum(v for k, v in r["transition_types"].items() if k != "cut")
        res["normal_footage"] = {"clips": min(20, len(plain)), "boundaries": n_bound, "gradual_transitions_detected": false_tr,
                                 "pass": false_tr <= 1}
        report["checks"]["C_transitions"] = {"results": res, "seconds": round(time.time() - t0, 1), "pass": all(v["pass"] for v in res.values())}
        print("C", json.dumps(res, default=str), flush=True)
        save()

    # ------------------------------------------------------------------ D LUT + E colour
    if "D" in want or "E" in want:
        t0 = time.time()
        p = S.create_project("release DE colour")
        src_709 = long_clips[2]
        der = work / "colour"
        der.mkdir(exist_ok=True)
        bt601 = der / "derived_bt601_sd.mp4"
        ff("-ss", "1", "-t", "3", "-i", str(src_709), "-an", "-vf", "scale=720:480:out_color_matrix=bt601:out_range=tv,setsar=1,format=yuv420p",
           "-colorspace", "smpte170m", "-color_primaries", "smpte170m", "-color_trc", "smpte170m", "-color_range", "tv", "-c:v", "libx264", "-crf", "10", str(bt601))
        full = der / "derived_full_range.mp4"
        ff("-ss", "1", "-t", "3", "-i", str(src_709), "-an", "-vf", "scale=out_color_matrix=bt709:out_range=pc,format=yuvj420p",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "pc", "-c:v", "libx264", "-crf", "10", str(full))
        sources = {"bt709_limited (real)": (src_709, "bt709", "tv"), "bt601_sd (derived from real)": (bt601, "bt601", "tv"),
                   "full_range (derived from real)": (full, "bt709", "pc")}
        for f in sorted((REAL / "user").glob("*.mp4")):
            sp, rg = probe(f, "stream=color_space,color_range")[:2] if probe(f, "stream=color_space,color_range") else ("", "")
            m = "bt601" if sp in ("smpte170m", "bt470bg") else "bt709"
            sources[f"phone {f.name[-12:-4]} ({sp or 'untagged'}, {rg or 'unknown'} range) (real)"] = (f, m, "pc" if rg == "pc" else "tv")
        hlg = REAL / "derived" / "uhd_4k_hevc10_hlg.mp4"
        ids = {}
        for label, (f, _, _) in sources.items():
            with open(f, "rb") as fh:
                ids[label] = S.add_asset(p["id"], f.name, fh, "clip")["id"]
        with open(hlg, "rb") as fh:
            hlg_id = S.add_asset(p["id"], hlg.name, fh, "clip")["id"]
        colour = {}
        if "E" in want:
            for label, (f, matrix, rng) in sources.items():
                src_in = 0.5 if "derived" in label else 1.0
                out = single_segment_render(p["id"], ids[label], src_in, 1.5, der / f"o_{len(colour)}.mp4")
                diffs = []
                for t in (0.3, 0.8, 1.2):
                    o = rgb_frame(out, t, 160, 90, "bt709", "tv")
                    s_ = rgb_frame(f, src_in + t, 160, 90, matrix, rng)
                    diffs.append(o - s_)
                d = np.stack(diffs)
                shift = d.mean(axis=(0, 1, 2))
                colour[label] = {"signed_mean_shift_rgb": [round(float(x), 2) for x in shift], "mean_abs_rgb": round(float(np.abs(d).mean()), 2),
                                 "output_tags": probe(out, "stream=color_space,color_primaries,color_transfer,color_range"),
                                 "pass": bool(np.abs(shift).max() <= 3.0)}
            out = single_segment_render(p["id"], hlg_id, 1.0, 1.5, der / "o_hlg.mp4")
            o = rgb_frame(out, 0.8, 160, 90, "bt709", "tv")
            colour["hlg_10bit_hevc (derived; tone-mapped by design)"] = {"output_mean_rgb": [round(float(x), 1) for x in o.mean(axis=(0, 1))],
                                                                         "output_tags": probe(out, "stream=color_space,color_primaries,color_transfer,color_range"),
                                                                         "pass": bool(5 < o.mean() < 250), "note": "HDR→SDR tone-map changes values by design; checked for a valid, non-clipped SDR picture"}
            report["checks"]["E_colour"] = {"results": colour, "pass": all(v["pass"] for v in colour.values())}
            print("E", json.dumps(colour, default=str), flush=True)
        if "D" in want:
            lut = der / "swap_rb.cube"
            n = 9
            lut.write_text(f"LUT_3D_SIZE {n}\n" + "\n".join(f"{b / (n - 1):.5f} {g / (n - 1):.5f} {r / (n - 1):.5f}"
                                                            for b in range(n) for g in range(n) for r in range(n)) + "\n")
            with open(lut, "rb") as fh:
                lut_id = S.add_asset(p["id"], lut.name, fh, "lut")["id"]
            lab = "bt709_limited (real)"
            o0 = single_segment_render(p["id"], ids[lab], 1.0, 1.5, der / "lut_off.mp4")
            o1 = single_segment_render(p["id"], ids[lab], 1.0, 1.5, der / "lut_on.mp4", lut_id)
            a0, a1 = rgb_frame(o0, 0.8, 160, 90, "bt709", "tv"), rgb_frame(o1, 0.8, 160, 90, "bt709", "tv")
            swap_err = float(np.abs(a1 - a0[..., ::-1]).mean())
            change = float(np.abs(a1 - a0).mean())
            rb_gap = float(np.abs(a0[..., 0] - a0[..., 2]).mean())
            report["checks"]["D_lut"] = {"source": lab, "mean_abs_change_vs_no_lut": round(change, 2), "mean_abs_error_vs_expected_swap": round(swap_err, 2),
                                         "source_mean_abs_red_blue_gap": round(rb_gap, 2), "pass": swap_err <= 6.0 and change >= 0.5 * rb_gap and rb_gap > 4,
                                         "frames": save_frames(o0, frames, "D_lut_off", [0.8]) + save_frames(o1, frames, "D_lut_on", [0.8])}
            print("D", json.dumps(report["checks"]["D_lut"], default=str), flush=True)
        report["checks"]["DE_seconds"] = round(time.time() - t0, 1)
        save()

    # ------------------------------------------------------------------ F audio
    if "F" in want:
        t0 = time.time()
        p = S.create_project("release F audio")
        der = work / "audio"
        der.mkdir(exist_ok=True)
        noaudio = der / "derived_no_audio.mp4"
        ff("-ss", "0", "-t", "6", "-i", str(long_clips[3]), "-an", "-c:v", "copy", str(noaudio))
        files = [REAL / "derived" / "speech_over_real_video.mp4", noaudio, REAL / "derived" / "container_mjpeg.avi", long_clips[4], long_clips[6], long_clips[8]]
        rates = {}
        for f in files:
            rates[f.name] = (probe(f, "stream=sample_rate,channels", "a:0") or ["none"])
            with open(f, "rb") as fh:
                S.add_asset(p["id"], f.name, fh, "clip")
        music = REAL / "derived" / "audio" / "sugar_plum_fairy.flac"
        rates[music.name] = probe(music, "stream=sample_rate,channels", "a:0")
        with open(music, "rb") as fh:
            S.add_asset(p["id"], music.name, fh, "music")
        S.analyze_project(p["id"], "fast")
        v = S.create_edit_plan(p["id"], "A 30 second story: keep the narration audible, music underneath and ducked under speech", "fast")
        r = S.render_version(p["id"], v["id"], preview=False)
        lo = loudness(Path(r["path"]))
        aud = r["report"].get("audio") or {}
        target = v["plan"]["audio"]["target_lufs"]
        res = {"input_audio (sample_rate,channels)": rates, "target_lufs": target, "measured": lo, "report": {k: aud.get(k) for k in
               ("integrated_lufs", "true_peak_db", "speech_seconds", "ducked_seconds")}, "output_audio": probe(Path(r["path"]), "stream=sample_rate,channels,codec_name", "a:0"),
               "qc_passed": r["report"]["qc"]["passed"], "seconds": round(time.time() - t0, 1)}
        res["pass"] = bool(lo["integrated_lufs"] is not None and abs(lo["integrated_lufs"] - target) <= 1.0 and lo["true_peak_dbtp"] <= -0.9
                           and (lo["sample_peak_db"] is None or lo["sample_peak_db"] < -0.5) and res["qc_passed"])
        report["checks"]["F_audio"] = res
        print("F", json.dumps(res, default=str), flush=True)
        save()

    report["finished"] = time.time()
    report["pass"] = all(v.get("pass", True) for v in report["checks"].values() if isinstance(v, dict))
    save()
    print("RELEASE CHECKS", "PASSED" if report["pass"] else "FAILED")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
