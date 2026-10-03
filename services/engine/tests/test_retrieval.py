"""Shot retrieval by description: label vocabulary, ranking, honest misses, and use in revisions."""
import json
from editor.retrieval import resolve, search


def _shots():
    return [{"filename": "street.mp4", "analysis": {"shots": [
        {"start": 0, "end": 2, "tags": ["wide", "outdoor"], "overall_edit_score": 0.6,
         "semantic": {"subjects": [{"label": "vehicles", "frequency": 1}], "objects": [{"label": "car", "frequency": 0.9}],
                      "scene_type": {"setting": "outdoor", "time_of_day": "day"}, "shot_size": "wide"}},
        {"start": 2, "end": 5, "tags": ["closeup", "faces", "crowd"], "overall_edit_score": 0.8,
         "semantic": {"subjects": [{"label": "people", "frequency": 1}, {"label": "crowd", "frequency": 1}], "objects": [{"label": "person", "frequency": 1}],
                      "scene_type": {"setting": "outdoor", "time_of_day": "night"}, "shot_size": "closeup"}}]}}]


def test_resolve_vocabulary():
    assert resolve("the crowd")[0] >= {"crowd"}
    assert resolve("more dogs")[0] == {"dog"}
    assert resolve("cell phones")[0] == {"cell phone"}
    assert resolve("close-ups")[0] == {"closeup"}
    labels, unknown = resolve("a red umbrella")
    assert labels == {"umbrella"} and unknown == ["red"]
    assert resolve("an ethereal feeling")[0] == set()


def test_search_ranks_and_reports_misses():
    r = search(_shots(), "show the crowd at night")
    assert r["understood"] and r["matches"][0]["shot"] == 1 and "night" in r["matches"][0]["matched"]
    assert search(_shots(), "cars")["matches"][0]["shot"] == 0
    miss = search(_shots(), "giraffe")
    assert miss["understood"] and miss["n_matches"] == 0
    vague = search(_shots(), "something ethereal")
    assert not vague["understood"] and "no embedding model" in vague["method"]


def test_revision_query_is_honest_when_nothing_matches(project):
    from editor import service as S

    S.create_edit_plan(project["id"], "A 15 second energetic festival recap", "fast")
    v = S.revise(project["id"], "show more of the giraffe")
    ch = [c for c in v["changes"] if c["op"] == "prefer_query"]
    assert ch and ch[0].get("noop") and "giraffe" in ch[0]["reason"]


def test_revision_query_prefers_matching_shots(project):
    from editor import db, service as S

    base = S.create_edit_plan(project["id"], "A 15 second energetic festival recap", "fast")
    # tag one clip's shots as containing a dog, as the deep detector would
    # a clip the baseline edit uses, chosen from the plan itself (which clips are used depends on the installed detectors)
    counts = {}
    for seg in base["plan"]["timeline"]:
        counts[seg["asset_id"]] = counts.get(seg["asset_id"], 0) + 1
    target = db.get("assets", min(counts, key=lambda k: (counts[k], k)))
    before = sum(s["asset_id"] == target["id"] for s in base["plan"]["timeline"])
    an = target["analysis"]
    for sh in an["shots"]:
        sh.setdefault("semantic", {}).setdefault("objects", []).append({"label": "dog", "frequency": 1.0})
    db.update("assets", target["id"], analysis=an)
    try:
        v = S.revise(project["id"], "show more of the dog")
        ch = [c for c in v["changes"] if c["op"] == "prefer_query"][0]
        assert not ch.get("noop") and ch["matched_labels"] == ["dog"]
        after = sum(s["asset_id"] == target["id"] for s in v["plan"]["timeline"])
        # its single 4 s shot is already in the edit: "more" keeps it, and does not repeat footage to add it twice
        assert after >= before >= 1 and base["id"] != v["id"]
        v2 = S.revise(project["id"], "no dogs please")
        ch2 = [c for c in v2["changes"] if c["op"] == "prefer_query"][0]
        assert ch2["weight"] < 0 and ch2["matched_labels"] == ["dog"]
        assert sum(s["asset_id"] == target["id"] for s in v2["plan"]["timeline"]) == 0
    finally:
        for sh in an["shots"]:
            sh["semantic"]["objects"] = [o for o in sh["semantic"]["objects"] if o["label"] != "dog"]
        db.update("assets", target["id"], analysis=an)


