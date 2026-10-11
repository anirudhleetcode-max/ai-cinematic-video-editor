"""T14 - Forged in Fire (2.5D)."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from ._b_helpers import put_title, add_sub, fam, fusion_subtitle

IRON = Material(base=(0.20, 0.18, 0.165), spec=(1.0, 0.82, 0.62), spec_power=34, spec_gain=0.55, diffuse=0.75,
                ambient=0.06, metal=0.25, env_sky=(0.40, 0.30, 0.22), env_horizon=(0.03, 0.02, 0.015),
                env_ground=(0.22, 0.10, 0.04), env_sharp=6, bevel=0.06, bevel_round=False, texture="concrete",
                tex_amount=0.35, bump=0.04, rim=(1.0, 0.55, 0.22), seed=61)

STRIKES = (-2.0, -1.0, 0.0)  # seconds relative to IMPACT_FRAME
STRIKE_X = (-0.32, 0.30, 0.0)  # where the hammer lands, fraction of title width
SHARP = (14.0, 6.0, 1.5, 0.0)  # sprite softness (px @1080) before S1, after S1, after S2, after S3


def heat_col(h):
    """Blackbody-ish ramp: intensity rises steeply with heat (dull red -> orange -> pale yellow)."""
    h = np.clip(np.asarray(h, np.float32), 0, 1.2)
    inten = h ** 2.2 * 1.25
    r = np.ones_like(h)
    g = 0.12 + 0.50 * np.clip((h - 0.35) / 0.6, 0, 1) + 0.2 * np.clip((h - 0.85) / 0.35, 0, 1)
    b = 0.02 + 0.10 * np.clip((h - 0.6) / 0.4, 0, 1) + 0.45 * np.clip((h - 0.85) / 0.35, 0, 1)
    return (np.stack([r, g, b], -1) * inten[..., None]).astype(np.float32)


class T14(Design):
    ID = "T14"
    NAME = "Forged in Fire"
    SLUG = "Forged_In_Fire"
    CATEGORY = "B - Premium Materials"
    CONCEPT = "A dark smithy: a glowing blank of iron is hammered, strike by strike, into razor-sharp letterforms."
    ENTRANCE = ("A soft, swollen, dull-red billet in the rough shape of the title heats up in the dark; three "
                "hammer strikes (left, right, centre) each flatten it, sharpen the edges and throw sparks.")
    REVEAL = ("The final strike on the impact frame locks the crisp forged title at white-orange heat; glowing "
              "seams pulse, then the metal cools in a controlled way to dark hammered iron with ember-red seams.")
    CAMERA = "Static, heavy framing with a hard jolt on every strike and a slow creep-in during cooling."
    MATERIAL = ("Hammered dark iron (concrete-grain bump, flat chamfer) with emissive heat driven by a "
                "blackbody ramp; edge and crack seams stay hot longest; forge underlight from below.")
    EXIT = "The last heat drains from the seams and quench steam rolls over the cold iron until it is gone."
    TECHNIQUES = ["2.5D extrusion stack", "multi-strike timing", "progressive sharpening", "spark bursts",
                  "emissive heat ramp", "glowing seams", "controlled cooling", "quench steam"]
    TRUE_3D = False
    DURATION_FRAMES = 228
    DEFAULTS = dict(MAIN_TITLE="FORGED", SUBTITLE="IN FIRE AND IRON", FONT_FAMILY="staatliches",
                    SUB_FONT_FAMILY="teko", TEXT_COLOR="#3A3430", ACCENT_COLOR="#FF6A1E",
                    ANIMATION_START=14, ANIMATION_DURATION=50, IMPACT_FRAME=112, HOLD_DURATION=70, EXIT_START=184,
                    EXIT_DURATION=36, LETTER_SPACING=0.09, TITLE_WIDTH=0.56)
    SOUND = [(0, "atmos", "Forge roar bed"), (0, "fire", "Coal bed crackle"), (14, "swell", "Heat swell"),
             (64, "hammer", "Strike 1"), (64, "debris", "Spark spray"), (88, "hammer", "Strike 2"),
             (88, "debris", "Spark spray"), (106, "rwhoosh", "Wind-up"), (112, "hammer", "Final strike"),
             (112, "impact", "Heavy anvil impact"), (112, "sub", "Sub drop"), (140, "water", "Quench hiss / steam"),
             (184, "tail", "Cooling metal ticks + tail")]

    def strike_times(self, c):
        return [c.impact + s for s in STRIKES]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        st = self.strike_times(c)
        nstr = sum(1 for s in st if t >= s)
        hits = [K.pulse(t, s, 0.012, 0.16) * p["IMPACT_INTENSITY"] for s in st]
        hit = max(hits)
        hx, hy = c.hero()

        # ---- heat timeline
        pre = K.smooth(K.prog(t, c.start, c.reveal)) * 0.55
        if t < imp:
            heat = pre + 0.08 * nstr + 0.22 * hit
        else:
            heat = 0.95 * math.exp(-(t - imp) / 1.0) + 0.3 * hit
        heat *= 1 - K.smooth(ex * 1.3)
        seam_heat = (0.45 * math.exp(-max(0, t - imp) / 3.0) + 0.42) if t >= imp else heat
        seam_heat *= 1 - K.smooth(ex * 1.15)
        forge = (0.5 + 0.2 * math.sin(t * 7.1) * math.sin(t * 2.3)) * (1 - 0.6 * K.smooth(ex))

        # ---- smithy: near-black, forge glow from below, haze
        nx, ny = K.grid(H, W)
        bg = K.vgrad(H, W, (0.006, 0.005, 0.005), (0.02, 0.01, 0.006))
        bg += (K.soft_spot(H, W, 0.2, 1.25, 2.2, 0.7, 1.4) * (0.10 + 0.05 * forge))[..., None] * acc * bgI
        bg += (K.soft_spot(H, W, hx / (H / 2), hy / (H / 2), 1.0, 0.4, 2) * (0.05 * heat + 0.12 * hit))[..., None] \
            * acc * bgI
        haze = E.fog(H, W, t, (0.06, 0.045, 0.035), density=0.8, scale=1.4, speed=(0.004, -0.02), seed=7, warp=0.0, contrast=1.2)
        bg += haze * bgI * (0.5 + forge)

        # ---- title sprite: soft billet sharpening strike by strike
        sp = c.title()
        sh = c.shaded(IRON)
        soft = SHARP[nstr] if nstr < 3 else 0.0
        if nstr < 3:
            nxt = st[nstr]
            soft = soft + 2.0 * K.smooth(K.prog(t, nxt - 0.5, 0.5))  # swells slightly before each strike
        key = ("forgemaps",)
        if key not in c.cache:
            cr = K.sample(K.fft_noise(256, 2.0, 63, True), sp.h, sp.w, 2.2 * sp.h / max(1, float(sp.cap_px)))
            cracks = np.clip((cr - 0.86) * 9, 0, 1) * sp.mask
            c.cache[key] = (cracks, sp.dist)
        cracks, dist = c.cache[key]
        edge_hot = np.clip(1 - dist / max(1.0, 0.09 * float(sp.cap_px)), 0, 1) * sp.mask
        # emissive heat: whole body + hotter edges / cracks; hot spot where the last strike landed
        body = heat * (0.7 + 0.3 * sh.tex if sh.tex is not None else 0.8)
        if nstr > 0 and t < imp + 1.5:
            sx = STRIKE_X[nstr - 1]
            body = body + 0.35 * np.exp(-((sh.u - sx) / 0.18) ** 2) * math.exp(-(t - st[nstr - 1]) / 0.8)
        seams = np.maximum(edge_hot * 0.85, cracks) * seam_heat
        hmap = np.maximum(body, seams)
        emis = heat_col(hmap) * (sp.mask * 1.25)[..., None]
        light_gain = 0.55 + 0.6 * forge * 0.5 + 0.6 * hit
        rgb, a = sh.shade(light=(0.25, 0.9, 0.45), rim_gain=0.4 * forge + 0.8 * hit, rim_dir=(0, 1),
                          base=K.col(p["TEXT_COLOR"]), light_gain=light_gain, emissive=emis)
        if soft > 0.4:
            a = K.blur(a, soft * k)
            rgb = K.blur(rgb, soft * k)
            # unformed billet: dull, no crisp bevel
            rgb = rgb * 0.8 + heat_col(np.full(a.shape, heat * 0.9)) * a[..., None] * 0.4
        # strike squash: a quick flatten + settle
        sq = sum(K.pulse(t, s, 0.01, 0.09) for s in st)
        scale = 1.0 + 0.035 * sq + 0.015 * (1 - K.smooth(K.prog(t, c.start, c.reveal)))
        dip = 7 * k * sq
        cam = c.cam(zoom=1.0 + 0.05 * K.ease_in_out(K.prog(t, imp, c.exit_start + c.exit_dur - imp), 2))
        L = c.layer()
        op = K.smooth(K.prog(t, c.start, 0.8)) * (1 - K.smooth(K.prog(t, c.exit_start + c.exit_dur * 0.55,
                                                                         c.exit_dur * 0.45)))
        depth = 0.10 * float(sp.cap_px) * p["EXTRUSION_DEPTH"] * (1 if nstr > 0 else 0.4)
        side = np.array((0.05, 0.035, 0.03)) + heat_col(np.array(heat * 0.6)) * 0.25
        put_title(c, L, cam, rgb, a, sp, scale, off=(0, dip, 0), depth=depth, side=side, slices=8,
                  side_light=lambda q: 0.3 + 0.7 * q, opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.6, (0, 16), 22, k)
        img = comp(bg, L)
        # heat bloom (emissive only)
        glow_src = np.maximum(L.rgb - 0.35, 0) * (0.3 + 0.7 * heat)
        img += K.blur(glow_src, 18 * k) * 0.9 * p["GLOW_STRENGTH"] + K.blur(glow_src, 5 * k) * 0.4

        # ---- sparks from each strike
        if p["PARTICLE_INTENSITY"] > 0:
            for si, s in enumerate(st):
                dt = t - s
                if dt < 0 or dt > 1.6:
                    continue
                B = c.cache.get(("sparks", si))
                if B is None:
                    r = np.random.default_rng(100 + si)
                    n = int(110 * p["PARTICLE_INTENSITY"])
                    ang = r.uniform(math.pi * 0.95, math.pi * 2.05, n)  # mostly upward fan
                    spd = r.uniform(0.4, 2.2, n)
                    B = c.cache[("sparks", si)] = (n, ang, spd, r.random(n))
                n, ang, spd, rr = B
                ox = (hx + STRIKE_X[si] * float(sp.ink_w)) / (H / 2)
                oy = (hy - float(sp.ink_h) * 0.45) / (H / 2)
                dist_ = spd * (1 - np.exp(-dt * 3)) / 3 * 1.1
                gx = ox + np.cos(ang) * dist_
                gy = oy + np.sin(ang) * dist_ * 0.8 + 0.9 * dt * dt
                fade = np.exp(-dt / (0.25 + 0.6 * rr))
                Pb = E.Particles(n, 1)
                Pb.z = (0.8 + 0.4 * rr).astype(np.float32)
                vx = np.cos(ang) * spd * 0.03 * np.exp(-dt * 3)
                vy = (np.sin(ang) * spd * 0.024 * np.exp(-dt * 3) + 0.03 * dt)
                img += E.particle_layer(H, W, Pb, gx, gy, (1.0, 0.62, 0.25), 1.3, 1.4 * fade, zoom=1.0, glow=0.8,
                                        streak=(vx, vy))
        # strike flash
        img += (K.soft_spot(H, W, hx / (H / 2), hy / (H / 2), 1.6, 0.8, 1.2) * 0.22 * hit)[..., None] * \
            (acc * 0.6 + 0.4)

        # ---- quench steam during cooling, thickening into the exit
        steam_amt = (0.25 * K.smooth(K.prog(t, imp + 1.0, 1.5)) * (1 - 0.6 * K.smooth(K.prog(t, imp + 3, 2)))
                     + 0.75 * K.smooth(ex)) * bgI
        if steam_amt > 0.01:
            stm = E.fog(H, W, t, (0.30, 0.29, 0.28), density=steam_amt, scale=2.0, speed=(0.006, -0.05), seed=19, warp=0.04, contrast=1.3)
            stm = stm * np.exp(-((ny - hy / (H / 2) - 0.1) / 0.55) ** 2)[..., None]
            img = img + stm * (0.6 + 0.4 * forge)

        img = add_sub(c, img, cam, imp + 0.8, c.exit_start, (0.70, 0.58, 0.48), y_rel=0.9, tracking=0.5, rel=0.22)
        if t >= st[0]:
            sx_, sy_ = 0.0, 0.0
            for s in st:
                e = K.pulse(t, s, 0.01, 0.18) * p["SHAKE_AMOUNT"]
                dx, dy = K.shake(t, 0.006 * e, 26, int(s * 10))
                sx_, sy_ = sx_ + dx * H, sy_ + dy * H
            if abs(sx_) + abs(sy_) > 0.05:
                M = np.float32([[1.01, 0, -0.005 * W + sx_], [0, 1.01, -0.005 * H + sy_]])
                img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        return c.finish(img, vignette=0.6, grain=0.035, bloom=(0.8, 0.5),
                        grade=dict(shadows=(0.004, 0.001, -0.002), contrast=1.07, sat=0.95))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        A0, AD = ctl("AnimStart"), ctl("AnimDuration")
        X0, XD = ctl("ExitStart"), ctl("ExitDuration")
        ex = prog(X0, XD)
        BG = ctl("BackgroundIntensity")
        S = [f"({I} - 48)", f"({I} - 24)", I]
        nstr = " + ".join(step(s) for s in S)
        hit = f"max(max({decay(S[0], 4)}, {decay(S[1], 4)}), {decay(S[2], 4)})"
        heat = (f"((1 - {step(I)})*(0.55*{prog(A0, AD)} + 0.08*({nstr}) + 0.35*{hit})"
                f" + {step(I)}*(0.95*pow(2.718282, -max(time - {I}, 0)/41) + 0.3*{hit}))*(1 - min({ex}*1.3, 1))")
        seam = f"({step(I)}*(0.55*pow(2.718282, -max(time - {I}, 0)/96) + 0.12) + (1 - {step(I)})*{heat})*(1 - min({ex}*1.15, 1))"
        forge = "(0.5 + 0.2*sin(time*0.296)*sin(time*0.096))"

        g.at(0, 0)
        bg = F.gradient_bg(g, "SmithyDark", [(0, "#010101", 1), (1, "#060302", 1)])
        bg = F.light_spot(g, "ForgeGlow", bg, None, (0.6, -0.1), 2.2, 0.7, 0.5, accent=True, gain=0.5,
                          blend=f"{BG}*({forge})*(1 - 0.6*{ex})")
        haze = F.noise(g, "ForgeHaze", "#000000", "#1a120c", detail=5, scale=2.4, seethe_rate=0.05, contrast=1.6,
                       center="Point(0.5, 0.5 - time*0.0009)")
        bg = F.merge(g, "HazeMerge", bg, haze, mode="Screen", blend=f"0.7*{BG}")

        g.at(0, 2)
        ff, fs = fam(p["FONT_FAMILY"])
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], ff, fs, 0.19, 1.09, color=p["TEXT_COLOR"])
        iron = F.fill_material(g, "IronFace", title, [(0, "#191614", 1), (0.5, "#3c3530", 1), (0.56, "#5b4c40", 1),
                                                      (1, "#120f0d", 1)])
        face = F.merge(g, "IronMerge", title, iron, mode="Multiply", blend=0.9)
        cracks = F.noise(g, "HeatCracks", "#000000", "#ffffff", detail=3, scale=9, seethe_rate=0.0, contrast=6,
                         brightness=-0.35)
        cm = F.bitmap_mask(g, "CrackClip", title)
        F.masked(cracks, cm)
        heat_s = F.accent_solid(g, "HeatColor", 1.3)
        hm = F.bitmap_mask(g, "HeatMatte", title)
        F.masked(heat_s, hm)
        face = F.merge(g, "BodyHeat", face, heat_s, mode="Screen", blend=f"min({heat}, 1)")
        edge = F.edge_light(g, "HotSeams", title, 0.0, 0.0025, accent=True, gain=1.6, blur_px=1.5)
        face = F.merge(g, "SeamHeat", face, edge, mode="Screen", blend=f"min({seam}*1.4, 1)")
        crack_col = F.cc(g, "CrackColor", cracks, gain=f"{seam}*1.2")
        face = F.merge(g, "CrackHeat", face, crack_col, mode="Screen", blend=0.8)
        g.at(0, 4)
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        ext = F.extrusion_stack(g, "Extrude", clear, title, layers=6, dx=0.0, dy=-0.0012, color=(0.05, 0.035, 0.03))
        solid_t = F.merge(g, "TitleSolid", ext, face)
        sharp = (f"14*(1 - {step(S[0])}) + 6*({step(S[0])} - {step(S[1])}) + 1.5*({step(S[1])} - {step(S[2])})")
        billet = F.blur(g, "BilletSoftness", solid_t, sharp)
        sq = f"({decay(S[0], 2)} + {decay(S[1], 2)} + {decay(S[2], 2)})"
        placed = F.title_placement(g, "StrikeSquash", billet, size_expr=f"1 + 0.035*{sq}",
                                   center_extra_y=f"-0.006*{sq}")
        glow = F.softglow(g, "HeatBloom", placed, 18, gain=f"{ctl('GlowStrength')}*(0.3 + 1.2*min({heat}, 1))",
                          threshold=0.3)
        scene = F.merge(g, "TitleOverSmithy", bg, glow,
                        blend=f"{prog(A0, 20)}*(1 - {clamp01(f'({ex} - 0.55)/0.45')})")

        g.at(0, 6)
        for i, (s, sx) in enumerate(zip(S, STRIKE_X)):
            nn = f"170*{ctl('ParticleIntensity')}*{window(s, s + ' + 2', 1, 1)}"
            scene = F.particles(g, f"Sparks{i + 1}", scene, number=170, lifespan=30, velocity=0.05, angle=90,
                                angle_var=70, size=0.25, color=(1.0, 0.62, 0.25), region="SphereRgn",
                                region_size=(0.03,), center_y=0.08, turbulence=0.05, glow=4, number_expr=nn)
            scene = F.impact_flash(g, f"StrikeFlash{i + 1}", scene, color=p["ACCENT_COLOR"], peak=0.16, frames=4,
                                   offset=-48 + 24 * i)
        g.at(0, 8)
        steam = F.noise(g, "QuenchSteam", "#000000", "#4a4744", detail=6, scale=3.0, seethe_rate=0.08, contrast=1.7,
                        center="Point(0.5, 0.5 - time*0.0025)")
        sm = F.ellipse(g, "SteamBand", (0.5, 0.55), 1.8, 0.7, 0.5)
        F.masked(steam, sm)
        steam_amt = (f"{BG}*(0.25*{prog(I + ' + 24', 36)}*(1 - 0.6*{prog(I + ' + 72', 48)}) + 0.75*{ex})")
        scene = F.merge(g, "SteamMerge", scene, steam, mode="Screen", blend=steam_amt)
        scene = fusion_subtitle(g, scene, p, size=0.03, tracking=1.6, color=(0.70, 0.58, 0.48), y_off=-0.14,
                                t_in=f"{I} + 20", t_out=X0)
        g.at(0, 10)
        sx = f"({decay(S[0], 4)} + {decay(S[1], 4)} + {decay(S[2], 4)})"
        cam = F.xf(g, "Camera", scene,
                   center=f"Point(0.5 + 0.006*{ctl('ShakeAmount')}*{sx}*sin(time*1.7), "
                          f"0.5 + 0.006*{ctl('ShakeAmount')}*{sx}*cos(time*2.3))",
                   size=f"1 + 0.05*{e_inout(prog(I, f'{X0} + {XD} - {I}'))}", edges=1)
        g.output = F.finish(g, cam, vignette=0.6)


DESIGN = T14()
