"""T32 - Rain and Steel."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, subtitle, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from . import _d_helpers as D

WET_STEEL = Material(base=(0.40, 0.43, 0.47), spec=(0.95, 0.97, 1.0), spec_power=90, spec_gain=1.1, diffuse=0.55,
                     ambient=0.05, metal=0.65, env_sky=(0.55, 0.60, 0.68), env_horizon=(0.03, 0.035, 0.04),
                     env_ground=(0.08, 0.085, 0.09), env_sharp=16, bevel=0.045, texture="brushed", tex_amount=0.06,
                     rim=(0.85, 0.9, 1.0), seed=32)

LAMPS = (-1.25, 0.0, 1.25)          # lamp x positions (frame heights from centre)
LAMP_DELAY = (-0.25, 0.0, 0.2)      # seconds relative to the impact frame


def lamp_level(t, on, off, seed):
    """Sodium/LED floodlight: off -> clunk on with a short flicker -> on -> cut."""
    if t < on:
        return 0.0
    dt = t - on
    lv = 1.0
    if dt < 0.3:
        lv = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(dt * 95 + seed * 3)) * (dt / 0.3) + 0.3 * (dt / 0.3)
        lv = min(lv, 1.0)
    if t >= off:
        lv *= max(0.0, 1 - (t - off) / 0.08)
    return lv


class T32(Design):
    ID = "T32"
    NAME = "Rain and Steel"
    SLUG = "Rain_And_Steel"
    CATEGORY = "G - Atmospheric and Environmental Cinema"
    CONCEPT = "A rain-soaked industrial yard at night: wet steel lettering waits in the dark until the floodlights hit."
    ENTRANCE = "The title cranes up from below the eye-line in near darkness, rain falling through cold ambient light."
    REVEAL = ("Three overhead floodlights clunk on in sequence (with a short electrical flicker) - rain turns into "
              "lit streaks, the wet steel lights up and its reflection appears on the flooded floor.")
    CAMERA = "Restrained slow lateral truck (wall, rain and floor at different parallax); tiny clunk shake only."
    MATERIAL = "Dark brushed wet steel: hard top specular, running water streaks over the faces, mirror-wet floor."
    EXIT = "The floodlights cut out one by one; the last silhouette fades with the rain."
    TECHNIQUES = ["procedural corrugated steel wall", "three-depth rain", "volumetric floodlight cones",
                  "running water specular streaks", "rippled floor reflection", "rain splash rings"]
    DURATION_FRAMES = 192
    DEFAULTS = dict(MAIN_TITLE="IRONCLAD", SUBTITLE="FORGED IN THE STORM", FONT_FAMILY="russo",
                    TEXT_COLOR="#9AA3AE", ACCENT_COLOR="#CFE3FF", ANIMATION_START=4, ANIMATION_DURATION=54,
                    IMPACT_FRAME=64, HOLD_DURATION=80, EXIT_START=150, EXIT_DURATION=34, LETTER_SPACING=0.06,
                    TITLE_WIDTH=0.58, TEXT_POSITION_Y=0.54, SUB_FONT_FAMILY="teko")
    SOUND = [(0, "rain", "Heavy rain bed on steel"), (0, "atmos", "Industrial hum, distant"),
             (4, "riser", "Low metallic riser under the crane-up"), (58, "metal", "Relay click / lamp 1 clunk"),
             (64, "impact", "Floodlight slam: heavy metallic clunk + sub"), (64, "hammer", "Steel resonance"),
             (69, "metal", "Lamp 3 clunk"), (70, "water", "Water sheeting off steel"),
             (150, "metal", "Breakers cut, lamp by lamp"), (175, "tail", "Rain tail")]

    # ------------------------------------------------------------ preview --
    def _wall(self, c):
        w = c.cache.get("wall")
        if w is not None:
            return w
        H, W, k = c.H, c.W, c.k
        Wt = int(W * 1.25)
        xs = np.arange(Wt, dtype=np.float32)[None, :]
        ys = np.arange(H, dtype=np.float32)[:, None]
        corr = 0.7 + 0.3 * np.sin(xs / (46 * k) * 2 * math.pi)
        alb = np.repeat(corr, H, 0)
        panel = 300 * k
        seam = np.abs(((xs + 40 * k) % panel) - panel / 2) > panel / 2 - 3 * k
        alb = np.where(np.repeat(seam, H, 0), 0.12, alb)
        for yh in (0.18, 0.62):
            alb[int(H * yh):int(H * yh + 6 * k)] = 0.15
            for x in np.arange(20 * k, Wt, 60 * k):
                cv2.circle(alb, (int(x), int(H * yh + 14 * k)), max(2, int(4 * k)), 0.9, -1, cv2.LINE_AA)
        grime = K.sample(K.fft_noise(256, 2.2, 41), H, Wt, 2.0)
        wet = K.sample(K.fft_noise(256, 1.7, 42), H, Wt, 3.0, stretch=(0.5, 6.0))
        alb = alb * (0.55 + 0.6 * grime)
        wet = np.clip((wet - 0.58) * 3, 0, 1)
        w = c.cache["wall"] = (alb.astype(np.float32), wet.astype(np.float32), Wt)
        return w

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        truck = K.ease_in_out(K.prog(t, 0, c.dur), 2)
        pan = (0.5 - truck) * 0.16  # frame heights, camera trucks left->right
        off_t = c.exit_start
        lv = [lamp_level(t, imp + LAMP_DELAY[i], off_t + 0.25 * (2 - i) * c.exit_dur / 1.4, i)
              for i in range(3)]
        lamps = sum(lv) / 3
        nx, ny = K.grid(H, W)

        # wall (far parallax) -----------------------------------------------
        alb, wet, Wt = self._wall(c)
        x0 = int((Wt - W) / 2 + pan * 0.5 * H / 2)
        alb = alb[:, x0:x0 + W]
        wetm = wet[:, x0:x0 + W]
        pool = np.zeros((H, W), np.float32)
        conemask = np.zeros((H, W), np.float32)
        for i, lx in enumerate(LAMPS):
            if lv[i] <= 0:
                continue
            X = lx + pan * 0.7
            pool += K.soft_spot(H, W, X, -0.2, 0.55, 0.9, 1.3) * lv[i]
            conemask += D.cone(H, W, (X, -1.15), 90, 15, 2.6, 0.3) * lv[i]
        amb = 0.045 * (1 - 0.4 * K.smooth(ex))
        steel = np.array([0.36, 0.40, 0.46], np.float32)
        light = (amb + 0.55 * pool)[..., None]
        bg = (alb[..., None] * steel * light + (wetm * pool * 0.3)[..., None] * acc) * bgI

        # volumetric cones + mist
        mist = D.plane(H, W, t, 1.4, (0.02, -0.03), 9, 1.0, (pan * 0.8, 0))
        bg += (conemask * (0.10 + 0.35 * mist))[..., None] * acc * 0.8 * bgI
        bg += (D.shaped(mist, 0.3, 1.0) * 0.035 * bgI)[..., None] * np.array([0.5, 0.55, 0.65], np.float32)
        # distant rain (behind title)
        rI = p["PARTICLE_INTENSITY"]
        rl = 0.12 + 1.6 * conemask[..., None]
        if rI > 0:
            bg += E.rain(H, W, t, n=int(500 * rI), angle=6, speed=2.4, length=0.05, seed=5,
                         color=(0.55, 0.6, 0.7), intensity=0.35) * rl

        # title ---------------------------------------------------------------
        sp = c.title()
        sh = c.shaded(WET_STEEL)
        ue = K.ease_out(u, 3)
        streaks = c.cache.get("streaks")
        if streaks is None:
            streaks = c.cache["streaks"] = K.fft_noise(256, 1.7, 77)
        sn = K.sample(streaks, sp.h, sp.w, 2.0 * sp.h / H * 2, 0.0, -t * 0.12, 0.0, (0.1, 3.0))
        runs = np.clip((sn - 0.68) * 5, 0, 1) * sp.mask * np.clip(sp.dist / (0.04 * sp.cap_px), 0, 1)
        lit = 0.18 + 1.1 * lamps
        rgb, a = sh.shade(light=(0.05, -0.9, 0.45), rim_dir=(0, -1), rim_gain=0.25 + 1.2 * lamps,
                          base=K.col(p["TEXT_COLOR"]), light_gain=lit,
                          env_shift=0.05 * math.sin(t * 0.4))
        rgb = rgb + (runs * (0.08 + 0.6 * lamps))[..., None] * acc
        cam = c.cam(zoom=1.0 + 0.02 * truck, pan=(pan * H / 2, 0))
        L = c.layer()
        rise = 70 * k * (1 - ue)
        op = K.smooth(u * 2.5) * (1 - K.smooth(K.prog(t, off_t + c.exit_dur * 0.6, c.exit_dur * 0.4)))
        c.place(L, cam, rgb, a, sp, 1.0, off=(0, rise, 0), opacity=op)
        img = comp(drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.5, (0, 10), 18, k), L)
        img = img + K.blur(np.maximum(L.rgb - 0.8, 0), 6 * k) * 0.6 * p["GLOW_STRENGTH"]

        # flooded floor with rippled reflection ----------------------------------
        hx, hy = c.hero()
        hrow = int(H / 2 + hy + sp.ink_h * 1.15 * cam.zoom)
        hrow = int(np.clip(hrow, H * 0.55, H * 0.92))
        xs, ys = K.pixgrid(H, W)
        rip = D.plane(H, W, t, 6.0, (0.0, 0.12), 15, 1.0, (pan, 0), beta=1.6, evolve=0.4)
        my = np.where(ys > hrow, 2 * hrow - ys + (rip - 0.5) * 8 * k, ys).astype(np.float32)
        mx = (xs + (rip - 0.5) * 10 * k).astype(np.float32)
        refl = cv2.remap(img, mx, np.clip(my, 0, H - 1), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        refl = K.blur(refl, 2.5 * k)
        floor = (ys > hrow).astype(np.float32)
        fade = np.clip(1 - (ys - hrow) / (H * 0.35), 0, 1) * floor
        puddle = 0.55 + 0.45 * D.shaped(D.plane(H, W, 0, 2.0, (0, 0), 23, 1.0, (pan * 1.5, 0)), 0.3, 0.8)
        img = img * (1 - floor[..., None]) + (refl * (0.45 * fade * puddle)[..., None]
                                              + (pool * 0.05 * floor)[..., None] * steel) * floor[..., None]
        img += (np.exp(-((ys - hrow) / (3 * k)) ** 2) * 0.08 * (0.3 + lamps))[..., None] * acc * bgI

        # splash rings on the floor
        if rI > 0 and lamps > 0:
            spl = np.zeros((H, W, 3), np.float32)
            r = np.random.default_rng(3)
            n = int(30 * rI)
            px = r.uniform(0, W, n)
            py = r.uniform(hrow + 6 * k, H, n)
            ph = r.random(n)
            per = 0.45
            for i in range(n):
                q = ((t / per + ph[i]) % 1.0)
                rad = (3 + 26 * q) * k * (0.5 + (py[i] - hrow) / (H - hrow + 1))
                I = (1 - q) ** 2 * 0.22 * lamps
                cv2.ellipse(spl, (int(px[i] * 4), int(py[i] * 4)), (int(rad * 4), int(rad * 4 * 0.25)), 0, 0, 360,
                            tuple(float(v) for v in acc * I), 1, cv2.LINE_AA, shift=2)
            img += spl

        # foreground rain (in front of title)
        if rI > 0:
            img += E.rain(H, W, t, n=int(260 * rI), angle=8, speed=3.2, length=0.09, seed=8,
                          color=(0.7, 0.75, 0.85), intensity=0.45, zoom=1.0) * (0.2 + 2.0 * conemask[..., None])
            near = E.rain(H, W, t, n=int(40 * rI), angle=10, speed=4.0, length=0.25, seed=12,
                          color=(0.7, 0.75, 0.85), intensity=0.5, zoom=1.0)
            img += K.blur(near, 3 * k) * (0.2 + 0.8 * lamps)

        img = apply_shake(c, img, 0.0025, 0.15, 22)
        img = subtitle(c, img, cam, imp + 0.7, off_t, (0.70, 0.74, 0.80), y_rel=0.82)
        return c.finish(img, vignette=0.5, grain=0.03, bloom=(0.8, 0.5),
                        grade=dict(shadows=(-0.003, 0.0, 0.006), sat=0.8, contrast=1.08))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"], "Floodlight Color")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        truck = e_inout(prog(0, g.frames))
        lamp = []
        for i, (dly, off) in enumerate(((-6, 2), (0, 1), (5, 0))):
            on = f"{I} + {dly}"
            cut = f"{ctl('ExitStart')} + {off}*{ctl('ExitDuration')}*0.18"
            lamp.append(f"({step(on)}*(1 - 0.6*(1 - {step(on + ' + 5')})*abs(sin(time*{2.1 + i * 0.4:.1f})))"
                        f"*(1 - {step(cut)}))")
        lamps = f"(({lamp[0]} + {lamp[1]} + {lamp[2]})/3)"

        g.at(0, 0)
        wall = F.gradient_bg(g, "SteelWall", [(0, "#0b0d10", 1), (1, "#06070a", 1)])
        corr = F.noise(g, "Corrugation", "#000000", "#2a3038", detail=2, scale=20, seethe_rate=0.0, contrast=2.0)
        corrx = F.xf(g, "CorrugationStretch", corr, center=f"Point(0.5 + 0.04*{truck}, 0.5)")
        corrx.set(Aspect=40.0)
        wall = F.merge(g, "CorrugationMerge", wall, corrx, mode="Screen", blend=f"0.5*{BG}")
        seams = None
        for i, x in enumerate((0.12, 0.31, 0.5, 0.69, 0.88)):
            m = F.rect(g, f"PanelSeam{i}", (x, 0.5), 0.003, 1.0, 0.001)
            if seams is not None:
                m.conn("EffectMask", seams, "Mask")
            seams = m
        sc = F.solid(g, "SeamColor", (0, 0, 0))
        F.masked(sc, seams)
        wall = F.merge(g, "Seams", wall, sc, blend=0.7)
        wet = D.f_fog(g, "WetStreaks", wall, "#000000", "#5a6474", 8, "1", (0.0, -0.002), blend=f"0.35*{BG}",
                      detail=3, contrast=2.4, aspect=0.08)
        g.at(0, 2)
        bg = wet
        for i, x in enumerate((0.18, 0.5, 0.82)):
            pool = F.light_spot(g, f"LampPool{i}", bg, None, (x, 0.62), 0.28, 0.75, 0.6, accent=True, gain=0.55,
                                blend=f"{BG}*{lamp[i]}")
            cone = F.closed_poly_mask(g, f"LampCone{i}Shape", [(x - 0.01, 1.02), (x + 0.01, 1.02), (x + 0.09, 0.1),
                                                                (x - 0.09, 0.1)], soft=0.04)
            ccol = F.accent_solid(g, f"LampCone{i}Color", 0.35)
            F.masked(ccol, cone)
            bg = F.merge(g, f"LampCone{i}", pool, ccol, mode="Screen", blend=f"{BG}*{lamp[i]}")
        bg = D.f_fog(g, "Mist", bg, "#000000", "#232933", 2.5, "1", (0.0008, -0.001), blend=f"0.4*{BG}")
        bg = F.xf(g, "WallParallax", bg, center=f"Point(0.5 + 0.02*(0.5 - {truck}), 0.5)", edges=1)

        def rain(name, base, n, speed, length, alpha):
            em = g.add("pEmitter", f"{name}Emitter")
            em.expr("Number", f"{n}*{ctl('ParticleIntensity')}", n)
            em.set(Lifespan=30, LifespanVariance=6, Velocity=speed, VelocityVariance=speed * 0.2, Angle=-84,
                   AngleVariance=2, Region=F.FuID("CubeRgn"))
            em.setk("ParticleStyle.ColorControls", 1)
            for ch, v in (("Red", 0.72), ("Green", 0.78), ("Blue", 0.88)):
                em.setk(f"ParticleStyle.{ch}", v)
            em.setk("ParticleStyle.Size", 0.12)
            em.setk("CubeRgn.Width", 2.6)
            em.setk("CubeRgn.Height", 0.05)
            em.setk("CubeRgn.Depth", 1.0)
            em.setk("Transform3DOp.Translate.Y", 0.65)
            rd = g.add("pRender", f"{name}Render")
            rd.conn("Input", em)
            F.frame_inputs(rd, g)
            st = F.dirblur(g, f"{name}Streak", rd, length, angle=-84)
            return F.merge(g, name, base, st, mode="Screen",
                           blend=f"min({ctl('ParticleIntensity')}, 1)*{alpha}*(0.3 + 0.7*{lamps})")

        g.at(0, 4)
        bg = rain("RainFar", bg, 260, 0.05, 0.02, 0.6)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Russo One", "Regular", 0.17, 1.06,
                             color=p["TEXT_COLOR"])
        refl = F.fill_material(g, "SteelReflect", title,
                               [(0, "#0c0e11", 1), (0.38, "#323840", 1), (0.47, "#cfd8e4", 1), (0.53, "#5b636e", 1),
                                (1, "#15181c", 1)])
        face = F.merge(g, "WetSteelFace", title, refl, mode="Multiply", blend=0.9)
        runs = F.noise(g, "WaterRuns", "#000000", "#ffffff", detail=3, scale=14, seethe_rate=0.01, contrast=3.0,
                       brightness=-0.35, center="Point(0.5, 0.5 + time*0.004)")
        runsx = F.xf(g, "WaterRunsStretch", runs)
        runsx.set(Aspect=0.1)
        rm = F.bitmap_mask(g, "WaterRunsMatte", title)
        F.masked(runsx, rm)
        face = F.merge(g, "WaterRunsMerge", face, runsx, mode="Screen",
                       blend=f"{ctl('GlowStrength')}*(0.15 + 0.6*{lamps})")
        g.at(0, 6)
        rim = F.edge_light(g, "TopSpecular", title, 0.0, -0.003, accent=True, gain=1.4, blur_px=1.0)
        face = F.merge(g, "TopSpecMerge", face, rim, mode="Screen", blend=f"min(0.2 + 1.0*{lamps}, 1)")
        lit = F.cc(g, "FloodlightExposure", face, gain=f"0.22 + 0.95*{lamps}")
        placed = F.title_placement(g, "TitleCrane", lit, center_extra_y=f"-0.06*(1 - {e_out(u, 3)})")
        tglow = F.softglow(g, "SpecGlow", placed, 8, gain=f"0.6*{ctl('GlowStrength')}", threshold=0.7)
        scene = F.merge(g, "TitleOverYard", bg, tglow, blend=f"min({u}*2.5, 1)*(1 - {clamp01(f'({ex} - 0.6)*2.5')})")
        g.at(0, 8)
        # flooded-floor reflection (vertical flip about the floor line under the title)
        rf = F.xf(g, "FloorReflection", tglow,
                  center=f"Point(0.5, 0.5 + 2*({ctl('TextPosY')} - 0.17) - 1)")
        rf.set(FlipVert=1)
        rfb = F.dirblur(g, "FloorRipple", rf, 0.012, angle=90)
        fm = F.rect(g, "FloorArea", (0.5, 0.0), 1.2, 0.0, 0.03)
        fm.expr("Height", f"2*({ctl('TextPosY')} - 0.17)", 0.7)
        F.masked(rfb, fm)
        scene = F.merge(g, "FloorReflectionMerge", scene, rfb, mode="Screen",
                        blend=f"0.4*min({u}*2.5, 1)*(1 - {ex})")
        scene = rain("RainNear", scene, 90, 0.08, 0.05, 0.8)
        g.at(0, 10)
        scene = D.f_sub(g, p, "Teko", "SemiBold", (0.70, 0.74, 0.80), -0.13, f"{I} + 16", f"{ctl('ExitStart')}",
                        scene=scene)
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.02, shake_frames=3, shake_amp=0.002)
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T32()
