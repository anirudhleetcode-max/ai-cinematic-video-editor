"""Application service layer used by the API, the CLI, tests and the benchmark.

Projects · assets (upload, validation, metadata, thumbnails, proxies) · media intelligence (parallel,
cached) · edit plans & versions · revisions & revert · preview/final render with QC auto-fix."""
from __future__ import annotations

import copy
from collections import Counter
import json
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import BinaryIO, Callable

from . import contract as C, db
from .config import get_settings
from .director.context import Asset, ProjectContext
from .director.planner import build_plan
from .director.revise import apply_revision
from .logging import get_logger, log, timed
from .media.analyze import HARD_ISSUES, analyze_video, apply_uniqueness
from .media.inspect import inspect_media
from .media.probe import image_thumbnail, kind_for, make_proxy, probe, thumbnail
from .music.analyze import analyze_music
from .reference.analyze import analyze_reference
from .render.engine import AssetInfo, fix_clipping, render_plan
from .schemas import EditPlan
from .storage import fingerprint, get_storage
from .transcribe import get_transcriber

logger = get_logger("service")
Progress = Callable[[str, float, str], None]
ROLES = {"clip", "broll", "music", "reference", "logo", "voiceover", "sfx", "lut"}


def _noop(stage: str, frac: float, msg: str = "") -> None:
    pass


# ------------------------------------------------------------------------------------ projects
def create_project(name: str, settings: dict | None = None) -> dict:
    pid = db.new_id("prj")
    now = time.time()
    db.insert("projects", id=pid, name=name.strip()[:120] or "Untitled", created=now, updated=now, settings=settings or {})
    get_storage().project_dir(pid)
    return db.get("projects", pid)  # type: ignore[return-value]


def list_projects() -> list[dict]:
    rows = db.query("SELECT * FROM projects ORDER BY updated DESC")
    for r in rows:
        r["n_assets"] = db.query("SELECT COUNT(*) AS n FROM assets WHERE project_id=?", (r["id"],))[0]["n"]
        r["n_versions"] = db.query("SELECT COUNT(*) AS n FROM versions WHERE project_id=?", (r["id"],))[0]["n"]
        thumb = db.query("SELECT id FROM assets WHERE project_id=? AND thumb IS NOT NULL AND role IN ('clip','broll') ORDER BY ordinal LIMIT 1", (r["id"],))
        r["cover_asset_id"] = thumb[0]["id"] if thumb else None
    return rows


def get_project(pid: str) -> dict:
    p = db.get("projects", pid)
    if not p:
        raise KeyError(f"project {pid} not found")
    return p


def touch(pid: str) -> None:
    db.update("projects", pid, updated=time.time())


def delete_project(pid: str) -> None:
    from .jobs import get_queue

    for j in db.query("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','running')", (pid,)):
        get_queue().cancel(j["id"])
    for t in ("assets", "versions", "renders", "jobs"):
        db.execute(f"DELETE FROM {t} WHERE project_id=?", (pid,))
    db.execute("DELETE FROM projects WHERE id=?", (pid,))
    get_storage().delete_project(pid)


def update_settings(pid: str, **kw) -> dict:
    p = get_project(pid)
    s = {**(p.get("settings") or {}), **kw}
    db.update("projects", pid, settings=s, updated=time.time())
    return s


# ------------------------------------------------------------------------------------ assets
def _infer_role(kind: str, filename: str, role: str | None) -> str:
    if role:
        if role not in ROLES:
            raise ValueError(f"invalid role '{role}'")
        return role
    n = filename.lower()
    if kind == "audio":
        return "voiceover" if re.search(r"voice|vo[_\-\s]|narrat", n) else ("sfx" if re.search(r"sfx|whoosh|impact", n) else "music")
    if kind == "image":
        return "logo" if "logo" in n else "clip"
    return "reference" if "reference" in n or n.startswith("ref") else "clip"


def add_asset(pid: str, filename: str, stream: BinaryIO, role: str | None = None) -> dict:
    get_project(pid)
    if filename.lower().endswith(".cube"):
        kind = "lut"
    else:
        kind = kind_for(filename)
    if kind is None:
        raise ValueError(f"unsupported file type: {Path(filename).suffix or filename}")
    role = "lut" if kind == "lut" else _infer_role(kind, filename, role)
    st = get_settings()
    path = get_storage().save_upload(pid, role, filename, stream, st.max_upload_mb << 20)
    return register_asset(pid, path, role, kind, filename)


