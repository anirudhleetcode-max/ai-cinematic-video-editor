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
from .planner import build_plan, repair, validate
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


# footage-quality words in a negative request map to the selector's issue avoidance (excluded, relaxed only if footage
# runs out — and then reported)
ISSUE_WORDS = {"dark": "underexposed", "underexposed": "underexposed", "too dark": "underexposed", "blurry": "blurry", "blurred": "blurry",
               "out of focus": "blurry", "soft": "blurry", "shaky": "shaky", "wobbly": "shaky", "unstable": "shaky", "overexposed": "overexposed",
               "washed out": "overexposed", "too bright": "overexposed", "blown out": "overexposed"}
NEG_VERBS = ("avoid", "exclude", "skip", "remove", "without", "no", "less", "fewer", "drop", "lose", "ban")
POS_VERBS = ("show", "feature", "include", "use", "want", "see", "more", "add", "keep")
_QUERY = re.compile(
    r"(?:\b(?P<neg>don't|dont|do not|never|not|stop|no longer)\s+(?:\w+\s+)?)?"
    r"\b(?P<verb>" + "|".join(NEG_VERBS + POS_VERBS) + r")\b\s+(?:me |us )?(?:using |showing )?(?:any |more |a lot more |lots of |some |all )?(?:of )?(?:the |a |an |those |these )?"
    r"(?:(?:shots?|clips?|footage|scenes?|moments?) (?:of|with) (?:the |a |an )?)?"
    r"(?P<phrase>[a-z][a-z \-]{1,40}?)(?=\s*\b(?:shots?|clips?|footage|scenes?|moments?|ones)\b|[,.!;]|\s*$| in | at | during | for | and (?:make|add|use|turn|change))")
_NOT_CONTENT = re.compile(r"(effects?|transitions?|text|titles?|music|songs?|tracks?|captions?|subtitles?|grain|vignette|slow[\s\-]?mo|energy|"
                          r"energetic|colou?rs?|grade|logo|intro|outro|ending|first|last|second|third|\d)\b")


def _content_queries(p: str, r: "Revision") -> None:
    """'show the crowd', 'no dogs', "don't use dark clips", 'avoid blurry footage', 'skip the shaky shots'."""
    from ..retrieval import resolve

    for m in _QUERY.finditer(p):
        phrase = m.group("phrase").strip()
        if not phrase or _NOT_CONTENT.match(phrase):
            continue
        neg = m.group("verb") in NEG_VERBS or (m.group("neg") is not None and m.group("verb") in POS_VERBS)
        issues = sorted({iss for w, iss in ISSUE_WORDS.items() if re.search(rf"\b{w}\b", phrase)})
        if neg:
            for iss in issues:
                r.add("avoid_issue", "selection", issue=iss, query=phrase)
        labels, unknown = resolve(phrase)
        unknown = [w for w in unknown if not any(w in k.split() for k in ISSUE_WORDS)]
        if labels and len(unknown) <= 2:
            r.add("prefer_query", "selection", query=phrase, labels=sorted(labels), weight=-0.8 if neg else 0.6, ignored_words=unknown)


