"""T33 - Desert Storm."""
import math

import cv2
import numpy as np

from .. import core as K
from .. import elements as E
from .. import fcomp as F
from ..base import Design, comp, drop_shadow, subtitle, apply_shake
from ..fusion import ctl, prog, e_out, e_in, e_inout, decay, step, window, clamp01
from ..typo import Material
from . import _d_helpers as D

SANDSTONE = Material(base=(0.80, 0.66, 0.48), spec=(1.0, 0.86, 0.66), spec_power=24, spec_gain=0.35, diffuse=0.85,
                     ambient=0.16, metal=0.0, bevel=0.06, texture="concrete", tex_amount=0.18, bump=0.02,
                     rim=(1.0, 0.72, 0.40), seed=33)


def dune(xs, seed, base, amp, freq):
    r = np.random.default_rng(seed)
    y = np.full_like(xs, base)
    for i in range(4):
        f = freq * (1.7 ** i)
        y += amp / (1.8 ** i) * np.sin(xs * f + r.uniform(0, 6.28))
    return y


class T33(Design):
    ID = "T33"
    NAME = "Desert Storm"
    SLUG = "Desert_Storm"
    CATEGORY = "D - Atmosphere and Environment"
    CONCEPT = "A towering haboob sweeps across the dunes; when it passes, a sandstone monument title is standing there."
    ENTRANCE = ("A rolling wall of sand crosses the frame from right to left; the title is uncovered behind its "
                "leading edge, letter by letter, with a sand-blasted edge.")
    REVEAL = "Gust peak as the wall front passes the title centre: sand streak burst, short shake, the sun breaks through."
    CAMERA = "Low-angle composition (low horizon, keystoned title looming up) with a slow lateral drift over parallax dunes."
    MATERIAL = "Warm weathered sandstone, low sun rim from the right, dusty ambient fill."
    EXIT = "A second dust front returns and erodes the letters into wind-blown sand from right to left."
    TECHNIQUES = ["advancing dust wall with density front", "3 parallax dust planes", "parallax dune ridges",
                  "sun god rays through dust", "erosion reveal / exit", "keystone low-angle title"]
    DURATION_FRAMES = 180
    DEFAULTS = dict(MAIN_TITLE="SANDSTORM", SUBTITLE="THE DESERT REMEMBERS", FONT_FAMILY="staatliches",
                    TEXT_COLOR="#E7C79C", ACCENT_COLOR="#FF9C45", ANIMATION_START=6, ANIMATION_DURATION=84,
                    IMPACT_FRAME=48, HOLD_DURATION=74, EXIT_START=134, EXIT_DURATION=40, LETTER_SPACING=0.08,
                    TITLE_WIDTH=0.6, TEXT_POSITION_Y=0.56, SUB_FONT_FAMILY="teko")
    SOUND = [(0, "wind", "Howling desert wind bed"), (0, "atmos", "Low rumble of the approaching storm"),
             (6, "whoosh", "Dust wall roar sweeping right to left"), (40, "debris", "Sand hiss / grit"),
             (46, "impact", "Gust peak - dull heavy thud"), (46, "sub", "Sub drop"),
             (52, "swell", "Warm swell as the sun breaks through"), (134, "wind", "Second gust"),
             (140, "debris", "Letters crumbling into sand"), (168, "tail", "Wind tail")]

    # ------------------------------------------------------------ preview --
    def frame(self, c):
        p, H, W, t, k = c.p, c.H, c.W, c.t, c.k
        acc = K.col(p["ACCENT_COLOR"])
        bgI = p["BACKGROUND_INTENSITY"]
        ex = c.exit_u()
        imp = c.impact
        u = c.reveal_u()
        hit = c.hit(0.03, 0.4)
        drift = K.ease_in_out(K.prog(t, 0, c.dur), 2)
        asp = W / H
        # dust wall: a band of thickness THICK moving right -> left; its trailing edge crosses the
        # title centre half-way through the reveal (= default impact frame)
        THICK = 1.1
        fu = K.prog(t, c.start, c.reveal)
        trail = (asp + 0.4 + THICK) * (1 - 2 * fu)
        front = trail - THICK
        trail2 = (asp + 0.4 + THICK) * (1 - 2 * K.ease_in(ex, 1.3))  # exit wall
        clear = K.smooth(K.prog(t, imp - 0.2, 1.4)) * (1 - 0.8 * K.smooth(ex))
        nx, ny = K.grid(H, W)
        sx, sy = 1.15 * asp * 0.8, -0.55  # sun position

        # sky ---------------------------------------------------------------
        bg = K.vgrad(H, W, (0.09, 0.045, 0.025), (0.55, 0.30, 0.13), 1.3) * (0.75 + 0.35 * clear) * bgI
        sun = K.soft_spot(H, W, sx, sy, 0.10, 0.10, 2.0)
        halo = K.soft_spot(H, W, sx, sy, 0.9, 0.7, 1.2)
        bg += ((sun * 1.2 + halo * 0.35) * (0.45 + 0.65 * clear) * bgI)[..., None] * acc

        # dunes (far / near) with parallax
        xs = np.linspace(-asp, asp, W).astype(np.float32)
        far_y = dune(xs + 0.08 * drift, 3, 0.42, 0.05, 2.0)
        near_y = dune(xs + 0.22 * drift, 8, 0.62, 0.08, 1.4)
        farm = (ny > far_y[None, :]).astype(np.float32)
        nearm = (ny > near_y[None, :]).astype(np.float32)
        farm = cv2.GaussianBlur(farm, (0, 0), 2 * k)
        nearm = cv2.GaussianBlur(nearm, (0, 0), 1.2 * k)
        haze_far = np.array([0.55, 0.33, 0.17], np.float32) * (0.8 + 0.3 * clear)
        bg = bg * (1 - farm[..., None]) + farm[..., None] * haze_far * bgI
        dune_lit = np.clip(1 - (ny - near_y[None, :]) * 2.5, 0.25, 1)
        bg = bg * (1 - nearm[..., None]) + (nearm * dune_lit)[..., None] * np.array([0.30, 0.16, 0.07], np.float32) * bgI

        # far dust plane (behind title)
        dfar = D.shaped(D.plane(H, W, t, 1.0, (0.10, 0.0), 5, 1.0, (drift * 0.15, 0), stretch=(3.5, 1.0)), 0.3, 1.0)
        dcol = np.array([0.75, 0.48, 0.24], np.float32)
        bg = D.over(bg, dcol * (0.7 + 0.4 * clear) * bgI, dfar * (0.35 - 0.2 * clear))

        # title (low-angle: tilted plane, looming) ----------------------------------
        sp = c.title()
        sh = c.shaded(SANDSTONE)
        rgb, a = sh.shade(light=(0.75, -0.35, 0.55), rim_dir=(1, -0.2), rim_gain=0.35 + 0.9 * clear + 0.6 * hit,
                          base=K.col(p["TEXT_COLOR"]), light_gain=0.7 + 0.5 * clear)
        cam = c.cam(zoom=1.0 + 0.04 * drift, pan=(-drift * 30 * k, 0))
        hx, hy = c.hero()
        # screen-x of every sprite column (approx., ignores keystone) -> reveal / erosion fronts
        colx = (np.arange(sp.w, dtype=np.float32) - sp.anchor[0]) * cam.zoom + hx
        colx = colx / (H / 2)
        er = c.cache.get("ernz")
        if er is None:
            er = c.cache["ernz"] = D.sprite_noise(sp, 3.0, 19, 1.5)
        rev = np.clip((colx[None, :] - trail + 0.15 + (er - 0.5) * 0.35) * 5, 0, 1)
        gone = np.clip((colx[None, :] - (trail2 - THICK) + 0.3 + (er - 0.5) * 0.4) * 5, 0, 1) if ex > 0 else 0.0
        a = a * rev * (1 - gone)
        # fresh sand-blasted edge glows warm
        edge = np.clip(1 - np.abs(colx[None, :] - trail + 0.1 + (er - 0.5) * 0.35) * 6, 0, 1) * sp.mask
        rgb = rgb + (edge * 0.4)[..., None] * acc
        L = c.layer()
        c.place(L, cam, rgb, a, sp, 1.0, rot=(16, 0, 0), off=(0, 0, 0))
        bg = drop_shadow(bg, L, p["SHADOW_STRENGTH"] * 0.45, (-30, 18), 24, k)
        img = comp(bg, L)

        # god rays from the sun through the dust
        occl = np.clip(1 - D.shaped(D.plane(H, W, t, 1.6, (0.12, 0.0), 21, 1.0, stretch=(2.5, 1.0)), 0.35, 0.9), 0, 1)
        src = (sun * 3 + halo * 0.6)[..., None] * acc * occl[..., None] * (1 - L.a[..., None] * 0.9)
        rays = K.god_rays(src.astype(np.float32), W / 2 + sx * H / 2, H / 2 + sy * H / 2, 0.7, 0.95, 20)
        img += rays * 0.35 * (0.3 + 0.7 * clear) * bgI

        # the moving dust wall + mid/front dust planes (in front of the title)
        wall_n = D.plane(H, W, t, 1.3, (0.25, -0.01), 11, 1.0, (drift * 0.3, 0), stretch=(1.6, 1.0), evolve=0.1)
        def band(tr):
            rel = nx - (tr - THICK) + (wall_n - 0.5) * 0.8 - ny * 0.12
            return np.clip(rel / 0.35, 0, 1) ** 2 * (1 - np.clip((rel - THICK) / 0.7, 0, 1)) ** 1.5
        wd = band(trail) * (0.6 + 0.7 * wall_n) if fu < 1 else 0.0
        wd2 = band(trail2) * (0.6 + 0.7 * wall_n) if ex > 0 else 0.0
        wtot = np.clip(wd + wd2, 0, 0.96)
        wcol = np.array([0.80, 0.52, 0.27], np.float32) * (0.75 + 0.3 * (ny[..., None] < 0)) * bgI
        img = D.over(img, wcol, wtot * min(1.0, bgI + 0.3))
        dmid = D.shaped(D.plane(H, W, t, 1.1, (0.22, 0.0), 27, 1.06, (drift * 0.5, 0), stretch=(4.0, 1.0)), 0.4, 1.0)
        img = D.over(img, dcol * 1.05 * bgI, dmid * (0.22 + 0.25 * K.smooth(ex)) * (1 - 0.4 * clear))

        # sand streak particles (gust)
        nP = int(160 * p["PARTICLE_INTENSITY"])
        if nP:
            P = c.cache.get("sand")
            if P is None:
                P = c.cache["sand"] = E.Particles(nP, seed=33, z=(0.4, 2.5))
            gust = 0.5 + 1.5 * K.pulse(t, imp, 0.1, 0.8) + 0.8 * K.smooth(ex)
            x, y = P.drift(t, vel=(-1.1, 0.03), turb=0.03, freq=1.5)
            sv = -0.03 * gust * np.ones(P.n, np.float32)
            img += E.particle_layer(H, W, P, x, y, (1.0, 0.75, 0.45), 0.9, 0.22 * (0.5 + 0.5 * gust), zoom=1.0,
                                    focus=1.0, dof=0.8, t=t, glow=0.6, streak=(sv * 7, sv * 0.04))
        # near grit plane, very fast (strongest parallax)
        dn = D.shaped(D.plane(H, W, t, 0.7, (0.45, 0.0), 37, 1.15, (drift * 1.2, 0), stretch=(5.0, 1.0)), 0.5, 1.0, 1.5)
        img = D.over(img, dcol * 0.9 * bgI, dn * 0.3 * (0.4 + K.pulse(t, imp, 0.1, 0.7) + K.smooth(ex)))

        img = apply_shake(c, img, 0.004, 0.25, 15)
        img = subtitle(c, img, cam, imp + 0.8, c.exit_start, (0.98, 0.86, 0.68), y_rel=0.82)
        return c.finish(img, vignette=0.45, grain=0.04, bloom=(0.8, 0.45),
                        grade=dict(shadows=(0.006, 0.002, -0.004), highlights=(0.02, 0.005, -0.02), contrast=1.06))

    # ------------------------------------------------------------- Fusion --
    def fusion(self, g, p):
        F.std_controls(g, p)
        F.accent_holder(g, p["ACCENT_COLOR"], "Sun Color")
        ex = prog(ctl("ExitStart"), ctl("ExitDuration"))
        u = prog(ctl("AnimStart"), ctl("AnimDuration"))
        BG = ctl("BackgroundIntensity")
        I = ctl("ImpactFrame")
        drift = e_inout(prog(0, g.frames))
        clear = f"({e_out(prog(I + ' - 5', 34), 2)}*(1 - 0.8*{ex}))"
        # dust-wall trailing edge in frame-x (0..1), right -> left; crosses centre half-way through
        front = f"(0.5 + 1.25*(1 - 2*{u}))"
        front2 = f"(0.5 + 1.25*(1 - 2*{e_in(ex, 1.3)}))"

        g.at(0, 0)
        sky = F.gradient_bg(g, "DuskSky", [(0, "#9e5c2b", 1), (0.55, "#5a3016", 1), (1, "#2a140a", 1)],
                            start=(0.5, 0.0), end=(0.5, 1.0))
        bg = F.light_spot(g, "SunHalo", sky, None, (0.85, 0.78), 0.7, 0.9, 0.7, accent=True, gain=0.6,
                          blend=f"{BG}*(0.45 + 0.55*{clear})")
        bg = F.light_spot(g, "SunDisc", bg, None, (0.85, 0.78), 0.06, 0.1, 0.25, accent=True, gain=1.4,
                          blend=f"{BG}*(0.5 + 0.5*{clear})")
        bg = D.f_fog(g, "DustFar", bg, "#000000", "#b0703a", 2.0, "1", (0.004, 0.0), blend=f"{BG}*(0.35 - 0.2*{clear})",
                     mode="Normal", aspect=0.3)
        g.at(0, 2)
        for i, (base, amp, col, par) in enumerate(((0.3, 0.035, "#8a5228", 0.02), (0.2, 0.05, "#3a1d0c", 0.06))):
            r = np.random.default_rng(3 + i * 5)
            pts = [(-0.1, -0.1)]
            ph = r.uniform(0, 6.28, 3)
            for j in range(15):
                x = -0.1 + 1.2 * j / 14
                y = base + sum(amp / (1.8 ** q) * math.sin(x * 6 * (1.7 ** q) + ph[q]) for q in range(3))
                pts.append((x, y))
            pts.append((1.1, -0.1))
            dm = F.closed_poly_mask(g, f"Dune{i}Shape", pts, soft=0.003)
            ds = F.solid(g, f"Dune{i}Color", col)
            F.masked(ds, dm)
            dx = F.xf(g, f"Dune{i}Parallax", ds, center=f"Point(0.5 - {par}*{drift}, 0.5)")
            bg = F.merge(g, f"Dune{i}", bg, dx, blend=f"min({BG}, 1)")

        g.at(0, 4)
        title = F.title_text(g, "MainTitle", p["MAIN_TITLE"], "Staatliches", "Regular", 0.19, 1.08,
                             color=p["TEXT_COLOR"])
        stone = F.noise(g, "SandstoneGrain", "#8a6a48", "#ffffff", detail=6, scale=40, seethe_rate=0.0, contrast=1.2)
        sm = F.bitmap_mask(g, "SandstoneMatte", title)
        F.masked(stone, sm)
        face = F.merge(g, "SandstoneFace", title, stone, mode="Multiply", blend=0.6)
        rim = F.edge_light(g, "SunRim", title, -0.0025, -0.001, accent=True, gain=1.3, blur_px=1.5)
        face = F.merge(g, "SunRimMerge", face, rim, mode="Screen",
                       blend=f"min({ctl('GlowStrength')}*(0.35 + 0.65*{clear} + 0.6*{decay(I, 10)}), 1)")
        lit = F.cc(g, "WarmExposure", face, gain=f"0.6 + 0.45*{clear}")
        g.at(0, 6)
        placed = F.title_placement(g, "TitlePlace", lit)
        keystone = g.add("CornerPositioner", "LowAngleKeystone")
        keystone.conn("Input", placed)
        keystone.set(TopLeft=[0.07, 0.97], TopRight=[0.93, 0.97], BottomLeft=[0.0, 0.0], BottomRight=[1.0, 0.0])
        # reveal behind the dust-wall front, erosion in front of the exit wall
        rv = F.rect(g, "UncoverFront", (1.5, 0.5), 2.0, 2.0, 0.05)
        rv.expr("Center", f"Point({front} + 1.0 - 0.04, 0.5)", [1.5, 0.5])
        er = F.rect(g, "ErodeFront", (2.5, 0.5), 2.0, 2.0, 0.06)
        er.expr("Center", f"Point({front2} + 1.0 - 0.45, 0.5)", [2.5, 0.5])
        er.set(PaintMode=F.FuID("Subtract"))
        er.conn("EffectMask", rv, "Mask")
        hold = F.solid(g, "TitleHolder", (0, 0, 0), alpha=0.0)
        tm = F.merge(g, "TitleUncovered", hold, keystone)
        F.masked(tm, er)
        scene = F.merge(g, "TitleOverDesert", bg, tm, blend="1")
        scene = F.merge(g, "TitleSandBlur", scene, F.dirblur(g, "ErodeStreaks", tm, f"0.04*{ex}", angle=180),
                        mode="Screen", blend=f"0.6*{ex}")

        g.at(0, 8)
        wallm = F.rect(g, "DustWallBody", (2.0, 0.5), 0.5, 2.0, 0.2)
        wallm.expr("Center", f"Point({front} - 0.3, 0.5)", [2.0, 0.5])
        wall2 = F.rect(g, "DustWall2Body", (3.0, 0.5), 0.5, 2.0, 0.2)
        wall2.expr("Center", f"Point({front2} - 0.3, 0.5)", [3.0, 0.5])
        wall2.conn("EffectMask", wallm, "Mask")
        scene = D.f_fog(g, "DustWall", scene, "#000000", "#c98a4a", 2.4, "1", (0.012, 0.0), blend=f"min({BG}+0.3, 1)",
                        mode="Normal", mask=wall2, contrast=1.3, aspect=0.6)
        scene = D.f_fog(g, "DustMid", scene, "#000000", "#b77a40", 1.8, f"1 + 0.06*{drift}", (0.008, 0.0),
                        blend=f"{BG}*(0.22 + 0.25*{ex})*(1 - 0.4*{clear})", mode="Normal", aspect=0.25)
        scene = F.particles(g, "SandStreaks", scene, number=70, lifespan=30, velocity=0.09, angle=180, angle_var=4,
                            size=0.15, color=(1.0, 0.75, 0.45), region="CubeRgn", region_size=(0.2, 1.4, 1.0),
                            center_y=0.0, turbulence=0.05, glow=2)
        scene = D.f_fog(g, "GritNear", scene, "#000000", "#a86c38", 1.2, f"1 + 0.15*{drift}", (0.02, 0.0),
                        blend=f"{BG}*0.3*(0.4 + {decay(I, 18)} + {ex})", mode="Normal", aspect=0.2, contrast=1.8)
        g.at(0, 10)
        scene = D.f_sub(g, p, "Teko", "SemiBold", (0.98, 0.86, 0.68), -0.13, f"{I} + 18", f"{ctl('ExitStart')}",
                        scene=scene)
        scene = F.camera_rig(g, "Camera", scene, 1.0, 1.04, shake_frames=6, shake_amp=0.004)
        g.output = F.finish(g, scene, vignette=0.45)


DESIGN = T33()
