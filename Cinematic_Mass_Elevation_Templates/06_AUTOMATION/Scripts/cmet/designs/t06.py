"""T06 - Inferno Reveal."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, apply_shake, subtitle
from ..fusion import FuID, ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_extruded

CHAR = Material(base=(0.42, 0.33, 0.27), spec=(1.0, 0.7, 0.45), spec_power=26, spec_gain=0.35, diffuse=0.85,
                ambient=0.08, metal=0.3, env_sky=(0.06, 0.04, 0.03), env_horizon=(0.12, 0.05, 0.02),
                env_ground=(0.9, 0.38, 0.1), env_sharp=7, bevel=0.06, texture="grain", tex_amount=0.3,
                bump=0.02, rim=(1.0, 0.5, 0.16), seed=66)


def fire_rgb(acc, temp):
    """Fire colour ramp: deep red -> accent orange -> yellow-white core."""
    deep = np.array([0.35, 0.03, 0.0], np.float32)
    yel = np.array([1.0, 0.82, 0.45], np.float32)
    t = temp[..., None]
    return deep * np.clip(t * 3, 0, 1) + acc * np.clip(t * 1.6 - 0.2, 0, 1.2) + yel * np.clip(t - 0.55, 0, 1) * 1.6


def soft_smoke(h, w, t, color, density, scale, rise, seed, light):
    """Billowing smoke with low domain warp (the shared smoke() warps strongly into marble contours)."""
    n = K.fbm_field(h, w, t, scale, (0.004, rise), seed, beta=2.5, evolve=0.05, warp=0.12)
    n2 = K.fbm_field(h, w, t, scale * 2.1, (-0.003, rise * 1.4), seed + 3, beta=2.2, evolve=0.07, warp=0.08)
    m = np.clip((0.7 * n + 0.3 * n2 - 0.42) * 2.0, 0, 1) ** 1.4
    lx, ly, lr, lc = light
    lit = 0.4 + 1.6 * K.soft_spot(h, w, lx, ly, lr)[..., None] * K.col(lc)[None, None, :]
    return m[..., None] * K.col(color)[None, None, :] * density * lit


class T06(Design):
    ID = "T06"
    NAME = "Inferno Reveal"
    SLUG = "Inferno_Reveal"
    CATEGORY = "B - Elemental Fury"
    CONCEPT = "The title emerges out of controlled firelight and smoke, seen through rising heat."
    ENTRANCE = ("Behind a curtain of smoke and strong heat shimmer the title slowly comes forward; the smoke thins and the "
                "distortion settles as the fire rises behind it.")
    REVEAL = "A restrained flare: flames lick up, a burst of sparks rises and the orange rim light peaks, then settles."
    CAMERA = "Locked-off with a gentle forward creep; small heat-jolt at the flare."
    MATERIAL = "Charred bronze lettering lit from below by the fire, orange rim from behind, warm halo for separation."
    EXIT = "The title burns away from the bottom up behind a glowing ember edge, releasing embers that rise with the heat."
    TECHNIQUES = ["procedural fire bed", "heat-shimmer displacement", "smoke curtain", "rising sparks with DOF",
                  "flare burst", "bottom-up burn-away with ember release"]
    TRUE_3D = False
    DURATION_FRAMES = 192
    DEFAULTS = dict(MAIN_TITLE="INFERNO", SUBTITLE="EVERYTHING BURNS", FONT_FAMILY="staatliches",
                    TEXT_COLOR="#7A6050", ACCENT_COLOR="#FF5A1F", ANIMATION_START=6, ANIMATION_DURATION=66,
                    IMPACT_FRAME=72, HOLD_DURATION=80, EXIT_START=154, EXIT_DURATION=34, LETTER_SPACING=0.08,
                    TITLE_WIDTH=0.6, TEXT_POSITION_Y=0.54)
    SOUND = [(0, "fire", "Fire bed roar"), (0, "atmos", "Low rumble"), (6, "swell", "Heat swell as smoke parts"),
             (40, "crackle", "Wood/ember crackle"), (68, "rwhoosh", "Air sucked into the flare"),
             (72, "whoosh", "Flame flare whoosh"), (72, "impact", "Soft heavy hit"), (74, "debris", "Spark scatter"),
             (154, "fire", "Burn-away crackle"), (176, "tail", "Smouldering tail")]

    # ------------------------------------------------------------ preview --
    def _fire(self, c, reach, tcx):
        H, W, t = c.H, c.W, c.t
        h4, w4 = H // 4, W // 4
        nx, ny = K.grid(h4, w4)
        a = K.fft_noise(256, 2.3, 61)
        b = K.fft_noise(256, 2.0, 62)
        wob = K.sample(K.fft_noise(256, 2.4, 63), h4, w4, 1.2, 0.0, t * 0.12)
        n1 = K.sample(a, h4, w4, 1.7, 0.03 * math.sin(t * 0.4), t * 0.38, stretch=(1.0, 2.3))
        n2 = K.sample(b, h4, w4, 3.4, 0.05 * math.sin(t * 0.7 + 1), t * 0.8, stretch=(1.0, 2.0))
        n = 0.65 * n1 + 0.35 * n2
        top = 1.0 - reach
        g = np.clip((ny - top + (wob - 0.5) * 0.2) / max(reach, 0.05), 0, 1.2)
        shape = 0.55 + 0.45 * np.exp(-((nx - tcx) / 1.4) ** 2)
        flame = np.clip((n - 0.5) * 2.6 + g * 1.3 - 0.45, 0, 1) * np.clip(g * 3, 0, 1) * shape
        flame = cv2.GaussianBlur(flame, (0, 0), 0.8)
        return flame

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        PI = p["PARTICLE_INTENSITY"]
        GL = p["GLOW_STRENGTH"]
        imp = c.impact
        ex = c.exit_u()
        u = c.reveal_u()
        ue = K.ease_in_out(u)
        hit = c.hit(0.05, 0.6)
        after = t >= imp
        sp = c.title()
        hx, hy = c.hero()
        tcx, tcy = hx / (H / 2), hy / (H / 2)

        # --- fire bed + smoke (behind the title)
        reach = (0.32 + 0.18 * K.smooth(K.prog(t, 0, c.start + c.reveal)) + 0.35 * hit) * (1 - 0.3 * K.smooth(ex))
        flame = self._fire(c, reach, tcx)
        fire = fire_rgb(acc, flame) * bgI
        h4, w4 = flame.shape
        h2, w2 = H // 2, W // 2
        nx2, ny2 = K.grid(h2, w2)
        bg = K.vgrad(h2, w2, (0.006, 0.004, 0.004), (0.05, 0.016, 0.006))
        glowpool = K.soft_spot(h2, w2, tcx, 0.9, 1.7, 0.8, 1.3) * (0.6 + 0.3 * ue + 0.8 * hit)
        bg += (glowpool * 0.12 * bgI)[..., None] * acc
        sm = soft_smoke(h2, w2, t, (0.08, 0.068, 0.06), density=0.7, scale=1.0, rise=0.05, seed=14,
                     light=(tcx, 0.9, 1.2, acc * 1.6))
        bg += sm * bgI * (0.6 + 0.4 * (1 - ex))
        bg += cv2.resize(fire, (w2, h2))
        # heat shimmer on the environment (stronger low in frame)
        q = K.fbm_field(h4, w4, t, 4.0, (0.0, 0.9), 71, beta=1.6, evolve=0.2)
        shim = (q - 0.5)
        wgt = np.clip((K.grid(h4, w4)[1] + 0.4) / 1.2, 0, 1)
        dxy = cv2.resize(shim * wgt, (w2, h2))
        amp_bg = 4.0
        xs, ys = K.pixgrid(h2, w2)
        bg = cv2.remap(bg, xs + dxy * amp_bg, ys + dxy * amp_bg * 1.6, cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_REFLECT)
        bg = cv2.resize(bg, (W, H), interpolation=cv2.INTER_LINEAR)

        # --- title
        sh = c.shaded(CHAR)
        ck = c.cache.get("burnfield")
        if ck is None:
            nz = K.sample(K.fft_noise(256, 1.6, 67), sp.h, sp.w, 3.0 * sp.h / H)
            vb = np.clip(0.5 - sh.v, 0, 1.2)            # 0 at the bottom of the ink, 1 at the top
            ck = c.cache["burnfield"] = (0.45 * nz + 0.55 * vb).astype(np.float32)
        thr = ck
        burn = ex * 1.25 - 0.12
        emis = None
        a_mul = 1.0
        if ex > 0:
            d = thr - burn
            a_mul = np.clip(d / 0.035, 0, 1)
            band = np.exp(-(d / 0.03) ** 2) * sp.mask
            emis = (band * 2.4)[..., None] * (acc * 0.8 + np.array([0.25, 0.15, 0.05], np.float32)) * GL
        rim = (0.4 + 0.5 * ue + 1.8 * hit) * (1 - 0.4 * ex)
        lg = (0.35 + 0.55 * ue + 0.35 * hit)
        rgb, a = sh.shade(light=(0.1, 0.65, 0.65), rim_dir=(0.0, 1.0), rim_gain=rim * GL, base=K.col(p["TEXT_COLOR"]),
                          light_gain=lg, emissive=emis, env_shift=0.05 * math.sin(t * 3.1))
        a = a * a_mul
        cam = c.cam(zoom=1.0 + 0.035 * K.ease_in_out(K.prog(t, 0, c.dur)))
        L = c.layer()
        scale = 0.93 + 0.07 * ue
        op = K.smooth(u * 1.6)
        depth = 0.1 * sp.cap_px * p["EXTRUSION_DEPTH"]
        if depth > 0.5:
            place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, (hx, hy, 0), scale,
                           (0, 0, p["TEXT_ROTATION"]), depth, (0.05, 0.025, 0.014), slices=6,
                           side_light=lambda qq: 0.4 + 0.8 * qq, opacity=op)
        else:
            c.place(L, cam, rgb, a, sp, scale, opacity=op)
        # heat shimmer through the title: strong while it emerges, faint in the hold
        amp_t = (16 * (1 - ue) + 1.6) * k * p["MOTION_BLUR_AMOUNT"]
        dfull = cv2.resize(shim, (W, H))
        X, Y = K.pixgrid(H, W)
        mx, my = X + dfull * amp_t, Y + dfull * amp_t * 1.8
        L.rgb = cv2.remap(L.rgb, mx, my, cv2.INTER_LINEAR)
        L.a = cv2.remap(L.a, mx, my, cv2.INTER_LINEAR)
        if u < 1:
            sb = 6 * k * (1 - ue)
            L.rgb, L.a = K.blur(L.rgb, sb), K.blur(L.a, sb)
        # warm halo separating the dark letters from the fire
        halo = K.blur(L.a, 26 * k)
        bg = bg + (halo * (0.12 + 0.12 * ue + 0.3 * hit) * GL)[..., None] * acc
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.55, 0), 8 * k) * 0.6 * GL

        # --- sparks drifting upward (two depths, DOF) + flare burst + released embers
        if PI > 0:
            P = c.cache.get("sparks")
            if P is None:
                P = c.cache["sparks"] = E.Particles(int(90 * PI), seed=6, z=(0.6, 2.2))
            x, y = P.drift(t, vel=(0.03, -0.22), turb=0.06, freq=1.1)
            vy = -0.012 * (0.5 + P.r)
            img += E.particle_layer(H, W, P, x, y, acc * 1.2 + np.array([0.25, 0.1, 0.0]), 1.3,
                                    0.9 * (0.6 + 0.4 * ue + hit), focus=1.0, dof=1.1, flicker=0.6, t=t,
                                    streak=(np.full(P.n, 0.002, np.float32), np.full(P.n, vy, np.float32)), glow=0.8)
            if after:
                dt = t - imp
                B = c.cache.get("flare")
                if B is None:
                    r = np.random.default_rng(3)
                    n = int(110 * PI)
                    B = c.cache["flare"] = (n, r.uniform(-0.6, 0.6, n) * sp.ink_w / (H / 2), r.uniform(-0.15, 0.05, n),
                                            r.uniform(0.25, 0.9, n), r.uniform(-0.25, 0.25, n), r.random(n))
                n, ox, oy, vu, vx, rr = B
                if dt < 3.0:
                    gx = tcx + ox + vx * dt
                    gy = tcy + sp.ink_h / H + oy - vu * dt * (1 - 0.25 * dt)
                    fade = np.exp(-dt / (0.5 + 0.8 * rr)) * np.clip(dt * 12, 0, 1)
                    Pb = E.Particles(n, 1)
                    Pb.z = (0.8 + 0.4 * rr).astype(np.float32)
                    img += E.particle_layer(H, W, Pb, gx, gy, acc * 1.3 + np.array([0.35, 0.15, 0.0]), 1.0,
                                            1.3 * fade * p["IMPACT_INTENSITY"], glow=1.0,
                                            streak=(vx * 0.02, -vu * 0.02 * np.ones(n)))
            if ex > 0:
                R = c.cache.get("release")
                if R is None:
                    r = np.random.default_rng(8)
                    ys_, xs_ = np.nonzero(sp.mask > 0.6)
                    idx = r.choice(len(xs_), size=min(int(260 * PI), len(xs_)), replace=False)
                    R = c.cache["release"] = (xs_[idx], ys_[idx], thr[ys_[idx], xs_[idx]], r.random(len(idx)))
                rx, ry, rt, rr = R
                t_rel = c.exit_start + (rt + 0.12) / 1.25 * c.exit_dur
                age = t - t_rel
                live = age > 0
                if live.any():
                    zf = cam.zoom
                    gx = (hx + (rx - sp.anchor[0]) * scale * zf) / (H / 2) + 0.05 * np.sin(age * 3 + rr * 6) * age
                    gy = (hy + (ry - sp.anchor[1]) * scale * zf) / (H / 2) - age * (0.18 + 0.2 * rr)
                    fade = live * np.exp(-np.maximum(age, 0) / (0.4 + 0.6 * rr))
                    Pr = E.Particles(len(rx), 1)
                    Pr.z = np.ones(len(rx), np.float32)
                    img += E.particle_layer(H, W, Pr, gx, gy, acc * 1.2 + np.array([0.3, 0.12, 0.0]), 0.9,
                                            1.1 * fade, glow=0.8)

        # --- smoke curtain in front of the title during the emergence
        front = (0.85 * (1 - K.smooth(K.prog(t, c.start, c.reveal * 0.9))) + 0.05 + 0.35 * K.smooth(ex)) * bgI
        fs = soft_smoke(h2, w2, t * 1.2, (0.11, 0.09, 0.08), density=front, scale=0.9, rise=0.06, seed=19,
                     light=(tcx, 0.8, 1.4, acc * 1.4))
        img = img + cv2.resize(fs, (W, H))
        img = subtitle(c, img, cam, imp + 0.6, c.exit_start, (0.85, 0.62, 0.45), y_rel=0.92, tracking=0.5)
        img = apply_shake(c, img, 0.0025, 0.3, 10)
        img = img * (1 - 0.9 * K.smooth((ex - 0.8) / 0.2))
        return c.finish(img, vignette=0.5, grain=0.035, bloom=(0.8, 0.45))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S = ctl("AnimStart")
        ES = ctl("ExitStart")
        BG = ctl("BackgroundIntensity")
        GL = ctl("GlowStrength")
        II = ctl("ImpactIntensity")
        AD = ctl("AnimDuration")
        ED = ctl("ExitDuration")
        u = prog(S, ctl("AnimDuration"))
        ue = e_inout(u)
        ex = prog(ES, ctl("ExitDuration"))
        flare = f"{II}*{decay(I, 14)}"

        # fire bed + smoke ----------------------------------------------------------
        g.at(0, 0)
        bg = F.gradient_bg(g, "EmberDark", [(0, "#020101", 1), (0.6, "#0a0402", 1), (1, "#200803", 1)])
        smoke = F.noise(g, "SmokeBack", "#000000", "#2c2420", detail=6, scale=2.2, seethe_rate=0.05, contrast=1.7,
                        center="Point(0.5 + time*0.0004, 0.5 + time*0.0025)")
        bg = F.merge(g, "SmokeBackMerge", bg, smoke, mode="Screen", blend=f"0.7*{BG}")
        g.at(0, 2)
        fire1 = F.noise(g, "FlameNoise", "#000000", "#ff6a20", detail=7, scale=3.5, seethe_rate=0.25, contrast=2.6,
                        center="Point(0.5, 0.5 + time*0.009)")
        fire1.set(Angle=0.0)
        fsh = F.ellipse(g, "FireBedShape", (0.5, 0.0), 1.8, 0.6, 0.35)
        fsh.expr("Height", f"(0.55 + 0.25*{prog(0, f'{S} + {AD}')} + 0.5*{flare})"
                           f"*(1 - 0.3*{ex})", 0.6)
        F.masked(fire1, fsh)
        bg = F.merge(g, "FireBed", bg, fire1, mode="Screen", blend=f"min({BG}, 1)")
        fire2 = F.noise(g, "FlameCore", "#000000", "#ffd27a", detail=5, scale=6, seethe_rate=0.4, contrast=3.0,
                        center="Point(0.5, 0.5 + time*0.016)")
        csh = F.ellipse(g, "FlameCoreShape", (0.5, 0.0), 1.4, 0.35, 0.3)
        csh.expr("Height", f"(0.3 + 0.35*{flare})*(1 - 0.3*{ex})", 0.35)
        F.masked(fire2, csh)
        bg = F.merge(g, "FlameCoreMerge", bg, fire2, mode="Screen", blend=f"0.6*min({BG}, 1)")
        bg = F.light_spot(g, "FireGlow", bg, None, (0.5, 0.1), 1.8, 0.8, 0.6, accent=True, gain=0.5,
                          blend=f"min({BG}*(0.4 + 0.3*{ue} + 0.6*{flare}), 1)")

        # title --------------------------------------------------------------------
        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Staatliches", "Regular", 0.2, 1.08,
                             color=p["TEXT_COLOR"])
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        bronze = F.fill_material(g, "CharredBronze", title,
                                 [(0, "#5a4a40", 1), (0.5, "#8a7466", 1), (1, "#e0b090", 1)])
        face = F.merge(g, "BronzeFace", title, bronze, mode="Multiply", blend=1.0)
        rim = F.edge_light(g, "FireRim", title, 0.0, 0.003, accent=True, gain=1.6, blur_px=1.6)
        face = F.merge(g, "FireRimMerge", face, rim, mode="Screen",
                       blend=f"min({GL}*(0.4 + 0.5*{ue} + 1.8*{flare})*(1 - 0.4*{ex}), 1)")
        ext = F.extrusion_stack(g, "CharDepth", clear, title, layers=5, dx=0.0, dy=-0.001, color=(0.05, 0.025, 0.014))
        body = F.merge(g, "TitleBody", ext, face)
        g.at(0, 6)
        # bottom-up burn-away: (vertical ramp + noise) thresholded by ExitStart progress
        ramp = F.gradient_bg(g, "BurnRamp", [(0, "#ffffff", 1), (1, "#000000", 1)], start=(0.5, 0.58), end=(0.5, 0.42))
        bn = F.noise(g, "BurnNoise", "#000000", "#8c8c8c", detail=5, scale=9, seethe_rate=0.0, contrast=1.5)
        burnmap = F.merge(g, "BurnMap", ramp, bn, mode="Multiply", blend=0.45)
        keep = F.bitmap_mask(g, "BurnKeep", burnmap, channel="Luminance")
        keep.expr("Low", f"{ex}*1.25 - 0.12", 0)
        keep.expr("High", f"{ex}*1.25 - 0.08", 0.04)
        burnt = F.merge(g, "BurnAway", clear, body)
        F.masked(burnt, keep)
        e1 = F.bitmap_mask(g, "BurnEdgeA", burnmap, channel="Luminance")
        e1.expr("Low", f"{ex}*1.25 - 0.16", 0)
        e1.expr("High", f"{ex}*1.25 - 0.12", 0.04)
        e2 = F.bitmap_mask(g, "BurnEdgeB", burnmap, channel="Luminance", paint="Subtract", prev=e1)
        e2.expr("Low", f"{ex}*1.25 - 0.08", 0)
        e2.expr("High", f"{ex}*1.25 - 0.04", 0.04)
        e3 = F.bitmap_mask(g, "BurnEdgeInTitle", title, paint="Multiply", prev=e2)
        edge = F.accent_solid(g, "BurnEdgeColor", 1.8)
        F.masked(edge, e3)
        burnt = F.merge(g, "BurnEdge", burnt, edge, mode="Screen", blend=f"{step(ES)}*{GL}")
        g.at(0, 8)
        lit = F.cc(g, "Firelight", burnt, gain=f"0.35 + 0.55*{ue} + 0.35*{flare}")
        heatblur = F.blur(g, "HeatSoften", lit, f"6*(1 - {ue})")
        placed = F.title_placement(g, "TitleCreep", heatblur, size_expr=f"0.93 + 0.07*{ue}")
        halo_src = F.accent_solid(g, "HaloColor", 1.0)
        hm = F.bitmap_mask(g, "HaloMatte", placed)
        F.masked(halo_src, hm)
        halo = F.blur(g, "HaloSoft", halo_src, 40)
        scene = F.merge(g, "Halo", bg, halo, mode="Screen",
                        blend=f"min({GL}*(0.15 + 0.15*{ue} + 0.35*{flare}), 1)")
        scene = F.merge(g, "TitleOverFire", scene, placed, blend=f"min({u}*1.6, 1)")

        # heat shimmer over everything (Displace driven by rising noise) --------------------------
        g.at(0, 10)
        dmap = F.noise(g, "HeatShimmerMap", "#000000", "#ffffff", detail=3, scale=12, seethe_rate=0.3,
                       contrast=1.0, center="Point(0.5, 0.5 + time*0.02)")
        disp = g.add("Displace", "HeatShimmer")
        disp.conn("Input", scene).conn("Foreground", dmap)
        disp.set(Type=1)
        disp.expr("XRefraction", f"{ctl('MotionBlurAmount')}*(0.002 + 0.012*(1 - {ue}))", 0.004)
        disp.expr("YRefraction", f"{ctl('MotionBlurAmount')}*(0.004 + 0.02*(1 - {ue}))", 0.008)
        scene = disp
        g.at(0, 12)
        scene = F.particles(g, "RisingSparks", scene, number=40, lifespan=70, velocity=0.03, angle=88, angle_var=12,
                            size=0.22, color=(1.0, 0.6, 0.25), region="CubeRgn", region_size=(2.2, 0.1, 1.0),
                            center_y=-0.55, turbulence=0.35, glow=4)
        burst = f"140*{ctl('ParticleIntensity')}*{II}*{window(I, I + ' + 3', 1, 1)}"
        scene = F.particles(g, "FlareSparks", scene, number=140, lifespan=50, velocity=0.04, angle=90, angle_var=35,
                            size=0.3, color=(1.0, 0.7, 0.3), region="CubeRgn", region_size=(0.9, 0.05, 0.3),
                            center_y=-0.12, turbulence=0.3, glow=5, number_expr=burst)
        rel = f"90*{ctl('ParticleIntensity')}*{window(ES, f'{ES} + {ED}', 1, 1)}"
        scene = F.particles(g, "BurnEmbers", scene, number=90, lifespan=40, velocity=0.02, angle=90, angle_var=40,
                            size=0.25, color=(1.0, 0.55, 0.2), region="CubeRgn", region_size=(0.9, 0.15, 0.1),
                            center_y=0.0, turbulence=0.4, glow=4, number_expr=rel)
        fsmoke = F.noise(g, "SmokeCurtain", "#000000", "#3a302a", detail=6, scale=2.0, seethe_rate=0.06,
                         contrast=1.6, center="Point(0.5 - time*0.0005, 0.5 + time*0.003)")
        scene = F.merge(g, "SmokeCurtainMerge", scene, fsmoke, mode="Screen",
                        blend=f"min({BG}*(0.85*(1 - {prog(S, f'0.9*{AD}')}) + 0.05 + 0.35*{ex}), 1)")
        g.at(0, 14)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.8,
                                    color=(0.85, 0.62, 0.45), y_off=-0.14)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 14", ES, 18, 10))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.035, shake_frames=8, shake_amp=0.0025,
                             push_start="0", push_dur=str(g.frames))
        black = F.solid(g, "FadeBlack", (0, 0, 0))
        scene = F.merge(g, "FinalFade", scene, black, blend=f"0.9*{clamp01(f'({ex} - 0.8)/0.2')}")
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T06()
