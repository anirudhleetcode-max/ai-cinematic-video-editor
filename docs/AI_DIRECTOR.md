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
| TimelineDirector | cut points from the **pacing engine** (`director/pacing.py`). Role ranges: hook 0.5–2.5 s, opening 2–5, build 1–4, emotional 2–6, climax 0.3–2, resolution 2–5; adjusted by energy, BPM (1/2/4/8-beat lengths), the reference's measured median, prompt pacing and shot type. Cuts land on beats and downbeats, but a deterministic minority are deliberately **before** the beat (hook/climax anticipation) or **after** it (relaxed emotional cuts); every slot records its beat relation |
| ClipSelector | **sequence construction**: slots are filled in narrative priority (hook → climax → opening → emotional → build → resolution), so the strongest material is reserved for those moments. Each choice is scored against the shots already placed on **both** sides (±3): same clip, same camera set-up (`angle_group`), visually similar frames, repeated close-ups, opposite pans. Subject continuity inside a section is rewarded, as are section-specific subjects from the ShotSemanticProfile (people, crowds, products, screens, outdoor). Imperfect shots are penalised by their edit score, not excluded. Only black / frozen / too-short / obstructed / duplicate shots are held back, and only until footage runs out (progressive relaxation, reported). Speech shots are not chopped below 2 s |
| TransitionDirector | **CUT is first-class and the default.** A boundary gets a transition only with a reason (section change, music drop, unavoidable similar framing), within the budget (style × EffectDensity, or the reference's measured frequency), and only if a palette transition fits: energy inside its range, duration inside its range, and movement requirements met (pushes, slides and whips need lateral motion) |
| EffectsDesigner | restrained accents: at most `effect_budget` of segments (**EffectDensity** minimal / low / medium / high / extreme; default low, or medium for energetic styles), only on music drops or downbeats in high-energy sections, chosen by each effect's metadata (style, recommended energy, pacing, intensity). Effects the user names always qualify |
| MotionDesigner | subtle push-in / pull-out / pan / drift on static shots only (budgeted); Ken Burns on photos |
| Reframer | crop centre on detected faces when the output aspect differs |
| Colorist | closed-loop technical match on each shot's colour thumbnail, plus neighbour smoothing; the reference's measured look mapped to grade overrides (see docs/COLOR.md) |
| AudioEngineer | dialogue / ambience / muted roles from VAD speech regions, speech regions in output time for ducking, de-clipping (see docs/AUDIO.md) |
| SoundDesigner | restrained SFX: whoosh on transitions (≥3 s apart), riser → impact into the climax, shimmer on the end card |
| TypographyDesigner | titles only from text the user (or brand kit / project name for end titles) provided — never invented |
| QualityController (pre-render) | `repair()` then `validate()` on every plan (deterministic, AI or revised). **Repaired:** unknown effects, transitions or motion presets → removed / cut / none; source ranges slid inside the clip; unknown text styles or animations → defaults; text clamped to the film; missing music / SFX / voice-over / LUT / logo references dropped; odd export dimensions → even. **Rejected:** missing assets, non-positive durations, ranges beyond the clip, gaps or overlaps, timeline end ≠ body end, invalid text timing, unknown styles or fonts, invalid audio references, odd resolutions |

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
| “Change the ending.” / “End with a title card.” | `ending` | **only the ending** (end card + end title) when its length is unchanged; a hard-cut ending re-times the body |
| “Make the intro shorter.” | `section_length_rel` | intro ×0.6 (longer ×1.4), structure rebuilt with previous picks |
| “Less effects.” / “No effects.” / “More effects.” | `effect_density` | fewer/no effects are removed in place (nothing re-planned); more effects re-plans at the next density |
| “Use more crowd shots.” / “Use more people.” | `prefer_tag` | clip selection with tag weight |
| “Make the text smaller.” | `text_scale` | text only |
| “Slow down the emotional section.” | `slow_section` | speeds of segments in low-energy sections |
| “Make the ending stronger.” | `stronger_ending` | ending length, end title scale, impact SFX |
| “Go back to the version before I changed the music.” | revert | copies the parent of the last music change into a new version |

“Make it more energetic” changes pacing ×0.72 **and** raises EffectDensity one step and enables beat sync. Structural
rebuilds prefer previous picks: a strong bonus for the same slot, and a smaller one for any shot the previous
version used. Positions move when the structure changes, so retention is measured as the share of previous shots
still in the edit.

Unrecognised revisions are merged into the original prompt and re-planned with previous picks preferred.
Cosmetic choices made earlier (colour, effects, titles) survive structural rebuilds.
