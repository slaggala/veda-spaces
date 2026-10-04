#!/usr/bin/env bash
# Plan guard (F4, F7, review R2). Reads `terraform show -json <plan>` and refuses the plan when it:
#   - deletes or replaces any resource (a destroy is never applied by automation);
#   - creates or changes an IAM role without the Veda permissions boundary, or with a trust policy that is not
#     known at plan time;
#   - puts an IAM role, policy or instance profile under a path, or names one outside <prefix>-* (RR-03: name
#     patterns in the boundary and the bucket policy only hold at path "/");
#   - trusts a principal outside the account, anything public, or an identity provider other than the GitHub
#     OIDC provider, or uses NotAction/NotPrincipal in a trust policy; GitHub trust is accepted only on the four
#     <prefix>-gh-* roles, each only from its own protected environment (plan: staging-plan, apply: staging-infra,
#     deploy: staging, evidence: staging-evidence; RR-03/RR-07), as the single exact subject
#     repo:<owner>@<owner id>/<repo>@<repo id>:environment:<that environment> (GitHub's immutable subject, IDs from the
#     manifest), audience sts.amazonaws.com, action
#     sts:AssumeRoleWithWebIdentity only;
#   - attaches a privileged AWS managed policy (AdministratorAccess*, PowerUserAccess, IAMFullAccess,
#     AWSOrganizationsFullAccess, job-function/*), or creates IAM users, groups, access keys, login profiles,
#     SAML providers, account settings or another OIDC provider;
#   - adds a resource policy, Lambda permission, KMS grant, AMI/snapshot permission or function URL that opens a
#     resource to another account or to the public;
#   - deploys outside ap-south-1 (Mumbai only, owner decision): an AWS provider configuration whose region is not the
#     constant ap-south-1 or the root variable aws_region (provider aliases and providers inside modules included),
#     an aws_region variable other than ap-south-1, or a resource whose planned region (AWS provider v6 records it on
#     every regional resource, whichever alias, module or per-resource region argument set it) is another region or
#     unknown. Global resources (IAM) have no region;
#   - does anything but create, update, read or no-op (delete, replace, forget).
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
    -h | --help) sed -n '2,21p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

