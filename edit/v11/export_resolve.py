"""Export the v11 edit as an editable DaVinci Resolve package.

Writes output/v11/resolve/:
  media/shots/<id>.mp4        each shot as rendered (doodle world, outline, stickers,
                              cut-out), including its transition overlap frames
  media/transitions/<n>.mp4   each transition exactly as rendered (iris, whip, zoom,
                              brush, light leak, dissolve, final fade)
  media/audio/OK_Kanmani_Song.wav  the song, decoded to 48 kHz PCM (exact length, no MP3 encoder delay)
  timeline.json               frame-exact layout (the single source for the files below)
  OK_Kanmani_v11.fcpxml       FCPXML 1.8 timeline (File > Import > Timeline)
  OK_Kanmani_v11_V1.edl       CMX3600 EDL of the cuts track (fallback)
  build_resolve_project.py    run inside Resolve (Workspace > Scripts): creates the project,
                              imports the media and builds the timeline

Layout: V1 has the 19 shots on hard cuts at the exact cut frames; V2 has the transitions
over the cuts (disable V2 to see bare cuts, or swap in Resolve transitions); A1 has the song.
V1 plus V2 reproduces output/v11/cute_doodle_ok_kanmani_v11.mp4 frame for frame.

Usage: EDIT_WORK=... python3 export_resolve.py
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
WORK = os.environ["EDIT_WORK"]
EDL = json.load(open(os.path.join(HERE, "edl.json")))
FINAL = os.path.join(REPO, "output", "v11", "cute_doodle_ok_kanmani_v11.mp4")
AUDIO = os.environ.get("V11_AUDIO", os.path.join(WORK, "v11", "OK_Kanmani_Song.mp3"))
PKG = os.path.join(REPO, "output", "v11", "resolve")
W, H, FPS, FRAMES = 1920, 1080, 30, EDL["frames"]


def shot_range(sh):
    a, b = sh["start"], sh["end"]
    for tr in EDL["transitions"]:
        if tr.get("to") == sh["id"]:
            a = min(a, tr["at"] - tr["before"])
        if tr.get("frm") == sh["id"]:
            b = max(b, tr["at"] + tr["after"])
    return max(0, a), min(FRAMES, b)


def encode(frames_iter, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-g", "15",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", path], stdin=subprocess.PIPE)
    n = 0
    for f in frames_iter:
        enc.stdin.write(np.ascontiguousarray(f).tobytes())
        n += 1
    enc.stdin.close()
    enc.wait()
    return n


def final_frames():
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", FINAL, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    out = []
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            break
        out.append(np.frombuffer(b, np.uint8).reshape(H, W, 3))
    p.wait()
    return out


def tc(f):
    return "%02d:%02d:%02d:%02d" % (f // (3600 * FPS), f // (60 * FPS) % 60, f // FPS % 60, f % FPS)


def rt(f):
    return f"{f}/30s"


def main():
    if os.path.exists(PKG):
        shutil.rmtree(PKG)
    os.makedirs(PKG)
    layout = dict(fps=FPS, width=W, height=H, frames=FRAMES, shots=[], transitions=[], audio=None)
    for sh in EDL["shots"]:
        a, b = shot_range(sh)
        store = np.load(os.path.join(WORK, "v11", f"shot_{sh['id']}.npy"), mmap_mode="r")
        rel = f"media/shots/{sh['id']}.mp4"
        n = encode((store[i] for i in range(len(store))), os.path.join(PKG, rel))
        assert n == b - a
        layout["shots"].append(dict(id=sh["id"], file=rel, media_frames=n, record_in=sh["start"], record_out=sh["end"],
                                    source_in=sh["start"] - a, desc=sh["desc"]))
    fin = final_frames()
    assert len(fin) == FRAMES
    k = 0
    for tr in EDL["transitions"]:
        if tr["type"] == "hard_cut":
            continue
        if tr["type"] == "fade_to_cream":
            lo, hi = tr["at"], FRAMES
        else:
            lo, hi = tr["at"] - tr["before"], tr["at"] + tr["after"]
        k += 1
        rel = f"media/transitions/T{k:02d}_{tr['type']}.mp4"
        encode(fin[lo:hi], os.path.join(PKG, rel))
        layout["transitions"].append(dict(id=f"T{k:02d}", type=tr["type"], file=rel, record_in=lo, record_out=hi,
                                          reason=tr["reason"]))
    os.makedirs(os.path.join(PKG, "media", "audio"))
    wav = os.path.join(PKG, "media", "audio", "OK_Kanmani_Song.wav")
    # WAV, not MP3: an MP3's encoder delay and padded header length make Resolve refuse to relink it
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", AUDIO, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", wav], check=True)
    samples = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration_ts",
                                  "-of", "csv=p=0", wav], capture_output=True, text=True, check=True).stdout.strip())
    layout["audio"] = dict(file="media/audio/OK_Kanmani_Song.wav", record_in=0, samples=samples, rate=48000)
    json.dump(layout, open(os.path.join(PKG, "timeline.json"), "w"), indent=1)

    # ---- FCPXML 1.8 (paths are placeholders under /PATH/TO/resolve; Resolve offers to relink on import)
    base = "file:///PATH/TO/resolve/"
    res = ['<format id="r0" name="FFVideoFormat1080p30" frameDuration="1/30s" width="1920" height="1080"/>']
    for i, s in enumerate(layout["shots"]):
        res.append(f'<asset id="s{i}" name="{s["id"]}" src="{base}{s["file"]}" start="0s" duration="{rt(s["media_frames"])}" hasVideo="1" format="r0"/>')
    for i, t in enumerate(layout["transitions"]):
        res.append(f'<asset id="t{i}" name="{t["id"]}_{t["type"]}" src="{base}{t["file"]}" start="0s" duration="{rt(t["record_out"] - t["record_in"])}" hasVideo="1" format="r0"/>')
    adur = f'{layout["audio"]["samples"]}/48000s'
    res.append(f'<asset id="au" name="OK_Kanmani_Song" src="{base}{layout["audio"]["file"]}" start="0s" duration="{adur}" hasAudio="1" audioSources="1" audioChannels="2" audioRate="48000"/>')
    spine = []
    for i, s in enumerate(layout["shots"]):
        kids = []
        for j, t in enumerate(layout["transitions"]):
            if s["record_in"] <= t["record_in"] < s["record_out"]:
                off = s["source_in"] + (t["record_in"] - s["record_in"])
                kids.append(f'<asset-clip ref="t{j}" lane="1" offset="{rt(off)}" name="{t["id"]}_{t["type"]}" start="0s" duration="{rt(t["record_out"] - t["record_in"])}" format="r0"/>')
        if i == 0:
            kids.append(f'<asset-clip ref="au" lane="-1" offset="{rt(s["source_in"])}" name="OK_Kanmani_Song" start="0s" duration="{adur}"/>')
        spine.append(f'<asset-clip ref="s{i}" offset="{rt(s["record_in"])}" name="{s["id"]}" start="{rt(s["source_in"])}" duration="{rt(s["record_out"] - s["record_in"])}" format="r0">'
                     + "".join(kids) + "</asset-clip>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.8">\n<resources>\n' + "\n".join(res)
           + '\n</resources>\n<library><event name="OK Kanmani v11"><project name="OK Kanmani v11">'
           + f'<sequence format="r0" duration="{rt(FRAMES)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k"><spine>\n'
           + "\n".join(spine) + "\n</spine></sequence></project></event></library>\n</fcpxml>\n")
    open(os.path.join(PKG, "OK_Kanmani_v11.fcpxml"), "w").write(xml)

    # ---- CMX3600 EDL, V1 cuts
    lines = ["TITLE: OK_Kanmani_v11_V1", "FCM: NON-DROP FRAME", ""]
    for i, s in enumerate(layout["shots"], 1):
        si, so = s["source_in"], s["source_in"] + s["record_out"] - s["record_in"]
        lines.append(f"{i:03d}  {s['id'][:8]:<8} V     C        {tc(si)} {tc(so)} {tc(s['record_in'])} {tc(s['record_out'])}")
        lines.append(f"* FROM CLIP NAME: {s['id']}.mp4")
    open(os.path.join(PKG, "OK_Kanmani_v11_V1.edl"), "w").write("\n".join(lines) + "\n")
    shutil.copy(os.path.join(HERE, "build_resolve_project.py"), PKG)
    print("package", PKG)


if __name__ == "__main__":
    main()
