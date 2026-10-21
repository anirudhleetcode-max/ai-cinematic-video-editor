"""v11: 30-second cute doodle music edit on "OK Kanmani" (user-supplied audio).

The reference-reel look (colour intro with glitter stickers; then the girls
cut out in black and white with a sparkly mint outline, on cute illustrated
backgrounds that change on every beat), built as a real edit:
19 footage cuts and cinematic transitions on the song's beats and accents.

  plan()      builds the edit decision list from music.json and writes edl.json
  render_shot renders each shot (plus transition overlaps) into a frame store
  assemble()  applies the transitions and encodes; the audio is the supplied
              MP3, copied unchanged

Reuses v5 backgrounds and intro stickers, v6 animated stickers, v7 stable
outline, v9 neural mattes, and v10 panels, sky, petals, brush wipe and
alpha reader.

Usage: EDIT_WORK=... EDIT_SOURCE=... python3 render_v11.py
"""
import json
import math
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for d in ("..", "../v5", "../v6", "../v7", "../v9", "../v10"):
    sys.path.insert(0, os.path.join(HERE, d))
from common import W, H, WORK, read_frames  # noqa: E402
import render_v5 as v5  # noqa: E402
import render_v6 as v6  # noqa: E402
import render_v10 as v10  # noqa: E402
from render_v7 import outline_field  # noqa: E402

FPS = 30
FRAMES = 900
OUT = os.path.join(WORK, "v11")
os.makedirs(OUT, exist_ok=True)
MUSIC = json.load(open(os.path.join(HERE, "music.json")))
BEATS = np.array(MUSIC["beats_s"])
v6.BEATS = BEATS                                                 # stickers bounce on this song's beats
TEAL, TEAL_D = v5.TEAL, v5.TEAL_D


def fr(t):
    return int(round(t * FPS))


# ---------------------------------------------------------------- edit decision list
# (id, song time of cut-in, source timeline seconds, section, look, description, transition-in, frames before/after)
SHOTS = [
    ("A1", 0.000, 2.00, "intro", "colour", "Calm, both looking into the lens", None),
    ("A2", 1.538, 17.40, "intro", "colour", "Both put their hands to their heads", ("hard_cut", 0, 0, "bar downbeat 1.54 s")),
    ("A3", 2.978, 35.40, "intro", "colour", "Peekaboo: hands over the face (slow punch-in)", ("hard_cut", 0, 0, "bar downbeat 2.98 s")),
    ("B1", 3.512, 35.93, "groove", "cutout", "The reveal: hands open into a smile. It continues A3's moment, so it doubles as a match cut", ("star_iris", 3, 4, "THE DROP, the strongest hit in the song (3.51 s)")),
    ("B2", 5.857, 14.80, "groove", "cutout", "Both laughing into the camera", ("hard_cut", 0, 0, "bar downbeat 5.86 s")),
    ("B3", 7.465, 48.90, "groove", "cutout", "Two hair flips", ("whip_left", 2, 2, "accent 7.47 s")),
    ("B4", 9.816, 31.00, "groove", "cutout", "A wave, a point, a thumbs-up", ("zoom_punch", 0, 5, "accent 9.82 s")),
    ("B5", 11.616, 54.30, "groove", "cutout", "Close-up laugh, arm out", ("hard_cut", 0, 0, "bar downbeat 11.62 s")),
    ("B6", 13.055, 69.90, "groove", "cutout", "Hands fluttering", ("brush_reveal", 6, 3, "bar downbeat 13.06 s")),
    ("B7", 14.478, 38.90, "groove", "cutout", "A finger to the lips", ("hard_cut", 0, 0, "bar downbeat 14.48 s")),
    ("B8", 15.940, 10.40, "groove", "cutout", "Hair flip and a point", ("heart_iris", 3, 4, "bar downbeat 15.94 s")),
    ("B9", 17.369, 56.00, "groove", "cutout", "Hands on her head", ("hard_cut", 0, 0, "bar downbeat 17.37 s")),
    ("B10", 18.814, 103.00, "groove", "cutout", "Standing, dancing gestures", ("whip_up", 2, 2, "bar downbeat 18.81 s")),
    ("B11", 20.242, 75.90, "groove", "cutout", "Pointing to themselves, smiling", ("hard_cut", 0, 0, "bar downbeat 20.24 s")),
    ("C1", 22.390, 82.00, "finale", "cutout", "Slow motion: the reach", ("light_leak", 6, 6, "second big hit (22.39 s), the final section")),
    ("C2", 23.864, 89.30, "finale", "sky", "Slow motion: petals falling", ("dissolve", 3, 3, "beat 23.86 s; a soft change for the most tender shot")),
    ("C3", 25.246, 94.60, "finale", "cutout_soft", "Slow motion: the hug", ("circle_iris", 3, 4, "accent 25.25 s")),
    ("C4", 27.463, 99.20, "finale", "cutout", "Close-up smile", ("hard_cut", 0, 0, "bar downbeat 27.46 s")),
    ("C5", 28.891, 105.60, "outro", "colour_end", "Both smiling to camera, back in colour", ("star_iris", 3, 4, "accent 28.89 s, the last hit")),
]

