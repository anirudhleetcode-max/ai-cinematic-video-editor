"""T22 - Hologram Breach."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, subtitle
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from . import _c_helpers as X

NB = 9          # preview bands
NB_F = 7        # Fusion bands
ORDER = [4, 1, 7, 2, 8, 0, 5, 3, 6]   # designed (non-sequential) assembly order
ORDER_F = [3, 0, 5, 2, 6, 1, 4]


def _blink(fr, i, age, dur=0.28):
    """Purposeful materialisation blink: decisive on/off pattern that ends on 'on'."""
    if age >= dur:
        return 1.0
    return 1.0 if K.hash01(fr * 7 + i * 13, 5) > 0.55 * (1 - age / dur) + 0.15 else 0.18


class T22(Design):
    ID = "T22"
    NAME = "Hologram Breach"
    SLUG = "Hologram_Breach"
    CATEGORY = "C - Future Tech and Kinetic Camera"
    CONCEPT = "The title is a projected hologram: a floor emitter throws a light beam and the wordmark assembles in it."
    ENTRANCE = ("Emitter pad powers on and opens a volumetric beam; the title materialises as horizontal scan "
                "segments in a designed non-sequential order, each sliding into register with a short blink.")
    REVEAL = "At the impact frame a lock-in scan pass sweeps the title: interference stops and the image stabilises."
    CAMERA = "Locked-off with a slow lateral parallax drift; no shake (precision device)."
    MATERIAL = "Emissive cyan light: scan lines, brighter edge fresnel, bottom-up projector falloff, faint interference."
    EXIT = "Projector cut: the hologram collapses vertically into the beam, the beam retracts into the emitter."
    TECHNIQUES = ["segmented scan assembly", "scan lines", "interference glitch (controllable)", "volumetric beam",
                  "emitter ring", "beam dust", "vertical collapse exit"]
    DURATION_FRAMES = 192
    DEFAULTS = dict(MAIN_TITLE="BREACH", SUBTITLE="SIGNAL ACQUIRED", FONT_FAMILY="orbitron",
                    TEXT_COLOR="#C8F6FF", ACCENT_COLOR="#2FD4FF", ANIMATION_START=12, ANIMATION_DURATION=58,
                    IMPACT_FRAME=76, HOLD_DURATION=72, EXIT_START=150, EXIT_DURATION=28, LETTER_SPACING=0.12,
                    TITLE_WIDTH=0.56, TEXT_POSITION_Y=0.55, SHADOW_STRENGTH=0.0)
    SOUND = [(0, "atmos", "Lab room tone / server hum"), (4, "digital", "Emitter power-on chirp"),
             (12, "swell", "Beam swell (frames 12-76)"), (18, "glitch", "Segment materialise ticks"),
             (44, "glitch", "Interference burst"), (70, "rwhoosh", "Reverse air into lock"),
             (76, "impact", "Soft digital lock hit"), (77, "shimmer", "Lock-in scan shimmer"),
             (150, "digital", "Projector cut"), (160, "tail", "Hum tail")]
    FUSION_NOTES = [
        "Extra controls: 'Flicker Amount' (FlickerAmount) and 'Glitch Amount' (GlitchAmount) scale the pre-lock "
        "flicker and the interference slice displacement; set both to 0 for a perfectly stable hologram. The final "
        "hold is always stable.",
        "Preview renderer mapping: the reference preview has no separate flicker/glitch parameters; both scale "
        "with IMPACT_INTENSITY there (0 = no flicker, no glitch).",
        "Fusion assembles 7 horizontal bands (preview: 9); the interference streaks are a stretched FastNoise.",
    ]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k, fr = c.p, c.H, c.W, c.t, c.k, c.fr
        acc = K.col(p["ACCENT_COLOR"])
        tc = K.col(p["TEXT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        amt = p["IMPACT_INTENSITY"]  # flicker/glitch scale in the preview
        ex = c.exit_u()
        imp = c.impact
        sp = c.title()
        hx, hy = c.hero()
        pre = 1 - K.smooth(K.prog(t, imp - 0.15, 0.3))           # interference only before lock
        power = K.smooth(K.prog(t, c.start - 0.35, 0.5))         # emitter on
        beam = K.smooth(K.prog(t, c.start - 0.1, 0.6)) * (1 - K.smooth(K.prog(ex, 0.45, 0.55)))
        collapse = K.ease_in(K.prog(ex, 0.0, 0.6), 2)

        # --- lab environment
        bg = K.vgrad(H, W, (0.004, 0.006, 0.010), (0.010, 0.014, 0.020))
        nx, ny = K.grid(H, W)
        cx = hx / (H / 2)
        pad_y = (hy + sp.ink_h * 1.45) / (H / 2)
        floor = np.clip((ny - pad_y + 0.05) * 3, 0, 1)
        bg += (floor * 0.025 * bgI)[..., None] * (0.4 + acc * 0.6)
        ring = E.ring(H, W, cx, pad_y, 0.055, 0.006, aspect=5.5) + 0.5 * E.ring(H, W, cx, pad_y, 0.075, 0.003, 5.5)
        padglow = K.soft_spot(H, W, cx, pad_y, 0.55, 0.05, 1.5)
        pl = power * (1 - 0.7 * K.smooth(K.prog(ex, 0.6, 0.4)))
        bg += ((ring * 0.9 + padglow * 0.35) * pl * bgI)[..., None] * acc
        top = (hy - sp.ink_h * 0.6) / (H / 2)
        span = max(1e-3, pad_y - top)
        fy = np.clip((pad_y - ny) / span, 0, 1)
        hw = 0.2 + (sp.ink_w / H * 1.05 - 0.2) * fy
        cone = (np.exp(-(np.abs(nx - cx) / hw) ** 4) * (ny > top) * np.clip((pad_y - ny) * 25, 0, 1)
                * (1 - 0.6 * fy) * np.clip((ny - top) * 6, 0, 1))
        cone = cone * (1 - collapse * np.clip((pad_y - ny) * 2.0, 0, 1))
        bg += (cone * 0.2 * beam * bgI)[..., None] * (acc * 0.8 + 0.1)
        # dust inside the beam
        if p["PARTICLE_INTENSITY"] > 0:
            P = c.cache.get("dust")
            if P is None:
                P = c.cache["dust"] = E.Particles(int(220 * p["PARTICLE_INTENSITY"]), seed=8, spread=(0.6, 1.0),
                                                  z=(0.6, 2.0))
            x, y = P.drift(t, vel=(0.0, -0.05), turb=0.02, freq=0.5, wrap=(0.6, 1.0))
            dl = E.particle_layer(H, W, P, x + cx, y + 0.2, acc * 0.6 + 0.4, 1.2, 0.6, glow=0.6)
            bg += dl * K.blur(cone, 8 * k)[..., None] * 3.0 * beam

        # --- hologram title (pure light, additive)
        key = "holo"
        if key not in c.cache:
            rgb0 = X.vband(sp, tc * 0.5 + acc * 0.22, acc * 0.7 + tc * 0.15)
            rgb0 += X.inner_edge(sp, 0.05)[..., None] * (acc * 0.9 + 0.35)
            c.cache[key] = rgb0
        rgb = c.cache[key] * sp.mask[..., None]
        yy = np.arange(sp.h, dtype=np.float32)[:, None, None]
        rgb = rgb * (0.6 + 0.4 * (0.5 + 0.5 * np.sin(yy / (3.6 * k) * math.pi)))          # fine scan lines
        roll = (yy - sp.ink[1]) / max(1.0, sp.ink_h) - (X.frac(t * 0.35) * 1.6 - 0.3)
        rgb = rgb * (1 + 0.35 * np.exp(-(roll / 0.08) ** 2))                                 # refresh band
        # global flicker before lock (purposeful, scaled by IMPACT_INTENSITY)
        fl = max(0.0, math.sin(t * 19.0) * math.sin(t * 7.3 + 1.1) - 0.25) * 1.4
        gain = 0.9 * (1 - 0.45 * amt * pre * min(1.0, fl)) * (1 + 0.7 * c.hit(0.02, 0.25))
        gain *= 1 + 1.5 * collapse

        cam = c.cam(zoom=1.0, pan=(-14 * k * math.sin(t * 0.25), 0))
        Lh = c.layer()
        y0, y1 = sp.ink[1] - 2, sp.ink[3] + 3
        edges = np.linspace(y0, y1, NB + 1)
        for j, i in enumerate(ORDER):
            ti = c.start + c.reveal * 0.85 * j / (NB - 1)
            age = t - ti
            if age < 0:
                continue
            vis = _blink(fr, i, age)
            slide = (1 - K.ease_out(K.prog(age, 0, 0.35), 3)) * (1 if i % 2 else -1) * 60 * k
            jit = 0.0
            if pre > 0 and K.hash01(fr // 2 + i * 31, 9) > 0.82:
                jit = (K.hash01(fr + i, 3) - 0.5) * 50 * k * amt * pre
            box = (0, edges[i], sp.w, edges[i + 1])
            from ..typo import place_sprite
            place_sprite(Lh, cam, rgb, sp.mask, box, sp.anchor, (hx, hy, 0), 1.0, (0, 0, p["TEXT_ROTATION"]),
                         (slide + jit, 0, 0, 0, 0, 0, 1, 0, 0), vis * gain, add=True)
            # bright materialisation line
            if age < 0.3:
                ln = np.zeros((sp.h, sp.w, 3), np.float32)
                yb = int(edges[i])
                ln[max(0, yb - 2):yb + 2, int(sp.ink[0]):int(sp.ink[2])] = (acc + 0.6) * (1 - age / 0.3) * 1.5
                place_sprite(Lh, cam, ln, np.ones((sp.h, sp.w), np.float32), (0, edges[i] - 4, sp.w, edges[i] + 4),
                             sp.anchor, (hx, hy, 0), 1.0, (0, 0, p["TEXT_ROTATION"]), (slide, 0, 0, 0, 0, 0, 1, 0, 0),
                             1.0, add=True)
        holo = Lh.rgb
        # lock-in scan pass at impact
        su = K.prog(t, imp, 0.45)
        if 0 < su < 1:
            sy = H / 2 + hy - sp.ink_h * 0.7 + sp.ink_h * 1.4 * K.ease_in_out(su, 2)
            band = np.exp(-((np.arange(H, dtype=np.float32) - sy) / (6 * k)) ** 2)[:, None, None]
            holo = holo + band * K.blur(holo, 3 * k) * 2.0 * (1 - su) + band * 0.0
        # interference slices on the hologram only (stop at lock)
        if pre > 0.05 and amt > 0 and K.hash01(fr // 3, 17) > 0.55 and t > c.start:
            holo = X.glitch_slices(holo, 0.6 * amt * pre, seed=fr // 3, k=k, n=3)
            holo = X.rgb_split(holo, 4 * k * amt * pre)
        # exit collapse toward the emitter
        if collapse > 0:
            sy_ = max(0.02, 1 - collapse)
            piv = H / 2 + pad_y * H / 2
            M = np.float32([[1 + 0.15 * collapse, 0, -0.15 * collapse * (W / 2 + hx)], [0, sy_, piv * (1 - sy_)]])
            holo = cv2.warpAffine(holo, M, (W, H))
            holo *= 1 - K.smooth(K.prog(ex, 0.55, 0.3))
        G = p["GLOW_STRENGTH"]
        img = bg + holo + (K.blur(holo, 5 * k) * 0.6 + K.blur(holo, 24 * k) * 0.45) * G

        img = subtitle(c, img, cam, imp + 0.35, c.exit_start - 0.2, tc * 0.6 + acc * 0.2, y_rel=0.85)
        img = X.grade_fast(img, shadows=(-0.002, 0.0, 0.006), contrast=1.03)
        return c.finish(img, vignette=0.55, grain=0.03, bloom=(0.9, 0.4))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p, extra=[("FlickerAmount", "Flicker Amount", 1.0, 0, 2, False, "Look"),
                                    ("GlitchAmount", "Glitch Amount", 1.0, 0, 2, False, "Look")])
        F.accent_holder(g, p["ACCENT_COLOR"])
        I = ctl("ImpactFrame")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        S, D = ctl("AnimStart"), ctl("AnimDuration")
        BG = ctl("BackgroundIntensity")
        pre = f"(1 - {e_inout(prog(f'{I} - 4', 8))})"
        collapse = e_in(clamp01(f"{ex}/0.6"), 2)
        beam = f"{e_inout(prog(f'{S} - 2', 14))}*(1 - {e_inout(clamp01(f'({ex} - 0.45)/0.55'))})"
        pad_y = 0.21

        g.at(0, 0)
        bg = F.gradient_bg(g, "LabGradient", [(0, "#010203", 1), (1, "#030405", 1)])
        pw = f"{e_inout(prog(f'{S} - 8', 12))}*(1 - 0.7*{e_inout(clamp01(f'({ex} - 0.6)/0.4'))})"
        rs = F.accent_solid(g, "EmitterRingColor", 1.2)
        rm = F.ellipse(g, "EmitterRingShape", (0.5, pad_y), 0.17, 0.03, 0.004, border=0.004)
        F.masked(rs, rm)
        bg = F.merge(g, "EmitterRing", bg, rs, mode="Screen", blend=f"{BG}*{pw}")
        bg = F.light_spot(g, "EmitterGlow", bg, None, (0.5, pad_y), 0.5, 0.05, 0.08, accent=True, gain=0.5,
                          blend=f"{BG}*{pw}")
        g.at(0, 2)
        cone = F.closed_poly_mask(g, "BeamShape", [(0.415, pad_y), (0.585, pad_y), (0.79, 0.6), (0.21, 0.6)],
                                  soft=0.04)
        cs = F.accent_solid(g, "BeamColor", 0.8)
        F.masked(cs, cone)
        bg = F.merge(g, "Beam", bg, cs, mode="Screen", blend=f"0.2*{BG}*{beam}")
        bg = F.particles(g, "BeamDust", bg, number=10, lifespan=80, velocity=0.004, angle=90, angle_var=10, size=0.25,
                         color=(0.6, 0.9, 1.0), region="CubeRgn", region_size=(0.3, 0.05, 0.2), center_y=-0.3,
                         turbulence=0.08, glow=2)
        bg = F.xf(g, "ParallaxDrift", bg, center="Point(0.5 - 0.004*sin(time*0.0104), 0.5)", edges=1)

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Orbitron", "Black", 0.1, 1.12,
                             color=p["TEXT_COLOR"])
        ramp = F.fill_material(g, "ProjectorFalloff", title, [(0, "#9feeff", 1), (1, "#ffffff", 1)],
                               start=(0.5, 0.42), end=(0.5, 0.58))
        holo = F.merge(g, "HoloFalloff", title, ramp, mode="Multiply", blend=0.6)
        scan = X.streak_noise(g, "ScanLines", "#5a6a70", "#ffffff", stretch=40, scale=60, seethe=0.6,
                              center="Point(0.5, 0.5 + time*0.002)")
        scm = F.bitmap_mask(g, "ScanClip", title)
        F.masked(scan, scm)
        holo = F.merge(g, "ScanMultiply", holo, scan, mode="Multiply", blend=0.45)
        rim = F.edge_light(g, "HoloEdge", title, 0.0, -0.002, accent=True, gain=1.2, blur_px=1.0)
        holo = F.merge(g, "HoloEdgeMerge", holo, rim, mode="Screen", blend=f"{ctl('GlowStrength')}")
        g.at(0, 6)
        hold = F.solid(g, "BandHolder", (0, 0, 0), alpha=0.0)
        cur = hold
        y0, y1 = 0.44, 0.56
        hb = (y1 - y0) / NB_F
        flick = (f"(1 - 0.45*{ctl('FlickerAmount')}*{pre}*min(max(sin(time*0.79)*sin(time*0.304 + 1.1) - 0.25, 0)*1.4, 1))")
        for j, i in enumerate(ORDER_F):
            ti = f"({S} + {D}*{0.85 * j / (NB_F - 1):.3f})"
            slide = f"{1 if i % 2 else -1}*0.03*(1 - {e_out(prog(ti, 8), 3)})"
            jit = f"{ctl('GlitchAmount')}*{pre}*0.012*sin(time*{2.1 + i * 0.7:.2f})*max(sin(time*0.37 + {i}), 0)"
            band = F.xf(g, f"Band{i}Shift", holo, center=f"Point(0.5 + {slide} + {jit}, 0.5)")
            bm = F.rect(g, f"Band{i}Mask", (0.5, y0 + hb * (i + 0.5)), 2.0, hb + 0.001, 0.0)
            F.masked(band, bm)
            blink = f"(1 - 0.8*(1 - {step(f'{ti} + 6')})*max(sin(time*2.6 + {i}), 0))"
            cur = F.merge(g, f"Band{i}", cur, band, blend=f"{step(ti)}*{blink}")
        g.at(0, 8)
        lock = F.rect(g, "LockScanBand", (0.5, 0.5), 2.0, 0.008, 0.01)
        lock.expr("Center", f"Point(0.5, 0.58 - 0.16*{e_inout(prog(I, 11))})", [0.5, 0.5])
        lclip = F.bitmap_mask(g, "LockScanClip", title, paint="Multiply", prev=lock)
        ls = F.accent_solid(g, "LockScanColor", 2.0)
        F.masked(ls, lclip)
        cur = F.merge(g, "LockScan", cur, ls, mode="Screen", blend=f"{step(I)}*(1 - {prog(I, 11)})")
        cur = F.cc(g, "HoloFlicker", cur, gain=f"{flick}*(1 + 0.7*{decay(I, 6)})*(1 + 1.5*{collapse})")
        # vertical collapse into the emitter (exit)
        col = g.add("Transform", "CollapseToEmitter")
        col.conn("Input", cur)
        col.set(UseSizeAndAspect=0, Pivot=[0.5, pad_y], Center=[0.5, pad_y])
        col.expr("YSize", f"max(1 - {collapse}, 0.02)", 1)
        col.expr("XSize", f"1 + 0.15*{collapse}", 1)
        placed = F.title_placement(g, "TitlePlace", col)
        glow = F.softglow(g, "HoloGlow", placed, 14, gain=f"0.8*{ctl('GlowStrength')}", threshold=0.15)
        scene = F.merge(g, "HoloOverLab", bg, glow, mode="Screen",
                        blend=f"1 - {e_inout(clamp01(f'({ex} - 0.55)/0.3'))}")
        g.at(0, 10)
        sub, subp = F.subtitle_text(g, "Subtitle", p["SUBTITLE"], "Teko", "SemiBold", 0.028, 1.6,
                                    color=(0.6, 0.85, 0.92), y_off=-0.1)
        scene = F.merge(g, "SubtitleMerge", scene, subp, blend=window(f"{I} + 8", f"{ctl('ExitStart')} - 5", 14, 8))
        g.output = F.finish(g, scene, vignette=0.55)


DESIGN = T22()
