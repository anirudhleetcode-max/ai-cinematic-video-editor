"""Specialised editing agents. Each is a deterministic, testable function over the ProjectContext and
the CreativeBible — no model calls happen here (the only optional model call is prompt interpretation).

Agents: StoryDirector · MusicDirector · TimelineDirector · ClipSelector · TransitionDirector ·
MotionDesigner · Colorist · AudioEngineer · SoundDesigner · TypographyDesigner · ReferenceMapper."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np

from ..media.frames import hamming
from ..music.analyze import best_window
from ..registry import templates
from ..registry.color import COLOR_PRESETS, solve_technical, technical_correction
from ..registry.editing import DENSITY
from ..schemas import (AudioPlan, CaptionSpec, ColorAdjust, ColorGrade, CreativeBible, CropSpec, EffectInstance, Ending, ExportSpec, MotionSpec,
                       MusicSegment, Segment, SfxItem, SpeedSpec, StorySection, StyleIntent, TextItem, TransitionSpec)
from .context import Candidate, ProjectContext

PACING_SHOT = {"slow": 3.6, "medium": 2.3, "fast": 1.45, "very_fast": 0.95}

RESOLUTIONS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "21:9": (1920, 822)}

STRUCTURES = {
    "event": [("hook", .08, .85), ("opening", .12, .45), ("people", .18, .55), ("activities", .2, .65), ("energy", .16, .8), ("best_moments", .14, .9), ("climax", .12, 1.0)],
    "festival": [("hook", .08, .9), ("opening", .1, .5), ("people", .16, .6), ("energy", .22, .85), ("best_moments", .24, .9), ("climax", .2, 1.0)],
    "concert": [("hook", .08, .9), ("opening", .12, .5), ("performance", .3, .8), ("crowd", .2, .75), ("climax", .3, 1.0)],
    "sports": [("hook", .08, 1.0), ("setup", .12, .55), ("build", .2, .7), ("action", .3, .9), ("climax", .3, 1.0)],
    "travel": [("establishing", .12, .35), ("journey", .16, .5), ("location", .18, .55), ("experience", .2, .7), ("people", .14, .6), ("climax", .12, .9), ("reflection", .08, .35)],
    "product": [("hook", .1, .85), ("problem", .14, .4), ("product", .16, .6), ("features", .22, .65), ("demonstration", .18, .7), ("benefit", .12, .8), ("cta", .08, .6)],
    "corporate": [("hook", .1, .6), ("intro", .16, .45), ("story", .3, .55), ("people", .2, .55), ("vision", .16, .7), ("cta", .08, .6)],
    "wedding": [("intro", .14, .3), ("preparation", .16, .4), ("ceremony", .24, .55), ("emotional_peak", .2, .65), ("celebration", .18, .85), ("resolution", .08, .35)],
    "emotional": [("intro", .15, .3), ("setup", .2, .4), ("build", .25, .55), ("emotional_peak", .25, .7), ("resolution", .15, .35)],
    "documentary": [("intro", .15, .35), ("setup", .2, .45), ("development", .3, .5), ("climax", .2, .65), ("resolution", .15, .4)],
    "trailer": [("hook", .1, .7), ("setup", .2, .4), ("build", .25, .65), ("climax", .3, 1.0), ("title", .15, .5)],
    "music": [("intro", .1, .5), ("verse", .25, .65), ("chorus", .25, .9), ("bridge", .15, .6), ("final_chorus", .25, 1.0)],
    "general": [("hook", .1, .8), ("intro", .12, .45), ("build", .22, .6), ("development", .22, .65), ("climax", .2, .9), ("outro", .14, .4)],
}
STRUCTURES["cinematic"] = STRUCTURES["general"]
STRUCTURES["birthday"] = STRUCTURES["event"]
STRUCTURES["portfolio"] = STRUCTURES["general"]

TRANSITION_PALETTES = {
    "none": [],
    "minimal": ["crossfade", "dip_to_black"],
    "subtle": ["crossfade", "blur_dissolve", "dip_to_black", "fade_slow"],
    "dynamic": ["push_left", "zoom", "whip", "crossfade", "slide_left", "light_leak"],
    "energetic": ["whip", "zoom", "flash", "glitch", "rgb_split", "push_left", "spin"],
    "glitch": ["glitch", "rgb_split", "pixel_dissolve", "flash"],
}


@dataclass
class Slot:
    section: str
    start: float
    duration: float
    energy: float
    beat_index: int | None = None
    on_downbeat: bool = False
    beat_relation: str = "free"  # downbeat | on_beat | before_beat | after_beat | section_end | free
    role: str = "build"


@dataclass
class Plan:
    """Mutable working state the agents fill in before it is frozen into an EditPlan."""
    intent: StyleIntent
    bible: CreativeBible
    template: dict
    export: ExportSpec
    duration: float
    sections: list[StorySection] = field(default_factory=list)
    beats: list[float] = field(default_factory=list)
    downbeats: list[float] = field(default_factory=list)
    music: list[MusicSegment] = field(default_factory=list)
    music_energy: list[tuple[float, float]] = field(default_factory=list)  # (t, energy) on output timeline
    drops: list[float] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=list)
    fixed_sections: set[str] = field(default_factory=set)  # lengths the user asked for explicitly (never beat-snapped)
    segments: list[Segment] = field(default_factory=list)
    texts: list[TextItem] = field(default_factory=list)
    sfx: list[SfxItem] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    ending: Ending = field(default_factory=Ending)
    color: ColorGrade = field(default_factory=ColorGrade)
    audio: AudioPlan = field(default_factory=AudioPlan)
    effects_global: list[EffectInstance] = field(default_factory=list)
    captions: CaptionSpec = field(default_factory=CaptionSpec)

    def note(self, msg: str) -> None:
        if len(self.decisions) < 590:
            self.decisions.append(msg)


# ------------------------------------------------------------------------------- templates / bible
def choose_template(intent: StyleIntent) -> dict:
    T = templates()
    plat = {"instagram_reel": "instagram_reel", "tiktok": "tiktok", "shorts": "instagram_reel", "youtube": "youtube_video"}.get(intent.platform or "")
    story_map = {"event": "event_highlight", "festival": "festival", "concert": "concert", "sports": "sports_highlight", "travel": "travel_film",
                 "product": "product_commercial", "corporate": "corporate_video", "wedding": "wedding_film", "emotional": "emotional_montage",
                 "documentary": "documentary", "trailer": "trailer", "music": "music_video", "birthday": "birthday", "portfolio": "portfolio_film",
                 "cinematic": "cinematic_film"}
    tid = story_map.get(intent.story_type or "")
    if tid == "event_highlight" and ("energetic" in intent.styles and "cinematic" not in intent.styles):
        tid = "college_event"
    if not tid and "energetic" in intent.styles:
        tid = "hype_video"
    tid = tid or plat or "cinematic_film"
    t = dict(T.get(tid) or next(iter(T.values())))
    if plat and plat != tid:  # platform template contributes aspect / duration / captions
        pt = T[plat]
        for k in ("aspect", "duration", "hookSeconds"):
            if k in pt:
                t.setdefault(k, pt[k])
    return t


def map_reference(ref: dict, intent: StyleIntent) -> dict:
    """ReferenceMapper: translate a ReferenceStyleProfile into planning parameters (style, not footage)."""
    aspects = set(intent.reference_aspects or ["pacing", "color", "transitions", "typography", "motion"])
    out: dict = {"aspects": sorted(aspects)}
    if "pacing" in aspects and ref.get("median_shot_duration"):
        out["shot_length"] = float(np.clip(ref["median_shot_duration"], 0.5, 8.0))
        cpm = ref.get("cuts_per_minute", 20)
        out["pacing"] = "very_fast" if cpm > 50 else "fast" if cpm > 30 else "medium" if cpm > 15 else "slow"
    if "transitions" in aspects:
        tf = float(ref.get("transition_frequency", 0.1))
        out["transition_budget"] = float(np.clip(tf, 0.0, 0.6))
        tt = ref.get("transition_types", {})
        out["transition_style"] = "none" if tf < 0.03 else ("subtle" if tt.get("fade", 0) + tt.get("dissolve", 0) >= tf * 0.5 * sum(tt.values() or [1]) else "dynamic")
    if "color" in aspects:
        target = {"luma": ref.get("brightness", 0.45), "temperature": ref.get("temperature", 0.0), "tint": ref.get("tint", 0.0),
                  "saturation": ref.get("saturation", 0.3), "contrast": ref.get("contrast", 0.2)}
        out["color_target"] = target
        # nearest creative preset by the look's salient traits
        warm, sat, con = target["temperature"], target["saturation"], target["contrast"]
        if sat < 0.08:
            preset = "black_and_white"
        elif warm > 0.06 and sat > 0.35:
            preset = "golden_hour"
        elif warm > 0.02:
            preset = "warm_documentary" if con < 0.2 else "teal_orange"
        elif warm < -0.03:
            preset = "cool_documentary" if target["luma"] > 0.35 else "night_cinema"
        elif con > 0.25:
            preset = "high_contrast"
        elif sat < 0.2:
            preset = "muted"
        else:
            preset = "cinematic_neutral"
        out["closest_named_look"] = preset
        g = ref.get("grade") or {}
        if g:
            # ReferenceGradeProfile → grade: a near-neutral base + overrides derived from the measured look
            # (the technical shot match moves exposure / white balance / saturation / contrast to the reference's values)
            ov: dict[str, float] = {}

            def cast_hue(c: dict) -> tuple[float | None, float]:
                rgb = np.array(c.get("rgb") or [0, 0, 0], np.float32)
                if not rgb.any():
                    return None, 0.0
                v = rgb - rgb.mean()
                mag = float(np.linalg.norm(v))
                if mag < 0.015:
                    return None, mag
                import colorsys
                hh, _, _ = colorsys.rgb_to_hsv(*(np.clip(0.5 + v * 3, 0, 1)))
                return round(float(hh) * 360, 1), mag

            sh_h, sh_m = cast_hue(g.get("shadows", {}))
            hl_h, hl_m = cast_hue(g.get("highlights", {}))
            if sh_h is not None or hl_h is not None:
                ov["split_shadow_hue"] = sh_h if sh_h is not None else 190.0
                ov["split_highlight_hue"] = hl_h if hl_h is not None else (sh_h if sh_h is not None else 35.0)
                ov["split_amount"] = round(float(np.clip(max(sh_m, hl_m) * 3.5, 0.05, 0.6)), 3)
                if hl_h is None:  # neutral highlights measured: weight the toning towards the shadows
                    ov["split_balance"] = 0.4
                elif sh_h is None:
                    ov["split_balance"] = -0.4
            if g.get("luma_p5", 0) > 0.08:
                ov["fade"] = round(float(np.clip((g["luma_p5"] - 0.05) * 1.5, 0, 0.25)), 3)
            out["color_preset"] = "natural" if COLOR_PRESETS.has("natural") else "cinematic_neutral"
            out["color_overrides"] = ov
            out["grade_mapping"] = {"shadow_cast_hue": sh_h, "highlight_cast_hue": hl_h, "lifted_blacks_p5": g.get("luma_p5"), "base": out["color_preset"]}
        else:
            out["color_preset"] = preset
            out["color_overrides"] = {"saturation": float(np.clip(1 + (sat - 0.3) * 0.8, 0.7, 1.4))}
    if "motion" in aspects:
        out["camera_motion"] = "dynamic" if ref.get("camera_motion", 0) > 1.0 else ("subtle" if ref.get("zoom_behavior", 0) > 0.05 or ref.get("camera_motion", 0) > 0.2 else "none")
    if "typography" in aspects:
        pos = ref.get("text_position", "none")
        out["text_position"] = {"top": "top", "bottom": "lower_third", "middle": "center"}.get(pos)
        out["text_presence"] = max((ref.get("text_presence") or {"x": 0}).values())
    if "music" in aspects and ref.get("music"):
        out["music_bpm"] = ref["music"].get("bpm")
    if ref.get("beat_alignment") is not None:
        out["beat_sync"] = ref["beat_alignment"] > 0.4
    return out


def build_bible(intent: StyleIntent, template: dict, ref_map: dict | None) -> CreativeBible:
    styles = intent.styles or template.get("tags", [])[:2]
    pacing = ref_map.get("pacing") if ref_map and ref_map.get("pacing") else (intent.pacing or template.get("pacing", "medium"))
    tstyle = intent.transition_style or (ref_map or {}).get("transition_style") or template.get("transitionStyle", "subtle")
    color = intent.color_preset or (ref_map or {}).get("color_preset") or template.get("color", "cinematic_neutral")
    energetic = pacing in ("fast", "very_fast") or "energetic" in styles
    density = intent.effect_density or ("medium" if (energetic and tstyle in ("energetic", "glitch")) else "low")
    eff_frac, trans_mult = DENSITY[density]
    trans_budget = (ref_map or {}).get("transition_budget")
    if trans_budget is None:  # a reference's measured transition frequency wins; otherwise style × density
        trans_budget = min(0.6, {"none": 0.0, "minimal": 0.1, "subtle": 0.18, "dynamic": 0.3, "energetic": 0.4, "glitch": 0.35}[tstyle] * trans_mult)
    story = intent.story_type or template.get("story", "general")
    return CreativeBible(
        style=", ".join(styles) or "cinematic",
        color=color,
        typography=intent.text_style or template.get("textStyle", "premium_title"),
        transition_philosophy=f"{tstyle}: cuts by default; transitions only at section changes, energy peaks and visually similar adjacent shots",
        effect_philosophy="restraint — effects only where they reinforce music or emotion" if not energetic else "accent hits on drops/downbeats, otherwise clean",
        pacing=pacing,
        music_strategy=intent.music_strategy or template.get("musicStrategy", "build_to_peak"),
        story_structure=[s for s, _, _ in STRUCTURES.get(story, STRUCTURES["general"])],
        effect_budget=eff_frac,
        effect_density=density,
        transition_budget=float(trans_budget),
    )


def export_for(intent: StyleIntent, template: dict, ref: dict | None, quality: str) -> ExportSpec:
    ar = intent.aspect_ratio or template.get("aspect") or (ref or {}).get("aspect_ratio") or "16:9"
    w, h = RESOLUTIONS.get(ar, RESOLUTIONS["16:9"])
    return ExportSpec(width=w, height=h, fps=30, quality=quality, preset_name=f"{ar} {h if w > h else w}p")


# ------------------------------------------------------------------------------- story
def story_director(plan: Plan, intent: StyleIntent) -> None:
    story = intent.story_type or plan.template.get("story", "general")
    struct = STRUCTURES.get(story, STRUCTURES["general"])
    body = plan.duration - plan.ending.duration
    hook = intent.hook_seconds if intent.hook_seconds is not None else plan.template.get("hookSeconds")
    intro = intent.intro_seconds
    weights = [w for _, w, _ in struct]
    fixed: dict[int, float] = {}
    if hook is not None and struct[0][0] in ("hook",):
        fixed[0] = float(hook)
    if intro is not None:
        idx = next((i for i, (n, _, _) in enumerate(struct) if n in ("intro", "opening", "establishing")), 0)
        fixed[idx] = float(intro)
    free_w = sum(w for i, w in enumerate(weights) if i not in fixed)
    free_t = max(1.0, body - sum(fixed.values()))
    lengths = [fixed.get(i, free_t * w / free_w) for i, w in enumerate(weights)]
    plan.fixed_sections = {struct[i][0] for i in fixed}
    base = PACING_SHOT.get(plan.bible.pacing, 2.3)
    if plan.template.get("_ref_shot_length"):
        base = plan.template["_ref_shot_length"]
    if intent.pacing_factor:
        base *= intent.pacing_factor
    curve = intent.energy_curve
    t = 0.0
    secs = []
    for i, ((name, _, e), L) in enumerate(zip(struct, lengths)):
        if L <= 0.05:
            continue
        if curve == "flat":
            e = 0.6
        elif curve in ("build", "build_to_climax"):
            e = 0.35 + 0.65 * (i / max(1, len(struct) - 1)) if name not in ("hook",) else e
        shot_len = float(np.clip(base * (1.35 - 0.7 * e), 0.45, 12))
        if name in ("emotional_peak", "reflection", "resolution") or ("emotional" in plan.intent.styles and e < 0.5):
            shot_len *= 1.3
        secs.append(StorySection(name=name, start=round(t, 3), end=round(t + L, 3), energy=round(float(e), 3), shot_length=round(shot_len, 3)))
        t += L
    plan.sections = secs
    plan.note(f"Story: '{story}' structure → " + " → ".join(f"{s.name.upper()} {s.end - s.start:.1f}s" for s in secs) + f" → END {plan.ending.duration:.1f}s")


# ------------------------------------------------------------------------------- music
def music_director(plan: Plan, ctx: ProjectContext, intent: StyleIntent, section_song: dict[str, int] | None = None) -> None:
    songs = [a for a in ctx.songs if a.analysis and a.analysis.get("ok")]
    total = plan.duration
    if not songs:
        plan.note("Music: no music supplied — edit is cut to standard timing, clip audio kept.")
        return
    strategy = plan.bible.music_strategy
    idx = [i for i in intent.music_indices if i != 0]
    chosen = songs
    if intent.music_strategy == "single" and idx:
        k = idx[0]
        chosen = [songs[(k - 1) if k > 0 else len(songs) - 1]] if abs(k) <= len(songs) else songs[:1]
    elif intent.music_strategy != "all":
        # auto: one song if it is long enough, otherwise chain songs
        prefer = "calm" if strategy == "calm" else "peak" if strategy == "peak" else "build_to_peak"
        longest = max(songs, key=lambda a: a.analysis["duration"])
        if longest.analysis["duration"] >= total + 2:
            long_enough = [a for a in songs if a.analysis["duration"] >= total + 2]  # never pick a song that would need looping
            scored = sorted(long_enough, key=lambda a: -_song_fit(a.analysis, total, prefer, plan))
            chosen = [scored[0]]
        else:
            chosen = sorted(songs, key=lambda a: -a.analysis["duration"])
    segs: list[MusicSegment] = []
    xf = 2.0
    if len(chosen) == 1 and not section_song:
        a = chosen[0]
        m = a.analysis
        prefer = "calm" if strategy == "calm" else "peak" if strategy == "peak" else "build_to_peak"
        if m["duration"] >= total:
            s0, _ = best_window(m, total, prefer)
            segs.append(MusicSegment(asset_id=a.id, src_in=s0, out_start=0, out_end=total, fade_in=0.4, fade_out=max(1.5, min(3.0, plan.ending.duration + 0.5))))
            plan.note(f"Music: '{a.filename}' {m['bpm']:.0f} BPM, window {s0:.1f}–{s0 + total:.1f}s chosen for a {prefer.replace('_', ' ')} arc.")
        else:
            # extend: loop a high-energy section at a downbeat with a crossfade (not an obvious repeat of the intro)
            t, src = 0.0, 0.0
            hi = m.get("high_energy") or [[0, m["duration"]]]
            # re-entry point must leave enough material after it for progress (≥ crossfade + 4 s), else the loop stalls
            need = xf + 4.0
            starts = [h[0] for h in hi if m["duration"] - h[0] >= need] or [d for d in m.get("downbeats", []) if m["duration"] - d >= need][:1] or [0.0]
            loop_from = float(starts[0])
            for _ in range(200):  # hard bound: every pass advances t by ≥ 4 s
                if t >= total - 0.1:
                    break
                remaining = total - t
                avail = m["duration"] - src
                L = min(avail, remaining + (xf if remaining > avail else 0))
                segs.append(MusicSegment(asset_id=a.id, src_in=round(src, 3), out_start=round(t, 3), out_end=round(min(total, t + L), 3),
                                         fade_in=0.4 if t == 0 else xf, fade_out=xf if t + L < total - 0.05 else min(3.0, plan.ending.duration + 0.5)))
                t += L - xf
                src = loop_from
            plan.note(f"Music: '{a.filename}' is shorter than the edit — extended by re-entering its high-energy section at {loop_from:.1f}s with {xf:.0f}s crossfades.")
    else:
        # chain songs (or assign songs to sections)
        if section_song:
            order = _section_song_order(plan, songs, chosen, section_song)
        else:
            weights = [a.analysis["duration"] for a in chosen]
            tot_w = sum(weights)
            order, t = [], 0.0
            for a, w in zip(chosen, weights):
                L = total * w / tot_w
                order.append((a, t, min(total, t + L)))
                t += L
        for k, (a, t0, t1) in enumerate(order):
            m = a.analysis
            L = t1 - t0 + (xf if k < len(order) - 1 else 0)
            s0, _ = best_window(m, min(L, m["duration"]), "peak" if k == len(order) - 1 else "build_to_peak")
            segs.append(MusicSegment(asset_id=a.id, src_in=s0, out_start=round(t0, 3), out_end=round(min(total, t0 + L), 3),
                                     fade_in=0.4 if k == 0 else xf, fade_out=xf if k < len(order) - 1 else min(3.0, plan.ending.duration + 0.5),
                                     section=order[k][0].filename))
        plan.note("Music: " + " → ".join(f"'{a.filename}' {t0:.1f}–{t1:.1f}s" for a, t0, t1 in order) + f" (crossfades {xf:.0f}s).")
    plan.music = segs
    # beat grid + energy on the OUTPUT timeline
    beats, downs, energy, drops = [], [], [], []
    for sg in segs:
        m = ctx.asset(sg.asset_id).analysis
        off = sg.out_start - sg.src_in
        lo, hi = sg.out_start + (sg.fade_in if sg.out_start > 0 else 0) * 0.5, sg.out_end - (sg.fade_out * 0.5 if sg.out_end < total else 0)
        beats += [b + off for b in m["beats"] if lo <= b + off < hi]
        downs += [b + off for b in m["downbeats"] if lo <= b + off < hi]
        drops += [d + off for d in m.get("drops", []) if lo <= d + off < hi]
        hop = m.get("energy_hop", 0.5)
        energy += [(i * hop + off, v) for i, v in enumerate(m["energy"]) if sg.out_start <= i * hop + off < sg.out_end]
    plan.beats, plan.downbeats, plan.drops = sorted(beats), sorted(downs), sorted(drops)
    plan.music_energy = sorted(energy)


def _song_fit(m: dict, total: float, prefer: str, plan: Plan) -> float:
    s0, _ = best_window(m, total, prefer)
    e = np.array(m["energy"])
    hop = m.get("energy_hop", 0.5)
    w = e[int(s0 / hop):int((s0 + total) / hop)]
    target = np.mean([s.energy for s in plan.sections]) if plan.sections else 0.6
    return float(-abs(w.mean() - target)) if len(w) else -1.0


def _section_song_order(plan: Plan, songs, chosen, section_song: dict[str, int]):
    """Assign specific songs to sections (e.g. 'use song 2 for the final section'); remaining time uses the base song."""
    base = chosen[0]
    marks = []
    for sec in plan.sections:
        k = section_song.get(sec.name)
        a = songs[k - 1] if k and 0 < k <= len(songs) else (songs[-1] if k == -1 else base)
        marks.append((a, sec.start, sec.end if sec is not plan.sections[-1] else plan.duration))
    merged = []
    for a, t0, t1 in marks:
        if merged and merged[-1][0] is a:
            merged[-1] = (a, merged[-1][1], t1)
        else:
            merged.append((a, t0, t1))
    return merged


def energy_at(plan: Plan, t: float) -> float | None:
    if not plan.music_energy:
        return None
    ts = np.array([x for x, _ in plan.music_energy])
    vs = np.array([v for _, v in plan.music_energy])
    m = (ts >= t - 1.0) & (ts <= t + 1.0)
    return float(vs[m].mean()) if m.any() else None


# ------------------------------------------------------------------------------- timeline
def timeline_director(plan: Plan, intent: StyleIntent) -> None:
    """Cut points from the pacing engine (director/pacing.py) on the music's beat grid.

    Not every cut sits exactly on a beat: phrase starts and section changes land on downbeats; most cuts land on a beat;
    a deterministic minority are deliberately offset — slightly *before* the beat in hook/climax (anticipation) or
    *after* it in emotional/opening/resolution sections (a late, relaxed cut). Each slot records its beat relation."""
    from .pacing import role_of, target_for

    body = plan.duration - plan.ending.duration
    beat_sync = bool(plan.beats) and (intent.beat_sync if intent.beat_sync is not None else plan.template.get("beatSync", plan.bible.pacing in ("fast", "very_fast")))
    rng = random.Random(7)
    slots: list[Slot] = []
    beats = np.array(plan.beats)
    downs = set(round(d, 3) for d in plan.downbeats)
    bi = float(np.median(np.diff(beats))) if len(beats) > 2 else 0.0
    bpm = 60.0 / bi if bi > 0 else None
    ref_med = plan.template.get("_ref_shot_length")
    pf = float(intent.pacing_factor or 1.0)

    def snap(x: float) -> float:
        if not (beat_sync and bi > 0 and len(beats)):
            return x
        k = int(np.argmin(np.abs(beats - x)))
        return float(beats[k]) if abs(beats[k] - x) <= bi else x

    relations: dict[str, int] = {}
    prev_end = 0.0
    for si, sec in enumerate(plan.sections):
        t = prev_end
        if sec.name in plan.fixed_sections:
            end = min(body, t + (sec.end - sec.start))
        else:
            end = body if si == len(plan.sections) - 1 else min(body, max(t + 0.5, snap(sec.end)))
        sec.start, sec.end = round(t, 3), round(end, 3)
        prev_end = end
        role = role_of(sec.name)
        lens = []
        while t < end - 0.05:
            me = energy_at(plan, t)
            e = sec.energy if me is None else 0.6 * sec.energy + 0.4 * me
            pt = target_for(sec.name, e, bpm=bpm if beat_sync else None, reference_median=ref_med, pacing_factor=pf)
            L = max(0.3, pt.target * rng.uniform(0.88, 1.12))
            nxt = t + L
            on_down, rel = False, "free"
            if beat_sync and bi > 0:
                n_beats = pt.beats or max(1, round(L / bi))
                cand = beats[(beats > t + max(0.3, pt.lo * pf * 0.8)) & (beats <= min(end, t + (n_beats + 1) * bi + 0.01))]
                if len(cand):
                    target = t + n_beats * bi
                    k = int(np.argmin(np.abs(cand - target) - (0.15 * bi) * np.array([round(c, 3) in downs for c in cand])))
                    nxt = float(cand[k])
                    on_down = round(nxt, 3) in downs
                    rel = "downbeat" if on_down else "on_beat"
                    roll = rng.random()
                    if not on_down and role in ("hook", "climax") and roll < 0.12:
                        nxt -= min(0.08, bi / 8)  # anticipation: cut a couple of frames before the hit
                        rel = "before_beat"
                    elif not on_down and role in ("emotional", "opening", "resolution") and roll < 0.2:
                        nxt += bi / 4  # late, relaxed cut
                        rel = "after_beat"
            if end - nxt < 0.6:  # don't leave a sliver at the end of a section
                nxt, rel = end, ("section_end" if beat_sync else rel)
            nxt = min(nxt, end)
            if nxt - t < 0.3:
                nxt = min(end, t + 0.3)
            bidx = int(np.argmin(np.abs(beats - t))) if len(beats) else None
            slots.append(Slot(sec.name, round(t, 3), round(nxt - t, 3), round(float(e), 3), bidx, on_down, rel, role))
            relations[rel] = relations.get(rel, 0) + 1
            lens.append(nxt - t)
            t = nxt
        if lens:
            sec.shot_length = round(float(np.clip(np.mean(lens), 0.25, 30)), 3)
    plan.slots = slots
    tot = max(1, sum(relations.values()))
    plan.note(f"Timeline: {len(slots)} shots from the pacing engine" + (f" on the beat grid ({bpm:.0f} BPM)" if beat_sync and bpm else " (free timing, no beat sync)")
              + f", median shot {np.median([s.duration for s in slots]):.2f}s; cut relations: "
              + ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in sorted(relations.items(), key=lambda kv: -kv[1])) + ".")


# ------------------------------------------------------------------------------- clip selection
SECTION_PREF = {
    "hook": ("cinematic_score", "energy_score"), "opening": ("cinematic_score",), "establishing": ("cinematic_score",), "intro": ("cinematic_score",),
    "people": ("face_visibility_score",), "crowd": ("face_visibility_score", "energy_score"), "activities": ("motion_score",),
    "energy": ("energy_score", "motion_score"), "best_moments": ("quality_score", "energy_score"), "climax": ("energy_score", "motion_score"),
    "emotional_peak": ("emotional_score", "face_visibility_score"), "reflection": ("emotional_score", "cinematic_score"),
    "resolution": ("emotional_score",), "performance": ("energy_score",), "action": ("motion_score", "energy_score"),
}
SECTION_TAGS = {"opening": ["wide", "static"], "establishing": ["wide", "static"], "people": ["faces", "closeup"], "crowd": ["crowd"],
                "emotional_peak": ["closeup", "faces"], "climax": ["high_motion"], "energy": ["high_motion"]}


HARD_EXCLUDE = ("black", "frozen", "too_short", "obstructed", "duplicate")
SECTION_SUBJECTS = {"people": ["people", "faces", "group"], "crowd": ["crowd", "group"], "emotional_peak": ["faces"], "ceremony": ["people"],
                    "opening": ["outdoor"], "establishing": ["outdoor", "wide"], "location": ["outdoor"], "product": ["products"],
                    "features": ["products", "screen"], "demonstration": ["screen", "products"], "celebration": ["group", "crowd"],
                    "performance": ["people"], "action": ["sports", "vehicles"]}
_ROLE_PRIORITY = {"hook": 0, "climax": 1, "opening": 2, "emotional": 3, "build": 4, "resolution": 5}


def clip_selector(plan: Plan, ctx: ProjectContext, intent: StyleIntent, prefer_previous: dict[int, str] | None = None,
                  tag_weights: dict[str, float] | None = None) -> None:
    """Sequence construction, not top-N picking.

    Slots are filled in narrative-priority order (hook → climax → opening → emotional → build → resolution) so the
    strongest material is reserved for the moments that need it; each choice is scored against the shots already placed
    on BOTH sides (±3 slots): same clip, same camera angle, visually similar, same shot size, opposite pans and repeated
    close-ups are penalised; subject continuity inside a section is rewarded. Technically imperfect shots are penalised
    by their edit score, not excluded — only black/frozen/too-short/obstructed/duplicate shots are held back, and even
    those only until the footage runs out (progressive relaxation, reported)."""
    from .pacing import role_of

    cands = ctx.candidates()
    user_avoid = set(intent.avoid or []) - set(HARD_EXCLUDE)
    need_n = max(3, len(plan.slots) // 4)
    relaxed: list[str] = []
    hard = set(HARD_EXCLUDE)
    usable = [c for c in cands if not (set(c.issues) & (hard | user_avoid))]
    for step, drop in (("user-avoided issues", user_avoid), ("duplicates", {"duplicate"}), ("frozen/too-short", {"frozen", "too_short"}),
                       ("obstructed/black", {"obstructed", "black"})):
        if len(usable) >= need_n:
            break
        if drop & (hard | user_avoid):
            user_avoid -= drop
            hard -= drop
            usable = [c for c in cands if not (set(c.issues) & (hard | user_avoid))]
            relaxed.append(step)
    if not usable:
        usable = sorted(cands, key=lambda c: -c.overall)[: max(3, len(plan.slots))]
    if not usable:
        raise RuntimeError("no usable footage")
    rejected = len(cands) - len(usable)
    prefer_tags = {t: 0.12 for t in intent.prefer_tags}
    prefer_tags.update(tag_weights or {})
    n = len(plan.slots)
    prev_keys = set((prefer_previous or {}).values())
    assigned: list[Candidate | None] = [None] * n
    use_count: dict[str, int] = {}
    asset_use: dict[str, int] = {}
    order = sorted(range(n), key=lambda k: (_ROLE_PRIORITY.get(plan.slots[k].role or role_of(plan.slots[k].section), 4), -plan.slots[k].energy, k))

    def size(c: Candidate) -> str:
        return (c.semantic or {}).get("shot_size", "unknown")

    def tags(c: Candidate) -> set[str]:
        return set(c.tags) | {x["label"] for x in (c.semantic or {}).get("subjects", [])}

    for k in order:
        sl = plan.slots[k]
        nbs = [(abs(j - k), assigned[j]) for j in range(max(0, k - 3), min(n, k + 4)) if j != k and assigned[j] is not None]
        best, best_s = None, -1e9
        for c in usable:
            s = c.overall
            prefs = SECTION_PREF.get(sl.section, ("quality_score",))
            s += 0.35 * sum(c.scores.get(sc, 0) for sc in prefs) / len(prefs)
            s -= 0.4 * abs(c.scores.get("energy_score", 0.5) - sl.energy)
            ct = tags(c)
            s += sum(0.1 for t in SECTION_TAGS.get(sl.section, []) if t in ct)
            s += sum(0.08 for t in SECTION_SUBJECTS.get(sl.section, []) if t in ct)
            s += sum(w for t, w in prefer_tags.items() if t in ct)
            if prefer_previous:
                if prefer_previous.get(k) == c.key:
                    s += 0.5  # same slot as before
                elif c.key in prev_keys and use_count.get(c.key, 0) == 0:
                    s += 0.3  # retained from the previous version (timing changed, so its slot moved)
            uc = use_count.get(c.key, 0)
            free = _free_length(c, [])
            if uc and not c.image:
                free = c.duration / (uc + 1)
            if free < min(sl.duration, 1.0) and not c.image:
                s -= 2.0
            s -= 0.45 * uc + 0.06 * asset_use.get(c.asset.id, 0)
            if c.speech > 0.5 and sl.duration < 2.0:
                s -= 0.15  # would chop someone mid-sentence
            for d, o in nbs:
                w = 1.0 if d == 1 else (0.4 if d == 2 else 0.2)
                if c.asset.id == o.asset.id:
                    s -= 0.35 * w
                if c.angle_group and c.angle_group == o.angle_group and c.asset.id != o.asset.id:
                    s -= 0.3 * w
                if d == 1 and not c.image and not o.image and hamming(c.dhash, o.dhash) < 12:
                    s -= 0.4
                if d == 1 and size(c) == size(o) and size(c) in ("closeup", "extreme_closeup"):
                    s -= 0.08
                if d == 1 and plan.slots[k].section == (plan.slots[k - 1].section if k > 0 else "") and "people" in ct and "people" in tags(o):
                    s += 0.04
                if d == 1 and "pan_left" in ct and "pan_right" in o.tags or d == 1 and "pan_right" in ct and "pan_left" in o.tags:
                    s -= 0.08
            if k == 0 and sl.section == "hook":
                s += 0.25 * c.scores.get("cinematic_score", 0) + 0.25 * c.scores.get("energy_score", 0) + 0.1 * c.scores.get("creative_score", 0)
            if sl.role == "opening" and size(c) in ("wide", "unknown") and (c.semantic or {}).get("scene_type", {}).get("setting") in ("outdoor", "indoor"):
                s += 0.06  # establishing shots open sections
            if s > best_s:
                best, best_s = c, s
        assert best is not None
        assigned[k] = best
        use_count[best.key] = use_count.get(best.key, 0) + 1
        asset_use[best.asset.id] = asset_use.get(best.asset.id, 0) + 1
    # ---- second pass in time order: speed, ramps, source ranges -----------------------------------------------
    slow_ok = intent.slow_motion if intent.slow_motion is not None else plan.template.get("slowMotion", False)
    ramps_ok = intent.speed_ramps if intent.speed_ramps is not None else plan.template.get("speedRamps", False)
    n_ramps = 0
    used_ranges: dict[str, list[tuple[float, float]]] = {}
    segs: list[Segment] = []
    for k, sl in enumerate(plan.slots):
        c = assigned[k]
        assert c is not None
        emotional = sl.section in ("emotional_peak", "reflection", "resolution", "intro") or (sl.energy < 0.45 and "emotional" in intent.styles)
        rate = (0.5 if sl.energy < 0.4 else 0.65) if (slow_ok and emotional and c.speech < 0.3) else 1.0
        ramp = None
        if ramps_ok and sl.energy > 0.7 and n_ramps < max(1, len(plan.slots) // 8) and sl.duration > 1.2 and not c.image and c.speech < 0.3:
            ramp = [(0.0, 1.6), (0.35, 1.6), (0.55, 0.45), (0.85, 0.45), (1.0, 1.0)]
            n_ramps += 1
        src_len = _src_needed(sl.duration, rate, ramp)
        src_in = _place(c, src_len, used_ranges.get(c.key, []))
        avail = (c.end - src_in) if not c.image else 1e9
        if src_len > avail + 1e-3:
            if ramp is None and avail / sl.duration >= 0.75:
                rate = avail / sl.duration
                src_len = avail
            else:
                ramp = None
                rate = max(0.5, avail / sl.duration) if avail > 0.2 else 1.0
                src_len = min(avail, sl.duration * rate)
        src_out = src_in + max(0.1, src_len)
        used_ranges.setdefault(c.key, []).append((src_in, src_out))
        freeze = max(0.0, sl.duration - (src_out - src_in) / max(rate, 1e-3)) if ramp is None and not c.image else 0.0
        prof = c.semantic or {}
        reason = f"{sl.section}: edit {c.overall:.2f} (q {c.scores.get('quality_score', 0):.2f} u {c.scores.get('usability_score', 1):.2f} c {c.scores.get('creative_score', 0):.2f})"
        if prof.get("shot_size") and prof["shot_size"] != "unknown":
            reason += f", {prof['shot_size']}"
        subj = [x["label"] for x in prof.get("subjects", [])][:3]
        if subj:
            reason += f", {'/'.join(subj)}"
        if c.issues:
            reason += f", accepted despite {','.join(c.issues[:2])}"
        if rate < 1 and ramp is None:
            reason += f", slow motion {rate:.2f}x"
        if ramp:
            reason += ", speed ramp"
        if sl.beat_relation not in ("free",):
            reason += f", cut {sl.beat_relation.replace('_', ' ')}"
        segs.append(Segment(
            id=f"s{k:03d}", asset_id=c.asset.id, shot_index=c.shot_index, src_in=round(src_in, 3), src_out=round(src_out if not c.image else sl.duration, 3),
            out_start=sl.start, out_duration=sl.duration, section=sl.section,
            speed=SpeedSpec(rate=round(float(np.clip(rate, 0.1, 16)), 3), ramp=ramp, freeze_end=round(min(freeze, 5.0), 3), interpolate=bool(rate < 0.8 and ctx.mode == "quality")),
            beat_index=sl.beat_index, reason=reason[:290], image=c.image,
            stabilize=("shaky" in c.issues and (intent.stabilize is not False)),
            stabilize_mode=(("standard" if c.scores.get("stability_score", 1) < 0.25 else "light") if "shaky" in c.issues else None),
        ))
    plan.segments = segs
    keys = [f"{s.asset_id}:{s.shot_index}" for s in segs]
    angles = [assigned[k].angle_group for k in range(n)]
    adj_same_clip = sum(1 for i in range(1, n) if segs[i].asset_id == segs[i - 1].asset_id)
    adj_same_angle = sum(1 for i in range(1, n) if angles[i] and angles[i] == angles[i - 1] and segs[i].asset_id != segs[i - 1].asset_id)
    plan.note(f"Clip selection (sequence): {n} shots from {len(set(s.asset_id for s in segs))} clips / {len(set(angles))} camera set-ups; "
              f"{len(keys) - len(set(keys))} shot re-uses; adjacent same-clip {adj_same_clip}, adjacent same-angle {adj_same_angle}; "
              f"{rejected} of {len(cands)} candidate shots held back ({', '.join(sorted(hard | user_avoid)) or 'none'})"
              + (f" — relaxed: {', '.join(relaxed)} (not enough footage)" if relaxed else "") + f"; {n_ramps} speed ramps; "
              f"{sum(1 for k in range(n) if assigned[k].issues)} imperfect-but-valuable shots used.")


def _free_length(c: Candidate, used: list[tuple[float, float]]) -> float:
    if c.image:
        return 1e9
    pts = sorted(used)
    best, cur = 0.0, c.start
    for a, b in pts:
        best = max(best, a - cur)
        cur = max(cur, b)
    return max(best, c.end - cur)


def _place(c: Candidate, length: float, used: list[tuple[float, float]]) -> float:
    if c.image:
        return 0.0
    # centre on the best moment if that window is free, else first free gap that fits
    s = float(np.clip(c.best - length / 2, c.start, max(c.start, c.end - length)))
    if all(s + length <= a or s >= b for a, b in used):
        return s
    cur = c.start
    for a, b in sorted(used) + [(c.end, c.end)]:
        if a - cur >= length:
            return cur
        cur = max(cur, b)
    return max(c.start, c.end - length)


def _src_needed(out_dur: float, rate: float, ramp) -> float:
    if not ramp:
        return out_dur * rate
    # integrate piecewise-linear rate over output time
    xs = [p for p, _ in ramp]
    ys = [r for _, r in ramp]
    return float(np.trapezoid(ys, xs) * out_dur) if hasattr(np, "trapezoid") else float(np.trapz(ys, xs) * out_dur)


# ------------------------------------------------------------------------------- transitions
def transition_director(plan: Plan, ctx: ProjectContext) -> None:
    """CUT is the default and a first-class choice. A boundary gets a transition only when it has a reason (section
    change, music drop, unavoidable similar framing), the budget (style × EffectDensity, or the reference's measured
    frequency) allows it, and a palette transition fits: energy inside its range, duration inside its range, and
    movement requirements met (pushes/slides/whips need lateral motion in the shots)."""
    from ..registry.transitions import TRANSITIONS

    style = plan.bible.transition_philosophy.split(":")[0]
    palette = [t for t in TRANSITION_PALETTES.get(style, TRANSITION_PALETTES["subtle"]) if TRANSITIONS.has(t)]
    budget = int(round(plan.bible.transition_budget * max(0, len(plan.segments) - 1)))
    used = 0
    beats = np.array(plan.beats)
    bi = float(np.median(np.diff(beats))) if len(beats) > 2 else 0.5
    cand_by_key = {c.key: c for c in ctx.candidates()}
    choices = []
    for k in range(1, len(plan.segments)):
        a, b = plan.segments[k - 1], plan.segments[k]
        reason, prio = None, 0.0
        if a.section != b.section:
            reason, prio = "section change", 1.0
        ca, cb = cand_by_key.get(f"{a.asset_id}:{a.shot_index}"), cand_by_key.get(f"{b.asset_id}:{b.shot_index}")
        if ca and cb and not ca.image and not cb.image and hamming(ca.dhash, cb.dhash) < 14 and (a.asset_id == b.asset_id or ca.angle_group == cb.angle_group):
            reason, prio = reason or "similar adjacent framing (avoids a jump cut)", max(prio, 0.7)
        if any(abs(b.out_start - d) < 0.3 for d in plan.drops):
            reason, prio = "music drop", 0.9
        if reason:
            choices.append((prio, k, reason, ca, cb))
    rng = random.Random(3)
    skipped = 0
    for prio, k, reason, ca, cb in sorted(choices, key=lambda x: -x[0]):
        if used >= budget or not palette:
            break
        a, b = plan.segments[k - 1], plan.segments[k]
        sec_e = next((s.energy for s in plan.sections if s.name == b.section), 0.5)
        lateral = bool(ca and cb and ({"pan_left", "pan_right", "moving", "high_motion"} & (set(ca.tags) | set(cb.tags))))

        def fits(tid: str) -> bool:
            m = TRANSITIONS.get(tid).__dict__.get("editing", {})
            lo, hi = m.get("energy", [0, 1])
            if not (lo - 0.1 <= sec_e <= hi + 0.1):
                return False
            if m.get("movement") == "lateral_motion" and not lateral:
                return False
            return True

        if reason == "section change" and sec_e < 0.45:
            order = ["dip_to_black", "fade_slow", "crossfade"]
        elif reason == "music drop":
            order = ["flash", "zoom", "whip"]
        elif reason.startswith("similar"):
            order = ["crossfade", "blur_dissolve", "morph"]
        else:
            order = palette[:] if sec_e <= 0.6 else rng.sample(palette, len(palette))
        tid = next((t for t in order if t in palette and fits(t)), None) or next((t for t in palette if fits(t)), None)
        if tid is None:
            skipped += 1
            continue  # nothing in the palette suits this boundary → keep the cut
        meta = TRANSITIONS.get(tid).__dict__.get("editing", {})
        dlo, dhi = meta.get("duration_range", [0.3, 1.0])
        dur = float(np.clip(dhi - (dhi - dlo) * sec_e, dlo, dhi))
        if bi:
            dur = max(0.2, round(dur / (bi / 2)) * (bi / 2))
        dur = min(dur, a.out_duration * 0.45, b.out_duration * 0.45)
        if dur < max(0.15, dlo * 0.6):
            skipped += 1
            continue
        b.transition_in = TransitionSpec(id=tid, duration=round(dur, 3))
        used += 1
        plan.note(f"Transition at {b.out_start:.2f}s: {tid} ({dur:.2f}s) — {reason}; energy {sec_e:.2f}, {meta.get('style')}.")
    plan.note(f"Transitions: {used} of {len(plan.segments) - 1} boundaries (budget {budget}, density '{plan.bible.effect_density}'); "
              f"all others are hard cuts" + (f"; {skipped} candidate boundaries kept as cuts (no fitting transition)" if skipped else "") + ".")


def effects_designer(plan: Plan, ctx: ProjectContext, intent: StyleIntent) -> None:
    """Accent effects with restraint: at most `effect_budget` of the segments (EffectDensity), only where the music or the
    story gives them a reason (drops / downbeats in high-energy sections, the climax entrance), chosen from the effects
    whose metadata matches the segment's energy and pacing. Effects the user asked for by name always qualify."""
    from ..registry.effects import EFFECTS

    if plan.bible.effect_density == "minimal" or plan.bible.effect_budget <= 0:
        plan.note("Effects: density 'minimal' — no accent effects.")
        return
    budget = int(math.floor(plan.bible.effect_budget * len(plan.segments)))
    asked = [e for e in intent.effects if EFFECTS.has(e)]
    accents = [d.id for d in EFFECTS.all() if d.__dict__.get("editing", {}).get("role") == "accent"]
    pool = asked + [a for a in accents if a not in asked]
    style = plan.bible.transition_philosophy.split(":")[0]
    allowed_styles = {"none": {"cinematic", "film"}, "minimal": {"cinematic", "film"}, "subtle": {"cinematic", "film", "soft"},
                      "dynamic": {"cinematic", "film", "energetic", "music", "smooth"}, "energetic": {"energetic", "music", "smooth", "stylised"},
                      "glitch": {"glitch", "music", "energetic"}}.get(style, {"cinematic", "film"})
    used, placed = 0, []
    drops = plan.drops
    for s in sorted(plan.segments, key=lambda x: -next((z.energy for z in plan.sections if z.name == x.section), 0.5)):
        if used >= budget:
            break
        sec_e = next((z.energy for z in plan.sections if z.name == s.section), 0.5)
        on_drop = any(abs(s.out_start - d) < 0.25 for d in drops)
        if not (on_drop or (sec_e >= 0.75 and s.beat_index is not None)) or s.effects:
            continue
        for eid in pool:
            m = EFFECTS.get(eid).__dict__.get("editing", {})
            lo, hi = m.get("recommended_energy", [0, 1])
            if eid not in asked and (m.get("style") not in allowed_styles or not (lo <= sec_e <= hi)):
                continue
            if eid not in asked and plan.bible.pacing not in m.get("recommended_pacing", ["any"]) and "any" not in m.get("recommended_pacing", []):
                continue
            d = EFFECTS.get(eid)
            params = {}
            for p_ in d.params:  # recommended intensity: position inside each numeric range
                if p_.kind != "enum" and p_.min is not None and p_.max is not None and p_.name in ("intensity", "strength", "shift", "amount"):
                    params[p_.name] = round(p_.min + (p_.max - p_.min) * m.get("recommended_intensity", 0.3), 3)
            if eid == "flash":
                params.update({"at": 0.0, "length": 0.12})
            s.effects = [EffectInstance(id=eid, params=params)]
            used += 1
            placed.append(f"{eid}@{s.out_start:.1f}s")
            break
    plan.note(f"Effects (density '{plan.bible.effect_density}', budget {budget}): " + (", ".join(placed) if placed else "none placed — no qualifying drop/accent moments") + ".")


