# Build checkpoint / progress log

Resume from the last row marked DONE. All commands run from `06_AUTOMATION/Scripts/`.

| Phase | Status | Notes |
|---|---|---|
| 1 Environment audit | DONE | Linux cloud container; no Resolve/Fusion/Blender/PowerShell; FFmpeg 6.1.1, Python 3.13, PowerShell 7.6 (installed for script testing), NumPy, Pillow (raqm), OpenCV, lupa (Lua 5.5) |
| 2 T01 prototype | DONE | Fusion macro + comp parse in real Lua; structure checks pass; 1080p preview passes media checks. NOT tested in Resolve. |
| 3 Shared components | DONE | `cmet/fcomp.py` (Fusion), `cmet/core.py`, `typo.py`, `elements.py` (preview), `sfx.py` (audio) |
| 4 T01-T10 | IN PROGRESS | T01, T02 done; T03-T10 being authored (parallel agent) |
| 5 T11-T20 | IN PROGRESS | parallel agent |
| 6 T21-T30 | IN PROGRESS | parallel agent |
| 7 T31-T40 | IN PROGRESS | T40 flagship done; T31-T39 parallel agent |
| 8 Catalog & previews | TOOLING DONE | catalog.py, qa.py, render_all.ps1, render_previews.ps1, install_titles.ps1 tested with pwsh |
| 9 QA | TODO | |
| 10 Final report | TODO | |

Resume: `python build.py all --jobs 4` rebuilds sources/previews/validation for every template that has a design module.
