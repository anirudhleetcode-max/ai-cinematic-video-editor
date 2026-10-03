"""Accounts (register / login / sessions), sanitised job responses, cancellation, production refusals, health."""
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def token_env(monkeypatch):
    from editor import config

    monkeypatch.setenv("EDITOR_AUTH", "token")
    monkeypatch.setenv("EDITOR_CLEANUP", "0")
    config.reset_settings()
    yield
    config.reset_settings()


def _client():
    from editor.api import app

    return TestClient(app)


def test_password_hashing():
    from editor import auth

    h = auth.hash_password("correct horse battery")
    assert h.startswith("scrypt$") and "correct" not in h
    assert auth.verify_password("correct horse battery", h)
    assert not auth.verify_password("correct horse batterx", h)
    assert not auth.verify_password("x", "garbage") and not auth.verify_password("x", None)
    assert auth.hash_password("same password!") != auth.hash_password("same password!")  # salted


def test_register_login_sessions_and_isolation(token_env, monkeypatch):
    from editor import auth, db

    monkeypatch.setattr(auth, "limiter", auth.RateLimiter())

    with _client() as c:
        assert c.get("/auth/config").json() == {"auth": "token", "registration": True}
        assert c.post("/auth/register", json={"email": "not-an-email", "password": "longenough1"}).status_code == 400
        assert c.post("/auth/register", json={"email": "a@example.com", "password": "short"}).status_code == 400
        r = c.post("/auth/register", json={"email": "A@Example.com", "password": "alice-password-1", "name": "Alice"})
        assert r.status_code == 200, r.text
        ta = r.json()["token"]
        assert ta.startswith("cts_")
        assert c.post("/auth/register", json={"email": "a@example.com", "password": "another-pass-1"}).status_code == 409
        assert c.post("/auth/login", json={"email": "a@example.com", "password": "wrong-password"}).status_code == 401
        assert c.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"}).status_code == 401
        A = {"authorization": f"Bearer {ta}"}
        assert c.get("/auth/me", headers=A).json()["name"] == "Alice"
        tb = c.post("/auth/register", json={"email": "b@example.com", "password": "bob-password-12"}).json()["token"]
        B = {"authorization": f"Bearer {tb}"}
        pid = c.post("/projects", json={"name": "A"}, headers=A).json()["id"]
        assert c.get(f"/projects/{pid}", headers=B).status_code == 404
        assert all(p["id"] != pid for p in c.get("/projects", headers=B).json())
        # only hashes are stored
        row = db.query("SELECT password_hash FROM users WHERE email='a@example.com'")[0]
        assert "alice-password-1" not in row["password_hash"]
        assert not db.query("SELECT 1 FROM sessions WHERE token_hash=?", (ta,))
        # second login gives a second session; logout revokes only that one
        t2 = c.post("/auth/login", json={"email": "a@example.com", "password": "alice-password-1"}).json()["token"]
        assert c.post("/auth/logout", headers={"authorization": f"Bearer {t2}"}).status_code == 200
        assert c.get("/auth/me", headers={"authorization": f"Bearer {t2}"}).status_code == 401
        assert c.get("/auth/me", headers=A).status_code == 200
        # expired sessions are refused
        db.execute("UPDATE sessions SET expires=? WHERE token_hash=?", (time.time() - 1, auth._hash(ta)))
        assert c.get("/auth/me", headers=A).status_code == 401


