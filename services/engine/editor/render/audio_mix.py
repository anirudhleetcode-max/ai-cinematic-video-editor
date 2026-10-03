"""Audio engine: dialogue assembly with overlap crossfades → dialogue processing chain → music bed
(window selection, multi-song crossfades) → ducking automation driven by the processed dialogue →
SFX / voice-over → limiter → two-pass EBU R128 loudness normalisation."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from ..config import get_settings
from ..proc import run
from ..registry.audio import AUDIO_PRESETS, synth_sfx
from ..schemas import EditPlan

SR = 48000


def _decode_stereo(path: Path, start: float = 0.0, dur: float | None = None) -> np.ndarray:
    st = get_settings()
    cmd = [st.ffmpeg, "-v", "error", "-nostdin"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    p = subprocess.run(cmd, capture_output=True, timeout=1800)
    if p.returncode != 0 or not p.stdout:
        return np.zeros((0, 2), np.float32)
    return np.frombuffer(p.stdout, np.float32).reshape(-1, 2).copy()


def _fade(x: np.ndarray, n_in: int, n_out: int, power: bool = True) -> np.ndarray:
    y = x.copy()
    if n_in > 0:
        r = np.linspace(0, 1, min(n_in, len(y)), dtype=np.float32)
        y[: len(r)] *= (np.sin(r * np.pi / 2) if power else r)[:, None]
    if n_out > 0:
        r = np.linspace(1, 0, min(n_out, len(y)), dtype=np.float32)
        y[len(y) - len(r):] *= (np.sin(r * np.pi / 2) if power else r)[:, None]
    return y


def _place(track: np.ndarray, x: np.ndarray, at: float, gain_db: float = 0.0) -> None:
    i = int(round(at * SR))
    if i >= len(track) or len(x) == 0:
        return
    n = min(len(x), len(track) - i)
    track[i:i + n] += x[:n] * (10 ** (gain_db / 20))


def build_dialogue(plan: EditPlan, seg_audio: dict[str, Path], total: float, role: str = "dialogue",
                   level_report: list | None = None) -> np.ndarray:
    """Assemble clip audio of one role ("dialogue" or "ambience") with crossfades on transition overlaps and 12 ms
    micro-fades on cuts. Dialogue clips are level-matched: each clip's speech RMS is brought to
    plan.audio.dialogue_target_db (±9 dB max) so speakers recorded at different distances don't jump in volume."""
    track = np.zeros((int(total * SR) + SR, 2), np.float32)
    regions = np.array(plan.audio.speech_regions or [], np.float64).reshape(-1, 2)
    for k, s in enumerate(plan.timeline):
        if not s.keep_audio or s.id not in seg_audio or s.audio_role != role:
            continue
        x, _ = sf.read(seg_audio[s.id], dtype="float32", always_2d=True)
        if x.shape[1] == 1:
            x = np.repeat(x, 2, 1)
        gain = s.audio_gain_db
        if role == "dialogue" and len(x):
            # speech-only RMS of this clip (regions inside the segment), else whole-clip RMS
            mono = np.abs(x).mean(1)
            sel = np.zeros(len(mono), bool)
            for a_, b_ in regions:
                i0, i1 = int((a_ - s.out_start) * SR), int((b_ - s.out_start) * SR)
                if i1 > 0 and i0 < len(mono):
                    sel[max(0, i0):min(len(mono), i1)] = True
            v = mono[sel] if sel.sum() > SR * 0.3 else mono
            rms_db = float(20 * np.log10(np.sqrt((v ** 2).mean()) + 1e-9))
            if rms_db > -60:
                adj = float(np.clip(plan.audio.dialogue_target_db - rms_db, -9.0, 9.0))
                gain += adj
                if level_report is not None:
                    level_report.append({"segment": s.id, "speech_rms_db": round(rms_db, 1), "gain_db": round(adj, 1)})
        head = s.transition_in.duration if s.transition_in.id != "cut" else 0.0
        nxt = plan.timeline[k + 1] if k + 1 < len(plan.timeline) else None
        tail = nxt.transition_in.duration if (nxt and nxt.transition_in.id != "cut") else 0.0
        x = _fade(x, int(max(head, 0.012) * SR), int(max(tail, 0.012) * SR))
        _place(track, x, s.out_start, gain)
    return track


