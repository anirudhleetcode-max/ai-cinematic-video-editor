"""Pacing engine: target shot durations from music, energy, story role, shot type, reference and prompt.

These are editing heuristics, not laws (documented in docs/AI_DIRECTOR.md). Every output range can be overridden by
the plan (an AI provider or the user's prompt sets `pacing_factor`, explicit section lengths, or a reference profile).

Role ranges (seconds, before tempo/energy/reference scaling):
    hook        0.5 – 2.5      fast, attention-grabbing
    opening     2.0 – 5.0      establishing, let the viewer orient
    build       1.0 – 4.0      rising energy
    emotional   2.0 – 6.0      hold on faces / moments
    climax      0.3 – 2.0      fastest cutting
    resolution  2.0 – 5.0      settle
"""
from __future__ import annotations

from dataclasses import dataclass

ROLE_RANGE: dict[str, tuple[float, float]] = {
    "hook": (0.5, 2.5), "opening": (2.0, 5.0), "build": (1.0, 4.0), "emotional": (2.0, 6.0), "climax": (0.3, 2.0), "resolution": (2.0, 5.0),
}
SECTION_ROLE = {
    "hook": "hook", "title": "hook", "cta": "resolution",
    "opening": "opening", "establishing": "opening", "intro": "opening", "setup": "opening", "problem": "opening",
    "people": "build", "activities": "build", "journey": "build", "location": "build", "experience": "build", "story": "build",
    "development": "build", "build": "build", "product": "build", "features": "build", "demonstration": "build", "preparation": "build",
    "verse": "build", "performance": "build", "crowd": "build", "vision": "build", "benefit": "build", "bridge": "emotional",
    "energy": "climax", "best_moments": "climax", "climax": "climax", "action": "climax", "chorus": "climax", "final_chorus": "climax",
    "celebration": "climax",
    "emotional_peak": "emotional", "ceremony": "emotional", "reflection": "resolution", "resolution": "resolution", "outro": "resolution",
}


@dataclass
class PaceTarget:
    role: str
    lo: float
    hi: float
    target: float
    beats: int | None  # preferred cut length in beats (None = free timing)
    why: str


def role_of(section: str) -> str:
    return SECTION_ROLE.get(section, "build")


def target_for(section: str, energy: float, *, bpm: float | None = None, reference_median: float | None = None, pacing_factor: float = 1.0,
               shot_size: str | None = None, speech: bool = False) -> PaceTarget:
    """Target duration for the next shot of `section` at local `energy` (0..1)."""
    role = role_of(section)
    lo, hi = ROLE_RANGE[role]
    why = [f"{role} range {lo:.1f}–{hi:.1f}s"]
    # energy moves the target inside the role range (high energy → shorter)
    t = hi - (hi - lo) * min(1.0, max(0.0, energy))
    if reference_median:
        # follow the reference's measured rhythm, but stay within the role's range (its pacing, not its exact cuts)
        ref = min(hi, max(lo, reference_median * (0.8 + 0.4 * (1 - energy))))
        t = 0.4 * t + 0.6 * ref
        why.append(f"reference median {reference_median:.2f}s")
    t *= pacing_factor
    if pacing_factor != 1.0:
        why.append(f"prompt pacing ×{pacing_factor:.2f}")
    if shot_size in ("wide", "unknown") and role in ("opening", "resolution", "emotional"):
        t *= 1.15  # wide establishing shots need time to read
        why.append("wide shot held longer")
    elif shot_size in ("closeup", "extreme_closeup") and role in ("climax", "hook"):
        t *= 0.9
    if speech:
        t = max(t, 2.5)  # never chop a speaking shot into a flash cut
        why.append("speech: ≥2.5s")
    t = max(0.3, min(t, hi * pacing_factor * 1.2 if pacing_factor > 1 else hi * 1.2))
    beats = None
    if bpm and bpm > 0:
        bi = 60.0 / bpm
        # prefer musically meaningful lengths: 1, 2, 4, 8 beats (phrase-aware) — pick the closest
        options = [1, 2, 3, 4, 6, 8, 12, 16]
        beats = min(options, key=lambda n: abs(n * bi - t))
        why.append(f"{beats} beats @ {bpm:.0f} BPM")
    return PaceTarget(role, lo, hi, round(t, 3), beats, "; ".join(why))
