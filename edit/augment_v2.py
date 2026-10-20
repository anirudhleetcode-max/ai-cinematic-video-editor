"""Add a school of colourful fish and bold travelling line art to plan_v2."""
import json
import os

import numpy as np

import analyze as A
from common import FPS, N_OUT, WORK

rng = np.random.default_rng(23)
path = os.path.join(WORK, "plan_v2.json")
plan = json.load(open(path))
ev = plan["events"]
forbid = A.forbid_stack(np.load(os.path.join(WORK, "masks_lo.npy")))
FISH_COLORS = [2, 3, 0, 7, 4, 1]          # turquoise, coral, pink, purple, yellow, lavender
added = 0
f = 45
while f < N_OUT - 3 * FPS:
    d = 1 if rng.random() < 0.5 else -1
    speed = rng.uniform(170, 330)
    life = int(min(N_OUT - f, 2160 / speed * FPS))
    best = None
    for _ in range(20):
        y = rng.choice([rng.uniform(60, 330), rng.uniform(700, 1000)])
        p0 = (-120 if d > 0 else 2040, y)
        v = (d * speed, rng.uniform(-15, 15))
        o = A.overlap(forbid, A.linear(p0, v), f, life, 40)
        if best is None or o < best[0]:
            best = (o, p0, v)
    _, p0, v = best
    for j in range(1 + int(rng.random() < 0.4)):       # sometimes two swim together
        ev.append(dict(kind="fish", f0=int(f + j * 8), life=life, p0=[float(p0[0] - d * j * 130), float(p0[1] + j * 55)],
                       v=[float(v[0]), float(v[1])], a=[0.0, 0.0], size=float(rng.uniform(38, 52) - j * 8),
                       color=int(FISH_COLORS[(added + j) % len(FISH_COLORS)]), dir=int(d)))
        added += 1
    f += int(rng.uniform(4.5, 8) * FPS)
# bold travelling line art: big squiggles and spirals drawing themselves
for f in range(30, N_OUT - 4 * FPS, int(2.6 * FPS)):
    k = ["wave", "swirl", "arrow", "wave", "constellation"][rng.integers(5)]
    for _ in range(12):
        p0 = (rng.uniform(140, 1780), rng.uniform(120, 960))
        if A.overlap(forbid, A.linear(p0, (0, 0)), f, 4 * FPS, 70) < 0.2:
            ev.append(dict(kind=k, f0=int(f), life=int(4 * FPS), p0=[float(p0[0]), float(p0[1])],
                           v=[float(rng.uniform(-25, 25)), float(rng.uniform(-15, 15))], a=[0.0, 0.0],
                           size=float(rng.uniform(70, 110)), color=int(rng.integers(0, 9)),
                           rot=float(rng.uniform(-0.5, 0.5)), dir=1 if rng.random() < 0.5 else -1))
            break
ev.sort(key=lambda e: e["f0"])
json.dump(plan, open(path, "w"))
print("fish added", added, "total events", len(ev))
