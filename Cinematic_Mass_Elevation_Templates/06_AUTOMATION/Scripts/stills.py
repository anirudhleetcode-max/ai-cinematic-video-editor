"""Render a still sheet for a design: python stills.py t05 10,50,90 out.jpg [PARAM=value ...]"""
import sys, importlib, cv2, numpy as np
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmet.base import Ctx
from cmet import elements as E
mod = importlib.import_module("cmet.designs." + sys.argv[1]); D = mod.DESIGN
frames = [int(x) for x in sys.argv[2].split(",")]
out = sys.argv[3]
ov = {}
for a in sys.argv[4:]:
    k, v = a.split("=", 1); ov[k] = type(D.params()[k])(v) if k in D.params() else v
p = D.params(ov); c = Ctx(D, p, 1920, 1080); ims = []
for f in frames:
    c.fr = f; c.t = f / 24
    ims.append(cv2.resize(cv2.cvtColor(E.to_uint8(D.frame(c)), cv2.COLOR_RGB2BGR), (640, 360), interpolation=cv2.INTER_AREA))
while len(ims) % 3: ims.append(np.zeros_like(ims[0]))
rows = [np.hstack(ims[i:i+3]) for i in range(0, len(ims), 3)]
cv2.imwrite(out, np.vstack(rows))
full = cv2.cvtColor(E.to_uint8(D.frame(c)), cv2.COLOR_RGB2BGR)
cv2.imwrite(out.replace(".jpg", "_full.jpg"), full)
