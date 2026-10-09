#!/usr/bin/env bash
# V1/V2 equivalence and the V2 checks against a real (private) rate card, on a throwaway local stack (pre-activation
# closure). The card never enters the repository and no amount is printed: only check names, pass/fail and the card's
# SHA-256, to compare with `veda estimator list-cards` on staging.
#   API_PYTHON=<python with api deps> app/e2e/run-real-card.sh <card.json outside the repository> [spec.json]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API="$ROOT/api"; APP="$ROOT/app"; OUT="$APP/e2e-artifacts"
PY="${API_PYTHON:-$API/.venv/bin/python}"
CARD="${1:-}"; SPEC="${2:-$ROOT/docs/implementation/estimator/specifications/essential-specification-v1.1.json}"
[ -f "$CARD" ] || { echo "usage: $0 <card.json> [spec.json]"; exit 2; }
CARD="$(cd "$(dirname "$CARD")" && pwd)/$(basename "$CARD")"
case "$CARD" in "$ROOT"/*) echo "refused: the card must stay outside the repository"; exit 2;; esac
mkdir -p "$OUT"
pids=()
cleanup() { for p in "${pids[@]}"; do kill "$p" 2>/dev/null; done; wait 2>/dev/null; }
trap cleanup EXIT
for port in 5000 8000; do
  curl -fsS "http://localhost:$port/" >/dev/null 2>&1 && { echo "port $port is already in use: stop the process first"; exit 1; }
done
wait_for() { for _ in $(seq 1 60); do curl -fsS "$1" >/dev/null 2>&1 && return 0; sleep 1; done; echo "timeout: $1"; return 1; }
estimator() { (cd "$API" && VEDA_ENV=local VEDA_DATABASE_URL=sqlite:///var/e2e.db "$PY" -m veda.cli estimator "$@"); }

( cd "$API" && PYTHON="$PY" tools/e2e_reset.sh ) > "$OUT/bootstrap.txt" || { cat "$OUT/bootstrap.txt"; exit 1; }
VERSION="$("$PY" -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' "$CARD")"
estimator load-card "$CARD" | "$PY" -I -c 'import json,sys;d=json.loads(sys.stdin.read().strip().splitlines()[-1]);print("card", d["loaded"], "sha256", d["sha256"])' || exit 1
estimator activate-card --version "$VERSION" --approval "Local real-card equivalence run" >/dev/null || exit 1
CODE="$("$PY" -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["spec_code"])' "$SPEC")"
if [ "$CODE" != "ESSENTIAL-1.1" ]; then  # tools/e2e_reset.sh already activates ESSENTIAL-1.1
  estimator load-spec "$SPEC" >/dev/null && estimator activate-spec --spec "$CODE" --approval "Local real-card equivalence run" >/dev/null || exit 1
fi
echo "specification $CODE"

( cd "$API" && exec env VEDA_ENV=local VEDA_DATABASE_URL=sqlite:///var/e2e.db VEDA_COOKIE_SECURE=false \
    VEDA_EMAIL_CAPTURE_DIR=var/mail VEDA_ARGON2_MEMORY_KIB=19456 VEDA_ARGON2_TIME_COST=2 \
    VEDA_PUBLIC_SITE_ORIGINS=http://localhost:8000 VEDA_ANCHOR_DIR=var/anchors VEDA_ESTIMATOR_ENABLED=true \
    "$PY" -m flask --app wsgi run --port 5000 ) > "$OUT/api.log" 2>&1 & pids+=($!)
# The page offers only what the real card prices (3 BHK), as staging does.
SITE_HOME_SIZES=3BHK node "$APP/e2e/static-server.mjs" "$APP/e2e/site-release" 8000 http://localhost:5000 > "$OUT/site-on.log" 2>&1 & pids+=($!)
wait_for http://127.0.0.1:5000/health/live && wait_for http://localhost:8000/ || exit 1

cd "$APP"
E2E_CARD="$CARD" E2E_SPEC="$CODE" E2E_QUIET=1 API_DIR="$API" API_PYTHON="$PY" node e2e/estimator-v2.e2e.mjs 2>&1 \
  | sed -E 's/ — .*$//'  # names and results only
exit "${PIPESTATUS[0]}"
