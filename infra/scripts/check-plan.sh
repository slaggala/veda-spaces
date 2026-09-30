#!/usr/bin/env bash
# Plan guard (F4, F7, review R2). Reads `terraform show -json <plan>` and refuses the plan when it:
#   - deletes or replaces any resource (a destroy is never applied by automation);
#   - creates or changes an IAM role without the Veda permissions boundary, or with a trust policy that is not
#     known at plan time;
#   - trusts a principal outside the account, anything public, or an identity provider other than the GitHub
#     OIDC provider; GitHub trust is accepted only on <prefix>-gh-* roles, only as an exact
#     repo:<owner>/<repo>:environment:<name> subject with audience sts.amazonaws.com;
#   - adds a resource policy, Lambda permission, KMS grant, AMI/snapshot permission or function URL that opens a
#     resource to another account or to the public.
# Offline and read-only: it only reads the JSON file. Used by bootstrap.sh; later stacks reuse it (AUT-301).
#
#   infra/scripts/check-plan.sh --plan-json plan.json --account 123456789012 --repo owner/repo [--prefix veda]
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

PLAN_JSON=""
ACCOUNT=""
REPO=""
PREFIX="$VEDA_PREFIX"
while (($#)); do
  case "$1" in
    --plan-json) PLAN_JSON="${2:-}"; shift 2 ;;
    --account) ACCOUNT="${2:-}"; shift 2 ;;
    --repo) REPO="${2:-}"; shift 2 ;;
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,15p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