def validate_cube(path: Path) -> dict:
    """A user .cube LUT is parsed and checked BEFORE FFmpeg ever reads it: size ≤ 8 MB, LUT_3D_SIZE 2–65, exactly
    size³ rows of 3 finite numbers, no other directives than TITLE / DOMAIN_MIN / DOMAIN_MAX / LUT_3D_SIZE."""
    if path.stat().st_size > 8 << 20:
        raise ValueError("LUT file too large (max 8 MB)")
    size, rows = None, 0
    for raw in path.read_text(encoding="utf-8", errors="strict").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head = line.split()[0].upper()
        if head == "LUT_3D_SIZE":
            size = int(line.split()[1])
            if not 2 <= size <= 65:
                raise ValueError("LUT_3D_SIZE must be between 2 and 65")
        elif head in ("TITLE", "DOMAIN_MIN", "DOMAIN_MAX"):
            continue
        else:
            parts = line.split()
            if len(parts) != 3:
                raise ValueError(f"invalid LUT row: {line[:40]!r}")
            vals = [float(x) for x in parts]
            if any(v != v or abs(v) > 1e6 for v in vals):
                raise ValueError("LUT contains non-finite values")
            rows += 1
    if size is None or rows != size ** 3:
        raise ValueError(f"not a valid 3D .cube LUT (size {size}, {rows} rows)")
    return {"lut_size": size}


def register_asset(pid: str, path: Path, role: str, kind: str, filename: str | None = None) -> dict:
    meta: dict = {}
    if kind == "lut":
        try:
            meta = validate_cube(path)
        except ValueError:
            path.unlink(missing_ok=True)
            raise
    if kind != "lut":
        try:
            meta = probe(path)
        except Exception as e:  # noqa: BLE001
            path.unlink(missing_ok=True)
            from .public import scrub

            raise ValueError(f"could not read media file {filename or path.name}: {scrub(str(e), 200)}") from e
        if kind == "video" and not meta.get("has_video"):
            if meta.get("has_audio"):
                kind = "audio"
                role = "music" if role == "clip" else role
            else:
                path.unlink(missing_ok=True)
                raise ValueError(f"{filename}: no video or audio stream")
        if kind == "audio" and not meta.get("has_audio"):
            path.unlink(missing_ok=True)
            raise ValueError(f"{filename}: no audio stream")
        if kind in ("video", "audio") and (meta.get("duration") or 0) > C.MAX_SOURCE_SECONDS:
            path.unlink(missing_ok=True)
            raise ValueError(f"{filename or path.name}: {meta['duration'] / 3600:.1f} h is longer than the {C.MAX_SOURCE_SECONDS // 3600} h source limit")
        if kind in ("video", "audio"):
            rep = inspect_media(path)
            if not rep["ok"]:
                path.unlink(missing_ok=True)
                raise ValueError(f"{filename or path.name}: unusable media ({', '.join(rep['issues'])})")
            P = rep["props"]
            meta["inspection"] = {"warnings": rep["warnings"], "normalize": rep["normalize"],
                                  **{k: P.get(k) for k in ("sar", "sar_value", "color_range", "color_primaries", "color_transfer", "color_space",
                                                            "hdr", "bit_depth", "chroma", "nominal_fps", "avg_fps", "field_order", "audio_streams")},
                                  "vfr": bool((P.get("timing") or {}).get("vfr")),
                                  "fps_from_timestamps": (P.get("timing") or {}).get("fps_from_timestamps")}
            if P.get("display_width"):
                meta["display_width"], meta["display_height"] = P["display_width"], P["display_height"]
                meta["orientation"] = P["orientation"]
    aid = db.new_id("ast")
    thumb = None
    try:
        tp = get_storage().work_path(pid, "thumbs", f"{aid}.jpg")
        if kind == "video":
            thumb = str(thumbnail(path, tp, min(1.0, (meta.get("duration") or 0) * 0.3)))
        elif kind == "image":
            thumb = str(image_thumbnail(path, tp))
    except Exception:  # noqa: BLE001 — thumbnail failure is cosmetic
        thumb = None
    n = db.query("SELECT COUNT(*) AS n FROM assets WHERE project_id=?", (pid,))[0]["n"]
    db.insert("assets", id=aid, project_id=pid, kind=kind, role=role, filename=filename or path.name, path=str(path), fingerprint=fingerprint(path),
              size=path.stat().st_size, meta=meta, thumb=thumb, created=time.time(), ordinal=n, status="uploaded")
    touch(pid)
    return db.get("assets", aid)  # type: ignore[return-value]


