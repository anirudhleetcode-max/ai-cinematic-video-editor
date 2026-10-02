"""Dynamic discovery of every creative registry."""
from __future__ import annotations

import json
from functools import lru_cache

from ..config import get_settings
from .audio import AUDIO_PRESETS
from .color import COLOR_PRESETS
from .effects import EFFECTS
from .motion import MOTION_PRESETS
from .text import TEXT_ANIMATIONS, TEXT_STYLES
from .transitions import TRANSITIONS

REGISTRIES = {
    "effects": EFFECTS,
    "transitions": TRANSITIONS,
    "text-animations": TEXT_ANIMATIONS,
    "text-styles": TEXT_STYLES,
    "color-presets": COLOR_PRESETS,
    "audio-presets": AUDIO_PRESETS,
    "motion-presets": MOTION_PRESETS,
}


@lru_cache(maxsize=1)
def templates() -> dict[str, dict]:
    out = {}
    for p in sorted(get_settings().templates_dir.glob("*.json")):
        t = json.loads(p.read_text())
        out[t["id"]] = t
    return out


KIND_WORDS = {"effects": r"effects?|fx", "transitions": r"transitions?", "text-animations": r"animations?|text|titles?|captions?|typography",
              "text-styles": r"text|titles?|captions?|typography|fonts?|lower[ -]?thirds?", "color-presets": r"colou?rs?|grades?|grading|looks?|luts?",
              "audio-presets": r"audio|sound|dialogue|voice", "motion-presets": r"motion|camera|zoom|pan"}


def search_library(q: str, limit: int = 40) -> list[dict]:
    import re

    ql = q.lower()
    wanted = {k for k, rx in KIND_WORDS.items() if re.search(rf"\b({rx})\b", ql)}
    terms = re.sub("|".join(rf"\b({rx})\b" for rx in KIND_WORDS.values()), " ", ql).strip() or ql
    res = []
    for kind, reg in REGISTRIES.items():
        if wanted and kind not in wanted:
            continue
        hits = reg.search(terms) if terms.strip() else reg.all()
        for d in hits:
            res.append({"kind": kind, **d.as_dict()})
    for tid, t in templates().items():
        hay = " ".join([tid, t["name"], *t.get("tags", [])]).lower()
        if any(w in hay for w in q.lower().split()):
            res.append({"kind": "templates", "id": tid, "name": t["name"], "tags": t.get("tags", [])})
    return res[:limit]


def library_stats() -> dict:
    return {k: {"definitions": len(r.all()), "parameter_configurations": r.total_configurations()} for k, r in REGISTRIES.items()} | {
        "templates": {"definitions": len(templates())}}
