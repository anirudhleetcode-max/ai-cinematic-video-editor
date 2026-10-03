"""HTTP API (FastAPI). Run: `uvicorn editor.api:app --port 8000`."""
from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import json
import os
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import auth as AUTH, db, service as S
from .config import get_settings
from .hw import diagnostics
from .jobs import STAGES, get_queue
from .logging import get_logger
from .media.probe import AUDIO_EXT, IMAGE_EXT, VIDEO_EXT
from .previews import preview as library_preview
from .proc import safe_filename, safe_path
from .public import public_job, scrub
from .registry import REGISTRIES, library_stats, search_library, templates
from .storage import UploadTooLarge, get_storage

logger = get_logger("api")


@asynccontextmanager
async def _lifespan(_: FastAPI):
    AUTH.check_config()
    db.connect()
    get_queue().start()
    if os.environ.get("EDITOR_CLEANUP", "1") != "0":
        from .cleanup import start_periodic

        start_periodic()
    yield


PUBLIC = ("/health", "/health/live", "/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect", "/auth/register", "/auth/login", "/auth/config")
JOB_SUFFIXES = ("/analyze", "/edit-plan", "/generate", "/preview", "/render", "/revise")


async def guard(request: Request) -> None:
    """Runs before EVERY route: authentication, rate limits, job limits and ownership of every path parameter
    (project / asset / version / render / job). Objects the caller does not own answer 404 (existence is not leaked)."""
    path = request.url.path
    if path in PUBLIC:
        if path.startswith("/auth/") and request.method == "POST":
            ip = request.client.host if request.client else "?"
            if not AUTH.limiter.allow(ip, "login", get_settings().login_rate_per_min):
                raise HTTPException(429, "too many attempts — wait a minute", headers={"Retry-After": "60"})
        return
    st = get_settings()
    if st.auth == "none":
        user = AUTH.LOCAL_USER
    else:
        hdr = request.headers.get("authorization", "")
        token = hdr[7:] if hdr.lower().startswith("bearer ") else (request.query_params.get("access_token") if request.method == "GET" else None)
        user = await asyncio.to_thread(AUTH.authenticate, token)
        if user is None:
            raise HTTPException(401, "authentication required", headers={"WWW-Authenticate": "Bearer"})
    if not AUTH.limiter.allow(user.id, "all", st.rate_limit_per_min):
        raise HTTPException(429, "rate limit exceeded — slow down", headers={"Retry-After": "10"})
    if request.method in ("POST", "PUT") and ("/assets" in path or "/uploads" in path or path.endswith("/reference")):
        if not AUTH.limiter.allow(user.id, "upload", st.upload_rate_per_min):
            raise HTTPException(429, "upload rate limit exceeded", headers={"Retry-After": "10"})
    if request.method == "POST" and path.endswith(JOB_SUFFIXES):
        if not AUTH.limiter.allow(user.id, "jobs", st.job_rate_per_min):
            raise HTTPException(429, "job submission rate limit exceeded", headers={"Retry-After": "30"})
        if st.auth != "none" and await asyncio.to_thread(AUTH.active_jobs, user) >= st.max_jobs_per_user:
            raise HTTPException(429, f"you already have {st.max_jobs_per_user} active jobs — wait for one to finish")
    for name, value in request.path_params.items():
        ok = await asyncio.to_thread(AUTH.may_access, user, name, value)
        if ok is False:
            raise HTTPException(404, "not found")
    request.state.user = user


def _user(request: Request) -> AUTH.User:
    return getattr(request.state, "user", AUTH.LOCAL_USER)


def _check_quota(request: Request, incoming: int) -> None:
    st = get_settings()
    u = _user(request)
    if st.auth == "none" or u.is_admin:
        return
    if AUTH.storage_used_bytes(u) + incoming > st.user_quota_gb * 2**30:
        raise HTTPException(413, f"storage quota of {st.user_quota_gb:g} GB exceeded")


