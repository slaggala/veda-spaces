#!/usr/bin/env bash
# Collect staging host evidence (13-evidence; runbook docs/operations/staging-platform-runbooks.md §5). Needs a
# veda-gh-evidence OIDC session. Runs veda-collect on the staging host (tags project=veda-spaces, env=staging) and prints
# the evidence object and its SHA-256, for the summary in docs/release-evidence/.
#
#   infra/scripts/collect-evidence.sh --label <a-z0-9->
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

LABEL=""
while (($#)); do
  case "$1" in
    --label) LABEL="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,7p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done
[[ "$LABEL" =~ ^[a-z0-9][a-z0-9-]{0,39}$ ]] || die "--label must be lowercase letters, digits and hyphens (at most 40)"

require_tools aws jq
ACCOUNT="$(manifest_get .account_id)"
require_account_id "$ACCOUNT"
require_region
arn="$(aws sts get-caller-identity --output json | jq -r '.Arn // empty')" || die "no usable AWS credentials"
[[ "$arn" =~ ^arn:aws:sts::${ACCOUNT}:assumed-role/${VEDA_PREFIX}-gh-evidence/.+$ ]] || die "the session is '${arn:-none}', not ${VEDA_PREFIX}-gh-evidence; refusing"

cmd="$(aws ssm send-command --region "$VEDA_REGION" --document-name "${VEDA_PREFIX}-collect" \
  --targets "Key=tag:project,Values=veda-spaces" "Key=tag:env,Values=staging" --max-concurrency 1 --max-errors 0 \
  --parameters "label=$LABEL" --comment "13-evidence ${GITHUB_RUN_ID:-local} $LABEL" --output json | jq -r '.Command.CommandId // empty')"
[[ -n "$cmd" ]] || die "send-command returned no command id"
status=""
for _ in $(seq 1 60); do
  status="$(aws ssm list-command-invocations --region "$VEDA_REGION" --command-id "$cmd" --output json | jq -r '.CommandInvocations[0].Status // empty')"
  case "$status" in Success | Failed | Cancelled | TimedOut) break ;; esac
  sleep 10
done
out="$(aws ssm list-command-invocations --region "$VEDA_REGION" --command-id "$cmd" --details --output json |
  jq -r '.CommandInvocations[0].CommandPlugins[0].Output // ""')"
printf '%s\n' "$out" | tail -n 20
[[ "$status" == Success ]] || die "veda-collect ended ${status:-unknown} (command $cmd)"
grep -Eq '^evidence s3://[^ ]+ sha256 [0-9a-f]{64}$' <<<"$out" || die "veda-collect reported no evidence object"
log "evidence: $(grep -E '^evidence ' <<<"$out" | tail -n 1)"
