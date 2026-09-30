#!/usr/bin/env bash
# One-time bootstrap of the dedicated Veda staging AWS account (plan §8, AUT-003).
#
#   infra/scripts/bootstrap.sh --expected-account-id 123456789012                # plan only (default)
#   infra/scripts/bootstrap.sh --expected-account-id 123456789012 --mode apply   # plan, show, type the ID, apply
#   ... --mode apply --plan-file F --plan-meta M --plan-sha256 D [--plan-run-id N] [--yes]
#                                                                                 # apply the approved plan D
#
# Options: --repo owner/repo (default: discovered)
#
# Credentials: a temporary owner session in the Veda account (AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN or a
# profile). The account must be the one approved in infra/config/staging-account.json, and the session must
# be in it; discovery also checks its name, alias and emptiness (F3). The Terraform provider refuses any other account.
#
# plan  : discovery + terraform plan + plan guard (no destroy, bounded roles, no external trust). Writes the plan,
#         its text and its metadata (commit, account, workflow, SHA-256 of the plan and of its text, Terraform
#         version) to infra/generated/, and prints the plan's SHA-256: the digest a reviewer approves. Nothing is
#         created.
# apply : applies exactly a reviewed plan (F4, RR-05): either the one just made and shown here, confirmed by typing
#         the account ID, or --plan-file/--plan-meta from an earlier plan run of the same commit whose SHA-256 is the
#         approved --plan-sha256 D (checked against the file itself, not only its metadata), and whose text, rendered
#         again from that file, is byte-identical to the text the reviewer read. --yes (no prompt) is accepted only
#         with an approved plan. Apply needs the GitHub environments protected (RR-07; github-setup.sh
#         --verify-environments) and stops otherwise. Then moves the state into the bucket it created (first run),
#         verifies the live bucket and key policies are the reviewed ones (RR-01, RR-02) and writes
#         infra/generated/bootstrap-outputs.json for github-setup.sh.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

MODE="plan"
EXPECTED=""
REPO_ARG=""
YES=0
REVIEWED_PLAN=""
REVIEWED_META=""
APPROVED_SHA=""
PLAN_RUN=""
while (($#)); do
  case "$1" in
    --mode) MODE="${2:-}"; shift 2 ;;
    --expected-account-id) EXPECTED="${2:-}"; shift 2 ;;
    --repo) REPO_ARG="${2:-}"; shift 2 ;;
    --yes) YES=1; shift ;;
    --plan-file) REVIEWED_PLAN="${2:-}"; shift 2 ;;
    --plan-meta) REVIEWED_META="${2:-}"; shift 2 ;;
    --plan-sha256) APPROVED_SHA="${2:-}"; shift 2 ;;
    --plan-run-id) PLAN_RUN="${2:-}"; shift 2 ;;
    --skip-guardrails) die "--skip-guardrails was removed: set manage_account_guardrails in infra/config/staging-account.json in a reviewed change (F5)" ;;
    -h | --help) sed -n '2,28p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ "$MODE" == "plan" || "$MODE" == "apply" ]] || die "--mode must be plan or apply"
if [[ -n "$REVIEWED_PLAN" || -n "$REVIEWED_META" || -n "$APPROVED_SHA" || -n "$PLAN_RUN" ]]; then
  [[ "$MODE" == "apply" ]] || die "--plan-file, --plan-meta, --plan-sha256 and --plan-run-id are for --mode apply"
  [[ -n "$REVIEWED_PLAN" && -n "$REVIEWED_META" && -n "$APPROVED_SHA" ]] ||
    die "--plan-file, --plan-meta and --plan-sha256 (the approved plan digest) go together"
  [[ "$APPROVED_SHA" =~ ^[0-9a-f]{64}$ ]] || die "--plan-sha256 must be the 64-hex SHA-256 of the approved plan file"
  [[ -z "$PLAN_RUN" || "$PLAN_RUN" =~ ^[0-9]+$ ]] || die "--plan-run-id must be a run ID"
fi
((!YES)) || [[ -n "$REVIEWED_PLAN" ]] ||
  die "--yes applies without a prompt, so it needs an approved plan: pass --plan-file, --plan-meta and --plan-sha256"
require_tools aws jq terraform curl git gh
require_account_id "$EXPECTED"
require_region
require_expected_account "$EXPECTED"
# PB-06: Mumbai only is enforced by IAM on this (unbounded) owner session, not only by the code it runs.
require_region_guarded_session
export TF_IN_AUTOMATION=1 TF_INPUT=0
mkdir -p "$GENERATED_DIR"