app = FastAPI(title="Autonomous AI Video Editor", version="0.2.0", lifespan=_lifespan, dependencies=[Depends(guard)])
def _cors_origins() -> list[str]:
    origins = list(get_settings().cors_origins)
    if get_settings().env == "development":
        origins += [o for o in ("http://127.0.0.1:3000", "http://localhost:3000") if o not in origins]
    return origins


app.add_middleware(CORSMiddleware, allow_origins=_cors_origins(), allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type"])


@app.exception_handler(KeyError)
async def _keyerr(_: Request, e: KeyError):
    return JSONResponse(status_code=404, content={"detail": scrub(str(e).strip("'\""))})


@app.exception_handler(ValueError)
async def _valerr(_: Request, e: ValueError):
    return JSONResponse(status_code=400, content={"detail": scrub(str(e))})


@app.exception_handler(Exception)
async def _unhandled(request: Request, e: Exception):
    """Anything unexpected: log it in full on the server, return a reference id and nothing internal to the client."""
    import traceback

    ref = db.new_id("err")
    from .logging import log as _log

    _log(logger, "unhandled error", 40, error_id=ref, path=request.url.path, error=f"{type(e).__name__}: {e}"[:500],
         traceback=traceback.format_exc()[-3000:])
    return JSONResponse(status_code=500, content={"detail": "internal error", "error_id": ref})


# ------------------------------------------------------------------------------------ accounts
class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    name: str | None = Field(None, max_length=80)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


def _bearer(request: Request) -> str | None:
    hdr = request.headers.get("authorization", "")
    return hdr[7:] if hdr.lower().startswith("bearer ") else None


@app.get("/auth/config")
def auth_config():
    st = get_settings()
    return {"auth": st.auth, "registration": st.allow_registration and st.auth == "token"}


@app.post("/auth/register")
async def auth_register(body: RegisterIn):
    st = get_settings()
    if st.auth != "token":
        raise HTTPException(400, "accounts are disabled in local single-user mode (EDITOR_AUTH=none)")
    if not st.allow_registration:
        raise HTTPException(403, "registration is closed — ask an administrator for an account")
    try:
        await asyncio.to_thread(AUTH.register, body.email, body.password, body.name)
    except AUTH.AuthError as e:
        raise HTTPException(409 if "exists" in str(e) else 400, str(e)) from None
    return await auth_login(LoginIn(email=body.email, password=body.password))


@app.post("/auth/login")
async def auth_login(body: LoginIn):
    if get_settings().auth != "token":
        raise HTTPException(400, "accounts are disabled in local single-user mode (EDITOR_AUTH=none)")
    r = await asyncio.to_thread(AUTH.login, body.email, body.password)
    if r is None:
        raise HTTPException(401, "invalid email or password")
    u, token, expires = r
    return {"token": token, "expires": expires, "user": {"id": u.id, "name": u.name, "is_admin": u.is_admin}}


@app.post("/auth/logout")
def auth_logout(request: Request):
    AUTH.logout(_bearer(request))
    return {"ok": True}


@app.get("/auth/me")
def auth_me(request: Request):
    u = _user(request)
    return {"id": u.id, "name": u.name, "is_admin": u.is_admin, "auth": get_settings().auth}


# ------------------------------------------------------------------------------------ health
def _component_health() -> dict:
    """Each dependency checked for real; nothing internal (paths, versions of secrets) is returned."""
    import shutil

    from .media import vad
    from .vision import models_dir

    st = get_settings()
    out: dict[str, dict] = {}
    try:
        db.query("SELECT 1")
        out["database"] = {"ok": True}
    except Exception:  # noqa: BLE001
        out["database"] = {"ok": False}
    try:
        probe = st.data_dir / ".health"
        probe.write_text("ok")
        probe.unlink()
        free = shutil.disk_usage(st.data_dir).free
        out["storage"] = {"ok": free > 2 * 2**30, "free_gb": round(free / 2**30, 1), "backend": type(get_storage()).__name__}
    except OSError:
        out["storage"] = {"ok": False}
    q = get_queue()
    counts = {r["status"]: r["n"] for r in db.query("SELECT status, COUNT(*) AS n FROM jobs WHERE status IN ('queued','running') GROUP BY status")}
    if q.runs_workers:
        alive = sum(t.is_alive() for t in q.threads)
        out["worker"] = {"ok": alive == q.n and q.n > 0, "threads_alive": alive, "threads": q.n, "process": "in-process"}
    else:  # separate worker process: it touches a heartbeat file on the shared data volume every 5 s
        hb = st.data_dir / ".worker-heartbeat"
        age = time.time() - hb.stat().st_mtime if hb.exists() else None
        out["worker"] = {"ok": age is not None and age < 30, "last_heartbeat_s": round(age, 1) if age is not None else None, "process": "separate"}
    out["queue"] = {"ok": True, "backend": type(q).__name__, "queued": counts.get("queued", 0), "running": counts.get("running", 0)}
    d = diagnostics()
    out["ffmpeg"] = {"ok": bool(d["ffmpeg"] and d["ffprobe"]), "encoder": d["selected_encoder"], "hardware_encoding": d["hardware_encoding"]}
    vis = models_dir()
    out["models"] = {"ok": True, "vision_deep": (vis / "object_detection_nanodet_2022nov.onnx").exists() and (vis / "face_detection_yunet_2023mar.onnx").exists(),
                     "vad": vad.available(), "note": "optional — the classic OpenCV / energy fallbacks run without them"}
    return out


@app.get("/health/live")
def health_live():
    return {"ok": True}


@app.get("/health")
def health():
    comps = _component_health()
    ok = all(c["ok"] for c in comps.values())
    d = comps["ffmpeg"]
    body = {"ok": ok, "ffmpeg": d["ok"], "encoder": d["encoder"], "hardware_encoding": d["hardware_encoding"], "components": comps, "time": time.time()}
    return JSONResponse(status_code=200 if ok else 503, content=body)


@app.get("/diagnostics")
def diag(request: Request):
    if os.environ.get("EDITOR_ENV", "development") != "development" and not _user(request).is_admin:
        raise HTTPException(403, "diagnostics are only available in development or to admins")
    d = diagnostics()
    jobs = db.query("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")
    failed = db.query("SELECT id, kind, error, finished FROM jobs WHERE status='failed' ORDER BY finished DESC LIMIT 10")
    active = db.query("SELECT id, kind, stage, progress, started FROM jobs WHERE status='running'")
    renders = db.query("SELECT id, kind, created, report FROM renders ORDER BY created DESC LIMIT 5")
    st = get_settings()
    return {**d, "data_dir": str(st.data_dir), "jobs": {r["status"]: r["n"] for r in jobs}, "active_jobs": active, "failed_jobs": failed,
            "cache": db.cache_stats(), "recent_renders": [{"id": r["id"], "kind": r["kind"], "created": r["created"],
                                                           "timings": (r["report"] or {}).get("timings"), "fallbacks": (r["report"] or {}).get("fallbacks")} for r in renders],
            "ai_provider": _ai_status()}


def _ai_status() -> dict:
    from .director.providers import get_provider

    p = get_provider()
    return {"provider": p.name, "external_ai": p.name != "deterministic"}


# ------------------------------------------------------------------------------------ library
@app.get("/effects")
def effects(q: str | None = None):
    return _registry("effects", q)


@app.get("/transitions")
def transitions(q: str | None = None):
    return _registry("transitions", q)


@app.get("/text-animations")
def text_animations(q: str | None = None):
    return _registry("text-animations", q)


@app.get("/text-styles")
def text_styles(q: str | None = None):
    return _registry("text-styles", q)


@app.get("/color-presets")
def color_presets(q: str | None = None):
    return _registry("color-presets", q)


@app.get("/audio-presets")
def audio_presets(q: str | None = None):
    return _registry("audio-presets", q)


@app.get("/motion-presets")
def motion_presets(q: str | None = None):
    return _registry("motion-presets", q)


def _registry(kind: str, q: str | None):
    reg = REGISTRIES[kind]
    items = reg.search(q) if q else reg.all()
    return {"kind": kind, "count": len(items), "parameter_configurations": sum(d.configurations() for d in items), "items": [d.as_dict() for d in items]}


@app.get("/templates")
def list_templates():
    return {"count": len(templates()), "items": list(templates().values())}


@app.get("/library/search")
def library_search(q: str):
    return {"query": q, "results": search_library(q)}


@app.get("/library/stats")
def lib_stats():
    return library_stats()


@app.get("/library/preview/{kind}/{item_id}")
def lib_preview(kind: str, item_id: str):
    try:
        return FileResponse(library_preview(kind, item_id), media_type="image/png", headers={"Cache-Control": "max-age=86400"})
    except KeyError as e:
        raise HTTPException(404, str(e))


# ------------------------------------------------------------------------------------ projects
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    settings: dict = Field(default_factory=dict)


@app.post("/projects")
def create_project(body: ProjectIn, request: Request):
    u = _user(request)
    if get_settings().auth != "none" and not u.is_admin:
        n = db.query("SELECT COUNT(*) AS n FROM projects WHERE owner_id=?", (u.id,))[0]["n"]
        if n >= get_settings().max_projects_per_user:
            raise HTTPException(429, f"project limit ({get_settings().max_projects_per_user}) reached — delete a project first")
    p = S.create_project(body.name, body.settings)
    db.update("projects", p["id"], owner_id=u.id)
    return {**p, "owner_id": u.id}


@app.get("/projects")
def list_projects(request: Request):
    u = _user(request)
    rows = S.list_projects()
    return rows if u.is_admin else [r for r in rows if r.get("owner_id") == u.id]


@app.get("/projects/{pid}")
def get_project(pid: str):
    p = S.get_project(pid)
    return {**p, "assets": [S.asset_summary(a) for a in db.query("SELECT * FROM assets WHERE project_id=? ORDER BY ordinal", (pid,))],
            "versions": S.list_versions(pid), "renders": [_render_row(r) for r in S.list_renders(pid)]}


@app.delete("/projects/{pid}")
def delete_project(pid: str):
    S.delete_project(pid)
    return {"deleted": pid}


class SettingsIn(BaseModel):
    brand_kit_id: str | None = None
    mode: str | None = None


@app.patch("/projects/{pid}")
def patch_project(pid: str, body: SettingsIn, request: Request):
    if body.brand_kit_id:
        b = db.get("brand_kits", body.brand_kit_id)
        u = _user(request)
        if not b or not (u.is_admin or get_settings().auth == "none" or b.get("owner_id") == u.id):
            raise HTTPException(404, "brand kit not found")
    return S.update_settings(pid, **body.model_dump(exclude_none=True))


# ------------------------------------------------------------------------------------ assets
ALLOWED = VIDEO_EXT | AUDIO_EXT | IMAGE_EXT | {".cube"}


@app.post("/projects/{pid}/assets")
async def upload_assets(request: Request, pid: str, files: list[UploadFile] = File(...), role: str | None = Form(None)):
    S.get_project(pid)
    _check_quota(request, int(request.headers.get("content-length") or 0))
    out, errors = [], []
    for f in files:
        name = safe_filename(f.filename or "upload")
        if Path(name).suffix.lower() not in ALLOWED:
            errors.append({"file": name, "error": f"unsupported type {Path(name).suffix}"})
            continue
        try:
            a = await asyncio.to_thread(S.add_asset, pid, name, f.file, role)
            out.append(S.asset_summary(a))
        except (ValueError, UploadTooLarge) as e:
            errors.append({"file": name, "error": scrub(str(e))})
    return {"assets": out, "errors": errors}


class UploadInit(BaseModel):
    filename: str
    size: int = Field(gt=0)
    role: str | None = None


@app.post("/projects/{pid}/uploads")
def init_upload(pid: str, body: UploadInit, request: Request):
    """Resumable upload: init → PUT chunks with ?offset= → complete."""
    S.get_project(pid)
    _check_quota(request, body.size)
    if Path(body.filename).suffix.lower() not in ALLOWED:
        raise HTTPException(400, f"unsupported type {safe_filename(Path(body.filename).suffix)}")
    if body.size > get_settings().max_upload_mb << 20:
        raise HTTPException(413, "file too large")
    uid = db.new_id("upl")
    meta = {"filename": safe_filename(body.filename), "size": body.size, "role": body.role, "project_id": pid}
    p = get_storage().work_path(pid, "uploads", f"{uid}.part")
    p.touch()
    p.with_suffix(".json").write_text(json.dumps(meta))
    return {"upload_id": uid, "received": 0}


def _upload_paths(pid: str, uid: str) -> tuple[Path, dict]:
    p = get_storage().work_path(pid, "uploads", f"{safe_filename(uid)}.part")
    mp = p.with_suffix(".json")
    if not mp.exists():
        raise HTTPException(404, "unknown upload")
    return p, json.loads(mp.read_text())


@app.put("/projects/{pid}/uploads/{uid}")
async def upload_chunk(pid: str, uid: str, request: Request, offset: int = 0):
    p, meta = _upload_paths(pid, uid)
    cur = p.stat().st_size
    if offset != cur:
        return JSONResponse(status_code=409, content={"detail": "offset mismatch", "received": cur})
    body = await request.body()
    if cur + len(body) > meta["size"]:
        raise HTTPException(400, "chunk exceeds declared size")
    with open(p, "ab") as fh:
        fh.write(body)
    return {"received": p.stat().st_size}


@app.get("/projects/{pid}/uploads/{uid}")
def upload_status(pid: str, uid: str):
    p, meta = _upload_paths(pid, uid)
    return {"received": p.stat().st_size, "size": meta["size"]}


@app.post("/projects/{pid}/uploads/{uid}/complete")
async def upload_complete(pid: str, uid: str):
    p, meta = _upload_paths(pid, uid)
    if p.stat().st_size != meta["size"]:
        raise HTTPException(400, f"incomplete upload: {p.stat().st_size}/{meta['size']} bytes")
    with open(p, "rb") as fh:
        a = await asyncio.to_thread(S.add_asset, pid, meta["filename"], fh, meta.get("role"))
    p.unlink(missing_ok=True)
    p.with_suffix(".json").unlink(missing_ok=True)
    return S.asset_summary(a)


@app.get("/projects/{pid}/search")
def search_shots(pid: str, q: str = ""):
    """Find analysed shots by description (label match — see editor/retrieval.py for what is and is not understood)."""
    from .retrieval import search

    if not q.strip() or len(q) > 200:
        raise HTTPException(400, "give a short description, e.g. ?q=crowd")
    assets = [a for a in S.list_assets(pid) if a.get("role") in ("clip", "broll")]
    full = [db.get("assets", a["id"]) for a in assets]
    return search([{"filename": a["filename"], "analysis": a.get("analysis")} for a in full if a], q)


@app.get("/projects/{pid}/assets")
def list_assets(pid: str):
    return [S.asset_summary(a) for a in db.query("SELECT * FROM assets WHERE project_id=? ORDER BY ordinal", (pid,))]


@app.delete("/assets/{aid}")
def delete_asset(aid: str):
    S.delete_asset(aid)
    return {"deleted": aid}


@app.patch("/assets/{aid}")
def patch_asset(aid: str, role: str = Form(...)):
    if role not in S.ROLES:
        raise HTTPException(400, "invalid role")
    db.update("assets", aid, role=role, analysis=None)
    return {"id": aid, "role": role}


@app.get("/assets/{aid}/thumbnail")
def asset_thumb(aid: str):
    a = db.get("assets", aid)
    if not a or not a.get("thumb") or not Path(a["thumb"]).exists():
        raise HTTPException(404, "no thumbnail")
    return FileResponse(a["thumb"], media_type="image/jpeg")


@app.get("/assets/{aid}/file")
def asset_file(aid: str):
    a = db.get("assets", aid)
    if not a:
        raise HTTPException(404, "asset not found")
    return FileResponse(safe_path(Path(a["path"]), get_settings().projects_dir), filename=a["filename"])


# ------------------------------------------------------------------------------------ pipeline
class ModeIn(BaseModel):
    mode: str = Field("fast", pattern="^(fast|quality|emergency)$")
    force: bool = False


def _job(kind: str, pid: str, params: dict) -> dict:
    S.get_project(pid)
    j = get_queue().submit(kind, pid, {"project_id": pid, **params})
    return {"job_id": j["id"], "kind": kind, "status": j["status"], "events": f"/jobs/{j['id']}/events"}


@app.post("/projects/{pid}/analyze")
def analyze(pid: str, body: ModeIn = ModeIn()):
    return _job("analyze", pid, body.model_dump())


@app.post("/projects/{pid}/reference")
async def reference(pid: str, file: UploadFile = File(...)):
    name = safe_filename(file.filename or "reference.mp4")
    if Path(name).suffix.lower() not in VIDEO_EXT:
        raise HTTPException(400, "reference must be a video file")
    for old in db.query("SELECT id FROM assets WHERE project_id=? AND role='reference'", (pid,)):
        S.delete_asset(old["id"])
    a = await asyncio.to_thread(S.add_asset, pid, name, file.file, "reference")
    return {"asset": S.asset_summary(a), **_job("analyze", pid, {"mode": "fast"})}


class PromptIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    mode: str = Field("fast", pattern="^(fast|quality|emergency)$")
    preview_first: bool = True


@app.post("/projects/{pid}/edit-plan")
def edit_plan(pid: str, body: PromptIn):
    return _job("plan", pid, body.model_dump())


@app.post("/projects/{pid}/generate")
def generate(pid: str, body: PromptIn):
    return _job("generate", pid, body.model_dump())


class RenderIn(BaseModel):
    version_id: str | None = None
    export: dict | None = None


@app.post("/projects/{pid}/preview")
def preview(pid: str, body: RenderIn = RenderIn()):
    return _job("preview", pid, body.model_dump())


@app.post("/projects/{pid}/render")
def render(pid: str, body: RenderIn = RenderIn()):
    if body.export:
        allowed = {"width", "height", "fps", "vcodec", "quality", "audio_bitrate_k", "prefer_hw", "preset_name"}
        bad = set(body.export) - allowed
        if bad:
            raise HTTPException(400, f"unknown export fields {sorted(bad)}")
    return _job("render", pid, body.model_dump())


class ReviseIn(BaseModel):
    text: str = Field(min_length=2, max_length=1000)
    base_version_id: str | None = None
    render: bool = True
    preview: bool = False


@app.post("/projects/{pid}/revise")
def revise(pid: str, body: ReviseIn):
    if (body.text or "").lower().strip().startswith(("go back", "revert", "undo")):
        return S.revert(pid, body.text)
    return _job("revise", pid, body.model_dump())


class RevertIn(BaseModel):
    query: str | None = None
    version_id: str | None = None


@app.post("/projects/{pid}/revert")
def revert(pid: str, body: RevertIn):
    return S.revert(pid, body.query, body.version_id)


@app.get("/projects/{pid}/versions")
def versions(pid: str):
    return S.list_versions(pid)


@app.get("/versions/{vid}")
def version(vid: str):
    v = S.get_version(vid)
    from .schemas import EditPlan

    v["estimate"] = {"final": S.estimate_render_seconds(EditPlan.model_validate(v["plan"])),
                     "preview": S.estimate_render_seconds(EditPlan.model_validate(v["plan"]), True)}
    return v


@app.get("/versions/{vid}/inspector")
def version_inspector(vid: str):
    return S.inspector(vid)


@app.get("/projects/{pid}/render-status")
def render_status(pid: str):
    rows = db.query("SELECT * FROM jobs WHERE project_id=? ORDER BY created DESC LIMIT 20", (pid,))
    return {"jobs": [public_job(r) for r in rows], "stages": STAGES}


@app.get("/jobs/{jid}")
def job(jid: str):
    j = db.get("jobs", jid)
    if not j:
        raise HTTPException(404, "job not found")
    return public_job(j, with_log=True)


@app.post("/jobs/{jid}/cancel")
def job_cancel(jid: str):
    j = get_queue().cancel(jid)
    if not j:
        raise HTTPException(404, "job not found")
    return public_job(j)


@app.get("/jobs/{jid}/events")
async def job_events(jid: str, request: Request):
    """Server-sent events with the job's real stage/progress from the worker."""

    async def gen():
        last = None
        while True:
            if await request.is_disconnected():
                break
            j = db.get("jobs", jid)
            if not j:
                yield "event: error\ndata: {\"detail\": \"job not found\"}\n\n"
                break
            pj = public_job(j)
            snap = {k: pj[k] for k in ("id", "kind", "status", "state", "stage", "progress", "error", "error_id", "last")}
            if snap != last:
                yield f"data: {json.dumps(snap, default=str)}\n\n"
                last = snap
            if j["status"] in ("done", "failed", "cancelled"):
                end = {k: pj[k] for k in ("status", "state", "result", "error", "error_id", "elapsed_s")}
                yield f"event: end\ndata: {json.dumps(end, default=str)}\n\n"
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _render_row(r: dict) -> dict:
    rep = r.get("report") or {}
    return {"id": r["id"], "version_id": r["version_id"], "kind": r["kind"], "created": r["created"], "qc_passed": (rep.get("qc") or {}).get("passed"),
            "timings": rep.get("timings"), "size_bytes": rep.get("size_bytes"), "encoder": rep.get("encoder"), "download": f"/renders/{r['id']}/download"}


@app.get("/projects/{pid}/renders")
def renders(pid: str):
    return [_render_row(r) for r in S.list_renders(pid)]


@app.get("/renders/{rid}/download")
def render_download(rid: str):
    r = db.get("renders", rid)
    if not r or not r.get("path") or not Path(r["path"]).exists():
        raise HTTPException(404, "render not found")
    p = safe_path(Path(r["path"]), get_settings().projects_dir)
    return FileResponse(p, media_type="video/mp4", filename=f"final_video_{rid}.mp4" if r["kind"] == "final" else f"preview_{rid}.mp4")


@app.get("/renders/{rid}/report")
def render_report(rid: str):
    r = db.get("renders", rid)
    if not r:
        raise HTTPException(404, "render not found")
    return r["report"]


# ------------------------------------------------------------------------------------ brand kits / benchmarks
class BrandIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    data: dict


@app.post("/brand-kits")
def brand_create(body: BrandIn, request: Request):
    b = S.save_brand_kit(body.name, body.data)
    db.update("brand_kits", b["id"], owner_id=_user(request).id)
    return b


@app.get("/brand-kits")
def brand_list(request: Request):
    u = _user(request)
    rows = S.list_brand_kits()
    return rows if u.is_admin else [r for r in rows if r.get("owner_id") == u.id]


@app.post("/admin/cleanup")
def admin_cleanup(request: Request, dry_run: bool = False):
    if not _user(request).is_admin:
        raise HTTPException(403, "admin only")
    from .cleanup import run_cleanup

    return run_cleanup(dry_run=dry_run)


@app.get("/benchmarks")
def benchmarks():
    return db.query("SELECT * FROM benchmarks ORDER BY created DESC LIMIT 50")


@app.get("/export-history")
def export_history(request: Request):
    u = _user(request)
    rows = db.query("SELECT r.id, r.project_id, p.name AS project, p.owner_id, r.kind, r.created, r.report FROM renders r JOIN projects p ON p.id=r.project_id "
                    "ORDER BY r.created DESC LIMIT 200")
    rows = [r for r in rows if u.is_admin or r["owner_id"] == u.id][:100]
    return [{**_render_row({**r, "version_id": None}), "project": r["project"], "project_id": r["project_id"]} for r in rows]
