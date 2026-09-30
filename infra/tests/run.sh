#!/usr/bin/env bash
# Offline regression tests for the AUT-001..003 remediation (F3, F4, F5, F7, F9, F10 and their script sides).
# Run: make -C infra test-scripts   (the policy findings F1, F2, F6, F7, F9 are in terraform/bootstrap/tests).
#
# The scripts run from a temporary copy of infra/ with stub aws, gh and terraform commands first on PATH, so no
# AWS, GitHub or Cloudflare API is reached and the working tree is never touched. The negative Terraform tests
# (prevent_destroy) use the real terraform with a mock provider.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
INFRA="$(cd "$HERE/.." && pwd)"
REAL_TF="$(command -v "${TERRAFORM:-terraform}" || true)"
FIXTURE_MANIFEST="$INFRA/terraform/bootstrap/tests/fixtures/account.json"
ACCT=111122223333

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export PATH="$HERE/stubs:$PATH"
unset GITHUB_ACTIONS GITHUB_REPOSITORY GITHUB_SHA
export AWS_REGION=ap-south-1

PASS=0
FAILED=()

# check <name> <ok|fail> <extended regex the output must contain> -- <command...>
check() {
  local name="$1" want="$2" pattern="$3" out rc
  shift 4
  out="$("$@" 2>&1)"
  rc=$?
  if { [[ "$want" == ok && $rc -eq 0 ]] || [[ "$want" == fail && $rc -ne 0 ]]; } && grep -Eq -- "$pattern" <<<"$out"; then
    PASS=$((PASS + 1))
    printf '  pass  %s\n' "$name"
  else
    FAILED+=("$name")
    printf '  FAIL  %s (exit %s, wanted %s matching /%s/)\n' "$name" "$rc" "$want" "$pattern"
    # shellcheck disable=SC2001 # prefixes every line, which ${var//} cannot anchor
    sed 's/^/        | /' <<<"$out" | tail -n 15
  fi
}

# absent <name> <extended regex> <text>: the text must NOT contain the pattern.
absent() {
  if grep -Eq -- "$2" <<<"$3"; then
    FAILED+=("$1")
    printf '  FAIL  %s (found /%s/)\n' "$1" "$2"
    grep -E -- "$2" <<<"$3" | sed 's/^/        | /' | head -n 5
  else
    PASS=$((PASS + 1))
    printf '  pass  %s\n' "$1"
  fi
}

# A fresh copy of infra/ (scripts, config) whose lib.sh resolves INFRA_DIR to the copy.
new_tree() {
  local t="$TMP/tree.$RANDOM$RANDOM"
  mkdir -p "$t/infra/terraform/bootstrap" "$t/infra/config" "$t/infra/generated"
  cp -R "$INFRA/scripts" "$t/infra/scripts"
  cp "$FIXTURE_MANIFEST" "$t/infra/config/staging-account.json"
  echo "$t"
}

# Stub answers for the approved, empty staging account.
good_account() {
  local d="$TMP/aws.$RANDOM$RANDOM"
  mkdir -p "$d"
  echo "{\"Account\":\"$ACCT\",\"Arn\":\"arn:aws:sts::$ACCT:assumed-role/OrganizationAccountAccessRole/owner\"}" >"$d/sts_get-caller-identity.json"
  echo "{\"AccountId\":\"$ACCT\",\"AccountName\":\"veda-staging\"}" >"$d/account_get-account-information.json"
  echo '{"AccountAliases":["veda-staging"]}' >"$d/iam_list-account-aliases.json"
  cat >"$d/iam_list-roles.json" <<'EOF'
{"Roles":[{"RoleName":"OrganizationAccountAccessRole","Path":"/"},
  {"RoleName":"AWSServiceRoleForSupport","Path":"/aws-service-role/support.amazonaws.com/"},
  {"RoleName":"AWSReservedSSO_Admin_0123","Path":"/aws-reserved/sso.amazonaws.com/"},
  {"RoleName":"veda-gh-apply","Path":"/"}]}
EOF
  echo '{"Users":[]}' >"$d/iam_list-users.json"
  echo "{\"Buckets\":[{\"Name\":\"veda-tfstate-$ACCT\"}]}" >"$d/s3api_list-buckets.json"
  echo '{"Reservations":[{"Instances":[{"InstanceId":"i-0veda","Tags":[{"Key":"project","Value":"veda-spaces"}]}]}]}' >"$d/ec2_describe-instances.json"
  echo '{"Functions":[{"FunctionName":"veda-canary"}]}' >"$d/lambda_list-functions.json"
  : >"$d/s3api_head-bucket.json"
  : >"$d/s3api_head-object.json"
  echo "{\"KeyMetadata\":{\"Arn\":\"arn:aws:kms:ap-south-1:$ACCT:key/k\"}}" >"$d/kms_describe-key.json"
  echo "$d"
}

