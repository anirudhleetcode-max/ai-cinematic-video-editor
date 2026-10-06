#!/usr/bin/env python3
"""FAILATHON AV - automated beat-synced mass edit.

Runs on Windows / macOS / Linux. Needs: Python 3.9+, ffmpeg + ffprobe on PATH,
numpy, Pillow. librosa is optional (better beat tracking).

    python failathon_autoedit.py --media "C:\\path\\to\\Ecellfailthon" --bgm "C:\\path\\to\\bgm.mp3"

Outputs (under --workspace, default = the FAILATHON_AV folder this script lives in):
    07_EXPORTS/FAILATHON_AV_FINAL.mp4        final 1080p H.264 + AAC
    06_PREVIEWS/FAILATHON_AV_PREVIEW.mp4     540p preview
    06_PREVIEWS/CONTACT_SHEET.jpg            thumbnail index of every source
    03_RESOLVE/FAILATHON_AV_FINAL.fcpxml     timeline for Resolve (File > Import > Timeline)
    03_RESOLVE/FAILATHON_AV_FINAL.edl        CMX3600 EDL of the V1 cut
    03_RESOLVE/edit_plan.json                consumed by FAILATHON_AV_RESOLVE_SCRIPT.py
    03_RESOLVE/media/                        graded shot renders, titles, SFX, BGM copy
    09_REPORTS/MEDIA_MANIFEST.csv, BEAT_MAP.csv, EDIT_REPORT.md, VALIDATION_REPORT.md

Source media is only ever read, never modified.
"""
import argparse, csv, json, math, os, random, re, shutil, subprocess, sys, time, wave
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H, FPS = 1920, 1080, 30
SR = 48000
VIDEO_EXT = {'.mp4', '.mov', '.m4v', '.mkv', '.avi', '.mts', '.m2ts', '.3gp', '.webm', '.wmv', '.mpg', '.mpeg'}
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.heic', '.webp', '.bmp', '.tif', '.tiff'}
T0 = time.time()


def log(msg):
    el = time.time() - T0
    print(f"[{int(el // 60):02d}:{int(el % 60):02d}] {msg}", flush=True)


def run(cmd, **kw):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed ({r.returncode}): {' '.join(map(str, cmd))[:400]}\n{r.stderr.decode(errors='ignore')[-1500:]}")
    return r.stdout


def ffprobe(path):
    out = run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', str(path)])
    return json.loads(out)


# --------------------------------------------------------------------------- inventory
def capture_time(path, probe, kind):
    if kind == 'image':
        try:
            ex = Image.open(path).getexif()
            v = ex.get_ifd(0x8769).get(36867) or ex.get(306)
            if v:
                return datetime.strptime(str(v)[:19], '%Y:%m:%d %H:%M:%S').timestamp()
        except Exception:
            pass
    tags = (probe or {}).get('format', {}).get('tags', {}) if probe else {}
    ct = tags.get('creation_time') or tags.get('com.apple.quicktime.creationdate')
    if ct:
        try:
            return datetime.fromisoformat(ct.replace('Z', '+00:00')).timestamp()
        except Exception:
            pass
    m = re.search(r'(20\d{2})(\d{2})(\d{2})[_-]?(\d{2})(\d{2})(\d{2})', path.name)
    if m:
        try:
            return datetime(*map(int, m.groups())).timestamp()
        except Exception:
            pass
    return path.stat().st_mtime


def inventory(media_dir):
    items = []
    for p in sorted(Path(media_dir).rglob('*')):
        if not p.is_file() or p.name.startswith('.'):
            continue
        ext = p.suffix.lower()
        kind = 'video' if ext in VIDEO_EXT else 'image' if ext in IMAGE_EXT else None
        if not kind:
            continue
        it = dict(path=str(p), name=p.name, rel=str(p.relative_to(media_dir)), kind=kind,
                  size_mb=round(p.stat().st_size / 1e6, 2), status='ok', note='')
        try:
            pr = ffprobe(p)
            vs = next((s for s in pr['streams'] if s['codec_type'] == 'video'), None)
            if not vs:
                raise RuntimeError('no video stream')
            w, h = int(vs['width']), int(vs['height'])
            rot = 0
            for sd in vs.get('side_data_list', []) or []:
                if 'rotation' in sd:
                    rot = int(float(sd['rotation']))
            rot = int(vs.get('tags', {}).get('rotate', rot) or 0)
            if abs(rot) % 180 == 90:
                w, h = h, w
            num, den = (vs.get('avg_frame_rate') or '0/1').split('/')
            fps = float(num) / float(den) if float(den) else 0.0
            dur = float(pr['format'].get('duration') or vs.get('duration') or 0) if kind == 'video' else 0.0
            it.update(width=w, height=h, fps=round(fps, 3), codec=vs.get('codec_name'), duration=round(dur, 3),
                      audio=any(s['codec_type'] == 'audio' for s in pr['streams']),
                      orientation='portrait' if h > w else 'landscape' if w > h else 'square',
                      ctime=capture_time(p, pr, kind))
            if kind == 'video' and dur < 0.4:
                it.update(status='reject', note='too short')
        except Exception as e:
            it.update(status='broken', note=str(e).splitlines()[0][:120], width=0, height=0, fps=0, codec='',
                      duration=0, audio=False, orientation='', ctime=p.stat().st_mtime)
        items.append(it)
    return items


# --------------------------------------------------------------------------- analysis
def dhash(gray):
    im = Image.fromarray(gray).resize((9, 8), Image.BILINEAR)
    a = np.asarray(im, dtype=np.int16)
    return int(''.join('1' if b else '0' for b in (a[:, 1:] > a[:, :-1]).flatten()), 2)


def hamming(a, b):
    return bin(a ^ b).count('1')


def lap_var(g):
    g = g.astype(np.float32)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def analyze(it, thumbs_dir):
    """Cheap per-clip analysis: keyframes at 2 fps, 192x108 grey."""
    sw, sh = 192, 108
    p = it['path']
    try:
        if it['kind'] == 'video':
            def grab(fast):
                pre = ['-skip_frame', 'nokey'] if fast else []
                raw = run(['ffmpeg', '-v', 'error', '-threads', '2'] + pre + ['-i', p, '-t', '180',
                           '-vf', f'fps=2,scale={sw}:{sh}:flags=area,format=gray', '-f', 'rawvideo', '-'])
                return np.frombuffer(raw, np.uint8)
            # long clips: keyframes only (fast); short clips or long-GOP files: full decode
            fr = grab(True) if it['duration'] > 60 else np.zeros(0, np.uint8)
            n = len(fr) // (sw * sh)
            if n < max(2, it['duration'] * 1.5):
                fr = grab(False)
                n = len(fr) // (sw * sh)
            if n == 0:
                raise RuntimeError('no decodable frames')
            frames = fr[:n * sw * sh].reshape(n, sh, sw)
        else:
            im = ImageOps.exif_transpose(Image.open(p)).convert('L').resize((sw, sh), Image.BILINEAR)
            frames = np.asarray(im)[None]
            n = 1
        sharp = np.array([lap_var(f) for f in frames])
        bright = frames.reshape(n, -1).mean(1) / 255
        contrast = frames.reshape(n, -1).std(1) / 255
        motion = np.zeros(n)
        if n > 1:
            d = np.abs(frames[1:].astype(np.int16) - frames[:-1]).mean((1, 2)) / 255
            motion[1:] = d
            motion[0] = d[0]
        idx = [int(n * q) for q in (0.2, 0.5, 0.8)]
        it['hashes'] = [dhash(frames[min(i, n - 1)]) for i in idx]
        it['per_t'] = dict(sharp=sharp.tolist(), bright=bright.tolist(), motion=motion.tolist())
        it['sharp'] = float(np.median(sharp))
        it['bright'] = float(np.median(bright))
        it['contrast'] = float(np.median(contrast))
        it['motion'] = float(np.median(motion)) if n > 1 else 0.0
        # colour thumbnail for the contact sheet
        tp = Path(thumbs_dir) / f"{abs(hash(p)) % 10**10}.jpg"
        if it['kind'] == 'video':
            run(['ffmpeg', '-v', 'error', '-y', '-ss', f"{it['duration'] * 0.5:.2f}", '-i', p, '-frames:v', '1',
                 '-vf', 'scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2', str(tp)])
        else:
            ImageOps.pad(ImageOps.exif_transpose(Image.open(p)).convert('RGB'), (320, 180)).save(tp, quality=80)
        it['thumb'] = str(tp)
    except Exception as e:
        it.update(status='broken', note=f'analysis failed: {str(e).splitlines()[0][:100]}')


