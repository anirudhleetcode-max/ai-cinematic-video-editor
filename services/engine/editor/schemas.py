"""Strict, versioned schemas. The EditPlan is the *only* interface between the AI layer and the media
engine: every field is validated and every value is bounded, so model output can never inject
arbitrary FFmpeg arguments."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AspectRatio = Literal["16:9", "9:16", "1:1", "4:5", "21:9"]
Mode = Literal["fast", "quality", "emergency"]
_ID = r"^[a-z0-9_\-]{1,64}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- intent (prompt understanding)
class StyleIntent(Strict):
    """Structured interpretation of the user's prompt (from the deterministic parser and/or an LLM)."""
    duration: float | None = Field(None, ge=3, le=1800)
    aspect_ratio: AspectRatio | None = None
    platform: str | None = Field(None, max_length=40)
    story_type: str | None = Field(None, max_length=40)
    styles: list[str] = Field(default_factory=list, max_length=12)
    mood: list[str] = Field(default_factory=list, max_length=12)
    pacing: Literal["slow", "medium", "fast", "very_fast"] | None = None
    pacing_factor: float | None = Field(None, ge=0.3, le=3.0, description="multiplier on shot length applied on top of pacing/reference")
    energy_curve: Literal["flat", "build", "build_to_climax", "peak_early", "wave"] | None = None
    beat_sync: bool | None = None
    color_preset: str | None = Field(None, max_length=48)
    color_adjust: dict[str, float] = Field(default_factory=dict)
    transition_style: Literal["none", "minimal", "subtle", "dynamic", "energetic", "glitch"] | None = None
    effects: list[str] = Field(default_factory=list, max_length=24)
    slow_motion: bool | None = None
    speed_ramps: bool | None = None
    camera_motion: Literal["none", "subtle", "dynamic"] | None = None
    stabilize: bool | None = None
    text_style: str | None = Field(None, max_length=48)
    title: str | None = Field(None, max_length=120)
    end_title: str | None = Field(None, max_length=120)
    captions: bool | None = None
    caption_style: str | None = Field(None, max_length=48)
    music_strategy: Literal["single", "all", "auto"] | None = None
    music_indices: list[int] = Field(default_factory=list, max_length=10)
    duck_music: bool | None = None
    keep_dialogue: bool | None = None
    sfx: bool | None = None
    hook_seconds: float | None = Field(None, ge=0, le=30)
    intro_seconds: float | None = Field(None, ge=0, le=60)
    ending: Literal["fade", "logo", "title", "logo_title", "cut"] | None = None
    use_reference: bool | None = None
    reference_aspects: list[str] = Field(default_factory=list, max_length=10)
    use_brand: bool | None = None
    avoid: list[str] = Field(default_factory=list, max_length=12)
    prefer_tags: list[str] = Field(default_factory=list, max_length=12)
    mode: Mode | None = None
    notes: list[str] = Field(default_factory=list, max_length=40)


# ---------------------------------------------------------------- creative bible
class CreativeBible(Strict):
    style: str
    color: str
    typography: str
    transition_philosophy: str
    effect_philosophy: str
    pacing: str
    music_strategy: str
    story_structure: list[str]
    effect_budget: float = Field(0.25, ge=0, le=1, description="max fraction of segments that may carry a stylised effect")
    transition_budget: float = Field(0.2, ge=0, le=1, description="max fraction of boundaries that are not hard cuts")


# ---------------------------------------------------------------- timeline elements
class SpeedSpec(Strict):
    """Constant speed (`rate`) or a ramp: list of (position 0..1 within the *output* segment, rate)."""
    rate: float = Field(1.0, ge=0.1, le=16)
    ramp: list[tuple[float, float]] | None = None
    freeze_end: float = Field(0.0, ge=0, le=5, description="seconds to hold the last frame")
    interpolate: bool = False

    @field_validator("ramp")
    @classmethod
    def _ramp(cls, v):
        if v is None:
            return v
        if len(v) < 2 or len(v) > 16:
            raise ValueError("ramp needs 2..16 keyframes")
        for p, r in v:
            if not (0 <= p <= 1 and 0.1 <= r <= 16):
                raise ValueError("ramp keyframe out of range")
        return sorted(v)


