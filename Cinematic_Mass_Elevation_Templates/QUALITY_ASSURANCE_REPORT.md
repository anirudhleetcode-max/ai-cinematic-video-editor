# Quality Assurance Report

Generated 2026-10-11T20:25:14+00:00 by `06_AUTOMATION/Scripts/qa.py` from the validated manifests.

## Three separate verification levels

| Level | What was checked | Result |
|---|---|---|
| 1. Source (static) | `.setting` and `.comp` parse in a real Lua 5.5 interpreter; every node connection and expression reference resolves; every CONTROLS reference is a defined control; no unused/dead published controls; editable text node present; time-based animation present; exit defined (ExitStart referenced); only known tool IDs | Lua parse 40/40, structure 40/40 |
| 2. Preview (rendered) | MP4 exists and is not truncated; ffprobe-readable; 1920x1080; duration and frame count match the template; audio present; not a static black screen; motion between samples; hero frame <6% clipped and has contrast | 40/40 |
| 3. DaVinci Resolve | Opened/rendered inside Resolve or Fusion | **0/40 - not possible: Resolve/Fusion were not installed in the build environment** |

A valid source file, a rendered preview and an application-tested project are different things; only levels 1 and 2 were achieved here.

## Per-template results

| ID | Name | Depth | Tools | Published controls | Lua | Structure | Preview | Hero clipped | Title-area contrast | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| T01 | Obsidian Impact | 2.5D | 69 | 39 | PASS | PASS | PASS | 0.0003 | 45.7 |  |
| T02 | Thunder God | 2.5D | 59 | 38 | PASS | PASS | PASS | 0.0 | 34.0 |  |
| T03 | Molten Core | 2.5D | 92 | 39 | PASS | PASS | PASS | 0.0 | 45.0 |  |
| T04 | Black Steel Reckoning | 2.5D | 76 | 39 | PASS | PASS | PASS | 0.0 | 26.2 |  |
| T05 | Shattered Monolith | 2.5D | 118 | 38 | PASS | PASS | PASS | 0.0 | 32.0 |  |
| T06 | Inferno Reveal | 2.5D | 83 | 40 | PASS | PASS | PASS | 0.0 | 35.2 |  |
| T07 | Explosive Arrival | 2.5D | 81 | 40 | PASS | PASS | PASS | 0.0 | 38.7 |  |
| T08 | Ember Storm | 2.5D | 63 | 37 | PASS | PASS | PASS | 0.0 | 38.0 |  |
| T09 | Ashes of Power | 2.5D | 85 | 39 | PASS | PASS | PASS | 0.0 | 40.1 |  |
| T10 | Shockwave Dominance | 2.5D | 79 | 40 | PASS | PASS | PASS | 0.0 | 34.2 |  |
| T11 | Golden Emperor | 3D | 50 | 36 | PASS | PASS | PASS | 0.0001 | 36.5 |  |
| T12 | Chrome Dominion | 3D | 59 | 35 | PASS | PASS | PASS | 0.0017 | 51.7 |  |
| T13 | Titanium Edge | 3D | 72 | 35 | PASS | PASS | PASS | 0.0 | 35.6 |  |
| T14 | Forged in Fire | 2.5D | 74 | 39 | PASS | PASS | PASS | 0.0 | 20.5 |  |
| T15 | Diamond Cut | 3D | 46 | 35 | PASS | PASS | PASS | 0.0003 | 53.9 |  |
| T16 | Ancient Titan | 2.5D | 95 | 39 | PASS | PASS | PASS | 0.0 | 38.8 |  |
| T17 | Celestial Ascent | 2.5D | 56 | 38 | PASS | PASS | PASS | 0.0083 | 56.6 |  |
| T18 | Dark Sorcery | 2.5D | 88 | 39 | PASS | PASS | PASS | 0.0 | 37.9 |  |
| T19 | Cosmic Overlord | 2.5D | 64 | 38 | PASS | PASS | PASS | 0.0009 | 39.9 |  |
| T20 | Phoenix Reborn | 2.5D | 74 | 39 | PASS | PASS | PASS | 0.0 | 40.5 |  |
| T21 | Neon Overdrive | 2.5D | 71 | 36 | PASS | PASS | PASS | 0.0102 | 77.2 |  |
| T22 | Hologram Breach | 2.5D | 73 | 38 | PASS | PASS | PASS | 0.0006 | 77.5 |  |
| T23 | Digital Awakening | 2.5D | 53 | 36 | PASS | PASS | PASS | 0.0037 | 69.9 |  |
| T24 | Quantum Split | 2.5D | 58 | 37 | PASS | PASS | PASS | 0.0006 | 78.1 |  |
| T25 | Future Warlord | 2.5D | 101 | 37 | PASS | PASS | PASS | 0.0 | 35.5 |  |
| T26 | Extreme Close-Up | 2.5D | 45 | 37 | PASS | PASS | PASS | 0.0 | 36.3 |  |
| T27 | Low-Angle Titan | 2.5D | 60 | 38 | PASS | PASS | PASS | 0.0006 | 39.9 |  |
| T28 | Rotating Monolith | 3D | 43 | 36 | PASS | PASS | PASS | 0.0002 | 47.2 |  |
| T29 | Cinematic Letter Assembly | 2.5D | 81 | 39 | PASS | PASS | PASS | 0.0 | 42.0 |  |
| T30 | Speed Ramp Dominance | 2.5D | 41 | 39 | PASS | PASS | PASS | 0.0001 | 59.7 |  |
| T31 | Midnight Fog | 2.5D | 62 | 36 | PASS | PASS | PASS | 0.0001 | 41.3 |  |
| T32 | Rain and Steel | 2.5D | 79 | 37 | PASS | PASS | PASS | 0.0009 | 45.0 |  |
| T33 | Desert Storm | 2.5D | 67 | 37 | PASS | PASS | PASS | 0.0027 | 46.3 |  |
| T34 | Underwater Colossus | 2.5D | 65 | 37 | PASS | PASS | PASS | 0.0003 | 41.7 |  |
| T35 | Frozen Kingdom | 2.5D | 157 | 36 | PASS | PASS | PASS | 0.0001 | 31.1 |  |
| T36 | Hero Silhouette | 2.5D | 57 | 38 | PASS | PASS | PASS | 0.0003 | 49.1 |  |
| T37 | Legacy Reveal | 2.5D | 81 | 36 | PASS | PASS | PASS | 0.0 | 35.1 |  |
| T38 | Royal Insignia | 2.5D | 119 | 39 | PASS | PASS | PASS | 0.0001 | 33.1 |  |
| T39 | Final Boss | 2.5D | 74 | 40 | PASS | PASS | PASS | 0.0 | 29.9 |  |
| T40 | Ultimate Mass Elevation | 2.5D | 95 | 49 | PASS | PASS | PASS | 0.0025 | 61.6 |  |

