"""T12 - Chrome Dominion (genuine 3D title)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from ._b_helpers import put_title, floor_reflection, add_sub, fam, fusion_subtitle, fusion_floor_reflection

CHROME = Material(base=(0.85, 0.87, 0.90), spec=(1.0, 1.0, 1.0), spec_power=220, spec_gain=1.6, diffuse=0.08,
                  ambient=0.01, metal=0.97, env_sky=(0.62, 0.65, 0.70), env_horizon=(0.004, 0.004, 0.006),
                  env_ground=(0.08, 0.085, 0.095), env_sharp=26, bevel=0.075, bevel_round=True, texture="none",
                  tex_amount=0.0, rim=(0.85, 0.92, 1.0), seed=41)

# strip softboxes: (x centre, y centre, half width, half height) in normalised grid units (y down)
STRIPS = [(-1.15, -0.62, 0.40, 0.012), (0.0, -0.68, 0.62, 0.014), (1.15, -0.62, 0.40, 0.012)]
STRIP_ON = (0.5, 1.0, 1.5)  # seconds


class T12(Design):
    ID = "T12"
    NAME = "Chrome Dominion"
    SLUG = "Chrome_Dominion"
    CATEGORY = "B - Premium Materials"
    CONCEPT = "A mirror-chrome monolith title stands up in a black studio lit only by hard strip softboxes."
    ENTRANCE = ("Studio strip lights clunk on one by one; the chrome title, lying back on the glossy floor, pivots "
                "upright on its base (X rotation 78 deg to 0) toward a low-angle camera.")
    REVEAL = ("At the lock the strip-light reflections race across the chrome faces, a cold edge light snaps on "
              "and the floor mirror catches the full title.")
    CAMERA = "Low-angle dolly-in that rises slightly to eye level; compact shake at the lock."
    MATERIAL = ("Mirror chrome: near-zero diffuse, very high specular exponent, layered strip reflections over a "
                "black horizon band, crisp bevels with cool edge illumination, dark extruded walls.")
    EXIT = "The title falls back flat into the floor reflection while the strip lights switch off in reverse order."
    TECHNIQUES = ["Text3D extrusion", "pivot-up reveal", "strip-light reflections", "edge illumination",
                  "mirror floor", "sequential light rig", "fall-back exit"]
    TRUE_3D = True
    DURATION_FRAMES = 180
    DEFAULTS = dict(MAIN_TITLE="DOMINION", SUBTITLE="RULE WITHOUT MERCY", FONT_FAMILY="orbitron",
                    SUB_FONT_FAMILY="orbitron_med", TEXT_COLOR="#D4DAE2", ACCENT_COLOR="#CFE2FF",
                    ANIMATION_START=40, ANIMATION_DURATION=34, IMPACT_FRAME=74, HOLD_DURATION=64, EXIT_START=140,
                    EXIT_DURATION=26, LETTER_SPACING=0.08, TITLE_WIDTH=0.6)
    FUSION_NOTES = [
        "Approximation: the Fusion MtlBlinn cannot reflect an environment, so the chrome look is built from a "
        "very high specular exponent, three animated spot/directional highlights and screen-space strip "
        "reflections (masked light sweeps). For true mirror chrome, replace GoldMtl-style Blinn ('ChromeMtl') with "
        "a MtlReflect fed by an HDRI SphereMap - not generated because those tool IDs are unverified here.",
        "The floor reflection is a flipped 2D copy of the rendered title (Transform FlipVert), not a ray-traced "
        "mirror; it stays correct while the title is upright and is faded out during the fall-back exit.",
    ]
    SOUND = [(0, "atmos", "Studio room tone"), (12, "metal", "Strip light 1 clunk"), (24, "metal", "Strip light 2"),
             (36, "metal", "Strip light 3"), (40, "whoosh", "Heavy pivot whoosh"), (60, "riser", "Short riser"),
             (74, "impact", "Chrome slab lands - hard impact"), (74, "metal", "Metallic ring"),
             (78, "shimmer", "Reflection sweep shimmer"), (140, "rwhoosh", "Reverse whoosh fall-back"),
             (152, "metal", "Lights off clunks"), (160, "tail", "Tail")]

    # ------------------------------------------------------------ preview --
    def strips_level(self, c, i):
        t = c.t
        on = K.smooth(K.prog(t, STRIP_ON[i], 0.08)) * (1 - 0.35 * K.pulse(t, STRIP_ON[i] + 0.08, 0.02, 0.12))
        off_t = c.exit_start + c.exit_dur * (0.35 + 0.2 * (2 - i))
        return on * (1 - K.smooth(K.prog(t, off_t, 0.06)))

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.02, 0.3)
        after = 1.0 if t >= imp else 0.0
        T = K.prog(t, 0, c.dur)
        nx, ny = K.grid(H, W)
        lv = [self.strips_level(c, i) for i in range(3)]

        # ---- black studio: strips, haze, glossy floor
        bg = K.vgrad(H, W, (0.008, 0.009, 0.011), (0.002, 0.002, 0.003))
        cam_rise = K.ease_in_out(K.prog(t, 0, c.exit_start), 2)
        y_hor = 0.30 - 0.06 * cam_rise  # floor horizon (normalised, y down) moves up as camera rises
        strip_img = np.zeros((H, W), np.float32)
        for (sx, sy, hw, hh), l in zip(STRIPS, lv):
            if l <= 0:
                continue
            m = (np.clip(1 - (np.abs(nx - sx) - hw) / 0.01, 0, 1) * np.clip(1 - (np.abs(ny - sy) - hh) / 0.006, 0, 1))
            strip_img += m * l
            # mirror image on the glossy floor
            ry = y_hor + 0.22 + (sy + 0.62) * 0.6
            mf = (np.clip(1 - (np.abs(nx - sx) - hw) / 0.25, 0, 1) * np.exp(-((ny - ry) / 0.10) ** 2))
            strip_img += mf * l * 0.035
        strip_rgb = strip_img[..., None] * (0.75 + 0.35 * acc) * 2.2 * bgI
        haze = K.blur(strip_img, 60 * k)[..., None] * (0.5 + 0.5 * acc) * 0.9 * bgI
        bg = bg + strip_rgb + haze
        floor = np.clip((ny - y_hor) * 20, 0, 1)[..., None]
        bg = bg * (1 - 0.25 * floor) + floor * (np.exp(-((ny - y_hor) / 0.02) ** 2) * 0.05 * sum(lv) / 3)[..., None] * acc * bgI
        # faint floor grain / brushed reflection streaks
        if "floorn" not in c.cache:
            c.cache["floorn"] = K.sample(K.fft_noise(256, 1.0, 5), H, W, 3.0, stretch=(14, 1))
        bg += (c.cache["floorn"] * floor[..., 0] * 0.012 * bgI)[..., None]

        # ---- title: pivots up about its base line
        sp = c.title()
        sh = c.shaded(CHROME)
        ue = K.ease_out(u, 2.0)
        bounce = 3.5 * math.exp(-max(0, t - imp) * 6) * math.sin(max(0, t - imp) * 22) * after
        rx = -78 * (1 - ue) - 74 * K.ease_in(ex, 2.2) + bounce
        # pivot about the bottom edge: rotate about anchor, then compensate so the base stays put
        half = float(sp.ink_h) * 0.5
        ang = math.radians(rx)
        off_y = half * (1 - math.cos(ang))
        off_z = -half * math.sin(ang)
        # moving strip reflections: env shift follows the pivot and then a lateral race at impact
        race = K.ease_in_out(K.prog(t, imp - 0.05, 0.9))
        env_shift = 0.9 * math.sin(ang) + 0.6 * (race - 0.5) * (1 if 0 < race < 1 else 0) + 0.05 * T
        lg = (0.25 + 0.75 * sum(lv) / 3) * (1 + 0.4 * hit)
        rgb, a = sh.shade(light=(0.1, -0.9, 0.45), rim_gain=0.2 + 0.9 * after * (1 - ex) + 1.2 * hit,
                          rim_dir=(0, -1), base=K.col(p["TEXT_COLOR"]), light_gain=lg, env_shift=env_shift)
        # layered strip reflections on the faces (screen-space approximation)
        ry = 2 * sh.nz * sh.ny + sh.v * 0.9 + env_shift
        rxn = 2 * sh.nz * sh.nx + sh.u * 0.6
        layers = np.zeros_like(ry)
        for (sx, sy, hw, hh), l, pos in zip(STRIPS, lv, (-0.42, -0.62, -0.30)):
            layers += l * np.exp(-((ry - pos) / 0.035) ** 2) * np.clip(1 - np.abs(rxn - sx * 0.35) / 0.8, 0, 1)
            layers += l * 0.22 * np.exp(-((ry - 0.33 - pos * 0.3) / 0.02) ** 2)
        sweep_b = np.exp(-((sh.u - (-0.8 + 1.6 * race)) / 0.05) ** 2) * (1 if 0 < race < 1 else 0)
        rgb = rgb + ((layers * 1.8 + sweep_b * 1.6) * a)[..., None] * (0.8 + 0.25 * acc) * lg
        zoom = 0.95 + 0.10 * K.ease_in_out(T, 2)
        cam = c.cam(zoom=zoom, tilt=7 * (1 - cam_rise) + 2, fov_scale=0.9,
                    pan=(0, -40 * k * (1 - cam_rise)))
        L = c.layer()
        op = K.smooth(K.prog(t, c.start - 0.1, 0.4)) * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.7,
                                                                             c.exit_dur * 0.3)))
        depth = 0.26 * float(sp.cap_px) * p["EXTRUSION_DEPTH"]
        put_title(c, L, cam, rgb, a, sp, 1.0, rot=(rx, 0, 0), off=(0, off_y, off_z), depth=depth,
                  side=np.array((0.10, 0.105, 0.115)) * (0.5 + 0.5 * lg), slices=12,
                  side_light=lambda q: 0.15 + 0.85 * q ** 2.5, opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.4, (0, 10), 14, k)
        img = comp(bg, L)
        hx, hy = c.hero()
        y_floor = H / 2 + (hy + half) * zoom + 4 * k
        refl = 0.35 * bgI * (1 - K.smooth(abs(rx) / 40))
        img = floor_reflection(img, L, y_floor, refl, 0.16, 2.5, k)
        img += K.blur(np.maximum(L.rgb - 0.9, 0), 6 * k) * 0.6 * p["GLOW_STRENGTH"]
        img += (K.soft_spot(H, W, hx / (H / 2), hy / (H / 2), 1.5, 0.6, 1.5) * 0.08 * hit)[..., None] * acc

        img = add_sub(c, img, cam, imp + 0.5, c.exit_start, (0.62, 0.68, 0.76), y_rel=0.95, tracking=0.6,
                      rel=0.18)
        img = apply_shake(c, img, 0.004, 0.18, 22)
        return c.finish(img, vignette=0.5, grain=0.025, bloom=(0.9, 0.5),
                        grade=dict(shadows=(-0.002, 0.0, 0.004), contrast=1.1, sat=0.8),
                        streak=(1.3, 0.18, 220, acc))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        X0, XD = ctl("ExitStart"), ctl("ExitDuration")
        ex = prog(X0, XD)
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")

        g.at(0, 0)
        bg = F.gradient_bg(g, "StudioBlack", [(0, "#010101", 1), (1, "#020203", 1)])
        on_frames = [round(s * 24) for s in STRIP_ON]
        for i, ((sx, sy, hw, hh), fon) in enumerate(zip(STRIPS, on_frames)):
            off = f"{X0} + {XD}*{0.35 + 0.2 * (2 - i):.2f}"
            lvl = f"{step(fon)}*(1 - {step(off)})"
            s = F.accent_solid(g, f"Strip{i + 1}Color", 1.6)
            cx, cy = 0.5 + sx * 0.5 * 1080 / 1920, 0.5 - sy * 0.5
            m = F.rect(g, f"Strip{i + 1}Shape", (cx, cy), hw * 1080 / 1920, hh, 0.002)
            F.masked(s, m)
            bg = F.merge(g, f"Strip{i + 1}", bg, s, mode="Screen", blend=f"{BG}*{lvl}")
        haze = F.blur(g, "StripHaze", bg, 80)
        bg = F.merge(g, "HazeMerge", bg, haze, mode="Screen", blend=f"0.6*{BG}")
        bg = F.light_spot(g, "FloorSheen", bg, None, (0.5, 0.36), 1.8, 0.03, 0.04, accent=True, gain=0.25,
                          blend=f"{BG}*{step(on_frames[0])}*(1 - {ex})")

        g.at(0, 2)
        ff, fs = fam(p["FONT_FAMILY"])
        bounce = f"3.5*pow(2.718282, -max(time - {I}, 0)/6)*sin(max(time - {I}, 0)*0.92)*{step(I)}"
        rot_x = f"-78*(1 - {e_out(u, 2)}) - 74*{e_in(ex, 2)} + {bounce}"
        render = F.text3d_rig(g, "Chrome", p["MAIN_TITLE"], ff, fs, size=0.4, extrusion=0.14, bevel=0.02,
                              color=p["TEXT_COLOR"], spec=(1, 1, 1), spec_exp=160, rot_x=rot_x, rot_y="0",
                              tz="0", cam_z=f"4.4 - 0.5*{e_inout(prog(0, g.frames))}",
                              cam_y=f"-0.35*(1 - {e_inout(prog(0, X0))})", key_rot=(-60, 10),
                              key_color=(0.95, 0.97, 1.0), key_int=1.4, amb=0.03, rim=True,
                              rim_color=(0.8, 0.9, 1.0))
        g.at(0, 4)
        lit = F.cc(g, "ChromeContrast", render, contrast=1.35, sat=0.6,
                   gain=f"(0.3 + 0.7*{step(on_frames[1])})*(1 + 0.4*{decay(I, 7)})")
        s1 = F.light_sweep(g, "StripReflectA", lit, render, f"{I} - 1", 22, angle=0, width=0.05,
                           color=(0.95, 0.97, 1.0), peak=1.0)
        s2 = F.light_sweep(g, "StripReflectB", s1, render, f"{I} + 4", 30, angle=12, width=0.025,
                           color=(0.9, 0.95, 1.0), peak=0.8)
        edge = F.edge_light(g, "EdgeLight", render, 0.0, -0.003, accent=True, gain=1.6, blur_px=1.0)
        s2 = F.merge(g, "EdgeMerge", s2, edge, mode="Screen",
                     blend=f"min({ctl('GlowStrength')}*(0.2 + 0.8*{step(I)}*(1 - {ex}) + 1.2*{decay(I, 6)}), 1)")
        scene = F.merge(g, "TitleOverStudio", bg, s2,
                        blend=f"{prog(ctl('AnimStart') + ' - 2', 10)}*(1 - {clamp01(f'({ex} - 0.7)*3.3')})")
        g.at(0, 6)
        scene = fusion_floor_reflection(g, "MirrorFloor", scene, lit, base_off=0.09,
                                        blend=f"0.35*{BG}*{step(I + ' - 4')}*(1 - min({ex}*2.5, 1))")
        scene = F.impact_flash(g, "LockFlash", scene, color=p["ACCENT_COLOR"], peak=0.08, frames=5)
        g.at(0, 8)
        scene = fusion_subtitle(g, scene, p, size=0.022, tracking=2.0, color=(0.62, 0.68, 0.76), y_off=-0.15,
                                t_in=f"{I} + 12", t_out=X0)
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.05, shake_frames=4, shake_amp=0.004)
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T12()
