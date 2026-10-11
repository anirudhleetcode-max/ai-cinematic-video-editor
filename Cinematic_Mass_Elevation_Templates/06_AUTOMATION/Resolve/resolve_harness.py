"""CMET DaVinci Resolve test harness.

Runs the 40 templates through the real DaVinci Resolve application using the
officially documented scripting API (DaVinciResolveScript). It never edits the
template files, never overwrites an existing project, and writes everything to
06_AUTOMATION/Validation/resolve_runs/<run_id>/.

Per template it records evidence for:
  C  composition loading   - title/comp inserted, Fusion comp obtained, macro tool and
                             inner tools present, published inputs readable,
                             expressions evaluate over time (probe values)
  D  rendering             - 1080p/24 H.264 render via the Deliver render queue
                             (verified later by analyze_resolve_run.py)
  E  editability           - main title / subtitle SetInput+readback; stills before/after
                             a text change and an Impact Frame change (compared later)
Visual comparison (F) against the Python previews is done by analyze_resolve_run.py.

Two insertion paths (both documented in 05_RESOLVE_IMPORT/Import_Instructions.md):
  A  Edit-page Fusion Title: Timeline.InsertFusionTitleIntoTimeline(<macro name>)
     (requires the titles installed with install_titles.ps1)
  B  Fusion composition clip: Timeline.InsertFusionCompositionIntoTimeline(), then the
     .setting is pasted into its comp and wired to MediaOut1 (comp:Execute Lua).
Default: try A, fall back to B, record which one was used.

Usage
  External (Resolve Studio, Preferences > System > General > External scripting = Local):
      python resolve_harness.py --root <Cinematic_Mass_Elevation_Templates> [--templates T01] [--no-render]
  Inside Resolve (Workspace > Scripts): use the stub installed by run_resolve_tests.ps1.

Compatible with Python 3.6+ (Resolve's supported range). Standard library only.
"""
import argparse
import datetime
import json
import os
import platform
import sys
import time
import traceback

FPS = 24


# --------------------------------------------------------------------------- connection
def get_resolve(log):
    g = globals()
    for name in ("resolve", "app"):
        obj = g.get(name)
        if obj is not None:
            try:
                r = obj if name == "resolve" else obj.GetResolve()
                if r:
                    log("connected via host-provided '%s' object" % name)
                    return r
            except Exception:
                pass
    try:
        import DaVinciResolveScript as dvr  # noqa
    except Exception as e:
        log("cannot import DaVinciResolveScript: %r" % (e,))
        log("hint: set RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB / PYTHONPATH (run_resolve_tests.ps1 does this)")
        return None
    r = dvr.scriptapp("Resolve")
    if not r:
        log("scriptapp('Resolve') returned None: Resolve not running, or external scripting disabled "
            "(Studio: Preferences > System > General > External scripting using = Local; free edition: "
            "run from Workspace > Scripts instead)")
        return None
    log("connected via DaVinciResolveScript.scriptapp")
    return r


