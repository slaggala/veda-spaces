#!/usr/bin/env bash
# PB-10: IAM's own evaluation of the rendered permissions boundary, before anything is applied. Read-only: it calls
# iam:SimulateCustomPolicy (a global action the region-guarded session keeps) with the boundary from the plan and an
# allow-all identity policy, and stops unless IAM itself gives the reviewed answer for each probe. One probe must be
# ALLOWED, so a simulator that denies everything cannot pass.
#
#   infra/scripts/simulate-boundary.sh --plan-json infra/generated/bootstrap-plan.json --account 123456789012
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

PLAN_JSON="" ACCOUNT=""
while (($#)); do
  case "$1" in
    --plan-json) PLAN_JSON="${2:-}"; shift 2 ;;
    --account) ACCOUNT="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,8p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done
require_tools aws jq
require_account_id "$ACCOUNT"
[[ -f "$PLAN_JSON" ]] || die "plan JSON not found: $PLAN_JSON"
boundary="$(jq -r '[.resource_changes[]? | select(.address == "aws_iam_policy.boundary") | .change.after.policy] | if length == 1 and (.[0] | type) == "string" then .[0] else empty end' "$PLAN_JSON")"
[[ -n "$boundary" ]] || die "the plan has no known veda-boundary policy to simulate; refusing"

A="arn:aws:iam::$ACCOUNT"
APPLY="$A:role/${VEDA_PREFIX}-gh-apply"
HOST="$A:role/${VEDA_PREFIX}-host"
BOUNDARY_ARN="$A:policy/${VEDA_PREFIX}-boundary"
ALLOW_ALL='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}'
failures=()

# probe <name> <expected: explicitDeny|allowed> <action> <resource> [key=value ...] (string context entries)
probe() {
  local name="$1" want="$2" action="$3" resource="$4" ctx=() kv got
  shift 4
  for kv in "$@"; do ctx+=("ContextKeyName=${kv%%=*},ContextKeyValues=${kv#*=},ContextKeyType=string"); done
  got="$(aws iam simulate-custom-policy --policy-input-list "$ALLOW_ALL" --permissions-boundary-policy-input-list "$boundary" \
    --action-names "$action" --resource-arns "$resource" ${ctx[@]+--context-entries "${ctx[@]}"} --output json |
    jq -r '.EvaluationResults[0].EvalDecision // empty')" || die "IAM simulation failed for '$name'; refusing"
  if [[ "$got" == "$want" ]]; then log "simulated: $name -> $got"; else failures+=("$name: IAM says ${got:-nothing}, expected $want"); fi
}

probe "control: a workload role reads EC2 in Mumbai" allowed ec2:DescribeInstances "*" \
  aws:RequestedRegion=ap-south-1 "aws:PrincipalArn=$HOST"
probe "S3 bucket outside Mumbai" explicitDeny s3:CreateBucket "arn:aws:s3:::${VEDA_PREFIX}-probe" \
  aws:RequestedRegion=us-east-1 "aws:PrincipalArn=$APPLY"
probe "role under a path (RR-03)" explicitDeny iam:CreateRole "$A:role/${VEDA_PREFIX}-x/admin" \
  aws:RequestedRegion=us-east-1 "aws:PrincipalArn=$APPLY" "iam:PermissionsBoundary=$BOUNDARY_ARN"
probe "trust change by a workload role (RR-03)" explicitDeny iam:UpdateAssumeRolePolicy "$HOST" \
  aws:RequestedRegion=us-east-1 "aws:PrincipalArn=$HOST"
probe "boundary removal" explicitDeny iam:DeleteRolePermissionsBoundary "$HOST" \
  aws:RequestedRegion=us-east-1 "aws:PrincipalArn=$APPLY"
probe "AdministratorAccess attached" explicitDeny iam:AttachRolePolicy "$HOST" \
  aws:RequestedRegion=us-east-1 "aws:PrincipalArn=$APPLY" "iam:PolicyARN=arn:aws:iam::aws:policy/AdministratorAccess"
probe "bootstrap state read (RR-01)" explicitDeny s3:GetObject "arn:aws:s3:::$(state_bucket_name "$ACCOUNT")/bootstrap/terraform.tfstate" \
  aws:RequestedRegion=ap-south-1 "aws:PrincipalArn=$APPLY"

if ((${#failures[@]})); then
  for f in "${failures[@]}"; do log "SIMULATION: $f"; done
  die "IAM does not evaluate the rendered boundary as reviewed (${#failures[@]} probe(s)); refusing"
fi
log "IAM simulation of the rendered boundary matches the review (7 probes, 1 allowed control)"
