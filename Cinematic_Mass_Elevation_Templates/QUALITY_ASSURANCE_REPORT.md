# Quality Assurance Report

Generated 2026-10-11T18:03:31+00:00 by `06_AUTOMATION/Scripts/qa.py` from the validated manifests.

## Three separate verification levels

| Level | What was checked | Result |
|---|---|---|
| 1. Source (static) | `.setting` and `.comp` parse in a real Lua 5.5 interpreter; every node connection and expression reference resolves; every CONTROLS reference is a defined control; no unused/dead published controls; editable text node present; time-based animation present; exit defined (ExitStart referenced); only known tool IDs | Lua parse 1/1, structure 1/1 |
| 2. Preview (rendered) | MP4 exists and is not truncated; ffprobe-readable; 1920x1080; duration and frame count match the template; audio present; not a static black screen; motion between samples; hero frame <6% clipped and has contrast | 1/1 |
| 3. DaVinci Resolve | Opened/rendered inside Resolve or Fusion | **0/1 - not possible: Resolve/Fusion were not installed in the build environment** |

A valid source file, a rendered preview and an application-tested project are different things; only levels 1 and 2 were achieved here.

## Per-template results

| ID | Name | Depth | Tools | Published controls | Lua | Structure | Preview | Hero clipped | Title-area contrast | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| T01 | Obsidian Impact | 2.5D | 69 | 39 | PASS | PASS | PASS | 0.0002 | 45.7 |  |

## Identifier evidence in the Fusion sources

Each input set in every macro was classified against `cmet/fusion_ref.py` (S = seen in real node text/docs, K = established usage not re-confirmed, ? = unconfirmed; Fusion drops unknown inputs on load, so a wrong name loses that one setting rather than breaking the file):

- S: 261, K: 139, ?: 14 (3.4% unconfirmed)

## Visual review

Every preview was reduced to a six-frame strip (build-up, pre-impact, impact+3, hold, exit, last frame) in `03_PREVIEWS/Contact_Sheets/per_template/` and the 40-up contact sheet `03_PREVIEWS/Contact_Sheets/contact_sheet_all.jpg`; these were inspected for missing/clipped text, blank frames, overexposure, clutter, broken framing and abrupt cuts. Findings are recorded in FINAL_REPORT.md.

## Hygiene

- Machine-specific paths in shipped text files: 1 (00_PROJECT_FILES/DaVinci_Resolve_Project/build_resolve_project.py)
- Categories: A - Dark Mass Elevation: T01
- Genuine 3D (Text3D) templates: none
- Project size: 17.7 MB in 114 files; free space at QA time: 31.7 GB
