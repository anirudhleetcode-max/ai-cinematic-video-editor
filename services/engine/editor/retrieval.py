"""Shot retrieval by description ("show the crowd", "more of the dog", "no screen recordings").

Label-based, not embedding-based: a query is mapped to the labels the analysers actually produce — detector object
classes (COCO-80, when the deep vision models are installed), subject categories, shot size, setting, time of day,
motion and speech tags. A shot matches when it carries one of those labels. When no analysed shot carries them, the
search says so instead of guessing. Free-text visual concepts outside this vocabulary ("a red umbrella at sunset")
need an image-text embedding model (e.g. CLIP), which is not installed — such queries return `understood=False`.
"""
from __future__ import annotations

import re

from .vision import SUBJECT_OF

_GROUPS: dict[str, set[str]] = {
    "people": {"people", "faces", "group", "crowd", "person"}, "person": {"people", "faces", "person"}, "human": {"people", "faces", "person"},
    "face": {"faces"}, "reaction": {"faces"}, "portrait": {"faces", "closeup"},
    "crowd": {"crowd", "group"}, "audience": {"crowd", "group"}, "group": {"group", "crowd"}, "team": {"group", "crowd"},
    "animal": {"animals"}, "pet": {"animals", "dog", "cat"}, "wildlife": {"animals"},
    "vehicle": {"vehicles"}, "traffic": {"vehicles", "car", "bus", "truck"}, "transport": {"vehicles"},
    "food": {"food"}, "meal": {"food"}, "dish": {"food"}, "drink": {"food", "cup", "wine glass", "bottle"},
    "sport": {"sports"}, "screen": {"screen", "screen_recording"}, "computer": {"laptop", "screen"}, "phone": {"cell phone"},
    "product": {"products"}, "street": {"street", "vehicles"}, "city": {"street", "vehicles"}, "urban": {"street", "vehicles"},
    "indoor": {"indoor", "interior"}, "inside": {"indoor", "interior"}, "interior": {"indoor", "interior"}, "room": {"indoor", "interior"},
    "outdoor": {"outdoor"}, "outside": {"outdoor"}, "nature": {"outdoor"}, "landscape": {"outdoor", "wide"},
    "night": {"night"}, "day": {"day"}, "daytime": {"day"}, "dark": {"dark"}, "bright": {"bright"},
    "closeup": {"closeup"}, "close": {"closeup"}, "wide": {"wide"}, "establishing": {"wide"}, "medium": {"medium"},
    "action": {"high_motion"}, "movement": {"high_motion", "moving"}, "motion": {"high_motion", "moving"}, "static": {"static"},
    "talking": {"speech"}, "speech": {"speech"}, "speaking": {"speech"}, "interview": {"speech", "faces"}, "dialogue": {"speech"},
    "colorful": {"colorful"}, "colourful": {"colorful"}, "recording": {"screen_recording"},
}
_COCO = set(SUBJECT_OF) | {"person"}
_STOP = {"the", "a", "an", "of", "with", "more", "some", "shots", "shot", "clips", "clip", "footage", "scenes", "scene", "moments", "moment",
         "show", "me", "and", "in", "at", "on", "use", "include", "lots", "lot", "few", "any", "all", "please", "those", "that", "this", "it"}


def _singular(w: str) -> str:
    if w in _GROUPS or w in _COCO:
        return w
    for suf, rep in (("ies", "y"), ("es", ""), ("s", "")):
        if w.endswith(suf) and (w[: -len(suf)] + rep) in (_GROUPS.keys() | _COCO):
            return w[: -len(suf)] + rep
    return w


def resolve(phrase: str) -> tuple[set[str], list[str]]:
    """(labels, unknown words) for a description."""
    p = re.sub(r"close[\s\-]?ups?", "closeup", phrase.lower())
    p = re.sub(r"[^a-z ]", " ", p)
    labels: set[str] = set()
    for coco in sorted(_COCO, key=len, reverse=True):  # multi-word labels first ("hot dog", "cell phone", "traffic light")
        if " " in coco and re.search(rf"\b{coco}s?\b", p):
            labels.add(coco)
            p = re.sub(rf"\b{coco}s?\b", " ", p)
    unknown = []
    for w in p.split():
        if w in _STOP:
            continue
        s = _singular(w)
        if s in _GROUPS:
            labels |= _GROUPS[s]
        elif s in _COCO:
            labels.add(s)
        else:
            unknown.append(w)
    return labels, unknown


def shot_labels(shot: dict) -> set[str]:
    sem = shot.get("semantic") or {}
    out = set(shot.get("tags") or []) | {x["label"] for x in sem.get("subjects", [])} | {x["label"] for x in sem.get("objects", [])}
    st = sem.get("scene_type") or {}
    out |= {v for v in st.values() if v and v != "unknown"}
    if sem.get("shot_size") and sem["shot_size"] != "unknown":
        out.add(sem["shot_size"])
    return out


def search(assets, phrase: str, limit: int = 20) -> dict:
    """Rank analysed shots of `assets` (director.context.Asset or dicts with filename/analysis) against a description."""
    labels, unknown = resolve(phrase)
    hits = []
    if labels:
        for a in assets:
            an = a.analysis if hasattr(a, "analysis") else a.get("analysis")
            name = a.filename if hasattr(a, "filename") else a.get("filename")
            for i, sh in enumerate((an or {}).get("shots", [])):
                m = labels & shot_labels(sh)
                if m:
                    hits.append({"file": name, "shot": i, "start": sh.get("start"), "end": sh.get("end"), "matched": sorted(m),
                                 "score": round(len(m) + 0.5 * float(sh.get("overall_edit_score") or 0), 3)})
    hits.sort(key=lambda h: -h["score"])
    return {"query": phrase, "labels": sorted(labels), "unknown_words": unknown, "understood": bool(labels), "matches": hits[:limit],
            "n_matches": len(hits), "method": "label match (detector classes, subjects, scene / framing / motion tags); no embedding model"}
