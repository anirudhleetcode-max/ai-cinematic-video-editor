import numpy as np

from editor import service as S
from editor.director.planner import build_plan
from editor.director.prompt_parser import parse_prompt
from editor.director.revise import apply_revision, parse_revision

ACCEPT = ("Create a 60-second professional cinematic event highlight. Analyze the reference and follow its pacing, color mood, typography philosophy, "
          "and transition style without copying its footage. Select the best clips, remove poor-quality shots, begin with a strong hook, synchronize "
          "cuts to the supplied music, use slower emotional shots where appropriate, build energy toward the climax, add tasteful motion and transitions, "
          "apply consistent professional color grading, add elegant event typography, duck music under speech, and finish with a strong branded ending.")


def test_parse_acceptance_prompt():
    i = parse_prompt(ACCEPT)
    assert i.duration == 60 and i.story_type == "event" and i.beat_sync and i.duck_music
    assert i.use_reference and {"pacing", "color", "typography", "transitions"} <= set(i.reference_aspects)
    assert i.energy_curve == "build_to_climax" and i.hook_seconds == 3.0 and i.ending == "logo_title" and i.aspect_ratio is None


def test_parse_platform_and_music():
    i = parse_prompt("Make this an Instagram reel, 30 sec, use all three songs, karaoke captions")
    assert i.aspect_ratio == "9:16" and i.duration == 30 and i.music_strategy == "all" and i.captions and i.caption_style == "karaoke"
    assert parse_prompt("use song 2").music_indices == [2]
    assert parse_prompt("2:30 travel film").duration == 150


def test_plan_quality(project):
    ctx = S.build_context(project["id"], ACCEPT.replace("60-second", "24-second"))
    plan = build_plan(ctx)
    assert abs(plan.duration - 24) < 1e-6
    assert plan.reference_profile_used and plan.ending.type == "logo_title" and plan.ending.logo_asset_id
    # no rejected footage used
    an = {a.id: a.analysis for a in ctx.clips}
    for s in plan.timeline:
        sh = next(x for x in an[s.asset_id]["shots"] if x["index"] == s.shot_index)
        assert not set(sh["issues"]) & {"blurry", "black", "duplicate"}, (s.asset_id, sh["issues"])
    # cuts land on the music beat grid
    beats = []
    for m in plan.music:
        a = ctx.asset(m.asset_id).analysis
        beats += [b - m.src_in + m.out_start for b in a["beats"]]
    beats = np.array(beats)
    cuts = [s.out_start + (s.transition_in.duration / 2 if s.transition_in.id != "cut" else 0) for s in plan.timeline[1:]]
    on_beat = np.mean([np.min(np.abs(beats - c)) < 0.06 for c in cuts])
    assert on_beat > 0.85, on_beat
    # restraint: most boundaries are cuts
    n_trans = sum(1 for s in plan.timeline if s.transition_in.id != "cut")
    assert n_trans <= max(1, int(0.4 * len(plan.timeline)))
    # consecutive shots come from different clips most of the time
    same = sum(1 for a, b in zip(plan.timeline, plan.timeline[1:]) if a.asset_id == b.asset_id)
    assert same <= len(plan.timeline) * 0.2


def test_revision_parsing():
    assert [o["op"] for o in parse_revision("Make it more energetic and reduce the intro to 3 seconds.").ops] == ["pacing", "section_length"]
    assert [o["domain"] for o in parse_revision("Make the colors warmer.").ops] == ["color"]
    assert parse_revision("Use song 2 for the final section.").ops[0] == {"op": "section_song", "domain": "music", "song": 2, "where": "final"}


def test_revisions_modify_existing_plan(project):
    ctx = S.build_context(project["id"], ACCEPT.replace("60-second", "24-second"))
    plan = build_plan(ctx)
    e, ops = apply_revision(plan, "Make it more energetic and reduce the intro to 3 seconds.", ctx)
    assert len(e.timeline) > len(plan.timeline)
    intro = next(s for s in e.story_structure if s.name in ("opening", "intro"))
    assert abs((intro.end - intro.start) - 3.0) < 0.01
    kept = sum(1 for a, b in zip(plan.timeline, e.timeline) if (a.asset_id, a.shot_index) == (b.asset_id, b.shot_index))
    assert kept >= len(plan.timeline) * 0.6
    w, _ = apply_revision(e, "Make the colors warmer.", ctx)
    assert w.color_grade.overrides["temperature"] > e.color_grade.overrides.get("temperature", 0)
    assert [s.model_dump() for s in w.timeline] == [s.model_dump() for s in e.timeline]  # colour-only change
    m, _ = apply_revision(w, "Use song 1 for the final section.", ctx)
    assert len({x.asset_id for x in m.music}) == 2 or m.music[-1].asset_id == ctx.songs[0].id
    assert m.music[-1].asset_id == ctx.songs[0].id
    assert m.color_grade.overrides.get("temperature") == w.color_grade.overrides.get("temperature")