def test_negative_requests_parse_with_their_meaning():
    """Negation must never flip a request: "don't use dark clips" is an exclusion, not a preference."""
    from editor.director.revise import parse_revision

    def ops(t):
        return [(o["op"], o.get("issue") or tuple(o.get("labels") or ()), o.get("weight")) for o in parse_revision(t).ops]

    assert ops("no dogs") == [("prefer_query", ("dog",), -0.8)]
    assert ("prefer_query", ("crowd", "faces", "group", "people", "person"), -0.8) in ops("avoid people")
    assert ("avoid_issue", "underexposed", None) in ops("don't use dark clips")
    assert all(w is None or w < 0 for _, _, w in ops("don't use dark clips"))
    assert ops("avoid blurry footage") == [("avoid_issue", "blurry", None)]
    assert ops("skip the shaky shots") == [("avoid_issue", "shaky", None)]
    assert ops("do not show the crowd") == [("prefer_query", ("crowd", "group"), -0.8)]
    assert ops("never use screen recordings")[0][2] == -0.8
    assert ops("show the crowd") == [("prefer_query", ("crowd", "group"), 0.6)]
    # unrelated revisions are not mistaken for content queries
    assert [o for o, _, _ in ops("remove the first scene")] == ["remove_segment"]
    assert [o for o, _, _ in ops("no transitions")] == ["transitions"]
    assert [o for o, _, _ in ops("cut it down to 30 seconds")] == ["duration"]


def test_avoid_issue_excludes_footage_or_reports_relaxation(project):
    from editor import db, service as S

    S.create_edit_plan(project["id"], "A 15 second energetic festival recap", "fast")
    v = S.revise(project["id"], "avoid blurry footage")
    ch = [c for c in v["changes"] if c["op"] == "avoid_issue"][0]
    used = {(s["asset_id"], s["shot_index"]) for s in v["plan"]["timeline"]}
    blurry = {(a["id"], i) for a in db.query("SELECT id, analysis FROM assets WHERE project_id=? AND role='clip'", (project["id"],))
              for i, sh in enumerate((a["analysis"] or {}).get("shots", [])) if "blurry" in sh.get("issues", []) for i in [sh.get("index", i)]}
    # either no blurry shot is used, or the revision says the exclusion had to be relaxed
    assert not (used & blurry) or ch.get("relaxed"), (used & blurry, ch)


def test_multi_label_exclusion_applies_in_full(project):
    """'avoid people' names five labels; the exclusion must not be diluted across them (it was −0.8/√5 ≈ −0.36,
    above the exclusion threshold, so people stayed in the edit — found on real footage)."""
    from editor import db, service as S

    base = S.create_edit_plan(project["id"], "A 15 second energetic festival recap", "fast")
    used = []
    for seg in base["plan"]["timeline"]:
        if seg["asset_id"] not in used:
            used.append(seg["asset_id"])
    tagged = used[:2]
    saved = {}
    for aid in tagged:
        a = db.get("assets", aid)
        saved[aid] = a["analysis"]
        an = json.loads(json.dumps(a["analysis"]))
        for sh in an["shots"]:
            sh.setdefault("semantic", {}).setdefault("objects", []).append({"label": "person", "frequency": 1.0})
            sh["semantic"].setdefault("subjects", []).append({"label": "people", "frequency": 1.0})
        db.update("assets", aid, analysis=an)
    try:
        v = S.revise(project["id"], "avoid people", base["id"])
        ch = [c for c in v["changes"] if c["op"] == "prefer_query"][0]
        after = sum(s["asset_id"] in tagged for s in v["plan"]["timeline"])
        assert after == 0 or ch.get("relaxed"), (after, ch)
    finally:
        for aid, an in saved.items():
            db.update("assets", aid, analysis=an)
