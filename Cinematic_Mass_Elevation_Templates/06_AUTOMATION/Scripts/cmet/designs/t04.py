"""T04 - Black Steel Reckoning."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01, shake
from ..typo import Material, place_extruded, place_sprite

STEEL = Material(base=(0.44, 0.46, 0.48), spec=(0.9, 0.94, 1.0), spec_power=70, spec_gain=0.55, diffuse=0.55,
                 ambient=0.07, metal=0.72, env_sky=(0.55, 0.58, 0.62), env_horizon=(0.03, 0.035, 0.04),
                 env_ground=(0.07, 0.075, 0.08), env_sharp=12, bevel=0.035, bevel_round=False, texture="brushed",
                 tex_amount=0.3, bump=0.0, rim=(0.85, 0.9, 1.0), seed=44)

PILLARS = [(-1.62, 0.13, 0.55), (-1.18, 0.07, 0.8), (1.12, 0.09, 0.75), (1.58, 0.15, 0.5)]  # x, half-width, depth


def stages(t, s0, imp):
    """Mechanical timing: slide (A) -> hard stop -> pause -> forward seat (B) ending exactly at impact."""
    span = max(imp - s0, 0.2)
    ua = K.prog(t, s0, span * 0.6)
    ub = K.prog(t, s0 + span * 0.76, span * 0.24)
    return ua, ub


class T04(Design):
    ID = "T04"
    NAME = "Black Steel Reckoning"
    SLUG = "Black_Steel_Reckoning"
    CATEGORY = "A - Dark Mass Elevation"
    CONCEPT = "Military-industrial and restrained: a slab of brushed steel lettering is machined into place."
    ENTRANCE = ("Multi-stage mechanical move: lateral slide with motion blur -> hard stop -> beat -> forward seat "
                "-> two steel locking rails clamp the title.")
    REVEAL = "Short metallic impact pulse, slight camera recoil and a narrow specular highlight raking across the steel."
    CAMERA = "Slow lateral track that stops dead on the impact frame; small recoil kick, no drift afterwards."
    MATERIAL = "Brushed steel face with flat chamfer, blackened metal sides and rails, restrained cold-silver highlights."
    EXIT = "The rails release and the title slides back and sideways out of the light into shadow."
    TECHNIQUES = ["staged mechanical timing", "lateral motion blur", "locking rails", "volumetric light shafts",
                  "industrial pillar silhouettes", "narrow specular rake", "camera recoil"]
    TRUE_3D = False
    DURATION_FRAMES = 168
    DEFAULTS = dict(MAIN_TITLE="RECKONING", SUBTITLE="STEEL DOES NOT BEND", FONT_FAMILY="blackops",
                    TEXT_COLOR="#9AA0A6", ACCENT_COLOR="#D6E0EA", ANIMATION_START=10, ANIMATION_DURATION=50,
                    IMPACT_FRAME=60, HOLD_DURATION=72, EXIT_START=134, EXIT_DURATION=30, LETTER_SPACING=0.06,
                    TITLE_WIDTH=0.6)
    SOUND = [(0, "atmos", "Industrial hall tone, distant machinery"), (10, "whoosh", "Heavy slide (servo whoosh)"),
             (32, "metal", "Hard stop clank"), (42, "rwhoosh", "Short pneumatic pull before the seat"),
             (60, "hammer", "Steel seat impact"), (60, "sub", "Sub thump"), (63, "metal", "Locking rails clamp"),
             (66, "shimmer", "Specular rake ring-out"), (134, "whoosh", "Slide back into shadow"),
             (150, "tail", "Hall reverb tail")]

    # ------------------------------------------------------------ preview --
    def _env(self, c, pan_px, dim):
        """Industrial hall at half res: haze, light shafts through smoke, pillar silhouettes."""
        p, H, W, t = c.p, c.H, c.W, c.t
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        h2, w2 = H // 2, W // 2
        nx, ny = K.grid(h2, w2)
        bg = K.vgrad(h2, w2, (0.010, 0.012, 0.015), (0.004, 0.0045, 0.006))
        shafts = c.cache.get("shafts")
        if shafts is None:
            s = np.zeros((h2, w2), np.float32)
            for ox, ang, spr, gain in ((-1.25, 52, 2.6, 1.0), (-0.55, 61, 1.8, 0.7), (0.35, 70, 1.4, 0.45),
                                       (-1.9, 44, 3.2, 0.6)):
                s += E.light_cone(h2, w2, (ox, -1.35), ang, spr, length=3.2, softness=0.4) * gain
            shafts = c.cache["shafts"] = s
        px = pan_px / (H / 2)
        sh_shift = np.roll(shafts, int(px * 0.3 * h2 / 2), axis=1)
        smoke = K.fbm_field(h2, w2, t, 1.8, (0.018, -0.006), 17, beta=2.2, evolve=0.04, warp=0.4)
        vol = sh_shift * (0.35 + 1.1 * smoke)
        fogl = np.clip((smoke - 0.45) * 1.5, 0, 1) * 0.02
        bg = bg + (vol * 0.16 * dim)[..., None] * acc + fogl[..., None] * np.array([0.6, 0.65, 0.7], np.float32)
        # pillars (silhouettes with a thin lit edge on the shaft side)
        for x0, hw, dz in PILLARS:
            xc = x0 + px * (0.7 / dz)
            m = np.clip((hw - np.abs(nx - xc)) / 0.004, 0, 1)
            edge = np.exp(-((nx - (xc - hw)) / 0.006) ** 2) * (ny < 0.9)
            bg = bg * (1 - m[..., None] * 0.92) + (edge * 0.05 * dim)[..., None] * acc
        # overhead beam
        beam = np.clip((0.035 - np.abs(ny + 0.8 - 0.02 * nx)) / 0.003, 0, 1)
        bg = bg * (1 - beam[..., None] * 0.9)
        return cv2.resize(bg * bgI, (W, H), interpolation=cv2.INTER_LINEAR), vol

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        imp = c.impact
        ex = c.exit_u()
        exe = K.ease_in(ex, 2)
        hit = c.hit(0.01, 0.14)
        after = 1.0 if t >= imp else 0.0
        ua, ub = stages(t, c.start, imp)
        # camera: lateral track that stops dead at impact, recoil kick
        track = 1 - K.ease_out(K.prog(t, 0, imp), 2)
        pan_px = 110 * k * track
        recoil = 0.022 * K.pulse(t, imp, 0.012, 0.12) * p["SHAKE_AMOUNT"]
        sx, sy = c.shake(0.0025, 0.12, 22)
        cam = c.cam(zoom=1.0 - recoil, pan=(pan_px + sx, sy))
        dim = 1 - 0.45 * K.smooth(ex)
        bg, vol = self._env(c, pan_px, dim)

        # dust motes, visible only inside the shafts
        PI = p["PARTICLE_INTENSITY"]
        if PI > 0:
            P = c.cache.get("motes")
            if P is None:
                P = c.cache["motes"] = E.Particles(int(260 * PI), seed=4, z=(0.5, 3.0))
            x, y = P.drift(t, vel=(0.012, 0.004), turb=0.03, freq=0.3)
            px_, py_, _ = E.project(x, y, P.z, W, H)
            vh, vw = vol.shape
            ix = np.clip((px_ / W * vw).astype(int), 0, vw - 1)
            iy = np.clip((py_ / H * vh).astype(int), 0, vh - 1)
            lit = np.clip(vol[iy, ix] * 1.6, 0, 1.5)
            bg += E.particle_layer(H, W, P, x, y, acc, 1.1, 0.5 * dim, focus=1.2, dof=1.0, fade=lit, glow=0.6)

        # --- title: slide (A), hard stop, seat (B), lock
        sp = c.title()
        sh = c.shaded(STEEL)
        ea = K.ease_in_out(ua, 2)
        slide_x = W * 0.46 * (1 - ea)
        z_seat = 0.22 * H * (1 - K.ease_in(ub, 2))
        jolt = -5 * k * K.pulse(t, c.start + (imp - c.start) * 0.6, 0.01, 0.05)     # hard-stop tick
        exit_x = -W * 0.18 * exe
        exit_z = 0.55 * H * exe
        rake_u = K.prog(t, imp + 0.04, 0.75)
        rake = (-0.8 + 1.6 * K.ease_in_out(rake_u), 0.035, 0.25, 2.2 * (0 < rake_u < 1))
        lg = (0.55 + 0.25 * ua + 0.2 * ub + 0.9 * hit) * (1 - 0.92 * K.smooth(ex * 1.2))
        rgb, a = sh.shade(light=(-0.55, -0.7, 0.45), rim_dir=(-0.5, -1.0), rim_gain=(0.25 + 0.2 * after + 2.2 * hit) * dim,
                          sweep=rake, base=K.col(p["TEXT_COLOR"]), light_gain=lg, env_shift=0.12 * ea - 0.1)
        L = c.layer()
        op = K.smooth(ua * 4) * (1 - K.smooth((ex - 0.55) / 0.45))
        hx, hy = c.hero()
        pos = (hx + slide_x + exit_x + jolt, hy, z_seat + exit_z)
        depth = 0.18 * sp.cap_px * p["EXTRUSION_DEPTH"]
        side = (0.012, 0.013, 0.015)
        if depth > 0.5:
            place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, pos, 1.0, (0, 0, p["TEXT_ROTATION"]),
                           depth, side, slices=8, side_light=lambda q: 0.3 + 1.4 * q * q, opacity=op)
        else:
            place_sprite(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, pos, 1.0, (0, 0, p["TEXT_ROTATION"]),
                         None, op)
        # lateral motion blur while sliding (velocity of the eased slide)
        vel = math.sin(math.pi * ua) * (0 < ua < 1) + 0.6 * math.sin(math.pi * ex) * (0 < ex < 1)
        mb = 70 * k * vel * p["MOTION_BLUR_AMOUNT"]
        if mb > 1.5:
            L.rgb = K.blur_dir(L.rgb, mb, 0)
            L.a = K.blur_dir(L.a, mb, 0)

        # locking rails: blackened steel bars clamp above and below the title just after impact
        lock_u = K.prog(t, imp + 0.06, 0.22)
        if lock_u > 0:
            rel = K.ease_in(K.prog(t, c.exit_start - 0.05, 0.3), 2)
            for side_y, sgn in ((-1, -1), (1, 1)):
                bw, bh = int(sp.ink_w * 1.12), max(3, int(sp.cap_px * 0.055))
                bar = np.empty((bh, bw, 3), np.float32)
                g = np.linspace(1.0, 0.25, bh, dtype=np.float32)[:, None, None]
                bar[...] = (0.10 * g + 0.02) * np.array([1.0, 1.03, 1.08], np.float32)
                bar[:1] += 0.22 * acc * (1 + 3 * hit)
                am = np.ones((bh, bw), np.float32)
                travel = (1 - K.ease_out(lock_u, 4)) * sgn * W * 0.9 + rel * sgn * W * 0.9
                by = hy + side_y * (sp.ink_h * 0.5 + sp.cap_px * 0.16)
                place_sprite(L, cam, bar, am, (0, 0, bw, bh), (bw / 2, bh / 2),
                             (hx + travel + exit_x, by, exit_z * 0.6), 1.0, (0, 0, p["TEXT_ROTATION"]), None,
                             (1 - K.smooth((ex - 0.4) / 0.4)))
        img = comp(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.6, 0), 6 * k) * 0.6 * p["GLOW_STRENGTH"] * (0.4 + 2 * hit)

        img = subtitle(c, img, cam, imp + 0.45, c.exit_start - 0.15, (0.6, 0.64, 0.68), y_rel=1.05,
                       tracking=0.5)
        # metallic pulse: brief cold lift of the whole frame
        img = img + (0.03 * hit) * acc[None, None, :] * p["BACKGROUND_INTENSITY"]
        return c.finish(img, vignette=0.6, grain=0.03, bloom=(0.8, 0.35), streak=(0.95, 0.35, 220, acc))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S = ctl("AnimStart")
        ES = ctl("ExitStart")
        BG = ctl("BackgroundIntensity")
        GL = ctl("GlowStrength")
        span = f"max({I} - {S}, 1)"
        ua = prog(S, f"{span}*0.6")
        ub = prog(f"{S} + {span}*0.76", f"{span}*0.24")
        ex = prog(ES, ctl("ExitDuration"))
        exe = e_in(ex, 2)
        dim = f"(1 - 0.45*{ex})"

        # environment: hall, shafts through smoke, pillars -----------------------
        g.at(0, 0)
        bg = F.gradient_bg(g, "HallTone", [(0, "#030405", 1), (1, "#010101", 1)])
        haze = F.noise(g, "ShaftSmoke", "#000000", "#ffffff", detail=6, scale=2.2, seethe_rate=0.05, contrast=1.5,
                       center="Point(0.5 + time*0.0009, 0.5 - time*0.0003)")
        sh1 = F.rect(g, "ShaftA", (0.34, 0.62), 0.07, 2.2, 0.06, angle=38)
        sh2 = F.rect(g, "ShaftB", (0.5, 0.6), 0.045, 2.2, 0.05, angle=29)
        sh2.conn("EffectMask", sh1, "Mask")
        sh3 = F.rect(g, "ShaftC", (0.68, 0.58), 0.03, 2.2, 0.04, angle=20)
        sh3.conn("EffectMask", sh2, "Mask")
        shaft_c = F.accent_solid(g, "ShaftColor", 0.5)
        F.masked(shaft_c, sh3)
        vol = F.merge(g, "ShaftVolume", shaft_c, haze, mode="Multiply", blend=0.75)
        bg = F.merge(g, "Shafts", bg, vol, mode="Screen", blend=f"min({BG}*{dim}*0.6, 1)")
        g.at(0, 2)
        pil = None
        for i, (x0, hw, dz) in enumerate(PILLARS):
            r = F.rect(g, f"Pillar{i + 1}", (0.5 + x0 / 3.556, 0.5), hw / 1.778, 1.2, 0.002)
            r.expr("Center", f"Point({0.5 + x0 / 3.556:.4f} + {0.7 / dz:.3f}*0.02*(1 - {e_out(prog(0, I), 2)}), 0.5)",
                   [0.5 + x0 / 3.556, 0.5])
            if pil is not None:
                r.conn("EffectMask", pil, "Mask")
            pil = r
        beam = F.rect(g, "OverheadBeam", (0.5, 0.9), 1.2, 0.035, 0.003, angle=-0.6)
        beam.conn("EffectMask", pil, "Mask")
        pillars = F.solid(g, "PillarSteel", (0.006, 0.006, 0.007))
        F.masked(pillars, beam)
        bg = F.merge(g, "PillarSilhouettes", bg, pillars, blend=0.92)
        bg = F.particles(g, "ShaftDust", bg, number=14, lifespan=200, velocity=0.001, angle=10, angle_var=180,
                         size=0.18, color=(0.8, 0.84, 0.9), region="CubeRgn", region_size=(1.6, 1.0, 1.0),
                         center_y=0.1, turbulence=0.08, glow=2)

        # title -------------------------------------------------------------
        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Black Ops One", "Regular", 0.16, 1.06,
                             color=p["TEXT_COLOR"])
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        steel = F.fill_material(g, "SteelGradient", title,
                                [(0, "#e4e8ec", 1), (0.42, "#9aa0a6", 1), (0.5, "#5a5f64", 1), (0.6, "#2c2f33", 1),
                                 (1, "#7d8288", 1)])
        face = F.merge(g, "SteelFace", title, steel, mode="Multiply", blend=1.0)
        brush_n = F.noise(g, "BrushNoise", "#5a5a5a", "#a8a8a8", detail=8, scale=40, seethe_rate=0.0, contrast=2.0)
        brush = F.dirblur(g, "BrushStreaks", brush_n, 0.12, angle=0.0)
        bm = F.bitmap_mask(g, "BrushMatte", title)
        brushed = F.merge(g, "BrushHolder", clear, brush)
        F.masked(brushed, bm)
        face = F.merge(g, "BrushedSteel", face, brushed, mode="Overlay", blend=0.35)
        rim = F.edge_light(g, "SilverEdge", title, -0.0015, -0.003, accent=True, gain=1.2, blur_px=0.8)
        face = F.merge(g, "EdgeMerge", face, rim, mode="Screen",
                       blend=f"min({GL}*{dim}*(0.3 + 0.2*{step(I)} + 2*{decay(I, 4)}), 1)")
        g.at(0, 6)
        ext = F.extrusion_stack(g, "BlackenedSides", clear, title, layers=7, dx=0.0007, dy=-0.0014,
                                color=(0.012, 0.013, 0.015))
        body = F.merge(g, "TitleBody", ext, face)
        rake = F.light_sweep(g, "SpecularRake", body, title, f"{I} + 1", 18, angle=14, width=0.025, peak=1.0,
                             accent=True)
        lit = F.cc(g, "KeyLight", rake,
                   gain=f"(0.55 + 0.25*{ua} + 0.2*{ub} + 0.8*{decay(I, 3)})*(1 - 0.92*{ex})")
        mb = F.dirblur(g, "SlideMotionBlur", lit,
                       f"0.05*{ctl('MotionBlurAmount')}*(sin(3.14159*{ua}) + 0.6*sin(3.14159*{ex}))", angle=0.0)
        g.at(0, 8)
        placed = F.title_placement(
            g, "MechanicalMove", mb,
            size_expr=f"(0.82 + 0.18*{e_in(ub, 2)})*(1 - 0.35*{exe})",
            center_extra_x=(f"0.46*(1 - {e_inout(ua)}) - 0.18*{exe}"
                            f" - 0.003*{decay(f'{S} + {span}*0.6', 2)}"))
        tglow = F.softglow(g, "SteelGlint", placed, 6, gain=f"{GL}*(0.2 + 1.2*{decay(I, 4)})", threshold=0.6)
        scene = F.merge(g, "TitleOverHall", bg, tglow,
                        blend=f"min({ua}*4, 1)*(1 - {clamp01(f'({ex} - 0.55)/0.45')})")

        # locking rails -----------------------------------------------------------
        g.at(0, 10)
        lock = e_out(prog(f"{I} + 1", 5), 4)
        rel = e_in(prog(f"{ES} - 1", 7), 2)
        for nm, sgn, dy in (("RailTop", -1, 0.085), ("RailBottom", 1, -0.085)):
            rm = F.rect(g, f"{nm}Shape", (0.5, 0.5), 0.62, 0.009, 0.0008)
            rm.expr("Width", f"0.62*{ctl('TextScale')}", 0.62)
            rm.expr("Center", (f"Point({ctl('TextPosX')} + {sgn}*0.9*(1 - {lock}) + {sgn}*0.9*{rel} - 0.18*{exe},"
                               f" {ctl('TextPosY')} + {dy}*{ctl('TextScale')})"), [0.5, 0.5])
            rs = F.solid(g, f"{nm}Steel", (0.07, 0.075, 0.08))
            F.masked(rs, rm)
            scene = F.merge(g, nm, scene, rs, blend=f"{step(f'{I} + 1')}*(1 - {clamp01(f'({ex} - 0.4)/0.4')})")
        scene = F.impact_flash(g, "MetalPulse", scene, color=p["ACCENT_COLOR"], peak=0.06, frames=3)

        g.at(0, 12)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.028, 1.8,
                                    color=(0.6, 0.64, 0.68), y_off=-0.15)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 11", f"{ES} - 4", 14, 8))
        d = decay(I, 3)
        SA = ctl("ShakeAmount")
        cam = F.xf(g, "CameraTrack", scene,
                   center=(f"Point(0.5 + 0.03*(1 - {e_out(prog(0, I), 2)}) + {shake(f'0.003*{SA}*{d}', 2.2, 1.0)},"
                           f" 0.5 + {shake(f'0.003*{SA}*{d}', 2.6, 2.0)})"),
                   size=f"1 - 0.022*{ctl('ShakeAmount')}*{decay(I, 4)}", edges=1)
        g.output = F.finish(g, cam, vignette=0.6)


DESIGN = T04()
