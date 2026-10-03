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
    A.dialogue_director(plan, ctx, intent)
    A.timeline_director(plan, intent)
    A.clip_selector(plan, ctx, intent, prefer_previous, tag_weights)
    A.transition_director(plan, ctx)
    A.effects_designer(plan, ctx, intent)
    A.apply_overlaps(plan, ctx)
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
    repair(ep, ctx)
    validate(ep, ctx)
    return ep


def finalize(plan: A.Plan, ctx: ProjectContext, provenance: dict) -> EditPlan:
    return EditPlan(
        project={"id": ctx.project_id, "name": ctx.name, "prompt": ctx.prompt[:2000]},
        duration=round(plan.duration, 3), aspect_ratio=plan.intent.aspect_ratio or plan.template.get("aspect") or (ctx.reference_profile or {}).get("aspect_ratio") or "16:9",
        fps=plan.export.fps, mode=ctx.mode, bible=plan.bible, story_structure=plan.sections, timeline=plan.segments, text=plan.texts,
        captions=plan.captions, effects_global=plan.effects_global, color_grade=plan.color, audio=plan.audio, music=plan.music, sfx=plan.sfx,
        voiceover=[], ending=plan.ending, export=plan.export, reference_profile_used=bool(ctx.reference_profile and plan.intent.use_reference is not False),
        editing_mode="dialogue" if plan.dialogue_led else "montage",
        intent=plan.intent, provenance={k: v for k, v in provenance.items() if isinstance(v, (str, bool))}, decisions=plan.decisions,
    )


def _registries():
    from ..registry import REGISTRIES

    return REGISTRIES


def repair(plan: EditPlan, ctx: ProjectContext) -> list[str]:
    """Automatic repair of everything that can be fixed without changing the editorial intent. Applied to EVERY plan
    (deterministic, AI-proposed or hand-edited) before validation. Returns the list of fixes applied."""
    R = _registries()
    fixes: list[str] = []
    assets = {a.id: a for a in ctx.assets}
    # unknown creative ids → safe defaults
    for s in plan.timeline:
        bad = [e.id for e in s.effects if not R["effects"].has(e.id)]
        if bad:
            s.effects = [e for e in s.effects if R["effects"].has(e.id)]
            fixes.append(f"{s.id}: removed unknown effects {bad}")
        if s.transition_in.id != "cut" and not R["transitions"].has(s.transition_in.id):
            fixes.append(f"{s.id}: unknown transition '{s.transition_in.id}' → cut")
            s.transition_in = type(s.transition_in)()
        if s.motion.preset != "none" and not R["motion-presets"].has(s.motion.preset):
            fixes.append(f"{s.id}: unknown motion preset '{s.motion.preset}' → none")
            s.motion.preset = "none"
        # source range inside the clip (slide back, then trim)
        a = assets.get(s.asset_id)
        if a is not None and not s.image:
            dur = float(a.meta.get("duration") or 0)
            if dur and s.src_out > dur:
                over = s.src_out - dur
                new_in = max(0.0, s.src_in - over)
                if s.src_out - over - new_in < 0.1:
                    continue
                fixes.append(f"{s.id}: source range {s.src_in:.2f}-{s.src_out:.2f} slid inside clip ({dur:.2f}s)")
                s.src_in, s.src_out = round(new_in, 3), round(min(dur, s.src_out - over), 3)
    plan.effects_global = [e for e in plan.effects_global if R["effects"].has(e.id)]
    # text: known styles / animations, timing inside the film
    for tx in plan.text:
        if not R["text-styles"].has(tx.style):
            fixes.append(f"text {tx.id}: unknown style '{tx.style}' → premium_title")
            tx.style = "premium_title" if R["text-styles"].has("premium_title") else R["text-styles"].all()[0].id
        if not R["text-animations"].has(tx.animation):
            fixes.append(f"text {tx.id}: unknown animation '{tx.animation}' → fade")
            tx.animation = "fade" if R["text-animations"].has("fade") else R["text-animations"].all()[0].id
        if tx.end > plan.duration:
            fixes.append(f"text {tx.id}: end clamped to film duration")
            tx.end = round(plan.duration - 0.05, 3)
            tx.start = min(tx.start, round(tx.end - 0.5, 3))
    # audio references must exist and be audio-capable
    keep = [m for m in plan.music if m.asset_id in assets and assets[m.asset_id].kind in ("audio", "video")]
    if len(keep) != len(plan.music):
        fixes.append(f"music: dropped {len(plan.music) - len(keep)} references to missing assets")
        plan.music = keep
    plan.sfx = [x for x in plan.sfx if x.asset_id is None or x.asset_id in assets]
    plan.voiceover = [v for v in plan.voiceover if v.asset_id in assets]
    # colour preset / LUT
    if not R["color-presets"].has(plan.color_grade.preset):
        fixes.append(f"colour preset '{plan.color_grade.preset}' unknown → cinematic_neutral")
        plan.color_grade.preset = "cinematic_neutral"
    if plan.color_grade.lut_asset_id and plan.color_grade.lut_asset_id not in assets:
        fixes.append("colour: LUT asset missing → removed")
        plan.color_grade.lut_asset_id = None
    # export: even dimensions (H.264 4:2:0 requires them)
    w, h = plan.export.width, plan.export.height
    if w % 2 or h % 2:
        plan.export.width, plan.export.height = w - w % 2, h - h % 2
        fixes.append(f"export: {w}x{h} → {plan.export.width}x{plan.export.height} (even dimensions)")
    if plan.ending.logo_asset_id and plan.ending.logo_asset_id not in assets:
        fixes.append("ending: logo asset missing → fade ending")
        plan.ending.logo_asset_id, plan.ending.type = None, "fade"
    if fixes:
        plan.decisions = [f"Plan repair: {f}" for f in fixes][:50] + plan.decisions
        plan.decisions = plan.decisions[:600]
    return fixes


