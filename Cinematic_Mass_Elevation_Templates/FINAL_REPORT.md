# Final Report - Cinematic Mass Elevation Templates

Generated 2026-10-11T21:24:17+00:00 by `06_AUTOMATION/Scripts/final_report.py` from the validated manifests and `06_AUTOMATION/Validation/test_results.json`.

## Summary

| Item | Result |
|---|---|
| Template definitions | **40** (T01-T40, 8 categories A-H as in the brief) |
| Editable Fusion compositions | **40 macros (.setting) + 40 flat compositions (.comp)** |
| A. Fusion source structural validation | **40/40 PASS** |
| B. Standalone Python preview validation (1080p) | **40/40 PASS** |
| C. DaVinci Resolve composition loading | **BLOCKED 40/40** |
| D. DaVinci Resolve rendering | **BLOCKED 40/40** |
| E. Editable text and controls (in Resolve) | **BLOCKED 40/40** |
| F. Visual comparison Resolve vs. preview | **BLOCKED 40/40** |
| Overall Resolve status | **BLOCKED 40/40** |
| Resolve connection | **not connected** - last harness run `cloud_build_env_20261011` could not reach DaVinci Resolve (no Resolve installation in that environment) |
| Full acceptance test suite (`run_tests.py`) | **40/40 templates pass every check; collection checks PASS** |
| Genuine 3D (Text3D/Renderer3D) | 5: T11, T12, T13, T15, T28 |
| 2.5D | 35 |
| Native .drp | Not shipped. Only Resolve can create one; `00_PROJECT_FILES/DaVinci_Resolve_Project/build_resolve_project.py` builds and exports it inside Resolve (untested) |
| External plugins | None |
| Library size / free disk | 179 MB / 31.1 GB free |
| 4K | Not batch-rendered (optional; `render_all.ps1 -Mode final`) |

## All 40 templates

