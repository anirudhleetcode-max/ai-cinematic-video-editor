# Importing the templates into DaVinci Resolve

> **Status:** none of these files has been opened in DaVinci Resolve or Fusion. The machine that built
> them had no Resolve. The Fusion text format, node IDs and input names follow documentation and forum
> examples, and every file parses as a valid Lua table in a real Lua interpreter. Please try **one**
> template first (the steps under "First-run check" below) before you rely on the whole library.

There are three ways to use a template. Path A is the easiest.

## Path A: Edit-page Fusion Titles (recommended)

1. **Install the fonts and macros.** In PowerShell, from this folder:
   ```powershell
   .\install_titles.ps1 -InstallFonts
   ```
   This copies `Fusion_Macros\*.setting` into
   `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Templates\Edit\Titles\Cinematic Mass Elevation\`.
   On macOS the folder is `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit/Titles/`, and on Linux it is `~/.local/share/DaVinciResolve/Fusion/Templates/Edit/Titles/`.
   Existing files are never overwritten unless you add `-Force`.

   To install by hand, copy the `.setting` files to that folder yourself, and install the fonts from `02_SHARED_ASSETS/Fonts`.
2. **Set the default title length.** Go to *Preferences > User > Editing > Standard Generator Duration* and set it to **10 seconds**. The templates are 6–10 s long; T40 is 10 s.
3. **Set the timeline format.** Use a 24 fps timeline, at 1920x1080 or 3840x2160 UHD.
4. **Restart Resolve.**
5. **Add a title.** On the Edit page, open *Effects > Toolbox > Titles*. The templates are under the *Fusion Titles* section, named `T01_Obsidian_Impact` … `T40_Ultimate_Mass_Elevation`. Drag one onto V2 or above.
6. **Trim the clip** to the template length. Each template's README gives its frame count; most are 192 frames (8 s).
7. **Edit it.** Select the clip and open the *Inspector > Title* tab:
   - Text controls: *Main Title*, *Subtitle*, and *Tagline* where present. Font, size, letter spacing, line spacing, alignment and colour sit next to the text field.
   - Timing controls: *Animation Start*, *Reveal Duration*, *Impact Frame*, *Exit Start*, *Exit Duration*.
   - Look controls: *Background/Particle/Glow/Impact Intensity*, *Camera Shake*, *Text Position/Scale/Rotation*, *Extrusion Depth*, *Letterbox*, *Accent Color*.

   For deeper edits, open the clip on the Fusion page.

## Path B: Fusion page (paste or import a composition)

- **Macro**
  1. Create a Fusion composition clip in your timeline (*Effects > Toolbox > Effects > Fusion Composition*) and open it on the Fusion page.
  2. Drag `Fusion_Macros/TNN_*.setting` into the Node Editor. You can also open the file in a text editor, copy everything, and press Ctrl+V in the Node Editor.
  3. Connect the macro's output to `MediaOut1`.
- **Composition**
  1. On the Fusion page, choose *File > Import > Fusion Composition…* and pick `Fusion_Compositions/TNN_*.comp`.
  2. The final node is named in the template README (usually `Letterbox` or `Grain`). Connect it to `MediaOut1` if Resolve did not.

  One forum report says this menu did nothing in Resolve 20. If that happens, use the macro route above.
- **Fusion Studio (standalone)**: open the `.comp` directly.

## Path C: Build a native .drp with the included script

`00_PROJECT_FILES/DaVinci_Resolve_Project/build_resolve_project.py` creates the project, one timeline per template, imports each `.comp`, and exports a real `.drp`. Full instructions are inside the file.

Limits:
- This route needs Resolve scripting to be available. According to a September 2026 report, scripting was removed from the free edition in 21.1.
- The script is **untested**.
- It refuses to overwrite an existing project of the same name.

## First-run check (please do this once)

1. Install T01 using Path A, add it to a 1080p / 24 fps timeline, and trim it to 192 frames.
2. Scrub through frames 0, 40, 84, 120 and 170. Compare them with `01_TEMPLATES/T01_Obsidian_Impact/preview/T01_Obsidian_Impact.mp4`. They should match in structure (dark build-up, edge ignition at 84, hold, fade-out), but expect the details to differ.
3. Change *Main Title* and drag *Impact Frame*. The rim ignition and the burst should move with it.
4. If a node shows an error or a value looks wrong, see `07_DOCUMENTATION/Troubleshooting.md`. Notes on uncertain input names are in `COMPATIBILITY_REPORT.md`.

## Per-template manual test list

`Resolve_Test_Checklist.md` (in this folder) lists, for each template:
- its frame count and impact frame;
- its depth model (3D or 2.5D);
- the input names that could not be confirmed and should be checked first;
- any Fusion-specific approximations.

## What lives where

| Folder | Contents |
|---|---|
| `Fusion_Macros/` | 40 `.setting` macros (editable titles with published controls) |
| `Fusion_Compositions/` | 40 flat `.comp` compositions (same node graphs, ungrouped) |
| `Media/` | Empty on purpose. The templates use no external media; everything is procedural. |
| `install_titles.ps1` | Installer for macros and fonts (Windows / macOS / Linux PowerShell 7) |
| `Resolve_Test_Checklist.md` | What to check per template in your first Resolve session |
