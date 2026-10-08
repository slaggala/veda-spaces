#!/usr/bin/env bash
# Browser E2E against a real local stack (12 §4.8; IR-14, IR-38): Flask API on SQLite, the SPA on Vite, and the
# marketing site served with its production headers (intake on at :8000, flag off at :8001).
#   API_PYTHON=<python with api deps> app/e2e/run-all.sh
# Exit status is non-zero if any journey fails. Artifacts (screenshots, logs) go to app/e2e-artifacts/.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API="$ROOT/api"; APP="$ROOT/app"; OUT="$APP/e2e-artifacts"
PY="${API_PYTHON:-$API/.venv/bin/python}"
mkdir -p "$OUT"
pids=()
cleanup() { for p in "${pids[@]}"; do kill "$p" 2>/dev/null; done; wait 2>/dev/null; }
trap cleanup EXIT

for port in 5000 5173 8000 8001; do
  if curl -fsS "http://127.0.0.1:$port/" >/dev/null 2>&1 || curl -fsS "http://localhost:$port/" >/dev/null 2>&1; then
    echo "port $port is already in use: stop the process first"; exit 1
  fi
done

wait_for() { for _ in $(seq 1 60); do curl -fsS "$1" >/dev/null 2>&1 && return 0; sleep 1; done; echo "timeout: $1"; return 1; }

( cd "$API" && PYTHON="$PY" tools/e2e_reset.sh ) > "$OUT/bootstrap.txt" || { cat "$OUT/bootstrap.txt"; exit 1; }
INVITE_LINK="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["invite_link"])' "$API/var/bootstrap.json")"

# Each server is exec'd so the tracked pid is the server itself and cleanup stops it.
( cd "$API" && exec env VEDA_ENV=local VEDA_DATABASE_URL=sqlite:///var/e2e.db VEDA_COOKIE_SECURE=false \
    VEDA_EMAIL_CAPTURE_DIR=var/mail VEDA_ARGON2_MEMORY_KIB=19456 VEDA_ARGON2_TIME_COST=2 \
    VEDA_PUBLIC_SITE_ORIGINS=http://localhost:8000 VEDA_ANCHOR_DIR=var/anchors VEDA_ESTIMATOR_ENABLED=true \
    "$PY" -m flask --app wsgi run --port 5000 ) > "$OUT/api.log" 2>&1 & pids+=($!)
( cd "$APP" && exec node node_modules/vite/bin/vite.js --port 5173 --strictPort ) > "$OUT/vite.log" 2>&1 & pids+=($!)
node "$APP/e2e/static-server.mjs" "$APP/e2e/site-release" 8000 http://localhost:5000 > "$OUT/site-on.log" 2>&1 & pids+=($!)
node "$APP/e2e/static-server.mjs" "$APP/e2e/site-release" 8001 > "$OUT/site-off.log" 2>&1 & pids+=($!)
wait_for http://127.0.0.1:5000/health/live && wait_for http://localhost:5173/ && wait_for http://localhost:8000/ \
  && wait_for http://localhost:8001/ || exit 1

status=0
cd "$APP"
run() { echo "== $1"; E2E_OUT="$OUT" API_DIR="$API" API_PYTHON="$PY" INVITE_LINK="$INVITE_LINK" node "e2e/$1" || status=1; }
run workspace.e2e.mjs
run access.e2e.mjs
run site.e2e.mjs
run estimator.e2e.mjs
run estimator-v2-prototype.e2e.mjs
run axe.e2e.mjs
exit $status