# lib.sh function in a strict shell, the way the scripts call it.
lib() {
  local tree="$1"
  shift
  bash -c 'set -euo pipefail; source "$0/infra/scripts/lib.sh"; eval "$1"' "$tree" "$*"
}

echo "== F3: the account is proven to be the approved, dedicated staging account"
T="$(new_tree)"
export AWS_STUB_DIR
AWS_STUB_DIR="$(good_account)"
check "approved empty account passes" ok "account $ACCT verified" -- lib "$T" verify_account_identity $ACCT

check "account differs from the manifest" fail "not the approved staging account" -- lib "$T" verify_account_identity 444455556666

T2="$(new_tree)"
jq '.account_id = null | .account_name = null' "$FIXTURE_MANIFEST" >"$T2/infra/config/staging-account.json"
check "no approved account committed" fail "no approved staging account" -- lib "$T2" verify_account_identity $ACCT

D="$(good_account)"
echo '{"Account":"999999999999"}' >"$D/sts_get-caller-identity.json"
check "session in another account (typed ID matches manifest)" fail "AWS session is for account 999999999999" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

D="$(good_account)"
echo "{\"AccountName\":\"aurion-live\"}" >"$D/account_get-account-information.json"
check "account name differs from the manifest" fail "account name is 'aurion-live'" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

T3="$(new_tree)"
jq '.account_name = "veda-production"' "$FIXTURE_MANIFEST" >"$T3/infra/config/staging-account.json"
D="$(good_account)"
echo '{"AccountName":"veda-production"}' >"$D/account_get-account-information.json"
check "production-looking account refused even when approved" fail "looks like production or Aurion" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T3/infra/scripts/lib.sh'; verify_account_identity $ACCT"

D="$(good_account)"
echo '{"AccountAliases":["veda-prod"]}' >"$D/iam_list-account-aliases.json"
check "account alias differs from the manifest" fail "account alias is 'veda-prod'" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

D="$(good_account)"
jq '.Roles += [{"RoleName":"legacy-admin","Path":"/"}]' "$D/iam_list-roles.json" >"$D/r" && mv "$D/r" "$D/iam_list-roles.json"
check "foreign IAM role" fail "roles: legacy-admin" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

D="$(good_account)"
echo '{"Users":[{"UserName":"alice"}]}' >"$D/iam_list-users.json"
check "IAM user" fail "users: alice" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

D="$(good_account)"
echo '{"Buckets":[{"Name":"prod-data"}]}' >"$D/s3api_list-buckets.json"
check "foreign S3 bucket" fail "buckets: prod-data" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

D="$(good_account)"
echo '{"Reservations":[{"Instances":[{"InstanceId":"i-0abc","Tags":[{"Key":"project","Value":"aurion"}]}]}]}' >"$D/ec2_describe-instances.json"
check "untagged EC2 instance" fail "instances: i-0abc" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

D="$(good_account)"
echo '{"Functions":[{"FunctionName":"trader-signal"}]}' >"$D/lambda_list-functions.json"
check "foreign Lambda function" fail "lambda functions: trader-signal" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

T4="$(new_tree)"
jq '.allowed_foreign_resources.iam_roles += ["legacy-admin"]' "$FIXTURE_MANIFEST" >"$T4/infra/config/staging-account.json"
D="$(good_account)"
jq '.Roles += [{"RoleName":"legacy-admin","Path":"/"}]' "$D/iam_list-roles.json" >"$D/r" && mv "$D/r" "$D/iam_list-roles.json"
check "foreign role allowed by the reviewed manifest" ok "verified" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T4/infra/scripts/lib.sh'; verify_account_identity $ACCT"

D="$(good_account)"
echo "AccessDenied" >"$D/account_get-account-information.fail"
check "account name lookup fails closed" fail "cannot read the account name" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

D="$(good_account)"
echo "AccessDenied" >"$D/iam_list-roles.fail"
check "resource listing fails closed" fail "cannot list account resources" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

