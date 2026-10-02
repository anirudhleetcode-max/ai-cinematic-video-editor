"""Planning context: everything the agents know about a project (assets, analyses, brand, reference)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Asset:
    id: str
    kind: str  # video | audio | image
    role: str  # clip | music | reference | logo | voiceover | sfx | lut | broll
    filename: str
    path: str
    meta: dict
    analysis: dict | None = None
    ordinal: int = 0


@dataclass
class Candidate:
    """One usable shot (sub-range of a clip) the Clip Selector can place on the timeline."""
    key: str
    asset: Asset
    shot_index: int
    start: float
    end: float
    best: float
    scores: dict
    issues: list[str]
    tags: list[str]
    metrics: dict
    overall: float
    dhash: int
    faces: list
    image: bool = False

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class ProjectContext:
    project_id: str
    name: str
    prompt: str
    assets: list[Asset]
    reference_profile: dict | None = None
    brand: dict | None = None
    mode: str = "fast"
    transcript_words: list[dict] = field(default_factory=list)  # [{w, asset_id, t0, t1}] source-time words

    @property
    def clips(self) -> list[Asset]:
        return sorted([a for a in self.assets if a.role in ("clip", "broll") and a.kind in ("video", "image")], key=lambda a: (a.ordinal, a.filename))

    @property
    def songs(self) -> list[Asset]:
        return sorted([a for a in self.assets if a.role == "music" and a.kind in ("audio", "video")], key=lambda a: (a.ordinal, a.filename))

    @property
    def voiceovers(self) -> list[Asset]:
        return [a for a in self.assets if a.role == "voiceover"]

    @property
    def logo(self) -> Asset | None:
        if self.brand and self.brand.get("logo_asset_id"):
            for a in self.assets:
                if a.id == self.brand["logo_asset_id"]:
                    return a
        return next((a for a in self.assets if a.role == "logo"), None)

    def asset(self, aid: str) -> Asset:
        for a in self.assets:
            if a.id == aid:
                return a
        raise KeyError(aid)

    def candidates(self) -> list[Candidate]:
        out: list[Candidate] = []
        for a in self.clips:
            if a.kind == "image":
                out.append(Candidate(f"{a.id}:0", a, 0, 0.0, 600.0, 0.0,
                                     {"quality_score": 0.7, "cinematic_score": 0.6, "energy_score": 0.2, "emotional_score": 0.4, "motion_score": 0.0,
                                      "uniqueness_score": 1.0, "face_visibility_score": 0.0, "composition_score": 0.5, "stability_score": 1.0,
                                      "sharpness_score": 0.8, "exposure_score": 0.8, "audio_score": 0.0},
                                     [], ["photo", "static"], {}, 0.6, 0, [], image=True))
                continue
            an = a.analysis or {}
            dur = float(an.get("meta", {}).get("duration") or a.meta.get("duration") or 0)
            for sh in an.get("shots", []):
                s, e = float(sh["start"]), min(float(sh["end"]), dur or float(sh["end"]))
                trim = min(0.15, (e - s) * 0.08)  # avoid boundary frames of detected cuts
                s, e = s + (trim if sh.get("index", 0) > 0 else 0.0), e - trim
                if e - s < 0.4:
                    continue
                out.append(Candidate(f"{a.id}:{sh['index']}", a, sh["index"], s, e, float(sh.get("best_moment", (s + e) / 2)), sh["scores"],
                                     list(sh.get("issues", [])), list(sh.get("tags", [])), sh.get("metrics", {}), float(sh.get("overall_edit_score", 0.5)),
                                     int(sh.get("dhash", 0)), sh.get("faces", [])))
        return out
