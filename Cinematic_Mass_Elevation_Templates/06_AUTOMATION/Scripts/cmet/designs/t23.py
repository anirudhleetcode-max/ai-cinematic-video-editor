"""T23 - Digital Awakening."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from . import _c_helpers as X


def _points(sp, k, n_max=1100, seed=4):
    """Target points sampled on a jittered lattice inside the glyph mask."""
    st = max(4.0, sp.cap_px / 13)
    r = np.random.default_rng(seed)
    ys, xs = np.mgrid[sp.ink[1]:sp.ink[3]:st, sp.ink[0]:sp.ink[2]:st]
    xs = xs.ravel() + r.uniform(-0.3, 0.3, xs.size) * st
    ys = ys.ravel() + r.uniform(-0.3, 0.3, ys.size) * st
    xi = np.clip(xs.astype(int), 0, sp.w - 1)
    yi = np.clip(ys.astype(int), 0, sp.h - 1)
    keep = sp.mask[yi, xi] > 0.5
    xs, ys = xs[keep], ys[keep]
    if len(xs) > n_max:
        idx = r.choice(len(xs), n_max, replace=False)
        xs, ys = xs[idx], ys[idx]
    order = np.argsort(xs)
    return xs[order].astype(np.float32), ys[order].astype(np.float32)


class T23(Design):
    ID = "T23"
    NAME = "Digital Awakening"
    SLUG = "Digital_Awakening"
    CATEGORY = "C - Future Tech and Kinetic Camera"
    CONCEPT = "A system boots: scattered data points and procedural lines organise themselves into a stable wordmark."
    ENTRANCE = ("Hundreds of disorganised points and short data lines drift in depth, then converge in a left-to-right "
                "wave onto a lattice inside the letterforms, forming a wireframe of the title.")
    REVEAL = "At the impact frame the point-lattice resolves block-by-block into the solid wordmark with an edge pulse."
    CAMERA = "Slow drift-in with depth parallax on the background node lattice."
    MATERIAL = "Clean white emissive face with a mint inner edge; mint data points and lines on a deep navy void."
    EXIT = "Decompile: the wordmark de-resolves block-by-block back into points that float upward and dissipate."
    TECHNIQUES = ["glyph-sampled point cloud", "plexus lines", "data streaks", "block resolve", "node lattice",
                  "decompile exit"]
    DURATION_FRAMES = 216
    DEFAULTS = dict(MAIN_TITLE="AWAKENING", SUBTITLE="SYSTEM ONLINE", FONT_FAMILY="orbitron_med",
                    TEXT_COLOR="#F2FFFB", ACCENT_COLOR="#3CF0C0", ANIMATION_START=6, ANIMATION_DURATION=90,
                    IMPACT_FRAME=104, HOLD_DURATION=72, EXIT_START=178, EXIT_DURATION=30, LETTER_SPACING=0.1,
                    TITLE_WIDTH=0.68, SHADOW_STRENGTH=0.0)
    SOUND = [(0, "atmos", "Deep digital room tone"), (6, "digital", "Data chatter as points appear"),
             (30, "swell", "Rising tonal swell while points converge"), (70, "digital", "Lattice lock ticks"),
             (98, "rwhoosh", "Reverse suck into resolve"), (104, "impact", "Clean digital impact (resolve)"),
             (105, "shimmer", "Block-resolve shimmer"), (178, "digital", "Decompile chatter"),
             (190, "tail", "Airy tail")]
    FUSION_NOTES = ["The Fusion version converges a pEmitter point field (Transform scale/centre onto the title) and "
                    "resolves the wordmark with a FastNoise threshold; the preview converges points sampled from the "
                    "actual glyph shapes and resolves in square blocks."]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k, fr = c.p, c.H, c.W, c.t, c.k, c.fr
        acc = K.col(p["ACCENT_COLOR"])
        tc = K.col(p["TEXT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        PI = p["PARTICLE_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        sp = c.title()
        hx, hy = c.hero()
        zoom = 1.0 + 0.04 * K.ease_in_out(K.prog(t, 0, c.dur))
        cx0, cy0 = W / 2 + hx * zoom, H / 2 + hy * zoom

        # --- void + node lattice (parallax)
        bg = K.radial(H, W, hx / (H / 2), hy / (H / 2), 1.9, (0.012, 0.03, 0.045), (0.002, 0.004, 0.009), 1.2)
        bg = bg * bgI
        key = "lattice"
        if key not in c.cache:
            r = np.random.default_rng(3)
            n = 420
            c.cache[key] = (r.uniform(-1.9, 1.9, n), r.uniform(-1.1, 1.1, n), r.uniform(1.2, 3.0, n), r.random(n))
        lx, ly, lz, lr = c.cache[key]
        s = (zoom + 0.03 * t / c.dur) / lz
        px = W / 2 + lx * s * H / 2
        py = H / 2 + ly * s * H / 2
        lat = np.zeros((H, W, 3), np.float32)
        on = K.smooth(K.prog(t, 0, 1.2)) * (1 - 0.6 * K.smooth(ex))
        for i in range(len(lx)):
            b = (0.06 + 0.25 * (lr[i] > 0.93) * (0.5 + 0.5 * math.sin(t * 2 + i))) * on * bgI
            if b > 0.01:
                cv2.circle(lat, (int(px[i] * 4), int(py[i] * 4)), max(1, int(1.6 * k * 4)), (float(b),) * 3, -1,
                           cv2.LINE_AA, shift=2)
        bg += lat * (acc * 0.6 + 0.3)
        # faint lattice links (geometric)
        segs, ints = [], []
        for i in range(0, len(lx) - 1, 3):
            j = i + 1
            d = math.hypot(px[i] - px[j], py[i] - py[j])
            if d < 260 * k:
                segs.append(((px[i], py[i]), (px[j], py[j])))
                ints.append(0.05 * on * bgI)
        bg += X.lines_buf(H, W, segs, acc, 1.0, k, ints)

        # --- point cloud -> lattice inside the glyphs
        key = "pts"
        if key not in c.cache:
            tx, ty = _points(sp, k)
            n = len(tx)
            r = np.random.default_rng(11)
            ang = r.uniform(0, 2 * np.pi, n)
            rad = r.uniform(0.35, 1.25, n) * W
            ox = np.cos(ang) * rad * 0.8
            oy = np.sin(ang) * rad * 0.45
            uu = (tx - tx.min()) / max(1.0, tx.max() - tx.min())
            delay = uu * 0.42 + r.uniform(0, 0.16, n)
            bs = max(6, int(sp.cap_px / 9))
            blk = r.random(((sp.h // bs) + 2, (sp.w // bs) + 2)).astype(np.float32)
            bmap = cv2.resize(blk, ((sp.w // bs + 2) * bs, (sp.h // bs + 2) * bs),
                              interpolation=cv2.INTER_NEAREST)[:sp.h, :sp.w]
            pr = bmap[np.clip(ty.astype(int), 0, sp.h - 1), np.clip(tx.astype(int), 0, sp.w - 1)]
            c.cache[key] = (tx, ty, ox, oy, delay, r.random(n), r.uniform(0, 6.28, n), bmap, pr,
                            (r.random(n) < 0.25))
        tx, ty, ox, oy, delay, rr, ph, bmap, pr, sq = c.cache[key]
        n = len(tx)
        T0 = c.start
        Tv = c.reveal * 0.55
        uprog = np.clip((t - T0 - delay * c.reveal) / Tv, 0, 1)
        e = 1 - (1 - uprog) ** 3
        sw = (1 - e)
        gx = cx0 + (tx - sp.anchor[0]) * zoom
        gy = cy0 + (ty - sp.anchor[1]) * zoom
        x = gx + ox * sw + np.sin(t * 1.3 + ph) * 40 * k * sw
        y = gy + oy * sw + np.cos(t * 1.1 + ph) * 30 * k * sw
        appear = np.clip((t - T0 + 0.3 - rr * 0.6) / 0.4, 0, 1)
        res_u = K.prog(t, imp - 0.12, 0.45)       # resolve progress
        de_u = K.prog(ex, 0.0, 0.65)               # decompile progress
        absorbed = np.clip((res_u * 1.15 - pr) * 8, 0, 1)
        freed = np.clip((de_u * 1.15 - pr) * 8, 0, 1)
        # decompile: freed points float upward and dissipate
        lift = np.clip((de_u * 1.15 - pr) / 0.5, 0, 1) ** 1.6
        y = y - lift * (120 + 220 * rr) * k
        x = x + lift * np.sin(ph) * 60 * k
        vis = appear * (1 - absorbed + freed) * (1 - lift) * min(1.0, PI + 0.0001 if PI > 0 else 0)
        inten = vis * (0.55 + 0.45 * np.sin(t * 6 + ph * 3) ** 2) * (0.6 + 0.6 * e)
        pts = np.zeros((H, W, 3), np.float32)
        if PI > 0:
            for i in range(0, n, 1 if PI >= 1 else max(1, int(1 / PI))):
                I = float(inten[i])
                if I < 0.02:
                    continue
                cc = (I, I, I)
                if sq[i]:
                    s2 = 2.2 * k * (1 + sw[i] * 1.5)
                    cv2.rectangle(pts, (int((x[i] - s2) * 4), int((y[i] - s2) * 4)),
                                  (int((x[i] + s2) * 4), int((y[i] + s2) * 4)), cc, 1, cv2.LINE_AA, shift=2)
                else:
                    cv2.circle(pts, (int(x[i] * 4), int(y[i] * 4)), max(1, int(1.7 * k * (1 + sw[i]) * 4)), cc, -1,
                               cv2.LINE_AA, shift=2)
            # plexus: neighbours in target order; length-attenuated so the wireframe emerges as they converge
            segs, ints = [], []
            for i in range(0, n - 2, 1 if PI >= 1 else 2):
                for j in (i + 1, i + 2):
                    d = math.hypot(x[i] - x[j], y[i] - y[j])
                    a = min(inten[i], inten[j]) * math.exp(-d / (55 * k)) * 0.5
                    if a > 0.02 and d < 240 * k:
                        segs.append(((x[i], y[i]), (x[j], y[j])))
                        ints.append(a)
            pts += X.lines_buf(H, W, segs, (1, 1, 1), 1.0, k, ints)
        pts = pts * (acc * 0.85 + 0.25)
        # data streaks (procedural data-like lines) during the build and the decompile
        busy = (1 - K.smooth(K.prog(t, imp, 0.6))) * K.smooth(K.prog(t, T0, 0.5)) + 0.6 * K.smooth(ex * 8) * (1 - K.smooth(K.prog(ex, 0.5, 0.4)))
        if busy > 0.01 and PI > 0:
            segs, ints = [], []
            for j in range(int(26 * PI)):
                sp_ = 0.6 + K.hash01(j, 2) * 1.6
                yy = H * (0.2 + 0.6 * K.hash01(j, 5))
                xx = ((K.hash01(j, 7) + t * sp_ * 0.35) % 1.4 - 0.2) * W
                ln = (40 + 160 * K.hash01(j, 9)) * k
                segs.append(((xx, yy), (xx + ln, yy)))
                ints.append(0.35 * busy * (0.4 + 0.6 * K.hash01(j, 11)))
            ds = X.lines_buf(H, W, segs, acc, 1.0, k, ints)
            pts += ds + K.blur(ds, 4 * k)

        # --- solid wordmark: block resolve / block decompile
        key = "face"
        if key not in c.cache:
            rgb0 = X.vband(sp, tc, tc * 0.82 + acc * 0.1)
            edge = X.inner_edge(sp, 0.05)
            c.cache[key] = (rgb0 * (1 - edge[..., None] * 0.7) + edge[..., None] * (acc * 1.2 + 0.2), edge)
        face, edge = c.cache[key]
        bvis = np.clip((res_u * 1.15 - bmap) * 8, 0, 1) * (1 - np.clip((de_u * 1.15 - bmap) * 8, 0, 1))
        a = sp.mask * bvis
        hit = c.hit(0.02, 0.3)
        rgb = face * (1 + 0.6 * hit) + edge[..., None] * acc * 1.5 * hit
        cam = c.cam(zoom=zoom)
        L = c.layer()
        c.place(L, cam, rgb, a, sp, 1.0)
        img = bg * (1 - L.a[..., None]) + L.rgb
        G = p["GLOW_STRENGTH"]
        glow_src = pts + L.rgb * (0.2 + 0.5 * hit)
        img += pts + (K.blur(glow_src, 5 * k) * 0.7 + K.blur(glow_src, 20 * k) * 0.4) * G
        img = subtitle(c, img, cam, imp + 0.5, c.exit_start - 0.1, tc * 0.55 + acc * 0.25, y_rel=0.82)
        img = X.grade_fast(img, shadows=(-0.003, 0.0, 0.006), contrast=1.04)
        return c.finish(img, vignette=0.5, grain=0.03, bloom=(0.9, 0.4))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        S, D = ctl("AnimStart"), ctl("AnimDuration")
        u = prog(S, D)
        BG = ctl("BackgroundIntensity")
        res = prog(f"{I} - 3", 11)
        de = clamp01(f"{ex}/0.65")

        g.at(0, 0)
        bg = F.gradient_bg(g, "Void", [(0, "#0a1a22", 1), (1, "#010204", 1)], gtype="Radial", start=(0.5, 0.5),
                           end=(0.5, 1.1))
        bg = F.cc(g, "VoidLevel", bg, gain=BG)
        bg = F.particles(g, "NodeLattice", bg, number=40, lifespan=400, velocity=0.0, angle=0, angle_var=0, size=0.18,
                         color=(0.35, 0.75, 0.65), region="CubeRgn", region_size=(3.6, 2.2, 1.0), center_y=0.0,
                         turbulence=0.0, glow=2)
        bg = F.xf(g, "LatticeDrift", bg, size=f"1 + 0.04*{e_inout(prog(0, g.frames))}", edges=1)
        g.at(0, 2)
        # converging point field
        pts = g.add("pEmitter", "PointCloudEmitter")
        pts.expr("Number", f"60*{ctl('ParticleIntensity')}*(1 - {step(I)})", 60)
        pts.set(Lifespan=300, Velocity=0.0, Region=F.FuID("CubeRgn"))
        pts.setk("ParticleStyle.ColorControls", 1)
        for kk, v in (("Red", 0.6), ("Green", 1.0), ("Blue", 0.9), ("Size", 0.22), ("SizeVariance", 0.12)):
            pts.setk(f"ParticleStyle.{kk}", v)
        pts.setk("CubeRgn.Width", 1.3)
        pts.setk("CubeRgn.Height", 0.22)
        pts.setk("CubeRgn.Depth", 0.2)
        ptt = g.add("pTurbulence", "PointCloudTurb")
        ptt.conn("Input", pts)
        ptt.expr("XStrength", f"0.6*(1 - {e_out(u, 2)})", 0.6)
        ptt.expr("YStrength", f"0.6*(1 - {e_out(u, 2)})", 0.6)
        prd = g.add("pRender", "PointCloudRender")
        prd.conn("Input", ptt)
        F.frame_inputs(prd, g)
        conv = F.xf(g, "PointConverge", prd, size=f"3.2 - 2.2*{e_out(u, 3)}",
                    angle=f"25*(1 - {e_out(u, 3)})")
        cglow = F.softglow(g, "PointGlow", conv, 4, gain=f"1.5*{ctl('GlowStrength')}", threshold=0.05)
        placedp = F.title_placement(g, "PointPlace", cglow)
        bg = F.merge(g, "PointCloud", bg, placedp, mode="Screen",
                     blend=f"min({ctl('ParticleIntensity')}, 1)*{clamp01(f'(time - {S})/12')}*(1 - {res})")
        # data streaks
        masks = []
        for j in range(6):
            spd = 0.004 + 0.003 * ((j * 7) % 5)
            y = 0.3 + 0.07 * j + 0.01 * (j % 2)
            m = F.rect(g, f"DataLine{j}", (0.5, y), 0.06 + 0.02 * (j % 3), 0.0016, 0.0005)
            m.expr("Center", f"Point(({j * 0.37:.2f} + time*{spd:.4f}) - floor({j * 0.37:.2f} + time*{spd:.4f})*1.0"
                             f" - 0.1, {y:.3f})", [0.5, y])
            masks.append(m)
        dl = F.accent_solid(g, "DataLineColor", 1.0)
        F.masked(dl, X.chain(masks))
        XS = ctl("ExitStart")
        busy = f"(1 - {res})*{clamp01(f'(time - {S})/12')} + 0.6*{window(ctl('ExitStart'), f'{XS} + 20', 2, 8)}"
        bg = F.merge(g, "DataLines", bg, dl, mode="Screen", blend=f"min(0.45*({busy}), 1)")

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Orbitron", "Medium", 0.1, 1.1, color=p["TEXT_COLOR"])
        edge = F.edge_light(g, "MintEdge", title, 0.0, -0.002, accent=True, gain=1.3, blur_px=1.0)
        face = F.merge(g, "EdgeMerge", title, edge, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.5 + 1.5*{decay(I, 8)}), 1)")
        g.at(0, 6)
        rn = F.noise(g, "ResolveNoise", "#000000", "#ffffff", detail=1, scale=28, seethe_rate=0.0, contrast=3.0)
        rm = F.bitmap_mask(g, "ResolveMask", rn, channel="Luminance")
        thr = f"(1 - {res}*1.1 + {de}*1.1)"
        rm.expr("Low", f"{thr} - 0.05", 0)
        rm.expr("High", f"{thr}", 0.05)
        hold = F.solid(g, "ResolveHolder", (0, 0, 0), alpha=0.0)
        resolved = F.merge(g, "ResolvedTitle", hold, face)
        F.masked(resolved, rm)
        placed = F.title_placement(g, "TitlePlace", resolved, size_expr=f"1 + 0.04*{e_inout(prog(0, g.frames))}")
        glow = F.softglow(g, "TitleGlow", placed, 10, gain=f"{ctl('GlowStrength')}*(0.3 + {decay(I, 10)})",
                          threshold=0.3)
        scene = F.merge(g, "TitleOverVoid", bg, glow)
        g.at(0, 8)
        scene = F.particles(g, "Decompile", scene, number=200, lifespan=40, velocity=0.006, angle=90, angle_var=30,
                            size=0.25, color=(0.6, 1.0, 0.9), region="CubeRgn", region_size=(1.2, 0.2, 0.1),
                            center_y=0.0, turbulence=0.1, glow=3,
                            number_expr=f"200*{ctl('ParticleIntensity')}*{window(ctl('ExitStart'), f'{XS} + 16', 1, 2)}")
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.028, 1.6,
                                    color=(0.62, 0.86, 0.8), y_off=-0.11)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 12", f"{ctl('ExitStart')} - 3", 14, 8))
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T23()