def speech_mask_envelope(regions: list, n: int, depth_db: float, attack: float, release: float, pad: float = 0.15) -> np.ndarray:
    """Linear gain automation: −depth inside speech regions (padded), smoothed with attack/release time constants —
    music/ambience/SFX glide down before a line and back up after it (never a hard cut in level)."""
    hop = int(0.02 * SR)
    m = n // hop + 1
    if depth_db <= 0 or not regions:
        return np.ones(n, np.float32)
    target = np.zeros(m)
    for a, b in regions:
        target[max(0, int((a - pad) / 0.02)):min(m, int((b + pad) / 0.02) + 1)] = -depth_db
    g = np.zeros(m)
    a_c, r_c = np.exp(-0.02 / max(attack, 1e-3)), np.exp(-0.02 / max(release, 1e-3))
    cur = 0.0
    for i, t in enumerate(target):
        c = a_c if t < cur else r_c
        cur = c * cur + (1 - c) * t
        g[i] = cur
    return np.interp(np.arange(n), np.arange(m) * hop + hop / 2, 10 ** (g / 20)).astype(np.float32)


def process_dialogue(track: np.ndarray, preset: str, tmp: Path) -> np.ndarray:
    if not np.any(track):
        return track
    st = get_settings()
    chain = AUDIO_PRESETS.get(preset if AUDIO_PRESETS.has(preset) else "dialogue_clean").render({})
    a, b = tmp / "dlg_in.wav", tmp / "dlg_out.wav"
    sf.write(a, track, SR, subtype="FLOAT")
    run([st.ffmpeg, "-v", "error", "-y", "-i", str(a), "-af", chain, "-ar", str(SR), "-c:a", "pcm_f32le", str(b)], timeout=1800)
    y, _ = sf.read(b, dtype="float32", always_2d=True)
    out = np.zeros_like(track)
    out[: min(len(y), len(out))] = y[: len(out)]
    return out


def build_music(plan: EditPlan, asset_paths: dict[str, Path], total: float) -> np.ndarray:
    track = np.zeros((int(total * SR) + SR, 2), np.float32)
    cache: dict[str, np.ndarray] = {}
    for m in plan.music:
        if m.asset_id not in asset_paths:
            continue
        L = m.out_end - m.out_start
        key = f"{m.asset_id}:{m.src_in:.3f}:{L:.3f}"
        if key not in cache:
            cache[key] = _decode_stereo(asset_paths[m.asset_id], m.src_in, L)
        x = _fade(cache[key], int(m.fade_in * SR), int(m.fade_out * SR))
        _place(track, x, m.out_start, m.gain_db)
    return track


