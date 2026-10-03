"""Measured post-render reviews.

reference_match()  — Reference Match Report: the rendered edit is analysed with the *same* analyser as the reference
                     and compared metric by metric. Scores are measurable similarity in [0, 1] per metric — not a
                     claim that the style was replicated.
review_checklist() — deterministic professional review checklist (story, pacing, shot selection, variety,
                     transitions, colour, audio, text, motion, ending, technical). Each item: pass / warn / fail with
                     the measured values that decided it.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from ..director.pacing import ROLE_RANGE, role_of
from ..media import frames as F
from ..media.probe import probe
from ..schemas import EditPlan


def _sim_ratio(a: float | None, b: float | None) -> float | None:
    if not a or not b or a <= 0 or b <= 0:
        return None
    return round(float(max(0.0, 1 - abs(math.log(a / b)) / math.log(2))), 3)  # 1 = equal, 0 = factor 2 apart


def _sim_abs(a: float | None, b: float | None, scale: float) -> float | None:
    if a is None or b is None:
        return None
    return round(float(max(0.0, 1 - abs(a - b) / scale)), 3)


def _hist_sim(a: list | None, b: list | None) -> float | None:
    if not a or not b or len(a) != len(b) or not sum(a) or not sum(b):
        return None
    pa, pb = np.array(a, float) / sum(a), np.array(b, float) / sum(b)
    return round(float(np.minimum(pa, pb).sum()), 3)  # histogram intersection


def reference_match(ref: dict, output: Path, plan: EditPlan) -> dict:
    from ..reference.analyze import analyze_reference

    out = analyze_reference(output)  # same analyser, no cache
    end = plan.ending.duration if plan.ending.type != "cut" else 0.0
    rows = []

    def add(metric: str, r, o, sim, kind: str = "measured"):
        rows.append({"metric": metric, "reference": r, "output": o, "similarity": sim, "basis": kind})

    add("median shot length (s)", ref.get("median_shot_duration"), out.get("median_shot_duration"),
        _sim_ratio(ref.get("median_shot_duration"), out.get("median_shot_duration")))
    add("cuts per minute", ref.get("cuts_per_minute"), out.get("cuts_per_minute"), _sim_ratio(ref.get("cuts_per_minute"), out.get("cuts_per_minute")))
    add("shot-length distribution", ref.get("shot_length_hist"), out.get("shot_length_hist"), _hist_sim(ref.get("shot_length_hist"), out.get("shot_length_hist")))
    add("transition density", ref.get("transition_frequency"), out.get("transition_frequency"),
        _sim_abs(ref.get("transition_frequency"), out.get("transition_frequency"), 0.3), "inferred (frame-statistics transition classifier)")
    for k, scale in (("brightness", 0.2), ("contrast", 0.1), ("saturation", 0.2), ("temperature", 0.1), ("tint", 0.05)):
        add(f"colour: {k}", ref.get(k), out.get(k), _sim_abs(ref.get(k), out.get(k), scale))
    rg, og = ref.get("grade") or {}, out.get("grade") or {}
    for zone in ("shadows", "highlights"):
        a, b = (rg.get(zone) or {}).get("temperature"), (og.get(zone) or {}).get("temperature")
        add(f"colour: {zone} warmth", a, b, _sim_abs(a, b, 0.1))
    ref_txt = len(ref.get("text_events") or []) / max(1e-3, ref.get("duration", 1)) * 60
    out_txt = len(out.get("text_events") or []) / max(1e-3, out.get("duration", 1)) * 60
    add("text events per minute", round(ref_txt, 2), round(out_txt, 2), _sim_abs(ref_txt, out_txt, max(2.0, ref_txt)), "heuristic text detector")
    rm, om = (ref.get("music") or {}).get("energy_mean"), (out.get("music") or {}).get("energy_mean")
    add("music energy (mean)", rm, om, _sim_abs(rm, om, 0.3))
    scored = [r["similarity"] for r in rows if r["similarity"] is not None]
    return {"metrics": rows, "overall_similarity": round(float(np.mean(scored)), 3) if scored else None,
            "note": "Measured similarity between the reference and this edit on each metric (1 = identical value). "
                    "It describes how closely measurable properties match; it is not a claim of stylistic replication."
                    + (f" The output includes a {end:.1f}s end card, which the reference may not have." if end else "")}


def segment_color_continuity(output: Path, plan: EditPlan) -> dict:
    """Measured colour continuity of the rendered edit: mean luma / temperature / saturation per segment (sampled at
    4 fps on the output) and the largest jumps between adjacent segments inside the same section."""
    meta = probe(output)
    fs = F.sample_frames(output, 4.0, 128, meta=meta)
    if not len(fs.rgb):
        return {}
    px = fs.rgb.astype(np.float32) / 255
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    luma = (0.299 * r + 0.587 * g + 0.114 * b).mean((1, 2))
    temp = (r - b).mean((1, 2))
    mx, mn = px.max(-1), px.min(-1)
    sat = np.where(mx > 1e-3, (mx - mn) / np.maximum(mx, 1e-3), 0).mean((1, 2))
    stats = []
    for s in plan.timeline:
        a, b_ = s.out_start + 0.15 * s.out_duration, s.out_start + 0.85 * s.out_duration
        m = (fs.times >= a) & (fs.times <= b_)
        if m.any():
            stats.append((s, float(luma[m].mean()), float(temp[m].mean()), float(sat[m].mean())))
    jl = jt = js = 0.0
    worst = None
    for (s0, l0, t0, z0), (s1, l1, t1, z1) in zip(stats, stats[1:]):
        if s0.section != s1.section:
            continue
        if abs(l1 - l0) > jl:
            jl, worst = abs(l1 - l0), s1.id
        jt, js = max(jt, abs(t1 - t0)), max(js, abs(z1 - z0))
    return {"segments_measured": len(stats), "max_adjacent_luma_jump": round(jl, 3), "max_adjacent_temperature_jump": round(jt, 3),
            "max_adjacent_saturation_jump": round(js, 3), "worst_luma_jump_at": worst}


def review_checklist(plan: EditPlan, qc: dict, audio: dict, report: dict, ctx_shots: dict[str, dict] | None = None,
                     color: dict | None = None) -> dict:
    items = []

    def item(area: str, question: str, status: str, evidence: dict):
        items.append({"area": area, "question": question, "status": status, "evidence": evidence})

    secs = [s.name for s in plan.story_structure]
    roles = [role_of(n) for n in secs]
    has_begin = any(r in ("hook", "opening") for r in roles[:2])
    has_peak = any(r == "climax" for r in roles)
    has_end = plan.ending.type != "cut" or roles[-1] in ("resolution", "climax")
    item("STORY", "Clear beginning / middle / end?", "pass" if (has_begin and has_peak and has_end and len(secs) >= 3) else "warn",
         {"sections": secs, "ending": plan.ending.type})
    # pacing: shot lengths inside their role's range (scaled by the plan's pacing factor)
    pf = (plan.intent.pacing_factor if plan.intent and plan.intent.pacing_factor else 1.0)
    inside = 0
    for s in plan.timeline:
        lo, hi = ROLE_RANGE[role_of(s.section)]
        inside += int(lo * pf * 0.6 <= s.out_duration <= hi * pf * 1.4)
    frac = inside / max(1, len(plan.timeline))
    item("PACING", "Does pacing follow the narrative roles and the music?", "pass" if frac >= 0.7 else "warn",
         {"shots_within_role_range": round(frac, 3), "beat_synced_cut_notes": [d for d in plan.decisions if d.startswith("Timeline:")][:1]})
    keys = [(s.asset_id, s.shot_index) for s in plan.timeline]
    if ctx_shots:
        used = [ctx_shots.get(f"{a}:{i}", {}) for a, i in keys]
        used_scores = [u.get("overall_edit_score", 0) for u in used if u]
        avail = [v.get("overall_edit_score", 0) for v in ctx_shots.values() if not ({"black", "frozen", "too_short", "obstructed", "duplicate"} & set(v.get("issues", [])))]
        hard_used = sum(1 for u in used if {"black", "frozen", "too_short", "obstructed", "duplicate"} & set(u.get("issues", [])))
        ok = used_scores and avail and np.mean(used_scores) >= np.mean(avail) and hard_used == 0
        item("SHOT SELECTION", "Are the best usable shots selected?", "pass" if ok else "warn",
             {"mean_score_used": round(float(np.mean(used_scores)), 3) if used_scores else None,
              "mean_score_available": round(float(np.mean(avail)), 3) if avail else None, "unusable_shots_used": hard_used})
    adj_same = sum(1 for a, b in zip(plan.timeline, plan.timeline[1:]) if a.asset_id == b.asset_id)
    repeats = len(keys) - len(set(keys))
    item("VARIETY", "Are shots sufficiently varied?", "pass" if adj_same <= max(1, len(keys) // 20) and repeats <= max(1, len(keys) // 10) else "warn",
         {"adjacent_same_clip": adj_same, "repeated_shots": repeats, "distinct_clips": len({a for a, _ in keys})})
    n_tr = sum(1 for s in plan.timeline if s.transition_in.id != "cut")
    budget = plan.bible.transition_budget * max(1, len(plan.timeline) - 1)
    item("TRANSITIONS", "Are transitions appropriate (cuts by default, within budget)?", "pass" if n_tr <= budget + 1 else "warn",
         {"transitions": n_tr, "boundaries": len(plan.timeline) - 1, "budget": round(budget, 1)})
    if color:
        ok = color.get("max_adjacent_luma_jump", 0) <= 0.12 and color.get("max_adjacent_temperature_jump", 0) <= 0.06
        item("COLOR", "Are neighbouring shots consistent (measured on the render)?", "pass" if ok else "warn", color)
    speech = audio.get("speech_seconds")
    lufs, target = audio.get("integrated_lufs"), plan.audio.target_lufs
    a_ok = lufs is not None and abs(lufs - target) <= 1.0 and ("clipping" not in " ".join(qc.get("failures", [])))
    if speech:
        a_ok = a_ok and audio.get("ducked_seconds", 0) > 0
    item("AUDIO", "Is dialogue intelligible and the mix controlled?", "pass" if a_ok else "warn",
         {"integrated_lufs": lufs, "target_lufs": target, "true_peak_db": audio.get("true_peak_db"), "speech_seconds": speech,
          "ducked_seconds": audio.get("ducked_seconds"), "dialogue_levels_matched": len(audio.get("dialogue_levels", []))})
    viol = report.get("text_violations") or []
    item("TEXT", "Is typography readable and inside safe areas?", "pass" if not viol else "warn", {"text_items": len(plan.text), "violations": viol[:5]})
    moving = sum(1 for s in plan.timeline if s.motion.preset != "none" and not s.image)
    item("MOTION", "Does motion feel intentional (budgeted, on static shots)?", "pass" if moving <= 0.65 * len(plan.timeline) else "warn",
         {"segments_with_camera_motion": moving, "speed_ramps": sum(1 for s in plan.timeline if s.speed.ramp),
          "stabilised": sum(1 for s in plan.timeline if s.stabilize)})
    item("ENDING", "Does the ending feel complete?", "pass" if (plan.ending.type in ("logo", "title", "logo_title", "fade") and plan.ending.duration >= 1.5) or plan.ending.type == "fade" else "warn",
         {"type": plan.ending.type, "duration": plan.ending.duration})
    item("TECHNICAL", "Is the output valid?", "pass" if qc.get("passed") else "fail", {"qc_failures": qc.get("failures"), "qc_warnings": qc.get("warnings")})
    counts = {k: sum(1 for i in items if i["status"] == k) for k in ("pass", "warn", "fail")}
    return {"items": items, "summary": counts,
            "note": "Deterministic checks over the plan and measurements of the rendered file; a 'pass' means the measured criterion was met, "
                    "not that the edit is aesthetically perfect."}