def list_assets(pid: str) -> list[dict]:
    rows = db.query("SELECT id, project_id, kind, role, filename, size, meta, thumb, ordinal, status, fingerprint, "
                    "CASE WHEN analysis IS NULL THEN 0 ELSE 1 END AS analyzed FROM assets WHERE project_id=? ORDER BY ordinal", (pid,))
    return rows


def asset_summary(a: dict) -> dict:
    an = a.get("analysis") or {}
    out = {k: a.get(k) for k in ("id", "kind", "role", "filename", "size", "meta", "status", "ordinal")}
    out["has_thumb"] = bool(a.get("thumb"))
    if a.get("role") in ("clip", "broll") and an.get("shots"):
        out["shots"] = [{k: s[k] for k in ("index", "start", "end", "overall_edit_score", "issues", "tags", "scores")} for s in an["shots"]]
        out["best_score"] = max(s["overall_edit_score"] for s in an["shots"])
    if a.get("role") == "music" and an.get("bpm"):
        out["music"] = {k: an.get(k) for k in ("bpm", "duration", "sections", "drops", "buildups")}
    if a.get("role") == "reference" and an:
        out["reference"] = {k: v for k, v in an.items() if k not in ("dominant_colors",)} | {"dominant_colors": an.get("dominant_colors", [])[:5]}
    return out


def delete_asset(aid: str) -> None:
    a = db.get("assets", aid)
    if a:
        Path(a["path"]).unlink(missing_ok=True)
        db.execute("DELETE FROM assets WHERE id=?", (aid,))


# ------------------------------------------------------------------------------------ analysis
def analyze_project(pid: str, mode: str = "fast", progress: Progress = _noop, force: bool = False) -> dict:
    rows = db.query("SELECT * FROM assets WHERE project_id=? ORDER BY ordinal", (pid,))
    todo = [a for a in rows if (force or not a.get("analysis")) and a["role"] in ("clip", "broll", "music", "reference") and a["kind"] in ("video", "audio")]
    st = get_settings()
    t0 = time.perf_counter()
    done = [0]
    stats = {"analyzed": 0, "cached": 0, "proxies": 0}

    def one(a: dict) -> tuple[str, dict]:
        p = Path(a["path"])
        fp = a["fingerprint"]
        before = db.cache_stats()["hits"]
        if a["role"] == "music":
            res = analyze_music(p, fp)
        elif a["role"] == "reference":
            res = analyze_reference(p, fp)
        else:
            res = analyze_video(p, mode, fp)
            # proxy for large sources (used for previews; originals are used for the final render)
            m_ = a["meta"] or {}
            if min(m_.get("display_width") or m_.get("width") or 0, m_.get("display_height") or m_.get("height") or 0) > 720 and mode != "emergency":
                proxy = get_storage().work_path(pid, "proxies", f"{a['id']}.mp4")
                if not proxy.exists():
                    make_proxy(p, proxy, meta=a.get("meta") or None)
                    stats["proxies"] += 1
                db.update("assets", a["id"], proxy=str(proxy))
        if db.cache_stats()["hits"] > before:
            stats["cached"] += 1
        return a["id"], res

    stage_for = {"music": "analyzing_music", "reference": "understanding_reference"}
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, st.analysis_threads)) as ex:
        for aid, res in ex.map(one, todo):
            results[aid] = res
            done[0] += 1
            role = next(a["role"] for a in todo if a["id"] == aid)
            progress(stage_for.get(role, "analyzing_media"), done[0] / max(1, len(todo)), f"{done[0]}/{len(todo)} assets analysed")
    for aid, res in results.items():
        db.update("assets", aid, analysis=res, status="analyzed")
    stats["analyzed"] = len(results)
    # project-level: duplicate detection & uniqueness across every clip
    progress("finding_best_shots", 1.0, "duplicate detection + clip ranking")
    clips = {a["id"]: (db.get("assets", a["id"]) or {}).get("analysis") for a in rows if a["role"] in ("clip", "broll") and a["kind"] == "video"}
    clips = {k: v for k, v in clips.items() if v}
    dups = apply_uniqueness(clips)
    for aid, an in clips.items():
        db.update("assets", aid, analysis=an)
    ref = next((a for a in rows if a["role"] == "reference"), None)
    if ref:
        prof = (db.get("assets", ref["id"]) or {}).get("analysis")
        if prof:
            update_settings(pid, reference_profile=prof, reference_asset_id=ref["id"])
    shots = [s for an in clips.values() for s in an.get("shots", [])]
    summary = {**stats, "seconds": round(time.perf_counter() - t0, 2), "clips": len(clips), "shots": len(shots),
               "usable_shots": sum(1 for s in shots if not (set(s["issues"]) & (HARD_ISSUES | {"duplicate"}))),
               "clean_shots": sum(1 for s in shots if not s["issues"]),
               "unusable_shots": sum(1 for s in shots if set(s["issues"]) & HARD_ISSUES), "duplicate_groups": len(dups),
               "rejected": {k: sum(1 for s in shots if k in s["issues"]) for k in ("blurry", "underexposed", "overexposed", "shaky", "black", "frozen", "duplicate")},
               "issues": dict(Counter(i for s in shots for i in s["issues"])),
               "vision_provider": next((an.get("vision_provider") for an in clips.values() if an.get("vision_provider")), None),
               "speech_detector": next((an.get("speech_detector") for an in clips.values() if an.get("speech_detector")), None),
               "cache": db.cache_stats()}
    update_settings(pid, last_analysis=summary)
    log(logger, "project analysed", project=pid, **{k: v for k, v in summary.items() if not isinstance(v, dict)})
    return summary