echo "== F4: lookups the plan depends on fail closed"
OIDC="arn:aws:iam::$ACCT:oidc-provider/token.actions.githubusercontent.com"
D="$(good_account)"
echo '{"Tags":[{"Key":"stack","Value":"bootstrap"},{"Key":"project","Value":"veda-spaces"}]}' >"$D/iam_list-open-id-connect-provider-tags.json"
check "OIDC provider created by the bootstrap" ok "^true$" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; oidc_provider_managed $OIDC"
echo '{"Tags":[]}' >"$D/iam_list-open-id-connect-provider-tags.json"
check "OIDC provider that predates the bootstrap" ok "^false$" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; oidc_provider_managed $OIDC"
D="$(good_account)"
echo "Throttling: Rate exceeded" >"$D/iam_list-open-id-connect-provider-tags.fail"
# The exact form discover.sh uses: the failure must stop the script, never read as "not managed".
check "OIDC tag lookup failure stops discovery" fail "refusing to guess" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; oidc_arn=$OIDC; oidc_managed=false; [[ -z \"\$oidc_arn\" ]] || oidc_managed=\"\$(oidc_provider_managed \"\$oidc_arn\")\"; echo reached-with-\$oidc_managed"

D="$(good_account)"
check "state bucket exists" ok "^exists$" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; state_bucket_status veda-tfstate-$ACCT $ACCT"
rm "$D/s3api_head-bucket.json"
echo "An error occurred (404) when calling the HeadBucket operation: Not Found" >"$D/s3api_head-bucket.fail"
check "state bucket absent (404)" ok "^absent$" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; state_bucket_status veda-tfstate-$ACCT $ACCT"
echo "An error occurred (403) when calling the HeadBucket operation: Forbidden" >"$D/s3api_head-bucket.fail"
check "F11 state bucket name owned elsewhere (403) stops the run" fail "may be taken by another account" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; s=\"\$(state_bucket_status veda-tfstate-$ACCT $ACCT)\"; echo reached-\$s"

echo "== F4 / F7 / R2: plan guard"
# plan_json <file> <resource_changes JSON array>
plan_json() { jq -n --argjson rc "$2" '{format_version: "1.2", resource_changes: $rc}' >"$1"; }
trust() { # trust <principal JSON> [condition JSON]
  jq -cn --argjson p "$1" --argjson c "${2:-null}" '{Version: "2012-10-17", Statement: [{Effect: "Allow", Action: "sts:AssumeRoleWithWebIdentity", Principal: $p} + (if $c then {Condition: $c} else {} end)]} | tojson'
}
role() { # role <address> <name> <trust JSON string> [boundary]
  jq -cn --arg a "$1" --arg n "$2" --argjson t "$3" --arg b "${4-arn:aws:iam::$ACCT:policy/veda-boundary}" \
    '{address: $a, type: "aws_iam_role", change: {actions: ["create"], after: {name: $n, assume_role_policy: $t, permissions_boundary: $b}, after_unknown: {}}}'
}
GH_PRINCIPAL="{\"Federated\":\"$OIDC\"}"
GH_OK_COND='{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com","token.actions.githubusercontent.com:sub":"repo:example-org/veda-spaces:environment:staging-infra"}}'
GH_ROLE="$(role 'aws_iam_role.github["apply"]' veda-gh-apply "$(trust "$GH_PRINCIPAL" "$GH_OK_COND")")"
guard() { "$T/infra/scripts/check-plan.sh" --plan-json "$1" --account $ACCT --repo example-org/veda-spaces; }
P="$TMP/plan"

plan_json "$P.ok" "[$GH_ROLE,
  $(role aws_iam_role.host veda-host "$(trust '{"Service":"ec2.amazonaws.com"}')"),
  {\"address\":\"aws_s3_bucket_policy.state\",\"type\":\"aws_s3_bucket_policy\",\"change\":{\"actions\":[\"create\"],\"after\":{\"policy\":$(jq -cn '{Statement:[{Effect:"Deny",Principal:"*",Action:"s3:*",Resource:"*"}]}|tojson')},\"after_unknown\":{}}},
  {\"address\":\"aws_kms_key.state\",\"type\":\"aws_kms_key\",\"change\":{\"actions\":[\"create\"],\"after\":{\"policy\":$(jq -cn --arg a "arn:aws:iam::$ACCT:root" '{Statement:[{Effect:"Allow",Principal:{AWS:$a},Action:"kms:*",Resource:"*"}]}|tojson')},\"after_unknown\":{}}},
  {\"address\":\"aws_sns_topic_policy.alarms\",\"type\":\"aws_sns_topic_policy\",\"change\":{\"actions\":[\"create\"],\"after\":{\"policy\":$(jq -cn --arg a "$ACCT" '{Statement:[{Effect:"Allow",Principal:"*",Action:"sns:Publish",Resource:"*",Condition:{StringEquals:{"aws:SourceAccount":$a}}}]}|tojson')},\"after_unknown\":{}}},
  {\"address\":\"aws_lambda_permission.events\",\"type\":\"aws_lambda_permission\",\"change\":{\"actions\":[\"create\"],\"after\":{\"principal\":\"events.amazonaws.com\"},\"after_unknown\":{}}}]"
check "clean bootstrap-shaped plan passes" ok "plan guard: no destroy" -- guard "$P.ok"

plan_json "$P.delete" '[{"address":"aws_iam_openid_connect_provider.github[0]","type":"aws_iam_openid_connect_provider","change":{"actions":["delete"],"after":null,"after_unknown":{}}}]'
check "a delete is refused" fail "aws_iam_openid_connect_provider.github\[0\]: plan delete" -- guard "$P.delete"
plan_json "$P.replace" '[{"address":"aws_s3_bucket.state","type":"aws_s3_bucket","change":{"actions":["delete","create"],"after":{},"after_unknown":{}}}]'
check "a replace is refused" fail "plan delete\+create" -- guard "$P.replace"

plan_json "$P.nob" "[$(role aws_iam_role.x veda-x "$(trust '{"Service":"ec2.amazonaws.com"}')" "")]"
check "role without the boundary" fail "without the veda-boundary" -- guard "$P.nob"
plan_json "$P.otherb" "[$(role aws_iam_role.x veda-x "$(trust '{"Service":"ec2.amazonaws.com"}')" "arn:aws:iam::$ACCT:policy/veda-open")]"
check "role with another boundary" fail "without the veda-boundary" -- guard "$P.otherb"
plan_json "$P.unknown" '[{"address":"aws_iam_role.x","type":"aws_iam_role","change":{"actions":["create"],"after":{"name":"veda-x","permissions_boundary":"arn:aws:iam::111122223333:policy/veda-boundary"},"after_unknown":{"assume_role_policy":true}}}]'
check "trust policy unknown at plan time" fail "not known at plan time" -- guard "$P.unknown"

plan_json "$P.ext" "[$(role aws_iam_role.x veda-x "$(trust '{"AWS":"arn:aws:iam::999999999999:root"}')")]"
check "F7 role trusting another account" fail "trusts arn:aws:iam::999999999999:root outside the account" -- guard "$P.ext"
plan_json "$P.star" "[$(role aws_iam_role.x veda-x "$(trust '{"AWS":"*"}')")]"
check "F7 role trusting everyone" fail "trusts \* outside the account" -- guard "$P.star"
plan_json "$P.saml" "[$(role aws_iam_role.x veda-x "$(trust "{\"Federated\":\"arn:aws:iam::$ACCT:saml-provider/idp\"}")")]"
check "role trusting another identity provider" fail "trusts Federated" -- guard "$P.saml"

plan_json "$P.r2" "[$(role aws_iam_role.host veda-host "$(trust "$GH_PRINCIPAL" "$GH_OK_COND")")]"
check "R2 non-veda-gh role trusting GitHub" fail "only veda-gh-\* roles may trust GitHub" -- guard "$P.r2"
plan_json "$P.like" "[$(role 'aws_iam_role.github["plan"]' veda-gh-plan "$(trust "$GH_PRINCIPAL" '{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com"},"StringLike":{"token.actions.githubusercontent.com:sub":"repo:example-org/veda-spaces:*"}}')")]"
check "R2 wildcard GitHub subject" fail "must use StringEquals only" -- guard "$P.like"
plan_json "$P.pr" "[$(role 'aws_iam_role.github["plan"]' veda-gh-plan "$(trust "$GH_PRINCIPAL" '{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com","token.actions.githubusercontent.com:sub":"repo:example-org/veda-spaces:pull_request"}}')")]"
check "R2 pull_request subject" fail "is not repo:example-org/veda-spaces:environment" -- guard "$P.pr"
plan_json "$P.repo" "[$(role 'aws_iam_role.github["plan"]' veda-gh-plan "$(trust "$GH_PRINCIPAL" '{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com","token.actions.githubusercontent.com:sub":"repo:attacker/veda-spaces:environment:staging-plan"}}')")]"
check "R2 another repository" fail "is not repo:example-org/veda-spaces" -- guard "$P.repo"
plan_json "$P.aud" "[$(role 'aws_iam_role.github["plan"]' veda-gh-plan "$(trust "$GH_PRINCIPAL" '{"StringEquals":{"token.actions.githubusercontent.com:sub":"repo:example-org/veda-spaces:environment:staging-plan"}}')")]"
check "R2 GitHub trust without audience" fail "audience must be sts.amazonaws.com" -- guard "$P.aud"

res() { # res <type> <address> <after JSON> [after_unknown JSON]
  local unknown="${4:-}"
  [[ -n "$unknown" ]] || unknown='{}'
  jq -cn --arg t "$1" --arg a "$2" --argjson after "$3" --argjson u "$unknown" \
    '{address: $a, type: $t, change: {actions: ["create"], after: $after, after_unknown: $u}}'
}
policy() { jq -cn --argjson s "$1" '{Version: "2012-10-17", Statement: $s} | tojson'; }
plan_json "$P.pub" "[$(res aws_s3_bucket_policy aws_s3_bucket_policy.a "{\"policy\":$(policy '[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"*"}]')}")]"
check "F7 public bucket policy" fail "Allow to \* without an account condition" -- guard "$P.pub"
plan_json "$P.xacct" "[$(res aws_kms_key aws_kms_key.data "{\"policy\":$(policy '[{"Effect":"Allow","Principal":{"AWS":"arn:aws:iam::999999999999:root"},"Action":"kms:Decrypt","Resource":"*"}]')}")]"
check "F7 key policy for another account" fail "Allow to another account \(arn:aws:iam::999999999999:root\)" -- guard "$P.xacct"
plan_json "$P.sqs" "[$(res aws_sqs_queue_policy aws_sqs_queue_policy.q "{\"policy\":\"\"}" '{"policy":true}')]"
check "F7 resource policy unknown at plan time" fail "policy not known at plan time" -- guard "$P.sqs"
plan_json "$P.topic" "[$(res aws_sns_topic aws_sns_topic.alarms '{"name":"veda-stg-alarms"}' '{"policy":true}')]"
check "default (computed) topic policy is not a finding" ok "plan guard: no destroy" -- guard "$P.topic"
plan_json "$P.lp" "[$(res aws_lambda_permission aws_lambda_permission.x '{"principal":"999999999999"}')]"
check "F7 Lambda permission for another account" fail "Lambda permission for 999999999999" -- guard "$P.lp"
plan_json "$P.url" "[$(res aws_lambda_function_url aws_lambda_function_url.x '{"authorization_type":"NONE"}')]"
check "F7 public function URL" fail "public function URL" -- guard "$P.url"
plan_json "$P.ami" "[$(res aws_ami_launch_permission aws_ami_launch_permission.x '{"account_id":"999999999999"}')]"
check "F7 AMI shared with another account" fail "shares with 999999999999" -- guard "$P.ami"
plan_json "$P.snap" "[$(res aws_snapshot_create_volume_permission aws_snapshot_create_volume_permission.x '{"account_id":"999999999999"}')]"
check "F7 snapshot shared with another account" fail "shares with 999999999999" -- guard "$P.snap"
plan_json "$P.grant" "[$(res aws_kms_grant aws_kms_grant.x '{"grantee_principal":"arn:aws:iam::999999999999:role/r"}')]"
check "F7 KMS grant to another account" fail "KMS grant to arn:aws:iam::999999999999:role/r" -- guard "$P.grant"

echo "== F4 / F5: bootstrap.sh applies only a verified, reviewed plan"
T="$(new_tree)"
BS="$T/infra/scripts/bootstrap.sh"
check "--yes without a reviewed plan is refused" fail "needs a reviewed plan" -- env AWS_STUB_DIR="$(good_account)" "$BS" --mode apply --expected-account-id $ACCT --yes
check "F5 --skip-guardrails is gone" fail "was removed: set manage_account_guardrails" -- "$BS" --mode apply --expected-account-id $ACCT --skip-guardrails
check "--plan-file with --mode plan is refused" fail "are for --mode apply" -- "$BS" --mode plan --expected-account-id $ACCT --plan-file x --plan-meta y

# reviewed <dir> <meta overrides (jq)>: a plan file and matching metadata, as a plan run uploads them.
reviewed() {
  mkdir -p "$1"
  echo "reviewed plan bytes" >"$1/bootstrap.tfplan"
  jq -n --arg sum "$(shasum -a 256 "$1/bootstrap.tfplan" | awk '{print $1}')" --arg acct $ACCT \
    '{mode: "plan", commit: "c0ffee", dirty: false, account_id: $acct, repository: "example-org/veda-spaces",
      plan_sha256: $sum, state_exists: true, created_at: "2026-09-30T00:00:00Z", run_id: "1"}' |
    jq "$2" >"$1/bootstrap-plan.meta.json"
}
tf_stub() { # tf_stub <plan.json source>
  local d="$TMP/tf.$RANDOM$RANDOM"
  mkdir -p "$d"
  cp "$1" "$d/plan.json"
  echo '{"account_id":{"value":"111122223333"},"region":{"value":"ap-south-1"}}' >"$d/outputs.json"
  echo "$d"
}
apply_reviewed() { # apply_reviewed <reviewed dir> <tf stub dir> <aws stub dir>
  env GITHUB_SHA=c0ffee TF_STUB_DIR="$2" AWS_STUB_DIR="$3" \
    "$BS" --mode apply --expected-account-id $ACCT --plan-file "$1/bootstrap.tfplan" --plan-meta "$1/bootstrap-plan.meta.json" --yes
}

R="$TMP/rev.ok" && reviewed "$R" '.'
TFD="$(tf_stub "$P.ok")"
check "reviewed plan is applied" ok "reviewed plan verified" -- apply_reviewed "$R" "$TFD" "$(good_account)"
check "  ... exactly that plan file" ok "apply -input=false -lock-timeout=5m $R/bootstrap.tfplan" -- cat "$TFD/calls.log"

R="$TMP/rev.sum" && reviewed "$R" '.'
echo "tampered" >>"$R/bootstrap.tfplan"
TFD="$(tf_stub "$P.ok")"
check "tampered plan file" fail "checksum mismatch" -- apply_reviewed "$R" "$TFD" "$(good_account)"
absent "  ... refused before terraform runs" "." "$(cat "$TFD/calls.log" 2>/dev/null || true)"

R="$TMP/rev.commit" && reviewed "$R" '.commit = "badc0de"'
check "plan from another commit" fail "made from commit badc0de" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)"
R="$TMP/rev.acct" && reviewed "$R" '.account_id = "444455556666"'
check "plan for another account" fail "made for account 444455556666" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)"
R="$TMP/rev.dirty" && reviewed "$R" '.dirty = true'
check "plan from uncommitted changes" fail "uncommitted infra changes" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)"
R="$TMP/rev.mode" && reviewed "$R" '.mode = "apply"'
check "metadata not from a plan run" fail "not from a plan run" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)"
R="$TMP/rev.state" && reviewed "$R" '.state_exists = false'
check "state bucket changed since the plan" fail "appeared or disappeared" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)"

