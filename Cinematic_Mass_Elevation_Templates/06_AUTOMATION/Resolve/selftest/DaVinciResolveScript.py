"""MOCK of DaVinci Resolve's scripting module - used ONLY by selftest_mock.py to exercise
the harness/analyzer control flow without Resolve. It fakes renders by copying the Python
preview and fakes stills by extracting preview frames. Results it produces are flagged
mock=True and are never merged into the real Resolve results."""
import json, os, shutil, subprocess

ROOT = os.environ["CMET_ROOT"]
INV = {t["macro_name"]: t for t in json.load(open(os.path.join(ROOT, "06_AUTOMATION", "Resolve", "resolve_test_inventory.json")))["templates"]}
FAIL = set(x for x in os.environ.get("CMET_MOCK_FAIL", "").split(",") if x)


class Tool:
    def __init__(self, name, regid, inputs=None, tpl=None):
        self.name, self.regid, self.inputs, self.tpl = name, regid, dict(inputs or {}), tpl
    def GetAttrs(self):
        return {"TOOLS_Name": self.name, "TOOLS_RegID": self.regid}
    def GetInput(self, k, t=None):
        if k not in self.inputs:
            return None
        v = self.inputs[k]
        return (v + 0.01 * t) if (t is not None and isinstance(v, float) and self.regid != "MacroOperator") else v
    def SetInput(self, k, v, t=None):
        if k in self.inputs:
            self.inputs[k] = v
            return True
        return False


class Comp:
    def __init__(self, tpl):
        self.tpl = tpl
        ins = {k: ("DEFAULT TEXT" if k in tpl["text_inputs"] else 1.0) for k in tpl["published_inputs"]}
        self.macro = Tool(tpl["macro_name"], "MacroOperator", ins, tpl)
        self.inner = {p["tool"]: Tool(p["tool"], "Merge", {p["input"]: 0.5}) for p in tpl["expression_probes"]}
    def GetToolList(self, sel=False, typ=None):
        tools = [self.macro, Tool("MediaOut1", "MediaOut")] + list(self.inner.values())
        return {float(i + 1): t for i, t in enumerate(tools)}
    def FindTool(self, n):
        return self.inner.get(n)
    def Execute(self, s):
        return True


class Item:
    def __init__(self, tpl):
        self.tpl, self.comp = tpl, Comp(tpl)
    def GetDuration(self):
        return 240
    def GetFusionCompByIndex(self, i):
        return self.comp


class Timeline:
    def __init__(self, name, project):
        self.name, self.project, self.item, self.tc = name, project, None, "01:00:00:00"
    def InsertFusionTitleIntoTimeline(self, name):
        if name.split("_")[0] in FAIL:
            return None
        self.item = Item(INV[name])
        return self.item
    def InsertFusionCompositionIntoTimeline(self):
        return None
    def GetStartTimecode(self):
        return "01:00:00:00"
    def GetStartFrame(self):
        return 86400
    def SetCurrentTimecode(self, tc):
        self.tc = tc
        return True


class MediaPool:
    def __init__(self, project):
        self.project = project
    def CreateEmptyTimeline(self, name):
        tl = Timeline(name, self.project)
        self.project.timelines.append(tl)
        return tl


class Project:
    def __init__(self):
        self.timelines, self.cur, self.settings, self.jobs = [], None, {}, {}
    def SetSetting(self, k, v):
        return True
    def GetMediaPool(self):
        return MediaPool(self)
    def SetCurrentTimeline(self, tl):
        self.cur = tl
        return True
    def ExportCurrentFrameAsStill(self, path):
        tpl = self.cur.item.tpl
        h, m, s, f = [int(x) for x in self.cur.tc.split(":")]
        frame = ((h * 60 + m) * 60 + s) * 24 + f - 86400
        prev = os.path.join(ROOT, tpl["python_preview"])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % (frame / 24), "-i", prev, "-frames:v", "1", path])
        macro = self.cur.item.comp.macro
        if macro.inputs.get(tpl["main_title_input"]) == tpl["test_title"] or macro.inputs.get("CONTROLS_ImpactFrame", 1.0) != 1.0:
            import cv2
            im = cv2.imread(path)
            cv2.rectangle(im, (700, 480), (1220, 600), (255, 255, 255), -1)
            cv2.imwrite(path, im)
        return True
    def SetCurrentRenderFormatAndCodec(self, f, c):
        return True
    def SetRenderSettings(self, s):
        self.settings = s
        return True
    def AddRenderJob(self):
        jid = "job%d" % (len(self.jobs) + 1)
        self.jobs[jid] = dict(self.settings, tpl=self.cur.item.tpl)
        return jid
    def StartRendering(self, ids):
        for j in ids:
            s = self.jobs[j]
            shutil.copy(os.path.join(ROOT, s["tpl"]["python_preview"]), os.path.join(s["TargetDir"], s["CustomName"] + ".mp4"))
        return True
    def IsRenderingInProgress(self):
        return False
    def GetRenderJobStatus(self, j):
        return {"JobStatus": "Complete", "CompletionPercentage": 100}
    def DeleteRenderJob(self, j):
        return True


class PM:
    def __init__(self):
        self.p = None
    def CreateProject(self, name):
        self.p = Project()
        return self.p
    def LoadProject(self, name):
        return None
    def SaveProject(self):
        return True


class Resolve:
    def GetVersionString(self):
        return "MOCK-0.0"
    def GetProductName(self):
        return "MOCK Resolve (no real application)"
    def GetProjectManager(self):
        return PM()
    def OpenPage(self, p):
        return True


def scriptapp(name):
    return Resolve()
