"""T36 - Hero Silhouette."""
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

BRUSHED_SILVER = Material(base=(0.82, 0.80, 0.78), spec=(1.0, 0.95, 0.88), spec_power=45, spec_gain=0.6,
                          diffuse=0.7, ambient=0.08, metal=0.5, env_sky=(0.75, 0.7, 0.62),
                          env_horizon=(0.06, 0.05, 0.05), env_ground=(0.12, 0.1, 0.09), env_sharp=9, bevel=0.05,
                          texture="brushed", tex_amount=0.05, rim=(1.0, 0.82, 0.6), seed=36)

# Abstract standing figure, in frame heights relative to (figure x, ground y). y down (negative = up).
FIG_ELLIPSES = [  # cx, cy, rx, ry
    (0.0, -1.42, 0.070, 0.088),   # head
    (0.0, -1.24, 0.215, 0.075),   # shoulders
]
FIG_POLYS = [
    [(-0.035, -1.36), (0.035, -1.36), (0.045, -1.26), (-0.045, -1.26)],                  # neck
    [(-0.22, -1.25), (0.22, -1.25), (0.17, -0.62), (-0.17, -0.62)],                      # torso
    [(-0.25, -1.22), (0.25, -1.22), (0.52, 0.05), (0.2, 0.0), (-0.1, 0.04), (-0.55, 0.05)],  # cape
]