# ------------------------------------------------------------------------------------ planning
def _brand(pid: str) -> dict | None:
    s = get_project(pid).get("settings") or {}
    bid = s.get("brand_kit_id")
    if not bid:
        return None
    b = db.get("brand_kits", bid)
    return b["data"] if b else None


def build_context(pid: str, prompt: str, mode: str = "fast") -> ProjectContext:
    p = get_project(pid)
    rows = db.query("SELECT * FROM assets WHERE project_id=? ORDER BY ordinal", (pid,))
    assets = [Asset(a["id"], a["kind"], a["role"], a["filename"], a["path"], a["meta"] or {}, a.get("analysis"), a["ordinal"]) for a in rows]
    settings = p.get("settings") or {}
    return ProjectContext(pid, p["name"], prompt, assets, settings.get("reference_profile"), _brand(pid), mode)


def _save_version(pid: str, plan: EditPlan, prompt: str, kind: str, parent: str | None, changes: list) -> dict:
    n = db.query("SELECT COALESCE(MAX(number),0) AS n FROM versions WHERE project_id=?", (pid,))[0]["n"] + 1
    vid = db.new_id("ver")
    db.insert("versions", id=vid, project_id=pid, number=n, parent_id=parent, prompt=prompt, kind=kind, plan=json.loads(plan.model_dump_json()),
              bible=json.loads(plan.bible.model_dump_json()), changes=changes, created=time.time())
    touch(pid)
    return {"id": vid, "number": n, "kind": kind, "prompt": prompt, "changes": changes}


def _attach_captions(plan: EditPlan, ctx: ProjectContext) -> None:
    if not plan.captions.enabled:
        return
    tr = get_transcriber()
    if not tr.available():
        plan.decisions.append("Captions: no speech-to-text model configured (EDITOR_STT_MODEL_DIR) — captions skipped, not faked.")
        plan.captions.enabled = False
        return
    words = []
    for s in plan.timeline:
        if not s.keep_audio or s.image or abs(s.speed.rate - 1) > 0.05:
            continue
        a = ctx.asset(s.asset_id)
        for wd in tr.words(Path(a.path), s.src_in, s.src_out - s.src_in):
            t0 = s.out_start + (wd["t0"] - s.src_in) / s.speed.rate
            t1 = s.out_start + (wd["t1"] - s.src_in) / s.speed.rate
            if 0 <= t0 < s.out_start + s.out_duration:
                words.append({"w": wd["w"], "t0": round(t0, 3), "t1": round(min(t1, s.out_start + s.out_duration), 3)})
    plan.captions.words = words
    plan.captions.source = "transcription"
    plan.decisions.append(f"Captions: {len(words)} words transcribed offline ({tr.name}).")


