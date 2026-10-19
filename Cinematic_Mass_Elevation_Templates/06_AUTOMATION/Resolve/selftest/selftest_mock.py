#!/usr/bin/env python3
"""Self-test of the Resolve harness + analyzer against a MOCK Resolve API.
Proves the scripts run end to end and that pass/fail logic reacts correctly.
It is NOT evidence of Resolve compatibility; outputs go to a temp folder."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.dirname(HERE)
ROOT = os.path.normpath(os.path.join(RES, "..", ".."))
tmp = tempfile.mkdtemp(prefix="cmet_mock_")
env = dict(os.environ, CMET_ROOT=ROOT, CMET_MOCK_RESOLVE="1", PYTHONPATH=HERE, CMET_MOCK_FAIL="T03")
ids = sys.argv[1] if len(sys.argv) > 1 else "T01,T03,T11"
r = subprocess.run([sys.executable, os.path.join(RES, "resolve_harness.py"), "--root", ROOT, "--templates", ids,
                    "--run-id", "mock", "--runs-dir", tmp], env=env)
assert r.returncode == 0, "harness failed"
r = subprocess.run([sys.executable, os.path.join(RES, "analyze_resolve_run.py"), "--run", "mock", "--runs-dir", tmp], env=env)
assert r.returncode == 0, "analyzer failed"
res = json.load(open(os.path.join(tmp, "mock", "resolve_test_results.json")))
st = {k: v["status"] for k, v in res["templates"].items() if k in ids.split(",")}
print("mock statuses:", st)
assert res["mock"] is True
assert st["T03"] == "FAIL", "injected insertion failure must be reported as FAIL"
for k in ids.split(","):
    if k != "T03":
        assert st[k] == "PASS", (k, res["templates"][k])
assert not os.path.exists(os.path.join(ROOT, "06_AUTOMATION", "Validation", "resolve_runs", "mock"))
print("SELFTEST OK (mock only) ->", tmp)
