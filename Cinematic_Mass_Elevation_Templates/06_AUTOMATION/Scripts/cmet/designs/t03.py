"""T03 - Molten Core."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, apply_shake, subtitle
from ..fusion import ctl, prog, e_out, decay, step, window, clamp01
from ..typo import Material, place_extruded

IRON = Material(base=(0.16, 0.15, 0.14), spec=(1.0, 0.72, 0.48), spec_power=30, spec_gain=0.45, diffuse=0.95,
                ambient=0.16, metal=0.4, env_sky=(0.2, 0.17, 0.15), env_horizon=(0.05, 0.035, 0.03),
                env_ground=(0.55, 0.2, 0.05), env_sharp=8, bevel=0.07, texture="concrete", tex_amount=0.35,
                bump=0.03, rim=(1.0, 0.45, 0.12), seed=33)


def heat_colour(acc, heat, cool):
    """Black-body-ish ramp: deep red when cool, accent when hot, near-white at the hottest."""
    c = np.array([acc[0], acc[1] * (0.35 + 0.65 * cool), acc[2] * (0.2 + 0.8 * cool)], np.float32)
    hot = np.clip(heat - 0.75, 0, None)[..., None] * np.array([1.0, 0.75, 0.45], np.float32) * 0.9
    return heat[..., None] * c * 1.6 + hot


def fissure_glow(H, W, pts, acc, lvl, k):
    """Thin white-hot crack line with a warm halo (halo built at quarter res for speed)."""
    core = np.zeros((H, W), np.float32)
    cv2.polylines(core, [(pts * 4).astype(np.int32).reshape(-1, 1, 2)], False, 1.0, max(1, int(2 * k)),
                  cv2.LINE_AA, shift=2)
    q = cv2.resize(core, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    halo = cv2.resize(cv2.GaussianBlur(q, (0, 0), 3 * k) * 3.0 + cv2.GaussianBlur(q, (0, 0), 14 * k) * 6.0,
                      (W, H), interpolation=cv2.INTER_LINEAR)
    hot = acc * 0.5 + np.array([0.5, 0.42, 0.3], np.float32)
    return (core[..., None] * hot + halo[..., None] * acc) * lvl


def comp_box(bg, layer):
    """Same as base.comp but only touches the layer's bounding box (much cheaper for a title-sized layer)."""
    rows = np.flatnonzero(layer.a.max(1) > 0)
    if len(rows) == 0:
        return bg
    cols = np.flatnonzero(layer.a[rows[0]:rows[-1] + 1].max(0) > 0)
    sl = (slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1))
    a = layer.a[sl][..., None]
    bg[sl] = bg[sl] * (1 - a) + layer.rgb[sl]
    return bg


