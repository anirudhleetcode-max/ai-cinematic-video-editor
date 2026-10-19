"""T19 - Cosmic Overlord (2.5D)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow
from ..fusion import FuID, ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_sprite
from ._b_helpers import put_title, add_sub, fam, fusion_subtitle

VOIDMETAL = Material(base=(0.40, 0.44, 0.52), spec=(0.85, 0.92, 1.0), spec_power=70, spec_gain=0.8, diffuse=0.45,
                     ambient=0.05, metal=0.65, env_sky=(0.30, 0.38, 0.55), env_horizon=(0.02, 0.025, 0.04),
                     env_ground=(0.55, 0.42, 0.30), env_sharp=10, bevel=0.06, bevel_round=True, texture="brushed",
                     tex_amount=0.06, rim=(1.0, 0.78, 0.55), seed=111)

PLANET_C, PLANET_R = (0.0, 2.50), 2.0  # normalised grid units (y down)


class T19(Design):
    ID = "T19"
    NAME = "Cosmic Overlord"
    SLUG = "Cosmic_Overlord"
    CATEGORY = "D - Mythic, Epic and Fantasy"
    CONCEPT = "A sovereign title assembles like a constellation above a planet while a star rises over its limb."
    ENTRANCE = ("A slow camera approach through three parallax star layers and drifting nebula; the letters drift "
                "in from deep space as points of light, linked by fading constellation lines, and lock into place.")
    REVEAL = ("On the impact frame the star crests the planet's limb: the atmosphere ignites, a restrained "
              "anamorphic flare crosses the frame and the metal letters catch a warm sunrise rim.")
    CAMERA = "Continuous forward dolly (star layers expand at different rates = parallax), gentle drift."
    MATERIAL = ("Dark blue-steel with cool space reflections and a warm sunrise rim from below; glyphs are born "
                "as emissive star points that cool into metal.")
    EXIT = "The camera keeps travelling: it flies through the title, which swells past the lens as stars stretch."
    TECHNIQUES = ["3-layer star parallax", "animated nebula", "planet limb + atmosphere", "constellation assembly",
                  "per-glyph depth convergence", "sunrise flare", "fly-through exit"]
    TRUE_3D = False
    DURATION_FRAMES = 236
    DEFAULTS = dict(MAIN_TITLE="OVERLORD", SUBTITLE="RULER OF A THOUSAND WORLDS", FONT_FAMILY="audiowide",
                    SUB_FONT_FAMILY="orbitron_med", TEXT_COLOR="#7F8BA0", ACCENT_COLOR="#FFB46A",
                    ANIMATION_START=20, ANIMATION_DURATION=92, IMPACT_FRAME=118, HOLD_DURATION=70, EXIT_START=192,
                    EXIT_DURATION=34, LETTER_SPACING=0.08, TITLE_WIDTH=0.6, TEXT_POSITION_Y=0.55, SHAKE_AMOUNT=0.3)
    FUSION_NOTES = [
        "Per-glyph constellation convergence is approximated in Fusion by a point-cell dissolve plus scale/blur "
        "convergence of the whole title (TextPlus has no per-character transforms without a Follower modifier).",
        "Star layers are pEmitter fields rendered by pRender and scaled by expressions for parallax.",
    ]
    SOUND = [(0, "atmos", "Deep space drone"), (20, "swell", "Cosmic pad swell"), (30, "shimmer", "Star points"),
             (60, "digital", "Constellation link ticks"), (100, "riser", "Solar riser"),
             (118, "impact", "Deep cosmic impact"), (118, "sub", "Sub drop"), (120, "shimmer", "Flare shimmer"),
             (192, "whoosh", "Fly-through whoosh"), (210, "tail", "Space tail")]

    # ------------------------------------------------------------ preview --
    def starfield(self, c, seed, n, zoom, drift, t):
        return E.stars(c.H, c.W, n=n, seed=seed, t=t, twinkle=0.25, zoom=zoom, drift=drift)

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        PI = p["PARTICLE_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.15, 0.9)
        after = 1.0 if t >= imp else 0.0
        T = K.prog(t, 0, c.dur)
        nx, ny = K.grid(H, W)
        hx, hy = c.hero()
        sp = c.title()
        dolly = K.ease_in_out(T, 1.5) + 0.8 * K.ease_in(ex, 2)  # forward travel

        # ---- deep space: nebula + three parallax star layers
        bg = K.radial(H, W, 0.3, -0.4, 2.6, (0.012, 0.014, 0.03), (0.002, 0.002, 0.006), 1.2)
        nz = 1.0 + 0.10 * dolly
        n1 = K.fbm_field(H, W, t, 0.9 / nz, (0.002, 0.001), 113, beta=3.0, evolve=0.01, warp=0.0)
        n2 = K.fbm_field(H, W, t, 1.7 / nz, (-0.002, 0.001), 114, beta=2.6, evolve=0.01, warp=0.0)
        m1 = np.clip((n1 - 0.48) * 2.2, 0, 1) ** 1.3 * K.soft_spot(H, W, -1.0, -0.35, 1.6, 0.9, 1.0)
        m2 = np.clip((n2 - 0.48) * 2.0, 0, 1) ** 1.3 * K.soft_spot(H, W, 1.1, -0.2, 1.4, 0.9, 1.0)
        neb = m1[..., None] * K.col((0.10, 0.16, 0.30)) + m2[..., None] * K.col((0.24, 0.07, 0.20)) + \
            (m1 * m2)[..., None] * K.col((0.3, 0.2, 0.1))
        bg += K.blur(neb, 8 * k) * 0.55 * bgI
        s_far = self.starfield(c, 201, int(600 * max(PI, 0.3)), 1.0 + 0.04 * dolly, (0.002, 0.0), t)
        s_mid = self.starfield(c, 202, int(260 * max(PI, 0.3)), 1.0 + 0.16 * dolly, (0.004, 0.0), t)
        s_near = self.starfield(c, 203, int(70 * max(PI, 0.3)), 1.0 + 0.45 * dolly, (0.008, 0.0), t)
        bg += (s_far * 0.55 + s_mid * 0.8 + s_near * 1.0) * bgI

        # ---- planet + atmosphere + rising star
        rise = K.ease_out(K.prog(t, c.start, imp - c.start), 2.2)
        pcx, pcy = PLANET_C[0], PLANET_C[1] - 0.06 * dolly
        pr = PLANET_R * (1 + 0.03 * dolly)
        d = np.sqrt((nx - pcx) ** 2 + (ny - pcy) ** 2)
        inside = np.clip((pr - d) * 300 * H / 1080 / 2, 0, 1)
        limb = np.exp(-((d - pr) / 0.012) ** 2)
        atmo = np.exp(-np.clip(d - pr, 0, None) / 0.05) * (d > pr - 0.02)
        sun_x = hx / (H / 2) + 0.25
        sun_y = pcy - pr - 0.02 + 0.10 * (1 - rise)
        toward = np.exp(-((nx - sun_x) / 0.9) ** 2)
        sunlvl = (0.15 + 0.85 * rise + 0.4 * hit) * (1 - 0.4 * K.smooth(ex))
        if "ptex" not in c.cache:
            c.cache["ptex"] = K.sample(K.fft_noise(256, 1.6, 115), H, W, 2.5, stretch=(4, 1))
        surf = (K.col((0.03, 0.035, 0.05)) + c.cache["ptex"][..., None] * K.col((0.03, 0.03, 0.035)))
        surf = surf * (0.4 + 1.6 * (toward * np.exp(-(d - pr + 0.25) ** 2 / 0.02))[..., None] * sunlvl)
        bg = bg * (1 - inside[..., None]) + surf * inside[..., None] * bgI
        bg += ((atmo * 0.35 * (0.3 + 0.7 * toward) + limb * 0.5 * toward) * sunlvl)[..., None] * \
            (K.col((0.35, 0.6, 1.0)) * 0.6 + acc * 0.4) * bgI
        sun = K.soft_spot(H, W, sun_x, sun_y, 0.05, 0.05, 2.0) * (sun_y < pcy - pr + 0.06)
        bg += (sun * 3.0 * sunlvl * (1 - inside))[..., None] * (acc * 0.4 + 0.6) * bgI
        bg += (K.soft_spot(H, W, sun_x, sun_y, 0.9, 0.35, 1.3) * 0.25 * sunlvl)[..., None] * acc * bgI

        # ---- title: glyphs converge from deep space as star points
        sh = c.shaded(VOIDMETAL)
        rgb, a = sh.shade(light=(0.3, 0.8, 0.5), rim_gain=0.2 + 1.0 * sunlvl * after + 0.8 * hit, rim_dir=(0.2, 1),
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.6 + 0.6 * sunlvl,
                          env_shift=0.1 * math.sin(t * 0.3))
        zoom_t = 1.0 + 0.06 * dolly
        cam = c.cam(zoom=zoom_t + 2.6 * K.ease_in(ex, 2.6), fov_scale=1.4)
        L = c.layer()
        G = sp.glyphs
        ng = max(1, len(G))
        rng = np.random.default_rng(117)
        starts = rng.uniform(0, 0.45, ng)
        offs = rng.uniform(-1, 1, (ng, 3)) * np.array([0.9 * W, 0.5 * H, 1.0])
        centers = []
        star_pts = []
        for i, gl in enumerate(G):
            gu = K.clamp((u - starts[i]) / 0.55)
            if gu <= 0:
                continue
            e = K.ease_out(gu, 3)
            z = (1 - e) * 4.0 * H * (0.6 + 0.4 * abs(offs[i, 2]))
            dx, dy = offs[i, 0] * (1 - e) * 0.35, offs[i, 1] * (1 - e) * 0.35
            cool = K.smooth((gu - 0.55) / 0.45)  # star point -> metal
            op = K.smooth((gu - 0.2) / 0.5)
            put_box = (int(gl.box[0]) - 2, int(gl.box[1]) - 2, int(gl.box[2]) + 2, int(gl.box[3]) + 2)
            glow_rgb = rgb * (0.4 + 0.6 * cool) + (1 - cool) * (acc * 0.25 + K.col((0.35, 0.5, 0.8))) * 0.9
            if op > 0.003:
                place_sprite(L, cam, glow_rgb, a, put_box, sp.anchor, (hx + dx, hy + dy, z), 1.0,
                             (0, 0, p["TEXT_ROTATION"]), None, op)
            P3 = np.array([[(gl.center[0] - sp.anchor[0]) + hx + dx, (gl.center[1] - sp.anchor[1]) + hy + dy, z]])
            pts, _ = cam.project(P3)
            centers.append(pts[0])
            star_pts.append((pts[0], (1 - cool) * K.smooth(gu * 4)))
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.3, (0, 10), 20, k)
        img = comp(bg, L, 1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.55, c.exit_dur * 0.45)))
        # star points + constellation lines while forming
        if star_pts:
            buf = np.zeros((H, W, 3), np.float32)
            for (x, y), lv in star_pts:
                if lv > 0.01:
                    cv2.circle(buf, (int(x * 4), int(y * 4)), int(3 * k * 4), tuple(float(v) for v in
                                                                                  (acc * 0.3 + 0.9) * lv * 2), -1,
                               cv2.LINE_AA, shift=2)
            link = (1 - K.smooth(K.prog(t, c.start + c.reveal * 0.75, c.reveal * 0.3))) * K.smooth(u * 3)
            img += buf * 0.8 + K.blur(buf, 6 * k) * 1.5
            if link > 0.01 and len(centers) > 1:
                ln = np.zeros((H, W), np.float32)
                arr = (np.array(centers) * 4).astype(np.int32).reshape(-1, 1, 2)
                cv2.polylines(ln, [arr], False, 1.0, max(1, int(k)), cv2.LINE_AA, shift=2)
                img += (ln * 0.35 * link)[..., None] * K.col((0.55, 0.72, 1.0))
        img += K.blur(np.maximum(L.rgb - 0.8, 0), 8 * k) * 0.6 * p["GLOW_STRENGTH"]
        # ---- sunrise flare (restrained anamorphic streak + soft bloom)
        fl = (0.25 * after * sunlvl + 0.9 * hit) * p["GLOW_STRENGTH"]
        if fl > 0.01:
            fx, fy = W / 2 + sun_x * H / 2, H / 2 + sun_y * H / 2
            ys = K.pixgrid(H, W)[1]
            streak = np.exp(-((ys - fy) / (2.5 * k)) ** 2) * np.exp(-np.abs(K.pixgrid(H, W)[0] - fx) / (700 * k))
            img += (streak * fl * 0.6)[..., None] * (K.col((0.5, 0.7, 1.0)) * 0.5 + acc * 0.5)
        # ---- exit: stars stretch as the camera rushes forward
        if ex > 0:
            img = K.zoom_blur(img, W / 2 + hx, H / 2 + hy, 0.12 * K.ease_in(ex, 2) * p["MOTION_BLUR_AMOUNT"])
        img = add_sub(c, img, cam, imp + 0.7, c.exit_start - 0.1, (0.72, 0.78, 0.90), y_rel=0.9, tracking=0.45,
                      rel=0.17)
        sx, sy = c.shake(0.002, 0.4, 9)
        if abs(sx) + abs(sy) > 0.05:
            Mx = np.float32([[1.01, 0, -0.005 * W + sx], [0, 1.01, -0.005 * H + sy]])
            img = cv2.warpAffine(img, Mx, (W, H), borderMode=cv2.BORDER_REFLECT)
        return c.finish(img, vignette=0.45, grain=0.025, bloom=(0.85, 0.5),
                        grade=dict(shadows=(-0.002, 0.0, 0.006), contrast=1.06, sat=0.95))

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
        dolly = f"({e_inout(prog(0, g.frames))} + 0.8*{e_in(ex, 2)})"
        rise = e_out(prog(A0, f"{I} - {A0}"), 2)
        sun = f"(0.15 + 0.85*{rise} + 0.4*{decay(I, 22)})*(1 - 0.4*{ex})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "DeepSpace", [(0, "#04050c", 1), (1, "#000002", 1)], gtype="Radial",
                           start=(0.6, 0.7), end=(1.4, 0.0))
        neb = F.noise(g, "Nebula", "#000000", "#2a1a3a", detail=7, scale=1.6, seethe_rate=0.01, contrast=1.8)
        neb2 = F.noise(g, "NebulaTeal", "#000000", "#10283c", detail=6, scale=2.4, seethe_rate=0.012, contrast=2.0,
                       center="Point(0.45, 0.55)")
        nb = F.merge(g, "NebulaMix", neb, neb2, mode="Screen")
        nb = F.xf(g, "NebulaDolly", nb, size=f"1 + 0.1*{dolly}")
        bg = F.merge(g, "NebulaMerge", bg, nb, mode="Screen", blend=f"{BG}")
        for i, (num, sc, sz) in enumerate(((140, 0.04, 0.12), (60, 0.16, 0.18), (18, 0.45, 0.26))):
            em = g.add("pEmitter", f"Stars{i + 1}Emitter")
            em.expr("Number", f"{num}*max({ctl('ParticleIntensity')}, 0.3)*{step(1)}*(1 - {step(3)})", num)
            em.set(Lifespan=400, Velocity=0.0, Region=FuID("CubeRgn"))
            em.setk("ParticleStyle.Size", sz)
            em.setk("CubeRgn.Width", 3.6)
            em.setk("CubeRgn.Height", 2.1)
            em.setk("CubeRgn.Depth", 0.5)
            rd = g.add("pRender", f"Stars{i + 1}Render")
            rd.conn("Input", em)
            F.frame_inputs(rd, g)
            sx = F.xf(g, f"Stars{i + 1}Parallax", rd, size=f"1 + {sc}*{dolly}")
            bg = F.merge(g, f"Stars{i + 1}", bg, sx, mode="Screen", blend=f"{BG}")
        g.at(0, 2)
        planet = F.solid(g, "PlanetSurface", "#07080c")
        pm = F.ellipse(g, "PlanetShape", (0.5, -0.88), 2.3, 4.1, 0.004)
        pm.expr("Center", f"Point(0.5, -0.88 + 0.03*{dolly})", [0.5, -0.88])
        F.masked(planet, pm)
        bg = F.merge(g, "Planet", bg, planet, blend=f"{BG}")
        atm = F.accent_solid(g, "AtmosphereColor", 0.8)
        am = F.ellipse(g, "AtmosphereShape", (0.5, -0.88), 2.3, 4.1, 0.03, border=0.006)
        am.expr("Center", f"Point(0.5, -0.88 + 0.03*{dolly})", [0.5, -0.88])
        F.masked(atm, am)
        bg = F.merge(g, "Atmosphere", bg, atm, mode="Screen", blend=f"min({BG}*{sun}, 1)")
        bg = F.light_spot(g, "SunRise", bg, None, (0.62, 0.22), 0.5, 0.2, 0.5, accent=True, gain=1.2,
                          blend=f"min({BG}*{sun}, 1)")

        g.at(0, 4)
        ff, fs = fam(p["FONT_FAMILY"])
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], ff, fs, 0.15, 1.08, color=p["TEXT_COLOR"])
        steel = F.fill_material(g, "BlueSteel", title, [(0, "#1a1f2a", 1), (0.5, "#5d6a80", 1), (0.55, "#9fb0c8", 1),
                                                        (1, "#151922", 1)])
        face = F.merge(g, "SteelMerge", title, steel, mode="Multiply", blend=0.85)
        rim = F.edge_light(g, "SunriseRim", title, 0.0, 0.003, accent=True, gain=1.5, blur_px=1.5)
        face = F.merge(g, "SunriseRimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.2 + {sun}*{step(I)} + 0.8*{decay(I, 22)}), 1)")
        pts = F.noise(g, "StarPointCells", "#000000", "#ffffff", detail=1, scale=30, seethe_rate=0.0, contrast=6,
                      discontinuous=True)
        pm2 = F.bitmap_mask(g, "Constellate", pts, channel="Luminance")
        pm2.expr("Low", f"0.95*(1 - {e_out(u, 2)})", 0.95)
        pm2.expr("High", f"0.95*(1 - {e_out(u, 2)}) + 0.05", 1)
        hold = F.solid(g, "TitleHolder", (0, 0, 0), alpha=0.0)
        tm = F.merge(g, "TitleAssemble", hold, face)
        F.masked(tm, pm2)
        hot = F.cc(g, "StarHeat", tm, gain=f"1 + 2.5*(1 - {prog(f'{A0} + {AD}*0.5', f'{AD}*0.5')})")
        g.at(0, 6)
        placed = F.title_placement(g, "TitleConverge", hot,
                                   size_expr=f"(0.85 + 0.15*{e_out(u, 3)})*(1 + 0.06*{dolly}) + 2.6*{e_in(ex, 3)}")
        conv = F.blur(g, "ConvergeBlur", placed, f"8*(1 - {e_out(u, 3)})")
        tglow = F.softglow(g, "StarGlow", conv, 12, gain=f"{ctl('GlowStrength')}*(0.3 + 1.2*(1 - {u}))",
                           threshold=0.4)
        scene = F.merge(g, "TitleInSpace", bg, tglow, blend=f"min({u}*4, 1)*(1 - {clamp01(f'({ex} - 0.55)/0.45')})")
        g.at(0, 8)
        streak = F.solid(g, "FlareStreakColor", (0.85, 0.85, 0.95))
        sm = F.rect(g, "FlareStreakShape", (0.62, 0.24), 1.6, 0.003, 0.004)
        F.masked(streak, sm)
        sgl = F.softglow(g, "FlareStreakGlow", streak, 6, gain=f"{ctl('GlowStrength')}", threshold=0.0)
        scene = F.merge(g, "SunriseFlare", scene, sgl, mode="Screen",
                        blend=f"min({ctl('GlowStrength')}*(0.25*{step(I)}*{sun} + 0.9*{decay(I, 22)}), 1)")
        zb = F.dirblur(g, "FlyThroughBlur", scene, f"0.12*{e_in(ex, 2)}*{ctl('MotionBlurAmount')}", btype=3)
        scene = fusion_subtitle(g, zb, p, size=0.022, tracking=1.6, color=(0.72, 0.78, 0.90), y_off=-0.12,
                                t_in=f"{I} + 16", t_out=f"{X0} - 2")
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.04, shake_frames=10, shake_amp=0.002)
        g.output = F.finish(g, scene, vignette=0.45)


DESIGN = T19()
