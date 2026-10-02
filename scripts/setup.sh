#!/usr/bin/env bash
# Linux / macOS setup. Usage: ./scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
need() { command -v "$1" >/dev/null 2>&1; }
echo "== Checking toolchain"
need python3 || { echo "Python 3.10+ is required"; exit 1; }
need node || { echo "Node.js 20+ is required"; exit 1; }
if ! need ffmpeg || ! need ffprobe; then
  echo "FFmpeg not found."
  if [[ "$(uname)" == "Darwin" ]]; then echo "  install: brew install ffmpeg"; else echo "  install: sudo apt-get install -y ffmpeg   (or your distro's package)"; fi
  exit 1
fi
ffmpeg -hide_banner -filters 2>/dev/null | grep -q " xfade " || echo "WARNING: your ffmpeg lacks xfade (need >= 4.3)"
ffmpeg -hide_banner -filters 2>/dev/null | grep -q " ass " || echo "WARNING: ffmpeg built without libass — titles/captions will not render"
echo "== Python environment (.venv)"
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -e "services/engine[dev]"
echo "== Web app"
(cd apps/web && npm install)
[ -f .env ] || cp .env.example .env
echo "== Health check"
python -c "import sys; sys.path.insert(0,'services/engine'); from editor.hw import diagnostics; import json; d=diagnostics(); print(json.dumps({k:d[k] for k in ('ffmpeg','encoders','selected_encoder','gpu','cpu_count','ram_total_gb')}, indent=1))"
echo
echo "Done. Start everything with:  npm run dev   (API on :8000, web on :3000)"
