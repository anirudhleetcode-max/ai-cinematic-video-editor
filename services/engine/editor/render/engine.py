"""Render orchestrator: EditPlan → MP4.

Stages (reported with real progress): segments (parallel, cached) → transitions → audio mix →
final pass (creative LUT, finishing, global effects, end card, text) → QC → auto-fix/retry."""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import psutil

from ..config import get_settings
from ..hw import encoder_args, pick_encoder
from ..logging import get_logger, log
from ..proc import MediaCommandError, ff_path, replace_file, run, run_ffmpeg_progress
from ..qc.check import quality_check
from ..registry.color import clamp_params, finishing_filters, preset_params, write_cube
from ..registry.effects import render_effect
from ..schemas import EditPlan
from . import audio_mix
from .colorspace import MEZZ_TO_RGB, TO_YUV420
from .segments import SegJob, SegResult, frames_for, render_segment, x264_mezz_args
from .text_ass import AssBuilder, write_srt
from .transitions import render_transition

logger = get_logger("render")
Progress = Callable[[str, float, str], None]


@dataclass
class AssetInfo:
    path: Path
    fingerprint: str
    meta: dict
    proxy: Path | None = None


PROXY_META = {"inspection": {"color_space": "bt709", "color_range": "limited"}}


def _noop(stage: str, frac: float, msg: str) -> None:
    pass


def scaled_export(plan: EditPlan, preview: bool) -> tuple[int, int, float, str]:
    if not preview:
        return plan.export.width, plan.export.height, plan.fps, plan.export.quality
    s = 640 / max(plan.export.width, plan.export.height)
    w = int(plan.export.width * s) // 2 * 2
    h = int(plan.export.height * s) // 2 * 2
    return w, h, plan.fps, "draft"


def render_end_card(plan: EditPlan, assets: dict[str, AssetInfo], out: Path, w: int, h: int, fps: float, quality: str, brand: dict | None) -> Path:
    st = get_settings()
    d = plan.ending.duration
    bg = (brand or {}).get("background", "0x0c0d10").replace("#", "0x")
    # dark backdrop with a soft radial falloff (vignette), no YUV blending
    g = f"color=c={bg}:s={w}x{h}:r={fps}:d={d:.3f},format=gbrp,vignette=angle=0.9:mode=backward,vignette=angle=0.6[base]"
    inputs: list[str] = []
    last = "base"
    if plan.ending.logo_asset_id and plan.ending.logo_asset_id in assets:
        lw = int(w * (0.32 if w >= h else 0.5))
        inputs = ["-loop", "1", "-t", f"{d:.3f}", "-i", str(assets[plan.ending.logo_asset_id].path)]
        y_expr = "(H-h)/2-H*0.06" if plan.ending.type == "logo_title" else "(H-h)/2"
        g += (f";[0:v]scale={lw}:-2,format=rgba,fade=t=in:st=0.25:d=0.7:alpha=1[lg];"
              f"[base][lg]overlay=x=(W-w)/2:y={y_expr}:shortest=1:format=gbrp[lo]")
        last = "lo"
    g += f";[{last}]fade=t=in:st=0:d=0.45,fps={fps},trim=end_frame={frames_for(d, fps)},{TO_YUV420}[v]"
    run([st.ffmpeg, "-v", "error", "-y", *inputs, "-filter_complex", g, "-map", "[v]", *x264_mezz_args(quality), "-an", str(out)], timeout=600)
    return out