def apply_overlaps(plan: Plan, ctx: ProjectContext | None = None) -> None:
    """Transitions overlap neighbouring shots: extend the outgoing shot's source by the overlap so the
    cut point (on the beat) is the *middle* of the transition and total duration stays unchanged.
    If a clip has no spare source frames, the shot slides earlier/later within its clip; if even that is
    impossible the transition is shortened (or becomes a cut)."""
    def src_dur(seg: Segment) -> float:
        if seg.image or ctx is None:
            return 1e9
        a = ctx.asset(seg.asset_id)
        return float(a.meta.get("duration") or (a.analysis or {}).get("meta", {}).get("duration") or 1e9) - 0.05

    for k in range(1, len(plan.segments)):
        b = plan.segments[k]
        d = b.transition_in.duration if b.transition_in.id != "cut" else 0.0
        if d <= 0:
            continue
        a = plan.segments[k - 1]
        # how much extra source each side can provide (sliding within the clip if needed)
        room_a = (src_dur(a) - (a.src_out - a.src_in)) / max(a.speed.rate, 1e-3) if not a.speed.ramp else 0.0
        room_b = (src_dur(b) - (b.src_out - b.src_in)) / max(b.speed.rate, 1e-3) if not b.speed.ramp else 0.0
        half = min(d / 2, room_a, room_b)
        if half < 0.08:
            b.transition_in = TransitionSpec()
            continue
        d = 2 * half
        b.transition_in.duration = round(d, 3)
        # outgoing shot: need half more seconds of source after src_out (slide back if the clip ends)
        need_a = half * a.speed.rate
        over = a.src_out + need_a - src_dur(a)
        if over > 0:
            a.src_in, a.src_out = round(a.src_in - over, 3), round(a.src_out - over, 3)
        # incoming shot: need half more seconds of source before src_in (slide forward if at 0)
        need_b = half * b.speed.rate
        under = need_b - b.src_in
        if under > 0:
            b.src_in, b.src_out = round(b.src_in + under, 3), round(b.src_out + under, 3)
        a.out_duration = round(a.out_duration + half, 3)
        a.src_out = round(a.src_out + need_a, 3)
        b.out_start = round(b.out_start - half, 3)
        b.out_duration = round(b.out_duration + half, 3)
        b.src_in = round(max(0.0, b.src_in - need_b), 3)


