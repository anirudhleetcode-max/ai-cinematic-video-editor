# Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `/health` says FFmpeg not found | Install FFmpeg ≥ 4.3 or set `FFMPEG_BIN`/`FFPROBE_BIN` to full paths (Windows: `C:\ffmpeg\bin\ffmpeg.exe`). |
| Titles/captions missing, QC warns about text | FFmpeg was built without libass (`ffmpeg -filters | grep ass`). Use a full build (e.g. gyan.dev on Windows). |
| Captions skipped | The offline STT model is not installed: `python scripts/download_stt_model.py`, then set `EDITOR_STT_MODEL_DIR`. |
| Render uses libx264 although a GPU exists | The hardware encoder failed its test encode (driver/FFmpeg build). See `/diagnostics` → `encoders`. |
| Video does not play in the browser preview but downloads fine | Chromium builds without proprietary codecs cannot decode H.264. Use Chrome/Edge/Safari/Firefox, or open the download. |
| Upload of a very large file fails | Raise `EDITOR_MAX_UPLOAD_MB`. Files above 64 MB use resumable chunked upload and can be retried. |
| “not enough usable footage” / repeated shots | Too little footage for the requested duration after quality filtering; the plan’s `decisions` explain which relaxations were applied. Add clips or shorten the duration. |
| Renders slow | Use Fast or Emergency mode, check `/benchmarks` for this machine’s measured speed, close other heavy processes. Quality-mode slow motion (`minterpolate`) is CPU-intensive. |
| Next.js “Module not found: @/…” | Use the pinned TypeScript 5 (`npm install` in `apps/web`), not a global TypeScript 7. |
| Port already in use | `API_PORT` (with `npm run dev`) or `--port` for the API, `PORT` for Next; update `NEXT_PUBLIC_API_URL`. |
| Interrupted job after a restart | Jobs are persisted; interrupted ones are re-queued on start. |
| Logs | The engine logs JSON lines to stdout; every render report (`/renders/{id}/report`) lists stages, timings, fallbacks and QC results. |
