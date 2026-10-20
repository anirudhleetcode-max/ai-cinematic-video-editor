#!/usr/bin/env bash
# Pass 3: join rendered chunks, add the original audio (trimmed to the edit,
# short fade in/out), write to a temp name and rename only on success.
set -euo pipefail
WORK="${EDIT_WORK:?}"
SRC="${EDIT_SOURCE:?}"
OUT_DIR="$(cd "$(dirname "$0")/.." && pwd)/output"
mkdir -p "$OUT_DIR"
TMP="$OUT_DIR/.cute_doodle_music_edit_v2.partial.mp4"
FINAL="$OUT_DIR/cute_doodle_music_edit_v2.mp4"
DUR=$(python3 -c "print(3396/30)")   # N_OUT / FPS

ffmpeg -v error -y -f concat -safe 0 -i "$WORK/v2chunks.txt" -i "$SRC" \
  -map 0:v:0 -map 1:a:0 -c:v copy \
  -af "atrim=0:$DUR,afade=t=in:d=0.3,afade=t=out:st=$(python3 -c "print($DUR-1.0)"):d=1.0" \
  -c:a aac -b:a 192k -t "$DUR" -movflags +faststart "$TMP"
mv "$TMP" "$FINAL"
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate,channels -of compact "$FINAL"
