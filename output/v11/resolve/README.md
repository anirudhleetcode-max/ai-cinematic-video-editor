# v11 "OK Kanmani": DaVinci Resolve package

This package rebuilds the v11 edit as an editable Resolve timeline. Resolve's own `.drp` project file can only be written by Resolve itself. Once the timeline is built, File > Export Project gives you one.

## Contents

| Path | What it is |
|---|---|
| `media/shots/*.mp4` | The 19 shots as rendered: doodle background, sparkly outline, stickers, black-and-white cut-out. Each includes its transition overlap frames as handles. |
| `media/transitions/*.mp4` | The 11 transitions exactly as rendered: star, heart and circle irises, whip pans, zoom punch, brush reveal, gold light leak, dissolve, fade to cream |
| `media/audio/OK_Kanmani_Song.wav` | The song as WAV, at its exact length. An MP3's encoder delay stops Resolve relinking it. |
| `timeline.json` | The frame-exact layout that the files below are generated from |
| `build_resolve_project.py` | Builds the project inside Resolve (see option 1 below) |
| `OK_Kanmani_v11.fcpxml` | Timeline for File > Import > Timeline. Its paths point to `/PATH/TO/resolve/`, so relink to this folder when Resolve asks. |
| `OK_Kanmani_v11_DOWNLOADS.fcpxml` | The same timeline with paths already set to `C:\Users\aniru\Downloads\OK_Kanmani_v11_resolve\resolve\`, the folder Windows **Extract All** creates in Downloads. No relinking is needed if the files are there. |
| `OK_Kanmani_v11_V1.edl` | CMX3600 EDL of the cuts track |

## Timeline (1920×1080, 30 fps, 30.0 s)

| Track | Contents |
|---|---|
| V1 | 19 shots on hard cuts at the exact cut frames |
| V2 | The 11 transitions placed over the cuts |
| A1 | The song, from 0 s |

V1 plus V2 reproduces `cute_doodle_ok_kanmani_v11.mp4` frame for frame. Disable V2 to see the bare cuts, or swap in Resolve's own transitions.

## How to open it in Resolve

1. **Run the build script.** Copy this folder into Resolve's scripts folder (`.../Fusion/Scripts/Edit/`), then run Workspace > Scripts > Edit > build_resolve_project.
2. **Or import the FCPXML:** File > Import > Timeline > `OK_Kanmani_v11.fcpxml`, then relink to `media/`.
3. **Or connect Filmit:** in Resolve, turn on Workspace > Workflow Integrations > Filmit Studio > MCP, and tell Claude where this folder is on your computer. Claude then builds the timeline.
