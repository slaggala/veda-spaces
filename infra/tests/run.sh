#!/usr/bin/env bash
# Offline regression tests for the AUT-001..003 remediation (F3, F4, F5, F7, F9, F10 and their script sides) and
# the final-certification findings (RR-01, RR-02, RR-03, RR-05, RR-07).
# Run: make -C infra test-scripts   (the policy findings F1, F2, F6, F7, F9 and the policy side of RR-01..RR-03 are
# in terraform/bootstrap/tests).
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
KEY="arn:aws:kms:ap-south-1:$ACCT:key/00000000-0000-0000-0000-000000000000"
# Reviewed policies as Terraform renders them, and the same policies as AWS stores them.
REVIEWED_BUCKET_POLICY='{"Version":"2012-10-17","Statement":[{"Sid":"DenyBootstrapStateExceptOwner","Effect":"Deny","Principal":"*","Action":"s3:*","Resource":"arn:aws:s3:::veda-tfstate-111122223333/bootstrap/*","Condition":{"ArnNotEquals":{"aws:PrincipalArn":["arn:aws:iam::111122223333:root","arn:aws:iam::111122223333:role/OrganizationAccountAccessRole"]}}}]}'
LIVE_BUCKET_POLICY='{"Version":"2012-10-17","Statement":[{"Sid":"DenyBootstrapStateExceptOwner","Effect":"Deny","Principal":{"AWS":"*"},"Action":"s3:*","Resource":"arn:aws:s3:::veda-tfstate-111122223333/bootstrap/*","Condition":{"ArnNotEquals":{"aws:PrincipalArn":["arn:aws:iam::111122223333:role/OrganizationAccountAccessRole","arn:aws:iam::111122223333:root"]}}}]}'
REVIEWED_KEY_POLICY='{"Version":"2012-10-17","Statement":[{"Sid":"DenyBootstrapStateExceptOwner","Effect":"Deny","Principal":"*","Action":["kms:Encrypt","kms:Decrypt"],"Resource":"*","Condition":{"StringLike":{"kms:EncryptionContext:aws:s3:arn":["arn:aws:s3:::veda-tfstate-111122223333/bootstrap/*"]}}}]}'
LIVE_KEY_POLICY='{"Version":"2012-10-17","Statement":[{"Sid":"DenyBootstrapStateExceptOwner","Effect":"Deny","Principal":{"AWS":"*"},"Action":["kms:Decrypt","kms:Encrypt"],"Resource":"*","Condition":{"StringLike":{"kms:EncryptionContext:aws:s3:arn":"arn:aws:s3:::veda-tfstate-111122223333/bootstrap/*"}}}]}'

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
  echo '{"OpenIDConnectProviderList":[]}' >"$d/iam_list-open-id-connect-providers.json"
  echo '{"SAMLProviderList":[]}' >"$d/iam_list-saml-providers.json"
  echo "{\"Buckets\":[{\"Name\":\"veda-tfstate-$ACCT\"}]}" >"$d/s3api_list-buckets.json"
  # PB-06: the session is region-guarded (a read in us-east-1 is denied by its session policy).
  echo "An error occurred (UnauthorizedOperation) when calling the DescribeAvailabilityZones operation: explicit deny in a session policy" \
    >"$d/ec2_describe-availability-zones@us-east-1.fail"
  # Owner decision: a member account of the approved organization (fixture: o-exampleorg01, management 999988887777).
  echo '{"Organization":{"Id":"o-exampleorg01","MasterAccountId":"999988887777","FeatureSet":"ALL"}}' \
    >"$d/organizations_describe-organization.json"
  # PB-09: the owner role (fixture manifest), one-hour sessions, trusted only inside the account.
  jq -n --arg acct "$ACCT" '{Role: {RoleName: "OrganizationAccountAccessRole", Arn: "arn:aws:iam::\($acct):role/OrganizationAccountAccessRole",
    MaxSessionDuration: 3600, AssumeRolePolicyDocument: {Version: "2012-10-17", Statement: [{Effect: "Allow",
    Principal: {AWS: "arn:aws:iam::\($acct):root"}, Action: "sts:AssumeRole"}]}}}' >"$d/iam_get-role.json"
  # N-03: every enabled region is inventoried; only ap-south-1 holds (Veda) resources.
  echo '{"Regions":[{"RegionName":"ap-south-1"},{"RegionName":"us-east-1"},{"RegionName":"eu-west-1"}]}' >"$d/ec2_describe-regions.json"
  echo '{"Reservations":[]}' >"$d/ec2_describe-instances.json"
  echo '{"Reservations":[{"Instances":[{"InstanceId":"i-0veda","Tags":[{"Key":"project","Value":"veda-spaces"}]}]}]}' >"$d/ec2_describe-instances@ap-south-1.json"
  echo '{"Vpcs":[]}' >"$d/ec2_describe-vpcs.json"
  echo '{"Functions":[]}' >"$d/lambda_list-functions.json"
  echo '{"Functions":[{"FunctionName":"veda-canary"}]}' >"$d/lambda_list-functions@ap-south-1.json"
  echo '{"DBInstances":[]}' >"$d/rds_describe-db-instances.json"
  echo '{"clusterArns":[]}' >"$d/ecs_list-clusters.json"
  echo '{"SecretList":[]}' >"$d/secretsmanager_list-secrets.json"
  echo '{"Keys":[]}' >"$d/kms_list-keys.json"
  echo '{"Aliases":[]}' >"$d/kms_list-aliases.json"
  echo '{"Keys":[{"KeyId":"k1"}]}' >"$d/kms_list-keys@ap-south-1.json"
  echo '{"Aliases":[{"AliasName":"alias/veda-tfstate","TargetKeyId":"k1"},{"AliasName":"alias/aws/s3","TargetKeyId":"k2"}]}' >"$d/kms_list-aliases@ap-south-1.json"
  # PB-10: IAM's simulation of the rendered boundary, as IAM answers it: only the control probe is allowed.
  cat >"$d/iam_simulate-custom-policy.cmd" <<'EOS'
#!/usr/bin/env bash
decision=explicitDeny
[[ " $* " == *" --action-names ec2:DescribeInstances "* ]] && decision=allowed
[[ -f "$AWS_STUB_DIR/simulate.allow" ]] && grep -qxF "$(sed -E 's/.*--action-names ([^ ]+).*/\1/' <<<"$*")" "$AWS_STUB_DIR/simulate.allow" && decision=allowed
[[ -f "$AWS_STUB_DIR/simulate.denyall" ]] && decision=explicitDeny
printf '{"EvaluationResults":[{"EvalDecision":"%s"}]}\n' "$decision"
EOS
  chmod +x "$d/iam_simulate-custom-policy.cmd"
  : >"$d/s3api_head-bucket.json"
  : >"$d/s3api_head-object.json"
  echo "{\"KeyMetadata\":{\"Arn\":\"$KEY\",\"KeyState\":\"Enabled\",\"KeyManager\":\"CUSTOMER\"}}" >"$d/kms_describe-key.json"
  # Live state protections, as AWS returns them (scalars for one-element arrays, {"AWS":"*"}): equal to the
  # reviewed policies in the terraform stub outputs once normalised.
  echo "{\"ServerSideEncryptionConfiguration\":{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"aws:kms\",\"KMSMasterKeyID\":\"$KEY\"},\"BucketKeyEnabled\":false}]}}" >"$d/s3api_get-bucket-encryption.json"
  jq -n --arg p "$LIVE_BUCKET_POLICY" '{Policy: $p}' >"$d/s3api_get-bucket-policy.json"
  jq -n --arg p "$LIVE_KEY_POLICY" '{Policy: $p}' >"$d/kms_get-key-policy.json"
  echo '{"KeyRotationEnabled":true}' >"$d/kms_get-key-rotation-status.json"
  echo "$d"
}

# GitHub answers for example-org/veda-spaces with every environment protected and main protected (RR-07).
gh_compliant() {
  local d="$TMP/gh.ok.$RANDOM$RANDOM" env reviewers policy
  mkdir -p "$d"
  for env in bootstrap staging-plan staging-infra staging staging-evidence; do
    reviewers='[{"type":"required_reviewers","reviewers":[{"type":"User","reviewer":{"id":1001}}]}]'
    [[ "$env" == staging-evidence ]] && reviewers='[]'
    policy='{"protected_branches":false,"custom_branch_policies":true}'
    [[ "$env" == staging-plan ]] && policy=null
    jq -n --argjson r "$reviewers" --argjson p "$policy" '{can_admins_bypass: false, protection_rules: $r, deployment_branch_policy: $p}' \
      >"$d/repos_example-org_veda-spaces_environments_$env.json"
    echo '{"branch_policies":[{"name":"main","type":"branch"}]}' >"$d/repos_example-org_veda-spaces_environments_${env}_deployment-branch-policies.json"
  done
  echo '{"name":"main","protected":true}' >"$d/repos_example-org_veda-spaces_branches_main.json"
  echo '{"id":424242,"full_name":"example-org/veda-spaces","private":true}' >"$d/repos_example-org_veda-spaces.json"
  echo '{"enforce_admins":{"enabled":true},"required_pull_request_reviews":{"required_approving_review_count":0},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}' \
    >"$d/repos_example-org_veda-spaces_branches_main_protection.json"
  echo "$d"
}
GHV="$(gh_compliant)"

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
# Shaped like `terraform show -json`: the root AWS provider takes its region from var.aws_region (ap-south-1).
plan_json() {
  jq -n --argjson rc "$2" '{format_version: "1.2", variables: {aws_region: {value: "ap-south-1"}},
    configuration: {provider_config: {aws: {name: "aws", full_name: "registry.terraform.io/hashicorp/aws",
      expressions: {region: {references: ["var.aws_region"]}}}}}, resource_changes: $rc}' >"$1"
}
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

