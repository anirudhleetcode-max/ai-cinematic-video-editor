"""T37 - Legacy Reveal."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_sprite
from . import _d_helpers as D

IVORY = Material(base=(0.95, 0.91, 0.84), spec=(1.0, 0.88, 0.66), spec_power=30, spec_gain=0.35, diffuse=0.8,
                 ambient=0.2, metal=0.15, env_sky=(1.0, 0.9, 0.75), env_horizon=(0.3, 0.22, 0.15),
                 env_ground=(0.2, 0.15, 0.1), env_sharp=6, bevel=0.035, texture="none", rim=(1.0, 0.78, 0.45),
                 seed=37)

BOKEH = [(-1.45, -0.55, 0.16, 0.0), (-0.95, 0.42, 0.10, 1.3), (-0.35, -0.75, 0.07, 2.1), (0.55, 0.62, 0.12, 0.7),
         (1.15, -0.45, 0.18, 2.9), (1.6, 0.3, 0.09, 4.0), (0.2, -0.95, 0.05, 5.1), (-1.7, 0.75, 0.13, 3.3)]


class T37(Design):
    ID = "T37"
    NAME = "Legacy Reveal"
    SLUG = "Legacy_Reveal"
    CATEGORY = "E - Character and Emotion"
    CONCEPT = ("A quiet, premium tribute reveal for a name, an event or a dedication: warm light, soft bokeh, "
               "letters arriving one by one like a held breath.")
    ENTRANCE = "Letter-by-letter fade with a gentle upward settle and slight tracking contraction; a gold hairline draws outward beneath."
    REVEAL = "At the impact frame a slow warm light sweep glides across the letters and the scene gently brightens (no shake)."
    CAMERA = "Very slow push-in with a subtle drift; bokeh and motes at different depths provide restrained parallax."
    MATERIAL = "Satin ivory serif with a soft gold edge light; gold ornamental rule."
    EXIT = "Everything softly lifts and dissolves into warm glow, letters fading last-to-first, to warm black."
    TECHNIQUES = ["per-glyph staggered fade", "gold hairline ornament", "drifting bokeh layer",
                  "floating motes with depth of field", "slow light sweep", "warm light leak"]
    DURATION_FRAMES = 228
    DEFAULTS = dict(MAIN_TITLE="ELEANOR HAYES", SUBTITLE="1941 - 2024  ·  FOREVER REMEMBERED", FONT_FAMILY="marcellus",
                    TEXT_COLOR="#F3E8D6", ACCENT_COLOR="#E9B060", ANIMATION_START=18, ANIMATION_DURATION=84,
                    IMPACT_FRAME=100, HOLD_DURATION=80, EXIT_START=180, EXIT_DURATION=44, LETTER_SPACING=0.14,
                    TITLE_WIDTH=0.6, SUB_FONT_FAMILY="marcellus")
    UPPER = True
    SOUND = [(0, "atmos", "Warm room tone, soft piano-pad bed"), (18, "shimmer", "Delicate shimmer per letter"),
             (60, "swell", "Gentle string swell"), (100, "swell", "Warm swell peak with the light sweep"),
             (102, "shimmer", "Soft chime"), (180, "tail", "Long warm reverb tail")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        warm = c.hit(0.6, 1.8)  # gentle swell, not a hit
        push = K.ease_in_out(K.prog(t, 0, c.dur), 2)
        fade_out = 1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.3, c.exit_dur * 0.7))
        nx, ny = K.grid(H, W)

        bg = K.vgrad(H, W, (0.030, 0.022, 0.018), (0.012, 0.009, 0.008)) * bgI
        leak = K.soft_spot(H, W, -1.5 + 0.1 * math.sin(t * 0.2), -0.9, 1.4, 1.0, 1.0)
        bg += (leak * (0.10 + 0.04 * math.sin(t * 0.6)) * bgI * fade_out)[..., None] * acc
        bg += (K.soft_spot(H, W, 0.0, 0.05, 1.3, 0.55, 1.2) * (0.05 + 0.05 * warm) * bgI)[..., None] * acc

        # bokeh (far layer, slow drift, moves less than the push)
        bk = np.zeros((H // 4, W // 4, 3), np.float32)
        s = H / 8
        for i, (bx, by, r, ph) in enumerate(BOKEH):
            x = bx + 0.05 * math.sin(t * 0.13 + ph) - 0.04 * push
            y = by + 0.04 * math.cos(t * 0.11 + ph) - 0.03 * t / max(c.dur, 1)
            I = 0.06 + 0.035 * math.sin(t * 0.4 + ph * 1.7)
            cv2.circle(bk, (int((W / 8 + x * s) * 4), int((H / 8 + y * s) * 4)), int(r * s * 4),
                       tuple(float(v) for v in (acc * 0.8 + 0.2) * I), -1, cv2.LINE_AA, shift=2)
        bk = cv2.GaussianBlur(bk, (0, 0), 2.0)
        bg += D.up(bk, H, W) * bgI * fade_out

        # floating motes behind the title
        nP = int(110 * p["PARTICLE_INTENSITY"])
        P = c.cache.get("motes")
        if P is None and nP:
            P = c.cache["motes"] = E.Particles(nP, seed=37, z=(0.5, 3.0))
        if nP:
            x, y = P.drift(t, vel=(0.004, -0.018), turb=0.03, freq=0.2)
            bg += E.particle_layer(H, W, P, x, y, acc * 0.7 + 0.3, 1.2, 0.35 * fade_out, zoom=1 + 0.05 * push,
                                   focus=1.0, dof=1.2, flicker=0.4, t=t, glow=1.0)

        # title: letters one by one -----------------------------------------------------
        sp = c.title()
        sh = c.shaded(IVORY)
        sw = K.prog(t, imp - 0.3, 2.6)
        sweep = (-0.8 + 1.7 * K.ease_in_out(sw), 0.16, 0.45, 0.9 * (1 if 0 < sw < 1 else 0))
        rgb, a = sh.shade(light=(-0.3, -0.6, 0.75), rim_dir=(-0.3, -1), rim_gain=0.35 + 0.35 * warm, sweep=sweep,
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.8 + 0.15 * warm)
        edge = sh.edge
        rgb = rgb + (edge * 0.25)[..., None] * acc
        cam = c.cam(zoom=1.0 + 0.05 * push, pan=(-10 * k * push, 0))
        L = c.layer()
        hx, hy = c.hero()
        n = max(1, len(sp.glyphs))
        lift = -14 * k * K.smooth(ex)
        for g in sp.glyphs:
            j = g.index / max(1, n - 1)
            gu = K.prog(u, 0.62 * j, 0.38)
            ge = K.ease_out(gu, 2.5)
            # exit: last letter fades first
            gx = K.prog(ex, 0.4 * (1 - j), 0.6)
            op = K.smooth(gu) * (1 - K.smooth(gx))
            if op <= 0.002:
                continue
            spread = 1 + 0.06 * (1 - ge)
            dxp = (g.center[0] - sp.anchor[0]) * (spread - 1)
            dy = 22 * k * (1 - ge) + lift * (1 + j)
            place_sprite(L, cam, rgb, a, g.box, sp.anchor, (hx, hy, 0), 1.0, (0, 0, p["TEXT_ROTATION"]),
                         (dxp, dy, 0, 0, 0, 0, 1.0, g.center[0], g.center[1]), op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.5, (0, 10), 22, k)
        img = comp(bg, L)
        img = img + K.blur(L.rgb, 14 * k) * (0.12 + 0.25 * warm + 0.6 * K.smooth(ex)) * p["GLOW_STRENGTH"] * acc

        # gold hairline ornament under the title
        ru = K.ease_in_out(K.prog(t, c.start + c.reveal * 0.35, 2.6), 2)
        if ru > 0 and fade_out > 0:
            ln = np.zeros((H, W, 3), np.float32)
            cx = W / 2 + hx * cam.zoom
            cy = H / 2 + (hy + sp.ink_h * 0.78) * cam.zoom
            half = sp.ink_w * 0.42 * ru * cam.zoom
            col = tuple(float(v) for v in acc * 0.9)
            for sgn in (-1, 1):
                x0 = cx + sgn * 16 * k
                cv2.line(ln, (int(x0 * 4), int(cy * 4)), (int((x0 + sgn * half) * 4), int(cy * 4)), col,
                         max(1, int(1.2 * k)), cv2.LINE_AA, shift=2)
            d = 6 * k * min(1, ru * 3)
            pts = np.int32([[cx * 4, (cy - d) * 4], [(cx + d) * 4, cy * 4], [cx * 4, (cy + d) * 4], [(cx - d) * 4, cy * 4]])
            cv2.fillPoly(ln, [pts], col, cv2.LINE_AA, shift=2)
            img += (ln + K.blur(ln, 3 * k) * 0.8) * fade_out
        img = subtitle(c, img, cam, imp - 0.4, c.exit_start + 0.2, (0.86, 0.78, 0.64), y_rel=1.28, fade=1.6,
                       grow=0.0, rel=0.26, tracking=0.3)
        # near motes (in front, soft)
        if nP:
            img += E.particle_layer(H, W, P, x * 1.3, y * 1.2, acc * 0.7 + 0.3, 2.0, 0.12 * fade_out,
                                    zoom=1.2 + 0.1 * push, focus=3.0, dof=0.6, t=t, glow=1.0)
        img = img * (1 - 0.85 * K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.5, c.exit_dur * 0.5)))
        return c.finish(img, vignette=0.6, grain=0.025, bloom=(0.75, 0.45),
                        grade=dict(shadows=(0.004, 0.002, 0.0), highlights=(0.015, 0.006, -0.012), contrast=1.03))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"], "Warm Gold Color")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        push = e_inout(prog(0, g.frames))
        out = f"(1 - {clamp01(f'({ex} - 0.3)/0.7')})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "WarmDark", [(0, "#030202", 1), (1, "#080605", 1)])
        bg = F.light_spot(g, "LightLeak", bg, None, (0.05, 0.95), 0.9, 0.9, 0.7, accent=True, gain=0.35,
                          blend=f"{BG}*{out}*(0.8 + 0.2*sin(time*0.025))")
        bg = F.light_spot(g, "CentreWarmth", bg, None, (0.5, 0.48), 0.8, 0.45, 0.7, accent=True, gain=0.25,
                          blend=f"{BG}*(0.6 + 0.4*{decay(I, 40)})")
        for i, (bx, by, r, ph) in enumerate(BOKEH):
            e = F.ellipse(g, f"Bokeh{i}Shape", (0.5, 0.5), r * 9 / 16, r, 0.25)
            e.expr("Center", f"Point({0.5 + bx * 0.5 * 9 / 16:.4f} + 0.014*sin(time*0.0054 + {ph}), "
                             f"{0.5 - by * 0.5:.4f} + 0.02*cos(time*0.0046 + {ph}) + time*0.00006)", [0.5, 0.5])
            s = F.accent_solid(g, f"Bokeh{i}Color", 0.5)
            F.masked(s, e)
            bg = F.merge(g, f"Bokeh{i}", bg, s, mode="Screen", blend=f"{BG}*{out}*(0.10 + 0.05*sin(time*0.017 + {ph}))")
        g.at(0, 2)
        bg = F.particles(g, "Motes", bg, number=6, lifespan=220, velocity=0.0012, angle=90, angle_var=30, size=0.3,
                         color=p["ACCENT_COLOR"], region="CubeRgn", region_size=(2.4, 1.4, 1.0), center_y=-0.1,
                         turbulence=0.08, glow=4)

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Marcellus SC", "Regular", 0.12, 1.14,
                             color=p["TEXT_COLOR"])
        satin = F.fill_material(g, "SatinIvory", title,
                                [(0, "#cbbfae", 1), (0.45, "#f6efe4", 1), (0.55, "#fffaf2", 1), (1, "#b8ab98", 1)])
        face = F.merge(g, "SatinFace", title, satin, mode="Multiply", blend=0.6)
        rim = F.edge_light(g, "GoldEdge", title, 0.001, -0.0015, accent=True, gain=1.0, blur_px=0.8)
        face = F.merge(g, "GoldEdgeMerge", face, rim, mode="Screen", blend=f"0.5*{ctl('GlowStrength')}")
        face = F.light_sweep(g, "WarmSweep", face, title, f"{I} - 7", 62, angle=30, width=0.12, peak=0.55,
                             accent=True)
        g.at(0, 6)
        # letters arrive left -> right: a very soft wipe with a trailing fade (one letter wide)
        wipe = F.rect(g, "LetterArrival", (0.0, 0.5), 2.0, 2.0, 0.09)
        wipe.expr("Center", f"Point(-0.95 + 1.5*{e_inout(u)}, 0.5)", [-0.95, 0.5])
        gone = F.rect(g, "LetterDeparture", (2.2, 0.5), 2.0, 2.0, 0.09)
        gone.expr("Center", f"Point(2.25 - 1.5*{e_inout(ex)}, 0.5)", [2.25, 0.5])
        gone.set(PaintMode=F.FuID("Subtract"))
        gone.conn("EffectMask", wipe, "Mask")
        hold = F.solid(g, "TitleHolder", (0, 0, 0), alpha=0.0)
        tm = F.merge(g, "TitleArrive", hold, face)
        F.masked(tm, gone)
        placed = F.title_placement(g, "TitleSettle", tm, size_expr=f"1.0 + 0.04*(1 - {e_out(u, 2.5)})",
                                   center_extra_y=f"-0.012*(1 - {e_out(u, 2.5)}) + 0.012*{ex}")
        tglow = F.softglow(g, "WarmGlow", placed, 16,
                           gain=f"{ctl('GlowStrength')}*(0.2 + 0.3*{decay(I, 40)} + 0.8*{ex})", threshold=0.5)
        scene = F.merge(g, "TitleOverWarmth", bg, tglow, blend=out)

        g.at(0, 8)
        ru = e_inout(prog(f"{ctl('AnimStart')} + 0.35*{ctl('AnimDuration')}", 62))
        rule = F.rect(g, "GoldRuleShape", (0.5, 0.41), 0.01, 0.0016, 0.0005)
        rule.expr("Center", f"Point({ctl('TextPosX')}, {ctl('TextPosY')} - 0.09)", [0.5, 0.41])
        rule.expr("Width", f"0.38*{ru}*{ctl('TextScale')}", 0.0)
        gap = F.rect(g, "GoldRuleGap", (0.5, 0.41), 0.018, 0.01, 0.0)
        gap.expr("Center", f"Point({ctl('TextPosX')}, {ctl('TextPosY')} - 0.09)", [0.5, 0.41])
        gap.set(PaintMode=F.FuID("Subtract"))
        gap.conn("EffectMask", rule, "Mask")
        dia = F.closed_poly_mask(g, "GoldDiamond", [(0.5, 0.416), (0.5035, 0.41), (0.5, 0.404), (0.4965, 0.41)])
        dia.expr("Center", f"Point({ctl('TextPosX')}, {ctl('TextPosY')} - 0.09 + 0.5 - 0.41)", [0.5, 0.5])
        dia.conn("EffectMask", gap, "Mask")
        rcol = F.accent_solid(g, "GoldRuleColor", 0.9)
        F.masked(rcol, dia)
        rglow = F.softglow(g, "GoldRuleGlow", rcol, 4, gain=f"0.8*{ctl('GlowStrength')}", threshold=0.1)
        scene = F.merge(g, "GoldRule", scene, rglow, blend=f"min({ru}*3, 1)*{out}")
        scene = D.f_sub(g, p, "Marcellus SC", "Regular", (0.86, 0.78, 0.64), -0.145, f"{I} - 10",
                        f"{ctl('ExitStart')} + 5", size=0.026, tracking=1.32, scene=scene)
        scene = F.particles(g, "MotesNear", scene, number=3, lifespan=220, velocity=0.0015, angle=90, angle_var=30,
                            size=0.8, color=p["ACCENT_COLOR"], region="CubeRgn", region_size=(2.4, 1.4, 0.3),
                            center_y=-0.1, turbulence=0.06, glow=8)
        scene = F.xf(g, "Camera", scene, center=f"Point(0.5 - 0.005*{push}, 0.5)", size=f"1 + 0.05*{push}", edges=1)
        g.output = F.finish(g, scene, vignette=0.6)


DESIGN = T37()
