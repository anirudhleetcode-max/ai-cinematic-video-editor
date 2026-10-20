"""v4 pipeline driver: each stage is resumable and skips work that already exists.

usage: EDIT_WORK=/scratch python3 pipeline.py <stage> [...]
  prep      source + slow-motion plate + beat grid + analysis cache
  stills    contact sheet of story moments  (output/v4/review/stills.jpg)
  proto     a b name   full-res motion prototype of frames [a, b)
  render    full render in resumable chunks + render manifest
  master    join chunks + original soundtrack -> $EDIT_WORK/v4_master.mp4
  deliver   two-pass delivery encode -> output/v4/cinematic_doodle_music_edit_v4.mp4
  qc        automated QC of the delivery file (qc.py)
  all       every stage in order
Config overrides: EDIT_V4_SET="outline.width_px=4;paint.intensity=0.8"
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
WORK = os.environ.setdefault("EDIT_WORK", os.path.join(ROOT, "work"))
SRC = os.environ.setdefault("EDIT_SOURCE", os.path.join(WORK, "source.mov"))
OUT = os.path.join(ROOT, "output", "v4")
SOURCE_COMMIT = "b3437ef"          # input/source.mov on claude/friendly-fermi-jn4h4o


def run(cmd, **kw):
    print("+", " ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    subprocess.run(cmd, check=True, **kw)


def prep():
    os.makedirs(WORK, exist_ok=True)
    if not os.path.exists(SRC):
        with open(SRC, "wb") as fh:
            subprocess.run(["git", "show", f"{SOURCE_COMMIT}:input/source.mov"], cwd=ROOT, stdout=fh, check=True)
    slow = os.path.join(WORK, "slowmo.mp4")
    if not os.path.exists(slow):
        run(["ffmpeg", "-v", "error", "-y", "-i", SRC, "-an", "-vf",
             "trim=start_frame=2648:end_frame=3032,setpts=(PTS-STARTPTS)*639/384,"
             "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
             "-frames:v", "639", "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p", slow])
    beats = os.path.join(WORK, "beats.json")
    if not os.path.exists(beats):
        sys.path.insert(0, os.path.join(HERE, ".."))
        import analyze
        a = analyze.analyse_audio()
        with open(beats, "w") as fh:
            json.dump({"audio": {"bpm": a["bpm"], "beats": a["beats"], "downbeat_phase": a["downbeat_phase"]}}, fh)
    if not os.path.exists(os.path.join(WORK, "v3_analysis.npz")):
        run([sys.executable, os.path.join(HERE, "..", "v3", "analyze_v3.py")])


def stills(times=(2.5, 9.6, 11.4, 23.0, 30.4, 35.0, 42.6, 55.8, 63.0, 74.0, 84.0, 90.5, 94.5, 98.9, 104.5, 109.8,
                  111.5, 112.8)):
    import cv2
    import numpy as np
    sys.path.insert(0, HERE)
    import render_v4 as R
    from common import read_frames
    os.makedirs(os.path.join(OUT, "review"), exist_ok=True)
    tiles = []
    for t in times:
        f = int(t * 30)
        o, _ = R.render_frame(next(read_frames(f, f + 1)).copy(), f, None)
        tile = cv2.resize(o, (640, 360), interpolation=cv2.INTER_AREA)
        cv2.putText(tile, f"{t:.1f}s  {R.E.TL.section(t)}", (10, 28), 0, 0.7, (255, 255, 255), 2)
        tiles.append(tile)
    while len(tiles) % 3:
        tiles.append(tiles[0] * 0)
    cv2.imwrite(os.path.join(OUT, "review", "stills.jpg"),
                np.vstack([np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]), [cv2.IMWRITE_JPEG_QUALITY, 88])


def proto(a, b, name):
    run([sys.executable, os.path.join(HERE, "render_v4.py"), str(a), str(b), name])
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(WORK, f"{name}.txt"),
         "-c", "copy", os.path.join(WORK, f"proto4_{name}.mp4")])


def render():
    run([sys.executable, os.path.join(HERE, "render_v4.py")])
    sys.path.insert(0, HERE)
    import render_v4 as R
    R.manifest(os.path.join(OUT, "render_manifest.json"))


def master():
    dur = 3396 / 30
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(WORK, "v4chunk.txt"),
         "-i", SRC, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-af", f"atrim=0:{dur},afade=t=in:d=0.3,afade=t=out:st={dur - 1.0}:d=1.0",
         "-c:a", "aac", "-b:a", "256k", "-t", str(dur), "-movflags", "+faststart",
         os.path.join(WORK, "v4_master.partial.mp4")])
    os.replace(os.path.join(WORK, "v4_master.partial.mp4"), os.path.join(WORK, "v4_master.mp4"))


def deliver(kbps=None):
    with open(os.path.join(HERE, "config.json")) as fh:
        cfg = json.load(fh)
    kbps = kbps or cfg["render"]["delivery_video_kbps"]
    m = os.path.join(WORK, "v4_master.mp4")
    tmp = os.path.join(OUT, ".cinematic_doodle_music_edit_v4.partial.mp4")
    log = os.path.join(WORK, "v4pass")
    run(["ffmpeg", "-v", "error", "-y", "-i", m, "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k",
         "-pass", "1", "-passlogfile", log, "-an", "-f", "null", "/dev/null"])
    run(["ffmpeg", "-v", "error", "-y", "-i", m, "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k",
         "-maxrate", f"{int(kbps * 1.6)}k", "-bufsize", f"{int(kbps * 2.4)}k", "-pass", "2", "-passlogfile", log,
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", tmp])
    os.replace(tmp, os.path.join(OUT, "cinematic_doodle_music_edit_v4.mp4"))


def qc():
    run([sys.executable, os.path.join(HERE, "qc.py"), os.path.join(OUT, "cinematic_doodle_music_edit_v4.mp4"),
         os.path.join(WORK, "v4_master.mp4"), os.path.join(OUT, "qc_results.json")])


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    if st == "proto":
        proto(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    elif st == "all":
        for fn in (prep, render, master, deliver, qc):
            fn()
    else:
        globals()[st]()
