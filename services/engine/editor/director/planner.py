"""AI Editing Director: prompt → intent → CreativeBible → agents → validated EditPlan."""
from __future__ import annotations

from ..schemas import EditPlan, StyleIntent
from . import agents as A
from .context import ProjectContext
from .providers import interpret


class PlanValidationError(ValueError):
    pass


def build_plan(ctx: ProjectContext, intent: StyleIntent | None = None, provenance: dict | None = None,
               prefer_previous: dict[int, str] | None = None, tag_weights: dict[str, float] | None = None,
               section_song: dict[str, int] | None = None) -> EditPlan:
    if intent is None:
        intent, provenance = interpret(ctx.prompt, {"assets": [{"name": a.filename, "role": a.role} for a in ctx.assets][:60]})
    mode = intent.mode or ctx.mode
    ctx.mode = mode
    template = A.choose_template(intent)
    ref_map = A.map_reference(ctx.reference_profile, intent) if (ctx.reference_profile and intent.use_reference is not False) else None
    if ref_map and ref_map.get("shot_length"):
        template["_ref_shot_length"] = ref_map["shot_length"]
    bible = A.build_bible(intent, template, ref_map)
    quality = {"fast": "standard", "quality": "high", "emergency": "draft"}[mode]
    export = A.export_for(intent, template, ctx.reference_profile, quality)
    usable_total = sum(c.duration for c in ctx.candidates() if not c.issues) or sum(c.duration for c in ctx.candidates())
    duration = intent.duration or template.get("duration") or min(60.0, max(10.0, usable_total * 0.7))
    plan = A.Plan(intent=intent, bible=bible, template=template, export=export, duration=float(duration))
    if mode == "emergency":
        plan.bible.transition_budget = min(plan.bible.transition_budget, 0.1)
        plan.note("EMERGENCY mode: beat cuts, simple transitions, fast encode — validity first.")
    if ref_map:
        plan.note(f"Reference style applied ({', '.join(ref_map['aspects'])}): shot length {ref_map.get('shot_length', '-')}, "
                  f"colour '{ref_map.get('color_preset', '-')}', transition budget {ref_map.get('transition_budget', '-')} — footage never reused.")
    A.ending_designer(plan, ctx, intent)
    A.story_director(plan, intent)
    A.music_director(plan, ctx, intent, section_song)
    A.timeline_director(plan, intent)
    A.clip_selector(plan, ctx, intent, prefer_previous, tag_weights)
    A.transition_director(plan, ctx)
    A.apply_overlaps(plan)
    A.motion_designer(plan, ctx, intent)
    A.reframe(plan, ctx)
    A.colorist(plan, ctx, intent, ref_map)
    A.audio_engineer(plan, ctx, intent)
    A.sound_designer(plan, intent)
    A.typography_designer(plan, ctx, intent, ref_map)
    if intent.captions:
        plan.captions.enabled = True
        plan.captions.style = intent.caption_style or "minimal_documentary"
        plan.note("Captions requested — populated from transcription when a speech-to-text provider is configured.")
    for e in intent.effects:
        if e in ("letterbox", "light_leak", "soft_glow", "bloom", "halation", "vhs", "chromatic_aberration", "black_white") and len(plan.effects_global) < 3:
            from ..schemas import EffectInstance
            plan.effects_global.append(EffectInstance(id=e))
    ep = finalize(plan, ctx, provenance or {})
    validate(ep, ctx)
    return ep


def finalize(plan: A.Plan, ctx: ProjectContext, provenance: dict) -> EditPlan:
    return EditPlan(
        project={"id": ctx.project_id, "name": ctx.name, "prompt": ctx.prompt[:2000]},
        duration=round(plan.duration, 3), aspect_ratio=plan.intent.aspect_ratio or plan.template.get("aspect") or (ctx.reference_profile or {}).get("aspect_ratio") or "16:9",
        fps=plan.export.fps, mode=ctx.mode, bible=plan.bible, story_structure=plan.sections, timeline=plan.segments, text=plan.texts,
        captions=plan.captions, effects_global=plan.effects_global, color_grade=plan.color, audio=plan.audio, music=plan.music, sfx=plan.sfx,
        voiceover=[], ending=plan.ending, export=plan.export, reference_profile_used=bool(ctx.reference_profile and plan.intent.use_reference is not False),
        intent=plan.intent, provenance={k: v for k, v in provenance.items() if isinstance(v, (str, bool))}, decisions=plan.decisions,
    )


def validate(plan: EditPlan, ctx: ProjectContext) -> list[str]:
    """Quality Controller (pre-render): structural checks that would otherwise only fail during rendering."""
    problems: list[str] = []
    body_end = plan.duration - plan.ending.duration
    t = 0.0
    for k, s in enumerate(plan.timeline):
        a = next((x for x in ctx.assets if x.id == s.asset_id), None)
        if a is None:
            problems.append(f"{s.id}: missing asset {s.asset_id}")
            continue
        dur = float(a.meta.get("duration") or 0)
        if not s.image and dur and s.src_out > dur + 0.05:
            problems.append(f"{s.id}: source range {s.src_in:.2f}-{s.src_out:.2f} exceeds clip duration {dur:.2f}")
        overlap = s.transition_in.duration if s.transition_in.id != "cut" else 0.0
        if k and abs(s.out_start - (t - overlap)) > 0.06:
            problems.append(f"{s.id}: timeline gap/overlap at {s.out_start:.2f} (expected {t - overlap:.2f})")
        t = s.out_start + s.out_duration
    if abs(t - body_end) > 0.15:
        problems.append(f"timeline ends at {t:.2f}s but body should end at {body_end:.2f}s")
    for tx in plan.text:
        if tx.end > plan.duration + 0.01 or tx.end <= tx.start:
            problems.append(f"text {tx.id} timing invalid")
    if problems:
        raise PlanValidationError("; ".join(problems[:12]))
    return problems
