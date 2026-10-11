#!/usr/bin/env python3
"""Normalise CATEGORY strings to the eight categories of the brief."""
import os, re, sys
CATS = [(1, 5, "A - Dark, Powerful Mass Elevation"), (6, 10, "B - Fire, Explosions and Impact"),
        (11, 15, "C - 3D Metal and Premium Materials"), (16, 20, "D - Mythic, Epic and Fantasy"),
        (21, 25, "E - Sci-Fi and Futuristic Motion Graphics"), (26, 30, "F - Cinematic Typography and Camera Movement"),
        (31, 35, "G - Atmospheric and Environmental Cinema"), (36, 40, "H - Signature Hero Elevations")]
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cmet", "designs")
ids = [int(a) for a in sys.argv[1:]] or range(1, 41)
for i in ids:
    p = os.path.join(D, f"t{i:02d}.py")
    if not os.path.exists(p):
        continue
    cat = next(c for a, b, c in CATS if a <= i <= b)
    s = open(p).read()
    s2 = re.sub(r'^    CATEGORY = .*$', f'    CATEGORY = "{cat}"', s, count=1, flags=re.M)
    if s2 != s:
        open(p, "w").write(s2)
    print(f"T{i:02d}", cat)