require_tools jq
[[ -f "$PLAN_JSON" ]] || die "plan JSON not found: $PLAN_JSON"
require_account_id "$ACCOUNT"
[[ "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "--repo must be owner/repo"
[[ "$REPO" == "$(manifest_get .repository)" ]] || die "--repo $REPO is not the repository the manifest approves"
SUBJECT_PREFIX="$(oidc_subject_prefix)"
# An empty or foreign file has no resource changes to refuse; it must not pass as a clean plan.
jq -e 'type == "object" and (.format_version | type) == "string"' "$PLAN_JSON" >/dev/null 2>&1 ||
  die "$PLAN_JSON is not a Terraform plan (terraform show -json output); refusing"

# {"veda-gh-plan": "staging-plan", ...}
GH_ENVS="$(for spec in $VEDA_GH_ROLE_ENVIRONMENTS; do printf '%s\n' "$spec"; done |
  jq -R --arg prefix "$PREFIX" 'split(":") | {key: "\($prefix)-gh-\(.[0])", value: .[1]}' | jq -s from_entries)"

violations="$(jq -r --arg acct "$ACCOUNT" --arg repo "$REPO" --arg subject "$SUBJECT_PREFIX" --arg prefix "$PREFIX" --arg region "$VEDA_REGION" --argjson ghenv "$GH_ENVS" '
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
      elif $s.NotAction then "\($addr): trust with NotAction"
      else ($s | principals)[]
        | if .t == "Service" then empty
          elif .t == "AWS" then (if .v != "*" and (.v | own) then empty else "\($addr): trusts \(.v) outside the account" end)
          elif .t == "Federated" and .v == github then
            (($s.Condition // {}) as $c
             | ($c.StringEquals["token.actions.githubusercontent.com:sub"] | arr) as $subs
             | ($c.StringEquals["token.actions.githubusercontent.com:aud"] | arr) as $aud
             | $ghenv[$name] as $env
             | if $env == null then "\($addr): only the bootstrap GitHub roles (\($ghenv | keys | join(", "))) may trust GitHub (R2, RR-03)"
               elif ($s.Action | arr) != ["sts:AssumeRoleWithWebIdentity"] then "\($addr): GitHub trust must allow sts:AssumeRoleWithWebIdentity only (\($s.Action | arr | join(",")))"
               elif ($c | to_entries | map(select(.key != "StringEquals") | .value | keys[]) | map(select(startswith("token.actions"))) | length) > 0
                 then "\($addr): GitHub claims must use StringEquals only"
               elif ($subs | length) == 0 then "\($addr): GitHub trust without a subject"
               elif $subs != ["\($subject):environment:\($env)"]
                 then "\($addr): \($name) must trust exactly \($subject):environment:\($env), its protected environment (got \($subs | join(",")))"
               elif $aud != ["sts.amazonaws.com"] then "\($addr): GitHub audience must be sts.amazonaws.com"
               else empty end)
          else "\($addr): trusts \(.t) \(.v)" end
      end;
  # RR-03: IAM entities at path "/" and named <prefix>-*; unknown at plan time is refused.
  def iam_name_path($addr; $kind; $after; $unknown):
    (if $unknown.path == true or (($after.path // "/") != "/") then "\($addr): IAM \($kind) under path \($after.path // "(unknown)"): only path / is allowed (RR-03)" else empty end),
    (if $unknown.name == true or (($after.name // "") | startswith($prefix + "-") | not) then "\($addr): IAM \($kind) name \($after.name // "(unknown)") is not \($prefix)-* (RR-03)" else empty end);
  def privileged: tostring | test("^arn:aws[a-z-]*:iam::aws:policy/(AdministratorAccess|PowerUserAccess$|IAMFullAccess$|AWSOrganizationsFullAccess$|job-function/)");
  def forbidden_type: IN("aws_iam_user", "aws_iam_user_policy", "aws_iam_user_policy_attachment", "aws_iam_user_group_membership",
    "aws_iam_user_login_profile", "aws_iam_user_ssh_key", "aws_iam_access_key", "aws_iam_group", "aws_iam_group_policy",
    "aws_iam_group_policy_attachment", "aws_iam_group_membership", "aws_iam_saml_provider", "aws_iam_account_password_policy",
    "aws_iam_account_alias", "aws_iam_signing_certificate", "aws_iam_virtual_mfa_device", "aws_iam_service_specific_credential");
  # Dedicated policy resources always carry an explicit policy, so an unknown one is refused. An inline policy
  # attribute (aws_kms_key, aws_sns_topic, ...) is Optional+Computed: unknown there means the AWS default, which
  # stays inside the account, so it is checked only when known.
  def dedicated: IN("aws_s3_bucket_policy", "aws_sqs_queue_policy", "aws_sns_topic_policy", "aws_ecr_repository_policy",
    "aws_cloudwatch_log_resource_policy", "aws_secretsmanager_secret_policy", "aws_ssm_resource_policy",
    "aws_lambda_layer_version_permission");
  def policy_field:
    {"aws_s3_bucket_policy": "policy", "aws_kms_key": "policy", "aws_sqs_queue_policy": "policy", "aws_sqs_queue": "policy",
     "aws_sns_topic_policy": "policy", "aws_sns_topic": "policy", "aws_ecr_repository_policy": "policy",
     "aws_cloudwatch_log_resource_policy": "policy_document", "aws_secretsmanager_secret_policy": "policy", # pragma: allowlist secret
     "aws_secretsmanager_secret": "policy", "aws_ssm_resource_policy": "policy", "aws_lambda_layer_version_permission": "policy"}[.]; # pragma: allowlist secret
  def aws_provider: ((.provider_name // "") | test("(^|/)hashicorp/aws$")) or ((.type // "") | startswith("aws_"));
  # Mumbai only: every AWS provider configuration pins the approved region, at the root, either as the constant or as
  # the validated root variable; the planned region of a resource (AWS provider v6) must be that region or absent (global).
  def region_ok: . == {"constant_value": $region} or . == {"references": ["var.aws_region"]};
  def region_findings:
    (.variables.aws_region.value // $region) as $region_var
    | ([.configuration.provider_config // {} | to_entries[] | select(.value.name == "aws")] as $pcs
     | (if ([.resource_changes[]? | select(aws_provider)] | length) > 0 and ($pcs | length) == 0
          then "plan has AWS resources but no AWS provider configuration: the region cannot be verified" else empty end),
       ($pcs[] | .key as $k | .value
        | if .module_address then "provider \($k): a module configures its own AWS provider (region must come from the root, \($region) only)"
          elif (.expressions.region | region_ok) | not then
            "provider \($k): region \((.expressions.region // {}) | .constant_value // ((.references // []) | if length > 0 then join(",") else null end) // "unset") is not \($region)"
          elif .expressions.region.references and ($region_var != $region) then
            "provider \($k): variable aws_region is \($region_var | tojson), not \($region)"
          else empty end)),
    ([.resource_changes[]? | select(aws_provider) | select((.change.actions - ["no-op", "read"]) | length > 0)
      | if .change.after_unknown.region == true then "\(.address): region not known at plan time (\($region) only)"
        elif (.change.after.region // null) != null and .change.after.region != $region
          then "\(.address): planned in \(.change.after.region), not \($region) (Mumbai only)"
        else empty end][]);

  [ region_findings ] + [ .resource_changes[]? | . as $rc | .address as $addr | (.change.after // {}) as $after | (.change.after_unknown // {}) as $unknown
    | if (.change.actions - ["create", "update", "read", "no-op"]) | length > 0 then
        "\($addr): plan \(.change.actions | join("+")) (the bootstrap never applies a destroy, replace or forget)"
      elif (.change.actions | index("create") or index("update")) | not then empty
      elif (.type | forbidden_type) then "\($addr): \(.type) is not allowed (users, groups, keys and account settings are out of scope)"
      elif .type == "aws_iam_openid_connect_provider" and $addr != "aws_iam_openid_connect_provider.github[0]" then
        "\($addr): only the bootstrap creates the GitHub OIDC provider"
      elif .type == "aws_iam_role" then
        iam_name_path($addr; "role"; $after; $unknown),
        (if $unknown.permissions_boundary == true or $after.permissions_boundary != boundary
           then "\($addr): IAM role without the \($prefix)-boundary permissions boundary" else empty end),
        (if $unknown.assume_role_policy == true then "\($addr): trust policy not known at plan time"
         else ($after.assume_role_policy | fromjson | trust_statements($addr; $after.name // "")) end),
        (($after.managed_policy_arns // []) | arr[] | select(privileged) | "\($addr): privileged managed policy \(.)")
      elif .type == "aws_iam_policy" then iam_name_path($addr; "policy"; $after; $unknown)
      elif .type == "aws_iam_instance_profile" then iam_name_path($addr; "instance profile"; $after; $unknown)
      elif .type == "aws_iam_role_policy_attachment" or .type == "aws_iam_policy_attachment" or .type == "aws_iam_role_policy_attachments_exclusive" then
        (([$after.policy_arn] + ($after.policy_arns // [])) | map(select(. != null))[] | select(privileged)
         | "\($addr): privileged managed policy \(.)")
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
log "plan guard: no destroy, everything in $VEDA_REGION, every role bounded at path /, GitHub trust only from each role's protected environment, no trust or resource policy outside account $ACCOUNT"