# ------------------------------------------------------------------------------- motion & reframing
def motion_designer(plan: Plan, ctx: ProjectContext, intent: StyleIntent) -> None:
    level = intent.camera_motion or plan.template.get("motion", "subtle")
    if level == "none":
        for s in plan.segments:
            if s.image:
                s.motion = MotionSpec(preset="ken_burns", intensity=0.4)
        plan.note("Camera motion: disabled (only photos get a gentle Ken Burns).")
        return
    cand = {c.key: c for c in ctx.candidates()}
    budget = int(len(plan.segments) * (0.45 if level == "subtle" else 0.65))
    used = 0
    for i, s in enumerate(plan.segments):
        c = cand.get(f"{s.asset_id}:{s.shot_index}")
        if s.image:
            s.motion = MotionSpec(preset="ken_burns", intensity=0.5)
            continue
        if used >= budget or c is None:
            continue
        static = c.scores.get("motion_score", 0) < 0.25
        sec_e = next((x.energy for x in plan.sections if x.name == s.section), 0.5)
        if not static and level == "subtle":
            continue
        if s.section in ("emotional_peak", "resolution", "reflection", "intro"):
            preset, inten = "push_in", 0.45
        elif s.section in ("opening", "establishing"):
            preset, inten = ("pull_out" if i % 2 else "pan_right"), 0.4
        elif sec_e > 0.75 and level == "dynamic":
            preset, inten = ("shake" if (i % 5 == 0 and s.beat_index is not None) else "push_in"), 0.6
        else:
            preset, inten = ("drift" if i % 3 else "push_in"), 0.35
        s.motion = MotionSpec(preset=preset, intensity=inten)
        used += 1
    plan.note(f"Camera motion ({level}): applied to {used} mostly-static shots; moving shots left untouched.")


