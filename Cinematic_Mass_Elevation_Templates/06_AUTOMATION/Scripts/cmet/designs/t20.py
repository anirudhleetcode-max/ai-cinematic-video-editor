"""T20 - Phoenix Reborn (2.5D)."""
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

SUNGOLD = Material(base=(0.95, 0.72, 0.42), spec=(1.0, 0.92, 0.75), spec_power=55, spec_gain=0.8, diffuse=0.55,
                   ambient=0.08, metal=0.55, env_sky=(1.0, 0.85, 0.65), env_horizon=(0.25, 0.06, 0.03),
                   env_ground=(0.45, 0.16, 0.06), env_sharp=8, bevel=0.06, bevel_round=True, texture="grain",
                   tex_amount=0.05, rim=(1.0, 0.45, 0.2), seed=121)

N_PART = 1400


class T20(Design):
    ID = "T20"
    NAME = "Phoenix Reborn"
    SLUG = "Phoenix_Reborn"
    CATEGORY = "C - Mythic Atmospheres"
    CONCEPT = "Renewal and power: a rising double spiral of living sparks becomes the title, which ignites reborn."
    ENTRANCE = ("Two intertwined helices of glowing particles spiral up from the dark, widen at the top and then "
                "stream inward, each spark flying to its own point on the letterforms.")
    REVEAL = ("On the impact frame the converged sparks ignite the title in a bright white-gold flash that throws "
              "two wing-like arcs of embers outward, then settles into a clean, readable gold hold.")
    CAMERA = "Slow upward tilt following the spiral, small lift-and-settle at the ignition."
    MATERIAL = ("Radiant sun-gold metal with crimson rim light and a white-hot edge that cools after ignition; "
                "emissive particles with soft bloom.")
    EXIT = "The title is reborn again as embers: it dissolves bottom-to-top into sparks that spiral up and away."
    TECHNIQUES = ["3D helix particle spiral", "per-particle target convergence", "ignition flash", "wing arcs",
                  "cooling edge heat", "bottom-up ember dissolve exit"]
    TRUE_3D = False
    DURATION_FRAMES = 156
    DEFAULTS = dict(MAIN_TITLE="PHOENIX", SUBTITLE="RISE FROM THE ASHES", FONT_FAMILY="bebas",
                    SUB_FONT_FAMILY="cinzel_bold", TEXT_COLOR="#E8B46A", ACCENT_COLOR="#FF7A2E",
                    ANIMATION_START=6, ANIMATION_DURATION=58, IMPACT_FRAME=64, HOLD_DURATION=56, EXIT_START=118,
                    EXIT_DURATION=32, LETTER_SPACING=0.10, TITLE_WIDTH=0.52, SHAKE_AMOUNT=0.5)
    FUSION_NOTES = [
        "The spiral is two pEmitters whose positions orbit the vertical axis by expression (helix); per-particle "
        "target convergence onto the glyphs is approximated by a radial zoom-in of the particle render plus "
        "the ignition flash (Fusion particles cannot target text pixels without extra tools).",
    ]
    SOUND = [(0, "atmos", "Warm low drone"), (6, "fire", "Soft flame bed"), (6, "riser", "Spiral riser"),
             (20, "whoosh", "Spiral swirl"), (40, "rwhoosh", "Sparks rush inward"), (64, "impact", "Ignition hit"),
             (64, "swell", "Rebirth swell"), (66, "shimmer", "Ember shimmer"), (118, "whoosh", "Ember lift-off"),
             (132, "tail", "Tail")]

    # ------------------------------------------------------------ preview --
    def setup(self, c, sp):
        S = c.cache.get("setup")
        if S is None:
            r = np.random.default_rng(123)
            ys, xs = np.nonzero(sp.mask > 0.5)
            idx = r.choice(len(xs), size=N_PART, replace=len(xs) < N_PART)
            tx = (xs[idx] - sp.anchor[0]).astype(np.float32)
            ty = (ys[idx] - sp.anchor[1]).astype(np.float32)
            S = dict(tx=tx, ty=ty, strand=r.integers(0, 2, N_PART), ph=r.uniform(0, 1, N_PART).astype(np.float32),
                     delay=r.uniform(0, 0.25, N_PART).astype(np.float32), r=r.random(N_PART).astype(np.float32),
                     jit=r.normal(0, 1, (N_PART, 2)).astype(np.float32))
            c.cache["setup"] = S
        return S

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        PI = p["PARTICLE_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.02, 0.45)
        after = 1.0 if t >= imp else 0.0
        T = K.prog(t, 0, c.dur)
        nx, ny = K.grid(H, W)
        hx, hy = c.hero()
        sp = c.title()
        hxn, hyn = float(hx / (H / 2)), float(hy / (H / 2))

        # ---- environment: warm dark, ember haze, rising heat
        bg = K.vgrad(H, W, (0.008, 0.004, 0.006), (0.05, 0.012, 0.008), gamma=1.4)
        lvl = (0.25 + 0.5 * K.smooth(u) + 0.6 * hit) * (1 - 0.6 * K.smooth(ex))
        bg += (K.soft_spot(H, W, hxn, hyn + 0.1, 1.4, 0.9, 1.3) * 0.16 * lvl)[..., None] * acc * bgI
        haze = E.fog(H, W, t, (0.10, 0.035, 0.02), density=0.8, scale=1.5, speed=(0.0, -0.03), seed=125, warp=0.0,
                     contrast=1.3)
        bg += haze * bgI * (0.4 + lvl)

        # ---- title: ignition, cooling, ember dissolve
        sh = c.shaded(SUNGOLD)
        heat = (1.4 * hit + 0.45 * math.exp(-max(0.0, t - imp) / 1.2) * after)
        rgb, a = sh.shade(light=(-0.2, -0.85, 0.5), rim_gain=0.5 + 1.2 * hit, rim_dir=(0, 1),
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.9 + 0.5 * hit,
                          emissive=(sh.edge * heat)[..., None] * K.col((1.0, 0.85, 0.6)),
                          env_shift=-0.1 + 0.05 * math.sin(t))
        # bottom-up dissolve on exit (ember front)
        if ex > 0:
            if "dnoise" not in c.cache:
                c.cache["dnoise"] = K.sample(K.fft_noise(256, 1.4, 127), sp.h, sp.w, 4.0 * sp.h / H)
            vmap = (0.5 - sh.v) * 0.8 + c.cache["dnoise"] * 0.35
            thr = K.ease_in_out(ex, 1.5) * 1.25 - 0.05
            keep = np.clip((vmap - thr) * 12, 0, 1)
            front = np.clip(1 - np.abs(vmap - thr) * 18, 0, 1)
            a = a * keep
            rgb = rgb + (front * sp.mask)[..., None] * (acc * 1.2 + 0.4)
        cam = c.cam(zoom=1.0 + 0.04 * K.ease_in_out(T, 2), pan=(0, -12 * k * K.pulse(t, imp, 0.05, 0.5)))
        L = c.layer()
        op = K.smooth(K.prog(t, imp - 0.06, 0.12))
        depth = 0.08 * float(sp.cap_px) * p["EXTRUSION_DEPTH"]
        put_title(c, L, cam, rgb, a, sp, 1.0 + 0.04 * K.pulse(t, imp, 0.02, 0.3), depth=depth,
                  side=np.array((0.35, 0.12, 0.05)), slices=5, side_light=lambda q: 0.4 + 0.6 * q, opacity=op)
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.4, (0, 12), 20, k)
        img = comp(bg, L)
        img += K.blur(np.maximum(L.rgb - 0.7, 0), 14 * k) * (0.5 + 1.2 * hit) * p["GLOW_STRENGTH"]
        img += (K.soft_spot(H, W, hxn, hyn, 1.3, 0.5, 1.6) * 0.35 * hit)[..., None] * (acc * 0.5 + 0.5)

        # ---- particles: helix -> convergence -> (hidden) ; exit embers spiral up from the title
        if PI > 0:
            S = self.setup(c, sp)
            n = int(N_PART * min(PI, 1.0))
            tx, ty = S["tx"][:n], S["ty"][:n]
            strand, ph, dl, rr, jit = S["strand"][:n], S["ph"][:n], S["delay"][:n], S["r"][:n], S["jit"][:n]
            s_px = H / 2
            pu = np.clip((u - dl) / (1 - 0.25), 0, 1)  # per-particle progress
            # helix (first 60%)
            hu = np.clip(pu / 0.6, 0, 1)
            theta = (ph * 6.0 + hu * 9.0 + strand * math.pi + t * 1.2)
            radius = 0.20 + 0.55 * hu ** 1.5
            hxp = hxn + np.cos(theta) * radius
            hyp = 1.05 - hu * (1.05 - hyn + 0.35) + (ph - 0.5) * 0.35 * (1 - hu)
            hz = 1.0 + 0.35 * np.sin(theta)
            # convergence (last 40%)
            cu = np.clip((pu - 0.6) / 0.4, 0, 1)
            ce = cu * cu * (3 - 2 * cu)
            gx = hxn + tx * cam.zoom / s_px
            gy = hyn + ty * cam.zoom / s_px
            x = hxp * (1 - ce) + gx * ce
            y = hyp * (1 - ce) + gy * ce
            z = hz * (1 - ce) + 1.0 * ce
            inten = np.clip(pu * 6, 0, 1) * (1 - np.clip((t - imp) / 0.25, 0, 1)) * 0.9
            # ignition wing arcs: a subset flies out sideways and up in arcs
            if t >= imp:
                dt = t - imp
                wing = (rr < 0.35)
                side = np.sign(tx + 1e-3)
                arc = 1 - np.exp(-dt * 2.5)
                wx = gx + side * arc * (0.6 + 0.8 * rr) * 0.9
                wy = gy - arc * (0.35 + 0.5 * rr) + 0.4 * arc * arc * np.abs(tx) / max(1.0, float(sp.ink_w))
                x = np.where(wing, wx, x)
                y = np.where(wing, wy, y)
                inten = np.where(wing, np.exp(-dt / (0.5 + 0.6 * rr)) * 1.2, inten)
            # exit embers rise from the dissolving front in a widening spiral
            if ex > 0:
                ev = 0.5 - ty / max(1.0, float(sp.ink_h))  # 0 bottom .. 1 top
                thr = K.ease_in_out(ex, 1.5) * 1.25 - 0.05
                age = np.clip((thr - ev * 0.8) * 2.5, 0, None)
                on = age > 0
                th2 = ph * 6.28 + age * 5
                x = np.where(on, gx + np.cos(th2) * age * 0.25 + jit[:, 0] * 0.02 * age, x)
                y = np.where(on, gy - age * 0.55, y)
                inten = np.where(on, np.exp(-age * 1.4) * 1.1, inten)
            P = c.cache.get("Pobj")
            if P is None or P.n != n:
                P = c.cache["Pobj"] = E.Particles(n, 1)
            P.z = z.astype(np.float32)
            P.r = rr
            P.r2 = np.full(n, 0.8, np.float32)
            col = acc * 0.6 + K.col((1.0, 0.85, 0.55)) * 0.5
            img += E.particle_layer(H, W, P, x.astype(np.float32), y.astype(np.float32), col, 1.6,
                                    inten.astype(np.float32) * 1.1, zoom=1.0, glow=1.2, t=t, flicker=0.25)
        img = add_sub(c, img, cam, imp + 0.55, c.exit_start - 0.1, (0.92, 0.76, 0.58), y_rel=0.85, tracking=0.5,
                      rel=0.17)
        sx, sy = c.shake(0.004, 0.25, 15)
        if abs(sx) + abs(sy) > 0.05:
            Mx = np.float32([[1.01, 0, -0.005 * W + sx], [0, 1.01, -0.005 * H + sy]])
            img = cv2.warpAffine(img, Mx, (W, H), borderMode=cv2.BORDER_REFLECT)
        return c.finish(img, vignette=0.55, grain=0.03, bloom=(0.8, 0.5),
                        grade=dict(shadows=(0.004, 0.0, -0.002), contrast=1.06, sat=0.95))

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
        lvl = f"(0.25 + 0.5*{e_inout(u)} + 0.6*{decay(I, 11)})*(1 - 0.6*{ex})"

        g.at(0, 0)
        bg = F.gradient_bg(g, "EmberDark", [(0, "#0d0302", 1), (1, "#020101", 1)])
        bg = F.light_spot(g, "HeatPool", bg, None, (0.5, 0.45), 1.4, 0.9, 0.6, accent=True, gain=0.3,
                          blend=f"min({BG}*{lvl}, 1)")
        haze = F.noise(g, "AshHaze", "#000000", "#1e0a05", detail=5, scale=2.2, seethe_rate=0.05, contrast=1.4,
                       center="Point(0.5, 0.5 - time*0.0012)")
        bg = F.merge(g, "HazeMerge", bg, haze, mode="Screen", blend=f"{BG}")

        g.at(0, 2)
        sparks = F.solid(g, "SparkClear", (0, 0, 0), alpha=0.0)
        for i in range(2):
            on = f"{step(A0)}*(1 - {step(I)})"
            sparks = F.particles(g, f"Helix{i + 1}", sparks, number=60, lifespan=40, velocity=0.012, angle=90,
                                 angle_var=8, size=0.35, color=p["ACCENT_COLOR"], region="SphereRgn",
                                 region_size=(0.02,), center_y=-0.55, turbulence=0.05, glow=6,
                                 number_expr=f"60*{PI}*{on}")
            em = g.tools[f"Helix{i + 1}Emitter"]
            ph = f"time*0.35 + {math.pi * i:.4f}"
            em.expr("Transform3DOp.Translate.X", f"(0.2 + 0.4*{u})*sin({ph})", 0)
            em.expr("Transform3DOp.Translate.Z", f"(0.2 + 0.4*{u})*cos({ph})", 0)
            em.expr("Transform3DOp.Translate.Y", f"-0.55 + 0.7*{e_inout(u)}", -0.55)
        conv = F.xf(g, "SparkConverge", sparks,
                    size=f"1 - 0.5*{e_in(prog(f'{A0} + {AD}*0.6', f'{AD}*0.4'), 2)}",
                    center=f"Point({ctl('TextPosX')}, {ctl('TextPosY')})")
        bg = F.merge(g, "SpiralSparks", bg, conv, mode="Screen", blend=f"min({PI}, 1)")

        g.at(0, 4)
        ff, fs = fam(p["FONT_FAMILY"])
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], ff, fs, 0.2, 1.1, color=p["TEXT_COLOR"])
        gold = F.fill_material(g, "SunGold", title, [(0, "#7a3a10", 1), (0.45, "#e0a050", 1), (0.52, "#fff0c8", 1),
                                                     (1, "#6a2a0a", 1)])
        face = F.merge(g, "GoldMerge", title, gold, mode="Multiply", blend=0.85)
        rim = F.edge_light(g, "CrimsonRim", title, 0.0, 0.003, accent=True, gain=1.4, blur_px=1.5)
        face = F.merge(g, "CrimsonRimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.5 + 1.2*{decay(I, 11)}), 1)")
        hotedge = F.edge_light(g, "WhiteHotEdge", title, 0.0, 0.0, color=(1.0, 0.9, 0.7), blur_px=2.0)
        face = F.merge(g, "WhiteHotMerge", face, hotedge, mode="Screen",
                       blend=f"min(1.4*{decay(I, 11)} + 0.45*{step(I)}*pow(2.718282, -max(time - {I}, 0)/29), 1)")
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        ext = F.extrusion_stack(g, "Extrude", clear, title, layers=4, dx=0.0, dy=-0.0012, color=(0.35, 0.12, 0.05))
        solid_t = F.merge(g, "TitleSolid", ext, face)
        # bottom-up ember dissolve on exit
        wipe = F.rect(g, "EmberWipe", (0.5, 0.5), 1.4, 1.0, 0.03)
        wipe.expr("Center", f"Point(0.5, 0.5 + 1.1*{e_inout(ex)})", [0.5, 0.5])
        held = F.solid(g, "TitleHolder", (0, 0, 0), alpha=0.0)
        tm = F.merge(g, "TitleDissolve", held, solid_t)
        F.masked(tm, wipe)
        g.at(0, 6)
        placed = F.title_placement(g, "TitleIgnite", tm, size_expr=f"1 + 0.04*{decay(I, 7)}",
                                   center_extra_y=f"0.01*{decay(I, 12)}")
        tglow = F.softglow(g, "IgnitionGlow", placed, 16, gain=f"{ctl('GlowStrength')}*(0.5 + 1.2*{decay(I, 11)})",
                           threshold=0.6)
        scene = F.merge(g, "TitleOverEmbers", bg, tglow, blend=prog(f"{I} - 1", 3))
        scene = F.impact_flash(g, "IgnitionFlash", scene, color=p["ACCENT_COLOR"], peak=0.25, frames=8)
        g.at(0, 8)
        wings = F.particles(g, "WingArcs", scene, number=260, lifespan=30, velocity=0.04, angle=90, angle_var=75,
                            size=0.3, color=(1.0, 0.75, 0.4), region="CubeRgn", region_size=(0.9, 0.05, 0.1),
                            center_y=0.0, turbulence=0.15, glow=6,
                            number_expr=f"260*{PI}*{window(I, I + ' + 2', 1, 1)}")
        embers = F.particles(g, "ExitEmbers", wings, number=30, lifespan=50, velocity=0.02, angle=90, angle_var=25,
                             size=0.25, color=p["ACCENT_COLOR"], region="CubeRgn", region_size=(0.9, 0.2, 0.1),
                             center_y=0.0, turbulence=0.4, glow=5, number_expr=f"30*{PI}*{window(X0, f'{X0} + {XD}', 2, 4)}")
        scene = fusion_subtitle(g, embers, p, size=0.026, tracking=1.6, color=(0.92, 0.76, 0.58), y_off=-0.13,
                                t_in=f"{I} + 12", t_out=f"{X0} - 2")
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.04, shake_frames=6, shake_amp=0.004)
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T20()