def grade_library(items):
    ok = [i for i in items if i['status'] == 'ok']
    if not ok:
        return
    sharp_r = np.argsort(np.argsort([i['sharp'] for i in ok])) / max(1, len(ok) - 1)
    con_r = np.argsort(np.argsort([i['contrast'] for i in ok])) / max(1, len(ok) - 1)
    for i, s, c in zip(ok, sharp_r, con_r):
        expo = 1 - min(1, abs(i['bright'] - 0.45) / 0.4)
        mot = i['motion']
        mot_pref = 0.4 if i['kind'] == 'image' else (1.0 if 0.015 < mot < 0.12 else 0.6 if mot <= 0.015 else 0.3)
        res = min(1, (i['width'] * i['height']) / (1920 * 1080))
        i['score'] = round(0.38 * s + 0.17 * c + 0.2 * expo + 0.15 * mot_pref + 0.1 * res, 4)
        if i['bright'] < 0.08 or i['bright'] > 0.95 or i['contrast'] < 0.03:
            i.update(status='reject', note='exposure unusable')
    # duplicates: keep the best-scoring member of each near-identical group
    ok = sorted([i for i in items if i['status'] == 'ok'], key=lambda i: -i['score'])
    kept = []
    for i in ok:
        dup = None
        for k in kept:
            if k['kind'] != i['kind']:
                continue
            dist = [hamming(a, b) for a, b in zip(i['hashes'], k['hashes'])]
            if i['kind'] == 'image':
                same = dist[1] <= 6
            else:
                same = max(dist) <= 10 and abs(i['duration'] - k['duration']) <= max(1.0, 0.15 * k['duration'])
            if same:
                dup = k
                break
        if dup:
            i.update(status='duplicate', note=f"duplicate of {dup['name']} (kept higher quality)")
        else:
            kept.append(i)
    sc = sorted([k['score'] for k in kept])
    for k in kept:
        q = sc.index(k['score']) / max(1, len(sc) - 1)
        k['grade'] = 'A' if q >= 0.75 else 'B' if q >= 0.4 else 'C' if q >= 0.12 else 'D'
    for i in items:
        i.setdefault('grade', 'D')


