"""T26 - Extreme Close-Up."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_sprite
from . import _c_helpers as X

LACQUER = Material(base=(0.6, 0.05, 0.07), spec=(1.0, 0.92, 0.85), spec_power=90, spec_gain=0.9, diffuse=0.7,
                   ambient=0.06, metal=0.3, env_sky=(0.9, 0.82, 0.75), env_horizon=(0.03, 0.02, 0.02),
                   env_ground=(0.08, 0.05, 0.04), env_sharp=12, bevel=0.06, texture="grain", tex_amount=0.06,
                   bump=0.02, rim=(1.0, 0.85, 0.7), seed=26)

BOOST = 3.0     # title raster boost for the extreme close-up
Z0 = 6.5        # start dolly zoom


class T26(Design):
    ID = "T26"
    NAME = "Extreme Close-Up"
    SLUG = "Extreme_Close_Up"
    CATEGORY = "C - Future Tech and Kinetic Camera"
    CONCEPT = "A macro study of the lettering: we start inside the lacquered surface of one letter and pull out to the name."
    ENTRANCE = ("Extreme macro crop on the bevel of the first letter with shallow depth of field and a raking edge "
                "light; the camera dollies backward on a long eased move while the tilt flattens out.")
    REVEAL = "The pull-back lands exactly on the impact frame with a tiny settle; focus snaps crisp and the edge light flares."
    CAMERA = "Backward dolly from 6.5x with perspective tilt/yaw unwinding to frontal; macro DOF opening to full focus."
    MATERIAL = "Deep crimson gloss lacquer with fine grain, warm bevel highlights and a travelling specular glint."
    EXIT = "Rack focus: the title defocuses into soft bokeh and the light fades."
    TECHNIQUES = ["boosted raster close-up", "backward dolly", "2.5D perspective tilt", "macro depth of field",
                  "travelling glint", "focus snap", "rack-focus exit"]
    DURATION_FRAMES = 200
    DEFAULTS = dict(MAIN_TITLE="CLOSER", SUBTITLE="EVERY DETAIL MATTERS", FONT_FAMILY="bebas",
                    TEXT_COLOR="#9E1620", ACCENT_COLOR="#FFD9B8", ANIMATION_START=0, ANIMATION_DURATION=112,
                    IMPACT_FRAME=112, HOLD_DURATION=60, EXIT_START=168, EXIT_DURATION=26, LETTER_SPACING=0.05,
                    TITLE_WIDTH=0.5, SHADOW_STRENGTH=0.6)
    SOUND = [(0, "atmos", "Intimate room tone"), (0, "swell", "Slow tonal swell under the pull-back (0-112)"),
             (30, "shimmer", "Glint shimmer"), (100, "rwhoosh", "Soft reverse whoosh"),
             (112, "impact", "Restrained low hit on the settle"), (113, "shimmer", "Focus-snap glint"),
             (168, "tail", "Defocus tail")]
    FUSION_NOTES = ["Fusion zooms the vector Text+ itself (Size/Center driven by expressions) so the close-up stays "
                    "crisp; use 'Text Scale' to resize the final title. The preview also tilts/yaws the camera for "
                    "perspective, which the 2D Fusion graph approximates with a slight rotation."]

    def _dolly(self, c):
        u = c.reveal_u()
        e = K.smoother(u)
        Z = Z0 ** (1 - e)
        dt = c.t - c.impact
        if dt > 0:
            Z *= 1 - 0.012 * math.sin(min(dt / 0.35, 1) * math.pi) * c.p["IMPACT_INTENSITY"]
        return u, e, Z

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        tc = K.col(p["TEXT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u, e, Z = self._dolly(c)
        hit = c.hit(0.02, 0.4)
        sp = c.title(boost=BOOST)
        hx, hy = c.hero()

        # --- studio backdrop + bokeh dust
        bg = K.radial(H, W, -0.6, -0.5, 2.4, (0.06, 0.035, 0.03), (0.006, 0.005, 0.006), 1.1) * bgI
        if p["PARTICLE_INTENSITY"] > 0:
            P = c.cache.get("dust")
            if P is None:
                P = c.cache["dust"] = E.Particles(int(90 * p["PARTICLE_INTENSITY"]), seed=26, z=(0.4, 2.5))
            x, y = P.drift(t, vel=(0.01, -0.004), turb=0.02, freq=0.3)
            bg += E.particle_layer(H, W, P, x, y, acc * 0.7, 2.5, 0.25, zoom=0.6 + 0.4 * Z ** 0.5, focus=0.3,
                                   dof=3.0, glow=0.5)

        # --- title material (shaded once; glint added in screen space)
        key = "shade"
        if key not in c.cache:
            sh = c.shaded(LACQUER, sprite=sp, name="boosted")
            rgb, a = sh.shade(light=(-0.55, -0.6, 0.6), base=tc, rim_gain=0.0, light_gain=1.0)
            rim = np.clip((1 - sh.nz) * 2.5, 0, 1) * np.clip(-sh.ny * 0.7 - sh.nx * 0.5 + 0.3, 0, 1) * sp.mask
            spec = np.clip((1 - sh.nz) * 1.6, 0, 1) * sp.mask
            c.cache[key] = (rgb, a, np.repeat(rim[..., None], 3, 2) * acc, np.repeat(spec[..., None], 3, 2))
        rgb, a, rim, spec = c.cache[key]

        # camera: pull back, pan from the crop point, perspective unwinding
        g0 = sp.glyphs[0] if sp.glyphs else None
        if g0 is not None:
            tx = (g0.box[0] + (g0.box[2] - g0.box[0]) * 0.18 - sp.anchor[0]) / BOOST
            ty = (g0.box[1] + (g0.box[3] - g0.box[1]) * 0.12 - sp.anchor[1]) / BOOST
        else:
            tx, ty = 0.0, 0.0
        w = (1 - e) ** 1.3
        tilt = 24 * (1 - e) ** 1.5
        yaw = -14 * (1 - e) ** 1.5
        cam = c.cam(zoom=Z, fov_scale=1.0, tilt=tilt, yaw=yaw,
                    pan=(-(tx + hx) * Z * w + hx * 0, -(ty + hy) * Z * w))
        s = 1.0 / BOOST
        L = c.layer()
        c.place(L, cam, rgb, a, sp, s)
        Lr = c.layer()
        rim_gain = (0.25 + 0.35 * (1 - e) + 1.4 * hit) * p["GLOW_STRENGTH"] * (1 - K.smooth(ex))
        c.place(Lr, cam, rim * rim_gain + 0, a, sp, s, add=True)
        Ls = c.layer()
        c.place(Ls, cam, spec, a, sp, s, add=True)
        nx, ny = K.grid(H, W)
        gpos = -2.2 + 4.4 * K.smooth(K.prog(t, c.start + c.reveal * 0.15, c.reveal * 0.95))
        band = np.exp(-((nx * 0.85 + ny * 0.5 - gpos) / 0.18) ** 2) * (1 if 0.0 < gpos < 2.3 or gpos <= 0 else 1)
        glint = Ls.rgb * band[..., None] * acc * (0.9 + 0.8 * hit)
        from ..base import drop_shadow
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.6, (14, 20), 30, k)
        img = bg * (1 - L.a[..., None]) + L.rgb + Lr.rgb + glint

        # --- macro depth of field: tilted focal plane that opens up as we pull out
        dof = (Z - 1) / (Z0 - 1)
        defocus_exit = K.ease_in(ex, 1.5)
        if dof > 0.02 or defocus_exit > 0:
            focus_y = 0.0
            dist = np.abs(ny * 0.9 + nx * 0.25 - focus_y)
            m = np.clip(dist * 2.2 * dof, 0, 1)
            if defocus_exit > 0:
                m = np.maximum(m, defocus_exit)
            r = 16 * k * max(dof, defocus_exit)
            bl = K.blur(img, r)
            img = img * (1 - m[..., None]) + bl * m[..., None]
        img *= 1 - 0.85 * K.smooth(K.prog(ex, 0.25, 0.75))
        img += K.blur(np.maximum(img - 0.7, 0), 18 * k) * 0.5 * p["GLOW_STRENGTH"] * hit
        cam_s = c.cam(zoom=1.0)
        img = subtitle(c, img, cam_s, imp + 0.5, c.exit_start - 0.2, (0.75, 0.68, 0.62), y_rel=0.82)
        return c.finish(img, vignette=0.55, grain=0.03, bloom=(0.8, 0.45),
                        grade=dict(shadows=(0.004, 0.0, -0.002), highlights=(0.01, 0.004, -0.006), contrast=1.06))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S, D = ctl("AnimStart"), ctl("AnimDuration")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        BG = ctl("BackgroundIntensity")
        u = prog(S, D)
        e = e_inout(u)
        settle = f"(1 - 0.012*{ctl('ImpactIntensity')}*{step(I)}*sin(min((time - {I})/8.4, 1)*3.14159))"
        Z = f"(pow({Z0}, 1 - {e})*{settle})"
        w = f"pow(1 - {e}, 1.3)"
        dof = f"(({Z} - 1)/{Z0 - 1})"
        base_size = 0.2

        g.at(0, 0)
        bg = F.gradient_bg(g, "Backdrop", [(0, "#140907", 1), (1, "#020202", 1)], gtype="Radial",
                           start=(0.2, 0.85), end=(1.0, 0.0))
        bg = F.cc(g, "BackdropLevel", bg, gain=BG)
        bg = F.particles(g, "Bokeh", bg, number=4, lifespan=300, velocity=0.0008, angle=20, angle_var=180, size=1.2,
                         color=(0.9, 0.75, 0.6), region="CubeRgn", region_size=(2.4, 1.4, 1.0), center_y=0.0,
                         turbulence=0.05, glow=12)
        g.at(0, 2)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Bebas Neue", "Regular", base_size, 1.05,
                             color=p["TEXT_COLOR"])
        # zoom the vector text itself (crisp close-up); the crop point is the first letter's upper-left bevel
        g.published = [q for q in g.published if q.cid != "MainTitleSize"]
        title.expr("Size", f"{base_size}*{Z}", base_size)
        title.expr("Center", f"Point(0.5 + 0.2*{Z}*{w}, 0.5 - 0.075*{Z}*{w})", [0.5, 0.5])
        refl = F.fill_material(g, "LacquerReflect", title,
                               [(0, "#2a0306", 1), (0.42, "#7c0d14", 1), (0.5, "#ffd6c8", 1), (0.56, "#5a080d", 1),
                                (1, "#180204", 1)], start=(0.4, 0.62), end=(0.6, 0.38))
        face = F.merge(g, "LacquerFace", title, refl, mode="Overlay", blend=0.85)
        rim = F.edge_light(g, "EdgeLight", title, -0.002, -0.003, accent=True, gain=1.3, blur_px=1.5)
        face = F.merge(g, "EdgeLightMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.25 + 0.35*(1 - {e}) + 1.4*{decay(I, 10)}), 1)*(1 - {ex})")
        g.at(0, 4)
        glint = F.light_sweep(g, "Glint", face, title, f"{S} + 0.15*{D}", f"0.95*{D}", angle=30, width=0.12, peak=0.9,
                              accent=True)
        placed = F.title_placement(g, "TitlePlace", glint, angle_extra=f"4*pow(1 - {e}, 1.5)")
        sh = F.cc(g, "ShadowMatte", placed, gain=0)
        sh = F.xf(g, "ShadowOffset", sh, center="Point(0.507, 0.481)")
        sh = F.blur(g, "ShadowSoft", sh, 16)
        scene = F.merge(g, "ShadowOverBackdrop", bg, sh, blend=f"0.6*{ctl('ShadowStrength')}")
        scene = F.merge(g, "TitleOverBackdrop", scene, placed)
        g.at(0, 6)
        # macro DOF: graduated blur (top/bottom) that opens with the pull-back; rack-focus exit
        focus = F.rect(g, "FocusBand", (0.5, 0.5), 2.0, 0.25, 0.25, invert=True, angle=-12)
        dofb = F.blur(g, "MacroDOF", scene, f"16*max({dof}, pow({ex}, 1.5))")
        dofm = F.merge(g, "MacroDOFMerge", scene, dofb, blend=f"min(1, {dof}*2 + {ex})")
        F.masked(dofm, focus)
        rack = F.blur(g, "RackFocus", dofm, f"18*pow({ex}, 1.5)")
        scene = F.cc(g, "LightFade", rack, gain=f"1 - 0.85*{e_inout(clamp01(f'({ex} - 0.25)/0.75'))}")
        scene = F.softglow(g, "SnapGlow", scene, 18, gain=f"0.5*{ctl('GlowStrength')}*{decay(I, 10)}", threshold=0.6)
        g.at(0, 8)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.5,
                                    color=(0.75, 0.68, 0.62), y_off=-0.14)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 12", f"{ctl('ExitStart')} - 5", 18, 10))
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T26()
