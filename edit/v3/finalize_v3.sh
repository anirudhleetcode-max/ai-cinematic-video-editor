#!/usr/bin/env bash
# Join v3 chunks, add the original soundtrack (0.3 s fade-in, 1 s fade-out),
# write to a temp name and rename only on success.
set -euo pipefail
WORK="${EDIT_WORK:?}"
SRC="${EDIT_SOURCE:?}"
OUT_DIR="$(cd "$(dirname "$0")/../.." && pwd)/output"
TMP="$OUT_DIR/.cinematic_doodle_music_edit_v3.partial.mp4"
FINAL="$OUT_DIR/cinematic_doodle_music_edit_v3.mp4"
DUR=$(python3 -c "print(3396/30)")
ffmpeg -v error -y -f concat -safe 0 -i "$WORK/v3chunk.txt" -i "$SRC" \
  -map 0:v:0 -map 1:a:0 -c:v copy \
  -af "atrim=0:$DUR,afade=t=in:d=0.3,afade=t=out:st=$(python3 -c "print($DUR-1.0)"):d=1.0" \
  -c:a aac -b:a 256k -t "$DUR" -movflags +faststart "$TMP"
mv "$TMP" "$FINAL"
ffprobe -v error -show_entries format=duration,size,bit_rate:stream=codec_name,profile,width,height,r_frame_rate,channels,sample_rate -of compact "$FINAL"
