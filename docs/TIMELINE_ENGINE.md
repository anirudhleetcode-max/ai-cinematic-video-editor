# Timeline engine & EditPlan

`editor/schemas.py` defines the contract between planning and rendering. Key types:

```text
EditPlan
  duration, aspect_ratio, fps, mode, bible: CreativeBible, story_structure: [StorySection]
  timeline: [Segment]                       # the clip selection, order and ranges
  text: [TextItem]   captions: CaptionSpec
  color_grade: ColorGrade (preset, intensity, overrides, optional LUT asset, match_shots)
  effects_global: [EffectInstance]
  audio: AudioPlan (dialogue preset, ducking depth/attack/release, LUFS target, true peak)
  music: [MusicSegment]  sfx: [SfxItem]  voiceover: [VoiceoverItem]
  ending: Ending (fade | logo | title | logo_title | cut)  export: ExportSpec
  intent: StyleIntent  provenance  decisions: [str]

Segment
  asset_id, shot_index, src_in, src_out, out_start, out_duration, section
  speed: SpeedSpec (rate | ramp [(pos, rate)…] | freeze_end | interpolate)
  motion: MotionSpec   crop: CropSpec (cx, cy, zoom)   effects: [EffectInstance]
  transition_in: TransitionSpec   technical: ColorAdjust   stabilize   keep_audio   audio_gain_db
```

## Timing model

* Output time is continuous: segment *k* starts where *k−1* ends, **minus** the overlap of segment *k*’s incoming
  transition. `apply_overlaps` extends both neighbours by half the transition so the cut point chosen on the beat
  is the *middle* of the transition and the total duration is unchanged. If a clip has no spare frames, the shot
  slides within its clip; if that is impossible the transition is shortened or becomes a cut.
* Source length = `out_duration × rate` (constant speed) or ∫ rate(u) du × out_duration (ramp).
* Validation (`planner.validate`) rejects: missing assets, source ranges beyond the clip, gaps/overlaps, timeline end
  ≠ `duration − ending.duration`, invalid text timing.

## Beat synchronisation

Music beats are mapped to output time per `MusicSegment` (`t_out = t_src − src_in + out_start`, inside fade-safe
bounds). Each cut targets `n = round(L / beat_interval)` beats from the previous cut and snaps to the nearest beat,
preferring downbeats; section boundaries snap to beats too (except lengths the user specified explicitly). The
test suite asserts ≥ 85 % of cuts land within 60 ms of a beat on beat-synced plans.

## Versions

Every plan is stored as a version (`generate` / `revision` / `revert`) with `parent_id` and change domains, so
history is linear and any version can be restored (restoring creates a new version rather than rewriting history).
