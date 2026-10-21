"""v2 planner: everything from v1 plus a continuously animated doodle universe.

Layers (all deterministic, seeded):
  * far    - ~70 tiny twinkling stars / dots drifting everywhere, always alive
  * mid    - ~14 slots of hearts, notes, butterflies, daisies, clouds, swirls,
             arrows, wavy lines, sound waves, suns, constellations - each slot
             respawns as soon as its previous doodle fades, so something is
             always moving and the arrangement keeps evolving
  * big    - occasional large illustrations (rainbow, big moon, sun, cloud)
             that draw themselves in and out
  * petals - soft falling petals during the slow-motion hug
  * finale - extra hearts and stars gathering in the last seconds
"""
import json
import os

import numpy as np

import analyze as A
from common import FPS, N_OUT, SLOW_A, SLOW_B, WORK

rng = np.random.default_rng(11)


def main():
    audio = A.analyse_audio()
    masks, motion, top = A.analyse_video()
    np.save(os.path.join(WORK, "masks_lo.npy"), masks)
    ev = A.plan(masks, motion, top, audio)
    forbid = A.forbid_stack(masks)

    def place(kind, f0, life, p0_fn, v_fn, radius, tries=10, max_ov=0.45, **kw):
        best = None
        for _ in range(tries):
            p0, v = p0_fn(), v_fn()
            o = A.overlap(forbid, A.linear(p0, v), f0, life, radius)
            if best is None or o < best[0]:
                best = (o, p0, v)
            if o == 0:
                break
        if best[0] <= max_ov:
            ev.append(dict(kind=kind, f0=int(f0), life=int(life), p0=[float(best[1][0]), float(best[1][1])],
                           v=[float(best[2][0]), float(best[2][1])], a=[0.0, 0.0], **kw))
            return True
        return False

    anywhere = lambda m=40: (rng.uniform(m, 1920 - m), rng.uniform(m, 1080 - m))

    # far layer: tiny stars that never stop twinkling
    for slot in range(72):
        f = -int(rng.uniform(0, 7) * FPS)
        while f < N_OUT:
            life = int(rng.uniform(5, 9) * FPS)
            p = anywhere(20)
            ev.append(dict(kind="tinystar", f0=int(max(0, f)), life=int(life + min(0, f)),
                           p0=[float(p[0]), float(p[1])],
                           v=[float(rng.uniform(-14, 14)), float(rng.uniform(-10, 4))], a=[0.0, 0.0],
                           size=float(rng.uniform(5, 12)), color=int(rng.integers(0, 7)),
                           dot=bool(rng.random() < 0.35)))
            f += life - int(rng.uniform(0.5, 1.5) * FPS)

    # mid layer: always-busy slots, the pool evolves through the song
    def pool(t):
        if SLOW_A / FPS <= t < SLOW_B / FPS:
            return ["heart", "butterfly", "heart_wing", "daisy", "swirl", "cloud", "dheart", "sparkle_ring"]
        if t < 28:
            return ["note", "swirl", "cloud", "daisy", "wave", "constellation", "star5", "sun"]
        if t < 55:
            return ["note", "soundwave", "heart", "butterfly", "arrow", "wave", "daisy", "swirl", "cloud"]
        return ["note", "heart", "butterfly", "soundwave", "constellation", "arrow", "daisy", "dheart",
                "swirl", "sun", "star5", "cloud"]

    moving = {"heart": (0, -55), "dheart": (0, -45), "heart_wing": (20, -40), "note": (15, -30),
              "butterfly": (60, -25), "cloud": (35, 0), "star5": (0, -20)}
    for slot in range(14):
        f = int(slot * 0.45 * FPS)
        while f < N_OUT - FPS:
            t = f / FPS
            k = pool(t)[rng.integers(len(pool(t)))]
            life = int(rng.uniform(3.5, 6.5) * FPS)
            vx, vy = moving.get(k, (0, 0))
            sign = 1 if rng.random() < 0.5 else -1
            size = float(rng.uniform(30, 50) if k not in ("cloud", "constellation", "swirl", "wave", "arrow")
                         else rng.uniform(55, 90))
            place(k, f, life, lambda: anywhere(90),
                  lambda: (sign * vx * rng.uniform(0.6, 1.3), vy * rng.uniform(0.7, 1.3)),
                  size, size=size, color=int(rng.integers(0, 7)), rot=float(rng.uniform(-0.5, 0.5)),
                  dir=sign)
            f += life - int(rng.uniform(0.6, 1.4) * FPS)

    # big illustrations at selected moments, upper corners / empty wall
    bigs = [(3.0, "rainbow"), (14.0, "bigmoon"), (24.0, "cloud_big"), (36.0, "sun_big"), (49.0, "rainbow"),
            (62.0, "bigmoon"), (73.0, "constellation_big"), (SLOW_A / FPS + 3.0, "rainbow"),
            (103.0, "sun_big"), (108.5, "bigmoon")]
    for t0, k in bigs:
        f = int(t0 * FPS)
        cands = [(250, 190), (1670, 190), (260, 880), (1660, 880), (960, 110)]
        place(k, f, int(5.5 * FPS), lambda: cands[rng.integers(len(cands))], lambda: (0, 0),
              130, tries=12, max_ov=0.5, size=125.0, color=int(rng.integers(0, 6)))

    # soft petals during the hug
    for i in range(36):
        f = SLOW_A + int(rng.uniform(0, (SLOW_B - SLOW_A) - 2 * FPS))
        ev.append(dict(kind="petal", f0=f, life=int(rng.uniform(4, 6) * FPS),
                       p0=[float(rng.uniform(80, 1840)), float(rng.uniform(-60, 200))],
                       v=[float(rng.uniform(-30, 30)), float(rng.uniform(60, 120))], a=[0.0, 0.0],
                       size=float(rng.uniform(14, 24)), color=int(rng.choice([0, 5, 6, 1]))))

    # finale: hearts and stars gather before the fade
    for i in range(26):
        f = N_OUT - int(rng.uniform(1.2, 5.0) * FPS)
        k = ["heart", "star5", "dheart", "sparkle"][i % 4]
        place(k, f, N_OUT - f, lambda: anywhere(100), lambda: (rng.uniform(-20, 20), rng.uniform(-50, -20)),
              30, tries=6, max_ov=0.6, size=float(rng.uniform(26, 44)), color=int(rng.integers(0, 7)))

    ev.sort(key=lambda e: e["f0"])
    kinds = {}
    for e in ev:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print("events", len(ev), kinds)
    with open(os.path.join(WORK, "plan_v2.json"), "w") as fh:
        json.dump(dict(audio=dict(bpm=audio["bpm"], beats=audio["beats"],
                                  downbeat_phase=audio["downbeat_phase"]), events=ev), fh)


if __name__ == "__main__":
    main()
