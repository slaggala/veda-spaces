#!/usr/bin/env bash
# Plan and apply of a staging stack through GitHub OIDC (AUT-301). Owner credentials are never used here.
#
#   infra/scripts/stack.sh plan  --stack core [--out DIR]
#       In 10-infra-plan with a veda-gh-plan session. terraform init with the S3 backend (staging/<stack>.tfstate,
#       state key, native lock), plan to DIR/<stack>.tfplan, plan guard (check-plan.sh). Writes the plan, its text
#       (<stack>-plan.txt), its JSON and its metadata (<stack>-plan.meta.json: stack, commit, account, repository,
#       workflow, run, Terraform version, SHA-256 of the plan and of its text, change counts). Terraform's plan output
#       goes to DIR/<stack>-plan.log, not to the job log: the repository is public (N-04-S). Prints the change
#       summary and the plan's SHA-256, the digest an apply must be approved for. Creates nothing.
#
#   infra/scripts/stack.sh apply --stack core --plan-dir DIR --plan-sha256 D --plan-run-id N
#       In 11-infra-apply with a veda-gh-apply session, and only once every gate of infra/config/apply-gate.json is
#       decided (OD-B7, N-04-S). Applies exactly the approved plan: the file whose SHA-256 is D, made by plan run N of
#       10-infra-plan on main for this commit, account, stack and Terraform version, whose text rendered again is the
#       text recorded at plan time, and which passes the plan guard again. Terraform refuses it if the state changed.
#
#   infra/scripts/stack.sh gate
#       Fails (exit 1) unless every apply gate is decided and its record exists. 11-infra-apply runs it first.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

CMD="${1:-}"
if [[ "$CMD" == -h || "$CMD" == --help ]]; then sed -n '2,24p' "$0"; exit 0; fi
[[ "$CMD" == plan || "$CMD" == apply || "$CMD" == gate ]] || die "usage: stack.sh plan|apply|gate ... (see --help)"
shift
STACK="" OUT="" PLAN_DIR="" APPROVED_SHA="" PLAN_RUN=""
while (($#)); do
  case "$1" in
    --stack) STACK="${2:-}"; shift 2 ;;
    --out) OUT="${2:-}"; shift 2 ;;
    --plan-dir) PLAN_DIR="${2:-}"; shift 2 ;;
    --plan-sha256) APPROVED_SHA="${2:-}"; shift 2 ;;
    --plan-run-id) PLAN_RUN="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,24p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

APPLY_GATE="${VEDA_APPLY_GATE:-$INFRA_DIR/config/apply-gate.json}"
PLAN_WORKFLOW=".github/workflows/10-infra-plan.yml"
APPLY_WORKFLOW=".github/workflows/11-infra-apply.yml"

