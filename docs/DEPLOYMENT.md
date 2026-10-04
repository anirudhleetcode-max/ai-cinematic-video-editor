# Deployment

Three processes, one codebase:

| Process | What | State | Image |
|---|---|---|---|
| **web** | Next.js app (standalone server) | none (only `NEXT_PUBLIC_API_URL`, compiled in) | `docker/web.Dockerfile` |
| **api** | FastAPI, `EDITOR_ROLE=api`: auth, uploads, plans, job submission, SSE progress, downloads | database + data volume | `docker/engine.Dockerfile --target api` |
| **worker** | `python -m editor.worker`, `EDITOR_ROLE=worker`: analysis, rendering, QC, cleanup | database + data volume | `docker/engine.Dockerfile --target worker` |

```
Browser ──HTTPS──▶ web (Next.js)
   └──HTTPS, Bearer session/API token──▶ api ──enqueue──▶ jobs table (SQLite, WAL) ◀──claim── worker(s)
                                          │                                                  │
                                          └──────── shared data volume (media, renders, cache) ┘
```

* **Queue**: jobs live in the database. A worker claims a job with an atomic `UPDATE … WHERE status='queued'`,
  heartbeats it every 10 s, and writes progress to the row (the API streams it over SSE). If a worker dies, any live
  worker re-queues the job once its heartbeat is 90 s old, up to `EDITOR_JOB_MAX_ATTEMPTS` (default 2), then marks it
  failed. Cancellation is a database flag, so `POST /jobs/{id}/cancel` on the API stops a job running in a worker.
  Jobs survive browser disconnects: closing the tab changes nothing on the server.
* **Database and storage — current limits.** SQLite on a volume shared by api and worker. That works on **one
  host** (docker compose, one VM). Several hosts need a network filesystem for the data volume and PostgreSQL for the
  database; the code is written for that (repository layer in `editor/db.py`, `Storage` interface in
  `editor/storage.py`) but **PostgreSQL and S3 backends are not implemented**. Media is local disk.
* **Local single process**: `EDITOR_ROLE=all` (default) runs API and worker threads in one process (`npm run dev`).

## Local (free, recommended for one user)
```bash
./scripts/setup.sh          # Linux/macOS  (Windows: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1)
npm run dev                 # API :8000 (with workers), web :3000; EDITOR_AUTH=none, single local user
```

## Docker compose (one host, production settings)
```bash
cp .env.example .env        # edit EDITOR_CORS_ORIGINS / NEXT_PUBLIC_API_URL for your domain
docker compose up --build -d
open http://localhost:3000  # create an account in the sign-in dialog
bash scripts/container_smoke.sh   # end-to-end check: two users, upload, generate, revise, download, isolation
```
Images use `mirror.gcr.io/library/{python,node}` base images (override with `--build-arg BASE=…`), run as non-root
users, and include FFmpeg from Debian (libx264/x265, zscale, vidstab, libass) and — when the build can download them —
the optional ONNX models (YuNet, NanoDet-Plus, Silero VAD). `/health` reports whether the models are present.

**Where this was validated:** the clean no-cache builds and the compose stack with real media are exercised by the
manual GitHub workflow `.github/workflows/release-validation.yml` (smoke flow, worker kill / cancel / restart, two-account
browser E2E). The development container used for this release cannot build the engine image itself: its network
policy blocks `deb.debian.org` (HTTP 403), so `apt-get install ffmpeg` fails there; the production-config stack was
additionally run there as separate API and worker processes without Docker.

For NVIDIA encoding run the worker with `--gpus all` (compose: uncomment `deploy:`); the engine only uses a hardware
encoder after a successful test encode (`GET /diagnostics` → `verified_hardware_encoders`). Detecting a GPU is not
the same as using one.

