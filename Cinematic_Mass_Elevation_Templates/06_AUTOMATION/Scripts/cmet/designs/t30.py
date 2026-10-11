"""T30 - Speed Ramp Dominance."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, subtitle, apply_shake, drop_shadow
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from . import _c_helpers as X

ENAMEL = Material(base=(0.92, 0.92, 0.9), spec=(1.0, 1.0, 1.0), spec_power=60, spec_gain=0.7, diffuse=0.75,
                  ambient=0.18, metal=0.2, env_sky=(0.9, 0.9, 0.92), env_horizon=(0.1, 0.1, 0.11),
                  env_ground=(0.2, 0.2, 0.2), bevel=0.045, texture="none", rim=(1.0, 0.4, 0.35), seed=30)
NRAYS = 150
ZFAR = 9.0      # start distance (multiples of the rest distance)


class T30(Design):
    ID = "T30"
    NAME = "Speed Ramp Dominance"
    SLUG = "Speed_Ramp_Dominance"
    CATEGORY = "C - Future Tech and Kinetic Camera"
    CONCEPT = "Pure momentum: the title rockets in from the vanishing point and slams into an almost-frozen slow-motion hold."
    ENTRANCE = ("A hyper-fast approach from the vanishing point through rushing speed lines, with zoom/directional "
                "blur proportional to velocity, then a hard speed-ramp deceleration.")
    REVEAL = ("At the impact frame the title brakes to a near standstill: red edge flash, anamorphic streak, speed "
              "lines freeze and drift; a slow-motion creep carries the long, readable hold.")
    CAMERA = "Forward rush with impact jolt; then a barely-moving slow-motion creep."
    MATERIAL = "Gloss white enamel with red (ACCENT) rim and impact accent."
    EXIT = "Reverse ramp: the title accelerates away into the vanishing point with zoom blur as the lines rush again."
    TECHNIQUES = ["speed ramp curve", "velocity-scaled zoom blur", "radial speed lines", "impact freeze",
                  "anamorphic streak", "slow-motion creep", "reverse ramp exit"]
    DURATION_FRAMES = 144
    DEFAULTS = dict(MAIN_TITLE="DOMINANCE", SUBTITLE="NOTHING CATCHES UP", FONT_FAMILY="russo",
                    TEXT_COLOR="#F3F3F1", ACCENT_COLOR="#FF3B30", ANIMATION_START=4, ANIMATION_DURATION=18,
                    IMPACT_FRAME=22, HOLD_DURATION=86, EXIT_START=110, EXIT_DURATION=16, LETTER_SPACING=0.04,
                    TITLE_WIDTH=0.64, SHADOW_STRENGTH=0.5, MOTION_BLUR_AMOUNT=1.0)
    SOUND = [(0, "riser", "Short aggressive riser (0-22)"), (4, "whoosh", "Hyper-fast pass-by whoosh"),
             (22, "impact", "Hard impact / brake slam"), (22, "sub", "Sub drop into slow motion"),
             (23, "swell", "Slow-motion tonal swell (hold)"), (40, "heartbeat", "Slowed heartbeat pulse"),
             (106, "rwhoosh", "Reverse suck before exit"), (110, "whoosh", "Exit rush"), (126, "tail", "Tail")]
    FUSION_NOTES = ["Motion blur: 'Motion Blur Amount' scales the DirectionalBlur (Zoom type) length on the title "
                    "and on the speed-line field."]

    def _dist(self, c, t):
        """Distance factor (1 = rest) along the speed-ramp curve."""
        u = K.prog(t, c.start, c.reveal)
        d = 1 + (ZFAR - 1) * (1 - u) ** 3.2                  # fast, then hard brake
        if t > c.impact:
            d *= 1 - 0.07 * K.prog(t, c.impact, c.exit_start - c.impact)   # slow-mo creep
        ex = K.prog(t, c.exit_start, c.exit_dur)
        d *= 1 + 14 * ex ** 3
        return d

    def _travel(self, c, t):
        u = K.prog(t, c.start, c.reveal)
        ex = K.prog(t, c.exit_start, c.exit_dur)
        return 3.0 * (1 - (1 - u) ** 3) + 0.06 * t + 3.5 * ex ** 2.5

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        tc = K.col(p["TEXT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        MB = p["MOTION_BLUR_AMOUNT"]
        ex = c.exit_u()
        imp = c.impact
        hit = c.hit(0.01, 0.3)
        sp = c.title()
        hx, hy = c.hero()
        dt = 1 / 24
        d0, d1 = self._dist(c, t - dt), self._dist(c, t)
        vel = abs(math.log(d0 / d1))                          # relative scale change per frame
        tr0, tr1 = self._travel(c, t - dt), self._travel(c, t)
        lspeed = tr1 - tr0

        # --- environment: dark tunnel, radial speed lines
        bg = K.radial(H, W, hx / (H / 2), hy / (H / 2), 2.0, (0.03, 0.03, 0.035), (0.004, 0.004, 0.005), 1.2) * bgI
        key = "rays"
        if key not in c.cache:
            r = np.random.default_rng(30)
            c.cache[key] = (r.uniform(0, 2 * np.pi, NRAYS), r.random(NRAYS), r.uniform(0.5, 1.5, NRAYS),
                            r.random(NRAYS) < 0.25)
        ang, r0, sv, red = c.cache[key]
        vx, vy = W / 2 + hx, H / 2 + hy
        segs, ints, segs_r, ints_r = [], [], [], []
        Rmax = math.hypot(W, H) * 0.6
        lvl = (0.25 + 0.75 * min(1.0, lspeed * 6)) * bgI * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur, 0.5)))
        for i in range(NRAYS):
            q = X.frac(r0[i] + tr1 * sv[i] * 0.35)
            rad = 0.12 + q ** 2.2 * 1.3
            ln = min(0.9, 0.01 + lspeed * sv[i] * 2.5 * MB + 0.015)
            a0 = rad * Rmax
            a1 = (rad + ln * rad) * Rmax
            p0 = (vx + math.cos(ang[i]) * a0, vy + math.sin(ang[i]) * a0 * 0.75)
            p1 = (vx + math.cos(ang[i]) * a1, vy + math.sin(ang[i]) * a1 * 0.75)
            I = lvl * min(1.0, q * 4) * (0.15 + 0.5 * sv[i] / 1.5)
            (segs_r if red[i] else segs).append((p0, p1))
            (ints_r if red[i] else ints).append(I)
        rl = X.lines_buf(H, W, segs, (0.85, 0.87, 0.9), 1.2, k, ints) + X.lines_buf(H, W, segs_r, acc, 1.6, k, ints_r)
        bg += rl + K.blur(rl, 4 * k) * 0.8

        # --- title on the speed-ramp curve
        sh = c.shaded(ENAMEL)
        rgb, a = sh.shade(light=(-0.3, -0.7, 0.6), base=tc, rim_gain=0.5 + 2.2 * hit, rim_dir=(0, -1),
                          light_gain=1.0 + 0.4 * hit)
        rim = X.inner_edge(sp, 0.035)[..., None] * acc * (0.15 + 1.6 * hit) * p["GLOW_STRENGTH"]
        rgb = rgb + rim
        zoom = 1.0 / d1
        cam = c.cam(zoom=1.0)
        L = c.layer()
        op = min(1.0, K.prog(t, c.start - 0.05, 0.15) + 0.0) * (1 - K.smooth(K.prog(ex, 0.75, 0.25)))
        jolt = 1 + 0.025 * K.pulse(t, imp, 0.02, 0.15) * p["SHAKE_AMOUNT"]
        c.place(L, cam, rgb, a, sp, zoom * jolt, opacity=op)
        # velocity-scaled zoom blur on the title (MOTION_BLUR_AMOUNT)
        amt = min(0.6, vel * 1.6 * MB)
        if amt > 0.004:
            Lrgb = K.zoom_blur(L.rgb, vx, vy, amt, steps=10)
            La = K.zoom_blur(L.a[..., None].repeat(3, 2), vx, vy, amt, steps=10)[..., 0]
        else:
            Lrgb, La = L.rgb, L.a
        if t > imp - 0.05:
            class _L:  # shadow only once the title is near the plane
                pass
            sl = _L()
            sl.a = La
            bg = drop_shadow(bg, sl, p["SHADOW_STRENGTH"] * 0.5 * min(1.0, 1 / d1), (0, 18), 26, k)
        img = bg * (1 - La[..., None]) + Lrgb

        # --- impact accent: anamorphic streak + edge flash glow
        if hit > 0.01:
            nx, ny = K.grid(H, W)
            band = np.exp(-((ny - hy / (H / 2)) / 0.006) ** 2) * np.exp(-((nx - hx / (H / 2)) / 1.6) ** 2)
            img += (band * hit * 1.2)[..., None] * (acc * 0.8 + 0.3)
        img += K.blur(np.maximum(Lrgb - 0.6, 0), 14 * k) * 0.6 * p["GLOW_STRENGTH"] * (0.25 + hit)
        img = apply_shake(c, img, 0.006, 0.18, 20)
        img = subtitle(c, img, cam, imp + 0.6, c.exit_start - 0.15, tc * 0.6 + acc * 0.15, y_rel=0.85)
        img = X.grade_fast(img, shadows=(0.002, 0.0, 0.004), contrast=1.08)
        return c.finish(img, vignette=0.55, grain=0.03, bloom=(0.85, 0.45), streak=(1.1, 0.3, 200, acc))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S, D = ctl("AnimStart"), ctl("AnimDuration")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        BG = ctl("BackgroundIntensity")
        MB = ctl("MotionBlurAmount")
        u = prog(S, D)
        creep = f"(1 - 0.07*{prog(I, f'({ctl(chr(69) + 'xitStart')} - {I})')})"
        dist = f"((1 + {ZFAR - 1}*pow(1 - {u}, 3.2))*{creep}*(1 + 14*pow({ex}, 3)))"
        # speed proxy: derivative of the ramp (approach) + exit acceleration
        speed = f"(3.2*{ZFAR - 1}*pow(1 - {u}, 2.2)*{step(S)}*(1 - {step(f'{S} + {D}')}) + 40*pow({ex}, 2))"

        g.at(0, 0)
        bg = F.gradient_bg(g, "Tunnel", [(0, "#080809", 1), (1, "#010101", 1)], gtype="Radial", start=(0.5, 0.5),
                           end=(0.5, 1.2))
        bg = F.cc(g, "TunnelLevel", bg, gain=BG)
        field = F.noise(g, "SpeedField", "#000000", "#ffffff", detail=2, scale=40, seethe_rate=0.0, contrast=4.0,
                        brightness=-0.35)
        field.expr("SeetheRate", f"0.05 + 0.6*min({speed}/10, 1)", 0.05)
        rays = F.dirblur(g, "SpeedLines", field, f"(0.15 + 0.6*min({speed}/10, 1))*{MB}", btype=3)
        hole = F.ellipse(g, "SpeedLinesVanish", (0.5, 0.5), 0.12, 0.2, 0.15, invert=True)
        F.masked(rays, hole)
        rtint = F.cc(g, "SpeedLinesTint", rays, gain=0.8)
        bg = F.merge(g, "SpeedLinesMerge", bg, rtint, mode="Screen",
                     blend=f"{BG}*(0.25 + 0.6*min({speed}/10, 1))*(1 - {step(f'{ctl(chr(69) + chr(120) + chr(105) + chr(116) + chr(83) + chr(116) + chr(97) + chr(114) + chr(116))} + {ctl(chr(69) + chr(120) + chr(105) + chr(116) + chr(68) + chr(117) + chr(114) + chr(97) + chr(116) + chr(105) + chr(111) + chr(110))} + 6')})")

        g.at(0, 2)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Russo One", "Regular", 0.13, 1.04, color=p["TEXT_COLOR"])
        enamel = F.fill_material(g, "EnamelShade", title, [(0, "#9a9a98", 1), (0.5, "#ffffff", 1), (1, "#d2d2d0", 1)])
        face = F.merge(g, "EnamelFace", title, enamel, mode="Multiply", blend=0.5)
        rim = F.edge_light(g, "RedRim", title, 0.0, -0.002, accent=True, gain=1.4, blur_px=1.0)
        face = F.merge(g, "RedRimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.15 + 1.6*{decay(I, 7)}), 1)")
        jolt = f"(1 + 0.025*{ctl('ShakeAmount')}*{decay(I, 4)})"
        placed = F.title_placement(g, "SpeedRamp", face, size_expr=f"{jolt}/{dist}")
        zb = F.dirblur(g, "TitleZoomBlur", placed, f"min(0.06*{speed}*{MB}, 0.5)", btype=3)
        zb.set(Center=[0.5, 0.5])
        glow = F.softglow(g, "ImpactGlow", zb, 14, gain=f"{ctl('GlowStrength')}*(0.25 + {decay(I, 8)})",
                          threshold=0.6)
        shp = F.cc(g, "ShadowMatte", glow, gain=0)
        shp = F.xf(g, "ShadowOffset", shp, center="Point(0.5, 0.483)")
        shp = F.blur(g, "ShadowSoft", shp, 14)
        scene = F.merge(g, "ShadowMerge", bg, shp, blend=f"0.5*{ctl('ShadowStrength')}*{step(f'{I} - 1')}")
        scene = F.merge(g, "TitleOverTunnel", scene, glow,
                        blend=f"{clamp01(f'(time - {S} + 1)/4')}*(1 - {e_inout(clamp01(f'({ex} - 0.75)/0.25'))})")
        g.at(0, 4)
        streak = F.accent_solid(g, "AnamorphicStreakColor", 1.2)
        F.masked(streak, F.ellipse(g, "AnamorphicStreakShape", (0.5, 0.5), 1.8, 0.012, 0.02))
        scene = F.merge(g, "AnamorphicStreak", scene, streak, mode="Screen",
                        blend=f"min({ctl('ImpactIntensity')}*{decay(I, 7)}, 1)")
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.6,
                                    color=(0.8, 0.78, 0.78), y_off=-0.12)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 14", f"{ctl('ExitStart')} - 4", 14, 6))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.01, shake_frames=4, shake_amp=0.006)
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T30()
