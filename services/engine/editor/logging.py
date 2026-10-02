"""Structured JSON-lines logging with project/job/stage context."""
from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar

_ctx: ContextVar[dict] = ContextVar("log_ctx", default={})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": round(record.created, 3),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
            **_ctx.get(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger("editor")
    if root.handlers:
        return
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)
    root.setLevel(level)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"editor.{name}")


def bind(**fields) -> object:
    """Bind context fields (project_id, job_id, stage) for subsequent log lines."""
    return _ctx.set({**_ctx.get(), **fields})


def log(logger: logging.Logger, msg: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, msg, extra={"fields": fields})


class timed:
    """Context manager that logs the duration of a block and records it in `self.seconds`."""

    def __init__(self, logger: logging.Logger, what: str, **fields):
        self.logger, self.what, self.fields, self.seconds = logger, what, fields, 0.0

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.seconds = time.perf_counter() - self.t0
        log(self.logger, f"{self.what} {'failed' if exc else 'done'}", duration_s=round(self.seconds, 3), **self.fields)
        return False
