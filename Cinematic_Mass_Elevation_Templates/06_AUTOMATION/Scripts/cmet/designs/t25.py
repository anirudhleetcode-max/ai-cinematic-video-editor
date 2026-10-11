"""T25 - Future Warlord."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01, shake
from ..typo import Material
from . import _c_helpers as X

CERAMIC = Material(base=(0.6, 0.62, 0.58), spec=(1.0, 0.95, 0.9), spec_power=24, spec_gain=0.35, diffuse=0.85,
                   ambient=0.12, metal=0.15, env_sky=(0.6, 0.6, 0.6), env_horizon=(0.05, 0.05, 0.05),
                   env_ground=(0.1, 0.1, 0.1), bevel=0.05, texture="grain", tex_amount=0.12, bump=0.02,
                   rim=(1.0, 0.6, 0.4), seed=25)


class T25(Design):
    ID = "T25"
    NAME = "Future Warlord"
    SLUG = "Future_Warlord"
    CATEGORY = "C - Future Tech and Kinetic Camera"
    CONCEPT = "A tactical unveiling: armoured blast shutters part inside a targeting visor to reveal the warlord's name."
    ENTRANCE = ("A restrained HUD boots (brackets search, then lock onto a recessed bay); the bay's twin armoured "
                "shutters unlock with a small jolt.")
    REVEAL = ("At the impact frame the shutters slam open, the title pushes forward out of the recess under a hard "
              "top light; dust shakes off the frame and the HUD settles to quiet corner brackets.")
    CAMERA = "Static tripod with a heavy slam shake; the HUD is a stable visor overlay (unaffected by shake)."
    MATERIAL = "Matte military ceramic lettering; brushed gunmetal shutters with accent hazard stripes; HUD in ACCENT."
    EXIT = "The shutters slam closed again and the HUD powers down line by line."
    TECHNIQUES = ["HUD bracket lock-on", "reticle", "mechanical shutters", "staged unlock", "slam shake", "dust shake-off",
                  "visor overlay"]
    DURATION_FRAMES = 228
    DEFAULTS = dict(MAIN_TITLE="WARLORD", SUBTITLE="COMMAND THE FRONT", FONT_FAMILY="blackops",
                    TEXT_COLOR="#C9CCC2", ACCENT_COLOR="#FF5A1F", ANIMATION_START=10, ANIMATION_DURATION=72,
                    IMPACT_FRAME=96, HOLD_DURATION=84, EXIT_START=186, EXIT_DURATION=26, LETTER_SPACING=0.05,
                    TITLE_WIDTH=0.52, SHADOW_STRENGTH=0.7)
    SOUND = [(0, "atmos", "Hangar room tone"), (6, "digital", "HUD boot blips"), (34, "digital", "Target lock beeps"),
             (60, "metal", "Clamp release clunk (unlock jolt)"), (64, "riser", "Hydraulic riser (64-96)"),
             (96, "metal", "Shutter slam open"), (96, "impact", "Heavy impact"), (97, "debris", "Dust/grit falling"),
             (186, "hammer", "Shutters slam closed"), (190, "digital", "HUD power-down"), (200, "tail", "Hangar tail")]
    FUSION_NOTES = ["HUD elements (BracketFrame*, Reticle*, RangeTicks) follow the Accent colour; their brightness is "
                    "the 'HUD' merges' Blend.",
                    "Shutter plates are RectangleMask-driven solids (ShutterTop/ShutterBottom) clipped to the bay."]

    def _open(self, c):
        """Shutter opening 0..1 (fraction of half-bay height)."""
        t, imp = c.t, c.impact
        unlock = imp - 1.5
        o = 0.0
        if t >= unlock:
            o = 0.05 * K.back_out(K.prog(t, unlock, 0.12), 2.5)
        if t >= imp:
            o = 0.05 + 0.97 * K.ease_out(K.prog(t, imp, 0.22), 3) - 0.02 * K.ease_in_out(K.prog(t, imp + 0.22, 0.3))
        close = K.ease_in(K.prog(c.exit_u(), 0, 0.45), 2)
        return max(0.0, o * (1 - close))

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        tc = K.col(p["TEXT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        after = 1.0 if t >= imp else 0.0
        hit = c.hit(0.01, 0.3)
        sp = c.title()
        hx, hy = c.hero()
        o = self._open(c)

        # bay geometry (screen px)
        cx, cy = W / 2 + hx, H / 2 + hy
        aw, ah = sp.ink_w * 1.16 + 60 * k, sp.ink_h * 2.0 + 40 * k
        ax0, ay0, ax1, ay1 = int(cx - aw / 2), int(cy - ah / 2), int(cx + aw / 2), int(cy + ah / 2)
        amid = (ay0 + ay1) / 2

        # --- hangar wall
        bg = K.vgrad(H, W, (0.03, 0.032, 0.034), (0.012, 0.012, 0.013))
        key = "wall"
        if key not in c.cache:
            nx, ny = K.grid(H, W)
            seams = np.zeros((H, W), np.float32)
            for xx in np.arange(-1.9, 1.9, 0.42):
                seams += np.exp(-((nx - xx) / 0.003) ** 2) * 0.5
            tex = K.sample(K.fft_noise(256, 1.0, 25), H, W, 6.0, stretch=(1.0, 8.0))
            c.cache[key] = (seams, tex)
        seams, tex = c.cache[key]
        bg = bg * (0.85 + 0.3 * tex[..., None]) - (seams * 0.012)[..., None]
        top_light = K.soft_spot(H, W, hx / (H / 2), hy / (H / 2) - 0.9, 1.4, 0.7, 1.2)
        bg += (top_light * (0.05 + 0.08 * after))[..., None] * np.array([1.0, 0.95, 0.88], np.float32)
        bg = bg * bgI
        # bay recess
        bg[ay0:ay1, ax0:ax1] = bg[ay0:ay1, ax0:ax1] * 0.25 + 0.004
        # bay frame bevel
        fr = np.zeros((H, W, 3), np.float32)
        X.rect_outline(fr, ax0 - 6 * k, ay0 - 6 * k, ax1 + 6 * k, ay1 + 6 * k, (0.16, 0.16, 0.17), max(1, int(8 * k)))
        cv2.line(fr, (int((ax0 - 6 * k) * 4), int((ay0 - 9 * k) * 4)), (int((ax1 + 6 * k) * 4), int((ay0 - 9 * k) * 4)),
                 (0.3, 0.3, 0.3), max(1, int(2 * k)), cv2.LINE_AA, shift=2)
        bg = np.maximum(bg, fr * bgI)

        # --- title in the bay: pushes forward when the shutters are open
        sh = c.shaded(CERAMIC)
        push = K.ease_out(K.prog(t, imp + 0.05, 0.6), 3) * (1 - K.ease_in(K.prog(ex, 0.0, 0.45), 2))
        lg = (0.25 + 0.75 * after) * (1 + 0.6 * hit)
        rgb, a = sh.shade(light=(0.0, -0.9, 0.45), base=tc, light_gain=lg, rim_gain=0.4 * after + 1.5 * hit,
                          rim_dir=(0, -1))
        cam = c.cam()
        L = c.layer()
        c.place(L, cam, rgb, a, sp, 1.0, off=(0, 6 * k * (1 - push), 0.12 * H * (1 - push)))
        # clip title to the bay
        clip = np.zeros((H, W), np.float32)
        clip[ay0:ay1, ax0:ax1] = 1
        L.a *= clip
        L.rgb *= clip[..., None]
        sh_bg = bg.copy()
        sh_strength = p["SHADOW_STRENGTH"] * (0.4 + 0.6 * push)
        from ..base import drop_shadow
        sh_bg = drop_shadow(sh_bg, L, sh_strength, (0, 10 + 10 * push), 14, k)
        img = sh_bg * (1 - L.a[..., None]) + L.rgb

        # --- shutters
        key = "plate"
        hh = int(ah / 2) + 2
        ww = ax1 - ax0
        if key not in c.cache or c.cache[key][0].shape[:2] != (hh, ww):
            yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
            n = K.sample(K.fft_noise(256, 1.0, 7), hh, ww, 4.0, stretch=(30.0, 1.0))
            base = (0.075 + 0.05 * n)
            grooves = ((yy % (22 * k)) < 1.5 * k) * -0.03
            pl = np.repeat((base + grooves)[..., None], 3, axis=2) * np.array([1.0, 1.0, 1.05], np.float32)
            hz = hh - yy < 0.1 * ah
            stripe = (((xx + yy) / (18 * k)) % 2 < 1)
            pl[hz & stripe] = acc * 0.38
            pl[hz & ~stripe] = 0.03
            pl[(hh - yy) < 3 * k] = 0.35   # lit leading edge
            for bxp in np.linspace(0.08, 0.92, 6):
                cv2.circle(pl, (int(bxp * ww), int(hh * 0.3)), max(2, int(4 * k)), (0.2, 0.2, 0.21), -1, cv2.LINE_AA)
            c.cache[key] = (pl, pl[::-1].copy())
        ptop, pbot = c.cache[key]
        shift = int(round(o * (hh - 2)))
        rows = hh - shift
        y_top1 = int(amid) - shift
        if rows > 0:
            ys0 = max(ay0, y_top1 - rows)
            seg = ptop[hh - (y_top1 - ys0):hh] if y_top1 > ys0 else None
            if seg is not None and y_top1 > ys0:
                img[ys0:y_top1, ax0:ax1] = seg * bgI * (0.7 + 0.3 * K.prog(t, 0, 1.0)) + seg * 0.4 * hit
            yb0 = int(amid) + shift
            ye = min(ay1, yb0 + rows)
            if ye > yb0:
                img[yb0:ye, ax0:ax1] = pbot[:ye - yb0] * bgI * (0.7 + 0.3 * K.prog(t, 0, 1.0))
        # clamp indicators on the frame (two lights per side): off -> accent at unlock
        unl = 1.0 if t >= imp - 1.5 else 0.0
        for sx in (ax0 - 18 * k, ax1 + 18 * k):
            for yy_ in (amid - 20 * k, amid + 20 * k):
                cv2.circle(img, (int(sx * 4), int(yy_ * 4)), max(4, int(5 * k * 4)),
                           tuple(float(v) for v in (acc * (0.25 + 1.2 * unl * (1 - ex)))), -1, cv2.LINE_AA, shift=2)

        # --- slam dust shaking off the frame
        if t >= imp and p["PARTICLE_INTENSITY"] > 0:
            dt = t - imp
            B = c.cache.get("dust")
            n = int(140 * p["PARTICLE_INTENSITY"])
            if B is None:
                r = np.random.default_rng(25)
                B = c.cache["dust"] = (r.uniform(0, 1, n), r.choice([0, 1], n), r.uniform(0.2, 1.0, n), r.random(n))
            ux, side, spd, rr = B
            px = ax0 + ux * aw
            py = np.where(side == 0, ay0 - 8 * k, ay1 + 8 * k) + (spd * 120 * dt + 300 * dt * dt) * k
            fade = np.exp(-dt / (0.4 + 0.6 * rr)) * (1 - ex)
            Pb = E.Particles(n, 1)
            Pb.z = np.ones(n, np.float32)
            img += E.particle_layer(H, W, Pb, (px - W / 2) / (H / 2), (py - H / 2) / (H / 2), (0.55, 0.52, 0.48),
                                    1.2, 0.7 * fade, glow=0.5)
        # glow from lit title
        img += K.blur(np.maximum(L.rgb - 0.5, 0), 12 * k) * 0.5 * p["GLOW_STRENGTH"] * (0.4 + hit)

        # --- camera shake (scene only)
        sx, sy = c.shake(0.007, 0.28, 18)
        if abs(sx) + abs(sy) > 0.05:
            M = np.float32([[1.01, 0, -0.005 * W + sx], [0, 1.01, -0.005 * H + sy]])
            img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)

        img = subtitle(c, img, cam, imp + 0.6, c.exit_start - 0.3, tc * 0.55 + acc * 0.1, y_rel=1.25)
        img = img * (1 - 0.7 * K.smooth(K.prog(ex, 0.55, 0.45)))  # bay lights down after the slam

        # --- HUD visor overlay (restrained, ACCENT)
        boot = K.smooth(K.prog(t, 0.1, 0.6))
        lock = K.ease_out(K.prog(t, c.start + 0.4, 1.2), 3)
        hud_lvl = boot * (0.55 - 0.32 * K.smooth(K.prog(t, imp, 0.8))) * (1 - K.smooth(K.prog(ex, 0.25, 0.5)))
        if hud_lvl > 0.01:
            hb = np.zeros((H, W, 3), np.float32)
            jit = (1 - lock) * 30 * k
            jx = math.sin(t * 7.0) * jit
            jy = math.cos(t * 5.0) * jit
            spread = 1 + 0.9 * (1 - lock)
            bx0, by0 = cx - aw / 2 * spread - 26 * k + jx, cy - ah / 2 * spread - 22 * k + jy
            bx1, by1 = cx + aw / 2 * spread + 26 * k + jx, cy + ah / 2 * spread + 22 * k + jy
            X.rect_outline(hb, bx0, by0, bx1, by1, acc, max(1, int(2 * k)), corner=34 * k)
            pre_imp = 1 - K.smooth(K.prog(t, imp, 0.6))
            # reticle (only until the reveal)
            if pre_imp > 0.01:
                R = ah * 0.95 * (1.3 - 0.3 * lock)
                rr_ = tuple(float(v) for v in acc * pre_imp)
                for i in range(4):
                    a0 = i * 90 + 20 + t * 40 * (1 - lock) + 10
                    cv2.ellipse(hb, (int(cx * 4), int(cy * 4)), (int(R * 4), int(R * 4)), 0, a0, a0 + 50, rr_,
                                max(1, int(1.5 * k)), cv2.LINE_AA, shift=2)
                cv2.line(hb, (int((cx - R - 30 * k) * 4), int(cy * 4)), (int((cx - R + 12 * k) * 4), int(cy * 4)), rr_,
                         1, cv2.LINE_AA, shift=2)
                cv2.line(hb, (int((cx + R - 12 * k) * 4), int(cy * 4)), (int((cx + R + 30 * k) * 4), int(cy * 4)), rr_,
                         1, cv2.LINE_AA, shift=2)
            # range ticks under the bay
            ty_ = by1 + 16 * k
            n_t = int(41 * min(1.0, boot * 1.2))
            for i in range(n_t):
                xx = bx0 + (bx1 - bx0) * i / 40
                l = (10 if i % 5 == 0 else 4) * k
                cv2.line(hb, (int(xx * 4), int(ty_ * 4)), (int(xx * 4), int((ty_ + l) * 4)),
                         tuple(float(v) for v in acc * 0.6), 1, cv2.LINE_AA, shift=2)
            # side data bars (status blocks)
            for side in (-1, 1):
                x0 = (bx0 - 70 * k) if side < 0 else (bx1 + 30 * k)
                for j in range(5):
                    w_ = (14 + 26 * K.hash01(j + (side > 0) * 7, 4) * (0.6 + 0.4 * lock)) * k
                    y_ = cy - 40 * k + j * 18 * k
                    cv2.rectangle(hb, (int(x0 * 4), int(y_ * 4)), (int((x0 + w_) * 4), int((y_ + 5 * k) * 4)),
                                  tuple(float(v) for v in acc * 0.5), -1, cv2.LINE_AA, shift=2)
            # exit power-down: lines drop out top-to-bottom
            if ex > 0:
                cut = int(H * K.smooth(K.prog(ex, 0.2, 0.5)))
                hb[:cut] = 0
            img += (hb + K.blur(hb, 3 * k) * 0.6) * hud_lvl
        return c.finish(img, vignette=0.55, grain=0.035, bloom=(0.8, 0.4),
                        grade=dict(shadows=(0.0, 0.002, 0.004), highlights=(0.01, 0.005, -0.006), contrast=1.08,
                                   sat=0.9))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S = ctl("AnimStart")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        BG = ctl("BackgroundIntensity")
        close = e_in(clamp01(f"{ex}/0.45"), 2)
        unlock = f"0.05*{step(f'{I} - 36')}"
        slam = f"0.97*{e_out(prog(I, 5), 3)}"
        opn = f"(({unlock}) + {slam})*(1 - {close})"
        push = f"{e_out(prog(f'{I} + 1', 14), 3)}*(1 - {close})"
        after = step(I)
        bw, bh = 0.62, 0.24   # bay (frame-relative)

        g.at(0, 0)
        bg = F.gradient_bg(g, "HangarWall", [(0, "#030303", 1), (1, "#08090a", 1)])
        wall = X.streak_noise(g, "WallTexture", "#000000", "#1b1c1d", stretch=1, scale=6, seethe=0.0)
        wall.set(UseSizeAndAspect=0, XSize=1.0, YSize=8.0)
        bg = F.merge(g, "WallTex", bg, wall, mode="Screen", blend=f"0.6*{BG}")
        bg = F.light_spot(g, "TopLight", bg, (1, 0.95, 0.88), (0.5, 0.95), 1.4, 0.7, 0.6,
                          blend=f"{BG}*(0.12 + 0.18*{after})")
        bay = F.solid(g, "BayRecess", (0.004, 0.004, 0.005))
        F.masked(bay, F.rect(g, "BayShape", (0.5, 0.5), bw, bh, 0.0))
        bg = F.merge(g, "Bay", bg, bay, blend=0.9)
        frm = F.solid(g, "BayFrameColor", (0.16, 0.16, 0.17))
        fm = F.rect(g, "BayFrameShape", (0.5, 0.5), bw + 0.008, bh + 0.014, 0.0)
        fm.set(BorderWidth=0.004)
        F.masked(frm, fm)
        bg = F.merge(g, "BayFrame", bg, frm, blend=BG)

        g.at(0, 2)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Black Ops One", "Regular", 0.13, 1.05,
                             color=p["TEXT_COLOR"])
        mat = F.fill_material(g, "CeramicShade", title, [(0, "#3a3b38", 1), (0.6, "#d8d9d2", 1), (1, "#ffffff", 1)],
                              start=(0.5, 0.44), end=(0.5, 0.56))
        face = F.merge(g, "CeramicFace", title, mat, mode="Multiply", blend=0.85)
        rim = F.edge_light(g, "TopRim", title, 0.0, -0.003, color=(1, 0.95, 0.9), blur_px=1.0)
        face = F.merge(g, "TopRimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.4*{after} + 1.2*{decay(I, 8)}), 1)")
        lit = F.cc(g, "TopLightLevel", face, gain=f"(0.25 + 0.75*{after})*(1 + 0.6*{decay(I, 8)})")
        placed = F.title_placement(g, "TitlePush", lit, size_expr=f"0.9 + 0.1*{push}",
                                   center_extra_y=f"0.006*(1 - {push})")
        shadow = F.cc(g, "TitleShadow", placed, gain=0)
        shadow = F.xf(g, "TitleShadowOffset", shadow, center=f"Point(0.5, 0.5 - 0.008 - 0.008*{push})")
        shadow = F.blur(g, "TitleShadowSoft", shadow, 8)
        g.at(0, 4)
        scene = F.merge(g, "ShadowOverBay", bg, shadow, blend=f"{ctl('ShadowStrength')}*(0.4 + 0.6*{push})")
        bayclip = F.rect(g, "TitleBayClip", (0.5, 0.5), bw, bh, 0.0)
        tclip = F.merge(g, "TitleInBay", scene, placed)
        F.masked(tclip, bayclip)
        scene = tclip

        # shutters
        g.at(0, 6)
        for nm, sgn in (("Top", 1), ("Bottom", -1)):
            plate = F.solid(g, f"Shutter{nm}Metal", (0.075, 0.077, 0.08))
            br = X.streak_noise(g, f"Shutter{nm}Brush", "#000000", "#2a2b2c", stretch=30, scale=10, seethe=0.0)
            pm = F.merge(g, f"Shutter{nm}Tex", plate, br, mode="Screen", blend=0.5)
            hz = F.accent_solid(g, f"Shutter{nm}HazardColor", 0.38)
            hzm = F.rect(g, f"Shutter{nm}HazardShape", (0.5, 0.5), bw, 0.024, 0.0)
            hzm.expr("Center", f"Point(0.5, 0.5 + {sgn}*({0.012:.3f} + {bh / 2:.3f}*{opn}))", [0.5, 0.5])
            F.masked(hz, hzm)
            pm = F.merge(g, f"Shutter{nm}Hazard", pm, hz)
            sm = F.rect(g, f"Shutter{nm}Shape", (0.5, 0.5), bw, bh / 2, 0.0)
            sm.expr("Center", f"Point(0.5, 0.5 + {sgn}*({bh / 4:.3f} + {bh / 2:.3f}*{opn}))", [0.5, 0.5])
            clipm = F.rect(g, f"Shutter{nm}BayClip", (0.5, 0.5), bw, bh, 0.0)
            clipm.set(PaintMode=F.FuID("Multiply"))
            clipm.conn("EffectMask", sm, "Mask")
            F.masked(pm, clipm)
            scene = F.merge(g, f"Shutter{nm}", scene, pm, blend=BG)
        scene = F.particles(g, "SlamDust", scene, number=160, lifespan=30, velocity=0.01, angle=-90, angle_var=40,
                            size=0.3, color=(0.55, 0.52, 0.48), region="CubeRgn", region_size=(1.2, 0.3, 0.1),
                            center_y=0.0, turbulence=0.2, glow=0,
                            number_expr=f"160*{ctl('ParticleIntensity')}*{window(I, f'{I} + 2', 1, 1)}")
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.0, shake_frames=7, shake_amp=0.007)
        scene = F.cc(g, "LightsDown", scene, gain=f"1 - 0.7*{e_inout(clamp01(f'({ex} - 0.55)/0.45'))}")

        # HUD visor overlay ---------------------------------------------
        g.at(0, 8)
        lock = e_out(prog(f"{S} + 10", 29), 3)
        spread = f"(1 + 0.9*(1 - {lock}))"
        hud = f"{clamp01('(time - 2)/14')}*(0.55 - 0.32*{e_inout(prog(I, 19))})*(1 - {e_inout(clamp01(f'({ex} - 0.25)/0.5'))})"
        bo = F.rect(g, "BracketFrameOuter", (0.5, 0.5), bw + 0.04, bh + 0.08, 0.0)
        bo.set(BorderWidth=0.003)
        bo.expr("Width", f"({bw + 0.04})*{spread}", bw)
        bo.expr("Height", f"({bh + 0.08})*{spread}", bh)
        bo.expr("Center", f"Point(0.5 + 0.015*(1 - {lock})*sin(time*0.29), 0.5 + 0.02*(1 - {lock})*cos(time*0.21))",
                [0.5, 0.5])
        cutw = F.rect(g, "BracketFrameCutW", (0.5, 0.5), 0.5, 2.0, 0.0)
        cutw.expr("Width", f"({bw + 0.04})*{spread} - 0.05", 0.5)
        cutw.set(PaintMode=F.FuID("Subtract"))
        cutw.conn("EffectMask", bo, "Mask")
        cuth = F.rect(g, "BracketFrameCutH", (0.5, 0.5), 2.0, 0.2, 0.0)
        cuth.expr("Height", f"({bh + 0.08})*{spread} - 0.09", 0.2)
        cuth.set(PaintMode=F.FuID("Subtract"))
        cuth.conn("EffectMask", cutw, "Mask")
        br = F.accent_solid(g, "BracketFrameColor", 1.0)
        F.masked(br, cuth)
        ret = F.ellipse(g, "ReticleRing", (0.5, 0.5), 0.3, 0.53, 0.002, border=0.0015)
        ret.expr("Width", f"0.3*(1.3 - 0.3*{lock})", 0.3)
        ret.expr("Height", f"0.533*(1.3 - 0.3*{lock})", 0.53)
        rcol = F.accent_solid(g, "ReticleColor", 1.0)
        F.masked(rcol, ret)
        hudimg = F.merge(g, "HUDReticle", br, rcol, mode="Screen", blend=f"1 - {e_inout(prog(I, 14))}")
        ticks = []
        for i in range(21):
            m = F.rect(g, f"RangeTicks{i}", (0.5 - (bw / 2 + 0.02) + (bw + 0.04) * i / 20, 0.5 - bh / 2 - 0.07), 0.0012,
                       0.02 if i % 5 == 0 else 0.008, 0.0)
            ticks.append(m)
        tk = F.accent_solid(g, "RangeTicksColor", 0.6)
        F.masked(tk, X.chain(ticks))
        hudimg = F.merge(g, "HUDTicks", hudimg, tk, mode="Screen")
        hudg = F.softglow(g, "HUDGlow", hudimg, 3, gain=f"0.6*{ctl('GlowStrength')}", threshold=0.05)
        scene = F.merge(g, "HUD", scene, hudg, mode="Screen", blend=hud)

        g.at(0, 10)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.5,
                                    color=(0.7, 0.68, 0.64), y_off=-0.175)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 14", f"{ctl('ExitStart')} - 7", 14, 8))
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T25()