R="$TMP/rev.del" && reviewed "$R" '.'
TFD="$(tf_stub "$P.delete")"
check "reviewed plan with a delete is refused" fail "plan guard refused" -- apply_reviewed "$R" "$TFD" "$(good_account)"
absent "  ... and never applied" "^apply " "$(cat "$TFD/calls.log")"

D="$(good_account)"
echo '{"Buckets":[{"Name":"aurion-trades"}]}' >"$D/s3api_list-buckets.json"
R="$TMP/rev.foreign" && reviewed "$R" '.'
check "reviewed plan into a non-empty account is refused" fail "buckets: aurion-trades" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$D"

T5="$(new_tree)"
jq '.account_id = null' "$FIXTURE_MANIFEST" >"$T5/infra/config/staging-account.json"
R="$TMP/rev.unapproved" && reviewed "$R" '.'
check "reviewed plan for an unapproved account is refused" fail "no approved staging account" -- env GITHUB_SHA=c0ffee TF_STUB_DIR="$(tf_stub "$P.ok")" AWS_STUB_DIR="$(good_account)" \
  "$T5/infra/scripts/bootstrap.sh" --mode apply --expected-account-id $ACCT --plan-file "$R/bootstrap.tfplan" --plan-meta "$R/bootstrap-plan.meta.json" --yes