CUTE_SOFT = [5, 6, 11, 13, 10]                                   # heart rings, pale stars, pink flowers, clouds, watercolour stars
BG_POOL = [f"v5:{i}" for i in range(14)] + [f"p:{i}" for i in range(6)]


def plan():
    shots = []
    for i, (sid, t, src, sec, look, desc, tr) in enumerate(SHOTS):
        start = fr(t)
        end = fr(SHOTS[i + 1][1]) if i + 1 < len(SHOTS) else FRAMES
        shots.append(dict(id=sid, start=start, end=end, src_in=int(round(src * FPS)), section=sec, look=look,
                          desc=desc, src_label=f"{src:.2f}-{src + (end - start) / FPS:.2f} s"))
    trans = []
    for i, (sid, t, src, sec, look, desc, tr) in enumerate(SHOTS):
        if tr:
            trans.append(dict(at=fr(t), frm=SHOTS[i - 1][0], to=sid, type=tr[0], before=tr[1], after=tr[2], reason=tr[3]))
    trans.append(dict(at=FRAMES - 10, type="fade_to_cream", frames=10, reason="the song ends at 29.98 s"))
    # background changes: on every beat in the groove; every beat in C1/C4; every 2 beats with soft
    # backgrounds in the hug; fixed sky in C2
    g = np.random.default_rng(1111)
    order = list(g.permutation(BG_POOL))
    sched, last, oi = [], None, 0
    for sh in shots:
        if sh["look"] not in ("cutout", "cutout_soft"):
            continue
        step = 2 if sh["look"] == "cutout_soft" else 1
        bts = [b for b in BEATS if sh["start"] / FPS - 0.02 < b < sh["end"] / FPS - 0.12]
        changes = [sh["start"]] + [fr(b) for b in bts[step::step] if fr(b) > sh["start"] + 4]
        for j, c in enumerate(changes):
            if sh["look"] == "cutout_soft":
                bg = f"v5:{CUTE_SOFT[j % len(CUTE_SOFT)]}"
            else:
                bg = order[oi % len(order)]
                oi += 1
                if bg == last:
                    bg = order[oi % len(order)]
                    oi += 1
            sched.append(dict(frame=c, shot=sh["id"], bg=bg))
            last = bg
    edl = dict(_doc="v11 edit decision list (frames at 30 fps; output frame k is song time k/30 s). A shot's source frame = src_in + (k - start), on the project timeline in edit/common.py. Generated by render_v11.plan() from music.json.",
               fps=FPS, frames=FRAMES,
               audio=dict(source="OK_Kanmani_Song.mp3 (user upload)", range_s=[0.0, 29.976], offset_s=0.0, processing="none (MP3 stream copied)"),
               shots=shots, transitions=trans, backgrounds=sched)
    json.dump(edl, open(os.path.join(HERE, "edl.json"), "w"), indent=1)
    return edl


EDL = plan()


def shot_range(sh):
    a, b = sh["start"], sh["end"]
    for tr in EDL["transitions"]:
        if tr.get("to") == sh["id"]:
            a = min(a, tr["at"] - tr["before"])
        if tr.get("frm") == sh["id"]:
            b = max(b, tr["at"] + tr["after"])
    return max(0, a), min(FRAMES, b)


# ---------------------------------------------------------------- looks
_bgc = {}


def background(key):
    if key not in _bgc:
        kind, i = key.split(":")
        _bgc[key] = (v5.get_bg(int(i)).astype(np.float32) if kind == "v5" else v10.panel(int(i)).astype(np.float32))
    return _bgc[key]


def bg_at(k, sh):
    cands = [s for s in EDL["backgrounds"] if s["shot"] == sh["id"] and s["frame"] <= max(k, sh["start"])]
    s = cands[-1]
    img = background(s["bg"])
    age = k - s["frame"]
    z = 1.02 + 0.02 * min(1.0, age / 30) + (0.03 * (1 - v10.ease(age / 4.0)) if age >= 0 else 0)   # settle on each change
    M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT), s


