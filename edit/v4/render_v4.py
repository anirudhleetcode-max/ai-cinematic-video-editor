"""v4 compositor and chunked renderer.

Depth order (back to front), each with an explicit blend policy:
   1  graded footage (wall plate)                         -
   2  distant scenery: sky, hills, clouds, stars           ink: MULTIPLY / light: ADD
   3  blue paint strokes                                  pigment: OVER
   4  illustrated landscape, tree, characters, lanterns    ink: MULTIPLY / light: ADD
   5  white scribbles                                     OVER (with ink shadow)
   6  auras, gold particles                               light: ADD
      (layers 2-6 are cut out behind the people with a feathered matte)
   7  people (the original pixels, untouched apart from grade/softening)
   8  white silhouette outline                            OVER + restrained glow
   9  filmic finishing: halation, diffusion, vignette, grain
"""
import hashlib
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
import engine as E  # noqa: E402  (sets up paths, loads config + timeline)

CFG = E.CFG
os.environ["EDIT_SAT"] = str(CFG["segmentation"]["saturation_threshold"])
os.environ["EDIT_DARK_V"] = str(CFG["segmentation"]["dark_threshold"])
import common  # noqa: E402
from common import N_OUT, SLOW_A, SLOW_B, WORK, person_mask, read_frames  # noqa: E402
import render_v3 as R3  # noqa: E402  (grade, skin softening, gesture streams)

Wd = E.Wd
Wd.CHAR_SCALE = CFG["world"]["character_scale"]
W, H, FPS = E.W, E.H, E.FPS
MW = CFG["segmentation"]["mask_width"]
MH = MW * 9 // 16
AN = np.load(os.path.join(WORK, "v3_analysis.npz"))
FACES = AN["faces"]
TRACK = E.track_faces(FACES, {SLOW_A, SLOW_B})
FXE = E.FX(CFG, E.TL, TRACK)
PAINT = E.PaintStrokeEngine(CFG, E.TL)
OUTLINE = E.ContourEngine(CFG)
PREROLL = 6


def face_ellipses(mask, faces, scale):
    """Fill the face interior (skin can fall below the saturation threshold) -
    kept inside the face box so it never pushes the matte out onto the wall."""
    kx, ky = CFG["segmentation"]["face_ellipse_scale"]
    for x, y, w, h in faces:
        if w <= 0:
            continue
        cx, cy = (x + w / 2) * scale, (y + h / 2) * scale
        cv2.ellipse(mask, (int(cx), int(cy)), (int(w * kx * scale), int(h * ky * scale)), 0, 0, 360, 255, -1)
    return mask
_gr = np.random.default_rng(CFG["render"]["seed"])
GRAIN = [_gr.normal(0, 1.0, (H, W)).astype(np.float32) for _ in range(5)]


