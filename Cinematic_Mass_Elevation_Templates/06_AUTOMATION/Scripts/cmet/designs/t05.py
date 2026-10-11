"""T05 - Shattered Monolith."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, apply_shake, subtitle
from ..fusion import FuID, ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_extruded, place_sprite, fragments

STONE = Material(base=(0.55, 0.52, 0.48), spec=(0.9, 0.92, 1.0), spec_power=12, spec_gain=0.12, diffuse=0.95,
                 ambient=0.10, metal=0.0, bevel=0.05, bevel_round=False, texture="stone", tex_amount=0.5,
                 bump=0.045, rim=(0.62, 0.75, 0.95), seed=55)

N_FRAG = 34
N_SHARDS_FUSION = 10


def _rock_poly(r, n=7):
    a = np.sort(r.uniform(0, 2 * np.pi, n))
    rad = r.uniform(0.55, 1.0, n)
    return np.stack([np.cos(a) * rad, np.sin(a) * rad * r.uniform(0.6, 1.0)], 1)


class T05(Design):
    ID = "T05"
    NAME = "Shattered Monolith"
    SLUG = "Shattered_Monolith"
    CATEGORY = "A - Dark Mass Elevation"
    CONCEPT = "Monumental stone typography assembled from fragments drifting in an atmospheric void - scale, not noise."
    ENTRANCE = ("Dark stone shards float scattered in depth, then converge on staggered paths (translation, tumble, "
                "depth) and lock together into the title.")
    REVEAL = "The last pieces lock on the impact frame: a small outward puff of chips and dust, joints seal over a second."
    CAMERA = "Slow orbit (yaw from left to right) with perspective shift and background parallax; tiny lock jolt."
    MATERIAL = "Weathered, chipped stone with bump texture, flat chamfer, cool directional rim light from upper left."
    EXIT = "Fine cracks spread through the surface from several origins, light leaks faintly through them, then the scene fades."
    TECHNIQUES = ["Voronoi / polygon fracture", "staggered convergence", "camera orbit", "floating rock parallax",
                  "chip + dust burst", "seam sealing", "spreading cracks"]
    TRUE_3D = False
    DURATION_FRAMES = 240
    DEFAULTS = dict(MAIN_TITLE="MONOLITH", SUBTITLE="WHAT WAS BROKEN WILL RISE", FONT_FAMILY="cinzel",
                    TEXT_COLOR="#8C8478", ACCENT_COLOR="#9FB8D8", ANIMATION_START=12, ANIMATION_DURATION=96,
                    IMPACT_FRAME=108, HOLD_DURATION=72, EXIT_START=180, EXIT_DURATION=56, LETTER_SPACING=0.08,
                    TITLE_WIDTH=0.7)
    SOUND = [(0, "atmos", "Vast hollow void drone"), (0, "wind", "Thin high wind"),
             (12, "riser", "Slow tectonic riser as the shards converge (12-108)"),
             (60, "debris", "Grinding stone passes"), (100, "rwhoosh", "Air pulled into the final lock"),
             (108, "impact", "Stone lock impact"), (108, "sub", "Sub drop"), (109, "debris", "Chips + dust scatter"),
             (180, "crackle", "Stone cracking spreads"), (210, "tail", "Low tail into silence")]

    # ------------------------------------------------------------ preview --
    def _setup(self, c, sp):
        S = c.cache.get("frag")
        if S is not None:
            return S
        H, W = c.H, c.W
        r = np.random.default_rng(17)
        frs = fragments(sp, N_FRAG, seed=23)
        n = len(frs)
        cx = np.array([f[1][0] for f in frs]) - sp.anchor[0]
        # scattered rest-of-opening state: spread outward from the title + deep in z
        dirx = np.sign(cx + 1e-3) * r.uniform(0.2, 1.0, n)
        off = np.stack([dirx * W * r.uniform(0.2, 0.5, n), r.uniform(-0.38, 0.38, n) * H,
                        r.uniform(0.15, 1.1, n) * H], 1)
        rot = r.uniform(-75, 75, (n, 3))
        rot[:, 2] *= 0.6
        # arrival order: outer pieces first, the last few lock exactly on the impact frame
        lag = np.clip(r.uniform(0, 1, n) * 0.9, 0, 1)
        lag[np.argsort(r.random(n))[:4]] = 0.0
        delay = r.uniform(0, 0.35, n)
        phase = r.uniform(0, 2 * np.pi, n)
        # joint (seam) map between neighbouring pieces, sealed after the lock
        seam = np.zeros_like(sp.mask)
        kern = np.ones((3, 3), np.uint8)
        for f in frs:
            m = (f[2] > 0.5).astype(np.uint8)
            seam = np.maximum(seam, (cv2.morphologyEx(m, cv2.MORPH_GRADIENT, kern) > 0).astype(np.float32))
        seam = cv2.GaussianBlur(seam * sp.mask, (0, 0), 0.7)
        # exit cracks in sprite pixels
        cracks = []
        for j, ox in enumerate(np.linspace(-0.42, 0.42, 5)):
            o = np.array([sp.anchor[0] + (ox + r.uniform(-0.04, 0.04)) * sp.ink_w,
                          sp.anchor[1] + r.uniform(-0.2, 0.2) * sp.ink_h])
            for ln in E.crack_lines(90 + j, (0.0, 0.0), n=5, length=0.9, segs=18, jitter=0.5):
                cracks.append(o[None, :] + ln * sp.ink_h)
        # distant floating rocks (background)
        rocks = [(r.uniform(-2.0, 2.0), r.uniform(-0.85, 0.85), r.uniform(1.5, 5.0), r.uniform(0.03, 0.11),
                  _rock_poly(r, int(r.integers(5, 9))), r.uniform(0, 6.28)) for _ in range(16)]
        S = c.cache["frag"] = dict(frs=frs, off=off, rot=rot, lag=lag, delay=delay, phase=phase, seam=seam,
                                   cracks=cracks, rocks=rocks)
        return S

    def _bg(self, c, yaw, S, ex):
        p, H, W, t = c.p, c.H, c.W, c.t
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        h2, w2 = H // 2, W // 2
        nx, ny = K.grid(h2, w2)
        bg = K.vgrad(h2, w2, (0.018, 0.021, 0.028), (0.007, 0.007, 0.009))
        bg += (K.soft_spot(h2, w2, -0.9 - yaw * 0.02, -0.7, 1.6, 1.0, 1.0) * 0.05)[..., None] * acc
        f1 = E.fog(h2, w2, t, (0.10, 0.11, 0.13), density=0.45, scale=0.55, speed=(0.004 + yaw * 0.0003, 0.0),
                   seed=5, warp=0.04, contrast=1.1)
        bg += f1
        # floating rocks with rim light, parallax driven by the orbit
        buf = np.zeros((h2, w2), np.float32)
        rimb = np.zeros((h2, w2), np.float32)
        for x0, y0, z, sz, poly, ph in S["rocks"]:
            x = x0 - yaw * 0.05 / z + 0.01 * t / z
            y = y0 + 0.02 * math.sin(t * 0.3 + ph)
            ang = ph + t * 0.05
            R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
            pts = (poly @ R.T) * sz / z ** 0.7 * 2.6
            px = (w2 / 2 + (x / z * 1.5 + pts[:, 0]) * h2 / 2)
            py = (h2 / 2 + (y / z * 1.5 + pts[:, 1]) * h2 / 2)
            arr = (np.stack([px, py], 1) * 4).astype(np.int32)
            cv2.fillPoly(buf, [arr], 1.0 / z ** 0.3, cv2.LINE_AA, shift=2)
            cv2.polylines(rimb, [arr[: max(2, len(arr) // 2 + 1)]], False, 1.0 / z ** 0.5, 1, cv2.LINE_AA, shift=2)
        buf = K.blur(buf, 0.8)
        bg = bg * (1 - np.clip(buf, 0, 1)[..., None] * 0.75) + K.blur(rimb, 0.7)[..., None] * acc * 0.25
        f2 = E.fog(h2, w2, t * 1.3, (0.09, 0.10, 0.12), density=0.22 + 0.4 * K.smooth(ex), scale=0.8,
                   speed=(0.01, 0.002), seed=8, warp=0.05, contrast=1.2, height=(0.35, 0.5))
        bg += f2
        return cv2.resize(bg * bgI, (W, H), interpolation=cv2.INTER_LINEAR), f2

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        imp = c.impact
        ex = c.exit_u()
        hit = c.hit(0.02, 0.35)
        after = t >= imp
        sp = c.title()
        S = self._setup(c, sp)
        sh = c.shaded(STONE)
        yaw = -9.0 + 15.0 * K.ease_in_out(K.prog(t, 0, c.dur), 2)
        cam = c.cam(zoom=1.0 + 0.04 * K.ease_in_out(K.prog(t, 0, c.dur)), yaw=yaw * 0.6, pan=(yaw * 2.0 * c.k, 0))
        bg, fogfront = self._bg(c, yaw, S, ex)

        # cracks (exit) and seams (before sealing) live in sprite space
        crack_u = K.smooth(ex / 0.6)
        crack = None
        if crack_u > 0:
            cb = np.zeros((sp.h, sp.w), np.float32)
            for ln in S["cracks"]:
                m = max(2, int(len(ln) * crack_u))
                cv2.polylines(cb, [(ln[:m] * 4).astype(np.int32).reshape(-1, 1, 2)], False, 1.0,
                              max(1, int(1.6 * k)), cv2.LINE_AA, shift=2)
            crack = cb * sp.mask
        seal = 1 - K.smooth(K.prog(t, imp + 0.15, 1.1))
        lg = (0.55 + 0.45 * K.smooth(c.reveal_u(0, c.reveal * 0.85))) * (1 - 0.6 * K.smooth(ex))
        emis = None
        if crack is not None:
            emis = (K.blur(crack, 3.0 * k) * 1.4 + K.blur(crack, 0.8) * 0.7)[..., None] * acc * p["GLOW_STRENGTH"] * (1 - ex)
        rgb, a = sh.shade(light=(-0.6, -0.55, 0.55), rim_dir=(-0.7, -0.7), rim_gain=(0.9 + 1.6 * hit) * (1 - 0.5 * ex),
                          base=K.col(p["TEXT_COLOR"]), light_gain=lg, emissive=emis)
        if crack is not None:
            rgb = rgb * (1 - crack * 0.85)[..., None]
        if seal > 0:
            rgb = rgb * (1 - S["seam"] * 0.8 * seal)[..., None]

        L = c.layer()
        hx, hy = c.hero()
        rotz = p["TEXT_ROTATION"]
        op = K.smooth(K.prog(t, 0, 0.8)) * (1 - K.smooth((ex - 0.55) / 0.45))
        depth = 0.14 * sp.cap_px * p["EXTRUSION_DEPTH"]
        side = (0.05, 0.048, 0.046)
        if not after:
            # fragments: floating, then converging on staggered paths
            frs, off, rot, lag, delay, ph = S["frs"], S["off"], S["rot"], S["lag"], S["delay"], S["phase"]
            order = np.argsort(-off[:, 2])
            span = max(imp - c.start, 0.1)
            for i in order:
                box, cen, fm = frs[i]
                s0 = c.start + delay[i] * span
                e0 = imp - lag[i] * 0.55 * span * 0.35
                ui = K.prog(t, s0, max(e0 - s0, 0.05))
                e = K.ease_in_out(ui, 3) if ui < 1 else 1.0
                rem = 1 - e
                bob = (1 - K.smooth(ui * 3))
                dx = off[i, 0] * rem + 12 * k * math.sin(t * 0.6 + ph[i]) * bob
                dy = off[i, 1] * rem + 10 * k * math.cos(t * 0.5 + ph[i]) * bob
                dz = off[i, 2] * rem
                rx, ry, rz = rot[i] * rem + 8 * bob * math.sin(t * 0.4 + ph[i])
                fa = fm
                fo = op * (0.7 + 0.3 * K.smooth(1 - dz / H))
                loc = (dx, dy, dz, rx, ry, rz, 1.0, cen[0], cen[1])
                if depth > 0.5 and rem > 0.002:
                    for q in (1.0, 0.5):
                        srgb = np.empty_like(rgb[box[1]:box[1] + 1, box[0]:box[0] + 1])
                        srgb[...] = np.array(side, np.float32) * (0.6 + 0.6 * (1 - q))
                        loc_s = (dx, dy, dz + depth * q, rx, ry, rz, 1.0, cen[0], cen[1])
                        sr = np.broadcast_to(srgb, rgb.shape)
                        place_sprite(L, cam, sr, fa, box, sp.anchor, (hx, hy, 0), 1.0, (0, 0, rotz), loc_s, fo)
                place_sprite(L, cam, rgb, fa, box, sp.anchor, (hx, hy, 0), 1.0, (0, 0, rotz), loc, fo)
        else:
            jolt = 3 * k * K.pulse(t, imp, 0.01, 0.08)
            if depth > 0.5:
                place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, (hx, hy + jolt, 0), 1.0, (0, 0, rotz),
                               depth, side, slices=8, side_light=lambda q: 0.6 + 0.6 * q, opacity=op)
            else:
                c.place(L, cam, rgb, a, sp, 1.0, off=(0, jolt, 0), opacity=op)
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.5, 0), 8 * k) * 0.5 * p["GLOW_STRENGTH"] * (0.2 + hit)

        # impact: chips + dust puff travelling outward from the title
        PI = p["PARTICLE_INTENSITY"]
        if after and PI > 0:
            dt = t - imp
            B = c.cache.get("chips")
            if B is None:
                r = np.random.default_rng(31)
                n = int(120 * PI)
                ox = r.uniform(-0.5, 0.5, n) * sp.ink_w / (H / 2)
                oy = r.uniform(-0.5, 0.5, n) * sp.ink_h / (H / 2)
                ang = np.arctan2(oy + r.normal(0, 0.05, n), ox + r.normal(0, 0.05, n))
                spd = r.uniform(0.15, 0.9, n) ** 1.5
                B = c.cache["chips"] = (n, ox, oy, ang, spd, r.random(n))
            n, ox, oy, ang, spd, rr = B
            dist = spd * (1 - np.exp(-dt * 3.0)) / 3.0
            gx = hx / (H / 2) + ox + np.cos(ang) * dist
            gy = hy / (H / 2) + oy + np.sin(ang) * dist * 0.7 + 0.12 * dt * dt
            fade = np.exp(-dt / (0.5 + rr)) * (1 - ex)
            Pc = E.Particles(n, 2)
            Pc.z = (0.8 + 0.4 * rr).astype(np.float32)
            img += E.particle_layer(H, W, Pc, gx, gy, np.array([0.5, 0.5, 0.52]) + acc * 0.3, 1.2, 0.9 * fade,
                                    glow=0.3)
            if dt < 2.5:
                q = cv2.resize(K.soft_spot(H // 4, W // 4, hx / (H / 2), hy / (H / 2) + 0.05,
                                           0.5 * sp.ink_w / (H / 2) * (1 + dt * 0.8), 0.25 + dt * 0.25, 1.4), (W, H))
                dust = K.fbm_field(H // 4, W // 4, t, 3.0, (0.02, -0.01), 41, beta=2.0)
                dust = cv2.resize(dust, (W, H))
                img += ((q * np.clip(dust - 0.35, 0, 1)) * 0.22 * math.exp(-dt / 0.7) * PI)[..., None] * \
                    np.array([0.55, 0.56, 0.6], np.float32) * p["BACKGROUND_INTENSITY"]

        img = img + fogfront.repeat(2, 0).repeat(2, 1)[:H, :W] * 0.35 * (0.3 + K.smooth(ex))
        img = subtitle(c, img, cam, imp + 0.8, c.exit_start + 0.2, (0.62, 0.64, 0.68), y_rel=0.9, tracking=0.45)
        img = apply_shake(c, img, 0.003, 0.25, 12)
        img = img * (1 - 0.9 * K.smooth((ex - 0.7) / 0.3))
        return c.finish(img, vignette=0.55, grain=0.03, bloom=(0.85, 0.35))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S = ctl("AnimStart")
        ES = ctl("ExitStart")
        BG = ctl("BackgroundIntensity")
        GL = ctl("GlowStrength")
        ex = prog(ES, ctl("ExitDuration"))
        orbit = e_inout(prog(0, g.frames))

        # void + floating rocks ----------------------------------------------
        g.at(0, 0)
        bg = F.gradient_bg(g, "Void", [(0, "#05060a", 1), (1, "#020203", 1)])
        fog1 = F.noise(g, "VoidFogFar", "#000000", "#1c1f26", detail=5, scale=1.6, seethe_rate=0.02, contrast=1.4,
                       center=f"Point(0.5 + 0.03*{orbit} + time*0.0002, 0.5)")
        bg = F.merge(g, "VoidFogFarMerge", bg, fog1, mode="Screen", blend=f"0.8*{BG}")
        bg = F.light_spot(g, "MoonGlow", bg, None, (0.25, 0.85), 1.4, 0.9, 0.6, accent=True, gain=0.25,
                          blend=f"0.6*{BG}")
        g.at(0, 2)
        import random
        rr = random.Random(5)
        rk = None
        for i in range(6):
            cx, cy, s = rr.uniform(0.05, 0.95), rr.uniform(0.2, 0.85), rr.uniform(0.02, 0.05)
            pts = [(cx + s * math.cos(a) * rr.uniform(0.6, 1), cy + s * 1.7 * math.sin(a) * rr.uniform(0.6, 1))
                   for a in sorted(rr.uniform(0, 6.283) for _ in range(6))]
            m = F.closed_poly_mask(g, f"FarRock{i + 1}", pts, soft=0.002)
            m.expr("Center", f"Point(0.5 - {0.02 + 0.01 * i:.3f}*{orbit}, 0.5 + 0.004*sin(time*0.03 + {i}))",
                   [0.5, 0.5])
            if rk is not None:
                m.conn("EffectMask", rk, "Mask")
            rk = m
        rocks = F.solid(g, "FarRockStone", (0.012, 0.012, 0.014))
        F.masked(rocks, rk)
        bg = F.merge(g, "FarRocks", bg, rocks, blend=0.85)
        bg = F.xf(g, "EnvOrbit", bg, center=f"Point(0.5 - 0.015*{orbit}, 0.5)", size=f"1 + 0.03*{orbit}", edges=1)

        # stone title material ----------------------------------------------------
        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Cinzel", "Black", 0.15, 1.08, color=p["TEXT_COLOR"])
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        grad = F.fill_material(g, "StoneShade", title,
                               [(0, "#d8d2c8", 1), (0.5, "#a49d92", 1), (1, "#5a554e", 1)])
        face = F.merge(g, "StoneFace", title, grad, mode="Multiply", blend=1.0)
        grain = F.noise(g, "StoneGrain", "#3a3a3a", "#c4c4c4", detail=10, scale=18, seethe_rate=0.0, contrast=1.8)
        gm = F.bitmap_mask(g, "StoneGrainMatte", title)
        gr = F.merge(g, "StoneGrainHolder", clear, grain)
        F.masked(gr, gm)
        face = F.merge(g, "WeatheredStone", face, gr, mode="Overlay", blend=0.55)
        rim = F.edge_light(g, "MoonRim", title, 0.0016, -0.0026, accent=True, gain=1.3, blur_px=1.0)
        face = F.merge(g, "RimMerge", face, rim, mode="Screen",
                       blend=f"min({GL}*(0.7 + 1.5*{ctl('ImpactIntensity')}*{decay(I, 10)})*(1 - 0.5*{ex}), 1)")
        ext = F.extrusion_stack(g, "StoneDepth", clear, title, layers=6, dx=0.0009, dy=-0.0012,
                                color=(0.05, 0.048, 0.046))
        stone = F.merge(g, "StoneBlock", ext, face)

        # exit cracks (title space): crack strokes x growing ellipse x title alpha
        g.at(0, 6)
        rc = random.Random(9)
        prev = None
        for j in range(5):
            x, y = 0.25 + 0.125 * j, 0.5 + rc.uniform(-0.03, 0.03)
            pts = [(x, y)]
            ang = rc.uniform(0, 6.283)
            for _ in range(9):
                ang += rc.gauss(0, 0.6)
                x += 0.018 * math.cos(ang)
                y += 0.012 * math.sin(ang)
                pts.append((x, y))
            m = F.polyline_mask(g, f"Crack{j + 1}", pts, border=0.0012, soft=0.0008)
            if prev is not None:
                m.conn("EffectMask", prev, "Mask")
            prev = m
        grow = F.ellipse(g, "CrackSpread", (0.5, 0.5), 0.01, 0.01, 0.05)
        grow.expr("Width", f"0.02 + 1.2*{clamp01(f'{ex}/0.6')}", 0.02)
        grow.expr("Height", f"0.02 + 1.2*{clamp01(f'{ex}/0.6')}", 0.02)
        grow.conn("EffectMask", prev, "Mask")         # spread ellipse x (union of crack strokes)
        grow.set(PaintMode=FuID("Multiply"))
        ctm = F.bitmap_mask(g, "CrackInTitle", title, paint="Multiply", prev=grow)
        dark = F.solid(g, "CrackShadow", (0.0, 0.0, 0.0))
        F.masked(dark, ctm)
        stone = F.merge(g, "CracksDark", stone, dark, blend=f"0.85*{step(ES)}")
        leak = F.accent_solid(g, "CrackLeak", 1.2)
        F.masked(leak, ctm)
        leak = F.softglow(g, "CrackLeakGlow", leak, 4, gain=f"{GL}", threshold=0.05)
        stone = F.merge(g, "CracksLight", stone, leak, mode="Screen", blend=f"0.6*{step(ES)}*(1 - {ex})")

        # fracture: polygon shards, each converging from a scattered pose ---------------
        g.at(0, 8)
        polys = F.shard_polys(n=N_SHARDS_FUSION, seed=5, box=(0.08, 0.36, 0.92, 0.64))
        rs = random.Random(13)
        span = f"max({I} - {S}, 1)"
        asm = clear
        for j, poly in enumerate(polys):
            g.at(0, 8 + j)
            cxp = sum(q[0] for q in poly) / len(poly)
            cyp = sum(q[1] for q in poly) / len(poly)
            dx = (cxp - 0.5) * rs.uniform(0.8, 2.2) + rs.uniform(-0.1, 0.1)
            dy = rs.uniform(-0.35, 0.35)
            ds = rs.uniform(-0.6, -0.3)          # far away = smaller
            da = rs.uniform(-70, 70)
            delay = rs.uniform(0.0, 0.35)
            lag = 0.0 if j in (3, 6) else rs.uniform(0.0, 0.25)
            uj = prog(f"{S} + {delay:.3f}*{span}", f"{span}*{1 - delay - lag:.3f}")
            rem = f"(1 - {e_inout(uj)})"
            mk = F.closed_poly_mask(g, f"ShardShape{j + 1}", poly, soft=0.0008)
            piece = F.merge(g, f"Shard{j + 1}", clear, stone)
            F.masked(piece, mk)
            mv = g.add("Transform", f"ShardMove{j + 1}")
            mv.conn("Input", piece)
            mv.set(Pivot=[round(cxp, 4), round(cyp, 4)])
            mv.expr("Center", (f"Point({cxp:.4f} + {dx:.3f}*{rem} + 0.006*sin(time*0.05 + {j})*(1 - {uj}),"
                               f" {cyp:.4f} + {dy:.3f}*{rem} + 0.006*cos(time*0.04 + {j})*(1 - {uj}))"),
                    [cxp, cyp])
            mv.expr("Angle", f"{da:.1f}*{rem}", 0)
            mv.expr("Size", f"1 + {ds:.2f}*{rem}", 1)
            asm = F.merge(g, f"Assemble{j + 1}", asm, mv,
                          blend=f"min({prog(0, 18)}, 1)*(0.4 + 0.6*{e_out(uj, 2)})")
        g.at(0, 20)
        lit = F.cc(g, "ConvergeLight", asm, gain=f"(0.35 + 0.65*{prog(S, f'{span}*0.85')})*(1 - 0.6*{ex})")
        placed = F.title_placement(g, "TitlePlace", lit, size_expr=f"1 + 0.03*{orbit}",
                                   center_extra_x=f"0.012 - 0.024*{orbit}",
                                   center_extra_y=f"-0.003*{decay(I, 2)}")
        scene = F.merge(g, "TitleOverVoid", bg, placed, blend=f"1 - {clamp01(f'({ex} - 0.55)/0.45')}")

        # impact + finish ------------------------------------------------------------
        g.at(0, 22)
        burst = f"160*{ctl('ParticleIntensity')}*{window(I, I + ' + 2', 1, 1)}"
        scene = F.particles(g, "StoneChips", scene, number=160, lifespan=40, velocity=0.02, angle=90, angle_var=180,
                            size=0.35, color=(0.55, 0.56, 0.6), region="CubeRgn", region_size=(0.9, 0.18, 0.1),
                            center_y=0.0, turbulence=0.1, glow=0, number_expr=burst)
        dust = F.noise(g, "DustPuff", "#000000", "#6a6c72", detail=5, scale=5, seethe_rate=0.2, contrast=1.6)
        dshape = F.ellipse(g, "DustPuffShape", (0.5, 0.5), 0.5, 0.2, 0.6)
        dshape.expr("Width", f"0.6 + 0.5*{prog(I, 40)}", 0.6)
        dshape.expr("Height", f"0.2 + 0.3*{prog(I, 40)}", 0.2)
        F.masked(dust, dshape)
        scene = F.merge(g, "DustPuffMerge", scene, dust, mode="Screen",
                        blend=f"0.5*{ctl('ParticleIntensity')}*{decay(I, 16)}")
        fog2 = F.noise(g, "VoidFogNear", "#000000", "#23262e", detail=5, scale=2.4, seethe_rate=0.03, contrast=1.5,
                       center="Point(0.5 + time*0.0006, 0.5)")
        scene = F.merge(g, "VoidFogNearMerge", scene, fog2, mode="Screen", blend=f"{BG}*(0.25 + 0.5*{ex})")
        g.at(0, 24)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.028, 1.6,
                                    color=(0.62, 0.64, 0.68), y_off=-0.14)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 20", f"{ES} + 5", 20, 12))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.04, shake_frames=6, shake_amp=0.003,
                             push_start="0", push_dur=str(g.frames))
        black = F.solid(g, "FadeBlack", (0, 0, 0))
        scene = F.merge(g, "FinalFade", scene, black, blend=f"0.9*{clamp01(f'({ex} - 0.7)/0.3')}")
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T05()
