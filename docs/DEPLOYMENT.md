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
* There is no authentication yet — do not expose the engine publicly without a reverse proxy that adds it.
