"""Build the v11 "OK Kanmani" edit as a DaVinci Resolve project.

Run inside DaVinci Resolve 18 or 19 (Free or Studio): Workspace > Scripts > Edit >
build_resolve_project. To make it appear there, copy this whole `resolve` folder into
Resolve's scripts folder:
  Windows: %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Edit\\
  macOS:   ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit/
Alternatively, run it from Resolve's Console (Workspace > Console > Py3) with
exec(open(r"<path>/build_resolve_project.py").read()).

It reads timeline.json next to this file, creates the project "OK Kanmani v11" (1080p30),
imports the media, and builds the timeline:
  V1  19 shots on hard cuts at the exact cut frames
  V2  the rendered transitions over the cuts (disable V2 to see bare cuts)
  A1  the song
After it finishes, File > Export Project gives you a .drp file.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()

try:
    resolve  # noqa: F821  (predefined in Resolve's script environment)
except NameError:
    import DaVinciResolveScript as dvr  # external scripting (Studio)
    resolve = dvr.scriptapp("Resolve")

layout = json.load(open(os.path.join(HERE, "timeline.json")))
pm = resolve.GetProjectManager()
proj = pm.CreateProject("OK Kanmani v11") or pm.LoadProject("OK Kanmani v11")
for k, v in (("timelineFrameRate", "30"), ("timelinePlaybackFrameRate", "30"),
             ("timelineResolutionWidth", "1920"), ("timelineResolutionHeight", "1080")):
    proj.SetSetting(k, v)
pool = proj.GetMediaPool()
root = pool.GetRootFolder()


def import_into(name, files):
    folder = pool.AddSubFolder(root, name)
    pool.SetCurrentFolder(folder)
    items = pool.ImportMedia([os.path.join(HERE, f) for f in files]) or []
    by = {}
    for it in items:
        by[it.GetClipProperty("File Name")] = it
    return by


shots = import_into("Shots", [s["file"] for s in layout["shots"]])
trans = import_into("Transitions", [t["file"] for t in layout["transitions"]])
audio = import_into("Audio", [layout["audio"]["file"]])
pool.SetCurrentFolder(root)

tl = pool.CreateEmptyTimeline("OK Kanmani v11")
proj.SetCurrentTimeline(tl)
tl.AddTrack("video")
start = tl.GetStartFrame()

clips = []
for s in layout["shots"]:
    clips.append({"mediaPoolItem": shots[os.path.basename(s["file"])], "startFrame": s["source_in"],
                  "endFrame": s["source_in"] + s["record_out"] - s["record_in"] - 1,
                  "trackIndex": 1, "recordFrame": start + s["record_in"], "mediaType": 1})
for t in layout["transitions"]:
    clips.append({"mediaPoolItem": trans[os.path.basename(t["file"])], "startFrame": 0,
                  "endFrame": t["record_out"] - t["record_in"] - 1,
                  "trackIndex": 2, "recordFrame": start + t["record_in"], "mediaType": 1})
clips.append({"mediaPoolItem": audio["OK_Kanmani_Song.wav"], "startFrame": 0,
              "endFrame": int(layout["audio"]["samples"] * 30 / layout["audio"]["rate"]) - 1,
              "trackIndex": 1, "recordFrame": start, "mediaType": 2})
added = pool.AppendToTimeline(clips)
print("OK Kanmani v11: placed %d of %d clips" % (len(added or []), len(clips)))