class T03(Design):
    ID = "T03"
    NAME = "Molten Core"
    SLUG = "Molten_Core"
    CATEGORY = "A - Dark Mass Elevation"
    CONCEPT = "Volcanic energy: a dark-iron title is born out of a glowing fissure in cracked volcanic rock."
    ENTRANCE = "The title rises vertically out of a molten fissure in the ground (clipped at the crack line), red-hot at its base."
    REVEAL = "As it seats, a radial burst of embers and an illumination pulse light the rock; heat crawls along the letter edges."
    CAMERA = "Low-angle camera (keystoned ground plane) with a slow continuous push-in; tiny impact jolt."
    MATERIAL = "Dark forged iron with molten-orange edge emission, cooling colour ramp; cracked basalt ground with lava veins."
    EXIT = "The heat drains (orange -> deep red -> black), leaving a dark silhouette against the horizon glow, then fades."
    TECHNIQUES = ["perspective ground plane", "lava vein network", "fissure clip-reveal", "edge heat crawl",
                  "ember burst", "cooling colour ramp", "2.5D extrusion"]
    TRUE_3D = False
    DURATION_FRAMES = 216
    DEFAULTS = dict(MAIN_TITLE="MOLTEN CORE", SUBTITLE="FORGED IN THE DEEP", FONT_FAMILY="russo",
                    TEXT_COLOR="#5A5450", ACCENT_COLOR="#FF6A1A", ANIMATION_START=14, ANIMATION_DURATION=62,
                    IMPACT_FRAME=76, HOLD_DURATION=74, EXIT_START=150, EXIT_DURATION=60, LETTER_SPACING=0.05,
                    TITLE_WIDTH=0.7, TEXT_POSITION_Y=0.52)
    SOUND = [(0, "atmos", "Deep volcanic rumble bed"), (0, "fire", "Low lava crackle / hiss"),
             (14, "riser", "Grinding sub riser while the title rises (14-76)"),
             (70, "rwhoosh", "Reverse heat suck into the seat"), (76, "impact", "Heavy iron seat impact"),
             (76, "sub", "Sub-bass drop"), (77, "debris", "Ember / grit scatter"),
             (98, "shimmer", "Heat shimmer as the glow crawls the edges"), (150, "swell", "Cooling hiss swell"),
             (186, "tail", "Rumble tail")]

    # ------------------------------------------------------------ preview --
    def _ground(self, c, yh, push):
        """Perspective basalt ground below horizon yh (normalised). Returns (rock_rgb_mult, veins) half-res."""
        H, W = c.H, c.W
        h2, w2 = H // 2, W // 2
        key = ("ground", yh, h2)
        G = c.cache.get(key)
        if G is None:
            nx, ny = K.grid(h2, w2)
            d = np.maximum(ny - yh, 1e-3)
            zg = 0.075 / d                    # depth of each ground pixel
            gx = nx * zg
            near = np.clip((ny - yh) / 0.06, 0, 1) ** 1.5  # fade detail at the horizon (anti-alias)
            G = c.cache[key] = (zg.astype(np.float32), gx.astype(np.float32), near.astype(np.float32),
                                K.fft_noise(256, 1.5, 61), K.fft_noise(256, 2.1, 62, True),
                                K.fft_noise(256, 1.9, 63, True))
        zg, gx, near, rockT, crkT, crk2T = G
        gz = zg + push
        mx = (gx * 0.55 * 256).astype(np.float32)
        my = (gz * 0.55 * 256).astype(np.float32)
        rock = cv2.remap(rockT, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        cr = cv2.remap(crkT, mx * 0.6, my * 0.6, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        cr2 = cv2.remap(crk2T, mx * 1.7 + 40, my * 1.7, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        veins = np.clip((cr - 0.955) / 0.045, 0, 1) ** 1.5 + 0.45 * np.clip((cr2 - 0.965) / 0.035, 0, 1) ** 2
        veins = veins * near
        return rock * near, veins, zg

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        PI = p["PARTICLE_INTENSITY"]
        imp = c.impact
        ex = c.exit_u()
        cool_ex = K.smooth(ex / 0.65)                 # exit part 1: heat drains
        fade_ex = K.smooth((ex - 0.6) / 0.4)          # exit part 2: silhouette fades
        u = c.reveal_u()
        hit = c.hit(0.02, 0.4)
        after = 1.0 if t >= imp else 0.0
        hold_cool = 0.25 * K.smooth(K.prog(t, imp + 0.6, c.exit_start - imp))
        heat_lvl = (0.55 + 0.45 * K.smooth(u)) * (1 - hold_cool) * (1 - cool_ex)
        anticip = K.smooth(K.prog(t, 0, c.start + c.reveal * 0.4))

        sp = c.title()
        zoom = 1.0 + 0.08 * K.ease_in_out(K.prog(t, 0, c.dur))
        cam = c.cam(zoom=zoom, tilt=4.0)
        hx, hy = c.hero()
        tcx, tcy = hx / (H / 2), hy / (H / 2)
        half_h = 0.5 * sp.ink_h * zoom / (H / 2)
        fy = tcy + half_h + 0.012          # fissure line (normalised, y down)
        yh = fy - 0.035                     # horizon just above the fissure (low camera)

        # --- sky / heat haze + ground, all soft -> computed at half resolution
        h2, w2 = H // 2, W // 2
        nx, ny = K.grid(h2, w2)
        bg = K.vgrad(h2, w2, (0.004, 0.003, 0.003), (0.03, 0.012, 0.006))
        glow_lvl = (0.35 + 0.4 * anticip + 0.5 * after * (1 - hold_cool)) * (1 - 0.55 * cool_ex)
        band = np.exp(-((ny - yh) / 0.10) ** 2) * np.exp(-((nx - tcx) / 1.6) ** 2)
        back = glow_lvl + 0.45 * K.smooth(ex / 0.4) * (1 - fade_ex)   # afterglow keeps the silhouette readable
        bg += (band * 0.22 * back)[..., None] * acc * bgI
        sm = E.smoke(h2, w2, t, (0.05, 0.03, 0.022), density=0.5, scale=1.3, rise=0.02, seed=9,
                     light=(tcx, yh, 0.9, acc * 1.4))
        sky = np.clip((yh + 0.02 - ny) / 0.08, 0, 1)[..., None]
        bg += sm * sky * bgI
        push = 0.25 * K.ease_in_out(K.prog(t, 0, c.dur))
        rock, veins, zg = self._ground(c, yh, push)
        gm = np.clip((ny - yh) / 0.006, 0, 1)
        lightpool = K.soft_spot(h2, w2, tcx, fy, 1.1, 0.22, 1.5) * (0.35 + 0.65 * glow_lvl + 1.6 * hit)
        rock_rgb = (0.022 + 0.07 * rock)[..., None] * np.array([1.0, 0.92, 0.86], np.float32)
        rock_rgb = rock_rgb * (0.6 + 1.6 * lightpool[..., None] * (0.5 + acc * 0.5))
        vein_lvl = (0.35 + 0.35 * anticip + 0.6 * after * (1 - hold_cool) + 1.2 * hit) * (1 - 0.75 * cool_ex)
        pulse = 0.85 + 0.15 * np.sin(t * 2.1 + nx * 3.0)
        vein_rgb = (veins * pulse * vein_lvl * (0.35 + 0.9 * lightpool))[..., None] * acc * 1.3
        ground = (rock_rgb + vein_rgb) * bgI
        bg = bg * (1 - gm[..., None]) + ground * gm[..., None]
        bg = cv2.resize(bg, (W, H), interpolation=cv2.INTER_LINEAR)

        # --- embers rising from the cracks
        if PI > 0:
            P = c.cache.get("embers")
            if P is None:
                P = c.cache["embers"] = E.Particles(int(220 * PI), seed=31, z=(0.4, 2.6))
            x, y = P.drift(t, vel=(0.012, -0.07), turb=0.05, freq=0.7)
            bg += E.particle_layer(H, W, P, x, y, acc * 1.2 + np.array([0.15, 0.04, 0.0]), 1.3,
                                   0.55 * (0.5 + 0.5 * glow_lvl) * (1 - 0.6 * cool_ex), zoom=zoom, focus=1.0,
                                   dof=1.0, flicker=0.6, t=t, glow=1.0)

        # --- title (rises out of the fissure)
        sh = c.shaded(IRON)
        ue = K.ease_out(u, 3)
        rise = (1 - ue) * sp.ink_h * 1.15
        # heat map on the letters: base heat (strong at the bottom), travelling edge band, impact edge pulse
        vb = np.clip(sh.v + 0.5, 0, 1.2)
        bottom = np.exp(-(1.0 - vb) * 3.2) * (0.35 + 0.65 * sh.edge)
        bottom = bottom * (0.5 + 1.2 * (1 - ue))
        band_pos = -0.75 + 1.5 * K.ease_in_out(K.prog(t, c.start + 0.3, imp - c.start - 0.1))
        band2 = -0.75 + 1.5 * K.ease_in_out(K.prog(t, imp + 0.9, 1.8))
        travel = (np.exp(-((sh.u - band_pos) / 0.12) ** 2) * (1 - after * K.prog(t, imp, 0.3))
                  + np.exp(-((sh.u - band2) / 0.12) ** 2) * (0 < K.prog(t, imp + 0.9, 1.8) < 1))
        heat = (bottom * 0.9 + travel * sh.edge * 1.3 + sh.edge * (0.25 * after + 0.8 * hit)) * heat_lvl
        heat = heat * p["GLOW_STRENGTH"]
        emis = heat_colour(acc, heat, 1 - cool_ex * 0.8)
        lg = (0.75 + 0.35 * glow_lvl + 0.45 * hit) * (1 - 0.85 * cool_ex)
        rgb, a = sh.shade(light=(-0.2, 0.55, 0.8), rim_dir=(0.0, 1.0), rim_gain=(0.5 + 0.8 * hit) * heat_lvl,
                          base=K.col(p["TEXT_COLOR"]), light_gain=lg, emissive=emis)
        L = c.layer()
        op = K.smooth(u * 5) * (1 - fade_ex)
        depth = 0.12 * sp.cap_px * p["EXTRUSION_DEPTH"]
        side = (0.05, 0.022, 0.012)
        if depth > 0.5:
            place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, (hx, hy + rise, 0), 1.0,
                           (0, 0, p["TEXT_ROTATION"]), depth, side, slices=6,
                           side_light=lambda q: 0.5 + 0.9 * q * (1 - cool_ex), opacity=op)
        else:
            c.place(L, cam, rgb, a, sp, 1.0, off=(0, rise, 0), opacity=op)
        # clip everything below the fissure (the part still inside the ground)
        fy_px = H / 2 + fy * H / 2
        rows = np.clip((fy_px - np.arange(H, dtype=np.float32)) / (3 * k), 0, 1)
        L.a *= rows[:, None]
        L.rgb *= rows[:, None, None]
        img = comp_box(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.45, 0), 9 * k) * 0.6 * p["GLOW_STRENGTH"] * (0.4 + hit)

        # --- the fissure itself (in front of the title base)
        fis = c.cache.get("fissure")
        if fis is None:
            r = np.random.default_rng(7)
            xs = np.linspace(-1.0, 1.0, 46)
            ys = np.cumsum(r.normal(0, 0.0025, 46))
            ys -= np.linspace(ys[0], ys[-1], 46)
            fis = c.cache["fissure"] = (xs, ys)
        xs, ys = fis
        span = 0.5 * sp.ink_w * zoom / (H / 2) * 1.35
        open_ = K.smooth(K.prog(t, 0.1, c.start + 0.3))
        pts = np.stack([W / 2 + (tcx + xs * span * (0.3 + 0.7 * open_)) * H / 2,
                        fy_px + ys * H / 2], 1)
        fis_lvl = (0.25 + 0.7 * anticip * (1 - after) + 0.55 * after * (1 - hold_cool) + 1.5 * hit) * (1 - cool_ex)
        if fis_lvl > 0.01:
            img = img + fissure_glow(H, W, pts, acc, fis_lvl * bgI, k)

        # --- impact: radial ember burst + illumination pulse
        if t >= imp and PI > 0:
            dt = t - imp
            B = c.cache.get("burst")
            if B is None:
                r = np.random.default_rng(12)
                n = int(150 * PI)
                ang = r.uniform(-math.pi, 0, n)            # upward hemisphere
                spd = r.uniform(0.3, 1.5, n) ** 1.4
                ox = r.uniform(-0.5, 0.5, n) * sp.ink_w / (H / 2)
                B = c.cache["burst"] = (n, ang, spd, ox, r.random(n))
            n, ang, spd, ox, rr = B
            dist = spd * (1 - np.exp(-dt * 2.5)) / 2.5
            gx = tcx + ox + np.cos(ang) * dist * 1.2
            gy = fy + np.sin(ang) * dist * 0.8 + 0.35 * dt * dt
            fade = np.exp(-dt / (0.35 + 0.6 * rr)) * (1 - ex)
            Pb = E.Particles(n, 1)
            Pb.z = (0.7 + 0.5 * rr).astype(np.float32)
            ramp = min(1.0, dt * 8) * np.exp(-dt * 2.5)
            vx = np.cos(ang) * spd * 0.02 * ramp
            vy = np.sin(ang) * spd * 0.014 * ramp + 0.006 * dt
            img += E.particle_layer(H, W, Pb, gx, gy, acc * 1.3 + np.array([0.3, 0.12, 0.0]), 1.0, 1.2 * fade,
                                    zoom=1.0, glow=1.3, streak=(vx, vy))
        if hit > 0.01:
            fl = cv2.resize(K.soft_spot(H // 4, W // 4, tcx, fy - 0.1, 1.5, 0.6, 1.5), (W, H))
            img += (fl * 0.18 * hit * bgI)[..., None] * acc

        img = subtitle(c, img, cam, imp + 0.5, c.exit_start - 0.1, (0.62, 0.5, 0.42), y_rel=1.02)
        img = apply_shake(c, img, 0.004, 0.3, 14)
        img = img * (1 - 0.85 * K.smooth((ex - 0.75) / 0.25))
        return c.finish(img, vignette=0.55, grain=0.035, bloom=(0.75, 0.5))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        BG = ctl("BackgroundIntensity")
        GL = ctl("GlowStrength")
        cool = clamp01(f"{ex}/0.65")
        fade = clamp01(f"({ex} - 0.6)/0.4")
        ES = ctl("ExitStart")
        hold_cool = f"0.25*{prog(f'{I} + 14', f'{ES} - {I}')}"
        HX = f"(0.55 + 0.45*{u})*(1 - {hold_cool})*(1 - {cool})"
        anticip = prog(0, f"{ctl('AnimStart')} + 0.4*{ctl('AnimDuration')}")
        glow = f"(0.35 + 0.4*{anticip} + 0.5*{step(I)}*(1 - {hold_cool}))*(1 - 0.55*{cool})"
        fis_y = f"{ctl('TextPosY')} - 0.085*{ctl('TextScale')}"

        # environment ----------------------------------------------------
        g.at(0, 0)
        bg = F.gradient_bg(g, "VolcanicSky", [(0, "#010101", 1), (0.5, "#080403", 1), (0.6, "#1c0b04", 1),
                                              (1, "#040202", 1)])
        smoke = F.noise(g, "SmokeRise", "#000000", "#2a160c", detail=6, scale=2.4, seethe_rate=0.04, contrast=1.6,
                        center="Point(0.5 + time*0.0003, 0.5 + time*0.0012)")
        bg = F.merge(g, "SmokeMerge", bg, smoke, mode="Screen", blend=f"0.5*{BG}")
        bg = F.light_spot(g, "HorizonHeat", bg, None, (0.5, 0.40), 2.4, 0.16, 0.25, accent=True, gain=0.5,
                          blend=f"min({BG}*{glow}, 1)")
        g.at(0, 2)
        rock = F.noise(g, "BasaltRock", "#030302", "#1a1612", detail=8, scale=7, seethe_rate=0.0, contrast=1.3)
        rock.expr("Center", f"Point(0.5, 0.5 - time*0.0008)", [0.5, 0.5])
        gmask = F.rect(g, "GroundMask", (0.5, 0.18), 1.4, 0.44, 0.03)
        gmask.expr("Center", f"Point(0.5, ({fis_y} + 0.02)/2)", [0.5, 0.2])
        gmask.expr("Height", f"{fis_y} + 0.02", 0.4)
        F.masked(rock, gmask)
        bg = F.merge(g, "GroundMerge", bg, rock, blend=BG)
        vein_n = F.noise(g, "LavaVeinNoise", "#000000", "#ffffff", detail=4, scale=9, seethe_rate=0.01, contrast=3.0)
        vein_n.expr("Center", "Point(0.5, 0.5 - time*0.0008)", [0.5, 0.5])
        vm = F.bitmap_mask(g, "LavaVeinMatte", vein_n, channel="Luminance")
        vm.set(Low=0.72, High=0.78)
        vein_c = F.accent_solid(g, "LavaVeinColor", 1.3)
        F.masked(vein_c, vm)
        vlim = F.rect(g, "LavaVeinLimit", (0.5, 0.18), 1.4, 0.44, 0.03)
        vlim.expr("Center", f"Point(0.5, ({fis_y} + 0.02)/2)", [0.5, 0.2])
        vlim.expr("Height", f"{fis_y} + 0.02", 0.4)
        vein_m = F.merge(g, "LavaVeinsHolder", F.solid(g, "VeinClear", (0, 0, 0), alpha=0.0), vein_c)
        F.masked(vein_m, vlim)
        bg = F.merge(g, "LavaVeins", bg, vein_m, mode="Screen",
                     blend=f"min({BG}*(0.35 + 0.35*{anticip} + 0.6*{step(I)}*(1 - {hold_cool}) + 1.2*{decay(I, 10)})"
                           f"*(1 - 0.75*{cool}), 1)")
        bg = F.light_spot(g, "FissureLightPool", bg, None, (0.5, 0.36), 1.2, 0.18, 0.4, accent=True, gain=0.8,
                          blend=f"min({BG}*(0.3*{glow} + 1.2*{decay(I, 12)}), 1)")
        bg = F.particles(g, "Embers", bg, number=26, lifespan=110, velocity=0.006, angle=90, angle_var=25, size=0.3,
                         color=(1.0, 0.45, 0.12), region="CubeRgn", region_size=(2.4, 0.3, 1.0), center_y=-0.25,
                         turbulence=0.25, glow=4)
        bg = F.xf(g, "EnvLowAngle", bg, center=f"Point(0.5, 0.5 + 0.012*{prog(0, g.frames)})",
                  size=f"1 + 0.03*{prog(0, g.frames)}", edges=1)

        # title -----------------------------------------------------------
        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Russo One", "Regular", 0.12, 1.05,
                             color=p["TEXT_COLOR"])
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        iron = F.fill_material(g, "ForgedIron", title,
                               [(0, "#9a948e", 1), (0.45, "#6a6560", 1), (0.55, "#3a3633", 1), (1, "#55504b", 1)])
        face = F.merge(g, "IronFace", title, iron, mode="Multiply", blend=1.0)
        g.at(0, 6)
        hb = F.rect(g, "HeatBaseShape", (0.5, 0.40), 2.0, 0.10, 0.09)
        hbm = F.bitmap_mask(g, "HeatBaseMatte", title, paint="Multiply", prev=hb)
        heat_base = F.accent_solid(g, "HeatBaseColor", 1.5)
        F.masked(heat_base, hbm)
        heat = F.merge(g, "HeatHolder", clear, heat_base,
                       blend=f"min(1.4*(1.0 - 0.6*{e_out(u, 3)})*{HX}*{GL}, 1)")
        edge = F.edge_light(g, "HotEdge", title, 0.0, 0.0035, accent=True, gain=1.8, blur_px=1.4)
        heat = F.merge(g, "HotEdgeMerge", heat, edge, mode="Screen",
                       blend=f"min({GL}*{HX}*(0.45 + 0.4*{step(I)} + 1.6*{decay(I, 10)}), 1)")
        heat = F.light_sweep(g, "HeatCrawlRise", heat, title, f"{ctl('AnimStart')} + 8",
                             f"{I} - {ctl('AnimStart')} - 6", angle=75, width=0.07, peak=1.0, accent=True)
        heat = F.light_sweep(g, "HeatCrawlHold", heat, title, f"{I} + 22", 44, angle=75, width=0.07,
                             peak=0.8, accent=True)
        heat = F.cc(g, "CoolingRamp", heat, gain=f"1 - 0.9*{cool}")
        heat.expr("MasterGreenGain", f"0.35 + 0.65*(1 - {cool})", 1)
        heat.expr("MasterBlueGain", f"0.2 + 0.8*(1 - {cool})", 1)
        g.at(0, 8)
        ext = F.extrusion_stack(g, "Extrude", clear, title, layers=6, dx=0.0, dy=-0.0011,
                                color=(0.05, 0.022, 0.012))
        solid_title = F.merge(g, "TitleSolid", ext, face)
        lit = F.cc(g, "UnderLight", solid_title,
                   gain=f"(0.5 + 0.4*{glow} + 1.0*{decay(I, 8)})*(1 - 0.6*{cool})")
        hot = F.merge(g, "HeatOnIron", lit, heat, mode="Screen", blend=1.0)
        g.at(0, 10)
        placed = F.title_placement(g, "TitleRise", hot,
                                   center_extra_y=f"-0.17*{ctl('TextScale')}*(1 - {e_out(u, 3)})")
        clip_shape = F.rect(g, "FissureClipShape", (0.5, 0.9), 2.0, 1.0, 0.002)
        clip_shape.expr("Center", f"Point(0.5, {fis_y} + 0.5)", [0.5, 0.9])
        clipped = F.merge(g, "FissureClip", F.solid(g, "ClipHolder", (0, 0, 0), alpha=0.0), placed)
        F.masked(clipped, clip_shape)
        tglow = F.softglow(g, "HeatGlow", clipped, 10,
                           gain=f"{GL}*(0.5 + 1.2*{decay(I, 10)})*(1 - {cool})", threshold=0.35)
        scene = F.merge(g, "TitleOverRock", bg, tglow, blend=f"min({u}*5, 1)*(1 - {fade})")

        # fissure + impact ----------------------------------------------------
        g.at(0, 12)
        fpts = [(0.12 + 0.76 * i / 14, 0.5 + 0.004 * math.sin(i * 2.3) + 0.003 * math.cos(i * 5.1))
                for i in range(15)]
        fm = F.polyline_mask(g, "FissureShape", fpts, border=0.0025, soft=0.0015)
        fm.expr("Center", f"Point({ctl('TextPosX')}, {fis_y})", [0.5, 0.415])
        fc = F.accent_solid(g, "FissureCore", 2.0)
        F.masked(fc, fm)
        fglow = F.softglow(g, "FissureGlow", fc, 18, gain=f"1.5*{GL}", threshold=0.05)
        scene = F.merge(g, "Fissure", scene, fglow, mode="Screen",
                        blend=(f"min({BG}*(0.25 + 0.7*{anticip}*(1 - {step(I)}) + 0.55*{step(I)}*(1 - {hold_cool})"
                               f" + 1.5*{decay(I, 8)})*(1 - {cool}), 1)"))
        burst_n = f"200*{ctl('ParticleIntensity')}*{window(I, I + ' + 2', 1, 1)}"
        scene = F.particles(g, "EmberBurst", scene, number=200, lifespan=36, velocity=0.035, angle=90,
                            angle_var=75, size=0.45, color=(1.0, 0.55, 0.2), region="CubeRgn",
                            region_size=(0.8, 0.02, 0.2), center_y=-0.08, turbulence=0.3, glow=6,
                            number_expr=burst_n)
        scene = F.impact_flash(g, "IlluminationPulse", scene, color=p["ACCENT_COLOR"], peak=0.14, frames=7)

        g.at(0, 14)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 1.5,
                                    color=(0.62, 0.5, 0.42), y_off=-0.16)
        scene = F.merge(g, "SubtitleMerge", scene, subp,
                        blend=window(f"{I} + 12", f"{ctl('ExitStart')} - 2", 18, 14))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.08, shake_frames=7, shake_amp=0.004)
        black = F.solid(g, "FadeBlack", (0, 0, 0))
        scene = F.merge(g, "FinalFade", scene, black, blend=f"0.85*{clamp01(f'({ex} - 0.75)/0.25')}")
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T03()