BOUNDARY_RES="$(jq -cn '{address: "aws_iam_policy.boundary", type: "aws_iam_policy", change: {actions: ["create"],
  after: {name: "veda-boundary", path: "/", policy: ({Version: "2012-10-17", Statement: [{Effect: "Allow", Action: "*", Resource: "*"}]} | tojson)}, after_unknown: {}}}')"
plan_json "$P.ok" "[$GH_ROLE, $BOUNDARY_RES,
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
check "R2 non-veda-gh role trusting GitHub" fail "only the bootstrap GitHub roles .* may trust GitHub" -- guard "$P.r2"
plan_json "$P.like" "[$(role 'aws_iam_role.github["plan"]' veda-gh-plan "$(trust "$GH_PRINCIPAL" '{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com"},"StringLike":{"token.actions.githubusercontent.com:sub":"repo:example-org/veda-spaces:*"}}')")]"
check "R2 wildcard GitHub subject" fail "must use StringEquals only" -- guard "$P.like"
plan_json "$P.pr" "[$(role 'aws_iam_role.github["plan"]' veda-gh-plan "$(trust "$GH_PRINCIPAL" '{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com","token.actions.githubusercontent.com:sub":"repo:example-org/veda-spaces:pull_request"}}')")]"
check "R2 pull_request subject" fail "must trust exactly repo:example-org/veda-spaces:environment:staging-plan" -- guard "$P.pr"
plan_json "$P.repo" "[$(role 'aws_iam_role.github["plan"]' veda-gh-plan "$(trust "$GH_PRINCIPAL" '{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com","token.actions.githubusercontent.com:sub":"repo:attacker/veda-spaces:environment:staging-plan"}}')")]"
check "R2 another repository" fail "must trust exactly repo:example-org/veda-spaces:environment:staging-plan.*got repo:attacker" -- guard "$P.repo"
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
check "--yes without a reviewed plan is refused" fail "needs an approved plan" -- env AWS_STUB_DIR="$(good_account)" "$BS" --mode apply --expected-account-id $ACCT --yes
check "F5 --skip-guardrails is gone" fail "was removed: set manage_account_guardrails" -- "$BS" --mode apply --expected-account-id $ACCT --skip-guardrails
check "--plan-file with --mode plan is refused" fail "are for --mode apply" -- "$BS" --mode plan --expected-account-id $ACCT --plan-file x --plan-meta y

sha() { shasum -a 256 "$1" | awk '{print $1}'; }
# reviewed <dir> <meta overrides (jq)>: a plan file, its text and matching metadata, as a plan run uploads them.
reviewed() {
  mkdir -p "$1"
  echo "reviewed plan bytes" >"$1/bootstrap.tfplan"
  echo "stub plan text" >"$1/bootstrap-plan.txt"
  jq -n --arg sum "$(sha "$1/bootstrap.tfplan")" --arg text "$(sha "$1/bootstrap-plan.txt")" --arg acct $ACCT \
    '{mode: "plan", commit: "c0ffee", dirty: false, account_id: $acct, repository: "example-org/veda-spaces",
      workflow_ref: "local", run_id: "1", run_attempt: "1", terraform_version: "1.16.4", plan_sha256: $sum,
      plan_text_sha256: $text, state_exists: true, created_at: "2026-09-30T00:00:00Z"}' |
    jq "$2" >"$1/bootstrap-plan.meta.json"
}
tf_stub() { # tf_stub <plan.json source>
  local d="$TMP/tf.$RANDOM$RANDOM"
  mkdir -p "$d"
  cp "$1" "$d/plan.json"
  jq -n --arg key "$KEY" --arg bp "$REVIEWED_BUCKET_POLICY" --arg kp "$REVIEWED_KEY_POLICY" \
    '{account_id: {value: "111122223333"}, region: {value: "ap-south-1"}, state_kms_key_arn: {value: $key},
      policy_documents: {value: {state_bucket: $bp, state_key: $kp}}}' >"$d/outputs.json"
  echo "$d"
}
# apply_reviewed <reviewed dir> <tf stub dir> <aws stub dir> [approved digest] [gh stub dir]
apply_reviewed() {
  env GITHUB_SHA=c0ffee TF_STUB_DIR="$2" AWS_STUB_DIR="$3" GH_STUB_DIR="${5:-$GHV}" \
    "$BS" --mode apply --expected-account-id $ACCT --plan-file "$1/bootstrap.tfplan" --plan-meta "$1/bootstrap-plan.meta.json" \
    --plan-sha256 "${4:-$(sha "$1/bootstrap.tfplan")}" --yes
}

R="$TMP/rev.ok" && reviewed "$R" '.'
TFD="$(tf_stub "$P.ok")"
check "reviewed plan is applied" ok "reviewed plan verified" -- apply_reviewed "$R" "$TFD" "$(good_account)"
check "  ... after re-rendering the reviewed text and verifying the live protections" ok "state protection verified" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)"
check "  ... exactly that plan file" ok "apply -input=false -lock-timeout=5m $R/bootstrap.tfplan" -- cat "$TFD/calls.log"

R="$TMP/rev.sum" && reviewed "$R" '.'
echo "tampered" >>"$R/bootstrap.tfplan"
TFD="$(tf_stub "$P.ok")"
check "tampered plan file" fail "checksum mismatch" -- apply_reviewed "$R" "$TFD" "$(good_account)"
absent "  ... refused before terraform runs" "^(init|plan|show|apply)" "$(cat "$TFD/calls.log" 2>/dev/null || true)"

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
check "reviewed plan for an unapproved account is refused" fail "no approved staging account" -- env GITHUB_SHA=c0ffee TF_STUB_DIR="$(tf_stub "$P.ok")" AWS_STUB_DIR="$(good_account)" GH_STUB_DIR="$GHV" \
  "$T5/infra/scripts/bootstrap.sh" --mode apply --expected-account-id $ACCT --plan-file "$R/bootstrap.tfplan" --plan-meta "$R/bootstrap-plan.meta.json" --plan-sha256 "$(sha "$R/bootstrap.tfplan")" --yes

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

echo "== F4 / F10 / RR-05 / RR-07: 00-bootstrap workflow"
WF="$INFRA/../.github/workflows/00-bootstrap.yml"
WFT="$(cat "$WF")"
PREFLIGHT="$(awk '/^  preflight:/{p=1} /^  bootstrap:/{p=0} p' "$WF")"
BOOTJOB="$(awk '/^  bootstrap:/{p=1} p' "$WF")"
check "apply passes the reviewed plan file" ok "--plan-file infra/generated/reviewed/bootstrap.tfplan" -- printf '%s\n' "$WFT"
# shellcheck disable=SC2016 # literal $PLAN_SHA256 in the workflow text
check "  ... with the approved digest and run, then --yes" ok '--plan-sha256 "\$PLAN_SHA256" --plan-run-id "\$PLAN_RUN_ID" --yes' -- printf '%s\n' "$WFT"
absent "  ... never --yes on the same line as --mode apply" "--mode apply.*--yes" "$WFT"
# shellcheck disable=SC2016 # literal $MODE in the workflow text
absent "  ... no mode passed through unchecked" '--mode "\$MODE"' "$WFT"
check "RR-05 plan_sha256 is an input" ok "^      plan_sha256:" -- printf '%s\n' "$WFT"
check "RR-05 the run name shows the approved digest to the environment reviewer" ok "^run-name: .*plan sha256 \{1\}.*inputs.plan_sha256" -- printf '%s\n' "$WFT"
check "RR-05 the plan run and artifact are verified before approval (preflight)" ok "verify-run.sh plan-run" -- printf '%s\n' "$PREFLIGHT"
check "RR-05 ... and again in the job that applies" ok "verify-run.sh plan-run" -- printf '%s\n' "$BOOTJOB"
absent "RR-05 no match on the workflow name" "workflowName" "$WFT"
check "RR-07 preflight verifies environment protection" ok "github-setup.sh --repo \"\\\$GITHUB_REPOSITORY\" --verify-environments" -- printf '%s\n' "$PREFLIGHT"
absent "RR-07 preflight holds no environment" "environment:" "$PREFLIGHT"
absent "RR-07 preflight holds no secret" "secrets\\." "$PREFLIGHT"
check "RR-07 the environment job needs the preflight" ok "^    needs: preflight$" -- printf '%s\n' "$BOOTJOB"
check "RR-07 the environment job proves its approval" ok "verify-run.sh approval .* --environment bootstrap" -- printf '%s\n' "$BOOTJOB"
approval_line="$(grep -n 'verify-run.sh approval' <<<"$BOOTJOB" | head -1 | cut -d: -f1)"
secret_line="$(grep -n 'secrets\.' <<<"$BOOTJOB" | head -1 | cut -d: -f1)"
check "RR-07 ... before any secret is used (line $approval_line < $secret_line)" ok "^before$" -- bash -c "[[ -n '$approval_line' && -n '$secret_line' && $approval_line -lt $secret_line ]] && echo before"
check "long-lived keys refused (ASIA prefix)" ok 'AWS_ACCESS_KEY_ID" == ASIA\*' -- cat "$WF"
check "approved account checked against the manifest" ok "infra/config/staging-account.json" -- grep -F "staging-account.json" "$WF"
check "runs only from protected main" ok "branches/main\" --jq .protected" -- cat "$WF"
check "runs only as 00-bootstrap.yml on main" ok "GITHUB_WORKFLOW_REF.*00-bootstrap.yml@refs/heads/main" -- cat "$WF"
check "GITHUB_TOKEN limited to contents and actions read" ok "^  contents: read$" -- cat "$WF"
absent "  ... no write permission" "^ +[a-z-]+: write" "$WFT"