# --------------------------------------------------------------------------- helpers
def tc_from_frame(start_tc, frame, fps=FPS):
    h, m, s, f = [int(x) for x in start_tc.replace(";", ":").split(":")]
    total = ((h * 60 + m) * 60 + s) * fps + f + int(frame)
    f = total % fps
    s = (total // fps) % 60
    m = (total // (fps * 60)) % 60
    h = total // (fps * 3600)
    return "%02d:%02d:%02d:%02d" % (h, m, s, f)


def safe(fn, *a, **k):
    try:
        return fn(*a, **k), None
    except Exception as e:
        return None, repr(e)


def tool_attrs(tool):
    a, _ = safe(tool.GetAttrs)
    a = a or {}
    return a.get("TOOLS_Name"), a.get("TOOLS_RegID")


def list_tools(comp):
    tl, err = safe(comp.GetToolList, False)
    out = []
    if tl:
        for t in tl.values():
            n, r = tool_attrs(t)
            out.append((n, r, t))
    return out, err


def find_macro(tools, tpl):
    for n, r, t in tools:
        if n and (n == tpl["macro_name"] or n.startswith(tpl["macro_name"])):
            return t, n, r
    key = tpl["main_title_input"]
    for n, r, t in tools:
        if r in ("MacroOperator", "GroupOperator"):
            v, err = safe(t.GetInput, key)
            if err is None and v is not None:
                return t, n, r
    return None, None, None


def find_inner(comp, tools, name):
    t, _ = safe(comp.FindTool, name)
    if t:
        return t
    for n, r, tt in tools:
        if n == name or (n and n.endswith("." + name)):
            return tt
    return None


def lua_quote(s):
    return "[==[" + s + "]==]"


# --------------------------------------------------------------------------- per template
def test_template(resolve, project, mp, tpl, root, run_dir, opts, log):
    res = {"id": tpl["id"], "name": tpl["name"], "category": tpl["category"], "fusion_source": tpl["setting"],
           "started": datetime.datetime.now().isoformat(timespec="seconds"), "path": None, "levels": {},
           "notes": [], "errors": []}
    tl_name = "%s %s" % (tpl["id"], tpl["name"])
    tl = mp.CreateEmptyTimeline(tl_name)
    if not tl:
        res["errors"].append("CreateEmptyTimeline failed")
        return res
    project.SetCurrentTimeline(tl)
    resolve.OpenPage("edit")
    item = None
    if opts.path in ("auto", "A"):
        item, err = safe(tl.InsertFusionTitleIntoTimeline, tpl["macro_name"])
        if item:
            res["path"] = "A (Edit-page Fusion Title)"
        else:
            res["notes"].append("InsertFusionTitleIntoTimeline(%s) returned %r %s" % (tpl["macro_name"], item, err or ""))
    if not item and opts.path in ("auto", "B"):
        item, err = safe(tl.InsertFusionCompositionIntoTimeline)
        if item:
            comp0, err0 = safe(item.GetFusionCompByIndex, 1)
            if comp0:
                setting = os.path.join(root, tpl["setting"])
                lua = ("local s = bmd.readfile(%s)\n"
                       "comp:Lock()\n"
                       "local ok = comp:Paste(s)\n"
                       "local mo = comp:FindTool('MediaOut1')\n"
                       "local m = comp:FindTool('%s')\n"
                       "if mo and m then mo:ConnectInput('Input', m) end\n"
                       "comp:Unlock()\n" % (lua_quote(setting.replace("\\", "/")), tpl["macro_name"]))
                _, err1 = safe(comp0.Execute, lua)
                res["path"] = "B (Fusion composition clip + pasted macro)"
                if err1:
                    res["errors"].append("comp.Execute paste failed: %s" % err1)
            else:
                res["errors"].append("GetFusionCompByIndex failed on composition clip: %s" % err0)
        else:
            res["errors"].append("InsertFusionCompositionIntoTimeline failed: %s" % err)
    if not item:
        res["levels"]["C_load"] = {"status": "FAIL", "detail": "could not insert template into timeline"}
        return res

    # ---------------- C: composition loading
    c = {"status": "FAIL"}
    dur, _ = safe(item.GetDuration)
    c["item_duration"] = dur
    c["expected_frames"] = tpl["duration_frames"]
    if dur is not None and dur < tpl["duration_frames"]:
        res["notes"].append("timeline item is %s frames but the template needs %s: set Preferences > User > "
                            "Editing > Standard Generator Duration to 10 s" % (dur, tpl["duration_frames"]))
    comp, err = safe(item.GetFusionCompByIndex, 1)
    if not comp:
        c["detail"] = "no Fusion comp on timeline item: %s" % err
        res["levels"]["C_load"] = c
        return res
    tools, err = list_tools(comp)
    c["tool_count_in_comp"] = len(tools)
    c["tool_regids"] = sorted({r for _, r, _ in tools if r})
    macro, mname, mreg = find_macro(tools, tpl)
    c["macro_tool"] = mname
    c["macro_regid"] = mreg
    if not macro:
        c["detail"] = "macro tool not found in comp (tools: %s)" % [n for n, _, _ in tools][:30]
        res["levels"]["C_load"] = c
        return res
    readable = {}
    for key in tpl["published_inputs"]:
        v, e = safe(macro.GetInput, key)
        readable[key] = (v is not None and e is None)
    c["published_readable"] = sum(readable.values())
    c["published_total"] = len(readable)
    c["published_unreadable"] = [k for k, ok in readable.items() if not ok]
    probes = []
    for pr in tpl["expression_probes"]:
        t = find_inner(comp, tools, pr["tool"])
        vals = {}
        if t:
            for fk in ("build", "impact", "hold", "exit_mid"):
                v, e = safe(t.GetInput, pr["input"], tpl["frames"][fk])
                vals[fk] = v if isinstance(v, (int, float)) else (None if v is None else str(v))
        probes.append({"tool": pr["tool"], "input": pr["input"], "found": bool(t), "values": vals})
    c["expression_probes"] = probes
    numeric = [p for p in probes if p["found"] and all(isinstance(v, (int, float)) for v in p["values"].values())
               and p["values"]]
    varying = [p for p in numeric if len(set(round(v, 6) for v in p["values"].values())) > 1]
    c["probes_found"] = sum(1 for p in probes if p["found"])
    c["probes_numeric"] = len(numeric)
    c["probes_time_varying"] = len(varying)
    ok = (c["published_readable"] == c["published_total"] and tpl["main_title_input"] in readable
          and readable[tpl["main_title_input"]])
    if c["probes_found"] and not varying:
        ok = False
        c["detail"] = "expressions did not vary over time (expression engine or references broken?)"
    c["status"] = "PASS" if ok else "FAIL"
    if not ok and "detail" not in c:
        c["detail"] = "published inputs unreadable: %s" % c["published_unreadable"][:8]
    res["levels"]["C_load"] = c

    # ---------------- E: editability (+ stills for later comparison)
    e = {"status": "FAIL"}
    stills_dir = os.path.join(run_dir, "stills", tpl["id"])
    os.makedirs(stills_dir, exist_ok=True)
    start_tc, _ = safe(tl.GetStartTimecode)
    start_tc = start_tc or "01:00:00:00"
    resolve.OpenPage("color")

    def still(tag, frame):
        tc = tc_from_frame(start_tc, frame)
        safe(tl.SetCurrentTimecode, tc)
        path = os.path.join(stills_dir, "%s_f%03d.png" % (tag, frame))
        okk, err = safe(project.ExportCurrentFrameAsStill, path)
        return path if okk and os.path.exists(path) else None, err

    hold = tpl["frames"]["hold"]
    ip3 = tpl["frames"]["impact_plus3"]
    e["still_default_hold"], err_s = still("default_hold", hold)
    if not e["still_default_hold"]:
        e["stills_error"] = err_s or "ExportCurrentFrameAsStill returned False"
    orig_title, _ = safe(macro.GetInput, tpl["main_title_input"])
    _, err = safe(macro.SetInput, tpl["main_title_input"], tpl["test_title"])
    back, _ = safe(macro.GetInput, tpl["main_title_input"])
    e["main_title_set"] = (back == tpl["test_title"])
    e["main_title_error"] = err
    e["still_test_title_hold"], _ = still("testtitle_hold", hold)
    if tpl["subtitle_input"]:
        orig_sub, _ = safe(macro.GetInput, tpl["subtitle_input"])
        safe(macro.SetInput, tpl["subtitle_input"], "SUBTITLE TEST")
        sb, _ = safe(macro.GetInput, tpl["subtitle_input"])
        e["subtitle_set"] = (sb == "SUBTITLE TEST")
        safe(macro.SetInput, tpl["subtitle_input"], orig_sub)
    safe(macro.SetInput, tpl["main_title_input"], orig_title)
    # control behaviour: move ImpactFrame by +20 and capture impact+3
    if "CONTROLS_ImpactFrame" in tpl["control_inputs"]:
        e["still_default_impact"], _ = still("default_impact", ip3)
        orig_imp, _ = safe(macro.GetInput, "CONTROLS_ImpactFrame")
        if isinstance(orig_imp, (int, float)):
            safe(macro.SetInput, "CONTROLS_ImpactFrame", float(orig_imp) + 20)
            nb, _ = safe(macro.GetInput, "CONTROLS_ImpactFrame")
            e["impact_frame_set"] = (isinstance(nb, (int, float)) and abs(nb - orig_imp - 20) < 1e-6)
            e["still_moved_impact"], _ = still("movedimpact", ip3)
            safe(macro.SetInput, "CONTROLS_ImpactFrame", orig_imp)
    # every published control: readback after a write (availability)
    ctl_ok = {}
    for key in tpl["control_inputs"]:
        k = "CONTROLS_" + tpl["control_inputs"][key] if not key.startswith("CONTROLS_") else key
        v0, _ = safe(macro.GetInput, k)
        if isinstance(v0, (int, float)):
            safe(macro.SetInput, k, v0 + 1)
            v1, _ = safe(macro.GetInput, k)
            ctl_ok[k] = isinstance(v1, (int, float)) and abs(v1 - v0 - 1) < 1e-6
            safe(macro.SetInput, k, v0)
        else:
            ctl_ok[k] = False
    e["controls_writable"] = sum(ctl_ok.values())
    e["controls_total"] = len(ctl_ok)
    e["controls_failed"] = [k for k, v in ctl_ok.items() if not v]
    e["status"] = "PASS" if (e["main_title_set"] and e.get("subtitle_set", True)
                             and e["controls_writable"] == e["controls_total"]) else "FAIL"
    res["levels"]["E_edit_api"] = e
    resolve.OpenPage("edit")

    # ---------------- D: render (default text)
    d = {"status": "NOT RUN"}
    if not opts.no_render:
        rdir = os.path.join(run_dir, "renders")
        os.makedirs(rdir, exist_ok=True)
        name = "%s_%s_resolve" % (tpl["id"], tpl["slug"])
        start, _ = safe(tl.GetStartFrame)
        start = start or 0
        frames = tpl["duration_frames"] if not dur else min(dur, tpl["duration_frames"])
        resolve.OpenPage("deliver")
        okf, _ = safe(project.SetCurrentRenderFormatAndCodec, "mp4", "H264")
        settings = {"SelectAllFrames": False, "MarkIn": start, "MarkOut": start + frames - 1, "TargetDir": rdir,
                    "CustomName": name, "FormatWidth": 1920, "FormatHeight": 1080, "FrameRate": 24.0,
                    "ExportVideo": True, "ExportAudio": False}
        oks, err = safe(project.SetRenderSettings, settings)
        d["format_ok"] = bool(okf)
        d["settings_ok"] = bool(oks)
        jid, err = safe(project.AddRenderJob)
        d["job_id"] = jid
        if not jid:
            d["status"] = "FAIL"
            d["detail"] = "AddRenderJob failed: %s" % err
        else:
            t0 = time.time()
            safe(project.StartRendering, [jid])
            timeout = opts.render_timeout
            while True:
                busy, _ = safe(project.IsRenderingInProgress)
                if not busy:
                    break
                if time.time() - t0 > timeout:
                    safe(project.StopRendering)
                    d["detail"] = "render timed out after %ss" % timeout
                    break
                time.sleep(1.0)
            st, _ = safe(project.GetRenderJobStatus, jid)
            d["job_status"] = st
            d["seconds"] = round(time.time() - t0, 1)
            safe(project.DeleteRenderJob, jid)
            outs = [f for f in os.listdir(rdir) if f.startswith(name)]
            d["output"] = os.path.join("renders", outs[0]) if outs else None
            d["frames_rendered_range"] = [start, start + frames - 1]
            d["status"] = "RENDERED" if (outs and st and str(st.get("JobStatus", "")).lower() == "complete") else "FAIL"
            if d["status"] == "FAIL" and "detail" not in d:
                d["detail"] = "job status %r, outputs %r" % (st, outs)
        resolve.OpenPage("edit")
    res["levels"]["D_render"] = d
    res["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
    return res


# --------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("CMET_ROOT", ""))
    ap.add_argument("--templates", default="")
    ap.add_argument("--path", choices=["auto", "A", "B"], default="auto")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--render-timeout", type=int, default=1200)
    ap.add_argument("--run-id", default=datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    ap.add_argument("--resume", action="store_true", help="skip templates already recorded in this run")
    ap.add_argument("--runs-dir", default="", help="override the output folder (used by the mock self-test)")
    opts = ap.parse_args(argv)
    root = opts.root or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    inv = json.load(open(os.path.join(root, "06_AUTOMATION", "Resolve", "resolve_test_inventory.json"),
                         encoding="utf-8"))
    run_dir = os.path.join(opts.runs_dir or os.path.join(root, "06_AUTOMATION", "Validation", "resolve_runs"), opts.run_id)
    os.makedirs(run_dir, exist_ok=True)
    logf = open(os.path.join(run_dir, "harness_log.txt"), "a", encoding="utf-8")

    def log(msg):
        line = "%s %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg)
        print(line)
        logf.write(line + "\n")
        logf.flush()

    results_path = os.path.join(run_dir, "harness_results.json")
    state = {"run_id": opts.run_id, "mock": bool(os.environ.get("CMET_MOCK_RESOLVE")), "host": platform.platform(),
             "python": sys.version.split()[0], "templates": {}}
    if opts.resume and os.path.exists(results_path):
        state = json.load(open(results_path, encoding="utf-8"))

    def save():
        json.dump(state, open(results_path, "w", encoding="utf-8"), indent=1, default=str)

    resolve = get_resolve(log)
    if not resolve:
        state["connection"] = {"connected": False}
        save()
        log("NOT CONNECTED - nothing tested. See harness_log.txt")
        return 2
    ver, _ = safe(resolve.GetVersionString)
    prod, _ = safe(resolve.GetProductName)
    state["connection"] = {"connected": True, "product": prod, "version": ver}
    if "MOCK" in str(prod).upper() or "MOCK" in str(ver).upper():
        state["mock"] = True  # never let a mock API be recorded as real Resolve evidence
    log("Resolve responded: %s %s" % (prod, ver))
    pm = resolve.GetProjectManager()
    proj_name = "CMET_ResolveTest_%s" % opts.run_id
    project = pm.LoadProject(proj_name) if opts.resume else None
    if not project:
        project = pm.CreateProject(proj_name)
    if not project:
        log("could not create test project %s (exists already?) - aborting without touching other projects" % proj_name)
        state["connection"]["project_error"] = "CreateProject failed"
        save()
        return 3
    state["project"] = proj_name
    for k, v in (("timelineResolutionWidth", "1920"), ("timelineResolutionHeight", "1080"),
                 ("timelineFrameRate", "24"), ("timelinePlaybackFrameRate", "24")):
        okk, _ = safe(project.SetSetting, k, v)
        log("SetSetting %s=%s -> %s" % (k, v, okk))
    mp = project.GetMediaPool()
    want = [x.strip().upper() for x in opts.templates.split(",") if x.strip()]
    todo = [t for t in inv["templates"] if not want or t["id"] in want]
    save()
    for tpl in todo:
        if opts.resume and tpl["id"] in state["templates"]:
            continue
        log("---- %s %s" % (tpl["id"], tpl["name"]))
        try:
            r = test_template(resolve, project, mp, tpl, root, run_dir, opts, log)
        except Exception:
            r = {"id": tpl["id"], "name": tpl["name"], "errors": [traceback.format_exc()], "levels": {}}
        state["templates"][tpl["id"]] = r
        pm.SaveProject()
        save()
        lv = r.get("levels", {})
        log("%s path=%s C=%s E=%s D=%s %s" % (tpl["id"], r.get("path"), lv.get("C_load", {}).get("status"),
                                             lv.get("E_edit_api", {}).get("status"),
                                             lv.get("D_render", {}).get("status"), "; ".join(r.get("errors", []))[:200]))
    log("done; results: %s" % results_path)
    log("next: python analyze_resolve_run.py --run %s" % opts.run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