def test_login_rate_limited(token_env, monkeypatch):
    from editor import auth, config

    monkeypatch.setattr(auth, "limiter", auth.RateLimiter())  # fresh buckets (earlier tests used the same client IP)
    monkeypatch.setenv("EDITOR_LOGIN_RATE_PER_MIN", "3")
    config.reset_settings()
    with _client() as c:
        codes = [c.post("/auth/login", json={"email": "x@example.com", "password": "whatever-123"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and 429 in codes[3:]


def test_registration_can_be_closed(token_env, monkeypatch):
    from editor import auth, config

    monkeypatch.setattr(auth, "limiter", auth.RateLimiter())
    monkeypatch.setenv("EDITOR_ALLOW_REGISTRATION", "0")
    config.reset_settings()
    with _client() as c:
        assert c.post("/auth/register", json={"email": "c@example.com", "password": "carol-password-1"}).status_code == 403


def test_production_refuses_unsafe_config(monkeypatch):
    from editor import auth, config

    monkeypatch.setenv("EDITOR_ENV", "production")
    monkeypatch.delenv("EDITOR_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("EDITOR_AUTH", "token")
    config.reset_settings()
    with pytest.raises(RuntimeError, match="set explicitly"):
        auth.check_config()
    monkeypatch.setenv("EDITOR_CORS_ORIGINS", "https://cutroom.example.com")
    cases = [
        ([("EDITOR_AUTH", "none")], "EDITOR_AUTH"),
        ([("EDITOR_AUTH", "token"), ("EDITOR_CORS_ORIGINS", "*")], "'\\*'"),
        ([("EDITOR_AUTH", "token"), ("EDITOR_CORS_ORIGINS", "http://cutroom.example.com")], "https"),
        ([("EDITOR_AUTH", "token"), ("EDITOR_RATE_LIMIT_PER_MIN", "0")], "rate limits"),
    ]
    for env, needle in cases:
        for k, v in env:
            monkeypatch.setenv(k, v)
        config.reset_settings()
        with pytest.raises(RuntimeError, match=needle):
            auth.check_config()
        for k, _ in env:
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("EDITOR_AUTH", "token")
    monkeypatch.setenv("EDITOR_CORS_ORIGINS", "https://cutroom.example.com")
    config.reset_settings()
    auth.check_config()
    config.reset_settings()


def test_job_responses_hide_internals(token_env):
    """A failed job's traceback and absolute paths stay on the server; the client gets a scrubbed message + reference."""
    from editor import auth, db
    from editor.jobs import get_queue
    from editor.public import public_job

    u, tok = auth.create_user("alice")
    H = {"authorization": f"Bearer {tok}"}
    q = get_queue()
    q.register("boom", lambda p, pr: (_ for _ in ()).throw(FileNotFoundError("/srv/cutroom/data/projects/prj_x/secret/clip.mp4 missing")))
    j = q.run_sync("boom", None, {})
    db.update("jobs", j["id"], owner_id=u["id"])
    with _client() as c:
        body = c.get(f"/jobs/{j['id']}", headers=H).json()
    assert body["status"] == "failed" and body["state"] == "failed" and body["error_id"] == j["id"]
    text = str(body)
    assert "/srv/cutroom" not in text and "Traceback" not in text and "clip.mp4" in body["error"]
    assert "Traceback" in str(db.get("jobs", j["id"])["log"])  # still available to operators
    # results never carry server paths
    assert "path" not in public_job({**j, "status": "done", "result": {"render_id": "r", "path": "/srv/x/final.mp4"}})["result"]


def test_job_states_and_cancel(token_env):
    from editor import auth, db
    from editor.jobs import JobCancelled, get_queue
    from editor.public import job_state

    assert job_state({"status": "running", "kind": "render", "stage": "rendering"}) == "rendering"
    assert job_state({"status": "running", "kind": "preview", "stage": "rendering"}) == "previewing"
    assert job_state({"status": "running", "kind": "generate", "stage": "quality_check"}) == "validating"
    assert job_state({"status": "running", "kind": "analyze", "stage": "analyzing_media"}) == "analyzing"
    assert job_state({"status": "done", "kind": "render"}) == "completed"
    u, tok = auth.create_user("alice")
    H = {"authorization": f"Bearer {tok}"}
    q = get_queue()
    seen = []

    def slow(p, pr):
        for i in range(200):
            pr("rendering", i / 200, "working")
            seen.append(i)
            time.sleep(0.01)
        return {}

    q.register("slow", slow)
    with _client() as c:
        j = q.submit("slow", None, {})
        db.update("jobs", j["id"], owner_id=u["id"])
        for _ in range(200):
            if db.get("jobs", j["id"])["status"] == "running":
                break
            time.sleep(0.02)
        r = c.post(f"/jobs/{j['id']}/cancel", headers=H)
        assert r.status_code == 200
        for _ in range(200):
            if db.get("jobs", j["id"])["status"] == "cancelled":
                break
            time.sleep(0.02)
        assert db.get("jobs", j["id"])["status"] == "cancelled" and len(seen) < 200
        assert c.get(f"/jobs/{j['id']}", headers=H).json()["state"] == "cancelled"
        # a queued job is cancelled before it runs
        jid = db.new_id("job")
        db.insert("jobs", id=jid, project_id=None, kind="slow", status="queued", stage="queued", progress=0.0, params={}, log=[], created=time.time(), owner_id=u["id"])
        assert c.post(f"/jobs/{jid}/cancel", headers=H).json()["state"] == "cancelled"
        q._execute(jid)
        assert db.get("jobs", jid)["status"] == "cancelled"
    assert JobCancelled


def test_health_reports_components():
    with _client() as c:
        r = c.get("/health")
        body = r.json()
    comps = body["components"]
    assert set(comps) >= {"database", "storage", "worker", "queue", "ffmpeg", "models"}
    assert comps["database"]["ok"] and comps["ffmpeg"]["ok"] and comps["worker"]["threads_alive"] >= 1
    assert r.status_code == (200 if body["ok"] else 503)
    assert "/" not in str({k: v for k, v in comps.items() if k != "models"})  # no filesystem paths


def test_unhandled_errors_return_reference_only(monkeypatch):
    from editor import service as S
    from editor.api import app

    def broken(*a, **k):
        raise RuntimeError("database at /var/lib/cutroom/secret.sqlite3 is locked")

    monkeypatch.setattr(S, "list_projects", broken)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/projects")
    assert r.status_code == 500 and r.json()["detail"] == "internal error" and r.json()["error_id"].startswith("err")
    assert "/var/lib" not in r.text


def test_tokens_never_reach_the_logs(token_env, caplog):
    """Media / download / SSE URLs carry ?access_token=; the request log records the path only (uvicorn's own access
    log is disabled for this reason)."""
    import logging

    from editor import auth

    u, tok = auth.create_user("alice")
    caplog.set_level(logging.DEBUG)
    with _client() as c:
        c.get(f"/projects?access_token={tok}")
        c.post("/auth/login", json={"email": "x@example.com", "password": "secret-password-1"})
    text = "\n".join(f"{r.getMessage()} {getattr(r, 'fields', '')}" for r in caplog.records)
    assert "request" in text and "/projects" in text
    assert tok not in text and "secret-password-1" not in text
