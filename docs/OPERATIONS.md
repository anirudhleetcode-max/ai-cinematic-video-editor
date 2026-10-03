# Operations

* **Users**: people register in the web app (`EDITOR_ALLOW_REGISTRATION=1`) or an admin creates them:
  `python -m editor.auth create-user NAME [--admin]` (prints an API token once). `list-users`, `disable-user ID`
  (also revokes that user's sessions). In compose: `docker compose exec api python -m editor.auth …`.
* **Backups**: everything is in the data volume — `editor.sqlite3` (back it up with `sqlite3 editor.sqlite3
  ".backup backup.sqlite3"` while running) and `projects/` (media, renders). `cache/` can be regenerated.
* **Logs**: one JSON object per line on stderr (`ts, level, logger, msg, job_id, project_id, …`). A failed job's
  traceback is logged with `error_id` = the job id the user sees; an unexpected API error is logged with the
  `err_…` id returned to the client. Passwords, tokens and API keys are never logged.
* **Jobs**: `GET /diagnostics` (admin) lists active and failed jobs. A worker that dies mid-job has the job re-queued
  after 90 s (max `EDITOR_JOB_MAX_ATTEMPTS`). Cancel: `POST /jobs/{id}/cancel` or the Cancel button.
* **Cleanup**: the worker removes renders older than `EDITOR_RETENTION_DAYS` (keeping each project's newest final),
  stale caches and abandoned uploads every 6 h; `POST /admin/cleanup?dry_run=true` previews. Deleting a project
  cancels its jobs and removes its files.
* **Health**: `/health` (503 with the failing component), `/health/live`; container healthchecks are built in.
* **Upgrades**: database migrations are additive and run at start-up (`editor/db.py::_migrate`). Analysis results
  are cached by analyser version; a new version re-analyses on next use.
* **Disk**: renders and caches grow with use; `/health` turns unhealthy below 2 GB free.
