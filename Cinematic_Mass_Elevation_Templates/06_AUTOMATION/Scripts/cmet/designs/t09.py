"""T09 - Ashes of Power."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, apply_shake, subtitle
from ..fusion import FuID, ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_extruded

ASH = Material(base=(0.62, 0.6, 0.57), spec=(1.0, 0.95, 0.88), spec_power=18, spec_gain=0.15, diffuse=0.9,
               ambient=0.12, metal=0.0, bevel=0.045, bevel_round=True, texture="concrete", tex_amount=0.45,
               bump=0.035, rim=(1.0, 0.9, 0.75), seed=99)


class T09(Design):
    ID = "T09"
    NAME = "Ashes of Power"
    SLUG = "Ashes_of_Power"
    CATEGORY = "B - Elemental Fury"
    CONCEPT = "Power rebuilt from ruin: falling ash and black dust are drawn together into solid lettering."
    ENTRANCE = ("Ash drifts down through a dark void; grains peel off their fall and travel on curved paths onto points "
                "of the letter shapes, accumulating until the letters exist as dusty forms.")
    REVEAL = "On the impact frame the dust compacts into a solid, stable title; a controlled puff and a backlight pulse."
    CAMERA = "Slow push-in while the camera drifts gently downward with the ash."
    MATERIAL = "Compacted ash / charcoal-stone with grainy bump, pale rim from a narrow vertical backlight slit."
    EXIT = "An erosion front crosses the title left to right; the released ash falls away under gravity."
    TECHNIQUES = ["targeted particle convergence onto glyph samples", "granular accumulation mask",
                  "narrow vertical slit backlight", "falling ash with flutter", "compaction pulse", "gravity crumble exit"]
    TRUE_3D = False
    DURATION_FRAMES = 204
    DEFAULTS = dict(MAIN_TITLE="ASHES OF POWER", SUBTITLE="FROM RUIN, A THRONE", FONT_FAMILY="cinzel_bold",
                    TEXT_COLOR="#B4AEA6", ACCENT_COLOR="#EAD3AE", ANIMATION_START=8, ANIMATION_DURATION=88,
                    IMPACT_FRAME=96, HOLD_DURATION=70, EXIT_START=166, EXIT_DURATION=36, LETTER_SPACING=0.06,
                    TITLE_WIDTH=0.7)
    SOUND = [(0, "atmos", "Dry hollow wind bed"), (0, "wind", "Ash-laden wind"),
             (8, "riser", "Granular riser while ash converges (8-96)"), (40, "debris", "Fine sand trickle"),
             (90, "rwhoosh", "Air drawn in"), (96, "impact", "Compaction thud"), (96, "sub", "Low sub"),
             (97, "debris", "Dust puff"), (166, "debris", "Crumble / sand pour"), (186, "tail", "Wind tail")]

    # ------------------------------------------------------------ preview --
    def _setup(self, c, sp):
        S = c.cache.get("ash")
        if S is not None:
            return S
        r = np.random.default_rng(91)
        ys, xs = np.nonzero(sp.mask > 0.55)
        n = min(int(900 * max(c.p["PARTICLE_INTENSITY"], 0.0)), len(xs))
        idx = r.choice(len(xs), size=n, replace=False) if n > 0 else np.zeros(0, int)
        tx, ty = xs[idx].astype(np.float32), ys[idx].astype(np.float32)
        u_t = (tx - sp.anchor[0]) / max(sp.ink_w, 1)
        S = dict(tx=tx, ty=ty,
                 x0=r.uniform(-2.2, 2.2, n).astype(np.float32), y0=r.uniform(-1.4, 1.4, n).astype(np.float32),
                 vy=r.uniform(0.05, 0.12, n).astype(np.float32), ph=r.uniform(0, 6.28, n).astype(np.float32),
                 # departures staggered roughly left -> right with randomness
                 s=np.clip(0.45 * (u_t + 0.5) + r.uniform(0, 0.4, n), 0, 0.82).astype(np.float32),
                 d=r.uniform(0.35, 0.55, n).astype(np.float32), sw=r.uniform(-0.25, 0.25, n).astype(np.float32),
                 rr=r.random(n).astype(np.float32))
        nz = K.sample(K.fft_noise(256, 1.2, 93), sp.h, sp.w, 6.0 * sp.h / c.H)
        S["grain"] = nz.astype(np.float32)
        ero = K.sample(K.fft_noise(256, 1.7, 94), sp.h, sp.w, 2.5 * sp.h / c.H)
        uu = (np.arange(sp.w, dtype=np.float32) - sp.anchor[0]) / max(sp.ink_w, 1)
        S["ero"] = (0.6 * (uu[None, :] + 0.5) + 0.4 * ero).astype(np.float32)
        c.cache["ash"] = S
        return S

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        PI = p["PARTICLE_INTENSITY"]
        GL = p["GLOW_STRENGTH"]
        imp = c.impact
        ex = c.exit_u()
        hit = c.hit(0.03, 0.5)
        after = t >= imp
        sp = c.title()
        S = self._setup(c, sp)
        hx, hy = c.hero()
        zoom = 1.0 + 0.06 * K.ease_in_out(K.prog(t, 0, c.dur))
        drift = 26 * k * (1 - 2 * K.ease_in_out(K.prog(t, 0, c.dur)))
        cam = c.cam(zoom=zoom, pan=(0, drift))
        tcx, tcy = hx / (H / 2), (hy + drift) / (H / 2)

        # --- void + narrow vertical backlight slit
        h2, w2 = H // 2, W // 2
        nx, ny = K.grid(h2, w2)
        bg = K.vgrad(h2, w2, (0.008, 0.008, 0.009), (0.004, 0.004, 0.004))
        back = (0.55 + 0.3 * K.smooth(c.reveal_u()) + 1.0 * hit) * (1 - 0.5 * K.smooth(ex))
        slit = np.exp(-((nx - tcx) / 0.007) ** 2) * np.exp(-((ny - tcy) / 1.1) ** 4)
        haze = np.exp(-((nx - tcx) / 0.22) ** 2) * np.exp(-((ny - tcy) / 0.9) ** 2)
        fogn = K.fbm_field(h2, w2, t, 1.2, (0.01, 0.004), 95, beta=2.4, warp=0.08)
        bg += ((slit * 0.7 + haze * 0.11 * (0.6 + 0.8 * fogn)) * back * bgI)[..., None] * acc
        bg += (np.clip(fogn - 0.45, 0, 1) * 0.04 * bgI)[..., None] * np.array([0.8, 0.8, 0.82], np.float32)
        bg = cv2.resize(bg, (W, H), interpolation=cv2.INTER_LINEAR)
        img = bg

        # --- ambient falling ash (lit near the slit)
        if PI > 0:
            P = c.cache.get("fall")
            if P is None:
                P = c.cache["fall"] = E.Particles(int(320 * PI), seed=97, z=(0.4, 3.0))
            x, y = P.drift(t, vel=(0.01, 0.07), turb=0.04, freq=0.8)
            lit = 0.25 + 1.6 * np.exp(-((x * zoom / P.z - tcx) / 0.2) ** 2)
            img = img + E.particle_layer(H, W, P, x, y, acc * 0.5 + 0.35, 1.2, 0.35 * lit * (1 - 0.5 * ex),
                                         zoom=zoom, focus=1.0, dof=1.0, flicker=0.3, t=t, glow=0.4,
                                         pan=(0, drift / (H / 2)))

        # --- title build-up (granular), solid after impact, eroded on exit
        sh = c.shaded(ASH)
        span = max(imp - c.start, 0.2)
        build = K.smooth(K.prog(t, c.start + span * 0.35, span * 0.65))
        solid = K.smooth(K.prog(t, imp - 0.08, 0.16))
        grain = S["grain"]
        dusty = np.clip((build * 1.15 - grain) / 0.12, 0, 1) * (0.55 + 0.45 * grain)
        amask = dusty * (1 - solid) + solid
        emis = None
        if ex > 0:
            front = ex * 1.3 - 0.15
            d = S["ero"] - front
            amask = amask * np.clip(d / 0.03, 0, 1)
            band = np.exp(-(d / 0.025) ** 2) * sp.mask
            emis = (band * 0.5)[..., None] * acc
        rim = (0.6 + 0.3 * build + 1.4 * hit) * (1 - 0.4 * ex) * GL
        lg = (0.25 + 0.45 * build + 0.3 * solid + 0.4 * hit) * (1 - 0.3 * ex)
        rgb, a = sh.shade(light=(-0.2, -0.6, 0.75), rim_dir=(0.0, -1.0), rim_gain=rim, base=K.col(p["TEXT_COLOR"]),
                          light_gain=lg, emissive=emis)
        a = a * amask
        L = c.layer()
        depth = 0.1 * sp.cap_px * p["EXTRUSION_DEPTH"] * solid
        if depth > 0.5:
            place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, (hx, hy, 0), 1.0,
                           (0, 0, p["TEXT_ROTATION"]), depth, (0.03, 0.028, 0.026), slices=6,
                           side_light=lambda q: 0.5 + 0.7 * q)
        else:
            c.place(L, cam, rgb, a, sp, 1.0)
        # contact shadow of the slit light onto the haze behind: darken the backlight where letters block it
        img = img * (1 - K.blur(L.a, 10 * k)[..., None] * 0.35 * p["SHADOW_STRENGTH"])
        img = comp(img, L)
        img = img + K.blur(np.maximum(L.rgb - 0.5, 0), 6 * k) * 0.4 * GL

        # --- converging grains: leave their fall, curve onto glyph sample points
        rot = math.radians(p["TEXT_ROTATION"])
        cr, sr = math.cos(rot), math.sin(rot)
        n = len(S["tx"])
        if n and PI > 0 and t < imp + 0.6:
            ox = (S["tx"] - sp.anchor[0]) * zoom
            oy = (S["ty"] - sp.anchor[1]) * zoom
            gx_t = (hx + ox * cr - oy * sr) / (H / 2)
            gy_t = (hy + drift + ox * sr + oy * cr) / (H / 2)
            fall_y = (S["y0"] + S["vy"] * t + 1.4) % 2.8 - 1.4
            fall_x = S["x0"] + 0.04 * np.sin(t * 1.3 + S["ph"])
            t0 = c.start + S["s"] * span
            w = np.clip((t - t0) / (S["d"] * span), 0, 1)
            w = w * w * (3 - 2 * w)
            # freeze the departure point so the path is continuous after departure
            fy0 = (S["y0"] + S["vy"] * np.minimum(t, t0) + 1.4) % 2.8 - 1.4
            fx0 = S["x0"] + 0.04 * np.sin(np.minimum(t, t0) * 1.3 + S["ph"])
            sx = np.where(w > 0, fx0, fall_x)
            sy = np.where(w > 0, fy0, fall_y)
            px = sx + (gx_t - sx) * w
            py = sy + (gy_t - sy) * w
            arc = np.sin(np.pi * w) * S["sw"]
            dxn, dyn = gx_t - sx, gy_t - sy
            px, py = px - dyn * arc, py + dxn * arc
            landed = w >= 1
            inten = (0.35 + 0.65 * w) * np.where(landed, 1 - solid, 1.0) * (0.5 + 0.5 * S["rr"])
            inten = inten * K.smooth(K.prog(t, 0, 0.6))
            Pg = E.Particles(n, 1)
            Pg.z = np.ones(n, np.float32)
            Pg.r = S["rr"] * 0.6
            vx = (dxn - dyn * np.cos(np.pi * w) * np.pi * S["sw"]) * 0.004 * (w > 0) * (w < 1)
            vy = (dyn + dxn * np.cos(np.pi * w) * np.pi * S["sw"]) * 0.004 * (w > 0) * (w < 1)
            img = img + E.particle_layer(H, W, Pg, px, py, acc * 0.3 + 0.35, 1.7, 1.2 * inten, glow=0.3,
                                         streak=(vx, vy))

        # --- compaction puff
        if after and PI > 0 and t < imp + 2.0:
            dt = t - imp
            q = cv2.resize(K.soft_spot(H // 4, W // 4, tcx, tcy, 0.55 * sp.ink_w / (H / 2) * (1 + 0.6 * dt),
                                       0.12 + 0.2 * dt, 1.6), (W, H))
            dn = cv2.resize(K.fbm_field(H // 4, W // 4, t, 3.0, (0.03, 0.01), 96, beta=2.0), (W, H))
            img = img + ((q * np.clip(dn - 0.4, 0, 1)) * 0.3 * math.exp(-dt / 0.6) * PI)[..., None] * \
                np.array([0.55, 0.54, 0.52], np.float32)

        # --- crumble: released ash falls with gravity
        if ex > 0 and PI > 0:
            R = c.cache.get("crumble")
            if R is None:
                r = np.random.default_rng(98)
                ys_, xs_ = np.nonzero(sp.mask > 0.6)
                idx = r.choice(len(xs_), size=min(int(500 * PI), len(xs_)), replace=False)
                R = c.cache["crumble"] = (xs_[idx].astype(np.float32), ys_[idx].astype(np.float32),
                                          S["ero"][ys_[idx], xs_[idx]], r.random(len(idx)).astype(np.float32))
            rx, ry, re, rr = R
            t_rel = c.exit_start + (re + 0.15) / 1.3 * c.exit_dur
            age = np.maximum(t - t_rel, 0)
            live = t > t_rel
            ox = (rx - sp.anchor[0]) * zoom
            oy = (ry - sp.anchor[1]) * zoom
            gx = (hx + ox * cr - oy * sr) / (H / 2) + 0.03 * age * (rr - 0.3)
            gy = (hy + drift + ox * sr + oy * cr) / (H / 2) + 0.35 * age * age + 0.05 * age
            Pc = E.Particles(len(rx), 1)
            Pc.z = np.ones(len(rx), np.float32)
            img = img + E.particle_layer(H, W, Pc, gx, gy, acc * 0.5 + 0.4, 1.0,
                                         0.8 * live * np.exp(-age / 1.2), glow=0.3,
                                         streak=(np.zeros(len(rx)), 0.01 * age + 0.002))

        img = subtitle(c, img, cam, imp + 0.6, c.exit_start - 0.2, (0.7, 0.66, 0.6), y_rel=0.95, tracking=0.5)
        img = apply_shake(c, img, 0.002, 0.25, 12)
        img = img * (1 - 0.9 * K.smooth((ex - 0.8) / 0.2))
        return c.finish(img, vignette=0.55, grain=0.04, bloom=(0.75, 0.45))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S = ctl("AnimStart")
        ES = ctl("ExitStart")
        BG = ctl("BackgroundIntensity")
        GL = ctl("GlowStrength")
        PI = ctl("ParticleIntensity")
        ED = ctl("ExitDuration")
        span = f"max({I} - {S}, 1)"
        build = e_inout(prog(f"{S} + 0.35*{span}", f"0.65*{span}"))
        solid = prog(f"{I} - 2", 4)
        ex = prog(ES, ctl("ExitDuration"))
        drift = f"(0.012*(1 - 2*{e_inout(prog(0, g.frames))}))"

        # void + narrow slit backlight ------------------------------------------------
        g.at(0, 0)
        bg = F.gradient_bg(g, "Void", [(0, "#020202", 1), (1, "#010101", 1)])
        back = f"min({BG}*(0.55 + 0.3*{build} + {ctl('ImpactIntensity')}*{decay(I, 12)})*(1 - 0.5*{ex}), 1)"
        bg = F.light_spot(g, "SlitHaze", bg, None, (0.5, 0.5), 0.14, 1.4, 0.5, accent=True, gain=0.3, blend=back)
        bg = F.light_spot(g, "BacklightSlit", bg, None, (0.5, 0.5), 0.004, 1.6, 0.004, accent=True, gain=1.4,
                          blend=back)
        hz = F.noise(g, "AshHaze", "#000000", "#141414", detail=5, scale=2.0, seethe_rate=0.03, contrast=1.5,
                     center="Point(0.5 + time*0.0004, 0.5 + time*0.0002)")
        bg = F.merge(g, "AshHazeMerge", bg, hz, mode="Screen", blend=f"0.7*{BG}")
        bg = F.particles(g, "FallingAsh", bg, number=30, lifespan=220, velocity=0.0035, angle=-90, angle_var=20,
                         size=0.22, color=(0.75, 0.72, 0.68), region="CubeRgn", region_size=(2.4, 0.1, 1.0),
                         center_y=0.62, turbulence=0.2, glow=0)
        bg = F.xf(g, "EnvDrift", bg, center=f"Point(0.5, 0.5 + 0.5*{drift})")

        # title: granular accumulation -> solid ------------------------------------------
        g.at(0, 2)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Cinzel", "Bold", 0.11, 1.06, color=p["TEXT_COLOR"])
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        ashg = F.fill_material(g, "AshShade", title, [(0, "#f0ece6", 1), (0.5, "#bdb7af", 1), (1, "#6e6a64", 1)])
        face = F.merge(g, "AshFace", title, ashg, mode="Multiply", blend=1.0)
        gn = F.noise(g, "AshGrainTex", "#4a4a4a", "#d0d0d0", detail=10, scale=22, seethe_rate=0.0, contrast=2.0)
        gm = F.bitmap_mask(g, "AshGrainMatte", title)
        gr = F.merge(g, "AshGrainHolder", clear, gn)
        F.masked(gr, gm)
        face = F.merge(g, "CompactedAsh", face, gr, mode="Overlay", blend=0.55)
        rim = F.edge_light(g, "SlitRim", title, 0.0, -0.0025, accent=True, gain=1.3, blur_px=1.0)
        face = F.merge(g, "SlitRimMerge", face, rim, mode="Screen",
                       blend=f"min({GL}*(0.6 + 0.3*{build} + 1.4*{ctl('ImpactIntensity')}*{decay(I, 10)}), 1)")
        ext = F.extrusion_stack(g, "AshDepth", clear, title, layers=5, dx=0.0, dy=-0.001, color=(0.03, 0.028, 0.026))
        body = F.merge(g, "AshBody", ext, face)
        g.at(0, 4)
        # granular build-up: grain noise thresholded by the build progress, then fully solid at impact
        bn = F.noise(g, "BuildGrain", "#000000", "#ffffff", detail=8, scale=30, seethe_rate=0.0, contrast=1.4)
        bm = F.bitmap_mask(g, "BuildMask", bn, channel="Luminance")
        bm.expr("Low", f"(1 - {build}*1.15)*(1 - {solid})", 1)
        bm.expr("High", f"(1 - {build}*1.15)*(1 - {solid}) + 0.12", 1)
        bm.set(Invert=1)
        # erosion front (exit): left->right ramp + noise
        er = F.gradient_bg(g, "ErodeRamp", [(0, "#000000", 1), (1, "#ffffff", 1)], start=(0.2, 0.5), end=(0.8, 0.5))
        en = F.noise(g, "ErodeNoise", "#000000", "#999999", detail=6, scale=8, seethe_rate=0.0, contrast=1.4)
        emap = F.merge(g, "ErodeMap", er, en, mode="Multiply", blend=0.4)
        em = F.bitmap_mask(g, "ErodeKeep", emap, channel="Luminance", paint="Multiply", prev=bm)
        em.expr("Low", f"{ex}*1.3 - 0.15", 0)
        em.expr("High", f"{ex}*1.3 - 0.12", 0.03)
        grown = F.merge(g, "AshAccumulate", clear, body)
        F.masked(grown, em)
        lit = F.cc(g, "Compaction", grown,
                   gain=f"(0.25 + 0.45*{build} + 0.3*{solid} + 0.4*{ctl('ImpactIntensity')}*{decay(I, 8)})*(1 - 0.3*{ex})")
        placed = F.title_placement(g, "TitlePlace", lit, center_extra_y=drift)
        sh_src = F.solid(g, "SlitShadowColor", (0, 0, 0))
        shm = F.bitmap_mask(g, "SlitShadowMatte", placed)
        F.masked(sh_src, shm)
        shadow = F.blur(g, "SlitShadowSoft", sh_src, 12)
        scene = F.merge(g, "SlitShadow", bg, shadow, blend=f"0.35*{ctl('ShadowStrength')}")
        scene = F.merge(g, "TitleOverVoid", scene, placed)

        # converging ash: a contracting, swirling particle field + grains inside the glyphs ---------------
        g.at(0, 6)
        cem = g.add("pEmitter", "ConvergeEmitter")
        cem.expr("Number", f"60*{PI}*(1 - {step(I)})", 60)
        cem.set(Lifespan=60, LifespanVariance=20, Velocity=0.0, Angle=0, Region=FuID("CubeRgn"))
        cem.setk("CubeRgn.Width", 0.9)
        cem.setk("CubeRgn.Height", 0.14)
        cem.setk("CubeRgn.Depth", 0.05)
        cem.setk("ParticleStyle.ColorControls", 1)
        cem.setk("ParticleStyle.Red", 0.8)
        cem.setk("ParticleStyle.Green", 0.78)
        cem.setk("ParticleStyle.Blue", 0.74)
        cem.setk("ParticleStyle.Size", 0.12)
        crd = g.add("pRender", "ConvergeRender")
        crd.conn("Input", cem)
        F.frame_inputs(crd, g)
        contract = F.xf(g, "ConvergeContract", crd,
                        size=f"1 + 2.2*(1 - {e_inout(prog(S, f'0.9*{span}'))})",
                        angle=f"35*(1 - {e_inout(prog(S, f'0.9*{span}'))})")
        cplace = F.title_placement(g, "ConvergePlace", contract, center_extra_y=drift)
        scene = F.merge(g, "ConvergingAsh", scene, cplace, mode="Screen",
                        blend=f"min({PI}, 1)*{prog(S, 12)}*(1 - {solid})")
        gem = F.particles(g, "GlyphGrains", clear, number=120, lifespan=30, velocity=0.0, angle=0, angle_var=0,
                          size=0.15, color=(0.85, 0.82, 0.78), region="CubeRgn", region_size=(0.9, 0.14, 0.05),
                          center_y=0.0, turbulence=0.02, glow=0)
        gim = F.bitmap_mask(g, "GlyphGrainMatte", title)
        F.masked(gem, gim)
        gplace = F.title_placement(g, "GlyphGrainPlace", gem, center_extra_y=drift)
        scene = F.merge(g, "GrainsOnGlyphs", scene, gplace, mode="Screen", blend=f"{build}*(1 - {solid})")

        g.at(0, 8)
        puff = F.noise(g, "CompactionPuff", "#000000", "#4c4a46", detail=5, scale=6, seethe_rate=0.2, contrast=1.6)
        psh = F.ellipse(g, "CompactionPuffShape", (0.5, 0.5), 0.6, 0.12, 0.6)
        psh.expr("Width", f"0.6 + 0.4*{prog(I, 36)}", 0.6)
        psh.expr("Height", f"0.12 + 0.2*{prog(I, 36)}", 0.12)
        F.masked(puff, psh)
        scene = F.merge(g, "CompactionPuffMerge", scene, puff, mode="Screen", blend=f"0.6*{PI}*{decay(I, 14)}")
        rel = f"220*{PI}*{window(ES, f'{ES} + {ED}', 1, 1)}"
        scene = F.particles(g, "CrumbleAsh", scene, number=220, lifespan=50, velocity=0.004, angle=-90, angle_var=25,
                            size=0.2, color=(0.78, 0.74, 0.7), region="CubeRgn", region_size=(0.9, 0.12, 0.05),
                            center_y=0.0, turbulence=0.1, glow=0, number_expr=rel)
        g.at(0, 10)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.028, 1.7,
                                    color=(0.7, 0.66, 0.6), y_off=-0.12)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 14", f"{ES} - 5", 18, 10))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.06, shake_frames=6, shake_amp=0.002,
                             push_start="0", push_dur=str(g.frames))
        black = F.solid(g, "FadeBlack", (0, 0, 0))
        scene = F.merge(g, "FinalFade", scene, black, blend=f"0.9*{clamp01(f'({ex} - 0.8)/0.2')}")
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T09()
