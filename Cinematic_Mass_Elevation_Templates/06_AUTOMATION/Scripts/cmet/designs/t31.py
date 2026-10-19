"""T31 - Midnight Fog."""
import math

import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from . import _d_helpers as D

PEWTER = Material(base=(0.62, 0.67, 0.74), spec=(0.85, 0.92, 1.0), spec_power=36, spec_gain=0.55, diffuse=0.7,
                  ambient=0.10, metal=0.45, env_sky=(0.55, 0.62, 0.75), env_horizon=(0.06, 0.07, 0.09),
                  env_ground=(0.10, 0.11, 0.13), env_sharp=8, bevel=0.05, texture="grain", tex_amount=0.05,
                  rim=(0.75, 0.85, 1.0), seed=31)


class T31(Design):
    ID = "T31"
    NAME = "Midnight Fog"
    SLUG = "Midnight_Fog"
    CATEGORY = "G - Atmospheric and Environmental Cinema"
    CONCEPT = "A moonlit midnight moor: the title lives inside layered fog and slowly condenses out of it."
    ENTRANCE = ("Fog-condensation reveal: the letterforms resolve out of the mist through a soft noise threshold "
                "while four fog planes drift past at different depths.")
    REVEAL = "At the impact frame a slow pressure wave parts the near fog around the title; the moon beam brightens."
    CAMERA = "Very slow push-in with a gentle lateral drift; fog planes zoom at depth-dependent rates (parallax)."
    MATERIAL = "Cool pewter with a soft directional moonlight from the upper left and a pale blue rim."
    EXIT = "The fog closes back in: front planes thicken and drift across while the title sinks into haze."
    TECHNIQUES = ["4-plane volumetric fog with parallax", "fog behind and in front of the title",
                  "noise-threshold condensation reveal", "volumetric moon beam", "fog parting wave", "depth haze"]
    DURATION_FRAMES = 216
    DEFAULTS = dict(MAIN_TITLE="MIDNIGHT", SUBTITLE="NOTHING STAYS HIDDEN", FONT_FAMILY="bebas",
                    TEXT_COLOR="#C9D3E0", ACCENT_COLOR="#8FB4FF", ANIMATION_START=10, ANIMATION_DURATION=96,
                    IMPACT_FRAME=112, HOLD_DURATION=56, EXIT_START=172, EXIT_DURATION=40, LETTER_SPACING=0.12,
                    TITLE_WIDTH=0.5, SUB_FONT_FAMILY="teko")
    SOUND = [(0, "atmos", "Night air bed, distant low drone"), (0, "wind", "Soft wind through the fog"),
             (10, "swell", "Slow pad swell under the condensation reveal"),
             (100, "rwhoosh", "Soft reverse air into the parting"),
             (112, "sub", "Deep sub pulse as the fog parts (no hard hit)"),
             (114, "shimmer", "Faint cold shimmer on the moonlit edge"), (172, "wind", "Fog rolls back in"),
             (180, "tail", "Long reverb tail")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.25, 1.2)
        push = K.ease_in_out(K.prog(t, 0, c.dur), 2)
        part = K.ease_out(K.prog(t, imp, 2.2), 2) * (1 - K.smooth(ex * 1.3))
        driftx = -0.10 * push  # lateral camera drift (frame heights)

        # sky + moon --------------------------------------------------------
        _, ny = K.grid(H, W)
        bg = K.vgrad(H, W, (0.010, 0.014, 0.028), (0.016, 0.020, 0.028))
        hz = np.exp(-((ny - 0.32 - 0.04 * push) / 0.35) ** 2)  # misty horizon glow (sinks as we push in)
        bg += (hz * 0.07 * bgI)[..., None] * (np.array([0.5, 0.6, 0.8], np.float32) * 0.6 + acc * 0.4)
        bg += (K.soft_spot(H, W, -1.35 + driftx * 0.2, -0.95, 0.9, 0.7, 1.4) * 0.22 * bgI)[..., None] * acc
        bg += (K.soft_spot(H, W, -1.35 + driftx * 0.2, -0.95, 0.10, 0.10, 2.0) * 0.5 * bgI)[..., None] * (acc * 0.4 + 0.6)
        sway = 2.5 * math.sin(t * 0.35)
        beam = D.cone(H, W, (-1.7 + driftx * 0.4, -1.25), 33 + sway, 13, 3.2, 0.5)
        beam_lvl = (0.55 + 0.25 * K.smooth(K.prog(t, c.start, c.reveal)) + 0.35 * hit) * (1 - 0.6 * K.smooth(ex))

        def fog_rgb(n, base, lit):
            return (base[None, None, :] + (beam * lit * beam_lvl)[..., None] * acc[None, None, :]) * n[..., None]

        # far fog banks (behind the title): wide, horizontally stretched
        nf = D.shaped(D.plane(H, W, t, 1.0, (0.005, 0.0), 3, 1 + 0.03 * push, (driftx * 0.3, 0),
                              stretch=(3.0, 1.0)), 0.2, 1.0)
        bg += fog_rgb(nf * (0.5 + 0.5 * hz), np.array([0.09, 0.105, 0.13], np.float32), 0.6) * bgI
        nm = D.shaped(D.plane(H, W, t, 1.4, (0.010, 0.0), 7, 1 + 0.06 * push, (driftx * 0.6, 0),
                              stretch=(2.6, 1.0)), 0.3, 1.0, 1.2)
        ground = np.clip((ny + 0.05) / 0.8, 0, 1)
        bg += fog_rgb(nm * (0.25 + 0.75 * ground), np.array([0.11, 0.125, 0.15], np.float32), 0.9) * bgI * 0.9

        # dust motes in the beam
        P = c.cache.get("motes")
        if P is None:
            P = c.cache["motes"] = E.Particles(int(140 * p["PARTICLE_INTENSITY"]), seed=31, z=(0.5, 3.0))
        if P.n:
            x, y = P.drift(t, vel=(0.02, 0.004), turb=0.05, freq=0.25)
            bm = D.cone(H, W, (-1.7, -1.25), 33, 16, 3.2, 0.3, res=8)
            mot = E.particle_layer(H, W, P, x + driftx, y, (0.8, 0.88, 1.0), 1.3, 0.35, zoom=1 + 0.08 * push,
                                   focus=1.0, dof=1.0, t=t, glow=0.8)
            bg += mot * (0.25 + 0.75 * bm[..., None])

        # title ---------------------------------------------------------------
        sp = c.title()
        sh = c.shaded(PEWTER)
        sw = K.prog(t, imp - 0.2, 1.8)
        sweep = (-0.8 + 1.7 * K.ease_in_out(sw), 0.14, 0.6, 0.8 * (1 if 0 < sw < 1 else 0))
        rgb, a = sh.shade(light=(-0.6, -0.55, 0.55), rim_dir=(-0.6, -0.8), rim_gain=0.7 + 0.8 * hit, sweep=sweep,
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.85 + 0.3 * hit)
        nz = c.cache.get("tnz")
        if nz is None:
            nz = c.cache["tnz"] = D.sprite_noise(sp, 1.4, 13, 2.4)
        thr = 1.25 - 1.45 * K.ease_in_out(u, 2)
        a = a * np.clip((nz - thr) * 3.5, 0, 1)
        haze = (1 - K.smooth(u)) * 0.5 + 0.28 * (1 - part) * K.smooth(u) + 0.55 * K.smooth(ex)
        fogc = np.array([0.12, 0.14, 0.18], np.float32) + acc * 0.08
        rgb = rgb * (1 - haze) + fogc * haze
        cam = c.cam(zoom=1 + 0.10 * push, pan=(driftx * H / 2 * 0.8, 0))
        L = c.layer()
        op = K.smooth(u * 1.6) * (1 - K.ease_in(ex, 1.5) * 0.92)
        c.place(L, cam, rgb, a, sp, 1.0, off=(0, 0, 0.08 * H * (1 - K.ease_out(u, 2))), opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.35, (14, 22), 40, k)
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.55, 0), 9 * k) * 0.5 * p["GLOW_STRENGTH"]

        # fog in front of the title (two planes, the nearest has the most parallax)
        hx, hy = c.hero()
        cx, cy = hx / (H / 2), hy / (H / 2)
        clear_r = 0.15 + 1.05 * part
        clearing = 1 - K.soft_spot(H, W, cx, cy, clear_r * 1.6, clear_r * 0.75, 1.6) * min(1.0, part * 1.6)
        front_d = (0.75 * (1 - 0.5 * K.smooth(K.prog(t, c.start + 0.5, c.reveal))) + 0.2) * clearing
        front_d = front_d + 0.62 * K.smooth(ex)
        n1 = D.shaped(D.plane(H, W, t, 1.2, (0.016, -0.001), 11, 1 + 0.16 * push, (driftx * 1.2, 0),
                              stretch=(2.2, 1.0)), 0.25, 1.0)
        img = D.over_lit(img, fog_rgb(np.ones_like(n1), np.array([0.14, 0.155, 0.18], np.float32), 1.0) * bgI,
                         n1 * front_d * min(1.0, bgI))
        n2 = D.shaped(D.plane(H, W, t, 0.75, (0.03 + 0.03 * K.smooth(ex), 0.0), 17, 1 + 0.32 * push,
                              (driftx * 2.0, 0), stretch=(1.8, 1.0)), 0.4, 1.0, 1.3)
        near_d = (0.30 + 0.5 * K.smooth(ex)) * (1 - 0.7 * part) * min(1.0, bgI)
        img = D.over_lit(img, fog_rgb(np.ones_like(n2), np.array([0.13, 0.145, 0.17], np.float32), 0.7), n2 * near_d)

        img = subtitle(c, img, cam, imp + 0.6, c.exit_start - 0.3, (0.62, 0.68, 0.78), y_rel=0.85)
        return c.finish(img, vignette=0.6, grain=0.04, bloom=(0.65, 0.45),
                        grade=dict(shadows=(-0.002, 0.0, 0.008), sat=0.9, contrast=1.04))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"], "Moonlight Color")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        push = e_inout(prog(0, g.frames))
        part = f"{e_out(prog(I, 50), 2)}*(1 - {ex})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "NightSky", [(0, "#080a0c", 1), (1, "#03050a", 1)])
        bg = F.light_spot(g, "MoonHalo", bg, None, (0.08, 0.95), 0.6, 0.6, 0.6, accent=True, gain=0.5,
                          blend=f"0.5*{BG}")
        bg = D.f_fog(g, "FogFar", bg, "#000000", "#141820", 1.8, f"1 + 0.03*{push}", (0.00025, 0.0),
                     blend=f"0.9*{BG}")
        g.at(0, 2)
        beam = F.closed_poly_mask(g, "MoonBeamShape", [(-0.05, 1.05), (0.12, 1.05), (0.85, 0.05), (0.45, -0.05)],
                                  soft=0.12)
        bcol = F.accent_solid(g, "MoonBeamColor", 0.6)
        F.masked(bcol, beam)
        bnoise = F.noise(g, "BeamFogNoise", "#303030", "#ffffff", detail=4, scale=2.4, seethe_rate=0.04,
                         contrast=1.3, center="Point(0.5 + time*0.0005, 0.5)")
        lit_beam = F.merge(g, "BeamThroughFog", bcol, bnoise, mode="Multiply")
        bg = F.merge(g, "MoonBeam", bg, lit_beam, mode="Screen",
                     blend=f"{BG}*(0.35 + 0.15*{u} + 0.25*{decay(I, 30)})*(1 - 0.6*{ex})")
        bg = D.f_fog(g, "FogMid", bg, "#000000", "#1c2129", 2.6, f"1 + 0.06*{push}", (0.0005, 0.00005),
                     blend=f"0.8*{BG}")
        bg = F.particles(g, "Motes", bg, number=10, lifespan=200, velocity=0.0015, angle=10, angle_var=180,
                         size=0.25, color=(0.8, 0.88, 1.0), region="CubeRgn", region_size=(2.4, 1.4, 1.0),
                         center_y=0.0, turbulence=0.08, glow=2)

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Bebas Neue", "Regular", 0.2, 1.12,
                             color=p["TEXT_COLOR"])
        refl = F.fill_material(g, "PewterReflect", title,
                               [(0, "#2a3038", 1), (0.42, "#7d8896", 1), (0.5, "#d8e2ee", 1), (0.58, "#5b6470", 1),
                                (1, "#1c2027", 1)])
        face = F.merge(g, "FaceReflect", title, refl, mode="Multiply", blend=0.75)
        rim = F.edge_light(g, "MoonRim", title, 0.002, -0.003, accent=True, gain=1.3, blur_px=1.2)
        face = F.merge(g, "RimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.5 + 0.6*{decay(I, 24)}), 1)")
        face = F.light_sweep(g, "MoonSweep", face, title, f"{I} - 5", 43, angle=35, width=0.1, peak=0.6,
                             accent=True)
        g.at(0, 6)
        # condensation reveal: luminance-threshold of a fog noise
        cn = F.noise(g, "CondenseNoise", "#000000", "#ffffff", detail=5, scale=5, seethe_rate=0.02, contrast=1.6)
        cm = F.bitmap_mask(g, "CondenseMask", cn, channel="Luminance")
        cm.expr("Low", f"1.05 - 1.25*{e_inout(u)}", 1)
        cm.expr("High", f"1.25 - 1.25*{e_inout(u)}", 1)
        hold = F.solid(g, "TitleHolder", (0, 0, 0), alpha=0.0)
        tm = F.merge(g, "TitleCondense", hold, face)
        F.masked(tm, cm)
        haze = F.cc(g, "DepthHaze", tm, gain=f"(0.45 + 0.55*{u})*(1 - 0.5*{ex})")
        placed = F.title_placement(g, "TitleDepth", haze, size_expr=f"0.94 + 0.06*{e_out(u, 2)}")
        tglow = F.softglow(g, "TitleGlow", placed, 10, gain=f"0.5*{ctl('GlowStrength')}", threshold=0.5)
        scene = F.merge(g, "TitleInFog", bg, tglow, blend=f"min({u}*1.6, 1)*(1 - 0.92*pow({ex}, 1.5))")

        g.at(0, 8)
        clear = F.ellipse(g, "FogParting", (0.5, 0.5), 0.2, 0.2, 0.35, invert=True)
        clear.expr("Width", f"0.15 + 1.1*{part}", 0.2)
        clear.expr("Height", f"(0.15 + 1.1*{part})*0.9", 0.2)
        scene = D.f_fog(g, "FogFront", scene, "#000000", "#2a3039", 2.2, f"1 + 0.16*{push}", (0.0008, -0.0001),
                        blend=f"min({BG}, 1)*(0.18 + 0.62*(1 - 0.65*{u}) + 0.62*{ex})", mode="Normal",
                        mask=clear, contrast=1.5)
        scene = D.f_fog(g, "FogNear", scene, "#000000", "#262b34", 1.2, f"1 + 0.32*{push}",
                        (0.0014, 0.0), blend=f"min({BG}, 1)*(0.35 + 0.5*{ex})*(1 - 0.7*{part})", contrast=1.8)
        g.at(0, 10)
        scene = D.f_sub(g, p, "Teko", "SemiBold", (0.62, 0.68, 0.78), -0.14, f"{I} + 14", f"{ctl('ExitStart')} - 6",
                        scene=scene)
        scene = F.xf(g, "Camera", scene, center=f"Point(0.5 + 0.02*{push}, 0.5)", size=f"1 + 0.10*{push}", edges=1)
        g.output = F.finish(g, scene, vignette=0.6)


DESIGN = T31()
