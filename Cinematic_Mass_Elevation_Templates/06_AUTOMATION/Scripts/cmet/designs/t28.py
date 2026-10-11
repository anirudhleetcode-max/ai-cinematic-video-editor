"""T28 - Rotating Monolith (true 3D)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, subtitle, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_extruded, rot_matrix
from . import _c_helpers as X

GRAPHITE = Material(base=(0.36, 0.38, 0.42), spec=(0.9, 0.95, 1.0), spec_power=45, spec_gain=0.6, diffuse=0.75,
                    ambient=0.08, metal=0.45, env_sky=(0.7, 0.75, 0.82), env_horizon=(0.04, 0.045, 0.05),
                    env_ground=(0.08, 0.08, 0.09), env_sharp=10, bevel=0.05, texture="brushed", tex_amount=0.1,
                    rim=(0.7, 0.85, 1.0), seed=28)


class T28(Design):
    ID = "T28"
    NAME = "Rotating Monolith"
    SLUG = "Rotating_Monolith"
    CATEGORY = "C - Future Tech and Kinetic Camera"
    CONCEPT = "The title is a solid graphite monolith that turns out of darkness under a single overhead shaft of light."
    ENTRANCE = ("The extruded title approaches from depth almost edge-on (78 deg yaw, pitched back 18 deg) and "
                "rotates on two axes into view - a weighty oblique turn, never a flat spin.")
    REVEAL = ("At the impact frame the rotation locks at a three-quarter angle (thickness still visible); the "
              "overhead light flares across the bevels and floor dust lifts.")
    CAMERA = "Real 3D: Camera3D slowly arcs (x-offset) while the solid rotates; light shaft stays fixed."
    MATERIAL = "Brushed graphite with silver bevels, cool rim; extrusion sides in deep graphite."
    EXIT = "The monolith keeps turning to edge-on and recedes into the dark while the light shaft closes."
    TECHNIQUES = ["Text3D + Renderer3D", "two-axis oblique rotation", "perspective extrusion", "overhead light shaft",
                  "floor reflection", "floor dust", "edge-on exit"]
    TRUE_3D = True
    DURATION_FRAMES = 204
    DEFAULTS = dict(MAIN_TITLE="MONOLITH", SUBTITLE="BUILT TO ENDURE", FONT_FAMILY="anton",
                    TEXT_COLOR="#7E8794", ACCENT_COLOR="#B8D4FF", ANIMATION_START=6, ANIMATION_DURATION=84,
                    IMPACT_FRAME=90, HOLD_DURATION=74, EXIT_START=168, EXIT_DURATION=30, LETTER_SPACING=0.05,
                    TITLE_WIDTH=0.56, SHADOW_STRENGTH=0.6, EXTRUSION_DEPTH=1.0)
    SOUND = [(0, "atmos", "Cavernous low drone"), (6, "rwhoosh", "Slow air displacement as it turns"),
             (20, "riser", "Grinding stone/metal riser (20-90)"), (84, "whoosh", "Final turn whoosh"),
             (90, "impact", "Deep lock-in impact"), (90, "metal", "Metallic resonance"), (92, "debris", "Floor dust"),
             (168, "rwhoosh", "Turn-away whoosh"), (182, "tail", "Long tail")]
    FUSION_NOTES = ["True 3D: edit the text in the Text3D node ('Main Title (3D)'); rotation is on "
                    "MonolithText3D Transform3DOp.Rotate.X/Y via expressions.",
                    "Material colour is the 'Material Color' control (MtlBlinn diffuse).",
                    "The preview adds a faint mirrored floor reflection; the Fusion graph uses a floor light pool "
                    "instead (add a second Renderer3D with a flipped camera if a true reflection is wanted)."]

    def _rot(self, c):
        u = c.reveal_u()
        eo = K.ease_out(u, 2.2)
        ex = c.exit_u()
        ei = K.ease_in(ex, 2)
        drift = K.ease_in_out(K.prog(c.t, c.impact, c.exit_start - c.impact), 2)
        ry = -78 * (1 - eo) - 20 * eo + 5 * drift + 100 * ei
        rx = 18 * (1 - eo) + 5 * eo - 8 * ei
        rz = 4 * (1 - eo)
        z = 1.1 * c.H * (1 - eo) ** 1.5 + 0.9 * c.H * ei
        return u, eo, ex, ei, rx, ry, rz, z

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        tc = K.col(p["TEXT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        imp = c.impact
        u, eo, ex, ei, rx, ry, rz, zt = self._rot(c)
        hit = c.hit(0.03, 0.5)
        sp = c.title()
        hx, hy = c.hero()
        shaft = K.smooth(K.prog(t, 0, 1.0)) * (1 - K.smooth(K.prog(ex, 0.4, 0.6)))

        # --- void, overhead shaft, floor
        nx, ny = K.grid(H, W)
        bg = K.vgrad(H, W, (0.004, 0.005, 0.007), (0.012, 0.013, 0.016))
        cx = hx / (H / 2)
        floor_y = (hy + sp.ink_h * 0.95) / (H / 2)
        key = ("env", cx, floor_y)
        if key not in c.cache:
            cone = E.light_cone(H, W, (cx, -1.25), 90, 20, 3.0, 0.3)
            pool = K.soft_spot(H, W, cx, floor_y + 0.06, 0.9, 0.12, 1.4) * (ny > floor_y)
            c.cache[key] = ((cone * 0.16)[..., None] * (acc * 0.4 + 0.6) * bgI,
                            (pool * 0.18)[..., None] * (acc * 0.3 + 0.7) * bgI)
        cone_rgb, pool_rgb = c.cache[key]
        bg += cone_rgb * (shaft * (1 + 0.6 * hit))
        bg += pool_rgb * shaft
        fogl = E.fog(H, W, t, (0.10, 0.11, 0.13), density=0.6, scale=1.4, speed=(0.012, 0.0), seed=28,
                     height=(floor_y + 0.08, 0.12))
        bg += fogl * bgI * (0.5 + 0.5 * shaft)

        # --- the monolith (real perspective extrusion, two-axis rotation)
        sh = c.shaded(GRAPHITE)
        Lw = np.array([0.25, -0.95, 0.35])   # overhead key (world, y down)
        R = rot_matrix(rx, ry, rz + p["TEXT_ROTATION"])
        Ll = R.T @ Lw
        spec_sweep = math.exp(-((ry + 32) / 14) ** 2) * (1 - ei)
        lg = (0.4 + 0.8 * eo) * (1 - 0.8 * ei) * (1 + 0.5 * hit)
        rgb, a = sh.shade(light=tuple(Ll), base=tc, rim_gain=(0.3 + 1.6 * hit) * (1 - ei), rim_dir=(0, -1),
                          light_gain=lg, env_shift=0.3 * math.sin(math.radians(ry)),
                          sweep=(-0.6 + 1.2 * K.smooth(K.prog(ry, -60, 50)), 0.18, 0.4, 1.2 * spec_sweep))
        cam = c.cam(zoom=1.0, fov_scale=1.2, pan=(-40 * k * (1 - eo) + 0 * hx, 0), yaw=6 * (1 - eo))
        L = c.layer()
        depth = 0.42 * sp.cap_px * p["EXTRUSION_DEPTH"]
        side = tc * 0.22 + 0.015
        lift = -6 * k * K.pulse(t, imp, 0.03, 0.25)
        place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, (hx, hy + lift, zt), 1.0, (rx, ry, rz +
                       p["TEXT_ROTATION"]), max(depth, 0.6), side * (1 - 0.7 * ei), slices=14,
                       side_light=lambda q: 0.25 + 0.75 * q ** 1.5,
                       opacity=min(1.0, u * 3 + 0.05) * (1 - K.smooth(K.prog(ex, 0.55, 0.45))))
        # floor reflection (flipped about the floor line, blurred and faint)
        fy = int(H / 2 + floor_y * H / 2)
        span = min(fy, H - fy, int(0.25 * H))
        refl = None
        if span > 4:
            src = L.rgb[fy - span:fy][::-1]
            fall = np.clip(1 - np.arange(span, dtype=np.float32) / span, 0, 1)[:, None, None]
            refl = K.blur(src, 6 * k) * 0.18 * fall
        from ..base import drop_shadow
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.5, (0, 24), 36, k)
        img = bg * (1 - L.a[..., None]) + L.rgb
        if refl is not None:
            img[fy:fy + span] += refl
        img += K.blur(np.maximum(L.rgb - 0.45, 0), 10 * k) * 0.6 * p["GLOW_STRENGTH"] * (0.3 + hit)

        # --- floor dust lifting at the lock
        if t >= imp and p["PARTICLE_INTENSITY"] > 0:
            dt = t - imp
            B = c.cache.get("dust")
            n = int(180 * p["PARTICLE_INTENSITY"])
            if B is None:
                r = np.random.default_rng(28)
                B = c.cache["dust"] = (r.uniform(-1, 1, n), r.uniform(0.2, 1.0, n), r.random(n))
            ux, spd, rr = B
            gx = cx + ux * sp.ink_w / H * 1.2 + np.sign(ux) * spd * 0.25 * (1 - np.exp(-dt * 1.5))
            gy = floor_y + 0.02 - spd * 0.08 * (1 - np.exp(-dt * 2)) + 0.01 * dt
            fade = np.exp(-dt / (0.8 + rr)) * (1 - ex)
            Pb = E.Particles(n, 1)
            Pb.z = (0.8 + 0.5 * rr).astype(np.float32)
            img += E.particle_layer(H, W, Pb, gx, gy, (0.6, 0.62, 0.68), 1.6, 0.35 * fade, glow=1.0)
        img = apply_shake(c, img, 0.0025, 0.3, 12)
        cam2 = c.cam(zoom=1.0)
        img = subtitle(c, img, cam2, imp + 0.5, c.exit_start - 0.2, (0.7, 0.74, 0.8), y_rel=0.9)
        img = X.grade_fast(img, shadows=(-0.002, 0.0, 0.006), contrast=1.06)
        return c.finish(img, vignette=0.6, grain=0.03, bloom=(0.8, 0.45))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S, D = ctl("AnimStart"), ctl("AnimDuration")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        BG = ctl("BackgroundIntensity")
        eo = e_out(prog(S, D), 2.2)
        ei = e_in(ex, 2)
        drift = e_inout(prog(I, f"({ctl('ExitStart')} - {I})"))
        shaft = f"{clamp01('time/24')}*(1 - {e_inout(clamp01(f'({ex} - 0.4)/0.6'))})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "Void", [(0, "#030405", 1), (1, "#010101", 1)])
        cs = F.accent_solid(g, "ShaftColor", 0.7)
        F.masked(cs, F.closed_poly_mask(g, "ShaftShape", [(0.44, 1.05), (0.56, 1.05), (0.86, 0.22), (0.14, 0.22)],
                                        soft=0.08))
        bg = F.merge(g, "LightShaft", bg, cs, mode="Screen",
                     blend=f"0.16*{BG}*{shaft}*(1 + 0.6*{decay(I, 12)})")
        bg = F.light_spot(g, "FloorPool", bg, None, (0.5, 0.26), 0.9, 0.12, 0.2, accent=True, gain=0.6,
                          blend=f"0.3*{BG}*{shaft}")
        fog = F.noise(g, "FloorFog", "#000000", "#1c1e22", detail=5, scale=2.0, seethe_rate=0.02, contrast=1.4,
                      center="Point(0.5 + time*0.0005, 0.5)")
        F.masked(fog, F.ellipse(g, "FloorFogBand", (0.5, 0.22), 2.0, 0.22, 0.4))
        bg = F.merge(g, "FloorFogMerge", bg, fog, mode="Screen", blend=f"{BG}*(0.5 + 0.5*{shaft})")

        g.at(0, 2)
        ry = f"(-78*(1 - {eo}) - 20*{eo} + 5*{drift} + 100*{ei})"
        rx = f"(18*(1 - {eo}) + 5*{eo} - 8*{ei})"
        tz = f"(-4*pow(1 - {eo}, 1.5) - 3.5*{ei})"
        rnd = F.text3d_rig(g, "Monolith", p["MAIN_TITLE"], "Anton", "Regular", size=0.55, extrusion=0.22, bevel=0.02,
                           color=p["TEXT_COLOR"], spec=(0.9, 0.95, 1.0), spec_exp=45, rot_y=ry, rot_x=rx, tz=tz,
                           cam_z="4.2", cam_x=f"0.25*(1 - {eo})", cam_y="0.05", key_rot=(-55, -25),
                           key_color=(1.0, 0.98, 0.95), key_int=1.3, amb=0.12, rim=True,
                           rim_color=p["ACCENT_COLOR"])
        g.tools["MonolithText3D"].expr("Transform3DOp.Rotate.Z", f"{ctl('TextRotation')} + 4*(1 - {eo})", 0)
        g.at(0, 4)
        lit = F.cc(g, "MonolithLevel", rnd,
                   gain=f"(0.35 + 0.65*{eo})*(1 - 0.8*{ei})*(1 + 0.5*{decay(I, 12)})")
        glow = F.softglow(g, "BevelGlow", lit, 10, gain=f"{ctl('GlowStrength')}*(0.3 + {decay(I, 12)})",
                          threshold=0.45)
        scene = bg
        sh = F.cc(g, "ShadowMatte", glow, gain=0)
        sh = F.xf(g, "ShadowOffset", sh, center="Point(0.5, 0.48)")
        sh = F.blur(g, "ShadowSoft", sh, 18)
        scene = F.merge(g, "ShadowMerge", scene, sh, blend=f"0.5*{ctl('ShadowStrength')}")
        scene = F.merge(g, "MonolithOverVoid", scene, glow,
                        blend=f"min({prog(S, D)}*3 + 0.05, 1)*(1 - {e_inout(clamp01(f'({ex} - 0.55)/0.45'))})")
        g.at(0, 6)
        scene = F.particles(g, "FloorDust", scene, number=180, lifespan=40, velocity=0.006, angle=90, angle_var=70,
                            size=0.35, color=(0.6, 0.62, 0.68), region="CubeRgn", region_size=(1.3, 0.03, 0.3),
                            center_y=-0.28, turbulence=0.15, glow=3,
                            number_expr=f"180*{ctl('ParticleIntensity')}*{window(I, f'{I} + 2', 1, 1)}")
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.6,
                                    color=(0.7, 0.74, 0.8), y_off=-0.15)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 12", f"{ctl('ExitStart')} - 5", 14, 10))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.02, shake_frames=6, shake_amp=0.0025)
        g.output = F.finish(g, scene, vignette=0.6)


DESIGN = T28()
