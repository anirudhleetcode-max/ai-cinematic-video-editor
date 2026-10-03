"""Job durability: a separate worker process executes queued jobs, stale jobs are recovered, retries are bounded."""
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


def test_recover_requeues_stale_and_fails_after_max_attempts():
    from editor import db
    from editor.jobs import get_queue

    q = get_queue()
    old = time.time() - 3600
    a, b = db.new_id("job"), db.new_id("job")
    for jid, attempts in ((a, 1), (b, 9)):
        db.insert("jobs", id=jid, project_id=None, kind="analyze", status="running", stage="rendering", progress=0.5, params={}, log=[],
                  created=old, started=old, heartbeat=old, attempts=attempts, worker_id="deadhost:1:abc")
    q.recover()
    assert db.get("jobs", a)["status"] in ("queued", "running", "done", "failed")  # re-queued (a live worker may pick it up at once)
    assert db.get("jobs", a)["worker_id"] != "deadhost:1:abc"
    jb = db.get("jobs", b)
    assert jb["status"] == "failed" and "retry limit" in jb["error"]


def test_separate_worker_process_runs_jobs(tmp_path):
    """API and worker as separate processes sharing only the data directory (as in docker-compose)."""
    data = tmp_path / "data"
    env = {**os.environ, "EDITOR_DATA_DIR": str(data), "EDITOR_ROLE": "worker", "EDITOR_CLEANUP": "0", "EDITOR_ENV": "development"}
    # the "API side": create the DB schema and enqueue through the same code path, in another process
    enqueue = ("from editor import db, service as S; from editor.jobs import get_queue; db.connect(); "
               "p = S.create_project('w'); j = get_queue().submit('analyze', p['id'], {'project_id': p['id']}); print(j['id'])")
    jid = subprocess.run([sys.executable, "-c", enqueue], env={**env, "EDITOR_ROLE": "api"}, capture_output=True, text=True, timeout=120, check=True).stdout.split()[-1]
    w = subprocess.Popen([sys.executable, "-m", "editor.worker"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        status = None
        for _ in range(240):
            with sqlite3.connect(data / "editor.sqlite3") as c:
                row = c.execute("SELECT status, worker_id FROM jobs WHERE id=?", (jid,)).fetchone()
            status = row[0]
            if status in ("done", "failed"):
                break
            time.sleep(0.25)
        assert status == "done", row
        assert row[1] and str(w.pid) in row[1]  # claimed by the worker process
        hb = data / ".worker-heartbeat"
        for _ in range(40):
            if hb.exists():
                break
            time.sleep(0.25)
        assert hb.exists()
    finally:
        w.terminate()
        w.wait(timeout=30)
