"""Release security audit: exercises a RUNNING stack (production configuration) endpoint by endpoint.

  python scripts/security_audit.py --api http://localhost:8000 --media DIR --data-dir DATA [--logs api.log worker.log]

Checks (each is a real request; nothing is inferred from code patterns):
  authentication on every route · cross-user access with real object ids (GET/POST/PATCH/DELETE, media, SSE, download)
  · path traversal in ids and filenames · shell metacharacters in filenames and prompts (argument arrays, no shell)
  · upload validation (executables, corrupt media, fake LUTs) · error responses (no paths, tracebacks, SQL, commands)
  · production API docs · CORS · admin-only endpoints · token in query string for state-changing requests ·
  tokens / passwords in the server logs.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import tempfile
import time
from pathlib import Path

import httpx

LEAK = re.compile(r"(/tmp/|/home/|/data/|/srv/|/var/|[A-Z]:\\\\|Traceback|File \"|sqlite|SELECT |INSERT |ffmpeg -|ffprobe -|-filter_complex)", re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--media", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--logs", nargs="*", default=[])
    ap.add_argument("--out", default="docs/security_audit.json")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.api, timeout=300)
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: object = "") -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:160]}", flush=True)

    def leak_free(r: httpx.Response) -> bool:
        return not LEAK.search(r.text)

    tag = secrets.token_hex(4)
    pw = {w: f"audit-{w}-{tag}-pw" for w in ("a", "b")}
    tok = {}
    for w in ("a", "b"):
        r = c.post("/auth/register", json={"email": f"audit-{w}-{tag}@example.com", "password": pw[w]})
        tok[w] = r.json()["token"]
    A, B = {"authorization": f"Bearer {tok['a']}"}, {"authorization": f"Bearer {tok['b']}"}
    med = Path(a.media)
    clips = sorted(p for p in med.iterdir() if p.suffix == ".mp4")[:3]
    song = sorted(p for p in med.iterdir() if p.suffix in (".ogg", ".mp3", ".wav"))[0]

    # ---- A's project with real objects (assets, versions, renders, jobs)
    pid = c.post("/projects", json={"name": "audit A"}, headers=A).json()["id"]
    work = Path(tempfile.mkdtemp())
    weird = work / "clip $(id) ; rm -rf ~ `uname` |x.mp4"
    shutil.copy(clips[0], weird)
    traversal = work / "trav.mp4"
    shutil.copy(clips[1], traversal)
    up = []
    for f, name in ((weird, weird.name), (traversal, "../../../../etc/cron.d/evil.mp4"), (clips[2], clips[2].name), (song, song.name)):
        with open(f, "rb") as fh:
            up.append(c.post(f"/projects/{pid}/assets", files=[("files", (name, fh))], headers=A).json())
    assets = c.get(f"/projects/{pid}/assets", headers=A).json()
    stored = [Path(p) for p in Path(a.data_dir).rglob("*") if p.is_file() and ("evil" in p.name or "uname" in p.name or "rm -rf" in p.name)]
    root = Path(a.data_dir).resolve()
    check("filename with shell metacharacters stored as data, inside the data dir", all(root in p.resolve().parents for p in stored) and len(assets) == 4,
          [p.name for p in stored])
    check("path-traversal filename cannot escape the data dir", not Path("/etc/cron.d/evil.mp4").exists() and all(root in p.resolve().parents for p in stored))
    check("no file created outside the data dir by uploads", not any(Path("/etc/cron.d").glob("*evil*")) if Path("/etc/cron.d").exists() else True)
    j = c.post(f"/projects/{pid}/generate", json={"prompt": "A 10 second recap; title \"$(touch /tmp/pwned_" + tag + ")\" `id`; rm -rf /", "preview_first": False},
               headers=A).json()
    t0 = time.time()
    while time.time() - t0 < 900:
        s = c.get(f"/jobs/{j['job_id']}", headers=A).json()
        if s["status"] in ("done", "failed", "cancelled"):
            break
        time.sleep(2)
    check("prompt with shell syntax renders as text, executes nothing", s["status"] == "done" and not Path(f"/tmp/pwned_{tag}").exists(), s["status"])
    vid = c.get(f"/projects/{pid}/versions", headers=A).json()[0]["id"]
    rid = c.get(f"/projects/{pid}/renders", headers=A).json()[0]["id"]
    aid = assets[0]["id"]
    jid = j["job_id"]

    # ---- authentication on every route
    routes = [("GET", "/projects"), ("POST", "/projects"), ("GET", f"/projects/{pid}"), ("GET", f"/projects/{pid}/assets"), ("GET", f"/assets/{aid}/file"),
              ("GET", f"/assets/{aid}/thumbnail"), ("GET", f"/projects/{pid}/versions"), ("GET", f"/versions/{vid}"), ("GET", f"/versions/{vid}/inspector"),
              ("GET", f"/projects/{pid}/renders"), ("GET", f"/renders/{rid}/download"), ("GET", f"/renders/{rid}/report"), ("GET", f"/jobs/{jid}"),
              ("GET", f"/jobs/{jid}/events"), ("POST", f"/jobs/{jid}/cancel"), ("GET", f"/projects/{pid}/search?q=car"), ("GET", f"/projects/{pid}/render-status"),
              ("POST", f"/projects/{pid}/revise"), ("POST", f"/projects/{pid}/render"), ("POST", f"/projects/{pid}/analyze"), ("PATCH", f"/projects/{pid}"),
              ("DELETE", f"/assets/{aid}"), ("DELETE", f"/projects/{pid}"), ("GET", "/export-history"), ("GET", "/brand-kits"), ("GET", "/diagnostics"),
              ("POST", "/admin/cleanup"), ("GET", "/auth/me"), ("GET", "/effects"), ("GET", "/benchmarks")]
    unauth = {f"{m} {u}": c.request(m, u, json={}).status_code for m, u in routes}
    check("every non-public route refuses an unauthenticated request (401)", all(v == 401 for v in unauth.values()), {k: v for k, v in unauth.items() if v != 401})
    bad = {f"{m} {u}": c.request(m, u, json={}, headers={"authorization": "Bearer cts_forged" + tag}).status_code for m, u in routes[:6]}
    check("forged token refused", all(v == 401 for v in bad.values()), bad)

    # ---- user B against A's real ids (every route that names an object)
    cross = {f"{m} {u}": c.request(m, u, json={"text": "make it warmer", "name": "x"}, headers=B).status_code
             for m, u in routes if any(x in u for x in (pid, aid, vid, rid, jid))}
    check("user B gets 404 on every one of A's objects (read, write, delete, media, SSE, download)", all(v == 404 for v in cross.values()),
          {k: v for k, v in cross.items() if v != 404})
    check("A's project still intact after B's attempts", c.get(f"/projects/{pid}", headers=A).status_code == 200 and len(c.get(f"/projects/{pid}/assets", headers=A).json()) == 4)
    check("B's project list does not include A's project", all(p["id"] != pid for p in c.get("/projects", headers=B).json()))
    check("B's export history does not include A's renders", all(r["id"] != rid for r in c.get("/export-history", headers=B).json()))
    ids = {"pid": "prj_" + "0" * 12, "aid": "../../../etc/passwd", "rid": "..%2F..%2Fetc%2Fpasswd", "jid": "job_' OR '1'='1"}
    trav = {u: c.get(u, headers=A).status_code for u in (f"/projects/{ids['pid']}", f"/assets/{ids['aid']}/file", f"/renders/{ids['rid']}/download",
                                                          f"/jobs/{ids['jid']}", "/library/preview/color-presets/..%2F..%2F..%2Fetc%2Fpasswd")}
    check("path traversal / SQL-ish ids are 404, never file contents", all(v in (404, 400, 422) for v in trav.values()) and "root:" not in "".join(
        c.get(u, headers=A).text for u in trav), trav)
    q = c.post(f"/projects/{pid}/revise?access_token={tok['a']}", json={"text": "warmer"})
    check("?access_token= is not accepted for state-changing requests", q.status_code == 401, q.status_code)

    # ---- upload validation
    def upload(name: str, data: bytes) -> dict:
        return c.post(f"/projects/{pid}/assets", files=[("files", (name, data))], headers=A).json()

    r1, r2, r3 = upload("tool.sh", b"#!/bin/sh\nid\n"), upload("fake.mp4", b"not a video at all"), upload("evil.cube", b"LUT_3D_SIZE 2\n../../etc/passwd\n")
    check("executable / unknown type refused", not r1["assets"] and r1["errors"], r1["errors"])
    check("corrupt media refused with a clean reason", not r2["assets"] and r2["errors"] and not LEAK.search(json.dumps(r2)), r2["errors"])
    check("malformed LUT refused before FFmpeg reads it", not r3["assets"] and r3["errors"], r3["errors"])

    # ---- error responses
    errs = [c.get("/projects/nope", headers=A), c.post("/projects", content=b"{not json", headers={**A, "content-type": "application/json"}),
            c.post(f"/projects/{pid}/render", json={"export": {"bogus": 1}}, headers=A), c.get(f"/jobs/job_{'0' * 12}", headers=A),
            c.post("/auth/login", json={"email": "x", "password": "y"}), c.get(f"/renders/{rid}/report", headers=A), c.get(f"/versions/{vid}", headers=A),
            c.get(f"/jobs/{jid}", headers=A)]
    check("error and data responses contain no paths, tracebacks, SQL or command lines", all(leak_free(r) for r in errs),
          [r.request.url.path for r in errs if not leak_free(r)])

    # ---- production surface
    docs = {u: c.get(u).status_code for u in ("/docs", "/redoc", "/openapi.json")}
    check("interactive API docs disabled in production", all(v == 404 for v in docs.values()), docs)
    adm = {u: c.request(m, u, headers=A).status_code for m, u in (("GET", "/diagnostics"), ("POST", "/admin/cleanup"))}
    check("diagnostics / admin endpoints refuse non-admin users (403)", all(v == 403 for v in adm.values()), adm)
    ev = c.options("/projects", headers={"origin": "https://evil.example", "access-control-request-method": "GET"})
    ok = c.options("/projects", headers={"origin": "http://localhost:3000", "access-control-request-method": "GET"})
    check("CORS: unknown origin not allowed, configured origin allowed",
          "access-control-allow-origin" not in ev.headers and ok.headers.get("access-control-allow-origin") == "http://localhost:3000",
          {"evil": ev.headers.get("access-control-allow-origin"), "configured": ok.headers.get("access-control-allow-origin")})
    h = c.get("/health")
    check("public /health exposes no paths or secrets", leak_free(h) and "token" not in h.text.lower(), list(h.json().get("components", {})))

    # ---- logs
    text = "".join(Path(p).read_text(errors="ignore") for p in a.logs if Path(p).exists())
    leaked = [n for n, v in (("token a", tok["a"]), ("token b", tok["b"]), ("password a", pw["a"]), ("password b", pw["b"])) if v in text]
    check("no tokens or passwords in the server logs", bool(a.logs) and not leaked, leaked or f"{len(text)} bytes of logs scanned")
    c.delete(f"/projects/{pid}", headers=A)
    out = {"label": "MEASURED against a running stack", "api": a.api, "checks": checks, "passed": sum(x["pass"] for x in checks), "failed": sum(not x["pass"] for x in checks)}
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(f"SECURITY AUDIT: {out['passed']} passed, {out['failed']} failed")
    return 0 if not out["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
