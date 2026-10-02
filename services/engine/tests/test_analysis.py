from editor.media.analyze import analyze_video, apply_uniqueness
from editor.media.probe import kind_for, probe
from editor.music.analyze import analyze_music, best_window
from editor.reference.analyze import analyze_reference
from editor.storage import fingerprint


def _by_kind(dataset, kind):
    return [c for c in dataset["clips"] if f"_{kind}" in c.name]


def test_probe_metadata(dataset):
    m = probe(dataset["clips"][0])
    assert m["has_video"] and m["has_audio"]
    assert (m["width"], m["height"]) == (640, 360)
    assert abs(m["fps"] - 30) < 0.1
    assert m["orientation"] == "landscape"
    assert kind_for("x.MOV") == "video" and kind_for("y.flac") == "audio" and kind_for("z.webp") == "image" and kind_for("a.sh") is None


def test_quality_detectors(dataset):
    issues = {}
    for c in dataset["clips"]:
        a = analyze_video(c, "fast")
        issues[c.name] = {i for s in a["shots"] for i in s["issues"]}
    for c in _by_kind(dataset, "blurry"):
        assert "blurry" in issues[c.name], issues[c.name]
    for c in _by_kind(dataset, "dark"):
        assert "underexposed" in issues[c.name]
    assert _by_kind(dataset, "shaky") and _by_kind(dataset, "overexposed")
    for c in _by_kind(dataset, "shaky"):
        assert "shaky" in issues[c.name]
    for c in _by_kind(dataset, "overexposed"):
        assert "overexposed" in issues[c.name]
    # the first clips are clean
    assert not issues[dataset["clips"][0].name] - {"underexposed"}


def test_duplicate_detection(dataset):
    an = {c.name: analyze_video(c, "fast") for c in dataset["clips"]}
    groups = apply_uniqueness(an)
    flat = {k.split(":")[0] for g in groups for k in g}
    assert any("duplicate" in n for n in flat), groups


def test_cache_hit(dataset):
    c = dataset["clips"][1]
    fp = fingerprint(c)
    a = analyze_video(c, "fast", fp)
    b = analyze_video(c, "fast", fp)
    assert a == b


def test_music_bpm_and_sections(dataset):
    for song, bpm in zip(dataset["songs"], (96, 128)):
        m = analyze_music(song)
        assert abs(m["bpm"] - bpm) / bpm < 0.04 or abs(m["bpm"] * 2 - bpm) / bpm < 0.04 or abs(m["bpm"] / 2 - bpm) / bpm < 0.04, m["bpm"]
        assert len(m["beats"]) > m["duration"] * bpm / 60 * 0.8
        assert len(m["sections"]) >= 3
        s0, s1 = best_window(m, 20)
        assert 0 <= s0 and s1 - s0 == 20


def test_reference_profile(dataset):
    r = analyze_reference(dataset["reference"])
    assert abs(r["median_shot_duration"] - 1.2) < 0.25
    assert r["cuts_per_minute"] > 35
    assert r["transition_types"].get("fade", 0) >= 1
    assert r["saturation"] > 0.3 and r["aspect_ratio"] == "16:9"
    assert r["music"] and abs(r["music"]["bpm"] - 124) < 6
