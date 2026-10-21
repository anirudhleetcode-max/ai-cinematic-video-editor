"""Pass 1: analyse footage + audio and plan every doodle event (deterministic)."""
import json
import os
import subprocess

import cv2
import numpy as np

from common import (FPS, N_OUT, SLOW_A, SLOW_B, SOURCE, WORK, person_mask,
                    read_frames)

LW, LH = 240, 135          # analysis resolution (1/8)
SC = 1920 / LW
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- footage
def analyse_video():
    masks = np.zeros((N_OUT, LH, LW), np.uint8)
    motion = np.zeros((N_OUT, 2), np.float32)    # left / right person head band
    top = np.zeros((N_OUT, 2, 2), np.float32)    # topmost mask point per half
    prev = None
    ema = None
    for i, fr in enumerate(read_frames(0, N_OUT, LW, LH)):
        m = person_mask(fr).astype(np.float32) / 255
        if i in (0, SLOW_A, SLOW_B) or ema is None:
            ema = m
        else:
            ema = 0.5 * ema + 0.5 * m
        mb = (ema > 0.5).astype(np.uint8)
        masks[i] = mb
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None and i not in (SLOW_A, SLOW_B):
            d = np.abs(g - prev) * mb
            d[LH // 2:] = 0                       # heads / raised hands only
            motion[i, 0] = d[:, :LW // 2].mean()
            motion[i, 1] = d[:, LW // 2:].mean()
        prev = g
        for h in range(2):
            sub = mb[:, h * LW // 2:(h + 1) * LW // 2]
            ys, xs = np.nonzero(sub)
            if len(ys):
                j = np.argmin(ys)
                top[i, h] = (xs[j] + h * LW // 2, ys[j])
            else:
                top[i, h] = (h * LW // 2 + LW // 4, LH)
    return masks, motion, top


# ---------------------------------------------------------------- audio
def analyse_audio():
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SOURCE, "-ac", "1", "-ar", "22050",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    sr, hop, n = 22050, 512, 2048
    nfr = (len(a) - n) // hop
    win = np.hanning(n).astype(np.float32)
    idx = np.arange(n)[None, :] + hop * np.arange(nfr)[:, None]
    mag = np.log1p(np.abs(np.fft.rfft(a[idx] * win, axis=1)) * 10)
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(1)
    flux = np.concatenate([[0], flux])
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    env_fps = sr / hop
    rms = np.sqrt((a[idx] ** 2).mean(1))
    # tempo by autocorrelation (70-180 bpm)
    f = flux - flux.mean()
    ac = np.correlate(f, f, "full")[len(f) - 1:]
    lags = np.arange(len(ac)) / env_fps
    ok = (lags > 60 / 180) & (lags < 60 / 70)
    period = lags[ok][np.argmax(ac[ok])]
    step = period * env_fps
    best, best_off = -1e9, 0
    for off in np.arange(0, step, 0.5):
        pos = (off + step * np.arange(int(len(flux) / step))).astype(int)
        s = flux[pos[pos < len(flux)]].sum()
        if s > best:
            best, best_off = s, off
    grid = best_off + step * np.arange(int(len(flux) / step))
    beats = []
    for g in grid:
        lo, hi = int(max(0, g - 0.05 * env_fps)), int(min(len(flux), g + 0.05 * env_fps + 1))
        if hi > lo:
            beats.append((lo + np.argmax(flux[lo:hi])) / env_fps)
    beats = np.array(beats)
    # downbeat phase = beat phase (mod 4) with the most onset energy
    bi = np.clip((beats * env_fps).astype(int), 0, len(flux) - 1)
    phase = int(np.argmax([flux[bi[k::4]].sum() for k in range(4)]))
    # per-video-frame loudness (dB) and onset strength
    t_env = np.arange(len(rms)) / env_fps
    t_vid = np.arange(N_OUT) / FPS
    loud = np.interp(t_vid, t_env, 20 * np.log10(rms + 1e-6))
    onset = np.interp(t_vid, t_env, flux)
    return dict(bpm=60 / period, beats=beats.tolist(), downbeat_phase=phase,
                loud=loud.tolist(), onset=onset.tolist())


# ---------------------------------------------------------------- planning
def forbid_stack(masks):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    return np.stack([cv2.dilate(m, k) for m in masks])


def overlap(forbid, path_fn, f0, life, radius):
    """Fraction of sampled frames where a sprite of `radius` px touches a person."""
    hits = 0
    samples = 0
    r = max(1, int(radius / SC))
    for f in range(f0, min(N_OUT, f0 + life), 3):
        x, y = path_fn(f - f0)
        xi, yi = int(x / SC), int(y / SC)
        samples += 1
        if xi < -r or xi >= LW + r or yi < -r or yi >= LH + r:
            continue
        x0, x1 = max(0, xi - r), min(LW, xi + r + 1)
        y0, y1 = max(0, yi - r), min(LH, yi + r + 1)
        if x1 > x0 and y1 > y0 and forbid[f, y0:y1, x0:x1].any():
            hits += 1
    return hits / max(1, samples)


def linear(p0, v, a=(0, 0)):
    return lambda df: (p0[0] + v[0] * df / FPS + 0.5 * a[0] * (df / FPS) ** 2,
                       p0[1] + v[1] * df / FPS + 0.5 * a[1] * (df / FPS) ** 2)


def band_points(mask_lo, inner=3, outer=7):
    k1 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * inner + 1, 2 * inner + 1))
    k2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * outer + 1, 2 * outer + 1))
    band = cv2.dilate(mask_lo, k2) - cv2.dilate(mask_lo, k1)
    ys, xs = np.nonzero(band)
    return xs * SC, ys * SC


def density(t):
    """Decoration density 0..1 — rich and clean moments alternate."""
    if t < 2.5:
        return 0.25
    if 18.5 <= t < 28:      # near-silent break in the song: keep it clean
        return 0.1
    if t < 18.5:
        return 0.5
    if t < 50:
        return 0.6
    if t < SLOW_A / FPS:
        return 0.85
    if t < SLOW_B / FPS:
        return 0.7
    return 1.0


def plan(masks, motion, top, audio):
    forbid = forbid_stack(masks)
    ev = []

    def add(kind, f0, life, path, radius, tries=8, max_ov=0.25, **kw):
        best = None
        for _ in range(tries):
            p = path()
            o = overlap(forbid, linear(*p), f0, life, radius)
            if best is None or o < best[0]:
                best = (o, p)
            if o == 0:
                break
        if best[0] <= max_ov:
            p0, v, acc = best[1]
            ev.append(dict(kind=kind, f0=int(f0), life=int(life), p0=list(map(float, p0)),
                           v=list(map(float, v)), a=list(map(float, acc)), **kw))
            return True
        return False

    def free_point(f, margin=60):
        return (rng.uniform(margin, 1920 - margin), rng.uniform(margin, 1080 - margin))

    beats = np.array(audio["beats"])
    ph = audio["downbeat_phase"]
    end_t = N_OUT / FPS - 1.0

    # 1. beat sparkles hugging the silhouettes
    for k, bt in enumerate(beats):
        if bt < 0.6 or bt > end_t:
            continue
        f = int(bt * FPS)
        d = density(bt)
        if rng.random() > d:
            continue
        xs, ys = band_points(masks[f])
        if not len(xs):
            continue
        for _ in range(1 + int(rng.random() < d) + int(k % 4 == ph)):
            j = rng.integers(len(xs))
            add("sparkle", f, int(FPS * rng.uniform(0.45, 0.8)),
                lambda j=j: ((xs[j] + rng.normal(0, 10), ys[j] + rng.normal(0, 10)), (0, -20), (0, 0)),
                18, tries=1, max_ov=0.5, size=float(rng.uniform(14, 26)),
                color=int(rng.integers(0, 5)), beat=True)

    # 2. downbeat floaters: hearts, notes, stars drifting up
    kinds = ["heart", "note", "star5", "heart", "note", "heart_wing", "dheart"]
    for k, bt in enumerate(beats):
        if k % 4 != ph or bt < 1.5 or bt > end_t - 2:
            continue
        f = int(bt * FPS)
        d = density(bt)
        if rng.random() > d * 0.9:
            continue
        kind = kinds[rng.integers(len(kinds))]
        life = int(FPS * rng.uniform(2.4, 3.6))
        size = float(rng.uniform(30, 52))
        slow = SLOW_A <= f < SLOW_B
        vy = -rng.uniform(40, 80) * (0.6 if slow else 1)
        add(kind, f, life,
            lambda: (free_point(f), (rng.uniform(-25, 25), vy), (0, 0)),
            size, size=size, color=int(rng.integers(0, 7)), rot=float(rng.uniform(-0.4, 0.4)))

    # 3. motion reactions: head turns / hair flips -> sparkles at head edge;
    #    raised hands -> little star trail following the topmost point
    last = [-99, -99]
    last_trail = [-99, -99]
    thr = np.percentile(motion[motion > 0], 90) if (motion > 0).any() else 1
    for f in range(1, N_OUT - 20):
        t = f / FPS
        for h in range(2):
            if motion[f, h] > thr and f - last[h] > 12 and rng.random() < density(t) + 0.2:
                last[h] = f
                xs, ys = band_points(masks[f])
                sel = (xs >= h * 960) & (xs < (h + 1) * 960)
                if sel.sum() == 0:
                    continue
                xs2, ys2 = xs[sel], ys[sel]
                order = np.argsort(ys2)[:max(1, len(ys2) // 5)]   # upper part = head
                for _ in range(3):
                    j = order[rng.integers(len(order))]
                    add("sparkle", f + int(rng.integers(0, 6)), int(FPS * 0.6),
                        lambda j=j: ((xs2[j], ys2[j]), (rng.normal(0, 30), rng.normal(-30, 15)), (0, 0)),
                        16, tries=1, max_ov=0.6, size=float(rng.uniform(12, 22)),
                        color=int(rng.integers(0, 5)))
            if f >= 3 and f - last_trail[h] > 30 and f not in range(SLOW_A, SLOW_A + 4) \
                    and f not in range(SLOW_B, SLOW_B + 4):
                dy = top[f - 3, h, 1] - top[f, h, 1]
                if dy * SC > 60 and top[f, h, 1] * SC < 500:
                    last_trail[h] = f
                    x, y = top[f, h] * SC
                    for s in range(6):
                        add("star4", f + s, int(FPS * 0.7),
                            lambda s=s: ((x + rng.normal(0, 18), y - 30 + s * 14), (0, -15), (0, 0)),
                            12, tries=1, max_ov=1.0, size=float(16 - s * 1.5),
                            color=int([4, 0, 6, 1, 4, 2][s]))

    # 4. both vibing together -> a matching pair of hearts between them
    lastpair = -999
    both = np.minimum(motion[:, 0], motion[:, 1])
    bthr = np.percentile(both[both > 0], 85) if (both > 0).any() else 1
    for f in range(30, N_OUT - 90):
        if both[f] > bthr and f - lastpair > 4 * FPS and density(f / FPS) > 0.3:
            col = masks[f].sum(0).astype(float)
            mid = slice(LW // 3, 2 * LW // 3)
            cx = (LW // 3 + np.argmin(col[mid])) * SC
            ok1 = add("heart", f, 75, lambda: ((cx - 34, rng.uniform(380, 640)), (-8, -55), (0, 0)),
                      26, tries=6, size=30.0, color=0, rot=-0.25)
            if ok1:
                p = ev[-1]["p0"]
                ev.append(dict(ev[-1], p0=[p[0] + 68, p[1] - 10], v=[8, -55], color=3, rot=0.25))
                lastpair = f

    # 5. whimsical fish crossing empty wall areas
    for t0, n_fish in [(31.5, 1), (58.0, 2), (72.0, 1), (104.5, 2)]:
        f = int(t0 * FPS)
        life = int(7.5 * FPS)
        direction = 1 if rng.random() < 0.5 else -1
        x0 = -120 if direction > 0 else 2040
        vx = direction * 2160 / (life / FPS)
        for i in range(n_fish):
            ok = add("fish", f + i * 10, life,
                     lambda i=i: ((x0 - direction * i * 150, rng.uniform(70, 420) + i * 60), (vx, rng.uniform(-8, 8)), (0, 0)),
                     45, tries=24, max_ov=0.35, size=float(46 - i * 10),
                     color=int([2, 0, 4][i % 3]), dir=direction)
            if not ok:
                break

    # 6. butterflies — the slow-motion hug and a couple of other moments
    for t0, count in [(44.0, 1), (SLOW_A / FPS + 1.0, 3), (108.0, 1)]:
        for i in range(count):
            f = int((t0 + i * 2.2) * FPS)
            add("butterfly", f, int(6 * FPS),
                lambda: (free_point(f, 150), (rng.uniform(-90, 90), rng.uniform(-60, -20)), (0, 0)),
                40, tries=16, max_ov=0.35, size=float(rng.uniform(34, 46)),
                color=int(rng.integers(0, 4)))

    # 7. celestial corner doodles that bob for a while
    for t0, dur, kind, corner in [(29.0, 9.0, "moon", "tl"), (52.0, 9.0, "planet", "tr"),
                                  (66.0, 8.0, "moon", "tr"), (101.5, 10.0, "planet", "tl"),
                                  (2.0, 5.0, "daisy", "tr"), (40.0, 6.0, "daisy", "tl"),
                                  (SLOW_A / FPS + 0.5, 8.0, "moon", "tr")]:
        f = int(t0 * FPS)
        x = 150 if corner == "tl" else 1770
        add(kind, f, int(dur * FPS), lambda: ((x + rng.normal(0, 25), rng.uniform(110, 180)), (0, 0), (0, 0)),
            60, tries=10, max_ov=0.3, size=58.0, color=int(rng.integers(0, 6)))

    # 8. shooting stars on transitions and the biggest onsets
    onset = np.array(audio["onset"])
    big = [f for f in range(60, N_OUT - 60) if onset[f] > np.percentile(onset, 99.6)]
    sel = []
    for f in big:
        if not sel or f - sel[-1] > 6 * FPS:
            sel.append(f)
    for f in sorted(set(sel + [SLOW_A - 6, SLOW_B - 6])):
        direction = 1 if rng.random() < 0.5 else -1
        add("shooting", f, 22,
            lambda: ((960 - direction * 1100, rng.uniform(60, 260)), (direction * 2600, 380), (0, 0)),
            30, tries=8, max_ov=1.0, size=34.0, color=4, dir=direction)

    # 9. handwritten captions (scene-based, no lyrics are claimed)
    texts = [(1.0, 4.2, "two voices, one vibe"),
             (SLOW_A / FPS + 2.0, 6.0, "bestie moments"),
             (N_OUT / FPS - 4.6, 3.6, "on repeat")]
    for t0, dur, s in texts:
        f = int(t0 * FPS)
        life = int(dur * FPS)
        cands = [(x, y) for y in (70, 110, 150) for x in (60, 1180)]
        best = None
        for c in cands:
            o = overlap(forbid, linear((c[0] + 330, c[1] + 40), (0, 0)), f, life, 330)
            if best is None or o < best[0]:
                best = (o, c)
        ev.append(dict(kind="text", f0=f, life=life, p0=list(map(float, best[1])), v=[0, 0], a=[0, 0],
                       text=s, size=96.0, color=0))
    ev.sort(key=lambda e: e["f0"])
    return ev


def main():
    os.makedirs(WORK, exist_ok=True)
    audio = analyse_audio()
    print(f"bpm {audio['bpm']:.1f}, {len(audio['beats'])} beats")
    masks, motion, top = analyse_video()
    events = plan(masks, motion, top, audio)
    kinds = {}
    for e in events:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print("events", kinds)
    with open(os.path.join(WORK, "plan.json"), "w") as fh:
        json.dump(dict(audio=dict(bpm=audio["bpm"], beats=audio["beats"],
                                  downbeat_phase=audio["downbeat_phase"]),
                       events=events), fh)


if __name__ == "__main__":
    main()
