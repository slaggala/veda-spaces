#!/usr/bin/env bash
# Deploy and migrate the API (02 §12.4, OPS-004; IR-11). Run on the host from the deploy directory:
#   ./deploy.sh <new-image-tag>            normal release
#   ./deploy.sh --rollback <n-1-tag>       normal rollback: N-1 image on the migrated (expand-only) schema
# Disaster rollback (restore a snapshot) is a manual runbook step: docs/operations/api-runbooks.md §3.
#
# Floors (runbook §2.1; RR-17, FC-12), enforced in EVERY mode — a normal deploy of an old image is refused too:
# - RELEASE_FLOOR: the oldest release sequence (veda/release.py, reported by `veda schema-status`) an image may
#   have. Images below it lack a security fix that no schema check can detect (3 excludes 9236aa3 and 2f6b59a).
# - ROLLBACK_FLOOR: the oldest schema revision an image must know (0009_mfa_challenge_binding, IR-01).
# Both are fixed here and read from nothing else: there is no flag, environment variable or override. Raise them
# when a release ships a fix that must not be undone; never lower them. An emergency exception would be a
# reviewed change to this file, not a runtime switch.
set -euo pipefail
cd "$(dirname "$0")"
readonly RELEASE_FLOOR=3
readonly ROLLBACK_FLOOR="0009_mfa_challenge_binding"

ROLLBACK=0
if [[ "${1:-}" == "--rollback" ]]; then ROLLBACK=1; shift; fi
TAG="${1:?usage: deploy.sh [--rollback] <image-tag>}"
COMPOSE=(docker compose -f docker-compose.yml)
export VEDA_IMAGE_TAG="$TAG"
# The persistent data volume (host-setup.sh mounts it) and the database Litestream replicates (litestream.yml).
readonly DATA_DIR=/var/lib/veda
readonly DB="$DATA_DIR/veda.db"
# The Cloudflare tunnel configuration render-edge.sh writes when the owner seeded /veda/staging/edge (AUT-201).
readonly EDGE_DIR=/etc/veda/cloudflared
# The rendered application configuration (render-env.sh from SSM): it decides whether the malware scanner runs.
readonly API_ENV="${VEDA_API_ENV:-/etc/veda/api.env}"
# render-env.sh writes NAME="value"; a plain NAME=value is read the same way.
setting() { [[ -r "$API_ENV" ]] || return 0; sed -n "s/^$1=//p" "$API_ENV" | tail -1 | sed -e 's/^"//' -e 's/"$//'; }

# Litestream serves replication metrics on 127.0.0.1:9090 once it has opened the database.
replicating() {
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:9090/metrics 2>/dev/null | grep -q litestream_ && return 0
    sleep 2
  done
  echo "litestream metrics unavailable"
  return 1
}

# Readiness is read inside the api container: only a loopback peer sees the detailed checks (the host reaches the
# port through the Docker bridge). Prints the body and succeeds when ready with the expected migrations state.
ready() {
  local expected="$1"
  for _ in $(seq 1 30); do
    if body=$("${COMPOSE[@]}" exec -T api python -c '
import json, sys, urllib.request
try:
    r = urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=5); print(r.read().decode())
except Exception as e:
    print(getattr(e, "read", lambda: str(e).encode())().decode()); sys.exit(1)' 2>/dev/null); then
      echo "$body"
      echo "$body" | grep -Eq "\"migrations\": ?\"$expected\"" && return 0
      echo "unexpected migrations state (wanted $expected)"; return 1
    fi
    sleep 2
  done
  echo "${body:-no response}"
  return 1
}

