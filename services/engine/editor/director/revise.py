"""Natural-language revision of an existing EditPlan.

Each revision is parsed into explicit operations. Cosmetic operations (colour, text, audio, effects)
patch the plan in place; structural ones (pacing, intro length, duration, music-per-section, shot
preferences) re-run only the planning stages that depend on them while *keeping previous clip picks*
where possible. Every change is recorded with its domain so versions can be compared/reverted."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

from ..schemas import EditPlan, SpeedSpec, StyleIntent
from .context import ProjectContext
from .planner import build_plan, validate
from .prompt_parser import WORDNUM, parse_prompt

SECTION_WORDS = {
    "final": -1, "last": -1, "ending": -1, "end": -1, "climax": "climax", "first": 0, "opening": 0, "intro": 0, "beginning": 0, "start": 0,
    "hook": 0, "middle": "mid", "emotional": "emotional",
}


@dataclass
class Revision:
    ops: list[dict] = field(default_factory=list)
    domains: set[str] = field(default_factory=set)

    def add(self, op: str, domain: str, **kw) -> None:
        self.ops.append({"op": op, "domain": domain, **kw})
        self.domains.add(domain)


def parse_revision(text: str) -> Revision:
    p = " " + text.lower() + " "
    r = Revision()
    if re.search(r"more (energetic|energy|exciting|dynamic|hype)|faster pac|speed (it )?up|punchier", p):
        r.add("pacing", "timeline", factor=0.72, pacing="fast")
    if re.search(r"(calmer|slower pac|more relaxed|less energetic|slow (it )?down the pac)", p):
        r.add("pacing", "timeline", factor=1.35, pacing="slow")
    if m := re.search(r"(intro|opening|hook)[a-z ]{0,25}?(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s*(seconds?|secs?|s)\b", p):
        v = float(m.group(2)) if m.group(2)[0].isdigit() else float(WORDNUM[m.group(2)])
        r.add("section_length", "structure", which=m.group(1), seconds=v)
    if m := re.search(r"(make it|change (it|the length|duration) to|cut it (down )?to|shorten (it )?to|extend (it )?to)\s*(\d+(?:\.\d+)?)\s*(seconds?|secs?|s|minutes?|mins?)\b", p):
        v = float(m.group(6)) * (60 if m.group(7).startswith("min") else 1)
        r.add("duration", "structure", seconds=v)
    ints = parse_prompt(text)
    adj = dict(ints.color_adjust)
    if adj:
        r.add("color_adjust", "color", adjust=adj)
    if ints.color_preset and re.search(r"colou?r|grade|look|black and white|monochrome|teal|vintage|golden|moody|pastel|muted", p):
        r.add("color_preset", "color", preset=ints.color_preset)
    for m in re.finditer(r"(?:use )?(song|track)\s*#?\s*(\d+|one|two|three|four|five)\s*(?:for|in|during|on) (?:the )?(final|last|ending|end|climax|first|opening|intro|beginning|middle|emotional)[a-z ]{0,12}", p):
        k = int(m.group(2)) if m.group(2).isdigit() else WORDNUM[m.group(2)]
        r.add("section_song", "music", song=k, where=m.group(3))
    if "section_song" not in [o["op"] for o in r.ops]:
        if m := re.search(r"use (the )?(song|track)\s*#?\s*(\d+|one|two|three|four|five)\b|use (the )?(first|second|third|last) (song|track)", p):
            tok = m.group(3) or m.group(5)
            k = int(tok) if tok.isdigit() else WORDNUM[tok]
            r.add("song", "music", song=k)
        elif re.search(r"(use )?all (the |of the )?(songs|tracks)|all (two|three|four|\d) songs", p):
            r.add("all_songs", "music")
    if m := re.search(r"remove (the )?(first|last|second|third|\d+(?:st|nd|rd|th)?) (scene|shot|clip)", p):
        tok = m.group(2)
        idx = {"first": 0, "second": 1, "third": 2, "last": -1}.get(tok)
        if idx is None:
            idx = int(re.sub(r"\D", "", tok)) - 1
        r.add("remove_segment", "timeline", index=idx)
    tags = {"crowd": r"crowd", "faces": r"faces|people|reactions?", "closeup": r"close[\s\-]?ups?", "wide": r"wide shots?|establishing", "high_motion": r"action|movement"}
    for tag, rx in tags.items():
        if re.search(rf"more ({rx})", p):
            r.add("prefer_tag", "selection", tag=tag, weight=0.35)
        if re.search(rf"(less|fewer|no) ({rx})", p):
            r.add("prefer_tag", "selection", tag=tag, weight=-0.35)
    if m := re.search(r"text (bigger|larger|smaller)|(bigger|larger|smaller) (text|titles?|typography)", p):
        word = m.group(1) or m.group(2)
        r.add("text_scale", "text", factor=0.8 if word == "smaller" else 1.25)
    if re.search(r"(remove|no|without) (the )?(text|titles|typography)", p):
        r.add("text_remove", "text")
    if m := re.search(r"title\s*(?:to|:|=|should say|says?)\s*[\"“]([^\"”]{1,80})[\"”]", text, re.I):
        r.add("title", "text", text=m.group(1))
    if re.search(r"slow (down )?the (emotional|sad|quiet|calm) (part|section|moments?|shots?)|more slow[\s\-]?mo", p):
        r.add("slow_section", "timeline", rate=0.7)
    if re.search(r"(ending|end|outro|finish) (much )?stronger|stronger (ending|end|finish)|better ending", p):
        r.add("stronger_ending", "structure")
    if re.search(r"no transitions|only cuts|hard cuts|remove (the )?transitions", p):
        r.add("transitions", "transitions", style="none")
    elif re.search(r"more transitions|(subtle|smoother) transitions", p):
        r.add("transitions", "transitions", style="subtle")
    elif re.search(r"(energetic|flashier|dynamic) transitions", p):
        r.add("transitions", "transitions", style="energetic")
    if re.search(r"(quieter|lower|softer) music|music (quieter|lower|softer)|turn (the )?music down", p):
        r.add("music_gain", "audio", delta=-4.0)
    if re.search(r"(louder|higher) music|music (louder|up)|turn (the )?music up", p):
        r.add("music_gain", "audio", delta=3.0)
    if re.search(r"(add|with|turn on) (subtitles|captions)", p):
        r.add("captions", "text", enabled=True)
    if re.search(r"(remove|no|without|turn off) (subtitles|captions)", p):
        r.add("captions", "text", enabled=False)
    for e in ints.effects:
        r.add("effect_add", "effects", effect=e)
    if re.search(r"(remove|no|without) (the )?(effects|grain|light leaks?)", p):
        r.add("effects_clear", "effects")
    if ints.aspect_ratio and re.search(r"reel|tiktok|shorts|vertical|square|9:16|1:1|4:5|instagram|youtube", p):
        r.add("aspect", "structure", aspect=ints.aspect_ratio, platform=ints.platform)
    return r


def _resolve_section(plan: EditPlan, where: str) -> list[str]:
    names = [s.name for s in plan.story_structure]
    if not names:
        return []
    w = SECTION_WORDS.get(where, where)
    if w == -1:
        # "final section": the last third of the story (at least the last section)
        k = max(1, round(len(names) / 3))
        return names[-k:]
    if w == 0:
        return names[:1]
    if w == "mid":
        return names[len(names) // 3: 2 * len(names) // 3 or 1]
    if w == "emotional":
        return [n for n, s in zip(names, plan.story_structure) if s.energy < 0.5] or names[:1]
    return [n for n in names if w in n] or names[-1:]


def apply_revision(plan: EditPlan, text: str, ctx: ProjectContext) -> tuple[EditPlan, list[dict]]:
    rev = parse_revision(text)
    if not rev.ops:
        # unrecognised: merge the revision into the original intent and re-plan (keeping clip picks)
        base = plan.intent or parse_prompt(ctx.prompt)
        merged = parse_prompt((ctx.prompt or "") + ". " + text)
        intent = StyleIntent(**{**base.model_dump(), **{k: v for k, v in merged.model_dump().items() if v not in (None, [], {})}})
        new = build_plan(ctx, intent, dict(plan.provenance), prefer_previous=_picks(plan))
        return new, [{"op": "replan", "domain": "all", "text": text}]
    new = copy.deepcopy(plan)
    intent = copy.deepcopy(plan.intent) if plan.intent else parse_prompt(ctx.prompt)
    structural = False
    tag_weights: dict[str, float] = {}
    section_song: dict[str, int] = {}
    applied: list[dict] = []
    for op in rev.ops:
        o = op["op"]
        if o == "pacing":
            intent.pacing = op["pacing"]
            intent.pacing_factor = round(min(3.0, max(0.3, (intent.pacing_factor or 1.0) * op["factor"])), 3)
            if op["factor"] < 1:
                intent.styles = list(dict.fromkeys([*intent.styles, "energetic"]))
                intent.speed_ramps = True if intent.speed_ramps is None else intent.speed_ramps
                intent.beat_sync = True
                intent.sfx = True if intent.sfx is None else intent.sfx
            structural = True
        elif o == "section_length":
            if op["which"] == "hook":
                intent.hook_seconds = op["seconds"]
            else:
                intent.intro_seconds = op["seconds"]
                intent.hook_seconds = 0.0 if (intent.hook_seconds is None or intent.hook_seconds > op["seconds"]) else intent.hook_seconds
            structural = True
        elif o == "duration":
            intent.duration = op["seconds"]
            structural = True
        elif o == "aspect":
            intent.aspect_ratio, intent.platform = op["aspect"], op.get("platform")
            structural = True
        elif o == "color_adjust":
            for k, v in op["adjust"].items():
                cur = new.color_grade.overrides.get(k)
                if k in ("temperature", "exposure", "tint"):
                    new.color_grade.overrides[k] = round((cur or 0.0) + v, 3)
                else:
                    new.color_grade.overrides[k] = round((cur or 1.0) * v, 3)
        elif o == "color_preset":
            new.color_grade.preset = op["preset"]
            new.bible.color = op["preset"]
        elif o == "section_song":
            names = _resolve_section(new, op["where"])
            songs = [a for a in ctx.songs if a.analysis and a.analysis.get("ok")]
            k = op["song"]
            target = songs[k - 1].id if 0 < k <= len(songs) else (songs[-1].id if k == -1 and songs else None)
            if target is None:
                new.decisions.insert(0, f"Revision: song {k} does not exist ({len(songs)} songs uploaded) — music unchanged.")
                op = {**op, "noop": True, "reason": "no such song"}
            elif all(_song_at(plan, sec) == target for sec in plan.story_structure if sec.name in names):
                new.decisions.insert(0, f"Revision: song {k} already plays in {', '.join(names)} — music unchanged.")
                op = {**op, "noop": True, "reason": "already in use"}
            else:
                for name in names:
                    section_song[name] = k
                structural = True
        elif o == "song":
            intent.music_strategy, intent.music_indices = "single", [op["song"]]
            structural = True
        elif o == "all_songs":
            intent.music_strategy, intent.music_indices = "all", []
            structural = True
        elif o == "remove_segment":
            if new.timeline:
                i = op["index"] if op["index"] >= 0 else len(new.timeline) + op["index"]
                if 0 <= i < len(new.timeline) and len(new.timeline) > 1:
                    _ripple_delete(new, i)
        elif o == "prefer_tag":
            tag_weights[op["tag"]] = tag_weights.get(op["tag"], 0) + op["weight"]
            structural = True
        elif o == "text_scale":
            for t in new.text:
                t.scale = round(min(3.0, max(0.3, t.scale * op["factor"])), 3)
        elif o == "text_remove":
            new.text = []
        elif o == "title":
            intent.title = op["text"]
            others = [t for t in new.text if t.id != "title"]
            from ..schemas import TextItem
            first_end = new.story_structure[0].end if new.story_structure else 3.0
            new.text = [TextItem(id="title", kind="title", text=op["text"], start=0.6, end=max(3.1, first_end - 0.2), style=new.bible.typography
                                 if new.bible.typography != "none" else "premium_title", animation="fade_up"), *others]
        elif o == "slow_section":
            emo = set(_resolve_section(new, "emotional"))
            for s in new.timeline:
                if s.section in emo and not s.image and not s.speed.ramp:
                    a = ctx.asset(s.asset_id)
                    dur = float(a.meta.get("duration") or s.src_out)
                    need = s.out_duration * op["rate"]
                    s.src_out = round(min(dur, s.src_in + need), 3)
                    rate = (s.src_out - s.src_in) / s.out_duration
                    s.speed = SpeedSpec(rate=round(max(0.1, rate), 3), interpolate=ctx.mode == "quality")
                    s.keep_audio = False
        elif o == "stronger_ending":
            intent.ending = intent.ending or "title"
            new.ending.duration = min(15.0, new.ending.duration + 1.0) if new.ending.duration else 0.0
            for t in new.text:
                if t.kind == "end_title":
                    t.scale = round(t.scale * 1.2, 3)
            from ..schemas import SfxItem
            if new.ending.duration > 0:
                new.sfx.append(SfxItem(kind="impact", at=round(new.duration - new.ending.duration, 3), gain_db=-12))
            structural = structural or new.ending.duration > 0
        elif o == "transitions":
            intent.transition_style = op["style"]
            structural = True
        elif o == "music_gain":
            for m in new.music:
                m.gain_db = round(max(-40, min(6, m.gain_db + op["delta"])), 2)
        elif o == "captions":
            new.captions.enabled = op["enabled"]
            intent.captions = op["enabled"]
        elif o == "effect_add":
            from ..schemas import EffectInstance
            if op["effect"] == "film_grain":
                new.color_grade.overrides["grain"] = max(new.color_grade.overrides.get("grain", 0), 8)
            elif op["effect"] == "vignette":
                new.color_grade.overrides["vignette"] = max(new.color_grade.overrides.get("vignette", 0), 0.35)
            elif not any(e.id == op["effect"] for e in new.effects_global) and len(new.effects_global) < 6:
                new.effects_global.append(EffectInstance(id=op["effect"]))
        elif o == "effects_clear":
            new.effects_global = []
            new.color_grade.overrides.pop("grain", None)
        applied.append(op)
    if structural:
        keep_color = new.color_grade.model_copy(deep=True)
        keep_text = [t.model_copy(deep=True) for t in new.text]
        keep_effects = list(new.effects_global)
        keep_music_gain = {m.asset_id: m.gain_db for m in new.music}
        rebuilt = build_plan(ctx, intent, dict(plan.provenance), prefer_previous=_picks(plan), tag_weights=tag_weights or None,
                             section_song=section_song or None)
        # cosmetic choices made earlier (or in this revision) survive a structural rebuild
        if "color" in rev.domains or (plan.color_grade != rebuilt.color_grade and "color" not in rev.domains):
            rebuilt.color_grade = keep_color
        rebuilt.effects_global = keep_effects
        if "text" in rev.domains or any(t.id == "title" for t in keep_text):
            rebuilt.text = [t for t in keep_text if t.end <= rebuilt.duration] or rebuilt.text
        for m in rebuilt.music:
            if m.asset_id in keep_music_gain and "audio" in rev.domains:
                m.gain_db = keep_music_gain[m.asset_id]
        rebuilt.decisions.insert(0, f"Revision '{text}': " + ", ".join(o["op"] for o in applied))
        new = rebuilt
    else:
        new.intent = intent
        new.decisions = [f"Revision '{text}': " + ", ".join(o["op"] for o in applied), *new.decisions][:600]
    validate(new, ctx)
    return new, applied


def _song_at(plan: EditPlan, sec) -> str | None:
    """The song that dominates a section's time span (by overlap)."""
    best, best_ov = None, 0.0
    for m in plan.music:
        ov = min(m.out_end, sec.end) - max(m.out_start, sec.start)
        if ov > best_ov:
            best, best_ov = m.asset_id, ov
    return best


