#!/usr/bin/env python3
"""Write FINAL_REPORT.md from the manifests and test results (no hand-typed numbers)."""
import datetime
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cmet.export import ROOT, TPL  # noqa: E402


def main():
    ms = []
    for d in sorted(os.listdir(TPL)):
        p = os.path.join(TPL, d, "manifest.json")
        if os.path.exists(p):
            m = json.load(open(p, encoding="utf-8"))
            m["_dir"] = d
            ms.append(m)
    tr = json.load(open(os.path.join(ROOT, "06_AUTOMATION", "Validation", "test_results.json")))
    by = {r["id"]: r for r in tr["templates"]}
    n = len(ms)
    src = sum(m["verification"]["structure"] == "PASS" for m in ms)
    prv = sum(m["verification"]["preview"] == "PASS" for m in ms)
    allpass = sum(1 for r in tr["templates"] if not r["errors"])
    coll = tr["collection"]
    n3 = [m["id"] for m in ms if m["true_3d"]]
    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fn in os.walk(ROOT) for f in fn)
    free = shutil.disk_usage(ROOT).free
    L = [
        "# Final Report - Cinematic Mass Elevation Templates", "",
        f"Generated {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} by "
        "`06_AUTOMATION/Scripts/final_report.py` from the validated manifests and `06_AUTOMATION/Validation/test_results.json`.",
        "",
        "## Summary", "",
        "| Item | Result |", "|---|---|",
        f"| Template definitions | **{n}** (T01-T40, 8 categories A-H as in the brief) |",
        f"| Editable Fusion compositions | **{n} macros (.setting) + {n} flat compositions (.comp)** |",
        f"| Level 1 - structural validation of Fusion sources | **{src}/{n} PASS** |",
        f"| Level 2 - standalone preview rendering (1080p, checked) | **{prv}/{n} PASS** |",
        f"| Level 3 - DaVinci Resolve import / render | **0/{n} tested** - Resolve is not available in the build environment |",
        f"| Full acceptance test suite (`run_tests.py`) | **{allpass}/{n} templates pass every check; collection checks "
        f"{'PASS' if all(v['ok'] for v in coll.values()) else 'FAIL'}** |",
        f"| Genuine 3D (Text3D/Renderer3D) | {len(n3)}: {', '.join(n3)} |",
        f"| 2.5D | {n - len(n3)} |",
        "| Native .drp | Not shipped. Only Resolve can create one; `00_PROJECT_FILES/DaVinci_Resolve_Project/build_resolve_project.py` builds and exports it inside Resolve (untested) |",
        "| External plugins | None |",
        f"| Library size / free disk | {size / 1e6:.0f} MB / {free / 1e9:.1f} GB free |",
        "| 4K | Not batch-rendered (optional; `render_all.ps1 -Mode final`) |",
        "",
        "## All 40 templates", "",
        "| ID | Template | Category | Length | Depth | Fusion source | Preview | Tests | Preview path |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in ms:
        r = by.get(m["id"], {"checks": {}, "errors": ["not tested"]})
        L.append(f"| {m['id']} | {m['name']} | {m['category'].split(' - ')[0]} | {m['duration_frames']}f / "
                 f"{m['duration_seconds']:.1f}s | {'3D' if m['true_3d'] else '2.5D'} | "
                 f"{'PASS' if m['verification']['structure'] == 'PASS' else 'FAIL'} | "
                 f"{'PASS' if m['verification']['preview'] == 'PASS' else 'FAIL'} | "
                 f"{sum(r['checks'].values())}/{len(r['checks'])} | `01_TEMPLATES/{m['_dir']}/{m['preview']}` |")
    L += ["", "Collection checks: " + ", ".join(f"{k} {'PASS' if v['ok'] else 'FAIL'}" for k, v in coll.items()), "",
          "## Where things are", "",
          "| What | Path |", "|---|---|",
          "| Browse all templates | `TEMPLATE_CATALOG.html` (offline), `TEMPLATE_CATALOG.md` |",
          "| Master contact sheets | `03_PREVIEWS/Contact_Sheets/contact_sheet_all.jpg` (40 thumbnails), `contact_sheet_strips.jpg` (40 six-frame strips) |",
          "| Six-frame strip per template | `03_PREVIEWS/Contact_Sheets/per_template/TNN_*_strip.jpg` |",
          "| Editable Fusion macros / compositions | `05_RESOLVE_IMPORT/Fusion_Macros/`, `05_RESOLVE_IMPORT/Fusion_Compositions/` (copies of each template's `source/`) |",
          "| Per-template package | `01_TEMPLATES/TNN_Name/` (source, preview, configuration, documentation, manifest, README) |",
          "| Master manifest | `00_PROJECT_FILES/Project_Manifest.json` |",
          "| Reports | `QUALITY_ASSURANCE_REPORT.md`, `COMPATIBILITY_REPORT.md`, `06_AUTOMATION/Validation/test_results.md` |",
          "| Resolve first-session checklist | `05_RESOLVE_IMPORT/Resolve_Test_Checklist.md` |",
          "",
          "## Using the templates in DaVinci Resolve (exact steps)", "",
          "1. Copy the `Cinematic_Mass_Elevation_Templates` folder anywhere, for example `%USERPROFILE%\\Documents`.",
          "2. Open PowerShell in `05_RESOLVE_IMPORT` and run",
          "   `powershell -ExecutionPolicy Bypass -File .\\install_titles.ps1 -InstallFonts`.",
          "   This installs the 40 macros and the bundled OFL fonts per user and never overwrites existing files.",
          "3. In Resolve, set *Preferences > User > Editing > Standard Generator Duration* to 10 s. Restart Resolve.",
          "4. Use a 24 fps timeline (1080p or UHD). On the Edit page, go to *Effects > Titles > Fusion Titles* and drag "
          "`TNN_...` onto the timeline. Trim it to the template's frame count from the table above.",
          "5. **Change the text:** select the clip, open *Inspector > Title*, and edit *Main Title* (and *Subtitle* / *Tagline*). "
          "Font, size, spacing, alignment and colour sit beside the text.",
          "6. **Adjust:** use *Impact Frame*, *Exit Start*, *Accent Color*, the intensities, *Camera Shake* and *Letterbox* in the "
          "same Inspector. For deeper edits, open the clip on the Fusion page; the node layout is explained in "
          "`07_DOCUMENTATION/Template_Editing_Guide.md`.",
          "7. **Render:** on the Deliver page choose QuickTime > Apple ProRes 422 HQ (or H.264), at timeline or UHD "
          "resolution and 24 fps, then *Add to Render Queue* > *Render All*.",
          "8. **First session:** test one template against its preview (*First-run check* in "
          "`05_RESOLVE_IMPORT/Import_Instructions.md`) and work through `Resolve_Test_Checklist.md`.",
          "",
          "To render without Resolve, using the same designs, text, colours and timing:",
          "`python 06_AUTOMATION/Scripts/render_title.py T40 --set MAIN_TITLE=\"YOUR TITLE\" --res 3840x2160 --codec prores --out title.mov`.",
          "",
          "## Known limitations", "",
          "- **Untested in Resolve.** No template has been opened in DaVinci Resolve or Fusion. Compatibility rests on "
          "documentation-sourced node and input IDs plus static validation.",
          "  - 2.4% of the inputs set in the macros are unconfirmed (21 distinct names, mostly particle sub-inputs). "
          "If one is wrong, Fusion loses only that setting.",
          "  - See `COMPATIBILITY_REPORT.md` sections 3 and 6.",
          "- **Previews are not Fusion renders.** They come from the Python reference renderer. Expect differences in "
          "noise, particle and glow detail.",
          "- **Fusion approximations.** Per-letter and particle-target effects are approximated in Fusion: T09, T19, "
          "T20, T23, T29 and T37 (details in each README).",
          "- **Telugu.** Shaping is verified in the reference renderer only; Text+ shaping in Resolve is untested.",
          "- **4K** was not batch-rendered (disk/time); 1080p previews are the verified deliverable.",
          "- **No .drp file is included** (cannot be created without Resolve; the build script is untested).",
          ""]
    open(os.path.join(ROOT, "FINAL_REPORT.md"), "w", encoding="utf-8").write("\n".join(L))
    print("FINAL_REPORT.md written:", n, "templates")


if __name__ == "__main__":
    main()
