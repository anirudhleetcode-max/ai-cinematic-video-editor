"""T02 - Thunder God."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow
from ..fusion import ctl, prog, e_out, e_in, decay, step, window, clamp01
from ..typo import Material

GUNMETAL = Material(base=(0.30, 0.32, 0.36), spec=(0.8, 0.9, 1.0), spec_power=50, spec_gain=0.8, diffuse=0.6,
                    ambient=0.08, metal=0.7, env_sky=(0.55, 0.62, 0.75), env_horizon=(0.05, 0.06, 0.08),
                    env_ground=(0.10, 0.11, 0.13), env_sharp=10, bevel=0.05, texture="grain", tex_amount=0.08,
                    rim=(0.55, 0.75, 1.0), seed=21)


def flicker(t, seed=0.0):
    """Sporadic storm flashes in [0,1]."""
    v = math.sin(t * 1.7 + seed) * math.sin(t * 0.37 + 1 + seed) * math.sin(t * 2.9 + 2 * seed)
    return max(0.0, v - 0.55) * 3.5


class T02(Design):
    ID = "T02"
    NAME = "Thunder God"
    SLUG = "Thunder_God"
    CATEGORY = "A - Dark Mass Elevation"
    CONCEPT = "Storm-powered hero introduction: the title pushes through mist inside a living thunderstorm."
    ENTRANCE = "Title travels forward through drifting mist while electrical light crawls behind the letterforms."
    REVEAL = "A branching lightning strike behind the title flash-lights the scene and the clouds; edge arcs crackle."
    CAMERA = "Slow forward dolly with a small shock pulse (zoom kick) at the strike."
    MATERIAL = "Gunmetal with cool sky reflections and electric-blue rim; lightning drawn behind the title only."
    EXIT = "Storm calms, the title dissolves back into the clouds through a noise-driven dissolve."
    TECHNIQUES = ["layered storm clouds", "procedural lightning", "cloud internal flashes", "mist pass-through",
                  "edge arcs", "noise dissolve"]
    DEFAULTS = dict(MAIN_TITLE="THUNDER GOD", SUBTITLE="THE STORM HAS A NAME", FONT_FAMILY="bebas",
                    TEXT_COLOR="#9AA4B4", ACCENT_COLOR="#7FB6FF", ANIMATION_START=6, ANIMATION_DURATION=72,
                    IMPACT_FRAME=80, HOLD_DURATION=60, EXIT_START=154, EXIT_DURATION=34, LETTER_SPACING=0.08,
                    TITLE_WIDTH=0.6)
    SOUND = [(0, "atmos", "Storm bed: wind + distant rumble"), (0, "wind", "Wind layer"),
             (30, "thunder", "Distant thunder roll (cloud flash)"), (66, "crackle", "Electrical crackle behind letters"),
             (76, "rwhoosh", "Reverse air suck into strike"), (80, "thunder", "Lightning strike crack + boom"),
             (80, "sub", "Sub-bass accent"), (120, "crackle", "Edge arc crackle"), (154, "tail", "Storm tail")]

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        hit = c.hit(0.02, 0.22)
        after = 1.0 if t >= imp else 0.0
        calm = 1 - 0.8 * K.smooth(ex)
        zoom = 1 + 0.05 * K.ease_in_out(K.prog(t, 0, c.dur)) + 0.025 * K.pulse(t, imp, 0.03, 0.3) * p["SHAKE_AMOUNT"]

        # --- storm sky: two cloud layers with parallax
        sky = K.vgrad(H, W, (0.015, 0.02, 0.035), (0.03, 0.035, 0.05))
        fl = (flicker(t, 0.0) * 0.6 + flicker(t * 1.3, 2.1) * 0.4) * calm * (0.3 + 0.7 * K.smooth(K.prog(t, 0, 1.5)))
        cA, dA = E.clouds(H, W, t * 0.8, (0.20, 0.23, 0.30), (0.025, 0.03, 0.04), seed=3, scale=0.55, speed=0.012,
                          contrast=1.6)
        cB, dB = E.clouds(H, W, t * 1.4, (0.13, 0.15, 0.20), (0.015, 0.018, 0.025), seed=8, scale=0.9, speed=0.02,
                          contrast=1.8)
        nx, ny = K.grid(H, W)
        # internal flashes light the clouds from a moving location
        fx = math.sin(t * 0.7) * 1.1
        flash_map = K.soft_spot(H, W, fx, -0.5, 1.2, 0.7, 1.4)
        strike = hit * 2.2 + after * 0.15 * calm
        vfall = np.clip(1.15 - (ny + 1) * 0.45, 0.25, 1)[..., None]  # heavier cloud mass up high
        light = 0.3 + fl * 1.8 * flash_map + strike * K.soft_spot(H, W, c.hero()[0] / (H / 2), -0.3, 1.6, 1.0, 1.0)
        bg = sky + (cA * light[..., None] * (1 + acc * 0.3) + cB * (0.6 * light)[..., None]) * vfall
        bg = bg * bgI

        # --- lightning bolt behind the title (impact) + distant bolt at frame ~30
        def bolt(seed, x0, x1, inten, scale):
            hx = W / 2 + x0 * H / 2
            pts = E.bolt_points((hx, -20), (W / 2 + x1 * H / 2, H * 0.62), seed=seed, depth=7, rough=0.18,
                                branches=4)
            return E.draw_lines(H, W, pts, acc, width=2.6 * scale, glow=1.2, intensity=inten, core=(0.9, 0.95, 1))
        if t >= imp and t < imp + 0.5:
            env = K.pulse(t, imp, 0.01, 0.12) + 0.6 * K.pulse(t, imp + 0.12, 0.01, 0.08)
            hx = c.hero()[0] / (H / 2)
            bg += bolt(int(p["IMPACT_FRAME"]) + 3, hx + 0.15, hx - 0.1, 1.0, 1.0) * env * p["IMPACT_INTENSITY"]
        d0 = 30 / 24
        if d0 <= t < d0 + 0.3:
            bg += bolt(77, -1.4, -1.2, 0.4, 0.6) * K.pulse(t, d0, 0.01, 0.08) * bgI

        # --- title
        sp = c.title()
        sh = c.shaded(GUNMETAL)
        u = c.reveal_u()
        ue = K.ease_out(u, 3)
        zfar = 1.8 * H * (1 - ue)
        crawl_x = -0.8 + 1.6 * K.smooth(K.prog(t, c.start + 0.8, imp - c.start - 0.8))
        rim = (0.25 + 0.8 * after + 3.0 * hit) * calm
        lightdir = (-0.2 - 0.6 * hit, -0.8, 0.5)
        rgb, a = sh.shade(light=lightdir, rim_gain=rim, rim_dir=(0, -1), base=K.col(p["TEXT_COLOR"]),
                          light_gain=(0.35 + 0.65 * ue) * (0.8 + 0.6 * fl + 1.2 * hit),
                          env_shift=0.15 * math.sin(t * 0.5))
        # electrical light travelling behind the letters (rim from behind, before impact)
        if t < imp + 1.0:
            band = np.exp(-((sh.u - crawl_x) / 0.12) ** 2) * (1 - after * K.prog(t, imp, 1.0))
            rgb = rgb + (band * sh.edge * 2.5)[..., None] * acc
        cam = c.cam(zoom=zoom)
        L = c.layer()
        # dissolve exit: noise threshold on alpha
        if ex > 0:
            nz = K.sample(K.fft_noise(256, 1.8, 5), sp.h, sp.w, 3.0 * sp.h / H)
            a = a * np.clip((nz - ex * 1.2 + 0.1) * 8, 0, 1)
            rgb = rgb + (np.clip(1 - np.abs(nz - ex * 1.2 + 0.05) * 25, 0, 1) * a)[..., None] * acc * 1.5
        op = K.smooth(u * 2)
        c.place(L, cam, rgb, a, sp, 1.0, off=(0, 0, zfar), opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.5, (0, 14), 26, k)
        img = comp(bg, L)

        # edge arcs crackling along the title after impact
        if after and p["GLOW_STRENGTH"] > 0:
            r = np.random.default_rng(int(t * 24))
            if r.random() < 0.6 * calm:
                arcs = []
                for _ in range(r.integers(1, 4)):
                    gx = r.uniform(-0.45, 0.45) * sp.ink_w * cam.zoom
                    gy = (-0.5 + r.uniform(-0.05, 0.05)) * sp.ink_h * cam.zoom
                    x0, y0 = W / 2 + c.hero()[0] * cam.zoom + gx, H / 2 + c.hero()[1] * cam.zoom + gy
                    x1 = x0 + r.uniform(-60, 60) * k
                    arcs += E.bolt_points((x0, y0), (x1, y0 - r.uniform(10, 40) * k), seed=int(r.integers(1e6)),
                                          depth=4, rough=0.3, branches=0)
                img += E.draw_lines(H, W, arcs, acc, 1.0, 0.6, 0.7 * calm, (0.85, 0.92, 1.0))

        # mist in front of the title (passes through, then thins)
        mist_amt = (0.55 * (1 - K.smooth(K.prog(t, c.start + 0.6, c.reveal))) + 0.08 + 0.5 * K.smooth(ex)) * bgI
        mist = E.fog(H, W, t, (0.35, 0.40, 0.50), density=mist_amt, scale=1.4, speed=(0.03, 0.004), seed=12,
                     warp=0.12)
        img = img + mist * (0.4 + 0.8 * light[..., None] * 0.5)

        # rain-like streak specks (wind-driven) for scale
        img = img + E.rain(H, W, t, n=int(260 * p["PARTICLE_INTENSITY"]), angle=18, speed=2.2, length=0.05,
                           seed=4, color=(0.55, 0.62, 0.75), intensity=0.25 * (0.4 + fl + hit))
        # strike flash (restrained)
        img = img + acc[None, None, :] * 0.12 * hit * bgI
        sx, sy = c.shake(0.004, 0.25, 18)
        if abs(sx) + abs(sy) > 0.05:
            M = np.float32([[1.01, 0, -0.005 * W + sx], [0, 1.01, -0.005 * H + sy]])
            img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)

        ss = c.sub()
        if ss is not None:
            so = K.smooth(K.prog(t, imp + 0.5, 0.8)) * (1 - K.smooth(K.prog(t, c.exit_start - 0.3, 0.5)))
            if so > 0:
                Ls = c.layer()
                srgb = np.empty((ss.h, ss.w, 3), np.float32)
                srgb[...] = 0.55 + acc * 0.3
                c.place(Ls, cam, srgb, ss.mask, ss, 1.0, off=(0, sp.ink_h * 0.8, 0), opacity=so)
                img = comp(img, Ls)
        return c.finish(img, vignette=0.5, grain=0.03, bloom=(0.75, 0.6),
                        grade=dict(shadows=(-0.004, 0.0, 0.01), sat=0.85, contrast=1.08),
                        streak=(1.2, 0.25, 160, acc))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        g.controls(timing=dict(AnimStart=p["ANIMATION_START"], AnimDuration=p["ANIMATION_DURATION"],
                               ImpactFrame=p["IMPACT_FRAME"], ExitStart=p["EXIT_START"],
                               ExitDuration=p["EXIT_DURATION"]))
        F.accent_holder(g, p["ACCENT_COLOR"])
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        fl = "max(0, sin(time*0.0708)*sin(time*0.0154 + 1)*sin(time*0.121 + 2) - 0.55)*3.5"
        calm = f"(1 - 0.8*{ex})"

        g.at(0, 0)
        sky = F.gradient_bg(g, "StormSky", [(0, "#04050a", 1), (1, "#0a0c14", 1)])
        cl1 = F.noise(g, "CloudsFar", "#06070b", "#4b5468", detail=8, scale=1.6, seethe_rate=0.02, contrast=1.8,
                      brightness=-0.15, center="Point(0.5 + time*0.0005, 0.5)")
        bg = F.merge(g, "CloudsFarMerge", sky, cl1, mode="Screen", blend=f"0.85*{BG}")
        cl2 = F.noise(g, "CloudsNear", "#020305", "#2c3344", detail=6, scale=3.2, seethe_rate=0.03, contrast=2.2,
                      brightness=-0.25, center="Point(0.5 + time*0.0011, 0.48)")
        bg = F.merge(g, "CloudsNearMerge", bg, cl2, mode="Screen", blend=f"0.7*{BG}")
        g.at(0, 2)
        bg = F.light_spot(g, "CloudFlash", bg, None, (0.5, 0.78), 1.4, 0.6, 0.6, accent=True, gain=0.8,
                          blend=f"min({BG}*{calm}*({fl}), 1)")
        bg = F.light_spot(g, "StrikeLight", bg, None, (0.5, 0.65), 1.8, 1.0, 0.6, accent=True, gain=1.2,
                          blend=f"min({ctl('ImpactIntensity')}*{decay(I, 6)}*1.5, 1)")
        bolt_pts = [(0.62, 1.02), (0.6, 0.93), (0.635, 0.86), (0.58, 0.78), (0.605, 0.7), (0.55, 0.62),
                    (0.57, 0.55), (0.52, 0.47)]
        bm = F.polyline_mask(g, "BoltShape", bolt_pts, border=0.004, soft=0.002)
        bc = F.solid(g, "BoltCore", (0.92, 0.96, 1.0))
        F.masked(bc, bm)
        bglow = F.softglow(g, "BoltGlow", bc, 25, gain=f"2*{ctl('GlowStrength')}", threshold=0.05)
        bg = F.merge(g, "Bolt", bg, bglow, mode="Screen",
                     blend=f"{ctl('ImpactIntensity')}*min({decay(I, 3)} + 0.6*{decay(I + ' + 3', 2)}, 1)")
        bg = F.xf(g, "EnvCamera", bg, size=f"1 + 0.03*{prog(0, g.frames)}", edges=1)

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Bebas Neue", "Regular", 0.2, 1.08,
                             color=p["TEXT_COLOR"])
        refl = F.fill_material(g, "GunmetalReflect", title,
                               [(0, "#1c2028", 1), (0.45, "#5d6878", 1), (0.5, "#c6d2e2", 1), (0.56, "#2a3039", 1),
                                (1, "#11141a", 1)])
        face = F.merge(g, "FaceReflect", title, refl, mode="Multiply", blend=0.9)
        rim = F.edge_light(g, "ElectricRim", title, 0.0, -0.003, accent=True, gain=1.5, blur_px=1.5)
        face = F.merge(g, "RimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*{calm}*(0.25 + 0.75*{step(I)} + 2*{decay(I, 8)} + 0.3*{fl}), 1)")
        g.at(0, 6)
        crawl = F.light_sweep(g, "ElectricCrawl", face, title, f"{ctl('AnimStart')} + 18",
                              f"{I} - {ctl('AnimStart')} - 18", angle=0, width=0.12, peak=0.9, accent=True)
        lit = F.cc(g, "StormLighting", crawl, gain=f"(0.35 + 0.65*{e_out(u, 3)})*(0.85 + 0.4*{fl} + 0.8*{decay(I, 6)})")
        placed = F.title_placement(g, "TitleDolly", lit, size_expr=f"0.7 + 0.3*{e_out(u, 3)}")
        tglow = F.softglow(g, "TitleGlow", placed, 14, gain=f"{ctl('GlowStrength')}*(0.3 + 1.5*{decay(I, 8)})",
                           threshold=0.35)
        # noise dissolve exit
        dn = F.noise(g, "DissolveNoise", "#000000", "#ffffff", detail=4, scale=6, seethe_rate=0.0, contrast=2.5)
        dm = F.bitmap_mask(g, "DissolveMask", dn, channel="Luminance")
        dm.expr("Low", f"{ex}*0.9", 0)
        dm.expr("High", f"{ex}*0.9 + 0.08", 0.08)
        hold = F.solid(g, "TitleHolder", (0, 0, 0), alpha=0.0)
        tmask = F.merge(g, "TitleDissolve", hold, tglow)
        F.masked(tmask, dm)
        scene = F.merge(g, "TitleOverStorm", bg, tmask, blend=f"min({u}*2, 1)")

        g.at(0, 8)
        mist = F.noise(g, "Mist", "#000000", "#5a6578", detail=5, scale=2.2, seethe_rate=0.04, contrast=1.5,
                       center="Point(0.5 + time*0.0025, 0.5)")
        scene = F.merge(g, "MistMerge", scene, mist, mode="Screen",
                        blend=f"{BG}*(0.08 + 0.55*(1 - {prog(ctl('AnimStart') + ' + 14', ctl('AnimDuration'))}) + 0.5*{ex})")
        scene = F.particles(g, "WindSpecks", scene, number=18, lifespan=40, velocity=0.05, angle=-75, angle_var=6,
                            size=0.2, color=(0.6, 0.68, 0.8), region="CubeRgn", region_size=(2.4, 0.1, 1.0),
                            center_y=0.6, turbulence=0.05, glow=0)
        scene = F.impact_flash(g, "StrikeFlash", scene, color=p["ACCENT_COLOR"], peak=0.15, frames=4)
        g.at(0, 10)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.5,
                                    color=(0.66, 0.74, 0.86), y_off=-0.15)
        scene = F.merge(g, "SubtitleMerge", scene, subp,
                        blend=window(f"{I} + 12", f"{ctl('ExitStart')} - 6", 18, 12))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.05, shake_frames=6, shake_amp=0.004)
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T02()