def reframe(plan: Plan, ctx: ProjectContext) -> None:
    out_ar = plan.export.width / plan.export.height
    cand = {c.key: c for c in ctx.candidates()}
    n = 0
    for s in plan.segments:
        a = ctx.asset(s.asset_id)
        w, h = a.meta.get("display_width") or a.meta.get("width") or 16, a.meta.get("display_height") or a.meta.get("height") or 9
        src_ar = w / h
        c = cand.get(f"{s.asset_id}:{s.shot_index}")
        cx, cy = 0.5, 0.5
        if c and c.faces:
            boxes = c.faces[0]
            if boxes:
                x, y, bw, bh = max(boxes, key=lambda b: b[2] * b[3])
                cx, cy = x + bw / 2, y + bh / 2.2
        if abs(src_ar - out_ar) > 0.02:
            n += 1
        s.crop = CropSpec(cx=round(float(np.clip(cx, 0, 1)), 3), cy=round(float(np.clip(cy, 0, 1)), 3), zoom=1.0)
    if n:
        plan.note(f"Reframing: {n} shots re-framed to {plan.export.width}x{plan.export.height}, centred on detected faces where available.")


# ------------------------------------------------------------------------------- colour
def colorist(plan: Plan, ctx: ProjectContext, intent: StyleIntent, ref_map: dict | None) -> None:
    preset = plan.bible.color if COLOR_PRESETS.has(plan.bible.color) else "cinematic_neutral"
    overrides: dict[str, float] = dict((ref_map or {}).get("color_overrides", {})) if (ref_map and "color" in ref_map.get("aspects", [])) else {}
    for k, v in (intent.color_adjust or {}).items():
        if k in ("temperature", "exposure"):
            overrides[k] = overrides.get(k, 0.0) + v
        else:
            overrides[k] = v
    for e in intent.effects:
        if e in ("film_grain",):
            overrides["grain"] = max(overrides.get("grain", 0), 8)
        if e == "vignette":
            overrides["vignette"] = max(overrides.get("vignette", 0), 0.35)
    # technical shot matching (closed loop): each shot's 16×9 colour thumbnail is run through the real grading model
    # and corrected toward the target (reference look if following its colour, else the median of the selected shots);
    # then adjacent shots in a section are pulled together so temperature / exposure / saturation never jump.
    cand = {c.key: c for c in ctx.candidates()}
    rows = []
    for s in plan.segments:
        c = cand.get(f"{s.asset_id}:{s.shot_index}")
        if c and c.metrics:
            sh = next((x for x in (ctx.asset(s.asset_id).analysis or {}).get("shots", []) if x["index"] == s.shot_index), {})
            px = np.frombuffer(bytes.fromhex(sh["rgb_thumb"]), np.uint8).reshape(-1, 3).astype(np.float32) / 255 if sh.get("rgb_thumb") else None
            rows.append((s, c.metrics, px))
    if rows:
        if ref_map and ref_map.get("color_target"):
            target = ref_map["color_target"]
            src = "reference"
        else:
            keys = ("luma", "temperature", "tint", "saturation", "contrast")
            target = {k: float(np.median([m.get(k, 0) for _, m, _ in rows])) for k in keys}
            target["luma"] = float(np.clip(target["luma"], 0.38, 0.52))
            src = "project median"
        params, pred = [], []
        for s, m, px in rows:
            if px is not None:
                p_, st_ = solve_technical(px, target, strength=0.75)
            else:  # older analysis without colour thumbnails: open-loop estimate
                p_ = technical_correction(m, target)
                st_ = None
            params.append(p_)
            pred.append(st_)

        def gaps() -> tuple[float, float, float]:
            dl = dt = ds = 0.0
            for i in range(1, len(rows)):
                if pred[i] is None or pred[i - 1] is None or rows[i][0].section != rows[i - 1][0].section:
                    continue
                dl = max(dl, abs(pred[i]["luma"] - pred[i - 1]["luma"]))
                dt = max(dt, abs(pred[i]["temperature"] - pred[i - 1]["temperature"]))
                ds = max(ds, abs(pred[i]["saturation"] - pred[i - 1]["saturation"]))
            return dl, dt, ds

        before = gaps()
        for _ in range(3):  # neighbour smoothing: shrink large adjacent jumps inside a section
            for i in range(1, len(rows)):
                a_, b_ = pred[i - 1], pred[i]
                if a_ is None or b_ is None or rows[i][0].section != rows[i - 1][0].section:
                    continue
                if abs(a_["luma"] - b_["luma"]) > 0.05 or abs(a_["temperature"] - b_["temperature"]) > 0.025 or abs(a_["saturation"] - b_["saturation"]) > 0.06:
                    mid = {k: (a_[k] + b_[k]) / 2 for k in a_}
                    for j in (i - 1, i):
                        tgt = {k: pred[j][k] + 0.6 * (mid[k] - pred[j][k]) for k in mid}
                        params[j], pred[j] = solve_technical(rows[j][2], tgt, strength=1.0)
        after = gaps()
        for (s, _, _), p_ in zip(rows, params):
            s.technical = ColorAdjust(exposure=round(float(np.clip(p_["exposure"], -1, 1)), 3), temperature=round(float(np.clip(p_["temperature"], -1, 1)), 3),
                                      tint=round(float(np.clip(p_["tint"], -1, 1)), 3), saturation=round(float(np.clip(p_["saturation"], 0, 3)), 3),
                                      contrast=round(float(np.clip(p_["contrast"], 0.5, 2)), 3))
        plan.note(f"Colour: closed-loop technical match of {len(rows)} shots to {src} (luma {target['luma']:.2f}, temp {target['temperature']:+.3f}); "
                  f"predicted max adjacent jump luma {before[0]:.3f}→{after[0]:.3f}, temperature {before[1]:.3f}→{after[1]:.3f}, "
                  f"saturation {before[2]:.3f}→{after[2]:.3f}; creative look '{preset}'" + (f" with overrides {overrides}" if overrides else "") + ".")
    plan.color = ColorGrade(preset=preset, intensity=1.0, overrides={k: round(float(v), 3) for k, v in overrides.items()}, match_shots=True)


