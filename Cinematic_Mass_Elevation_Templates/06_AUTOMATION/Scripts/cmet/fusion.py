"""Fusion (.setting / .comp) writer.

Builds a node graph in Python and serialises it to Fusion's Lua-table text
format. Every template exports:

* a MacroOperator `.setting` (install as an Edit-page Fusion Title, or drag
  into the Fusion page node editor), with published controls, and
* a flat `.comp` composition for Fusion Studio / Resolve's Fusion page
  (File > Import > Composition).

Animation is driven by Simple Expressions that reference a single CONTROLS
tool carrying user controls (timing, intensities). This makes the timing
controls genuinely functional: changing CONTROLS.ImpactFrame re-times every
coupled effect. Only conservative expression functions are used
(min, max, abs, sin, cos, floor, pow, Point, time) - `pow` rather than `^` or `exp`.
"""
from __future__ import annotations

import math
import re
from collections import OrderedDict


# --------------------------------------------------------------------------
# Lua value model
# --------------------------------------------------------------------------
class Raw:
    def __init__(self, s):
        self.s = s


class FuID:
    def __init__(self, s):
        self.s = s


class Call:
    """`Name { ... }` constructor."""

    def __init__(self, name, table=None, ordered=False):
        self.name = name
        self.table = table if table is not None else OrderedDict()
        self.ordered = ordered


class Ordered(OrderedDict):
    """`ordered() { ... }` table."""


class Grad:
    """Fusion Gradient value: list of (pos, (r,g,b,a))."""

    def __init__(self, stops):
        self.stops = stops