echo "== F8: documentation states the apply-role exception"
RB="$INFRA/../docs/operations/staging-bootstrap.md"
absent "runbook does not claim every role is denied application data" "Applies to every role:" "$(cat "$RB")"
check "runbook names the apply role as able to reach data through the host" ok "veda-gh-apply. carries the same" -- cat "$RB"
check "  ... and says how" ok "reach that data through the host role" -- cat "$RB"

echo "== RR-03: plan guard closes the IAM path and trust-policy bypass"
T="$(new_tree)" # guard() (above) runs check-plan.sh from $T
iam() { # iam <type> <address> <after JSON> [after_unknown JSON]
  local unknown="${4:-}"
  [[ -n "$unknown" ]] || unknown='{}'
  jq -cn --arg t "$1" --arg a "$2" --argjson after "$3" --argjson u "$unknown" \
    '{address: $a, type: $t, change: {actions: ["create"], after: $after, after_unknown: $u}}'
}
EC2_TRUST="$(trust '{"Service":"ec2.amazonaws.com"}')"
gh_trust() { # gh_trust <subject> [action JSON]
  jq -cn --arg p "$OIDC" --arg s "$1" --argjson a "${2:-\"sts:AssumeRoleWithWebIdentity\"}" \
    '{Version: "2012-10-17", Statement: [{Effect: "Allow", Action: $a, Principal: {Federated: $p},
      Condition: {StringEquals: {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                                 "token.actions.githubusercontent.com:sub": $s}}}]} | tojson'
}
B="arn:aws:iam::$ACCT:policy/veda-boundary"
# iam_role <address> <name> <path> <trust JSON string> [after_unknown JSON]; built with jq (bash 3.2 would
# brace-expand escaped JSON inside a nested command substitution).
iam_role() {
  iam aws_iam_role "$1" "$(jq -cn --arg n "$2" --arg p "$3" --arg b "$B" --argjson t "$4" \
    '{name: $n, path: $p, permissions_boundary: $b, assume_role_policy: $t}')" "${5:-}"
}
plan_json "$P.rr3ok" "[$GH_ROLE,
  $(iam_role aws_iam_role.host veda-host / "$EC2_TRUST"),
  $(iam aws_iam_policy aws_iam_policy.p '{"name":"veda-host-permissions","path":"/"}'),
  $(iam aws_iam_instance_profile aws_iam_instance_profile.p '{"name":"veda-host","path":"/"}'),
  $(iam aws_iam_role_policy_attachment aws_iam_role_policy_attachment.ro '{"policy_arn":"arn:aws:iam::aws:policy/ReadOnlyAccess"}'),
  $(iam aws_iam_openid_connect_provider 'aws_iam_openid_connect_provider.github[0]' '{"url":"https://token.actions.githubusercontent.com"}')]"
check "bootstrap-shaped IAM at path / passes" ok "every role bounded at path /" -- guard "$P.rr3ok"
: >"$P.empty"
check "an empty plan file is refused, not passed as clean" fail "is not a Terraform plan" -- guard "$P.empty"
echo '{"resource_changes":[]}' >"$P.foreign"
check "a JSON file that is not a plan is refused" fail "is not a Terraform plan" -- guard "$P.foreign"

plan_json "$P.rp" "[$(iam_role aws_iam_role.x admin /veda-x/ "$EC2_TRUST")]"
check "RR-03 role under a path" fail "IAM role under path /veda-x/" -- guard "$P.rp"
check "RR-03 ... and not named veda-*" fail "IAM role name admin is not veda-\*" -- guard "$P.rp"
plan_json "$P.rpu" "[$(iam aws_iam_role aws_iam_role.x "$(jq -cn --arg b "$B" --argjson t "$EC2_TRUST" '{permissions_boundary: $b, assume_role_policy: $t}')" '{"name":true,"path":true}')]"
check "RR-03 role name and path unknown at plan time" fail "IAM role under path \(unknown\)" -- guard "$P.rpu"
plan_json "$P.pp" "[$(iam aws_iam_policy aws_iam_policy.x '{"name":"veda-admin","path":"/ops/"}')]"
check "RR-03 policy under a path" fail "IAM policy under path /ops/" -- guard "$P.pp"
plan_json "$P.ipp" "[$(iam aws_iam_instance_profile aws_iam_instance_profile.x '{"name":"veda-host","path":"/x/"}')]"
check "RR-03 instance profile under a path" fail "IAM instance profile under path /x/" -- guard "$P.ipp"

gh_role() { iam_role "aws_iam_role.github[\"$1\"]" "$2" / "$3"; }
plan_json "$P.envx" "[$(gh_role apply veda-gh-apply "$(gh_trust repo:example-org/veda-spaces:environment:staging-plan)")]"
check "RR-03 apply role trusted by the plan environment" fail "veda-gh-apply must trust exactly repo:example-org/veda-spaces:environment:staging-infra" -- guard "$P.envx"
plan_json "$P.envu" "[$(gh_role deploy veda-gh-deploy "$(gh_trust repo:example-org/veda-spaces:environment:unprotected)")]"
check "RR-03 role trusted by an unprotected environment" fail "veda-gh-deploy must trust exactly repo:example-org/veda-spaces:environment:staging, .*got repo:example-org/veda-spaces:environment:unprotected" -- guard "$P.envu"
plan_json "$P.ghx" "[$(gh_role extra veda-gh-extra "$(gh_trust repo:example-org/veda-spaces:environment:staging-infra)")]"
check "RR-03 a new veda-gh-* role trusting GitHub" fail "only the bootstrap GitHub roles" -- guard "$P.ghx"
plan_json "$P.sub2" "[$(gh_role plan veda-gh-plan "$(jq -cn --arg p "$OIDC" '{Version: "2012-10-17", Statement: [{Effect: "Allow", Action: "sts:AssumeRoleWithWebIdentity", Principal: {Federated: $p}, Condition: {StringEquals: {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com", "token.actions.githubusercontent.com:sub": ["repo:example-org/veda-spaces:environment:staging-plan", "repo:example-org/veda-spaces:environment:dev"]}}}]} | tojson')")]"
check "RR-03 a second subject beside the protected environment" fail "must trust exactly" -- guard "$P.sub2"
plan_json "$P.tag" "[$(gh_role plan veda-gh-plan "$(gh_trust repo:example-org/veda-spaces:environment:staging-plan '["sts:AssumeRoleWithWebIdentity","sts:TagSession"]')")]"
check "RR-03 GitHub trust with sts:TagSession" fail "sts:AssumeRoleWithWebIdentity only" -- guard "$P.tag"
plan_json "$P.na" "[$(iam_role aws_iam_role.x veda-x / "$(jq -cn '{Statement: [{Effect: "Allow", NotAction: "iam:*", Principal: {Service: "ec2.amazonaws.com"}}]} | tojson')")]"
check "RR-03 trust with NotAction" fail "trust with NotAction" -- guard "$P.na"
for pol in AdministratorAccess AdministratorAccess-Amplify PowerUserAccess IAMFullAccess job-function/SystemAdministrator; do
  plan_json "$P.priv" "[$(iam aws_iam_role_policy_attachment aws_iam_role_policy_attachment.x "{\"policy_arn\":\"arn:aws:iam::aws:policy/$pol\"}")]"
  check "RR-03 privileged managed policy $pol" fail "privileged managed policy arn:aws:iam::aws:policy/$pol" -- guard "$P.priv"
done
for t in aws_iam_user aws_iam_access_key aws_iam_group aws_iam_saml_provider aws_iam_user_login_profile; do
  plan_json "$P.forb" "[$(iam $t $t.x '{}')]"
  check "RR-03 $t refused" fail "$t is not allowed" -- guard "$P.forb"
done
plan_json "$P.oidc2" "[$(iam aws_iam_openid_connect_provider aws_iam_openid_connect_provider.other '{"url":"https://evil.example"}')]"
check "RR-03 another OIDC provider refused" fail "only the bootstrap creates the GitHub OIDC provider" -- guard "$P.oidc2"

echo "== RR-07: GitHub environment protection is a hard prerequisite of apply"
T="$(new_tree)"
GS="$T/infra/scripts/github-setup.sh"
venv() { GH_STUB_DIR="$1" "$GS" --repo example-org/veda-spaces --verify-environments; }
check "RR-07 protected environments and main verify" ok "match the bootstrap rules" -- venv "$GHV"
absent "  ... using only endpoints a workflow token can read (no admin protection endpoint)" "branches/main/protection" "$(cat "$GHV/calls.log")"
gh_drift() { # gh_drift <file suffix> <jq, or DELETE>
  local d="$TMP/ghd.$RANDOM$RANDOM"
  cp -R "$GHV" "$d"
  rm -f "$d/calls.log"
  if [[ "$2" == DELETE ]]; then rm "$d/repos_example-org_veda-spaces_$1.json"; else
    jq "$2" "$d/repos_example-org_veda-spaces_$1.json" >"$d/x" && mv "$d/x" "$d/repos_example-org_veda-spaces_$1.json"; fi
  echo "$d"
}
check "RR-07 missing bootstrap environment (would be auto-created unprotected)" fail "bootstrap: environment missing" -- venv "$(gh_drift environments_bootstrap DELETE)"
check "RR-07 bootstrap environment without reviewers" fail "bootstrap: no required reviewers" -- venv "$(gh_drift environments_bootstrap '.protection_rules = []')"
check "RR-07 staging-infra (apply role) open to any branch" fail "staging-infra: not restricted to main" -- venv "$(gh_drift environments_staging-infra '.deployment_branch_policy = null')"
check "RR-07 admin bypass on staging" fail "staging: admins can bypass" -- venv "$(gh_drift environments_staging '.can_admins_bypass = true')"
check "RR-07 main unprotected" fail "main: branch not protected" -- venv "$(gh_drift branches_main '.protected = false')"
check "RR-07 no GitHub access fails closed" fail "do not match the bootstrap rules" -- venv "$TMP/empty-gh-$RANDOM"

