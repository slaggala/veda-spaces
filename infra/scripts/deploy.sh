#!/usr/bin/env bash
# Workflow side of a staging deploy (12-deploy; runbook docs/operations/staging-platform-runbooks.md §1). Needs a
# veda-gh-deploy OIDC session confined to Mumbai. Owner credentials are never used here.
#
#   infra/scripts/deploy.sh --tag <12 hex digits of the commit>
#
# 1. Builds the API image from this commit and pushes it to veda-api with the immutable tag.
# 2. Waits for the image scan and refuses HIGH or CRITICAL findings.
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
    -h | --help) sed -n '2,13p' "$0"; exit 0 ;;
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

log "1. build and push $REPO:$TAG"
docker build --platform linux/arm64 -f "$REPO_ROOT/api/deploy/Dockerfile" -t "$REGISTRY/$REPO:$TAG" "$REPO_ROOT/api"
aws ecr get-login-password --region "$VEDA_REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker push "$REGISTRY/$REPO:$TAG"
DIGEST="$(aws ecr describe-images --region "$VEDA_REGION" --repository-name "$REPO" --image-ids "imageTag=$TAG" --output json |
  jq -r '.imageDetails[0].imageDigest // empty')"
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || die "cannot read the pushed image digest"
log "image $REPO@$DIGEST"

log "2. image scan"
aws ecr wait image-scan-complete --region "$VEDA_REGION" --repository-name "$REPO" --image-id "imageDigest=$DIGEST"
counts="$(aws ecr describe-image-scan-findings --region "$VEDA_REGION" --repository-name "$REPO" --image-id "imageDigest=$DIGEST" \
  --output json | jq -c '.imageScanFindings.findingSeverityCounts // {}')"
log "scan findings: $counts"
[[ "$(jq '(.CRITICAL // 0) + (.HIGH // 0)' <<<"$counts")" == 0 ]] || die "the image has HIGH or CRITICAL findings; refusing to deploy it"

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
