"""T24 - Quantum Split."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, subtitle, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from . import _c_helpers as X

SATIN = Material(base=(0.9, 0.9, 0.92), spec=(1.0, 0.97, 1.0), spec_power=30, spec_gain=0.35, diffuse=0.75,
                 ambient=0.3, metal=0.0, bevel=0.035, texture="none", rim=(0.8, 0.7, 1.0), seed=24)

# channel layer layout: (channel colour, x dir, y dir, z dir, yaw dir)
LAYERS = [((1, 0, 0), -1.0, -0.22, 0.45, 14), ((0, 1, 0), 0.0, 0.10, -0.25, 0), ((0, 0, 1), 1.0, 0.18, 0.15, -14)]


class T24(Design):
    ID = "T24"
    NAME = "Quantum Split"
    SLUG = "Quantum_Split"
    CATEGORY = "C - Future Tech and Kinetic Camera"
    CONCEPT = "The title exists in three states at once: its RGB channels sit on separate depth planes and collapse into one."
    ENTRANCE = ("Red, green and blue channel copies of the title float apart on different depth planes (with two "
                "faint violet depth echoes) and slide together under a camera yaw that reveals their parallax.")
    REVEAL = "Precisely on the impact frame all planes align into a single white wordmark; a thin light line snaps outward."
    CAMERA = "Yaw drift that settles to frontal exactly at alignment; micro shake on the snap."
    MATERIAL = "Satin white face with a soft bevel; additive RGB channel planes; violet echo planes."
    EXIT = "The planes split again in depth (red back, blue forward) and dissolve with a soft defocus."
    TECHNIQUES = ["RGB channel separation", "depth planes", "parallax yaw", "timed convergence", "alignment snap",
                  "micro residual fringe", "depth split exit"]
    DURATION_FRAMES = 156
    DEFAULTS = dict(MAIN_TITLE="QUANTUM", SUBTITLE="EVERY STATE AT ONCE", FONT_FAMILY="staatliches",
                    TEXT_COLOR="#F4F1FF", ACCENT_COLOR="#8E6BFF", ANIMATION_START=4, ANIMATION_DURATION=44,
                    IMPACT_FRAME=50, HOLD_DURATION=60, EXIT_START=116, EXIT_DURATION=28, LETTER_SPACING=0.08,
                    TITLE_WIDTH=0.56, SHADOW_STRENGTH=0.5)
    SOUND = [(0, "atmos", "Low tonal bed"), (2, "swell", "Phasing swell while planes converge (2-50)"),
             (20, "shimmer", "Spectral shimmer"), (44, "rwhoosh", "Reverse whoosh into alignment"),
             (50, "impact", "Tight alignment hit"), (50, "digital", "Snap click"), (51, "sub", "Short sub"),
             (116, "whoosh", "Depth split whoosh"), (132, "tail", "Tonal tail")]

    def _sep(self, c):
        u = K.prog(c.t, c.start, max(0.05, c.impact - c.start))
        sep = (1 - K.smoother(u)) ** 1.4
        dt = c.t - c.impact
        res = 0.0
        if dt >= 0:
            res = 0.035 * math.sin(dt * 2 * math.pi * 7) * math.exp(-dt / 0.12) * c.p["IMPACT_INTENSITY"]
        return sep, res

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        tc = K.col(p["TEXT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        sp = c.title()
        hx, hy = c.hero()
        sep, res = self._sep(c)
        xs = K.ease_in(K.prog(ex, 0, 0.8), 2)  # exit split
        vis = min(1.0, K.prog(t, c.start - 0.1, 0.35)) * (1 - K.smooth(K.prog(ex, 0.3, 0.7)))

        # --- environment: graphite void, violet backlight, faint interference lines, dust
        bg = K.vgrad(H, W, (0.016, 0.014, 0.022), (0.006, 0.005, 0.009))
        bx, by = hx / (H / 2), hy / (H / 2)
        bg += (K.soft_spot(H, W, bx, by, 1.3, 0.6, 1.4) * (0.14 + 0.1 * (1 - sep)) * bgI)[..., None] * acc
        nx, ny = K.grid(H, W)
        il = (np.sin((ny * 90 + t * 0.6) * math.pi) > 0.985) * 0.02 * np.exp(-((ny - by) / 0.5) ** 2)
        bg += (il * bgI * (0.5 + sep))[..., None] * acc
        if p["PARTICLE_INTENSITY"] > 0:
            P = c.cache.get("dust")
            if P is None:
                P = c.cache["dust"] = E.Particles(int(160 * p["PARTICLE_INTENSITY"]), seed=24, z=(0.5, 3.0))
            x, y = P.drift(t, vel=(0.01, -0.006), turb=0.03, freq=0.3)
            bg += E.particle_layer(H, W, P, x, y, acc * 0.6 + 0.4, 1.2, 0.18, focus=1.0, dof=1.0, glow=0.6)

        # --- title channel planes
        sh = c.shaded(SATIN)
        rgb, a = sh.shade(light=(-0.3, -0.6, 0.75), base=tc, rim_gain=0.35, rim_dir=(0, -1),
                          light_gain=1.0 + 0.5 * c.hit(0.02, 0.25))
        yaw = 9.0 * sep - 5.0 * xs
        cam = c.cam(zoom=1.0 + 0.03 * K.ease_out(K.prog(t, 0, c.dur), 2), yaw=yaw, fov_scale=1.4)
        Lc = c.layer()
        La = c.layer()
        D = 0.10 * W
        s_all = sep + xs
        for i, (chn, dx, dy, dz, ry) in enumerate(LAYERS):
            ox = dx * D * s_all + dx * res * W * 0.05
            oy = dy * D * sep * 0.6
            oz = dz * H * sep * 0.5 + (0.6 * H * xs if i == 0 else (-0.35 * H * xs if i == 2 else 0.1 * H * xs))
            crgb = rgb * np.array(chn, np.float32)[None, None, :]
            c.place(Lc, cam, crgb, a, sp, 1.0, rot=(0, ry * sep, 0), off=(ox, oy, oz), opacity=vis, add=True)
            if i == 1:
                c.place(La, cam, crgb * 0, a, sp, 1.0, rot=(0, 0, 0), off=(ox, oy, oz), opacity=vis * 0.92)
        # violet depth echoes (behind), collapse with the planes
        for j, zz in enumerate((0.9, 1.6)):
            op = 0.22 * vis * min(1.0, sep * 2.5 + xs * 2)
            if op > 0.01:
                c.place(Lc, cam, rgb * acc * 0.8, a, sp, 1.0, off=(0, 0, zz * H * (sep + xs)), opacity=op, add=True)
        img = bg * (1 - La.a[..., None]) + (K.blur(Lc.rgb, 10 * k * xs) if xs > 0 else Lc.rgb)
        G = p["GLOW_STRENGTH"]
        img += K.blur(Lc.rgb, 14 * k) * 0.25 * G * (0.4 + sep + c.hit(0.02, 0.3))

        # --- alignment snap: thin light line expanding outward
        hit = c.hit(0.01, 0.35)
        if hit > 0.01:
            dt = t - imp
            wline = (0.2 + 2.6 * (1 - math.exp(-dt / 0.18))) * sp.ink_w / H
            line = np.exp(-((ny - by - sp.ink_h * 0.62 / (H / 2)) / 0.0025) ** 2) * np.exp(-(((nx - bx) / wline) ** 6))
            img += (line * hit * 1.5)[..., None] * (acc * 0.6 + 0.6)
        img = apply_shake(c, img, 0.0025, 0.12, 22)
        img = subtitle(c, img, cam, imp + 0.4, c.exit_start - 0.2, tc * 0.6 + acc * 0.15, y_rel=0.86)
        return c.finish(img, vignette=0.5, grain=0.03, bloom=(0.85, 0.4),
                        grade=dict(shadows=(0.002, 0.0, 0.006), contrast=1.05))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S = ctl("AnimStart")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        BG = ctl("BackgroundIntensity")
        u = prog(S, f"({I} - {S})")
        sep = f"pow(1 - {e_inout(u)}, 1.4)"
        res = f"(0.035*{ctl('ImpactIntensity')}*sin((time - {I})*1.833)*{decay(I, 3)})"
        xs = e_in(clamp01(f"{ex}/0.8"), 2)
        vis = f"{clamp01(f'(time - {S} + 2)/8')}*(1 - {e_inout(clamp01(f'({ex} - 0.3)/0.7'))})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "GraphiteVoid", [(0, "#040306", 1), (1, "#0b0a10", 1)])
        bg = F.light_spot(g, "VioletBacklight", bg, None, (0.5, 0.5), 1.3, 0.6, 0.6, accent=True, gain=0.5,
                          blend=f"{BG}*(0.3 + 0.2*(1 - {sep}))")
        il = X.streak_noise(g, "Interference", "#000000", "#2a2240", stretch=60, scale=40, seethe=0.05)
        bg = F.merge(g, "InterferenceMerge", bg, il, mode="Screen", blend=f"0.25*{BG}*(0.5 + {sep})")
        bg = F.particles(g, "Dust", bg, number=6, lifespan=200, velocity=0.0015, angle=30, angle_var=180, size=0.25,
                         color=(0.7, 0.65, 0.9), region="CubeRgn", region_size=(2.4, 1.4, 1.0), center_y=0.0,
                         turbulence=0.1, glow=2)

        g.at(0, 2)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Staatliches", "Regular", 0.15, 1.08,
                             color=p["TEXT_COLOR"])
        sat = F.fill_material(g, "SatinShade", title, [(0, "#8e8a99", 1), (0.5, "#ffffff", 1), (1, "#cfcad8", 1)])
        face = F.merge(g, "SatinFace", title, sat, mode="Multiply", blend=0.5)
        face = F.merge(g, "SatinRim", face, F.edge_light(g, "SatinEdge", title, 0, -0.002, accent=True, gain=0.8,
                                                           blur_px=1.0), mode="Screen", blend=0.5)
        g.at(0, 4)
        holder = F.solid(g, "PlaneHolder", (0, 0, 0), alpha=0.0)
        cur = holder
        D = 0.10
        for i, (chn, dx, dy, dz, ry) in enumerate(LAYERS):
            nm = "RGB"[i]
            ch = X.channel(g, f"Channel{nm}", face, nm)
            zsz = f"(1 - {dz * 0.25:.3f}*{sep} - {[0.35, -0.2, -0.1][i]:.2f}*{xs})"
            pl = F.xf(g, f"Plane{nm}", ch,
                      center=f"Point(0.5 + {dx * D:.4f}*({sep} + {xs}) + {dx * 0.05:.3f}*{res}, "
                             f"0.5 - {dy * D * 0.6 * 1.778:.4f}*{sep})",
                      size=zsz, angle=f"{-ry * 0.15:.2f}*{sep}")
            cur = F.merge(g, f"Plane{nm}Merge", cur, pl, mode="Screen")
        g.at(0, 6)
        for j, zz in enumerate((0.9, 1.6)):
            tint = F.cc(g, f"Echo{j}Tint", face, gain=0.8)
            tint.set(MasterRedGain=0.55, MasterGreenGain=0.42, MasterBlueGain=1.0)
            echo = F.xf(g, f"Echo{j}", tint, size=f"1 - {0.25 * zz:.2f}*({sep} + {xs})")
            cur = F.merge(g, f"Echo{j}Merge", cur, echo, mode="Screen",
                          blend=f"min({sep}*2.5 + {xs}*2, 1)")
        defoc = F.blur(g, "ExitDefocus", cur, f"12*{xs}")
        placed = F.title_placement(g, "TitlePlace", defoc, size_expr=f"1 + 0.03*{e_out(prog(0, g.frames), 2)}")
        glow = F.softglow(g, "PlaneGlow", placed, 14, gain=f"0.3*{ctl('GlowStrength')}*(0.4 + {sep} + {decay(I, 6)})",
                          threshold=0.2)
        scene = F.merge(g, "PlanesOverVoid", bg, glow, blend=vis)
        g.at(0, 8)
        line = F.accent_solid(g, "SnapLineColor", 1.6)
        lm = F.rect(g, "SnapLineShape", (0.5, 0.42), 0.2, 0.003, 0.002)
        lm.expr("Width", f"0.15 + 0.9*{e_out(prog(I, 10), 3)}", 0.2)
        F.masked(line, lm)
        scene = F.merge(g, "SnapLine", scene, line, mode="Screen", blend=f"{ctl('ImpactIntensity')}*{decay(I, 8)}")
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.028, 1.6,
                                    color=(0.78, 0.74, 0.88), y_off=-0.115)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 10", f"{ctl('ExitStart')} - 5", 14, 10))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.03, shake_frames=3, shake_amp=0.0025)
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T24()
