"""What the API may show a client. Internal filesystem paths, tracebacks and log internals never leave the server;
errors carry a short reference id that operators can find in the structured logs."""
from __future__ import annotations

import re
import time

# Absolute POSIX paths (/x/y...) and Windows paths (C:\x or C:/x). Relative names like "clip.mp4" are kept.
_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|(?<![\w.:])/)(?:[^\s'\"<>:]+[\\/])+([^\s'\"<>\\/]*)")
_TB = re.compile(r"Traceback \(most recent call last\).*", re.S)

# spec job states (docs/PRODUCT_SPEC.md)
STATES = ("queued", "analyzing", "planning", "previewing", "rendering", "validating", "completed", "failed", "cancelled")
_STAGE_STATE = {"analyzing_media": "analyzing", "finding_best_shots": "analyzing", "analyzing_music": "analyzing",
                "understanding_reference": "analyzing", "planning_story": "planning", "building_timeline": "planning",
                "quality_check": "validating", "finalizing": "validating"}
PRIVATE_RESULT_KEYS = {"path", "paths", "work_dir", "cache_dir", "log_path"}


def scrub(text: str | None, limit: int = 400) -> str | None:
    """Remove tracebacks and directory components of absolute paths (keeps the file name)."""
    if text is None:
        return None
    t = _TB.sub("", str(text))
    t = _PATH.sub(lambda m: m.group(1) or "<path>", t)
    t = t.strip().splitlines()[0] if t.strip() else "internal error"
    return t[:limit]


def job_state(j: dict) -> str:
    st = j.get("status")
    if st == "done":
        return "completed"
    if st in ("failed", "cancelled", "queued"):
        return st
    stage = j.get("stage") or ""
    if stage in _STAGE_STATE:
        return _STAGE_STATE[stage]
    kind = j.get("kind")
    if kind == "analyze":
        return "analyzing"
    if kind == "plan":
        return "planning"
    if stage in ("rendering", "applying_color", "mixing_audio"):
        return "previewing" if kind == "preview" or (j.get("params") or {}).get("preview") else "rendering"
    return {"preview": "previewing", "render": "rendering", "generate": "planning", "revise": "planning"}.get(kind, "queued")


def clean_result(v):
    if isinstance(v, dict):
        return {k: clean_result(x) for k, x in v.items() if k not in PRIVATE_RESULT_KEYS}
    if isinstance(v, list):
        return [clean_result(x) for x in v]
    if isinstance(v, str) and ("/" in v or "\\" in v) and _PATH.search(v):
        return scrub(v, 2000)
    return v


def public_job(j: dict, with_log: bool = False) -> dict:
    now = time.time()
    start = j.get("started") or j.get("created")
    end = j.get("finished") or (now if j.get("status") in ("running", "queued") else None)
    out = {"id": j["id"], "project_id": j.get("project_id"), "kind": j["kind"], "status": j["status"], "state": job_state(j),
           "stage": j.get("stage"), "progress": j.get("progress"), "created": j.get("created"), "started": j.get("started"),
           "finished": j.get("finished"), "elapsed_s": round(end - start, 1) if start and end else None,
           "error": scrub(j.get("error")), "error_id": j["id"] if j.get("status") == "failed" else None,
           "result": clean_result(j.get("result"))}
    log = [ln for ln in (j.get("log") or []) if ln.get("stage") != "error"]
    out["last"] = [{"stage": ln.get("stage"), "progress": ln.get("progress"), "msg": scrub(ln.get("msg"), 200)} for ln in log[-1:]]
    if with_log:
        out["log"] = [{"t": ln.get("t"), "stage": ln.get("stage"), "progress": ln.get("progress"), "msg": scrub(ln.get("msg"), 200)} for ln in log[-50:]]
    return out
