"""T01 - Obsidian Impact (prototype / reference implementation)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow
from ..fusion import ctl, prog, e_out, e_in, decay, step, window, clamp01
from ..typo import Material, place_extruded

OBSIDIAN = Material(base=(0.03, 0.03, 0.035), spec=(1.0, 0.86, 0.72), spec_power=70, spec_gain=0.7, diffuse=0.55,
                    ambient=0.05, metal=0.4, env_sky=(0.55, 0.47, 0.4), env_horizon=(0.01, 0.01, 0.012),
                    env_ground=(0.05, 0.04, 0.035), env_sharp=14, bevel=0.06, texture="obsidian",
                    tex_amount=0.06, bump=0.025, rim=(1.0, 0.72, 0.45), seed=11)


class T01(Design):
    ID = "T01"
    NAME = "Obsidian Impact"
    SLUG = "Obsidian_Impact"
    CATEGORY = "A - Dark Mass Elevation"
    CONCEPT = "Monumental black-glass lettering emerges from total darkness and is carved out by a hard backlight."
    ENTRANCE = "Deep forward travel from far depth while the title is still unlit (silhouette emergence)."
    REVEAL = "At the impact frame a sharp warm backlight ignites the letter edges; restrained dust burst and shards."
    CAMERA = "Slow continuous push-in, short decaying impact shake."
    MATERIAL = "Obsidian black glass with conchoidal bump, dark-steel bevel, warm rim light; 2.5D extrusion stack."
    EXIT = "Edge light drains away, then the title sinks back into darkness."
    TECHNIQUES = ["depth push", "backlight rim", "dust burst", "shards", "light sweep", "2.5D extrusion"]
    DEFAULTS = dict(MAIN_TITLE="OBSIDIAN", SUBTITLE="THE RECKONING BEGINS", FONT_FAMILY="anton",
                    TEXT_COLOR="#141418", ACCENT_COLOR="#FFB070", ANIMATION_START=12, ANIMATION_DURATION=66,
                    IMPACT_FRAME=84, HOLD_DURATION=60, EXIT_START=150, EXIT_DURATION=36, LETTER_SPACING=0.07)
    SOUND = [(0, "atmos", "Low drone / room tone bed"), (12, "riser", "Sub riser under the push (frames 12-84)"),
             (78, "whoosh", "Reverse whoosh into impact"), (84, "impact", "Heavy low impact + sub-bass drop"),
             (85, "debris", "Fine stone debris scatter"), (96, "shimmer", "Light sweep metallic shimmer"),
             (150, "tail", "Atmospheric tail / reverb decay")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u_rev = c.reveal_u()
        hit = c.hit(0.02, 0.45)
        after = 1.0 if t >= imp else 0.0

        # --- environment (own slower camera for parallax)
        bg = K.vgrad(H, W, (0.003, 0.003, 0.005), (0.010, 0.009, 0.009))
        nx, ny = K.grid(H, W)
        hy = 0.40 - 0.02 * K.ease_in_out(K.prog(t, 0, c.dur))  # horizon drifts as camera pushes
        hz = (np.exp(-((ny - hy) / 0.006) ** 2) * 0.35 + np.exp(-((ny - hy) / 0.10) ** 2) * 0.06)
        hz = hz * np.exp(-(nx / 1.5) ** 2)
        build = K.smooth(K.prog(t, 0, 2.0))
        bg += (hz * (0.35 + 0.65 * build))[..., None] * acc * bgI
        fogl = E.fog(H, W, t, (0.10, 0.085, 0.075), density=0.5, scale=1.3, speed=(0.010, 0.0), seed=3,
                     height=(hy - 0.05, 0.25))
        bg += fogl * bgI
        # backlight source behind the title: anticipation -> ignition -> drain
        anticip = K.smooth(K.prog(t, c.start, imp - c.start)) * (1 - after)
        back_lvl = (0.05 + 0.25 * anticip + after * (0.55 + 1.6 * hit)) * (1 - ex)
        hx, hyy = c.hero()
        bx, by = hx / (H / 2), hyy / (H / 2) - 0.05
        spot = K.soft_spot(H, W, bx, by, 1.05, 0.42, 2.0)
        bg += (spot * back_lvl * 0.35)[..., None] * acc * bgI

        # --- dust (mid + foreground, depth of field)
        P = c.cache.get("dust")
        if P is None:
            P = c.cache["dust"] = E.Particles(int(300 * p["PARTICLE_INTENSITY"]), seed=5, z=(0.35, 3.0))
        if P.n:
            x, y = P.drift(t, vel=(0.025, -0.008), turb=0.04, freq=0.4)
            dust = E.particle_layer(H, W, P, x, y, (1.0, 0.85, 0.7), 1.6, 0.35 * (0.4 + back_lvl), zoom=1 + 0.06 * t / c.dur,
                                    focus=1.0, dof=1.2, t=t, glow=1.0)
            bg += dust

        # --- title
        sp = c.title()
        sh = c.shaded(OBSIDIAN)
        ue = K.ease_out(u_rev, 4)
        zfar = 2.4 * H * (1 - ue)
        settle = -6 * k * K.pulse(t, imp, 0.02, 0.25)  # tiny weight dip at impact
        rim = (0.12 * ue + after * (1.1 + 2.6 * hit)) * (1 - K.smooth(ex * 1.6))
        lg = (0.25 + 0.75 * ue) * (1 - 0.85 * K.smooth(ex))
        sw = K.prog(t, imp + 0.45, 1.3)
        sweep = (-0.9 + 1.8 * K.ease_in_out(sw), 0.10, 0.35, 1.4 * (1 if 0 < sw < 1 else 0))
        rgb, a = sh.shade(light=(-0.35, -0.8, 0.5), rim_dir=(0.0, -1.0), rim_gain=rim, sweep=sweep,
                          base=K.col(p["TEXT_COLOR"]) * 0.25 + 0.02, light_gain=lg)
        cam = c.cam(zoom=1.0 + 0.07 * K.ease_in_out(K.prog(t, 0, c.dur)))
        L = c.layer()
        op = K.smooth(u_rev * 2.5) * (1 - K.ease_in(ex, 2))
        hx, hy2 = c.hero()
        depth = 0.16 * sp.cap_px * p["EXTRUSION_DEPTH"]
        side = (0.012, 0.011, 0.012)
        if depth > 0.5:
            place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, (hx, hy2 + settle, zfar), 1.0,
                           (0, 0, p["TEXT_ROTATION"]), depth, side, slices=10,
                           side_light=lambda q: 0.4 + 0.6 * q, opacity=op)
        else:
            c.place(L, cam, rgb, a, sp, 1.0, off=(0, settle, zfar), opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.6, (0, 18), 30, k)
        img = comp(bg, L)

        # rim bloom only from the lit edges
        img = img + K.blur(np.maximum(L.rgb - 0.25, 0), 10 * k) * 0.8 * p["GLOW_STRENGTH"] * (0.3 + hit)

        # --- impact: dust burst + shards (independent of the title layer)
        if t >= imp and p["PARTICLE_INTENSITY"] > 0:
            dt = t - imp
            B = c.cache.get("burst")
            if B is None:
                r = np.random.default_rng(9)
                n = int(160 * p["PARTICLE_INTENSITY"])
                ang = r.uniform(0, 2 * np.pi, n)
                spd = r.uniform(0.2, 1.4, n) ** 1.5
                ox = r.uniform(-0.5, 0.5, n) * sp.ink_w / (H / 2)
                oy = r.uniform(-0.3, 0.3, n) * sp.ink_h / (H / 2)
                B = c.cache["burst"] = (n, ang, spd, ox, oy, r.random(n))
            n, ang, spd, ox, oy, rr = B
            dist = spd * (1 - np.exp(-dt * 2.2)) / 2.2 * 1.2
            gx = bx + ox + np.cos(ang) * dist
            gy = by + 0.05 + oy + np.sin(ang) * dist * 0.6 + 0.05 * dt * dt
            fade = np.exp(-dt / (0.5 + rr)) * (1 - ex)
            Pb = E.Particles(n, 1)
            Pb.z = np.full(n, 1.0, np.float32) * (0.8 + 0.4 * rr).astype(np.float32)
            vx, vy = np.cos(ang) * spd * 0.02, np.sin(ang) * spd * 0.012
            img += E.particle_layer(H, W, Pb, gx, gy, acc * 1.2 + 0.2, 1.4, 1.3 * fade, zoom=1.0, glow=1.2,
                                    streak=(vx * np.exp(-dt * 2), vy * np.exp(-dt * 2)))
        # flash
        img += (K.soft_spot(H, W, bx, by + 0.05, 1.4, 0.7, 1.5) * 0.14 * hit * bgI)[..., None] * acc

        # --- subtitle
        ss = c.sub()
        if ss is not None:
            su = K.prog(t, imp + 0.35, 0.9)
            so = K.smooth(su) * (1 - K.smooth(K.prog(t, c.exit_start - 0.2, 0.6)))
            if so > 0:
                Ls = c.layer()
                srgb = np.empty((ss.h, ss.w, 3), np.float32)
                srgb[...] = 0.62 + acc * 0.18
                c.place(Ls, cam, srgb, ss.mask, ss, 1.0 + 0.05 * (1 - K.ease_out(su)),
                        off=(0, sp.ink_h * 0.78, 0), opacity=so)
                img = comp(img, Ls)

        # --- camera shake + finish
        sx, sy = c.shake(0.006, 0.35, 16)
        if abs(sx) + abs(sy) > 0.05:
            M = np.float32([[1.01, 0, -0.005 * W + sx], [0, 1.01, -0.005 * H + sy]])
            img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        return c.finish(img, vignette=0.55, grain=0.035, bloom=(0.7, 0.55),
                        grade=dict(shadows=(-0.004, 0.0, 0.006), highlights=(0.02, 0.008, -0.01), contrast=1.05))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        acc = p["ACCENT_COLOR"]
        g.controls(timing=dict(AnimStart=p["ANIMATION_START"], AnimDuration=p["ANIMATION_DURATION"],
                               ImpactFrame=p["IMPACT_FRAME"], HoldDuration=p["HOLD_DURATION"],
                               ExitStart=p["EXIT_START"], ExitDuration=p["EXIT_DURATION"]))
        F.accent_holder(g, acc)
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")

        # environment ---------------------------------------------------
        g.at(0, 0)
        bg = F.gradient_bg(g, "EnvGradient", [(0, "#020203", 1), (0.6, "#060507", 1), (1, "#0b0909", 1)],
                           start=(0.5, 1.0), end=(0.5, 0.0))
        bg = F.light_spot(g, "HorizonLine", bg, None, (0.5, 0.3), 1.7, 0.006, 0.02, accent=True,
                          blend=f"{BG}*(0.35 + 0.65*{prog(0, 48)})")
        bg = F.light_spot(g, "HorizonGlow", bg, None, (0.5, 0.3), 1.8, 0.22, 0.35, accent=True, gain=0.4,
                          blend=f"0.25*{BG}")
        fogn = F.noise(g, "GroundFog", "#000000", "#1a1612", detail=5, scale=2.5, seethe_rate=0.03, contrast=1.4,
                       center=f"Point(0.5 + time*0.0007, 0.5)")
        fogm = F.ellipse(g, "GroundFogBand", (0.5, 0.3), 2.0, 0.45, 0.4)
        F.masked(fogn, fogm)
        bg = F.merge(g, "FogMerge", bg, fogn, mode="Screen", blend=f"0.6*{BG}")
        g.at(0, 2)
        back = (f"{BG}*(1-{ex})*(0.05 + 0.25*{prog(ctl('AnimStart'), ctl('ImpactFrame') + ' - ' + ctl('AnimStart'))}"
                f"*(1-{step(ctl('ImpactFrame'))}) + {step(ctl('ImpactFrame'))}*(0.5 + 0.5*{decay(ctl('ImpactFrame'), 14)}))")
        bg = F.light_spot(g, "Backlight", bg, None, (0.5, 0.53), 1.0, 0.45, 0.5, accent=True, gain=0.6,
                          blend=f"min({back}, 1)")
        bg = F.particles(g, "Dust", bg, number=6, lifespan=190, velocity=0.002, angle=20, angle_var=180, size=0.35,
                         color=(0.9, 0.78, 0.62), region="CubeRgn", region_size=(2.2, 1.4, 1.0), center_y=0.0,
                         turbulence=0.15, glow=3)
        bg = F.xf(g, "EnvCamera", bg, size=f"1 + 0.03*{prog(0, g.frames)}", edges=1)

        # title -----------------------------------------------------------
        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Anton", "Regular", 0.17, 1.07,
                             color=p["TEXT_COLOR"])
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        refl = F.fill_material(g, "ObsidianReflect", title,
                               [(0, "#000000", 1), (0.46, "#0c0b0c", 1), (0.5, "#4a4038", 1), (0.54, "#0d0c0d", 1),
                                (1, "#000000", 1)], start=(0.5, 0.62), end=(0.5, 0.38))
        face = F.merge(g, "FaceReflect", title, refl, mode="Screen", blend=0.8)
        g.at(0, 6)
        rim_gain = (f"min({ctl('GlowStrength')}*(1-min({ex}*1.6, 1))*(0.12*{u} + {step(ctl('ImpactFrame'))}"
                    f"*(0.75 + 0.25*{decay(ctl('ImpactFrame'), 16)})), 1)")
        rim = F.edge_light(g, "RimTop", title, 0.0, -0.004, accent=True, gain=1.5, blur_px=1.2)
        face = F.merge(g, "RimMerge", face, rim, mode="Screen", blend=rim_gain)
        g.at(0, 8)
        ext = F.extrusion_stack(g, "Extrude", clear, title, layers=8, dx=0.0, dy=-0.0012, color=(0.012, 0.011, 0.012))
        solid_title = F.merge(g, "TitleSolid", ext, face)
        swept = F.light_sweep(g, "Sweep", solid_title, title, f"{ctl('ImpactFrame')} + 10", 30, angle=20, width=0.05,
                              peak=0.7, accent=False, color=(1, 0.9, 0.78))
        g.at(0, 10)
        lit = F.cc(g, "Emergence", swept, gain=f"(0.25 + 0.75*{e_out(u, 4)})*(1 - 0.85*{ex})")
        placed = F.title_placement(g, "TitlePush", lit, size_expr=f"0.62 + 0.38*{e_out(u, 4)}",
                                   center_extra_y=f"-0.004*{decay(ctl('ImpactFrame'), 6)}")
        glow = F.softglow(g, "RimGlow", placed, 10, gain=f"{ctl('GlowStrength')}*(0.4 + 1.2*{decay(ctl('ImpactFrame'), 12)})",
                          threshold=0.25)
        scene = F.merge(g, "TitleOverEnv", bg, glow,
                        blend=f"min({u}*2.5, 1)*(1 - pow({ex}, 2))")

        # impact ----------------------------------------------------------
        g.at(0, 12)
        burst_n = f"220*{ctl('ParticleIntensity')}*{window(ctl('ImpactFrame'), ctl('ImpactFrame') + ' + 2', 1, 1)}"
        scene = F.particles(g, "DustBurst", scene, number=220, lifespan=40, velocity=0.03, angle=90, angle_var=180,
                            size=0.5, color=acc, region="SphereRgn", region_size=(0.12,), center_y=0.0,
                            turbulence=0.2, glow=6, number_expr=burst_n)
        scene = F.impact_flash(g, "ImpactFlash", scene, color=acc, peak=0.18, frames=6)

        # subtitle ----------------------------------------------------------
        g.at(0, 14)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.032, 1.6,
                                    color=(0.72, 0.68, 0.64), y_off=-0.13)
        scene = F.merge(g, "SubtitleMerge", scene, subp,
                        blend=window(f"{ctl('ImpactFrame')} + 8", f"{ctl('ExitStart')} - 5", 20, 14))

        # camera + finish ----------------------------------------------------
        g.at(0, 16)
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.06, shake_frames=8, shake_amp=0.005)
        out = F.finish(g, scene, vignette=0.55, letterbox=True, grain=True)
        g.output = out


DESIGN = T01()