def duck_envelope(dialogue: np.ndarray, depth_db: float, attack: float, release: float, threshold_db: float = -42.0) -> np.ndarray:
    """Gain curve (linear) for the music bed: −depth when dialogue is active, with attack/release smoothing."""
    hop = int(0.02 * SR)
    mono = np.abs(dialogue).mean(1)
    n = len(mono) // hop
    if n == 0 or depth_db <= 0:
        return np.ones(len(dialogue), np.float32)
    rms = np.sqrt((mono[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    active = (db > threshold_db).astype(np.float32)
    # hold for 250 ms to avoid pumping between words
    hold = int(0.25 / 0.02)
    act = np.convolve(active, np.ones(hold), mode="same") > 0
    target = np.where(act, -depth_db, 0.0)
    g = np.zeros(n)
    a_c = np.exp(-0.02 / max(attack, 1e-3))
    r_c = np.exp(-0.02 / max(release, 1e-3))
    cur = 0.0
    for i, t in enumerate(target):
        c = a_c if t < cur else r_c
        cur = c * cur + (1 - c) * t
        g[i] = cur
    lin = 10 ** (g / 20)
    return np.interp(np.arange(len(dialogue)), np.arange(n) * hop + hop / 2, lin).astype(np.float32)


def build_sfx(plan: EditPlan, asset_paths: dict[str, Path], total: float) -> np.ndarray:
    track = np.zeros((int(total * SR) + SR, 2), np.float32)
    for k, s in enumerate(plan.sfx):
        if s.asset_id and s.asset_id in asset_paths:
            x = _decode_stereo(asset_paths[s.asset_id])
        else:
            mono = synth_sfx(s.kind, SR, seed=k, length=s.params.get("length"))
            x = np.stack([mono, mono], 1)
        _place(track, x, max(0.0, s.at), s.gain_db)  # risers are scheduled to *end* at the hit (see SoundDesigner)
    return track


def loudness(path: Path) -> dict:
    st = get_settings()
    p = subprocess.run([st.ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=1800)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr)
    return json.loads(m.group(0)) if m else {}


def mix(plan: EditPlan, seg_audio: dict[str, Path], asset_paths: dict[str, Path], out: Path, tmp: Path) -> dict:
    total = plan.duration
    n = int(round(total * SR))
    levels: list = []
    dlg = process_dialogue(build_dialogue(plan, seg_audio, total, "dialogue", levels), plan.audio.dialogue_preset, tmp)
    amb = build_dialogue(plan, seg_audio, total, "ambience")
    music = build_music(plan, asset_paths, total)
    report = {"dialogue_active": bool(np.any(dlg)), "ambience_active": bool(np.any(amb)), "music_active": bool(np.any(music)),
              "dialogue_levels": levels[:200]}
    L = len(dlg)
    if plan.audio.speech_regions and plan.audio.ducking:
        # dialogue priority: duck music, ambience and SFX only where speech was detected (VAD regions)
        gm = speech_mask_envelope(plan.audio.speech_regions, L, plan.audio.duck_depth_db, plan.audio.duck_attack, plan.audio.duck_release)
        ga = speech_mask_envelope(plan.audio.speech_regions, L, plan.audio.ambience_duck_db, plan.audio.duck_attack, plan.audio.duck_release)
        gs = speech_mask_envelope(plan.audio.speech_regions, L, plan.audio.sfx_duck_db, plan.audio.duck_attack, plan.audio.duck_release)
        music *= gm[:, None]
        amb *= ga[:, None]
        report["ducking_min_gain_db"] = round(float(20 * np.log10(gm.min() + 1e-9)), 2)
        report["ducked_seconds"] = round(float((gm < 10 ** (-3 / 20)).sum() / SR), 2)
        report["speech_seconds"] = round(float(sum(b - a for a, b in plan.audio.speech_regions)), 2)
    elif plan.audio.ducking and np.any(dlg) and np.any(music):  # no VAD regions: energy-driven ducking (legacy)
        g = duck_envelope(dlg, plan.audio.duck_depth_db, plan.audio.duck_attack, plan.audio.duck_release)
        music *= g[:, None]
        gs = None
        report["ducking_min_gain_db"] = round(float(20 * np.log10(g.min() + 1e-9)), 2)
    else:
        gs = None
    vo = np.zeros_like(dlg)
    for v in plan.voiceover:
        if v.asset_id in asset_paths:
            _place(vo, _decode_stereo(asset_paths[v.asset_id]), v.out_start, v.gain_db)
    sfx = build_sfx(plan, asset_paths, total)
    if plan.audio.speech_regions and plan.audio.ducking and gs is not None:
        sfx *= gs[:, None]
    dlg = dlg + amb
    y = (dlg * 10 ** (plan.audio.dialogue_gain_db / 20) + music + vo + sfx)[:n]
    # end fade (0.6 s) to avoid an abrupt stop
    y = _fade(y, 0, int(0.6 * SR), power=False)
    # soft limiter before loudness normalisation
    peak = float(np.abs(y).max()) if len(y) else 0.0
    if peak > 0.98:
        y = np.tanh(y / peak * 1.2) / np.tanh(1.2) * 0.98
    raw = tmp / "mix_raw.wav"
    sf.write(raw, y, SR, subtype="FLOAT")
    st = get_settings()
    meas = loudness(raw)
    if meas and float(meas.get("input_i", "-70")) > -60:
        ln = (f"loudnorm=I={plan.audio.target_lufs}:TP={plan.audio.true_peak_db}:LRA=11:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
              f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear=true")
        run([st.ffmpeg, "-v", "error", "-y", "-i", str(raw), "-af", f"{ln},aresample={SR}", "-ar", str(SR), "-c:a", "pcm_s16le", str(out)], timeout=1800)
    else:
        run([st.ffmpeg, "-v", "error", "-y", "-i", str(raw), "-c:a", "pcm_s16le", str(out)])
    final = loudness(out)
    report.update(integrated_lufs=float(final.get("input_i", -70)), true_peak_db=float(final.get("input_tp", -70)), lra=float(final.get("input_lra", 0)),
                  target_lufs=plan.audio.target_lufs)
    return report