STATE_KEY="bootstrap/terraform.tfstate"
BACKEND_FILE="$BOOTSTRAP_DIR/backend_s3.tf"
PLAN_FILE="$GENERATED_DIR/bootstrap.tfplan"
META_FILE="$GENERATED_DIR/bootstrap-plan.meta.json"
BUCKET="$(state_bucket_name "$EXPECTED")"
COMMIT="$(current_commit)"
WORKFLOW_REF="${GITHUB_WORKFLOW_REF:-local}"
TF_VERSION="$(terraform version -json | jq -r '.terraform_version // empty')"
[[ -n "$TF_VERSION" ]] || die "cannot read the Terraform version"

# F4, RR-05: the approved plan is the file whose SHA-256 the reviewer approved (--plan-sha256), made by a plan run of
# this commit, account, workflow and Terraform version, with the text the reviewer read. Checked before Terraform
# runs at all; the text is rendered again from the file once Terraform is initialised (verify_plan_text).
verify_reviewed_plan() {
  local sum meta text
  [[ -f "$REVIEWED_PLAN" ]] || die "reviewed plan not found: $REVIEWED_PLAN"
  [[ -f "$REVIEWED_META" ]] || die "reviewed plan metadata not found: $REVIEWED_META"
  REVIEWED_PLAN="$(cd "$(dirname "$REVIEWED_PLAN")" && pwd)/$(basename "$REVIEWED_PLAN")"
  REVIEWED_META="$(cd "$(dirname "$REVIEWED_META")" && pwd)/$(basename "$REVIEWED_META")"
  meta="$REVIEWED_META"
  sum="$(sha256_of "$REVIEWED_PLAN")"
  [[ "$sum" == "$APPROVED_SHA" ]] ||
    die "plan file sha256 $sum is not the approved plan ($APPROVED_SHA): refusing to apply a plan nobody approved"
  [[ "$sum" == "$(jq -r '.plan_sha256 // empty' "$meta")" ]] ||
    die "reviewed plan checksum mismatch: the plan file is not the one that was reviewed"
  [[ "$(jq -r '.mode // empty' "$meta")" == "plan" ]] || die "reviewed plan metadata is not from a plan run"
  [[ "$(jq -r '.account_id // empty' "$meta")" == "$EXPECTED" ]] ||
    die "reviewed plan was made for account $(jq -r .account_id "$meta"), not $EXPECTED"
  [[ "$(jq -r '.commit // empty' "$meta")" == "$COMMIT" ]] ||
    die "reviewed plan was made from commit $(jq -r .commit "$meta"), this run is $COMMIT; plan again"
  [[ "$(jq -r '.dirty' "$meta")" == "false" ]] ||
    die "reviewed plan was made from a working tree with uncommitted infra changes; plan again from a clean commit"
  [[ "$(jq -r '.workflow_ref // empty' "$meta")" == "$WORKFLOW_REF" ]] ||
    die "reviewed plan was made by '$(jq -r '.workflow_ref // "?"' "$meta")', this run is '$WORKFLOW_REF'; refusing"
  [[ -z "$PLAN_RUN" || "$(jq -r '.run_id // empty' "$meta")" == "$PLAN_RUN" ]] ||
    die "reviewed plan metadata is from run $(jq -r '.run_id // "?"' "$meta"), not the approved run $PLAN_RUN"
  [[ "$(jq -r '.terraform_version // empty' "$meta")" == "$TF_VERSION" ]] ||
    die "reviewed plan was made with Terraform $(jq -r '.terraform_version // "?"' "$meta"), this is $TF_VERSION; refusing"
  text="$(dirname "$REVIEWED_PLAN")/bootstrap-plan.txt"
  [[ -f "$text" && "$(sha256_of "$text")" == "$(jq -r '.plan_text_sha256 // empty' "$meta")" ]] ||
    die "the reviewed plan text beside the plan file is missing or is not the text recorded at plan time"
  log "reviewed plan verified: sha256 $sum (approved), commit $COMMIT, account $EXPECTED, $WORKFLOW_REF"
}