# ------------------------------------------------------------------------------- audio & sfx
def audio_engineer(plan: Plan, ctx: ProjectContext, intent: StyleIntent) -> None:
    """Dialogue priority: shots with detected speech (VAD) keep their audio as DIALOGUE; other kept clip audio is AMBIENCE.
    Speech regions are mapped to output time so the mixer ducks music, ambience and SFX under speech with smooth
    automation curves; each dialogue clip is level-matched; clipped source audio gets de-clipping."""
    keep = intent.keep_dialogue if intent.keep_dialogue is not None else True
    has_music = bool(plan.music)
    n_speech, regions = 0, []
    for s in plan.segments:
        a = ctx.asset(s.asset_id)
        aud = (a.analysis or {}).get("audio", {})
        sp = 0.0
        rate = max(s.speed.rate, 1e-3)
        seg_regions = []
        for x, y in aud.get("speech", []):
            ov0, ov1 = max(x, s.src_in), min(y, s.src_out)
            if ov1 > ov0:
                sp += ov1 - ov0
                seg_regions.append((round(s.out_start + (ov0 - s.src_in) / rate, 3), round(s.out_start + (ov1 - s.src_in) / rate, 3)))
        speech = sp > 0.4 * (s.src_out - s.src_in) and s.speed.rate >= 0.95 and not s.speed.ramp
        has_audio = bool(a.meta.get("has_audio"))
        if speech and keep and has_audio:
            s.keep_audio, s.audio_role, s.audio_gain_db = True, "dialogue", 0.0
            regions += seg_regions
            n_speech += 1
        elif has_audio and not has_music:
            s.keep_audio, s.audio_role, s.audio_gain_db = True, "ambience", -8.0
        else:
            s.keep_audio, s.audio_role = False, "muted"
        if s.keep_audio and aud.get("clipping_runs", 0) > 0.001:
            s.audio_repair = ["declip"]
    merged: list[tuple[float, float]] = []
    for r in sorted(regions):
        if merged and r[0] - merged[-1][1] < 0.3:
            merged[-1] = (merged[-1][0], max(merged[-1][1], r[1]))
        else:
            merged.append(r)
    target = -14.0 if (plan.intent.platform or "") in ("instagram_reel", "tiktok", "shorts", "youtube") else -16.0
    plan.audio = AudioPlan(dialogue_preset="dialogue_clean", ducking=intent.duck_music is not False, duck_depth_db=12.0 if n_speech else 0.0,
                           target_lufs=target, keep_clip_audio="speech_only" if has_music else "all", speech_regions=merged[:2000])
    det = next(((a.analysis or {}).get("speech_detector") for a in ctx.clips if (a.analysis or {}).get("speech_detector")), "unknown")
    plan.note(f"Audio: {n_speech} dialogue shots ({sum(b - a for a, b in merged):.1f}s of speech, detector {det}); music ducked "
              f"{plan.audio.duck_depth_db:.0f} dB, ambience {plan.audio.ambience_duck_db:.0f} dB, SFX {plan.audio.sfx_duck_db:.0f} dB under speech; "
              f"dialogue clips level-matched to {plan.audio.dialogue_target_db:.0f} dBFS RMS; "
              f"{sum(1 for s in plan.segments if s.audio_repair)} clips de-clipped; loudness target {target:.0f} LUFS.")


