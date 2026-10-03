"""End-to-end smoke test against a running Cutroom API (local, containers, or a deployment).

  python scripts/smoke_flow.py --api http://localhost:8000 [--web http://localhost:3000] [--media DIR] [--out report.json]

Two users register, user A uploads clips + a song, analyses, generates (preview + final), revises, downloads the MP4
and probes it with ffprobe; user B must not see any of A's objects. Every step is timed; nothing is assumed —
a failed step fails the run. Media: --media DIR (real files) or, without it, generated test clips (reported as
synthetic)."""
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
AUDIO = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}


class Smoke:
    def __init__(self, api: str):
        self.c = httpx.Client(base_url=api.rstrip("/"), timeout=120)
        self.steps: list[dict] = []

    def step(self, name: str, fn):
        t = time.perf_counter()
        try:
            out = fn()
            self.steps.append({"step": name, "ok": True, "seconds": round(time.perf_counter() - t, 2)})
            print(f"  ok   {name} ({time.perf_counter() - t:.1f}s)", flush=True)
            return out
        except Exception as e:
            self.steps.append({"step": name, "ok": False, "seconds": round(time.perf_counter() - t, 2), "error": str(e)[:500]})
            print(f"  FAIL {name}: {e}", flush=True)
            raise

    def wait(self, H: dict, jid: str, limit: float = 3600) -> dict:
        t0 = time.time()
        while time.time() - t0 < limit:
            j = self.c.get(f"/jobs/{jid}", headers=H).json()
            if j["status"] in ("done", "failed", "cancelled"):
                if j["status"] != "done":
                    raise RuntimeError(f"job {j['kind']} {j['status']}: {j.get('error')} (ref {j.get('error_id')})")
                return j
            time.sleep(1.0)
        raise TimeoutError(f"job {jid} did not finish in {limit}s")


def ok(r: httpx.Response, code: int = 200) -> dict:
    if r.status_code != code:
        raise RuntimeError(f"{r.request.method} {r.request.url.path} → {r.status_code}: {r.text[:300]}")
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--web", default=None)
    ap.add_argument("--media", default=None, help="directory with real clips and at least one song")
    ap.add_argument("--max-clips", type=int, default=8)
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    s = Smoke(a.api)
    report: dict = {"api": a.api, "web": a.web, "started": time.time()}
    try:
        health = s.step("health", lambda: s.c.get("/health").json())
        report["health"] = health
        if not health.get("ok"):
            raise RuntimeError(f"unhealthy: {json.dumps(health.get('components'))}")
        if a.web:
            s.step("web serves", lambda: httpx.get(a.web, timeout=30).raise_for_status())
        tag = secrets.token_hex(4)
        users = {}
        for who in ("a", "b"):
            r = s.step(f"register user {who}", lambda who=who: ok(s.c.post("/auth/register", json={"email": f"smoke-{who}-{tag}@example.com", "password": f"smoke-pass-{tag}-{who}"})))
            users[who] = {"authorization": f"Bearer {r['token']}"}
        A, B = users["a"], users["b"]
        s.step("unauthenticated is refused", lambda: (s.c.get("/projects").status_code == 401) or (_ for _ in ()).throw(RuntimeError("not 401")))
        pid = s.step("create project", lambda: ok(s.c.post("/projects", json={"name": f"smoke {tag}"}, headers=A)))["id"]
        if a.media:
            files = sorted(p for p in Path(a.media).iterdir() if p.suffix.lower() in VIDEO)[: a.max_clips]
            songs = sorted(p for p in Path(a.media).iterdir() if p.suffix.lower() in AUDIO)[:1]
            report["media"] = "real (from --media)"
        else:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "engine"))
            from editor import testmedia

            ds = testmedia.make_dataset(Path(tempfile.mkdtemp()), n_clips=6, n_songs=1, with_reference=False, clip_seconds=(3.0, 5.0), w=640, h=360)
            files, songs = ds["clips"], ds["songs"]
            report["media"] = "synthetic test clips (generated)"
        if not files or not songs:
            raise RuntimeError("need clips and a song")

        def upload():
            for p in files:
                with open(p, "rb") as fh:
                    ok(s.c.post(f"/projects/{pid}/assets", files=[("files", (p.name, fh))], headers=A, timeout=600))
            with open(songs[0], "rb") as fh:
                ok(s.c.post(f"/projects/{pid}/assets", files=[("files", (songs[0].name, fh))], data={"role": "music"}, headers=A, timeout=600))
            return len(files) + 1

        report["uploaded"] = s.step("upload", upload)
        for url in (f"/projects/{pid}", f"/projects/{pid}/assets", f"/projects/{pid}/versions"):
            s.step(f"user b denied {url}", lambda url=url: (s.c.get(url, headers=B).status_code == 404) or (_ for _ in ()).throw(RuntimeError("not 404")))
        j = s.step("analyze", lambda: s.wait(A, ok(s.c.post(f"/projects/{pid}/analyze", json={"mode": "fast"}, headers=A))["job_id"]))
        prompt = f"A {a.duration:.0f} second energetic recap synced to the music, warm colour, title 'Smoke test'"
        g = s.step("generate (preview + final)", lambda: s.wait(A, ok(s.c.post(f"/projects/{pid}/generate", json={"prompt": prompt, "preview_first": True}, headers=A))["job_id"]))
        report["generate_timings"] = (g.get("result") or {}).get("timings")
        rv = s.step("revise (natural language)", lambda: s.wait(A, ok(s.c.post(f"/projects/{pid}/revise", json={"text": "make the music quieter"}, headers=A))["job_id"]))
        report["revision_changes"] = [c.get("op") for c in (rv.get("result") or {}).get("changes", [])]
        rows = s.step("list renders", lambda: ok(s.c.get(f"/projects/{pid}/renders", headers=A)))
        final = next(r for r in rows if r["kind"] == "final")
        out = Path(tempfile.mkdtemp()) / "final.mp4"

        def download():
            with s.c.stream("GET", final["download"], headers=A) as r:
                if r.status_code != 200:
                    raise RuntimeError(f"download {r.status_code}")
                with open(out, "wb") as fh:
                    for chunk in r.iter_bytes():
                        fh.write(chunk)
            return out.stat().st_size

        report["download_bytes"] = s.step("download final", download)
        s.step("user b cannot download", lambda: (s.c.get(final["download"], headers=B).status_code == 404) or (_ for _ in ()).throw(RuntimeError("not 404")))

        def probe():
            p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height,pix_fmt,color_primaries",
                                "-of", "json", str(out)], capture_output=True, text=True, timeout=60)
            if p.returncode:
                raise RuntimeError("ffprobe failed: " + p.stderr[:200])
            info = json.loads(p.stdout)
            dur = float(info["format"]["duration"])
            if abs(dur - a.duration) > 0.5:
                raise RuntimeError(f"duration {dur} != {a.duration}")
            return info

        report["final_probe"] = s.step("probe final", probe)
        report["qc"] = s.step("render report", lambda: ok(s.c.get(f"/renders/{final['id']}/report", headers=A)).get("qc", {}).get("passed"))
        s.step("delete project", lambda: ok(s.c.delete(f"/projects/{pid}", headers=A)))
        report["passed"] = True
    except Exception:
        report["passed"] = False
    report["steps"] = s.steps
    report["finished"] = time.time()
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=2, default=str))
    print("SMOKE", "PASSED" if report["passed"] else "FAILED")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
