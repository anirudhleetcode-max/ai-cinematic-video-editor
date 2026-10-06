# FAILATHON AV: spot-edit kit

A beat-synced, cinematic mass edit built automatically from the event footage and the exact BGM.
The tools here render the final MP4 and then build the editable DaVinci Resolve project, which exports the genuine `.drp`.

## Fastest path (Windows laptop with the footage and Resolve)

1. Get this repo onto the laptop: `git clone` it, or download the branch as a zip.
2. Put the BGM at `FAILATHON_AV\01_AUDIO\BGM_FAILATHON.mp3`. Audio is kept out of git, so copy it from WhatsApp.
3. Open **DaVinci Resolve**. Set *Preferences > System > General > External scripting using* to **Local**.
4. Double-click `08_SCRIPTS\RUN_FAILATHON.bat`, or run:
   ```
   08_SCRIPTS\RUN_FAILATHON.bat "C:\Users\aniru\Downloads\Ecellfailthon-20261006T194834Z-1-001\Ecellfailthon" "C:\path\to\bgm.mp3"
   ```
   It installs numpy, Pillow and librosa, and installs FFmpeg through winget if it's missing. It then renders the edit and builds the Resolve project.

Options (append to the command):
`--order "arrival,registration,stage,activities,teams,prize"` (folder or filename keywords, in event order)
`--presenter "E-CELL PRESENTS"` · `--tagline "FAIL · LEARN · RISE"` · `--words "FAIL FAST,BUILD BOLD,RISE HIGHER"`.
Without `--order`, clips are placed in capture-time order, which follows the real event.

## Outputs
| File | What |
|---|---|
| `07_EXPORTS/FAILATHON_AV_FINAL.mp4` | Final 1920x1080 30p H.264 (CRF 16), AAC 320k |
| `06_PREVIEWS/FAILATHON_AV_PREVIEW.mp4` | 540p preview |
| `06_PREVIEWS/CONTACT_SHEET.jpg` | Every source file with its grade (A/B/C/D, DUPLICATE, REJECT) |
| `06_PREVIEWS/FINAL_FRAME_STRIP.jpg` | One frame per second of the final, for a quick visual check |
| `03_RESOLVE/FAILATHON_AV_FINAL.drp` | **Exported by Resolve** through `FAILATHON_AV_RESOLVE_SCRIPT.py`, then re-imported to validate it |
| `03_RESOLVE/FAILATHON_AV_FINAL.fcpxml` / `.edl` | Timeline interchange (Resolve: File > Import > Timeline) |
| `09_REPORTS/` | MEDIA_MANIFEST.csv, BEAT_MAP.csv, EDIT_REPORT.md, VALIDATION_REPORT.md, RESOLVE_VALIDATION.md |

## What the edit does
- **Rapid analysis**: sharpness, exposure, contrast and motion from keyframes sampled at 2 fps; A/B/C/D grading. Perceptual-hash duplicate detection keeps the best copy.
- **BGM as master clock**: beat grid, downbeats, drops (energy jumps) and strong hits. Every cut lands on a beat, and shot length follows the music's energy (8-beat intro shots down to single-beat drop cuts).
- **Hits**: drops get a cut, white flash, decaying shake, punch-in, impact SFX and a title slam. Section changes get a whip blur and a whoosh, and a riser leads into the drops.
- **Speed ramps**: fast→slow-motion on hero motion shots, normal→fast into drops, and a 0.5x slow-motion hero under the end card.
- **Titles**: animated (tracking-in, blur-to-sharp, scale slam, accent line), rendered as ProRes 4444 with alpha, using Inter Display (bundled, OFL licence).
- **Colour**: per-clip exposure balance, then one unified gentle look (S-curve, teal/warm split, vignette).
- **Audio**: the BGM is never cut or replaced, only gain-staged to −1 dBFS. SFX sit under it, there's a limiter at −1 dBFS, and camera audio is muted.

Source media is only read and never modified.
