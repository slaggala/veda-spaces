#!/usr/bin/env bash
# Deploy and migrate the API (02 §12.4, OPS-004; IR-11). Run on the host from the deploy directory:
#   ./deploy.sh <new-image-tag>            normal release
#   ./deploy.sh --rollback <n-1-tag>       normal rollback: N-1 image on the migrated (expand-only) schema
# Disaster rollback (restore a snapshot) is a manual runbook step: docs/operations/api-runbooks.md §3.
set -euo pipefail
cd "$(dirname "$0")"

ROLLBACK=0
if [[ "${1:-}" == "--rollback" ]]; then ROLLBACK=1; shift; fi
TAG="${1:?usage: deploy.sh [--rollback] <image-tag>}"
COMPOSE=(docker compose -f docker-compose.yml)
export VEDA_IMAGE_TAG="$TAG"

ready() {
  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:8000/health/ready >/dev/null; then return 0; fi
    sleep 2
  done
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
  echo "4. Rollback: no migration; the N-1 image must be told the newer revision is compatible"
  grep -q '^VEDA_SCHEMA_AHEAD_ACCEPTED=' /etc/veda/api.env || {
    echo "Set VEDA_SCHEMA_AHEAD_ACCEPTED=<current revision> in /etc/veda/api.env first (runbook §2)"; exit 1; }
fi

echo "5. Deploy: restart the API on image $TAG; /health/ready must pass"
"${COMPOSE[@]}" up -d --no-deps api
if ! ready; then
  echo "API not ready on $TAG: leaving worker and scheduler stopped; follow the rollback runbook"
  exit 1
fi

echo "6. Resume the worker and scheduler"
"${COMPOSE[@]}" up -d --no-deps worker scheduler
echo "done: $TAG"