# Every gate must be decided with a status it allows and a record committed in the repository.
require_apply_gate() {
  local problems
  [[ -f "$APPLY_GATE" ]] || die "apply gate file not found: $APPLY_GATE; refusing"
  # An empty, truncated or reshaped file must never read as "no problems".
  jq -e 'type == "object" and (.gates | type) == "object"' "$APPLY_GATE" >/dev/null 2>&1 ||
    die "apply gate file $APPLY_GATE is not a JSON object with a gates object; refusing"
  problems="$(jq -r --arg root "$REPO_ROOT" '
    def allowed: {"OD-B7": ["CLOSED", "ACCEPTED"], "N-04-S": ["ACCEPTED", "PRIVATE_REPOSITORY"]};
    (.gates // {}) as $g
    | (allowed | keys[] | select($g[.] == null) | "\(.): gate missing"),
      ($g | to_entries[] | .key as $k | .value as $v
        | if (allowed[$k] // null) == null then "\($k): unknown gate"
          elif ($v.status // "UNDECIDED") == "UNDECIDED" then "\($k): \($v.title // "") is UNDECIDED"
          elif (allowed[$k] | index($v.status)) == null then "\($k): status \($v.status) is not one of \(allowed[$k] | join(", "))"
          elif (($v.record // "") | length) == 0 then "\($k): decided without a record"
          else empty end)' "$APPLY_GATE")" || die "apply gate file is not valid JSON; refusing"
  if [[ -z "$problems" ]]; then
    while IFS= read -r rec; do
      [[ -f "$REPO_ROOT/$rec" ]] || problems+="record $rec does not exist in the repository"$'\n'
    done < <(jq -r '.gates[].record' "$APPLY_GATE")
  fi
  if [[ -n "$problems" ]]; then
    while IFS= read -r p; do [[ -n "$p" ]] && log "GATE: $p"; done <<<"$problems"
    die "staging applies are disabled until every gate in infra/config/apply-gate.json is decided (owner decision OD-B7); refusing"
  fi
  log "apply gates decided: $(jq -r '[.gates | to_entries[] | "\(.key)=\(.value.status)"] | join(", ")' "$APPLY_GATE")"
}

if [[ "$CMD" == gate ]]; then
  require_tools jq
  require_apply_gate
  exit 0
fi

[[ "$STACK" =~ ^[a-z]+$ ]] || die "--stack must be a stack name such as core"
STACK_DIR="$INFRA_DIR/terraform/envs/staging-$STACK"
[[ -d "$STACK_DIR" ]] || die "unknown stack $STACK (no $STACK_DIR)"
STATE_KEY="staging/$STACK.tfstate"

require_tools aws jq terraform git
ACCOUNT="$(manifest_get .account_id)"
REPO="$(manifest_get .repository)"
require_account_id "$ACCOUNT"
require_region

# The session is the workflow role for this command, in the approved account, confined to Mumbai by veda-boundary.
require_workflow_session() {
  local role="$1" arn
  arn="$(aws sts get-caller-identity --output json 2>/dev/null | jq -r '.Arn // empty')" ||
    die "no usable AWS credentials (aws sts get-caller-identity failed)"
  [[ "$arn" =~ ^arn:aws:sts::${ACCOUNT}:assumed-role/${VEDA_PREFIX}-gh-${role}/.+$ ]] ||
    die "the session is '${arn:-none}', not ${VEDA_PREFIX}-gh-$role in account $ACCOUNT; refusing"
  require_region_guarded_session
  log "session: $arn"
}

# The backend is the bootstrap's state bucket and key; the repository variables must name exactly those.
backend_init() {
  local bucket key_arn
  bucket="$(state_bucket_name "$ACCOUNT")"
  [[ -z "${TF_STATE_BUCKET:-}" || "$TF_STATE_BUCKET" == "$bucket" ]] ||
    die "TF_STATE_BUCKET is $TF_STATE_BUCKET, the approved account's state bucket is $bucket; refusing"
  key_arn="${TF_STATE_KMS_KEY_ARN:-}"
  [[ "$key_arn" =~ ^arn:aws:kms:${VEDA_REGION}:${ACCOUNT}:key/[0-9a-f-]{36}$ ]] ||
    die "TF_STATE_KMS_KEY_ARN must be the state key of account $ACCOUNT in $VEDA_REGION (got '${key_arn:-empty}'); refusing"
  terraform -chdir="$STACK_DIR" init -input=false -reconfigure \
    "-backend-config=bucket=$bucket" "-backend-config=key=$STATE_KEY" "-backend-config=region=$VEDA_REGION" \
    "-backend-config=encrypt=true" "-backend-config=kms_key_id=$key_arn" "-backend-config=use_lockfile=true" >/dev/null ||
    die "terraform init failed for $STATE_KEY"
  log "backend: s3://$bucket/$STATE_KEY (state key, native lock)"
}

guard() {
  "$INFRA_DIR/scripts/check-plan.sh" --plan-json "$1" --account "$ACCOUNT" --repo "$REPO" --prefix "$VEDA_PREFIX"
}

TF_VERSION="$(terraform version -json | jq -r '.terraform_version // empty')"
[[ -n "$TF_VERSION" ]] || die "cannot read the Terraform version"
COMMIT="$(current_commit)"
export TF_IN_AUTOMATION=1 TF_INPUT=0

if [[ "$CMD" == plan ]]; then
  OUT="${OUT:-$GENERATED_DIR/$STACK}"
  mkdir -p "$OUT"
  OUT="$(cd "$OUT" && pwd)"
  require_workflow_session plan
  backend_init
  PLAN="$OUT/$STACK.tfplan"
  # The plan output can describe infrastructure in detail; it stays in a file (N-04-S), and only a failure is shown.
  if ! terraform -chdir="$STACK_DIR" plan -input=false -lock-timeout=5m -no-color -out="$PLAN" >"$OUT/$STACK-plan.log" 2>&1; then
    tail -n 40 "$OUT/$STACK-plan.log" >&2
    die "terraform plan failed"
  fi
  terraform -chdir="$STACK_DIR" show -no-color "$PLAN" >"$OUT/$STACK-plan.txt"
  terraform -chdir="$STACK_DIR" show -json "$PLAN" >"$OUT/$STACK-plan.json"
  guard "$OUT/$STACK-plan.json"
  jq -n --arg stack "$STACK" --arg commit "$COMMIT" --arg account "$ACCOUNT" --arg repo "$REPO" \
    --arg wf "${GITHUB_WORKFLOW_REF:-local}" --arg run "${GITHUB_RUN_ID:-local}" --arg attempt "${GITHUB_RUN_ATTEMPT:-1}" \
    --arg tf "$TF_VERSION" --arg sum "$(sha256_of "$PLAN")" --arg text "$(sha256_of "$OUT/$STACK-plan.txt")" \
    --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --slurpfile p "$OUT/$STACK-plan.json" \
    '{mode: "plan", stack: $stack, commit: $commit, account_id: $account, repository: $repo, workflow_ref: $wf,
      run_id: $run, run_attempt: $attempt, terraform_version: $tf, plan_sha256: $sum, plan_text_sha256: $text,
      state_key: ("staging/" + $stack + ".tfstate"), created_at: $at,
      changes: ([$p[0].resource_changes[]?.change.actions | join(",")] | group_by(.) | map({(.[0]): length}) | add // {})}' \
    >"$OUT/$STACK-plan.meta.json"
  summary="$(grep -E '^(Plan: |No changes\.)' "$OUT/$STACK-plan.txt" | head -n 1 || true)"
  log "plan summary: ${summary:-(no summary line)}"
  log "plan sha256 (the digest an apply must be approved for): $(jq -r .plan_sha256 "$OUT/$STACK-plan.meta.json")"
  log "plan mode: nothing was created"
  exit 0
fi

# --- apply -------------------------------------------------------------------------------------------------------
require_apply_gate
[[ -n "$PLAN_DIR" && -n "$APPROVED_SHA" && -n "$PLAN_RUN" ]] ||
  die "apply needs --plan-dir, --plan-sha256 (the approved digest) and --plan-run-id"
[[ "$APPROVED_SHA" =~ ^[0-9a-f]{64}$ ]] || die "--plan-sha256 must be the 64-hex SHA-256 of the approved plan file"
[[ "$PLAN_RUN" =~ ^[0-9]+$ ]] || die "--plan-run-id must be a run ID"
[[ "${GITHUB_WORKFLOW_REF:-}" == "$REPO/$APPLY_WORKFLOW@refs/heads/main" ]] ||
  die "staging stacks are applied only by $APPLY_WORKFLOW on main (this is '${GITHUB_WORKFLOW_REF:-local}'); refusing"
PLAN="$PLAN_DIR/$STACK.tfplan" META="$PLAN_DIR/$STACK-plan.meta.json" TEXT="$PLAN_DIR/$STACK-plan.txt"
for f in "$PLAN" "$META" "$TEXT"; do [[ -f "$f" ]] || die "reviewed plan file missing: $f"; done
PLAN="$(cd "$PLAN_DIR" && pwd)/$STACK.tfplan"
sum="$(sha256_of "$PLAN")"
[[ "$sum" == "$APPROVED_SHA" ]] || die "plan file sha256 $sum is not the approved plan ($APPROVED_SHA); refusing"
meta_problems="$(jq -r --arg sum "$sum" --arg stack "$STACK" --arg acct "$ACCOUNT" --arg repo "$REPO" --arg commit "$COMMIT" \
  --arg wf "$REPO/$PLAN_WORKFLOW@refs/heads/main" --arg run "$PLAN_RUN" --arg tf "$TF_VERSION" '
  [ (if .mode != "plan" then "is not from a plan run" else empty end),
    (if .plan_sha256 != $sum then "names plan sha256 \(.plan_sha256), not the approved file" else empty end),
    (if .stack != $stack then "is for stack \(.stack), not \($stack)" else empty end),
    (if .account_id != $acct then "is for account \(.account_id), not \($acct)" else empty end),
    (if .repository != $repo then "is for repository \(.repository), not \($repo)" else empty end),
    (if .commit != $commit then "was made from commit \(.commit), this run is \($commit): plan again" else empty end),
    (if .workflow_ref != $wf then "was made by \(.workflow_ref), not \($wf)" else empty end),
    (if .run_id != $run then "is from run \(.run_id), not the approved run \($run)" else empty end),
    (if .terraform_version != $tf then "was made with Terraform \(.terraform_version), this is \($tf)" else empty end)
  ] | .[]' "$META")" || die "cannot read the plan metadata; refusing"
if [[ -n "$meta_problems" ]]; then
  while IFS= read -r p; do log "REFUSED: the reviewed plan $p"; done <<<"$meta_problems"
  die "the reviewed plan is not the approved plan for this apply"
fi
[[ "$(sha256_of "$TEXT")" == "$(jq -r .plan_text_sha256 "$META")" ]] ||
  die "the reviewed plan text is not the text recorded at plan time; refusing"
require_workflow_session apply
backend_init
terraform -chdir="$STACK_DIR" show -no-color "$PLAN" >"$PLAN_DIR/applying-plan.txt"
[[ "$(sha256_of "$PLAN_DIR/applying-plan.txt")" == "$(jq -r .plan_text_sha256 "$META")" ]] ||
  die "the plan file renders a different text from the one that was reviewed; refusing"
terraform -chdir="$STACK_DIR" show -json "$PLAN" >"$PLAN_DIR/applying-plan.json"
guard "$PLAN_DIR/applying-plan.json"
log "approved plan verified: sha256 $sum, plan run $PLAN_RUN, commit $COMMIT, stack $STACK"
# The apply output stays in a file, like the plan output (N-04-S): it can carry planned values, and AWS errors can
# repeat them (the AUT-112 recipient is masked only in the plan job). The log shows the result line, or on failure the
# last lines with every email address redacted.
if ! terraform -chdir="$STACK_DIR" apply -input=false -lock-timeout=5m -no-color "$PLAN" >"$PLAN_DIR/apply.log" 2>&1; then
  tail -n 40 "$PLAN_DIR/apply.log" | sed -E 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/<redacted email>/g' >&2
  die "terraform apply failed (output in $PLAN_DIR/apply.log)"
fi
log "$(grep -E '^Apply complete!' "$PLAN_DIR/apply.log" | tail -n 1 || true)"
log "applied the approved plan of run $PLAN_RUN to $STATE_KEY"
