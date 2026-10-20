"""v3 compositor: filmic grade + the illustrated world composited onto the wall.

Order per frame:
  1. original pixels -> very light skin-only softening -> filmic grade
  2. world ink layer   MULTIPLY into the wall   (behind the people)
  3. world light layer ADD + soft glow          (behind the people)
  4. gesture particle streams (released by the singers' own hand gestures)
  5. contour line at two authored moments (opening, climax)
  6. halation/diffusion, transitions, slow camera breathing, grain
People are protected by a refined mask (saturation/dark segmentation unioned
with YuNet face ellipses); nothing from the world is ever drawn over them.
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("EDIT_SAT", "58")
import common  # noqa: E402
from common import FPS, H, N_OUT, SLOW_A, SLOW_B, W, WORK, person_mask, read_frames  # noqa: E402
import world as Wd  # noqa: E402
from analyze_v3 import face_detector, face_ellipses, faces_of  # noqa: E402

MW, MH = 480, 270
PREROLL = 6
AN = np.load(os.path.join(WORK, "v3_analysis.npz"))
TOP = AN["top"]


# ------------------------------------------------------------- gesture streams
def plan_gestures():
    """Strong hand raises in the development sections send gold ink to a flower."""
    sc = 1920 / 240
    ev = []
    windows = [(28.5, 53.0), (56.0, 77.0)]
    for h in range(2):
        for f in range(3, N_OUT):
            t = f / FPS
            if not any(a <= t <= b for a, b in windows):
                continue
            dy = (TOP[f - 3, h, 1] - TOP[f, h, 1]) * sc
            if dy > 70 and TOP[f, h, 1] * sc < 520:
                ev.append((dy, f, h))
    ev.sort(reverse=True)
    chosen = []
    for dy, f, h in ev:
        if all(abs(f - g) > 4.5 * FPS for _, g, _ in chosen):
            chosen.append((dy, f, h))
        if len(chosen) >= 6:
            break
    streams = []
    free = {"w": [i for i, fl in enumerate(Wd.FLOWERS) if fl["side"] == "w"],
            "e": [i for i, fl in enumerate(Wd.FLOWERS) if fl["side"] == "e"]}
    for dy, f, h in sorted(chosen, key=lambda c: c[1]):
        side = "w" if h == 0 else "e"
        if not free[side]:
            continue
        hand = TOP[f, h] * sc
        fi = free[side].pop(0 if side == "w" else -1)
        tgt = Wd.path_pt(Wd.FLOWERS[fi]["s"]) + np.array([0, -24])
        t0 = f / FPS
        streams.append(dict(t0=t0, src=hand, dst=tgt, flower=fi))
        Wd.GESTURE_BLOOMS[fi] = t0 + 1.5
    return streams


STREAMS = plan_gestures()


def draw_streams(light, t):
    for s in STREAMS:
        u0 = t - s["t0"]
        if u0 < 0 or u0 > 2.2:
            continue
        a, b = s["src"], s["dst"]
        c = (a + b) / 2 + np.array([0, -160])
        for k in range(16):
            u = (u0 - k * 0.045) / 1.5
            if u < 0 or u > 1:
                continue
            ue = Wd.ease(u)
            p = (1 - ue) ** 2 * a + 2 * (1 - ue) * ue * c + ue * ue * b
            p = p + np.array([6 * math.sin(k * 1.7 + u * 5), 5 * math.cos(k * 2.3 + u * 4)])
            light.dot(p, 2.2 - 0.06 * k, Wd.LIGHT_GOLD, 0.85 * (1 - u * 0.4))


# ------------------------------------------------------------- grade
def _luts():
    x = np.arange(256) / 255.0
    # filmic: gentle toe lift, soft shoulder (highlight roll-off), mild S in mids
    expo = np.clip(x * 1.07, 0, None)
    toe = 0.012
    sh = 1 - np.exp(-2.6 * expo)
    sh /= (1 - math.exp(-2.6 * 1.07))
    y = toe + (1 - toe - 0.015) * (0.72 * sh + 0.28 * expo / 1.07)
    y = y + 0.06 * np.sin(np.pi * y) * (y - 0.5) * 2
    # warm ivory paper-white, slightly cool deep shadows (split tone)
    r = y * 1.025 + 0.010 * x
    g = y * 1.005
    b = y * 0.955 + 0.022 * (1 - x) ** 3
    to8 = lambda c: np.clip(c * 255, 0, 255).astype(np.uint8)
    return to8(b), to8(g), to8(r)


LUT_B, LUT_G, LUT_R = _luts()
_yy, _xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIGNETTE = (1 - 0.085 * (((_xx - W / 2) / (W / 2)) ** 2 + ((_yy - H / 2) / (H / 2)) ** 2) ** 1.4)[..., None]
del _yy, _xx
_gr = np.random.default_rng(4)
GRAIN = [_gr.normal(0, 1.0, (H, W)).astype(np.float32) for _ in range(5)]


def soften_skin(img, mask_lo):
    """Very light, skin-only, texture-preserving softening (no geometry change)."""
    half = cv2.resize(img, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
    ycc = cv2.cvtColor(half, cv2.COLOR_BGR2YCrCb)
    skin = ((ycc[..., 1] > 135) & (ycc[..., 1] < 178) & (ycc[..., 2] > 80) & (ycc[..., 2] < 132)
            & (ycc[..., 0] > 60)).astype(np.float32)
    pm = cv2.resize(mask_lo, (W // 2, H // 2)).astype(np.float32) / 255
    skin = cv2.GaussianBlur(skin * pm, (0, 0), 4)
    delta = cv2.bilateralFilter(half, 7, 20, 5).astype(np.float32) - half.astype(np.float32)
    out = img.astype(np.float32) + cv2.resize(delta * skin[..., None] * 0.3, (W, H))
    return np.clip(out, 0, 255).astype(np.uint8)


def grade(img):
    out = cv2.merge([cv2.LUT(c, l) for c, l in zip(cv2.split(img), (LUT_B, LUT_G, LUT_R))]).astype(np.float32)
    luma = out @ np.array([0.114, 0.587, 0.299], np.float32)
    out = luma[..., None] + (out - luma[..., None]) * 1.05       # controlled richness
    return out


def finish(out, f, extra_glow=0.0):
    small = cv2.resize(out, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    lum = small.mean(2, keepdims=True)
    hi = np.clip((lum - 190) / 65, 0, 1)
    halo = cv2.GaussianBlur(small * hi, (0, 0), 7) * np.array([0.55, 0.75, 1.0], np.float32)  # warm halation
    diff = cv2.GaussianBlur(small, (0, 0), 16)
    out = out + cv2.resize(halo, (W, H)) * (0.18 + extra_glow)
    k = 0.022 + extra_glow * 0.2
    out = 255 - (255 - out) * (1 - k * cv2.resize(diff, (W, H)) / 255)                  # light diffusion
    out *= VIGNETTE
    luma_n = GRAIN[f % len(GRAIN)]
    out += (luma_n * (1.6 + 1.2 * (1 - np.clip(out.mean(2) / 255, 0, 1))))[..., None]   # finer in highlights
    return out


# ------------------------------------------------------------- contour moments
def draw_contour(light, mask_lo, t, f):
    a1 = Wd.env(t, Wd.K.window_w - 0.6, Wd.K.window_w + 2.8, 0.8, 1.6) * 0.55
    a2 = 0.0   # no contour at the climax: the embrace stays untouched
    a = max(a1, a2)
    if a <= 0:
        return
    col = Wd.LIGHT_CREAM if a1 >= a2 else Wd.LIGHT_GOLD
    prog = Wd.ramp(t, Wd.K.window_w - 0.6, Wd.K.window_w + 0.9) if a1 >= a2 else \
        Wd.ramp(t, Wd.K.climax + 2.0, Wd.K.climax + 4.5)
    gap = cv2.dilate(mask_lo, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    cs, _ = cv2.findContours(gap, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    sx = W / MW
    for c in cs:
        if cv2.contourArea(c) < 1500:
            continue
        p = c[:, 0, :].astype(np.float64)
        keep = (p[:, 0] > 2) & (p[:, 0] < MW - 3) & (p[:, 1] > 2) & (p[:, 1] < MH - 3)
        p = p[::2]
        keep = keep[::2]
        # circular smoothing
        r = 6
        k = np.exp(-0.5 * (np.arange(-r, r + 1) / 3.5) ** 2)
        k /= k.sum()
        ext = np.vstack([p[-r:], p, p[:r]])
        ps = np.stack([np.convolve(ext[:, d], k, "valid") for d in range(2)], 1) * sx + sx / 2
        run = []
        for i in range(len(ps)):
            if keep[i]:
                run.append(ps[i])
            elif len(run) > 8:
                Wd.stroke(light, np.array(run), col, a, 2.0, prog, 999, t, 0.8, taper=True)
                run = []
            else:
                run = []
        if len(run) > 8:
            Wd.stroke(light, np.array(run), col, a, 2.0, prog, 998, t, 0.8, taper=True)


# ------------------------------------------------------------- frame
def camera(t, f):
    if SLOW_A <= f < SLOW_B:
        return 1.0 + 0.045 * Wd.ease((f - SLOW_A) / (SLOW_B - SLOW_A))
    t0 = 0 if f < SLOW_A else SLOW_B / FPS
    return 1.0 + 0.012 * (1 - math.cos(2 * math.pi * (t - t0) / 26.0)) / 2 + 0.006 * Wd.ease((t - t0) / 60)


def transition(f):
    t = f / FPS
    black = 1 - Wd.ramp(t, 0.0, 1.2)
    black = max(black, Wd.ramp(t, Wd.K.end - 1.0, Wd.K.end - 0.03))
    warm = 0.0
    for c in (SLOW_A, SLOW_B):
        warm = max(warm, 0.32 * math.exp(-abs(f - c + 0.5) / 4.0))
    return black, warm


def render_frame(img, f, ema, det):
    t = f / FPS
    faces = faces_of(det, cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA))
    m = person_mask(cv2.resize(img, (MW, MH), interpolation=cv2.INTER_AREA))
    m = face_ellipses(m, faces, MW / 1920).astype(np.float32) / 255
    ema = m if ema is None else 0.55 * ema + 0.45 * m
    mask_lo = (ema > 0.5).astype(np.uint8) * 255

    base = grade(soften_skin(img, mask_lo))
    ink, light = Wd.render_world(t)
    draw_streams(light, t)

    keep = cv2.dilate(mask_lo, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    keep = cv2.resize(cv2.GaussianBlur(keep, (0, 0), 1.2), (W, H)).astype(np.float32) / 255
    wall = (1 - keep)[..., None]

    ia = ink.a.astype(np.float32)[..., None] / 255 * wall
    out = base * (1 - ia * (1 - ink.col.astype(np.float32) / 255))      # multiply ink into the wall
    cw = Wd.climax_wash(t)
    if cw is not None:
        wa = (cw[0][..., None]) * wall
        out = out * (1 - wa * (1 - cw[1] / 255))
    la = light.a.astype(np.float32)[..., None] / 255 * wall
    lc = light.col.astype(np.float32) * la
    small = cv2.resize(lc, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    glow = cv2.resize(cv2.GaussianBlur(small, (0, 0), 6), (W, H))
    out = out + lc * 0.85 + glow * 1.4

    cl = Wd.Layer()
    draw_contour(cl, mask_lo, t, f)
    ca = cl.a.astype(np.float32)[..., None] / 255
    if ca.any():
        out = out + cl.col.astype(np.float32) * ca * 0.8 + \
            cv2.resize(cv2.GaussianBlur(cv2.resize(cl.col.astype(np.float32) * ca, (W // 4, H // 4)), (0, 0), 4),
                       (W, H)) * 0.8

    black, warm = transition(f)
    climax_glow = 0.1 * Wd.env(t, Wd.K.climax, Wd.K.seated + 0.5, 3, 2)
    out = finish(out, f, climax_glow)
    if warm > 0:
        out = out + np.array([150, 205, 255], np.float32) * warm
    z = camera(t, f)
    if z > 1.0005:
        M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
        out = cv2.warpAffine(out, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if black > 0:
        out = out * (1 - black)
    return np.clip(out, 0, 255).astype(np.uint8), ema


def render_chunk(args):
    k, a, b, prefix = args
    det = face_detector()
    path = os.path.join(WORK, f"{prefix}_{k:02d}.mp4")
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-maxrate", "9M", "-bufsize", "18M", "-pix_fmt", "yuv420p", "-threads", "2", path],
        stdin=subprocess.PIPE)
    scene = max(c for c in (0, SLOW_A, SLOW_B) if c <= a)
    pre = max(scene, a - PREROLL)
    ema = None
    for i, fr in enumerate(read_frames(pre, b)):
        f = pre + i
        if f in (SLOW_A, SLOW_B):
            ema = None
        out, ema = render_frame(fr, f, ema, det)
        if f >= a:
            enc.stdin.write(out.tobytes())
        if f % 150 == 0:
            print(f"{prefix} {k}: frame {f}", flush=True)
    enc.stdin.close()
    enc.wait()
    if enc.returncode:
        raise RuntimeError(f"encoder failed for chunk {k}")
    return path


def main():
    """render_v3.py [start end prefix]  - renders [start, end) in parallel chunks."""
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else N_OUT
    prefix = sys.argv[3] if len(sys.argv) > 3 else "v3chunk"
    nproc = int(os.environ.get("EDIT_PROCS", "4"))
    n = max(1, min(nproc * 2, (b - a) // 30))
    edges = np.linspace(a, b, n + 1).astype(int)
    with Pool(nproc) as pool:
        paths = pool.map(render_chunk, [(k, edges[k], edges[k + 1], prefix) for k in range(n)])
    with open(os.path.join(WORK, f"{prefix}.txt"), "w") as fh:
        for p in paths:
            fh.write(f"file '{p}'\n")
    print("gesture streams:", [(round(s["t0"], 1), s["flower"]) for s in STREAMS])
    print("chunks done")


if __name__ == "__main__":
    main()
