"""Job durability against the running docker-compose stack (release gate, Phase 9).

  python scripts/compose_durability.py --media DIR [--api http://localhost:8000] [--out docs/compose_durability.json]

1. worker killed mid-job (docker compose kill worker) → restarted → the job is re-queued from its stale heartbeat
   and completes on the new worker
2. cancellation of a running job through the API stops it in the separate worker container
3. a completed job and its output survive `docker compose restart` of api + worker (persisted on the volume)
"""
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import time
from pathlib import Path

import httpx

VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
AUDIO = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}


def compose(*a: str) -> None:
    subprocess.run(["docker", "compose", *a], check=True, capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--media", required=True)
    ap.add_argument("--out", default="docs/compose_durability.json")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.api, timeout=300)
    tag = secrets.token_hex(4)
    tok = c.post("/auth/register", json={"email": f"dur-{tag}@example.com", "password": f"durability-{tag}"}).json()["token"]
    H = {"authorization": f"Bearer {tok}"}
    pid = c.post("/projects", json={"name": "durability"}, headers=H).json()["id"]
    med = Path(a.media)
    for p in sorted(x for x in med.iterdir() if x.suffix.lower() in VIDEO)[:6]:
        with open(p, "rb") as fh:
            c.post(f"/projects/{pid}/assets", files=[("files", (p.name, fh))], headers=H).raise_for_status()
    song = sorted(x for x in med.iterdir() if x.suffix.lower() in AUDIO)[0]
    with open(song, "rb") as fh:
        c.post(f"/projects/{pid}/assets", files=[("files", (song.name, fh))], data={"role": "music"}, headers=H).raise_for_status()

    def job(jid):
        return c.get(f"/jobs/{jid}", headers=H).json()

    def wait(jid, states, limit=1800):
        t0 = time.time()
        while time.time() - t0 < limit:
            j = job(jid)
            if j["status"] in states:
                return j
            time.sleep(1)
        raise TimeoutError(jid)

    rep: dict = {"label": "MEASURED against docker compose (api + worker + web containers)"}
    # 1. kill the worker mid-job
    jid = c.post(f"/projects/{pid}/generate", json={"prompt": "A 20 second energetic recap cut to the music", "preview_first": False}, headers=H).json()["job_id"]
    wait(jid, ("running",))
    while job(jid)["progress"] < 0.2:
        time.sleep(1)
    before = job(jid)
    t_kill = time.time()
    compose("kill", "worker")
    time.sleep(3)
    compose("up", "-d", "worker")
    done = wait(jid, ("done", "failed", "cancelled"), 2400)
    rep["worker_killed_mid_job"] = {"progress_when_killed": before["progress"], "stage_when_killed": before["stage"],
                                    "final_status": done["status"], "seconds_from_kill_to_done": round(time.time() - t_kill, 1),
                                    "error": done.get("error"), "pass": done["status"] == "done"}
    print(json.dumps(rep["worker_killed_mid_job"]), flush=True)
    # 2. cancel a running job
    jid2 = c.post(f"/projects/{pid}/render", json={}, headers=H).json()["job_id"]
    wait(jid2, ("running",))
    time.sleep(3)
    c.post(f"/jobs/{jid2}/cancel", headers=H).raise_for_status()
    t_c = time.time()
    j2 = wait(jid2, ("done", "failed", "cancelled"), 600)
    rep["cancel_running_job"] = {"final_status": j2["status"], "state": j2.get("state"), "seconds_to_stop": round(time.time() - t_c, 1),
                                 "pass": j2["status"] == "cancelled"}
    print(json.dumps(rep["cancel_running_job"]), flush=True)
    # 3. persistence across a restart
    final = next(r for r in c.get(f"/projects/{pid}/renders", headers=H).json() if r["kind"] == "final")
    compose("restart", "api", "worker")
    for _ in range(60):
        try:
            if c.get("/health").status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(2)
    d = c.get(final["download"], headers=H)
    rep["persistence_after_restart"] = {"job_status": job(jid)["status"], "download_status": d.status_code, "bytes": len(d.content),
                                        "mp4": d.content[4:8] == b"ftyp", "pass": d.status_code == 200 and d.content[4:8] == b"ftyp" and job(jid)["status"] == "done"}
    print(json.dumps(rep["persistence_after_restart"]), flush=True)
    rep["health_after"] = c.get("/health").json()
    rep["pass"] = all(v["pass"] for k, v in rep.items() if isinstance(v, dict) and "pass" in v)
    Path(a.out).write_text(json.dumps(rep, indent=1))
    print("DURABILITY", "PASSED" if rep["pass"] else "FAILED")
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
