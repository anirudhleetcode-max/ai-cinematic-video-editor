#!/usr/bin/env python3
"""Verify a Resolve harness run and produce the authoritative Resolve test results.

    python analyze_resolve_run.py --run <run_id> [--no-merge]

Reads 06_AUTOMATION/Validation/resolve_runs/<run_id>/harness_results.json, then
independently checks the evidence the harness produced:
  C  composition loading  (from the harness: insertion, macro found, published inputs
                           readable, expression probes evaluate and vary over time)
  D  Resolve render       ffprobe, 1920x1080, frame count, full decode, motion, no black
                          middle, exposure, entrance/exit change
  E  editable text/controls  API set/readback + still comparison: does changing the title
                          text / Impact Frame actually change the rendered image?
  F  visual comparison    Resolve render vs. the Python preview at six key frames
                          (scores + side-by-side sheet for human review)
Writes <run>/resolve_test_results.{json,md}, <run>/comparisons/*.jpg and (unless
--no-merge, never for mock runs) merges into 06_AUTOMATION/Validation/resolve_test_results.json.
Needs ffmpeg/ffprobe, numpy, opencv-python.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
VAL = os.path.join(ROOT, "06_AUTOMATION", "Validation")
CANON = os.path.join(VAL, "resolve_test_results.json")
FPS = 24


def ffprobe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", p],
                       capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None


def grab(p, frame, W=320, H=180, color=False):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.4f" % (frame / FPS), "-i", p, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "bgr24" if color else "gray", "-s", "%dx%d" % (W, H), "-"],
                         capture_output=True).stdout
    n = W * H * (3 if color else 1)
    if len(raw) != n:
        return None
    a = np.frombuffer(raw, np.uint8)
    return a.reshape(H, W, 3) if color else a.reshape(H, W).astype(np.float32)


def load_still(p, W=320, H=180):
    if not p or not os.path.exists(p):
        return None
    im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    return None if im is None else cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)


def corr(a, b):
    a = cv2.GaussianBlur(a, (0, 0), 2).ravel()
    b = cv2.GaussianBlur(b, (0, 0), 2).ravel()
    if a.std() < 1e-3 or b.std() < 1e-3:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def check_render(path, inv, expected):
    d = {"status": "FAIL", "errors": []}
    pr = ffprobe(path)
    if not pr:
        d["errors"].append("ffprobe failed")
        return d
    vs = [s for s in pr["streams"] if s["codec_type"] == "video"]
    if not vs:
        d["errors"].append("no video stream")
        return d
    v = vs[0]
    d["codec"], d["size"] = v.get("codec_name"), "%sx%s" % (v["width"], v["height"])
    d["fps"] = v.get("r_frame_rate")
    nb = int(v.get("nb_frames") or 0)
    d["frames"] = nb
    d["audio_stream"] = any(s["codec_type"] == "audio" for s in pr["streams"])
    if (v["width"], v["height"]) != (1920, 1080):
        d["errors"].append("size %s" % d["size"])
    if d["fps"] not in ("24/1", "24000/1000"):
        d["errors"].append("frame rate %s" % d["fps"])
    if nb and nb != expected:
        d["errors"].append("frames %d != %d" % (nb, expected))
    full = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"], capture_output=True, text=True)
    d["decode_clean"] = full.returncode == 0 and not full.stderr.strip()
    if not d["decode_clean"]:
        d["errors"].append("decode errors: " + full.stderr[:160])
    fr = inv["frames"]
    imgs = {k: grab(path, fr[k]) for k in ("build", "impact_plus3", "hold", "exit_mid", "end")}
    imgs["start"] = grab(path, 1)
    if any(x is None for x in imgs.values()):
        d["errors"].append("frame extraction failed")
        return d
    mid = [grab(path, f) for f in np.linspace(expected * 0.3, expected * 0.7, 6)]
    d["min_mid_luma"] = round(min(float(x.mean()) for x in mid), 2)
    if d["min_mid_luma"] <= 3.0:
        d["errors"].append("black middle section")
    h = imgs["hold"]
    d["hold_contrast"] = round(float(h.std()), 2)
    d["hold_clipped"] = round(float((h > 250).mean()), 4)
    if h.std() < 8:
        d["errors"].append("hold frame low contrast (title missing?)")
    if (h > 250).mean() >= 0.06:
        d["errors"].append("hold frame overexposed")
    d["entrance_diff"] = round(float(np.abs(imgs["start"] - h).mean()), 2)
    d["exit_diff"] = round(float(np.abs(imgs["end"] - h).mean()), 2)
    d["entrance"] = "PASS" if d["entrance_diff"] > 2 else "FAIL"
    d["exit"] = "PASS" if d["exit_diff"] > 2 else "FAIL"
    d["hold"] = "PASS" if h.std() >= 8 and (h > 250).mean() < 0.06 else "FAIL"
    if d["entrance"] == "FAIL":
        d["errors"].append("no visible entrance")
    if d["exit"] == "FAIL":
        d["errors"].append("no visible exit")
    d["status"] = "PASS" if not d["errors"] else "FAIL"
    return d


def compare_preview(resolve_mp4, preview_mp4, inv, out_jpg):
    keys = ("build", "impact", "impact_plus3", "hold", "exit_mid", "end")
    cols, scores = [], {}
    for k in keys:
        f = inv["frames"][k]
        a = grab(preview_mp4, f, 384, 216, color=True)
        b = grab(resolve_mp4, f, 384, 216, color=True)
        if a is None or b is None:
            continue
        ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
        scores[k] = {"luma_corr": round(corr(ga, gb), 3), "mean_luma_python": round(float(ga.mean()), 1),
                     "mean_luma_resolve": round(float(gb.mean()), 1),
                     "mean_rgb_dist": round(float(np.linalg.norm(a.reshape(-1, 3).mean(0) - b.reshape(-1, 3).mean(0))), 1)}
        cols.append(np.vstack([a, b]))
    if cols:
        sheet = np.hstack(cols)
        lab = np.zeros((28, sheet.shape[1], 3), np.uint8)
        cv2.putText(lab, "%s  top: Python preview   bottom: DaVinci Resolve render   (%s)" % (inv["id"], ", ".join(keys)),
                    (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.imwrite(out_jpg, np.vstack([lab, sheet]), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return scores


def overall(levels):
    st = [levels.get(k, {}).get("status") for k in ("C_load", "D_render", "E_edit")]
    if all(s == "PASS" for s in st):
        return "PASS"
    if any(s == "FAIL" for s in st):
        return "FAIL"
    if any(s == "BLOCKED" for s in st):
        return "BLOCKED"
    return "NOT TESTED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--no-merge", action="store_true")
    ap.add_argument("--runs-dir", default=os.path.join(VAL, "resolve_runs"))
    a = ap.parse_args()
    run_dir = os.path.join(a.runs_dir, a.run)
    h = json.load(open(os.path.join(run_dir, "harness_results.json"), encoding="utf-8"))
    inv = {t["id"]: t for t in json.load(open(os.path.join(HERE, "resolve_test_inventory.json"),
                                                encoding="utf-8"))["templates"]}
    conn = h.get("connection", {})
    os.makedirs(os.path.join(run_dir, "comparisons"), exist_ok=True)
    out = {"run_id": a.run, "mock": bool(h.get("mock")), "analyzed_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "connection": conn, "host": h.get("host"), "templates": {}}
    for tid, t in sorted(inv.items()):
        hr = h.get("templates", {}).get(tid)
        r = {"id": tid, "name": t["name"], "category": t["category"], "fusion_source": t["setting"], "levels": {}}
        if not conn.get("connected"):
            for k in ("C_load", "D_render", "E_edit", "F_visual"):
                r["levels"][k] = {"status": "BLOCKED", "detail": "no connection to DaVinci Resolve"}
            r["status"] = "BLOCKED"
            out["templates"][tid] = r
            continue
        if not hr:
            r["status"] = "NOT TESTED"
            out["templates"][tid] = r
            continue
        r["insert_path"] = hr.get("path")
        r["notes"] = hr.get("notes", [])
        r["errors"] = hr.get("errors", [])
        lv = hr.get("levels", {})
        r["levels"]["C_load"] = lv.get("C_load", {"status": "FAIL", "detail": "; ".join(r["errors"])[:300]})
        dr = lv.get("D_render", {})
        if dr.get("status") == "RENDERED" and dr.get("output"):
            mp4 = os.path.join(run_dir, dr["output"])
            dchk = check_render(mp4, t, t["duration_frames"])
            dchk["output"] = os.path.relpath(mp4, ROOT)
            dchk["render_seconds"] = dr.get("seconds")
            r["levels"]["D_render"] = dchk
            prev = os.path.join(ROOT, t["python_preview"])
            sc = compare_preview(mp4, prev, t, os.path.join(run_dir, "comparisons", "%s_compare.jpg" % tid))
            hc = sc.get("hold", {}).get("luma_corr")
            r["levels"]["F_visual"] = {"status": "COMPARED" if sc else "NOT TESTED", "scores": sc,
                                       "hold_luma_corr": hc,
                                       "flag": ("differs strongly from Python preview - review" if hc is not None and hc < 0.3
                                                else "similar structure" if hc is not None else None),
                                       "sheet": os.path.relpath(os.path.join(run_dir, "comparisons", "%s_compare.jpg" % tid), ROOT),
                                       "visual_review": "PENDING"}
        else:
            r["levels"]["D_render"] = {"status": "FAIL" if dr.get("status") == "FAIL" else "NOT TESTED",
                                       "detail": dr.get("detail")}
            r["levels"]["F_visual"] = {"status": "NOT TESTED"}
        ea = lv.get("E_edit_api", {})
        e = {"api": ea.get("status"), "main_title_set": ea.get("main_title_set"), "subtitle_set": ea.get("subtitle_set"),
             "controls_writable": "%s/%s" % (ea.get("controls_writable"), ea.get("controls_total")),
             "controls_failed": ea.get("controls_failed")}
        s0, s1 = load_still(ea.get("still_default_hold")), load_still(ea.get("still_test_title_hold"))
        if s0 is not None and s1 is not None:
            band = (slice(54, 126), slice(32, 288))
            e["text_change_pixel_diff"] = round(float(np.abs(s0[band] - s1[band]).mean()), 2)
            e["text_change_visible"] = e["text_change_pixel_diff"] > 1.0
        i0, i1 = load_still(ea.get("still_default_impact")), load_still(ea.get("still_moved_impact"))
        if i0 is not None and i1 is not None:
            e["impact_move_pixel_diff"] = round(float(np.abs(i0 - i1).mean()), 2)
            e["impact_control_visible"] = e["impact_move_pixel_diff"] > 0.5
        if ea.get("status") == "PASS" and e.get("text_change_visible") and e.get("impact_control_visible", True):
            e["status"] = "PASS"
        elif ea.get("status") == "PASS" and "text_change_visible" not in e:
            e["status"] = "PARTIAL"
            e["detail"] = "API edits verified; stills unavailable so the visual effect of the edit is unproven"
        elif ea:
            e["status"] = "FAIL"
        else:
            e["status"] = "NOT TESTED"
        r["levels"]["E_edit"] = e
        r["audio"] = "N/A - titles carry no audio in Resolve; sound design is supplied separately (cue sheets + SFX)"
        r["status"] = overall(r["levels"])
        out["templates"][tid] = r
    counts = {}
    for k in ("C_load", "D_render", "E_edit", "F_visual"):
        c = {}
        for r in out["templates"].values():
            s = r["levels"].get(k, {}).get("status", "NOT TESTED")
            c[s] = c.get(s, 0) + 1
        counts[k] = c
    so = {}
    for r in out["templates"].values():
        so[r["status"]] = so.get(r["status"], 0) + 1
    out["summary"] = {"levels": counts, "overall": so}
    json.dump(out, open(os.path.join(run_dir, "resolve_test_results.json"), "w", encoding="utf-8"), indent=1, default=str)
    L = ["# Resolve test run %s%s" % (a.run, " (MOCK - not real Resolve evidence)" if out["mock"] else ""), "",
         "Connection: %s" % (("%s %s" % (conn.get("product"), conn.get("version"))) if conn.get("connected") else "NOT CONNECTED"),
         "", "| Level | Counts |", "|---|---|"]
    for k, c in counts.items():
        L.append("| %s | %s |" % (k, ", ".join("%s %d" % kv for kv in sorted(c.items()))))
    L += ["| Overall | %s |" % ", ".join("%s %d" % kv for kv in sorted(so.items())), "",
          "| ID | Name | Path | C load | D render | E edit | F hold corr | Status | Errors/notes |", "|---|---|---|---|---|---|---|---|---|"]
    for tid, r in sorted(out["templates"].items()):
        lv = r["levels"]
        L.append("| %s | %s | %s | %s | %s | %s | %s | **%s** | %s |" % (
            tid, r["name"], r.get("insert_path") or "-", lv.get("C_load", {}).get("status", "-"),
            lv.get("D_render", {}).get("status", "-"), lv.get("E_edit", {}).get("status", "-"),
            lv.get("F_visual", {}).get("hold_luma_corr", "-"), r["status"],
            "; ".join((r.get("errors") or []) + (lv.get("D_render", {}).get("errors") or []) + (r.get("notes") or []))[:160]))
    open(os.path.join(run_dir, "resolve_test_results.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:12]))
    if out["mock"]:
        print("MOCK run: not merged into the canonical results.")
    elif not a.no_merge:
        canon = json.load(open(CANON, encoding="utf-8")) if os.path.exists(CANON) else {"templates": {}}
        for tid, r in out["templates"].items():
            if r["status"] != "NOT TESTED" or tid not in canon["templates"]:
                r["run_id"] = a.run
                canon["templates"][tid] = r
        canon["updated_at"] = out["analyzed_at"]
        canon["last_run"] = a.run
        canon["last_connection"] = conn
        json.dump(canon, open(CANON, "w", encoding="utf-8"), indent=1, default=str)
        print("merged into", os.path.relpath(CANON, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
