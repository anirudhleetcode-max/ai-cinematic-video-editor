# Installation Guide

## 1. Copy the library

Copy the whole `Cinematic_Mass_Elevation_Templates` folder to a location of your choice. The suggested
location is `C:\Users\<you>\Documents\Cinematic_Mass_Elevation_Templates`.

All internal references are relative, so the folder can live anywhere.

| Part | Approximate size |
|---|---|
| Whole library | ~200 MB, mostly 1080p previews |
| Sources and docs | a few MB |

## 2. DaVinci Resolve titles (editable templates)

```powershell
cd <library>\05_RESOLVE_IMPORT
powershell -ExecutionPolicy Bypass -File .\install_titles.ps1 -InstallFonts
```

Then:
1. Restart Resolve.
2. Set *Preferences > User > Editing > Standard Generator Duration* to **10 s**.
3. Use the titles from *Edit page > Effects > Titles > Fusion Titles*.

For the manual and Fusion-page routes, see `05_RESOLVE_IMPORT/Import_Instructions.md`.

**Requirements:**
- DaVinci Resolve 18 or newer, free or Studio. **Untested; see COMPATIBILITY_REPORT.md.**
- The genuine-3D templates (T11, T12, T13, T15, T28) use Fusion's OpenGL 3D renderer.
- No third-party plugins are needed.

## 3. Optional: reference renderer and automation (Windows / macOS / Linux)

You need this only if you want to:
- render customised titles without Resolve,
- regenerate previews, or
- rebuild the Fusion files.

Setup:
1. Install **Python 3.10+** (python.org; tick "Add to PATH").
2. Install **FFmpeg** (ffmpeg.org) and add its `bin` folder to PATH.
3. Install the Python packages:
   ```
   pip install numpy opencv-python-headless pillow lupa
   ```
   `lupa` is only needed for validation.
4. Optional, Telugu shaping: Pillow wheels on Windows and macOS already include libraqm. On Linux, install
   `libraqm0` (or `libraqm`) if `python -c "from PIL import features; print(features.check('raqm'))"` prints False.

Test it:
```powershell
python 06_AUTOMATION\Scripts\render_title.py --list
python 06_AUTOMATION\Scripts\render_title.py T01 --set MAIN_TITLE="HELLO" --out hello.mp4
```

## 4. What is where

See `README.md` for the folder map and `TEMPLATE_CATALOG.html` to browse all templates.