def _creative_graph(plan: EditPlan, tmp: Path, w: int, h: int) -> tuple[str, str]:
    gp = preset_params(plan.color_grade.preset, plan.color_grade.overrides)
    lut = write_cube(tmp / "creative.cube", gp, plan.color_grade.intensity)
    chain = f"[0:v]{MEZZ_TO_RGB},lut3d=file={ff_path(lut)}:interp=tetrahedral"
    fin = finishing_filters(gp, w, h, plan.color_grade.intensity)
    if fin:
        chain += "," + ",".join(fin)
    chain += "[cg]"
    cur = "cg"
    parts = [chain]
    effects = list(plan.effects_global)
    if clamp_params(gp)["halation"] * plan.color_grade.intensity > 0 and not any(e.id == "halation" for e in effects):
        from ..schemas import EffectInstance
        effects.append(EffectInstance(id="halation", params={"intensity": round(0.4 * clamp_params(gp)["halation"] * min(1.0, plan.color_grade.intensity), 3)}))
    ctx = {"w": w, "h": h, "dur": plan.duration, "fps": plan.fps}
    for k, e in enumerate(effects):
        try:
            parts.append(render_effect(e.id, dict(e.params), ctx, cur, f"ge{k}"))
            cur = f"ge{k}"
        except KeyError:
            continue
    return ";".join(parts), cur


def fix_clipping(path: Path, limit: float = 0.79) -> None:
    """QC auto-fix: re-limit the audio stream only (video stream copied)."""
    st = get_settings()
    tmp = path.with_suffix(".fix.mp4")
    run([st.ffmpeg, "-v", "error", "-y", "-i", str(path), "-c:v", "copy", "-af", f"alimiter=limit={limit}:level=false", "-c:a", "aac", "-b:a", "320k",
         "-movflags", "+faststart", str(tmp)], timeout=1800)
    replace_file(tmp, path)


