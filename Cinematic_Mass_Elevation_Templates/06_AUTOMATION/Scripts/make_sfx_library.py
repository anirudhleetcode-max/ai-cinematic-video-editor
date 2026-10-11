#!/usr/bin/env python3
"""Regenerate the one-shot SFX library in 02_SHARED_ASSETS/Sound_Effects (all synthesised)."""
import os
import sys

import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cmet import sfx  # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "..", "02_SHARED_ASSETS", "Sound_Effects"))
LIB = [("impact_heavy", lambda: sfx.impact(1)), ("sub_drop", lambda: sfx.sub_drop(2)),
       ("metal_hit", lambda: sfx.metal_hit(3)), ("whoosh", lambda: sfx.whoosh(4)),
       ("reverse_whoosh", lambda: sfx.whoosh(5, 1.2, True)), ("riser_3s", lambda: sfx.riser(6, 3.0)),
       ("debris", lambda: sfx.debris(7)), ("shimmer", lambda: sfx.shimmer(8)), ("tail", lambda: sfx.tail(9)),
       ("thunder", lambda: sfx.thunder(10)), ("electric_crackle", lambda: sfx.crackle(11)),
       ("digital_tone", lambda: sfx.digital(14)), ("glitch", lambda: sfx.glitch(15)),
       ("swell", lambda: sfx.swell(16)), ("ice_crackle", lambda: sfx.ice(17)), ("hammer", lambda: sfx.hammer(20)),
       ("heartbeat", lambda: sfx.heartbeat(21))]

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, fn in LIB:
        s = sfx.norm(fn()) * 0.8
        with wave.open(os.path.join(OUT, f"{name}.wav"), "wb") as w:  # mono 16-bit 48 kHz
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sfx.SR)
            w.writeframes((np.clip(s, -1, 1) * 32767).astype("<i2").tobytes())
        print("wrote", name)