def _picks(plan: EditPlan) -> dict[int, str]:
    return {k: f"{s.asset_id}:{s.shot_index}" for k, s in enumerate(plan.timeline)}


def _ripple_delete(plan: EditPlan, i: int) -> None:
    removed = plan.timeline.pop(i)
    shift = removed.out_duration - (removed.transition_in.duration if removed.transition_in.id != "cut" else 0.0)
    if i < len(plan.timeline):
        nxt = plan.timeline[i]
        if i == 0:
            from ..schemas import TransitionSpec
            nxt.transition_in = TransitionSpec()
    for s in plan.timeline[i:]:
        s.out_start = round(s.out_start - shift, 3)
    if plan.timeline:
        plan.timeline[0].out_start = 0.0
        plan.timeline[0].transition_in.id = "cut"
        plan.timeline[0].transition_in.duration = 0.0
    plan.duration = round(plan.duration - shift, 3)
    end = plan.duration
    for m in plan.music:
        if m.out_end > end:
            m.out_end = round(end, 3)
    plan.music = [m for m in plan.music if m.out_end - m.out_start > 0.5]
    for t in plan.text:
        if t.start >= removed.out_start:
            t.start = round(max(0.0, t.start - shift), 3)
            t.end = round(max(t.start + 0.5, t.end - shift), 3)
    plan.sfx = [type(x)(**{**x.model_dump(), "at": x.at - shift if x.at >= removed.out_start else x.at}) for x in plan.sfx if x.at < end]
    for sec in plan.story_structure:
        if sec.start >= removed.out_start + removed.out_duration - 1e-6:
            sec.start, sec.end = round(sec.start - shift, 3), round(sec.end - shift, 3)
        elif sec.end > removed.out_start:
            sec.end = round(max(sec.start + 0.3, sec.end - shift), 3)
