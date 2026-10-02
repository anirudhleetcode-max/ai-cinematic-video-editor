"""HTTP API (FastAPI). Run: `uvicorn editor.api:app --port 8000`."""
from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import db, service as S
from .config import get_settings
from .hw import diagnostics
from .jobs import STAGES, get_queue
from .logging import get_logger
from .media.probe import AUDIO_EXT, IMAGE_EXT, VIDEO_EXT
from .previews import preview as library_preview
from .proc import safe_filename, safe_path
from .registry import REGISTRIES, library_stats, search_library, templates
from .storage import UploadTooLarge, get_storage

logger = get_logger("api")


@asynccontextmanager
async def _lifespan(_: FastAPI):
    db.connect()
    get_queue().start()
    yield


app = FastAPI(title="Autonomous AI Video Editor", version="0.1.0", lifespan=_lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(get_settings().cors_origins) + ["http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(KeyError)
async def _keyerr(_: Request, e: KeyError):
    return JSONResponse(status_code=404, content={"detail": str(e).strip("'")})


@app.exception_handler(ValueError)
async def _valerr(_: Request, e: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(e)})


# ------------------------------------------------------------------------------------ health
@app.get("/health")
def health():
    d = diagnostics()
    return {"ok": bool(d["ffmpeg"] and d["ffprobe"]), "ffmpeg": d["ffmpeg"], "ffprobe": d["ffprobe"], "encoder": d["selected_encoder"],
            "hardware_encoding": d["hardware_encoding"], "time": time.time()}


@app.get("/diagnostics")
def diag():
    if os.environ.get("EDITOR_ENV", "development") != "development":
        raise HTTPException(403, "diagnostics are only available in development")
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
def create_project(body: ProjectIn):
    return S.create_project(body.name, body.settings)


@app.get("/projects")
def list_projects():
    return S.list_projects()


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
def patch_project(pid: str, body: SettingsIn):
    return S.update_settings(pid, **body.model_dump(exclude_none=True))


# ------------------------------------------------------------------------------------ assets
ALLOWED = VIDEO_EXT | AUDIO_EXT | IMAGE_EXT | {".cube"}


@app.post("/projects/{pid}/assets")
async def upload_assets(pid: str, files: list[UploadFile] = File(...), role: str | None = Form(None)):
    S.get_project(pid)
    out, errors = [], []
    for f in files:
        name = safe_filename(f.filename or "upload")
        if Path(name).suffix.lower() not in ALLOWED:
            errors.append({"file": f.filename, "error": f"unsupported type {Path(name).suffix}"})
            continue
        try:
            a = await asyncio.to_thread(S.add_asset, pid, name, f.file, role)
            out.append(S.asset_summary(a))
        except (ValueError, UploadTooLarge) as e:
            errors.append({"file": f.filename, "error": str(e)})
    return {"assets": out, "errors": errors}


class UploadInit(BaseModel):
    filename: str
    size: int = Field(gt=0)
    role: str | None = None


@app.post("/projects/{pid}/uploads")
def init_upload(pid: str, body: UploadInit):
    """Resumable upload: init → PUT chunks with ?offset= → complete."""
    S.get_project(pid)
    if Path(body.filename).suffix.lower() not in ALLOWED:
        raise HTTPException(400, f"unsupported type {Path(body.filename).suffix}")
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
    rows = db.query("SELECT id, kind, status, stage, progress, error, created, started, finished FROM jobs WHERE project_id=? ORDER BY created DESC LIMIT 20", (pid,))
    return {"jobs": rows, "stages": STAGES}


@app.get("/jobs/{jid}")
def job(jid: str):
    j = db.get("jobs", jid)
    if not j:
        raise HTTPException(404, "job not found")
    return j


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
            snap = {k: j[k] for k in ("id", "kind", "status", "stage", "progress", "error")}
            snap["last"] = (j.get("log") or [])[-1:] if j.get("log") else []
            if snap != last:
                yield f"data: {json.dumps(snap, default=str)}\n\n"
                last = snap
            if j["status"] in ("done", "failed"):
                yield f"event: end\ndata: {json.dumps({'status': j['status'], 'result': j.get('result'), 'error': j.get('error')}, default=str)}\n\n"
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
def brand_create(body: BrandIn):
    return S.save_brand_kit(body.name, body.data)


@app.get("/brand-kits")
def brand_list():
    return S.list_brand_kits()


@app.get("/benchmarks")
def benchmarks():
    return db.query("SELECT * FROM benchmarks ORDER BY created DESC LIMIT 50")


@app.get("/export-history")
def export_history():
    rows = db.query("SELECT r.id, r.project_id, p.name AS project, r.kind, r.created, r.report FROM renders r JOIN projects p ON p.id=r.project_id "
                    "ORDER BY r.created DESC LIMIT 100")
    return [{**_render_row({**r, "version_id": None}), "project": r["project"], "project_id": r["project_id"]} for r in rows]