T="$(new_tree)"
BS="$T/infra/scripts/bootstrap.sh"
R="$TMP/rev.rr7" && reviewed "$R" '.'
TFD="$(tf_stub "$P.ok")"
check "RR-07 apply refused while an environment is unprotected" fail "prerequisite of apply" -- apply_reviewed "$R" "$TFD" "$(good_account)" "" "$(gh_drift environments_staging-infra '.protection_rules = []')"
absent "  ... and nothing is applied" "^apply " "$(cat "$TFD/calls.log" 2>/dev/null || true)"
R="$TMP/rev.rr7b" && reviewed "$R" '.'
TFD="$(tf_stub "$P.ok")"
check "RR-07 apply refused without GitHub access" fail "prerequisite of apply" -- apply_reviewed "$R" "$TFD" "$(good_account)" "" "$TMP/empty-gh-$RANDOM"
absent "  ... and nothing is applied" "^apply " "$(cat "$TFD/calls.log" 2>/dev/null || true)"

VR="$T/infra/scripts/verify-run.sh"
AP="$TMP/gh.approvals" && mkdir -p "$AP"
approval() { GH_STUB_DIR="$1" "$VR" approval --repo example-org/veda-spaces --run-id 200 --environment bootstrap; }
echo '[{"state":"approved","comment":"plan sha256 ok","environments":[{"name":"bootstrap"}],"user":{"login":"owner"}}]' >"$AP/repos_example-org_veda-spaces_actions_runs_200_approvals.json"
check "RR-07 run approved for the bootstrap environment" ok "approved for environment 'bootstrap' by: owner" -- approval "$AP"
echo '[]' >"$AP/repos_example-org_veda-spaces_actions_runs_200_approvals.json"
check "RR-07 run that was never approved (unprotected environment)" fail "no approved review for environment 'bootstrap'" -- approval "$AP"
echo '[{"state":"approved","environments":[{"name":"staging"}],"user":{"login":"owner"}}]' >"$AP/repos_example-org_veda-spaces_actions_runs_200_approvals.json"
check "RR-07 approval for another environment only" fail "no approved review for environment 'bootstrap'" -- approval "$AP"
echo '[{"state":"rejected","environments":[{"name":"bootstrap"}],"user":{"login":"owner"}}]' >"$AP/repos_example-org_veda-spaces_actions_runs_200_approvals.json"
check "RR-07 rejected review" fail "no approved review" -- approval "$AP"
rm "$AP/repos_example-org_veda-spaces_actions_runs_200_approvals.json"
check "RR-07 approvals unreadable fails closed" fail "cannot read the approvals" -- approval "$AP"

echo "== RR-05: reviewed plan -> approved plan -> applied plan"
# bootstrap.sh side (local and in the job): the approved digest, the metadata binding and the re-rendered text.
T="$(new_tree)"
BS="$T/infra/scripts/bootstrap.sh"
R="$TMP/rev.rr5" && reviewed "$R" '.'
check "RR-05 --plan-file without the approved digest is refused" fail "go together" -- env GITHUB_SHA=c0ffee "$BS" --mode apply --expected-account-id $ACCT --plan-file "$R/bootstrap.tfplan" --plan-meta "$R/bootstrap-plan.meta.json" --yes
check "RR-05 malformed approved digest is refused" fail "must be the 64-hex SHA-256" -- env GITHUB_SHA=c0ffee "$BS" --mode apply --expected-account-id $ACCT --plan-file "$R/bootstrap.tfplan" --plan-meta "$R/bootstrap-plan.meta.json" --plan-sha256 abc --yes

# The attack RR-05 names: a genuine, self-consistent plan + metadata that is not the one the reviewer approved.
R="$TMP/rev.subst" && reviewed "$R" '.'
echo "an alternate plan" >"$R/bootstrap.tfplan"
jq --arg s "$(sha "$R/bootstrap.tfplan")" '.plan_sha256 = $s' "$R/bootstrap-plan.meta.json" >"$R/m" && mv "$R/m" "$R/bootstrap-plan.meta.json"
TFD="$(tf_stub "$P.ok")"
check "RR-05 substituted plan with matching metadata is refused" fail "is not the approved plan" -- apply_reviewed "$R" "$TFD" "$(good_account)" "$(printf 'reviewed plan bytes\n' | shasum -a 256 | awk '{print $1}')"
absent "  ... before terraform runs" "^(init|apply)" "$(cat "$TFD/calls.log" 2>/dev/null || true)"

R="$TMP/rev.wf" && reviewed "$R" '.workflow_ref = "example-org/veda-spaces/.github/workflows/evil.yml@refs/heads/main"'
check "RR-05 plan made by another workflow" fail "was made by 'example-org/veda-spaces/.github/workflows/evil.yml" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)"
R="$TMP/rev.tfv" && reviewed "$R" '.terraform_version = "1.15.0"'
check "RR-05 plan made with another Terraform version" fail "made with Terraform 1.15.0" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)"
R="$TMP/rev.txt" && reviewed "$R" '.'
echo "a different text" >"$R/bootstrap-plan.txt"
check "RR-05 reviewed text replaced beside the plan" fail "not the text recorded at plan time" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)"
R="$TMP/rev.render" && reviewed "$R" '.'
TFD="$(tf_stub "$P.ok")"
echo "Plan: 99 to add" >"$TFD/plan.txt"
check "RR-05 plan file renders a different text than was reviewed" fail "renders a different text" -- apply_reviewed "$R" "$TFD" "$(good_account)"
absent "  ... and is never applied" "^apply " "$(cat "$TFD/calls.log")"
R="$TMP/rev.run" && reviewed "$R" '.'
check "RR-05 metadata from another run than the approved one" fail "not the approved run 42" -- env GITHUB_SHA=c0ffee TF_STUB_DIR="$(tf_stub "$P.ok")" AWS_STUB_DIR="$(good_account)" GH_STUB_DIR="$GHV" \
  "$BS" --mode apply --expected-account-id $ACCT --plan-file "$R/bootstrap.tfplan" --plan-meta "$R/bootstrap-plan.meta.json" --plan-sha256 "$(sha "$R/bootstrap.tfplan")" --plan-run-id 42 --yes

# verify-run.sh side (00-bootstrap): the plan run, its artifact and the approved digest.
C=0123456789abcdef0123456789abcdef01234567
VR="$T/infra/scripts/verify-run.sh"
plan_run_stub() { # plan_run_stub: a GitHub with plan run 100 (and its artifact 555) and this apply run 200
  local d="$TMP/ghrun.$RANDOM$RANDOM" z="$TMP/zip.$RANDOM$RANDOM"
  mkdir -p "$d" "$z"
  echo "reviewed plan bytes" >"$z/bootstrap.tfplan"
  echo "stub plan text" >"$z/bootstrap-plan.txt"
  echo '{}' >"$z/discovered.json"
  jq -n --arg sum "$(sha "$z/bootstrap.tfplan")" --arg text "$(sha "$z/bootstrap-plan.txt")" --arg c $C \
    '{mode: "plan", commit: $c, workflow_ref: "example-org/veda-spaces/.github/workflows/00-bootstrap.yml@refs/heads/main",
      run_id: "100", plan_sha256: $sum, plan_text_sha256: $text}' >"$z/bootstrap-plan.meta.json"
  (cd "$z" && zip -q -X "$d/repos_example-org_veda-spaces_actions_artifacts_555_zip.json" bootstrap.tfplan bootstrap-plan.meta.json bootstrap-plan.txt discovered.json)
  jq -n --arg c $C '{id: 100, path: ".github/workflows/00-bootstrap.yml", workflow_id: 7, head_sha: $c, head_branch: "main",
    event: "workflow_dispatch", status: "completed", conclusion: "success", display_title: "00-bootstrap (plan)",
    repository: {full_name: "example-org/veda-spaces"}, head_repository: {full_name: "example-org/veda-spaces"}}' \
    >"$d/repos_example-org_veda-spaces_actions_runs_100.json"
  echo '{"id":200,"path":".github/workflows/00-bootstrap.yml","workflow_id":7}' >"$d/repos_example-org_veda-spaces_actions_runs_200.json"
  jq -n --arg c $C --arg dg "sha256:$(sha "$d/repos_example-org_veda-spaces_actions_artifacts_555_zip.json")" \
    '{artifacts: [{id: 555, name: "bootstrap-plan-100", expired: false, digest: $dg, workflow_run: {id: 100, head_sha: $c}}]}' \
    >"$d/repos_example-org_veda-spaces_actions_runs_100_artifacts?per_page=100.json"
  echo "$d"
}
APPROVED="$(printf 'reviewed plan bytes\n' | shasum -a 256 | awk '{print $1}')"
bind() { GH_STUB_DIR="$1" "$VR" plan-run --repo example-org/veda-spaces --run-id 100 --this-run-id 200 --commit $C --plan-sha256 "${2:-$APPROVED}" --out "$TMP/out.$RANDOM"; }
run_drift() { # run_drift <file suffix> <jq>
  local d
  d="$(plan_run_stub)"
  jq "$2" "$d/repos_example-org_veda-spaces_$1.json" >"$d/x" && mv "$d/x" "$d/repos_example-org_veda-spaces_$1.json"
  echo "$d"
}
check "RR-05 approved plan of a reviewed plan run is bound" ok "approved plan bound: run 100, artifact sha256:" -- bind "$(plan_run_stub)"
check "RR-05 another plan (not the approved digest)" fail "is not the approved plan" -- bind "$(plan_run_stub)" "$(printf 'x' | shasum -a 256 | awk '{print $1}')"
check "RR-05 a workflow file other than 00-bootstrap.yml (same name)" fail "was made by .github/workflows/evil.yml" -- bind "$(run_drift actions_runs_100 '.path = ".github/workflows/evil.yml"')"
check "RR-05 another workflow ID" fail "belongs to workflow 8" -- bind "$(run_drift actions_runs_100 '.workflow_id = 8')"
check "RR-05 the apply run is not 00-bootstrap.yml" fail "this apply run is .github/workflows/other.yml" -- bind "$(run_drift actions_runs_200 '.path = ".github/workflows/other.yml"')"
check "RR-05 plan run for another commit" fail "is for commit badc0de" -- bind "$(run_drift actions_runs_100 '.head_sha = "badc0de"')"
check "RR-05 plan run from a fork" fail "fork or other repository" -- bind "$(run_drift actions_runs_100 '.head_repository.full_name = "attacker/veda-spaces"')"
check "RR-05 plan run on another branch" fail "ran on feature, not main" -- bind "$(run_drift actions_runs_100 '.head_branch = "feature"')"
check "RR-05 failed plan run" fail "is completed/failure" -- bind "$(run_drift actions_runs_100 '.conclusion = "failure"')"
check "RR-05 an apply run instead of a plan run" fail "not a plan run" -- bind "$(run_drift actions_runs_100 '.display_title = "00-bootstrap (apply of plan run 1, plan sha256 x)"')"
D="$(plan_run_stub)"
printf 'x' >>"$D/repos_example-org_veda-spaces_actions_artifacts_555_zip.json"
check "RR-05 artifact bytes differ from the digest recorded at upload" fail "differs from the digest GitHub recorded" -- bind "$D"
check "RR-05 artifact without a recorded digest" fail "no SHA-256 digest recorded" -- bind "$(run_drift 'actions_runs_100_artifacts?per_page=100' 'del(.artifacts[0].digest)')"
check "RR-05 two artifacts with the plan's name" fail "exactly one artifact named bootstrap-plan-100" -- bind "$(run_drift 'actions_runs_100_artifacts?per_page=100' '.artifacts += .artifacts')"
check "RR-05 expired artifact" fail "is expired" -- bind "$(run_drift 'actions_runs_100_artifacts?per_page=100' '.artifacts[0].expired = true')"
check "RR-05 artifact of another run" fail "not from run 100" -- bind "$(run_drift 'actions_runs_100_artifacts?per_page=100' '.artifacts[0].workflow_run.id = 99')"
D="$(plan_run_stub)"
rm "$D/repos_example-org_veda-spaces_actions_runs_100.json"
check "RR-05 plan run unreadable fails closed" fail "cannot read run 100" -- bind "$D"

