"""T10 - Shockwave Dominance."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, subtitle
from ..fusion import FuID, ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_extruded

CHROME = Material(base=(0.78, 0.8, 0.84), spec=(1.0, 1.0, 1.0), spec_power=90, spec_gain=0.9, diffuse=0.35,
                  ambient=0.05, metal=0.85, env_sky=(0.85, 0.86, 0.9), env_horizon=(0.03, 0.03, 0.035),
                  env_ground=(0.28, 0.08, 0.08), env_sharp=16, bevel=0.06, bevel_round=True, texture="none",
                  tex_amount=0.0, rim=(1.0, 0.25, 0.25), seed=101)


class T10(Design):
    ID = "T10"
    NAME = "Shockwave Dominance"
    SLUG = "Shockwave_Dominance"
    CATEGORY = "B - Fire, Explosions and Impact"
    CONCEPT = "A title that lands like a strike: everything around it is pushed outward by a radial shockwave."
    ENTRANCE = ("A short inhale (the air darkens and haze is pulled inward), then the title slams down from in front "
                "of the camera, accelerating into its mark with zoom blur.")
    REVEAL = ("Radial impact: a crisp crimson ring, a wide pressure-haze ring and a refraction band travel outward "
              "independently of the title; light rays stream from behind the letters.")
    CAMERA = "Hard zoom kick and short violent shake at the strike, then a slow dominant push-in."
    MATERIAL = "Polished dark chrome with crimson rim and floor reflection tint, hard drop shadow on the haze."
    EXIT = "Implosion: a ring collapses back inward while the title compresses into a point of light."
    TECHNIQUES = ["accelerating slam with zoom blur", "inhale anticipation", "independent shockwave ring(s)",
                  "refraction displacement band", "volumetric rays through letter gaps", "implosion exit"]
    TRUE_3D = False
    DURATION_FRAMES = 156
    DEFAULTS = dict(MAIN_TITLE="DOMINANCE", SUBTITLE="ONE STRIKE  ONE RULER", FONT_FAMILY="teko",
                    TEXT_COLOR="#C9CED6", ACCENT_COLOR="#E0262E", ANIMATION_START=4, ANIMATION_DURATION=22,
                    IMPACT_FRAME=26, HOLD_DURATION=76, EXIT_START=124, EXIT_DURATION=26, LETTER_SPACING=0.09,
                    TITLE_WIDTH=0.56)
    SOUND = [(0, "atmos", "Low pressure drone"), (4, "rwhoosh", "Air inhale before the strike"),
             (18, "whoosh", "Title slam whoosh"), (26, "impact", "Massive impact"), (26, "sub", "Sub-bass boom"),
             (27, "whoosh", "Shockwave air blast outward"), (30, "debris", "Fine debris rattle"),
             (60, "swell", "Ray swell under the hold"), (124, "rwhoosh", "Implosion suck"),
             (146, "impact", "Final soft hit as it collapses"), (148, "tail", "Tail")]
    FUSION_NOTES = [
        "The shockwave is fully independent of the title: ShockRingPrimary / ShockRingHaze (expanding EllipseMask "
        "rings) and ShockRefraction (Displace driven by RefractRingShape) all key off Impact Frame and scale with "
        "Impact Intensity. Move their Center inputs together to relocate the impact point.",
    ]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        PI = p["PARTICLE_INTENSITY"]
        II = p["IMPACT_INTENSITY"]
        GL = p["GLOW_STRENGTH"]
        imp = c.impact
        ex = c.exit_u()
        dt = t - imp
        after = dt >= 0
        hit = c.hit(0.01, 0.2)
        sp = c.title()
        hx, hy = c.hero()
        cx, cy = hx / (H / 2), hy / (H / 2)
        inhale = K.smooth(K.prog(t, c.start, imp - c.start)) * (0 if after else 1)

        # --- environment: dark pressure haze, red ambience after the strike
        h2, w2 = H // 2, W // 2
        nx, ny = K.grid(h2, w2)
        bg = K.vgrad(h2, w2, (0.012, 0.012, 0.014), (0.006, 0.005, 0.006))
        hz = K.fbm_field(h2, w2, t, 1.3, (0.0, 0.0), 103, beta=2.4, warp=0.1)
        rr = np.sqrt(((nx - cx) / 1.15) ** 2 + (ny - cy) ** 2)
        # haze is pulled inward during the inhale, pushed outward after the strike (radial scale of the field)
        push = (-0.25 * inhale) if not after else 0.35 * (1 - math.exp(-dt * 3))
        hz = cv2.remap(hz, *self._radial_maps(h2, w2, cx, cy, push))
        ambient = 0.4 * (1 - inhale * 0.7) + (0.6 + 1.2 * hit) * after * (1 - 0.6 * K.smooth(ex))
        bg += (np.clip(hz - 0.4, 0, 1) * 0.10 * ambient)[..., None] * np.array([0.7, 0.7, 0.75], np.float32)
        bg += (np.exp(-rr / 0.9) * 0.07 * ambient * after)[..., None] * acc
        bg = cv2.resize(bg * bgI, (W, H), interpolation=cv2.INTER_LINEAR)

        # --- shockwave (independent of the title): crisp ring + pressure-haze ring + refraction band
        if after and II > 0 and dt < 1.1:
            u1 = K.ease_out(dt / 0.75, 2)
            u2 = K.ease_out(max(dt - 0.08, 0) / 1.0, 2)
            r1, r2 = 0.05 + 2.3 * u1, 0.05 + 1.9 * u2
            f1 = max(0.0, 1 - dt / 0.75) ** 1.3 * min(II, 2)
            f2 = max(0.0, 1 - dt / 1.1) ** 1.5 * min(II, 2)
            ring = E.ring(h2, w2, cx, cy, r1, 0.008 + 0.01 * u1, 1.15) * f1
            haze = E.ring(h2, w2, cx, cy, r2, 0.09 + 0.08 * u2, 1.15) * f2
            ringc = (acc * 0.7 + 0.45)
            bg = bg + cv2.resize(ring * 0.9, (W, H))[..., None] * ringc * bgI
            bg = bg + cv2.resize(haze * 0.12, (W, H))[..., None] * (acc * 0.6 + 0.2) * bgI
            bg = E.shockwave_displace(bg, cx, cy, r1 * 0.97, 0.05, 0.03 * f1)
            bg = E.shockwave_displace(bg, cx, cy, r2, 0.12, 0.012 * f2)

        # --- title: accelerating slam from in front of the camera; implosion on exit
        sh = c.shaded(CHROME)
        us = c.reveal_u()
        es = K.ease_in(us, 3)
        z = -0.72 * c.cam().f * (1 - es)                         # starts close to the lens
        kick = 1.0 + 0.035 * K.pulse(t, imp, 0.01, 0.1) * p["SHAKE_AMOUNT"]
        push = 0.05 * K.ease_in_out(K.prog(t, imp, c.dur - imp))
        cam = c.cam(zoom=kick + push)
        ie = K.ease_in(ex, 3)
        scale = 1.0 - 0.97 * ie
        rim = (0.35 + 0.4 * after + 2.5 * hit) * GL
        rgb, a = sh.shade(light=(-0.4, -0.7, 0.6), rim_dir=(0.0, 1.0), rim_gain=rim, base=K.col(p["TEXT_COLOR"]),
                          light_gain=0.85 + 0.6 * hit + 0.6 * ie, env_shift=0.08 * math.sin(t * 0.6) - 0.05)
        L = c.layer()
        op = K.smooth(us * 3) * (1 - K.smooth((ex - 0.85) / 0.15))
        if op > 0:
            depth = 0.16 * sp.cap_px * p["EXTRUSION_DEPTH"] * (1 - ie)
            if depth > 0.5 and us >= 0.7:
                place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, (hx, hy, z), scale,
                               (0, 0, p["TEXT_ROTATION"]), depth, (0.03, 0.02, 0.022), slices=8,
                               side_light=lambda q: 0.35 + 0.9 * q, opacity=op)
            else:
                c.place(L, cam, rgb, a, sp, scale, off=(0, 0, z), opacity=op)
            zb = (0.3 * (1 - es) * (us < 1) * (us > 0) + 0.25 * K.smooth(ex) * (ex < 1)) * p["MOTION_BLUR_AMOUNT"]
            if zb > 0.005:
                z4 = K.zoom_blur(np.dstack([L.rgb, L.a]), W / 2 + hx, H / 2 + hy, zb, steps=14)
                L.rgb, L.a = np.ascontiguousarray(z4[..., :3]), np.ascontiguousarray(z4[..., 3])
        # --- debris dust kicked outward with the wave
        if after and PI > 0 and dt < 2.0:
            D = c.cache.get("dust")
            if D is None:
                r = np.random.default_rng(10)
                n = int(140 * PI)
                D = c.cache["dust"] = (n, r.uniform(0, 2 * np.pi, n), r.uniform(0.3, 1.0, n), r.random(n))
            n, ang, spd, rr2 = D
            dist = 0.5 * sp.ink_w / (H / 2) * (0.6 + 0.4 * rr2) + spd * 2.0 * K.ease_out(min(dt / 1.2, 1), 2)
            gx = cx + np.cos(ang) * dist * 1.15
            gy = cy + np.sin(ang) * dist
            Pd = E.Particles(n, 1)
            Pd.z = (0.7 + 0.6 * rr2).astype(np.float32)
            vx, vy = np.cos(ang) * 0.02 * (1 - dt / 2), np.sin(ang) * 0.02 * (1 - dt / 2)
            bg += E.particle_layer(H, W, Pd, gx, gy, acc * 0.4 + 0.45, 1.0, 0.7 * (1 - dt / 2.0), glow=0.5,
                                    streak=(vx, vy))

        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.7 * (1 if after else 0.3), (0, 16), 20, k)
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.7, 0), 6 * k) * 0.5 * GL * (0.4 + hit)

        # --- rays streaming from behind the letters (occluded by the title alpha)
        ray_lvl = ((0.25 + 1.4 * hit + 0.12 * math.sin(t * 1.3)) * after * (1 - K.smooth(ex * 1.4))) * bgI * GL
        if ray_lvl > 0.01:
            q = 4
            core = K.soft_spot(H // q, W // q, cx, cy, 0.5 * sp.ink_w / (H / 2), 0.35 * sp.ink_h / (H / 2) + 0.05, 1.5)
            occ = cv2.resize(L.a, (W // q, H // q), interpolation=cv2.INTER_AREA)
            src = (core * (1 - occ))[..., None] * (acc * 0.8 + 0.25)
            rays = K.god_rays(np.ascontiguousarray(src), (W / 2 + hx), (H / 2 + hy), length=0.6, decay=0.94,
                              steps=20, scale=2)
            img = img + cv2.resize(rays, (W, H)) * ray_lvl * 1.4

        # --- implosion ring + final point of light
        if ex > 0:
            ri = 2.4 * (1 - K.ease_in(ex, 2)) + 0.01
            f = K.smooth(ex * 3) * (1 - K.smooth((ex - 0.9) / 0.1))
            ring = E.ring(h2, w2, cx, cy, ri, 0.01 + 0.03 * (1 - ex), 1.15) * f
            img = img + cv2.resize(ring * 0.6, (W, H))[..., None] * (acc * 0.7 + 0.3) * bgI
            pt = K.pulse(t, c.exit_start + c.exit_dur * 0.88, 0.03, 0.12)
            if pt > 0.01:
                sp4 = cv2.resize(K.soft_spot(H // 4, W // 4, cx, cy, 0.05, None, 1.0), (W, H))
                img = img + (sp4 * pt * 1.6)[..., None] * (acc * 0.4 + 0.6)

        img = img * (1 - 0.35 * inhale)          # the inhale darkens the frame
        img = img + (0.12 * hit * bgI) * (acc * 0.4 + 0.6)[None, None, :]
        img = subtitle(c, img, cam, imp + 0.7, c.exit_start - 0.15, (0.75, 0.76, 0.8), y_rel=0.82, tracking=0.6)
        sx, sy = c.shake(0.012, 0.22, 24)
        if abs(sx) + abs(sy) > 0.05:
            M = np.float32([[1.02, 0, -0.01 * W + sx], [0, 1.02, -0.01 * H + sy]])
            img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        img = img * (1 - K.smooth((ex - 0.94) / 0.06))
        return c.finish(img, vignette=0.6, grain=0.035, bloom=(0.8, 0.45), ca=0.0015 * (1 + 4 * hit))

    def _radial_maps(self, h, w, cx, cy, push):
        """remap() maps scaling a field radially about (cx, cy) (normalised coords); push>0 expands outward."""
        xs, ys = K.pixgrid(h, w)
        pcx, pcy = w / 2 + cx * h / 2, h / 2 + cy * h / 2
        s = 1.0 / (1.0 + push)
        return (pcx + (xs - pcx) * s).astype(np.float32), (pcy + (ys - pcy) * s).astype(np.float32), \
            cv2.INTER_LINEAR

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
        ED = ctl("ExitDuration")
        us = prog(S, f"{I} - {S}")
        ex = prog(ES, ctl("ExitDuration"))
        inhale = f"{us}*(1 - {step(I)})"
        ie = e_in(ex, 3)

        # environment: pressure haze pulled in, then blown out --------------------------------
        g.at(0, 0)
        bg = F.gradient_bg(g, "PressureDark", [(0, "#030304", 1), (1, "#010101", 1)])
        haze = F.noise(g, "PressureHaze", "#000000", "#1c1c20", detail=5, scale=2.2, seethe_rate=0.02, contrast=1.5)
        hz = F.xf(g, "HazePushPull", haze,
                  size=f"1 - 0.25*{inhale} + 0.35*{step(I)}*(1 - {decay(I, 8)})", edges=1)
        bg = F.merge(g, "HazeMerge", bg, hz, mode="Screen",
                     blend=f"min({BG}*(0.4*(1 - 0.7*{inhale}) + {step(I)}*(0.6 + 1.2*{II}*{decay(I, 5)})*(1 - 0.6*{ex})), 1)")
        bg = F.light_spot(g, "CrimsonAmbience", bg, None, (0.5, 0.5), 1.4, 1.0, 0.7, accent=True, gain=0.35,
                          blend=f"min({BG}*{step(I)}*(0.5 + {II}*{decay(I, 8)})*(1 - 0.6*{ex}), 1)")

        # shockwave: independent rings + refraction ------------------------------------------------
        g.at(0, 2)
        bg = F.shock_ring(g, "ShockRingPrimary", bg, center=(0.5, 0.5), max_size=2.3, frames=18, border=0.006,
                          soft=0.006, peak=0.9)
        bg = F.shock_ring(g, "ShockRingHaze", bg, center=(0.5, 0.5), max_size=1.9, frames=26, border=0.06,
                          soft=0.08, peak=0.25, offset=2)
        rmap = F.solid(g, "RefractRingColor", (1, 1, 1))
        rsh = F.ellipse(g, "RefractRingShape", (0.5, 0.5), 0.1, 0.1, 0.05)
        rsh.set(BorderWidth=0.03)
        rsh.expr("Width", f"0.02 + 2.3*{e_out(prog(I, 18), 2)}", 0.1)
        rsh.expr("Height", f"(0.02 + 2.3*{e_out(prog(I, 18), 2)})*1.7778", 0.1)
        F.masked(rmap, rsh)
        disp = g.add("Displace", "ShockRefraction")
        disp.conn("Input", bg).conn("Foreground", rmap)
        disp.set(Type=0, Center=[0.5, 0.5])
        disp.expr("RefractionStrength", f"0.035*{II}*{step(I)}*(1 - {prog(I, 18)})", 0)
        bg = disp

        # title ---------------------------------------------------------------------------------
        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Teko", "SemiBold", 0.24, 1.09, color=p["TEXT_COLOR"])
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        chrome = F.fill_material(g, "DarkChrome", title,
                                 [(0, "#ffffff", 1), (0.46, "#b8bec8", 1), (0.5, "#2a2c30", 1), (0.6, "#5a5e66", 1),
                                  (1, "#8a3a3e", 1)])
        face = F.merge(g, "ChromeFace", title, chrome, mode="Multiply", blend=1.0)
        rim = F.edge_light(g, "CrimsonRim", title, 0.0, 0.003, accent=True, gain=1.6, blur_px=1.2)
        face = F.merge(g, "CrimsonRimMerge", face, rim, mode="Screen",
                       blend=f"min({GL}*(0.35 + 0.4*{step(I)} + 2.5*{II}*{decay(I, 6)}), 1)")
        ext = F.extrusion_stack(g, "ChromeDepth", clear, title, layers=7, dx=0.0, dy=-0.0013,
                                color=(0.03, 0.02, 0.022))
        body = F.merge(g, "TitleBody", ext, face)
        g.at(0, 6)
        zb = F.dirblur(g, "SlamZoomBlur", body,
                       f"{ctl('MotionBlurAmount')}*(0.3*(1 - {e_in(us, 3)})*(1 - {step(I)}) + 0.25*{ex})",
                       angle=0.0, btype=3)
        placed = F.title_placement(g, "Slam", zb, size_expr=f"(3.4 - 2.4*{e_in(us, 3)})*(1 - 0.97*{ie})")
        shadow_src = F.solid(g, "ShadowColor", (0, 0, 0))
        shm = F.bitmap_mask(g, "ShadowMatte", placed)
        F.masked(shadow_src, shm)
        shadow = F.xf(g, "ShadowOffset", F.blur(g, "ShadowSoft", shadow_src, 16), center=(0.5, 0.485))
        scene = F.merge(g, "DropShadow", bg, shadow, blend=f"0.7*{ctl('ShadowStrength')}*{step(I)}")
        # rays: bright core behind the title, title alpha cut out, radially smeared
        g.at(0, 8)
        core = F.accent_solid(g, "RayCoreColor", 1.2)
        csh = F.ellipse(g, "RayCoreShape", (0.5, 0.5), 0.5, 0.25, 0.5)
        tcut = F.bitmap_mask(g, "RayTitleCut", placed, paint="Subtract", prev=csh)
        F.masked(core, tcut)
        rays = F.dirblur(g, "RayStreaks", core, 0.35, angle=0.0, btype=3)
        scene = F.merge(g, "Rays", scene, rays, mode="Screen",
                        blend=f"min({BG}*{GL}*{step(I)}*(0.25 + 1.4*{II}*{decay(I, 6)} + 0.12*sin(time*0.054))*(1 - min({ex}*1.4, 1)), 1)")
        scene = F.merge(g, "TitleOverWave", scene, placed,
                        blend=f"min({us}*3, 1)*(1 - {clamp01(f'({ex} - 0.85)/0.15')})")

        # implosion ring + final point ------------------------------------------------------------------
        g.at(0, 10)
        ic = F.accent_solid(g, "ImplosionColor", 1.3)
        ish = F.ellipse(g, "ImplosionRingShape", (0.5, 0.5), 2.4, 2.4, 0.01)
        ish.set(BorderWidth=0.008)
        ish.expr("Width", f"0.01 + 2.4*(1 - {e_in(ex, 2)})", 2.4)
        ish.expr("Height", f"(0.01 + 2.4*(1 - {e_in(ex, 2)}))*1.7778", 4.2)
        F.masked(ic, ish)
        scene = F.merge(g, "ImplosionRing", scene, ic, mode="Screen",
                        blend=f"{clamp01(f'{ex}*3')}*(1 - {clamp01(f'({ex} - 0.9)/0.1')})")
        pt = F.light_spot(g, "CollapsePoint", scene, (1.0, 0.85, 0.85), (0.5, 0.5), 0.05, 0.09, 0.08,
                          blend=f"{decay(f'{ES} + 0.88*{ED}', 3)}")
        scene = pt
        scene = F.particles(g, "WaveDust", scene, number=140, lifespan=30, velocity=0.05, angle=90, angle_var=180,
                            size=0.25, color=(0.75, 0.6, 0.6), region="SphereRgn", region_size=(0.15,),
                            center_y=0.0, turbulence=0.05, glow=2,
                            number_expr=f"140*{ctl('ParticleIntensity')}*{window(I, I + ' + 2', 1, 1)}")
        dark = F.solid(g, "InhaleDark", (0, 0, 0))
        scene = F.merge(g, "InhaleDarken", scene, dark, blend=f"0.35*{inhale}")
        scene = F.impact_flash(g, "StrikeFlash", scene, color=(1.0, 0.85, 0.85), peak=0.12, frames=3)
        g.at(0, 12)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 2.0,
                                    color=(0.75, 0.76, 0.8), y_off=-0.15)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 17", f"{ES} - 4", 14, 8))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.05, shake_frames=5, shake_amp=0.012,
                             push_start=I, push_dur=f"({g.frames} - {I})")
        kick = F.xf(g, "ZoomKick", scene, size=f"1 + 0.035*{ctl('ShakeAmount')}*{decay(I, 3)}", edges=1)
        g.output = F.finish(g, kick, vignette=0.6)


DESIGN = T10()