# RR-05: the text the reviewer read is exactly what this Terraform renders from the file it is about to apply.
verify_plan_text() {
  terraform show -no-color "$PLAN_FILE" >"$GENERATED_DIR/applying-plan.txt"
  [[ "$(sha256_of "$GENERATED_DIR/applying-plan.txt")" == "$(jq -r '.plan_text_sha256' "$REVIEWED_META")" ]] ||
    die "the plan file renders a different text from the one that was reviewed; refusing"
  log "plan text re-rendered from the approved file matches the reviewed text"
}

write_backend() {
  cat >"$BACKEND_FILE" <<'EOF'
# Generated by infra/scripts/bootstrap.sh once the state bucket exists. Do not commit (gitignored).
terraform {
  backend "s3" {}
}
EOF
}

# Sets BARGS (bash 3.2 compatible: macOS operators run this with the system bash).
backend_args() {
  BARGS=("-backend-config=bucket=$BUCKET" "-backend-config=key=$STATE_KEY"
    "-backend-config=region=$VEDA_REGION" "-backend-config=encrypt=true"
    "-backend-config=kms_key_id=$1" "-backend-config=use_lockfile=true")
}

# Plan guard over a saved plan (destroys, boundaries, external trust).
guard_plan() {
  terraform show -json "$1" >"$GENERATED_DIR/bootstrap-plan.json"
  "$INFRA_DIR/scripts/check-plan.sh" --plan-json "$GENERATED_DIR/bootstrap-plan.json" --account "$EXPECTED" \
    --repo "$REPO" --prefix "$VEDA_PREFIX"
  # PB-10: IAM itself must evaluate the rendered boundary as reviewed (read-only simulation).
  "$INFRA_DIR/scripts/simulate-boundary.sh" --plan-json "$GENERATED_DIR/bootstrap-plan.json" --account "$EXPECTED"
}

if [[ -n "$REVIEWED_PLAN" ]]; then
  verify_reviewed_plan
  verify_account_identity "$EXPECTED"
  REPO="$(jq -r '.repository // empty' "$REVIEWED_META")"
  [[ -n "$REPO" ]] || die "reviewed plan metadata has no repository"
  [[ -z "${GITHUB_REPOSITORY:-}" || "$REPO" == "$GITHUB_REPOSITORY" ]] ||
    die "reviewed plan was made for $REPO, this run is $GITHUB_REPOSITORY"
  [[ "$REPO" == "$(manifest_get .repository)" ]] ||
    die "repository $REPO is not the one the manifest approves ($(manifest_get .repository)); refusing"
else
  # N-05 / PB-08: plan only from a clean checkout, ignored files included.
  require_clean_tree
  discover_args=(--expected-account-id "$EXPECTED")
  [[ -n "$REPO_ARG" ]] && discover_args+=(--repo "$REPO_ARG")
  "$INFRA_DIR/scripts/discover.sh" "${discover_args[@]}"
  REPO="$(jq -r .github.repository "$GENERATED_DIR/discovered.json")"
fi

# Assigned before comparing: a failed lookup must stop the run, not read as "absent".
# RR-07: the environments that gate this workflow and the new roles must be protected before anything is applied.
[[ "$MODE" == plan ]] || require_github_protection "$REPO"
# PB-01: the approved repository by name and numeric ID (discovery checked it too on the plan path).
require_repository_identity "$REPO"

BUCKET_STATUS="$(state_bucket_status "$BUCKET" "$EXPECTED")"
STATE_EXISTS=false
[[ "$BUCKET_STATUS" == exists ]] && STATE_EXISTS=true
if [[ -n "$REVIEWED_PLAN" ]]; then
  [[ "$(jq -r .state_exists "$REVIEWED_META")" == "$STATE_EXISTS" ]] ||
    die "the state bucket appeared or disappeared since the plan was made; plan again"
fi

cd "$BOOTSTRAP_DIR"
if [[ "$STATE_EXISTS" == "true" ]]; then
  # RR-02: the key is the one the bucket encrypts with; the alias must agree with it, not decide it.
  KEY_ARN="$(state_key_from_bucket "$BUCKET" "$EXPECTED")"
  [[ -f terraform.tfstate ]] && die "local terraform.tfstate present while $BUCKET exists: resolve manually (docs/operations/staging-bootstrap.md §6)"
  log "remote state: s3://$BUCKET/$STATE_KEY"
  write_backend
  backend_args "$KEY_ARN"
  terraform init -reconfigure -input=false "${BARGS[@]}" >/dev/null
else
  log "first run: local state, migrated to s3://$BUCKET after apply"
  rm -f "$BACKEND_FILE"
  terraform init -reconfigure -input=false >/dev/null