echo "== F5: guardrails and the OIDC provider cannot be destroyed by a changed input"
BOOT="$INFRA/terraform/bootstrap"
n_res="$(grep -c '^resource ' "$BOOT/guardrails.tf")"
n_pd="$(grep -c 'prevent_destroy = true' "$BOOT/guardrails.tf")"
check "every guardrail resource has prevent_destroy ($n_pd/$n_res)" ok "^same$" -- bash -c "[[ $n_res -gt 0 && $n_res -eq $n_pd ]] && echo same"
if [[ -n "$REAL_TF" ]]; then
  (cd "$BOOT" && "$REAL_TF" init -backend=false -input=false >/dev/null 2>&1)
  negative() { (cd "$BOOT" && "$REAL_TF" test -no-color -test-directory=tests/negative -filter="tests/negative/$1.tftest.hcl"); }
  check "turning guardrails off fails the plan instead of destroying them" fail "Instance cannot be destroyed" -- negative guardrails_destroy
  out="$(negative guardrails_destroy 2>&1)"
  check "  ... after the guardrails were created" ok 'run "create_with_guardrails"\.\.\. pass' -- printf '%s\n' "$out"
  for r in aws_s3_account_public_access_block aws_ebs_encryption_by_default aws_ebs_snapshot_block_public_access \
    aws_ec2_image_block_public_access aws_ec2_instance_metadata_defaults aws_accessanalyzer_analyzer; do
    check "  ... $r protected" ok "Resource $r\.[a-z]+\[0\] has" -- printf '%s\n' "$out"
  done
  check "F4 passing our OIDC provider as existing fails the plan" fail "aws_iam_openid_connect_provider.github\[0\] has" -- negative oidc_destroy
  out="$(negative oidc_destroy 2>&1)"
  check "  ... after the provider was created" ok 'run "create_oidc_provider"\.\.\. pass' -- printf '%s\n' "$out"