def parse_revision(text: str) -> Revision:
    p = " " + text.lower().replace("\u2019", "'") + " "
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
        if re.search(rf"(?<!not )(?<!n't )\bmore ({rx})", p):
            r.add("prefer_tag", "selection", tag=tag, weight=0.35)
    handled = {o["tag"] for o in r.ops if o["op"] == "prefer_tag"}
    if not handled:
        _content_queries(p, r)
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
    if "stronger_ending" not in [o["op"] for o in r.ops]:
        if m := re.search(r"end(?:ing)? (?:it )?(?:with|on|to|as) (?:a |an |the )?(logo and (?:a )?title|title and (?:a )?logo|logo|title(?: card)?|fade(?: out)?|hard cut|cut)\b", p):
            word = m.group(1)
            typ = "logo_title" if "logo" in word and "title" in word else ("logo" if "logo" in word else "title" if "title" in word else "fade" if "fade" in word else "cut")
            r.add("ending", "ending", type=typ)
        elif re.search(r"(change|different|new|another|replace) (the )?(ending|end|outro)", p):
            r.add("ending", "ending", type="other")
    if m := re.search(r"(intro|opening|hook) (much )?(shorter|longer)|(shorten|lengthen|shorter|longer) (the )?(intro|opening|hook)", p):
        which = m.group(1) or m.group(6)
        longer = "longer" in m.group(0) or "lengthen" in m.group(0)
        if "section_length" not in [o["op"] for o in r.ops]:
            r.add("section_length_rel", "structure", which=which, factor=1.4 if longer else 0.6)
    if re.search(r"(no|remove all|without) (visual )?effects", p):
        r.add("effect_density", "effects", density="minimal")
    elif re.search(r"(less|fewer|reduce|tone down|calmer) (the )?(visual )?effects|too many effects", p):
        r.add("effect_density", "effects", step=-1)
    elif re.search(r"more (visual )?effects|(add|bolder) effects", p):
        r.add("effect_density", "effects", step=1)
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
    negated = bool(re.search(r"(remove|no|without|less|fewer|drop|lose) (the |any )?[a-z ]{0,12}(grain|leak|glow|vignette|letterbox|bars|vhs|glitch|bloom|effects?)", p))
    for e in ([] if negated else ints.effects):
        r.add("effect_add", "effects", effect=e)
    if re.search(r"(remove|no|without) (the )?(grain|light leaks?)", p) or ("effect_density" not in [o["op"] for o in r.ops]
                                                                         and re.search(r"(remove|no|without) (the )?effects", p)):
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
                levels = ["minimal", "low", "medium", "high", "extreme"]
                cur = intent.effect_density or new.bible.effect_density or "low"
                if cur in levels and cur != "minimal":
                    intent.effect_density = levels[min(len(levels) - 1, levels.index(cur) + 1)]
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
        elif o == "avoid_issue":
            intent.avoid = list(dict.fromkeys([*(intent.avoid or []), op["issue"]]))
            structural = True
        elif o == "prefer_query":
            from ..retrieval import search

            res = search(ctx.clips, op["query"])
            found = sorted({lab for h in res["matches"] for lab in h["matched"]})
            if not found:
                op = {**op, "noop": True, "reason": f"no analysed shot shows {op['query']!r} (searched labels: {', '.join(op['labels'])})"}
            else:
                for lab in found:
                    tag_weights[lab] = tag_weights.get(lab, 0) + op["weight"] / len(found) ** 0.5
                op = {**op, "matched_labels": found, "matching_shots": res["n_matches"]}
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
        elif o == "ending":
            typ = op["type"]
            if typ == "other":  # "change the ending": pick a different ending that the project can support
                order = ["logo_title", "title", "logo", "fade"]
                typ = next((t for t in order if t != new.ending.type and (ctx.logo or "logo" not in t)), "fade")
                op = {**op, "type": typ}
            intent.ending = typ
            if typ != "cut" and new.ending.duration > 0:
                # same length → change ONLY the ending (end card + end title); timeline and segments untouched
                new.ending.type = typ
                new.ending.logo_asset_id = ctx.logo.id if (ctx.logo and "logo" in typ) else None
                if "logo" in typ and not ctx.logo:
                    new.ending.type = "title"
                others = [t for t in new.text if t.kind != "end_title"]
                if new.ending.type in ("title", "logo_title"):
                    from ..schemas import TextItem
                    end_text = intent.end_title or ctx.name
                    others.append(TextItem(id="end_title", kind="end_title", text=end_text[:120], start=round(new.duration - new.ending.duration + 0.3, 3),
                                           end=round(new.duration - 0.25, 3), style="end_card", animation="tracking_reveal",
                                           position="center" if new.ending.type == "title" else "bottom"))
                new.text = others
            else:
                structural = True  # ending length changes (e.g. a hard cut) → re-time the body
        elif o == "section_length_rel":
            sec = next((x for x in new.story_structure if x.name == op["which"] or (op["which"] == "intro" and x.name in ("intro", "opening"))), None)
            if sec is not None:
                secs = round(max(0.8, (sec.end - sec.start) * op["factor"]), 2)
                if op["which"] == "hook" or sec.name == "hook":
                    intent.hook_seconds = secs
                else:
                    intent.intro_seconds = secs
                op = {**op, "seconds": secs}
                structural = True
        elif o == "effect_density":
            levels = ["minimal", "low", "medium", "high", "extreme"]
            cur = new.bible.effect_density if new.bible.effect_density in levels else "low"
            target = op.get("density") or levels[max(0, min(len(levels) - 1, levels.index(cur) + op.get("step", 0)))]
            intent.effect_density = target
            op = {**op, "from": cur, "to": target}
            if levels.index(target) < levels.index(cur):
                # fewer effects: remove accents in place (no re-plan, segments keep everything else)
                fx_segs = [s for s in new.timeline if s.effects]
                keep_n = 0 if target == "minimal" else len(fx_segs) // 2
                for s in fx_segs[keep_n:]:
                    s.effects = []
                if target == "minimal":
                    new.effects_global = []
                new.bible.effect_density = target
            else:
                structural = True
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
        relax = next((d for d in rebuilt.decisions if "relaxed:" in d), "")
        for o in applied:  # never violate an exclusion silently: say when footage ran out
            if o["op"] == "avoid_issue" and "user-avoided issues" in relax or o["op"] == "prefer_query" and o.get("weight", 0) < 0 and "user-excluded content" in relax:
                o["relaxed"] = True
                o["reason"] = "not enough other footage — some matching shots had to be used"
        rebuilt.decisions.insert(0, f"Revision '{text}': " + ", ".join(o["op"] + (" (relaxed: not enough other footage)" if o.get("relaxed") else "")
                                                                  for o in applied))
        new = rebuilt
    else:
        new.intent = intent
        new.decisions = [f"Revision '{text}': " + ", ".join(o["op"] for o in applied), *new.decisions][:600]
    repair(new, ctx)
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
