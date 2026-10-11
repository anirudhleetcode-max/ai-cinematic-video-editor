# DaVinci Resolve test workflow

These tools test the 40 templates **inside the real DaVinci Resolve application** and record evidence for each
one. They have to run on a machine with Resolve installed. The cloud environment that built this library has no
Resolve, no GPU and no Windows desktop. The harness was run there anyway, and its log shows that it could not
connect, so all 40 templates are recorded as **BLOCKED** (run `cloud_build_env_20261011`).

## One-time preparation (on the Windows PC with Resolve)

1. Install Python 3.10+ (64-bit) and FFmpeg on PATH. Then run `pip install numpy opencv-python` (needed only for the analyzer).
2. Start DaVinci Resolve and set *Preferences > User > Editing > Standard Generator Duration* to **10 seconds**.
   Titles are inserted at this length. The templates run 6–10 s (144–240 frames).
3. **Resolve Studio:** set *Preferences > System > General > External scripting using* to **Local** and restart Resolve.
   **Free edition:** external scripting is not available, so use the in-Resolve launcher instead (step 3 below). A
   September 2026 report says Resolve 21.1 removed scripting from the free edition entirely; if so, only the manual
   checklist applies.

## Run

Run from this folder (`06_AUTOMATION/Resolve/`):

```powershell
# 1. read-only audit of the PC (Resolve version, scripting module, Python, fonts, disk) -> Validation/resolve/
powershell -ExecutionPolicy Bypass -File .\run_resolve_tests.ps1 -AuditOnly

# 2. end-to-end test of T01 only (installs titles + fonts without overwriting, creates a NEW test project)
powershell -ExecutionPolicy Bypass -File .\run_resolve_tests.ps1 -Templates T01

# 3. after T01 passes: all 40
powershell -ExecutionPolicy Bypass -File .\run_resolve_tests.ps1
```

Free edition:
1. After step 2 has installed the launcher, choose *Workspace > Scripts > Utility > CMET_Run_Resolve_Tests* inside Resolve.
2. Then run `.\run_resolve_tests.ps1 -Analyze <run id>`. The run ID is printed in Resolve's console and is the folder name under `Validation/resolve_runs/`.

## What it does and what counts as evidence

| Level | How it is tested | Evidence kept |
|---|---|---|
| C. Composition loads | The title is inserted with `Timeline.InsertFusionTitleIntoTimeline(<macro>)`, the Edit-page title path. If that fails, a Fusion composition clip is used with the `.setting` pasted in and wired to `MediaOut1`. The harness then checks that the macro tool is found and that every published input is readable. Up to 8 inner expressions per template must evaluate to numbers that **change over time**. | `harness_results.json`: tool list, readable inputs, expression probe values |
| D. Resolve render | A 1920x1080, 24 fps H.264 job goes through the Deliver render queue, with mark in/out set to the template length. The output is then checked by ffprobe, a full decode, frame count, motion, non-black middle, exposure, and a visible entrance and exit. | `renders/TNN_*_resolve.mp4` and the analyzer metrics |
| E. Editable | The harness writes *Main Title*, *Subtitle* and every timing and look control, then reads each back. It exports stills before and after a title change and an Impact Frame change; the pixels must differ. | stills under `stills/TNN/`, plus diff values |
| F. Visual comparison | The Resolve render and the Python preview are compared at 6 key frames (luma correlation, mean colour). | `comparisons/TNN_compare.jpg` (top: preview, bottom: Resolve) for human review |

Status rules:
- A template is **PASS** only when C, D and E all pass.
- It is **FAIL** when an executed check failed.
- It is **BLOCKED** when Resolve could not be reached.
- It is **NOT TESTED** when the harness never ran it.

Audio is "N/A": Resolve titles carry no audio. The sound design is supplied separately as cue sheets plus SFX.

## Safety

- Every run creates a new project, `CMET_ResolveTest_<run id>`. The harness aborts if that name already exists, and it never opens, changes or deletes other projects.
- Titles are installed into their own `Cinematic Mass Elevation` folder, and existing files are never overwritten. If an older, different copy is installed, the launcher stops rather than test the wrong version.
- Fonts are installed per user. The in-Resolve launcher stub is not overwritten if a different one exists.
- Template files in the repository are never modified by the harness.
- Outputs go only to `06_AUTOMATION/Validation/resolve_runs/<run id>/`. The analyzer merges results into `06_AUTOMATION/Validation/resolve_test_results.json`.
- Nothing changes Resolve preferences or system security settings. The steps that need you (starting Resolve, preference changes) are printed as `ACTION NEEDED`.

## Files

| File | Purpose |
|---|---|
| `run_resolve_tests.ps1` | Windows launcher: audit, install, connect, run, analyze |
| `resolve_harness.py` | Runs inside or against Resolve; documented scripting API only; Python 3.6+, stdlib only |
| `analyze_resolve_run.py` | Verifies the evidence and writes `resolve_test_results.{json,md}` |
| `resolve_test_inventory.json` | Per-template inputs, frames and probes, generated by `build_inventory.py` from the manifests and `.setting` files |
| `CMET_Run_Resolve_Tests_stub.py` | In-Resolve launcher template (installed to `Fusion\Scripts\Utility`) |
| `selftest/` | **Mock** Resolve API and `selftest_mock.py`. These prove the harness and analyzer logic only; they are never Resolve evidence, and their results are refused by the merge step. |

## API calls the harness relies on (to confirm on first run)

From the Resolve scripting README:
- `scriptapp`, `GetProductName`, `GetVersionString`, `GetProjectManager`
- `CreateProject`, `SetSetting`, `GetMediaPool`, `CreateEmptyTimeline`, `SetCurrentTimeline`
- `InsertFusionTitleIntoTimeline`, `InsertFusionCompositionIntoTimeline`, `GetFusionCompByIndex`
- `GetStartTimecode`, `SetCurrentTimecode`, `ExportCurrentFrameAsStill`
- `SetCurrentRenderFormatAndCodec`, `SetRenderSettings`, `AddRenderJob`, `StartRendering`, `IsRenderingInProgress`, `GetRenderJobStatus`, `DeleteRenderJob`

From the Fusion scripting API:
- `GetToolList`, `GetAttrs`, `GetInput`, `SetInput`, `FindTool`, `Execute`

Each call is wrapped so that a missing or failing call is recorded as an error for that template rather than aborting the run.
