"""T34 - Underwater Colossus."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from . import _d_helpers as D

SUNKEN_STONE = Material(base=(0.55, 0.62, 0.58), spec=(0.7, 0.95, 0.9), spec_power=20, spec_gain=0.25, diffuse=0.85,
                        ambient=0.14, metal=0.0, bevel=0.07, texture="stone", tex_amount=0.32, bump=0.03,
                        rim=(0.5, 0.95, 0.9), seed=34)
WATER = np.array([0.02, 0.11, 0.13], np.float32)


class T34(Design):
    ID = "T34"
    NAME = "Underwater Colossus"
    SLUG = "Underwater_Colossus"
    CATEGORY = "D - Atmosphere and Environment"
    CONCEPT = "A sunken monument of colossal stone letters rises out of the deep into the light from the surface."
    ENTRANCE = ("Slow-motion ascent: the title rises from below the frame and out of the depth haze, "
                "the water colour clearing off it as it approaches.")
    REVEAL = ("It settles at the impact frame - a slow silt plume billows out from its base and the caustic light "
              "from the surface lands on the faces.")
    CAMERA = "Weightless slow drift and gentle push; marine snow and haze planes drift at different depths; refraction wobble."
    MATERIAL = "Algae-tinted weathered stone with animated caustic light projected onto the letter faces."
    EXIT = "The colossus sinks back into the dark while the light shafts dim and the haze closes."
    TECHNIQUES = ["surface light shafts", "projected caustics on the title", "marine snow with depth of field",
                  "layered blue-green haze", "silt plume", "refraction wobble", "slow-motion ascent"]
    DURATION_FRAMES = 240
    DEFAULTS = dict(MAIN_TITLE="LEVIATHAN", SUBTITLE="FROM THE DEEP IT RISES", FONT_FAMILY="anton",
                    TEXT_COLOR="#A8BDB4", ACCENT_COLOR="#7DF0DC", ANIMATION_START=12, ANIMATION_DURATION=112,
                    IMPACT_FRAME=124, HOLD_DURATION=64, EXIT_START=190, EXIT_DURATION=46, LETTER_SPACING=0.06,
                    TITLE_WIDTH=0.6, SUB_FONT_FAMILY="teko")
    SOUND = [(0, "water", "Deep underwater ambience, muffled pressure"), (0, "atmos", "Whale-like low drone"),
             (12, "swell", "Slow rising swell under the ascent"), (110, "rwhoosh", "Muffled reverse surge"),
             (124, "sub", "Deep muffled thoom as it settles"), (126, "debris", "Silt plume hiss (soft)"),
             (140, "shimmer", "Caustic light shimmer"), (190, "swell", "Descending swell"),
             (220, "tail", "Long underwater tail")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        ue = K.ease_out(u, 2.2)
        hit = c.hit(0.4, 1.6)
        drift = K.ease_in_out(K.prog(t, 0, c.dur), 2)
        nx, ny = K.grid(H, W)
        dim = 1 - 0.65 * K.smooth(ex)

        # water volume --------------------------------------------------------
        bg = K.vgrad(H, W, (0.05, 0.25, 0.27), (0.004, 0.025, 0.04), 0.8) * bgI * (0.75 + 0.25 * dim)
        shafts = np.zeros((H // 4, W // 4), np.float32)
        sg = D.small_grid(H, W)
        for i, (x0, ph) in enumerate(((-1.2, 0.0), (-0.3, 1.7), (0.5, 3.1), (1.3, 4.4))):
            ang = 97 - x0 * 5 + 2.5 * math.sin(t * 0.21 + ph)
            m = E.light_cone(H // 4, W // 4, (x0 - 0.2 + 0.05 * drift, -2.6), ang, 5.5 + 1.5 * math.sin(t * 0.3 + ph),
                             2.2, 0.15)
            shafts += m * (0.6 + 0.4 * math.sin(t * 0.5 + ph * 2))
        shafts = D.up(shafts, H, W)
        flick = D.plane(H, W, t, 3.0, (0.03, 0.05), 3, 1.0, stretch=(0.3, 2.0), evolve=0.3)
        bg += (shafts * (0.5 + 0.6 * flick) * 0.42 * np.clip(0.9 - ny * 0.5, 0.3, 1.3) * dim * bgI)[..., None] * (acc * 0.6 + 0.2)
        # far haze plane + seabed silhouette
        hf = D.shaped(D.plane(H, W, t, 1.0, (0.008, 0.002), 5, 1 + 0.03 * drift, (drift * 0.05, 0)), 0.3, 1.0)
        bg += (hf * 0.10 * bgI)[..., None] * np.array([0.10, 0.4, 0.42], np.float32)
        xs = np.linspace(-W / H, W / H, W).astype(np.float32) + 0.06 * drift
        bed = 0.78 + 0.06 * np.sin(xs * 2.1 + 1) + 0.03 * np.sin(xs * 5.3)
        bm = cv2.GaussianBlur((ny > bed[None, :]).astype(np.float32), (0, 0), 3 * k)
        bg = bg * (1 - bm[..., None] * 0.8)

        # marine snow behind the title (far)
        nP = int(260 * p["PARTICLE_INTENSITY"])
        P = c.cache.get("snow")
        if P is None and nP:
            P = c.cache["snow"] = E.Particles(nP, seed=34, z=(0.3, 3.5))
        if nP:
            x, y = P.drift(t, vel=(0.006, 0.012), turb=0.03, freq=0.2)
            far = P.z > 1.0
            Pf = E.Particles(0)
            Pf.n, Pf.z, Pf.r, Pf.r2, Pf.r3, Pf.phase = int(far.sum()), P.z[far], P.r[far], P.r2[far], P.r3[far], P.phase[far]
            bg += E.particle_layer(H, W, Pf, x[far], y[far], (0.6, 0.9, 0.85), 1.1, 0.35, zoom=1 + 0.05 * drift,
                                   focus=1.0, dof=0.9, t=t, glow=0.6)

        # title -----------------------------------------------------------------
        sp = c.title()
        sh = c.shaded(SUNKEN_STONE)
        cs = c.cache.get("cs")
        if cs is None:
            cs = c.cache["cs"] = (max(8, sp.h // 2), max(8, sp.w // 2))
        caus = E.caustics(cs[0] * 2, cs[1] * 2, t * 0.6, scale=1.7 * sp.w / W, seed=31, sharp=9.0)
        caus = cv2.resize(caus, (sp.w, sp.h))
        topness = np.clip(0.6 - sh.v * 0.8, 0.2, 1.2)
        light_in = (0.35 + 0.65 * ue) * dim
        patch = D.shaped(K.sample(K.fft_noise(256, 2.4, 61), sp.h, sp.w, 1.2 * sp.w / W * 2, t * 0.02, t * 0.01), 0.3, 0.8)
        emis = ((caus * topness * sp.mask * (0.3 + 0.7 * patch)) * (0.8 + 0.4 * hit) * light_in)[..., None] * acc
        rgb, a = sh.shade(light=(0.1, -0.95, 0.45), rim_dir=(0, -1), rim_gain=(0.4 + 0.5 * hit) * light_in,
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.55 + 0.4 * ue, emissive=emis)
        haze = np.clip(0.85 * (1 - ue) + 0.12 + 0.75 * K.smooth(ex), 0, 0.97)
        rgb = rgb * (1 - haze) + WATER * 1.4 * haze
        sink = K.ease_in(ex, 2)
        rise = (0.62 * H) * (1 - ue) + 0.4 * H * sink
        zoff = 0.5 * H * (1 - ue) + 0.6 * H * sink
        cam = c.cam(zoom=1.0 + 0.06 * drift, pan=(math.sin(t * 0.25) * 8 * k, math.sin(t * 0.19) * 5 * k))
        L = c.layer()
        op = K.smooth(u * 3) * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.5, c.exit_dur * 0.5)))
        c.place(L, cam, rgb, a, sp, 1.0, off=(0, rise, zoff), opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.3, (0, 30), 40, k)
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.5, 0), 8 * k) * 0.5 * p["GLOW_STRENGTH"]

        # silt plume from the base after the settle
        if t > imp - 0.1:
            dt = t - imp
            hx, hy = c.hero()
            bx, by = hx / (H / 2), (hy + sp.ink_h * 0.5 * cam.zoom) / (H / 2)
            grow = 1 - math.exp(-max(dt, 0) / 1.2)
            sm = D.shaped(D.plane(H, W, t, 2.0, (0.01, -0.02), 41, 1.0, (0, 0), evolve=0.08), 0.3, 0.9)
            env = K.soft_spot(H, W, bx, by + 0.05 - 0.1 * grow, 0.25 + 1.1 * grow, 0.08 + 0.22 * grow, 1.3)
            dens = np.clip(sm * 1.4, 0, 1) * env * min(1.0, dt * 2) * math.exp(-max(dt, 0) / 3.5) * 0.9 * p["IMPACT_INTENSITY"]
            img = D.over(img, np.array([0.13, 0.27, 0.26], np.float32) * bgI, dens)

        # near haze + near marine snow (in front)
        hn = D.shaped(D.plane(H, W, t, 0.8, (0.012, -0.004), 9, 1 + 0.12 * drift, (drift * 0.2, 0)), 0.35, 1.0)
        img = D.over(img, WATER * 1.6 * bgI, hn * (0.25 + 0.4 * K.smooth(ex)))
        if nP:
            near = ~far
            Pn = E.Particles(0)
            Pn.n, Pn.z, Pn.r, Pn.r2, Pn.r3, Pn.phase = int(near.sum()), P.z[near], P.r[near], P.r2[near], P.r3[near], P.phase[near]
            img += E.particle_layer(H, W, Pn, x[near], y[near], (0.6, 0.9, 0.85), 1.3, 0.3, zoom=1 + 0.12 * drift,
                                    focus=1.0, dof=1.1, t=t, glow=0.6)
        # refraction wobble
        wob = c.cache.get("wob")
        if wob is None:
            wob = c.cache["wob"] = K.fft_noise(256, 2.2, 55)
        dx = K.sample(wob, H // 4, W // 4, 1.5, t * 0.05, 0) - 0.5
        dy = K.sample(wob, H // 4, W // 4, 1.5, 0.3, t * 0.05) - 0.5
        img = K.remap_offset(img, D.up(dx, H, W) * 6 * k, D.up(dy, H, W) * 4 * k)
        img = subtitle(c, img, cam, imp + 1.0, c.exit_start - 0.2, (0.62, 0.86, 0.82), y_rel=0.8, fade=1.4)
        return c.finish(img, vignette=0.6, grain=0.03, bloom=(0.6, 0.5),
                        grade=dict(shadows=(-0.004, 0.004, 0.008), sat=0.95, contrast=1.04))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"], "Surface Light Color")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        ue = e_out(u, 2.2)
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        drift = e_inout(prog(0, g.frames))
        dim = f"(1 - 0.65*{ex})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "WaterColumn", [(0, "#0d4045", 1), (0.5, "#06222a", 1), (1, "#01070b", 1)],
                           start=(0.5, 1.0), end=(0.5, 0.0))
        for i, (x0, ph) in enumerate(((0.2, 0.0), (0.42, 1.7), (0.62, 3.1), (0.82, 4.4))):
            sm = F.closed_poly_mask(g, f"Shaft{i}Shape", [(x0 - 0.01, 1.05), (x0 + 0.01, 1.05), (x0 - 0.02, 0.0),
                                                          (x0 - 0.12, 0.0)], soft=0.05)
            sm.expr("Center", f"Point(0.5 + 0.015*sin(time*0.0088 + {ph}), 0.5)", [0.5, 0.5])
            sc = F.accent_solid(g, f"Shaft{i}Color", 0.45)
            F.masked(sc, sm)
            bg = F.merge(g, f"Shaft{i}", bg, sc, mode="Screen",
                         blend=f"{BG}*{dim}*(0.35 + 0.25*sin(time*0.021 + {ph * 2:.1f}))")
        bg = D.f_fog(g, "HazeFar", bg, "#000000", "#164c50", 1.8, f"1 + 0.03*{drift}", (0.0003, 0.0001),
                     blend=f"0.6*{BG}")
        g.at(0, 2)
        bg = F.particles(g, "MarineSnowFar", bg, number=14, lifespan=220, velocity=0.0008, angle=-80, angle_var=40,
                         size=0.2, color=(0.6, 0.9, 0.85), region="CubeRgn", region_size=(2.4, 1.4, 1.5),
                         center_y=0.0, turbulence=0.06, glow=2)

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Anton", "Regular", 0.19, 1.06, color=p["TEXT_COLOR"])
        stone = F.noise(g, "StoneWeathering", "#5c6b64", "#ffffff", detail=7, scale=18, seethe_rate=0.0, contrast=1.3)
        smatte = F.bitmap_mask(g, "StoneMatte", title)
        F.masked(stone, smatte)
        face = F.merge(g, "WeatheredFace", title, stone, mode="Multiply", blend=0.7)
        caus = F.noise(g, "Caustics", "#000000", "#ffffff", detail=3, scale=9, seethe_rate=0.25, contrast=4.0,
                       brightness=-0.4, center="Point(0.5 + time*0.0008, 0.5 - time*0.0005)")
        cm = F.bitmap_mask(g, "CausticsMatte", title)
        F.masked(caus, cm)
        ctint = F.accent_solid(g, "CausticTint", 1.0)
        ctinted = F.merge(g, "CausticTinted", caus, ctint, mode="Multiply")
        face = F.merge(g, "CausticProjection", face, ctinted, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.35 + 0.65*{ue})*{dim}*(0.7 + 0.4*{decay(I, 40)}), 1)")
        g.at(0, 6)
        rim = F.edge_light(g, "SurfaceRim", title, 0.0, -0.003, accent=True, gain=1.0, blur_px=2.0)
        face = F.merge(g, "SurfaceRimMerge", face, rim, mode="Screen", blend=f"0.5*{dim}")
        haze = F.cc(g, "DepthHaze", face, gain=f"(0.25 + 0.75*{ue})*(1 - 0.8*{ex})")
        placed = F.title_placement(g, "Ascent", haze, size_expr=f"(0.8 + 0.2*{ue})*(1 - 0.3*{e_in(ex, 2)})",
                                   center_extra_y=f"-0.6*(1 - {ue}) - 0.35*{e_in(ex, 2)}")
        soft = F.blur(g, "DepthSoften", placed, f"6*(1 - {ue}) + 6*{ex}")
        scene = F.merge(g, "TitleInWater", bg, soft, blend=f"min({u}*3, 1)*(1 - {clamp01(f'({ex} - 0.5)*2')})")

        g.at(0, 8)
        plume_m = F.ellipse(g, "SiltPlumeShape", (0.5, 0.4), 0.2, 0.1, 0.4)
        pg = e_out(prog(I, 70), 2)
        plume_m.expr("Center", f"Point({ctl('TextPosX')}, {ctl('TextPosY')} - 0.1 + 0.08*{pg})", [0.5, 0.4])
        plume_m.expr("Width", f"0.2 + 0.9*{pg}", 0.2)
        plume_m.expr("Height", f"0.1 + 0.35*{pg}", 0.1)
        scene = D.f_fog(g, "SiltPlume", scene, "#000000", "#2a5250", 3.0, "1", (0.0002, 0.0006),
                        blend=f"0.8*{ctl('ImpactIntensity')}*{step(I)}*pow(2.718282, -max(time - ({I}), 0)/84)",
                        mode="Normal", mask=plume_m)
        scene = D.f_fog(g, "HazeNear", scene, "#000000", "#0d3236", 1.4, f"1 + 0.12*{drift}", (0.0005, -0.0002),
                        blend=f"{BG}*(0.25 + 0.4*{ex})", mode="Normal")
        scene = F.particles(g, "MarineSnowNear", scene, number=8, lifespan=220, velocity=0.0012, angle=-80,
                            angle_var=40, size=0.45, color=(0.6, 0.9, 0.85), region="CubeRgn",
                            region_size=(2.4, 1.4, 0.4), center_y=0.0, turbulence=0.05, glow=4)
        g.at(0, 10)
        scene = D.f_sub(g, p, "Teko", "SemiBold", (0.62, 0.86, 0.82), -0.14, f"{I} + 24", f"{ctl('ExitStart')} - 5",
                        scene=scene)
        scene = F.xf(g, "Camera", scene,
                     center=f"Point(0.5 + 0.004*sin(time*0.0104), 0.5 + 0.004*sin(time*0.0079))",
                     size=f"1 + 0.06*{drift}", edges=1)
        g.output = F.finish(g, scene, vignette=0.6)


DESIGN = T34()
