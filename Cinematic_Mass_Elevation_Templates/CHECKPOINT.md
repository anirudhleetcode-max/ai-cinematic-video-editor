# Build checkpoint / progress log

Resume from the last row marked DONE. All commands run from `06_AUTOMATION/Scripts/`.

| Phase | Status | Notes |
|---|---|---|
| 1 Environment audit | DONE | Linux cloud container; no Resolve/Fusion/Blender/PowerShell; FFmpeg 7, Python 3.13, NumPy, Pillow (raqm), OpenCV, lupa (Lua 5.5) |
| 2 T01 prototype | DONE | Fusion macro + comp parse in real Lua; structure checks pass; 1080p preview passes media checks. NOT tested in Resolve. |
| 3 Shared components | DONE | `cmet/fcomp.py` (Fusion), `cmet/core.py`, `typo.py`, `elements.py` (preview), `sfx.py` (audio) |
| 4 T01-T10 | IN PROGRESS | |
| 5 T11-T20 | TODO | |
| 6 T21-T30 | TODO | |
| 7 T31-T40 | TODO | |
| 8 Catalog & previews | TODO | |
| 9 QA | TODO | |
| 10 Final report | TODO | |

Resume: `python build.py all --jobs 4` rebuilds sources/previews/validation for every template that has a design module.