echo "== RR-01 / RR-02: live state protections verified after apply (fail closed)"
T="$(new_tree)"
BS="$T/infra/scripts/bootstrap.sh"
prot() { # prot <aws stub dir>: apply a clean reviewed plan against that account
  local r="$TMP/rev.p.$RANDOM$RANDOM" tfd
  reviewed "$r" '.'
  tfd="$(tf_stub "$P.ok")"
  apply_reviewed "$r" "$tfd" "$1"
  local rc=$?
  [[ -f "$T/infra/generated/bootstrap-outputs.json" ]] && echo "OUTPUTS WRITTEN"
  rm -f "$T/infra/generated/bootstrap-outputs.json"
  return $rc
}
check "RR-01/02 live policies equal the reviewed ones (after AWS normalisation)" ok "state protection verified" -- prot "$(good_account)"
D="$(good_account)"
jq -n --arg p '{"Version":"2012-10-17","Statement":[{"Sid":"AccountAdministration","Effect":"Allow","Principal":{"AWS":"arn:aws:iam::111122223333:root"},"Action":"kms:*","Resource":"*"}]}' '{Policy: $p}' >"$D/kms_get-key-policy.json"
check "RR-02 live key policy weakened to root delegation only" fail "key policy differs from the reviewed plan" -- prot "$D"
absent "  ... and no outputs (role ARNs) are written" "OUTPUTS WRITTEN" "$(prot "$D" 2>&1)"
D="$(good_account)"
jq -n --arg p "$(jq -c '.Statement[0].Condition.ArnNotEquals["aws:PrincipalArn"] += ["arn:aws:iam::111122223333:role/veda-gh-apply"]' <<<"$REVIEWED_BUCKET_POLICY")" '{Policy: $p}' >"$D/s3api_get-bucket-policy.json"
check "RR-01 live bucket policy admits a veda role" fail "bucket policy differs from the reviewed plan" -- prot "$D"
D="$(good_account)"
jq '.ServerSideEncryptionConfiguration.Rules[0].BucketKeyEnabled = true' "$D/s3api_get-bucket-encryption.json" >"$D/x" && mv "$D/x" "$D/s3api_get-bucket-encryption.json"
check "RR-02 S3 Bucket Key enabled" fail "S3 Bucket Key enabled" -- prot "$D"
D="$(good_account)"
echo '{"KeyRotationEnabled":false}' >"$D/kms_get-key-rotation-status.json"
check "RR-02 key rotation off" fail "key rotation is off" -- prot "$D"
D="$(good_account)"
echo "AccessDenied" >"$D/kms_get-key-policy.fail"
check "RR-02 key policy unreadable fails closed" fail "cannot read the policy of" -- prot "$D"
D="$(good_account)"
jq '.ServerSideEncryptionConfiguration.Rules[0].ApplyServerSideEncryptionByDefault.KMSMasterKeyID = "arn:aws:kms:ap-south-1:999999999999:key/x"' "$D/s3api_get-bucket-encryption.json" >"$D/x" && mv "$D/x" "$D/s3api_get-bucket-encryption.json"
check "RR-02 bucket encrypted with another account's key" fail "not encrypted with exactly one KMS key of account $ACCT" -- prot "$D"
D="$(good_account)"
echo '{"KeyMetadata":{"Arn":"arn:aws:kms:ap-south-1:111122223333:key/k","KeyState":"PendingDeletion","KeyManager":"CUSTOMER"}}' >"$D/kms_describe-key.json"
check "RR-02 state key pending deletion (or the alias points elsewhere)" fail "not an enabled customer-managed key|does not point at the key" -- prot "$D"

echo "== PB-01: the account manifest (schema, owner decisions, completeness)"
T="$(new_tree)"
CM="$T/infra/scripts/check-manifest.sh"
cp "$INFRA/config/staging-account.json" "$T/infra/config/staging-account.json"
check "PB-01 committed manifest is structurally valid (Mumbai, organization member, repository and ID)" ok "valid \(structure\)" -- "$CM"
check "PB-01 committed manifest is complete (owner values committed)" ok "valid \(complete\)" -- "$CM" --complete
check "  ... for the veda-staging member account of the Veda organization" ok '^813238078849 o-q9ji0hj18c 749251636763$' -- jq -r '"\(.account_id) \(.organization_id) \(.management_account_id)"' "$T/infra/config/staging-account.json"
man() { # man <jq over the fixture manifest>: a tree whose manifest is the fixture changed by the jq program
  local t
  t="$(new_tree)"
  jq "$1" "$FIXTURE_MANIFEST" >"$t/infra/config/staging-account.json"
  echo "$t"
}
check "PB-01 complete fixture manifest passes" ok "valid \(complete\)" -- "$(man '.')/infra/scripts/check-manifest.sh" --complete
check "PB-01 placeholder account ID refused" fail "placeholder value \"123456789012\"" -- "$(man '.account_id = "123456789012"')/infra/scripts/check-manifest.sh" --complete
check "PB-01 placeholder name refused" fail "placeholder value \"<account name>\"" -- "$(man '.account_name = "<account name>"')/infra/scripts/check-manifest.sh" --complete
check "PB-01 missing alias refused" fail "account_alias must be set" -- "$(man '.account_alias = null')/infra/scripts/check-manifest.sh" --complete
check "PB-01 Aurion alias refused" fail "looks like production or Aurion" -- "$(man '.account_alias = "aurion-staging"')/infra/scripts/check-manifest.sh" --complete
check "PB-01 another region refused" fail "region must be ap-south-1" -- "$(man '.region = "us-east-1"')/infra/scripts/check-manifest.sh"
check "PB-01 standalone account refused (owner decision: member account)" fail "organizations_mode must be \"member\"" -- "$(man '.organizations_mode = "standalone"')/infra/scripts/check-manifest.sh"
check "PB-01 organization ID required" fail "organization_id must be the AWS Organizations ID" -- "$(man 'del(.organization_id)')/infra/scripts/check-manifest.sh"
check "PB-01 management account as the staging account refused" fail "account_id is the management account" -- "$(man '.management_account_id = .account_id')/infra/scripts/check-manifest.sh"
check "PB-01 repository ID required" fail "repository_id must be the numeric GitHub repository ID" -- "$(man 'del(.repository_id)')/infra/scripts/check-manifest.sh"
check "PB-09 IAM user as owner refused" fail "is not an exact, non-veda IAM role ARN" -- "$(man '.bootstrap_principal_arns = ["arn:aws:iam::111122223333:user/owner"]')/infra/scripts/check-manifest.sh" --complete
check "PB-09 owner session longer than one hour refused" fail "max_owner_session_seconds must be 900-3600" -- "$(man '.max_owner_session_seconds = 43200')/infra/scripts/check-manifest.sh"
T6="$(man '.account_alias = null')"
check "PB-01 an incomplete manifest stops the account check before any AWS call" fail "the account manifest is not complete" -- env AWS_STUB_DIR="$(good_account)" bash -c "set -euo pipefail; source '$T6/infra/scripts/lib.sh'; verify_account_identity $ACCT"