## Identifier evidence in the Fusion sources

Each input set in every macro was classified against `cmet/fusion_ref.py` (S = seen in real node text/docs, K = established usage not re-confirmed, ? = unconfirmed; Fusion drops unknown inputs on load, so a wrong name loses that one setting rather than breaking the file):

- S: 11259, K: 6777, ?: 442 (2.4% unconfirmed)

## Visual review

Every preview was reduced to a six-frame strip (build-up, pre-impact, impact+3, hold, exit, last frame) in `03_PREVIEWS/Contact_Sheets/per_template/` and the 40-up contact sheet `03_PREVIEWS/Contact_Sheets/contact_sheet_all.jpg`; these were inspected for missing/clipped text, blank frames, overexposure, clutter, broken framing and abrupt cuts. Findings are recorded in FINAL_REPORT.md.

## Hygiene

- Machine-specific paths in shipped text files: 0 (none)
- Categories: A - Dark, Powerful Mass Elevation: T01, T02, T03, T04, T05; B - Fire, Explosions and Impact: T06, T07, T08, T09, T10; C - 3D Metal and Premium Materials: T11, T12, T13, T14, T15; D - Mythic, Epic and Fantasy: T16, T17, T18, T19, T20; E - Sci-Fi and Futuristic Motion Graphics: T21, T22, T23, T24, T25; F - Cinematic Typography and Camera Movement: T26, T27, T28, T29, T30; G - Atmospheric and Environmental Cinema: T31, T32, T33, T34, T35; H - Signature Hero Elevations: T36, T37, T38, T39, T40
- Genuine 3D (Text3D) templates: T11, T12, T13, T15, T28
- Project size: 178.6 MB in 708 files; free space at QA time: 31.1 GB
