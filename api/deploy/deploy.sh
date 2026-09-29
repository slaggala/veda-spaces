#!/usr/bin/env bash
# Deploy and migrate the API (02 §12.4, OPS-004; IR-11). Run on the host from the deploy directory:
#   ./deploy.sh <new-image-tag>            normal release
#   ./deploy.sh --rollback <n-1-tag>       normal rollback: N-1 image on the migrated (expand-only) schema
# Disaster rollback (restore a snapshot) is a manual runbook step: docs/operations/api-runbooks.md §3.
#
# ROLLBACK_FLOOR is the oldest schema revision a rollback target image must know (runbook §2.1, RR-17). Images
# that predate it lack a security fix whose absence the schema cannot compensate for: for this release,
# 0009_mfa_challenge_binding (IR-01), so the 9236aa3 image is never a valid rollback target. Raise the floor when a
# release ships a fix that must not be rolled back; never lower it.
set -euo pipefail
cd "$(dirname "$0")"
ROLLBACK_FLOOR="0009_mfa_challenge_binding"

ROLLBACK=0
if [[ "${1:-}" == "--rollback" ]]; then ROLLBACK=1; shift; fi
TAG="${1:?usage: deploy.sh [--rollback] <image-tag>}"
COMPOSE=(docker compose -f docker-compose.yml)
export VEDA_IMAGE_TAG="$TAG"

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

echo "1. Pre-flight: single-worker configuration and replication"
"${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli deploy-check
curl -fsS http://127.0.0.1:9090/metrics | grep -q litestream_ || { echo "litestream metrics unavailable"; exit 1; }

echo "2. Snapshot: nightly-style snapshot now, recorded for disaster rollback"
"${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli maintenance snapshot | tee "pre-deploy-snapshot-$(date -u +%Y%m%dT%H%M%SZ).json"

echo "3. Quiesce: pause the outbox worker and scheduler (the API keeps serving)"
"${COMPOSE[@]}" stop worker scheduler

if [[ $ROLLBACK -eq 0 ]]; then
  echo "4. Migrate: expand-only, safe while the N-1 image serves (the same configuration checks run first)"
  "${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli migrate
else
  echo "4. Rollback: no migration. The target image must know the rollback floor and the current revision must be declared"
  # Both read inside a container of the *target* image: the revision in the database and what that image knows.
  if ! "${COMPOSE[@]}" run --rm --no-deps api python -m veda.cli schema-status --require-known "$ROLLBACK_FLOOR"; then
    echo "Refusing: image $TAG predates rollback floor $ROLLBACK_FLOOR (runbook §2.1: forward-fix or snapshot restore)"
    exit 1
  fi
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

echo "5. Deploy: restart the API on image $TAG; /health/ready must pass with migrations: $EXPECTED"
"${COMPOSE[@]}" up -d --no-deps api
if ! ready "$EXPECTED"; then
  echo "API not ready on $TAG: leaving worker and scheduler stopped; follow the rollback runbook"
  exit 1
fi

echo "6. Resume the worker and scheduler"
"${COMPOSE[@]}" up -d --no-deps worker scheduler
echo "done: $TAG"
