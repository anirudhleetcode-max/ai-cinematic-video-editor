"""T08 - Ember Storm."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, subtitle
from ..fusion import FuID, ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material

SATIN_GOLD = Material(base=(0.85, 0.7, 0.5), spec=(1.0, 0.85, 0.62), spec_power=45, spec_gain=0.45, diffuse=0.7,
                      ambient=0.1, metal=0.55, env_sky=(0.7, 0.5, 0.3), env_horizon=(0.08, 0.04, 0.02),
                      env_ground=(0.5, 0.25, 0.08), env_sharp=5, bevel=0.05, bevel_round=True, texture="grain",
                      tex_amount=0.12, bump=0.0, rim=(1.0, 0.7, 0.4), seed=88)

# ember depth layers: (count, z range, size, brightness)
LAYERS = [(260, (1.6, 3.4), 1.0, 0.55), (130, (0.85, 1.3), 1.4, 0.8), (80, (0.3, 0.6), 2.8, 1.25)]
NEAR, TITLE_Z = 0.45, 1.0


def soft_smoke(h, w, t, color, density, scale, rise, seed, light):
    n = K.fbm_field(h, w, t, scale, (0.006, rise), seed, beta=2.5, evolve=0.04, warp=0.1)
    m = np.clip((n - 0.42) * 2.0, 0, 1) ** 1.4
    lx, ly, lr, lc = light
    lit = 0.35 + 1.5 * K.soft_spot(h, w, lx, ly, lr)[..., None] * K.col(lc)[None, None, :]
    return m[..., None] * K.col(color)[None, None, :] * density * lit


class T08(Design):
    ID = "T08"
    NAME = "Ember Storm"
    SLUG = "Ember_Storm"
    CATEGORY = "B - Elemental Fury"
    CONCEPT = "A slow, elegant reveal inside a storm of embers layered in depth - cinematic focus does the storytelling."
    ENTRANCE = ("Rack focus: the shot opens focused on foreground embers with the title a soft glow behind smoke; focus "
                "pulls slowly to the title plane while the smoke thins.")
    REVEAL = "As focus locks, a gentle warm swell blooms behind the letters, the embers swirl and a satin sheen glides across."
    CAMERA = "Slow lateral crane with real parallax between three ember depth layers; selective focus (bokeh near and far)."
    MATERIAL = "Satin gold with soft warm reflections and an ember-orange rim; embers glow with flicker and bokeh."
    EXIT = "Focus racks back to the near embers; the title melts into bokeh and fades with the storm."
    TECHNIQUES = ["three-layer particle depth", "animated focus distance (rack focus)", "bokeh / DOF",
                  "parallax crane", "light swell", "satin sweep"]
    TRUE_3D = False
    DURATION_FRAMES = 240
    DEFAULTS = dict(MAIN_TITLE="EMBERSTORM", SUBTITLE="A LEGEND WRITTEN IN FIRE", FONT_FAMILY="marcellus",
                    TEXT_COLOR="#E6C79E", ACCENT_COLOR="#FF9238", ANIMATION_START=0, ANIMATION_DURATION=118,
                    IMPACT_FRAME=118, HOLD_DURATION=74, EXIT_START=192, EXIT_DURATION=48, LETTER_SPACING=0.1,
                    TITLE_WIDTH=0.64)
    SOUND = [(0, "atmos", "Warm airy drone"), (0, "wind", "Soft wind carrying embers"),
             (0, "fire", "Distant fire crackle"), (30, "swell", "Long orchestral-style swell into the focus lock"),
             (118, "swell", "Warm bloom as focus locks"), (120, "shimmer", "Satin sheen shimmer"),
             (190, "wind", "Gust as focus racks away"), (210, "tail", "Long airy tail")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        PI = p["PARTICLE_INTENSITY"]
        GL = p["GLOW_STRENGTH"]
        imp = c.impact
        ex = c.exit_u()
        u = c.reveal_u()
        uf = K.ease_in_out(u, 2.5)
        swell = c.hit(0.6, 1.4)
        focus = NEAR + (TITLE_Z - NEAR) * uf - (TITLE_Z - NEAR) * K.ease_in_out(ex, 2)
        crane = 1 - 2 * K.ease_in_out(K.prog(t, 0, c.dur), 2)           # +1 -> -1
        cam_x = 0.05 * crane                                              # normalised units at z = 1
        cam_y = -0.02 * crane
        hx, hy = c.hero()
        tcx, tcy = hx / (H / 2), hy / (H / 2)

        # --- deep background: warm darkness with distant lit smoke
        h2, w2 = H // 2, W // 2
        bg = K.vgrad(h2, w2, (0.008, 0.005, 0.004), (0.03, 0.012, 0.005))
        bg += soft_smoke(h2, w2, t, (0.08, 0.05, 0.035), 0.9, 0.9, 0.025, 21,
                         (tcx - cam_x * 0.3, 0.7, 1.4, acc * 1.2)) * bgI
        bg += (K.soft_spot(h2, w2, tcx - cam_x * 0.5, tcy, 1.1, 0.5, 1.4) * (0.05 + 0.14 * swell))[..., None] * acc * bgI
        bg = cv2.resize(bg * bgI, (W, H), interpolation=cv2.INTER_LINEAR)

        def embers(idx):
            n, zr, size, bright = LAYERS[idx]
            key = ("emb", idx)
            P = c.cache.get(key)
            if P is None:
                P = c.cache[key] = E.Particles(int(n * PI), seed=40 + idx, z=zr, spread=(2.6, 1.4))
            if P.n == 0:
                return 0
            gust = 0.05 * swell
            x, y = P.drift(t, vel=(0.012, -0.045), turb=0.05 + gust, freq=0.35)
            x = x - cam_x / P.z * 1.0
            y = y - cam_y / P.z
            return E.particle_layer(H, W, P, x, y, acc * 1.15 + np.array([0.2, 0.08, 0.0]), size,
                                    bright * (0.8 + 0.3 * swell), focus=focus, dof=2.6, flicker=0.45, t=t,
                                    glow=1.0)

        img = bg + embers(0)
        mid = embers(1) if PI > 0 else 0
        img = img + mid * 0.5    # mid layer: half of it sits behind the title plane

        # --- title: defocus driven by the focus distance; emerges through thinning smoke
        sp = c.title()
        sh = c.shaded(SATIN_GOLD)
        sw_u = K.prog(t, imp + 0.2, 2.4)
        sweep = (-0.9 + 1.8 * K.ease_in_out(sw_u), 0.16, 0.4, 0.9 * (0 < sw_u < 1))
        lg = 0.55 + 0.5 * uf + 0.35 * swell
        rgb, a = sh.shade(light=(-0.3, -0.5, 0.8), rim_dir=(0.0, 1.0), rim_gain=(0.35 + 0.6 * swell) * GL, sweep=sweep,
                          base=K.col(p["TEXT_COLOR"]), light_gain=lg, env_shift=0.1 * crane)
        cam = c.cam(zoom=1.0 + 0.05 * K.ease_in_out(K.prog(t, 0, c.dur)), pan=(-cam_x * H / 2, -cam_y * H / 2))
        L = c.layer()
        op = K.smooth(K.prog(t, c.start + 0.2, c.reveal * 0.65)) * (1 - K.smooth((ex - 0.35) / 0.65))
        c.place(L, cam, rgb, a, sp, 1.0 + 0.03 * (1 - uf), opacity=op)
        defocus = abs(focus - TITLE_Z) * 34 * k
        if defocus > 0.4:
            L.rgb, L.a = K.blur(L.rgb, defocus), K.blur(L.a, defocus)
        img = comp(img, L)
        img = img + K.blur(np.maximum(L.rgb - 0.45, 0), 14 * k) * (0.35 + 0.6 * swell) * GL

        # --- smoke between camera and title (thins as the focus arrives)
        front = (0.75 * (1 - K.smooth(u * 1.1)) + 0.12 + 0.3 * K.smooth(ex)) * bgI
        fs = soft_smoke(h2, w2, t * 1.3, (0.12, 0.08, 0.06), front, 1.3, 0.04, 27, (tcx, 0.6, 1.5, acc))
        img = img + cv2.resize(fs, (W, H))
        if PI > 0:
            img = img + mid * 0.5 + embers(2)   # near layer always in front

        img = subtitle(c, img, cam, imp + 0.9, c.exit_start - 0.3, (0.88, 0.76, 0.6), y_rel=0.88, tracking=0.55,
                       fade=1.4)
        img = img * (1 - 0.92 * K.smooth((ex - 0.75) / 0.25))
        return c.finish(img, vignette=0.5, grain=0.03, bloom=(0.7, 0.55))

    # ------------------------------------------------------------- Fusion --
    def _ember_layer(self, g, name, bg, number, size, region_z, blur_expr, center_x_expr, mode="Screen"):
        em = g.add("pEmitter", f"{name}Emitter")
        em.expr("Number", f"{number}*{ctl('ParticleIntensity')}", number)
        em.set(Lifespan=160, LifespanVariance=50, Velocity=0.003, VelocityVariance=0.002, Angle=90, AngleVariance=40,
               Region=FuID("CubeRgn"))
        em.setk("ParticleStyle.ColorControls", 1)
        em.setk("ParticleStyle.Red", 1.0)
        em.setk("ParticleStyle.Green", 0.6)
        em.setk("ParticleStyle.Blue", 0.25)
        em.setk("ParticleStyle.Size", size)
        em.setk("ParticleStyle.SizeVariance", size * 0.6)
        em.setk("CubeRgn.Width", 2.6)
        em.setk("CubeRgn.Height", 1.6)
        em.setk("CubeRgn.Depth", 0.2)
        em.setk("Transform3DOp.Translate.Z", region_z)
        tb = g.add("pTurbulence", f"{name}Swirl")
        tb.conn("Input", em)
        tb.set(XStrength=0.15, YStrength=0.1, ZStrength=0.05)
        rd = g.add("pRender", f"{name}Render")
        rd.conn("Input", tb)
        F.frame_inputs(rd, g)
        bl = F.blur(g, f"{name}Defocus", rd, blur_expr)
        gl = F.softglow(g, f"{name}Glow", bl, 6, gain=f"1.2*{ctl('GlowStrength')}", threshold=0.08)
        mv = F.xf(g, f"{name}Parallax", gl, center=center_x_expr)
        return F.merge(g, name, bg, mv, mode=mode, blend=f"min({ctl('ParticleIntensity')}, 1)")

    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S = ctl("AnimStart")
        ES = ctl("ExitStart")
        BG = ctl("BackgroundIntensity")
        GL = ctl("GlowStrength")
        AD = ctl("AnimDuration")
        u = prog(S, AD)
        ex = prog(ES, ctl("ExitDuration"))
        focus = f"({NEAR} + {TITLE_Z - NEAR}*{e_inout(u)} - {TITLE_Z - NEAR}*{e_inout(ex)})"
        crane = f"(1 - 2*{e_inout(prog(0, g.frames))})"
        swell = f"{ctl('ImpactIntensity')}*{decay(I, 30)}*{step(I)}"

        g.at(0, 0)
        bg = F.gradient_bg(g, "WarmDark", [(0, "#020101", 1), (0.7, "#090403", 1), (1, "#1c0a03", 1)])
        smoke = F.noise(g, "DistantSmoke", "#000000", "#2a1810", detail=5, scale=1.8, seethe_rate=0.03, contrast=1.5,
                        center=f"Point(0.5 + 0.01*{crane}, 0.5 + time*0.0008)")
        bg = F.merge(g, "DistantSmokeMerge", bg, smoke, mode="Screen", blend=f"0.8*{BG}")
        bg = F.light_spot(g, "SwellGlow", bg, None, (0.5, 0.5), 1.2, 0.5, 0.6, accent=True, gain=0.6,
                          blend=f"min({BG}*(0.25 + 0.7*{swell}), 1)")
        g.at(0, 2)
        bg = self._ember_layer(g, "EmbersFar", bg, 90, 0.18, -1.5, f"14*abs({focus} - 2.2)",
                               f"Point(0.5 + 0.004*{crane}, 0.5)")
        bg = self._ember_layer(g, "EmbersMid", bg, 50, 0.28, 0.0, f"14*abs({focus} - 1.05)",
                               f"Point(0.5 + 0.012*{crane}, 0.5)")

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Marcellus SC", "Regular", 0.14, 1.12,
                             color=p["TEXT_COLOR"])
        gold = F.fill_material(g, "SatinGold", title,
                               [(0, "#fff4dc", 1), (0.45, "#e2c49a", 1), (0.55, "#9c7650", 1), (1, "#d8b88c", 1)])
        face = F.merge(g, "GoldFace", title, gold, mode="Multiply", blend=1.0)
        rim = F.edge_light(g, "EmberRim", title, 0.0, 0.0025, accent=True, gain=1.3, blur_px=1.5)
        face = F.merge(g, "EmberRimMerge", face, rim, mode="Screen", blend=f"min({GL}*(0.35 + 0.6*{swell}), 1)")
        face = F.light_sweep(g, "SatinSheen", face, title, f"{I} + 5", 58, angle=22, width=0.14, peak=0.6,
                             color=(1.0, 0.9, 0.75))
        g.at(0, 6)
        lit = F.cc(g, "FocusLight", face, gain=f"0.45 + 0.4*{e_inout(u)} + 0.35*{swell}")
        defocus = F.blur(g, "TitleDefocus", lit, f"34*abs({focus} - {TITLE_Z})")
        placed = F.title_placement(g, "TitleCrane", defocus, size_expr=f"1.03 - 0.03*{e_inout(u)}",
                                   center_extra_x=f"0.012*{crane}", center_extra_y=f"-0.006*{crane}")
        bloom = F.softglow(g, "TitleBloom", placed, 16, gain=f"{GL}*(0.3 + 0.6*{swell})", threshold=0.45)
        scene = F.merge(g, "TitleInStorm", bg, bloom,
                        blend=f"{prog(f'{S} + 5', f'0.65*{AD}')}"
                              f"*(1 - {clamp01(f'({ex} - 0.35)/0.65')})")
        g.at(0, 8)
        fsm = F.noise(g, "SmokeVeil", "#000000", "#3a2416", detail=5, scale=2.2, seethe_rate=0.05, contrast=1.6,
                      center=f"Point(0.5 + 0.02*{crane}, 0.5 + time*0.0015)")
        scene = F.merge(g, "SmokeVeilMerge", scene, fsm, mode="Screen",
                        blend=f"min({BG}*(0.75*(1 - {u}) + 0.12 + 0.3*{ex}), 1)")
        scene = self._ember_layer(g, "EmbersNear", scene, 22, 0.5, 1.2, f"20*abs({focus} - {NEAR})",
                                  f"Point(0.5 + 0.03*{crane}, 0.5)")
        g.at(0, 10)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "Light", 0.03, 1.8,
                                    color=(0.88, 0.76, 0.6), y_off=-0.13)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 22", f"{ES} - 7", 34, 12))
        cam = F.xf(g, "Camera", scene, center=f"Point(0.5, 0.5)", size=f"1 + 0.05*{e_inout(prog(0, g.frames))}",
                   edges=1)
        black = F.solid(g, "FadeBlack", (0, 0, 0))
        cam = F.merge(g, "FinalFade", cam, black, blend=f"0.92*{clamp01(f'({ex} - 0.75)/0.25')}")
        g.output = F.finish(g, cam, vignette=0.5)


DESIGN = T08()