## Hosted
* **Frontend**: any Node host or Vercel (`apps/web`). Set `NEXT_PUBLIC_API_URL` at build time. No secrets.
* **API + worker must not run on Vercel / serverless**: renders take minutes and need FFmpeg, disk and long-lived
  processes. Use a VM or a container host with a persistent volume (e.g. Fly.io machine + volume, Render / Railway
  service + disk, any VPS with docker compose). Put HTTPS in front of the API (a reverse proxy or the platform's).
* Required production settings: `EDITOR_ENV=production`, `EDITOR_AUTH=token`, `EDITOR_CORS_ORIGINS=https://<web origin>`.

## Start-up refusals (`EDITOR_ENV` ≠ development)
The API and the worker refuse to start when: `EDITOR_AUTH` is not `token`; `EDITOR_CORS_ORIGINS` contains `*` or a
non-localhost `http://` origin; rate limits are disabled; `EDITOR_SESSION_DAYS` is outside 0–90; the data directory
contains an apostrophe. In production the API does not add the localhost development origins to CORS.

## Health checks
| Endpoint | Public | Checks |
|---|---|---|
| `GET /health/live` | yes | the API process answers (container liveness) |
| `GET /health` | yes | database query, storage writable + free space (> 2 GB), worker (in-process threads, or the separate worker's heartbeat file < 30 s old), queue depth, FFmpeg/FFprobe + selected encoder, model files present. **503** when any required component fails. No paths or secrets in the body |
| worker container | — | `/data/.worker-heartbeat` younger than 30 s |
| web container | — | `GET /` answers |
| `GET /diagnostics` | admin | data dir, failed jobs, cache stats, recent render timings |

## Security
| Control | Setting | Default |
|---|---|---|
| Accounts | `POST /auth/register` (email + password ≥ 10 chars; `EDITOR_ALLOW_REGISTRATION`), `POST /auth/login` → session token, `POST /auth/logout`. Passwords: scrypt (N=2¹⁴, r=8, p=1, 16-byte salt). Sessions expire after `EDITOR_SESSION_DAYS` | registration on, 14 days |
| API tokens | `python -m editor.auth create-user NAME [--admin]` (for scripts; shown once) | — |
| Token storage | session and API tokens stored only as SHA-256; passwords only as scrypt hashes | always |
| Brute force | `EDITOR_LOGIN_RATE_PER_MIN` per client IP on `/auth/*`; equal-time response for unknown emails | 10 |
| Ownership | every project, asset, version, render and job is owned; one guard checks every path parameter on every route; others' objects answer **404** | always |
| Rate / job / project limits | `EDITOR_RATE_LIMIT_PER_MIN`, `EDITOR_UPLOAD_RATE_PER_MIN`, `EDITOR_JOB_RATE_PER_MIN`, `EDITOR_MAX_JOBS_PER_USER`, `EDITOR_MAX_PROJECTS_PER_USER` | 240 / 120 / 20 / 3 / 50 |
| Upload limits | `EDITOR_MAX_UPLOAD_MB` per file; `EDITOR_USER_QUOTA_GB` per user; sources ≤ 3 h | 4096 MB / 50 GB |
| File validation | extension whitelist; FFprobe + decode-window check; `.cube` parsed before FFmpeg reads it; sanitised filenames; paths confined to the data directory | always |
| Error responses | job errors scrubbed of absolute paths and tracebacks; unexpected exceptions return `{"detail": "internal error", "error_id"}` and are logged in full server-side; job results never include server paths | always |
| Processes | FFmpeg / FFprobe only, as argument arrays (never a shell), `EDITOR_PROCESS_TIMEOUT` + progress watchdog | 7200 s |
| Cleanup | `EDITOR_RETENTION_DAYS`: old renders (except each project's newest final), caches, abandoned uploads; every 6 h in the worker | 30 days |
| Logs | structured JSON; no passwords, tokens or API keys are logged | — |

Media and event URLs (`<video>`, `<img>`, downloads, SSE) cannot send headers, so they accept `?access_token=` on
**GET only**; the token can then appear in proxy access logs. Keep logs private. Sign-out revokes the session.

Not implemented: OAuth/SSO, email verification and password reset (an admin can disable a user:
`python -m editor.auth disable-user ID`), short-lived signed media URLs, multi-machine rate limiting (limits are per
API process), PostgreSQL / S3 backends.
