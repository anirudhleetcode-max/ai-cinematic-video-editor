"""Shot retrieval by description: label vocabulary, ranking, honest misses, and use in revisions."""
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