else
  FAILED+=("negative Terraform tests (terraform not found)")
fi

echo "== F9 / F10: GitHub environments, main protection, variables"
T="$(new_tree)"
GS="$T/infra/scripts/github-setup.sh"
G="$TMP/gh.dry" && mkdir -p "$G"
echo '{"login":"owner"}' >"$G/user.json"
echo '{"id":1001}' >"$G/users_owner.json"
out_env="$(GH_STUB_DIR="$G" "$GS" --repo example-org/veda-spaces 2>&1)"
for env in bootstrap staging-plan staging-infra staging staging-evidence; do
  check "F10 $env: admins cannot bypass" ok "environments/$env <<< \{[^}]*\"can_admins_bypass\":false" -- printf '%s\n' "$out_env"
done
check "F9 staging-plan requires a reviewer" ok 'environments/staging-plan <<< .*"reviewers":\[\{"type":"User","id":1001\}\]' -- printf '%s\n' "$out_env"
check "F10 main protection enforced for admins, PR required, no force push" ok 'branches/main/protection <<< .*"enforce_admins":true.*"required_pull_request_reviews":\{"required_approving_review_count":0.*"allow_force_pushes":false,"allow_deletions":false' -- printf '%s\n' "$out_env"
absent "F10 dry run changes nothing" "-X (PUT|POST)" "$(cat "$G/calls.log")"