def sound_designer(plan: Plan, intent: StyleIntent) -> None:
    on = intent.sfx if intent.sfx is not None else plan.template.get("sfx", False)
    if not on:
        return
    items: list[SfxItem] = []
    last = -10.0
    for s in plan.segments[1:]:
        t = s.transition_in
        if t.id == "cut" or s.out_start - last < 3.0:
            continue
        kind = "impact" if t.id in ("flash", "zoom") else "whoosh"
        at = s.out_start + (t.duration / 2 if kind == "impact" else -0.15)
        items.append(SfxItem(kind=kind, at=round(max(0, at), 3), gain_db=-15 if kind == "whoosh" else -13))
        last = s.out_start
    climax = next((x for x in plan.sections if x.name in ("climax", "final_chorus", "action")), None)
    if climax and climax.start > 2.5:
        items.append(SfxItem(kind="riser", at=round(climax.start - 2.0, 3), gain_db=-18, params={"length": 2.0}))
        items.append(SfxItem(kind="impact", at=round(climax.start, 3), gain_db=-13))
    if plan.ending.type != "cut":
        items.append(SfxItem(kind="shimmer", at=round(plan.duration - plan.ending.duration + 0.2, 3), gain_db=-20))
    plan.sfx = sorted(items, key=lambda x: x.at)
    plan.note(f"Sound design: {len(plan.sfx)} restrained SFX (whoosh on transitions, riser→impact into the climax).")


