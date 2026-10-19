"""T17 - Celestial Ascent (2.5D)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from ._b_helpers import put_title, add_sub, fam, fusion_subtitle

ALABASTER = Material(base=(0.92, 0.88, 0.80), spec=(1.0, 0.95, 0.85), spec_power=30, spec_gain=0.35, diffuse=0.7,
                     ambient=0.22, metal=0.18, env_sky=(1.0, 0.95, 0.85), env_horizon=(0.55, 0.55, 0.62),
                     env_ground=(0.62, 0.6, 0.62), env_sharp=5, bevel=0.06, bevel_round=True, texture="grain",
                     tex_amount=0.05, rim=(1.0, 0.92, 0.75), seed=91)


class T17(Design):
    ID = "T17"
    NAME = "Celestial Ascent"
    SLUG = "Celestial_Ascent"
    CATEGORY = "D - Mythic, Epic and Fantasy"
    CONCEPT = "A heavenly reveal high above the cloud sea: the title descends through luminous clouds into sunlight."
    ENTRANCE = ("The camera climbs out of a bank of glowing cloud; layered clouds stream past the lens while the "
                "pale title descends slowly from above into frame, half-veiled by passing vapour.")
    REVEAL = ("On the impact frame the sun crests directly behind the letters: volumetric shafts of light fan out "
              "around the title and its edges ignite with a warm-white rim.")
    CAMERA = "Measured vertical ascent (cloud layers parallax downward), slow push; no shake."
    MATERIAL = ("Backlit alabaster/ivory stone with soft specular, strong warm-white rim from the sun behind, "
                "gentle 2.5D depth; atmospheric scattering softens the far cloud sea.")
    EXIT = "The title keeps ascending up and out of frame into the light while the clouds close beneath the camera."
    TECHNIQUES = ["layered cloud parallax", "volumetric god rays (radial smear of occluded sun)", "backlit rim",
                  "cloud pass-through", "descending title", "ascend-out exit"]
    TRUE_3D = False
    DURATION_FRAMES = 210
    DEFAULTS = dict(MAIN_TITLE="ASCENSION", SUBTITLE="BEYOND THE HEAVENS", FONT_FAMILY="cinzel_bold",
                    SUB_FONT_FAMILY="marcellus", TEXT_COLOR="#EFE6D6", ACCENT_COLOR="#FFE2B0",
                    ANIMATION_START=10, ANIMATION_DURATION=86, IMPACT_FRAME=96, HOLD_DURATION=66, EXIT_START=162,
                    EXIT_DURATION=42, LETTER_SPACING=0.09, TITLE_WIDTH=0.6, SHAKE_AMOUNT=0.0)
    FUSION_NOTES = [
        "God rays are made with a Zoom-type DirectionalBlur of the sun disc masked by the inverted title and "
        "cloud alpha (no dedicated Rays tool is used, for compatibility). Move SunCore/RaysSmear centre together "
        "if you reposition the title.",
    ]
    SOUND = [(0, "wind", "High-altitude wind"), (0, "atmos", "Airy choir pad"), (10, "swell", "Rising strings"),
             (40, "whoosh", "Cloud layer passes"), (70, "whoosh", "Cloud layer passes"),
             (80, "riser", "Light riser"), (96, "swell", "Sun crest swell"), (96, "shimmer", "Radiance shimmer"),
             (96, "sub", "Soft sub bloom"), (162, "whoosh", "Ascent whoosh"), (186, "tail", "Airy tail")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.3, 1.6)
        after = 1.0 if t >= imp else 0.0
        T = K.prog(t, 0, c.dur)
        nx, ny = K.grid(H, W)
        hx, hy = c.hero()
        sp = c.title()
        climb = K.ease_in_out(K.prog(t, 0, c.exit_start + c.exit_dur), 1.6)  # camera ascent 0..1

        # ---- sky: deep zenith -> warm horizon; sun rises behind the title
        sun_y = float(hy / (H / 2)) + 0.45 - 0.58 * K.ease_out(K.prog(t, c.start, imp - c.start + 0.4), 2)
        sun_x = float(hx / (H / 2))
        sky = K.vgrad(H, W, (0.035, 0.055, 0.12), (0.50, 0.38, 0.28), gamma=1.3)
        sun_lvl = (0.35 + 0.65 * K.smooth(K.prog(t, c.start, imp - c.start)) + 0.25 * hit) * (1 - 0.3 * K.smooth(ex))
        glow = K.soft_spot(H, W, sun_x, sun_y, 1.1, 0.6, 1.4)
        core = K.soft_spot(H, W, sun_x, sun_y, 0.13, 0.13, 2.0)
        sky = sky + (glow * 0.32 * sun_lvl)[..., None] * acc + (core * 0.9 * sun_lvl)[..., None] * (acc * 0.4 + 0.6)
        bg = sky * bgI
        # cloud sea below (sinks as the camera climbs), billowy lit tops
        sea_y = 0.22 + 0.4 * climb
        n = K.fbm_field(H, W, t, 1.1, (0.006, 0.0), 91, beta=2.6, evolve=0.01, warp=0.0)
        n2 = K.fbm_field(H, W, t, 2.6, (0.01, 0.0), 92, beta=2.2, evolve=0.02, warp=0.0)
        nn = n * 0.65 + n2 * 0.35
        sea = np.clip((ny - sea_y + 0.22 * (nn - 0.5)) / 0.10, 0, 1)
        lit = np.clip(1.15 - (ny - sea_y) * 1.8, 0, 1) * (0.5 + 0.8 * nn) * \
            (0.6 + 0.6 * np.exp(-((nx - sun_x) / 1.4) ** 2))
        shadow_c, lit_c = K.col((0.20, 0.20, 0.27)), K.col((1.0, 0.86, 0.70))
        sea_c = shadow_c * (1 - lit[..., None]) + lit_c * lit[..., None] * (0.55 + 0.45 * sun_lvl)
        bg = bg * (1 - sea[..., None]) + sea_c * sea[..., None] * bgI

        # ---- title: descends into place, ascends out on exit
        sh = c.shaded(ALABASTER)
        ud = K.ease_out(u, 2.2)
        y_off = -(1 - ud) * H * 0.55 - K.ease_in(ex, 2.2) * H * 0.75
        rim = 0.35 + 0.9 * sun_lvl * after + 0.6 * hit
        rgb, a = sh.shade(light=(0.0, 0.6, 0.8), rim_gain=rim, rim_dir=(0, -1), base=K.col(p["TEXT_COLOR"]),
                          light_gain=0.42 + 0.1 * sun_lvl, env_shift=-0.2 + 0.2 * climb)
        cam = c.cam(zoom=0.98 + 0.07 * K.ease_in_out(T, 2))
        L = c.layer()
        op = K.smooth(u * 2.5) * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.6, c.exit_dur * 0.4)))
        depth = 0.08 * float(sp.cap_px) * p["EXTRUSION_DEPTH"]
        put_title(c, L, cam, rgb, a, sp, 1.0, off=(0, y_off, 0), depth=depth, side=np.array((0.55, 0.5, 0.48)),
                  slices=6, side_light=lambda q: 0.5 + 0.5 * q, opacity=op)
        # backlit edge halo (sun behind): bright rim along the alpha edge
        edge = np.clip(L.a - K.blur(L.a, 3 * k), 0, 1)
        img = comp(bg, L)
        img += (K.blur(edge, 2 * k) * 1.6 * sun_lvl * (0.3 + 0.7 * after))[..., None] * (acc * 0.5 + 0.5)

        # ---- god rays: sun disc occluded by the title, smeared radially
        occ_src = (core * 2.0 + glow * 0.25) * sun_lvl * (1 - L.a) * (1 - sea)
        cx_px, cy_px = W / 2 + sun_x * H / 2, H / 2 + sun_y * H / 2
        rays = K.god_rays(occ_src.astype(np.float32), cx_px, cy_px, length=0.9, decay=0.965, steps=26, scale=4)
        ray_gain = (0.6 + 1.3 * after * sun_lvl + 0.6 * hit) * p["GLOW_STRENGTH"] * bgI
        img += rays[..., None] * (acc * 0.55 + 0.45) * ray_gain

        # ---- cloud layers streaming past the camera (front), thick at start, closing on exit
        dense = 1 - K.smooth(K.prog(t, 0.0, c.start + c.reveal * 0.8))
        for i, (sc, spd, amt) in enumerate(((0.9, 0.9, 0.55), (1.6, 1.5, 0.35))):
            yshift = 0.05 * t * spd + climb * 0.9 * spd
            m = K.fbm_field(H, W, 0.0, sc, (0.0, 0.0), 95 + i, beta=2.6, evolve=0.0, warp=0.0)
            m = np.roll(m, int(yshift * H), 0)
            m = K.blur(np.clip((m - 0.32) / 0.5, 0, 1) ** 1.3, 6 * k)
            low = np.clip((ny + 0.5) / 0.6, 0, 1)
            a_c = np.clip(m * (amt * (0.15 + 1.7 * dense) + 0.9 * K.smooth(ex) * low), 0, 0.95)
            ccol = K.col((1.0, 0.95, 0.9)) * (0.62 + 0.38 * sun_lvl) * (0.75 + 0.25 * m[..., None])
            img = img * (1 - a_c[..., None]) + ccol * a_c[..., None] * bgI
        # floating motes of light
        P = c.cache.get("motes")
        if P is None:
            P = c.cache["motes"] = E.Particles(int(90 * p["PARTICLE_INTENSITY"]), seed=17, z=(0.5, 2.5))
        if P.n:
            x, y = P.drift(t, vel=(0.004, -0.03), turb=0.02, freq=0.3)
            img += E.particle_layer(H, W, P, x, y, acc * 0.6 + 0.4, 1.2, 0.18 * sun_lvl, zoom=1.0, dof=0.8,
                                    focus=1.0, t=t, flicker=0.3, glow=0.8)
        img = add_sub(c, img, cam, imp + 0.8, c.exit_start, (1.0, 0.95, 0.86), y_rel=0.92, tracking=0.6, rel=0.21)
        return c.finish(img, vignette=0.35, grain=0.02, bloom=(0.9, 0.35),
                        grade=dict(highlights=(0.004, 0.0, -0.012), contrast=1.04, sat=0.92))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        A0, AD = ctl("AnimStart"), ctl("AnimDuration")
        X0, XD = ctl("ExitStart"), ctl("ExitDuration")
        ex = prog(X0, XD)
        u = prog(A0, AD)
        BG = ctl("BackgroundIntensity")
        climb = e_inout(prog(0, f"{X0} + {XD}"))
        sun = f"(0.35 + 0.65*{prog(A0, f'{I} - {A0}')} + 0.25*{decay(I, 38)})*(1 - 0.3*{ex})"
        sun_y = f"(0.22 + 0.34*{e_out(prog(A0, f'{I} - {A0} + 10'), 2)})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "HeavenSky", [(0, "#283a5c", 1), (0.6, "#a88e78", 1), (1, "#c8a888", 1)],
                           start=(0.5, 1.0), end=(0.5, 0.2))
        sglow = F.accent_solid(g, "SunGlowColor", 0.8)
        sgm = F.ellipse(g, "SunGlowShape", (0.5, 0.5), 1.2, 0.8, 0.6)
        sgm.expr("Center", f"Point({ctl('TextPosX')}, {sun_y})", [0.5, 0.5])
        F.masked(sglow, sgm)
        bg = F.merge(g, "SunGlow", bg, sglow, mode="Screen", blend=f"min({BG}*{sun}*0.6, 1)")
        sea = F.noise(g, "CloudSea", "#5f5f6c", "#fff0dc", detail=7, scale=2.2, seethe_rate=0.01, contrast=1.8,
                      center=f"Point(0.5 + time*0.0004, 0.5 - 0.35*{climb})")
        seam = F.rect(g, "CloudSeaShape", (0.5, 0.15), 1.4, 0.3, 0.08)
        seam.expr("Center", f"Point(0.5, 0.2 - 0.3*{climb})", [0.5, 0.15])
        F.masked(sea, seam)
        bg = F.merge(g, "CloudSeaMerge", bg, sea, blend=f"{BG}")

        g.at(0, 2)
        ff, fs = fam(p["FONT_FAMILY"])
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], ff, fs, 0.15, 1.09, color=p["TEXT_COLOR"])
        ivory = F.fill_material(g, "IvoryFace", title, [(0, "#d8cebe", 1), (0.5, "#f4ece0", 1), (1, "#bfb3a2", 1)])
        face = F.merge(g, "IvoryMerge", title, ivory, mode="Multiply", blend=0.8)
        rim = F.edge_light(g, "SunRim", title, 0.0, -0.0025, accent=True, gain=1.6, blur_px=1.5)
        face = F.merge(g, "SunRimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.35 + 0.9*{sun}*{step(I)} + 0.6*{decay(I, 38)}), 1)")
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        ext = F.extrusion_stack(g, "Extrude", clear, title, layers=5, dx=0.0, dy=-0.001, color=(0.55, 0.5, 0.48))
        solid_t = F.merge(g, "TitleSolid", ext, face)
        placed = F.title_placement(g, "TitleDescent", solid_t,
                                   center_extra_y=f"0.55*(1 - {e_out(u, 2)}) + 0.75*{e_in(ex, 2)}")
        scene = F.merge(g, "TitleInSky", bg, placed, blend=f"min({u}*2.5, 1)*(1 - {clamp01(f'({ex} - 0.6)/0.4')})")

        g.at(0, 4)
        core = F.solid(g, "SunCore", (1.0, 0.95, 0.85))
        cm = F.ellipse(g, "SunCoreShape", (0.5, 0.5), 0.09, 0.16, 0.08)
        cm.expr("Center", f"Point({ctl('TextPosX')}, {sun_y})", [0.5, 0.5])
        inv = F.bitmap_mask(g, "TitleCutout", placed, paint="Subtract", prev=cm)
        F.masked(core, inv)
        rays = F.dirblur(g, "RaysSmear", core, f"0.25 + 0.15*{step(I)}", btype=3)
        rays.expr("Center", f"Point({ctl('TextPosX')}, {sun_y})", [0.5, 0.5])
        rglow = F.softglow(g, "RaysGlow", rays, 20, gain=f"{ctl('GlowStrength')}*1.5", threshold=0.02)
        scene = F.merge(g, "GodRays", scene, rglow, mode="Screen",
                        blend=f"min({BG}*(0.45 + 0.9*{step(I)}*{sun} + 0.5*{decay(I, 38)}), 1)")
        g.at(0, 6)
        for i, (sc, spd, amt) in enumerate(((2.0, 0.006, 0.55), (3.6, 0.010, 0.35))):
            cl = F.noise(g, f"PassingCloud{i + 1}", "#000000", "#f2ebe0", detail=6, scale=sc, seethe_rate=0.02,
                         contrast=2.2, brightness=-0.2, center=f"Point(0.5, 0.5 - time*{spd})")
            dense = f"(1 - {prog(0, f'{A0} + {AD}*0.8')})"
            scene = F.merge(g, f"CloudPass{i + 1}", scene, cl, mode="Screen",
                            blend=f"min({BG}*({amt}*(0.25 + 1.6*{dense}) + 0.6*{ex}), 1)")
        scene = F.particles(g, "LightMotes", scene, number=5, lifespan=200, velocity=0.003, angle=90, angle_var=40,
                            size=0.3, color=(1.0, 0.92, 0.78), region="CubeRgn", region_size=(2.2, 1.4, 1.0),
                            center_y=0.0, turbulence=0.1, glow=3)
        g.at(0, 8)
        scene = fusion_subtitle(g, scene, p, size=0.026, tracking=1.8, color=(0.86, 0.78, 0.66), y_off=-0.13,
                                t_in=f"{I} + 20", t_out=X0)
        scene = F.camera_rig(g, "Camera", scene, 0.98, 1.05, shake_frames=6, shake_amp=0.0)
        g.output = F.finish(g, scene, vignette=0.35)


DESIGN = T17()