def create_edit_plan(pid: str, prompt: str, mode: str = "fast", progress: Progress = _noop) -> dict:
    progress("planning_story", 0.1, "interpreting prompt")
    ctx = build_context(pid, prompt, mode)
    if not ctx.clips:
        raise ValueError("upload at least one video clip or image before generating")
    if any(a.analysis is None for a in ctx.clips if a.kind == "video") or any(a.analysis is None for a in ctx.songs):
        analyze_project(pid, mode, progress)
        ctx = build_context(pid, prompt, mode)
    with timed(logger, "planning", project=pid) as tm:
        plan = build_plan(ctx)
        _attach_captions(plan, ctx)
    progress("building_timeline", 1.0, f"{len(plan.timeline)} shots planned in {tm.seconds:.2f}s")
    v = _save_version(pid, plan, prompt, "generate", None, [{"op": "generate", "domain": "all"}])
    update_settings(pid, last_prompt=prompt, mode=mode)
    return {**v, "plan": json.loads(plan.model_dump_json()), "planning_seconds": round(tm.seconds, 3)}


def list_versions(pid: str) -> list[dict]:
    rows = db.query("SELECT id, number, parent_id, prompt, kind, changes, created FROM versions WHERE project_id=? ORDER BY number", (pid,))
    for r in rows:
        rr = db.query("SELECT id, kind, path, created FROM renders WHERE version_id=? ORDER BY created DESC", (r["id"],))
        r["renders"] = rr
    return rows


def get_version(vid: str) -> dict:
    v = db.get("versions", vid)
    if not v:
        raise KeyError(f"version {vid} not found")
    return v


def latest_version(pid: str) -> dict | None:
    rows = db.query("SELECT * FROM versions WHERE project_id=? ORDER BY number DESC LIMIT 1", (pid,))
    return rows[0] if rows else None


def revise(pid: str, text: str, base_version_id: str | None = None) -> dict:
    base = get_version(base_version_id) if base_version_id else latest_version(pid)
    if not base:
        raise ValueError("no edit plan to revise yet — generate one first")
    plan = EditPlan.model_validate(base["plan"])
    ctx = build_context(pid, (plan.project or {}).get("prompt", ""), plan.mode)
    new, ops = apply_revision(plan, text, ctx)
    if new.captions.enabled and not new.captions.words:
        _attach_captions(new, ctx)
    return {**_save_version(pid, new, text, "revision", base["id"], ops), "plan": json.loads(new.model_dump_json())}


def revert(pid: str, query: str | None = None, version_id: str | None = None) -> dict:
    """'go back to version 2' / 'go back to the version before I changed the music' → new version copying the target."""
    versions = db.query("SELECT * FROM versions WHERE project_id=? ORDER BY number", (pid,))
    if not versions:
        raise ValueError("no versions")
    target = None
    if version_id:
        target = get_version(version_id)
    elif query:
        q = query.lower()
        if m := re.search(r"version\s*(\d+)", q):
            target = next((v for v in versions if v["number"] == int(m.group(1))), None)
        else:
            domain = next((d for d, rx in {"music": r"music|song|track", "color": r"colou?r|grade|warm|cool", "text": r"text|title|typograph|caption",
                                           "timeline": r"pac|energ|cut|scene|shot", "structure": r"intro|ending|length|duration"}.items() if re.search(rx, q)), None)
            if domain:
                changed = [v for v in versions if any(c.get("domain") in (domain, "all") for c in (v.get("changes") or [])) and v["kind"] != "generate"]
                if changed:
                    last = changed[-1]
                    target = next((v for v in versions if v["id"] == last.get("parent_id")), None) or next(
                        (v for v in reversed(versions) if v["number"] < last["number"]), None)
            elif re.search(r"previous|undo|last version|before", q) and len(versions) > 1:
                target = versions[-2]
    if not target:
        raise ValueError(f"could not find a version matching '{query or version_id}'")
    plan = EditPlan.model_validate(target["plan"])
    return {**_save_version(pid, plan, query or f"revert to v{target['number']}", "revert", target["id"],
                            [{"op": "revert", "domain": "all", "to_version": target["number"]}]), "reverted_to": target["number"]}


