#!/usr/bin/env bash
# Workflow side of a staging deploy (12-deploy; runbook docs/operations/staging-platform-runbooks.md §1). Needs a
# veda-gh-deploy OIDC session confined to Mumbai. Owner credentials are never used here.
#
#   infra/scripts/deploy.sh --tag <12 hex digits of the commit>
#
# 1. Builds the API image from this commit and pushes it to veda-api with the immutable tag.
# 2. Waits for the image scan and refuses HIGH or CRITICAL findings not covered by a reviewed staging exception
#    (check-image-scan.sh, infra/config/image-scan-exceptions.json).
# 3. Uploads the deploy bundle (api/deploy and infra/host as committed: git archive) with its SHA-256; an existing
#    bundle for the tag must be the same bytes.
# 4. Runs the SSM document veda-deploy on the staging host (tags project=veda-spaces, env=staging) with the tag, the
#    image digest and the bundle SHA-256, waits for it and prints its result.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

TAG=""
while (($#)); do
  case "$1" in
    --tag) TAG="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,14p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done
[[ "$TAG" =~ ^[0-9a-f]{12}$ ]] || die "--tag must be the first 12 hex digits of the commit"
[[ "$(current_commit)" == "$TAG"* ]] || die "--tag $TAG is not this commit ($(current_commit))"

require_tools aws jq docker git
ACCOUNT="$(manifest_get .account_id)"
require_account_id "$ACCOUNT"
require_region
arn="$(aws sts get-caller-identity --output json | jq -r '.Arn // empty')" || die "no usable AWS credentials"
[[ "$arn" =~ ^arn:aws:sts::${ACCOUNT}:assumed-role/${VEDA_PREFIX}-gh-deploy/.+$ ]] || die "the session is '${arn:-none}', not ${VEDA_PREFIX}-gh-deploy; refusing"
require_region_guarded_session

REGISTRY="$ACCOUNT.dkr.ecr.$VEDA_REGION.amazonaws.com"
REPO="${VEDA_PREFIX}-api"
BUCKET="${VEDA_PREFIX}-stg-artifacts-$ACCOUNT"
KEY="deploy/$TAG/bundle.tgz"

image_digest() { aws ecr describe-images --region "$VEDA_REGION" --repository-name "$REPO" --image-ids "imageTag=$TAG" --output json; }
# Tags are immutable: a commit already pushed (a re-run after a configuration or secret change, runbook §6.5/§6.6)
# reuses its image instead of failing on the push. The scan gate below still applies to it.
ecr_err="$(mktemp)"
if existing="$(image_digest 2>"$ecr_err")"; then
  DIGEST="$(jq -r '.imageDetails[0].imageDigest // empty' <<<"$existing")"
  log "1. image $REPO:$TAG already pushed (immutable tag): reusing it"
elif grep -q ImageNotFoundException "$ecr_err"; then
  log "1. build and push $REPO:$TAG"
  docker build --platform linux/arm64 -f "$REPO_ROOT/api/deploy/Dockerfile" -t "$REGISTRY/$REPO:$TAG" "$REPO_ROOT/api"
  aws ecr get-login-password --region "$VEDA_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
  docker push "$REGISTRY/$REPO:$TAG"
  DIGEST="$(image_digest | jq -r '.imageDetails[0].imageDigest // empty')"
else
  cat "$ecr_err" >&2
  die "cannot read $REPO:$TAG from ECR; refusing"
fi
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || die "cannot read the pushed image digest"
log "image $REPO@$DIGEST"

log "2. image scan"
# Scan on push registers the scan a few seconds after the push. Until then ECR answers ScanNotFoundException, which
# the CLI waiter (ecr wait image-scan-complete) treats as a failure, so poll instead: "not found yet" and "in
# progress" wait, a completed scan is read, and anything else (a failed or unsupported scan, another error, the time
# limit) refuses the deploy. The deploy role cannot start a scan itself.
SCAN_POLL_SECONDS="${VEDA_SCAN_POLL_SECONDS:-10}"
SCAN_MAX_POLLS="${VEDA_SCAN_MAX_POLLS:-60}"
scan_err="$(mktemp)" scan_json="$(mktemp)"
trap 'rm -f "$scan_err" "$scan_json"' EXIT
findings=""
for ((i = 1; i <= SCAN_MAX_POLLS; i++)); do
  if out="$(aws ecr describe-image-scan-findings --region "$VEDA_REGION" --repository-name "$REPO" \
    --image-id "imageDigest=$DIGEST" --output json 2>"$scan_err")"; then
    status="$(jq -r '.imageScanStatus.status // empty' <<<"$out")"
    case "$status" in
      COMPLETE) findings="$out"; break ;;
      IN_PROGRESS | PENDING) ;;
      *) die "image scan ended ${status:-without a status}: $(jq -r '.imageScanStatus.description // empty' <<<"$out"); refusing" ;;
    esac
  elif grep -q ScanNotFoundException "$scan_err"; then
    status="not registered yet"
  else
    die "cannot read the image scan: $(tr '\n' ' ' <"$scan_err")"
  fi
  ((i < SCAN_MAX_POLLS)) && sleep "$SCAN_POLL_SECONDS"
