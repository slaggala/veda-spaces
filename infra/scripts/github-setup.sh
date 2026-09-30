#!/usr/bin/env bash
# GitHub repository setup for the staging workflows (plan §8 step 3, AUT-003). DRY-RUN BY DEFAULT: prints each
# change and makes it only with --apply. Needs a GitHub identity with admin rights on the repository.
#
#   infra/scripts/github-setup.sh [--repo owner/repo] [--reviewers alice,bob]            # environments
#   infra/scripts/github-setup.sh --outputs infra/generated/bootstrap-outputs.json --variables-only
#   add --apply to make the changes
#
# Environments (the OIDC trust of each role is pinned to one of them):
#   bootstrap         reviewers, main only        00-bootstrap (temporary owner credentials)
#   staging-plan      no reviewers, any branch    PR plans (read-only role)
#   staging-infra     reviewers, main only        infra apply, secrets seed
#   staging           reviewers, main only        deploy, drills
#   staging-evidence  no reviewers, main only     evidence collection (read-only role)
#
# Secrets are never set here: the owner adds BOOTSTRAP_AWS_*, CF_* and GH_ADMIN_TOKEN (see the runbook §3).
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

REPO_ARG=""
REVIEWERS=""
OUTPUTS=""
APPLY=0
VARIABLES_ONLY=0
while (($#)); do
  case "$1" in
    --repo) REPO_ARG="${2:-}"; shift 2 ;;
    --reviewers) REVIEWERS="${2:-}"; shift 2 ;;
    --outputs) OUTPUTS="${2:-}"; shift 2 ;;
    --variables-only) VARIABLES_ONLY=1; shift ;;
    --apply) APPLY=1; shift ;;
    -h | --help) sed -n '2,19p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

require_tools gh jq
REPO="$(resolve_repo "$REPO_ARG")"
((APPLY)) || log "DRY RUN: nothing is changed (add --apply)"

# Dry run prints to stderr so it stays visible when the real command's stdout is discarded.
run() {
  if ((APPLY)); then "$@"; else { printf 'would run:'; printf ' %q' "$@"; printf '\n'; } >&2; fi
}

setup_environment() {
  local env="$1" with_reviewers="$2" main_only="$3" body reviewers_json='[]'
  if [[ "$with_reviewers" == yes && ${#REVIEWER_IDS[@]} -gt 0 ]]; then
    reviewers_json="$(printf '%s\n' "${REVIEWER_IDS[@]}" | jq -R 'tonumber | {type: "User", id: .}' | jq -s .)"
  fi
  if [[ "$main_only" == yes ]]; then
    body="$(jq -n --argjson r "$reviewers_json" \
      '{wait_timer: 0, prevent_self_review: false, reviewers: $r,
        deployment_branch_policy: {protected_branches: false, custom_branch_policies: true}}')"
  else
    body="$(jq -n --argjson r "$reviewers_json" \
      '{wait_timer: 0, prevent_self_review: false, reviewers: $r, deployment_branch_policy: null}')"
  fi
  log "environment $env (reviewers: $with_reviewers, main only: $main_only)"
  run gh api -X PUT "repos/$REPO/environments/$env" --input - <<<"$body" >/dev/null
  if [[ "$main_only" == yes ]]; then
    if ((APPLY)) && gh api "repos/$REPO/environments/$env/deployment-branch-policies" \
      --jq '.branch_policies[].name' 2>/dev/null | grep -qx main; then
      return
    fi
    run gh api -X POST "repos/$REPO/environments/$env/deployment-branch-policies" \
      -f name=main -f type=branch >/dev/null
  fi
}

if ((!VARIABLES_ONLY)); then
  REVIEWER_IDS=()
  [[ -n "$REVIEWERS" ]] || REVIEWERS="$(gh api user --jq .login)"
  IFS=',' read -r -a logins <<<"$REVIEWERS"
  for login in "${logins[@]}"; do REVIEWER_IDS+=("$(gh api "users/$login" --jq .id)"); done

  # prevent_self_review stays false: a single-owner repository would otherwise deadlock every approval.
  setup_environment bootstrap yes yes
  setup_environment staging-plan no no
  setup_environment staging-infra yes yes
  setup_environment staging yes yes
  setup_environment staging-evidence no yes
fi

if [[ -n "$OUTPUTS" ]]; then
  [[ -f "$OUTPUTS" ]] || die "outputs file not found: $OUTPUTS"
  var() { run gh variable set "$1" --repo "$REPO" --body "$2" "${@:3}"; }

  var AWS_ACCOUNT_ID "$(jq -r .account_id "$OUTPUTS")"
  var AWS_REGION "$(jq -r .region "$OUTPUTS")"
  var TF_STATE_BUCKET "$(jq -r .state_bucket "$OUTPUTS")"
  var TF_STATE_KMS_KEY_ARN "$(jq -r .state_kms_key_arn "$OUTPUTS")"
  for purpose in plan apply deploy evidence; do
    env="$(jq -r ".github_environments.$purpose" "$OUTPUTS")"
    var AWS_ROLE_ARN "$(jq -r ".github_role_arns.$purpose" "$OUTPUTS")" --env "$env"
  done

  DISCOVERED="$GENERATED_DIR/discovered.json"
  if [[ -f "$DISCOVERED" ]] && [[ "$(jq -r .cloudflare.discovered "$DISCOVERED")" == true ]]; then
    var CF_ACCOUNT_ID "$(jq -r .cloudflare.account_id "$DISCOVERED")"
    var CF_ZONE_ID "$(jq -r .cloudflare.zone_id "$DISCOVERED")"
  else
    warn "Cloudflare IDs not discovered; CF_ACCOUNT_ID/CF_ZONE_ID must be set before AUT-201"
  fi
fi

log "done ($([[ $APPLY -eq 1 ]] && echo applied || echo dry run))"