def inspector(vid: str) -> list[dict]:
    """Human-readable Edit Plan Inspector rows."""
    v = get_version(vid)
    plan = EditPlan.model_validate(v["plan"])
    names = {a["id"]: a["filename"] for a in db.query("SELECT id, filename FROM assets WHERE project_id=?", (v["project_id"],))}
    rows = []
    for k, s in enumerate(plan.timeline):
        txt = [t.text for t in plan.text if t.start < s.out_start + s.out_duration and t.end > s.out_start]
        mus = next((names.get(m.asset_id, m.asset_id) for m in plan.music if m.out_start <= s.out_start < m.out_end), None)
        rows.append({
            "scene": k + 1, "start": round(s.out_start, 2), "end": round(s.out_start + s.out_duration, 2), "section": s.section,
            "clip": names.get(s.asset_id, s.asset_id), "source": f"{s.src_in:.2f}–{s.src_out:.2f}s",
            "speed": "ramp" if s.speed.ramp else f"{s.speed.rate:g}x", "motion": s.motion.preset, "transition": s.transition_in.id,
            "effects": [e.id for e in s.effects], "grade": plan.color_grade.preset, "music": mus,
            "beat": s.beat_index, "text": txt, "audio": "dialogue" if s.keep_audio else "music bed", "reason": s.reason,
        })
    return rows


# ------------------------------------------------------------------------------------ rendering
def _asset_infos(pid: str) -> dict[str, AssetInfo]:
    out = {}
    for a in db.query("SELECT * FROM assets WHERE project_id=?", (pid,)):
        out[a["id"]] = AssetInfo(Path(a["path"]), a["fingerprint"], a["meta"] or {}, Path(a["proxy"]) if a.get("proxy") else None)
    return out


