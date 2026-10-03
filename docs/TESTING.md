# Testing

| Suite | Command | Needs | What it proves |
|---|---|---|---|
| Engine unit + integration | `cd services/engine && python -m pytest -q` | FFmpeg | contract ↔ docs, analysis, director, revisions, retrieval, colour pipeline (incl. user LUTs), render + QC, API, auth, accounts, isolation, limits, job states / cancel / recovery, separate worker process, health, error scrubbing |
| Real media | included above (`test_real_media.py`); skipped without `data/real-media` | `python scripts/fetch_real_media.py && python scripts/make_real_variants.py` | ingest of real CC footage and derived variants (rotation, VFR, HDR, 10-bit, ProRes, corrupt, …) |
| Web unit | `npm --prefix apps/web test` | Node | components, API client |
| Web typecheck | `npm --prefix apps/web run lint` | Node | `tsc --noEmit` |
| Browser E2E (local mode) | `node apps/web/tests/e2e/ui.e2e.mjs <media>` | API + web running, Chromium | upload → generate → play/download in a real browser |
| Browser E2E (accounts) | `node apps/web/tests/e2e/auth.e2e.mjs <media>` | API with `EDITOR_AUTH=token` + web | sign-up in the UI, refresh mid-job, revision, browser download, sign-out; second user cannot list or open the first user's project |
| HTTP smoke flow | `python scripts/smoke_flow.py --api URL [--web URL] [--media DIR]` | a running stack (local, containers, deployment) | two users, upload, analyse, generate, revise, download + ffprobe, isolation, delete |
| Containers | `bash scripts/container_smoke.sh` | Docker, built images | the smoke flow against api + worker + web containers |
| Real acceptance | `python scripts/real_acceptance.py` | real media | full brief → final on 79 real inputs, 7 checks → `docs/real_acceptance_report.json` |
| Real benchmarks | `python scripts/real_benchmark.py --durations 60 300 600` | real media, time | measured preview / final / RSS → `docs/real_benchmarks.json` |

CI (`.github/workflows/ci.yml`) runs the engine suite (with the optional models when downloadable), web typecheck /
tests / build, then builds the three images and runs the container smoke test.

Rules: tests are not weakened or deleted to get green; benchmark numbers come only from runs; synthetic media is
labelled as synthetic in every report.
