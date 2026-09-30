#!/usr/bin/env bash
# PB-02 evidence: proves, read-only, that the target account is the approved, dedicated Veda account (N-03).
#
#   infra/scripts/account-inventory.sh --expected-account-id 123456789012
#
# Runs every check discovery runs before a plan (region-guarded session, complete manifest, name, alias, standalone,
# owner role, all-region inventory with nothing foreign or named like Aurion/swing-trader), then writes the full
# inventory to infra/generated/account-inventory.json (gitignored) for the owner to archive. Creates nothing.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

EXPECTED=""
while (($#)); do
  case "$1" in
    --expected-account-id) EXPECTED="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,9p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done
require_tools aws jq
require_account_id "$EXPECTED"
require_region
require_region_guarded_session
verify_account_identity "$EXPECTED"
mkdir -p "$GENERATED_DIR"
inventory="$(account_inventory)" || die "cannot list account resources; refusing"
jq -n --arg account "$EXPECTED" --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg caller "$(aws sts get-caller-identity --query Arn --output text)" --argjson inv "$inventory" \
  '{account_id: $account, collected_at: $at, caller_arn: $caller, verdict: "dedicated to Veda (no foreign resource in any region)",
    regions: ([$inv[] | .region] | unique), resources: $inv}' >"$GENERATED_DIR/account-inventory.json"
log "wrote $GENERATED_DIR/account-inventory.json ($(jq length <<<"$inventory") resources)"
