"""T16 - Ancient Titan (2.5D)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01, shake
from ..typo import Material
from ._b_helpers import put_title, add_sub, fam, fusion_subtitle

STONE = Material(base=(0.55, 0.50, 0.43), spec=(1.0, 0.9, 0.75), spec_power=12, spec_gain=0.12, diffuse=0.95,
                 ambient=0.10, metal=0.0, bevel=0.05, bevel_round=False, texture="stone", tex_amount=0.45,
                 bump=0.05, rim=(1.0, 0.85, 0.65), seed=81)

# ruin silhouettes per layer: list of (x centre, width, height, broken-top jitter) in normalised units
def _ruins(seed, n, xr, wr, hr):
    r = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        out.append((r.uniform(*xr), r.uniform(*wr), r.uniform(*hr), r.uniform(0.02, 0.08), r.integers(1e6)))
    return out


FAR = _ruins(5, 11, (-2.0, 2.0), (0.05, 0.12), (0.15, 0.55))
MID = [(x, w, h, j, sd) for x, (_, w, h, j, sd) in zip((-1.72, -1.38, -1.02, 1.08, 1.42, 1.80),
                                                      _ruins(9, 6, (0, 1), (0.10, 0.16), (0.45, 0.95)))]


class T16(Design):
    ID = "T16"
    NAME = "Ancient Titan"
    SLUG = "Ancient_Titan"
    CATEGORY = "C - Mythic Atmospheres"
    CONCEPT = "A colossal carved-stone title rises out of the ground of a ruined, hazy ancient valley."
    ENTRANCE = ("Under a continuous low rumble the monumental stone letters grind up out of the earth, shedding "
                "dust and grit, while ground dust billows along their base.")
    REVEAL = ("On the impact frame the title settles to full height with a heavy thud: a ground-hugging dust "
              "wave rolls outward and a shaft of low sun rakes across the carved faces.")
    CAMERA = "Low worm's-eye angle, slow upward tilt with parallax between ruin layers; rumble shake while rising."
    MATERIAL = ("Weathered sandstone: stone texture bump, flat-cut chamfer, hard directional side-light from "
                "the left, deep 2.5D extrusion stack; atmospheric perspective on the ruins.")
    EXIT = "Haze thickens and rolls across the valley, swallowing the title into atmosphere."
    TECHNIQUES = ["2.5D extrusion stack", "ground-occluded rise", "ruin parallax layers", "atmospheric perspective",
                  "dust shed + ground dust wave", "raking sun shaft", "haze swallow exit"]
    TRUE_3D = False
    DURATION_FRAMES = 240
    DEFAULTS = dict(MAIN_TITLE="TITAN", SUBTITLE="OLDER THAN THE GODS", FONT_FAMILY="anton", FONT_SIZE=0.26,
                    SUB_FONT_FAMILY="cinzel_bold", TEXT_COLOR="#9A8E7C", ACCENT_COLOR="#FFC07A",
                    ANIMATION_START=16, ANIMATION_DURATION=96, IMPACT_FRAME=112, HOLD_DURATION=72, EXIT_START=186,
                    EXIT_DURATION=44, LETTER_SPACING=0.08, TITLE_WIDTH=0.5, TEXT_POSITION_Y=0.56)
    SOUND = [(0, "wind", "Desert valley wind"), (0, "atmos", "Low distant drone"),
             (16, "riser", "Stone grinding rumble rising"), (16, "debris", "Grit trickle"),
             (60, "debris", "Falling stones"), (112, "impact", "Colossal thud"), (112, "sub", "Ground sub drop"),
             (114, "debris", "Dust wave"), (186, "wind", "Haze gust"), (210, "tail", "Long tail")]

    # ------------------------------------------------------------ preview --
    def build_env(self, c, horizon):
        """Static valley plate (cached): far layer (sky, sun, hazy far ruins, hills) and a mid layer
        (RGBA: lit stone columns, architraves, broken tops, fallen blocks, ground)."""
        H, W, k = c.H, c.W, c.k
        acc = K.col(c.p["ACCENT_COLOR"])
        bgI = c.p["BACKGROUND_INTENSITY"]
        haze = K.col((0.42, 0.38, 0.33))
        hn = (horizon - H / 2) / (H / 2)
        far = K.vgrad(H, W, (0.09, 0.09, 0.10), (0.40, 0.355, 0.30), gamma=0.8)
        far += (K.soft_spot(H, W, -1.45, hn - 0.22, 1.2, 0.55, 1.2) * 0.45)[..., None] * acc
        far += (K.soft_spot(H, W, -1.45, hn - 0.22, 0.18, 0.12, 2.0) * 0.5)[..., None] * (acc * 0.5 + 0.5)
        # far hills
        xs = np.arange(W, dtype=np.float32)
        hill = horizon - (0.04 + 0.03 * np.sin(xs / W * 7.1 + 1.3) + 0.015 * np.sin(xs / W * 23 + 0.4)) * H
        ys = K.pixgrid(H, W)[1]
        hm = np.clip((ys - hill[None, :]) / 2.0, 0, 1)
        far = far * (1 - hm[..., None] * 0.2) + hm[..., None] * haze * 0.25
        # far ruins (pale, hazy)
        fm = np.zeros((H, W), np.float32)
        for x, w, h, jit, sd in FAR:
            self._column(fm, None, W / 2 + x * 0.55 * H / 2, w * 0.3 * H / 2, h * 0.55 * H / 2, horizon + 0.004 * H,
                         jit * H * 0.2, int(sd), k)
        fm = cv2.GaussianBlur(fm, (0, 0), 1.2 * k)
        far = far * (1 - fm[..., None] * 0.5) + fm[..., None] * haze * 0.62
        # mid layer: lit columns
        ma = np.zeros((H, W), np.float32)
        lit = np.zeros((H, W), np.float32)
        for x, w, h, jit, sd in MID:
            self._column(ma, lit, W / 2 + x * 0.95 * H / 2, w * 0.5 * H / 2, h * 0.75 * H / 2, horizon + 0.02 * H,
                         jit * H * 0.35, int(sd), k)
        # architrave across the first pair of tall columns
        xs_ = sorted(MID, key=lambda r: r[0])
        for j in range(0, len(xs_) - 1, 3):
            x0 = W / 2 + xs_[j][0] * 0.95 * H / 2
            x1 = W / 2 + xs_[j + 1][0] * 0.95 * H / 2
            if abs(x1 - x0) < 0.45 * H:
                ytop = horizon + 0.02 * H - min(xs_[j][2], xs_[j + 1][2]) * 0.75 * H / 2
                cv2.rectangle(ma, (int(x0 * 4), int((ytop - 22 * k) * 4)), (int(x1 * 4), int(ytop * 4)), 1.0, -1,
                              cv2.LINE_AA, shift=2)
        # fallen blocks + ground
        r = np.random.default_rng(14)
        for _ in range(14):
            bx = r.uniform(0, W)
            by = horizon + 0.02 * H + r.uniform(0, 0.12) * H
            bw, bh = r.uniform(20, 70) * k, r.uniform(10, 26) * k
            ang = r.uniform(-12, 12)
            box = cv2.boxPoints(((bx, by), (bw, bh), ang))
            cv2.fillPoly(ma, [np.int32(box * 4)], 1.0, cv2.LINE_AA, shift=2)
        gm = np.clip((ys - (horizon + 0.02 * H)) / 2.0, 0, 1)
        ma = np.maximum(ma, gm)
        gfall = np.clip((ys - horizon) / (0.45 * H), 0, 1)
        stone = K.col((0.17, 0.15, 0.13))
        gtex = K.sample(K.fft_noise(256, 1.6, 78), H, W, 3.0, stretch=(6.0, 1.0))
        grain = K.sample(K.fft_noise(256, 1.2, 77), H, W, 6.0)
        mid = stone[None, None, :] * (0.75 + 0.5 * grain[..., None])
        mid = mid * (1 - 0.55 * gfall[..., None]) * (0.7 + 0.6 * gtex[..., None] * gm[..., None] + 0.3 * (1 - gm[..., None])) + lit[..., None] * acc * 0.22 + \
            (gm * (1 - gfall) * 0.10)[..., None] * haze
        # atmospheric perspective on the mid layer too
        mid = mid * 0.8 + haze * 0.12
        return far * bgI, mid * bgI, ma

    @staticmethod
    def _column(mask, lit, cx, hw, h, base, jit, sd, k):
        r = np.random.default_rng(sd)
        top = base - h
        broken = sd % 3 != 0
        pts = [(cx - hw, base), (cx - hw * 0.92, top)]
        if broken:
            for i in range(1, 6):
                pts.append((cx - hw * 0.92 + 1.84 * hw * i / 6, top + r.uniform(0, jit)))
        pts += [(cx + hw * 0.92, top + (r.uniform(0, jit) if broken else 0)), (cx + hw, base)]
        cv2.fillPoly(mask, [np.int32(np.array(pts) * 4)], 1.0, cv2.LINE_AA, shift=2)
        if not broken:  # capital + abacus
            cv2.rectangle(mask, (int((cx - hw * 1.45) * 4), int((top - 9 * k) * 4)),
                          (int((cx + hw * 1.45) * 4), int((top + 3 * k) * 4)), 1.0, -1, cv2.LINE_AA, shift=2)
        cv2.rectangle(mask, (int((cx - hw * 1.3) * 4), int((base - 8 * k) * 4)),
                      (int((cx + hw * 1.3) * 4), int(base * 4)), 1.0, -1, cv2.LINE_AA, shift=2)
        if lit is not None:  # sun from the left lights the left third of each shaft; flutes
            pl = np.array([(cx - hw, base), (cx - hw * 0.92, top + jit), (cx - hw * 0.35, top + jit),
                           (cx - hw * 0.4, base)])
            cv2.fillPoly(lit, [np.int32(pl * 4)], 1.0, cv2.LINE_AA, shift=2)
            for f in np.linspace(-0.6, 0.6, 5):
                x = cx + f * hw
                cv2.line(lit, (int(x * 4), int((top + jit) * 4)), (int(x * 4), int((base - 10 * k) * 4)), -0.4,
                         max(1, int(2 * k)), cv2.LINE_AA, shift=2)

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.03, 0.5)
        after = 1.0 if t >= imp else 0.0
        T = K.prog(t, 0, c.dur)
        nx, ny = K.grid(H, W)
        hx, hy = c.hero()
        sp = c.title()

        # camera: worm's-eye, slow upward tilt (scene drifts down) + slow push
        zoom = 1.0 + 0.06 * K.ease_in_out(T, 2)
        tilt_px = 60 * k * K.ease_in_out(T, 2)
        ground = float(H / 2 + hy + float(sp.ink_h) * 0.5 * zoom + tilt_px)  # title base / ground line (pixels)
        horizon = float(H / 2 + hy + float(sp.ink_h) * 0.5 - 0.02 * H)  # static plate horizon

        haze_c = K.col((0.42, 0.38, 0.33)) * bgI
        env = c.cache.get("env")
        if env is None:
            env = c.cache["env"] = self.build_env(c, horizon)
        far, mid, ma = env
        par = 26 * k * T  # parallax drift
        Mf = np.float32([[1, 0, par * 0.3], [0, 1, tilt_px * 0.55]])
        Mm = np.float32([[1, 0, par], [0, 1, tilt_px]])
        far_w = cv2.warpAffine(far, Mf, (W, H), borderMode=cv2.BORDER_REPLICATE)
        mid_w = cv2.warpAffine(mid, Mm, (W, H), borderMode=cv2.BORDER_REPLICATE)
        ma_w = cv2.warpAffine(ma, Mm, (W, H), borderMode=cv2.BORDER_REPLICATE)
        bg = far_w * (1 - ma_w[..., None]) + mid_w * ma_w[..., None]
        shaft = c.cache.get("shaft")
        if shaft is None:
            shaft = c.cache["shaft"] = E.light_cone(H, W, (-2.4, -0.9), 14, 18, 5.0, 0.3)
        bg += (shaft * (0.07 + 0.06 * after))[..., None] * acc * bgI
        ys = K.pixgrid(H, W)[1]

        # ---- title rising out of the ground
        sh = c.shaded(STONE)
        ue = K.ease_in_out(u, 1.6)
        rise = (1 - ue) * float(sp.ink_h) * 1.08
        settle = 5 * k * K.pulse(t, imp, 0.03, 0.2)
        rumble = (1 - after) * K.smooth(u * 6) * (1 - ue * 0.3)
        rx_, ry_ = K.shake(t, 0.0018 * rumble * p["SHAKE_AMOUNT"], 33, 4)
        rx_, ry_ = rx_ * H, ry_ * H
        sweep_u = K.prog(t, imp + 0.2, 2.2)
        sweep = (-0.8 + 1.6 * K.ease_in_out(sweep_u), 0.22, 0.4, 0.35 * (1 if 0 < sweep_u < 1 else 0))
        rgb, a = sh.shade(light=(-0.85, -0.35, 0.4), rim_gain=0.15 + 0.2 * after, rim_dir=(-1, 0), sweep=sweep,
                          base=K.col(p["TEXT_COLOR"]), light_gain=1.05)
        # dirt staining near the base while it is still emerging
        cam = c.cam(zoom=zoom, tilt=6, pan=(0, tilt_px))
        L = c.layer()
        depth = 0.22 * float(sp.cap_px) * p["EXTRUSION_DEPTH"]
        put_title(c, L, cam, rgb, a, sp, 1.0, off=(rx_, rise + settle + ry_, 0), depth=depth,
                  side=np.array((0.16, 0.14, 0.12)), slices=10, side_light=lambda q: 0.5 + 0.5 * q,
                  opacity=1.0 if t >= c.start else 0.0)
        # occlude by the ground: only what is above the ground line is visible
        occ = np.clip((ground + 2 * k - ys) / (3 * k), 0, 1)
        L.a *= occ
        L.rgb *= occ[..., None]
        # atmospheric perspective on the title itself (and the haze-swallow exit)
        fogamt = 0.10 + 0.75 * K.smooth(ex)
        L.rgb = L.rgb * (1 - fogamt) + haze_c * L.a[..., None] * fogamt
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.5, (40, 10), 30, k)
        img = comp(bg, L)

        # ---- dust: shed grit falling off the letters, base billow, impact wave, floating motes
        PI = p["PARTICLE_INTENSITY"]
        if PI > 0:
            if t >= c.start and t < imp + 1.5:
                G = c.cache.get("grit")
                if G is None:
                    r = np.random.default_rng(3)
                    n = int(220 * PI)
                    G = c.cache["grit"] = (n, r.uniform(-0.5, 0.5, n), r.random(n), r.random(n))
                n, gxr, ph, rr = G
                life = 0.9
                age = ((t * (0.8 + 0.4 * rr) + ph * life) % life)
                top_y = ground - float(sp.ink_h) * zoom + rise * zoom
                gx = (W / 2 + hx + gxr * float(sp.ink_w) * zoom) / (H / 2) - W / H
                gy0 = (top_y + rr * (ground - top_y) - H / 2) / (H / 2)
                gy = gy0 + 0.6 * age * age
                fade = (1 - age / life) * K.smooth(u * 5) * (1 - after * K.prog(t, imp, 1.0))
                Pg = E.Particles(n, 1)
                Pg.z = np.full(n, 1.0, np.float32)
                img += E.particle_layer(H, W, Pg, gx, gy, (0.55, 0.5, 0.44), 1.1, 0.6 * fade, glow=0.0,
                                        streak=(np.zeros(n), np.full(n, 0.012)))
            # base billow (smoke-like dust band at the ground line)
            band = np.exp(-((ys - ground) / (0.05 * H)) ** 2) * np.exp(-((K.grid(H, W)[0] - hx / (H / 2)) /
                                                                          (float(sp.ink_w) / H * 1.3)) ** 2)
            dust_amt = (0.55 * rumble + 1.1 * K.pulse(t, imp, 0.05, 1.2) * p["IMPACT_INTENSITY"]) * PI
            if dust_amt > 0.01:
                spread = 1 + 1.6 * K.ease_out(K.prog(t, imp, 2.5)) * after
                dn = E.fog(H, W, t, haze_c * 1.3, density=1.0, scale=2.0, speed=(0.03, -0.01), seed=21, warp=0.0, contrast=1.1)
                band2 = np.exp(-((ys - ground + 0.02 * H) / (0.06 * H * spread ** 0.5)) ** 2) * \
                    np.exp(-((K.grid(H, W)[0] - hx / (H / 2)) / (float(sp.ink_w) / H * 1.2 * spread)) ** 2)
                img = img + dn * (np.maximum(band, band2) * dust_amt)[..., None]
            M = c.cache.get("motes")
            if M is None:
                M = c.cache["motes"] = E.Particles(int(160 * PI), seed=12, z=(0.5, 3.0))
            x, y = M.drift(t, vel=(0.02, -0.004), turb=0.03, freq=0.3)
            lit = np.clip(1.2 - (x + 1.5) * 0.25, 0.2, 1.0)
            img += E.particle_layer(H, W, M, x, y, acc * 0.7 + 0.3, 1.4, 0.22 * lit, zoom=zoom, focus=1.2, dof=1.2,
                                    t=t, flicker=0.2, glow=0.6)
        # haze layer in front (always a little; thick on exit)
        front = E.fog(H, W, t, haze_c, density=1.0, scale=1.0, speed=(0.02, 0.0), seed=33, warp=0.0, contrast=1.0)
        famt = 0.10 + 0.85 * K.smooth(ex)
        img = img * (1 - 0.6 * famt) + (front * 0.6 + haze_c * 0.5) * famt
        img = add_sub(c, img, cam, imp + 0.8, c.exit_start + 0.2, (0.80, 0.72, 0.62), y_rel=-0.98,
                      tracking=0.45, rel=0.16)
        sx, sy = c.shake(0.007, 0.35, 12)
        if abs(sx) + abs(sy) > 0.05:
            Mx = np.float32([[1.01, 0, -0.005 * W + sx], [0, 1.01, -0.005 * H + sy]])
            img = cv2.warpAffine(img, Mx, (W, H), borderMode=cv2.BORDER_REFLECT)
        return c.finish(img, vignette=0.5, grain=0.04, bloom=(0.85, 0.35),
                        grade=dict(shadows=(0.0, 0.002, 0.006), highlights=(0.012, 0.004, -0.01), contrast=1.08,
                                   sat=0.85))

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
        PI = ctl("ParticleIntensity")
        ground_y = 0.40  # normalised (y up) ground line under the title at rest

        g.at(0, 0)
        bg = F.gradient_bg(g, "DuskSky", [(0, "#5c524a", 1), (0.55, "#3a3532", 1), (1, "#19191c", 1)],
                           start=(0.5, 0.0), end=(0.5, 1.0))
        bg = F.light_spot(g, "LowSun", bg, None, (0.0, 0.5), 1.0, 0.5, 0.6, accent=True, gain=0.5, blend=f"0.6*{BG}")
        for lay, (ruins, sc, col, yb) in enumerate(((FAR, 0.55, "#4f4842", 0.47), (MID, 0.95, "#2b2724", 0.46))):
            sil = F.solid(g, f"Ruins{lay + 1}Color", col)
            prev = None
            for j, (x, w, h, jit, sd) in enumerate(ruins[:6]):
                m = F.rect(g, f"Ruin{lay + 1}_{j + 1}", (0.5 + x * sc * 0.5 * 1080 / 1920, yb + h * sc * 0.25),
                           w * sc * 0.5 * 1080 / 1920, h * sc * 0.5, 0.002)
                if prev is not None:
                    m.set(PaintMode=FuID_merge())
                    m.conn("EffectMask", prev, "Mask")
                prev = m
            F.masked(sil, prev)
            drift = F.xf(g, f"Ruins{lay + 1}Parallax", sil,
                         center=f"Point(0.5 + {0.008 * (lay + 1)}*{prog(0, g.frames)}, 0.5)")
            bg = F.merge(g, f"Ruins{lay + 1}", bg, drift, blend=f"{BG}*{0.6 + 0.3 * lay}")
        g.at(0, 2)
        grd = F.solid(g, "GroundColor", "#2e2722")
        gmask = F.rect(g, "GroundShape", (0.5, ground_y / 2 + 0.02), 1.2, ground_y + 0.04, 0.01)
        F.masked(grd, gmask)
        bg = F.merge(g, "Ground", bg, grd, blend=f"{BG}")
        shaft = F.accent_solid(g, "SunShaftColor", 0.5)
        sm = F.ellipse(g, "SunShaftShape", (0.25, 0.62), 0.2, 1.5, 0.6, angle=-60)
        F.masked(shaft, sm)
        bg = F.merge(g, "SunShaft", bg, shaft, mode="Screen", blend=f"{BG}*(0.25 + 0.2*{step(I)})")

        g.at(0, 4)
        ff, fs = fam(p["FONT_FAMILY"])
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], ff, fs, 0.24, 1.08, color=p["TEXT_COLOR"])
        stone = F.noise(g, "StoneGrain", "#5a5246", "#b0a491", detail=8, scale=12, seethe_rate=0.0, contrast=1.6)
        sclip = F.bitmap_mask(g, "StoneClip", title)
        F.masked(stone, sclip)
        face = F.merge(g, "StoneFace", title, stone, mode="Multiply", blend=0.85)
        lit_edge = F.edge_light(g, "SunEdge", title, 0.003, 0.0, accent=True, gain=1.2, blur_px=1.0)
        face = F.merge(g, "SunEdgeMerge", face, lit_edge, mode="Screen", blend=0.6)
        shade_edge = F.edge_light(g, "ShadowEdge", title, -0.003, 0.0, color=(0, 0, 0), blur_px=1.0)
        face = F.merge(g, "ShadowEdgeMerge", face, shade_edge, blend=0.7)
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        ext = F.extrusion_stack(g, "Extrude", clear, title, layers=10, dx=0.0012, dy=0.0012,
                                color=(0.12, 0.105, 0.09))
        solid_t = F.merge(g, "TitleSolid", ext, face)
        sweep = F.light_sweep(g, "RakingSun", solid_t, title, f"{I} + 5", 52, angle=20, width=0.2,
                              color=(1.0, 0.85, 0.65), peak=0.3)
        g.at(0, 6)
        rumble = f"(1 - {step(I)})*min({u}*6, 1)"
        rise = f"-0.26*(1 - {e_inout(u)})"
        shk = f"0.002*{ctl('ShakeAmount')}*{rumble}"
        placed = F.title_placement(g, "TitleRise", sweep,
                                   center_extra_y=f"{rise} - 0.005*{decay(I, 5)} + {shake(shk, 1.4, 4)}",
                                   center_extra_x=shake(shk, 1.3, 2))
        occl = F.rect(g, "GroundOcclusion", (0.5, 0.75), 1.2, 0.5, 0.004)
        occl.expr("Center", f"Point(0.5, {ctl('TextPosY')} - 0.1 + 0.25)", [0.5, 0.75])
        hold = F.solid(g, "TitleHolder", (0, 0, 0), alpha=0.0)
        above = F.merge(g, "AboveGround", hold, placed)
        F.masked(above, occl)
        hz = F.cc(g, "AtmosPerspective", above, gain=f"1 - 0.1 - 0.6*{ex}", sat=f"0.9 - 0.5*{ex}")
        scene = F.merge(g, "TitleInValley", bg, hz)

        g.at(0, 8)
        dust = F.noise(g, "GroundDust", "#000000", "#8a7e6e", detail=5, scale=4, seethe_rate=0.06, contrast=1.6,
                       center="Point(0.5 + time*0.0015, 0.5)")
        dm = F.ellipse(g, "DustBand", (0.5, ground_y), 0.8, 0.12, 0.5)
        dm.expr("Width", f"0.8 + 1.2*{e_out(prog(I, 60))}", 0.8)
        F.masked(dust, dm)
        scene = F.merge(g, "DustBillow", scene, dust, mode="Screen",
                        blend=f"min({PI}*(0.5*{rumble} + 1.1*{decay(I, 28)}*{ctl('ImpactIntensity')}), 1)")
        scene = F.particles(g, "Grit", scene, number=40, lifespan=24, velocity=0.0, angle=-90, angle_var=10,
                            size=0.25, color=(0.55, 0.5, 0.44), region="CubeRgn", region_size=(0.9, 0.25, 0.1),
                            center_y=0.0, turbulence=0.05, glow=0,
                            number_expr=f"40*{PI}*{rumble}")
        scene = F.particles(g, "Motes", scene, number=6, lifespan=200, velocity=0.002, angle=10, angle_var=180,
                            size=0.3, color=(1.0, 0.85, 0.65), region="CubeRgn", region_size=(2.2, 1.4, 1.0),
                            center_y=0.0, turbulence=0.1, glow=3)
        haze = F.noise(g, "ValleyHaze", "#000000", "#6b6158", detail=4, scale=1.6, seethe_rate=0.02, contrast=1.2,
                       center="Point(0.5 + time*0.0008, 0.5)")
        scene = F.merge(g, "HazeSwallow", scene, haze, mode="Screen", blend=f"{BG}*(0.12 + 0.9*{ex})")
        g.at(0, 10)
        scene = fusion_subtitle(g, scene, p, size=0.026, tracking=1.6, color=(0.80, 0.72, 0.62), y_off=0.16,
                                t_in=f"{I} + 20", t_out=f"{X0} + 5")
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.06, shake_frames=9, shake_amp=0.007)
        g.output = F.finish(g, scene, vignette=0.5)


def FuID_merge():
    from ..fusion import FuID
    return FuID("Merge")


DESIGN = T16()
