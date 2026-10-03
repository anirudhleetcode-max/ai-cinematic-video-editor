# Deployment

The product has two processes: the **web app** (Next.js, stateless) and the **engine** (FastAPI + worker threads +
FFmpeg, stateful: media, cache and SQLite under `EDITOR_DATA_DIR`).

## Local (free, recommended)
```bash
./scripts/setup.sh          # Linux/macOS  (Windows: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1)
npm run dev                 # API :8000, web :3000
```
No API keys are needed: the deterministic director is the default. Set `ANTHROPIC_API_KEY` (and `pip install
"services/engine[ai]"`) or `OPENAI_BASE_URL` (e.g. Ollama) to enable an AI provider; failures fall back automatically.

## Docker (optional)
```bash
docker compose up --build   # engine + web; data in the ./data volume
```
`docker/api.Dockerfile` installs FFmpeg from Debian packages. For NVIDIA encoding run the engine container with
`--gpus all` and an FFmpeg build with NVENC; the engine only uses an encoder after a successful test encode.

## Architecture for public deployment
```
Browser ──HTTPS──▶ Frontend (Next.js, stateless; Vercel or any Node host)
   │
   └──HTTPS (Bearer token)──▶ API (FastAPI)  ──▶ Job queue ──▶ Media worker(s) (FFmpeg, analysis, render)
                                   │                                  │
                                   ▼                                  ▼
                               Database (SQLite → PostgreSQL)     Storage (local disk → S3-compatible)
```
* The browser never runs or describes server-side media commands. The API accepts only typed, bounded JSON
  (Pydantic, `extra="forbid"`). Filter graphs are built server-side from registries whose parameters are clamped.
  Only the configured `ffmpeg` / `ffprobe` binaries can run, always as argument lists (never through a shell).
* Vercel is suitable for the frontend only. Workers need FFmpeg, local scratch disk and long-running processes:
  run them on a VM, a container with a persistent volume, a GPU instance, or a local machine.
* The API process and the workers are the same codebase. Today they run in one process (`EDITOR_WORKERS`
  threads). The `JobQueue` and `Storage` interfaces are where a Redis queue and S3 storage plug in; those backends
  are not implemented yet.

## Security (required before exposing the API)
| Control | Setting | Default |
|---|---|---|
| Authentication | `EDITOR_AUTH=token`; tokens from `python -m editor.auth create-user NAME [--admin]` (shown once, stored as SHA-256) | `token` whenever `EDITOR_ENV` ≠ `development`; the server **refuses to start** with `EDITOR_AUTH=none` outside development |
| Project ownership | every project, asset, version, render and job is owned; one guard checks every path parameter on every route; other users' objects answer **404** | always on |
| Rate limits (per user, per minute) | `EDITOR_RATE_LIMIT_PER_MIN`, `EDITOR_UPLOAD_RATE_PER_MIN`, `EDITOR_JOB_RATE_PER_MIN` | 240 / 120 / 20 |
| Job limits | `EDITOR_MAX_JOBS_PER_USER` active (queued + running) jobs | 3 |
| Project limits | `EDITOR_MAX_PROJECTS_PER_USER` | 50 |
| Upload limits | `EDITOR_MAX_UPLOAD_MB` per file; `EDITOR_USER_QUOTA_GB` per user | 4096 MB / 50 GB |
| File validation | extension whitelist; FFprobe and decode-window check (corrupt files rejected with a reason); `.cube` LUTs parsed and checked before FFmpeg reads them; sanitised filenames; storage paths confined to the data directory | always on |
| Process timeouts | `EDITOR_PROCESS_TIMEOUT` on every FFmpeg / FFprobe run, plus a watchdog on progress-reporting encodes | 7200 s |
| Cleanup | `EDITOR_RETENTION_DAYS`: old renders (except each project's newest final), caches and abandoned upload parts are removed every 6 h; `POST /admin/cleanup?dry_run=true` previews it | 30 days |
| Admin-only | `/diagnostics` (outside development), `/admin/cleanup` | — |

Media and event URLs (`<video>`, `<img>`, downloads, Server-Sent Events) cannot send headers. They accept
`?access_token=` on **GET only**, which means the token can appear in access logs. Put the API behind HTTPS, keep
logs private, and rotate tokens: disable a user with `python -m editor.auth disable-user ID`.

Not implemented yet: OAuth/SSO, short-lived signed media URLs, per-user storage directories (isolation is enforced
by ownership checks and path confinement), and multi-machine rate limiting (limits are per API process).

## Hosted
* **Frontend**: any Node host or Vercel (`apps/web`, `output: "standalone"`). Set `NEXT_PUBLIC_API_URL` to the engine URL.
* **Engine/workers must not run on Vercel/serverless**: renders take minutes, need FFmpeg, local disk and long-lived
  processes. Run them on a VM, a container service with persistent disk, a GPU instance, or a local machine exposed
  through a tunnel. Set `EDITOR_CORS_ORIGINS` to the web origin and `EDITOR_ENV=production` (hides `/diagnostics`).
* **Scaling**: `EDITOR_WORKERS` controls concurrent jobs per process. The `JobQueue` and `Storage` interfaces are the
  seams for Redis/RQ and S3-compatible storage; these backends are not implemented yet.

## Security checklist
* FFmpeg is invoked only through `editor.proc.run` with argument arrays (no shell); only the configured ffmpeg/ffprobe
  binaries can be executed.
* Uploads: extension whitelist, `EDITOR_MAX_UPLOAD_MB`, sanitised filenames, paths confined to the data directory.
