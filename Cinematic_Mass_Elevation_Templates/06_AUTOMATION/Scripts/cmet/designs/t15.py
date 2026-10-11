"""T15 - Diamond Cut (genuine 3D title)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from ._b_helpers import put_title, glint, add_sub, fam, fusion_subtitle

DIAMOND = Material(base=(0.86, 0.90, 0.96), spec=(1.0, 1.0, 1.0), spec_power=260, spec_gain=1.4, diffuse=0.25,
                   ambient=0.04, metal=0.62, env_sky=(0.80, 0.86, 0.98), env_horizon=(0.03, 0.035, 0.06),
                   env_ground=(0.22, 0.25, 0.34), env_sharp=9, bevel=0.11, bevel_round=False, texture="facets",
                   tex_amount=0.22, bump=0.03, rim=(0.8, 0.9, 1.0), seed=71)


class T15(Design):
    ID = "T15"
    NAME = "Diamond Cut"
    SLUG = "Diamond_Cut"
    CATEGORY = "B - Premium Materials"
    CONCEPT = "A flawless, faceted crystal title displayed like a jewel on midnight velvet."
    ENTRANCE = ("A controlled orbit: the camera arcs around the cut-crystal title (yaw 55 deg and a slight "
                "pitch resolving to front-on) while hundreds of facets catch and lose the light.")
    REVEAL = ("On the impact frame the orbit settles, the display spotlight brightens and one star-shaped glint "
              "with a faint spectral fringe fires from a letter crown; facets keep scintillating gently.")
    CAMERA = "Measured orbit + dolly that decelerates into a locked front view; no shake."
    MATERIAL = ("Faceted crystal: Voronoi facet planes with per-facet specular flashes driven by the view "
                "angle, sharp flat chamfer bevel (crown), cool environment reflection, restrained dispersion "
                "(2-3 px RGB split on the brightest sparkles only).")
    EXIT = "The title turns away in the opposite direction as the spotlight closes, leaving a last glint."
    TECHNIQUES = ["Text3D extrusion", "camera orbit", "facet scintillation", "restrained dispersion",
                  "star glints", "caustic velvet backdrop", "spotlight close exit"]
    TRUE_3D = True
    DURATION_FRAMES = 204
    DEFAULTS = dict(MAIN_TITLE="DIAMOND", SUBTITLE="CUT FROM PRESSURE", FONT_FAMILY="cinzel_deco",
                    SUB_FONT_FAMILY="marcellus", TEXT_COLOR="#DCE5F1", ACCENT_COLOR="#A9C8FF",
                    ANIMATION_START=6, ANIMATION_DURATION=90, IMPACT_FRAME=96, HOLD_DURATION=64, EXIT_START=164,
                    EXIT_DURATION=32, LETTER_SPACING=0.07, TITLE_WIDTH=0.6, SHAKE_AMOUNT=0.0)
    FUSION_NOTES = [
        "Facet scintillation in Fusion is approximated by a discontinuous FastNoise cell pattern clipped to the "
        "rendered title and modulated by the camera orbit; Text3D itself has smooth faces (no real facets).",
        "Dispersion is limited to a subtle tinted sweep; enable chromatic aberration in your grade if you want "
        "more prismatic separation (keep it restrained for readability).",
    ]
    SOUND = [(0, "atmos", "Quiet velvet room tone"), (6, "swell", "Glassy pad swell under the orbit"),
             (30, "shimmer", "Facet sparkles"), (60, "shimmer", "Facet sparkles"), (84, "riser", "Crystal riser"),
             (96, "ice", "Crystalline ping"), (96, "sub", "Soft sub bloom"), (100, "shimmer", "Glint"),
             (164, "rwhoosh", "Soft reverse whoosh"), (190, "shimmer", "Last glint"), (194, "tail", "Tail")]

    # ------------------------------------------------------------ preview --
    def facet_maps(self, c, sp, sh):
        """Gem-cut facet map: dense Voronoi cells (~0.13 cap) each with its own
        random facet orientation (angle, tilt), plus thin cut lines."""
        key = "facetmaps"
        if key not in c.cache:
            rng = np.random.default_rng(71)
            cell = max(6.0, 0.13 * sp.cap_px)
            n = int(sp.w * sp.h / (cell * cell))
            seeds = np.ones((sp.h, sp.w), np.uint8)
            xs = rng.integers(0, sp.w, n)
            ys = rng.integers(0, sp.h, n)
            seeds[ys, xs] = 0
            _, lab = cv2.distanceTransformWithLabels(seeds, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
            ang_v = rng.uniform(0, 2 * math.pi, n + 2).astype(np.float32)
            tilt_v = rng.uniform(0.3, 1.0, n + 2).astype(np.float32)
            lab = np.clip(lab, 0, n + 1)
            ang, tilt = ang_v[lab], tilt_v[lab]
            lf = lab.astype(np.float32)
            edge = ((np.abs(np.diff(lf, axis=1, append=lf[:, -1:])) > 0) |
                    (np.abs(np.diff(lf, axis=0, append=lf[-1:, :])) > 0)).astype(np.float32)
            lines = cv2.GaussianBlur(edge, (0, 0), 0.7) * sp.mask
            c.cache[key] = (ang, tilt, lines.astype(np.float32))
        return c.cache[key]

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        ue = K.ease_in_out(u, 2.2)
        hit = c.hit(0.04, 0.5)
        after = 1.0 if t >= imp else 0.0
        hx, hy = c.hero()
        nx, ny = K.grid(H, W)

        # ---- velvet backdrop with slow caustics and a display spotlight
        spot = (0.35 + 0.45 * K.smooth(u) + 0.25 * hit) * (1 - K.smooth(K.prog(t, c.exit_start, c.exit_dur * 0.8)))
        bg = K.radial(H, W, hx / (H / 2), hy / (H / 2) - 0.1, 2.0, (0.030, 0.035, 0.065), (0.004, 0.004, 0.010), 1.2)
        bg = bg * (0.5 + 0.5 * spot)
        cau = E.caustics(H, W, t * 0.35, scale=2.2, seed=31, sharp=8)
        cmask = K.soft_spot(H, W, hx / (H / 2), hy / (H / 2) + 0.05, 1.6, 0.8, 1.2)
        bg += (cau * cmask * 0.05 * spot)[..., None] * acc * bgI
        bg += (E.light_cone(H, W, (hx / (H / 2), -1.3), 90, 14, 3.0, 0.4) * 0.07 * spot)[..., None] * \
            (0.6 + 0.4 * acc) * bgI
        if "stars" not in c.cache:
            c.cache["stars"] = E.stars(H, W, n=int(120 * p["PARTICLE_INTENSITY"]) + 1, seed=73, twinkle=0.0)
        tw = 0.5 + 0.5 * math.sin(t * 2.3)
        bg += c.cache["stars"] * 0.25 * (0.6 + 0.4 * tw) * bgI

        # ---- title: orbit
        sp = c.title()
        sh = c.shaded(DIAMOND)
        yaw = 55 * (1 - ue) - 48 * K.ease_in(ex, 2)
        pitch = -16 * (1 - ue)
        zpos = 0.6 * H * (1 - ue) + 0.6 * H * K.ease_in(ex, 2)
        ya = math.radians(yaw)
        light = (-0.35 + 0.8 * math.sin(ya), -0.75 + 0.4 * math.sin(math.radians(pitch)), 0.55)
        rgb, a = sh.shade(light=light, rim_gain=0.35 + 0.5 * hit, rim_dir=(0.2, -1), base=K.col(p["TEXT_COLOR"]),
                          light_gain=0.55 + 0.55 * spot, env_shift=0.8 * math.sin(ya) + 0.15 * t / c.dur)
        ang, tilt, lines = self.facet_maps(c, sp, sh)
        # facet scintillation: a facet flashes when its tilted normal lines up with the moving light
        phase = ya * 3.0 + math.radians(pitch) * 2 + 0.25 * t
        fac = np.cos(ang - phase) * tilt
        sparkle = np.clip((fac - 0.85) / 0.15, 0, 1) ** 2 * a
        sparkle *= (0.55 + 0.45 * (1 - after)) * (0.6 + 0.4 * spot)
        bri = np.clip(0.5 + 0.5 * fac, 0, 1) ** 1.6
        deep = np.array((0.13, 0.16, 0.26), np.float32)
        white = K.col(p["TEXT_COLOR"]) * 1.15
        facet_col = deep[None, None, :] * (1 - bri[..., None]) + white[None, None, :] * bri[..., None]
        lvl = 0.45 + 0.6 * spot
        rgb = rgb * 0.45 + facet_col * lvl * a[..., None] + (lines * 0.35 * lvl)[..., None] * (0.8 + 0.2 * acc)
        # restrained dispersion: tiny R/B offset on the sparkle layer only
        sp_rgb = np.stack([np.roll(sparkle, 2, 1), sparkle, np.roll(sparkle, -2, 1)], -1) * 1.6
        rgb = rgb + sp_rgb * (0.9 + 0.1 * acc)
        zoom = 0.96 + 0.07 * K.ease_in_out(K.prog(t, 0, c.dur), 2)
        cam = c.cam(zoom=zoom, fov_scale=1.0, yaw=0.0, tilt=0.0)
        L = c.layer()
        op = K.smooth(u * 3.5) * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.5, c.exit_dur * 0.5)))
        depth = 0.24 * sp.cap_px * p["EXTRUSION_DEPTH"]
        side = np.array((0.30, 0.34, 0.44)) * (0.5 + 0.5 * spot)
        put_title(c, L, cam, rgb, a, sp, 1.0, rot=(pitch, yaw, 0), off=(0, 0, zpos), depth=depth, side=side,
                  slices=10, side_light=lambda q: 0.35 + 0.65 * q, opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.4, (0, 20), 30, k)
        img = comp(bg, L)
        img += K.blur(np.maximum(L.rgb - 0.95, 0), 4 * k) * 0.8 * p["GLOW_STRENGTH"]

        # ---- star glints: the impact glint (with faint spectral fringe) + a late exit glint
        for t0, gx_rel, gy_rel, gain in ((imp, -0.28, -0.46, 1.6), (c.exit_start + c.exit_dur * 0.45, 0.33, -0.4,
                                                                     1.0)):
            gi = K.pulse(t, t0, 0.06, 0.45) * gain * p["GLOW_STRENGTH"] * (p["IMPACT_INTENSITY"] if t0 == imp else 1)
            if gi > 0.01:
                gx = W / 2 + hx + gx_rel * sp.ink_w * zoom
                gy = H / 2 + hy + gy_rel * sp.ink_h * zoom
                for ch, dx in ((0, -3 * k), (1, 0), (2, 3 * k)):
                    g1 = glint(H, W, gx + dx, gy, 150 * k, (1, 1, 1), gi, rays=4, angle=0.0, thin=0.007)
                    img[..., ch] += g1[..., ch] * (0.9 + 0.1 * acc[ch])
        img = add_sub(c, img, cam, imp + 0.5, c.exit_start - 0.1, (0.70, 0.76, 0.86), y_rel=0.95, tracking=0.55,
                      rel=0.18)
        img = apply_shake(c, img, 0.001, 0.2, 8)
        return c.finish(img, vignette=0.55, grain=0.025, bloom=(0.9, 0.45),
                        grade=dict(shadows=(-0.002, 0.0, 0.006), contrast=1.06, sat=0.9),
                        streak=(1.25, 0.15, 180, acc))

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
        spot = f"(0.35 + 0.45*{e_inout(u)} + 0.25*{decay(I, 12)})*(1 - {prog(X0, f'{XD}*0.8')})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "Velvet", [(0, "#0a0c18", 1), (1, "#010103", 1)], gtype="Radial",
                           start=(0.5, 0.55), end=(1.3, 0.0))
        cau = F.noise(g, "Caustics", "#000000", "#ffffff", detail=3, scale=5, seethe_rate=0.06, contrast=3.5,
                      brightness=-0.3, center="Point(0.5 + time*0.0004, 0.5)")
        caum = F.ellipse(g, "CausticsPool", (0.5, 0.47), 1.4, 0.7, 0.5)
        cau_c = F.cc(g, "CausticsTint", cau, gain=0.12, sat=0.3)
        F.masked(cau_c, caum)
        bg = F.merge(g, "CausticsMerge", bg, cau_c, mode="Screen", blend=f"{BG}*{spot}")
        bg = F.light_spot(g, "DisplaySpot", bg, None, (0.5, 0.75), 0.5, 1.2, 0.6, accent=True, gain=0.25,
                          blend=f"{BG}*{spot}")

        g.at(0, 2)
        ff, fs = fam(p["FONT_FAMILY"])
        yaw = f"55*(1 - {e_inout(u)}) - 48*{e_in(ex, 2)}"
        pitch = f"16*(1 - {e_inout(u)})"
        render = F.text3d_rig(g, "Crystal", p["MAIN_TITLE"], ff, fs, size=0.4, extrusion=0.12, bevel=0.03,
                              color=p["TEXT_COLOR"], spec=(1, 1, 1), spec_exp=200, rot_y=yaw, rot_x=pitch,
                              tz=f"-1.5*(1 - {e_inout(u)}) - 1.5*{e_in(ex, 2)}",
                              cam_z=f"4.3 - 0.3*{e_inout(prog(0, g.frames))}",
                              cam_x=f"0.6*sin(3.14159*(1 - {e_inout(u)}))", key_rot=(-40, -30),
                              key_color=(0.95, 0.97, 1.0), key_int=1.3, amb=0.1, rim=True, rim_color=(0.75, 0.85, 1.0))
        g.at(0, 4)
        facets = F.noise(g, "FacetCells", "#000000", "#ffffff", detail=1, scale=14, seethe_rate=0.0, contrast=5,
                         brightness=-0.55, discontinuous=True)
        facets.expr("Angle", f"({yaw})*4", 0)
        fclip = F.bitmap_mask(g, "FacetClip", render)
        F.masked(facets, fclip)
        lit = F.cc(g, "SpotExposure", render, gain=f"0.55 + 0.55*{spot}")
        lit = F.merge(g, "FacetSparkle", lit, facets, mode="Screen",
                      blend=f"0.7*(0.55 + 0.45*(1 - {step(I)}))")
        sw = F.light_sweep(g, "PrismSweep", lit, render, f"{I} - 6", 34, angle=35, width=0.03, accent=True,
                           peak=0.55)
        glow = F.softglow(g, "CrystalGlow", sw, 6, gain=f"0.6*{ctl('GlowStrength')}", threshold=0.85)
        scene = F.merge(g, "TitleOverVelvet", bg, glow,
                        blend=f"min({u}*3.5, 1)*(1 - {clamp01(f'({ex} - 0.5)*2')})")
        g.at(0, 6)
        gl = F.solid(g, "GlintCore", (1, 1, 1))
        gm = F.ellipse(g, "GlintShape", (0.36, 0.56), 0.004, 0.004, 0.003)
        F.masked(gl, gm)
        gs = F.dirblur(g, "GlintRays", gl, 0.08, angle=0, btype=0)
        gs2 = F.dirblur(g, "GlintRaysV", gl, 0.08, angle=90, btype=0)
        gstar = F.merge(g, "GlintStar", gs, gs2, mode="Screen")
        gglow = F.softglow(g, "GlintGlow", gstar, 10, gain=f"3*{ctl('GlowStrength')}", threshold=0.0)
        scene = F.merge(g, "Glint", scene, gglow, mode="Screen",
                        blend=f"min({ctl('ImpactIntensity')}*{decay(I, 11)}*1.5, 1)")
        g.at(0, 8)
        scene = fusion_subtitle(g, scene, p, size=0.024, tracking=1.8, color=(0.70, 0.76, 0.86), y_off=-0.15,
                                t_in=f"{I} + 12", t_out=f"{X0} - 2")
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.05, shake_frames=6, shake_amp=0.0)
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T15()