| ID | Template | Category | Length | Depth | A Source | B Preview | Tests | Resolve (C/D/E/F) | Preview path |
|---|---|---|---|---|---|---|---|---|---|
| T01 | Obsidian Impact | A | 192f / 8.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T01_Obsidian_Impact/preview/T01_Obsidian_Impact.mp4` |
| T02 | Thunder God | A | 192f / 8.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T02_Thunder_God/preview/T02_Thunder_God.mp4` |
| T03 | Molten Core | A | 216f / 9.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T03_Molten_Core/preview/T03_Molten_Core.mp4` |
| T04 | Black Steel Reckoning | A | 168f / 7.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T04_Black_Steel_Reckoning/preview/T04_Black_Steel_Reckoning.mp4` |
| T05 | Shattered Monolith | A | 240f / 10.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T05_Shattered_Monolith/preview/T05_Shattered_Monolith.mp4` |
| T06 | Inferno Reveal | B | 192f / 8.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T06_Inferno_Reveal/preview/T06_Inferno_Reveal.mp4` |
| T07 | Explosive Arrival | B | 144f / 6.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T07_Explosive_Arrival/preview/T07_Explosive_Arrival.mp4` |
| T08 | Ember Storm | B | 240f / 10.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T08_Ember_Storm/preview/T08_Ember_Storm.mp4` |
| T09 | Ashes of Power | B | 204f / 8.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T09_Ashes_of_Power/preview/T09_Ashes_of_Power.mp4` |
| T10 | Shockwave Dominance | B | 156f / 6.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T10_Shockwave_Dominance/preview/T10_Shockwave_Dominance.mp4` |
| T11 | Golden Emperor | C | 216f / 9.0s | 3D | PASS | PASS | 26/26 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T11_Golden_Emperor/preview/T11_Golden_Emperor.mp4` |
| T12 | Chrome Dominion | C | 180f / 7.5s | 3D | PASS | PASS | 26/26 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T12_Chrome_Dominion/preview/T12_Chrome_Dominion.mp4` |
| T13 | Titanium Edge | C | 168f / 7.0s | 3D | PASS | PASS | 26/26 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T13_Titanium_Edge/preview/T13_Titanium_Edge.mp4` |
| T14 | Forged in Fire | C | 228f / 9.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T14_Forged_In_Fire/preview/T14_Forged_In_Fire.mp4` |
| T15 | Diamond Cut | C | 204f / 8.5s | 3D | PASS | PASS | 26/26 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T15_Diamond_Cut/preview/T15_Diamond_Cut.mp4` |
| T16 | Ancient Titan | D | 240f / 10.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T16_Ancient_Titan/preview/T16_Ancient_Titan.mp4` |
| T17 | Celestial Ascent | D | 210f / 8.8s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T17_Celestial_Ascent/preview/T17_Celestial_Ascent.mp4` |
| T18 | Dark Sorcery | D | 192f / 8.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T18_Dark_Sorcery/preview/T18_Dark_Sorcery.mp4` |
| T19 | Cosmic Overlord | D | 236f / 9.8s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T19_Cosmic_Overlord/preview/T19_Cosmic_Overlord.mp4` |
| T20 | Phoenix Reborn | D | 156f / 6.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T20_Phoenix_Reborn/preview/T20_Phoenix_Reborn.mp4` |
| T21 | Neon Overdrive | E | 168f / 7.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T21_Neon_Overdrive/preview/T21_Neon_Overdrive.mp4` |
| T22 | Hologram Breach | E | 192f / 8.0s | 2.5D | PASS | PASS | 26/26 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T22_Hologram_Breach/preview/T22_Hologram_Breach.mp4` |
| T23 | Digital Awakening | E | 216f / 9.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T23_Digital_Awakening/preview/T23_Digital_Awakening.mp4` |
| T24 | Quantum Split | E | 156f / 6.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T24_Quantum_Split/preview/T24_Quantum_Split.mp4` |
| T25 | Future Warlord | E | 228f / 9.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T25_Future_Warlord/preview/T25_Future_Warlord.mp4` |
| T26 | Extreme Close-Up | F | 200f / 8.3s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T26_Extreme_Close_Up/preview/T26_Extreme_Close_Up.mp4` |
| T27 | Low-Angle Titan | F | 240f / 10.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T27_Low_Angle_Titan/preview/T27_Low_Angle_Titan.mp4` |
| T28 | Rotating Monolith | F | 204f / 8.5s | 3D | PASS | PASS | 26/26 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T28_Rotating_Monolith/preview/T28_Rotating_Monolith.mp4` |
| T29 | Cinematic Letter Assembly | F | 180f / 7.5s | 2.5D | PASS | PASS | 26/26 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T29_Cinematic_Letter_Assembly/preview/T29_Cinematic_Letter_Assembly.mp4` |
| T30 | Speed Ramp Dominance | F | 144f / 6.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T30_Speed_Ramp_Dominance/preview/T30_Speed_Ramp_Dominance.mp4` |
| T31 | Midnight Fog | G | 216f / 9.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T31_Midnight_Fog/preview/T31_Midnight_Fog.mp4` |
| T32 | Rain and Steel | G | 192f / 8.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T32_Rain_And_Steel/preview/T32_Rain_And_Steel.mp4` |
| T33 | Desert Storm | G | 180f / 7.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T33_Desert_Storm/preview/T33_Desert_Storm.mp4` |
| T34 | Underwater Colossus | G | 240f / 10.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T34_Underwater_Colossus/preview/T34_Underwater_Colossus.mp4` |
| T35 | Frozen Kingdom | G | 204f / 8.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T35_Frozen_Kingdom/preview/T35_Frozen_Kingdom.mp4` |
| T36 | Hero Silhouette | H | 168f / 7.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T36_Hero_Silhouette/preview/T36_Hero_Silhouette.mp4` |
| T37 | Legacy Reveal | H | 228f / 9.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T37_Legacy_Reveal/preview/T37_Legacy_Reveal.mp4` |
| T38 | Royal Insignia | H | 196f / 8.2s | 2.5D | PASS | PASS | 26/26 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T38_Royal_Insignia/preview/T38_Royal_Insignia.mp4` |
| T39 | Final Boss | H | 156f / 6.5s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T39_Final_Boss/preview/T39_Final_Boss.mp4` |
| T40 | Ultimate Mass Elevation | H | 240f / 10.0s | 2.5D | PASS | PASS | 25/25 | BLOCKED (BLOCKED/BLOCKED/BLOCKED/BLOCKED) | `01_TEMPLATES/T40_Ultimate_Mass_Elevation/preview/T40_Ultimate_Mass_Elevation.mp4` |

## Resolve test lists

- **PASS (0):** none
- **FAIL (0):** none
- **BLOCKED (40):** T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20, T21, T22, T23, T24, T25, T26, T27, T28, T29, T30, T31, T32, T33, T34, T35, T36, T37, T38, T39, T40
- **NOT TESTED (0):** none

## Manual actions still required

1. On the Windows PC with DaVinci Resolve, run the read-only audit: `powershell -ExecutionPolicy Bypass -File 06_AUTOMATION\Resolve\run_resolve_tests.ps1 -AuditOnly`.
2. Start Resolve. Set *Preferences > User > Editing > Standard Generator Duration* to 10 s. In Resolve Studio, also set *Preferences > System > General > External scripting using* to Local.
3. Run the end-to-end T01 test: `run_resolve_tests.ps1 -Templates T01`. In the free edition, use *Workspace > Scripts > Utility > CMET_Run_Resolve_Tests*.
4. If T01 passes, run all 40 (`run_resolve_tests.ps1`), then commit `06_AUTOMATION/Validation/resolve_runs/<run>/` and `resolve_test_results.json`. Re-run `build.py validate`, `qa.py`, `catalog.py` and `final_report.py`, or hand the results back to Claude to analyse and fix any FAIL templates.
5. Review the side-by-side sheets in `resolve_runs/<run>/comparisons/` (level F visual review).


Collection checks: catalog_html_40_unique PASS, catalog_links_resolve PASS, catalog_md_40_unique PASS, strips_40 PASS, contact_sheet PASS, thumbnails_40 PASS, resolve_import_40 PASS, project_manifest_40 PASS, no_private_paths PASS, no_partial_files PASS, no_running_builds PASS, resolve_results_40 PASS, resolve_claims_match_evidence PASS, no_fake_drp PASS

## Where things are

| What | Path |
|---|---|
| Browse all templates | `TEMPLATE_CATALOG.html` (offline), `TEMPLATE_CATALOG.md` |
| Master contact sheets | `03_PREVIEWS/Contact_Sheets/contact_sheet_all.jpg` (40 thumbnails), `contact_sheet_strips.jpg` (40 six-frame strips) |
| Six-frame strip per template | `03_PREVIEWS/Contact_Sheets/per_template/TNN_*_strip.jpg` |
| Editable Fusion macros / compositions | `05_RESOLVE_IMPORT/Fusion_Macros/`, `05_RESOLVE_IMPORT/Fusion_Compositions/` (copies of each template's `source/`) |
| Per-template package | `01_TEMPLATES/TNN_Name/` (source, preview, configuration, documentation, manifest, README) |
| Master manifest | `00_PROJECT_FILES/Project_Manifest.json` |
| Reports | `QUALITY_ASSURANCE_REPORT.md`, `COMPATIBILITY_REPORT.md`, `06_AUTOMATION/Validation/test_results.md` |
| Resolve first-session checklist | `05_RESOLVE_IMPORT/Resolve_Test_Checklist.md` |

## Using the templates in DaVinci Resolve (exact steps)

1. Copy the `Cinematic_Mass_Elevation_Templates` folder anywhere, for example `%USERPROFILE%\Documents`.
2. Open PowerShell in `05_RESOLVE_IMPORT` and run
   `powershell -ExecutionPolicy Bypass -File .\install_titles.ps1 -InstallFonts`.
   This installs the 40 macros and the bundled OFL fonts per user and never overwrites existing files.
3. In Resolve, set *Preferences > User > Editing > Standard Generator Duration* to 10 s. Restart Resolve.
4. Use a 24 fps timeline (1080p or UHD). On the Edit page, go to *Effects > Titles > Fusion Titles* and drag `TNN_...` onto the timeline. Trim it to the template's frame count from the table above.
5. **Change the text:** select the clip, open *Inspector > Title*, and edit *Main Title* (and *Subtitle* / *Tagline*). Font, size, spacing, alignment and colour sit beside the text.
6. **Adjust:** use *Impact Frame*, *Exit Start*, *Accent Color*, the intensities, *Camera Shake* and *Letterbox* in the same Inspector. For deeper edits, open the clip on the Fusion page; the node layout is explained in `07_DOCUMENTATION/Template_Editing_Guide.md`.
7. **Render:** on the Deliver page choose QuickTime > Apple ProRes 422 HQ (or H.264), at timeline or UHD resolution and 24 fps, then *Add to Render Queue* > *Render All*.
8. **First session:** test one template against its preview (*First-run check* in `05_RESOLVE_IMPORT/Import_Instructions.md`) and work through `Resolve_Test_Checklist.md`.

To render without Resolve, using the same designs, text, colours and timing:
`python 06_AUTOMATION/Scripts/render_title.py T40 --set MAIN_TITLE="YOUR TITLE" --res 3840x2160 --codec prores --out title.mov`.

## Known limitations

- **Resolve testing.** See the Summary (levels C-F). Until the harness has run on a machine with Resolve, compatibility rests on documentation-sourced node and input IDs plus static validation.
  - 2.4% of the inputs set in the macros are unconfirmed (21 distinct names, mostly particle sub-inputs). If one is wrong, Fusion loses only that setting.
  - See `COMPATIBILITY_REPORT.md` sections 3 and 6.
- **Previews are not Fusion renders.** They come from the Python reference renderer. Expect differences in noise, particle and glow detail.
- **Fusion approximations.** Per-letter and particle-target effects are approximated in Fusion: T09, T19, T20, T23, T29 and T37 (details in each README).
- **Telugu.** Shaping is verified in the reference renderer only; Text+ shaping in Resolve is untested.
- **4K** was not batch-rendered (disk/time); 1080p previews are the verified deliverable.
- **No .drp file is included** (cannot be created without Resolve; the build script is untested).
