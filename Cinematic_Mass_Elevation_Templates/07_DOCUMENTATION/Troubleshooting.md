# Troubleshooting

These Fusion files were generated and statically validated. They were **not** tested inside Resolve (see
COMPATIBILITY_REPORT.md), so the entries below include the failure modes that are most likely on a
first import.

| Symptom | Likely cause | Fix |
|---|---|---|
| Titles don't appear in Effects > Titles | Wrong templates folder for your Resolve version, or Resolve not restarted | Restart Resolve. In the Effects panel, right-click a Fusion Title > *Show Folder* (or open Fusion page > Effects > Templates) to find the real folder, then run `install_titles.ps1 -Target "<that folder>"`. |
| Text shows in a default font | Bundled font not installed | `install_titles.ps1 -InstallFonts`, restart Resolve, or pick any installed font in the Inspector. |
| Title clip is too short / animation cut off | Standard Generator Duration is 5 s by default | Trim the clip longer (8–10 s), or set Preferences > User > Editing > Standard Generator Duration = 10 s before adding titles. |
| A node shows a red error / expression error | An expression function or input name differs in your Fusion version | Open the node and right-click the parameter > *Remove Expression*, then set a value or keyframes. Please note which node failed; `COMPATIBILITY_REPORT.md` lists the input names marked as unconfirmed. |
| Particles missing | pEmitter style/colour input names unconfirmed, or Particle Intensity = 0 | Check *Particle Intensity*. On the `*Emitter` node, set Style to *Blob* and choose a colour by hand. |
| Particles render oddly sized | Particle size units differ between versions | Adjust `*Emitter` > Style > Size. |
| Imported .comp shows nothing in the viewer | Final node not connected to MediaOut1 | Connect the node named in the template README ("Final node") to `MediaOut1`. |
| File > Import > Fusion Composition does nothing | Reported Resolve 20 issue | Use the `.setting` macro instead: drag it into the Node Editor. |
| 3D template is black | Renderer3D uses OpenGL; lights or camera not selected | On `*Render` select the `*Camera` in *Camera*, enable lighting, or switch Renderer Type to Software. |
| Light sweep / rim too strong | Expression gains assume Resolve's default glow response | Lower *Glow Strength*. |
| Telugu letters broken in Resolve | Text+ shaping limitation | Use the reference renderer for that title (`render_title.py ... --set FONT_FAMILY=telugu`), then import the clip. |
| `render_all.ps1` says Python packages missing | Dependencies not installed | `pip install numpy opencv-python-headless pillow lupa` |
| PowerShell blocks the script | Execution policy | `powershell -ExecutionPolicy Bypass -File .\render_all.ps1` |
| Reference render slow | CPU-only renderer | Use 1080p while editing, render 4K only at the end, and use `render_previews.ps1 -Jobs <cores>`. |

If you find a Fusion incompatibility, the generator can fix it for all 40 templates at once. The node
graphs come from `06_AUTOMATION/Scripts/cmet/fcomp.py`, so correct the component there and run
`python build.py sources`.
