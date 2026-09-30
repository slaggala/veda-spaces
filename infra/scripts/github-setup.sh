#!/usr/bin/env bash
# GitHub repository setup for the staging workflows (plan §8 step 3, AUT-003). DRY-RUN BY DEFAULT: prints each
# change and makes it only with --apply. Needs a GitHub identity with admin rights on the repository.
#
#   infra/scripts/github-setup.sh [--repo owner/repo] [--reviewers alice,bob]            # environments + main
#   infra/scripts/github-setup.sh --verify                                              # read back, fail on drift
#   infra/scripts/github-setup.sh --verify-environments       # environments + main protected (RR-07; any read token)
#   infra/scripts/github-setup.sh --outputs infra/generated/bootstrap-outputs.json --variables-only
#   add --apply to make the changes
#
# Environments (the OIDC trust of each role is pinned to one of them). Every one has can_admins_bypass=false (F10):
#   bootstrap         reviewers, main only        00-bootstrap (temporary owner credentials)
#   staging-plan      reviewers, any branch       PR plans (read-only role; reads state, F9)
#   staging-infra     reviewers, main only        infra apply, secrets seed
#   staging           reviewers, main only        deploy, drills
#   staging-evidence  no reviewers, main only     evidence collection (read-only role)
# Branch protection on main (F10): pull request required (0 approvals, so a single owner can merge; owner decision
# RR-G), enforced for admins, no force pushes, no deletion. "main only" environments mean nothing without it. An
# already compliant protection is left as it is, and required status checks are never dropped.
#
# Variables (--outputs): repository-level AWS_ROLE_ARN_PLAN/APPLY/DEPLOY/EVIDENCE, AWS_ACCOUNT_ID, AWS_REGION,
# TF_STATE_BUCKET, TF_STATE_KMS_KEY_ARN, CF_ACCOUNT_ID, CF_ZONE_ID. Repository variables need only the
# "Variables: write" permission, so GH_ADMIN_TOKEN never needs "Environments" or "Administration" (F10). A role
# ARN is not a secret: AWS enforces the environment through the OIDC trust.
#
# --verify-environments is the gate bootstrap.sh and 00-bootstrap run before any apply (RR-07). It reads only what a
# workflow's GITHUB_TOKEN (actions: read, contents: read) can: each environment's reviewers, admin bypass and branch
# policy, and whether main is protected. --verify also reads the protection details (needs admin).
#
# Secrets are never set here: the owner adds BOOTSTRAP_AWS_*, CF_READ_TOKEN and GH_ADMIN_TOKEN (see the runbook §3).
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

REPO_ARG=""
REVIEWERS=""
OUTPUTS=""
APPLY=0
VARIABLES_ONLY=0
VERIFY=0
VERIFY_ENVIRONMENTS=0
while (($#)); do
  case "$1" in
    --repo) REPO_ARG="${2:-}"; shift 2 ;;
    --reviewers) REVIEWERS="${2:-}"; shift 2 ;;
    --outputs) OUTPUTS="${2:-}"; shift 2 ;;
    --variables-only) VARIABLES_ONLY=1; shift ;;
    --verify) VERIFY=1; shift ;;
    --verify-environments) VERIFY_ENVIRONMENTS=1; shift ;;
    --apply) APPLY=1; shift ;;
    -h | --help) sed -n '2,32p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

require_tools gh jq
REPO="$(resolve_repo "$REPO_ARG")"

# name reviewers(yes|no) main_only(yes|no)
ENVIRONMENTS="bootstrap:yes:yes staging-plan:yes:no staging-infra:yes:yes staging:yes:yes staging-evidence:no:yes"

