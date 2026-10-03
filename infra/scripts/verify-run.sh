#!/usr/bin/env bash
# Verifies GitHub Actions runs for 00-bootstrap and the staging stack workflows (RR-05, RR-07, AUT-301). Read-only:
# GET requests with the workflow's GITHUB_TOKEN (actions: read). Every lookup fails closed.
#
#   infra/scripts/verify-run.sh plan-run --repo owner/repo --run-id N --this-run-id M --commit SHA \
#                                        --plan-sha256 DIGEST --out DIR
#       RR-05. Binds the reviewed plan to the approved plan to the file that will be applied. It accepts plan run N
#       only if it is a completed, successful workflow_dispatch plan run of .github/workflows/00-bootstrap.yml (the
#       same workflow as run M, this apply run) on main, in this repository, for commit SHA. It downloads that run's
#       single artifact bootstrap-plan-N and checks, in order:
#         1. the zip's SHA-256 equals the digest GitHub recorded when the plan run uploaded it (no substituted or
#            re-uploaded artifact);
#         2. the plan file's SHA-256 equals DIGEST, the approved plan digest typed into the apply run and shown in
#            its name to the environment reviewer (no other plan, whatever its metadata says);
#         3. the metadata names that digest, run N, commit SHA and the 00-bootstrap workflow on main, and the plan
#            text the reviewer read has the SHA-256 recorded at plan time.
#       The verified files are left in DIR for bootstrap.sh, which checks the digest again and re-renders the text.
#
#   infra/scripts/verify-run.sh plan-run --stack STACK ... (same options)
#       AUT-301, the same binding for a staging stack: plan run N must be a successful workflow_dispatch run of
#       .github/workflows/10-infra-plan.yml on main ("10-infra-plan (STACK)"), run M must be
#       .github/workflows/11-infra-apply.yml, the artifact is STACK-plan-N with STACK.tfplan, STACK-plan.meta.json and
#       STACK-plan.txt, and the metadata must name 10-infra-plan on main.
#
#   infra/scripts/verify-run.sh approval --repo owner/repo --run-id N --environment NAME
#       RR-07. Succeeds only if run N has an approved review for environment NAME: proof that the job ran behind a
#       required reviewer, not in an unprotected (for example auto-created) environment.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

CMD="${1:-}"
if [[ "$CMD" == -h || "$CMD" == --help ]]; then sed -n '2,30p' "$0"; exit 0; fi
[[ "$CMD" == plan-run || "$CMD" == approval ]] || die "usage: verify-run.sh plan-run|approval ... (see --help)"
shift
REPO="" RUN="" THIS_RUN="" COMMIT="" DIGEST="" OUT="" ENVIRONMENT="" STACK=""
while (($#)); do
  case "$1" in
    --repo) REPO="${2:-}"; shift 2 ;;
    --run-id) RUN="${2:-}"; shift 2 ;;
    --this-run-id) THIS_RUN="${2:-}"; shift 2 ;;
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --plan-sha256) DIGEST="${2:-}"; shift 2 ;;
    --out) OUT="${2:-}"; shift 2 ;;
    --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
    --stack) STACK="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,30p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