class MotionSpec(Strict):
    preset: str = Field("none", pattern=_ID)
    intensity: float = Field(0.5, ge=0, le=1)
    params: dict[str, float] = Field(default_factory=dict)


class CropSpec(Strict):
    """Normalised crop window (centre + zoom) used for reframing to the output aspect."""
    cx: float = Field(0.5, ge=0, le=1)
    cy: float = Field(0.5, ge=0, le=1)
    zoom: float = Field(1.0, ge=1, le=4)


class EffectInstance(Strict):
    id: str = Field(pattern=_ID)
    params: dict[str, float | str] = Field(default_factory=dict)


class TransitionSpec(Strict):
    id: str = Field("cut", pattern=_ID)
    duration: float = Field(0.0, ge=0, le=3)
    params: dict[str, float | str] = Field(default_factory=dict)


class ColorAdjust(Strict):
    """Technical (shot-matching) correction applied per segment before the creative grade."""
    exposure: float = Field(0.0, ge=-1, le=1)
    gamma: float = Field(1.0, ge=0.5, le=2)
    temperature: float = Field(0.0, ge=-1, le=1)
    tint: float = Field(0.0, ge=-1, le=1)
    saturation: float = Field(1.0, ge=0, le=3)
    contrast: float = Field(1.0, ge=0.5, le=2)


class Segment(Strict):
    id: str = Field(pattern=_ID)
    asset_id: str
    shot_index: int = 0
    src_in: float = Field(ge=0)
    src_out: float = Field(gt=0)
    out_start: float = Field(ge=0)
    out_duration: float = Field(gt=0, le=600)
    section: str = "main"
    speed: SpeedSpec = Field(default_factory=SpeedSpec)
    motion: MotionSpec = Field(default_factory=MotionSpec)
    crop: CropSpec = Field(default_factory=CropSpec)
    effects: list[EffectInstance] = Field(default_factory=list, max_length=6)
    transition_in: TransitionSpec = Field(default_factory=TransitionSpec)
    technical: ColorAdjust = Field(default_factory=ColorAdjust)
    stabilize: bool = False
    keep_audio: bool = True
    audio_gain_db: float = Field(0.0, ge=-60, le=12)
    beat_index: int | None = None
    reason: str = Field("", max_length=300)
    image: bool = False

    @field_validator("src_out")
    @classmethod
    def _range(cls, v, info):
        src_in = info.data.get("src_in", 0)
        if v <= src_in:
            raise ValueError("src_out must be > src_in")
        return v


class TextItem(Strict):
    id: str = Field(pattern=_ID)
    kind: Literal["title", "subtitle", "lower_third", "caption", "quote", "chapter", "credits", "social", "kinetic", "end_title"] = "title"
    text: str = Field(max_length=300)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    style: str = Field("premium_title", pattern=_ID)
    animation: str = Field("fade_up", pattern=_ID)
    position: Literal["center", "lower_third", "top", "bottom", "upper_left", "lower_left", "lower_right"] = "center"
    scale: float = Field(1.0, ge=0.3, le=3)
    params: dict[str, float | str] = Field(default_factory=dict)


class CaptionSpec(Strict):
    enabled: bool = False
    style: str = Field("minimal_documentary", pattern=_ID)
    burn_in: bool = True
    words: list[dict] = Field(default_factory=list)  # [{w, t0, t1}] in output time
    source: Literal["none", "transcription"] = "none"


class ColorGrade(Strict):
    preset: str = Field("cinematic_neutral", pattern=_ID)
    intensity: float = Field(1.0, ge=0, le=1.5)
    overrides: dict[str, float] = Field(default_factory=dict)
    lut_asset_id: str | None = None
    match_shots: bool = True


