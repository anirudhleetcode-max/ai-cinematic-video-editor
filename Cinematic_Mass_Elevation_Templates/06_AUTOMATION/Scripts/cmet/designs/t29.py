"""T29 - Cinematic Letter Assembly."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, subtitle, drop_shadow
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_sprite
from . import _c_helpers as X

IVORY = Material(base=(0.92, 0.89, 0.83), spec=(1.0, 0.96, 0.9), spec_power=36, spec_gain=0.4, diffuse=0.8,
                 ambient=0.22, metal=0.05, bevel=0.04, texture="grain", tex_amount=0.05, rim=(1.0, 0.9, 0.75),
                 seed=29)

# designed (non-uniform) rhythm: relative gaps between successive arrivals (multiplied by the stagger interval)
RHYTHM = [1.0, 1.7, 0.7, 1.3, 0.6, 1.5, 0.8, 2.1, 0.9, 1.2, 0.7, 1.6]
N_SLOTS = 8


def arrival_order(n):
    """Outer letters first, alternating sides, centre letter last (lands on the impact)."""
    c = (n - 1) / 2
    idx = sorted(range(n), key=lambda i: (-abs(i - c), i > c))
    return idx


def offsets(n, stagger):
    """Start offset (frames) for each letter index."""
    order = arrival_order(n)
    t, out = 0.0, [0.0] * n
    for j, i in enumerate(order):
        if j > 0:
            t += stagger * RHYTHM[(j - 1) % len(RHYTHM)]
        out[i] = t
    return out


class T29(Design):
    ID = "T29"
    NAME = "Cinematic Letter Assembly"
    SLUG = "Cinematic_Letter_Assembly"
    CATEGORY = "F - Cinematic Typography and Camera Movement"
    CONCEPT = "An elegant credit-style build: each letter flies in on its own arc and clicks into place on a light rule."
    ENTRANCE = ("Letters travel in individually from depth on curved, rotating paths. Outer letters arrive first, "
                "alternating sides, with a designed non-uniform rhythm; the centre letter lands last.")
    REVEAL = "Each landing ticks a glint on the champagne baseline; at the impact frame the rule flashes and a sheen crosses the word."
    CAMERA = "Gentle locked-off push; depth comes from the letters' own 3D arcs."
    MATERIAL = "Ivory porcelain lettering with a soft bevel; champagne (ACCENT) baseline rule and glints."
    EXIT = "Letters lift away in reverse order with the same rhythm, rotating back into depth."
    TECHNIQUES = ["per-glyph 3D arcs (preview)", "slot-based stagger (Fusion)", "designed rhythm", "landing glints",
                  "baseline rule draw", "sheen sweep", "staggered reverse exit"]
    DURATION_FRAMES = 180
    DEFAULTS = dict(MAIN_TITLE="ASCENDANT", SUBTITLE="A STORY IN NINE LETTERS", FONT_FAMILY="cinzel_bold",
                    TEXT_COLOR="#EDE6D8", ACCENT_COLOR="#C9A46A", ANIMATION_START=8, ANIMATION_DURATION=28,
                    IMPACT_FRAME=82, HOLD_DURATION=56, EXIT_START=140, EXIT_DURATION=28, LETTER_SPACING=0.12,
                    TITLE_WIDTH=0.7, SHADOW_STRENGTH=0.55, STAGGER_FRAMES=4)
    SOUND = [(0, "atmos", "Warm room tone"), (8, "whoosh", "First letters fly in"), (20, "shimmer", "Soft ticks per landing"),
             (40, "whoosh", "Mid letters"), (76, "rwhoosh", "Centre letter approach"), (82, "impact", "Soft lock-in hit"),
             (83, "shimmer", "Sheen sweep"), (140, "whoosh", "Letters lift away"), (160, "tail", "Airy tail")]
    FUSION_NOTES = [
        "Per-letter animation: the preview animates every glyph on its own 3D arc. Fusion's per-character Text+ "
        "Follower could not be verified offline, so the Fusion graph keeps ONE editable Text+ and staggers 8 "
        "vertical slices ('LetterSlot0..7', RectangleMask slots across the title width) instead. For other title "
        "lengths, adjust the slot masks' Center/Width to match the letters.",
        "Extra control 'Stagger Interval (frames)' (StaggerFrames) sets the base interval between arrivals; the "
        "designed rhythm multiplies it per slot. 'Reveal Duration' (AnimDuration) is the travel time of each "
        "letter/slot. In the preview the interval is the design default STAGGER_FRAMES (4).",
    ]

    def _path(self, i, n, k, W, H):
        """Designed start pose for letter i (dx, dy, dz, rx, ry, rz)."""
        side = -1 if i < (n - 1) / 2 else (1 if i > (n - 1) / 2 else 0)
        h = K.hash01(i, 29)
        dx = side * (0.18 + 0.12 * h) * W
        dy = (-0.28 if i % 2 == 0 else 0.22) * H
        dz = (0.9 + 0.8 * K.hash01(i, 3)) * H
        rx = (55 if i % 2 == 0 else -45) * (0.7 + 0.3 * h)
        ry = side * 50 + (1 - abs(side)) * 30
        rz = (-1) ** i * (14 + 18 * h)
        return dx, dy, dz, rx, ry, rz

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k, fr = c.p, c.H, c.W, c.t, c.k, c.fr
        acc = K.col(p["ACCENT_COLOR"])
        tc = K.col(p["TEXT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        hit = c.hit(0.02, 0.35)
        sp = c.title()
        hx, hy = c.hero()
        stg = p["STAGGER_FRAMES"]
        dur = c.reveal

        # --- warm studio backdrop
        key = "bg"
        if key not in c.cache:
            b = K.vgrad(H, W, (0.06, 0.052, 0.045), (0.018, 0.016, 0.015))
            b += (K.soft_spot(H, W, hx / (H / 2), hy / (H / 2) - 0.2, 1.5, 0.8, 1.2) * 0.05)[..., None] * \
                np.array([1.0, 0.92, 0.8], np.float32)
            c.cache[key] = b * bgI
        bg = c.cache[key].copy()
        if p["PARTICLE_INTENSITY"] > 0:
            P = c.cache.get("motes")
            if P is None:
                P = c.cache["motes"] = E.Particles(int(70 * p["PARTICLE_INTENSITY"]), seed=29, z=(0.6, 2.5))
            x, y = P.drift(t, vel=(0.006, -0.004), turb=0.02, freq=0.25)
            bg += E.particle_layer(H, W, P, x, y, acc * 0.5 + 0.3, 1.4, 0.12, dof=1.0, glow=0.5)

        # --- letters
        sh = c.shaded(IVORY)
        rgb, a = sh.shade(light=(-0.35, -0.7, 0.6), base=tc, rim_gain=0.25 + 1.0 * hit, rim_dir=(0, -1),
                          sweep=(-0.9 + 1.8 * K.ease_in_out(K.prog(t, imp + 0.05, 0.9)), 0.12, 0.35,
                                 1.0 * (0 < t - imp - 0.05 < 0.9)))
        cam = c.cam(zoom=1.0 + 0.04 * K.ease_in_out(K.prog(t, 0, c.dur)), fov_scale=1.5)
        L = c.layer()
        gl = sp.glyphs
        n = len(gl)
        offs = offsets(n, stg)
        order = arrival_order(n)
        rev_rank = {i: j for j, i in enumerate(order[::-1])}  # exit: last arrival leaves first
        land_glints = []
        for i, g in enumerate(gl):
            t0 = c.start + offs[i] / c.fps
            u = K.prog(t, t0, dur)
            if u <= 0:
                continue
            dx, dy, dz, rx, ry, rz = self._path(i, n, k, W, H)
            te = c.exit_start + rev_rank[i] * stg * 0.6 / c.fps        # exit: reverse order, same rhythm
            v = K.ease_in(K.prog(t, te, c.exit_dur * 0.6), 2.5)

            def pose(uu):
                e = K.ease_out(uu, 4)
                settle = 0.035 * math.sin(min(1.0, K.prog(t, t0 + dur, 0.3)) * math.pi) if t > t0 + dur else 0.0
                w = 1 - e
                arc = math.sin(e * math.pi) * 0.08 * H * (1 if i % 2 else -1)   # curved path
                return (dx * w + arc * 0.5, dy * w + arc - v * 0.22 * H, dz * w + v * 0.6 * H,
                        rx * w - 35 * v, ry * w, rz * w + 10 * v * (1 if i % 2 else -1),
                        1.0 + settle, g.center[0], g.center[1])
            op = K.smooth(u * 3) * (1 - K.smooth(v * 1.4))
            mb = p["MOTION_BLUR_AMOUNT"]
            if mb > 0 and u < 0.9:     # motion trail echoes while the letter is travelling
                for lag, wgt in ((0.05, 0.22), (0.1, 0.12)):
                    place_sprite(L, cam, rgb, a, g.box, sp.anchor, (hx, hy, 0), 1.0, (0, 0, p["TEXT_ROTATION"]),
                                 pose(max(0.0, u - lag * mb)), op * wgt)
            place_sprite(L, cam, rgb, a, g.box, sp.anchor, (hx, hy, 0), 1.0, (0, 0, p["TEXT_ROTATION"]), pose(u), op)
            if t >= t0 + dur * 0.85:
                land_glints.append((g, K.pulse(t, t0 + dur * 0.85, 0.02, 0.35)))
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.55, (6, 16), 18, k)
        img = bg * (1 - L.a[..., None]) + L.rgb

        # --- champagne baseline rule + landing glints
        by = H / 2 + hy + sp.ink_h * 0.5 * cam.zoom + 22 * k
        first = c.start + (dur * 0.85)
        draw = K.ease_in_out(K.prog(t, first, imp - first))
        fade = 1 - K.smooth(K.prog(ex, 0.3, 0.6))
        if draw > 0 and fade > 0:
            half = sp.ink_w * 0.56 * draw * cam.zoom
            cxp = W / 2 + hx
            buf = np.zeros((H, W, 3), np.float32)
            cv2.line(buf, (int((cxp - half) * 4), int(by * 4)), (int((cxp + half) * 4), int(by * 4)),
                     tuple(float(v) for v in acc * (0.55 + 1.2 * hit)), max(1, int(1.5 * k)), cv2.LINE_AA, shift=2)
            for g, gv in land_glints:
                if gv > 0.01:
                    gx = cxp + (g.center[0] - sp.anchor[0]) * cam.zoom
                    cv2.circle(buf, (int(gx * 4), int(by * 4)), max(1, int(3 * k * 4)),
                               tuple(float(v) for v in (acc + 0.4) * gv * 1.5), -1, cv2.LINE_AA, shift=2)
            img += (buf + K.blur(buf, 6 * k) * 1.5 + K.blur(buf, 30 * k) * 0.8 * hit) * fade * p["GLOW_STRENGTH"]
        img = subtitle(c, img, cam, imp + 0.45, c.exit_start - 0.1, tc * 0.7 + acc * 0.15, y_rel=0.95,
                       tracking=0.5)
        img = X.grade_fast(img, shadows=(0.004, 0.002, 0.0), contrast=1.05)
        return c.finish(img, vignette=0.55, grain=0.03, bloom=(0.85, 0.4))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p, extra=[("StaggerFrames", "Stagger Interval (frames)", p["STAGGER_FRAMES"], 0, 24, True,
                                     "Timing")])
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S, D = ctl("AnimStart"), ctl("AnimDuration")
        ST = ctl("StaggerFrames")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        BG = ctl("BackgroundIntensity")

        g.at(0, 0)
        bg = F.gradient_bg(g, "Studio", [(0, "#050404", 1), (1, "#100e0c", 1)])
        bg = F.light_spot(g, "TopPool", bg, (1.0, 0.92, 0.8), (0.5, 0.62), 1.5, 0.8, 0.6, blend=f"0.1*{BG}")
        bg = F.particles(g, "Motes", bg, number=3, lifespan=300, velocity=0.0008, angle=40, angle_var=180, size=0.3,
                         color=(0.9, 0.8, 0.6), region="CubeRgn", region_size=(2.4, 1.4, 1.0), center_y=0.0,
                         turbulence=0.05, glow=2)

        g.at(0, 2)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Cinzel", "Bold", 0.1, 1.12, color=p["TEXT_COLOR"])
        shade = F.fill_material(g, "IvoryShade", title, [(0, "#a39a8a", 1), (0.55, "#ffffff", 1), (1, "#d8d0c2", 1)])
        face = F.merge(g, "IvoryFace", title, shade, mode="Multiply", blend=0.6)
        sheen = F.light_sweep(g, "Sheen", face, title, f"{I} + 1", 22, angle=25, width=0.05, peak=0.6,
                              color=(1, 0.97, 0.9))
        g.at(0, 4)
        holder = F.solid(g, "SlotHolder", (0, 0, 0), alpha=0.0)
        acc_img = F.solid(g, "AssemblyHolder", (0, 0, 0), alpha=0.0)
        cur = acc_img
        n = N_SLOTS
        offs = offsets(n, 1.0)          # in units of StaggerFrames
        order = arrival_order(n)
        x0, x1 = 0.17, 0.83
        sw = (x1 - x0) / n
        for i in range(n):
            g.at(i % 4 * 6, 4 + (i // 4) * 2)
            cxs = x0 + sw * (i + 0.5)
            slot = F.rect(g, f"LetterSlot{i}", (cxs, 0.5), sw + 0.002, 0.4, 0.0)
            sl = F.merge(g, f"LetterSlice{i}", holder, sheen)
            F.masked(sl, slot)
            side = -1 if i < (n - 1) / 2 else 1
            u = prog(f"{S} + {ST}*{offs[i]:.2f}", D)
            e = e_out(u, 4)
            rank = order[::-1].index(i)
            v = e_in(prog(f"{ctl('ExitStart')} + {ST}*{rank * 0.6:.2f}", f"{ctl('ExitDuration')}*0.6"), 2.5)
            dx = side * (0.1 + 0.06 * K.hash01(i, 29))
            dy = 0.25 if i % 2 == 0 else -0.2
            arc = 0.04 * (1 if i % 2 else -1)
            xf = F.xf(g, f"LetterMove{i}", sl,
                      center=f"Point(0.5 + {dx:.3f}*(1 - {e}) + {arc * 0.5:.3f}*sin({e}*3.14159), "
                             f"0.5 + {dy:.3f}*(1 - {e}) + {arc:.3f}*sin({e}*3.14159) + 0.2*{v})",
                      size=f"(1 + 0.9*(1 - {e}))*(1 - 0.35*{v})",
                      angle=f"{(-1) ** i * 22:.1f}*(1 - {e}) - {(-1) ** i * 10:.1f}*{v}")
            xf.set(Pivot=[cxs, 0.5])
            blur = F.blur(g, f"LetterBlur{i}", xf, f"10*(1 - {e})*{ctl('MotionBlurAmount')}")
            cur = F.merge(g, f"LetterLand{i}", cur, blur,
                          blend=f"{clamp01(f'{u}*3')}*(1 - {clamp01(f'{v}*1.4')})")
        g.at(0, 9)
        placed = F.title_placement(g, "TitlePlace", cur, size_expr=f"1 + 0.04*{e_inout(prog(0, g.frames))}")
        shp = F.cc(g, "ShadowMatte", placed, gain=0)
        shp = F.xf(g, "ShadowOffset", shp, center="Point(0.503, 0.485)")
        shp = F.blur(g, "ShadowSoft", shp, 10)
        scene = F.merge(g, "ShadowMerge", bg, shp, blend=f"0.55*{ctl('ShadowStrength')}")
        scene = F.merge(g, "LettersOverStudio", scene, placed)
        g.at(0, 11)
        rule = F.accent_solid(g, "BaselineRuleColor", 1.0)
        rm = F.rect(g, "BaselineRuleShape", (0.5, 0.435), 0.01, 0.0018, 0.0006)
        first = f"({S} + 0.85*{D})"
        rm.expr("Width", f"0.68*{e_inout(prog(first, f'({I} - {first})'))}", 0.01)
        F.masked(rule, rm)
        rglow = F.softglow(g, "BaselineGlow", rule, 6, gain=f"{ctl('GlowStrength')}*(0.6 + 1.5*{decay(I, 10)})",
                           threshold=0.05)
        scene = F.merge(g, "BaselineRule", scene, rglow, mode="Screen",
                        blend=f"1 - {e_inout(clamp01(f'({ex} - 0.3)/0.6'))}")
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.026, 1.9,
                                    color=(0.8, 0.76, 0.68), y_off=-0.1)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 10", f"{ctl('ExitStart')} - 2", 14, 10))
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T29()
