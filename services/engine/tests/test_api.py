import time

from fastapi.testclient import TestClient

from editor.api import app


def test_api_flow(dataset):
    with TestClient(app) as c:
        assert c.get("/health").json()["ok"]
        for k in ("/effects", "/transitions", "/text-animations", "/color-presets", "/templates", "/audio-presets", "/motion-presets"):
            r = c.get(k)
            assert r.status_code == 200 and r.json()["count"] > 0
        assert c.get("/library/preview/color-presets/teal_orange").headers["content-type"] == "image/png"
        p = c.post("/projects", json={"name": "API"}).json()
        pid = p["id"]
        files = [("files", (x.name, open(x, "rb"), "video/mp4")) for x in dataset["clips"][:5]]
        files.append(("files", (dataset["songs"][0].name, open(dataset["songs"][0], "rb"), "audio/wav")))
        files.append(("files", ("evil.sh", b"#!/bin/sh", "text/plain")))
        r = c.post(f"/projects/{pid}/assets", files=files).json()
        assert len(r["assets"]) == 6 and r["errors"][0]["file"] == "evil.sh"
        # resumable upload of the logo in 3 chunks
        data = open(dataset["logo"], "rb").read()
        u = c.post(f"/projects/{pid}/uploads", json={"filename": "logo.png", "size": len(data), "role": "logo"}).json()["upload_id"]
        n = len(data) // 3 + 1
        for off in range(0, len(data), n):
            assert c.put(f"/projects/{pid}/uploads/{u}?offset={off}", content=data[off:off + n]).status_code == 200
        assert c.put(f"/projects/{pid}/uploads/{u}?offset=0", content=b"x").status_code == 409  # wrong offset is refused
        assert c.post(f"/projects/{pid}/uploads/{u}/complete").json()["role"] == "logo"
        j = c.post(f"/projects/{pid}/generate", json={"prompt": "8 second energetic highlight, cut to the beat, end with the logo", "preview_first": False}).json()
        deadline = time.time() + 600
        while True:
            s = c.get(f"/jobs/{j['job_id']}").json()
            if s["status"] in ("done", "failed") or time.time() > deadline:
                break
            time.sleep(1)
        assert s["status"] == "done", s.get("error")
        stages = {x["stage"] for x in s["log"]}
        assert {"analyzing_media", "planning_story", "rendering", "quality_check"} <= stages
        rid = s["result"]["final"]["id"]
        d = c.get(f"/renders/{rid}/download")
        assert d.status_code == 200 and d.content[4:8] == b"ftyp"
        vs = c.get(f"/projects/{pid}/versions").json()
        assert len(vs) == 1 and c.get(f"/versions/{vs[0]['id']}/inspector").json()[0]["scene"] == 1
        assert c.post(f"/projects/{pid}/render", json={"export": {"bogus": 1}}).status_code == 400
        assert c.get("/projects/nope").status_code == 404
        # no server path, traceback or command line in any response the client can read
        from editor.config import get_settings

        root = str(get_settings().data_dir)
        urls = [f"/projects/{pid}", f"/projects/{pid}/assets", f"/projects/{pid}/versions", f"/versions/{vs[0]['id']}",
                f"/versions/{vs[0]['id']}/inspector", f"/projects/{pid}/renders", f"/renders/{rid}/report", f"/jobs/{j['job_id']}",
                f"/projects/{pid}/render-status", "/export-history", "/projects"]
        for u in urls:
            body = c.get(u).text
            assert root not in body and "Traceback" not in body and "ffmpeg -" not in body, u
