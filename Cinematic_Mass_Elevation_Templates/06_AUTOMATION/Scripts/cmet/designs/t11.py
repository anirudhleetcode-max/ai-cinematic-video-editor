"""T11 - Golden Emperor (genuine 3D title)."""
import math

import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from ._b_helpers import put_title, floor_reflection, glint, add_sub, fam, fusion_subtitle, fusion_floor_reflection

GOLD = Material(base=(0.86, 0.62, 0.30), spec=(1.0, 0.93, 0.80), spec_power=120, spec_gain=1.1, diffuse=0.32,
                ambient=0.025, metal=0.82, env_sky=(0.92, 0.86, 0.78), env_horizon=(0.035, 0.025, 0.015),
                env_ground=(0.30, 0.24, 0.17), env_sharp=11, bevel=0.085, bevel_round=True, texture="brushed",
                tex_amount=0.035, bump=0.01, rim=(1.0, 0.80, 0.55), seed=31)


class T11(Design):
    ID = "T11"
    NAME = "Golden Emperor"
    SLUG = "Golden_Emperor"
    CATEGORY = "C - 3D Metal and Premium Materials"
    CONCEPT = "A regal, restrained gold title: solid polished bullion letterforms turn to face the camera in a dark hall."
    ENTRANCE = ("The extruded gold title glides forward from depth while turning from a three-quarter angle to "
                "face the lens (yaw -38 deg to 0) under a slow, elegant camera push.")
    REVEAL = ("As it squares up a warm key light blooms behind it; a single narrow specular highlight travels "
              "across the bevels; a star glint catches one serif.")
    CAMERA = "Continuous slow push-in with a gentle low-angle tilt that levels out; a whisper of settle at the lock."
    MATERIAL = ("Polished gold (Blinn, high specular exponent) with warm-neutral environment reflection, dark "
                "horizon band, crisp rounded bevel and darker extruded sides; glossy floor reflection.")
    EXIT = "The title turns away on its vertical axis and recedes while the key light dims to black."
    TECHNIQUES = ["Text3D extrusion + bevel", "MtlBlinn gold", "camera push", "yaw reveal", "narrow light sweep",
                  "floor reflection", "star glint", "gold dust bokeh"]
    TRUE_3D = True
    DURATION_FRAMES = 216
    DEFAULTS = dict(MAIN_TITLE="EMPEROR", SUBTITLE="ALL KINGDOMS KNEEL", FONT_FAMILY="cinzel",
                    SUB_FONT_FAMILY="marcellus", TEXT_COLOR="#C9954C", ACCENT_COLOR="#FFC890",
                    ANIMATION_START=8, ANIMATION_DURATION=84, IMPACT_FRAME=92, HOLD_DURATION=74, EXIT_START=170,
                    EXIT_DURATION=38, LETTER_SPACING=0.10, TITLE_WIDTH=0.58, SHAKE_AMOUNT=0.4)
    SOUND = [(0, "atmos", "Low warm drone, hall ambience"), (8, "swell", "Orchestral swell under the turn"),
             (70, "riser", "Soft metallic riser into the lock"), (92, "metal", "Deep resonant gold 'lock' hit"),
             (92, "sub", "Sub-bass bloom"), (100, "shimmer", "Specular sweep shimmer"),
             (104, "shimmer", "Glint ping"), (170, "whoosh", "Slow turning whoosh"), (176, "tail", "Reverb tail")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        ue = K.ease_in_out(u, 2.4)
        hit = c.hit(0.05, 0.6)
        after = 1.0 if t >= imp else 0.0
        T = K.prog(t, 0, c.dur)

        # ---- environment: dark warm hall, key pool, faint beam
        bg = K.vgrad(H, W, (0.010, 0.008, 0.006), (0.004, 0.003, 0.002))
        hx, hy = c.hero()
        bx, by = hx / (H / 2), hy / (H / 2)
        key = (0.08 + 0.42 * K.smooth(K.prog(t, c.start, imp - c.start)) + 0.25 * hit) * (1 - K.smooth(ex))
        bg += (K.soft_spot(H, W, bx, by - 0.05, 1.15, 0.55, 1.6) * key * 0.55)[..., None] * acc * bgI
        cone = E.light_cone(H, W, (-1.4, -1.25), 38, 9, 3.5, 0.5)
        bg += (cone * 0.08 * (0.4 + key))[..., None] * acc * bgI
        # floor: dark glossy plane with horizon glow
        y_floor_n = by + 0.30
        nx, ny = K.grid(H, W)
        floor = np.clip((ny - y_floor_n) * 6, 0, 1)
        bg = bg * (1 - 0.5 * floor[..., None]) + (np.exp(-((ny - y_floor_n) / 0.012) ** 2)
                                                   * np.exp(-(nx / 1.3) ** 2) * 0.12 * key)[..., None] * acc * bgI

        # ---- gold dust bokeh
        P = c.cache.get("dust")
        if P is None:
            P = c.cache["dust"] = E.Particles(int(140 * p["PARTICLE_INTENSITY"]), seed=17, z=(0.4, 3.2))
        if P.n:
            x, y = P.drift(t, vel=(0.01, -0.012), turb=0.05, freq=0.35)
            bg += E.particle_layer(H, W, P, x, y, acc * 0.9 + 0.1, 1.8, 0.32 * (0.35 + key),
                                   zoom=1 + 0.08 * T, focus=1.0, dof=1.4, t=t, flicker=0.3, glow=1.0)

        # ---- title (perspective-projected extruded solid)
        sp = c.title()
        sh = c.shaded(GOLD)
        yaw = -38 * (1 - ue) + 34 * K.ease_in(ex, 2)
        tilt_obj = 6 * (1 - ue)
        zpos = 1.25 * H * (1 - K.ease_out(u, 2.2)) + 0.9 * H * K.ease_in(ex, 2)
        settle = -4 * k * K.pulse(t, imp, 0.04, 0.3)
        # light fixed in the world: key from upper-left front -> moves across the face as it turns
        ya = math.radians(yaw)
        light = (-0.45 + 0.9 * math.sin(ya) * 0.8, -0.65, 0.6)
        sw = K.prog(t, imp + 0.25, 1.7)
        sweep = (-0.75 + 1.5 * K.ease_in_out(sw), 0.035, 0.55, 2.2 * (1 if 0 < sw < 1 else 0))
        lg = (0.35 + 0.65 * K.smooth(u * 1.3)) * (1 - 0.8 * K.smooth(ex)) * (1 + 0.25 * hit)
        rgb, a = sh.shade(light=light, rim_gain=0.35 * after + 0.6 * hit, rim_dir=(0.3, -1), sweep=sweep,
                          base=K.col(p["TEXT_COLOR"]), light_gain=lg, env_shift=0.25 * math.sin(ya) + 0.06 * T)
        zoom = 0.94 + 0.12 * K.ease_in_out(T, 2)
        cam = c.cam(zoom=zoom, tilt=-5 * (1 - ue), fov_scale=0.95)
        L = c.layer()
        op = K.smooth(u * 3) * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.5, c.exit_dur * 0.5)))
        depth = 0.30 * float(sp.cap_px) * p["EXTRUSION_DEPTH"]
        side = np.array((0.36, 0.23, 0.09))
        put_title(c, L, cam, rgb, a, sp, 1.0, rot=(tilt_obj, yaw, 0), off=(0, settle, zpos), depth=depth,
                  side=side * (0.6 + 0.4 * lg), slices=14, side_light=lambda q: 0.25 + 0.75 * q ** 1.6, opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.5, (0, 22), 34, k)
        y_floor = H / 2 + (hy + float(sp.ink_h) * 0.5 * zoom) * 1.0 + 6 * k
        img = comp(bg, L)
        img = floor_reflection(img, L, y_floor, 0.28 * bgI, 0.14, 5, k)
        # warm halo from the hot highlights only
        img += K.blur(np.maximum(L.rgb - 0.85, 0), 12 * k) * 0.5 * p["GLOW_STRENGTH"]

        # ---- glint on a serif when the sweep passes
        if 0 < sw < 1 and op > 0.5:
            gpos = -0.75 + 1.5 * K.ease_in_out(sw)
            gx = W / 2 + hx + gpos * float(sp.ink_w) * zoom * 0.95
            gy = H / 2 + hy - float(sp.ink_h) * 0.46 * zoom
            gi = math.exp(-((sw - 0.55) / 0.12) ** 2) * 1.3 * p["GLOW_STRENGTH"]
            img += glint(H, W, gx, gy, 110 * k, (1.0, 0.9, 0.75), gi, rays=2, angle=0.0, thin=0.008)

        img = add_sub(c, img, cam, imp + 0.6, c.exit_start - 0.2, (0.78, 0.66, 0.48), y_rel=0.98, tracking=0.5,
                      rel=0.2)
        img = apply_shake(c, img, 0.002, 0.3, 10)
        return c.finish(img, vignette=0.6, grain=0.028, bloom=(0.85, 0.45),
                        grade=dict(shadows=(0.004, 0.002, -0.002), highlights=(0.01, 0.004, -0.01), contrast=1.06,
                                   sat=0.95))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        key = f"(0.08 + 0.42*{prog(ctl('AnimStart'), I + ' - ' + ctl('AnimStart'))} + 0.25*{decay(I, 14)})*(1 - {ex})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "HallGradient", [(0, "#020101", 1), (1, "#0a0806", 1)])
        bg = F.light_spot(g, "KeyPool", bg, None, (0.5, 0.53), 1.15, 0.55, 0.5, accent=True, gain=0.55,
                          blend=f"min({BG}*{key}, 1)")
        beam_col = F.accent_solid(g, "BeamColor", 0.35)
        beam = F.ellipse(g, "BeamShape", (0.3, 0.8), 0.18, 1.3, 0.6, angle=38)
        F.masked(beam_col, beam)
        bg = F.merge(g, "KeyBeam", bg, beam_col, mode="Screen", blend=f"{BG}*(0.25 + {key})*0.4")
        bg = F.light_spot(g, "FloorLine", bg, None, (0.5, 0.36), 1.6, 0.008, 0.02, accent=True, gain=0.3,
                          blend=f"{BG}*{key}")
        bg = F.particles(g, "GoldDust", bg, number=8, lifespan=200, velocity=0.002, angle=80, angle_var=180,
                         size=0.4, color=(1.0, 0.82, 0.55), region="CubeRgn", region_size=(2.2, 1.4, 1.2),
                         center_y=0.0, turbulence=0.12, glow=5)

        g.at(0, 2)
        ff, fs = fam(p["FONT_FAMILY"])
        yaw = f"-38*(1 - {e_inout(u)}) + 34*{e_in(ex, 2)}"
        tilt = f"6*(1 - {e_inout(u)})"
        tz = f"-3.2*(1 - {e_out(u, 2)}) - 2.2*{e_in(ex, 2)}"
        render = F.text3d_rig(g, "Gold", p["MAIN_TITLE"], ff, fs, size=0.42, extrusion=0.12, bevel=0.022,
                              color=p["TEXT_COLOR"], spec=(1.0, 0.93, 0.8), spec_exp=90, rot_y=yaw, rot_x=tilt,
                              tz=tz, cam_z=f"4.3 - 0.45*{e_inout(prog(0, g.frames))}",
                              cam_y=f"-0.25*(1 - {e_inout(u)})", key_rot=(-25, -40), key_color=(1.0, 0.9, 0.75),
                              key_int=1.3, amb=0.08, rim=True, rim_color=(1.0, 0.78, 0.5))
        g.at(0, 4)
        lit = F.cc(g, "GoldExposure", render,
                   gain=f"(0.35 + 0.65*min({u}*1.3, 1))*(1 - 0.8*{ex})*(1 + 0.25*{decay(I, 14)})")
        swept = F.light_sweep(g, "SpecSweep", lit, render, f"{I} + 6", 40, angle=28, width=0.03,
                              color=(1.0, 0.94, 0.82), peak=0.9)
        glow = F.softglow(g, "GoldHalo", swept, 14, gain=f"0.5*{ctl('GlowStrength')}", threshold=0.75)
        scene = F.merge(g, "TitleOverHall", bg, glow,
                        blend=f"min({u}*3, 1)*(1 - {clamp01(f'({ex} - 0.5)*2')})")
        g.at(0, 6)
        scene = fusion_floor_reflection(g, "FloorReflection", scene, lit, base_off=0.1,
                                        blend=f"0.28*{BG}*(1 - {ex})")
        scene = F.impact_flash(g, "LockBloom", scene, color=p["ACCENT_COLOR"], peak=0.06, frames=14)
        g.at(0, 8)
        scene = fusion_subtitle(g, scene, p, size=0.026, tracking=1.8, color=(0.78, 0.66, 0.48), y_off=-0.15,
                                t_in=f"{I} + 14")
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.04, shake_frames=8, shake_amp=0.0015)
        g.output = F.finish(g, scene, vignette=0.6)


DESIGN = T11()
