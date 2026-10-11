"""T13 - Titanium Edge (genuine 3D title assembled from sliding slats)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from ._b_helpers import put_title, add_sub, fam, fusion_subtitle

TITANIUM = Material(base=(0.56, 0.59, 0.63), spec=(0.80, 0.90, 1.0), spec_power=150, spec_gain=1.4, diffuse=0.55,
                    ambient=0.08, metal=0.5, env_sky=(0.80, 0.90, 1.05), env_horizon=(0.10, 0.12, 0.15),
                    env_ground=(0.24, 0.27, 0.32), env_sharp=7, bevel=0.045, bevel_round=False,
                    texture="brushed", tex_amount=0.16, bump=0.008, rim=(0.70, 0.85, 1.0), seed=53)

N_SLATS = 6
ORDER = (0, 5, 2, 3, 1, 4)  # lock order, outside-in, alternating


def slat_times(c):
    """(start, duration) in seconds for each slat; the last one locks at start+reveal."""
    R = c.reveal
    d = 0.42 * R
    st = (R - d) / (N_SLATS - 1)
    out = {}
    for j, i in enumerate(ORDER):
        out[i] = (c.start + j * st, d)
    return out


def snap(u):
    """Precise decelerating slide with a tiny mechanical overshoot at the lock."""
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    e = 1 - (1 - u) ** 4
    return e + 0.012 * math.sin(math.pi * K.clamp((u - 0.75) / 0.25)) * (u > 0.75)


class T13(Design):
    ID = "T13"
    NAME = "Titanium Edge"
    SLUG = "Titanium_Edge"
    CATEGORY = "B - Premium Materials"
    CONCEPT = "Precision-machined titanium lettering assembled like a mechanism from horizontal slats."
    ENTRANCE = ("Guide rails draw on, then six horizontal slats of the extruded titanium title slide in from "
                "alternating sides, out of depth, locking into alignment one by one with a crisp mechanical snap.")
    REVEAL = ("The final slat locks on the impact frame: a cold seam flash runs along each joint and a narrow "
              "silver-blue highlight cuts across the chamfered edges.")
    CAMERA = "Slight three-quarter angle that squares up with a measured dolly; micro-jolt on each lock."
    MATERIAL = ("Cold brushed titanium: anisotropic brushed texture, flat chamfer bevel, narrow high-exponent "
                "silver-blue specular, cool environment reflection, dark gunmetal sides.")
    EXIT = "The slats close like blinds - each band collapses to a thin line in sequence - and the rails retract."
    TECHNIQUES = ["Text3D extrusion", "rectangle-masked slats", "staggered mechanical slide", "seam flashes",
                  "narrow spec sweep", "technical grid + rails", "blinds exit"]
    TRUE_3D = True
    DURATION_FRAMES = 168
    DEFAULTS = dict(MAIN_TITLE="TITANIUM", SUBTITLE="ENGINEERED TO ENDURE", FONT_FAMILY="russo",
                    SUB_FONT_FAMILY="orbitron_med", TEXT_COLOR="#9AA3AE", ACCENT_COLOR="#8EC8FF",
                    ANIMATION_START=12, ANIMATION_DURATION=50, IMPACT_FRAME=62, HOLD_DURATION=64, EXIT_START=128,
                    EXIT_DURATION=26, LETTER_SPACING=0.07, TITLE_WIDTH=0.6, SHAKE_AMOUNT=0.6)
    FUSION_NOTES = [
        "Slats are rectangle-masked copies of the single Renderer3D output, each moved by its own Transform. "
        "If you change the title size or line count, adjust the slat masks' Center/Height (SlatNShape) so the "
        "bands still cover the letters.",
    ]
    SOUND = [(0, "atmos", "Clean cold room tone"), (2, "digital", "Guide rails draw on"),
             (12, "whoosh", "Slat 1 slide"), (19, "metal", "Lock click"), (26, "metal", "Lock click"),
             (34, "metal", "Lock click"), (41, "metal", "Lock click"), (48, "metal", "Lock click"),
             (62, "impact", "Final lock - tight impact"), (62, "metal", "Machined ring"),
             (66, "shimmer", "Edge highlight"), (128, "digital", "Blinds close ticks"), (150, "tail", "Tail")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        hit = c.hit(0.02, 0.25)
        after = 1.0 if t >= imp else 0.0
        T = K.prog(t, 0, c.dur)
        nx, ny = K.grid(H, W)
        sp = c.title()
        hx, hy = c.hero()

        # ---- environment: cold slate gradient, technical grid, guide rails
        bg = K.radial(H, W, hx / (H / 2), hy / (H / 2), 2.2, (0.07, 0.082, 0.10), (0.008, 0.01, 0.014), 1.3)
        if "grid" not in c.cache:
            g = np.zeros((H, W), np.float32)
            step_px = int(60 * k)
            g[:, ::step_px] = 1
            g[::step_px, :] = 1
            g = cv2.GaussianBlur(g, (0, 0), 0.6)
            c.cache["grid"] = g * np.exp(-(nx ** 2) / 3.0 - (ny ** 2) / 0.8)
        drift = 1 + 0.03 * T
        bg += (c.cache["grid"] * 0.025 * bgI)[..., None] * (0.5 + 0.5 * acc)
        zoom = 0.97 + 0.06 * K.ease_in_out(T, 2)
        top = H / 2 + hy - float(sp.ink_h) * 0.62 * zoom
        bot = H / 2 + hy + float(sp.ink_h) * 0.62 * zoom
        rail_in = K.ease_out(K.prog(t, 0.05, 0.45), 3)
        rail_out = K.ease_in(K.prog(t, c.exit_start + c.exit_dur * 0.4, c.exit_dur * 0.6), 2)
        rail_len = W * 0.42 * (rail_in - rail_out)
        rails = np.zeros((H, W, 3), np.float32)
        if rail_len > 2:
            for yy in (top, bot):
                cv2.line(rails, (int((W / 2 + hx - rail_len) * 4), int(yy * 4)),
                         (int((W / 2 + hx + rail_len) * 4), int(yy * 4)), (1, 1, 1), 1, cv2.LINE_AA, shift=2)
                for sx in (-1, 1):  # end ticks
                    x = W / 2 + hx + sx * rail_len
                    cv2.line(rails, (int(x * 4), int((yy - 8 * k) * 4)), (int(x * 4), int((yy + 8 * k) * 4)),
                             (1, 1, 1), 1, cv2.LINE_AA, shift=2)
        rail_lvl = (0.35 - 0.2 * after + 0.3 * hit) * bgI
        bg += (rails + K.blur(rails, 3 * k)) * acc * rail_lvl
        # scanning line sweeping during build-up
        scan = K.prog(t, 0.1, c.start + c.reveal)
        if 0 < scan < 1:
            sx_n = (-1.9 + 3.8 * scan)
            bg += (np.exp(-((nx - sx_n) / 0.004) ** 2) * np.exp(-((ny - hy / (H / 2)) / 0.35) ** 2)
                   * 0.25 * bgI)[..., None] * acc

        # ---- title: slats
        sh = c.shaded(TITANIUM)
        sw = K.prog(t, imp + 0.15, 1.1)
        sweep = (-0.8 + 1.6 * K.ease_in_out(sw), 0.025, 0.9, 2.0 * (1 if 0 < sw < 1 else 0))
        yaw = 14 * (1 - K.ease_in_out(K.prog(t, c.start, c.reveal + 0.6), 2))
        rgb, a = sh.shade(light=(-0.3 - 0.01 * yaw, -0.85, 0.45), rim_gain=0.25 + 0.6 * hit, rim_dir=(0, -1),
                          sweep=sweep, base=K.col(p["TEXT_COLOR"]), light_gain=1.35 + 0.25 * hit,
                          env_shift=0.1 * math.sin(t * 0.6))
        cam = c.cam(zoom=zoom, fov_scale=1.0, tilt=2.0)
        L = c.layer()
        ink0, ink1 = sp.ink[1] - 4, sp.ink[3] + 4
        edges = np.linspace(ink0, ink1, N_SLATS + 1)
        edges[0], edges[-1] = 0, sp.h
        times = slat_times(c)
        depth = 0.18 * float(sp.cap_px) * p["EXTRUSION_DEPTH"]
        side = np.array((0.11, 0.12, 0.135))
        seams = []
        for i in range(N_SLATS):
            t0, d = times[i]
            uu = K.prog(t, t0, d)
            if uu <= 0:
                continue
            e = snap(uu)
            dirn = -1 if i % 2 == 0 else 1
            dx = dirn * (1 - e) * W * 0.85
            dz = (1 - e) * 0.5 * H
            y0, y1 = edges[i], edges[i + 1]
            # blinds exit: band collapses about its centre line, staggered top to bottom
            eu = K.ease_in(K.prog(t, c.exit_start + i * c.exit_dur * 0.08, c.exit_dur * 0.55), 2)
            if eu > 0:
                ym = (y0 + y1) / 2
                hh = (y1 - y0) / 2 * (1 - eu)
                y0, y1 = ym - hh, ym + hh
                if hh < 0.6:
                    continue
            op = K.smooth(uu * 4)
            put_title(c, L, cam, rgb, a, sp, 1.0, rot=(0, yaw, 0), off=(dx, 0, dz), depth=depth, side=side,
                      slices=8 if uu >= 1 else 5, side_light=lambda q: 0.2 + 0.8 * q ** 2, opacity=op,
                      box=(0, int(math.floor(y0)), sp.w, int(math.ceil(y1))))
            lock = K.pulse(t, t0 + d * 0.8, 0.01, 0.12)
            if lock > 0.02 and i > 0:
                seams.append((edges[i], lock))
            if lock > 0.02 and i < N_SLATS - 1:
                seams.append((edges[i + 1], lock))
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.45, (0, 14), 18, k)
        img = comp(bg, L)
        # seam flashes along the joint lines (screen space)
        for ys, lvl in seams:
            yy = H / 2 + hy + (ys - sp.anchor[1]) * zoom
            m = (np.exp(-((K.pixgrid(H, W)[1] - yy) / (1.5 * k)) ** 2)
                 * (np.abs(K.pixgrid(H, W)[0] - W / 2 - hx) < float(sp.ink_w) * 0.55 * zoom))
            img += (m * L.a * lvl * 1.2 * p["GLOW_STRENGTH"])[..., None] * acc
        img += K.blur(np.maximum(L.rgb - 0.9, 0), 5 * k) * 0.5 * p["GLOW_STRENGTH"]
        img += (K.soft_spot(H, W, hx / (H / 2), hy / (H / 2), 1.2, 0.35, 2) * 0.06 * hit)[..., None] * acc

        img = add_sub(c, img, cam, imp + 0.35, c.exit_start - 0.1, (0.62, 0.70, 0.80), y_rel=0.92, tracking=0.7,
                      rel=0.16)
        img = apply_shake(c, img, 0.003, 0.12, 30)
        return c.finish(img, vignette=0.45, grain=0.02, bloom=(0.9, 0.4),
                        grade=dict(shadows=(-0.003, 0.0, 0.006), highlights=(-0.01, 0.0, 0.012), contrast=1.08,
                                   sat=0.85))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        A0, AD = ctl("AnimStart"), ctl("AnimDuration")
        X0, XD = ctl("ExitStart"), ctl("ExitDuration")
        ex = prog(X0, XD)
        BG = ctl("BackgroundIntensity")

        g.at(0, 0)
        bg = F.gradient_bg(g, "SlateGradient", [(0, "#151a22", 1), (1, "#020305", 1)], gtype="Radial",
                           start=(0.5, 0.5), end=(1.2, 0.0))
        grid = F.noise(g, "TechGrid", "#000000", "#2a3442", detail=1, scale=40, seethe_rate=0.0, contrast=4.0,
                       discontinuous=True)
        gm = F.ellipse(g, "GridFalloff", (0.5, 0.5), 1.6, 0.9, 0.5)
        F.masked(grid, gm)
        bg = F.merge(g, "GridMerge", bg, grid, mode="Screen", blend=f"0.25*{BG}")
        rail_in = e_out(prog(1, 11), 3)
        rail_out = e_in(prog(f"{X0} + {XD}*0.4", f"{XD}*0.6"), 2)
        for nm, yy in (("RailTop", 0.585), ("RailBottom", 0.415)):
            s = F.accent_solid(g, f"{nm}Color", 1.0)
            r = F.rect(g, f"{nm}Shape", (0.5, yy), 0.42, 0.0016, 0.0008)
            r.expr("Width", f"0.84*({rail_in} - {rail_out})", 0.84)
            F.masked(s, r)
            bg = F.merge(g, nm, bg, s, mode="Screen",
                         blend=f"{BG}*(0.35 - 0.2*{step(I)} + 0.3*{decay(I, 6)})")
        scan = F.accent_solid(g, "ScanColor", 1.0)
        sm = F.rect(g, "ScanShape", (0.5, 0.5), 0.003, 0.5, 0.004)
        sm.expr("Center", f"Point(-0.05 + 1.1*{prog(2, f'{A0} + {AD}')}, 0.5)", [0.5, 0.5])
        F.masked(scan, sm)
        bg = F.merge(g, "ScanLine", bg, scan, mode="Screen",
                     blend=f"0.3*{BG}*(1 - {step(f'{A0} + {AD}')})")

        g.at(0, 2)
        ff, fs = fam(p["FONT_FAMILY"])
        yaw = f"14*(1 - {e_inout(prog(A0, f'{AD} + 14'))})"
        render = F.text3d_rig(g, "Titanium", p["MAIN_TITLE"], ff, fs, size=0.4, extrusion=0.10, bevel=0.012,
                              color=p["TEXT_COLOR"], spec=(0.8, 0.9, 1.0), spec_exp=120, rot_y=yaw, rot_x="0",
                              tz="0", cam_z=f"4.2 - 0.25*{e_inout(prog(0, g.frames))}", cam_y="0.05",
                              key_rot=(-35, -25), key_color=(0.85, 0.92, 1.0), key_int=1.2, amb=0.1, rim=True,
                              rim_color=(0.6, 0.8, 1.0))
        g.at(0, 4)
        clear = F.solid(g, "SlatClear", (0, 0, 0), alpha=0.0)
        band_h = 0.19 / N_SLATS
        y_top = 0.5 + 0.095
        slats = clear
        for j, i in enumerate(ORDER):
            g.at(j, 5)
            t0 = f"({A0} + {j}*{AD}*0.58/{N_SLATS - 1})"
            d = f"({AD}*0.42)"
            uu = prog(t0, d)
            yc = y_top - band_h * (i + 0.5)
            hh = band_h + (0.08 if i in (0, N_SLATS - 1) else 0.0)
            ycc = yc + (0.04 if i == 0 else -0.04 if i == N_SLATS - 1 else 0.0)
            m = F.rect(g, f"Slat{i + 1}Shape", (0.5, ycc), 1.2, hh, 0.0)
            eu = e_in(prog(f"{X0} + {XD}*{0.08 * i:.2f}", f"{XD}*0.55"), 2)
            m.expr("Height", f"{hh:.4f}*(1 - {eu})", hh)
            m.expr("Center", f"Point(0.5, {ycc:.4f} + {ctl('TextPosY')} - 0.5)", [0.5, ycc])
            cut = F.merge(g, f"Slat{i + 1}Cut", clear, render)
            F.masked(cut, m)
            dirn = -1 if i % 2 == 0 else 1
            mv = F.xf(g, f"Slat{i + 1}Slide", cut, center=f"Point(0.5 + {dirn}*0.9*(1 - {e_out(uu, 4)}), 0.5)",
                      size=f"1 - 0.25*(1 - {e_out(uu, 4)})")
            slats = F.merge(g, f"Slat{i + 1}Join", slats, mv, blend=f"min({uu}*4, 1)")
        g.at(0, 7)
        swept = F.light_sweep(g, "EdgeSweep", slats, render, f"{I} + 4", 26, angle=55, width=0.025,
                              color=(0.85, 0.93, 1.0), peak=1.0)
        seam = F.edge_light(g, "SeamLight", render, 0.0, -0.002, accent=True, gain=1.4, blur_px=0.8)
        swept = F.merge(g, "SeamFlash", swept, seam, mode="Screen",
                        blend=f"min({ctl('GlowStrength')}*(0.2 + 1.2*{decay(I, 5)}), 1)*(1 - {ex})")
        scene = F.merge(g, "TitleOverSlate", bg, swept)
        scene = F.impact_flash(g, "LockFlash", scene, color=p["ACCENT_COLOR"], peak=0.06, frames=5)
        g.at(0, 9)
        scene = fusion_subtitle(g, scene, p, size=0.022, tracking=2.0, color=(0.62, 0.70, 0.80), y_off=-0.14,
                                t_in=f"{I} + 8", t_out=f"{X0} - 2")
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.04, shake_frames=3, shake_amp=0.003)
        g.output = F.finish(g, scene, vignette=0.45)


DESIGN = T13()