def finish(out, f, extra=0.0):
    g = CFG["grade"]
    small = cv2.resize(out, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    lum = small.mean(2, keepdims=True)
    hi = np.clip((lum - 195) / 60, 0, 1)
    halo = cv2.GaussianBlur(small * hi, (0, 0), 7) * np.array([0.55, 0.75, 1.0], np.float32)
    out = out + cv2.resize(halo, (W, H)) * (g["halation"] + extra)
    k = g["diffusion"] + extra * 0.15
    diff = cv2.GaussianBlur(small, (0, 0), 16)
    out = 255 - (255 - out) * (1 - k * cv2.resize(diff, (W, H)) / 255)
    out *= R3.VIGNETTE
    out += (GRAIN[f % len(GRAIN)] * (1.5 + 1.1 * (1 - np.clip(out.mean(2) / 255, 0, 1))))[..., None]
    return out


def bbox(*alphas):
    occ = alphas[0]
    for a in alphas[1:]:
        occ = cv2.max(occ, a)
    x, y, w, h = cv2.boundingRect(occ)
    if w == 0:
        return None
    m = 48
    x0, y0 = max(0, x - m) // 4 * 4, max(0, y - m) // 4 * 4
    x1, y1 = min(W, (x + w + m + 3) // 4 * 4), min(H, (y + h + m + 3) // 4 * 4)
    return slice(y0, y1), slice(x0, x1)


def glow(img, sigma):
    h, w = img.shape[:2]
    s = cv2.resize(img, (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_AREA)
    return cv2.resize(cv2.GaussianBlur(s, (0, 0), sigma), (w, h))


def render_frame(img, f, ema):
    t = f / FPS
    seg = CFG["segmentation"]
    # -- 7: people matte (refined colour segmentation at 960x540 + face ellipses)
    m = person_mask(cv2.resize(img, (MW, MH), interpolation=cv2.INTER_AREA))
    m = face_ellipses(m, FACES[f], MW / 1920).astype(np.float32) / 255
    a_ema = seg["temporal_ema"]
    ema = m if ema is None else a_ema * ema + (1 - a_ema) * m
    mask = (ema > 0.5).astype(np.uint8) * 255
    keep = cv2.GaussianBlur(cv2.resize(mask, (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), seg["matte_feather_px"])

    # -- 1: graded plate
    base = R3.grade(R3.soften_skin(img, mask))

    # -- 2-6: the illustrated world and its effects
    ink, light = Wd.render_world(t)
    R3.draw_streams(light, t)
    FXE.stars(ink, light, t)
    FXE.particles(light, t)
    FXE.aura(light, ink, t, f)
    body, paint, white = Wd.Layer(), Wd.Layer(), Wd.Layer()
    PAINT.draw(body, paint, light, t)
    FXE.scribbles(white, ink, t)

    out = base
    cw = Wd.climax_wash(t)
    if cw is not None:
        wa = cw[0][..., None] * (1 - keep.astype(np.float32)[..., None] / 255)
        out = out * (1 - wa * (1 - cw[1] / 255))
    sl = bbox(body.a, paint.a, ink.a, light.a, white.a)
    if sl is not None:
        wall = (1 - keep[sl].astype(np.float32) / 255)[..., None]
        roi = out[sl]
        ba = body.a[sl].astype(np.float32)[..., None] / 255 * wall
        roi = roi * (1 - ba * (1 - body.col[sl].astype(np.float32) / 255))                  # 3 paint wash multiply
        pa = paint.a[sl].astype(np.float32)[..., None] / 255 * wall
        roi = roi * (1 - pa) + paint.col[sl].astype(np.float32) * pa                       # 3 bristles over
        ia = ink.a[sl].astype(np.float32)[..., None] / 255 * wall
        roi = roi * (1 - ia * (1 - ink.col[sl].astype(np.float32) / 255))                   # 2/4 ink multiply
        la = light.a[sl].astype(np.float32)[..., None] / 255 * wall
        lc = light.col[sl].astype(np.float32) * la
        roi = roi + lc * 0.85 + glow(lc, 6) * 1.4                                          # 6 light add
        wa_ = white.a[sl].astype(np.float32)[..., None] / 255 * wall
        roi = roi * (1 - wa_) + white.col[sl].astype(np.float32) * wa_
        out[sl] = roi

    # -- 8: white outline above the people
    oa = E.TL.outline_alpha(t)
    if oa > 0 and CFG["outline"]["enabled"]:
        ow, osh = Wd.Layer(), Wd.Layer()
        small = cv2.GaussianBlur(cv2.resize(img, (W // 2, H // 2), interpolation=cv2.INTER_AREA), (0, 0), 1.5)
        OUTLINE.draw(ow, osh, mask, W / MW, t, oa, E.TL.outline_redraw(t), small)
        so = bbox(ow.a, osh.a)
        if so is not None:
            sa = osh.a[so].astype(np.float32)[..., None] / 255
            roi = out[so] * (1 - sa * (1 - osh.col[so].astype(np.float32) / 255))
            wa_ = ow.a[so].astype(np.float32)[..., None] / 255
            wc = ow.col[so].astype(np.float32)
            roi = roi * (1 - wa_) + wc * wa_ + glow(wc * wa_, 1.0) * CFG["outline"]["glow"]
            out[so] = roi

    # -- 9: finishing
    climax = 0.08 * Wd.env(t, Wd.K.climax, Wd.K.seated + 0.5, 3, 2)
    out = finish(out, f, climax)
    black, warm = R3.transition(f)
    if warm > 0:
        out = out + np.array([150, 205, 255], np.float32) * warm
    if SLOW_A <= f < SLOW_B:                       # slow push-in only inside the slow-motion hug
        z = 1.0 + 0.04 * Wd.ease((f - SLOW_A) / (SLOW_B - SLOW_A))
        M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
        out = cv2.warpAffine(out, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if black > 0:
        out = out * (1 - black)
    return np.clip(out, 0, 255).astype(np.uint8), ema


# ---------------------------------------------------------------- chunked, resumable rendering
def render_chunk(args):
    k, a, b, prefix = args
    path = os.path.join(WORK, f"{prefix}_{k:02d}.mp4")
    done = path + ".done"
    if os.path.exists(done) and os.path.exists(path):
        with open(done) as fh:
            if fh.read().strip() == f"{a}-{b}":
                print(f"{prefix} {k}: cached", flush=True)
                return path
    r = CFG["render"]
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", str(r["master_crf"]),
         "-maxrate", r["master_maxrate"], "-bufsize", "24M", "-pix_fmt", "yuv420p", "-threads", "2", path],
        stdin=subprocess.PIPE)
    scene = max(c for c in (0, SLOW_A, SLOW_B) if c <= a)
    pre = max(scene, a - PREROLL)
    ema = None
    for i, fr in enumerate(read_frames(pre, b)):
        f = pre + i
        if f in (SLOW_A, SLOW_B):
            ema = None
        out, ema = render_frame(fr, f, ema)
        if f >= a:
            enc.stdin.write(out.tobytes())
        if f % 150 == 0:
            print(f"{prefix} {k}: frame {f}", flush=True)
    enc.stdin.close()
    enc.wait()
    if enc.returncode:
        raise RuntimeError(f"encoder failed for chunk {k}")
    with open(done, "w") as fh:
        fh.write(f"{a}-{b}")
    return path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def manifest(path_out):
    src = os.environ.get("EDIT_SOURCE", common.SOURCE)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration,size:stream=codec_name,width,height,r_frame_rate,sample_rate,channels",
                            "-of", "json", src], capture_output=True, text=True).stdout
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=HERE).stdout.strip()
    except Exception:
        commit = "unknown"
    m = dict(source=src, source_sha256=sha256(src), source_probe=json.loads(probe), git_commit_at_render=commit,
             config=CFG, timeline_sha256=sha256(os.path.join(HERE, "timeline.json")),
             face_model="face_detection_yunet_2023mar.onnx",
             face_model_sha256=sha256(os.path.join(HERE, "..", "v3", "assets", "face_detection_yunet_2023mar.onnx")),
             opencv=cv2.__version__, numpy=np.__version__, frames=N_OUT, fps=FPS,
             slow_motion_window=[SLOW_A, SLOW_B], beats_file="beats.json")
    with open(path_out, "w") as fh:
        json.dump(m, fh, indent=2)


def main():
    """render_v4.py [start end prefix] - parallel chunks over [start, end)."""
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else N_OUT
    prefix = sys.argv[3] if len(sys.argv) > 3 else "v4chunk"
    r = CFG["render"]
    nproc = min(int(r["workers"]), os.cpu_count() or 1)
    n = max(1, min(int(r["chunks"]), (b - a) // 30))
    edges = np.linspace(a, b, n + 1).astype(int)
    with Pool(nproc) as pool:
        paths = pool.map(render_chunk, [(k, edges[k], edges[k + 1], prefix) for k in range(n)])
    with open(os.path.join(WORK, f"{prefix}.txt"), "w") as fh:
        for p in paths:
            fh.write(f"file '{p}'\n")
    print("chunks done")


if __name__ == "__main__":
    main()
