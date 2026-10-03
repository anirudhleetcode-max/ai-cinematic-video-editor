"""Security before internet deployment: authentication, ownership isolation, rate / job / quota limits, input validation."""
import os
import time
from pathlib import Path

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


def test_requires_token_and_isolates_users(token_env, dataset):
    from editor import auth

    ua, ta = auth.create_user("alice")
    ub, tb = auth.create_user("bob")
    A, B = {"authorization": f"Bearer {ta}"}, {"authorization": f"Bearer {tb}"}
    with _client() as c:
        assert c.get("/health").status_code == 200  # public
        assert c.get("/projects").status_code == 401
        assert c.get("/projects", headers={"authorization": "Bearer nope"}).status_code == 401
        pid = c.post("/projects", json={"name": "Alice film"}, headers=A).json()["id"]
        with open(dataset["clips"][0], "rb") as fh:
            up = c.post(f"/projects/{pid}/assets", files=[("files", ("a.mp4", fh, "video/mp4"))], headers=A).json()
        aid = up["assets"][0]["id"]
        # bob sees nothing of alice's: list filtered, direct access answers 404 (existence not leaked)
        assert all(p["id"] != pid for p in c.get("/projects", headers=B).json())
        for url in (f"/projects/{pid}", f"/projects/{pid}/assets", f"/assets/{aid}/file", f"/assets/{aid}/thumbnail", f"/projects/{pid}/versions"):
            assert c.get(url, headers=B).status_code == 404, url
        assert c.post(f"/projects/{pid}/analyze", json={}, headers=B).status_code == 404
        assert c.delete(f"/projects/{pid}", headers=B).status_code == 404
        # alice can; query token works for GET media URLs only
        assert c.get(f"/projects/{pid}", headers=A).status_code == 200
        assert c.get(f"/assets/{aid}/thumbnail?access_token={ta}").status_code == 200
        assert c.post(f"/projects/{pid}/analyze?access_token={ta}", json={}).status_code == 401
        # disabled users lose access immediately
        from editor import db

        db.update("users", ub["id"], disabled=1)
        assert c.get("/projects", headers=B).status_code == 401


def test_rate_job_and_quota_limits(token_env, monkeypatch, dataset):
    from editor import auth, config

    monkeypatch.setenv("EDITOR_RATE_LIMIT_PER_MIN", "5")
    monkeypatch.setenv("EDITOR_MAX_JOBS_PER_USER", "0")
    monkeypatch.setenv("EDITOR_USER_QUOTA_GB", "0.000001")
    config.reset_settings()
    _, t = auth.create_user("carol")
    H = {"authorization": f"Bearer {t}"}
    with _client() as c:
        pid = c.post("/projects", json={"name": "limits"}, headers=H).json()["id"]
        with open(dataset["clips"][0], "rb") as fh:
            r = c.post(f"/projects/{pid}/assets", files=[("files", ("a.mp4", fh, "video/mp4"))], headers=H)
        assert r.status_code == 413  # quota
        assert c.post(f"/projects/{pid}/generate", json={"prompt": "10 second edit"}, headers=H).status_code == 429  # job limit
        codes = [c.get("/projects", headers=H).status_code for _ in range(8)]
        assert 429 in codes  # rate limit


def test_production_refuses_no_auth(monkeypatch):
    from editor import auth, config

    monkeypatch.setenv("EDITOR_ENV", "production")
    monkeypatch.setenv("EDITOR_AUTH", "none")
    config.reset_settings()
    try:
        with pytest.raises(RuntimeError):
            auth.check_config()
    finally:
        monkeypatch.delenv("EDITOR_ENV")
        monkeypatch.delenv("EDITOR_AUTH")
        config.reset_settings()


def test_cube_validation(tmp_path):
    from editor.service import validate_cube

    good = tmp_path / "g.cube"
    good.write_text("TITLE \"t\"\nLUT_3D_SIZE 2\n" + "\n".join("0.0 0.5 1.0" for _ in range(8)) + "\n")
    assert validate_cube(good)["lut_size"] == 2
    for body in ("LUT_3D_SIZE 2\n0 0 0\n", "LUT_3D_SIZE 99\n", "LUT_3D_SIZE 2\n" + "\n".join("0 0 nan" for _ in range(8)),
                 "LUT_3D_SIZE 2\n" + "\n".join("0 0" for _ in range(8)), "LUT_1D_SIZE 4\n0 0 0\n"):
        bad = tmp_path / f"b{abs(hash(body))}.cube"
        bad.write_text(body)
        with pytest.raises(ValueError):
            validate_cube(bad)


def test_filter_path_escaping():
    from editor.proc import ff_path

    assert ff_path("C:/Users/me/data/x.cube") == "'C\\:/Users/me/data/x.cube'"
    assert ff_path(Path("/srv/data/x.ass")) == "'/srv/data/x.ass'"
    with pytest.raises(ValueError):
        ff_path("/srv/John's data/x.cube")


def test_media_processes_always_time_out(monkeypatch):
    import subprocess

    from editor import config, proc

    monkeypatch.setenv("EDITOR_PROCESS_TIMEOUT", "1")
    config.reset_settings()
    try:
        t = time.perf_counter()
        with pytest.raises(subprocess.TimeoutExpired):
            proc.run([config.get_settings().ffmpeg, "-v", "error", "-re", "-f", "lavfi", "-i", "anullsrc", "-t", "30", "-f", "null", "-"])
        assert time.perf_counter() - t < 10
    finally:
        monkeypatch.delenv("EDITOR_PROCESS_TIMEOUT")
        config.reset_settings()


def test_cleanup_keeps_newest_final(tmp_path):
    from editor import db, service as S
    from editor.cleanup import run_cleanup

    p = S.create_project("cleanup")
    old = time.time() - 90 * 86400
    files = []
    for i, kind in enumerate(("final", "final", "preview")):
        f = tmp_path / f"r{i}.mp4"
        f.write_bytes(b"x" * 100)
        files.append(f)
        db.insert("renders", id=f"rnd_c{i}{os.getpid()}", project_id=p["id"], version_id=None, kind=kind, path=str(f), report={}, created=old + i)
    st = run_cleanup(retention_days=30)
    assert st["renders_deleted"] == 2
    assert files[1].exists() and not files[0].exists() and not files[2].exists()  # newest final kept
