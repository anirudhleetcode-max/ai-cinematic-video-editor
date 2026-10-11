"""T35 - Frozen Kingdom."""
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

ICE = Material(base=(0.78, 0.88, 0.97), spec=(0.9, 0.97, 1.0), spec_power=80, spec_gain=0.9, diffuse=0.55,
               ambient=0.16, metal=0.45, env_sky=(0.75, 0.88, 1.0), env_horizon=(0.12, 0.2, 0.3),
               env_ground=(0.08, 0.12, 0.18), env_sharp=10, bevel=0.06, texture="ice", tex_amount=0.25,
               bump=0.015, rim=(0.7, 0.88, 1.0), seed=35)

SEEDS = ((-0.42, -0.15, 0.00), (-0.14, 0.25, 0.22), (0.16, -0.2, 0.10), (0.43, 0.18, 0.30))  # u, v, delay


def spires(seed, n, y_base, h_rng, w_rng, spread=2.2, gap=0.0):
    """Ice spires along the ground; `gap` keeps |x| < gap clear (title area)."""
    r = np.random.default_rng(seed)
    out = []
    for i in range(n):
        x = -spread + 2 * spread * (i + r.uniform(0.15, 0.85)) / n
        if abs(x) < gap:
            x = math.copysign(gap + r.uniform(0, 0.25), x if x != 0 else 1)
        h = r.uniform(*h_rng)
        w = r.uniform(*w_rng)
        lean = r.uniform(-0.12, 0.12) * h
        out.append((x, y_base, w, h, lean, r.uniform(0.35, 0.65)))
    return out