def render_plan(plan: EditPlan, assets: dict[str, AssetInfo], out_path: Path, work: Path, progress: Progress = _noop, preview: bool = False,
                brand: dict | None = None, prefer_hw: bool = True) -> dict:
    t_start = time.perf_counter()
    st = get_settings()
    w, h, fps, quality = scaled_export(plan, preview)
    work.mkdir(parents=True, exist_ok=True)
    cache = work.parent / "segment_cache"
    tmp = work / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    report: dict = {"preview": preview, "width": w, "height": h, "fps": fps, "fallbacks": [], "timings": {}}
    proc_peak = {"rss": 0}

    def mem():
        try:
            rss = psutil.Process().memory_info().rss
            proc_peak["rss"] = max(proc_peak["rss"], rss)
        except Exception:  # noqa: BLE001
            pass

    # ---- 1. segments -----------------------------------------------------------------------
    t0 = time.perf_counter()
    jobs = []
    for k, s in enumerate(plan.timeline):
        ai = assets[s.asset_id]
        src = ai.proxy if (preview and ai.proxy and ai.proxy.exists()) else ai.path
        sw = ai.meta.get("display_width") or ai.meta.get("width") or w
        sh = ai.meta.get("display_height") or ai.meta.get("height") or h
        src_meta = ai.meta
        if preview and ai.proxy and ai.proxy.exists():
            sw, sh = int(sw * 360 / sh) // 2 * 2, 360
            src_meta = PROXY_META  # proxies are already square-pixel BT.709 limited-range SDR
        nxt = plan.timeline[k + 1] if k + 1 < len(plan.timeline) else None
        head = s.transition_in.duration if (k > 0 and s.transition_in.id != "cut") else 0.0
        tail = nxt.transition_in.duration if (nxt and nxt.transition_in.id != "cut") else 0.0
        jobs.append(SegJob(s, src, ai.fingerprint + ("p" if src != ai.path else ""), bool(ai.meta.get("has_audio")), int(sw), int(sh), head, tail,
                           w, h, fps, quality, cache, plan.mode, src_meta, ai.path))
    results: dict[str, SegResult] = {}
    n_workers = max(1, min(4, (psutil.cpu_count() or 2) // 2 + (0 if preview else 0)))
    done = 0
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        futs = {ex.submit(render_segment, j): j for j in jobs}
        for f in as_completed(futs):
            j = futs[f]
            try:
                r = f.result()
            except Exception as e:  # clip failed entirely → planner-level recovery happens in the caller
                raise RuntimeError(f"segment {j.seg.id} ({j.src.name}) failed: {e}") from e
            results[r.seg_id] = r
            report["fallbacks"] += [f"{r.seg_id}: {x}" for x in r.fallbacks]
            done += 1
            mem()
            progress("rendering", done / len(jobs) * 0.55, f"segment {done}/{len(jobs)}{' (cached)' if r.cached else ''}")
    report["segments_cached"] = sum(1 for r in results.values() if r.cached)
    report["segments_rendered"] = len(results) - report["segments_cached"]
    report["timings"]["segments_s"] = round(time.perf_counter() - t0, 2)

    # ---- 2. transitions + assembly list -----------------------------------------------------
    t0 = time.perf_counter()
    pieces: list[Path] = []
    for k, s in enumerate(plan.timeline):
        r = results[s.id]
        if k > 0 and r.head is not None:
            prev = results[plan.timeline[k - 1].id]
            tkey = hashlib.sha256(json.dumps([str(prev.tail), str(r.head), s.transition_in.id, s.transition_in.duration, s.transition_in.params],
                                             sort_keys=True).encode()).hexdigest()[:20]
            tp = cache / f"tr_{tkey}.mp4"
            if not tp.exists():
                _, note = render_transition(s.transition_in.id, dict(s.transition_in.params), prev.tail, r.head, tp, w, h, fps, quality)  # type: ignore[arg-type]
                if note:
                    report["fallbacks"].append(f"transition {s.id}: {note}")
            pieces.append(tp)
        pieces.append(r.body)  # type: ignore[arg-type]
    progress("rendering", 0.62, "transitions built")
    lst = work / "pieces.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in pieces))
    report["timings"]["transitions_s"] = round(time.perf_counter() - t0, 2)

    # ---- 3. audio ----------------------------------------------------------------------------
    t0 = time.perf_counter()
    progress("mixing_audio", 0.64, "dialogue, music bed, ducking, SFX, loudness")
    mix_path = work / "mix.wav"
    seg_audio = {sid: r.audio for sid, r in results.items()}
    # the mix depends only on audio-relevant plan fields + the segment audio files + source fingerprints: cache it, so a
    # colour / text / ending-only revision reuses it (dependency-aware invalidation)
    mix_key = hashlib.sha256(json.dumps({
        "v": "mix3", "audio": plan.audio.model_dump(), "music": [m.model_dump() for m in plan.music], "sfx": [x.model_dump() for x in plan.sfx],
        "vo": [v.model_dump() for v in plan.voiceover], "dur": plan.duration,
        "segs": [[sg.id, sg.out_start, sg.out_duration, sg.keep_audio, sg.audio_role, sg.audio_gain_db, sg.transition_in.id, sg.transition_in.duration,
                  str(results[sg.id].audio.parent.name) if sg.id in results else None] for sg in plan.timeline],
        "fps": {k: v.fingerprint for k, v in assets.items() if any(m.asset_id == k for m in plan.music) or any(x.asset_id == k for x in plan.sfx)},
    }, sort_keys=True, default=str).encode()).hexdigest()[:24]
    mix_cache = cache.parent / "mix_cache" / mix_key
    try:
        if (mix_cache / "mix.wav").exists() and (mix_cache / "report.json").exists():
            shutil.copyfile(mix_cache / "mix.wav", mix_path)
            report["audio"] = {**json.loads((mix_cache / "report.json").read_text()), "cached": True}
        else:
            report["audio"] = audio_mix.mix(plan, seg_audio, {k: v.path for k, v in assets.items()}, mix_path, tmp)
            mix_cache.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(mix_path, mix_cache / "mix.wav")
            (mix_cache / "report.json").write_text(json.dumps(report["audio"], default=str))
    except Exception as e:  # noqa: BLE001 — keep producing a video even if the mixer fails
        report["fallbacks"].append(f"audio mix failed ({type(e).__name__}: {str(e)[:120]}) → silence")
        run([st.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{plan.duration:.3f}", str(mix_path)])
        report["audio"] = {"error": str(e)[:300]}
    report["timings"]["audio_s"] = round(time.perf_counter() - t0, 2)

    # ---- 4. text -----------------------------------------------------------------------------
    ass = AssBuilder(w, h)
    for tx in plan.text:
        ass.add(tx)
    ass.add_captions(plan.captions)
    ass_path = ass.write(work / "text.ass")
    if plan.captions.enabled and plan.captions.words:
        write_srt(plan.captions.words, out_path.with_suffix(".srt"))
        report["subtitles"] = [str(out_path.with_suffix(".srt")), str(out_path.with_suffix(".vtt"))]
    report["text_violations"] = ass.violations

    # ---- 5. final pass ------------------------------------------------------------------------
    t0 = time.perf_counter()
    progress("rendering", 0.68, "final pass: grade, effects, typography, encode")
    graph, cur = _creative_graph(plan, tmp, w, h)
    inputs = ["-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(mix_path)]
    if plan.ending.duration > 0:
        card = render_end_card(plan, assets, work / "endcard.mp4", w, h, fps, quality, brand)
        inputs += ["-i", str(card)]
        graph += f";[{cur}]setpts=PTS-STARTPTS[gb];[2:v]setpts=PTS-STARTPTS[ec];[gb][ec]concat=n=2:v=1:a=0[cat]"
        cur = "cat"
    elif plan.ending.type == "fade":
        graph += f";[{cur}]fade=t=out:st={max(0.0, plan.duration - 1.2):.3f}:d=1.2[fo]"
        cur = "fo"
    graph += ";[1:a]alimiter=limit=0.891:level=false:attack=2:release=60,aresample=48000[aout]"
    graph += f";[{cur}]ass={ff_path(ass_path)}:fontsdir={ff_path(st.fonts_dir)},fps={fps},trim=end_frame={frames_for(plan.duration, fps)},{TO_YUV420}[vout]"
    enc = pick_encoder(plan.export.vcodec, prefer_hw=prefer_hw and plan.export.prefer_hw and not preview)
    tried = []
    for e in [enc, "libx264"] if enc != "libx264" else ["libx264"]:
        tried.append(e)
        cmd = [st.ffmpeg, "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
               *encoder_args(e, quality), "-r", str(fps), "-c:a", "aac", "-b:a", f"{plan.export.audio_bitrate_k}k", "-ar", "48000", "-ac", "2",
               "-movflags", "+faststart", "-shortest", str(out_path)]
        try:
            run_ffmpeg_progress(cmd, plan.duration, lambda f: progress("rendering", 0.68 + 0.25 * f, "encoding"))
            report["encoder"] = e
            break
        except MediaCommandError as ex:
            report["fallbacks"].append(f"encoder {e} failed → {'CPU' if e != 'libx264' else 'none'} ({str(ex)[:160]})")
            if e == "libx264":
                raise
    report["timings"]["final_pass_s"] = round(time.perf_counter() - t0, 2)
    mem()

    # ---- 6. QC ---------------------------------------------------------------------------------
    t0 = time.perf_counter()
    progress("quality_check", 0.95, "ffprobe + black/freeze/silence/clipping detectors")
    expect_audio = bool(plan.music) or any(s.keep_audio for s in plan.timeline)
    qc = quality_check(out_path, plan, expect_audio, ass.violations, draft=preview)
    report["qc"] = qc
    report["timings"]["qc_s"] = round(time.perf_counter() - t0, 2)
    report["timings"]["total_s"] = round(time.perf_counter() - t_start, 2)
    report["peak_rss_mb"] = round(proc_peak["rss"] / 2**20, 1)
    report["output"] = str(out_path)
    report["size_bytes"] = out_path.stat().st_size if out_path.exists() else 0
    shutil.rmtree(tmp, ignore_errors=True)
    log(logger, "render done", out=out_path.name, preview=preview, total_s=report["timings"]["total_s"], qc=qc["passed"])
    return report
