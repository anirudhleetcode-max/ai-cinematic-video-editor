"""T40 - Ultimate Mass Elevation (flagship)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, apply_shake, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_extruded

BRONZE = Material(base=(0.42, 0.28, 0.16), spec=(1.0, 0.82, 0.58), spec_power=55, spec_gain=0.9, diffuse=0.55,
                  ambient=0.06, metal=0.75, env_sky=(0.85, 0.66, 0.42), env_horizon=(0.06, 0.04, 0.03),
                  env_ground=(0.16, 0.10, 0.06), env_sharp=12, bevel=0.055, texture="brushed", tex_amount=0.10,
                  rim=(1.0, 0.78, 0.5), seed=40)


class T40(Design):
    ID = "T40"
    NAME = "Ultimate Mass Elevation"
    SLUG = "Ultimate_Mass_Elevation"
    CATEGORY = "H - Signature Hero Elevations"
    CONCEPT = ("Flagship: a distant light on a dark horizon grows into volumetric shafts that the title cuts "
               "through; a single controlled detonation of light crowns the hero, who then holds in burnished bronze.")
    ENTRANCE = ("Near-black opening with drifting haze and a far horizon light; slow dolly; the title rises from "
                "below the horizon as a backlit silhouette, its letters casting light shafts toward the camera.")
    REVEAL = ("Impact: the horizon light flares into an anamorphic streak, the bronze surface ignites (rim + key), "
              "a soft pressure ring and a restrained ember burst, short camera shake, then a premium light sweep.")
    CAMERA = "Continuous slow dolly-in with a slight rise; one brief decaying shake at impact; still during the hold."
    MATERIAL = "Burnished bronze (brushed metal, warm environment reflection, gold rim) with 2.5D perspective extrusion."
    EXIT = ("The light collapses: a horizontal light slit closes over the title like a shutter, leaving a final "
            "anamorphic line that shrinks to a point and fades out.")
    TECHNIQUES = ["horizon light source", "occluded volumetric shafts", "silhouette rise", "perspective extrusion",
                  "anamorphic flare", "pressure ring", "ember burst", "light sweep", "light-slit shutter exit"]
    DURATION_FRAMES = 240
    DEFAULTS = dict(MAIN_TITLE="MASS ELEVATION", SUBTITLE="ONE NAME. ONE LEGEND.", OPTIONAL_TAGLINE="IN CINEMAS",
                    FONT_FAMILY="cinzel", TEXT_COLOR="#B07A48", ACCENT_COLOR="#FFB25E", ANIMATION_START=40,
                    ANIMATION_DURATION=70, IMPACT_FRAME=114, HOLD_DURATION=82, EXIT_START=196, EXIT_DURATION=36,
                    LETTER_SPACING=0.08, TITLE_WIDTH=0.74, DURATION=240)
    SOUND = [(0, "atmos", "Deep dark bed, wide"), (0, "wind", "Distant high wind"),
             (36, "riser", "Long tension riser into impact (frames 36-114)"),
             (70, "heartbeat", "Sub heartbeat pulse as the title rises"),
             (104, "rwhoosh", "Reverse whoosh 10 frames before impact"),
             (114, "impact", "Main hit: heavy impact"), (114, "sub", "Sub-bass drop"),
             (115, "debris", "Ember debris scatter"), (128, "shimmer", "Light sweep shimmer"),
             (160, "swell", "Warm orchestral-style pad swell under the hold"),
             (196, "whoosh", "Shutter whoosh on exit"), (226, "tail", "Final low tail")]

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        imp = c.impact
        ex = c.exit_u()
        hit = c.hit(0.02, 0.5)
        after = 1.0 if t >= imp else 0.0
        u = c.reveal_u()
        ue = K.ease_out(u, 3)
        dolly = K.ease_in_out(K.prog(t, 0, c.dur))
        nx, ny = K.grid(H, W)

        hx, hy = c.hero()
        horizon = hy / (H / 2) + 0.075 - 0.02 * dolly  # just behind the letters' lower half
        src_x = hx / (H / 2)
        # --- light source envelope (grows, flares at impact, collapses at exit)
        grow = K.smooth(K.prog(t, 0.3, imp - 0.3))
        src = (0.08 + 0.55 * grow + after * (0.6 + 2.8 * hit)) * (1 - K.smooth(ex))
        # --- base environment
        bg = K.vgrad(H, W, (0.004, 0.004, 0.006), (0.010, 0.008, 0.007))
        haze = E.fog(H, W, t, (0.12, 0.09, 0.07), density=1.0, scale=1.2, speed=(0.008, -0.002), seed=40,
                     height=(horizon - 0.1, 0.45))
        sky_glow = K.soft_spot(H, W, src_x, horizon, 1.9, 0.35, 1.0)
        bg = bg + haze * (0.25 + 0.75 * sky_glow[..., None] * (0.3 + src)) * bgI
        line = np.exp(-((ny - horizon) / 0.004) ** 2) * np.exp(-((nx - src_x) / 1.4) ** 2)
        bg = bg + (line * (0.15 + 0.5 * src))[..., None] * acc * bgI
        core_spot = K.soft_spot(H, W, src_x, horizon, 0.06, 0.03, 1.0)
        bg = bg + (core_spot * src * 1.6)[..., None] * (acc * 0.6 + 0.4) * bgI

        # --- title (rises from below the horizon, pushes forward)
        sp = c.title()
        sh = c.shaded(BRONZE)
        rise = (1 - ue) * sp.ink_h * 1.6
        zfar = (1 - ue) * 0.8 * H
        cam = c.cam(zoom=1.0 + 0.10 * dolly, pan=(0, -12 * k * dolly))
        ignite = after * (0.55 + 0.45 * math.exp(-max(0, t - imp) / 1.5))
        pre = 0.12 * ue * (1 - after)
        sw = K.prog(t, imp + 0.6, 1.4)
        sweep = (-0.9 + 1.8 * K.ease_in_out(sw), 0.08, 0.5, 1.6 * (1 if 0 < sw < 1 else 0) * p["GLOW_STRENGTH"])
        rim = (0.35 * ue + after * (1.4 + 2.5 * hit)) * (1 - K.smooth(ex * 1.5))
        lg = (pre + ignite * (1 - 0.7 * K.smooth(ex))) + 0.02
        breathe = 1 + 0.04 * math.sin(t * 2.1) * after
        rgb, a = sh.shade(light=(-0.3, -0.75, 0.55), rim_gain=rim * breathe, rim_dir=(0.0, -1.0), sweep=sweep,
                          base=K.col(p["TEXT_COLOR"]), light_gain=lg, env_shift=0.1 * math.sin(t * 0.4))
        L = c.layer()
        depth = 0.14 * sp.cap_px * p["EXTRUSION_DEPTH"]
        pos = (hx, hy + rise, zfar)
        if depth > 0.5:
            place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, pos, 1.0, (4 * (1 - ue), 0, p["TEXT_ROTATION"]),
                           depth, (0.05, 0.03, 0.018), slices=12, side_light=lambda q: 0.25 + 0.75 * q ** 1.5,
                           opacity=K.smooth(u * 3))
        else:
            c.place(L, cam, rgb, a, sp, 1.0, rot=(4 * (1 - ue), 0, 0), off=(0, rise, zfar), opacity=K.smooth(u * 3))
        # clip the rising title at the horizon until it has cleared it (emerges from below)
        hz_px = H / 2 + horizon * H / 2 * cam.zoom
        clipm = np.clip((hz_px - K.pixgrid(H, W)[1]) / (6 * k) + 0.5, 0, 1) if u < 1 else None
        if clipm is not None and ue < 0.995:
            soft = max(0.0, 1 - ue * 1.25)
            m = clipm * soft + (1 - soft)
            L.a *= m
            L.rgb *= m[..., None]

        # --- volumetric shafts: light source occluded by the title
        if p["BACKGROUND_INTENSITY"] > 0:
            occl = (core_spot * 4 + K.soft_spot(H, W, src_x, horizon, 0.7, 0.12, 1.0) * 1.2) * src
            occl = occl * (1 - np.clip(L.a * 1.2, 0, 1))
            occl = occl * (0.6 + 0.8 * K.fbm_field(H, W, t, 3.0, (0.01, 0.0), 41, beta=2.2, evolve=0.04))
            sx_px = W / 2 + src_x * H / 2 * cam.zoom
            sy_px = H / 2 + horizon * H / 2 * cam.zoom
            rays = K.god_rays(occl[..., None] * acc[None, None, :], sx_px, sy_px, length=1.4, decay=0.965, steps=28)
            bg = bg + rays * 1.8 * bgI

        if after:
            fl = (1.4 * hit + 0.22 * ignite) * (1 - K.smooth(ex))
            flare = np.exp(-((ny - horizon) / 0.014) ** 2) * np.exp(-((nx - src_x) / 2.2) ** 2)
            bg = bg + (flare * fl)[..., None] * (acc * 0.7 + 0.3)  # behind the title: letters silhouette it
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.5, (0, 20), 34, k)
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.35, 0), 12 * k) * 0.7 * p["GLOW_STRENGTH"] * (0.4 + hit)

        # --- impact: anamorphic flare + pressure ring + embers
        if after:
            dt = t - imp
            rr = 0.1 + 1.5 * K.ease_out(K.prog(dt, 0, 1.1), 2)
            ringm = E.ring(H, W, hx / (H / 2), hy / (H / 2), rr, 0.05 + 0.1 * rr, aspect=1.6)
            img = img + (ringm * 0.18 * (1 - K.prog(dt, 0, 1.1)) * p["IMPACT_INTENSITY"])[..., None] * acc
            if dt < 1.2:
                img = E.shockwave_displace(img, hx / (H / 2), hy / (H / 2), rr, 0.06, 0.01 * (1 - dt / 1.2) *
                                           p["IMPACT_INTENSITY"])
        if p["PARTICLE_INTENSITY"] > 0:
            P = c.cache.get("emb")
            if P is None:
                P = c.cache["emb"] = E.Particles(int(220 * p["PARTICLE_INTENSITY"]), seed=40, spread=(2.0, 1.4),
                                                 z=(0.4, 3.0))
            if after:
                dt = t - imp
                x, y = P.drift(dt + 3, vel=(0.01, -0.07), turb=0.05, freq=0.8)
                burst = 1 + 3.0 * math.exp(-dt / 0.6)
                fade = (0.3 + 0.7 * math.exp(-dt / 2.5)) * (1 - K.smooth(ex))
                img = img + E.particle_layer(H, W, P, x, y, acc * 1.1 + 0.15, 1.6, 0.55 * fade * burst,
                                             zoom=cam.zoom, focus=1.0, dof=1.0, flicker=0.5, t=t, glow=1.5)
            else:
                x, y = P.drift(t, vel=(0.006, -0.01), turb=0.03, freq=0.4)
                img = img + E.particle_layer(H, W, P, x, y, (0.9, 0.8, 0.7), 1.2, 0.18 * (0.3 + src), zoom=cam.zoom,
                                             focus=1.0, dof=1.0, t=t, glow=0.8)

        img = subtitle(c, img, cam, imp + 0.7, c.exit_start - 0.4, 0.70 + acc * 0.25, y_rel=0.95, rel=0.27,
                       tracking=0.45)
        img = subtitle(c, img, cam, imp + 1.5, c.exit_start - 0.4, 0.5 + acc * 0.2, y_rel=-0.85,
                       key="OPTIONAL_TAGLINE", rel=0.16, tracking=0.9, grow=0.0)

        # --- exit: horizontal light slit shutter
        if ex > 0:
            e2 = K.ease_in_out(ex)
            half = (1 - e2) * 1.05  # half-height of the open slit (normalised)
            cy = hy / (H / 2)
            slit = np.clip((half - np.abs(ny - cy)) / 0.02, 0, 1)
            edge = np.exp(-((np.abs(ny - cy) - half) / 0.01) ** 2) * (1 - e2) * 0.7
            img = img * slit[..., None] + edge[..., None] * acc
            if ex > 0.75:
                q = K.prog(ex, 0.75, 0.25)
                ln = np.exp(-((ny - cy) / 0.004) ** 2) * np.exp(-((nx - src_x) / (1.8 * (1 - q) + 0.02)) ** 2)
                img = img + (ln * (1 - q) * 1.2)[..., None] * (acc * 0.6 + 0.4)

        img = apply_shake(c, img, 0.006, 0.3, 15)
        return c.finish(img, vignette=0.5, grain=0.03, bloom=(0.7, 0.5),
                        grade=dict(shadows=(-0.002, 0.0, 0.006), highlights=(0.02, 0.006, -0.012), contrast=1.06),
                        streak=(1.0, 0.35, 220, acc))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        BG = ctl("BackgroundIntensity")
        grow = prog(8, f"{I} - 8")
        src = f"((0.08 + 0.55*{grow})*(1 - {step(I)}) + {step(I)}*(0.75 + 0.6*{decay(I, 18)}))*(1 - {ex})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "EnvGradient", [(0, "#010102", 1), (0.6, "#050405", 1), (1, "#0a0807", 1)])
        haze = F.noise(g, "Haze", "#000000", "#2a1f17", detail=5, scale=2.0, seethe_rate=0.02, contrast=1.3,
                       center="Point(0.5 + time*0.0004, 0.5)")
        hm = F.ellipse(g, "HazeBand", (0.5, 0.42), 2.2, 0.7, 0.5)
        F.masked(haze, hm)
        bg = F.merge(g, "HazeMerge", bg, haze, mode="Screen", blend=f"{BG}*(0.35 + 0.65*{grow})")
        bg = F.light_spot(g, "SkyGlow", bg, None, (0.5, 0.465), 2.0, 0.4, 0.5, accent=True, gain=0.5,
                          blend=f"min({BG}*{src}*0.6, 1)")
        bg = F.light_spot(g, "HorizonLine", bg, None, (0.5, 0.465), 1.6, 0.004, 0.02, accent=True, gain=1.2,
                          blend=f"min({BG}*(0.15 + 0.6*{src}), 1)")
        g.at(0, 2)
        core = F.accent_solid(g, "SourceCoreColor", 2.0)
        cm = F.ellipse(g, "SourceCoreShape", (0.5, 0.465), 0.05, 0.05, 0.1)
        F.masked(core, cm)
        # volumetric shafts: noisy light through a zoom-type directional blur centred on the source
        shaft_noise = F.noise(g, "ShaftNoise", "#000000", "#ffffff", detail=3, scale=12, seethe_rate=0.05,
                              contrast=1.8)
        shaft_mask = F.ellipse(g, "ShaftMask", (0.5, 0.465), 0.5, 0.35, 0.4)
        F.masked(shaft_noise, shaft_mask)
        shafts_src = F.merge(g, "ShaftSource", core, shaft_noise, mode="Multiply")
        rays = F.dirblur(g, "Shafts", shafts_src, length=f"0.6*{BG}", btype=3)
        rays.set(Center=[0.5, 0.465])
        rays_glow = F.cc(g, "ShaftsGain", rays, gain=f"2.5*{BG}")
        bg = F.merge(g, "ShaftsMerge", bg, rays_glow, mode="Screen", blend=f"min({src}, 1)")
        bg = F.merge(g, "SourceMerge", bg, core, mode="Screen", blend=f"min({src}, 1)")
        bg = F.particles(g, "Motes", bg, number=4, lifespan=200, velocity=0.002, angle=80, angle_var=60, size=0.3,
                         color=(0.9, 0.8, 0.68), region="CubeRgn", region_size=(2.2, 1.3, 1.0), center_y=0.0,
                         turbulence=0.1, glow=3)
        bg = F.xf(g, "EnvCamera", bg, size=f"1 + 0.05*{e_inout(prog(0, g.frames))}", edges=1)

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Cinzel", "Black", 0.12, 1.08, color=p["TEXT_COLOR"])
        refl = F.fill_material(g, "BronzeReflect", title,
                               [(0, "#1a0f08", 1), (0.42, "#6b4526", 1), (0.5, "#f2c58a", 1), (0.55, "#3a2414", 1),
                                (1, "#120a05", 1)])
        face = F.merge(g, "BronzeFace", title, refl, mode="Multiply", blend=0.85)
        brushed = F.noise(g, "BrushedGrain", "#808080", "#b0b0b0", detail=8, scale=40, seethe_rate=0.0, contrast=1.2)
        brushed.set(Angle=0.0)
        bm = F.bitmap_mask(g, "BrushedMatte", title)
        F.masked(brushed, bm)
        face = F.merge(g, "BrushedMerge", face, brushed, mode="Overlay", blend=0.35)
        rim = F.edge_light(g, "GoldRim", title, 0.0, -0.0035, accent=True, gain=1.6, blur_px=1.2)
        face = F.merge(g, "RimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(1 - min({ex}*1.5, 1))*(0.35*{u} + {step(I)}*(0.8 + 0.2*{decay(I, 20)})), 1)")
        g.at(0, 6)
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        ext = F.extrusion_stack(g, "Extrude", clear, title, layers=8, dy=-0.0011, color=(0.05, 0.03, 0.018))
        solid_t = F.merge(g, "TitleSolid", ext, face)
        swept = F.light_sweep(g, "Sweep", solid_t, title, f"{I} + 14", 34, angle=28, width=0.05, peak=0.85,
                              color=(1.0, 0.92, 0.78))
        lit = F.cc(g, "Ignition",
                   swept, gain=f"(0.12*{u}*(1 - {step(I)}) + {step(I)}*(0.55 + 0.45*{decay(I, 36)}))*(1 - 0.7*{ex}) + 0.02")
        g.at(0, 8)
        placed = F.title_placement(g, "TitleRise", lit, size_expr=f"0.86 + 0.14*{e_out(u, 3)}",
                                   center_extra_y=f"-0.16*(1 - {e_out(u, 3)})")
        horizon_clip = F.rect(g, "HorizonClip", (0.5, 0.675), 1.2, 0.65, 0.01)
        horizon_clip.expr("SoftEdge", f"0.004 + 0.5*{u}", 0.01)
        clipped = F.merge(g, "TitleClipHolder", clear, placed)
        F.masked(clipped, horizon_clip)
        tglow = F.softglow(g, "TitleGlow", clipped, 12,
                           gain=f"{ctl('GlowStrength')}*(0.35 + 1.4*{decay(I, 14)})", threshold=0.3)
        scene = F.merge(g, "TitleOverEnv", bg, tglow, blend=f"min({u}*3, 1)")

        g.at(0, 10)
        flare = F.accent_solid(g, "FlareColor", 1.6)
        fm = F.ellipse(g, "FlareShape", (0.5, 0.465), 2.4, 0.012, 0.02)
        F.masked(flare, fm)
        scene = F.merge(g, "AnamorphicFlare", scene, flare, mode="Screen",
                        blend=f"min({ctl('ImpactIntensity')}*({decay(I, 10)}*1.2 + 0.15*{step(I)})*(1 - {ex}), 1)")
        scene = F.shock_ring(g, "PressureRing", scene, center=(0.5, 0.5), max_size=1.4, frames=26, border=0.03,
                             soft=0.06, peak=0.35)
        burst_n = f"60*{ctl('ParticleIntensity')}*{window(I, I + ' + 3', 1, 1)} + 1.2*{ctl('ParticleIntensity')}*{step(I)}"
        scene = F.particles(g, "Embers", scene, number=60, lifespan=90, velocity=0.012, angle=90, angle_var=70,
                            size=0.45, color=p["ACCENT_COLOR"], region="CubeRgn", region_size=(1.2, 0.1, 0.3),
                            center_y=-0.05, turbulence=0.35, glow=6, number_expr=burst_n)
        scene = F.impact_flash(g, "ImpactFlash", scene, color=p["ACCENT_COLOR"], peak=0.15, frames=6)

        g.at(0, 12)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.5,
                                    color=(0.78, 0.66, 0.52), y_off=-0.12)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 16", f"{ctl('ExitStart')} - 8", 18, 12))
        tag, tagp = F.subtitle_text(g, "Tagline", p["OPTIONAL_TAGLINE"], "Teko", "Light", 0.02, 2.0,
                                    color=(0.6, 0.52, 0.42), label="Tagline", group=12, y_off=0.11)
        scene = F.merge(g, "TaglineMerge", scene, tagp, blend=window(f"{I} + 36", f"{ctl('ExitStart')} - 8", 18, 12))

        g.at(0, 14)
        # exit: horizontal light-slit shutter
        slit = F.rect(g, "ShutterSlit", (0.5, 0.5), 1.2, 1.0, 0.004)
        slit.expr("Height", f"0.002 + 1.1*(1 - {e_inout(ex)})", 1.0)
        slit.expr("Center", f"Point(0.5, {ctl('TextPosY')})", [0.5, 0.5])
        black = F.solid(g, "ShutterBlack", (0, 0, 0))
        hold = F.merge(g, "ShutterHold", black, scene)
        F.masked(hold, slit)
        line = F.accent_solid(g, "ShutterLineColor", 1.5)
        lm = F.rect(g, "ShutterLineShape", (0.5, 0.5), 2.0, 0.003, 0.004)
        lm.expr("Width", f"0.02 + 2*(1 - {clamp01(f'({ex} - 0.75)*4')})", 2.0)
        lm.expr("Center", f"Point(0.5, {ctl('TextPosY')})", [0.5, 0.5])
        F.masked(line, lm)
        scene = F.merge(g, "ShutterLine", hold, line, mode="Screen",
                        blend=f"{step(ctl('ExitStart'))}*(1 - {clamp01(f'({ex} - 0.85)*6.6')})")
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.08, shake_frames=8, shake_amp=0.005)
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T40()