echo "== Owner inputs: the templates are exactly what the checks accept"
TPL="$INFRA/config/templates"
fill() { # fill <template>: the owner values of the fixture account
  sed -e 's/<ACCOUNT_ID: 12 digits>/111122223333/; s/<ACCOUNT_ID>/111122223333/g' \
    -e 's/<ACCOUNT_NAME: [^>]*>/veda-staging/; s/<ACCOUNT_ALIAS: [^>]*>/veda-staging/' \
    -e 's/<OWNER_ROLE_NAME>/bootstrap-owner/g; s/<OWNER_USER_NAME>/bootstrap-operator/g' "$1"
}
T="$(new_tree)"
cp "$TPL/staging-account.template.json" "$T/infra/config/staging-account.json"
check "the unfilled manifest template is refused (placeholders)" fail "placeholder value" -- "$T/infra/scripts/check-manifest.sh" --complete
fill "$TPL/staging-account.template.json" >"$T/infra/config/staging-account.json"
check "the manifest template, filled with the owner values, is complete" ok "valid \(complete\)" -- "$T/infra/scripts/check-manifest.sh" --complete
jq '.allowed_foreign_resources.iam_roles = []' "$T/infra/config/staging-account.json" >"$T/x" && mv "$T/x" "$T/infra/config/staging-account.json"
check "an owner role missing from allowed_foreign_resources.iam_roles is refused" fail "owner role bootstrap-owner is not listed" -- "$T/infra/scripts/check-manifest.sh" --complete
T="$(new_tree)"
fill "$TPL/staging-account.template.json" >"$T/infra/config/staging-account.json"
D="$(good_account)"
echo "{\"Account\":\"$ACCT\",\"Arn\":\"arn:aws:sts::$ACCT:assumed-role/bootstrap-owner/veda-bootstrap\"}" >"$D/sts_get-caller-identity.json"
jq -n --slurpfile m "$T/infra/config/staging-account.json" '{Organization: {Id: $m[0].organization_id, MasterAccountId: $m[0].management_account_id}}' \
  >"$D/organizations_describe-organization.json"
jq -n --argjson trust "$(fill "$TPL/owner-role-trust-policy.template.json")" \
  '{Role: {RoleName: "bootstrap-owner", Arn: "arn:aws:iam::111122223333:role/bootstrap-owner", MaxSessionDuration: 3600, AssumeRolePolicyDocument: $trust}}' >"$D/iam_get-role.json"
jq '.Roles = [{"RoleName":"bootstrap-owner","Path":"/"},{"RoleName":"veda-gh-apply","Path":"/"}]' "$D/iam_list-roles.json" >"$D/x" && mv "$D/x" "$D/iam_list-roles.json"
echo '{"Users":[{"UserName":"bootstrap-operator"}]}' >"$D/iam_list-users.json"
check "the owner role built from the templates passes the live owner and inventory checks" ok "no foreign resources in any region" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"
jq '.Role.MaxSessionDuration = 7200' "$D/iam_get-role.json" >"$D/x" && mv "$D/x" "$D/iam_get-role.json"
check "  ... and a two-hour maximum session on that role is refused" fail "allows sessions longer than 3600 seconds" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"

echo "== PB-06: Mumbai only, enforced by IAM on the owner session and by the plan guard"
T="$(new_tree)"
rguard() { "$T/infra/scripts/check-plan.sh" --plan-json "$1" --account "$ACCT" --repo example-org/veda-spaces; }
REAL="$HERE/fixtures/plan-regions.json" # `terraform show -json` of Terraform 1.16.4 / AWS provider 6.x, see the file
check "PB-06 real plan: provider alias in us-east-1 refused" fail "provider aws.use1: region us-east-1 is not ap-south-1" -- rguard "$REAL"
check "PB-06 real plan: module with its own provider refused" fail "provider module.m:aws: a module configures its own AWS provider" -- rguard "$REAL"
check "PB-06 real plan: resource through the alias refused" fail "aws_sns_topic.alias: planned in us-east-1" -- rguard "$REAL"
check "PB-06 real plan: per-resource region argument refused" fail "aws_sns_topic.arg: planned in eu-west-1" -- rguard "$REAL"
check "PB-06 real plan: resource in a module refused" fail "module.m.aws_sns_topic.mod: planned in sa-east-1" -- rguard "$REAL"
jq 'del(.configuration.provider_config["aws.use1"], .configuration.provider_config["module.m:aws"])
    | .resource_changes |= map(select(.address == "aws_sns_topic.home" or .address == "aws_iam_policy.global"))' "$REAL" >"$P.mumbai"
check "PB-06 real plan: Mumbai resource and a global IAM policy pass" ok "everything in ap-south-1" -- rguard "$P.mumbai"
jq '.variables.aws_region.value = "eu-west-1"' "$P.mumbai" >"$P.var"
check "PB-06 aws_region variable other than Mumbai refused" fail "variable aws_region is \"eu-west-1\"" -- rguard "$P.var"
jq '.configuration.provider_config.aws.expressions.region = {"constant_value": "us-east-1"}' "$P.mumbai" >"$P.const"
check "PB-06 root provider with another constant region refused" fail "provider aws: region us-east-1 is not ap-south-1" -- rguard "$P.const"
jq 'del(.configuration.provider_config.aws.expressions.region)' "$P.mumbai" >"$P.noreg"
check "PB-06 root provider without a region (environment fallback) refused" fail "provider aws: region unset is not ap-south-1" -- rguard "$P.noreg"
jq 'del(.configuration)' "$P.mumbai" >"$P.nocfg"
check "PB-06 AWS resources without a provider configuration refused" fail "no AWS provider configuration" -- rguard "$P.nocfg"
jq '.resource_changes[0].change.after_unknown.region = true' "$P.mumbai" >"$P.unk"
check "PB-06 region unknown at plan time refused" fail "region not known at plan time" -- rguard "$P.unk"
jq '.resource_changes[0].change.actions = ["forget"]' "$P.mumbai" >"$P.forget"
check "a forget (removed block) is refused" fail "plan forget" -- rguard "$P.forget"

D="$(good_account)"
rm "$D/ec2_describe-availability-zones@us-east-1.fail"
echo '{"AvailabilityZones":[{"ZoneName":"us-east-1a"}]}' >"$D/ec2_describe-availability-zones@us-east-1.json"
check "PB-06 owner session that can act outside Mumbai is refused" fail "can act in us-east-1" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; require_region_guarded_session"
D="$(good_account)"
echo "Could not connect to the endpoint URL" >"$D/ec2_describe-availability-zones@us-east-1.fail"
check "PB-06 unproven region guard fails closed" fail "cannot prove the session is confined" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; require_region_guarded_session"
check "PB-06 region-guarded session passes" ok "confined to ap-south-1 by IAM" -- env AWS_STUB_DIR="$(good_account)" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; require_region_guarded_session"
D="$(good_account)"
rm "$D/ec2_describe-availability-zones@us-east-1.fail"
echo '{"AvailabilityZones":[]}' >"$D/ec2_describe-availability-zones@us-east-1.json"
R="$TMP/rev.region" && reviewed "$R" '.'
TFD="$(tf_stub "$P.ok")"
check "PB-06 apply refused with a session that is not region-guarded" fail "can act in us-east-1" -- apply_reviewed "$R" "$TFD" "$D"
absent "  ... before terraform runs" "^(init|apply)" "$(cat "$TFD/calls.log" 2>/dev/null || true)"

SP="$INFRA/config/bootstrap-session-policy.json"
VEDA_INVENTORY_ACTIONS="$(bash -c "source '$INFRA/scripts/lib.sh'; echo \"\$VEDA_INVENTORY_ACTIONS\"")"
BOUNDARY_GLOBALS="$(sed -n '/global_actions = \[/,/\]/p' "$INFRA/terraform/bootstrap/main.tf" | grep -oE '"[a-z-]+:[A-Za-z*]+"' | tr -d '"' | sort)"
{ printf '%s\n' "$BOUNDARY_GLOBALS"; tr ' ' '\n' <<<"$VEDA_INVENTORY_ACTIONS"; } | sort >"$TMP/sp.want"
jq -r '.Statement[] | select(.Effect == "Deny") | .NotAction[]' "$SP" | sort >"$TMP/sp.got"
check "PB-06 session policy exempts exactly the boundary's global services and the inventory reads" ok "^same$" -- bash -c "diff '$TMP/sp.want' '$TMP/sp.got' && echo same"
check "  ... denies every other action outside ap-south-1" ok '^"ap-south-1"$' -- jq '.Statement[] | select(.Effect == "Deny") | .Condition.StringNotEquals["aws:RequestedRegion"]' "$SP"
absent "  ... the inventory exemptions are read-only" ":(Create|Put|Update|Delete|Run|Start|Attach|Modify|Invoke|Tag)" "$(tr ' ' '\n' <<<"$VEDA_INVENTORY_ACTIONS")"
check "  ... and fits the 2,048-character STS session-policy limit" ok "^fits$" -- bash -c "[[ \$(jq -c . '$SP' | wc -c) -lt 2048 ]] && echo fits"
# CLI operation -> IAM action, for every regional call the inventory makes.
INVENTORY_CALLS='ec2/describe-instances=ec2:DescribeInstances ec2/describe-vpcs=ec2:DescribeVpcs lambda/list-functions=lambda:ListFunctions rds/describe-db-instances=rds:DescribeDBInstances ecs/list-clusters=ecs:ListClusters secretsmanager/list-secrets=secretsmanager:ListSecrets kms/list-aliases=kms:ListAliases kms/list-keys=kms:ListKeys kms/describe-key=kms:DescribeKey'
calls="$(grep -oE 'aws [a-z0-9]+ [a-z-]+ --region' "$INFRA/scripts/lib.sh" | awk '{print $2"/"$3}' | grep -v '^ec2/describe-availability-zones$' | sort -u)"
uncovered=""
for c in $calls; do
  action=""
  for m in $INVENTORY_CALLS; do [[ "${m%%=*}" == "$c" ]] && action="${m#*=}"; done
  [[ -n "$action" && " $VEDA_INVENTORY_ACTIONS " == *" $action "* ]] || uncovered+="$c "