echo '{"account_id":"111122223333","region":"ap-south-1","state_bucket":"veda-tfstate-111122223333","state_kms_key_arn":"arn:k","github_role_arns":{"plan":"arn:p","apply":"arn:a","deploy":"arn:d","evidence":"arn:e"}}' >"$TMP/outputs.json"
out_var="$(GH_STUB_DIR="$G" "$GS" --repo example-org/veda-spaces --outputs "$TMP/outputs.json" --variables-only 2>&1)"
check "F10 role ARNs are repository variables (Variables: write only)" ok "variable set AWS_ROLE_ARN_APPLY --repo example-org/veda-spaces --body arn:a" -- printf '%s\n' "$out_var"
absent "F10 no environment-scoped variable" "--env" "$out_var"

# --verify against a compliant repository, then one drift at a time.
V="$TMP/gh.verify" && mkdir -p "$V"
for env in bootstrap staging-plan staging-infra staging staging-evidence; do
  reviewers='[{"type":"required_reviewers","reviewers":[{"type":"User","reviewer":{"id":1001}}]}]'
  [[ "$env" == staging-evidence ]] && reviewers='[]'
  policy='{"protected_branches":false,"custom_branch_policies":true}'
  [[ "$env" == staging-plan ]] && policy=null
  jq -n --argjson r "$reviewers" --argjson p "$policy" '{can_admins_bypass: false, protection_rules: $r, deployment_branch_policy: $p}' \
    >"$V/repos_example-org_veda-spaces_environments_$env.json"
  echo '{"branch_policies":[{"name":"main","type":"branch"}]}' >"$V/repos_example-org_veda-spaces_environments_${env}_deployment-branch-policies.json"
