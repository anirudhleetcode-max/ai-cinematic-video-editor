# AI Editing Director

The director turns a prompt (+ analysed media + optional reference + optional brand kit) into a validated `EditPlan`.
AI text never reaches FFmpeg: the only model output accepted is a `StyleIntent` object validated by Pydantic
(`extra="forbid"`, bounded numbers, whitelisted enums); everything after that is deterministic code.

## 1. Prompt understanding → `StyleIntent`

`director/prompt_parser.py` (always available, offline) extracts: duration (`60-second`, `1:30`, `2 minutes`),
platform → aspect ratio (Reel/TikTok/Shorts → 9:16, Instagram post → 4:5, YouTube → 16:9, cinema → 21:9), story
type, styles/mood, pacing, energy curve, beat sync, colour preset and relative adjustments (warmer, brighter…),
transition style, effects, slow motion, speed ramps, camera motion, stabilisation, quoted titles, captions and caption
style, music strategy (`use all three songs`, `use song 2`), ducking, dialogue, SFX, hook/intro length, ending
(logo / title / fade), reference aspects (pacing, colour, typography, transitions, motion, music), brand, shot
preferences (crowd, faces, close-ups, wide) and quality exclusions.

`director/providers.py` defines `AIProvider` with:

| Provider | Requires | Notes |
|---|---|---|
| `DeterministicFallbackProvider` | nothing | default; the parser above |
| `ClaudeProvider` | `pip install anthropic`, `ANTHROPIC_API_KEY` | official SDK, `messages.parse(output_format=StyleIntent)` structured output, model `claude-opus-5-5` (override `ANTHROPIC_MODEL`) |
| `OpenAICompatibleProvider` | `OPENAI_BASE_URL` (+ key) | any `/v1/chat/completions` server, JSON mode |
| `LocalProvider` | a local OpenAI-compatible server (Ollama, LM Studio) | free |

The AI result is **merged** onto the deterministic parse (lists unioned, scalars refined). Any provider error,
refusal or invalid output falls back to the deterministic result; plan `provenance` records which provider
actually produced the intent (`ai_used: true/false`) — the UI never claims AI where it wasn’t used.

## 2. Templates and the Creative Bible

21 JSON templates (`packages/templates/`) give defaults per genre (pacing, colour, transitions, typography,
music strategy, motion, SFX). The `CreativeBible` freezes the film’s style, colour, typography, transition and
effect philosophy, pacing, music strategy, story structure, and **budgets** (max share of non-cut boundaries,
max share of stylised segments). Every agent reads the bible, so style cannot drift mid-film.

## 3. Agents (all deterministic, `director/agents.py`)

| Agent | Responsibility |
|---|---|
| ReferenceMapper | maps a `ReferenceStyleProfile` to shot length, pacing, transition budget/style, colour target + nearest preset, camera motion, text position, beat sync |
| StoryDirector | picks a structure (event, travel, product, wedding, documentary, trailer, music, …), section lengths (explicit hook/intro lengths honoured exactly), per-section energy and shot length |
| MusicDirector | single song (best window for a build-to-peak / calm / peak arc), song chaining with crossfades (`use all songs`), section-specific songs (`song 2 for the final section`), downbeat-aligned extension instead of obvious loops; produces the output-time beat grid, drops and energy curve |
| TimelineDirector | cut points per section from target shot length × energy, snapped to beats (downbeats preferred), section ends snapped to beats |
| ClipSelector | scores every candidate shot per slot: overall score, section-specific scores, energy match, tag preferences, diversity (no reuse, no same-clip or visually-similar consecutive shots, no repeated close-ups), progressive quality relaxation only if footage runs out; slow motion on emotional sections, speed ramps on high-energy slots (budgeted) |
| TransitionDirector | cuts by default; transitions only at section changes, music drops and visually similar adjacent shots, within the bible’s budget, durations quantised to half-beats |
| MotionDesigner | subtle push-in / pull-out / pan / drift on static shots only (budgeted); Ken Burns on photos |
| Reframer | crop centre on detected faces when the output aspect differs |
| Colorist | technical shot matching (exposure, white balance, tint, saturation, contrast) to the reference look or the project median, then the creative preset + overrides |
| AudioEngineer | keeps dialogue shots (speech detected, normal speed), mutes the rest under music, ducking depth, loudness target per platform |
| SoundDesigner | restrained SFX: whoosh on transitions (≥3 s apart), riser → impact into the climax, shimmer on the end card |
| TypographyDesigner | titles only from text the user (or brand kit / project name for end titles) provided — never invented |
| QualityController (pre-render) | validates source ranges, timeline continuity, text timing |

Professional heuristics are encoded as scores and budgets: long shots in emotional sections, short shots in
high-energy ones, no consecutive similar shots, close-up repetition penalty, establishing (wide/static) shots in
openings, faces in “people” sections, restraint on transitions and effects.

## 4. Revisions (`director/revise.py`)

A revision is parsed into explicit operations, each tagged with a domain:

| Example | Operation(s) | What is recomputed |
|---|---|---|
| “Make it more energetic and reduce the intro to 3 seconds.” | `pacing`, `section_length` | structure + timeline; previous clip picks preferred |
| “Make the colors warmer.” | `color_adjust` | colour plan only (render reuses every segment) |
| “Use song 2 for the final section.” | `section_song` | music plan (+ beat re-snap of the timeline) |
| “Remove the first scene.” | `remove_segment` | ripple delete; music/text/SFX shifted |
| “Use more crowd shots.” | `prefer_tag` | clip selection with tag weight |
| “Make the text smaller.” | `text_scale` | text only |
| “Slow down the emotional section.” | `slow_section` | speeds of segments in low-energy sections |
| “Make the ending stronger.” | `stronger_ending` | ending length, end title scale, impact SFX |
| “Go back to the version before I changed the music.” | revert | copies the parent of the last music change into a new version |

Unrecognised revisions are merged into the original prompt and re-planned with previous picks preferred.
Cosmetic choices made earlier (colour, effects, titles) survive structural rebuilds.
