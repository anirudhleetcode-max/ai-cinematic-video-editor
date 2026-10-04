"""Retention / cleanup policy (EDITOR_RETENTION_DAYS, default 30).

* renders older than the retention period are deleted (file + row) — except each project's newest final render
* render caches (segment / transition / mix caches, per-render work dirs) untouched for the retention period are deleted
  (they are rebuilt on demand — caches are an optimisation, never the only copy of anything)
* abandoned resumable-upload parts older than 24 h are deleted
Source media and edit plans are never deleted by this policy (only by deleting the asset / project).
"""
from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

from . import db
from .config import get_settings
from .logging import get_logger, log

logger = get_logger("cleanup")


def _age_days(p: Path) -> float:
    try:
        newest = max([p.stat().st_mtime] + [c.stat().st_mtime for c in p.rglob("*")] if p.is_dir() else [p.stat().st_mtime])
    except (OSError, ValueError):
        return 0.0
    return (time.time() - newest) / 86400


def run_cleanup(retention_days: int | None = None, dry_run: bool = False) -> dict:
    st = get_settings()
    days = st.retention_days if retention_days is None else retention_days
    stats = {"renders_deleted": 0, "cache_dirs_deleted": 0, "upload_parts_deleted": 0, "orphan_outputs_deleted": 0, "bytes_freed": 0, "retention_days": days, "dry_run": dry_run}
    if days <= 0:
        return stats
    cutoff = time.time() - days * 86400
    keep = {r["id"] for r in db.query(
        "SELECT r.id FROM renders r WHERE r.kind='final' AND r.created = (SELECT MAX(created) FROM renders r2 WHERE r2.project_id=r.project_id AND r2.kind='final')")}
    for r in db.query("SELECT id, path, created FROM renders WHERE created < ?", (cutoff,)):
        if r["id"] in keep:
            continue
        p = Path(r["path"] or "")
        size = p.stat().st_size if p.exists() else 0
        if not dry_run:
            p.unlink(missing_ok=True)
            db.execute("DELETE FROM renders WHERE id=?", (r["id"],))
        stats["renders_deleted"] += 1
        stats["bytes_freed"] += size
    for proj in st.projects_dir.glob("*"):
        work = proj / "work"
        for d in [*(work.glob("segment_cache/*")), *(work.glob("mix_cache/*")), *(work.glob("rnd_*"))]:
            if _age_days(d) > days:  # cached segment dirs, cached transition clips (tr_*.mp4), mixes, old work dirs
                size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.is_dir() else d.stat().st_size
                if not dry_run:
                    shutil.rmtree(d, ignore_errors=True) if d.is_dir() else d.unlink(missing_ok=True)
                stats["cache_dirs_deleted"] += 1
                stats["bytes_freed"] += size
        # outputs no render row points to: partial files of a worker that was killed mid-render (a cancelled or failed
        # render removes its own); an hour of grace so a render still being written is never touched
        known = {r["path"] for r in db.query("SELECT path FROM renders WHERE project_id=?", (proj.name,))}
        for f in proj.glob("outputs/*.mp4"):
            if str(f) not in known and _age_days(f) > 1 / 24:
                size = f.stat().st_size
                if not dry_run:
                    f.unlink(missing_ok=True)
                stats["orphan_outputs_deleted"] += 1
                stats["bytes_freed"] += size
        for part in work.glob("uploads/*.part"):
            if _age_days(part) > 1:
                size = part.stat().st_size
                if not dry_run:
                    part.unlink(missing_ok=True)
                    part.with_suffix(".json").unlink(missing_ok=True)
                stats["upload_parts_deleted"] += 1
                stats["bytes_freed"] += size
    log(logger, "cleanup", **stats)
    return stats


def start_periodic(every_hours: float = 6.0) -> threading.Thread:
    def loop():
        while True:
            try:
                run_cleanup()
            except Exception as e:  # noqa: BLE001 — cleanup must never take the server down
                log(logger, "cleanup failed", error=str(e)[:300])
            time.sleep(every_hours * 3600)

    t = threading.Thread(target=loop, daemon=True, name="cleanup")
    t.start()
    return t
