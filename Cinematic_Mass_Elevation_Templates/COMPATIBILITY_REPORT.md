# Compatibility Report

## 1. Environment audit (Phase 1)

| Item | Finding |
|---|---|
| Operating system | Ubuntu 24.04 (Linux 6.18 kernel, x86-64) cloud container. **Not Windows.** |
| Requested location `C:\Users\aniru\Documents\Cinematic_Mass_Elevation_Templates` | Not available on this machine. The project was built in the repository folder `Cinematic_Mass_Elevation_Templates/` and uses only relative paths, so you can copy the folder to that location. |
| Free disk space at start | 30 GB on the build volume. All previews were rendered at 1080p. No 4K batch was run. |
| DaVinci Resolve | **Not installed.** Not installable here either: the download is gated behind a registration form, and the app needs a GPU desktop session. |
| Fusion Studio (standalone) | **Not installed** (paid product). |
| Resolve version | Not applicable. |
| Blender | Not installed. It was not needed: genuine 3D is done natively with Fusion `Text3D`/`Renderer3D`. |
| FFmpeg / ffprobe | 6.1.1, with libx264, ProRes (prores_ks) and AAC. |
| Python | 3.13 with NumPy 2.5, Pillow 12.3 (FreeType + **libraqm** complex-script shaping), OpenCV 5.0 headless, and lupa 2.8 (an embedded **Lua 5.5** interpreter used to parse the Fusion files). |
| PowerShell | Not present at first. PowerShell 7.6 was installed from Microsoft's apt repository so the `.ps1` scripts could be executed and tested on Linux. They are written to stay compatible with Windows PowerShell 5.1 syntax. |
| Installed system fonts | DejaVu, Liberation, Inter, Noto Color Emoji, FreeFont, IPA, WenQuanYi and others. There was no condensed display face and no Telugu face. |
| Fonts added | 14 OFL families from the Google Fonts distribution, bundled with their licences: Anton, Bebas Neue, Black Ops One, Russo One, Cinzel, Cinzel Decorative, Marcellus SC, Orbitron, Audiowide, Staatliches, Teko, Ramabhadra (Telugu), Noto Sans Telugu, Mandali (Telugu). |
| Paid plugins | None used or required. |

## 2. What "compatible" means here: three separate levels

| Level | Method | Status |
|---|---|---|
| **Source valid** | Each `.setting` and `.comp` is evaluated by a real Lua 5.5 interpreter, with Fusion's constructors stubbed out. The resulting tree is then checked: every `SourceOp` exists; every expression reference resolves; every `CONTROLS.x` is a defined user control; every published control is used; there is an editable text node, time-based animation and a defined exit; every tool ID is on the known list. | Run on every template; see QUALITY_ASSURANCE_REPORT.md |
| **Preview rendered** | Python reference renderer → H.264 MP4, checked with ffprobe and frame sampling | Run on every template; see QUALITY_ASSURANCE_REPORT.md |
| **Works in Resolve** | Open, play and render inside DaVinci Resolve or Fusion | **NOT TESTED for any template** |

A file that parses and passes the structural checks can still misbehave in Resolve. The likely causes are listed below.

## 3. Fusion format: sources and confidence

The node and input identifiers come from documentation and real pasted node text found in forum and blog
excerpts. They were compiled into `06_AUTOMATION/Scripts/cmet/fusion_ref.py`, with an evidence grade for
each entry:
- **S**: seen in real node text or docs.
- **K**: established usage that was not re-confirmed.
- **?**: unconfirmed.

The validator only allows tool IDs graded S or K. Each template's manifest records how many S, K and ?
inputs it uses.

Fusion ignores unknown inputs when it loads a file. If an input name is wrong, that one setting is lost
(for example, a particle colour falls back to its default); the file still loads. An unknown tool ID would
be a load error, which is why only S/K tool IDs are allowed.

**Most likely to need a manual touch-up in Resolve:**

| Area | Uncertainty | Effect if wrong | Manual fix |
|---|---|---|---|
| `pEmitter` style/colour/size names (`["ParticleStyle.Red"]`, `Style`) and `pTurbulence` strengths | K/? | Particles have the default look (white, default size) | Set colour/size on the `*Emitter` node |
| `pRender` frame size inputs | ? | Particle layer renders at the default size | Set the size on `*Render`, or enable *Use Frame Format Settings* |
| `DirectionalBlur` `Type` numbering (Linear/Radial/Centered/Zoom) | K | Wrong blur type (e.g. the T40 light shafts) | Choose the type in the node |
| `Renderer3D` sub-inputs (`RendererOpenGL.LightingEnabled`, `Supersampling`) and `MtlBlinn` input names | ?/K | 3D title unlit, or the material colour has its default value | Enable lighting on the renderer; set colours on `*Mtl` |
| `PolylineMask` point table format (lightning, cracks, shards, shutter) | K | Shape missing | Redraw the polyline |
| Expression functions | Only `min`, `max`, `abs`, `sin`, `cos`, `floor`, `pow`, `Point` and `time` are used. `pow`, `min`, `max`, `sin`, `cos`, `floor` and `Point` appear in documentation excerpts (S); `abs` is standard Lua math (K). `exp()` and `^` were deliberately avoided, and the validator flags them | An expression evaluates to an error | Right-click the parameter > Remove Expression and set a value |
| `.comp` import via File > Import > Fusion Composition | One forum report says it fails in Resolve 20 | Nothing imports | Use the `.setting` macro |
| Text+ shaping of Telugu inside Resolve | Untested | Broken conjuncts | Use the reference renderer for Telugu titles |

The graphs are generated from `cmet/fcomp.py`, so a confirmed correction can be made once and applied
to all 40 templates with `python build.py sources`.

## 4. Native Resolve project (.drp)

**No `.drp` file is shipped.** A `.drp` can only be produced by Resolve itself, and no fake or renamed file
was created. `00_PROJECT_FILES/DaVinci_Resolve_Project/build_resolve_project.py` uses the documented
scripting API to build the project and export a genuine `.drp` on your machine:
- `CreateProject`
- `CreateEmptyTimeline`
- `InsertFusionCompositionIntoTimeline`
- `ImportFusionComp`
- `ExportProject`
- `SetRenderSettings` / `AddRenderJob` / `StartRendering`

The script is **untested**. External scripting needs Resolve Studio. A September 2026 report says Resolve
21.1 removed scripting from the free edition entirely. The manual import procedure in
`05_RESOLVE_IMPORT/Import_Instructions.md` works without scripting.

## 5. Preview renderer vs. Fusion output

The preview MP4s are **not** Fusion renders. They come from the project's reference renderer, which
implements each design separately in Python: the same concept, timing, controls, colours and text. Expect
these differences from what Resolve produces:
- noise character (FFT noise vs. Fusion FastNoise);
- particle appearance;
- glow falloff;
- material detail. The preview shades a bevel from a distance field; the Fusion 2.5D titles use gradient
  fills plus edge-light passes.

The 3D templates use Fusion's real `Text3D` geometry in the source. Their previews approximate the
extruded solid with perspective-projected slices.