echo "0. Floors: image $TAG must report release >= $RELEASE_FLOOR and know schema $ROLLBACK_FLOOR"
# Read inside a container of the target image. An image too old to answer (no schema-status command, no release
# field, malformed output) is refused like one that answers below the floor.
if ! STATUS=$("${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli schema-status --require-known "$ROLLBACK_FLOOR"); then
  echo "Refusing: image $TAG does not know schema floor $ROLLBACK_FLOOR or cannot report its release (runbook §2.1)"
  exit 1
fi
RELEASE=$(printf '%s' "$STATUS" | python3 -c 'import json,sys
try:
    r = json.loads(sys.stdin.read().strip().splitlines()[-1]).get("release")
except Exception:
    r = None
print(r if type(r) is int else "invalid")')
if [[ "$RELEASE" == "invalid" ]] || (( RELEASE < RELEASE_FLOOR )); then
  echo "Refusing: image $TAG reports release '$RELEASE', below release floor $RELEASE_FLOOR (runbook §2.1: forward-fix)"
  exit 1
fi

# Catalog V3 activation (pre-plan closure, phase 7): only with the V3 staging approval record packaged in this image
# APPROVED and current (review date and expiry not reached, not revoked). Checked before any snapshot, migration or
# restart, so a refusal changes nothing. With V3 off (the normal case) nothing is checked here.
if [[ "$(setting VEDA_CATALOG_ESTIMATOR_ENABLED)" == "true" ]]; then
  echo "0b. V3 activation requested: the approval record in image $TAG must be APPROVED and current"
  if ! "${COMPOSE[@]}" run --rm --no-deps api python -m veda.modules.catalog.staging_approval; then
    echo "APPROVAL RECORD INVALID: refusing to deploy V3 (turn every catalog_v3 flag off, or approve a current record)"
    exit 1
  fi
fi

echo "1. Pre-flight: single-worker configuration and replication"
"${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli deploy-check
mountpoint -q "$DATA_DIR" || { echo "Refusing: $DATA_DIR is not the mounted data volume"; exit 1; }
FIRST=0
if [[ ! -e "$DB" ]]; then
  # No database on the volume: the first deploy, or a rebuilt host. A rebuilt host must restore its replica first
  # (api-runbooks §3): starting empty would begin a new Litestream generation beside the old one, and retention
  # would later delete the old one. So an empty volume is accepted only while the replica holds no generation.
  [[ $ROLLBACK -eq 0 ]] || { echo "Refusing: no database at $DB to roll back"; exit 1; }
  GENERATIONS=$("${COMPOSE[@]}" run --rm --no-deps litestream generations "$DB") ||
    { echo "Refusing: cannot list the replica's generations for $DB"; exit 1; }
  if [[ -n "$(printf '%s\n' "$GENERATIONS" | tail -n +2 | grep -v '^[[:space:]]*$' || true)" ]]; then
    echo "Refusing: no database at $DB but its replica has generations; restore it first (api-runbooks §3)"
    exit 1
  fi
  FIRST=1
  echo "first deploy: no database and an empty replica; replication starts once the migration creates the database"
else
  # Started if it is not running (a no-op when it is; a changed configuration recreates it), then it must report.
  "${COMPOSE[@]}" up -d --no-deps litestream
  replicating || exit 1
fi

if [[ $FIRST -eq 1 ]]; then
  echo "2. Snapshot: none (no database yet)"
else
  echo "2. Snapshot: nightly-style snapshot now, recorded for disaster rollback"
  "${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli maintenance snapshot | tee "pre-deploy-snapshot-$(date -u +%Y%m%dT%H%M%SZ).json"
fi

echo "3. Quiesce: pause the outbox worker and scheduler (the API keeps serving)"
"${COMPOSE[@]}" stop worker scheduler

if [[ $ROLLBACK -eq 0 ]]; then
  echo "4. Migrate: expand-only, safe while the N-1 image serves (the same configuration checks run first)"
  "${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli migrate
else
  echo "4. Rollback: no migration (floors checked in step 0). The current revision must be declared if newer"
  REV=$("${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli schema-status | python3 -c 'import json,sys; print(json.load(sys.stdin)["current"])')
  STATE=$("${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli schema-status | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])')
  if [[ "$STATE" == "ahead_undeclared" || "$STATE" == "ahead" ]]; then
    grep -Eq "^VEDA_SCHEMA_AHEAD_ACCEPTED=(.*,)?${REV}(,.*)?$" /etc/veda/api.env || {
      echo "Set VEDA_SCHEMA_AHEAD_ACCEPTED=$REV in /etc/veda/api.env first (runbook §2)"; exit 1; }
  elif [[ "$STATE" != "head" ]]; then
    echo "Refusing: database state for image $TAG is $STATE"; exit 1
  fi
fi
EXPECTED=head
[[ $ROLLBACK -eq 1 && "${STATE:-head}" != "head" ]] && EXPECTED=ahead

if [[ $FIRST -eq 1 ]]; then
  echo "4b. Replication: start Litestream on the new database; it must report before the API starts"
  "${COMPOSE[@]}" up -d --no-deps litestream
  replicating || { echo "Refusing to start the API without replication; worker and scheduler stay stopped"; exit 1; }
fi

# Catalog V3 malware scanner (targeted media enablement): only when the configuration selects clamd, only with an
# image pinned by digest, and the scanner must answer PING before the API restarts. Otherwise it is not running.
SCANNER="$(setting VEDA_CATALOG_MEDIA_SCANNER)"
if [[ "$SCANNER" == "clamd" ]]; then
  echo "4c. Scanner: clamd on the private Compose network"
  VEDA_CLAMD_IMAGE="$(setting VEDA_CATALOG_CLAMD_IMAGE)"
  [[ "$VEDA_CLAMD_IMAGE" =~ ^[a-z0-9./_-]+(:[A-Za-z0-9._-]+)?@sha256:[0-9a-f]{64}$ ]] ||
    { echo "Refusing to start the scanner: VEDA_CATALOG_CLAMD_IMAGE is not pinned by digest"; exit 1; }
  export VEDA_CLAMD_IMAGE
  "${COMPOSE[@]}" --profile scanner up -d --no-deps clamd
  scanner_ready=0
  for _ in $(seq 1 90); do
    if "${COMPOSE[@]}" run --rm --no-deps api python -c '
import socket, sys
try:
    with socket.create_connection(("clamd", 3310), timeout=5) as s:
        s.sendall(b"zPING\0")
        sys.exit(0 if s.recv(16).strip(b"\0\n ") == b"PONG" else 1)
except OSError:
    sys.exit(1)' >/dev/null 2>&1; then scanner_ready=1; break; fi
    sleep 10
  done
  (( scanner_ready )) || { echo "Refusing to continue: the scanner did not answer (uploads would stay FAILED)"; exit 1; }
else
  echo "4c. Scanner: not selected (VEDA_CATALOG_MEDIA_SCANNER=${SCANNER:-unset}); media uploads stay PENDING"
  "${COMPOSE[@]}" --profile scanner rm -s -f clamd
fi

echo "5. Deploy: restart the API on image $TAG; /health/ready must pass with migrations: $EXPECTED"
"${COMPOSE[@]}" up -d --no-deps api
if ! ready "$EXPECTED"; then
  echo "API not ready on $TAG: leaving worker and scheduler stopped; follow the rollback runbook"
  exit 1
fi

echo "6. Resume the worker and scheduler"
"${COMPOSE[@]}" up -d --no-deps worker scheduler

# The tunnel connects out to Cloudflare only and serves the API host behind Cloudflare Access (AUT-201). Its
# metrics on 127.0.0.1:20241 report the edge connections it holds.
tunnel_ready() {
  for _ in $(seq 1 30); do
    n=$(curl -fsS http://127.0.0.1:20241/ready 2>/dev/null | python3 -c 'import json,sys
try:
    print(int(json.load(sys.stdin).get("readyConnections", 0)))
except Exception:
    print(0)') || n=0
    if (( n > 0 )); then echo "tunnel ready: $n edge connection(s)"; return 0; fi
    sleep 2
  done
  echo "tunnel not ready: no edge connection"
  return 1
}
if [[ -f "$EDGE_DIR/config.yml" ]]; then
  echo "7. Edge: Cloudflare tunnel, Cloudflare Access required at the origin"
  grep -q "^        required: true$" "$EDGE_DIR/config.yml" && [[ -f "$EDGE_DIR/tunnel.env" ]] ||
    { echo "Refusing to start the tunnel: its configuration does not require Cloudflare Access or has no token"; exit 1; }
  "${COMPOSE[@]}" --profile edge up -d --no-deps cloudflared
  tunnel_ready || { echo "the API is deployed and serves on loopback; the tunnel did not connect"; exit 1; }
else
  echo "7. Edge: not configured (no tunnel); the API serves on loopback only"
  "${COMPOSE[@]}" --profile edge rm -s -f cloudflared
fi
echo "done: $TAG"