class T35(Design):
    ID = "T35"
    NAME = "Frozen Kingdom"
    SLUG = "Frozen_Kingdom"
    CATEGORY = "D - Atmosphere and Environment"
    CONCEPT = "In a hall of ice spires the title freezes into existence: frost crawls across an invisible pane and becomes letters."
    ENTRANCE = ("Frost propagation: from four nucleation points, branching frost dendrites grow and the letters "
                "crystallise behind the advancing frost front (white rime at the front, clear ice behind).")
    REVEAL = "At the impact frame the ice 'locks': a cold glint sweeps the faces and a ring of fine crystals bursts outward."
    CAMERA = "Slow lateral glide with parallax between two layers of ice spires, ground mist and falling ice."
    MATERIAL = "Clear blue ice with refracted inner texture, sharp cold specular and pale rim light."
    EXIT = "The ice sublimates: the frost front runs backwards and the letters evaporate into rising cold vapour."
    TECHNIQUES = ["frost-front reveal field", "growing frost dendrites (crack_lines/draw_partial)",
                  "parallax ice spires", "falling ice glints", "cold rim light", "sublimation exit"]
    DURATION_FRAMES = 204
    DEFAULTS = dict(MAIN_TITLE="WINTERFALL", SUBTITLE="THE THRONE OF ICE AWAKENS", FONT_FAMILY="cinzel_bold",
                    TEXT_COLOR="#DCEBFA", ACCENT_COLOR="#9CD6FF", ANIMATION_START=14, ANIMATION_DURATION=74,
                    IMPACT_FRAME=92, HOLD_DURATION=70, EXIT_START=164, EXIT_DURATION=36, LETTER_SPACING=0.05,
                    TITLE_WIDTH=0.62, SUB_FONT_FAMILY="teko")
    SOUND = [(0, "wind", "Cold high wind, glassy air"), (0, "atmos", "Low icy drone"),
             (14, "ice", "Crackling frost growth (continuous)"), (60, "riser", "Crystalline riser"),
             (92, "ice", "Ice lock: sharp glassy crack"), (92, "sub", "Soft sub under the lock"),
             (94, "shimmer", "Glint shimmer"), (164, "wind", "Sublimation hiss / vapour"),
             (190, "tail", "Glassy tail")]

    # ------------------------------------------------------------ preview --
    def _frost(self, c, sp):
        f = c.cache.get("frost")
        if f is not None:
            return f
        hh, ww = sp.h, sp.w
        ys, xs = np.mgrid[0:hh, 0:ww].astype(np.float32)
        R = max(1.0, sp.ink_w * 0.33)
        field = np.full((hh, ww), 9.0, np.float32)
        pts = []
        for su, sv, dl in SEEDS:
            px = sp.anchor[0] + su * sp.ink_w
            py = sp.anchor[1] + sv * sp.ink_h
            pts.append((px, py, dl))
            field = np.minimum(field, np.sqrt((xs - px) ** 2 + (ys - py) ** 2) / R + dl)
        nz = D.sprite_noise(sp, 2.5, 51, 1.6)
        field = field + (nz - 0.5) * 0.35
        lines = []
        for i, (px, py, dl) in enumerate(pts):
            ls = E.crack_lines(350 + i, (0.0, 0.0), n=9, length=0.8, segs=18, jitter=0.55)
            scale = sp.cap_px * 1.15
            lines.append([np.stack([px + l[:, 0] * scale, py + l[:, 1] * scale], 1) for l in ls])
        f = c.cache["frost"] = (field, lines, pts, float(field[sp.mask > 0.5].max()))
        return f

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.02, 0.5)
        glide = K.ease_in_out(K.prog(t, 0, c.dur), 2)
        pan = (0.5 - glide) * 0.2
        nx, ny = K.grid(H, W)

        # cold hall ----------------------------------------------------------------
        bg = K.vgrad(H, W, (0.010, 0.020, 0.045), (0.035, 0.065, 0.10), 1.2) * bgI
        bg += (K.soft_spot(H, W, 0.0, -0.1, 1.6, 0.8, 1.2) * 0.07 * bgI)[..., None] * acc

        def draw_spires(layer_spires, par, lit_col, dark_col, edge_col, blur_px):
            buf = np.zeros((H // 2, W // 2, 3), np.float32)
            s = H / 4  # half-res pixels per normalised unit
            for (x, yb, w, h, lean, split) in layer_spires:
                X = (x + pan * par) * s + W / 4
                Yb = yb * s + H / 4
                tip = (X + lean * s, Yb - h * s)
                L = (X - w * s, Yb)
                Rr = (X + w * s, Yb)
                M = (X + (split - 0.5) * w * s, Yb)
                cv2.fillPoly(buf, [np.int32([tip, L, M])], tuple(float(v) for v in lit_col), cv2.LINE_AA)
                cv2.fillPoly(buf, [np.int32([tip, M, Rr])], tuple(float(v) for v in dark_col), cv2.LINE_AA)
                cv2.line(buf, (int(tip[0]), int(tip[1])), (int(L[0]), int(L[1])), tuple(float(v) for v in edge_col),
                         1, cv2.LINE_AA)
            if blur_px:
                buf = cv2.GaussianBlur(buf, (0, 0), blur_px)
            return cv2.resize(buf, (W, H))

        sp_far = c.cache.setdefault("spf", spires(5, 16, 0.5, (0.35, 0.9), (0.04, 0.09)))
        sp_near = c.cache.setdefault("spn", spires(9, 8, 1.0, (0.9, 1.9), (0.08, 0.16), 2.6, 1.25))
        far = draw_spires(sp_far, 0.4, (0.10, 0.18, 0.27), (0.04, 0.08, 0.13), acc * 0.5, 1.6 * k)
        mfar = (far.max(2) > 0.01).astype(np.float32)[..., None]
        bg = bg * (1 - mfar) + far * bgI
        mist_f = D.shaped(D.plane(H, W, t, 1.2, (0.01, 0.0), 13, 1.0, (pan * 0.5, 0), stretch=(3, 1)), 0.25, 1.0)
        bg += (mist_f * np.clip((ny - 0.0) * 1.5, 0, 1) * 0.12 * bgI)[..., None] * (acc * 0.5 + 0.3)

        # title + frost ------------------------------------------------------------
        sp = c.title()
        sh = c.shaded(ICE)
        field, lines, pts, fmax = self._frost(c, sp)
        front = (fmax + 0.25) * K.ease_in_out(u, 1.6) - 0.05
        back = (fmax + 0.3) * K.ease_in(ex, 1.5)  # sublimation (runs backwards from the far end)
        rim_band = np.clip(1 - np.abs(front - field) / 0.12, 0, 1)
        a_rev = np.clip((front - field) / 0.08, 0, 1)
        a_ex = np.clip(((fmax - field) - back) / 0.1 + 1, 0, 1) if ex > 0 else 1.0
        sw = K.prog(t, imp, 0.9)
        sweep = (-0.8 + 1.7 * K.ease_out(sw, 2), 0.08, 0.7, 1.6 * (1 if 0 < sw < 1 else 0) * p["IMPACT_INTENSITY"])
        rgb, a = sh.shade(light=(-0.3, -0.8, 0.55), rim_dir=(-0.3, -1), rim_gain=0.6 + 1.2 * hit, sweep=sweep,
                          base=K.col(p["TEXT_COLOR"]), light_gain=1.05, env_shift=0.1 * math.sin(t * 0.3))
        rime = (rim_band * (1 - K.smooth(K.prog(t, imp, 0.8))) + 0.0)
        rgb = rgb * (1 - 0.6 * rime[..., None]) + rime[..., None] * 1.1
        a = a * a_rev * a_ex
        cam = c.cam(zoom=1.0 + 0.04 * glide, pan=(pan * H / 2 * 0.3, 0))
        L = c.layer()
        c.place(L, cam, rgb, a, sp, 1.0)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.35, (0, 14), 26, k)
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.75, 0), 8 * k) * 0.5 * p["GLOW_STRENGTH"]

        # frost dendrites on the invisible pane (sprite space, placed with the title)
        if u > 0 and ex < 1:
            dend = np.zeros((sp.h, sp.w, 3), np.float32)
            for i, (px, py, dl) in enumerate(pts):
                frac = K.clamp((front - dl) / 0.9)
                if frac <= 0:
                    continue
                arr = [((ln) * 4).astype(np.int32).reshape(-1, 1, 2)[:max(2, int(len(ln) * frac))] for ln in lines[i]]
                cv2.polylines(dend, arr, False, (0.8, 0.8, 0.8), max(1, int(1.0 * k)), cv2.LINE_AA, shift=2)
            dend = dend + K.blur(dend, 2.5 * k) * 0.8
            fade = (0.6 - 0.48 * K.smooth(K.prog(t, imp, 1.5))) * (1 - K.smooth(ex * 1.5))
            da = np.clip(dend[..., 0], 0, 1) * fade
            drgb = np.empty_like(dend)
            drgb[...] = acc * 0.6 + 0.4
            Ld = c.layer()
            c.place(Ld, cam, drgb, da, sp, 1.0)
            img = img + Ld.rgb * 0.9

        # crystal burst at the lock
        nP = int(200 * p["PARTICLE_INTENSITY"])
        if t >= imp and nP:
            dt = t - imp
            r = np.random.default_rng(35)
            ang = r.uniform(0, 2 * np.pi, nP // 2)
            spd = r.uniform(0.3, 1.2, nP // 2)
            hx, hy = c.hero()
            ox = r.uniform(-0.5, 0.5, nP // 2) * sp.ink_w / (H / 2)
            dist = spd * (1 - math.exp(-dt * 3)) / 3 * 0.8
            gx = hx / (H / 2) + ox + np.cos(ang) * dist
            gy = hy / (H / 2) + np.sin(ang) * dist * 0.5 + 0.03 * dt * dt
            Pb = E.Particles(nP // 2, 3)
            Pb.z = np.full(nP // 2, 1.0, np.float32)
            img += E.particle_layer(H, W, Pb, gx, gy, acc * 0.6 + 0.5, 1.0, 0.9 * math.exp(-dt / 0.9), glow=1.0,
                                    flicker=0.6, t=t)

        # near spires (foreground parallax), falling ice, ground mist
        near = draw_spires(sp_near, 1.4, (0.05, 0.10, 0.16), (0.015, 0.03, 0.05), acc * 0.35, 2.5 * k)
        mn = cv2.GaussianBlur((near.max(2) > 0.005).astype(np.float32), (0, 0), 2 * k)[..., None]
        img = img * (1 - mn) + near * bgI
        if nP:
            P = c.cache.get("ice")
            if P is None:
                P = c.cache["ice"] = E.Particles(nP, seed=36, z=(0.4, 3.0))
            x, y = P.drift(t, vel=(0.01, 0.05), turb=0.04, freq=0.5)
            img += E.particle_layer(H, W, P, x + pan * 0.3, y, (0.8, 0.92, 1.0), 1.1, 0.4, zoom=1 + 0.04 * glide,
                                    focus=1.0, dof=1.0, flicker=0.7, t=t, glow=0.8)
        vap = D.shaped(D.plane(H, W, t, 1.5, (0.008, -0.03), 17, 1.0, (pan * 1.5, 0)), 0.35, 1.0)
        hx, hy = c.hero()
        vap_env = K.soft_spot(H, W, hx / (H / 2), hy / (H / 2) - 0.1, 1.2, 0.4, 1.5)
        mist_n = np.clip((ny - 0.35) * 1.4, 0, 1) * 0.3 + vap_env * 0.6 * K.smooth(ex) * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur, 0.5)))
        img = D.over(img, (acc * 0.4 + 0.25) * bgI, vap * mist_n)

        img = subtitle(c, img, cam, imp + 0.6, c.exit_start - 0.2, (0.75, 0.86, 0.96), y_rel=0.82)
        return c.finish(img, vignette=0.55, grain=0.03, bloom=(0.75, 0.5),
                        grade=dict(shadows=(-0.004, 0.0, 0.008), highlights=(-0.01, 0.0, 0.015), contrast=1.05))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"], "Frost Light Color")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        glide = e_inout(prog(0, g.frames))

        g.at(0, 0)
        bg = F.gradient_bg(g, "ColdHall", [(0, "#03050c", 1), (1, "#091119", 1)], start=(0.5, 1.0), end=(0.5, 0.0))
        bg = F.light_spot(g, "HallGlow", bg, None, (0.5, 0.55), 1.2, 0.6, 0.6, accent=True, gain=0.3,
                          blend=f"0.5*{BG}")

        def spire_layer(name, seed, n, ybase, hr, wr, spread, gap, lit, dark, par, base):
            masks_l, masks_d = None, None
            for i, (x, yb, w, h, lean, split) in enumerate(spires(seed, n, ybase, hr, wr, spread, gap)):
                cx = 0.5 + x * 0.5 * 9 / 16 * 1.0
                ybn = 0.5 - yb * 0.5
                tip = (cx + lean * 0.5 * 9 / 16, ybn + h * 0.5)
                Lp = (cx - w * 0.5 * 9 / 16, ybn)
                Rp = (cx + w * 0.5 * 9 / 16, ybn)
                Mp = (cx + (split - 0.5) * w * 0.5 * 9 / 16, ybn)
                ml = F.closed_poly_mask(g, f"{name}{i}Lit", [tip, Lp, Mp])
                md = F.closed_poly_mask(g, f"{name}{i}Dark", [tip, Mp, Rp])
                if masks_l is not None:
                    ml.conn("EffectMask", masks_l, "Mask")
                    md.conn("EffectMask", masks_d, "Mask")
                masks_l, masks_d = ml, md
            sl = F.solid(g, f"{name}LitColor", lit)
            F.masked(sl, masks_l)
            sd = F.solid(g, f"{name}DarkColor", dark)
            F.masked(sd, masks_d)
            m = F.merge(g, f"{name}Faces", sl, sd)
            x = F.xf(g, f"{name}Parallax", m, center=f"Point(0.5 + {par}*(0.5 - {glide}), 0.5)")
            return F.merge(g, name, base, x, blend=f"min({BG}, 1)")

        g.at(0, 2)
        bg = spire_layer("SpiresFar", 5, 16, 0.5, (0.35, 0.9), (0.04, 0.09), 2.2, 0.0, "#1a2e45", "#0a1521", 0.02, bg)
        bg = D.f_fog(g, "GroundMistFar", bg, "#000000", "#2c4a63", 2.0, "1", (0.0004, 0.0), blend=f"0.4*{BG}")

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Cinzel", "Bold", 0.16, 1.05, color=p["TEXT_COLOR"])
        ice = F.fill_material(g, "IceRefraction", title,
                              [(0, "#6f8fb0", 1), (0.4, "#c8def2", 1), (0.5, "#ffffff", 1), (0.6, "#9cb6cf", 1),
                               (1, "#4d6a88", 1)])
        face = F.merge(g, "IceFace", title, ice, mode="Multiply", blend=0.8)
        rim = F.edge_light(g, "ColdRim", title, 0.0015, -0.003, accent=True, gain=1.4, blur_px=1.0)
        face = F.merge(g, "ColdRimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.6 + 0.8*{decay(I, 10)}), 1)")
        face = F.light_sweep(g, "LockGlint", face, title, I, 22, angle=40, width=0.05, peak=1.0)
        g.at(0, 6)
        # frost-front field: horizontal ramp + crystal noise, thresholded by the reveal progress
        ramp = F.gradient_bg(g, "FrostRamp", [(0, "#000000", 1), (1, "#ffffff", 1)], start=(0.2, 0.5), end=(0.8, 0.5))
        fn = F.noise(g, "FrostNoise", "#000000", "#ffffff", detail=8, scale=12, seethe_rate=0.0, contrast=1.6)
        field = F.merge(g, "FrostField", ramp, fn, mode="Overlay", blend=0.6)
        fm = F.bitmap_mask(g, "FrostFront", field, channel="Luminance")
        fm.expr("Low", f"1.1*{e_inout(u)} - 0.08 - 1.2*{e_in(ex, 1.5)}", 0)
        fm.expr("High", f"1.1*{e_inout(u)} - 1.2*{e_in(ex, 1.5)}", 0)
        fm.set(Invert=1)
        hold = F.solid(g, "TitleHolder", (0, 0, 0), alpha=0.0)
        tm = F.merge(g, "TitleCrystallise", hold, face)
        F.masked(tm, fm)
        placed = F.title_placement(g, "TitlePlace", tm)
        tglow = F.softglow(g, "IceGlow", placed, 9, gain=f"0.6*{ctl('GlowStrength')}", threshold=0.7)
        scene = F.merge(g, "TitleInHall", bg, tglow)

        g.at(0, 8)
        # frost dendrites: stroked polylines, revealed by growing circles from each nucleation point
        r = np.random.default_rng(7)
        prev_reveal = None
        dend_all = None
        for i, (su, sv, dl) in enumerate(SEEDS):
            cx, cy = 0.5 + su * 0.62, 0.5 + sv * 0.08
            strokes = None
            for j, ln in enumerate(E.crack_lines(350 + i, (0.0, 0.0), n=4, length=1.0, segs=10, jitter=0.42)[:4]):
                pts = [(cx + q[0] * 0.09 * 9 / 16, cy - q[1] * 0.09) for q in ln]
                sm = F.polyline_mask(g, f"Dendrite{i}_{j}", pts, border=0.0012, soft=0.0008)
                if strokes is not None:
                    sm.conn("EffectMask", strokes, "Mask")
                strokes = sm
            grow = F.ellipse(g, f"FrostGrow{i}", (cx, cy), 0.01, 0.01, 0.05)
            gs = f"(2.2*max({e_inout(u)} - {dl * 0.5:.2f}, 0))"
            grow.expr("Width", gs, 0.01)
            grow.expr("Height", f"{gs}*1.7778", 0.01)
            grow.set(PaintMode=F.FuID("Multiply"))
            grow.conn("EffectMask", strokes, "Mask")
            if dend_all is not None:
                # combine this seed's revealed strokes with the previous ones
                comb = F.bitmap_mask(g, f"DendriteSet{i}", dend_all)
                grow2 = grow
                comb.conn("EffectMask", grow2, "Mask")
                dend_src = comb
            else:
                dend_src = grow
            dcol = F.accent_solid(g, f"DendriteColor{i}", 1.2, alpha=1.0)
            F.masked(dcol, dend_src)
            dend_all = dcol
        dplaced = F.title_placement(g, "DendritePlace", dend_all)
        dglow = F.softglow(g, "DendriteGlow", dplaced, 4, gain=f"{ctl('GlowStrength')}", threshold=0.1)
        scene = F.merge(g, "Dendrites", scene, dglow, mode="Screen",
                        blend=f"(0.7 - 0.45*{e_out(prog(I, 36), 2)})*(1 - {ex})")
        scene = F.particles(g, "CrystalBurst", scene, number=180, lifespan=26, velocity=0.02, angle=90, angle_var=180,
                            size=0.25, color=(0.85, 0.95, 1.0), region="CubeRgn", region_size=(1.2, 0.15, 0.2),
                            center_y=0.0, turbulence=0.1, glow=4,
                            number_expr=f"180*{ctl('ParticleIntensity')}*{window(I, I + ' + 2', 1, 1)}")
        g.at(0, 10)
        scene = spire_layer("SpiresNear", 9, 8, 1.0, (0.9, 1.9), (0.08, 0.16), 2.6, 1.25, "#0d1a29", "#04080e", 0.07, scene)
        scene = F.particles(g, "FallingIce", scene, number=10, lifespan=140, velocity=0.004, angle=-90, angle_var=20,
                            size=0.22, color=(0.85, 0.94, 1.0), region="CubeRgn", region_size=(2.4, 0.1, 1.0),
                            center_y=0.7, turbulence=0.08, glow=3)
        vm = F.ellipse(g, "VapourArea", (0.5, 0.45), 1.0, 0.5, 0.5)
        vm.expr("Center", f"Point({ctl('TextPosX')}, {ctl('TextPosY')} + 0.08*{ex})", [0.5, 0.5])
        scene = D.f_fog(g, "SublimationVapour", scene, "#000000", "#a8c8e0", 3.0, "1", (0.0002, 0.002),
                        blend=f"0.7*{ex}*(1 - {prog(ctl('ExitStart') + ' + ' + ctl('ExitDuration'), 12)})",
                        mode="Normal", mask=vm)
        scene = D.f_sub(g, p, "Teko", "SemiBold", (0.75, 0.86, 0.96), -0.13, f"{I} + 14", f"{ctl('ExitStart')} - 5",
                        scene=scene)
        scene = F.xf(g, "Camera", scene, center=f"Point(0.5 + 0.01*(0.5 - {glide}), 0.5)", size=f"1 + 0.04*{glide}",
                     edges=1)
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T35()
