"""T07 - Explosive Arrival."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, apply_shake, subtitle
from ..fusion import FuID, ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material, place_extruded, place_sprite

BLASTPLATE = Material(base=(0.72, 0.69, 0.64), spec=(1.0, 0.85, 0.65), spec_power=22, spec_gain=0.3, diffuse=0.85,
                      ambient=0.12, metal=0.15, env_sky=(0.3, 0.27, 0.24), env_horizon=(0.05, 0.04, 0.03),
                      env_ground=(0.9, 0.45, 0.15), env_sharp=6, bevel=0.06, bevel_round=False, texture="concrete",
                      tex_amount=0.35, bump=0.03, rim=(1.0, 0.62, 0.25), seed=77)


def blast_colour(acc, temp):
    deep = np.array([0.4, 0.06, 0.01], np.float32)
    white = np.array([1.0, 0.92, 0.75], np.float32)
    t = temp[..., None]
    return deep * np.clip(t * 2.5, 0, 1) + acc * np.clip(t * 1.5 - 0.15, 0, 1.3) + white * np.clip(t - 0.6, 0, 1) * 2.2


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


class T07(Design):
    ID = "T07"
    NAME = "Explosive Arrival"
    SLUG = "Explosive_Arrival"
    CATEGORY = "B - Fire, Explosions and Impact"
    CONCEPT = "A procedural detonation behind the title throws it into frame: fireball, smoke, shockwave and debris."
    ENTRANCE = ("A short charged beat (ignition point flickering in the dark), then the blast hurls the title forward "
                "out of the fireball core with zoom blur.")
    REVEAL = ("Expanding fireball cooling into billowing lit smoke, a fast shockwave ring with refraction, ballistic "
              "debris and embers - all behind/around the title, never permanently over it.")
    CAMERA = "Locked-off, heavy concussive shake on detonation, then a very slow settle-in push."
    MATERIAL = "Pale blast-worn concrete/steel plate, flat chamfer, fire rim light from behind, hard drop shadow on the smoke."
    EXIT = "The title rushes past camera (fly-through with zoom blur) as the smoke closes in."
    TECHNIQUES = ["procedural fireball (noise + radial density + temperature ramp)", "lit smoke billow",
                  "shockwave ring + displacement", "ballistic debris (dark chunks + burning streaks)",
                  "zoom-blur arrival", "fly-through exit"]
    TRUE_3D = False
    DURATION_FRAMES = 144
    DEFAULTS = dict(MAIN_TITLE="DETONATION", SUBTITLE="NO WARNING", FONT_FAMILY="anton",
                    TEXT_COLOR="#D2CABF", ACCENT_COLOR="#FF8A2E", ANIMATION_START=4, ANIMATION_DURATION=20,
                    IMPACT_FRAME=24, HOLD_DURATION=70, EXIT_START=114, EXIT_DURATION=22, LETTER_SPACING=0.05,
                    TITLE_WIDTH=0.62)
    SOUND = [(0, "atmos", "Tense low room tone"), (4, "heartbeat", "Single heavy pulse"),
             (8, "riser", "Short charge riser (8-24)"), (22, "rwhoosh", "Reverse suck into the blast"),
             (24, "impact", "Detonation boom"), (24, "sub", "Sub-bass drop"), (25, "debris", "Debris + glass scatter"),
             (26, "fire", "Fireball roar / burning tail"), (60, "crackle", "Embers crackle"),
             (110, "whoosh", "Fly-through whoosh"), (120, "tail", "Explosion reverb tail")]
    FUSION_NOTES = [
        "Debris on/off: set Particle Intensity to 0 to disable all debris and embers (DebrisEmitter/EmberEmitter "
        "Number = count x ParticleIntensity); values between 0 and 2 scale the amount.",
        "Explosion strength: Impact Intensity scales fireball size and brightness, the flash, both shockwave rings and "
        "the shockwave refraction (0 = title arrives without the blast).",
        "The fireball is FastNoise inside an expanding soft EllipseMask; to re-centre the blast move FireballShape, "
        "FireCoreShape, SmokeShape, ShockRingA/B Shape centres together.",
    ]

    # ------------------------------------------------------------ preview --
    def _blast(self, c, dt, cx, cy, II):
        """Fireball + smoke at quarter res. Returns (emission rgb, smoke alpha) quarter-res."""
        H, W, t = c.H, c.W, c.t
        h4, w4 = H // 4, W // 4
        nx, ny = K.grid(h4, w4)
        size = 0.55 + 0.45 * min(II, 2.0)
        R = size * 1.05 * (1 - math.exp(-dt * 4.0)) + size * 0.06 * dt
        Rs = R * 1.15 + 0.12 * dt
        a = K.fft_noise(256, 2.2, 71)
        b = K.fft_noise(256, 1.8, 72)
        sc = 1.6 / (0.35 + R)
        n = 0.65 * K.sample(a, h4, w4, sc, 0.0, -0.03 * dt) + 0.35 * K.sample(b, h4, w4, sc * 2.3, 0.1, -0.08 * dt)
        d = np.sqrt(((nx - cx) / 1.25) ** 2 + (ny - cy) ** 2)
        body = np.clip(1.0 - d / (R * (0.62 + 0.75 * n) + 1e-3), 0, 1)
        sbody = np.clip(1.0 - d / (Rs * (0.65 + 0.8 * n) + 1e-3), 0, 1)
        hot = math.exp(-dt / 0.45)
        warm = math.exp(-dt / 0.8)
        temp = body ** 0.8 * (0.12 + 0.2 * warm + 1.3 * hot) * (0.6 + 0.6 * n) + body * 0.3 * warm
        temp = temp * (0.5 + 0.5 * np.clip(1 - d / (R + 1e-3), 0, 1)) * min(1.0, 0.4 + 0.6 * II)
        smoke_a = np.clip(sbody * 1.6, 0, 1) * np.clip(dt / 0.5, 0, 1) * (1 - 0.6 * hot)
        smoke_a = smoke_a * (0.55 + 0.45 * n)
        return temp, smoke_a, R, n

    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        PI = p["PARTICLE_INTENSITY"]
        II = p["IMPACT_INTENSITY"]
        GL = p["GLOW_STRENGTH"]
        imp = c.impact
        ex = c.exit_u()
        dt = t - imp
        after = dt >= 0
        hit = c.hit(0.01, 0.12)
        sp = c.title()
        hx, hy = c.hero()
        cx, cy = hx / (H / 2), hy / (H / 2) + 0.04

        # --- base: darkness + ignition beat
        h4, w4 = H // 4, W // 4
        bg4 = K.vgrad(h4, w4, (0.006, 0.006, 0.007), (0.012, 0.009, 0.007))
        charge = K.smooth(K.prog(t, c.start, imp - c.start)) * (0 if after else 1)
        if charge > 0:
            fl = 0.6 + 0.4 * math.sin(t * 61) * math.sin(t * 23)
            bg4 += (K.soft_spot(h4, w4, cx, cy, 0.05 + 0.08 * charge, None, 1.5) * charge * fl * 1.5)[..., None] * acc
            bg4 += (K.soft_spot(h4, w4, cx, cy, 0.8, 0.5, 1.2) * charge * 0.05)[..., None] * acc
        smoke_rgb = None
        if after:
            temp, sa, R, n = self._blast(c, dt, cx, cy, II)
            # smoke lit from inside by the remaining fire
            inner = K.blur(temp, 6) * 2.0
            smoke_col = np.array([0.045, 0.04, 0.036], np.float32) * (1 + 0.5 * n[..., None])
            smoke_rgb = smoke_col + inner[..., None] * acc * 0.22
            bg4 = bg4 * (1 - sa[..., None] * 0.9) + smoke_rgb * sa[..., None] * bgI
            bg4 = bg4 + blast_colour(acc, temp) * bgI * 1.3
            # ground-light / air glow
            bg4 += (K.soft_spot(h4, w4, cx, cy, 1.6, 1.0, 1.2) * (0.06 + 0.3 * hit) * min(II, 1.5))[..., None] * acc
        bg = cv2.resize(bg4, (W, H), interpolation=cv2.INTER_LINEAR)

        # shockwave: ring + refraction (independent of the title)
        if after and dt < 0.9 and II > 0:
            h2, w2 = H // 2, W // 2
            rr_ = 0.08 + 2.4 * K.ease_out(dt / 0.9, 2)
            fade = (1 - dt / 0.9) ** 1.5 * min(II, 1.5)
            ring = E.ring(h2, w2, cx, cy, rr_, 0.012 + 0.02 * dt, 1.25)
            ring2 = E.ring(h2, w2, cx, cy, rr_ * 0.82, 0.05, 1.25)
            bg += cv2.resize(ring * 0.5 + ring2 * 0.12, (W, H))[..., None] * fade * (acc * 0.6 + 0.4) * bgI
            bg = E.shockwave_displace(bg, cx, cy, rr_, 0.06, 0.02 * fade)

        # --- title: blasted forward out of the core, then fly-through exit
        sh = c.shaded(BLASTPLATE)
        ua = K.prog(t, imp, 0.32)
        ea = K.expo_out(ua)
        settle = 0.03 * H * math.sin(min(dt, 1.0) * 14) * math.exp(-max(dt, 0) * 7) if after else 0
        z = 4.0 * H * (1 - ea) + settle
        exe = K.ease_in(ex, 2.4)
        z -= exe * 4.2 * H
        fire_l = (0.0 if not after else (0.25 + 1.5 * math.exp(-dt / 0.6)) * min(II, 1.5))
        rgb, a = sh.shade(light=(-0.45, -0.5, 0.75), rim_dir=(0.0, -1.0), rim_gain=(0.35 + fire_l) * GL,
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.55 + 0.35 * min(fire_l, 1.0),
                          env_shift=-0.1)
        L = c.layer()
        op = (1.0 if after else 0.0) * (1 - K.smooth((ex - 0.5) / 0.5))
        sx, sy = c.shake(0.014, 0.45, 19)
        cam = c.cam(zoom=1.0 + 0.04 * K.ease_in_out(K.prog(t, imp, c.dur - imp)))
        if op > 0:
            depth = 0.14 * sp.cap_px * p["EXTRUSION_DEPTH"]
            if depth > 0.5:
                place_extruded(L, cam, rgb, a, (0, 0, sp.w, sp.h), sp.anchor, (hx, hy, z), 1.0,
                               (0, 0, p["TEXT_ROTATION"]), depth, (0.05, 0.035, 0.025), slices=6,
                               side_light=lambda q: 0.4 + 0.8 * q, opacity=op)
            else:
                c.place(L, cam, rgb, a, sp, 1.0, off=(0, 0, z), opacity=op)
            zb = (0.35 * (1 - ea) * (ua < 1) + 0.25 * K.smooth(ex) * (ex < 1)) * p["MOTION_BLUR_AMOUNT"]
            if zb > 0.005:
                ccx, ccy = W / 2 + hx, H / 2 + hy
                z4 = K.zoom_blur(np.dstack([L.rgb, L.a]), ccx, ccy, zb)
                L.rgb, L.a = np.ascontiguousarray(z4[..., :3]), np.ascontiguousarray(z4[..., 3])
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.8, (10, 22), 22, k)
        img = comp_box(bg, L)
        img = img + K.blur(np.maximum(L.rgb - 0.6, 0), 8 * k) * 0.5 * GL

        # --- debris: dark chunks (subtractive) + burning streaks (additive); PARTICLE_INTENSITY 0 disables
        if after and PI > 0 and dt < 3.5:
            D = c.cache.get("debris")
            if D is None:
                r = np.random.default_rng(5)
                n = int(160 * PI)
                ang = r.uniform(0, 2 * np.pi, n)
                spd = r.uniform(0.4, 2.2, n) ** 1.3
                D = c.cache["debris"] = (n, ang, spd, r.random(n), r.uniform(0.4, 1.6, n))
            n, ang, spd, rr, zz = D
            s = spd * (1 - np.exp(-dt * 1.8)) / 1.8
            gx = cx + np.cos(ang) * s * 1.3
            gy = cy + np.sin(ang) * s * 0.9 + 0.45 * dt * dt
            vx = np.cos(ang) * spd * 0.03 * np.exp(-dt * 1.8)
            vy = np.sin(ang) * spd * 0.02 * np.exp(-dt * 1.8) + 0.01 * dt
            Pd = E.Particles(n, 1)
            Pd.z = zz.astype(np.float32)
            burning = rr < 0.45
            fade = np.exp(-dt / (0.6 + rr))
            hotb = E.particle_layer(H, W, Pd, gx, gy, acc * 1.3 + np.array([0.3, 0.15, 0.0]), 1.4,
                                    1.4 * fade * burning, glow=1.0, streak=(vx, vy))
            dark = E.particle_layer(H, W, Pd, gx, gy, (1, 1, 1), 2.6, 1.0 * (~burning) * np.clip(2.5 - dt, 0, 1),
                                    glow=0.0, streak=(vx * 0.6, vy * 0.6))
            img = img * (1 - np.clip(dark[..., :1] * 0.85, 0, 0.9)) + hotb
        # embers drifting in the hot air afterwards
        if after and PI > 0:
            P = c.cache.get("embers")
            if P is None:
                P = c.cache["embers"] = E.Particles(int(110 * PI), seed=12, z=(0.5, 2.5))
            x, y = P.drift(t, vel=(0.02, -0.08), turb=0.06, freq=0.9)
            img += E.particle_layer(H, W, P, x, y, acc * 1.2, 1.0, 0.5 * min(1.0, dt * 2) * (1 - ex), dof=1.0,
                                    flicker=0.6, t=t, glow=0.8)
        # flash
        img = img + (0.18 * hit * bgI) * (acc * 0.5 + 0.5)[None, None, :]
        # smoke closing in for the exit
        if ex > 0:
            fs = K.fbm_field(H // 4, W // 4, t, 1.2, (0.03, -0.01), 88, beta=2.4, warp=0.1)
            fs = cv2.resize(np.clip((fs - 0.4) * 2.0, 0, 1) * K.smooth(ex) * 0.8, (W, H))
            img = img * (1 - fs[..., None]) + fs[..., None] * np.array([0.05, 0.045, 0.04], np.float32)

        img = subtitle(c, img, cam, imp + 0.9, c.exit_start - 0.2, (0.85, 0.72, 0.6), y_rel=0.95, tracking=0.6)
        if abs(sx) + abs(sy) > 0.05:
            M = np.float32([[1.02, 0, -0.01 * W + sx], [0, 1.02, -0.01 * H + sy]])
            img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        return c.finish(img, vignette=0.5, grain=0.04, bloom=(0.75, 0.55), streak=(1.1, 0.25, 180, acc))

    # ------------------------------------------------------------- Fusion --
    def _debris(self, g, name, bg, number, lifespan, velocity, size, color, glow, gravity, count_expr):
        r, gg, b = F.rgb3(color)
        em = g.add("pEmitter", f"{name}Emitter")
        em.expr("Number", count_expr, number)
        em.set(Lifespan=lifespan, LifespanVariance=lifespan * 0.4, Velocity=velocity, VelocityVariance=velocity * 0.7,
               Angle=90, AngleVariance=180, Region=FuID("SphereRgn"))
        em.setk("SphereRgn.Radius", 0.04)
        em.setk("ParticleStyle.ColorControls", 1)
        em.setk("ParticleStyle.Red", r)
        em.setk("ParticleStyle.Green", gg)
        em.setk("ParticleStyle.Blue", b)
        em.setk("ParticleStyle.Size", size)
        em.setk("ParticleStyle.SizeVariance", size * 0.7)
        fo = g.add("pDirectionalForce", f"{name}Gravity")
        fo.conn("Input", em)
        fo.set(Strength=gravity, Direction=-90)
        rd = g.add("pRender", f"{name}Render")
        rd.conn("Input", fo)
        F.frame_inputs(rd, g)
        out = rd
        if glow:
            out = F.softglow(g, f"{name}Glow", rd, glow, gain=f"1.2*{ctl('GlowStrength')}", threshold=0.1)
        return F.merge(g, name, bg, out, mode="Screen" if glow else "Normal",
                       blend=f"min({ctl('ParticleIntensity')}, 1)")

    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        S = ctl("AnimStart")
        ES = ctl("ExitStart")
        BG = ctl("BackgroundIntensity")
        GL = ctl("GlowStrength")
        II = ctl("ImpactIntensity")
        PI = ctl("ParticleIntensity")
        ex = prog(ES, ctl("ExitDuration"))
        grow = e_out(prog(I, 18), 3)
        cool = f"(1 - {prog(I, 36)})"
        charge = f"{prog(S, f'{I} - {S}')}*(1 - {step(I)})"

        # darkness + ignition point ------------------------------------------------
        g.at(0, 0)
        bg = F.gradient_bg(g, "Night", [(0, "#010101", 1), (1, "#040302", 1)])
        bg = F.light_spot(g, "Ignition", bg, None, (0.5, 0.46), 0.04, 0.07, 0.6, accent=True, gain=2.0,
                          blend=f"min({charge}*(0.6 + 0.4*sin(time*2.5)*sin(time*0.97)), 1)")
        # smoke billow (darkens, lit from inside) ----------------------------------
        g.at(0, 2)
        smoke = F.noise(g, "SmokeBillow", "#020202", "#2a241f", detail=6, scale=3.0, seethe_rate=0.08, contrast=1.6,
                        center="Point(0.5, 0.5 + time*0.0012)")
        ssh = F.ellipse(g, "SmokeShape", (0.5, 0.46), 0.1, 0.1, 0.5)
        ssh.expr("Width", f"(0.1 + 1.6*{II}*{e_out(prog(I, 40), 2)} + 0.004*max(time - {I}, 0))", 0.1)
        ssh.expr("Height", f"(0.1 + 1.6*{II}*{e_out(prog(I, 40), 2)} + 0.004*max(time - {I}, 0))*1.5", 0.15)
        F.masked(smoke, ssh)
        bg = F.merge(g, "SmokeMerge", bg, smoke, blend=f"min(0.85*{step(I)}*{BG}, 1)")
        # fireball ---------------------------------------------------------------------
        fire = F.noise(g, "FireballNoise", "#200400", "#ff7a26", detail=7, scale=5, seethe_rate=0.5, contrast=2.2)
        fire.expr("XScale", f"5/(0.3 + {grow})", 5)
        fsh = F.ellipse(g, "FireballShape", (0.5, 0.46), 0.1, 0.1, 0.35)
        fsh.expr("Width", f"0.05 + 1.1*{II}*{grow}", 0.1)
        fsh.expr("Height", f"(0.05 + 1.1*{II}*{grow})*1.45", 0.15)
        F.masked(fire, fsh)
        bg = F.merge(g, "Fireball", bg, fire, mode="Screen",
                     blend=f"min({step(I)}*(0.25 + 0.9*{cool})*{BG}, 1)")
        core = F.solid(g, "FireCoreColor", (1.0, 0.9, 0.7))
        csh = F.ellipse(g, "FireCoreShape", (0.5, 0.46), 0.1, 0.1, 0.4)
        csh.expr("Width", f"0.05 + 0.6*{II}*{e_out(prog(I, 8), 2)}", 0.1)
        csh.expr("Height", f"(0.05 + 0.6*{II}*{e_out(prog(I, 8), 2)})*1.45", 0.15)
        F.masked(core, csh)
        bg = F.merge(g, "FireCore", bg, core, mode="Screen", blend=f"min({II}*{decay(I, 6)}, 1)")
        g.at(0, 4)
        bg = F.shock_ring(g, "ShockRingA", bg, center=(0.5, 0.46), max_size=2.4, frames=20, border=0.01, soft=0.02,
                          peak=0.8)
        bg = F.shock_ring(g, "ShockRingB", bg, center=(0.5, 0.46), max_size=1.9, frames=24, border=0.03, soft=0.06,
                          peak=0.3, offset=2)
        # shockwave refraction: displacement driven by a ring-shaped map
        rmap = F.solid(g, "RefractRingColor", (1, 1, 1))
        rsh = F.ellipse(g, "RefractRingShape", (0.5, 0.46), 0.1, 0.1, 0.06)
        rsh.set(BorderWidth=0.04)
        rsh.expr("Width", f"0.02 + 2.4*{e_out(prog(I, 20), 2)}", 0.1)
        rsh.expr("Height", f"(0.02 + 2.4*{e_out(prog(I, 20), 2)})*1.7778", 0.1)
        F.masked(rmap, rsh)
        disp = g.add("Displace", "ShockRefraction")
        disp.conn("Input", bg).conn("Foreground", rmap)
        disp.set(Type=0, Center=[0.5, 0.46])
        disp.expr("RefractionStrength", f"0.03*{II}*{step(I)}*(1 - {prog(I, 20)})", 0)
        bg = disp

        # title ------------------------------------------------------------------------
        g.at(0, 6)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Anton", "Regular", 0.19, 1.05, color=p["TEXT_COLOR"])
        clear = F.solid(g, "Clear", (0, 0, 0), alpha=0.0)
        plate = F.fill_material(g, "BlastPlate", title,
                                [(0, "#ffffff", 1), (0.5, "#cfc8bf", 1), (0.56, "#8c847a", 1), (1, "#b4ab9f", 1)])
        face = F.merge(g, "PlateFace", title, plate, mode="Multiply", blend=1.0)
        rim = F.edge_light(g, "FireRim", title, 0.0, -0.003, accent=True, gain=1.5, blur_px=1.4)
        face = F.merge(g, "FireRimMerge", face, rim, mode="Screen",
                       blend=f"min({GL}*(0.35 + 1.5*{II}*{decay(I, 14)}), 1)")
        ext = F.extrusion_stack(g, "PlateDepth", clear, title, layers=6, dx=0.0006, dy=-0.0012,
                                color=(0.05, 0.035, 0.025))
        body = F.merge(g, "TitleBody", ext, face)
        g.at(0, 8)
        arrive = e_out(prog(I, 8), 5)
        exe = e_in(ex, 2)
        zb = F.dirblur(g, "ArrivalZoomBlur", body,
                       f"{ctl('MotionBlurAmount')}*(0.3*(1 - {arrive})*{step(I)} + 0.25*{ex})", angle=0.0, btype=3)
        placed = F.title_placement(g, "Blastforward", zb,
                                   size_expr=f"(0.12 + 0.88*{arrive})*(1 + 4*{exe})")
        shadow_src = F.solid(g, "ShadowColor", (0, 0, 0))
        shm = F.bitmap_mask(g, "ShadowMatte", placed)
        F.masked(shadow_src, shm)
        shadow = F.xf(g, "ShadowOffset", F.blur(g, "ShadowSoft", shadow_src, 18), center=(0.505, 0.48))
        scene = F.merge(g, "DropShadow", bg, shadow, blend=f"0.8*{ctl('ShadowStrength')}*{step(I)}")
        scene = F.merge(g, "TitleOverBlast", scene, placed,
                        blend=f"{step(I)}*(1 - {clamp01(f'({ex} - 0.5)/0.5')})")

        # debris + embers (ParticleIntensity 0 = off) -----------------------------------------
        g.at(0, 10)
        win = window(I, I + " + 2", 1, 1)
        scene = self._debris(g, "Debris", scene, 160, 45, 0.09, 0.5, (0.04, 0.035, 0.03), 0, 0.004,
                             f"160*{PI}*{win}")
        scene = self._debris(g, "BurningDebris", scene, 120, 30, 0.07, 0.35, (1.0, 0.6, 0.25), 6, 0.003,
                             f"120*{PI}*{II}*{win}")
        scene = F.particles(g, "Embers", scene, number=24, lifespan=80, velocity=0.004, angle=90, angle_var=40,
                            size=0.25, color=(1.0, 0.55, 0.2), region="CubeRgn", region_size=(1.8, 1.0, 0.5),
                            center_y=0.0, turbulence=0.3, glow=4, start=I)
        scene = F.impact_flash(g, "BlastFlash", scene, color=(1.0, 0.82, 0.6), peak=0.3, frames=4)
        g.at(0, 12)
        esm = F.noise(g, "ExitSmoke", "#000000", "#0e0c0a", detail=5, scale=2.0, seethe_rate=0.1, contrast=1.8,
                      center="Point(0.5 + time*0.002, 0.5)")
        scene = F.merge(g, "ExitSmokeMerge", scene, esm, blend=f"0.85*{ex}")
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.03, 2.0,
                                    color=(0.85, 0.72, 0.6), y_off=-0.15)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 22", f"{ES} - 5", 14, 8))
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.04, shake_frames=12, shake_amp=0.014,
                             push_start=I, push_dur=f"({g.frames} - {I})")
        g.output = F.finish(g, scene, vignette=0.5)


DESIGN = T07()