require_tools jq
[[ -f "$PLAN_JSON" ]] || die "plan JSON not found: $PLAN_JSON"
require_account_id "$ACCOUNT"
[[ "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "--repo must be owner/repo"

violations="$(jq -r --arg acct "$ACCOUNT" --arg repo "$REPO" --arg prefix "$PREFIX" '
  def arr: if type == "array" then . elif . == null then [] else [.] end;
  def esc: gsub("(?<c>[.+*?()\\[\\]{}|^$\\\\])"; "\\\(.c)");
  def own: tostring | (. == $acct) or test("^arn:aws[a-z-]*:(iam|sts)::" + $acct + ":");
  def boundary: "arn:aws:iam::" + $acct + ":policy/" + $prefix + "-boundary";
  def github: "arn:aws:iam::" + $acct + ":oidc-provider/token.actions.githubusercontent.com";
  def principals:
    if .Principal == "*" then [{t: "AWS", v: "*"}]
    else (.Principal // {}) | to_entries | map(.key as $k | .value | arr | map({t: $k, v: .})) | add // []
    end;
  def names_account: (.Condition // {}) | tostring | contains($acct);
  # Allow statements that admit someone outside the account ("*" is accepted only when a condition names it).
  def open_statements($addr):
    (.Statement | arr)[] | select(.Effect == "Allow") as $s
    | if $s.NotPrincipal then "\($addr): Allow with NotPrincipal"
      else ($s | principals)[]
        | if .t == "Service" then empty
          elif .v == "*" then (if ($s | names_account) then empty else "\($addr): Allow to * without an account condition" end)
          elif .t == "AWS" then (if (.v | own) then empty else "\($addr): Allow to another account (\(.v))" end)
          else "\($addr): Allow to \(.t) principal \(.v)" end
      end;
  def trust_statements($addr; $name):
    (.Statement | arr)[] | select(.Effect == "Allow") as $s
    | if $s.NotPrincipal then "\($addr): trust with NotPrincipal"
      else ($s | principals)[]
        | if .t == "Service" then empty
          elif .t == "AWS" then (if .v != "*" and (.v | own) then empty else "\($addr): trusts \(.v) outside the account" end)
          elif .t == "Federated" and .v == github then
            (($s.Condition // {}) as $c
             | ($c.StringEquals["token.actions.githubusercontent.com:sub"] | arr) as $subs
             | ($c.StringEquals["token.actions.githubusercontent.com:aud"] | arr) as $aud
             | if ($name | startswith($prefix + "-gh-") | not) then "\($addr): only \($prefix)-gh-* roles may trust GitHub (R2)"
               elif ($c | to_entries | map(select(.key != "StringEquals") | .value | keys[]) | map(select(startswith("token.actions"))) | length) > 0
                 then "\($addr): GitHub claims must use StringEquals only"
               elif ($subs | length) == 0 then "\($addr): GitHub trust without a subject"
               elif ($subs | map(test("^repo:" + ($repo | esc) + ":environment:[A-Za-z0-9_.-]+$")) | all | not)
                 then "\($addr): GitHub subject is not repo:\($repo):environment:<name> (\($subs | join(",")))"
               elif $aud != ["sts.amazonaws.com"] then "\($addr): GitHub audience must be sts.amazonaws.com"
               else empty end)
          else "\($addr): trusts \(.t) \(.v)" end
      end;
  # Dedicated policy resources always carry an explicit policy, so an unknown one is refused. An inline policy
  # attribute (aws_kms_key, aws_sns_topic, ...) is Optional+Computed: unknown there means the AWS default, which
  # stays inside the account, so it is checked only when known.
  def dedicated: IN("aws_s3_bucket_policy", "aws_sqs_queue_policy", "aws_sns_topic_policy", "aws_ecr_repository_policy",
    "aws_cloudwatch_log_resource_policy", "aws_secretsmanager_secret_policy", "aws_ssm_resource_policy",
    "aws_lambda_layer_version_permission");
  def policy_field:
    {"aws_s3_bucket_policy": "policy", "aws_kms_key": "policy", "aws_sqs_queue_policy": "policy", "aws_sqs_queue": "policy",
     "aws_sns_topic_policy": "policy", "aws_sns_topic": "policy", "aws_ecr_repository_policy": "policy",
     "aws_cloudwatch_log_resource_policy": "policy_document", "aws_secretsmanager_secret_policy": "policy",
     "aws_secretsmanager_secret": "policy", "aws_ssm_resource_policy": "policy", "aws_lambda_layer_version_permission": "policy"}[.];

  [ .resource_changes[]? | . as $rc | .address as $addr | (.change.after // {}) as $after | (.change.after_unknown // {}) as $unknown
    | if (.change.actions | index("delete")) then
        "\($addr): plan \(.change.actions | join("+")) (the bootstrap never applies a destroy or replace)"
      elif (.change.actions | index("create") or index("update")) | not then empty
      elif .type == "aws_iam_role" then
        (if $unknown.permissions_boundary == true or $after.permissions_boundary != boundary
           then "\($addr): IAM role without the \($prefix)-boundary permissions boundary" else empty end),
        (if $unknown.assume_role_policy == true then "\($addr): trust policy not known at plan time"
         else ($after.assume_role_policy | fromjson | trust_statements($addr; $after.name // "")) end)
      elif .type == "aws_lambda_permission" then
        (if ($after.principal | tostring | test("\\.amazonaws\\.com$")) or ($after.principal | own) then empty
         else "\($addr): Lambda permission for \($after.principal)" end)
      elif .type == "aws_lambda_function_url" then
        (if $after.authorization_type == "NONE" then "\($addr): public function URL (authorization NONE)" else empty end)
      elif .type == "aws_ami_launch_permission" or .type == "aws_snapshot_create_volume_permission" then
        (if ($after.account_id // "") == $acct then empty else "\($addr): shares with \($after.account_id // $after.group // "?")" end)
      elif .type == "aws_kms_grant" then
        (if ($after.grantee_principal | tostring | own) then empty else "\($addr): KMS grant to \($after.grantee_principal)" end)
      elif (.type | policy_field) != null then
        (.type | policy_field) as $f
        | if $unknown[$f] == true then (if (.type | dedicated) then "\($addr): \($f) not known at plan time" else empty end)
          elif ($after[$f] // "") == "" then empty
          else ($after[$f] | fromjson | open_statements($addr)) end
      else empty end
  ] | .[]' "$PLAN_JSON")" || die "cannot read $PLAN_JSON as a Terraform plan"

if [[ -n "$violations" ]]; then
  printf '%s\n' "$violations" | while IFS= read -r v; do log "REFUSED: $v"; done
  die "plan guard refused the plan ($(printf '%s\n' "$violations" | wc -l | tr -d ' ') finding(s))"
fi
log "plan guard: no destroy, every role bounded, no trust or resource policy outside account $ACCOUNT"