def contact_sheet(items, out):
    ok = [i for i in items if i.get('thumb')]
    if not ok:
        return
    cols = 8
    rows = math.ceil(len(ok) / cols)
    sheet = Image.new('RGB', (cols * 330, rows * 215), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    for n, i in enumerate(ok):
        x, y = (n % cols) * 330 + 5, (n // cols) * 215 + 5
        try:
            sheet.paste(Image.open(i['thumb']), (x, y))
        except Exception:
            pass
        col = {'A': (255, 200, 0), 'B': (120, 220, 120), 'C': (150, 150, 150)}.get(i.get('grade'), (220, 70, 70))
        tag = i['grade'] if i['status'] == 'ok' else i['status'].upper()
        d.text((x, y + 184), f"[{tag}] {i['name'][:38]}", fill=col)
    sheet.save(out, quality=85)


# --------------------------------------------------------------------------- music
def load_audio(path, sr=22050):
    raw = run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'])
    return np.frombuffer(raw, np.float32).copy(), sr


def analyze_bgm(path):
    y, sr = load_audio(path)
    dur = len(y) / sr
    hop = 512
    try:
        import librosa
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time', tightness=100)
        tempo = float(np.atleast_1d(tempo)[0])
        oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
        method = 'librosa beat_track (dynamic programming over onset strength)'
    except Exception:
        nfft = 2048
        frames = np.lib.stride_tricks.sliding_window_view(np.pad(y, (0, nfft)), nfft)[::hop]
        S = np.abs(np.fft.rfft(frames * np.hanning(nfft), axis=1))
        oenv = np.maximum(0, np.diff(np.log1p(S), axis=0)).sum(1)
        oenv = np.concatenate([[0], oenv])
        fps_o = sr / hop
        ac = np.correlate(oenv - oenv.mean(), oenv - oenv.mean(), 'full')[len(oenv) - 1:]
        lags = np.arange(int(fps_o * 60 / 180), int(fps_o * 60 / 70))
        lag = lags[np.argmax(ac[lags])]
        tempo = 60 * fps_o / lag
        phase = max(range(lag), key=lambda p: oenv[p::lag].sum())
        beats = np.arange(phase, len(oenv), lag) / fps_o
        method = 'numpy spectral-flux autocorrelation (librosa not installed)'
    beats = np.asarray(beats, float)
    if len(beats) < 8:
        step = 60 / max(60.0, tempo or 120.0)
        beats = np.arange(0, dur, step)
    # energy envelopes
    nfr = len(y) // hop
    rms = np.sqrt(np.mean(y[:nfr * hop].reshape(nfr, hop) ** 2, axis=1))
    t = np.arange(nfr) * hop / sr
    win = max(1, int(sr / hop))
    sm = np.convolve(rms, np.ones(win) / win, 'same')
    lo, hi = np.percentile(sm, 5), np.percentile(sm, 98)
    en = np.clip((sm - lo) / max(1e-9, hi - lo), 0, 1)
    oenv = np.asarray(oenv, float)
    ot = np.arange(len(oenv)) * hop / sr
    oenv_n = oenv / max(1e-9, np.percentile(oenv, 99))
    beat_energy = np.interp(beats, t, en)
    beat_hit = np.array([oenv_n[max(0, np.searchsorted(ot, b) - 2):np.searchsorted(ot, b) + 3].max(initial=0) for b in beats])
    # downbeat phase: the phase whose beats carry the most onset strength
    phase = max(range(4), key=lambda p: beat_hit[p::4].sum())
    # drops: biggest rises in 1 s smoothed energy, min 6 s apart
    d = np.zeros_like(en)
    d[win:] = en[win:] - en[:-win]
    drops = []
    for i in np.argsort(d)[::-1]:
        tt = t[i]
        if tt < 3 or tt > dur - 6:
            continue
        if all(abs(tt - x) > 6 for x in drops):
            drops.append(tt)
        if len(drops) == 4:
            break
    drops = sorted(float(beats[np.argmin(np.abs(beats - x))]) for x in drops)
    # strongest hits
    hits = sorted(float(b) for b in beats[np.argsort(beat_hit)[-14:]])
    return dict(duration=dur, tempo=tempo, beats=beats.tolist(), downbeat_phase=phase,
                beat_energy=beat_energy.tolist(), beat_hit=beat_hit.tolist(), drops=drops, hits=hits,
                method=method, energy_curve=[(float(a), float(b)) for a, b in zip(t[::win // 2 or 1], en[::win // 2 or 1])])


def write_beat_map(music, out):
    with open(out, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['time_s', 'timecode', 'event', 'beat_index', 'bar', 'beat_in_bar', 'energy', 'hit_strength'])
        ph = music['downbeat_phase']
        rows = []
        for k, b in enumerate(music['beats']):
            bb = (k - ph) % 4 + 1
            rows.append((b, 'downbeat' if bb == 1 else 'beat', k, (k - ph) // 4 + 1, bb,
                         music['beat_energy'][k], music['beat_hit'][k]))
        for x in music['drops']:
            rows.append((x, 'DROP / energy jump', '', '', '', '', ''))
        for x in music['hits']:
            rows.append((x, 'strong hit', '', '', '', '', ''))
        for r in sorted(rows, key=lambda r: r[0]):
            tc = f"{int(r[0] // 60):02d}:{r[0] % 60:06.3f}"
            w.writerow([f"{r[0]:.3f}", tc, r[1], r[2], r[3], r[4],
                        f"{r[5]:.3f}" if r[5] != '' else '', f"{r[6]:.3f}" if r[6] != '' else ''])


# --------------------------------------------------------------------------- planning
def plan_shots(music, cfg):
    beats = music['beats']
    en = music['beat_energy']
    dur = music['duration']
    drops = music['drops']
    rnd = random.Random(7)
    first_drop = drops[0] if drops and drops[0] < dur * 0.45 else beats[min(len(beats) - 1, 32)]
    end_start = beats[int(np.argmin(np.abs(np.array(beats) - (dur - cfg['endcard_seconds']))))]
    bi = lambda t: int(np.argmin(np.abs(np.array(beats) - t)))
    shots = []
    k = 0
    # always start at 0 so there is no black head
    starts = []
    pre = bi(first_drop)
    # INTRO: long shots accelerating into the first drop
    i = 0
    while i < pre:
        left = pre - i
        n = 8 if left > 16 else 4 if left > 6 else 2 if left > 2 else 1
        starts.append((i, n, 'intro'))
        i += n
    # BODY
    end_i = bi(end_start)
    drop_idx = [bi(x) for x in drops]
    while i < end_i:
        since = min([i - d for d in drop_idx if d <= i], default=99)
        until = min([d - i for d in drop_idx if d > i], default=99)
        e = en[i]
        if until <= 2:
            n = 1
        elif since < 8:
            n = rnd.choice([1, 1, 2])
        elif e > 0.72:
            n = rnd.choice([1, 2, 2])
        elif e > 0.45:
            n = rnd.choice([2, 2, 4])
        else:
            n = rnd.choice([4, 4, 2])
        n = min(n, max(1, until if until < 99 else n), end_i - i)
        sec = 'drop' if since < 8 else 'build' if until <= 8 else 'peak' if e > 0.72 else 'breathe'
        starts.append((i, n, sec))
        i += n
    beat_t = lambda j: beats[j] if j < len(beats) else dur
    for j, (i, n, sec) in enumerate(starts):
        a, b = (0.0 if j == 0 else beat_t(i)), beat_t(i + n)
        if b - a < 0.25:
            continue
        shots.append(dict(start=a, end=b, section=sec, beats=n, bi=i, on_drop=i in drop_idx,
                          after_drop=any(0 <= i - d < 8 for d in drop_idx)))
    shots.append(dict(start=beat_t(end_i), end=dur, section='finale', beats=0, bi=end_i, on_drop=False, after_drop=False))
    # merge tiny tail
    return shots, first_drop, beat_t(end_i)


def candidate_segments(it):
    """Usable source windows of a clip, best first."""
    if it['kind'] == 'image':
        return [dict(item=it, t=0.0, q=it['score'])]
    pt = it['per_t']
    sh = np.array(pt['sharp'])
    mo = np.array(pt['motion'])
    br = np.array(pt['bright'])
    n = len(sh)
    sn = sh / max(1e-9, sh.max())
    q = sn + 0.6 * np.clip(mo / 0.08, 0, 1) - 1.5 * (np.abs(br - 0.45) > 0.38)
    # short phone clips: take several distinct moments (>= 1.2 s apart) so a small library doesn't repeat shots
    max_seg = max(1, min(6, int(it['duration'] / 1.3)))
    segs = []
    for idx in np.argsort(q)[::-1]:
        tt = idx / 2.0
        if tt > it['duration'] - 0.5:
            continue
        if all(abs(tt - s['t']) > 1.2 for s in segs):
            segs.append(dict(item=it, t=float(tt), q=float(it['score'] * (1 - 0.15 * len(segs)))))
        if len(segs) >= max_seg:
            break
    return segs or [dict(item=it, t=0.0, q=it['score'])]


def assign(shots, items, order_keys, intro=(), hero_name=''):
    usable = [i for i in items if i['status'] == 'ok' and i['grade'] in 'ABC']
    if not usable:
        raise RuntimeError('no usable media found')

    def order_key(i):
        rel = i['rel'].lower()
        grp = next((n for n, k in enumerate(order_keys) if k.lower() in rel), len(order_keys))
        return (grp, i['ctime'], i['rel'])
    body = [s for s in shots if s['section'] != 'finale']
    need = len(body)
    segs = []
    for i in sorted(usable, key=lambda i: -i['score']):
        segs += [dict(s, grade=i['grade']) for s in candidate_segments(i)]
    # prefer A/B, top up with C, then extra windows of the same clips
    by_q = sorted(segs, key=lambda s: (s is not None, -s['q']))
    primary = []
    seen = set()
    for s in by_q:                                  # one window per clip first
        if s['item']['path'] not in seen:
            primary.append(s)
            seen.add(s['item']['path'])
    extra = [s for s in by_q if s not in primary]
    pool = primary[:need]
    if len(pool) < need:
        pool += extra[:need - len(pool)]
    while len(pool) < need:                         # very small libraries: reuse
        pool.append(dict(primary[len(pool) % len(primary)]))
    # event order: chronological / --order groups
    pool.sort(key=lambda s: (order_key(s['item']), s['t']))
    # put the strongest material on drops: swap with best A within +/-3 slots
    for k, sh in enumerate(body):
        if sh['on_drop'] or sh['after_drop']:
            win = range(max(0, k - 3), min(len(pool), k + 4))
            best = max(win, key=lambda j: pool[j]['q'] + (0.2 if pool[j]['item']['grade'] == 'A' else 0))
            pool[k], pool[best] = pool[best], pool[k]
    hero = max(primary, key=lambda s: s['q'] + (0.3 if s['item']['kind'] == 'video' else 0))
    for sh, s in zip(body, pool):
        sh['src'] = s
    shots[-1]['src'] = hero
    # editor overrides: branding shots open the film, chosen hero under the end card
    byname = {i['name'].rsplit('.', 1)[0].upper(): i for i in items if i.get('per_t')}
    for k, nm in enumerate(intro):
        if nm.upper() in byname and k < len(body):
            body[k]['src'] = candidate_segments(byname[nm.upper()])[0]
    if hero_name.upper() in byname:
        shots[-1]['src'] = candidate_segments(byname[hero_name.upper()])[0]
    # avoid the same clip back-to-back
    for k in range(1, len(body)):
        if body[k]['src']['item']['path'] == body[k - 1]['src']['item']['path']:
            for j in range(k + 1, min(len(body), k + 6)):
                if body[j]['src']['item']['path'] not in (body[k - 1]['src']['item']['path'],):
                    body[k]['src'], body[j]['src'] = body[j]['src'], body[k]['src']
                    break


def decorate(shots, music):
    """Choose transitions / speed / punch for each shot."""
    rnd = random.Random(11)
    punch = False
    for k, s in enumerate(shots):
        d = s['end'] - s['start']
        s.update(fx=[], speed=1.0, ramp=None, zoom=1.0, sfx=[])
        it = s['src']['item']
        if k == 0:
            s['fx'].append('fade_from_black')
        if s['on_drop']:
            s['fx'] += ['flash', 'shake']
            s['zoom'] = 1.06
            s['sfx'].append('impact')
        elif k > 0 and shots[k - 1]['section'] != s['section'] and s['section'] != 'finale':
            s['fx'].append('whip')
            s['sfx'].append('whoosh')
        elif s['section'] in ('drop', 'peak') and d < 0.6:
            punch = not punch
            s['zoom'] = 1.1 if punch else 1.0
        elif s['section'] in ('drop', 'peak') and rnd.random() < 0.18:
            s['fx'].append('whip')
            s['sfx'].append('whoosh')
        # MASS layer: constant camera energy
        hot = s['section'] in ('drop', 'peak', 'build')
        bar_start = (s['bi'] - music['downbeat_phase']) % 4 == 0
        if s['on_drop'] or (hot and bar_start):
            s['zmove'] = 'slam_out'                     # fast 1.35 -> 1.0 zoom-out slam on the bar
            if not s['on_drop']:
                s['fx'].append('flash_soft')
                s['sfx'].append('whoosh')
        elif s['section'] == 'finale':
            s['zmove'] = 'out_slow'
        else:
            s['zmove'] = 'in' if k % 2 else 'out'      # alternating push-in / pull-out
            if hot and 'whip' not in s['fx'] and k % 2 == 0:
                s['fx'].append('whip')
                s['sfx'].append('whoosh')
            elif hot:
                s['fx'].append('zoomblur')
        if it['kind'] == 'video':
            if s['section'] == 'finale':
                s['speed'] = 0.5
            elif s['section'] in ('breathe', 'intro') and d >= 1.5 and it['motion'] > 0.01 and it['grade'] == 'A':
                s['ramp'] = 'fast_slow'          # SPEED RAMP B: fast -> slow motion -> cut
            elif s['section'] == 'build' and d >= 0.8 and it['motion'] > 0.01:
                s['ramp'] = 'slow_fast'          # SPEED RAMP A: normal -> fast -> cut
        if s['section'] == 'finale':
            s['fx'].append('fade_to_black')
            s['sfx'].append('boom')


# --------------------------------------------------------------------------- rendering
def grade_filter(it):
    b = max(-0.08, min(0.08, (0.45 - it.get('bright', 0.45)) * 0.35))
    sat = 1.12 if it.get('contrast', 0.2) > 0.12 else 1.05
    # PASS 1 exposure balance, PASS 2 unified look (gentle S-curve, teal shadows / warm highlights)
    return (f"eq=brightness={b:.3f}:contrast=1.07:saturation={sat}:gamma=0.98,"
            "curves=all='0/0.02 0.25/0.22 0.5/0.5 0.75/0.79 1/0.98',"
            "colorbalance=rs=-0.03:gs=0.0:bs=0.035:rh=0.035:gh=0.01:bh=-0.03,"
            "vignette=angle=PI/5.5")


def frame_fill(it, zoom):
    zw, zh = int(W * zoom) // 2 * 2, int(H * zoom) // 2 * 2
    if it['orientation'] == 'landscape' or it['width'] / max(1, it['height']) > 1.5:
        return f"scale={zw}:{zh}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}", None
    # portrait / square: sharp foreground on a blurred, darkened fill of itself
    return None, (f"split=2[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"boxblur=30:3,eq=brightness=-0.12[bgb];[fg]scale=-2:{zh}:flags=lanczos[fgs];"
                  f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,crop={W}:{H}")


def render_shot(k, s, out_dir):
    it = s['src']['item']
    d = s['end'] - s['start']
    nfr = max(1, round(s['end'] * FPS) - round(s['start'] * FPS))
    d = nfr / FPS
    out = Path(out_dir) / f"SHOT_{k + 1:03d}.mov"
    s['file'] = str(out)
    s['frames'] = nfr
    pre = []
    if it['kind'] == 'image':
        inp = ['-loop', '1', '-framerate', str(FPS), '-t', f"{d + 0.2:.3f}", '-i', it['path']]
        z0, z1 = (1.0, 1.08) if k % 2 == 0 else (1.08, 1.0)
        fill, comp = frame_fill(it, 1.0)
        base = (fill if fill else comp.replace(f"crop={W}:{H}", f"crop={W}:{H}", 1))
        # Ken Burns on stills (zoompan on a 2x canvas to avoid jitter)
        chain = (f"{base},scale={W * 2}:{H * 2},zoompan=z='{z0}+({z1 - z0})*on/{nfr}':"
                 f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}")
        src_in, src_len = 0.0, 0.0
    else:
        sp = s['speed']
        if s['ramp'] == 'fast_slow':
            src_len = d * 0.4 * 2.0 + d * 0.6 * 0.45
        elif s['ramp'] == 'slow_fast':
            src_len = d * 0.6 * 1.0 + d * 0.4 * 2.2
        else:
            src_len = d * sp
        src_in = max(0.0, min(s['src']['t'] - src_len * 0.3, it['duration'] - src_len - 0.05))
        if src_in + src_len > it['duration']:      # clip shorter than needed: slow it to fit
            src_in = 0.0
            sp = max(0.25, (it['duration'] - 0.05) / d)
            s['speed'], s['ramp'] = sp, None
            src_len = d * sp
        inp = ['-ss', f"{src_in:.3f}", '-t', f"{src_len + 0.3:.3f}", '-i', it['path']]
        if s['ramp'] == 'fast_slow':
            a = d * 0.4 * 2.0
            tm = (f"[0:v]fps={FPS * 2},split=2[r1][r2];[r1]trim=0:{a:.3f},setpts=(PTS-STARTPTS)/2.0[p1];"
                  f"[r2]trim={a:.3f},setpts=(PTS-STARTPTS)/0.45[p2];[p1][p2]concat=n=2:v=1:a=0,fps={FPS}")
        elif s['ramp'] == 'slow_fast':
            a = d * 0.6
            tm = (f"[0:v]split=2[r1][r2];[r1]trim=0:{a:.3f},setpts=PTS-STARTPTS[p1];"
                  f"[r2]trim={a:.3f},setpts=(PTS-STARTPTS)/2.2[p2];[p1][p2]concat=n=2:v=1:a=0,fps={FPS}")
        else:
            tm = f"[0:v]setpts=(PTS-STARTPTS)/{sp:.4f},fps={FPS}"
        fill, comp = frame_fill(it, 1.0)
        chain = tm + ',' + (fill if fill else comp)
        zm = s.get('zmove', 'in')
        z = {'in': f"1.0+0.16*on/{nfr}", 'out': f"1.16-0.16*on/{nfr}",
             'slam_out': f"if(lt(on,9),1.38-0.38*(1-pow(1-on/9,3)),1.0+0.04*(on-9)/{nfr})",
             'out_slow': f"1.12-0.12*on/{nfr}"}[zm]
        chain += (f",scale=2304:1296:flags=bicubic,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                  f":d=1:s={W}x{H}:fps={FPS}")
        pre = []
    if it['kind'] == 'image':
        chain = '[0:v]' + chain
    fx = [grade_filter(it)]
    if 'shake' in s['fx']:
        fx.append(f"scale={W + 64}:{H + 36},crop={W}:{H}:x='32+26*sin(t*71)*exp(-t*7)':y='18+16*cos(t*53)*exp(-t*7)'")
    if 'whip' in s['fx']:
        fx.append("avgblur=sizeX=48:sizeY=1:enable='lt(t,0.1)'")
    if 'zoomblur' in s['fx']:
        fx.append("gblur=sigma=18:enable='lt(t,0.07)'")
    if 'flash_soft' in s['fx']:
        fx.append("fade=t=in:st=0:d=0.1:color=white")
    if 'flash' in s['fx']:
        fx.append("fade=t=in:st=0:d=0.17:color=white")
    if 'fade_from_black' in s['fx']:
        fx.append(f"fade=t=in:st=0:d={min(0.8, d / 2):.2f}")
    if 'fade_to_black' in s['fx']:
        fx.append(f"fade=t=out:st={max(0, d - 1.0):.2f}:d=1.0")
    chain += ',' + ','.join(fx) + f",trim=end_frame={nfr},setsar=1,format=yuv420p[v]"
    cmd = ['ffmpeg', '-v', 'error', '-y'] + inp + ['-filter_complex', chain, '-map', '[v]', '-frames:v', str(nfr),
                                                   '-r', str(FPS), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '15',
                                                   '-pix_fmt', 'yuv420p', '-an', str(out)]
    run(cmd)
    s['src_in'], s['src_len'] = src_in, src_len
    return out


# --------------------------------------------------------------------------- titles
def find_font(ws, heavy=True):
    cands = [ws / '04_GRAPHICS/fonts' / ('InterDisplay-Black.otf' if heavy else 'InterDisplay-Medium.otf')]
    win = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    cands += [win / f for f in (['BebasNeue-Regular.ttf', 'Montserrat-Black.ttf', 'arialbd.ttf', 'segoeuib.ttf'] if heavy
                                else ['Montserrat-Medium.ttf', 'segoeui.ttf', 'arial.ttf'])]
    cands += [Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
              Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')]
    for c in cands:
        if c.exists():
            return str(c)
    return None


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def render_title(spec, out, ws):
    """Animated title rendered to a ProRes 4444 (alpha) clip.
    styles: 'reveal' (tracking-in + blur-to-sharp), 'impact' (scale-down slam), 'endcard'."""
    heavy = ImageFont.truetype(find_font(ws, True), spec.get('size', 190)) if find_font(ws, True) else ImageFont.load_default()
    light = ImageFont.truetype(find_font(ws, False), spec.get('sub_size', 58)) if find_font(ws, False) else ImageFont.load_default()
    n = max(2, round(spec['dur'] * FPS))
    tmp = Path(str(out) + '_frames')
    tmp.mkdir(exist_ok=True)
    accent = (255, 196, 0)
    text = spec['text']
    for f in range(n):
        t = f / FPS
        p_in = ease(t / spec.get('in', 0.45))
        p_out = 1 - ease((t - (spec['dur'] - 0.3)) / 0.3) if spec.get('out', True) else 1
        a = p_in * p_out
        im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        if spec['style'] == 'endcard':
            base = Image.new('RGBA', (W, H), (0, 0, 0, int(150 * min(1, t / 0.4))))
            im = Image.alpha_composite(im, base)
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        if spec['style'] == 'impact':
            scale = 1.0 + 0.35 * (1 - ease(t / 0.18))
            track = 0
        else:
            scale = 1.0
            track = int(60 * (1 - p_in)) + 6
        # draw text with tracking
        chars = list(text)
        widths = [d.textlength(c, font=heavy) + track for c in chars]
        tw = sum(widths) - track
        bbox = d.textbbox((0, 0), text, font=heavy)
        th = bbox[3] - bbox[1]
        x = (W - tw) / 2
        y = H / 2 - th / 2 - bbox[1] - (30 if spec.get('sub') else 0)
        for c, wdt in zip(chars, widths):
            d.text((x, y), c, font=heavy, fill=(255, 255, 255, 255))
            x += wdt
        # accent line (draws on left->right)
        lw = int(tw * 0.5 * ease((t - 0.1) / 0.5))
        if lw > 2 and spec['style'] != 'impact':
            ly = int(y + bbox[3] + 26)
            d.rectangle([W // 2 - lw // 2, ly, W // 2 + lw // 2, ly + 6], fill=accent + (255,))
        if spec.get('sub'):
            sp = ease((t - 0.25) / 0.45)
            sb = d.textbbox((0, 0), spec['sub'], font=light)
            sx = (W - (sb[2] - sb[0])) / 2
            sy = y + bbox[3] + 60 + 20 * (1 - sp)
            d.text((sx, sy), spec['sub'], font=light, fill=(235, 235, 235, int(255 * sp)))
        if scale != 1.0:
            layer = layer.resize((int(W * scale), int(H * scale)), Image.BICUBIC)
            layer = layer.crop(((layer.width - W) // 2, (layer.height - H) // 2,
                                (layer.width - W) // 2 + W, (layer.height - H) // 2 + H))
        blur = 14 * (1 - p_in) if spec['style'] != 'impact' else 0
        if blur > 0.5:
            layer = layer.filter(ImageFilter.GaussianBlur(blur))
        # soft shadow for legibility on bright footage
        sh = layer.split()[3].filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * 0.55))
        shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        shadow.putalpha(sh)
        im = Image.alpha_composite(im, shadow)
        im = Image.alpha_composite(im, layer)
        if a < 1:
            al = im.split()[3].point(lambda v: int(v * a))
            im.putalpha(al)
        im.save(tmp / f"{f:04d}.png", compress_level=1)
    run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i', str(tmp / '%04d.png'),
         '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', str(out)])
    shutil.rmtree(tmp, ignore_errors=True)


def plan_titles(shots, music, first_drop, end_start, cfg):
    beats = music['beats']
    drops = music['drops']
    titles = []
    spb = 60 / max(60, music['tempo'])
    # intro: presenter line, then the identity hit on the first drop
    t_pre = beats[min(len(beats) - 1, 8)] if first_drop > 6 else 0.3
    if first_drop - t_pre > 2.5:
        titles.append(dict(name='T01_PRESENTS', text=cfg['presenter'], style='reveal', size=88, at=t_pre,
                           dur=min(3.2, first_drop - t_pre - 0.6)))
    titles.append(dict(name='T02_FAILATHON', text=cfg['title'], style='impact', size=230, at=first_drop,
                       dur=min(2.2, 8 * spb), sub=None))
    words = cfg['section_words']
    for n, dr in enumerate(drops[1:]):
        if n >= len(words) or dr > end_start - 3:
            break
        titles.append(dict(name=f'T{n + 3:02d}_{re.sub("[^A-Z]", "", words[n].upper())[:12]}', text=words[n],
                           style='impact', size=170, at=dr, dur=min(1.6, 4 * spb)))
    titles.append(dict(name='T99_ENDCARD', text=cfg['title'], style='endcard', size=210, sub=cfg['tagline'],
                       at=end_start + 0.25, dur=music['duration'] - end_start - 0.25, out=False))
    return titles


# --------------------------------------------------------------------------- sfx
def synth_sfx(out_dir):
    """Small reusable SFX kit synthesised from noise/sine (no external library needed)."""
    rng = np.random.default_rng(3)
    kit = {}

    def save(name, x):
        x = np.clip(x / max(1e-9, np.abs(x).max()) * 0.9, -1, 1)
        st = np.stack([x, x], 1)
        p = Path(out_dir) / f'{name}.wav'
        with wave.open(str(p), 'wb') as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((st * 32767).astype(np.int16).tobytes())
        kit[name] = str(p)

    def lp(x, a):
        y = np.empty_like(x)
        acc = 0.0
        for i, v in enumerate(x):
            acc += a[i] * (v - acc) if hasattr(a, '__len__') else a * (v - acc)
            y[i] = acc
        return y
    # whoosh: band-swept noise, swelling into the cut
    n = int(SR * 0.45)
    t = np.linspace(0, 1, n)
    noise = rng.standard_normal(n)
    sweep = 0.02 + 0.35 * t ** 2
    w = lp(noise, sweep) - lp(lp(noise, sweep), 0.01)
    save('whoosh', w * np.sin(np.pi * t) ** 1.5 * (0.3 + t))
    # impact: sub thump + transient
    n = int(SR * 1.2)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * (55 * t - 25 * t ** 2)) * np.exp(-t * 4)
    click = rng.standard_normal(n) * np.exp(-t * 60) * 0.6
    save('impact', sub + lp(click, 0.3))
    # boom: longer cinematic low hit for the end card
    n = int(SR * 3.0)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * (48 * t - 10 * t ** 2)) * np.exp(-t * 1.6) + 0.25 * lp(rng.standard_normal(n), 0.05) * np.exp(-t * 3)
    save('boom', boom)
    # riser
    n = int(SR * 2.0)
    t = np.linspace(0, 1, n)
    r = lp(rng.standard_normal(n), 0.01 + 0.3 * t ** 2) * t ** 2 + 0.3 * np.sin(2 * np.pi * (200 * t + 600 * t ** 2)) * t ** 3
    save('riser', r)
    return kit


def sfx_events(shots, titles, music):
    ev = []
    for s in shots:
        for name in s['sfx']:
            if name == 'whoosh':
                ev.append(('whoosh', s['start'] - 0.38, 0.24))
            elif name == 'impact':
                ev.append(('impact', s['start'], 0.42))
            elif name == 'boom':
                ev.append(('boom', s['start'] + 0.25, 0.45))
    for dr in music['drops']:
        ev.append(('riser', dr - 2.0, 0.26))
    ev = [e for e in ev if e[1] >= 0]
    return sorted(ev, key=lambda e: e[1])


# --------------------------------------------------------------------------- assembly
def assemble(shots, titles, sfx_kit, sfx_ev, bgm, music, media_dir, out, title_dir):
    lst = Path(media_dir) / 'concat.txt'
    lst.write_text(''.join(f"file '{Path(s['file']).as_posix()}'\n" for s in shots))
    base = Path(media_dir) / 'V1_BASE.mov'
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(base)])
    inputs = ['-i', str(base), '-i', str(bgm)]
    fc = []
    v = '[0:v]'
    idx = 2
    for t in titles:
        inputs += ['-itsoffset', f"{t['at']:.3f}", '-i', t['file']]
        fc.append(f"{v}[{idx}:v]overlay=0:0:eof_action=pass:format=auto[v{idx}]")
        v = f'[v{idx}]'
        idx += 1
    fc.append(f"{v}format=yuv420p[vout]")
    # audio: BGM untouched apart from gain staging; SFX bus kept under it
    fc.append(f"[1:a]aresample={SR},volume={music.get('bgm_gain_db', 0):.2f}dB[bgm]")
    mix = ['[bgm]']
    for n, (name, at, vol) in enumerate(sfx_ev):
        inputs += ['-i', sfx_kit[name]]
        ms = int(at * 1000)
        fc.append(f"[{idx}:a]volume={vol},adelay={ms}|{ms}[s{n}]")
        mix.append(f'[s{n}]')
        idx += 1
    fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,"
              f"alimiter=limit=0.89:attack=3:release=60:level=0,afade=t=out:st={music['duration'] - 0.6:.3f}:d=0.6[aout]")
    run(['ffmpeg', '-v', 'error', '-y'] + inputs + ['-filter_complex', ';'.join(fc), '-map', '[vout]', '-map', '[aout]',
                                                    '-t', f"{music['duration']:.3f}", '-r', str(FPS),
                                                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '17', '-profile:v', 'high',
                                                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                                                    '-c:a', 'aac', '-b:a', '320k', '-ar', str(SR), str(out)])
    return base


# --------------------------------------------------------------------------- interchange
def tc(frames, fps=FPS):
    return f"{frames // (3600 * fps):02d}:{frames // (60 * fps) % 60:02d}:{frames // fps % 60:02d}:{frames % fps:02d}"


def write_edl(shots, out):
    lines = ['TITLE: FAILATHON_AV_FINAL', 'FCM: NON-DROP FRAME', '']
    rec = 0
    for k, s in enumerate(shots):
        n = s['frames']
        reel = f"AX"
        lines.append(f"{k + 1:03d}  {reel:<8} V     C        {tc(0)} {tc(n)} {tc(rec)} {tc(rec + n)}")
        lines.append(f"* FROM CLIP NAME: {Path(s['file']).name}")
        lines.append(f"* SOURCE: {s['src']['item']['rel']} @ {s.get('src_in', 0):.2f}s speed={s['speed']} ramp={s['ramp']}")
        lines.append('')
        rec += n
    Path(out).write_text('\n'.join(lines))


def write_fcpxml(shots, titles, sfx_ev, sfx_kit, bgm, music, out):
    def r(sec):
        return f"{round(sec * FPS)}/{FPS}s"
    total = sum(s['frames'] for s in shots)
    res, assets = [], {}
    res.append(f'<format id="r0" name="FFVideoFormat1080p{FPS}" frameDuration="1/{FPS}s" width="{W}" height="{H}"/>')

    def asset(path, has_v=True, has_a=False, dur=None):
        if path in assets:
            return assets[path]
        aid = f"a{len(assets) + 1}"
        assets[path] = aid
        uri = Path(path).resolve().as_uri()
        res.append(f'<asset id="{aid}" name="{Path(path).stem}" start="0s" duration="{r(dur or 3600)}" '
                   f'hasVideo="{int(has_v)}" hasAudio="{int(has_a)}" format="r0" audioSources="1" audioChannels="2" '
                   f'audioRate="{SR}"><media-rep kind="original-media" src="{uri}"/></asset>')
        return aid
    spine = []
    off = 0
    for k, s in enumerate(shots):
        aid = asset(s['file'], dur=s['frames'] / FPS)
        inner = ''
        if k == 0:
            inner += f'<asset-clip ref="{asset(str(bgm), False, True, music["duration"])}" lane="-1" offset="0s" ' \
                     f'name="BGM" start="0s" duration="{r(music["duration"])}" role="dialogue"/>'
            for t in titles:
                inner += f'<asset-clip ref="{asset(t["file"], dur=t["dur"])}" lane="2" offset="{r(t["at"])}" ' \
                         f'name="{t["name"]}" start="0s" duration="{r(t["dur"])}"/>'
            for name, at, vol in sfx_ev:
                inner += f'<asset-clip ref="{asset(sfx_kit[name], False, True, 3)}" lane="-2" offset="{r(max(0, at))}" ' \
                         f'name="SFX_{name}" start="0s" duration="{r(0.5 if name != "boom" else 3)}"/>'
            for x in music['drops']:
                inner += f'<marker start="{r(x)}" duration="1/{FPS}s" value="DROP"/>'
        if s['on_drop']:
            inner += f'<marker start="0s" duration="1/{FPS}s" value="HIT {s["section"]}"/>'
        spine.append(f'<asset-clip ref="{aid}" offset="{off}/{FPS}s" name="SHOT_{k + 1:03d} | {s["section"]}" '
                     f'start="0s" duration="{s["frames"]}/{FPS}s">{inner}</asset-clip>')
        off += s['frames']
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.9">\n<resources>\n'
           + '\n'.join(res) + '\n</resources>\n<library><event name="FAILATHON_AV">'
           f'<project name="FAILATHON_AV_FINAL"><sequence format="r0" duration="{total}/{FPS}s" tcStart="0s" '
           f'tcFormat="NDF" audioLayout="stereo" audioRate="48k"><spine>\n' + '\n'.join(spine) +
           '\n</spine></sequence></project></event></library>\n</fcpxml>\n')
    Path(out).write_text(xml)


# --------------------------------------------------------------------------- validation
def validate(final, music, shots, titles):
    res = {}
    pr = ffprobe(final)
    v = next(s for s in pr['streams'] if s['codec_type'] == 'video')
    a = next((s for s in pr['streams'] if s['codec_type'] == 'audio'), None)
    res['container'] = pr['format']['format_name']
    res['video'] = f"{v['codec_name']} {v['width']}x{v['height']} @ {v['avg_frame_rate']}"
    res['audio'] = f"{a['codec_name']} {a.get('sample_rate')} Hz {a.get('channels')}ch" if a else 'MISSING'
    res['duration'] = float(pr['format']['duration'])
    res['bgm_duration'] = music['duration']
    res['duration_ok'] = abs(res['duration'] - music['duration']) < 0.15
    out = subprocess.run(['ffmpeg', '-v', 'info', '-i', str(final), '-vf', 'blackdetect=d=0.25:pix_th=0.06',
                          '-af', 'silencedetect=n=-45dB:d=0.6,astats=metadata=0', '-f', 'null', '-'],
                         stderr=subprocess.PIPE, stdout=subprocess.PIPE).stderr.decode(errors='ignore')
    blacks = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', out)
    silences = re.findall(r'silence_start: ([\d.]+)', out)
    peaks = re.findall(r'Peak level dB: ([-\d.inf]+)', out)
    res['black_segments'] = [(float(a_), float(b_)) for a_, b_ in blacks]
    # fades at head and tail are intentional
    res['unintended_black'] = [b for b in res['black_segments'] if b[0] > 1.0 and b[1] < music['duration'] - 1.2]
    res['silences'] = [float(x) for x in silences if 0.5 < float(x) < music['duration'] - 1.5]
    try:
        res['audio_peak_db'] = max(float(p) for p in peaks if p not in ('-inf',))
    except ValueError:
        res['audio_peak_db'] = None
    res['clipping'] = res['audio_peak_db'] is not None and res['audio_peak_db'] > -0.1
    dec = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(final), '-f', 'null', '-'], stderr=subprocess.PIPE)
    res['decode_errors'] = dec.stderr.decode(errors='ignore').strip()[:500]
    res['pass'] = (res['duration_ok'] and not res['unintended_black'] and not res['clipping']
                   and not res['decode_errors'] and a is not None)
    return res


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--media', required=True, help='folder with all event photos/videos (read-only)')
    ap.add_argument('--bgm', required=True, help='the exact BGM file')
    ap.add_argument('--workspace', default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument('--order', default='', help='comma-separated folder/filename keywords in event order')
    ap.add_argument('--title', default='FAILATHON')
    ap.add_argument('--presenter', default='E-CELL PRESENTS')
    ap.add_argument('--tagline', default='FAIL  ·  LEARN  ·  RISE')
    ap.add_argument('--words', default='FAIL FAST,BUILD BOLD,RISE HIGHER', help='impact words for later drops')
    ap.add_argument('--intro', default='', help='clip names (no extension) forced to open the film')
    ap.add_argument('--hero', default='', help='clip name forced under the end card')
    ap.add_argument('--endcard', type=float, default=6.0, help='seconds reserved for the end card')
    ap.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()

    ws = Path(a.workspace)
    for d in ['01_AUDIO', '03_RESOLVE/media/shots', '03_RESOLVE/media/titles', '05_SFX', '06_PREVIEWS/thumbs',
              '07_EXPORTS', '09_REPORTS', '10_BACKUPS']:
        (ws / d).mkdir(parents=True, exist_ok=True)
    for f in (ws / '03_RESOLVE/media/shots').glob('SHOT_*.mov'):
        f.unlink()
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            sys.exit(f'{tool} not found on PATH - install ffmpeg (winget install Gyan.FFmpeg) and retry')
    cfg = dict(title=a.title, presenter=a.presenter, tagline=a.tagline, endcard_seconds=a.endcard,
               section_words=[w.strip() for w in a.words.split(',') if w.strip()])
    order_keys = [k.strip() for k in a.order.split(',') if k.strip()]

    # PHASE 3 inventory + analysis
    items = inventory(a.media)
    log(f"Inventory: {len(items)} media files ({sum(i['kind'] == 'video' for i in items)} video, "
        f"{sum(i['kind'] == 'image' for i in items)} photo)")
    with ThreadPoolExecutor(a.jobs) as ex:
        list(ex.map(lambda i: analyze(i, ws / '06_PREVIEWS/thumbs') if i['status'] == 'ok' else None, items))
    grade_library(items)
    contact_sheet(items, ws / '06_PREVIEWS/CONTACT_SHEET.jpg')
    with open(ws / '09_REPORTS/MEDIA_MANIFEST.csv', 'w', newline='', encoding='utf-8') as fh:
        cols = ['rel', 'kind', 'status', 'grade', 'score', 'duration', 'width', 'height', 'fps', 'codec', 'orientation',
                'audio', 'size_mb', 'sharp', 'bright', 'contrast', 'motion', 'note', 'path']
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for i in sorted(items, key=lambda i: i['rel']):
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in i.items() if k in cols})
    counts = {g: sum(1 for i in items if i['status'] == 'ok' and i['grade'] == g) for g in 'ABCD'}
    log(f"Analysis done: A={counts['A']} B={counts['B']} C={counts['C']} D={counts['D']} "
        f"dup={sum(i['status'] == 'duplicate' for i in items)} reject/broken="
        f"{sum(i['status'] in ('reject', 'broken') for i in items)}")

    # PHASE 4-5 BGM
    bgm_copy = ws / '01_AUDIO' / ('BGM_MASTER' + Path(a.bgm).suffix.lower())
    if Path(a.bgm).resolve() != bgm_copy.resolve():
        shutil.copy2(a.bgm, bgm_copy)
    music = analyze_bgm(bgm_copy)
    vol = subprocess.run(['ffmpeg', '-i', str(bgm_copy), '-af', 'volumedetect', '-f', 'null', '-'],
                         stderr=subprocess.PIPE).stderr.decode(errors='ignore')
    mx = re.search(r'max_volume: ([-\d.]+) dB', vol)
    music['bgm_peak_db'] = float(mx.group(1)) if mx else 0.0
    music['bgm_gain_db'] = min(0.0, -1.0 - music['bgm_peak_db'])   # only ever turn down, never alter the music
    write_beat_map(music, ws / '09_REPORTS/BEAT_MAP.csv')
    log(f"BGM: {music['duration']:.2f}s, {music['tempo']:.1f} BPM, {len(music['beats'])} beats, "
        f"drops at {', '.join(f'{x:.2f}' for x in music['drops'])}")

    # PHASE 7-14 edit plan
    shots, first_drop, end_start = plan_shots(music, cfg)
    assign(shots, items, order_keys, [x.strip() for x in a.intro.split(',') if x.strip()], a.hero)
    decorate(shots, music)
    log(f"Plan: {len(shots)} shots, first drop {first_drop:.2f}s, end card {end_start:.2f}s")
    shot_dir = ws / '03_RESOLVE/media/shots'
    with ThreadPoolExecutor(a.jobs) as ex:
        futs = [ex.submit(render_shot, k, s, shot_dir) for k, s in enumerate(shots)]
        for f in futs:
            f.result()
    log('Shots rendered')

    # PHASE 15-16 titles
    titles = plan_titles(shots, music, first_drop, end_start, cfg)
    with ThreadPoolExecutor(min(a.jobs, 4)) as ex:
        futs = []
        for t in titles:
            t['file'] = str(ws / '03_RESOLVE/media/titles' / f"{t['name']}.mov")
            if not Path(t['file']).exists():
                futs.append(ex.submit(render_title, t, t['file'], ws))
        for f in futs:
            f.result()
    log(f'{len(titles)} animated titles rendered')

    # PHASE 17 SFX
    kit = synth_sfx(ws / '05_SFX')
    ev = sfx_events(shots, titles, music)

    # PHASE 20-25 assemble + render
    final = ws / '07_EXPORTS/FAILATHON_AV_FINAL.mp4'
    assemble(shots, titles, kit, ev, bgm_copy, music, ws / '03_RESOLVE/media', final, ws / '03_RESOLVE/media/titles')
    log('Final MP4 rendered')
    preview = ws / '06_PREVIEWS/FAILATHON_AV_PREVIEW.mp4'
    if os.environ.get('FA_PREVIEW'): run(['ffmpeg', '-v', 'error', '-y', '-i', str(final), '-vf', 'scale=960:540', '-c:v', 'libx264', '-crf', '24',
         '-preset', 'veryfast', '-c:a', 'aac', '-b:a', '160k', str(preview)])
    # frame strip for quick visual QA
    run(['ffmpeg', '-v', 'error', '-y', '-i', str(final), '-vf', 'fps=1,scale=320:-2,tile=8x10', '-frames:v', '1',
         str(ws / '06_PREVIEWS/FINAL_FRAME_STRIP.jpg')])

    # interchange for Resolve
    write_edl(shots, ws / '03_RESOLVE/FAILATHON_AV_FINAL.edl')
    write_fcpxml(shots, titles, ev, kit, bgm_copy, music, ws / '03_RESOLVE/FAILATHON_AV_FINAL.fcpxml')
    plan = dict(fps=FPS, width=W, height=H, bgm=str(bgm_copy.resolve()), duration=music['duration'],
                tempo=music['tempo'], drops=music['drops'], hits=music['hits'],
                downbeats=music['beats'][music['downbeat_phase']::4],
                shots=[dict(file=str(Path(s['file']).resolve()), frames=s['frames'], start=s['start'], section=s['section'],
                            source=s['src']['item']['path'], source_in=s.get('src_in', 0.0), source_len=s.get('src_len', 0.0),
                            source_kind=s['src']['item']['kind'], speed=s['speed'], ramp=s['ramp'], fx=s['fx'],
                            zoom=s['zoom'], on_drop=s['on_drop']) for s in shots],
                titles=[dict(file=str(Path(t['file']).resolve()), name=t['name'], text=t['text'], at=t['at'], dur=t['dur'],
                             sub=t.get('sub')) for t in titles],
                sfx=[dict(file=str(Path(kit[n]).resolve()), name=n, at=at, gain=vol) for n, at, vol in ev],
                final_mp4=str(final.resolve()))
    (ws / '03_RESOLVE/edit_plan.json').write_text(json.dumps(plan, indent=1))

    # validation + reports
    val = validate(final, music, shots, titles)
    log(f"Validation: {'PASS' if val['pass'] else 'ISSUES FOUND'}")
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    bk = ws / '10_BACKUPS' / f'plan_{stamp}'
    bk.mkdir(parents=True, exist_ok=True)
    for f in ['03_RESOLVE/edit_plan.json', '03_RESOLVE/FAILATHON_AV_FINAL.fcpxml', '03_RESOLVE/FAILATHON_AV_FINAL.edl']:
        shutil.copy2(ws / f, bk)
    write_reports(ws, items, music, shots, titles, ev, val, a, counts)
    log('Done.')
    print(json.dumps({k: v for k, v in val.items() if k != 'black_segments'}, indent=1))


