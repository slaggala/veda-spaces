#!/usr/bin/env bash
# Validates the approved-account manifest, infra/config/staging-account.json (PB-01). Offline: reads the file only.
#
#   infra/scripts/check-manifest.sh              # schema and the fixed owner decisions (Mumbai only, member of the
#                                                # approved AWS organization, repository and its ID); nulls allowed
#   infra/scripts/check-manifest.sh --complete   # also every value a bootstrap needs, with no placeholder: what
#                                                # bootstrap.sh and discover.sh require before any AWS call
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

MODE=structure
case "${1:-}" in
  "") ;;
  --complete) MODE=complete ;;
  -h | --help) sed -n '2,8p' "$0"; exit 0 ;;
  *) die "unknown argument: $1" ;;
esac
require_tools jq
problems="$(manifest_problems "$MODE")"
if [[ -n "$problems" ]]; then
  while IFS= read -r p; do log "MANIFEST: $p"; done <<<"$problems"
  die "${VEDA_ACCOUNT_MANIFEST#"$REPO_ROOT"/} is not valid for $MODE ($(wc -l <<<"$problems" | tr -d ' ') problem(s))"
fi
log "${VEDA_ACCOUNT_MANIFEST#"$REPO_ROOT"/}: valid ($MODE)"
