# Cinematic Mass Elevation Templates

A library of 40 original, editable cinematic title templates for DaVinci Resolve / Fusion. They cover
mass-elevation hero introductions, character and villain intros, dialogue reveals, title cards, event and
festival openers (college fests, hackathons, Failathons), trailers and logo reveals.

Every template ships as:
- an **editable Fusion macro** (`.setting`), which installs as an Edit-page Fusion Title with published
  controls;
- a **flat Fusion composition** (`.comp`) with the same node graph;
- a **1080p preview** with a procedural sound-cue mix, plus a thumbnail;
- a **manifest**, a README, a parameter reference, a sound-design cue sheet and a render profile.

> **Verification status, plainly:** the Fusion files were generated and statically validated. They parse in
> a real Lua interpreter, every node link, expression and control resolves, and every tool ID is a known
> Fusion ID. They were **not opened in DaVinci Resolve**, because the build machine had no Resolve.
>
> The previews were rendered by this project's Python reference renderer, not by Fusion.
>
> See [COMPATIBILITY_REPORT.md](COMPATIBILITY_REPORT.md) and [QUALITY_ASSURANCE_REPORT.md](QUALITY_ASSURANCE_REPORT.md).

## Start here

1. Browse: open **[TEMPLATE_CATALOG.html](TEMPLATE_CATALOG.html)** (works offline). You can also use
   [TEMPLATE_CATALOG.md](TEMPLATE_CATALOG.md) or the contact sheet
   `03_PREVIEWS/Contact_Sheets/contact_sheet_all.jpg`.
2. Install into Resolve: `05_RESOLVE_IMPORT/install_titles.ps1 -InstallFonts`, then follow
   [05_RESOLVE_IMPORT/Import_Instructions.md](05_RESOLVE_IMPORT/Import_Instructions.md). Do the one-template
   "First-run check" first.
3. Customise: in the Inspector, change **Main Title / Subtitle**, font, colours, **Impact Frame**, **Exit
   Start** and intensities. See [07_DOCUMENTATION/Template_Editing_Guide.md](07_DOCUMENTATION/Template_Editing_Guide.md).
4. Render: use the Deliver page in Resolve, or render without Resolve:
   `python 06_AUTOMATION/Scripts/render_title.py T40 --set MAIN_TITLE="YOUR TITLE" --res 3840x2160 --codec prores --out title.mov`.
   See [07_DOCUMENTATION/Rendering_Guide.md](07_DOCUMENTATION/Rendering_Guide.md).

## The 40 templates

| Category | Templates |
|---|---|
| A - Dark, Powerful Mass Elevation | T01 Obsidian Impact, T02 Thunder God, T03 Molten Core, T04 Black Steel Reckoning, T05 Shattered Monolith |
| B - Fire, Explosions and Impact | T06 Inferno Reveal, T07 Explosive Arrival, T08 Ember Storm, T09 Ashes of Power, T10 Shockwave Dominance |
| C - 3D Metal and Premium Materials | T11 Golden Emperor\*, T12 Chrome Dominion\*, T13 Titanium Edge\*, T14 Forged in Fire, T15 Diamond Cut\* |
| D - Mythic, Epic and Fantasy | T16 Ancient Titan, T17 Celestial Ascent, T18 Dark Sorcery, T19 Cosmic Overlord, T20 Phoenix Reborn |
| E - Sci-Fi and Futuristic | T21 Neon Overdrive, T22 Hologram Breach, T23 Digital Awakening, T24 Quantum Split, T25 Future Warlord |
| F - Cinematic Typography and Camera | T26 Extreme Close-Up, T27 Low-Angle Titan, T28 Rotating Monolith\*, T29 Cinematic Letter Assembly, T30 Speed Ramp Dominance |
| G - Atmospheric and Environmental | T31 Midnight Fog, T32 Rain and Steel, T33 Desert Storm, T34 Underwater Colossus, T35 Frozen Kingdom |
| H - Signature Hero Elevations | T36 Hero Silhouette, T37 Legacy Reveal, T38 Royal Insignia, T39 Final Boss, **T40 Ultimate Mass Elevation (flagship)** |

\* Genuine 3D in the Fusion source: `Text3D` extrusion and bevel, a `MtlBlinn` material, lights, `Camera3D`
and `Renderer3D`. All other templates are 2.5D: layered compositing, extrusion stacks and parallax, with no
3D geometry.

## Folder map

| Folder | Contents |
|---|---|
| `00_PROJECT_FILES/` | `Project_Manifest.json` (master list of templates and every file); `DaVinci_Resolve_Project/build_resolve_project.py` (builds and exports a real `.drp` inside your Resolve; untested). No `.drp` is shipped. |
| `01_TEMPLATES/TNN_Name/` | `source/` (.setting + .comp), `preview/` (mp4 + thumbnail), `configuration/` (render profile, default params), `documentation/` (parameters, sound design), `manifest.json`, `README.md` |
| `02_SHARED_ASSETS/` | `Fonts/` (14 OFL families incl. Telugu, with licences), `Sound_Effects/` (17 synthesised one-shots, CC0-style), `Procedural_Textures/` (tileable PNGs), READMEs for procedural backgrounds/particles/environment |
| `03_PREVIEWS/` | `Thumbnails/`, `Contact_Sheets/` (40-up sheet + six-frame strip per template); previews live in each template folder |
| `04_FINAL_RENDERS/` | Output folder for `render_all.ps1 -Mode final` (`Template_NN/`) |
| `05_RESOLVE_IMPORT/` | `Fusion_Macros/` (all 40 .setting), `Fusion_Compositions/` (all 40 .comp), `install_titles.ps1`, `Import_Instructions.md` |
| `06_AUTOMATION/` | `Scripts/` (generator, reference renderer, validator, catalog, QA, CLI), `Validation/` (build state, render reports) |
| `07_DOCUMENTATION/` | Editing, text (incl. Telugu), rendering, troubleshooting guides; developer authoring guide |

Root scripts:
- `render_all.ps1` renders the final or preview outputs with checks and a report.
- `render_previews.ps1` regenerates the sources, previews, manifests and catalog.

## Rebuilding

Everything is generated from `06_AUTOMATION/Scripts/cmet/`. Each template is one design module
(`designs/tNN.py`) that defines both its Fusion graph and its preview renderer.

```
cd 06_AUTOMATION/Scripts
python build.py all --jobs 4      # sources, previews, validation
python catalog.py && python qa.py
```

## Licences

- Templates, code, generated textures and sounds: original work created for this project.
- Fonts: SIL OFL 1.1, with licence files alongside.
- No copyrighted film material, logos, characters, music or dialogue is used.