fi

if [[ -n "$REVIEWED_PLAN" ]]; then
  PLAN_FILE="$REVIEWED_PLAN"
  verify_plan_text
else
  dirty=false # require_clean_tree above refused anything else
  terraform plan -input=false -lock-timeout=5m -out="$PLAN_FILE"
  terraform show -no-color "$PLAN_FILE" >"$GENERATED_DIR/bootstrap-plan.txt"
  jq -n --arg commit "$COMMIT" --arg account "$EXPECTED" --arg repo "$REPO" --arg sum "$(sha256_of "$PLAN_FILE")" \
    --arg text_sum "$(sha256_of "$GENERATED_DIR/bootstrap-plan.txt")" --arg tf "$TF_VERSION" --arg wf "$WORKFLOW_REF" \
    --argjson state_exists "$STATE_EXISTS" --argjson dirty "$dirty" --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg run "${GITHUB_RUN_ID:-local}" --arg attempt "${GITHUB_RUN_ATTEMPT:-1}" \
    '{mode: "plan", commit: $commit, dirty: $dirty, account_id: $account, repository: $repo, workflow_ref: $wf,
      run_id: $run, run_attempt: $attempt, terraform_version: $tf, plan_sha256: $sum, plan_text_sha256: $text_sum,
      state_exists: $state_exists, created_at: $at}' >"$META_FILE"
  log "plan written to $GENERATED_DIR/bootstrap-plan.txt (metadata: $META_FILE)"
  log "plan sha256 (the digest to approve): $(jq -r .plan_sha256 "$META_FILE")"
fi

guard_plan "$PLAN_FILE"

if [[ "$MODE" == "plan" ]]; then
  log "plan mode: nothing was created"
  exit 0
fi

if [[ -z "$REVIEWED_PLAN" ]]; then
  terraform show -no-color "$PLAN_FILE" >&2
  log "plan sha256 $(sha256_of "$PLAN_FILE")"
  read -r -p "Apply the plan above to AWS account $EXPECTED? Type the account ID to confirm: " answer
  [[ "$answer" == "$EXPECTED" ]] || die "not confirmed"
elif ((!YES)); then
  terraform show -no-color "$PLAN_FILE" >&2
  read -r -p "Apply the reviewed plan above to AWS account $EXPECTED? Type the account ID to confirm: " answer
  [[ "$answer" == "$EXPECTED" ]] || die "not confirmed"
fi

# Terraform itself refuses a saved plan whose state has changed since it was made ("stale plan").
terraform apply -input=false -lock-timeout=5m "$PLAN_FILE"
[[ -n "$REVIEWED_PLAN" ]] || rm -f "$PLAN_FILE"

if [[ "$STATE_EXISTS" != "true" ]]; then
  KEY_ARN="$(terraform output -raw state_kms_key_arn)"
  log "migrating state into s3://$BUCKET/$STATE_KEY"
  write_backend
  backend_args "$KEY_ARN"
  terraform init -migrate-state -force-copy -input=false "${BARGS[@]}" >/dev/null
  aws s3api head-object --bucket "$BUCKET" --key "$STATE_KEY" --expected-bucket-owner "$EXPECTED" >/dev/null ||
    die "state migration could not be verified; keep terraform.tfstate and see the runbook §6"
  rm -f terraform.tfstate terraform.tfstate.backup
  log "state migrated and verified; local copy removed"
fi

# RR-01, RR-02: fail closed unless the live bucket and key protections are exactly the reviewed ones. No outputs
# (and so no role ARNs for GitHub) are written otherwise.
verify_state_protection "$BUCKET" "$EXPECTED" "$(terraform output -json)"

terraform output -json | jq '{
  account_id: .account_id.value, region: .region.value,
  state_bucket: .state_bucket.value, state_kms_key_arn: .state_kms_key_arn.value,
  github_oidc_provider_arn: .github_oidc_provider_arn.value,
  permissions_boundary_arn: .permissions_boundary_arn.value,
  github_role_arns: .github_role_arns.value, github_environments: .github_environments.value,
  backend_config: .backend_config.value
}' >"$GENERATED_DIR/bootstrap-outputs.json"
log "wrote $GENERATED_DIR/bootstrap-outputs.json"
log "next: infra/scripts/github-setup.sh --outputs $GENERATED_DIR/bootstrap-outputs.json --variables-only --apply"
