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
    rcanon_p = os.path.join(ROOT, "06_AUTOMATION", "Validation", "resolve_test_results.json")
    rcanon = json.load(open(rcanon_p, encoding="utf-8")) if os.path.exists(rcanon_p) else {"templates": {}}
    rv = {m["id"]: (m["verification"].get("resolve") or {"status": "NOT TESTED"}) for m in ms}

    def rcount(level):
        c = {}
        for v in rv.values():
            k = v.get(level, "NOT TESTED") or "NOT TESTED"
            c[k] = c.get(k, 0) + 1
        return ", ".join("**%s %d/%d**" % (k, c[k], n) for k in sorted(c))

    lc = rcanon.get("last_connection") or {}
    rconn = ("connected: %s %s (run %s)" % (lc.get("product"), lc.get("version"), rcanon.get("last_run"))
             if lc.get("connected") else "**not connected** - last harness run `%s` could not reach DaVinci Resolve "
             "(no Resolve installation in that environment)" % rcanon.get("last_run"))
    L = [
        "# Final Report - Cinematic Mass Elevation Templates", "",
        f"Generated {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} by "
        "`06_AUTOMATION/Scripts/final_report.py` from the validated manifests and `06_AUTOMATION/Validation/test_results.json`.",
        "",
        "## Summary", "",
        "| Item | Result |", "|---|---|",
        f"| Template definitions | **{n}** (T01-T40, 8 categories A-H as in the brief) |",
        f"| Editable Fusion compositions | **{n} macros (.setting) + {n} flat compositions (.comp)** |",
        f"| A. Fusion source structural validation | **{src}/{n} PASS** |",
        f"| B. Standalone Python preview validation (1080p) | **{prv}/{n} PASS** |",
        f"| C. DaVinci Resolve composition loading | {rcount('C_load')} |",
        f"| D. DaVinci Resolve rendering | {rcount('D_render')} |",
        f"| E. Editable text and controls (in Resolve) | {rcount('E_edit')} |",
        f"| F. Visual comparison Resolve vs. preview | {rcount('F_visual')} |",
        f"| Overall Resolve status | {rcount('status')} |",
        f"| Resolve connection | {rconn} |",
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
        "| ID | Template | Category | Length | Depth | A Source | B Preview | Tests | Resolve (C/D/E/F) | Preview path |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in ms:
        r = by.get(m["id"], {"checks": {}, "errors": ["not tested"]})
        L.append(f"| {m['id']} | {m['name']} | {m['category'].split(' - ')[0]} | {m['duration_frames']}f / "
                 f"{m['duration_seconds']:.1f}s | {'3D' if m['true_3d'] else '2.5D'} | "
                 f"{'PASS' if m['verification']['structure'] == 'PASS' else 'FAIL'} | "
                 f"{'PASS' if m['verification']['preview'] == 'PASS' else 'FAIL'} | "
                 f"{sum(r['checks'].values())}/{len(r['checks'])} | "
                 f"{rv[m['id']].get('status')} ({rv[m['id']].get('C_load')}/{rv[m['id']].get('D_render')}/"
                 f"{rv[m['id']].get('E_edit')}/{rv[m['id']].get('F_visual')}) | `01_TEMPLATES/{m['_dir']}/{m['preview']}` |")
    groups = {}
    for tid, v in rv.items():
        groups.setdefault(v.get("status", "NOT TESTED"), []).append(tid)
    L += ["", "## Resolve test lists", ""]
    for k in ("PASS", "FAIL", "BLOCKED", "NOT TESTED"):
        L.append("- **%s (%d):** %s" % (k, len(groups.get(k, [])), ", ".join(sorted(groups.get(k, []))) or "none"))
    L += ["", "## Manual actions still required", "",
          "1. On the Windows PC with DaVinci Resolve, run the read-only audit: "
          "`powershell -ExecutionPolicy Bypass -File 06_AUTOMATION\\Resolve\\run_resolve_tests.ps1 -AuditOnly`.",
          "2. Start Resolve. Set *Preferences > User > Editing > Standard Generator Duration* to 10 s. "
          "In Resolve Studio, also set *Preferences > System > General > External scripting using* to Local.",
          "3. Run the end-to-end T01 test: `run_resolve_tests.ps1 -Templates T01`. "
          "In the free edition, use *Workspace > Scripts > Utility > CMET_Run_Resolve_Tests*.",
          "4. If T01 passes, run all 40 (`run_resolve_tests.ps1`), then commit "
          "`06_AUTOMATION/Validation/resolve_runs/<run>/` and `resolve_test_results.json`. Re-run "
          "`build.py validate`, `qa.py`, `catalog.py` and `final_report.py`, or hand the results back to Claude "
          "to analyse and fix any FAIL templates.",
          "5. Review the side-by-side sheets in `resolve_runs/<run>/comparisons/` (level F visual review).", ""]
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
          "- **Resolve testing.** See the Summary (levels C-F). Until the harness has run on a machine with Resolve, compatibility rests on "
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
