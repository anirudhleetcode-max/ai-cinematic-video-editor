"""Job queue abstraction.

`LocalJobQueue` persists jobs in SQLite; worker threads (in the API process, or in a separate
`python -m editor.worker` process) claim and execute them. Progress, stage and log lines are written to the job
row and streamed to clients over SSE. The `JobQueue`
interface (submit / get / cancel) is what a Redis/RQ/Celery backend would implement."""
from __future__ import annotations

import logging
import os
import queue
import socket
import threading
import uuid
import time
import traceback
from abc import ABC, abstractmethod
from typing import Callable

from . import db
from .config import get_settings
from .logging import bind, get_logger, log

logger = get_logger("jobs")

STAGES = ["uploading", "analyzing_media", "finding_best_shots", "analyzing_music", "understanding_reference", "planning_story",
          "building_timeline", "applying_color", "mixing_audio", "rendering", "quality_check", "finalizing"]

class JobCancelled(Exception):
    pass


Handler = Callable[[dict, Callable[[str, float, str], None]], dict]


class JobQueue(ABC):
    @abstractmethod
    def submit(self, kind: str, project_id: str | None, params: dict) -> dict: ...

    @abstractmethod
    def get(self, job_id: str) -> dict | None: ...


class LocalJobQueue(JobQueue):
    """Jobs live in the database; any process with EDITOR_ROLE=worker|all claims them atomically
    (UPDATE ... WHERE status='queued'), so API and worker can run as separate processes / containers sharing the DB
    and data volume. A worker heartbeats its running jobs; a job whose heartbeat stops (worker crashed, container
    replaced) is re-queued by any live worker after STALE_S, up to EDITOR_JOB_MAX_ATTEMPTS attempts, then failed.
    Cancellation is a database flag, so it works across processes."""

    STALE_S = 90.0
    POLL_S = 1.0

    def __init__(self, workers: int | None = None):
        self.handlers: dict[str, Handler] = {}
        self.q: queue.Queue[str] = queue.Queue()  # wake-up hints for jobs submitted in this process
        self.n = workers or get_settings().workers
        self.threads: list[threading.Thread] = []
        self._started = False
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self._running: set[str] = set()
        self._rlock = threading.Lock()

    def register(self, kind: str, fn: Handler) -> None:
        self.handlers[kind] = fn

    @property
    def runs_workers(self) -> bool:
        return get_settings().role in ("all", "worker")

    def start(self) -> None:
        if self._started or not self.runs_workers:
            return
        self._started = True
        if get_settings().role == "all":
            # single-process mode: nothing else can be running these, so jobs left 'running' by a previous process
            # were interrupted by its restart
            self.recover(stale_s=0.0)
        for i in range(self.n):
            t = threading.Thread(target=self._worker, name=f"job-worker-{i}", daemon=True)
            t.start()
            self.threads.append(t)
        threading.Thread(target=self._heartbeat, name="job-heartbeat", daemon=True).start()

    def recover(self, stale_s: float | None = None) -> int:
        """Re-queue (or fail, after too many attempts) running jobs whose worker stopped heartbeating."""
        cutoff = time.time() - (self.STALE_S if stale_s is None else stale_s)
        n = 0
        for j in db.query("SELECT id, attempts, worker_id FROM jobs WHERE status='running' AND COALESCE(heartbeat, started, 0) <= ?", (cutoff,)):
            if j["worker_id"] == self.worker_id and j["id"] in self._running:
                continue
            if (j["attempts"] or 0) >= get_settings().job_max_attempts:
                db.execute("UPDATE jobs SET status='failed', error=?, finished=? WHERE id=? AND status='running'",
                           ("the worker stopped while running this job (retry limit reached)", time.time(), j["id"]))
            else:
                n += db.execute("UPDATE jobs SET status='queued', stage='queued', worker_id=NULL WHERE id=? AND status='running'", (j["id"],))
                self.q.put(j["id"])
        if n:
            log(logger, "re-queued interrupted jobs", n=n)
        return n

    def submit(self, kind: str, project_id: str | None, params: dict) -> dict:
        if kind not in self.handlers:
            raise ValueError(f"unknown job kind {kind}")
        jid = db.new_id("job")
        db.insert("jobs", id=jid, project_id=project_id, kind=kind, status="queued", stage="queued", progress=0.0, params=params, log=[], created=time.time(),
                  attempts=0, cancel_requested=0)
        self.q.put(jid)
        return db.get("jobs", jid)  # type: ignore[return-value]

    def get(self, job_id: str) -> dict | None:
        return db.get("jobs", job_id)

    def cancel(self, job_id: str) -> dict | None:
        """Queued jobs are cancelled immediately; running jobs stop at their next progress report (an FFmpeg step
        already started finishes or times out first). Finished jobs are left alone."""
        j = db.get("jobs", job_id)
        if not j or j["status"] not in ("queued", "running"):
            return j
        if not db.execute("UPDATE jobs SET status='cancelled', stage='cancelled', finished=? WHERE id=? AND status='queued'", (time.time(), job_id)):
            db.execute("UPDATE jobs SET cancel_requested=1, stage='cancelling' WHERE id=? AND status='running'", (job_id,))
        return db.get("jobs", job_id)

    def run_sync(self, kind: str, project_id: str | None, params: dict) -> dict:
        """Execute immediately in the calling thread (CLI, tests)."""
        j = self.submit(kind, project_id, params)
        self._execute(j["id"])
        return db.get("jobs", j["id"])  # type: ignore[return-value]

    def _next(self) -> str | None:
        try:
            return self.q.get(timeout=self.POLL_S)
        except queue.Empty:
            rows = db.query("SELECT id FROM jobs WHERE status='queued' ORDER BY created LIMIT 1")
            return rows[0]["id"] if rows else None

    def _worker(self) -> None:
        last_recover = 0.0
        while True:
            try:
                if time.time() - last_recover > 30:
                    last_recover = time.time()
                    self.recover()
                jid = self._next()
                if jid:
                    self._execute(jid)
            except Exception as e:  # noqa: BLE001 — a worker thread must never die
                log(logger, "worker loop error", logging.ERROR, error=str(e)[:300])
                time.sleep(1.0)

    def _heartbeat(self) -> None:
        while True:
            time.sleep(10.0)
            with self._rlock:
                ids = list(self._running)
            for jid in ids:
                try:
                    db.execute("UPDATE jobs SET heartbeat=? WHERE id=? AND worker_id=?", (time.time(), jid, self.worker_id))
                except Exception:  # noqa: BLE001
                    pass

    def _execute(self, jid: str) -> None:
        now = time.time()
        claimed = db.execute("UPDATE jobs SET status='running', started=?, heartbeat=?, stage='starting', worker_id=?, attempts=COALESCE(attempts,0)+1 "
                             "WHERE id=? AND status='queued'", (now, now, self.worker_id, jid))
        if not claimed:
            return  # another worker took it, or it was cancelled / already finished
        j = db.get("jobs", jid)
        if j["kind"] not in self.handlers:
            db.update("jobs", jid, status="failed", error=f"unknown job kind {j['kind']}", finished=time.time())
            return
        with self._rlock:
            self._running.add(jid)
        bind(job_id=jid, project_id=j["project_id"], job_kind=j["kind"])
        lines: list[dict] = []
        last_write = [0.0]

        def progress(stage: str, frac: float, msg: str = "") -> None:
            now = time.time()
            if not lines or lines[-1]["stage"] != stage or lines[-1]["msg"] != msg:
                lines.append({"t": round(now, 2), "stage": stage, "progress": round(float(frac), 4), "msg": msg})
            if now - last_write[0] > 0.25 or frac >= 1.0:
                last_write[0] = now
                row = db.query("SELECT cancel_requested FROM jobs WHERE id=?", (jid,))
                if row and row[0]["cancel_requested"]:
                    raise JobCancelled()
                db.update("jobs", jid, stage=stage, progress=round(float(frac), 4), log=lines[-200:], heartbeat=now)

        try:
            res = self.handlers[j["kind"]](j["params"] or {}, progress)
            db.update("jobs", jid, status="done", stage="finalizing", progress=1.0, result=res, log=lines[-200:], finished=time.time())
            log(logger, "job done", seconds=round(time.time() - (j["created"] or time.time()), 2))
        except JobCancelled:
            db.update("jobs", jid, status="cancelled", stage="cancelled", log=lines[-200:], finished=time.time())
            log(logger, "job cancelled")
        except Exception as e:  # noqa: BLE001
            tb = traceback.format_exc()
            db.update("jobs", jid, status="failed", error=f"{type(e).__name__}: {e}"[:2000], log=lines[-200:] + [{"t": time.time(), "stage": "error", "msg": tb[-1500:]}],
                      finished=time.time())
            log(logger, "job failed", logging.ERROR, error=str(e)[:500], error_id=jid, traceback=tb[-3000:])
        finally:
            with self._rlock:
                self._running.discard(jid)


