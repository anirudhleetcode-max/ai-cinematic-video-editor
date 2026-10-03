# Cutroom — Autonomous AI Video Editor

**Upload → Prompt → Generate → Download.** Drop raw clips, songs, an optional logo and an optional reference video, describe the film you want in plain language, and Cutroom:

1. **analyses** every file (shot boundaries, sharpness, exposure, camera shake, motion, faces/people, speech, silence, duplicates, composition, colour) and every song (BPM, beats, downbeats, sections, drops, energy),
2. **learns the style** of a reference video (pacing, shot-length distribution, transition frequency, colour statistics, camera motion, text placement, music energy) — without ever reusing its footage,
3. **plans the edit** with an AI Editing Director (story structure, clip selection, beat-synced timeline, transitions with restraint, camera motion, colour, audio, typography, ending) into a strict, validated `EditPlan`,
4. **renders** it with a real FFmpeg/OpenCV/numpy media engine (cuts, 71 transitions, speed changes and ramps, reframing, camera moves, shot matching + LUT-based grading, effects, animated typography, ducked/normalised audio mix) to MP4,
5. **checks** the result (FFprobe + black/freeze/silence/clipping detectors, safe areas) and auto-fixes what it can,
6. lets you **revise** in plain language (“make it warmer”, “intro 3 seconds”, “use song 2 for the final section”) — patching the existing plan and re-rendering only what changed.

Everything is free/open-source and runs locally. An LLM is **optional**: the deterministic director works offline; Claude or any OpenAI-compatible model (including a local one) can refine prompt interpretation when configured.

> Status: tested end-to-end on synthetic media **and on real footage**: real camera clips, real music and real
> speech, plus format variants derived from them (4K, HLG, rotated phone MOV, VFR, anamorphic, 24–120 fps, corrupt
> files). See [docs/REAL_FOOTAGE_HARDENING.md](docs/REAL_FOOTAGE_HARDENING.md) for what real footage broke and how
> it was fixed, [docs/BENCHMARKS.md](docs/BENCHMARKS.md) for measured timings, and the limitations sections for
> what is not covered.

### Optional local models (free, offline)
```bash
python scripts/download_models.py   # YuNet faces + NanoDet COCO-80 objects (OpenCV DNN), Silero VAD (onnxruntime)
```
Without them the engine falls back to classic OpenCV face/person detection and a DSP speech detector, and every
analysis records which detector produced it.

### Real-footage testing
```bash
python scripts/fetch_real_media.py --all && python scripts/make_real_variants.py   # real CC-licensed media (not committed)
python scripts/real_media_report.py                  # inspect everything under tests/real_media/
python scripts/real_acceptance.py --assemble         # 70+ real clips, 3 real songs, reference → report
python scripts/real_benchmark.py --durations 60 300 600
```
To test your own event, put its media in `tests/real_media/event01/` (`clips/ music/ reference/ logo/`, or one
flat folder) and run `python scripts/real_acceptance.py`. Source files are never modified.

## Quick start

Requirements: **Python 3.10+**, **Node.js 20+**, **FFmpeg 6+ with libass and xfade** (`ffmpeg -filters | grep -E " ass | xfade "`).

```bash
# Linux / macOS
./scripts/setup.sh
npm run dev            # API → http://localhost:8000   Web → http://localhost:3000

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
npm run dev
```

Manual setup (any OS):

```bash
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e "services/engine[dev]"               # add [ai] for Claude, [transcribe] for captions
(cd apps/web && npm install)
cp .env.example .env
npm run dev
```

Try it without your own footage: `npm run demo-media` writes a clearly-labelled **DEMO** dataset of synthetic clips (with deliberate blur/dark/shaky/duplicate shots), songs with known BPM and a reference video to `data/demo-media/`.

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | API (uvicorn, reload) + web app (Next.js dev) |
| `npm run build` / `npm run start:api` / `npm run start:web` | production build / servers |
| `npm test` | backend pytest suite + frontend Vitest suite |
| `npm run test:e2e` | browser end-to-end: create → upload → generate → MP4 (needs both servers + demo media) |
| `npm run acceptance` | spec acceptance test: 50 clips, 3 songs, reference, 3 revisions → `docs/acceptance_report.json` |
| `npm run benchmark -- --sizes 10 25 50 100 200` | real measurements stored in the DB and `docs/benchmarks.json` |
| `npm run health` | engine health (FFmpeg, encoder) |
| `python scripts/download_stt_model.py` | optional free offline speech-to-text model for automatic captions |

## Repository layout

```
apps/web/                 Next.js 15 + TypeScript (strict) + Tailwind + Zustand + Framer Motion
services/engine/editor/   Python engine + FastAPI
  api.py  service.py  jobs.py            HTTP API, application services, job queue (SQLite-backed)
  media/  music/  reference/             media intelligence, music intelligence, reference style profile
  director/                              prompt parser, AI providers, planning agents, revision engine
  registry/                              effect / transition / text / colour / audio / motion registries
  render/  qc/                           segment renderer, colour space, transitions, audio mix, typography (ASS), QC + reviews
  vision.py  auth.py  cleanup.py         vision providers, authentication/limits, retention
packages/fonts/           OFL fonts (Inter, Montserrat, Playfair Display, Bebas Neue)
packages/templates/       21 JSON editing templates
scripts/                  setup (sh/ps1), dev runner, benchmarks, acceptance tests (synthetic + real footage), media fetch, models
docker/ docker-compose.yml  optional containers
docs/                     architecture and subsystem documentation
examples/pitch-film/      an earlier hand-directed Remotion edit (kept for reference)
```

## Documentation

[ARCHITECTURE](docs/ARCHITECTURE.md) · [REAL_FOOTAGE_HARDENING](docs/REAL_FOOTAGE_HARDENING.md) · [API](docs/API.md) · [AI_DIRECTOR](docs/AI_DIRECTOR.md) · [TIMELINE_ENGINE](docs/TIMELINE_ENGINE.md) · [EFFECT_ENGINE](docs/EFFECT_ENGINE.md) · [RENDERING](docs/RENDERING.md) · [COLOR](docs/COLOR.md) · [AUDIO](docs/AUDIO.md) · [REFERENCE_ANALYSIS](docs/REFERENCE_ANALYSIS.md) · [BENCHMARKS](docs/BENCHMARKS.md) · [DEPLOYMENT](docs/DEPLOYMENT.md) (security) · [TROUBLESHOOTING](docs/TROUBLESHOOTING.md)

Before exposing the API to the internet, read the security section of [DEPLOYMENT](docs/DEPLOYMENT.md): set
`EDITOR_ENV=production`, which makes token authentication mandatory, and create users with
`python -m editor.auth create-user NAME`.