require_tools gh jq
[[ "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "--repo must be owner/repo"
[[ "$RUN" =~ ^[0-9]+$ ]] || die "--run-id must be a run ID"

if [[ "$CMD" == approval ]]; then
  [[ -n "$ENVIRONMENT" ]] || die "--environment is required"
  approvals="$(gh api "repos/$REPO/actions/runs/$RUN/approvals")" || die "cannot read the approvals of run $RUN; refusing"
  approvers="$(jq -r --arg env "$ENVIRONMENT" '
    [.[]? | select(.state == "approved") | select(any(.environments[]?; .name == $env)) | .user.login] | unique | join(",")' \
    <<<"$approvals")" || die "cannot read the approvals of run $RUN; refusing"
  [[ -n "$approvers" ]] ||
    die "run $RUN has no approved review for environment '$ENVIRONMENT': it is not protected by a required reviewer; refusing"
  log "run $RUN was approved for environment '$ENVIRONMENT' by: $approvers"
  exit 0
fi

require_tools unzip
[[ "$THIS_RUN" =~ ^[0-9]+$ ]] || die "--this-run-id must be a run ID"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "--commit must be a full commit SHA"
[[ "$DIGEST" =~ ^[0-9a-f]{64}$ ]] || die "--plan-sha256 must be the 64-hex SHA-256 of the reviewed plan file"
[[ -n "$OUT" ]] || die "--out is required"

# What a plan run is: the bootstrap's own workflow (plan and apply in one file), or a staging stack's plan workflow
# with its separate apply workflow (AUT-301).
if [[ -z "$STACK" ]]; then
  PLAN_WF="$VEDA_BOOTSTRAP_WORKFLOW" APPLY_WF="$VEDA_BOOTSTRAP_WORKFLOW" PLAN_TITLE="00-bootstrap (plan)"
  ART_PREFIX="bootstrap-plan" PLAN_FILE="bootstrap.tfplan" META_FILE="bootstrap-plan.meta.json" TEXT_FILE="bootstrap-plan.txt"
  SAME_WORKFLOW=true
else
  [[ "$STACK" =~ ^[a-z]+$ ]] || die "--stack must be a stack name such as core"
  PLAN_WF=".github/workflows/10-infra-plan.yml" APPLY_WF=".github/workflows/11-infra-apply.yml" PLAN_TITLE="10-infra-plan ($STACK)"
  ART_PREFIX="$STACK-plan" PLAN_FILE="$STACK.tfplan" META_FILE="$STACK-plan.meta.json" TEXT_FILE="$STACK-plan.txt"
  SAME_WORKFLOW=false
fi

run="$(gh api "repos/$REPO/actions/runs/$RUN")" || die "cannot read run $RUN; refusing"
this="$(gh api "repos/$REPO/actions/runs/$THIS_RUN")" || die "cannot read run $THIS_RUN; refusing"
run_problems="$(jq -r --argjson this "$this" --arg repo "$REPO" --arg sha "$COMMIT" --arg wf "$PLAN_WF" --arg awf "$APPLY_WF" \
  --arg title "$PLAN_TITLE" --argjson same "$SAME_WORKFLOW" --argjson id "$RUN" '
  [ (if .id != $id then "is not run \($id)" else empty end),
    (if .path != $wf then "was made by \(.path), not \($wf)" else empty end),
    (if $this.path != $awf then "this apply run is \($this.path), not \($awf)" else empty end),
    (if $same and .workflow_id != $this.workflow_id then "belongs to workflow \(.workflow_id), not this workflow (\($this.workflow_id))" else empty end),
    (if .repository.full_name != $repo or .head_repository.full_name != $repo then "is not from \($repo) (fork or other repository)" else empty end),
    (if .head_sha != $sha then "is for commit \(.head_sha), not \($sha): plan again on this commit" else empty end),
    (if .head_branch != "main" then "ran on \(.head_branch), not main" else empty end),
    (if .event != "workflow_dispatch" then "was triggered by \(.event), not workflow_dispatch" else empty end),
    (if .status != "completed" or .conclusion != "success" then "is \(.status)/\(.conclusion), not a successful run" else empty end),
    (if .display_title != $title then "is \"\(.display_title)\", not a plan run" else empty end)
  ] | .[]' <<<"$run")" || die "cannot read run $RUN; refusing"
if [[ -n "$run_problems" ]]; then
  while IFS= read -r p; do log "REFUSED: plan run $RUN $p"; done <<<"$run_problems"
  die "run $RUN is not a reviewed ${PLAN_WF##*/} plan run for this commit"
fi

name="$ART_PREFIX-$RUN"
artifacts="$(gh api "repos/$REPO/actions/runs/$RUN/artifacts?per_page=100")" || die "cannot list the artifacts of run $RUN; refusing"
artifact="$(jq -c --arg n "$name" '[.artifacts[]? | select(.name == $n)] | if length == 1 then .[0] else empty end' <<<"$artifacts")"
[[ -n "$artifact" ]] || die "run $RUN does not have exactly one artifact named $name; refusing"
jq -e --argjson id "$RUN" --arg sha "$COMMIT" '.expired == false and .workflow_run.id == $id and .workflow_run.head_sha == $sha' \
  <<<"$artifact" >/dev/null || die "artifact $name is expired or not from run $RUN at $COMMIT; refusing"
artifact_id="$(jq -r .id <<<"$artifact")"
artifact_digest="$(jq -r '.digest // empty' <<<"$artifact")"
[[ "$artifact_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || die "artifact $name has no SHA-256 digest recorded by GitHub; refusing"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
gh api "repos/$REPO/actions/artifacts/$artifact_id/zip" >"$tmp/plan.zip" || die "cannot download artifact $name; refusing"
[[ "sha256:$(sha256_of "$tmp/plan.zip")" == "$artifact_digest" ]] ||
  die "artifact $name differs from the digest GitHub recorded when run $RUN uploaded it ($artifact_digest); refusing"

rm -rf "$OUT"
mkdir -p "$OUT"
unzip -q "$tmp/plan.zip" -d "$OUT"
for f in "$PLAN_FILE" "$META_FILE" "$TEXT_FILE"; do
  [[ -f "$OUT/$f" ]] || die "artifact $name has no $f; refusing"
done

plan_sum="$(sha256_of "$OUT/$PLAN_FILE")"
[[ "$plan_sum" == "$DIGEST" ]] ||
  die "the plan of run $RUN (sha256 $plan_sum) is not the approved plan (sha256 $DIGEST); refusing"
meta="$OUT/$META_FILE"
jq -e --arg d "$DIGEST" --arg run "$RUN" --arg sha "$COMMIT" --arg wf "$REPO/$PLAN_WF@refs/heads/main" \
  '.plan_sha256 == $d and .run_id == $run and .commit == $sha and .workflow_ref == $wf' "$meta" >/dev/null ||
  die "the metadata of run $RUN does not name the approved digest, run $RUN, commit $COMMIT and $PLAN_WF on main; refusing"
[[ "$(sha256_of "$OUT/$TEXT_FILE")" == "$(jq -r '.plan_text_sha256 // empty' "$meta")" ]] ||
  die "the plan text in artifact $name is not the text recorded at plan time; refusing"

log "approved plan bound: run $RUN, artifact $artifact_digest, plan sha256 $DIGEST, text sha256 $(jq -r .plan_text_sha256 "$meta")"
