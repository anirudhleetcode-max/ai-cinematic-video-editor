"""T21 - Neon Overdrive."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, apply_shake, subtitle
from ..fusion import ctl, prog, e_out, e_inout, decay, step, window, clamp01
from . import _c_helpers as X

COOL = (0.22, 0.36, 1.0)  # fixed secondary of the controlled palette (grid far lines / horizon)


class T21(Design):
    ID = "T21"
    NAME = "Neon Overdrive"
    SLUG = "Neon_Overdrive"
    CATEGORY = "C - Future Tech and Kinetic Camera"
    CONCEPT = "A night-drive title: neon tubes ignite around the letterforms above a receding light grid."
    ENTRANCE = ("Camera glides over a receding neon floor grid (fast, then decelerating) while a neon tube traces "
                "the letter edges left-to-right with short starter flickers.")
    REVEAL = "At the impact frame the letter faces power up with a single digital slice-distortion hit."
    CAMERA = "Low forward glide over the grid that brakes into a slow drift; no shake (energy is in the light)."
    MATERIAL = "Dark glass faces that fill with cool white light; magenta (ACCENT) neon tube inside the letter edge."
    EXIT = "Power-down: the tubes cut out right-to-left with a stutter, faces drain, the grid goes dark from the horizon."
    TECHNIQUES = ["perspective floor grid", "edge-tube draw-on", "starter flicker", "slice distortion",
                  "floor glow pool", "power-down wipe"]
    DURATION_FRAMES = 168
    DEFAULTS = dict(MAIN_TITLE="OVERDRIVE", SUBTITLE="MAXIMUM VOLTAGE", FONT_FAMILY="audiowide",
                    TEXT_COLOR="#EEF3FF", ACCENT_COLOR="#FF2E93", ANIMATION_START=8, ANIMATION_DURATION=46,
                    IMPACT_FRAME=60, HOLD_DURATION=64, EXIT_START=126, EXIT_DURATION=32, LETTER_SPACING=0.06,
                    TITLE_WIDTH=0.66, TEXT_POSITION_Y=0.56, SHADOW_STRENGTH=0.0)
    SOUND = [(0, "atmos", "Low synth drone bed"), (6, "riser", "Electric riser under the glide (frames 6-60)"),
             (10, "crackle", "Neon starter ticks as the tube traces"), (56, "rwhoosh", "Reverse suck into power-up"),
             (60, "impact", "Synth-bass hit: faces power up"), (60, "glitch", "Short digital slice glitch"),
             (61, "sub", "Sub drop"), (126, "digital", "Power-down stutter"), (140, "tail", "Electric hum tail")]
    FUSION_NOTES = ["Floor grid lines are PolylineMask/RectangleMask shapes in the 'FloorGrid*' nodes; move "
                    "'GridLinesV*' points to change the vanishing point."]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        cool = K.col(COOL)
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        after = 1.0 if t >= imp else 0.0
        hit = c.hit(0.01, 0.18)
        sp = c.title()
        hx, hy = c.hero()

        # --- glide: fast scroll that brakes into a drift
        scroll = 1.5 * (1 - math.exp(-max(t - 0.0, 0) / 1.1)) + 0.16 * t
        drift = 6 * k * math.sin(t * 0.4)
        grid_off = K.smooth(K.prog(ex, 0.2, 0.75))  # grid goes dark after the tubes
        env_on = K.smooth(K.prog(t, 0, 0.8)) * (1 - grid_off)

        bg = K.vgrad(H, W, (0.004, 0.003, 0.012), (0.008, 0.004, 0.014))
        yh = H / 2 + hy + max(0.19 * H, sp.ink_h * 1.3)  # horizon under the title + subtitle
        vx = W / 2 + hx + drift
        nx, ny = K.grid(H, W)
        yhn = (yh - H / 2) / (H / 2)
        sky = np.exp(-np.maximum(yhn - ny, 0) / 0.18) * (ny < yhn)
        bg += (sky * 0.10 * env_on)[..., None] * (acc * 0.5 + cool * 0.5) * bgI
        hl = np.exp(-((ny - yhn) / 0.008) ** 2) * np.exp(-(nx / 1.6) ** 2)
        bg += (hl * 0.55 * env_on)[..., None] * (acc * 0.7 + 0.3) * bgI

        # --- floor grid (vertical rays + scrolling depth lines)
        segs, ints, colsA = [], [], []
        for i in range(-22, 23):
            segs.append(((vx, yh), (vx + i * 0.13 * W, H + 40 * k)))
            ints.append(0.5 if i % 4 else 0.9)
        nlines = 12
        for j in range(nlines):
            q = X.frac(j / nlines + scroll)
            dist = 1 + 14 * (1 - q)
            y = yh + (H * 1.05 - yh) / dist
            fade = min(1.0, q * 3) * (1 - max(0.0, q - 0.92) / 0.08)
            segs.append(((0, y), (W, y)))
            ints.append(1.2 * fade / (0.5 + 0.5 * dist ** 0.5))
        gl = X.lines_buf(H, W, segs, (1, 1, 1), 1.4, k, ints)
        floor = np.clip((ny - yhn) / max(1e-3, 1 - yhn), 0, 1)
        gcol = (acc[None, None, :] * floor[..., None] + cool[None, None, :] * (1 - floor[..., None]) * 0.9)
        gl = gl[..., :1] * gcol * (floor ** 0.5)[..., None]
        # power-down: grid extinguishes from the horizon outward
        if grid_off > 0:
            gl = gl * np.clip((floor - grid_off * 1.1) * 6, 0, 1)[..., None]
        grid = gl * 1.3 * env_on * bgI
        bg += grid + K.blur(grid, 5 * k) * 1.2

        # --- title: tube draw-on, starter flicker, power-up, power-down
        sh = X.inner_edge(sp, 0.045)
        su = (np.arange(sp.w, dtype=np.float32) - sp.anchor[0]) / max(1.0, sp.ink_w)  # -0.5..0.5
        lead = -0.62 + 1.25 * K.ease_in_out(u, 2)
        lead_off = 0.62 - 1.3 * K.ease_in(K.prog(ex, 0.0, 0.7), 1.6)
        vis = np.clip((lead - su) * 18, 0, 1) * np.clip((lead_off - su) * 18, 0, 1)
        # starter flicker on the freshly lit section and on the cut-out edge
        fk = 0.5 + 0.5 * math.sin(t * 61.0) * math.sin(t * 23.0 + 1.3)
        near = np.exp(-((su - lead) / 0.12) ** 2) * (1 - after)
        near2 = np.exp(-((su - lead_off) / 0.10) ** 2) * (1.0 if ex > 0 else 0.0)
        vis = vis * (1 - (near + near2) * (1 - fk) * 0.9)
        tube = sh * vis[None, :]
        fill = (0.04 + 0.86 * K.ease_out(K.prog(t, imp, 0.35), 2) * after) * (1 - K.smooth(K.prog(ex, 0.1, 0.6)))
        face = X.vband(sp, K.col(p["TEXT_COLOR"]), K.col(p["TEXT_COLOR"]) * 0.55) * fill
        face = face + (0.012 + 0.02 * u)  # dark glass ambient
        tube_rgb = (acc * 1.6 + 0.35)[None, None, :] * tube[..., None]
        core = np.clip(tube - 0.55, 0, 1)[..., None] * 1.2  # hot white core
        rgb = face * (1 - tube[..., None]) + tube_rgb + core
        a = sp.mask

        zt = 0.35 * H * (1 - K.ease_out(u, 3))
        cam = c.cam(zoom=1.0 + 0.035 * K.ease_out(K.prog(t, 0, c.dur), 2), pan=(-drift * 0.3, 0))
        L = c.layer()
        c.place(L, cam, rgb, a, sp, 1.0, off=(0, 0, zt), opacity=min(1.0, u * 4 + 0.02))
        # emissive layer for glow (tube + face light)
        Le = c.layer()
        c.place(Le, cam, tube_rgb + face * 0.35, a, sp, 1.0, off=(0, 0, zt), opacity=1.0, add=True)
        img = comp(bg, L)
        G = p["GLOW_STRENGTH"]
        img += (K.blur(Le.rgb, 6 * k) * 0.9 + K.blur(Le.rgb, 26 * k) * 0.6) * G
        # floor glow pool under the title (reflected light)
        pool = K.soft_spot(H, W, (hx) / (H / 2), yhn + 0.06, sp.ink_w / H * 1.1, 0.07, 1.6) * (ny > yhn)
        lvl = (0.10 * u + 0.22 * fill) * (1 - grid_off)
        img += (pool * lvl * bgI)[..., None] * (acc * 0.6 + K.col(p["TEXT_COLOR"]) * 0.25)

        # --- digital distortion: one purposeful hit at ignition-complete + impact
        g_amt = hit * 1.0 + 0.35 * K.pulse(t, c.start + c.reveal * 0.98, 0.01, 0.08) * p["IMPACT_INTENSITY"]
        g_amt += 0.5 * K.pulse(t, c.exit_start, 0.01, 0.1) * p["IMPACT_INTENSITY"]
        if g_amt > 0.03:
            img = X.glitch_slices(img, min(1.0, g_amt), seed=int(t * 12), k=k, n=4)
            img = X.rgb_split(img, 5 * k * min(1.0, g_amt))

        img = subtitle(c, img, cam, imp + 0.4, c.exit_start - 0.1, K.col(p["TEXT_COLOR"]) * 0.55 + acc * 0.25,
                       y_rel=0.95)
        img = X.grade_fast(img, shadows=(0.0, -0.002, 0.008), contrast=1.04)
        return c.finish(img, vignette=0.5, grain=0.03, bloom=(0.85, 0.45))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        grid_off = e_inout(clamp01(f"({ex} - 0.2)/0.75"))
        env_on = f"{clamp01('time/20')}*(1 - {grid_off})"

        # environment -------------------------------------------------
        g.at(0, 0)
        bg = F.gradient_bg(g, "NightGradient", [(0, "#010103", 1), (0.6, "#030208", 1), (1, "#020104", 1)])
        hy = 0.37  # horizon (title sits at TextPosY 0.56 by default) (Fusion y up)
        bg = F.light_spot(g, "HorizonLine", bg, None, (0.5, hy), 1.8, 0.008, 0.01, accent=True, gain=0.8,
                          blend=f"0.6*{BG}*{env_on}")
        bg = F.light_spot(g, "SkyGlow", bg, COOL, (0.5, hy + 0.05), 1.9, 0.22, 0.6, gain=0.3,
                          blend=f"0.25*{BG}*{env_on}")
        g.at(0, 2)
        masks = []
        for i in range(-7, 8):
            masks.append(X.seg_mask(g, f"GridLinesV{i + 7}", (0.5, hy), (0.5 + i * 0.12, -0.05), border=0.0012))
        # depth lines: positions scroll with a braking glide (fast, then slow)
        scroll = "(1.5*(1 - pow(2.718282, -time/26)) + 0.0067*time)"
        n = 8
        for j in range(n):
            q = f"({j / n:.4f} + {scroll} - floor({j / n:.4f} + {scroll}))"
            d = f"(1 + 14*(1 - {q}))"
            m = F.rect(g, f"GridLineH{j}", (0.5, 0.2), 2.0, 0.002, 0.001)
            m.expr("Center", f"Point(0.5, {hy} - ({hy} + 0.05)/{d})", [0.5, 0.2])
            m.expr("Height", f"0.0012 + 0.003/{d}", 0.002)
            masks.append(m)
        grid_mask = X.chain(masks)
        floor_fade = F.rect(g, "FloorGridFade", (0.5, hy / 2), 2.0, hy, 0.12)
        floor_fade.set(PaintMode=F.FuID("Multiply"))
        floor_fade.conn("EffectMask", grid_mask, "Mask")
        gsol = F.accent_solid(g, "FloorGridColor", 1.0)
        F.masked(gsol, floor_fade)
        gglow = F.softglow(g, "FloorGridGlow", gsol, 6, gain=f"0.8*{ctl('GlowStrength')}", threshold=0.05)
        bg = F.merge(g, "FloorGrid", bg, gglow, mode="Screen", blend=f"min(1.0*{BG}*{env_on}, 1)")
        bg = F.xf(g, "GlideCamera", bg, center=f"Point(0.5 + 0.003*sin(time*0.0167), 0.5)",
                  size=f"1 + 0.03*{e_out(prog(0, g.frames), 2)}", edges=1)

        # title -------------------------------------------------------
        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Audiowide", "Regular", 0.12, 1.06,
                             color=p["TEXT_COLOR"])
        fill = (f"(0.04 + 0.86*{e_out(prog(I, 8), 2)}*{step(I)})*(1 - {e_inout(clamp01(f'({ex} - 0.1)/0.6'))})")
        face_cc = F.cc(g, "FacePower", title, gain=fill)
        g.at(0, 5)
        tblur = F.blur(g, "TubeErode", title, 5)
        m1 = F.bitmap_mask(g, "TubeOuter", title)
        m2 = F.bitmap_mask(g, "TubeInner", tblur, paint="Subtract", prev=m1)
        m2.set(Low=0.82, High=0.97)
        lead = f"(-0.02 + 1.07*{e_inout(u)} - 1.1*pow({clamp01(f'{ex}/0.7')}, 1.6))"
        draw = F.rect(g, "TubeDrawOn", (0.5, 0.5), 2.0, 2.0, 0.02)
        draw.expr("Center", f"Point({lead} - 1, 0.5)", [0.5, 0.5])
        draw.set(PaintMode=F.FuID("Multiply"))
        draw.conn("EffectMask", m2, "Mask")
        tube = F.accent_solid(g, "TubeColor", 1.6)
        F.masked(tube, draw)
        flick = (f"(1 - 0.85*(1 - {step(I)})*{clamp01(f'{u}*30')}*max(0, sin(time*2.54)*sin(time*0.96 + 1.3)))")
        g.at(0, 6)
        tglow = F.softglow(g, "TubeGlow", tube, 10, gain=f"1.4*{ctl('GlowStrength')}", threshold=0.05)
        lit = F.merge(g, "TubeOverFace", face_cc, tglow, mode="Screen", blend=flick)
        placed = F.title_placement(g, "TitleGlide", lit, size_expr=f"0.78 + 0.22*{e_out(u, 3)}")
        halo = F.softglow(g, "FaceHalo", placed, 22, gain=f"0.5*{ctl('GlowStrength')}*(0.3 + {decay(I, 10)})",
                          threshold=0.3)
        scene = F.merge(g, "TitleOverGrid", bg, halo, blend=f"min({u}*4 + 0.02, 1)")
        scene = F.light_spot(g, "FloorPool", scene, None, (0.5, hy - 0.03), 0.55, 0.06, 0.08, accent=True,
                             gain=0.7, blend=f"{BG}*(0.1*{u} + 0.22*{step(I)}*(1 - {ex}))")

        # digital slice distortion --------------------------------------
        g.at(0, 8)
        gl = f"{ctl('ImpactIntensity')}*({decay(I, 4)} + 0.5*{decay(ctl('ExitStart'), 3)})"
        for i, (y, h, dx) in enumerate(((0.53, 0.03, 0.04), (0.47, 0.018, -0.06), (0.5, 0.012, 0.025))):
            sl = F.xf(g, f"SliceShift{i}", scene, center=f"Point(0.5 + {dx}*{gl}, 0.5)")
            band = F.rect(g, f"SliceBand{i}", (0.5, y), 2.0, h, 0.0)
            F.masked(sl, band)
            scene = F.merge(g, f"Slice{i}", scene, sl, blend=f"min({gl}*4, 1)")

        g.at(0, 10)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.5,
                                    color=(0.78, 0.7, 0.86), y_off=-0.125)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 10", f"{ctl('ExitStart')} - 2", 14, 10))
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T21()
