"""T39 - Final Boss."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, subtitle, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_extruded
from . import _d_helpers as D

DARK_IRON = Material(base=(0.30, 0.29, 0.29), spec=(1.0, 0.75, 0.68), spec_power=40, spec_gain=0.6, diffuse=0.6,
                     ambient=0.06, metal=0.55, env_sky=(0.35, 0.32, 0.32), env_horizon=(0.03, 0.02, 0.02),
                     env_ground=(0.45, 0.08, 0.05), env_sharp=10, bevel=0.06, texture="concrete", tex_amount=0.12,
                     bump=0.02, rim=(1.0, 0.25, 0.15), seed=39)

ROT = (11.0, -13.0, -3.0)  # aggressive low-angle / three-quarter perspective


def heartbeat(t, period=1.15):
    """Two-beat pulse ('lub-dub') in [0,1]."""
    ph = (t % period) / period
    return math.exp(-((ph - 0.05) / 0.035) ** 2) + 0.6 * math.exp(-((ph - 0.22) / 0.04) ** 2)


class T39(Design):
    ID = "T39"
    NAME = "Final Boss"
    SLUG = "Final_Boss"
    CATEGORY = "H - Signature Hero Elevations"
    CONCEPT = "The last enemy arrives: a massive dark-iron title slams out of the abyss and holds, breathing red."
    ENTRANCE = ("A long ominous build (smoke, heartbeat red underlight), then a very fast 10-frame launch from deep "
                "space straight at the lens with zoom motion blur.")
    REVEAL = "Hard impact: short violent shake, layered smoke blasts outward, red underlight flares; then a dead-stable hero hold."
    CAMERA = "Aggressive low three-quarter perspective on the extruded title; locked-off after a short impact shake."
    MATERIAL = "Pitted dark iron, deep 2.5D extrusion, blood-red underlight and rim pulsing with a heartbeat."
    EXIT = "The red light cuts and the title is yanked back into the abyss in a fast pull."
    TECHNIQUES = ["fast z-launch with zoom blur", "deep perspective extrusion", "3-layer smoke with radial blast",
                  "heartbeat-driven underlight", "short impact shake", "snap-back exit"]
    DURATION_FRAMES = 156
    DEFAULTS = dict(MAIN_TITLE="DREADLORD", SUBTITLE="NO ONE SURVIVES THE LAST LEVEL", FONT_FAMILY="blackops",
                    TEXT_COLOR="#8E8784", ACCENT_COLOR="#FF2A18", ANIMATION_START=18, ANIMATION_DURATION=10,
                    IMPACT_FRAME=28, HOLD_DURATION=92, EXIT_START=130, EXIT_DURATION=18, LETTER_SPACING=0.04,
                    TITLE_WIDTH=0.7, EXTRUSION_DEPTH=1.0, SUB_FONT_FAMILY="teko")
    SOUND = [(0, "atmos", "Abyssal drone"), (0, "heartbeat", "Heavy heartbeat (continues through the hold)"),
             (4, "riser", "Tension riser (frames 4-28)"), (18, "whoosh", "Fast incoming whoosh"),
             (28, "impact", "Massive impact + distorted sub"), (28, "metal", "Iron slam"),
             (29, "debris", "Debris / grit"), (30, "tail", "Impact tail"), (130, "rwhoosh", "Snap-back suck"),
             (138, "sub", "Final sub drop")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.02, 0.35)
        after = 1.0 if t >= imp else 0.0
        hb = heartbeat(t)
        build = K.smooth(K.prog(t, 0, imp))
        alive = 1 - K.smooth(K.prog(ex, 0.0, 0.3))  # red light cut at exit start
        under = (0.12 + 0.25 * build + after * (0.45 + 0.25 * hb) + 1.0 * hit) * alive
        nx, ny = K.grid(H, W)
        blast = (1 - math.exp(-max(t - imp, 0) / 0.5)) * after

        # abyss + furnace slit far behind ------------------------------------------
        bg = K.vgrad(H, W, (0.006, 0.004, 0.005), (0.03, 0.006, 0.005), 1.6) * bgI
        slit = np.exp(-((ny - 0.42) / 0.012) ** 2) * np.exp(-(nx / 1.4) ** 2)
        bg += ((slit * 0.25 + K.soft_spot(H, W, 0, 0.35, 2.0, 0.5, 1.2) * 0.25) * under * bgI)[..., None] * acc
        s1 = D.shaped(D.plane(H, W, t, 1.4, (0.01, -0.012), 6, 1 + 0.12 * blast, (0, 0)), 0.3, 1.0)
        lit = np.clip(0.2 + (ny + 0.2) * 0.8, 0, 1.2)
        bg += (s1 * (0.04 + lit * under * 0.25) * bgI)[..., None] * (acc * 0.8 + 0.08)

        # title: fast launch from the abyss -------------------------------------------
        sp = c.title()
        sh = c.shaded(DARK_IRON)
        rgb, a = sh.shade(light=(0.1, 0.9, 0.5), rim_dir=(0, 1), rim_gain=0.5 + 1.2 * under,
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.6 + 0.6 * under,
                          env_shift=-0.1)
        top = (sh.edge * np.clip(-sh.ny * 3, 0, 1) * 0.35)[..., None] * np.array([0.8, 0.75, 0.75], np.float32)
        rgb = rgb + top
        ue = K.ease_out(u, 1.6)
        ze = K.ease_in(ex, 3)
        zoff = 9.0 * H * (1 - ue) + 12.0 * H * ze
        sc = 1.0 + 0.04 * (1 - K.ease_out(K.prog(t, imp, 0.35), 2)) * after  # tiny compression bounce
        cam = c.cam(zoom=1.0)
        L = c.layer()
        op = K.smooth(u * 4) * (1 - K.smooth(K.prog(ex, 0.6, 0.4)))
        hx, hy = c.hero()
        depth = 0.3 * sp.cap_px * p["EXTRUSION_DEPTH"]
        if op > 0:
            if depth > 0.5:
                place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, (hx, hy, zoff), sc,
                               (ROT[0], ROT[1], ROT[2] + p["TEXT_ROTATION"]), depth, (0.05, 0.035, 0.035),
                               slices=14, side_light=lambda q: 0.3 + 0.7 * q, opacity=op)
            else:
                c.place(L, cam, rgb, a, sp, sc, rot=ROT, off=(0, 0, zoff), opacity=op)
        speed = max((1 - ue) * (1 if u < 1 else 0), ze) * p["MOTION_BLUR_AMOUNT"]
        if speed > 0.02:
            L.rgb = K.zoom_blur(L.rgb, W / 2 + hx, H / 2 + hy, 0.35 * speed, 10)
            L.a = K.zoom_blur(L.a, W / 2 + hx, H / 2 + hy, 0.35 * speed, 10)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.7, (0, -20), 30, k)
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.35, 0), 10 * k) * (0.5 + hit) * p["GLOW_STRENGTH"] * acc

        # layered smoke in front: radial blast at impact, then slow heavy roll
        s2 = D.shaped(D.plane(H, W, t, 1.0, (0.015, -0.01), 14, 1 + 0.45 * blast, (0, 0)), 0.35, 1.0)
        hx_n, hy_n = hx / (H / 2), hy / (H / 2)
        ring = K.soft_spot(H, W, hx_n, hy_n, 0.3 + 2.2 * blast, 0.2 + 1.2 * blast, 1.2)
        hole = 1 - K.soft_spot(H, W, hx_n, hy_n, 0.2 + 1.6 * blast, 0.12 + 0.8 * blast, 1.6) * after
        d2 = s2 * (0.35 * (1 - after) + after * (0.18 + 0.5 * ring * math.exp(-max(t - imp, 0) / 1.2)) * hole
                   + 0.45 * K.smooth(ex))
        img = D.over_lit(img, ((0.025 + lit * under * 0.22)[..., None] * (acc * 0.9 + 0.1)) * bgI, d2 * min(1.0, bgI))
        s3 = D.shaped(D.plane(H, W, t, 0.7, (0.03, -0.02), 22, 1.1 + 0.8 * blast, (0, 0)), 0.45, 1.0, 1.4)
        img = D.over_lit(img, ((0.02 + lit * under * 0.15)[..., None] * (acc * 0.9 + 0.1)) * bgI,
                         s3 * (0.25 + 0.3 * after * math.exp(-max(t - imp, 0) / 0.8)) * min(1.0, bgI))

        # grit kicked up at impact (restrained)
        nP = int(120 * p["PARTICLE_INTENSITY"])
        if after and nP and t < imp + 2.5:
            dt = t - imp
            r = np.random.default_rng(39)
            ang = r.uniform(0, 2 * np.pi, nP)
            spd = r.uniform(0.3, 1.6, nP)
            dist = spd * (1 - math.exp(-dt * 2.5)) / 2.5
            gx = hx_n + r.uniform(-0.5, 0.5, nP) * sp.ink_w / (H / 2) + np.cos(ang) * dist
            gy = hy_n + r.uniform(-0.35, 0.35, nP) * sp.ink_h / (H / 2) + np.sin(ang) * dist * 0.6 + 0.25 * dt * dt
            Pb = E.Particles(nP, 4)
            Pb.z = (0.7 + 0.6 * r.random(nP)).astype(np.float32)
            img += E.particle_layer(H, W, Pb, gx, gy, acc * 0.5 + 0.25, 1.1, 0.8 * math.exp(-dt / 0.7), glow=0.6,
                                    streak=(np.cos(ang) * 0.01 * math.exp(-dt * 3), np.sin(ang) * 0.006 * math.exp(-dt * 3)))
        img += acc[None, None, :] * 0.10 * hit * bgI
        img = apply_shake(c, img, 0.011, 0.18, 24)
        img = subtitle(c, img, cam, imp + 0.6, c.exit_start - 0.1, (0.78, 0.70, 0.68), y_rel=1.0)
        return c.finish(img, vignette=0.65, grain=0.045, bloom=(0.7, 0.55),
                        grade=dict(shadows=(0.004, -0.002, -0.002), sat=1.05, contrast=1.12))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"], "Underlight Color")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        ph = "((time/27.6) - floor(time/27.6))"
        hb = f"(pow(2.718282, -pow(({ph} - 0.05)/0.035, 2)) + 0.6*pow(2.718282, -pow(({ph} - 0.22)/0.04, 2)))"
        alive = f"(1 - {clamp01(f'{ex}/0.3')})"
        under = (f"((0.12 + 0.25*{prog(0, I)} + {step(I)}*(0.45 + 0.25*{hb}) + {ctl('ImpactIntensity')}*{decay(I, 8)})"
                 f"*{alive})")
        blast = f"({step(I)}*(1 - pow(2.718282, -max(time - ({I}), 0)/12)))"
        ue = f"(1 - pow(1 - {u}, 1.6))"

        g.at(0, 0)
        bg = F.gradient_bg(g, "Abyss", [(0, "#080102", 1), (0.5, "#020101", 1), (1, "#000000", 1)])
        slit = F.rect(g, "FurnaceSlitShape", (0.5, 0.29), 1.4, 0.008, 0.02)
        sc = F.accent_solid(g, "FurnaceSlitColor", 1.0)
        F.masked(sc, slit)
        bg = F.merge(g, "FurnaceSlit", bg, F.blur(g, "FurnaceSlitGlow", sc, 12), mode="Screen",
                     blend=f"min(0.5*{BG}*{under}, 1)")
        bg = F.light_spot(g, "Underlight", bg, None, (0.5, 0.15), 1.6, 0.5, 0.6, accent=True, gain=0.5,
                          blend=f"min({BG}*{under}, 1)")
        bg = D.f_fog(g, "SmokeBack", bg, "#000000", "#3a0f0a", 2.2, f"1 + 0.12*{blast}", (0.0004, 0.0005),
                     blend=f"{BG}*(0.4 + 0.4*{under})")

        g.at(0, 2)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Black Ops One", "Regular", 0.19, 1.04,
                             color=p["TEXT_COLOR"])
        iron = F.noise(g, "IronPitting", "#5a5452", "#ffffff", detail=7, scale=30, seethe_rate=0.0, contrast=1.4)
        im = F.bitmap_mask(g, "IronMatte", title)
        F.masked(iron, im)
        face = F.merge(g, "IronFace", title, iron, mode="Multiply", blend=0.6)
        under_rim = F.edge_light(g, "BloodUnderRim", title, 0.0, 0.004, accent=True, gain=1.6, blur_px=1.6)
        face = F.merge(g, "UnderRimMerge", face, under_rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.4 + 0.9*{under}), 1)")
        top = F.edge_light(g, "TopEdge", title, 0.0, -0.002, color=(0.8, 0.75, 0.75), blur_px=0.8)
        face = F.merge(g, "TopEdgeMerge", face, top, mode="Screen", blend=0.35)
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        ext = F.extrusion_stack(g, "Extrude", clear, title, layers=10, dx=-0.0012, dy=0.0022,
                                color=(0.05, 0.035, 0.035))
        solid = F.merge(g, "IronSolid", ext, face)
        lit = F.cc(g, "UnderExposure", solid, gain=f"0.5 + 0.55*{under}")
        g.at(0, 4)
        persp = g.add("CornerPositioner", "AggressivePerspective")
        persp.conn("Input", lit)
        persp.set(TopLeft=[0.10, 0.93], TopRight=[0.86, 1.0], BottomLeft=[0.0, 0.03], BottomRight=[1.0, 0.0])
        placed = F.title_placement(g, "Launch", persp,
                                   size_expr=f"(0.03 + 0.97*{ue})*(1 - 0.98*{e_in(ex, 3)})"
                                             f"*(1 + 0.04*{step(I)}*(1 - {e_out(prog(I, 8), 2)}))")
        zb = F.dirblur(g, "LaunchZoomBlur", placed,
                       f"0.25*{ctl('MotionBlurAmount')}*max((1 - {ue})*(1 - {step(I)}), {e_in(ex, 3)})", btype=3)
        zb.expr("Center", f"Point({ctl('TextPosX')}, {ctl('TextPosY')})", [0.5, 0.5])
        tglow = F.softglow(g, "RedGlow", zb, 12, gain=f"{ctl('GlowStrength')}*(0.4 + 1.2*{decay(I, 8)})",
                           threshold=0.3)
        scene = F.merge(g, "TitleOverAbyss", bg, tglow,
                        blend=f"min({u}*4, 1)*(1 - {clamp01(f'({ex} - 0.6)/0.4')})")

        g.at(0, 6)
        hole = F.ellipse(g, "BlastClearing", (0.5, 0.5), 0.1, 0.1, 0.3, invert=True)
        hole.expr("Center", f"Point({ctl('TextPosX')}, {ctl('TextPosY')})", [0.5, 0.5])
        hole.expr("Width", f"0.1 + 1.2*{blast}", 0.1)
        hole.expr("Height", f"0.1 + 0.8*{blast}", 0.1)
        scene = D.f_fog(g, "SmokeMid", scene, "#000000", "#2a0b08", 1.8, f"1 + 0.45*{blast}", (0.0006, 0.0004),
                        blend=f"min({BG}, 1)*(0.35*(1 - {step(I)}) + {step(I)}*(0.18 + 0.5*{decay(I, 29)}) + 0.45*{ex})",
                        mode="Normal", mask=hole)
        scene = D.f_fog(g, "SmokeNear", scene, "#000000", "#1e0806", 1.2, f"1.1 + 0.8*{blast}", (0.0012, 0.0008),
                        blend=f"min({BG}, 1)*(0.25 + 0.3*{decay(I, 19)})", mode="Normal", contrast=1.8)
        scene = F.particles(g, "Grit", scene, number=120, lifespan=40, velocity=0.03, angle=90, angle_var=180,
                            size=0.3, color=(0.6, 0.25, 0.2), region="CubeRgn", region_size=(1.2, 0.2, 0.3),
                            center_y=0.0, turbulence=0.15, glow=2,
                            number_expr=f"120*{ctl('ParticleIntensity')}*{window(I, I + ' + 2', 1, 1)}")
        scene = F.impact_flash(g, "ImpactFlash", scene, color=p["ACCENT_COLOR"], peak=0.12, frames=4)
        g.at(0, 8)
        scene = D.f_sub(g, p, "Teko", "SemiBold", (0.78, 0.70, 0.68), -0.15, f"{I} + 14", f"{ctl('ExitStart')} - 2",
                        scene=scene)
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.0, shake_frames=4, shake_amp=0.012)
        g.output = F.finish(g, scene, vignette=0.65)


DESIGN = T39()