def teal_outline(bg, field_on, k):
    band, d = v10.stable_band(field_on, 12, 16)
    sh = np.clip(1 - np.abs(d - 32) / 6, 0, 1) * (d > 27)
    bg = bg * (1 - 0.22 * sh[..., None])                          # soft shadow under the sticker edge
    g = np.random.default_rng(k // 3)                             # glitter re-sparkles every 3 frames
    sp = cv2.resize(g.random((H // 3, W // 3)).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)
    col = TEAL[None, None] * (0.82 + 0.36 * sp[..., None]) + (sp[..., None] > 0.92) * 80
    col = np.where(sp[..., None] < 0.1, TEAL_D[None, None], col)
    rim = (np.clip(1.6 - np.abs(d - 12.8), 0, 1) + np.clip(1.6 - np.abs(d - 27.2), 0, 1)) * 0.55
    col = col * (1 - rim[..., None]) + 255 * rim[..., None]
    a = band[..., None]
    return bg * (1 - a) + np.clip(col, 0, 255) * a


def bw(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return np.repeat(np.clip((g - 128) * 1.12 + 132, 0, 255)[..., None], 3, 2)


def colour_look(img, al, t, k):
    base = v10.grade(img, lift=(4, 3, 2), contrast=1.05, sat=1.05, warm=4)
    st = base.copy()
    v5.stickers_intro(st, t)                                     # glitter stars and gold hearts...
    a = al[..., None]
    return st * (1 - a) + base * a                                # ...tucked behind the girls


def render_shot(sid):
    i = [j for j, s in enumerate(EDL["shots"]) if s["id"] == sid][0]
    sh = EDL["shots"][i]
    a, b = shot_range(sh)
    pre = 12 if sh["look"] in ("cutout", "cutout_soft", "sky") else 0      # outline settles before frame a
    s0 = sh["src_in"] + (a - sh["start"]) - pre
    n = b - a + pre
    frames = list(read_frames(s0, s0 + n))
    alphas = v10.read_alpha(s0, n)
    store = np.lib.format.open_memmap(os.path.join(OUT, f"shot_{sid}.npy"), "w+", np.uint8, (b - a, H, W, 3))
    field = None
    for j in range(n):
        k = a + j - pre
        img, al = frames[j], alphas[j]
        if sh["look"] in ("cutout", "cutout_soft", "sky"):
            field = outline_field((al > 0.5).astype(np.uint8), field)
        if k < a:
            continue
        t_song, t_shot = k / FPS, (k - sh["start"]) / FPS
        if sh["look"] == "colour":
            out = colour_look(img, al, t_song, k)
            if sid == "A3":                                       # slow punch-in toward the drop
                z = 1.0 + 0.06 * v10.ease((k - sh["start"]) / max(1, sh["end"] - sh["start"]))
                M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
                out = cv2.warpAffine(out, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        elif sh["look"] == "colour_end":
            base = v10.grade(img, lift=(4, 3, 2), contrast=1.05, sat=1.05, warm=6)
            st = base.copy()
            v5.stickers_intro(st, max(0.0, t_shot) + 0.2)
            v6.draw_stickers(st, t_song, k, 900 + i, max(0.0, t_shot))
            out = st * (1 - al[..., None]) + base * al[..., None]
        else:
            if sh["look"] == "sky":
                bg = v10.world_sky(max(0.0, t_shot), k)
                v10.draw_petals(bg, max(0.0, t_shot))
            else:
                bg, s = bg_at(k, sh)
                bg = bg.copy()
                v6.draw_stickers(bg, t_song, k, 1000 + EDL["backgrounds"].index(s), max(0.0, (k - s["frame"]) / FPS))
            bg = teal_outline(bg, field[2], k)
            a3 = al[..., None]
            out = bg * (1 - a3) + bw(img) * a3
        store[k - a] = np.clip(out, 0, 255).astype(np.uint8)
    store.flush()
    return sid, a, b


# ---------------------------------------------------------------- transitions
def shape_mask(kind, p, cx=W / 2, cy=H / 2):
    """Iris mask growing from the centre (p 0..1): a crisp star, heart or circle, plus its doodle edge."""
    m = np.zeros((H, W), np.float32)
    edge = np.zeros((H, W), np.float32)
    e = v10.ease(p)
    if kind == "star":
        R = 20 + e * 2300
        pts = v5.star_pts(cx, cy + 0.08 * R, R, 0.0, 0.48)
    elif kind == "heart":
        sc = 15 + e * 1500
        pts = v5.heart_pts(cx, cy + 0.12 * sc, sc)
    else:
        th = np.linspace(0, 2 * math.pi, 120)
        R = 10 + e * 1150
        pts = np.stack([cx + R * np.cos(th), cy + R * np.sin(th)], 1).astype(np.int32)
    cv2.fillPoly(m, [pts], 1.0, cv2.LINE_AA)
    if 0 < p < 1:
        cv2.polylines(edge, [pts], True, 1.0, 14, cv2.LINE_AA)
    return m, edge


def whip(A, B, p, axis):
    s = v10.ease(p)
    shift = int(s * (W if axis == 0 else H))
    k = (61, 1) if axis == 0 else (1, 61)
    Ab, Bb = cv2.blur(A, k), cv2.blur(B, k)
    if axis == 0:
        out = np.zeros_like(A)
        out[:, :W - shift] = Ab[:, shift:]
        out[:, W - shift:] = Bb[:, :shift]
    else:
        out = np.zeros_like(A)
        out[:H - shift] = Ab[shift:]
        out[H - shift:] = Bb[:shift]
    return out


def assemble():
    stores = {}
    for sh in EDL["shots"]:
        a, b = shot_range(sh)
        stores[sh["id"]] = (np.load(os.path.join(OUT, f"shot_{sh['id']}.npy"), mmap_mode="r"), a)

    def get(sid, k):
        arr, a = stores[sid]
        return arr[k - a].astype(np.float32)

    fade = [t for t in EDL["transitions"] if t["type"] == "fade_to_cream"][0]
    cream = v10.PAPER
    tmp = os.path.join(OUT, "v11_video.tmp.mkv")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                            "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    log = []
    for k in range(FRAMES):
        cur = [s for s in EDL["shots"] if s["start"] <= k < s["end"]][0]
        out = get(cur["id"], k)
        for tr in EDL["transitions"]:
            if tr["type"] in ("hard_cut", "fade_to_cream"):
                continue
            lo, hi = tr["at"] - tr["before"], tr["at"] + tr["after"]
            if not (lo <= k < hi):
                continue
            p = (k - lo + 1) / (hi - lo)
            A, B = get(tr["frm"], k), get(tr["to"], k)
            ty = tr["type"]
            if ty in ("star_iris", "heart_iris", "circle_iris"):
                m, edge = shape_mask(ty.split("_")[0], p)
                out = A * (1 - m[..., None]) + B * m[..., None]
                ring = cv2.GaussianBlur(edge, (0, 0), 1.2)[..., None]
                out = out * (1 - ring) + (TEAL * 0.4 + 255 * 0.6)[None, None] * ring       # minty-white doodle edge
            elif ty == "brush_reveal":
                m, band = v10.brush_mask(p)
                out = A * (1 - m[..., None]) + B * m[..., None]
                out = out * (1 - band[..., None] * 0.9) + v10.PAPER[None, None] * band[..., None] * 0.9
            elif ty in ("whip_left", "whip_up"):
                out = whip(A, B, p, 0 if ty == "whip_left" else 1)
            elif ty == "zoom_punch":
                z = 1.14 - 0.14 * v10.ease(p)
                M = np.array([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]], np.float32)
                zb = cv2.warpAffine(B, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                z2 = z + 0.02 * (1 - p)
                M2 = np.array([[z2, 0, (1 - z2) * W / 2], [0, z2, (1 - z2) * H / 2]], np.float32)
                out = zb * 0.6 + cv2.warpAffine(B, M2, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT) * 0.4
            elif ty == "dissolve":
                out = A * (1 - p) + B * p
            elif ty == "light_leak":
                src = A if k < tr["at"] else B
                d = (k - tr["at"] + 0.5) / (tr["before"] if k < tr["at"] else tr["after"])
                lvl = 0.6 * (1 - abs(d)) ** 1.4
                yy, xx = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4
                rad = cv2.resize(np.exp(-np.hypot(xx - W * 0.85, yy - H * 0.1) / 1300).astype(np.float32), (W, H))[..., None]
                out = src + v10.hexc("#ffc98a")[None, None] * rad * lvl + (255 - src) * rad * lvl * 0.3
        if k >= fade["at"]:
            q = (k - fade["at"] + 1) / fade["frames"]
            out = out * (1 - q) + cream[None, None] * q
        enc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
        log.append((k, cur["id"], cur["src_in"] + k - cur["start"]))
    enc.stdin.close()
    enc.wait()
    os.replace(tmp, os.path.join(OUT, "v11_video.mkv"))
    json.dump(log, open(os.path.join(OUT, "frame_log.json"), "w"))
    return os.path.join(OUT, "v11_video.mkv")


def main():
    v5.build_backgrounds()
    want = sys.argv[1:] or [s["id"] for s in EDL["shots"]]
    with Pool(4) as pool:
        for sid, a, b in pool.imap_unordered(render_shot, want):
            print("shot", sid, a, b, flush=True)
    if not sys.argv[1:]:
        print("assembled", assemble())


if __name__ == "__main__":
    main()
