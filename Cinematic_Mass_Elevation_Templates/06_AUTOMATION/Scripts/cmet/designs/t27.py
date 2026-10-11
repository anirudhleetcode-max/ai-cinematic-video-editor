"""T27 - Low-Angle Titan."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, subtitle, apply_shake, drop_shadow
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_extruded
from . import _c_helpers as X

PATINA = Material(base=(0.45, 0.62, 0.55), spec=(1.0, 0.85, 0.65), spec_power=26, spec_gain=0.35, diffuse=0.8,
                  ambient=0.1, metal=0.25, env_sky=(0.75, 0.62, 0.55), env_horizon=(0.12, 0.1, 0.1),
                  env_ground=(0.08, 0.09, 0.09), env_sharp=8, bevel=0.045, texture="stone", tex_amount=0.22,
                  bump=0.03, rim=(1.0, 0.72, 0.45), seed=27)


class T27(Design):
    ID = "T27"
    NAME = "Low-Angle Titan"
    SLUG = "Low_Angle_Titan"
    CATEGORY = "C - Future Tech and Kinetic Camera"
    CONCEPT = "We stand at the foot of a colossal monument: the name towers over us against a dusk sky."
    ENTRANCE = ("Low camera near the ground: the giant lettering rises up into frame from below the horizon while "
                "the camera cranes up and the steep upward perspective slowly eases.")
    REVEAL = ("At the impact frame the monument crests into full view - a low rumble, grit trickles off the letter "
              "tops and the setting sun rims the top edges.")
    CAMERA = "Worm's-eye 2.5D perspective (tilt + wide lens), slow crane with a long ease; one restrained rumble."
    MATERIAL = "Weathered verdigris bronze with stone-like pitting; thick perspective extrusion showing the underside."
    EXIT = "Haze rolls in across the ground and the monument drains to a silhouette, then into the dusk."
    TECHNIQUES = ["worm's-eye perspective", "perspective extrusion (underside)", "rising crane reveal", "dusk sky",
                  "ground haze", "grit fall", "silhouette exit"]
    DURATION_FRAMES = 240
    DEFAULTS = dict(MAIN_TITLE="TITAN", SUBTITLE="RISE ABOVE ALL", FONT_FAMILY="teko",
                    TEXT_COLOR="#8DB3A4", ACCENT_COLOR="#FFB46A", ANIMATION_START=12, ANIMATION_DURATION=100,
                    IMPACT_FRAME=116, HOLD_DURATION=84, EXIT_START=200, EXIT_DURATION=32, LETTER_SPACING=0.06,
                    TITLE_WIDTH=0.5, SHADOW_STRENGTH=0.6)
    SOUND = [(0, "wind", "High wind across open ground"), (0, "atmos", "Low dusk drone"),
             (12, "riser", "Massive slow riser under the crane (12-116)"), (100, "rwhoosh", "Air displacement"),
             (116, "sub", "Sub-bass swell / rumble"), (116, "impact", "Distant monumental boom"),
             (118, "debris", "Grit trickling off the letters"), (200, "wind", "Wind rises with the haze"),
             (214, "tail", "Long tail")]
    FUSION_NOTES = ["The worm's-eye keystone is a CornerPositioner ('TitanKeystone'); its corner inputs "
                    "(TopLeft/TopRight/BottomLeft/BottomRight) are driven by expressions - adjust the 0.6x top "
                    "factor to change the perspective strength."]

    def _rise(self, c):
        u = c.reveal_u()
        return u, K.ease_in_out(u, 2.2)

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        tc = K.col(p["TEXT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u, e = self._rise(c)
        hit = c.hit(0.05, 0.6)
        after = 1.0 if t >= imp else 0.0
        sp = c.title()
        hx, hy = c.hero()
        sil = K.smooth(K.prog(ex, 0.0, 0.6))     # light drains to silhouette
        haze = K.smooth(K.prog(ex, 0.2, 0.8))

        # --- dusk sky (camera cranes up => horizon drops)
        hzn = 0.64 + 0.08 * e + (hy / H)            # horizon (fraction of H from top)
        nx, ny = K.grid(H, W)
        yy = (ny + 1) / 2
        top = np.array([0.03, 0.035, 0.07], np.float32)
        mid = np.array([0.16, 0.10, 0.12], np.float32)
        low = np.array([0.45, 0.24, 0.12], np.float32)
        f1 = np.clip(yy / hzn, 0, 1)[..., None]
        sky = top * (1 - f1) ** 1.2 + mid * np.clip(1 - np.abs(f1 - 0.6) * 2.5, 0, 1) + low * f1 ** 3
        sun = K.soft_spot(H, W, hx / (H / 2) + 0.25, (hzn * 2 - 1) - 0.25, 0.8, 0.5, 1.6)
        sky = sky + (sun * (0.35 + 0.15 * after))[..., None] * acc
        cl, dn = E.clouds(H, W, t * 0.6, (0.32, 0.2, 0.18), (0.05, 0.04, 0.06), seed=27, scale=0.7, speed=0.006,
                          contrast=1.4)
        sky = sky * (1 - dn[..., None] * 0.5 * (1 - f1)) + cl * 0.45 * (1 - f1)
        ground = (ny + 1) / 2 > hzn
        bg = np.where(ground[..., None], np.array([0.02, 0.018, 0.02], np.float32), sky) * bgI
        bg = bg * (1 - 0.5 * sil)

        # --- the monument: worm's-eye perspective, rising
        sh = c.shaded(PATINA)
        lg = (0.45 + 0.35 * e) * (1 - 0.85 * sil)
        rim = (0.4 + 0.9 * after + 1.4 * hit) * (1 - sil)
        rgb, a = sh.shade(light=(0.35, -0.75, 0.45), base=tc, rim_gain=rim, rim_dir=(0.2, -1.0), light_gain=lg,
                          env_shift=-0.25)
        lean = -(34 - 12 * e)                       # top leans away (worm's-eye)
        cam = c.cam(zoom=1.0, fov_scale=0.75)
        sc = 1.5
        hh = sp.ink_h * 0.5 * sc
        th = math.radians(lean)
        base_y = hzn * H - H / 2 + 0.01 * H          # letter feet on the horizon line
        rise = (1 - e) * 0.62 * H
        pos = (hx, base_y - hh + rise + hh * (1 - math.cos(th)), -hh * math.sin(th))
        L = c.layer()
        depth = 0.45 * sp.cap_px * p["EXTRUSION_DEPTH"]
        side = tc * 0.16 * (1 - 0.8 * sil) + 0.01
        if depth > 0.5:
            place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, pos, sc,
                           (lean, 0, p["TEXT_ROTATION"]), depth, side, slices=14,
                           side_light=lambda q: 0.35 + 0.65 * q)
        else:
            from ..typo import place_sprite
            place_sprite(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, pos, sc, (lean, 0, p["TEXT_ROTATION"]))
        # the ground occludes whatever is still below the horizon
        gmask = ((ny + 1) / 2 > hzn).astype(np.float32)
        L.a *= 1 - gmask
        L.rgb *= (1 - gmask)[..., None]
        # dusk haze in front of the base
        fogl = E.fog(H, W, t, (0.42, 0.3, 0.26), density=0.5 + 0.9 * haze, scale=1.1, speed=(0.02, 0.0), seed=27,
                     height=(hzn * 2 - 1 - 0.05 - 0.5 * haze, 0.25 + 0.5 * haze))
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.3, (0, 6), 30, k)
        img = bg * (1 - L.a[..., None]) + L.rgb
        img = img + fogl * bgI * (1 - 0.6 * sil + 0.6 * haze)
        img = img * (1 - 0.75 * K.smooth(K.prog(ex, 0.55, 0.45)))

        # --- grit trickling from the letter tops after the crest
        if t >= imp and p["PARTICLE_INTENSITY"] > 0:
            dt = t - imp
            B = c.cache.get("grit")
            n = int(220 * p["PARTICLE_INTENSITY"])
            if B is None:
                r = np.random.default_rng(27)
                B = c.cache["grit"] = (r.uniform(-0.5, 0.5, n), r.uniform(0, 1.2, n), r.random(n))
            ux, dl, rr = B
            ptop = cam.project(np.array([[hx, base_y - 2 * hh * math.cos(th), -2 * hh * math.sin(th)]]))[0][0]
            px = ptop[0] + ux * sp.ink_w * sc * 0.8
            tt = np.maximum(dt - dl, 0)
            py = ptop[1] + 10 * k + 0.5 * 900 * k * tt * tt
            fade = (tt > 0) * np.exp(-tt / 1.2) * (1 - sil)
            Pb = E.Particles(n, 1)
            Pb.z = (0.8 + 0.6 * rr).astype(np.float32)
            img += E.particle_layer(H, W, Pb, (px - W / 2) / (H / 2), (py - H / 2) / (H / 2), (0.75, 0.62, 0.5),
                                    1.0, 0.5 * fade, glow=0.3, streak=(np.zeros(n), -0.01 * np.minimum(tt, 1) * np.ones(n)))
        img += K.blur(np.maximum(L.rgb - 0.5, 0), 14 * k) * 0.6 * p["GLOW_STRENGTH"] * (0.3 + hit)
        img = apply_shake(c, img, 0.003, 0.6, 9)
        cam2 = c.cam(zoom=1.0)
        img = subtitle(c, img, cam2, imp + 0.8, c.exit_start - 0.2, (0.85, 0.72, 0.6),
                       y_rel=((hzn + 0.075) * H - H / 2 - hy) / max(1.0, sp.ink_h))
        img = X.grade_fast(img, shadows=(0.0, 0.002, 0.008), highlights=(0.015, 0.006, -0.01), contrast=1.06)
        return c.finish(img, vignette=0.5, grain=0.035, bloom=(0.8, 0.45))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S, D = ctl("AnimStart"), ctl("AnimDuration")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        BG = ctl("BackgroundIntensity")
        e = e_inout(prog(S, D))
        sil = e_inout(clamp01(f"{ex}/0.6"))
        haze = e_inout(clamp01(f"({ex} - 0.2)/0.8"))
        after = step(I)

        g.at(0, 0)
        sky = F.gradient_bg(g, "DuskSky", [(0, "#733d1f", 1), (0.25, "#2a1a20", 1), (0.6, "#0c0c18", 1),
                                           (1, "#06070f", 1)], start=(0.5, 0.1), end=(0.5, 1.0))
        sky = F.light_spot(g, "SettingSun", sky, None, (0.62, 0.3), 0.9, 0.5, 0.6, accent=True, gain=0.8,
                           blend=f"{BG}*(0.45 + 0.15*{after})")
        cl = F.noise(g, "DuskClouds", "#000000", "#3a2622", detail=6, scale=1.4, seethe_rate=0.01, contrast=1.5,
                     center="Point(0.5 + time*0.0003, 0.6)")
        sky = F.merge(g, "CloudsMerge", sky, cl, mode="Screen", blend=f"0.5*{BG}")
        bg = F.cc(g, "SkyLevel", sky, gain=f"{BG}*(1 - 0.5*{sil})")

        g.at(0, 2)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Teko", "SemiBold", 0.26, 1.06, color=p["TEXT_COLOR"])
        pat = F.noise(g, "PatinaPitting", "#6d7c74", "#ffffff", detail=7, scale=14, seethe_rate=0.0, contrast=1.6)
        F.masked(pat, F.bitmap_mask(g, "PatinaClip", title))
        face = F.merge(g, "PatinaFace", title, pat, mode="Multiply", blend=0.6)
        rim = F.edge_light(g, "SunRim", title, 0.0, -0.004, accent=True, gain=1.3, blur_px=1.5)
        face = F.merge(g, "SunRimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.4 + 0.9*{after} + 1.4*{decay(I, 14)})*(1 - {sil}), 1)")
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        ext = F.extrusion_stack(g, "Underside", clear, title, layers=10, dx=0.0, dy=-0.004, color=(0.05, 0.07, 0.06))
        solid_t = F.merge(g, "TitleSolid", ext, face)
        lit = F.cc(g, "DuskLight", solid_t, gain=f"(0.45 + 0.35*{e})*(1 - 0.85*{sil})")
        placed = F.title_placement(g, "TitlePlace", lit)
        g.at(0, 4)
        ks = g.add("CornerPositioner", "TitanKeystone")
        ks.conn("Input", placed)
        rise = f"(1.05*(1 - {e}) - 0.05)"
        kt = f"(0.6 + 0.25*{e})"      # top width factor (worm's-eye convergence)
        ks.expr("TopLeft", f"Point(0.5 - 0.5*{kt}, 0.95 - {rise} - 0.1*(1 - {e}))", [0.0, 1.0])
        ks.expr("TopRight", f"Point(0.5 + 0.5*{kt}, 0.95 - {rise} - 0.1*(1 - {e}))", [1.0, 1.0])
        ks.expr("BottomLeft", f"Point(-0.15, -0.25 - {rise})", [0.0, 0.0])
        ks.expr("BottomRight", f"Point(1.15, -0.25 - {rise})", [1.0, 0.0])
        glow = F.softglow(g, "MonumentGlow", ks, 14, gain=f"0.5*{ctl('GlowStrength')}*(0.3 + {decay(I, 12)})",
                          threshold=0.5)
        scene = F.merge(g, "MonumentOverSky", bg, glow)
        # ground in front: the monument rises from behind the horizon
        gnd = F.solid(g, "Ground", (0.02, 0.018, 0.02))
        gm = F.rect(g, "GroundShape", (0.5, 0.0), 2.0, 0.72, 0.006)
        gm.expr("Height", f"0.72 - 0.16*{e}", 0.72)
        F.masked(gnd, gm)
        scene = F.merge(g, "GroundMerge", scene, gnd, blend=f"min({BG}, 1)")
        g.at(0, 6)
        fog = F.noise(g, "GroundHaze", "#000000", "#6b4c42", detail=5, scale=1.6, seethe_rate=0.03, contrast=1.4,
                      center="Point(0.5 + time*0.0012, 0.5)")
        fm = F.rect(g, "GroundHazeBand", (0.5, 0.22), 2.0, 0.25, 0.2)
        fm.expr("Height", f"0.25 + 0.6*{haze}", 0.25)
        F.masked(fog, fm)
        scene = F.merge(g, "GroundHazeMerge", scene, fog, mode="Screen", blend=f"{BG}*(0.5 + 0.9*{haze})")
        scene = F.particles(g, "GritFall", scene, number=120, lifespan=50, velocity=0.004, angle=-90, angle_var=8,
                            size=0.2, color=(0.75, 0.62, 0.5), region="CubeRgn", region_size=(1.1, 0.02, 0.1),
                            center_y=0.25, turbulence=0.02, glow=0,
                            number_expr=f"120*{ctl('ParticleIntensity')}*{window(I, f'{I} + 30', 1, 10)}")
        scene = F.cc(g, "DuskFade", scene, gain=f"1 - 0.75*{e_inout(clamp01(f'({ex} - 0.55)/0.45'))}")
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.6,
                                    color=(0.85, 0.72, 0.6), y_off=-0.29)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 20", f"{ctl('ExitStart')} - 5", 18, 10))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.02, shake_frames=14, shake_amp=0.003)
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T27()
