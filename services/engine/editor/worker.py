"""Standalone job worker: `python -m editor.worker` (EDITOR_ROLE=worker).

Runs the same job handlers as the API process but no HTTP server. Point it at the same EDITOR_DATA_DIR (database
and media volume) as the API, and run the API with EDITOR_ROLE=api so it only enqueues."""
from __future__ import annotations

import os
import signal
import threading


def main() -> int:
    os.environ.setdefault("EDITOR_ROLE", "worker")
    from . import auth, db
    from .config import get_settings
    from .jobs import get_queue
    from .logging import get_logger, log

    logger = get_logger("worker")
    if get_settings().role not in ("worker", "all"):
        raise SystemExit("EDITOR_ROLE must be 'worker' (or 'all') to run jobs")
    auth.check_config()
    db.connect()
    q = get_queue()
    q.start()
    if os.environ.get("EDITOR_CLEANUP", "1") != "0":
        from .cleanup import start_periodic

        start_periodic()
    log(logger, "worker started", worker_id=q.worker_id, threads=q.n)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.wait(5.0):
        alive = sum(t.is_alive() for t in q.threads)
        (get_settings().data_dir / ".worker-heartbeat").write_text(f"{alive}")
    log(logger, "worker stopping (running jobs are re-queued by the next worker)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