class MusicSegment(Strict):
    asset_id: str
    src_in: float = Field(ge=0)
    out_start: float = Field(ge=0)
    out_end: float = Field(gt=0)
    fade_in: float = Field(0.5, ge=0, le=10)
    fade_out: float = Field(1.0, ge=0, le=15)
    gain_db: float = Field(-6.0, ge=-40, le=6)
    section: str = "main"


class SfxItem(Strict):
    kind: Literal["whoosh", "impact", "hit", "riser", "downer", "click", "pop", "sweep", "transition", "ambient", "shimmer"]
    at: float = Field(ge=0)
    gain_db: float = Field(-14.0, ge=-40, le=6)
    asset_id: str | None = None
    params: dict[str, float] = Field(default_factory=dict)


class AudioPlan(Strict):
    dialogue_preset: str = Field("dialogue_clean", pattern=_ID)
    dialogue_gain_db: float = Field(0.0, ge=-30, le=12)
    ducking: bool = True
    duck_depth_db: float = Field(12.0, ge=0, le=40)
    duck_attack: float = Field(0.15, ge=0.01, le=2)
    duck_release: float = Field(0.6, ge=0.05, le=5)
    target_lufs: float = Field(-14.0, ge=-30, le=-8)
    true_peak_db: float = Field(-1.0, ge=-6, le=0)
    keep_clip_audio: Literal["speech_only", "all", "none"] = "speech_only"


class VoiceoverItem(Strict):
    asset_id: str
    out_start: float = Field(ge=0)
    gain_db: float = Field(0.0, ge=-30, le=12)


class Ending(Strict):
    type: Literal["fade", "logo", "title", "logo_title", "cut"] = "fade"
    text: str | None = Field(None, max_length=120)
    logo_asset_id: str | None = None
    duration: float = Field(2.5, ge=0, le=15)


class ExportSpec(Strict):
    width: int = Field(1920, ge=128, le=7680)
    height: int = Field(1080, ge=128, le=4320)
    fps: float = Field(30, ge=10, le=120)
    vcodec: Literal["h264", "hevc"] = "h264"
    quality: Literal["draft", "standard", "high"] = "high"
    audio_bitrate_k: int = Field(320, ge=64, le=512)
    prefer_hw: bool = True
    preset_name: str = "1080p"

    @field_validator("width", "height")
    @classmethod
    def _even(cls, v):
        return v - (v % 2)


class StorySection(Strict):
    name: str = Field(pattern=_ID)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    energy: float = Field(0.5, ge=0, le=1)
    shot_length: float = Field(2.0, gt=0.2, le=30)


class EditPlan(Strict):
    schema_version: Literal[1] = 1
    project: dict[str, str] = Field(default_factory=dict)
    duration: float = Field(gt=0, le=1800)
    aspect_ratio: AspectRatio = "16:9"
    fps: float = Field(30, ge=10, le=120)
    mode: Mode = "fast"
    bible: CreativeBible
    story_structure: list[StorySection]
    timeline: list[Segment] = Field(min_length=1, max_length=2000)
    text: list[TextItem] = Field(default_factory=list, max_length=500)
    captions: CaptionSpec = Field(default_factory=CaptionSpec)
    effects_global: list[EffectInstance] = Field(default_factory=list, max_length=6)
    color_grade: ColorGrade = Field(default_factory=ColorGrade)
    audio: AudioPlan = Field(default_factory=AudioPlan)
    music: list[MusicSegment] = Field(default_factory=list, max_length=20)
    sfx: list[SfxItem] = Field(default_factory=list, max_length=500)
    voiceover: list[VoiceoverItem] = Field(default_factory=list, max_length=50)
    ending: Ending = Field(default_factory=Ending)
    export: ExportSpec = Field(default_factory=ExportSpec)
    reference_profile_used: bool = False
    intent: StyleIntent | None = None
    provenance: dict[str, str | bool] = Field(default_factory=dict)
    decisions: list[str] = Field(default_factory=list, max_length=600)
