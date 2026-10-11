"""T38 - Royal Insignia."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from . import _d_helpers as D

SILVER_PLATE = Material(base=(0.92, 0.9, 0.86), spec=(1.0, 0.95, 0.85), spec_power=60, spec_gain=0.7, diffuse=0.6,
                        ambient=0.12, metal=0.6, env_sky=(0.95, 0.9, 0.82), env_horizon=(0.08, 0.08, 0.12),
                        env_ground=(0.2, 0.17, 0.14), env_sharp=12, bevel=0.05, texture="none",
                        rim=(1.0, 0.85, 0.55), seed=38)

R_FRAC = 0.235  # emblem radius as a fraction of frame height


def emblem_parts():
    """Original procedural insignia, in emblem units (radius 1, y down), each
    part with its assembly time (0..1 of the reveal)."""
    rings = [(1.00, 0.030, 0.00, 1), (0.90, 0.012, 0.08, -1), (0.50, 0.010, 0.30, 1)]  # r, width, t0, sweep dir
    beads = [(0.95, i * 360 / 40) for i in range(40)]
    ticks = [(i * 15.0, 0.80, 0.86 if i % 2 else 0.88) for i in range(24)]
    leaves = []
    for side in (-1, 1):
        for j in range(9):
            a = 90 + side * (44 + j * 9.5)  # from near the bottom up the side
            ar = math.radians(a)
            for io in (-1, 1):
                r = 0.71 + io * 0.045
                cx, cy = r * math.cos(ar), r * math.sin(ar)
                ang = a + 90 + io * side * 28
                leaves.append((cx, cy, 0.075 * (1 - 0.03 * j), 0.028, ang, 0.30 + 0.03 * j + 0.012 * (io + 1)))
    chevrons = []
    for i in range(3):  # crest above the ring
        y = -1.12 - i * 0.11
        w = 0.30 - i * 0.07
        chevrons.append(([(-w, y + 0.09), (0.0, y - 0.03), (w, y + 0.09)], 0.50 + 0.07 * i, -1))
    chevrons.append(([(-0.22, 1.10), (0.0, 1.22), (0.22, 1.10)], 0.55, 1))  # base chevron
    diamonds = [((0.0, -1.52), 0.07, 0.72), ((0.0, 1.36), 0.05, 0.70)]
    bars = [(-0.36, 1.75, 0.62), (0.36, 1.75, 0.66)]  # banner rules: y, half length, t0
    return rings, beads, ticks, leaves, chevrons, diamonds, bars


def pop(u, t0, d=0.12):
    return K.ease_out(K.prog(u, t0, d), 2.5)


class T38(Design):
    ID = "T38"
    NAME = "Royal Insignia"
    SLUG = "Royal_Insignia"
    CATEGORY = "H - Signature Hero Elevations"
    CONCEPT = "An original heraldic insignia - rings, ticks, laurel arcs, chevron crest - assembles piece by piece around the title."
    ENTRANCE = ("Ordered assembly: rings sweep on, ticks and beads click around the dial, laurel leaves bloom up "
                "both sides, chevrons slide in, banner rules extend - while the whole emblem settles its rotation.")
    REVEAL = "At the impact frame the emblem locks: a gold glint sweeps it, the title appears on the banner with a light sweep."
    CAMERA = "Near-static premium framing with a very slow push; dust motes drift in the light."
    MATERIAL = "Polished gold insignia (ACCENT), embossed with a soft top light; ivory-silver title; deep royal velvet."
    EXIT = "The emblem rotates and expands past the camera while dissolving; the title fades a beat later."
    TECHNIQUES = ["procedural emblem from primitives", "staggered assembly", "emboss shading", "counter-rotating rings",
                  "light sweep / glint", "independent emblem scale & rotation controls"]
    DURATION_FRAMES = 196
    EMBLEM_SCALE = 1.0      # preview equivalents of the Fusion 'Emblem Scale' / 'Emblem Rotation' controls
    EMBLEM_ROTATION = 0.0
    DEFAULTS = dict(MAIN_TITLE="SOVEREIGN", SUBTITLE="BY ROYAL DECREE", FONT_FAMILY="cinzel_deco",
                    TEXT_COLOR="#F1ECE2", ACCENT_COLOR="#D9A84A", ANIMATION_START=8, ANIMATION_DURATION=70,
                    IMPACT_FRAME=80, HOLD_DURATION=72, EXIT_START=156, EXIT_DURATION=34, LETTER_SPACING=0.06,
                    TITLE_WIDTH=0.40, SUB_FONT_FAMILY="marcellus")
    FUSION_NOTES = ["Emblem Scale / Emblem Rotation (Look page) transform the insignia independently of the title.",
                    "The emblem colour follows the Accent Color control; the title colour is the Main Title Color."]
    SOUND = [(0, "atmos", "Regal low pad / hall ambience"), (8, "metal", "Ring sweep - metallic scrape"),
             (20, "shimmer", "Ticks clicking around the dial"), (30, "metal", "Laurel leaves chiming in"),
             (44, "whoosh", "Chevrons slide in"), (80, "impact", "Lock: deep orchestral hit + metal clang"),
             (80, "shimmer", "Gold glint"), (156, "rwhoosh", "Emblem expands away"), (175, "tail", "Hall reverb tail")]

    # ------------------------------------------------------------ preview --
    def _emblem(self, c, u, spin, glint, scale):
        """Render the emblem (half res): returns (rgb, alpha) at full res."""
        H, W, k = c.H // 2, c.W // 2, c.k / 2
        acc = K.col(c.p["ACCENT_COLOR"])
        rings, beads, ticks, leaves, chevrons, diamonds, bars = c.cache.setdefault("parts", emblem_parts())
        hx, hy = c.hero()
        cx0, cy0 = W / 2 + hx / 2, H / 2 + hy / 2
        R = R_FRAC * H * scale
        m = np.zeros((H, W), np.float32)
        rot = self.EMBLEM_ROTATION + spin[0]
        dial = spin[1]

        def P(x, y, rr=0.0):
            a = math.radians(rot + rr)  # rr: extra spin of the dial parts only
            ca, sa = math.cos(a), math.sin(a)
            return cx0 + (x * ca - y * sa) * R, cy0 + (x * sa + y * ca) * R

        S = 4  # subpixel shift
        for r, w, t0, dr in rings:
            sw = K.ease_in_out(K.prog(u, t0, 0.3), 2) * 360
            if sw <= 0:
                continue
            x, y = P(0, 0)
            cv2.ellipse(m, (int(x * S), int(y * S)), (int(r * R * S), int(r * R * S)), rot - 90, 0, dr * sw, 1.0,
                        max(1, int(w * R)), cv2.LINE_AA, shift=2)
        for i, (r, a) in enumerate(beads):
            s = pop(u, 0.12 + 0.25 * i / len(beads), 0.08)
            if s <= 0:
                continue
            x, y = P(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), dial)
            cv2.circle(m, (int(x * S), int(y * S)), max(1, int(0.012 * R * s * S)), 1.0, -1, cv2.LINE_AA, shift=2)
        for i, (a, r0, r1) in enumerate(ticks):
            s = pop(u, 0.15 + 0.3 * i / len(ticks), 0.08)
            if s <= 0:
                continue
            ar = math.radians(a)
            x0, y0 = P(r0 * math.cos(ar), r0 * math.sin(ar), -dial)
            rr = r0 + (r1 - r0) * s
            x1, y1 = P(rr * math.cos(ar), rr * math.sin(ar), -dial)
            cv2.line(m, (int(x0 * S), int(y0 * S)), (int(x1 * S), int(y1 * S)), 1.0, max(1, int(0.008 * R)),
                     cv2.LINE_AA, shift=2)
        for (lx, ly, a, b, ang, t0) in leaves:
            s = pop(u, t0, 0.12)
            if s <= 0:
                continue
            x, y = P(lx, ly)
            cv2.ellipse(m, (int(x * S), int(y * S)), (max(1, int(a * R * s * S)), max(1, int(b * R * s * S))),
                        ang + rot, 0, 360, 1.0, -1, cv2.LINE_AA, shift=2)
        for pts, t0, d in chevrons:
            s = pop(u, t0, 0.18)
            if s <= 0:
                continue
            off = d * 0.6 * (1 - s)
            arr = np.int32([[*(np.array(P(px, py + off)) * S)] for px, py in pts]).reshape(-1, 1, 2)
            cv2.polylines(m, [arr], False, float(min(1, s * 1.5)), max(1, int(0.035 * R)), cv2.LINE_AA, shift=2)
        for (dx, dy), r, t0 in diamonds:
            s = pop(u, t0, 0.12)
            if s <= 0:
                continue
            pts = [P(dx, dy - r * s), P(dx + r * 0.6 * s, dy), P(dx, dy + r * s), P(dx - r * 0.6 * s, dy)]
            cv2.fillPoly(m, [np.int32(np.array(pts) * S)], 1.0, cv2.LINE_AA, shift=2)
        for by, half, t0 in bars:
            s = K.ease_in_out(K.prog(u, t0, 0.25), 2)
            if s <= 0:
                continue
            for sgn in (-1, 1):
                x0, y0 = P(sgn * 0.08, by)
                x1, y1 = P(sgn * (0.08 + (half - 0.08) * s), by)
                cv2.line(m, (int(x0 * S), int(y0 * S)), (int(x1 * S), int(y1 * S)), 1.0, max(1, int(0.008 * R)),
                         cv2.LINE_AA, shift=2)
        # emboss shading
        mb = cv2.GaussianBlur(m, (0, 0), max(0.8, 1.6 * k * 2))
        gx = cv2.Sobel(mb, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(mb, cv2.CV_32F, 0, 1, ksize=3)
        nd = np.clip(-(gx * -0.45 + gy * -0.85) * 1.6, -1, 1)
        nx, ny = K.grid(H, W)
        sweep = np.exp(-(((nx - cx0 / (H / 2) + W / H) * 0.8 + (ny - cy0 / (H / 2) + 1) * 0.5 - glint) / 0.12) ** 2)
        shade = 0.62 + 0.55 * nd + 0.15 * np.clip(-(ny - cy0 / (H / 2) + 1), -1, 1)
        rgb = m[..., None] * (acc[None, None, :] * shade[..., None] + np.clip(nd, 0, 1)[..., None] ** 3 * 0.6
                              + sweep[..., None] * 1.2 * (acc * 0.5 + 0.5))
        Hf, Wf = c.H, c.W
        return (cv2.resize(rgb, (Wf, Hf), interpolation=cv2.INTER_LINEAR),
                cv2.resize(m, (Wf, Hf), interpolation=cv2.INTER_LINEAR))

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.03, 0.5)
        push = K.ease_in_out(K.prog(t, 0, c.dur), 2)
        locked = 1.0 if t >= imp else 0.0
        hx, hy = c.hero()
        cx, cy = hx / (H / 2), hy / (H / 2)

        # royal velvet backdrop ---------------------------------------------------
        base = c.cache.get("velvet")
        if base is None:
            dam = K.sample(K.fft_noise(256, 1.4, 38, True), H, W, 4.0)
            vel = K.radial(H, W, cx, cy, 2.2, (0.055, 0.07, 0.15), (0.008, 0.01, 0.025), 1.3) * (0.85 + 0.25 * dam)[..., None]
            aura = K.soft_spot(H, W, cx, cy, 0.8, 0.7, 1.4)[..., None] * acc
            base = c.cache["velvet"] = (vel.astype(np.float32), aura.astype(np.float32))
        bg = base[0] * bgI + base[1] * ((0.08 + 0.12 * locked + 0.2 * hit) * bgI)

        # emblem ------------------------------------------------------------------
        settle = 1 - K.ease_out(u, 3)
        spin = (-50 * settle + 60 * K.ease_in(ex, 2), 3.0 * t)  # (whole emblem, dial-only drift)
        scale = self.EMBLEM_SCALE * (1 + 0.04 * push + 0.08 * settle + 0.9 * K.ease_in(ex, 2))
        glint = -1.2 + 3.2 * K.ease_in_out(K.prog(t, imp - 0.05, 1.0))
        ergb, ea = self._emblem(c, u, spin, glint, scale)
        eop = 1 - K.smooth(K.prog(ex, 0.1, 0.7))
        bg = bg * (1 - ea[..., None] * eop * 0.9) + ergb * eop
        bg += K.blur(ergb, 10 * k) * (0.25 + 0.5 * hit) * p["GLOW_STRENGTH"] * eop

        # banner plate behind the title
        sp = c.title()
        pu = K.ease_in_out(K.prog(u, 0.6, 0.3), 2)
        R = R_FRAC * H * scale
        pw, ph = 1.75 * R * pu, 0.36 * R
        if pw > 1 and eop > 0:
            y0, y1 = int(max(0, H / 2 + hy - ph)), int(min(H, H / 2 + hy + ph))
            xs = np.arange(W, dtype=np.float32)
            X = np.clip((1 - np.abs(xs - (W / 2 + hx)) / pw) * 6, 0, 1)
            yy = np.arange(y0, y1, dtype=np.float32)
            Y = np.clip((1 - np.abs(yy - (H / 2 + hy)) / ph) * 5, 0, 1)
            pm = (Y[:, None] * X[None, :] * 0.85 * eop)[..., None]
            bg[y0:y1] = bg[y0:y1] * (1 - pm) + pm * np.array([0.010, 0.013, 0.03], np.float32)

        # title (appears at the lock)
        sh = c.shaded(SILVER_PLATE)
        sw = K.prog(t, imp + 0.1, 1.2)
        sweep = (-0.8 + 1.7 * K.ease_in_out(sw), 0.1, 0.5, 1.4 * (1 if 0 < sw < 1 else 0))
        rgb, a = sh.shade(light=(-0.2, -0.8, 0.6), rim_dir=(0, -1), rim_gain=0.5 + 0.8 * hit, sweep=sweep,
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.95, env_shift=0.05 * math.sin(t * 0.3))
        tu = K.prog(t, imp - 0.12, 0.5)
        cam = c.cam(zoom=1.0 + 0.04 * push)
        L = c.layer()
        op = K.smooth(tu) * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.3, c.exit_dur * 0.7)))
        c.place(L, cam, rgb, a, sp, 1.0 + 0.06 * (1 - K.ease_out(tu, 2)), opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.6, (0, 8), 14, k)
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.7, 0), 8 * k) * 0.5 * p["GLOW_STRENGTH"]

        nP = int(80 * p["PARTICLE_INTENSITY"])
        if nP:
            P = c.cache.get("dust")
            if P is None:
                P = c.cache["dust"] = E.Particles(nP, seed=38, z=(0.5, 3.0))
            x, y = P.drift(t, vel=(0.006, -0.012), turb=0.03, freq=0.25)
            img += E.particle_layer(H, W, P, x, y, acc * 0.8 + 0.2, 1.1, 0.3, zoom=1 + 0.04 * push, focus=1.0,
                                    dof=1.0, flicker=0.5, t=t, glow=0.8)
        img = subtitle(c, img, cam, imp + 0.5, c.exit_start, (0.86, 0.76, 0.52),
                       y_rel=0.66 * R_FRAC * H * self.EMBLEM_SCALE / max(sp.ink_h, 1), rel=0.17, tracking=0.3)
        return c.finish(img, vignette=0.55, grain=0.025, bloom=(0.8, 0.45),
                        grade=dict(shadows=(-0.002, 0.0, 0.008), highlights=(0.015, 0.008, -0.01), contrast=1.05))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p, extra=[("EmblemScale", "Emblem Scale", 1.0, 0.2, 3.0, False, "Look"),
                                    ("EmblemRotation", "Emblem Rotation", 0.0, -180, 180, False, "Look")])
        F.accent_holder(g, p["ACCENT_COLOR"], "Emblem Color")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        push = e_inout(prog(0, g.frames))
        Wd, Hd = g.W, g.H
        Rpx = R_FRAC * Hd

        def X(x):
            return 0.5 + x * Rpx / Wd

        def Y(y):
            return 0.5 - y * Rpx / Hd

        def lvl(t0, d=0.12):
            return e_out(clamp01(f"({u} - {t0:.3f})/{d}"), 2.5)

        g.at(0, 0)
        bg = F.gradient_bg(g, "RoyalVelvet", [(0, "#0e1530", 1), (1, "#020309", 1)], gtype="Radial",
                           start=(0.5, 0.5), end=(1.1, 0.5))
        dam = F.noise(g, "Damask", "#000000", "#1a2346", detail=3, scale=14, seethe_rate=0.0, contrast=1.8)
        bg = F.merge(g, "DamaskMerge", bg, dam, mode="Screen", blend=f"0.35*{BG}")
        bg = F.light_spot(g, "EmblemAura", bg, None, (0.5, 0.5), 0.9, 1.4, 0.7, accent=True, gain=0.35,
                          blend=f"{BG}*(0.25 + 0.35*{step(I)} + 0.5*{decay(I, 12)})")

        g.at(0, 2)
        rings, beads, ticks, leaves, chevrons, diamonds, bars = emblem_parts()
        chain = None

        def add(m):
            nonlocal chain
            if chain is not None:
                m.conn("EffectMask", chain, "Mask")
            chain = m
            return m

        for i, (r, w, t0, dr) in enumerate(rings):
            e = F.ellipse(g, f"Ring{i}", (0.5, 0.5), 2 * r * Rpx / Wd, 2 * r * Rpx / Hd, 0.001, border=w * Rpx / Wd)
            gs = f"(0.6 + 0.4*{lvl(t0, 0.3)})"
            e.expr("Width", f"{2 * r * Rpx / Wd:.5f}*{gs}", 2 * r * Rpx / Wd)
            e.expr("Height", f"{2 * r * Rpx / Hd:.5f}*{gs}", 2 * r * Rpx / Hd)
            e.expr("Level", lvl(t0, 0.3), 1)
            add(e)
        beadring = F.ellipse(g, "BeadRing", (0.5, 0.5), 1.9 * Rpx / Wd, 1.9 * Rpx / Hd, 0.002, border=0.004)
        beadring.expr("Level", f"0.6*{lvl(0.12, 0.25)}", 1)
        add(beadring)
        for i, (a, r0, r1) in enumerate(ticks[::2]):
            ar = math.radians(a)
            rm = (r0 + r1) / 2
            tk = F.rect(g, f"Tick{i}", (X(rm * math.cos(ar)), Y(rm * math.sin(ar))), 0.006 * Rpx / Wd * 2,
                        (r1 - r0) * Rpx / Hd, 0.0005, angle=-(a + 90))
            tk.expr("Level", lvl(0.15 + 0.3 * i / 12, 0.08), 1)
            add(tk)
        dial_gold = F.accent_solid(g, "DialGold", 1.0)
        F.masked(dial_gold, chain)
        dial = F.xf(g, "DialSpin", dial_gold, angle="-time*0.125")
        chain = None
        for i, (lx, ly, a, b, ang, t0) in enumerate(leaves):
            lf = F.ellipse(g, f"Laurel{i}", (X(lx), Y(ly)), 2 * a * Rpx / Wd, 2 * b * Rpx / Hd, 0.002, angle=-ang)
            s = lvl(t0, 0.12)
            lf.expr("Width", f"{2 * a * Rpx / Wd:.5f}*{s}", 2 * a * Rpx / Wd)
            lf.expr("Height", f"{2 * b * Rpx / Hd:.5f}*{s}", 2 * b * Rpx / Hd)
            add(lf)
        for i, (pts, t0, d) in enumerate(chevrons):
            cm = F.polyline_mask(g, f"Chevron{i}", [(X(x), Y(y)) for x, y in pts], border=0.035 * Rpx / Wd,
                                 soft=0.001)
            cm.expr("Center", f"Point(0.5, 0.5 + {-d * 0.6 * Rpx / Hd:.4f}*(1 - {lvl(t0, 0.18)}))", [0.5, 0.5])
            cm.expr("Level", f"min({lvl(t0, 0.18)}*1.5, 1)", 1)
            add(cm)
        for i, ((dx, dy), r, t0) in enumerate(diamonds):
            dm = F.closed_poly_mask(g, f"Diamond{i}", [(X(dx), Y(dy - r)), (X(dx + r * 0.6), Y(dy)), (X(dx), Y(dy + r)),
                                                       (X(dx - r * 0.6), Y(dy))])
            dm.expr("Level", lvl(t0, 0.12), 1)
            add(dm)
        for i, (by, half, t0) in enumerate(bars):
            bm = F.rect(g, f"BannerRule{i}", (0.5, Y(by)), 2 * half * Rpx / Wd, 0.008 * Rpx / Hd * 2, 0.0005)
            bm.expr("Width", f"{2 * half * Rpx / Wd:.5f}*{e_inout(clamp01(f'({u} - {t0})/0.25'))}", 0.0)
            add(bm)
        crest = F.accent_solid(g, "CrestGold", 1.0)
        F.masked(crest, chain)
        gold = F.merge(g, "EmblemAssembly", dial, crest)
        g.at(0, 4)
        emb_mat = F.fill_material(g, "GoldEmboss", gold,
                                  [(0, "#5a3b10", 1), (0.45, "#e9c46f", 1), (0.52, "#fff2c8", 1), (0.6, "#b88a34", 1),
                                   (1, "#4a300c", 1)], start=(0.5, 0.95), end=(0.5, 0.05))
        emb = F.merge(g, "EmblemMetal", gold, emb_mat, mode="Multiply", blend=0.85)
        emb = F.light_sweep(g, "EmblemGlint", emb, gold, f"{I} - 1", 24, angle=35, width=0.07, peak=1.0)
        settle = f"(1 - {e_out(u, 3)})"
        etf = F.xf(g, "EmblemTransform", emb,
                   center=f"Point({ctl('TextPosX')}, {ctl('TextPosY')})",
                   size=f"{ctl('EmblemScale')}*(1 + 0.04*{push} + 0.08*{settle} + 0.9*{e_in(ex, 2)})",
                   angle=f"{ctl('EmblemRotation')} + 50*{settle} - 60*{e_in(ex, 2)}")
        eglow = F.softglow(g, "EmblemGlow", etf, 10, gain=f"{ctl('GlowStrength')}*(0.3 + 0.6*{decay(I, 12)})",
                           threshold=0.4)
        bg = F.merge(g, "EmblemOverVelvet", bg, eglow, blend=f"1 - {clamp01(f'({ex} - 0.1)/0.7')}")

        g.at(0, 6)
        plate = F.solid(g, "BannerPlateColor", (0.012, 0.016, 0.035))
        pm = F.rect(g, "BannerPlate", (0.5, 0.5), 0.01, 2 * 0.36 * Rpx / Hd, 0.004)
        pm.expr("Center", f"Point({ctl('TextPosX')}, {ctl('TextPosY')})", [0.5, 0.5])
        pm.expr("Width", f"{2 * 1.75 * Rpx / Wd:.4f}*{ctl('EmblemScale')}*{e_inout(clamp01(f'({u} - 0.6)/0.3'))}",
                0.01)
        F.masked(plate, pm)
        bg = F.merge(g, "BannerPlateMerge", bg, plate, blend=f"0.85*(1 - {clamp01(f'({ex} - 0.1)/0.7')})")

        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Cinzel Decorative", "Black", 0.1, 1.06,
                             color=p["TEXT_COLOR"])
        refl = F.fill_material(g, "SilverPlate", title,
                               [(0, "#6b6862", 1), (0.42, "#d9d4ca", 1), (0.5, "#ffffff", 1), (0.6, "#a29c92", 1),
                                (1, "#55524d", 1)])
        face = F.merge(g, "TitleFace", title, refl, mode="Multiply", blend=0.75)
        rim = F.edge_light(g, "TitleGoldRim", title, 0.0, -0.002, accent=True, gain=1.2, blur_px=0.8)
        face = F.merge(g, "TitleRimMerge", face, rim, mode="Screen", blend=f"min({ctl('GlowStrength')}*0.6, 1)")
        face = F.light_sweep(g, "TitleSweep", face, title, f"{I} + 2", 29, angle=25, width=0.06, peak=0.9)
        tu = prog(f"{I} - 3", 12)
        placed = F.title_placement(g, "TitleOnBanner", face, size_expr=f"1 + 0.06*(1 - {e_out(tu, 2)})")
        scene = F.merge(g, "TitleOverEmblem", bg, placed,
                        blend=f"{tu}*(1 - {clamp01(f'({ex} - 0.3)/0.7')})")
        g.at(0, 8)
        scene = F.particles(g, "GoldDust", scene, number=6, lifespan=180, velocity=0.0015, angle=90, angle_var=60,
                            size=0.25, color=p["ACCENT_COLOR"], region="CubeRgn", region_size=(2.2, 1.4, 1.0),
                            center_y=0.0, turbulence=0.07, glow=3)
        scene = F.impact_flash(g, "LockFlash", scene, color=p["ACCENT_COLOR"], peak=0.08, frames=6)
        scene = D.f_sub(g, p, "Marcellus SC", "Regular", (0.86, 0.76, 0.52), -0.66 * R_FRAC, f"{I} + 12",
                        f"{ctl('ExitStart')}", size=0.02, tracking=1.3, scene=scene)
        scene = F.xf(g, "Camera", scene, size=f"1 + 0.04*{push}", edges=1)
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T38()