def write_reports(ws, items, music, shots, titles, ev, val, a, counts):
    used = {s['src']['item']['path'] for s in shots}
    n_trans = sum(1 for s in shots if set(s['fx']) & {'flash', 'whip', 'shake'})
    lens = [s['frames'] / FPS for s in shots]
    secs = {}
    for s in shots:
        secs.setdefault(s['section'], []).append(s['frames'] / FPS)
    rep = f"""# FAILATHON AV — Edit Report

Generated {datetime.now():%Y-%m-%d %H:%M} by `08_SCRIPTS/failathon_autoedit.py`.

| Item | Value |
|---|---|
| Project | FAILATHON_AV |
| DaVinci Resolve | not used for the render. Build the project with `08_SCRIPTS/FAILATHON_AV_RESOLVE_SCRIPT.py` on a machine that has Resolve |
| Timeline | {W}x{H}, {FPS} fps |
| BGM | `{Path(a.bgm).name}`, {music['duration']:.3f} s, {music['tempo']:.1f} BPM, peak {music['bgm_peak_db']:.1f} dBFS, gain applied {music['bgm_gain_db']:.1f} dB |
| Source files | {len(items)} ({sum(i['kind'] == 'video' for i in items)} video, {sum(i['kind'] == 'image' for i in items)} photo), total {sum(i.get('duration', 0) or 0 for i in items) / 60:.1f} min of video |
| Grades | A={counts['A']} B={counts['B']} C={counts['C']} D={counts['D']}; duplicates {sum(i['status'] == 'duplicate' for i in items)}; rejected/broken {sum(i['status'] in ('reject', 'broken') for i in items)} |
| Clips used / unused | {len(used)} / {len(items) - len(used)} |
| Final duration | {val['duration']:.3f} s |
| Cuts | {len(shots) - 1} ({len(shots)} shots; avg {np.mean(lens):.2f} s, min {min(lens):.2f} s, max {max(lens):.2f} s) |
| Transitions | {n_trans} designed transitions (flash/shake impacts on drops, whip blur on section changes), all other edits are hard cuts on beats |
| Speed ramps | {sum(1 for s in shots if s['ramp'])} ramps, {sum(1 for s in shots if s['speed'] != 1.0 and not s['ramp'])} constant slow-motion shots |
| Titles | {len(titles)}: {', '.join(t['text'] for t in titles)} |
| SFX | {len(ev)} events ({', '.join(sorted(set(e[0] for e in ev)))}) |
| Export | H.264 High, CRF 16, yuv420p, {FPS} fps, AAC 320 kbps 48 kHz, faststart |

## Pacing by section
""" + '\n'.join(f"- **{k}**: {len(v)} shots, avg {np.mean(v):.2f} s" for k, v in secs.items()) + f"""

## Beat sync method
{music['method']}. The beat grid sets every cut point, and each shot is 1, 2, 4 or 8 beats long.
The shot length follows the music's energy on that beat: about 1 beat in the 8 beats after a drop and on high-energy bars, 2–4 beats in calmer passages, and long shots in the intro.
Drops are the largest rises in 1-second RMS energy: {', '.join(f'{x:.2f}s' for x in music['drops'])}.
Each drop gets a cut, a white flash, a decaying camera shake, a 6% punch-in, an impact SFX and, where planned, a title slam.
A riser starts 2 s before each of the first two drops. Shot boundaries are rounded to whole frames at {FPS} fps.

## Shot selection
Each file is analysed from keyframes sampled at 2 fps, scaled down to 192x108. The script measures sharpness (Laplacian variance), exposure, contrast and motion, then ranks the clips into grades A–D.
Near-duplicates are found by comparing perceptual hashes (dHash) at 20/50/80% through each clip; only the best-scoring copy of each duplicate group is kept.
The shot order follows the event: capture time, or the `--order` keywords. A/B clips are moved onto the drops (swapped within ±3 slots), and the best video is held back for the slow-motion finale.

## Colour
Pass 1 corrects exposure per clip, using its measured brightness.
Pass 2 applies the same gentle look to every shot: S-curve, teal shadows / warm highlights, +7% contrast, a small saturation lift and a light vignette.
There is no LUT, and skin tones are protected because the hue shift is small.

## Audio
The BGM is the master track. Its gain is only ever lowered, to give -1 dBFS peak headroom, and it is never cut or replaced.
The SFX are synthesised by the script (whoosh, impact, boom, riser) and kept 8–11 dB below the BGM. A limiter at -1 dBFS sits on the mix, with a 0.6 s fade-out at the end.
Original camera audio is muted.

## Validation
See VALIDATION_REPORT.md: **{'PASS' if val['pass'] else 'ISSUES FOUND'}**.

## Known limitations / not automated
- No `.drp` is produced by this script. A genuine `.drp` can only be exported by DaVinci Resolve: run `FAILATHON_AV_RESOLVE_SCRIPT.py` inside Resolve, which builds the project and calls `ExportProject`.
- Shot selection is based on measured image quality, not on what is in the frame (no face or object recognition). Check the contact sheet and swap shots in Resolve if needed.
- Speed ramps and grades are baked into the graded shot files on timeline V1. The Resolve script also builds a second timeline from the untouched source media for regrading.
- Titles are pre-rendered ProRes 4444 clips with alpha (same look in the MP4 and in Resolve). Text+ versions are added for editing where the Resolve API allows.
"""
    (ws / '09_REPORTS/EDIT_REPORT.md').write_text(rep, encoding='utf-8')
    v = f"""# FAILATHON AV — Validation Report

| Check | Result |
|---|---|
| Output file | `07_EXPORTS/FAILATHON_AV_FINAL.mp4` ({val['container']}) |
| Video stream | {val['video']} |
| Audio stream | {val['audio']} |
| Duration vs BGM | {val['duration']:.3f} s vs {val['bgm_duration']:.3f} s — {'OK' if val['duration_ok'] else 'MISMATCH'} |
| Unintended black frames | {val['unintended_black'] or 'none'} (head/tail fades are intentional: {val['black_segments']}) |
| Unexpected silence (> 0.6 s) | {val['silences'] or 'none'} |
| Audio peak | {val['audio_peak_db']} dBFS — {'CLIPPING' if val['clipping'] else 'OK'} |
| Full decode | {val['decode_errors'] or 'clean, no errors'} |
| Missing media | {', '.join(i['rel'] for i in items if i['status'] == 'broken') or 'none'} |
| Overall | **{'PASS' if val['pass'] else 'ISSUES FOUND'}** |

`.drp`: not produced here. It has to be exported by DaVinci Resolve (see 03_RESOLVE/README_RESOLVE.md).
"""
    (ws / '09_REPORTS/VALIDATION_REPORT.md').write_text(v, encoding='utf-8')


if __name__ == '__main__':
    main()