done
[[ -n "$findings" ]] || die "image scan not complete after $SCAN_MAX_POLLS checks (last: $status); refusing"
counts="$(jq -c '.imageScanFindings.findingSeverityCounts // {}' <<<"$findings")"
log "scan findings: $counts"
# HIGH and CRITICAL findings refuse the image unless a reviewed, unexpired staging exception covers each one exactly
# (infra/config/image-scan-exceptions.json).
printf '%s' "$findings" >"$scan_json"
"$(dirname "$0")/check-image-scan.sh" --findings "$scan_json" --environment staging

log "3. deploy bundle s3://$BUCKET/$KEY"
BUNDLE="$GENERATED_DIR/bundle-$TAG.tgz"
mkdir -p "$GENERATED_DIR"
git -C "$REPO_ROOT" archive --format=tar.gz -o "$BUNDLE" "$(current_commit)" api/deploy infra/host
SUM="$(sha256_of "$BUNDLE")"
if existing="$(aws s3api head-object --bucket "$BUCKET" --key "$KEY" --output json 2>/dev/null)"; then
  [[ "$(jq -r '.Metadata.sha256 // empty' <<<"$existing")" == "$SUM" ]] || die "a different bundle already exists for $TAG; refusing"
else
  aws s3 cp --region "$VEDA_REGION" "$BUNDLE" "s3://$BUCKET/$KEY" --metadata "sha256=$SUM" >/dev/null
fi
log "bundle sha256 $SUM"

log "4. veda-deploy on the staging host"
cmd="$(aws ssm send-command --region "$VEDA_REGION" --document-name "${VEDA_PREFIX}-deploy" \
  --targets "Key=tag:project,Values=veda-spaces" "Key=tag:env,Values=staging" --max-concurrency 1 --max-errors 0 \
  --parameters "releaseTag=$TAG,imageDigest=$DIGEST,bundleSha256=$SUM" \
  --cloud-watch-output-config "CloudWatchOutputEnabled=true,CloudWatchLogGroupName=/${VEDA_PREFIX}/staging/host" \
  --comment "12-deploy ${GITHUB_RUN_ID:-local} $TAG" --output json | jq -r '.Command.CommandId // empty')"
[[ -n "$cmd" ]] || die "send-command returned no command id"
status=""
for _ in $(seq 1 180); do
  status="$(aws ssm list-commands --region "$VEDA_REGION" --command-id "$cmd" --output json | jq -r '.Commands[0].Status // empty')"
  case "$status" in Success | Failed | Cancelled | TimedOut | "Delivery Timed Out" | "Execution Timed Out") break ;; esac
  sleep 10
done
aws ssm list-command-invocations --region "$VEDA_REGION" --command-id "$cmd" --details --output json |
  jq -r '.CommandInvocations[] | "\(.InstanceId): \(.Status)\n\(.CommandPlugins[0].Output // "" | .[-3000:])"'
[[ "$status" == Success ]] || die "veda-deploy ended $status (command $cmd); the host log group holds the full output"
log "deployed $TAG ($DIGEST) to staging"