done
check "  ... and every regional inventory call is exempted ($(wc -l <<<"$calls" | tr -d ' ') calls)" ok "^covered$" -- bash -c "[[ -z '$uncovered' ]] && echo covered || { echo 'uncovered: $uncovered'; exit 1; }"

echo "== PB-10: IAM's own simulation of the rendered boundary is a stop condition"
T="$(new_tree)"
SIM="$T/infra/scripts/simulate-boundary.sh"
check "PB-10 boundary evaluated by IAM as reviewed passes" ok "matches the review \(7 probes, 1 allowed control\)" -- env AWS_STUB_DIR="$(good_account)" "$SIM" --plan-json "$P.ok" --account $ACCT
D="$(good_account)" && echo s3:CreateBucket >"$D/simulate.allow"
check "PB-10 IAM allowing a bucket outside Mumbai stops the run" fail "S3 bucket outside Mumbai: IAM says allowed, expected explicitDeny" -- env AWS_STUB_DIR="$D" "$SIM" --plan-json "$P.ok" --account $ACCT
D="$(good_account)" && : >"$D/simulate.denyall"
check "PB-10 a simulator that denies everything stops the run" fail "control: a workload role reads EC2 in Mumbai: IAM says explicitDeny, expected allowed" -- env AWS_STUB_DIR="$D" "$SIM" --plan-json "$P.ok" --account $ACCT
D="$(good_account)" && rm "$D/iam_simulate-custom-policy.cmd" && echo "AccessDenied" >"$D/iam_simulate-custom-policy.fail"
check "PB-10 simulation unavailable fails closed" fail "IAM simulation failed" -- env AWS_STUB_DIR="$D" "$SIM" --plan-json "$P.ok" --account $ACCT
jq 'del(.resource_changes[] | select(.address == "aws_iam_policy.boundary"))' "$P.ok" >"$P.nob2"
check "PB-10 a plan without the boundary cannot be simulated and is refused" fail "no known veda-boundary policy" -- env AWS_STUB_DIR="$(good_account)" "$SIM" --plan-json "$P.nob2" --account $ACCT
BS="$T/infra/scripts/bootstrap.sh"
D="$(good_account)" && echo iam:AttachRolePolicy >"$D/simulate.allow"
R="$TMP/rev.sim" && reviewed "$R" '.'
TFD="$(tf_stub "$P.ok")"
check "PB-10 apply stops when IAM disagrees with the review" fail "does not evaluate the rendered boundary as reviewed" -- apply_reviewed "$R" "$TFD" "$D"
absent "  ... and nothing is applied" "^apply " "$(cat "$TFD/calls.log" 2>/dev/null || true)"

echo "== N-03: the account is dedicated to Veda in every region (owner decision: organization member account)"
T="$(new_tree)"
vai() { env AWS_STUB_DIR="$1" bash -c "set -euo pipefail; source '$T/infra/scripts/lib.sh'; verify_account_identity $ACCT"; }
check "N-03 empty account verified across all regions" ok "no foreign resources in any region" -- vai "$(good_account)"
D="$(good_account)"
echo '{"Reservations":[{"Instances":[{"InstanceId":"i-0use1","Tags":[{"Key":"project","Value":"veda-spaces"}]}]}]}' >"$D/ec2_describe-instances@us-east-1.json"
check "N-03 instance outside Mumbai refused even when tagged veda-spaces" fail "instances: i-0use1@us-east-1" -- vai "$D"
D="$(good_account)"
echo '{"Reservations":[{"Instances":[{"InstanceId":"i-0swing","Tags":[{"Key":"Name","Value":"swing-trader-vm"}]}]}]}' >"$D/ec2_describe-instances@eu-west-1.json"
check "N-03 swing-trader-vm in another region refused as another project" fail "named like Aurion or swing-trader-vm \(instances: i-0swing@eu-west-1\)" -- vai "$D"
D="$(good_account)"
echo '{"Roles":[{"RoleName":"aurion-deployer","Path":"/"}]}' >"$D/iam_list-roles.json"
T7="$(man '.allowed_foreign_resources.iam_roles += ["aurion-deployer"]')"
check "N-03 Aurion role refused even when the manifest allows it" fail "named like Aurion or swing-trader-vm \(roles: aurion-deployer\)" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T7/infra/scripts/lib.sh'; verify_account_identity $ACCT"
D="$(good_account)"
echo '{"Vpcs":[{"VpcId":"vpc-0abc"}]}' >"$D/ec2_describe-vpcs@eu-west-1.json"
check "N-03 non-default VPC in another region refused" fail "vpcs: vpc-0abc@eu-west-1" -- vai "$D"
D="$(good_account)"
echo '{"DBInstances":[{"DBInstanceIdentifier":"trades"}]}' >"$D/rds_describe-db-instances@ap-south-1.json"
check "N-03 RDS instance refused" fail "rds instances: trades@ap-south-1" -- vai "$D"
D="$(good_account)"
echo '{"clusterArns":["arn:aws:ecs:us-east-1:111122223333:cluster/c"]}' >"$D/ecs_list-clusters@us-east-1.json"
check "N-03 ECS cluster refused" fail "ecs clusters: arn:aws:ecs:us-east-1:111122223333:cluster/c@us-east-1" -- vai "$D"
D="$(good_account)"
echo '{"SecretList":[{"Name":"broker-api"}]}' >"$D/secretsmanager_list-secrets@eu-west-1.json"
check "N-03 Secrets Manager secret refused" fail "secrets: broker-api@eu-west-1" -- vai "$D"
D="$(good_account)"
echo '{"Keys":[{"KeyId":"k9"}]}' >"$D/kms_list-keys@us-east-1.json"
check "N-03 customer-managed KMS key outside Mumbai refused" fail "kms keys: k9@us-east-1" -- vai "$D"
D="$(good_account)"
echo '{"SAMLProviderList":[{"Arn":"arn:aws:iam::111122223333:saml-provider/corp"}]}' >"$D/iam_list-saml-providers.json"
check "N-01 SAML identity provider refused (the boundary cannot see SAML sessions)" fail "saml providers: arn:aws:iam::111122223333:saml-provider/corp" -- vai "$D"
D="$(good_account)"
echo '{"OpenIDConnectProviderList":[{"Arn":"arn:aws:iam::111122223333:oidc-provider/accounts.google.com"}]}' >"$D/iam_list-open-id-connect-providers.json"
check "N-03 identity provider other than GitHub refused" fail "oidc providers: arn:aws:iam::111122223333:oidc-provider/accounts.google.com" -- vai "$D"
D="$(good_account)"
rm "$D/s3api_head-bucket.json"
echo "An error occurred (404) when calling the HeadBucket operation: Not Found" >"$D/s3api_head-bucket.fail"
echo '{"Buckets":[]}' >"$D/s3api_list-buckets.json"
echo '{"Reservations":[]}' >"$D/ec2_describe-instances@ap-south-1.json"
echo '{"Functions":[]}' >"$D/lambda_list-functions@ap-south-1.json"
echo '{"Keys":[]}' >"$D/kms_list-keys@ap-south-1.json"
check "N-03 before the bootstrap, a squatted veda-* role is foreign" fail "roles: veda-gh-apply" -- vai "$D"
D="$(good_account)"
echo "AccessDenied" >"$D/ec2_describe-regions.fail"
check "N-03 region listing fails closed" fail "cannot list account resources" -- vai "$D"
D="$(good_account)"
echo "AccessDenied" >"$D/rds_describe-db-instances@eu-west-1.fail"
check "N-03 a regional listing fails closed" fail "cannot list account resources" -- vai "$D"
D="$(good_account)"
rm "$D/organizations_describe-organization.json"
echo "An error occurred (AWSOrganizationsNotInUseException) when calling the DescribeOrganization operation: Your account is not a member of an organization." >"$D/organizations_describe-organization.fail"
check "owner decision: a standalone account is refused" fail "cannot read the AWS Organization" -- vai "$D"
D="$(good_account)"
echo '{"Organization":{"Id":"o-otherorg0001","MasterAccountId":"999988887777"}}' >"$D/organizations_describe-organization.json"
check "  ... a member of another organization is refused" fail "belongs to organization o-otherorg0001, the manifest approves o-exampleorg01" -- vai "$D"
D="$(good_account)"
echo '{"Organization":{"Id":"o-exampleorg01","MasterAccountId":"444455556666"}}' >"$D/organizations_describe-organization.json"
check "  ... an organization with another management account is refused" fail "management account is 444455556666" -- vai "$D"
T8="$(man '.management_account_id = "111122223333" | .account_id = "111122223333"')"
D="$(good_account)"
echo '{"Organization":{"Id":"o-exampleorg01","MasterAccountId":"111122223333"}}' >"$D/organizations_describe-organization.json"
check "  ... the management account itself is refused" fail "is the management account" -- env AWS_STUB_DIR="$D" bash -c "set -euo pipefail; source '$T8/infra/scripts/lib.sh'; verify_account_identity $ACCT"
D="$(good_account)"
rm "$D/organizations_describe-organization.json"
echo "AccessDenied" >"$D/organizations_describe-organization.fail"
check "  ... and an unreadable organization fails closed" fail "cannot read the AWS Organization" -- vai "$D"

