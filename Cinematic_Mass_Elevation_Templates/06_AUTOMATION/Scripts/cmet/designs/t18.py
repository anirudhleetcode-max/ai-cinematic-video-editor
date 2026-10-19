"""T18 - Dark Sorcery (2.5D)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from ._b_helpers import put_title, add_sub, fam, fusion_subtitle

HEXSILVER = Material(base=(0.30, 0.30, 0.34), spec=(0.85, 0.80, 1.0), spec_power=60, spec_gain=0.7, diffuse=0.55,
                     ambient=0.05, metal=0.55, env_sky=(0.45, 0.42, 0.55), env_horizon=(0.02, 0.015, 0.03),
                     env_ground=(0.10, 0.08, 0.14), env_sharp=9, bevel=0.06, bevel_round=True, texture="obsidian",
                     tex_amount=0.10, bump=0.02, rim=(0.75, 0.55, 1.0), seed=101)

N_OUTER, N_INNER = 18, 11
FLOOR_DY, FLOOR_SQ = 0.50, 0.28  # floor-circle offset below the title (half heights) and squash


def make_runes(seed, n):
    """Original procedural runes: each is 2-4 strokes between nodes of a 3x4 lattice
    (vertical stem always present), so every glyph is angular, symmetric-ish and unique."""
    r = np.random.default_rng(seed)
    nodes = [(x, y) for y in (0.0, 0.33, 0.66, 1.0) for x in (-0.5, 0.0, 0.5)]
    runes = []
    for _ in range(n):
        strokes = [((0.0, 0.0), (0.0, 1.0))]
        for _ in range(r.integers(2, 4)):
            a, b = r.choice(len(nodes), 2, replace=False)
            pa, pb = nodes[a], nodes[b]
            if r.random() < 0.5:  # mirror for a ritual symmetry
                strokes.append(((-pa[0], pa[1]), (-pb[0], pb[1])))
            strokes.append((pa, pb))
        if r.random() < 0.35:
            strokes.append(((-0.35, 0.5), (0.35, 0.5)))
        runes.append(strokes)
    return runes


RUNES_OUT = make_runes(7, N_OUTER)
RUNES_IN = make_runes(13, N_INNER)


class T18(Design):
    ID = "T18"
    NAME = "Dark Sorcery"
    SLUG = "Dark_Sorcery"
    CATEGORY = "D - Mythic, Epic and Fantasy"
    CONCEPT = "An occult invocation: a ritual circle of original runes ignites in swirling smoke and summons the title."
    ENTRANCE = ("Smoke spirals inward around a vertical ritual circle whose rings trace on and whose runes ignite "
                "one by one; the letters condense out of the vortex through a spiral, edge-glowing dissolve.")
    REVEAL = ("At the impact frame the circle flares, an energy ring pulses outward and the runes burn bright, "
              "then settle to a slow, breathing glow behind a smoked-silver title.")
    CAMERA = "Locked-off with a slow creeping push and a subtle counter-rotation of the circle layers."
    MATERIAL = ("Smoked dark silver with violet rim light and faint inner glow along the edges; glowing runes and "
                "rings are emissive and drawn behind the title only.")
    EXIT = "The circle collapses inward and the title is twisted into the vortex and swallowed by the smoke."
    TECHNIQUES = ["procedural original runes", "concentric energy rings", "polar smoke vortex", "spiral dissolve",
                  "energy pulse ring", "swirl-warp exit"]
    TRUE_3D = False
    DURATION_FRAMES = 192
    DEFAULTS = dict(MAIN_TITLE="SORCERY", SUBTITLE="THE OLD MAGIC WAKES", FONT_FAMILY="marcellus",
                    SUB_FONT_FAMILY="cinzel_bold", TEXT_COLOR="#ABA6BC", ACCENT_COLOR="#9A66FF",
                    ANIMATION_START=8, ANIMATION_DURATION=72, IMPACT_FRAME=82, HOLD_DURATION=62, EXIT_START=146,
                    EXIT_DURATION=34, LETTER_SPACING=0.10, TITLE_WIDTH=0.58, SHAKE_AMOUNT=0.5, TEXT_POSITION_Y=0.55)
    FUSION_NOTES = [
        "The Fusion version draws 6 representative runes as PolylineMasks on a rotating Transform; the preview "
        "renders the full 29-rune circle. Add or reshape runes by editing the RuneN polylines.",
    ]
    SOUND = [(0, "atmos", "Dark drone, low choir"), (0, "wind", "Swirling wind"), (10, "whoosh", "Smoke spiral"),
             (20, "digital", "Rune ignitions (soft ticks)"), (40, "heartbeat", "Ritual heartbeat"),
             (64, "riser", "Invocation riser"), (82, "impact", "Arcane impact"), (82, "swell", "Choir swell"),
             (84, "shimmer", "Energy ring"), (146, "rwhoosh", "Vortex suck"), (170, "tail", "Dark tail")]

    # ------------------------------------------------------------ preview --
    def draw_circle(self, c, R, rot, lvl_outer, lvl_inner, draw_u, flare, collapse):
        H, W, k = c.H, c.W, c.k
        S = int(900 * k)
        buf = np.zeros((S, S), np.float32)
        hx, hy = c.hero()
        cx, cy = S / 2, S / 2
        Rp = R * (1 - collapse) * H / 4  # half-res pixels
        lt = cv2.LINE_AA
        out_shape = (W // 2, H // 2)
        if Rp < 2:
            return np.zeros((H // 2, W // 2), np.float32)
        sweep = 360 * K.clamp(draw_u * 1.25)
        for rr, w in ((1.0, 2), (0.93, 1), (0.70, 1), (0.64, 2), (0.40, 1)):
            cv2.ellipse(buf, (int(cx * 4), int(cy * 4)), (int(Rp * rr * 4), int(Rp * rr * 4)), rot * (1 if rr > 0.6
                        else -1.4), 0, sweep, 1.0, max(1, int(w * 2 * k)), lt, shift=2)
        # spokes between the inner rings (hexagram-like star, original arrangement)
        if draw_u > 0.5:
            pts = []
            for i in range(7):
                a = math.radians(rot * -1.4 + i * 360 / 7 * 3)
                pts.append((cx + math.cos(a) * Rp * 0.64, cy + math.sin(a) * Rp * 0.64))
            arr = (np.array(pts) * 4).astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(buf, [arr], True, 0.6 * K.smooth((draw_u - 0.5) * 2), max(1, int(2 * k)), lt, shift=2)
        # runes on the outer band and inner band
        for runes, rad, sz, lvl, sgn in ((RUNES_OUT, 0.815, 0.075, lvl_outer, 1), (RUNES_IN, 0.52, 0.06, lvl_inner,
                                                                                    -1.4)):
            n = len(runes)
            for i, strokes in enumerate(runes):
                ig = K.clamp((draw_u * 1.3 - i / n) * 4)
                if ig <= 0:
                    continue
                a = math.radians(rot * sgn + i * 360 / n)
                ca, sa = math.cos(a), math.sin(a)
                ox, oy = cx + ca * Rp * rad, cy + sa * Rp * rad
                s = Rp * sz
                # glyph "up" points outward from the centre
                ux, uy = ca, sa
                vx, vy = -sa, ca
                flick = lvl * ig * (0.8 + 0.2 * math.sin(c.t * 5 + i * 1.7))
                for (p0, p1) in strokes:
                    q = []
                    for (gx, gy) in (p0, p1):
                        q.append((ox + (gx * vx + (gy - 0.5) * ux) * s * 2, oy + (gx * vy + (gy - 0.5) * uy) * s * 2))
                    cv2.line(buf, (int(q[0][0] * 4), int(q[0][1] * 4)), (int(q[1][0] * 4), int(q[1][1] * 4)),
                             min(2.0, flick + flare), max(1, int(2.5 * k)), lt, shift=2)
        # lay the circle flat on the floor under the title (perspective squash)
        tcx, tcy = (W / 2 + hx) / 2, (H / 2 + hy) / 2 + FLOOR_DY * H / 4
        M = np.float32([[1, 0, tcx - S / 2], [0, FLOOR_SQ, tcy - S / 2 * FLOOR_SQ]])
        buf = cv2.GaussianBlur(buf, (0, 0), 0.9)
        return cv2.warpAffine(buf, M, out_shape, flags=cv2.INTER_AREA)

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        acc2 = np.clip(acc[[1, 2, 0]] * 0.5 + K.col((0.2, 0.9, 0.6)) * 0.5, 0, 1)  # secondary eerie tint
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.02, 0.4)
        after = 1.0 if t >= imp else 0.0
        T = K.prog(t, 0, c.dur)
        hx, hy = c.hero()
        sp = c.title()
        if "polar" not in c.cache:
            xs, ys = K.pixgrid(H // 2, W // 2)
            dx, dy = xs - (W / 2 + hx) / 2, ys - (H / 2 + hy) / 2
            c.cache["polar"] = (np.sqrt(dx * dx + dy * dy).astype(np.float32) / (H / 2),
                                np.arctan2(dy, dx).astype(np.float32))
        rad, ang = c.cache["polar"]

        # ---- vortex smoke (polar fbm) in deep violet-black
        swirl = 0.35 * t + 1.6 / (0.35 + rad) * (0.25 + 0.35 * K.smooth(ex))
        if "smoketex" not in c.cache:
            c.cache["smoketex"] = K.fft_noise(256, 2.2, 103)
        tex = c.cache["smoketex"]
        uu = ((ang + swirl) / (2 * math.pi)) % 1.0
        vv = (np.log(rad + 0.05) * 0.35 + 0.08 * t) % 1.0
        sm = cv2.remap(tex, (uu * 256).astype(np.float32), (vv * 256).astype(np.float32), cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_WRAP)
        sm = np.clip((sm - 0.42) * 2.2, 0, 1) ** 1.4 * np.clip(rad * 1.5, 0.2, 1.0)
        smoke = cv2.resize(sm, (W, H), interpolation=cv2.INTER_LINEAR)
        bg = K.radial(H, W, hx / (H / 2), hy / (H / 2), 1.8, (0.035, 0.02, 0.05), (0.004, 0.003, 0.006), 1.3)
        bg = bg + smoke[..., None] * (K.col((0.10, 0.08, 0.13)) + acc * 0.05) * bgI

        # ---- ritual circle (behind the title)
        draw_u = K.prog(t, c.start, c.reveal * 0.85)
        collapse = K.ease_in(K.prog(t, c.exit_start, c.exit_dur * 0.6), 2.5)
        lvl = (0.35 + 0.25 * after + 0.1 * math.sin(t * 2.2)) * (1 - collapse)
        rot = 6 * t + 30 * collapse
        circ = self.draw_circle(c, 1.45, rot, lvl, lvl * 0.8, draw_u, 1.2 * hit, collapse)
        circ = cv2.resize(circ, (W, H), interpolation=cv2.INTER_LINEAR)
        cglow = K.blur(circ, 4 * k) * 1.2 + K.blur(circ, 16 * k) * 0.9
        bg += (circ[..., None] * (acc * 0.5 + 0.55) + cglow[..., None] * acc) * 0.8 * p["GLOW_STRENGTH"] * bgI
        # outward energy ring at impact
        ru = K.prog(t, imp, 0.9)
        if 0 < ru < 1:
            ring = E.ring(H, W, hx / (H / 2), hy / (H / 2) + FLOOR_DY, 0.1 + 0.7 * K.ease_out(ru, 2), 0.008 + 0.02 * ru,
                          aspect=1 / FLOOR_SQ)
            bg += (ring * (1 - ru) * 1.1 * p["IMPACT_INTENSITY"])[..., None] * (acc * 0.7 + acc2 * 0.3)

        # ---- title: spiral dissolve in, swirl out
        sh = c.shaded(HEXSILVER)
        rgb, a = sh.shade(light=(-0.3, -0.8, 0.5), rim_gain=0.4 + 0.9 * hit + 0.25 * after, rim_dir=(0, -1),
                          base=K.col(p["TEXT_COLOR"]), light_gain=1.1 + 0.3 * hit,
                          emissive=(sh.edge * (0.25 + 0.6 * hit) * (0.6 + 0.4 * math.sin(t * 2.2)))[..., None] * acc)
        if "dissolve" not in c.cache:
            uS, vS = sh.u, sh.v * float(sp.ink_h) / max(1.0, float(sp.ink_w))
            r_ = np.sqrt(uS * uS + vS * vS)
            th = np.arctan2(vS, uS)
            nz = K.sample(K.fft_noise(256, 1.8, 104), sp.h, sp.w, 3.5 * sp.h / H)
            c.cache["dissolve"] = (((th / (2 * math.pi)) % 1.0) * 0.35 + r_ * 0.9 + nz * 0.45).astype(np.float32)
        dmap = c.cache["dissolve"]
        thr = K.ease_in_out(K.prog(t, c.start + c.reveal * 0.25, c.reveal * 0.75), 2) * 1.55
        reveal = np.clip((thr - dmap) * 10, 0, 1)
        front = np.clip(1 - np.abs(thr - dmap - 0.05) * 14, 0, 1) * (thr < 1.5)
        a2 = a * reveal
        rgb2 = rgb + (front * a)[..., None] * (acc * 1.6 + 0.2)
        cam = c.cam(zoom=1.0 + 0.05 * K.ease_in_out(T, 2))
        L = c.layer()
        depth = 0.07 * float(sp.cap_px) * p["EXTRUSION_DEPTH"]
        put_title(c, L, cam, rgb2, a2, sp, 1.0 - 0.6 * K.ease_in(ex, 2), rot=(0, 0, -40 * K.ease_in(ex, 2)),
                  depth=depth, side=np.array((0.05, 0.04, 0.07)), slices=5, opacity=1 - K.smooth(K.prog(
                      t, c.exit_start + c.exit_dur * 0.5, c.exit_dur * 0.5)))
        if ex > 0:  # swirl the title layer into the vortex
            xs, ys = K.pixgrid(H, W)
            cxp, cyp = W / 2 + hx, H / 2 + hy
            dx, dy = xs - cxp, ys - cyp
            rr = np.sqrt(dx * dx + dy * dy) / (H / 2)
            tw = K.ease_in(ex, 1.6) * 3.0 * np.exp(-rr * 1.2)
            cs, sn = np.cos(tw), np.sin(tw)
            mx = (cxp + dx * cs - dy * sn).astype(np.float32)
            my = (cyp + dx * sn + dy * cs).astype(np.float32)
            L.rgb = cv2.remap(L.rgb, mx, my, cv2.INTER_LINEAR)
            L.a = cv2.remap(L.a, mx, my, cv2.INTER_LINEAR)
        # dark smoky halo behind the letters keeps them readable over the runes
        halo = K.blur(L.a, 26 * k)
        bg = bg * (1 - np.clip(halo * 0.75, 0, 0.8))[..., None]
        img = comp(bg, L)
        img += K.blur(np.maximum(L.rgb - 0.6, 0), 8 * k) * 0.7 * p["GLOW_STRENGTH"]

        # ---- foreground wisps + embers of energy
        wisp = np.clip((cv2.resize(sm, (W, H)) - 0.25), 0, 1) * np.clip(1.1 - K.grid(H, W)[1] * 0.0, 0, 1)
        img += (wisp * (0.05 + 0.25 * K.smooth(ex)) * bgI)[..., None] * K.col((0.16, 0.13, 0.2))
        P = c.cache.get("motes")
        if P is None:
            P = c.cache["motes"] = E.Particles(int(110 * p["PARTICLE_INTENSITY"]), seed=31, z=(0.6, 2.2))
        if P.n:
            ang_p = P.phase + t * (0.6 + P.r) * (1 + 2 * ex)
            rad_p = (0.3 + 1.2 * P.r2) * (1 - 0.8 * K.ease_in(ex, 2))
            x = hx / (H / 2) + np.cos(ang_p) * rad_p * 1.2
            y = hy / (H / 2) + np.sin(ang_p) * rad_p * 0.6
            img += E.particle_layer(H, W, P, x, y, acc * 0.8 + acc2 * 0.2, 1.3, 0.35 * (0.5 + 0.5 * after + hit),
                                    t=t, flicker=0.5, glow=1.0)
        img = add_sub(c, img, cam, imp + 0.6, c.exit_start - 0.1, (0.78, 0.72, 0.90), y_rel=-0.95, tracking=0.5,
                      rel=0.2)
        sx, sy = c.shake(0.003, 0.3, 14)
        if abs(sx) + abs(sy) > 0.05:
            Mx = np.float32([[1.01, 0, -0.005 * W + sx], [0, 1.01, -0.005 * H + sy]])
            img = cv2.warpAffine(img, Mx, (W, H), borderMode=cv2.BORDER_REFLECT)
        return c.finish(img, vignette=0.6, grain=0.035, bloom=(0.8, 0.45),
                        grade=dict(shadows=(0.002, -0.002, 0.006), contrast=1.08, sat=0.95))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        A0, AD = ctl("AnimStart"), ctl("AnimDuration")
        X0, XD = ctl("ExitStart"), ctl("ExitDuration")
        ex = prog(X0, XD)
        u = prog(A0, AD)
        BG = ctl("BackgroundIntensity")
        draw = prog(A0, f"{AD}*0.85")
        collapse = e_in(prog(X0, f"{XD}*0.6"), 2)
        lvl = f"(0.35 + 0.25*{step(I)} + 0.1*sin(time*0.092))*(1 - {collapse})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "VoidGradient", [(0, "#0b0612", 1), (1, "#010102", 1)], gtype="Radial",
                           start=(0.5, 0.5), end=(1.1, 0.0))
        smoke = F.noise(g, "VortexSmoke", "#000000", "#2a2236", detail=6, scale=3.0, seethe_rate=0.05, contrast=1.8)
        smoke.expr("Angle", "time*0.9", 0)
        swirl = F.xf(g, "SmokeTwist", smoke, angle=f"time*0.6 + 90*{e_in(ex, 2)}", size=f"1 + 0.5*{e_in(ex, 2)}")
        bg = F.merge(g, "SmokeMerge", bg, swirl, mode="Screen", blend=f"{BG}")

        g.at(0, 2)
        circle = F.solid(g, "CircleClear", (0, 0, 0), alpha=0.0)
        for i, (rr, bw) in enumerate(((0.66, 0.003), (0.615, 0.0015), (0.46, 0.0015), (0.42, 0.003))):
            col = F.accent_solid(g, f"Ring{i + 1}Color", 1.2)
            m = F.ellipse(g, f"Ring{i + 1}Shape", (0.5, 0.5), rr * 1080 / 1920, rr, 0.003, border=bw)
            F.masked(col, m)
            circle = F.merge(g, f"Ring{i + 1}", circle, col, mode="Screen",
                             blend=f"min({draw}*1.25 - {i * 0.1}, 1)")
        for j in range(6):
            strokes = RUNES_OUT[j]
            a = math.radians(j * 60 + 15)
            ox, oy = 0.5 + math.cos(a) * 0.54 * 1080 / 1920, 0.5 + math.sin(a) * 0.54
            pts = []
            for (p0, p1) in strokes:
                for (gx, gy) in (p0, p1):
                    pts.append((ox + gx * 0.035 * 1080 / 1920, oy + (gy - 0.5) * 0.07))
            pm = F.polyline_mask(g, f"Rune{j + 1}", pts, border=0.0022, soft=0.001)
            rc = F.accent_solid(g, f"Rune{j + 1}Color", 1.4)
            F.masked(rc, pm)
            circle = F.merge(g, f"RuneIgnite{j + 1}", circle, rc, mode="Screen",
                             blend=f"min(max(({draw}*1.3 - {j / 6:.3f})*4, 0), 1)")
        circle = F.xf(g, "CircleSpin", circle, angle=f"time*0.25 + 30*{collapse}", size=f"1 - {collapse}")
        circle = F.xf(g, "FloorPerspective", circle,
                      center=f"Point({ctl('TextPosX')}, {ctl('TextPosY')} - {FLOOR_DY / 2:.3f})")
        circle.set(UseSizeAndAspect=0, XSize=2.2, YSize=2.2 * FLOOR_SQ)
        cg = F.softglow(g, "CircleGlow", circle, 16, gain=f"{ctl('GlowStrength')}*1.4", threshold=0.05)
        bg = F.merge(g, "RitualCircle", bg, cg, mode="Screen",
                     blend=f"min({BG}*({lvl} + 1.2*{decay(I, 10)}), 1)")
        bg = F.shock_ring(g, "EnergyPulse", bg, center=(0.5, 0.5 - FLOOR_DY / 2), max_size=1.2, frames=22, border=0.01,
                         peak=0.8)

        g.at(0, 4)
        ff, fs = fam(p["FONT_FAMILY"])
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], ff, fs, 0.16, 1.1, color=p["TEXT_COLOR"])
        silver = F.fill_material(g, "SmokedSilver", title, [(0, "#1b1a22", 1), (0.48, "#5d5a6c", 1),
                                                           (0.53, "#a8a2bf", 1), (1, "#141319", 1)])
        face = F.merge(g, "SilverMerge", title, silver, mode="Multiply", blend=0.85)
        rim = F.edge_light(g, "ArcaneRim", title, 0.0, -0.003, accent=True, gain=1.5, blur_px=1.5)
        face = F.merge(g, "ArcaneRimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.4 + 0.9*{decay(I, 10)} + 0.25*{step(I)}), 1)")
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        ext = F.extrusion_stack(g, "Extrude", clear, title, layers=4, dx=0.0, dy=-0.0012, color=(0.05, 0.04, 0.07))
        solid_t = F.merge(g, "TitleSolid", ext, face)
        dn = F.noise(g, "SpiralDissolveNoise", "#000000", "#ffffff", detail=4, scale=5, seethe_rate=0.0, contrast=2.0)
        dn.expr("Angle", f"180*(1 - {u})", 0)
        dm = F.bitmap_mask(g, "SpiralDissolve", dn, channel="Luminance")
        thr = f"(1 - {e_inout(prog(f'{A0} + {AD}*0.25', f'{AD}*0.75'))})"
        dm.expr("Low", f"{thr}*0.95", 0)
        dm.expr("High", f"{thr}*0.95 + 0.06", 0.06)
        hold = F.solid(g, "TitleHolder", (0, 0, 0), alpha=0.0)
        tmask = F.merge(g, "TitleCondense", hold, solid_t)
        F.masked(tmask, dm)
        g.at(0, 6)
        placed = F.title_placement(g, "TitleVortex", tmask, size_expr=f"1 - 0.6*{e_in(ex, 2)}",
                                   angle_extra=f"-40*{e_in(ex, 2)}")
        tw = F.dirblur(g, "VortexTwist", placed, f"0.12*{e_in(ex, 2)}", btype=1)
        glow = F.softglow(g, "TitleGlow", tw, 10, gain=f"{ctl('GlowStrength')}*(0.4 + {decay(I, 10)})",
                          threshold=0.5)
        scene = F.merge(g, "TitleOverVoid", bg, glow, blend=f"1 - {clamp01(f'({ex} - 0.5)*2')}")
        scene = F.particles(g, "ArcaneMotes", scene, number=10, lifespan=80, velocity=0.004, angle=90, angle_var=180,
                            size=0.3, color=p["ACCENT_COLOR"], region="SphereRgn", region_size=(0.6,), center_y=0.0,
                            turbulence=0.3, glow=4)
        wisps = F.noise(g, "ForegroundWisps", "#000000", "#282034", detail=5, scale=2.4, seethe_rate=0.06,
                        contrast=1.6, center="Point(0.5 + time*0.001, 0.5)")
        scene = F.merge(g, "WispMerge", scene, wisps, mode="Screen", blend=f"{BG}*(0.1 + 0.4*{ex})")
        g.at(0, 8)
        scene = fusion_subtitle(g, scene, p, size=0.026, tracking=1.6, color=(0.78, 0.72, 0.90), y_off=0.12,
                                t_in=f"{I} + 14", t_out=f"{X0} - 2")
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.05, shake_frames=7, shake_amp=0.003)
        g.output = F.finish(g, scene, vignette=0.6)


DESIGN = T18()
