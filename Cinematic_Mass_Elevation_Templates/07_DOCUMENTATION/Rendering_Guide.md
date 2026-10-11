# Rendering Guide

## 1. Rendering from DaVinci Resolve (customised Fusion titles)

DaVinci Resolve has no supported command-line renderer, so final renders happen inside Resolve.

1. Put the title on a 24 fps timeline, either at UHD 3840x2160 for 4K or at 1920x1080. Trim the clip to the template length; most are 192 frames.
2. Over a background clip, the title composites with alpha. To render a stand-alone title clip, set In/Out to the title.
3. On the **Deliver** page, choose either:
   - *QuickTime*, *Apple ProRes 422 HQ* (mezzanine), at timeline resolution, 24 fps, or
   - *MP4 / H.264* (or *H.265*) at a high quality setting.
4. Check *Render at source resolution* or set 3840x2160, then *Add to Render Queue* and *Render All*.
5. Optional: to get a title with transparency, use *QuickTime ProRes 4444* with *Export Alpha* enabled.
   You must also remove or disable the template's environment branch and the letterbox, because the
   templates are designed as full-frame shots.

Batch option:
- `00_PROJECT_FILES/DaVinci_Resolve_Project/build_resolve_project.py --render` builds one timeline per template and queues a ProRes job for each into `04_FINAL_RENDERS/Template_NN/`.
- It needs Resolve scripting to be available, and it is **untested**.
- `render_all.ps1 -Engine resolve` prints these steps.

## 2. Rendering with the reference renderer (no Resolve)

This renderer produced the previews. You can use it for real deliverables, and it reproduces each template's
design with your text, colours and timing. Requirements: Python 3.10+, `pip install numpy opencv-python-headless pillow`, and FFmpeg on PATH.

```powershell
# one customised 4K ProRes title
python 06_AUTOMATION\Scripts\render_title.py T40 --set MAIN_TITLE="YOUR NAME" --res 3840x2160 --codec prores --out yourname.mov

# all templates, final 4K ProRes 422 HQ into 04_FINAL_RENDERS\Template_NN\ (+ report)
.\render_all.ps1 -Mode final

# selected templates at 1080p H.264
.\render_all.ps1 -Mode final -Templates T01,T07,T40 -Resolution 1920x1080 -Codec h264

# regenerate previews, thumbnails, manifests, catalog
.\render_previews.ps1
```

`render_all.ps1`:
- validates each manifest and the files it requires;
- creates the output folders;
- renders each template;
- checks every output with ffprobe for existence, size and duration;
- keeps going if one template fails;
- writes `06_AUTOMATION/Validation/render_report_<timestamp>.md/.json`.

Render time, measured on one 2026 cloud CPU core:
- about 1.5 s per frame at 1080p, so about 5 min per 8 s title;
- roughly 4× that at UHD.

`render_previews.ps1` renders in parallel (`-Jobs`).

Disk use:
- 1080p H.264 preview: about 3–5 MB.
- UHD ProRes 422 HQ (~707 Mb/s at 24 fps): about 0.7 GB for 8 s.
- All 40 at UHD ProRes: about 28–30 GB.

Render 4K only for the templates you need.

## 3. Sound

- **Previews:** the preview MP4s contain a procedural cue mix built from the template's `documentation/sound_design.md`.
- **Reference-renderer exports:** these include the same mix unless you pass `--no-audio`.
- **Resolve:** place the one-shots from `02_SHARED_ASSETS/Sound_Effects/` at the frames listed in the cue sheet, or use your own library.
