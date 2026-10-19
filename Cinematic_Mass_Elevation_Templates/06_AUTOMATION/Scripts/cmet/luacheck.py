"""Parse generated Fusion files with a real Lua interpreter (lupa).

Fusion's .setting/.comp text is a Lua table constructor using a few
constructor functions (ordered, Input, BezierSpline, FuID, Gradient, ...).
We stub every global as a constructor that records its name, evaluate the
file, and convert the result back into Python for structural checks.
This proves the files are syntactically valid Lua tables with the intended
structure. It does NOT prove Fusion will render them as intended.
"""
from __future__ import annotations

import lupa

_PRELUDE = r"""
local function mk(name)
  return function(t)
    if type(t) ~= 'table' then t = {t} end
    t.__ctor = name
    return t
  end
end
local env = setmetatable({}, {__index = function(_, k)
  if k == 'ordered' then return function() return mk('ordered') end end
  return mk(k)
end})
function __load(src)
  local chunk, err = load('return ' .. src, 'fusion', 't', env)
  if not chunk then return nil, err end
  local ok, res = pcall(chunk)
  if not ok then return nil, res end
  return res
end
"""


def _strip_comments(src: str) -> str:
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("--"))


def parse(src: str):
    rt = lupa.LuaRuntime(unpack_returned_tuples=True)
    rt.execute(_PRELUDE)
    body = _strip_comments(src).strip()
    if body.startswith("Composition"):
        body = body[len("Composition"):].strip()
        ctor = "Composition"
    else:
        ctor = None
    res = rt.globals().__load(body)
    if isinstance(res, tuple):
        val, err = res
        if val is None:
            raise SyntaxError(str(err))
        res = val
    if res is None:
        raise SyntaxError("empty result")
    return _py(res), ctor


def _py(v):
    if lupa.lua_type(v) == "table":
        keys = list(v.keys())
        d = {}
        for k in keys:
            d[k] = _py(v[k])
        return d
    return v


def tools_of(tree, ctor=None):
    """Return {name: (type, inputs_dict, raw)} for a .setting (macro) or .comp."""
    tools = tree.get("Tools", {})
    out = {}
    for name, t in tools.items():
        if name == "__ctor":
            continue
        if isinstance(t, dict) and t.get("__ctor") in ("MacroOperator", "GroupOperator"):
            for n2, t2 in t.get("Tools", {}).items():
                if n2 == "__ctor":
                    continue
                out[n2] = (t2.get("__ctor"), {k: v for k, v in t2.get("Inputs", {}).items() if k != "__ctor"}, t2)
        else:
            out[name] = (t.get("__ctor"), {k: v for k, v in t.get("Inputs", {}).items() if k != "__ctor"}, t)
    return out
