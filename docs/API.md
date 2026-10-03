# HTTP API

Base URL: `http://localhost:8000` (FastAPI; interactive schema at `/docs`). All long-running work returns a job
(`{"job_id": …}`); follow it with `GET /jobs/{id}` or the Server-Sent Events stream `GET /jobs/{id}/events`.
Errors: `400`/`422` validation, `403` diagnostics outside development, `404` unknown id, `413` file too large.

## Health & system
| Method | Path | Notes |
|---|---|---|
| GET | `/health` | component health (database, storage, worker, queue, FFmpeg, models); 503 if unhealthy |
| GET | `/health/live` | liveness |
| GET | `/auth/config` | `{auth, registration}` |
| POST | `/auth/register` | `{email, password, name?}` → `{token, expires, user}` |
| POST | `/auth/login` | `{email, password}` → `{token, expires, user}` (401 on bad credentials) |
| POST | `/auth/logout` | revokes the session token |
| GET | `/auth/me` | current user |
| GET | `/projects/{pid}/search?q=` | find analysed shots by description (label match; see `editor/retrieval.py`) |
| POST | `/jobs/{id}/cancel` | cancel a queued or running job |
| GET | `/diagnostics` | FFmpeg filters/encoders (verified by test encode), GPU, CPU/RAM, disk — development mode only |
| GET | `/benchmarks` | stored benchmark runs (`scripts/benchmark.py`) |
| GET | `/export-history` | every completed render with timings |

## Library
| GET | `/effects` `/transitions` `/text-animations` `/text-styles` `/color-presets` `/audio-presets` `/motion-presets` `/templates` | definitions with typed, bounded parameters |
|---|---|---|
| GET | `/library/search?q=&kind=` | kind-aware keyword search (“zoom transition”) |
| GET | `/library/stats` | definition and parameter-combination counts |
| GET | `/library/preview/{kind}/{id}` | rendered PNG preview (cached) |

## Projects & assets
| Method | Path | Body / notes |
|---|---|---|
| POST | `/projects` | `{"name": "...", "settings": {}}` |
| GET | `/projects` · `/projects/{pid}` | detail includes assets, versions, renders |
| PATCH | `/projects/{pid}` | `{"brand_kit_id"?, "mode"?: "fast"\|"quality"\|"emergency"}` |
| DELETE | `/projects/{pid}` | removes files and rows |
| POST | `/projects/{pid}/assets` | multipart `files[]`, optional `role` (`clip`, `broll`, `music`, `reference`, `logo`, `sfx`, `voiceover`, `lut`; inferred from type if omitted). Extension whitelist, size cap, sanitised names |
| POST | `/projects/{pid}/uploads` | resumable: `{"filename","size","role"}` → `upload_id` |
| PUT | `/projects/{pid}/uploads/{uid}?offset=N` | raw chunk bytes; offset must equal bytes received |
| GET | `/projects/{pid}/uploads/{uid}` | bytes received (resume point) |
| POST | `/projects/{pid}/uploads/{uid}/complete` | finalises into an asset |
| GET | `/projects/{pid}/assets` · PATCH/DELETE `/assets/{aid}` | list, change role/order, remove |
| GET | `/assets/{aid}/thumbnail` · `/assets/{aid}/file` | JPEG thumbnail; media (HTTP range supported) |
| POST | `/projects/{pid}/analyze` | `{"mode"?, "force"?}` → job: analyse all assets (cached by fingerprint) |
| POST | `/projects/{pid}/reference` | multipart reference video (shortcut for role=reference) |

## Planning, rendering, revisions
| Method | Path | Body |
|---|---|---|
| POST | `/projects/{pid}/edit-plan` | `{"prompt": "...", "mode"?}` → job producing a version |
| POST | `/projects/{pid}/generate` | `{"prompt", "preview_first": true}` → analyse → plan → preview → final render → QC |
| POST | `/projects/{pid}/preview` | `{"version_id"?}` → 640 px draft render |
| POST | `/projects/{pid}/render` | `{"version_id"?, "export"?: {width,height,fps,vcodec,quality,audio_bitrate_k,prefer_hw,preset_name}}` (unknown fields rejected) |
| POST | `/projects/{pid}/revise` | `{"text": "Make the colors warmer.", "render": true, "preview": false}`; texts starting with “go back/revert/undo” revert immediately |
| POST | `/projects/{pid}/revert` | `{"query": "before I changed the music"}` or `{"version_id"}` |
| GET | `/projects/{pid}/versions` · `/versions/{vid}` | plan JSON + render-time estimate from measured history |
| GET | `/versions/{vid}/inspector` | per-segment explanation (why each shot/transition/grade) |
| GET | `/projects/{pid}/render-status` | recent jobs and the stage list |
| GET | `/projects/{pid}/renders` · `/renders/{rid}/download` · `/renders/{rid}/report` | MP4 + QC/timing report |

## Jobs
`GET /jobs/{id}` → `{status: queued|running|done|failed|cancelled, state, stage, progress (0–1), elapsed_s, result, error, error_id}`.
`state` is the product job state: queued · analyzing · planning · previewing · rendering · validating · completed ·
failed · cancelled. `error` is a one-line message without server paths or tracebacks; `error_id` is the reference
to give an operator (the full traceback is in the server log under that id).
`GET /jobs/{id}/events` emits `data: {...}` on every change and closes when the job ends. Progress values come from
real work units (assets analysed, segments rendered, FFmpeg `out_time`), never timers.

## Brand kits
`POST /brand-kits` `{"name", "data": {colors, fonts, logo…}}` · `GET /brand-kits`.

## Example
```bash
P=$(curl -s -XPOST localhost:8000/projects -H 'content-type: application/json' -d '{"name":"Demo"}' | jq -r .id)
curl -s -XPOST localhost:8000/projects/$P/assets -F files=@clip1.mp4 -F files=@song.mp3
J=$(curl -s -XPOST localhost:8000/projects/$P/generate -H 'content-type: application/json' \
  -d '{"prompt":"30 second energetic highlight, cut to the beat"}' | jq -r .job_id)
curl -N localhost:8000/jobs/$J/events
```
