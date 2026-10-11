"""Build a native DaVinci Resolve project (.drp) from the 40 Fusion compositions.

STATUS: written against the documented Resolve scripting API but NOT TESTED -
Resolve was not available where this library was built. Run it on your own
machine and check the console output.

How to run
----------
Inside Resolve (works in the free and Studio editions where scripting is
enabled for your version):
  1. Copy this file to the Resolve scripts folder, e.g.
     Windows: %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Utility\\
     macOS:   ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/
     Linux:   ~/.local/share/DaVinciResolve/Fusion/Scripts/Utility/
  2. Set CMET_ROOT below (or the CMET_ROOT environment variable) to the
     Cinematic_Mass_Elevation_Templates folder.
  3. Preferences > User > Editing > Standard Generator Duration = 10 seconds
     (compositions are inserted at that length; templates are 6-10 s).
  4. Workspace > Scripts > Utility > build_resolve_project.
Externally (Studio, scripting set to "Local"): `python build_resolve_project.py`
with RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB / PYTHONPATH set as described in
Resolve's Developer/Scripting/README.txt.

Note: one report (Puget Systems, Sep 2026) says Resolve 21.1 removed scripting
from the free edition. If `Resolve` is unavailable, use the manual procedure
in 05_RESOLVE_IMPORT/Import_Instructions.md instead.

What it does
------------
* creates project "Cinematic_Mass_Elevation_Templates" (fails if it exists -
  it never overwrites an existing project),
* sets 1920x1080 (or UHD with --uhd) @ 24 fps,
* for each template creates timeline "T01 Obsidian Impact" etc., inserts a
  Fusion composition clip and imports the template's .comp into it,
* exports the project to 00_PROJECT_FILES/DaVinci_Resolve_Project/
  Cinematic_Mass_Elevation_Templates.drp,
* optionally (--render) queues a render job per timeline into
  04_FINAL_RENDERS/Template_NN/.
"""
import json
import os
import sys

CMET_ROOT = os.environ.get("CMET_ROOT", "")  # e.g. r"C:\\Users\\you\\Documents\\Cinematic_Mass_Elevation_Templates"
PROJECT = "Cinematic_Mass_Elevation_Templates"


def get_resolve():
    try:
        return resolve  # noqa: F821  (defined when run from Resolve's Scripts menu)
    except NameError:
        pass
    try:
        import DaVinciResolveScript as dvr  # type: ignore
        return dvr.scriptapp("Resolve")
    except Exception as e:  # pragma: no cover
        print("Cannot reach Resolve scripting:", e)
        return None


def root_dir():
    if CMET_ROOT:
        return CMET_ROOT
    here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else ""
    cand = os.path.normpath(os.path.join(here, "..", ".."))
    if os.path.isdir(os.path.join(cand, "01_TEMPLATES")):
        return cand
    raise SystemExit("Set CMET_ROOT to the Cinematic_Mass_Elevation_Templates folder")


def main(argv):
    uhd = "--uhd" in argv
    do_render = "--render" in argv
    root = root_dir()
    r = get_resolve()
    if r is None:
        raise SystemExit("DaVinci Resolve scripting not available")
    pm = r.GetProjectManager()
    proj = pm.CreateProject(PROJECT)
    if not proj:
        raise SystemExit(f"Project '{PROJECT}' already exists or could not be created; rename/delete it first. "
                         "(This script never overwrites an existing project.)")
    w, h = ("3840", "2160") if uhd else ("1920", "1080")
    for k, v in (("timelineResolutionWidth", w), ("timelineResolutionHeight", h), ("timelineFrameRate", "24"),
                 ("timelinePlaybackFrameRate", "24")):
        print("SetSetting", k, v, proj.SetSetting(k, v))
    mp = proj.GetMediaPool()
    results = []
    tdir = os.path.join(root, "01_TEMPLATES")
    for d in sorted(os.listdir(tdir)):
        mfile = os.path.join(tdir, d, "manifest.json")
        if not os.path.exists(mfile):
            continue
        m = json.load(open(mfile, encoding="utf-8"))
        comp_path = os.path.join(tdir, d, m["fusion_composition"])
        name = f"{m['id']} {m['name']}"
        tl = mp.CreateEmptyTimeline(name)
        ok = False
        note = ""
        if tl:
            proj.SetCurrentTimeline(tl)
            item = tl.InsertFusionCompositionIntoTimeline()
            if item:
                fc = item.ImportFusionComp(comp_path)
                if fc:
                    names = item.GetFusionCompNameList() or []
                    if names:
                        item.LoadFusionCompByName(names[-1])
                    ok = True
                    note = "Fusion comp imported; connect its final node to MediaOut1 on the Fusion page if needed"
                else:
                    note = "ImportFusionComp returned None"
            else:
                note = "InsertFusionCompositionIntoTimeline failed"
        else:
            note = "CreateEmptyTimeline failed"
        results.append((m["id"], ok, note))
        print(m["id"], "OK" if ok else "FAILED", note)
        if ok and do_render:
            out = os.path.join(root, "04_FINAL_RENDERS", f"Template_{m['id'][1:]}")
            os.makedirs(out, exist_ok=True)
            proj.SetRenderSettings({"TargetDir": out, "CustomName": f"{m['id']}_{m['slug']}",
                                    "FormatWidth": int(w), "FormatHeight": int(h), "FrameRate": 24.0,
                                    "MarkIn": 0, "MarkOut": int(m["duration_frames"]) - 1})
            proj.SetCurrentRenderFormatAndCodec("mov", "ProRes422HQ")
            print("  render job:", proj.AddRenderJob())
    pm.SaveProject()
    drp = os.path.join(root, "00_PROJECT_FILES", "DaVinci_Resolve_Project", f"{PROJECT}.drp")
    print("ExportProject:", pm.ExportProject(PROJECT, drp), drp)
    if do_render:
        print("StartRendering:", proj.StartRendering())
    report = os.path.join(root, "00_PROJECT_FILES", "DaVinci_Resolve_Project", "build_report.json")
    json.dump([{"id": i, "imported": ok, "note": n} for i, ok, n in results], open(report, "w"), indent=2)
    print(f"{sum(1 for _, ok, _ in results if ok)}/{len(results)} timelines built; report: {report}")


if __name__ == "__main__":
    main(sys.argv[1:])