done
echo '{"enforce_admins":{"enabled":true},"required_pull_request_reviews":{"required_approving_review_count":0},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}' \
  >"$V/repos_example-org_veda-spaces_branches_main_protection.json"
verify() { GH_STUB_DIR="$1" "$GS" --repo example-org/veda-spaces --verify; }
check "F10 compliant repository verifies" ok "match the bootstrap rules" -- verify "$V"
drift() { # drift <name> <file suffix> <jq>
  local d="$TMP/gh.$RANDOM$RANDOM"
  cp -R "$V" "$d"
  jq "$3" "$d/repos_example-org_veda-spaces_$2.json" >"$d/x" && mv "$d/x" "$d/repos_example-org_veda-spaces_$2.json"
  echo "$d"
}
check "F10 admin bypass detected" fail "staging-infra: admins can bypass" -- verify "$(drift a environments_staging-infra '.can_admins_bypass = true')"
check "F9 staging-plan without reviewers detected" fail "staging-plan: no required reviewers" -- verify "$(drift b environments_staging-plan '.protection_rules = []')"
check "F10 bootstrap open to any branch detected" fail "bootstrap: not restricted to main" -- verify "$(drift c environments_bootstrap '.deployment_branch_policy = null')"
check "F10 extra deployment branch detected" fail "staging: deployment branches are 'branch:feature/x,branch:main'" -- verify "$(drift d environments_staging_deployment-branch-policies '.branch_policies += [{"name":"feature/x","type":"branch"}]')"
check "F10 force pushes on main detected" fail "main: force pushes allowed" -- verify "$(drift e branches_main_protection '.allow_force_pushes.enabled = true')"
check "F10 protection not enforced for admins detected" fail "main: protection not enforced for admins" -- verify "$(drift f branches_main_protection '.enforce_admins.enabled = false')"
U="$(drift g branches_main_protection '.')" && rm "$U/repos_example-org_veda-spaces_branches_main_protection.json"
check "F10 unprotected main detected" fail "main: branch not protected" -- verify "$U"

echo "== F4 / F10: 00-bootstrap workflow"
WF="$INFRA/../.github/workflows/00-bootstrap.yml"
WFT="$(cat "$WF")"
check "apply passes the reviewed plan file" ok "--plan-file infra/generated/reviewed/bootstrap.tfplan" -- printf '%s\n' "$WFT"
check "  ... and its metadata, then --yes" ok "--plan-meta infra/generated/reviewed/bootstrap-plan.meta.json --yes" -- printf '%s\n' "$WFT"
absent "  ... never --yes on the same line as --mode apply" "--mode apply.*--yes" "$WFT"
# shellcheck disable=SC2016 # literal $MODE / $sha in the workflow text
absent "  ... no mode passed through unchecked" '--mode "\$MODE"' "$WFT"
# shellcheck disable=SC2016
check "reviewed plan must be this commit's successful plan run on main" ok 'headSha == \$sha' -- cat "$WF"
check "  ... of this workflow in plan mode" ok 'displayTitle == "00-bootstrap \(plan\)"' -- cat "$WF"
check "long-lived keys refused (ASIA prefix)" ok 'AWS_ACCESS_KEY_ID" == ASIA\*' -- cat "$WF"
check "approved account checked against the manifest" ok "infra/config/staging-account.json" -- grep -F "staging-account.json" "$WF"
check "runs only from protected main" ok "branches/main\" --jq .protected" -- cat "$WF"
check "GITHUB_TOKEN limited to contents and actions read" ok "^  contents: read$" -- cat "$WF"
absent "  ... no write permission" "^ +[a-z-]+: write" "$WFT"

echo "== F8: documentation states the apply-role exception"
RB="$INFRA/../docs/operations/staging-bootstrap.md"
absent "runbook does not claim every role is denied application data" "Applies to every role:" "$(cat "$RB")"
check "runbook names the apply role as able to reach data through the host" ok "veda-gh-apply. carries the same" -- cat "$RB"
check "  ... and says how" ok "reach that data through the host role" -- cat "$RB"

echo
echo "$PASS passed, ${#FAILED[@]} failed"
if ((${#FAILED[@]})); then
  printf '  failed: %s\n' "${FAILED[@]}"
  exit 1
fi