def estimate_render_seconds(plan: EditPlan, preview: bool = False) -> dict:
    """Estimate from *measured* history on this machine (seconds of processing per output second)."""
    kind = "preview" if preview else "final"
    rows = db.query("SELECT report FROM renders WHERE kind=? ORDER BY created DESC LIMIT 10", (kind,))
    ratios = [r["report"]["timings"]["total_s"] / max(1e-3, r["report"].get("duration", 1)) for r in rows
              if r.get("report") and r["report"].get("timings") and r["report"].get("duration")]
    if not ratios:
        return {"seconds": None, "basis": "no measured renders yet on this machine"}
    ratios.sort()
    ratio = ratios[len(ratios) // 2]
    return {"seconds": round(ratio * plan.duration, 1), "basis": f"median of {len(ratios)} measured {kind} renders ({ratio:.2f}s per output second)"}


def render_version(pid: str, vid: str | None = None, preview: bool = False, progress: Progress = _noop, export: dict | None = None) -> dict:
    v = get_version(vid) if vid else latest_version(pid)
    if not v:
        raise ValueError("no edit plan to render")
    plan = EditPlan.model_validate(v["plan"])
    if export:
        plan.export = plan.export.model_copy(update={k: val for k, val in export.items() if k in plan.export.model_fields})
    st = get_settings()
    rid = db.new_id("rnd")
    out = get_storage().work_path(pid, "outputs", f"{'preview' if preview else 'final'}_v{v['number']}_{rid}.mp4")
    work = get_storage().work_path(pid, "work", rid, "x").parent
    assets = _asset_infos(pid)
    attempts = []
    report: dict = {}
    for attempt in range(st.qc_max_retries + 1):
        try:
            report = render_plan(plan, assets, out, work, progress, preview=preview, brand=_brand(pid), prefer_hw=attempt == 0)
        except Exception as e:  # noqa: BLE001 — recovery: CPU encoder, no global effects, then emergency settings
            attempts.append({"attempt": attempt, "error": str(e)[:500]})
            log(logger, "render attempt failed", project=pid, attempt=attempt, error=str(e)[:300])
            if attempt == 0:
                plan.effects_global = []
            elif attempt == 1:
                for s in plan.timeline:
                    s.effects, s.motion.preset, s.stabilize = [], "none", False
                    s.speed.interpolate = False
            if attempt >= st.qc_max_retries:
                raise
            continue
        qc = report["qc"]
        attempts.append({"attempt": attempt, "qc_passed": qc["passed"], "failures": qc["failures"]})
        if qc["passed"]:
            break
        fixed = False
        if "no_clipping" in qc["failures"]:
            progress("quality_check", 0.97, "auto-fix: re-limiting audio")
            fix_clipping(out)
            fixed = True
        if fixed:
            from .qc.check import quality_check
            report["qc"] = quality_check(out, plan, True, report.get("text_violations"), draft=preview)
            attempts.append({"attempt": attempt, "autofix": "audio limiter", "qc_passed": report["qc"]["passed"]})
            if report["qc"]["passed"]:
                break
        if attempt < st.qc_max_retries:
            progress("quality_check", 0.97, f"auto-fix: re-render without effects (QC: {', '.join(qc['failures'])})")
            plan.effects_global = []
            shutil.rmtree(work, ignore_errors=True)
    report["attempts"] = attempts
    report["duration"] = plan.duration
    if not preview and out.exists():
        # measured post-render reviews (never fail the render because a review could not run)
        from .qc.review import reference_match, review_checklist, segment_color_continuity

        t_r = time.perf_counter()
        progress("finalizing", 0.985, "measuring colour continuity, reference match and review checklist")
        shots = {f"{a['id']}:{sh['index']}": sh for a in db.query("SELECT id, analysis FROM assets WHERE project_id=? AND role IN ('clip','broll')", (pid,))
                 for sh in ((a.get("analysis") or {}).get("shots") or [])}
        screen = {s.id for s in plan.timeline if "screen_recording" in (shots.get(f"{s.asset_id}:{s.shot_index}") or {}).get("tags", [])}
        try:
            report["color_continuity"] = segment_color_continuity(out, plan, screen)
        except Exception as e:  # noqa: BLE001
            report["color_continuity"] = {"error": str(e)[:200]}
        ref = (get_project(pid).get("settings") or {}).get("reference_profile")
        if ref and plan.reference_profile_used:
            try:
                report["reference_match"] = reference_match(ref, out, plan)
            except Exception as e:  # noqa: BLE001
                report["reference_match"] = {"error": str(e)[:200]}
        try:
            report["review"] = review_checklist(plan, report.get("qc", {}), report.get("audio", {}), report, shots, report.get("color_continuity"))
        except Exception as e:  # noqa: BLE001
            report["review"] = {"error": str(e)[:200]}
        report.setdefault("timings", {})["reviews_s"] = round(time.perf_counter() - t_r, 2)
    progress("finalizing", 1.0, "done")
    db.insert("renders", id=rid, project_id=pid, version_id=v["id"], kind="preview" if preview else "final", path=str(out), report=report, created=time.time())
    shutil.rmtree(work / "tmp", ignore_errors=True)
    touch(pid)
    return {"id": rid, "version_id": v["id"], "version": v["number"], "path": str(out), "report": report}


def list_renders(pid: str) -> list[dict]:
    return db.query("SELECT id, version_id, kind, path, created, report FROM renders WHERE project_id=? ORDER BY created DESC", (pid,))


def generate(pid: str, prompt: str, mode: str = "fast", preview_first: bool = True, progress: Progress = _noop) -> dict:
    """One-click pipeline: analyse → plan → (preview) → final render → QC."""
    t0 = time.perf_counter()
    times = {}
    a0 = time.perf_counter()
    summary = analyze_project(pid, mode, progress)
    times["analysis_s"] = round(time.perf_counter() - a0, 2)
    p0 = time.perf_counter()
    v = create_edit_plan(pid, prompt, mode, progress)
    times["planning_s"] = round(time.perf_counter() - p0, 2)
    preview = None
    if preview_first:
        r0 = time.perf_counter()
        preview = render_version(pid, v["id"], True, lambda s, f, m: progress(s, f, f"preview: {m}"))
        times["preview_s"] = round(time.perf_counter() - r0, 2)
    r0 = time.perf_counter()
    final = render_version(pid, v["id"], False, progress)
    times["render_s"] = round(time.perf_counter() - r0, 2)
    times["total_s"] = round(time.perf_counter() - t0, 2)
    return {"analysis": summary, "version": {k: v[k] for k in ("id", "number")}, "preview": preview and {"id": preview["id"], "path": preview["path"]},
            "final": {"id": final["id"], "path": final["path"], "qc": final["report"]["qc"]["passed"]}, "timings": times}


# ------------------------------------------------------------------------------------ brand kits
def save_brand_kit(name: str, data: dict) -> dict:
    bid = db.new_id("brd")
    allowed = {k: data[k] for k in ("logo_asset_id", "colors", "background", "font", "title", "end_title", "watermark", "lower_third_style",
                                    "music_asset_id", "intro_asset_id", "outro_asset_id") if k in data}
    db.insert("brand_kits", id=bid, name=name[:80], data=allowed, created=time.time())
    return db.get("brand_kits", bid)  # type: ignore[return-value]


def list_brand_kits() -> list[dict]:
    return db.query("SELECT * FROM brand_kits ORDER BY created DESC")


def copy_plan(plan: EditPlan) -> EditPlan:
    return copy.deepcopy(plan)