# --- verify: read back and fail on any drift from the rules above ---------------------------------------------
if ((VERIFY || VERIFY_ENVIRONMENTS)); then
  problems=()
  for spec in $ENVIRONMENTS; do
    IFS=: read -r env with_reviewers main_only <<<"$spec"
    if ! body="$(gh api "repos/$REPO/environments/$env" 2>/dev/null)"; then
      problems+=("$env: environment missing")
      continue
    fi
    [[ "$(jq -r '.can_admins_bypass' <<<"$body")" == false ]] || problems+=("$env: admins can bypass protection rules")
    if [[ "$with_reviewers" == yes ]]; then
      jq -e '[.protection_rules[]? | select(.type == "required_reviewers") | .reviewers[]?] | length > 0' <<<"$body" >/dev/null ||
        problems+=("$env: no required reviewers")
    fi
    if [[ "$main_only" == yes ]]; then
      jq -e '.deployment_branch_policy.custom_branch_policies == true' <<<"$body" >/dev/null ||
        problems+=("$env: not restricted to main")
      policies="$(gh api "repos/$REPO/environments/$env/deployment-branch-policies" --jq '[.branch_policies[] | "\(.type // "branch"):\(.name)"] | sort | join(",")' 2>/dev/null || echo "?")"
      [[ "$policies" == "branch:main" ]] || problems+=("$env: deployment branches are '$policies', expected only main")
    fi
  done
  if ((VERIFY_ENVIRONMENTS && !VERIFY)); then
    [[ "$(gh api "repos/$REPO/branches/main" --jq .protected 2>/dev/null)" == true ]] || problems+=("main: branch not protected")
  elif protection="$(gh api "repos/$REPO/branches/main/protection" 2>/dev/null)"; then
    jq -e '.enforce_admins.enabled == true' <<<"$protection" >/dev/null || problems+=("main: protection not enforced for admins")
    jq -e '.required_pull_request_reviews != null' <<<"$protection" >/dev/null || problems+=("main: pull request not required")
    jq -e '(.allow_force_pushes.enabled // false) == false' <<<"$protection" >/dev/null || problems+=("main: force pushes allowed")
    jq -e '(.allow_deletions.enabled // false) == false' <<<"$protection" >/dev/null || problems+=("main: deletion allowed")
  else
    problems+=("main: branch not protected")
  fi
  if ((${#problems[@]})); then
    for p in "${problems[@]}"; do log "DRIFT: $p"; done
    die "GitHub settings for $REPO do not match the bootstrap rules (${#problems[@]} problem(s)); run with --apply"
  fi
  log "GitHub settings for $REPO match the bootstrap rules"
  exit 0
fi

((APPLY)) || log "DRY RUN: nothing is changed (add --apply)"

# Dry run prints to stderr so it stays visible when the real command's stdout is discarded.
run() {
  if ((APPLY)); then "$@"; else { printf 'would run:'; printf ' %q' "$@"; printf '\n'; } >&2; fi
}

# method path body: the body is shown in the dry run so the reviewer sees exactly what would be set.
api_json() {
  if ((APPLY)); then
    gh api -X "$1" "$2" --input - <<<"$3" >/dev/null
  else
    printf 'would run: gh api -X %s %s <<< %s\n' "$1" "$2" "$(jq -c . <<<"$3")" >&2
  fi
}

setup_environment() {
  local env="$1" with_reviewers="$2" main_only="$3" body reviewers_json='[]' policy='null'
  if [[ "$with_reviewers" == yes ]]; then
    ((${#REVIEWER_IDS[@]} > 0)) || die "environment $env needs at least one reviewer"
    reviewers_json="$(printf '%s\n' "${REVIEWER_IDS[@]}" | jq -R 'tonumber | {type: "User", id: .}' | jq -s .)"
  fi
  [[ "$main_only" == yes ]] && policy='{"protected_branches": false, "custom_branch_policies": true}'
  # prevent_self_review stays false: a single-owner repository would otherwise deadlock every approval (R5; owner
  # decision RR-F of 2026-09-30, to be revisited before a second collaborator is added).
  body="$(jq -n --argjson r "$reviewers_json" --argjson p "$policy" \
    '{wait_timer: 0, prevent_self_review: false, can_admins_bypass: false, reviewers: $r, deployment_branch_policy: $p}')"
  log "environment $env (reviewers: $with_reviewers, main only: $main_only, admins cannot bypass)"
  api_json PUT "repos/$REPO/environments/$env" "$body"
  if [[ "$main_only" == yes ]]; then
    if ((APPLY)) && gh api "repos/$REPO/environments/$env/deployment-branch-policies" \
      --jq '.branch_policies[].name' 2>/dev/null | grep -qx main; then
      return
    fi
    api_json POST "repos/$REPO/environments/$env/deployment-branch-policies" '{"name": "main", "type": "branch"}'
  fi
}

# Keeps whatever protection main already has when it meets the rules (its required status checks included). Only a
# non-compliant or missing protection is written, and then the existing required status checks, review settings,
# linear history and conversation resolution are carried over: a PUT replaces the whole protection.
protect_main() {
  local current='{}' body
  if current="$(gh api "repos/$REPO/branches/main/protection" 2>/dev/null)"; then
    if jq -e '.enforce_admins.enabled == true and .required_pull_request_reviews != null
              and (.allow_force_pushes.enabled // false) == false and (.allow_deletions.enabled // false) == false' \
      <<<"$current" >/dev/null; then
      log "branch protection on main already meets the rules; left unchanged (required status checks kept)"
      return
    fi
  else
    current='{}'
  fi
  log "branch protection on main (pull request required, enforced for admins, no force push or deletion; existing checks kept)"
  body="$(jq -c '{
    required_status_checks: (.required_status_checks | if . == null then null
      else {strict: (.strict // false), checks: [.checks[]? | {context, app_id}]} end),
    enforce_admins: true,
    required_pull_request_reviews: {
      required_approving_review_count: (.required_pull_request_reviews.required_approving_review_count // 0),
      dismiss_stale_reviews: true,
      require_code_owner_reviews: (.required_pull_request_reviews.require_code_owner_reviews // false),
      require_last_push_approval: (.required_pull_request_reviews.require_last_push_approval // false)},
    restrictions: null,
    required_linear_history: (.required_linear_history.enabled // false),
    required_conversation_resolution: (.required_conversation_resolution.enabled // false),
    allow_force_pushes: false,
    allow_deletions: false}' <<<"$current")"
  api_json PUT "repos/$REPO/branches/main/protection" "$body"
}

if ((!VARIABLES_ONLY)); then
  REVIEWER_IDS=()
  [[ -n "$REVIEWERS" ]] || REVIEWERS="$(gh api user --jq .login)"
  IFS=',' read -r -a logins <<<"$REVIEWERS"
  for login in "${logins[@]}"; do REVIEWER_IDS+=("$(gh api "users/$login" --jq .id)"); done

  for spec in $ENVIRONMENTS; do
    IFS=: read -r env with_reviewers main_only <<<"$spec"
    setup_environment "$env" "$with_reviewers" "$main_only"
  done
  protect_main
fi

if [[ -n "$OUTPUTS" ]]; then
  [[ -f "$OUTPUTS" ]] || die "outputs file not found: $OUTPUTS"
  var() { run gh variable set "$1" --repo "$REPO" --body "$2"; }

  var AWS_ACCOUNT_ID "$(jq -r .account_id "$OUTPUTS")"
  var AWS_REGION "$(jq -r .region "$OUTPUTS")"
  var TF_STATE_BUCKET "$(jq -r .state_bucket "$OUTPUTS")"
  var TF_STATE_KMS_KEY_ARN "$(jq -r .state_kms_key_arn "$OUTPUTS")"
  for purpose in plan apply deploy evidence; do
    upper="$(tr '[:lower:]' '[:upper:]' <<<"$purpose")"
    var "AWS_ROLE_ARN_$upper" "$(jq -r ".github_role_arns.$purpose" "$OUTPUTS")"
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