echo "== PB-09 / N-12: the owner session and owner role"
D="$(good_account)"
echo "{\"Account\":\"$ACCT\",\"Arn\":\"arn:aws:iam::$ACCT:root\"}" >"$D/sts_get-caller-identity.json"
check "PB-09 root user session refused" fail "not an assumed owner role" -- vai "$D"
D="$(good_account)"
echo "{\"Account\":\"$ACCT\",\"Arn\":\"arn:aws:iam::$ACCT:user/alice\"}" >"$D/sts_get-caller-identity.json"
check "PB-09 IAM user session refused" fail "not an assumed owner role" -- vai "$D"
D="$(good_account)"
echo "{\"Account\":\"$ACCT\",\"Arn\":\"arn:aws:sts::$ACCT:assumed-role/SomeOtherAdmin/s\"}" >"$D/sts_get-caller-identity.json"
check "PB-09 session of a role that is not an owner refused" fail "session role SomeOtherAdmin is not in bootstrap_principal_arns" -- vai "$D"
D="$(good_account)"
jq '.Role.MaxSessionDuration = 43200' "$D/iam_get-role.json" >"$D/x" && mv "$D/x" "$D/iam_get-role.json"
check "PB-09 owner role allowing 12-hour sessions refused" fail "allows sessions longer than 3600 seconds" -- vai "$D"
D="$(good_account)"
jq '.Role.AssumeRolePolicyDocument.Statement += [{"Effect":"Allow","Principal":{"Federated":"arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"},"Action":"sts:AssumeRoleWithWebIdentity"}]' "$D/iam_get-role.json" >"$D/x" && mv "$D/x" "$D/iam_get-role.json"
check "N-12 owner role trusted by a web identity refused" fail "is trusted by Federated arn:aws:iam::111122223333:oidc-provider" -- vai "$D"
D="$(good_account)"
jq '.Role.AssumeRolePolicyDocument.Statement[0].Principal.AWS = "arn:aws:iam::999999999999:root"' "$D/iam_get-role.json" >"$D/x" && mv "$D/x" "$D/iam_get-role.json"
check "N-12 owner role trusted by another account refused" fail "is trusted by AWS arn:aws:iam::999999999999:root" -- vai "$D"
D="$(good_account)"
jq '.Role.AssumeRolePolicyDocument.Statement[0].Principal = {"Service":"ec2.amazonaws.com"}' "$D/iam_get-role.json" >"$D/x" && mv "$D/x" "$D/iam_get-role.json"
check "N-12 owner role assumable by a service refused" fail "is trusted by Service ec2.amazonaws.com" -- vai "$D"
D="$(good_account)"
jq '.Role.Arn = "arn:aws:iam::111122223333:role/other/OrganizationAccountAccessRole"' "$D/iam_get-role.json" >"$D/x" && mv "$D/x" "$D/iam_get-role.json"
check "PB-09 owner role at another path refused" fail "owner role OrganizationAccountAccessRole is arn:aws:iam::111122223333:role/other/" -- vai "$D"

echo "== PB-01 / N-11: the repository is the approved one, by name and numeric ID"
T="$(new_tree)"
BS="$T/infra/scripts/bootstrap.sh"
G2="$TMP/ghid.$RANDOM" && cp -R "$GHV" "$G2" && rm -f "$G2/calls.log"
echo '{"id":999,"full_name":"example-org/veda-spaces","private":true}' >"$G2/repos_example-org_veda-spaces.json"
R="$TMP/rev.repoid" && reviewed "$R" '.'
check "PB-01 re-registered repository (same name, other ID) refused" fail "has ID 999, the manifest approves 424242" -- apply_reviewed "$R" "$(tf_stub "$P.ok")" "$(good_account)" "" "$G2"
R="$TMP/rev.repo" && reviewed "$R" '.repository = "example-org/other"'
check "PB-01 plan for a repository the manifest does not approve refused" fail "repository example-org/other is not the one the manifest approves" -- env GITHUB_SHA=c0ffee TF_STUB_DIR="$(tf_stub "$P.ok")" AWS_STUB_DIR="$(good_account)" GH_STUB_DIR="$GHV" \
  "$BS" --mode apply --expected-account-id $ACCT --plan-file "$R/bootstrap.tfplan" --plan-meta "$R/bootstrap-plan.meta.json" --plan-sha256 "$(sha "$R/bootstrap.tfplan")" --yes

echo "== N-05 / PB-08: a plan is made only from a clean checkout (ignored files included)"
git_tree() { # a git checkout of a copy of infra/ with one commit
  local g="$TMP/git.$RANDOM$RANDOM"
  mkdir -p "$g"
  cp -R "$INFRA" "$g/infra"
  rm -rf "$g/infra/terraform/bootstrap/.terraform" "$g/infra/generated"
  cp "$FIXTURE_MANIFEST" "$g/infra/config/staging-account.json"
  git -C "$g" init -q && git -C "$g" add -A && git -C "$g" -c user.name=t -c user.email=t@example.invalid commit -qm base
  echo "$g"
}
ct() { bash -c "set -euo pipefail; source '$1/infra/scripts/lib.sh'; require_clean_tree && echo clean"; }
Gt="$(git_tree)"
mkdir -p "$Gt/infra/terraform/bootstrap/.terraform/providers" && : >"$Gt/infra/terraform/bootstrap/generated.auto.tfvars.json" && : >"$Gt/infra/terraform/bootstrap/terraform.tfstate"
check "N-05 clean checkout with Terraform working files and generated inputs passes" ok "^clean$" -- ct "$Gt"
Gt="$(git_tree)" && printf 'provider "aws" {\n  region = "us-east-1"\n}\n' >"$Gt/infra/terraform/bootstrap/override.tf"
check "N-05 ignored override.tf refused" fail "not clean .*infra/terraform/bootstrap/override.tf" -- ct "$Gt"
Gt="$(git_tree)" && : >"$Gt/infra/terraform/bootstrap/x_override.tf"
check "N-05 ignored *_override.tf refused" fail "x_override.tf" -- ct "$Gt"
Gt="$(git_tree)" && : >"$Gt/infra/terraform/bootstrap/terraform.tfvars"
check "N-05 ignored terraform.tfvars refused" fail "terraform.tfvars" -- ct "$Gt"
Gt="$(git_tree)" && : >"$Gt/infra/terraform/bootstrap/extra.tf"
check "N-05 untracked .tf refused" fail "extra.tf" -- ct "$Gt"
Gt="$(git_tree)" && echo "# edit" >>"$Gt/infra/terraform/bootstrap/boundary.tf"
check "N-05 uncommitted change refused" fail "boundary.tf" -- ct "$Gt"
check "N-05 not a git checkout refused" fail "not a git checkout" -- ct "$T"

echo "== N-04 / PB-01: 00-bootstrap runs only from the approved, private repository"
check "N-04 public repository refused before any environment is used" ok 'REPOSITORY_PRIVATE" == "true"' -- printf '%s\n' "$PREFLIGHT"
check "PB-01 repository name and ID checked against the manifest" ok 'GITHUB_REPOSITORY_ID" == "\$\(jq -r .repository_id' -- printf '%s\n' "$PREFLIGHT"
check "PB-01 manifest must be complete" ok "check-manifest.sh --complete" -- printf '%s\n' "$PREFLIGHT"
absent "N-04 discovery output is not uploaded or summarised" "discovered\\.json" "$WFT"
check "N-08 only refs/heads/main may run it" ok 'GITHUB_REF" == "refs/heads/main"' -- printf '%s\n' "$PREFLIGHT"

echo "== PB-03: GitHub setup never drops main's existing protection"
T="$(new_tree)"
GS="$T/infra/scripts/github-setup.sh"
Gp="$TMP/gh.prot" && mkdir -p "$Gp"
echo '{"login":"owner"}' >"$Gp/user.json"
echo '{"id":1001}' >"$Gp/users_owner.json"
echo '{"required_status_checks":{"strict":true,"checks":[{"context":"app","app_id":15368}]},"enforce_admins":{"enabled":true},"required_pull_request_reviews":{"required_approving_review_count":0},"allow_force_pushes":{"enabled":false},"allow_deletions":{"enabled":false}}' \
  >"$Gp/repos_example-org_veda-spaces_branches_main_protection.json"
out_p="$(GH_STUB_DIR="$Gp" "$GS" --repo example-org/veda-spaces 2>&1)"
check "PB-03 compliant main protection is left unchanged" ok "already meets the rules; left unchanged" -- printf '%s\n' "$out_p"
absent "  ... no protection write at all" "branches/main/protection <<<" "$out_p"
jq '.enforce_admins.enabled = false' "$Gp/repos_example-org_veda-spaces_branches_main_protection.json" >"$Gp/x" && mv "$Gp/x" "$Gp/repos_example-org_veda-spaces_branches_main_protection.json"
out_p="$(GH_STUB_DIR="$Gp" "$GS" --repo example-org/veda-spaces 2>&1)"
check "PB-03 non-compliant protection is fixed with its required status checks kept" ok 'branches/main/protection <<< .*"required_status_checks":\{"strict":true,"checks":\[\{"context":"app","app_id":15368\}\]\}.*"enforce_admins":true' -- printf '%s\n' "$out_p"
echo
echo "$PASS passed, ${#FAILED[@]} failed"
if ((${#FAILED[@]})); then
  printf '  failed: %s\n' "${FAILED[@]}"
  exit 1
fi
