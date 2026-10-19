# CMET in-Resolve launcher (installed by run_resolve_tests.ps1 into Fusion/Scripts/Utility).
# Run it from DaVinci Resolve: Workspace > Scripts > Utility > CMET_Run_Resolve_Tests
# It hands Resolve's own scripting object to the harness, so it also works where
# external scripting is unavailable. Results: 06_AUTOMATION/Validation/resolve_runs/<run>/
import os, sys
CMET_ROOT = r"__CMET_ROOT__"
TEMPLATES = r"__TEMPLATES__"  # e.g. "T01" or "" for all
sys.path.insert(0, os.path.join(CMET_ROOT, "06_AUTOMATION", "Resolve"))
import resolve_harness as H  # noqa: E402
try:
    H.resolve = resolve  # noqa: F821  (provided by Resolve's script environment)
except NameError:
    pass
args = ["--root", CMET_ROOT]
if TEMPLATES:
    args += ["--templates", TEMPLATES]
H.main(args)
