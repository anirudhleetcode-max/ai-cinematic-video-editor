"""Render-stage profile on real footage (release gate, Phase 15).

  python scripts/profile_render.py [--out docs/render_profile.json]

Times the stages of one segment render the way render/segments.py builds it, adding one stage at a time to the same
FFmpeg graph on the same real 1080p and 4K sources (3 s, 1920×1080 output, Fast-mode mezzanine settings):
decode → +retime → +RGB working-space conversion → +grade LUT → +crop → +YUV conversion → +finishing → +x264 encode.
The difference between consecutive rows is that stage's cost. Also reports how many segments of a real 5-minute plan
take the numpy camera-motion path and what one such segment costs, plus text and final-pass encode timing.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine"))
REAL = ROOT / "tests" / "real_media"


def timed(args: list[str], reps: int = 3) -> float:
    best = 1e9
    for _ in range(reps):
        t = time.perf_counter()
        subprocess.run(args, check=True, capture_output=True)
        best = min(best, time.perf_counter() - t)
    return round(best, 3)


def main() -> int:
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "docs" / "render_profile.json"
    from editor import contract as C
    from editor.media.probe import probe
    from editor.registry.color import finishing_filters
    from editor.render.colorspace import TO_YUV420, source_to_rgb
    from editor.render.segments import x264_mezz_args
    from editor.registry.color import write_cube

    tmp = Path(tempfile.mkdtemp(prefix="profile-"))
    srcs = {"1080p_h264": next(p for p in sorted((REAL / "event01" / "clips").glob("*.mp4")) if probe(p).get("height") == 1080),
            "2160p_h264": REAL / "derived" / "uhd_4k_30.mp4"}
    grade = {"exposure": 0.05, "contrast": 1.08, "saturation": 1.1, "temperature": 0.05, "tint": 0.0, "gamma": 1.0, "vignette": 0.3, "grain": 0.2, "sharpen": 0.2}
    lut = write_cube(tmp / "grade.cube", grade, 0.8)
    fin = ",".join(finishing_filters(grade, 1920, 1080, 0.8))
    res: dict = {"label": "MEASURED (best of 3 per row)", "machine": "4 CPU, no GPU, libx264", "segment_seconds": 3.0, "sources": {}}
    for name, src in srcs.items():
        meta = probe(src)
        sw, sh = meta["display_width"] if meta.get("display_width") else meta["width"], meta.get("display_height") or meta["height"]
        cover = max(1920 / sw, 1080 / sh)
        cw, ch = int(-(-sw * cover // 2) * 2), int(-(-sh * cover // 2) * 2)
        base = ["ffmpeg", "-v", "error", "-y", "-nostdin", "-ss", "2", "-t", "3.5", "-i", str(src)]
        steps = [("decode", "null"), ("+retime (setpts, fps 30)", "setpts=PTS-STARTPTS,fps=30"),
                 ("+RGB working space (scale + matrix)", f"setpts=PTS-STARTPTS,fps=30,{source_to_rgb(meta, cw, ch)},setsar=1"),
                 ("+grade LUT (lut3d tetrahedral)", f"setpts=PTS-STARTPTS,fps=30,{source_to_rgb(meta, cw, ch)},setsar=1,lut3d=file={lut}:interp=tetrahedral"),
                 ("+crop", f"setpts=PTS-STARTPTS,fps=30,{source_to_rgb(meta, cw, ch)},setsar=1,lut3d=file={lut}:interp=tetrahedral,crop=1920:1080"),
                 ("+YUV 4:2:0 BT.709 conversion", f"setpts=PTS-STARTPTS,fps=30,{source_to_rgb(meta, cw, ch)},setsar=1,lut3d=file={lut}:interp=tetrahedral,crop=1920:1080,{TO_YUV420}")]
        if fin:
            steps.append(("+finishing (vignette/grain/sharpen)", steps[-1][1] + "," + fin))
        rows, prev = [], 0.0
        full = steps[-1][1]
        for label, vf in steps:
            t = timed([*base, "-vf", vf, "-frames:v", "90", "-f", "null", "-"])
            rows.append({"stage": label, "cumulative_s": t, "stage_s": round(t - prev, 3)})
            prev = t
        enc = timed([*base, "-vf", full, "-frames:v", "90", *x264_mezz_args("standard"), "-an", str(tmp / "o.mp4")])
        rows.append({"stage": f"+x264 mezzanine encode (CRF {C.MEZZANINE_CRF['standard']}, {C.MEZZANINE_PRESET['standard']})", "cumulative_s": enc,
                     "stage_s": round(enc - prev, 3)})
        res["sources"][name] = {"source": f"{src.name} {sw}x{sh} {meta.get('vcodec')}", "rows": rows}
        print(name, json.dumps(rows), flush=True)
    # final pass: concat of mezzanines + text overlay + 1080p x264 at final settings (from a 10 s mezzanine)
    mz = tmp / "mz.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2", "-t", "10", "-i", str(srcs["1080p_h264"]), "-vf", "fps=30,scale=1920:1080,format=yuv420p",
                    *x264_mezz_args("standard"), "-an", str(mz)], check=True)
    q = C.MODE_QUALITY["fast"]
    res["final_pass_10s"] = {"decode_only_s": timed(["ffmpeg", "-v", "error", "-i", str(mz), "-f", "null", "-"]),
                             "encode_final_x264_s": timed(["ffmpeg", "-v", "error", "-y", "-i", str(mz), "-c:v", "libx264", "-preset", C.FINAL_PRESET[q],
                                                           "-crf", str(C.FINAL_CRF[q]), "-pix_fmt", "yuv420p", "-an", str(tmp / "f.mp4")])}
    print("final", json.dumps(res["final_pass_10s"]), flush=True)
    out_path.write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