class T36(Design):
    ID = "T36"
    NAME = "Hero Silhouette"
    SLUG = "Hero_Silhouette"
    CATEGORY = "E - Character and Emotion"
    CONCEPT = "A lone caped figure stands in smoke against a blinding backlight; the title racks into focus in front of it."
    ENTRANCE = ("Rack focus: the title starts large, soft and dim in the foreground and pulls into focus while the "
                "backlight slowly rises behind the abstract figure silhouette.")
    REVEAL = "Backlight surge at the impact frame: light rays burst around the silhouette, smoke billows outward, title rim ignites."
    CAMERA = "Controlled crane-up and push; smoke, figure and light source at three parallax depths."
    MATERIAL = "Brushed silver title with warm backlit rim; procedural figure silhouette with light-wrapped edges."
    EXIT = "The backlight dies, the title racks back out of focus and the figure dissolves into the smoke."
    TECHNIQUES = ["procedural figure silhouette (primitives)", "occluded god rays", "lit volumetric smoke",
                  "rack focus", "light wrap on silhouette edges", "backlight surge"]
    DURATION_FRAMES = 168
    DEFAULTS = dict(MAIN_TITLE="THE VIGILANT", SUBTITLE="EVERY CITY NEEDS ONE", FONT_FAMILY="teko",
                    TEXT_COLOR="#E6E1D8", ACCENT_COLOR="#FFC27A", ANIMATION_START=6, ANIMATION_DURATION=54,
                    IMPACT_FRAME=60, HOLD_DURATION=60, EXIT_START=132, EXIT_DURATION=32, LETTER_SPACING=0.1,
                    TITLE_WIDTH=0.62, TEXT_POSITION_Y=0.42, SUB_FONT_FAMILY="teko")
    SOUND = [(0, "atmos", "Dark city wind / room tone"), (0, "heartbeat", "Slow heartbeat"),
             (6, "riser", "Focus-pull riser"), (54, "rwhoosh", "Reverse air into the surge"),
             (60, "impact", "Deep cinematic hit + sub"), (60, "swell", "Backlight swell / choir-like pad"),
             (62, "wind", "Smoke billow gust"), (132, "rwhoosh", "Light drains"), (150, "tail", "Low tail")]

    # ------------------------------------------------------------ preview --
    def _figure(self, c, res=2):
        m = c.cache.get("fig")
        if m is not None:
            return m
        H, W = c.H // res, c.W // res
        s = H / 2
        Wf = int(W * 1.0)
        buf = np.zeros((int(H * 1.3), Wf), np.float32)
        ox, oy = Wf / 2, buf.shape[0] * 0.98  # figure foot point in the buffer
        for cx, cy, rx, ry in FIG_ELLIPSES:
            cv2.ellipse(buf, (int((ox + cx * s) * 4), int((oy + cy * s) * 4)), (int(rx * s * 4), int(ry * s * 4)),
                        0, 0, 360, 1.0, -1, cv2.LINE_AA, shift=2)
        for poly in FIG_POLYS:
            pts = np.int32([[(ox + x * s) * 4, (oy + y * s) * 4] for x, y in poly])
            cv2.fillPoly(buf, [pts], 1.0, cv2.LINE_AA, shift=2)
        buf = cv2.GaussianBlur(buf, (0, 0), 1.5)
        m = c.cache["fig"] = (buf, ox, oy, s, res)
        return m

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.04, 0.5)
        crane = K.ease_in_out(K.prog(t, 0, c.dur), 2)
        after = 1.0 if t >= imp else 0.0
        back = (0.12 + 0.45 * K.smooth(K.prog(t, c.start, imp - c.start)) * (1 - after)
                + after * (0.75 + 0.55 * hit)) * (1 - 0.92 * K.smooth(ex))
        nx, ny = K.grid(H, W)

        # light source behind the figure (farthest layer, moves least)
        lx, ly = 0.0, -0.42 + 0.06 * crane
        src = (K.soft_spot(H, W, lx, ly, 0.22, 0.22, 2.0) * 2.5 + K.soft_spot(H, W, lx, ly, 1.2, 0.9, 1.2) * 0.35)
        bg = K.vgrad(H, W, (0.008, 0.008, 0.01), (0.02, 0.016, 0.014)) * bgI
        bg += (src * back * bgI)[..., None] * acc
        # back smoke (lit from behind)
        sm_b = D.shaped(D.plane(H, W, t, 1.6, (0.006, -0.025), 4, 1 + 0.03 * crane, (0, -0.05 * crane)), 0.3, 1.0)
        litmap = K.soft_spot(H, W, lx, ly, 1.1, 0.9, 1.1)
        bg += (sm_b * (0.03 + litmap * back * 0.5) * bgI)[..., None] * (acc * 0.8 + 0.1)

        # figure (mid layer)
        fig, ox, oy, s, res = self._figure(c)
        fs = 1.12 + 0.06 * crane  # push
        fy_ground = (1.08 + 0.10 * crane)  # ground point in frame heights from centre (moves down: crane up)
        M = np.float32([[fs * res, 0, W / 2 - ox * fs * res], [0, fs * res, H / 2 + fy_ground * H / 2 - oy * fs * res]])
        fm = cv2.warpAffine(fig, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        fm = fm * (1 - 0.85 * K.smooth(ex))
        # light wrap: blurred light bleeding over the silhouette edges
        wrap = np.clip(K.blur(1 - fm, 6 * k) - (1 - fm), 0, 1) * fm
        rays_src = (src * back)[..., None] * acc * (1 - fm[..., None])
        rays = K.god_rays(rays_src.astype(np.float32), W / 2 + lx * H / 2, H / 2 + ly * H / 2, 0.9, 0.96, 24)
        fig_col = np.array([0.012, 0.011, 0.012], np.float32)
        bg = bg * (1 - fm[..., None]) + fm[..., None] * fig_col + (wrap * back * 1.6)[..., None] * acc
        bg += rays * (0.5 + 0.35 * hit) * bgI

        # mid smoke around the figure's legs (ground)
        sm_m = D.shaped(D.plane(H, W, t, 1.3, (0.01, -0.02), 8, 1 + 0.07 * crane, (0, -0.1 * crane)), 0.3, 1.0)
        grd = np.clip((ny - 0.2) * 1.4, 0, 1)
        bil = 1 + 0.8 * K.smooth(K.prog(t, imp, 1.5)) * after
        bg = D.over_lit(bg, ((0.05 + litmap * back * 0.6)[..., None] * (acc * 0.7 + 0.15)) * bgI,
                        sm_m * grd * 0.8 * min(1.0, bgI))

        # title: rack focus ------------------------------------------------------------
        sp = c.title()
        sh = c.shaded(BRUSHED_SILVER)
        rgb, a = sh.shade(light=(0.0, -0.4, 1.0), rim_dir=(0, -1), rim_gain=0.3 + 1.4 * back,
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.35 + 0.5 * K.smooth(u) + 0.25 * hit)
        focus = K.ease_in_out(u, 2) * (1 - K.ease_in(ex, 2))
        cam = c.cam(zoom=1.0 + 0.05 * crane, pan=(0, -18 * k * crane))
        L = c.layer()
        sc = 1.0 + 0.22 * (1 - focus)
        op = K.smooth(u * 2.0) * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.4, c.exit_dur * 0.6)))
        c.place(L, cam, rgb, a, sp, sc, off=(0, -30 * k * (1 - focus), -0.15 * H * (1 - focus)), opacity=op)
        defocus = (1 - focus) * 26 * k * p["MOTION_BLUR_AMOUNT"]
        if defocus > 0.5:
            L.rgb = K.blur(L.rgb, defocus)
            L.a = K.blur(L.a, defocus)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.6, (0, 16), 30, k)
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.6, 0), 9 * k) * 0.55 * p["GLOW_STRENGTH"]

        # near smoke (front, fastest parallax), billows at the surge
        sm_n = D.shaped(D.plane(H, W, t, 1.0, (0.015, -0.03), 12, 1 + 0.16 * crane, (0, -0.25 * crane)), 0.4, 1.0, 1.3)
        dens = sm_n * (0.25 + 0.25 * bil * after * math.exp(-max(t - imp, 0) / 2.0) + 0.35 * K.smooth(ex))
        img = D.over_lit(img, ((0.03 + litmap * back * 0.45)[..., None] * (acc * 0.7 + 0.15)) * bgI,
                         dens * min(1.0, bgI))
        # restrained embers/dust in the light
        nP = int(90 * p["PARTICLE_INTENSITY"])
        if nP:
            P = c.cache.get("dust")
            if P is None:
                P = c.cache["dust"] = E.Particles(nP, seed=36, z=(0.5, 3.0))
            x, y = P.drift(t, vel=(0.01, -0.02), turb=0.04, freq=0.3)
            img += E.particle_layer(H, W, P, x, y, acc * 0.8 + 0.2, 1.2, 0.3 * (0.3 + back), focus=1.0, dof=1.0,
                                    t=t, glow=0.8)
        img = apply_shake(c, img, 0.003, 0.3, 14)
        img = subtitle(c, img, cam, imp + 0.6, c.exit_start - 0.2, (0.80, 0.76, 0.70), y_rel=0.78)
        return c.finish(img, vignette=0.6, grain=0.04, bloom=(0.7, 0.55),
                        grade=dict(shadows=(-0.002, 0.0, 0.006), highlights=(0.015, 0.005, -0.01), contrast=1.08))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"], "Backlight Color")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        crane = e_inout(prog(0, g.frames))
        back = (f"((0.12 + 0.45*{prog(ctl('AnimStart'), I + ' - ' + ctl('AnimStart'))}*(1 - {step(I)})"
                f" + {step(I)}*(0.75 + 0.45*{decay(I, 12)}))*(1 - 0.92*{ex}))")
        focus = f"({e_inout(u)}*(1 - {e_in(ex, 2)}))"

        g.at(0, 0)
        bg = F.gradient_bg(g, "Darkness", [(0, "#050404", 1), (1, "#020203", 1)])
        light = F.accent_solid(g, "BacklightColor", 1.0)
        core = F.ellipse(g, "BacklightCore", (0.5, 0.71), 0.14, 0.25, 0.35)
        F.masked(light, core)
        lsrc = F.blur(g, "BacklightBloom", light, 40)
        bg = F.merge(g, "Backlight", bg, lsrc, mode="Screen", blend=f"min({BG}*{back}, 1)")
        bg = D.f_fog(g, "SmokeBack", bg, "#000000", "#5a4630", 2.4, f"1 + 0.03*{crane}", (0.0003, 0.001),
                     blend=f"{BG}*(0.25 + 0.5*{back})")
        g.at(0, 2)
        # figure silhouette from primitives (frame coords: x 0..1, y 0..1 up)
        def fx(x):
            return 0.5 + x * 0.5 * 9 / 16

        def fy(y):
            return 0.5 - (y + 1.08) * 0.5

        figm = None
        for i, (cx, cy, rx, ry) in enumerate(FIG_ELLIPSES):
            e = F.ellipse(g, f"Figure{('Head', 'Shoulders')[i]}", (fx(cx), fy(cy)), rx * 2 * 0.5 * 9 / 16,
                          ry * 2 * 0.5, 0.004)
            if figm is not None:
                e.conn("EffectMask", figm, "Mask")
            figm = e
        for i, poly in enumerate(FIG_POLYS):
            m = F.closed_poly_mask(g, f"Figure{('Neck', 'Torso', 'Cape')[i]}", [(fx(x), fy(y)) for x, y in poly],
                                   soft=0.003)
            m.conn("EffectMask", figm, "Mask")
            figm = m
        fsol = F.solid(g, "FigureColor", (0.012, 0.011, 0.012))
        F.masked(fsol, figm)
        figx = F.xf(g, "FigureCrane", fsol, center=f"Point(0.5, 0.5 - 0.05*{crane})", size=f"1.12 + 0.06*{crane}")
        figfade = F.merge(g, "FigureInSmoke", bg, figx, blend=f"1 - 0.85*{ex}")
        # occluded light rays: zoom-blur the light-with-figure-holdout image from the light centre
        rays = F.dirblur(g, "BacklightRays", figfade, 0.35, btype=3)
        rays.set(Center=[0.5, 0.71])
        bg = F.merge(g, "RaysMerge", figfade, rays, mode="Screen", blend=f"min({BG}*(0.4 + 0.5*{decay(I, 14)}), 1)")
        bg = D.f_fog(g, "SmokeGround", bg, "#000000", "#4a3826", 2.0, f"1 + 0.07*{crane}", (0.0005, 0.001),
                     blend=f"{BG}*(0.3 + 0.5*{back})")

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Teko", "SemiBold", 0.2, 1.1, color=p["TEXT_COLOR"])
        refl = F.fill_material(g, "SilverReflect", title,
                               [(0, "#3a3836", 1), (0.42, "#9a958e", 1), (0.5, "#f4efe6", 1), (0.58, "#76726c", 1),
                                (1, "#2a2827", 1)])
        face = F.merge(g, "SilverFace", title, refl, mode="Multiply", blend=0.8)
        rim = F.edge_light(g, "BackRim", title, 0.0, -0.003, accent=True, gain=1.5, blur_px=1.4)
        face = F.merge(g, "BackRimMerge", face, rim, mode="Screen", blend=f"min({ctl('GlowStrength')}*1.4*{back}, 1)")
        lit = F.cc(g, "FrontFill", face, gain=f"0.35 + 0.5*{u} + 0.25*{decay(I, 12)}")
        g.at(0, 6)
        placed = F.title_placement(g, "RackScale", lit, size_expr=f"1 + 0.22*(1 - {focus})",
                                   center_extra_y=f"0.03*(1 - {focus})")
        rack = F.blur(g, "RackFocus", placed, f"26*(1 - {focus})*{ctl('MotionBlurAmount')}")
        tglow = F.softglow(g, "TitleGlow", rack, 10, gain=f"0.55*{ctl('GlowStrength')}", threshold=0.6)
        scene = F.merge(g, "TitleOverHero", bg, tglow,
                        blend=f"min({u}*2, 1)*(1 - {clamp01(f'({ex} - 0.4)/0.6')})")
        g.at(0, 8)
        scene = D.f_fog(g, "SmokeNear", scene, "#000000", "#3d2e20", 1.5, f"1 + 0.16*{crane}", (0.0006, 0.0013),
                        blend=f"min({BG}, 1)*(0.25 + 0.3*{decay(I, 40)} + 0.35*{ex})", mode="Normal")
        scene = F.particles(g, "LightDust", scene, number=8, lifespan=150, velocity=0.002, angle=80, angle_var=60,
                            size=0.3, color=p["ACCENT_COLOR"], region="CubeRgn", region_size=(2.2, 1.4, 1.0),
                            center_y=0.0, turbulence=0.1, glow=3)
        scene = D.f_sub(g, p, "Teko", "SemiBold", (0.80, 0.76, 0.70), -0.12, f"{I} + 14", f"{ctl('ExitStart')} - 5",
                        scene=scene)
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.05, shake_frames=6, shake_amp=0.003)
        g.output = F.finish(g, scene, vignette=0.6)


DESIGN = T36()
