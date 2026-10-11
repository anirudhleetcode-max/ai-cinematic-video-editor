#!/usr/bin/env python3
"""Render a customised title with the reference renderer (no Resolve needed).

Examples
  python render_title.py T01 --set MAIN_TITLE="RAGHAVA" --set SUBTITLE="THE RETURN" --out raghava.mp4
  python render_title.py T40 --config my_title.json --res 3840x2160 --codec prores --out final.mov
  python render_title.py T07 --set MAIN_TITLE="ఫెయిలథాన్" --set FONT_FAMILY=telugu --out telugu.mp4
  python render_title.py --list

--config takes a JSON object of parameters (see the template's
configuration/default_params.json). --set overrides individual keys.
Outputs: H.264 MP4 (default), ProRes 422 HQ MOV (--codec prores), or a PNG
sequence (--codec png, written to a folder). Audio is the procedural cue mix
unless --no-audio is given.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from cmet.base import PARAM_SCHEMA, render, Ctx  # noqa: E402
from cmet import export as X  # noqa: E402
from cmet import elements as E  # noqa: E402


def coerce(schema, key, val):
    default, _, kind = schema[key]
    if kind in ("float",):
        return float(val)
    if kind == "frame":
        return int(float(val))
    return str(val).replace("\\n", "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template", nargs="?")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--config")
    ap.add_argument("--res", default="1920x1080")
    ap.add_argument("--codec", choices=["h264", "prores", "png"], default="h264")
    ap.add_argument("--out")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    designs = sorted(f[1:3] for f in os.listdir(os.path.join(HERE, "cmet", "designs"))
                     if f.startswith("t") and f.endswith(".py"))
    if a.list or not a.template:
        for n in designs:
            d = importlib.import_module(f"cmet.designs.t{n}").DESIGN
            print(f"{d.ID}  {d.NAME:32s} {d.CATEGORY}")
        return
    n = int(a.template.upper().lstrip("T"))
    d = importlib.import_module(f"cmet.designs.t{n:02d}").DESIGN
    ov = {}
    sch = d.schema()
    if a.config:
        for k, v in json.load(open(a.config, encoding="utf-8")).items():
            if k in sch:
                ov[k] = coerce(sch, k, v)
    for kv in a.set:
        k, v = kv.split("=", 1)
        k = k.strip().upper()
        if k not in sch:
            sys.exit(f"unknown parameter {k}; see configuration/default_params.json")
        ov[k] = coerce(sch, k, v)
    W, H = (int(x) for x in a.res.lower().split("x"))
    out = a.out or f"{d.ID}_{d.SLUG}_custom." + {"h264": "mp4", "prores": "mov", "png": "png"}[a.codec]
    if a.codec == "png":
        import cv2
        os.makedirs(out, exist_ok=True)
        p = d.params(ov)
        c = Ctx(d, p, W, H)
        for f in range(int(p["DURATION"])):
            c.fr, c.t = f, f / 24
            cv2.imwrite(os.path.join(out, f"frame_{f:04d}.png"),
                        cv2.cvtColor(E.to_uint8(d.frame(c)), cv2.COLOR_RGB2BGR))
        print("wrote", out)
        return
    wav = None
    if not a.no_audio:
        wav = os.path.join(tempfile.mkdtemp(), "audio.wav")
        X.make_audio(d, wav, d.params(ov))
    st = render(d, out, W, H, ov, audio=wav, codec=a.codec, crf=16 if W > 1920 else 18)
    print(f"wrote {out} ({st['frames']} frames, {st['seconds']}s, ffmpeg rc={st['rc']})")
    sys.exit(st["rc"])


if __name__ == "__main__":
    main()