# ------------------------------------------------------------------------------- typography & ending
def typography_designer(plan: Plan, ctx: ProjectContext, intent: StyleIntent, ref_map: dict | None) -> None:
    style = plan.bible.typography
    if style == "none":
        plan.note("Typography: disabled by prompt.")
        return
    anim = plan.template.get("textAnimation", "fade_up")
    texts: list[TextItem] = []
    title = intent.title or (ctx.brand or {}).get("title")
    pos = (ref_map or {}).get("text_position") or "center"
    if title:
        first = plan.sections[0] if plan.sections else None
        t0 = 0.6 if first else 0.5
        t1 = min(plan.duration - plan.ending.duration - 0.5, max(t0 + 2.5, (first.end if first else 3.0) - 0.2))
        texts.append(TextItem(id="title", kind="title", text=title, start=t0, end=round(t1, 3), style=style, animation=anim, position=pos))
    end_text = intent.end_title or (ctx.brand or {}).get("end_title") or (ctx.name if plan.ending.type in ("title", "logo_title") else None)
    if end_text and plan.ending.type in ("title", "logo_title"):
        e0 = plan.duration - plan.ending.duration + 0.3
        texts.append(TextItem(id="end_title", kind="end_title", text=end_text, start=round(e0, 3), end=round(plan.duration - 0.25, 3), style="end_card",
                              animation="tracking_reveal", position="center" if plan.ending.type == "title" else "bottom"))
    # music-driven entrances: start each text on the nearest downbeat (within ±0.5 s) so titles land with the music
    snapped = 0
    downs = np.array(plan.downbeats) if plan.downbeats else np.zeros(0)
    for t in texts:
        if len(downs):
            k = int(np.argmin(np.abs(downs - t.start)))
            if abs(downs[k] - t.start) <= 0.5 and downs[k] + 1.5 < t.end:
                t.start = round(float(downs[k]), 3)
                snapped += 1
    plan.texts = texts
    if snapped:
        plan.note(f"Typography: {snapped} text entrance(s) placed on downbeats.")
    plan.note("Typography: " + (", ".join(f"'{t.text}' ({t.style}/{t.animation})" for t in texts) if texts else "no on-screen text (none was provided — nothing invented)."))


def ending_designer(plan: Plan, ctx: ProjectContext, intent: StyleIntent) -> None:
    typ = intent.ending or ("logo_title" if intent.use_brand else plan.template.get("ending", "fade"))
    logo = ctx.logo
    if typ in ("logo", "logo_title") and not logo:
        plan.note("Ending: logo requested but no logo asset/brand kit found — using a title/fade ending instead.")
        typ = "title" if typ == "logo_title" else "fade"
    dur = {"fade": 0.0, "cut": 0.0, "title": 3.0, "logo": 3.0, "logo_title": 3.5}[typ]
    plan.ending = Ending(type=typ, duration=dur, logo_asset_id=logo.id if logo and typ in ("logo", "logo_title") else None,
                         text=intent.end_title)
