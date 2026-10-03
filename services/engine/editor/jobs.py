"""Job queue abstraction.

`LocalJobQueue` persists jobs in SQLite and executes them on in-process worker threads; progress,
stage and log lines are written to the job row and streamed to clients over SSE. The `JobQueue`
interface (submit / get / cancel) is what a Redis/RQ/Celery backend would implement."""
from __future__ import annotations

import queue
import threading
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

Handler = Callable[[dict, Callable[[str, float, str], None]], dict]


class JobQueue(ABC):
    @abstractmethod
    def submit(self, kind: str, project_id: str | None, params: dict) -> dict: ...

    @abstractmethod
    def get(self, job_id: str) -> dict | None: ...


class LocalJobQueue(JobQueue):
    def __init__(self, workers: int | None = None):
        self.handlers: dict[str, Handler] = {}
        self.q: queue.Queue[str] = queue.Queue()
        self.n = workers or get_settings().workers
        self.threads: list[threading.Thread] = []
        self._started = False

    def register(self, kind: str, fn: Handler) -> None:
        self.handlers[kind] = fn

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        # requeue jobs interrupted by a restart
        for j in db.query("SELECT id FROM jobs WHERE status IN ('queued','running') ORDER BY created"):
            db.update("jobs", j["id"], status="queued", stage="queued", error=None)
            self.q.put(j["id"])
        for i in range(self.n):
            t = threading.Thread(target=self._worker, name=f"job-worker-{i}", daemon=True)
            t.start()
            self.threads.append(t)

    def submit(self, kind: str, project_id: str | None, params: dict) -> dict:
        if kind not in self.handlers:
            raise ValueError(f"unknown job kind {kind}")
        jid = db.new_id("job")
        db.insert("jobs", id=jid, project_id=project_id, kind=kind, status="queued", stage="queued", progress=0.0, params=params, log=[], created=time.time())
        self.q.put(jid)
        return db.get("jobs", jid)  # type: ignore[return-value]

    def get(self, job_id: str) -> dict | None:
        return db.get("jobs", job_id)

    def run_sync(self, kind: str, project_id: str | None, params: dict) -> dict:
        """Execute immediately in the calling thread (CLI, tests)."""
        j = self.submit(kind, project_id, params)
        self._execute(j["id"])
        return db.get("jobs", j["id"])  # type: ignore[return-value]

    def _worker(self) -> None:
        while True:
            jid = self.q.get()
            try:
                self._execute(jid)
            finally:
                self.q.task_done()

    def _execute(self, jid: str) -> None:
        j = db.get("jobs", jid)
        if not j or j["status"] not in ("queued",):
            return
        bind(job_id=jid, project_id=j["project_id"], job_kind=j["kind"])
        db.update("jobs", jid, status="running", started=time.time(), stage="starting")
        lines: list[dict] = []
        last_write = [0.0]

        def progress(stage: str, frac: float, msg: str = "") -> None:
            now = time.time()
            if not lines or lines[-1]["stage"] != stage or lines[-1]["msg"] != msg:
                lines.append({"t": round(now, 2), "stage": stage, "progress": round(float(frac), 4), "msg": msg})
            if now - last_write[0] > 0.25 or frac >= 1.0:
                last_write[0] = now
                db.update("jobs", jid, stage=stage, progress=round(float(frac), 4), log=lines[-200:])

        try:
            res = self.handlers[j["kind"]](j["params"] or {}, progress)
            db.update("jobs", jid, status="done", stage="finalizing", progress=1.0, result=res, log=lines[-200:], finished=time.time())
            log(logger, "job done", seconds=round(time.time() - (j["created"] or time.time()), 2))
        except Exception as e:  # noqa: BLE001
            tb = traceback.format_exc()
            db.update("jobs", jid, status="failed", error=f"{type(e).__name__}: {e}"[:2000], log=lines[-200:] + [{"t": time.time(), "stage": "error", "msg": tb[-1500:]}],
                      finished=time.time())
            log(logger, "job failed", error=str(e)[:500])


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