_queue: LocalJobQueue | None = None


def get_queue() -> LocalJobQueue:
    global _queue
    if _queue is None:
        from . import service as S

        q = LocalJobQueue()
        q.register("analyze", lambda p, pr: S.analyze_project(p["project_id"], p.get("mode", "fast"), pr, p.get("force", False)))
        q.register("plan", lambda p, pr: _strip_plan(S.create_edit_plan(p["project_id"], p["prompt"], p.get("mode", "fast"), pr)))
        q.register("preview", lambda p, pr: _render_summary(S.render_version(p["project_id"], p.get("version_id"), True, pr)))
        q.register("render", lambda p, pr: _render_summary(S.render_version(p["project_id"], p.get("version_id"), False, pr, p.get("export"))))
        q.register("generate", lambda p, pr: S.generate(p["project_id"], p["prompt"], p.get("mode", "fast"), p.get("preview_first", True), pr))
        q.register("revise", _revise_job)
        _queue = q
    return _queue


def _strip_plan(v: dict) -> dict:
    return {k: v[k] for k in ("id", "number", "kind", "prompt", "planning_seconds") if k in v} | {"n_segments": len(v["plan"]["timeline"]), "duration": v["plan"]["duration"]}


def _render_summary(r: dict) -> dict:
    rep = r["report"]
    return {"render_id": r["id"], "version": r["version"], "path": r["path"], "qc_passed": rep["qc"]["passed"], "qc_failures": rep["qc"]["failures"],
            "timings": rep["timings"], "encoder": rep.get("encoder"), "fallbacks": rep.get("fallbacks", []), "segments_cached": rep.get("segments_cached"),
            "audio": rep.get("audio")}


def _revise_job(p: dict, pr) -> dict:
    from . import service as S

    pr("planning_story", 0.2, "applying revision")
    v = S.revise(p["project_id"], p["text"], p.get("base_version_id"))
    out = {"version": _strip_plan(v), "changes": v["changes"]}
    if v["changes"] and all(c.get("noop") for c in v["changes"]):
        # nothing to change (e.g. that song already plays there): say so instead of re-rendering an identical film
        out["noop"] = True
        out["message"] = "; ".join(f"{c['op']}: {c.get('reason', 'no change')}" for c in v["changes"])
        return out
    if p.get("render", True):
        out["render"] = _render_summary(S.render_version(p["project_id"], v["id"], p.get("preview", False), pr))
    return out
