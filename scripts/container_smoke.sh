#!/usr/bin/env bash
# Start the compose stack (api + worker + web containers), wait for health, run the end-to-end smoke flow, stop.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${SMOKE_OUT:-docs/container_smoke.json}
docker compose up -d --no-build
trap 'docker compose logs --no-color --tail=80 api worker > /tmp/cutroom-compose.log 2>&1 || true; docker compose down -v' EXIT
for i in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -sS http://localhost:8000/health; echo
python3 -m pip install -q httpx 2>/dev/null || true
python3 scripts/smoke_flow.py --api http://localhost:8000 --web http://localhost:3000 --out "$OUT" ${SMOKE_MEDIA:+--media "$SMOKE_MEDIA"}