def validate(plan: EditPlan, ctx: ProjectContext) -> list[str]:
    """Quality Controller (pre-render): structural checks that would otherwise only fail during rendering. Rejects
    invalid timestamps / overlaps, missing assets, unknown effects / transitions / fonts / text styles, negative
    durations, invalid audio references and invalid resolutions. Call `repair()` first to fix what can be fixed."""
    R = _registries()
    problems: list[str] = []
    body_end = plan.duration - plan.ending.duration
    assets = {a.id: a for a in ctx.assets}
    t = 0.0
    for k, s in enumerate(plan.timeline):
        a = assets.get(s.asset_id)
        if a is None:
            problems.append(f"{s.id}: missing asset {s.asset_id}")
            continue
        if s.out_duration <= 0 or s.src_out <= s.src_in:
            problems.append(f"{s.id}: non-positive duration")
        dur = float(a.meta.get("duration") or 0)
        if not s.image and dur and s.src_out > dur + 0.05:
            problems.append(f"{s.id}: source range {s.src_in:.2f}-{s.src_out:.2f} exceeds clip duration {dur:.2f}")
        for e in s.effects:
            if not R["effects"].has(e.id):
                problems.append(f"{s.id}: unknown effect {e.id}")
        if s.transition_in.id != "cut" and not R["transitions"].has(s.transition_in.id):
            problems.append(f"{s.id}: unknown transition {s.transition_in.id}")
        overlap = s.transition_in.duration if s.transition_in.id != "cut" else 0.0
        if k and abs(s.out_start - (t - overlap)) > 0.06:
            problems.append(f"{s.id}: timeline gap/overlap at {s.out_start:.2f} (expected {t - overlap:.2f})")
        t = s.out_start + s.out_duration
    if abs(t - body_end) > 0.15:
        problems.append(f"timeline ends at {t:.2f}s but body should end at {body_end:.2f}s")
    for tx in plan.text:
        if tx.end > plan.duration + 0.01 or tx.end <= tx.start:
            problems.append(f"text {tx.id} timing invalid")
        if not R["text-styles"].has(tx.style):
            problems.append(f"text {tx.id}: unknown text style/font {tx.style}")
        if not R["text-animations"].has(tx.animation):
            problems.append(f"text {tx.id}: unknown animation {tx.animation}")
    for m in plan.music:
        if m.asset_id not in assets:
            problems.append(f"music references missing asset {m.asset_id}")
        if m.out_end <= m.out_start:
            problems.append(f"music segment {m.out_start:.2f}-{m.out_end:.2f} has non-positive length")
    if plan.export.width % 2 or plan.export.height % 2:
        problems.append(f"invalid resolution {plan.export.width}x{plan.export.height} (must be even)")
    if not R["color-presets"].has(plan.color_grade.preset):
        problems.append(f"unknown colour preset {plan.color_grade.preset}")
    if problems:
        raise PlanValidationError("; ".join(problems[:12]))
    return problems