_ident = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _num(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if math.isnan(v) or math.isinf(v):
        raise ValueError("non-finite number in Fusion output")
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def _str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _key(k):
    if isinstance(k, (int, float)) and not isinstance(k, bool):
        return f"[{_num(k)}]"
    if _ident.match(k):
        return k
    return f"[{_str(k)}]"


def lua(v, ind=0):
    t = "\t"
    if isinstance(v, Raw):
        return v.s
    if isinstance(v, FuID):
        return f"FuID {{ {_str(v.s)} }}"
    if isinstance(v, Grad):
        rows = ",\n".join(f"{t * (ind + 2)}[{_num(p)}] = {{ {', '.join(_num(x) for x in c)} }}" for p, c in v.stops)
        return f"Gradient {{\n{t * (ind + 1)}Colors = {{\n{rows}\n{t * (ind + 1)}}}\n{t * ind}}}"
    if isinstance(v, bool) or isinstance(v, (int, float)):
        return _num(v)
    if isinstance(v, str):
        return _str(v)
    if isinstance(v, Call):
        body = _table_body(v.table, ind)
        pre = f"{v.name} " + ("ordered() " if v.ordered else "")
        return pre + body
    if isinstance(v, Ordered):
        return "ordered() " + _table_body(v, ind)
    if isinstance(v, dict):
        return _table_body(v, ind)
    if isinstance(v, (list, tuple)):
        if all(isinstance(x, (int, float)) for x in v) and len(v) <= 4:
            return "{ " + ", ".join(_num(x) for x in v) + " }"
        inner = ",\n".join(t * (ind + 1) + lua(x, ind + 1) for x in v)
        return "{\n" + inner + ",\n" + t * ind + "}"
    raise TypeError(f"cannot serialise {type(v)}")


def _table_body(d, ind):
    t = "\t"
    if not d:
        return "{ }"
    rows = []
    for k, val in d.items():
        rows.append(f"{t * (ind + 1)}{_key(k)} = {lua(val, ind + 1)},")
    return "{\n" + "\n".join(rows) + "\n" + t * ind + "}"


# --------------------------------------------------------------------------
# Expression helpers (strings). `C` is the controls tool name.
# --------------------------------------------------------------------------
C = "CONTROLS"
A_NAME = "ACCENT"


def ctl(name):
    return f"{C}.{name}"


def clamp01(x):
    return f"min(max({x}, 0), 1)"


def prog(start, dur):
    """0..1 linear progress through [start, start+dur] (frames)."""
    return clamp01(f"(time - ({start})) / max({dur}, 1)")


def e_out(u, p=3):
    return f"(1 - pow(1 - {u}, {p}))"


def e_in(u, p=3):
    return f"pow({u}, {p})"


def e_inout(u):
    return f"(0.5 - 0.5*cos(3.14159265*{u}))"


def decay(start, frames):
    """Impact envelope: 0 before start, 1 at start then exponential decay."""
    # pow(e, -x) instead of exp(-x): pow is confirmed in Fusion Simple Expressions, exp is not
    return f"(min(max((time - ({start}) + 1), 0), 1) * pow(2.718282, -max(time - ({start}), 0) / {frames}))"


def step(start):
    return f"min(max(time - ({start}) + 1, 0), 1)"


def window(a, b, fin, fout):
    """1 between a and b with linear fades (frames)."""
    return f"({clamp01(f'(time - ({a}) + {fin}) / {fin}')} * (1 - {clamp01(f'(time - ({b})) / {fout}')}))"


def shake(amp, freq=0.55, seed=1.0):
    return (f"({amp}) * (sin(time*{freq:.3f}*1.31 + {seed}) * 0.6 + sin(time*{freq:.3f}*2.71 + {seed*3.1:.3f}) * 0.3"
            f" + sin(time*{freq:.3f}*5.17 + {seed*7.7:.3f}) * 0.1)")


# Standard timing controls every template exposes (all in frames @ 24 fps).
TIMING_CONTROLS = [
    ("AnimStart", "Animation Start (frames)", 0, 0, 120),
    ("AnimDuration", "Reveal Duration (frames)", 48, 1, 144),
    ("ImpactFrame", "Impact Frame", 84, 0, 240),
    ("HoldDuration", "Hero Hold (frames)", 48, 0, 192),
    ("ExitStart", "Exit Start (frame)", 150, 0, 300),
    ("ExitDuration", "Exit Duration (frames)", 30, 1, 120),
]
LEVEL_CONTROLS = [
    ("BackgroundIntensity", "Background Intensity", 1.0, 0, 2),
    ("ParticleIntensity", "Particle Intensity", 1.0, 0, 2),
    ("GlowStrength", "Glow Strength", 1.0, 0, 3),
    ("ShadowStrength", "Shadow Strength", 0.7, 0, 1),
    ("ImpactIntensity", "Impact Intensity", 1.0, 0, 2),
    ("ShakeAmount", "Camera Shake", 1.0, 0, 3),
    ("TextScale", "Text Scale", 1.0, 0.2, 3),
    ("TextPosX", "Text Position X", 0.5, 0, 1),
    ("TextPosY", "Text Position Y", 0.5, 0, 1),
    ("TextRotation", "Text Rotation", 0.0, -180, 180),
    ("ExtrusionDepth", "Extrusion Depth", 1.0, 0, 3),
    ("BevelAmount", "Bevel Amount", 1.0, 0, 3),
    ("MotionBlurAmount", "Motion Blur Amount", 1.0, 0, 3),
    ("Letterbox", "Letterbox (2.39:1)", 1.0, 0, 1),
]


# --------------------------------------------------------------------------
# Graph
# --------------------------------------------------------------------------
class Tool:
    def __init__(self, g, tid, name, pos):
        self.g = g
        self.tid = tid
        self.name = name
        self.inputs: "OrderedDict[str, object]" = OrderedDict()
        self.pos = pos
        self.user_controls = None
        self.extra = OrderedDict()
        self.passthrough = False

    # input setters ------------------------------------------------------
    def set(self, **kw):
        for k, v in kw.items():
            self.inputs[k.replace("__", ".")] = ("v", v)
        return self

    def setk(self, key, v):
        self.inputs[key] = ("v", v)
        return self

    def expr(self, key, expression, value=0):
        self.inputs[key] = ("e", value, expression)
        return self

    def conn(self, key, src, out="Output"):
        if src is None:
            return self
        if isinstance(src, Tool):
            self.inputs[key] = ("c", src.name, out)
        else:
            self.inputs[key] = ("c", src, out)
        return self

    def serialise_inputs(self):
        d = OrderedDict()
        for k, spec in self.inputs.items():
            kind = spec[0]
            if kind == "v":
                d[k] = Call("Input", OrderedDict(Value=spec[1]))
            elif kind == "e":
                v = spec[1]
                d[k] = Call("Input", OrderedDict(Value=v, Expression=spec[2]))
            elif kind == "c":
                d[k] = Call("Input", OrderedDict(SourceOp=spec[1], Source=spec[2]))
        return d

    def to_lua_obj(self):
        t = OrderedDict()
        if self.passthrough:
            t["PassThrough"] = True
        if self.extra.get("NameSet"):
            t["NameSet"] = True
        t["Inputs"] = self.serialise_inputs()
        t["ViewInfo"] = Call("OperatorInfo", OrderedDict(Pos=[float(self.pos[0]), float(self.pos[1])]))
        if self.user_controls:
            t["UserControls"] = self.user_controls
        return Call(self.tid, t)


class Published:
    def __init__(self, tool, inp, name, page="Controls", default=None, group=None, cid=None):
        self.tool, self.inp, self.name, self.page, self.default, self.group, self.cid = tool, inp, name, page, default, group, cid


class Graph:
    def __init__(self, name, W=1920, H=1080, fps=24, frames=192):
        self.name = name
        self.W, self.H, self.fps, self.frames = W, H, fps, frames
        self.tools: "OrderedDict[str, Tool]" = OrderedDict()
        self.published: list[Published] = []
        self.output: Tool | None = None
        self._col = 0
        self._row = 0
        self.notes: list[str] = []

    def at(self, col, row):
        self._col, self._row = col, row
        return self

    def add(self, tid, name, pos=None, **inputs):
        if name in self.tools:
            raise ValueError(f"duplicate tool name {name}")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ValueError(f"bad tool name {name}")
        if pos is None:
            pos = (self._col * 110, self._row * 33)
            self._col += 1
        t = Tool(self, tid, name, pos)
        t.set(**inputs)
        self.tools[name] = t
        return t

    def publish(self, tool, inp, name, page="Controls", default=None, group=None, cid=None):
        self.published.append(Published(tool, inp, name, page, default, group, cid))

    # Controls node ------------------------------------------------------
    def controls(self, timing: dict, levels: dict | None = None, extra: list | None = None):
        """Create the CONTROLS tool (an identity Transform that carries all
        user controls) and publish them. `timing` overrides defaults."""
        t = self.add("Transform", C, pos=(0, -66))
        uc = Ordered()
        specs = []
        for cid, label, dflt, lo, hi in TIMING_CONTROLS:
            specs.append((cid, label, timing.get(cid, dflt), lo, hi, True, "Timing"))
        lv = dict(levels or {})
        for cid, label, dflt, lo, hi in LEVEL_CONTROLS:
            specs.append((cid, label, lv.get(cid, dflt), lo, hi, False, "Look"))
        for e in extra or []:
            specs.append(e)
        for cid, label, dflt, lo, hi, integer, page in specs:
            d = OrderedDict(
                LINKS_Name=label,
                LINKID_DataType="Number",
                INPID_InputControl="SliderControl",
                INP_Default=float(dflt),
                INP_MinScale=float(lo),
                INP_MaxScale=float(hi),
            )
            if integer:
                d["INP_Integer"] = True
            d["ICS_ControlPage"] = "Controls"
            uc[cid] = d
            t.setk(cid, float(dflt))
            self.publish(t, cid, label, page=page, default=float(dflt))
        t.user_controls = uc
        self.ctrl = t
        return t

    def referenced_controls(self):
        refs = set()
        for t in self.tools.values():
            for spec in t.inputs.values():
                if spec[0] == "e":
                    refs.update(re.findall(rf"\b{C}\.([A-Za-z_][A-Za-z0-9_]*)", spec[2]))
        return refs

    def prune_controls(self):
        """Drop user controls that no expression uses, so every published
        control demonstrably drives something (no dummy sliders)."""
        if C not in self.tools:
            return
        ctrl = self.tools[C]
        refs = self.referenced_controls()
        for cid in list((ctrl.user_controls or {}).keys()):
            if cid not in refs:
                del ctrl.user_controls[cid]
                ctrl.inputs.pop(cid, None)
        self.published = [p for p in self.published
                          if not (p.tool is ctrl and p.inp not in refs)]
        if A_NAME in self.tools:
            used = any(A_NAME + "." in spec[2] for t in self.tools.values()
                       for spec in t.inputs.values() if spec[0] == "e")
            if not used:
                raise ValueError("ACCENT holder present but unused")

    def control_names(self):
        return list((self.tools[C].user_controls or {}).keys()) if C in self.tools else []

    # Serialisation ------------------------------------------------------
    def check(self):
        """Structural self-check: every connection resolves, output set."""
        errs = []
        for t in self.tools.values():
            for k, spec in t.inputs.items():
                if spec[0] == "c" and spec[1] not in self.tools:
                    errs.append(f"{t.name}.{k} -> missing {spec[1]}")
                if spec[0] == "e":
                    for ref in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)", spec[2]):
                        if ref[0] not in self.tools:
                            errs.append(f"{t.name}.{k} expression references missing tool {ref[0]}")
                        elif ref[0] == C and ref[1] not in (self.tools[C].user_controls or {}):
                            errs.append(f"{t.name}.{k} expression references undefined control {ref[1]}")
        if self.output is None:
            errs.append("no output tool")
        for p in self.published:
            if p.tool.name not in self.tools:
                errs.append(f"published {p.name} on missing tool")
        return errs

    def _tools_table(self, offset=(0, 0)):
        tt = Ordered()
        for name, t in self.tools.items():
            tt[name] = t.to_lua_obj()
        return tt

    def macro_text(self, macro_name, macro_type="MacroOperator"):
        errs = self.check()
        if errs:
            raise ValueError("graph errors: " + "; ".join(errs))
        ins = Ordered()
        used = set()
        for i, p in enumerate(self.published):
            key = p.cid or f"{p.tool.name}_{p.inp}".replace(".", "_")
            if key in used:
                key = f"{key}_{i}"
            used.add(key)
            d = OrderedDict(SourceOp=p.tool.name, Source=p.inp, Name=p.name)
            if p.group is not None:
                d["ControlGroup"] = p.group
            if p.page:
                d["Page"] = p.page
            if p.default is not None and not isinstance(p.default, str):
                d["Default"] = p.default
            ins[key] = Call("InstanceInput", d)
        body = OrderedDict()
        body["CtrlWZoom"] = False
        body["NameSet"] = True
        body["CustomData"] = OrderedDict(
            Path=OrderedDict(Map=OrderedDict({"Setting:": f"Templates:/Edit/Titles/"})),
            HelpPage=f"Cinematic Mass Elevation Templates - {macro_name}")
        body["Inputs"] = ins
        body["Outputs"] = OrderedDict(
            MainOutput1=Call("InstanceOutput", OrderedDict(SourceOp=self.output.name, Source="Output")))
        body["ViewInfo"] = Call("GroupInfo", OrderedDict(Pos=[0.0, 0.0]))
        body["Tools"] = self._tools_table()
        top = OrderedDict()
        top["Tools"] = Ordered({macro_name: Call(macro_type, body)})
        top["ActiveTool"] = macro_name
        hdr = (f"-- {macro_name}: Cinematic Mass Elevation Templates\n"
               f"-- Generated Fusion macro ({macro_type}). Install into\n"
               f"--   <Fusion support>/Templates/Edit/Titles/ to use as an Edit-page title,\n"
               f"-- or drag this file into the Fusion page node editor.\n")
        return hdr + lua(top) + "\n"

    def comp_text(self):
        errs = self.check()
        if errs:
            raise ValueError("graph errors: " + "; ".join(errs))
        end = self.frames - 1
        top = OrderedDict()
        top["CurrentTime"] = 0
        top["RenderRange"] = [0, end]
        top["GlobalRange"] = [0, end]
        top["HiQ"] = True
        top["PlaybackUpdateMode"] = 0
        top["Version"] = "Fusion 18 (generated)"
        top["SavedOutputs"] = 0
        top["HeldTools"] = 0
        top["DisabledTools"] = 0
        top["LockedTools"] = 0
        top["AudioOffset"] = 0
        top["Resumable"] = True
        top["OutputClips"] = {}
        top["Tools"] = self._tools_table()
        top["Prefs"] = OrderedDict(Comp=OrderedDict(
            FrameFormat=OrderedDict(Name="Custom", Width=self.W, Height=self.H, AspectX=1.0, AspectY=1.0,
                                    Rate=float(self.fps), GuideRatio=1.77777777777778, DepthFull=2,
                                    DepthPreview=2, DepthInteractive=2),
            Unsorted=OrderedDict(GlobalStart=0, GlobalEnd=end, RenderStart=0, RenderEnd=end),
        ))
        hdr = (f"-- {self.name}: Cinematic Mass Elevation Templates (flat composition)\n"
               f"-- Final image: tool '{self.output.name}'. In Resolve's Fusion page connect it to MediaOut1.\n")
        return hdr + "Composition " + lua(top) + "\n"
