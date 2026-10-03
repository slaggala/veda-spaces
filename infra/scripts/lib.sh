# shellcheck shell=bash
# Shared helpers for infra/scripts (AUT-003). Sourced, never executed.

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$INFRA_DIR/.." && pwd)"
GENERATED_DIR="$INFRA_DIR/generated"
BOOTSTRAP_DIR="$INFRA_DIR/terraform/bootstrap"
export INFRA_DIR REPO_ROOT GENERATED_DIR BOOTSTRAP_DIR

VEDA_REGION="ap-south-1"
VEDA_PREFIX="veda"
VEDA_ZONE="${VEDA_ZONE:-vedaspaces.com}"
# The approved account, committed and changed only through a reviewed pull request (F3). The offline tests
# point VEDA_ACCOUNT_MANIFEST at a fixture.
VEDA_ACCOUNT_MANIFEST="${VEDA_ACCOUNT_MANIFEST:-$INFRA_DIR/config/staging-account.json}"
export VEDA_REGION VEDA_PREFIX VEDA_ZONE VEDA_ACCOUNT_MANIFEST

# Account names or aliases that can never be the Veda staging account.
VEDA_FORBIDDEN_ACCOUNT_NAMES='prod|aurion'
# Resources that betray another project in the account (Aurion, the swing-trader VM): refused even if allowed.
VEDA_FORBIDDEN_RESOURCE_NAMES='aurion|swing[-_]?trader'
# PB-06: a region the region-guarded owner session must NOT be able to use (proved by a harmless read being denied).
VEDA_REGION_PROBE="us-east-1"
# The read-only calls the all-region inventory makes (N-03). The bootstrap session policy
# (infra/config/bootstrap-session-policy.json) exempts exactly these, plus the global services, from its region deny.
VEDA_INVENTORY_ACTIONS='ec2:DescribeRegions ec2:DescribeInstances ec2:DescribeVpcs lambda:ListFunctions rds:DescribeDBInstances ecs:ListClusters kms:ListKeys kms:ListAliases kms:DescribeKey secretsmanager:ListSecrets'
export VEDA_FORBIDDEN_RESOURCE_NAMES VEDA_REGION_PROBE VEDA_INVENTORY_ACTIONS

# The GitHub environment each veda-gh-* role is trusted by (RR-03): fixed, and each one protected and verified by
# github-setup.sh (RR-07). Terraform's github_environments validation holds the same mapping.
VEDA_GH_ROLE_ENVIRONMENTS='plan:staging-plan apply:staging-infra deploy:staging evidence:staging-evidence'
# The only workflow whose plan runs an apply may use (RR-05).
VEDA_BOOTSTRAP_WORKFLOW='.github/workflows/00-bootstrap.yml'
export VEDA_GH_ROLE_ENVIRONMENTS VEDA_BOOTSTRAP_WORKFLOW

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
warn() { if [[ -n "${GITHUB_ACTIONS:-}" ]]; then echo "::warning::$*" >&2; else log "WARNING: $*"; fi; }
die() {
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then echo "::error::$*" >&2; else log "ERROR: $*"; fi
  exit 1
}

require_tools() {
  local t missing=()
  for t in "$@"; do command -v "$t" >/dev/null 2>&1 || missing+=("$t"); done
  ((${#missing[@]} == 0)) || die "missing tools: ${missing[*]}"
}

require_account_id() {
  [[ "${1:-}" =~ ^[0-9]{12}$ ]] || die "expected account ID must be 12 digits (got '${1:-}')"
}

# The only region this project may use; refuse anything else before any AWS call is made.
require_region() {
  local r="${AWS_REGION:-${AWS_DEFAULT_REGION:-$VEDA_REGION}}"
  [[ "$r" == "$VEDA_REGION" ]] || die "AWS region must be $VEDA_REGION (got $r)"
  export AWS_REGION="$VEDA_REGION" AWS_DEFAULT_REGION="$VEDA_REGION"
}

manifest_get() { jq -r "$1 // empty" "$VEDA_ACCOUNT_MANIFEST"; }

# PB-01: prints one line per problem with the manifest; nothing means valid. "structure" checks the schema and the
# fixed owner decisions (the committed manifest may still hold nulls); "complete" also requires every value a
# bootstrap needs, with no placeholder.
manifest_problems() {
  local mode="$1"
  [[ -f "$VEDA_ACCOUNT_MANIFEST" ]] || { echo "manifest not found: $VEDA_ACCOUNT_MANIFEST"; return 0; }
  jq -r --arg mode "$mode" --arg forbidden "$VEDA_FORBIDDEN_ACCOUNT_NAMES" --arg prefix "$VEDA_PREFIX" '
    def str_or_null: . == null or type == "string";
    def placeholder: type == "string" and (test("[<>]|TODO|CHANGE|REPLACE|EXAMPLE|PLACEHOLDER"; "i") or . == "123456789012" or . == "000000000000");
    [ (if .schema_version != 2 then "schema_version must be 2" else empty end),
      (if .region != "ap-south-1" then "region must be ap-south-1 (Mumbai only)" else empty end),
      # Owner decision (2026-10-02): a member account of the Veda organization, never its management account.
      (if .organizations_mode != "member" then "organizations_mode must be \"member\" (owner decision)" else empty end),
      (if (.organization_id | type) != "string" or (.organization_id | test("^o-[a-z0-9]{10,32}$") | not)
         then "organization_id must be the AWS Organizations ID (o-...)" else empty end),
      (if (.management_account_id | type) != "string" or (.management_account_id | test("^[0-9]{12}$") | not)
         then "management_account_id must be the 12-digit management account ID" else empty end),
      (if .account_id != null and .account_id == .management_account_id
         then "account_id is the management account: Veda staging must be a member account" else empty end),
      (if (.repository | type) != "string" or (.repository | test("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$") | not) then "repository must be owner/repo" else empty end),
      (if (.repository_id | type) != "number" or .repository_id <= 0 then "repository_id must be the numeric GitHub repository ID" else empty end),
      (if (.max_owner_session_seconds | type) != "number" or .max_owner_session_seconds < 900 or .max_owner_session_seconds > 3600
         then "max_owner_session_seconds must be 900-3600" else empty end),
      (if (.manage_account_guardrails | type) != "boolean" then "manage_account_guardrails must be true or false" else empty end),
      (if (.bootstrap_principal_arns | type) != "array" then "bootstrap_principal_arns must be a list" else empty end),
      (if (.allowed_foreign_resources | type) != "object" then "allowed_foreign_resources must be an object" else empty end),
      (if (.account_id | str_or_null) and (.account_name | str_or_null) and (.account_alias | str_or_null) | not
         then "account_id, account_name and account_alias must be strings or null" else empty end),
      ([.account_id, .account_name, .account_alias, (.bootstrap_principal_arns // [])[]] | map(select(placeholder)) | .[]
         | "placeholder value \(tojson)"),
      (if $mode == "complete" then
        (.account_id as $a
         | (if ($a | type) != "string" or ($a | test("^[0-9]{12}$") | not) then "account_id must be the 12-digit account ID" else empty end),
           (if (.account_name | type) != "string" or .account_name == "" then "account_name is not set" else empty end),
           (if (.account_alias | type) != "string" or (.account_alias | test("^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])$") | not)
              then "account_alias must be set (3-63 lowercase letters, digits, hyphens)" else empty end),
           ([.account_name, .account_alias] | map(select(type == "string" and test($forbidden; "i"))) | .[]
              | "\(tojson) looks like production or Aurion"),
           (if ((.bootstrap_principal_arns // []) | length) == 0 then "bootstrap_principal_arns is empty" else empty end),
           ((.bootstrap_principal_arns // [])[] | select((type != "string")
              or (test("^arn:aws:iam::" + ($a | tostring) + ":role/[A-Za-z0-9+=,.@_/-]+$") | not)
              or test(":role/(.*/)?" + $prefix + "-"))
            | "bootstrap_principal_arns: \(tojson) is not an exact, non-\($prefix) IAM role ARN in account \($a)"),
           # The owner role is not a Veda resource: the all-region inventory must be told it may exist.
           ((.allowed_foreign_resources.iam_roles // []) as $allowed
            | (.bootstrap_principal_arns // [])[] | select(type == "string") | (split("/") | last) as $n
            | select(($allowed | index($n)) == null)
            | "owner role \($n) is not listed in allowed_foreign_resources.iam_roles"))
       else empty end)
    ] | .[]' "$VEDA_ACCOUNT_MANIFEST" 2>/dev/null || echo "manifest is not valid JSON"
}

# F3: the account typed at run time must be the one committed in the manifest, and the manifest complete (PB-01).
require_approved_account() {
  local expected="$1" approved problems
  [[ -f "$VEDA_ACCOUNT_MANIFEST" ]] || die "account manifest not found: $VEDA_ACCOUNT_MANIFEST"
  approved="$(manifest_get .account_id)"
  [[ "$approved" =~ ^[0-9]{12}$ ]] ||
    die "no approved staging account in ${VEDA_ACCOUNT_MANIFEST#"$REPO_ROOT"/}: commit account_id and account_name in a reviewed change first (runbook §2)"
  [[ "$expected" == "$approved" ]] ||
    die "account $expected is not the approved staging account ($approved) in ${VEDA_ACCOUNT_MANIFEST#"$REPO_ROOT"/}; refusing"
  problems="$(manifest_problems complete)"
  [[ -z "$problems" ]] || die "the account manifest is not complete: $(tr '\n' ';' <<<"$problems" | sed 's/;$//'); refusing"
}

# PB-01 / N-11: the repository is the one the manifest approves, by name and by its numeric ID (a deleted and
# re-registered repository of the same name has another ID). Needs gh; every lookup fails closed.
require_repository_identity() {
  local repo="$1" want_repo want_id id
  want_repo="$(manifest_get .repository)"
  want_id="$(manifest_get .repository_id)"
  [[ "$repo" == "$want_repo" ]] || die "repository $repo is not the one the manifest approves ($want_repo); refusing"
  id="$(gh api "repos/$repo" --jq .id 2>/dev/null)" || die "cannot read the ID of repository $repo; refusing"
  [[ -n "$id" && "$id" == "$want_id" ]] ||
    die "repository $repo has ID ${id:-?}, the manifest approves $want_id (renamed, deleted or re-registered?); refusing"
}

# PB-06: the owner session must be confined to ap-south-1 by IAM (the region-deny session policy in
# infra/config/bootstrap-session-policy.json). Proof: a harmless read in another region must be DENIED. A success
# means the session could deploy anywhere; any other error proves nothing. Both stop the run.
require_region_guarded_session() {
  local err
  if err="$(aws ec2 describe-availability-zones --region "$VEDA_REGION_PROBE" --output json 2>&1 >/dev/null)"; then
    die "this AWS session can act in $VEDA_REGION_PROBE: start it with the region-deny session policy (infra/config/bootstrap-session-policy.json, runbook §3); refusing"
  fi
  grep -Eq 'UnauthorizedOperation|AccessDenied|explicit deny' <<<"$err" ||
    die "cannot prove the session is confined to $VEDA_REGION ($VEDA_REGION_PROBE probe: ${err:-no detail}); refusing"
  log "session confined to $VEDA_REGION by IAM ($VEDA_REGION_PROBE denied)"
}

# Refuses to continue unless the active AWS session belongs to the expected (dedicated Veda) account.
require_expected_account() {
  local expected="$1" actual
  actual="$(aws sts get-caller-identity --output json 2>/dev/null | jq -r '.Account // empty')" ||
    die "no usable AWS credentials (aws sts get-caller-identity failed)"
  [[ -n "$actual" ]] || die "no usable AWS credentials (aws sts get-caller-identity failed)"
  [[ "$actual" == "$expected" ]] || die "AWS session is for account $actual, expected $expected; refusing"
}

# F3, N-03: prove the session is in the dedicated staging account, not merely in the account whose ID was typed:
# a complete manifest, the live account name and alias, no production/Aurion name, membership of the approved
# AWS organization as a member (not management) account (owner decision), an owner role that is safe to hold the state (PB-09), and an all-region inventory with nothing the
# bootstrap did not create (unless the manifest lists it). Every lookup fails closed.
verify_account_identity() {
  local expected="$1" name alias want_name want_alias bucket_status state_exists=false inventory foreign forbidden
  require_approved_account "$expected"
  require_expected_account "$expected"

  name="$(aws account get-account-information --output json | jq -r '.AccountName // empty')" ||
    die "cannot read the account name (account:GetAccountInformation); refusing"
  want_name="$(manifest_get .account_name)"
  [[ -n "$want_name" ]] || die "account_name is not set in the account manifest; refusing"
  [[ "$name" == "$want_name" ]] || die "account name is '$name', the manifest approves '$want_name'; refusing"

  alias="$(aws iam list-account-aliases --output json | jq -r '.AccountAliases[0] // empty')" ||
    die "cannot read the account alias (iam:ListAccountAliases); refusing"
  want_alias="$(manifest_get .account_alias)"
  [[ "$alias" == "$want_alias" ]] ||
    die "account alias is '${alias:-<none>}', the manifest approves '${want_alias:-<none>}'; refusing"

  if printf '%s\n%s\n' "$name" "$alias" | grep -Eiq "$VEDA_FORBIDDEN_ACCOUNT_NAMES"; then
    die "account '$name' (alias '${alias:-<none>}') looks like production or Aurion; refusing"
  fi

  require_organization_member "$expected"
  require_owner_session "$expected"

  # Assigned before comparing: a failed lookup must stop the run, not read as "absent".
  bucket_status="$(state_bucket_status "$(state_bucket_name "$expected")" "$expected")" || die "cannot read the state bucket; refusing"
  if [[ "$bucket_status" == exists ]]; then state_exists=true; fi
  inventory="$(account_inventory)" || die "cannot list account resources; refusing"
  forbidden="$(jq -r --arg re "$VEDA_FORBIDDEN_RESOURCE_NAMES" '[.[] | select(([.id, .name] | join(" ")) | test($re; "i"))]
    | group_by(.kind) | map("\(.[0].kind): " + (map(.id + (if .region == "global" then "" else "@" + .region end)) | join(","))) | join("; ")' <<<"$inventory")"
  [[ -z "$forbidden" ]] || die "the account holds resources named like Aurion or swing-trader-vm ($forbidden); it is not the dedicated Veda account; refusing"
  foreign="$(foreign_resources "$inventory" "$state_exists")" || die "cannot evaluate account resources; refusing"
  [[ -z "$foreign" ]] ||
    die "the account holds resources the bootstrap did not create and the manifest does not allow: $foreign"
  log "account $expected verified: name '$name', alias '${alias:-<none>}', member of $(manifest_get .organization_id), owner session, no foreign resources in any region"
}

# Owner decision (2026-10-02): the account is a member of exactly the approved organization, and is not its
# management account (SCPs do not apply to the management account). Fails closed on any lookup error.
require_organization_member() {
  local expected="$1" org want_org want_mgmt
  org="$(aws organizations describe-organization --output json 2>&1)" ||
    die "cannot read the AWS Organization of this account (${org:-no detail}); the manifest approves a member account; refusing"
  want_org="$(manifest_get .organization_id)"
  want_mgmt="$(manifest_get .management_account_id)"
  [[ "$(jq -r '.Organization.Id // empty' <<<"$org")" == "$want_org" ]] ||
    die "the account belongs to organization $(jq -r '.Organization.Id // "?"' <<<"$org"), the manifest approves $want_org; refusing"
  [[ "$(jq -r '.Organization.MasterAccountId // empty' <<<"$org")" == "$want_mgmt" ]] ||
    die "the organization's management account is $(jq -r '.Organization.MasterAccountId // "?"' <<<"$org"), the manifest approves $want_mgmt; refusing"
  [[ "$expected" != "$want_mgmt" ]] || die "account $expected is the management account; Veda staging must be a member account; refusing"
}

# PB-09 / N-12: the session is one of the manifest's owner roles (not the root user, not an IAM user), and every owner
# role is safe to hold the bootstrap state: at its exact ARN, sessions of at most max_owner_session_seconds, and a
# trust policy that admits only principals of this account (no identity provider, service, other account or "*").
require_owner_session() {
  local expected="$1" caller role_name max arn want role bad
  caller="$(aws sts get-caller-identity --output json | jq -r '.Arn // empty')" || die "cannot read the caller identity; refusing"
  [[ "$caller" =~ ^arn:aws[a-z-]*:sts::${expected}:assumed-role/([^/]+)/.+$ ]] ||
    die "the session is $caller, not an assumed owner role (root and IAM users may not run the bootstrap); refusing"
  role_name="${BASH_REMATCH[1]}"
  max="$(manifest_get .max_owner_session_seconds)"
  for want in $(jq -r '.bootstrap_principal_arns[]' "$VEDA_ACCOUNT_MANIFEST"); do
    role="$(aws iam get-role --role-name "${want##*/}" --output json)" || die "cannot read owner role ${want##*/}; refusing"
    arn="$(jq -r '.Role.Arn // empty' <<<"$role")"
    [[ "$arn" == "$want" ]] || die "owner role ${want##*/} is $arn, the manifest names $want; refusing"
    jq -e --argjson max "$max" '.Role.MaxSessionDuration <= $max' <<<"$role" >/dev/null ||
      die "owner role $want allows sessions longer than $max seconds; set its maximum session duration to $max or less; refusing"
    bad="$(jq -r --arg acct "$expected" '
      (.Role.AssumeRolePolicyDocument | if type == "string" then fromjson else . end).Statement
      | (if type == "array" then . else [.] end)[] | select(.Effect == "Allow")
      | if .NotPrincipal then "NotPrincipal"
        elif .Principal == "*" then "*"
        else (.Principal // {}) | to_entries[] | .key as $k | (.value | if type == "array" then .[] else . end)
          | select($k != "AWS" or (. != $acct and (test("^arn:aws[a-z-]*:iam::" + $acct + ":") | not)))
          | "\($k) \(.)" end' <<<"$role")" || die "cannot read the trust policy of owner role $want; refusing"
    [[ -z "$bad" ]] || die "owner role $want is trusted by $(tr '\n' ',' <<<"$bad" | sed 's/,$//'): only principals of this account may assume it; refusing"
  done
  jq -e --arg n "$role_name" '[.bootstrap_principal_arns[] | split("/") | last] | index($n) != null' "$VEDA_ACCOUNT_MANIFEST" >/dev/null ||
    die "the session role $role_name is not in bootstrap_principal_arns; refusing"
}

# N-03: every resource of the kinds a workload or another project would leave, in every enabled region (regional
# kinds) or account-wide (IAM, S3). JSON array of {kind, id, region, name, veda}. Read-only; fails on any lookup error.
account_inventory() {
  local out j regions r keys k meta
  j="$(aws iam list-roles --output json)" || return 1
  out="$(jq -c '[.Roles[] | select((.Path | startswith("/aws-service-role/") or startswith("/aws-reserved/")) | not)
    | {kind: "roles", id: .RoleName, region: "global", name: .RoleName, veda: false}]' <<<"$j")" || return 1
  j="$(aws iam list-users --output json)" || return 1
  out="$(jq -c --argjson o "$out" '$o + [.Users[] | {kind: "users", id: .UserName, region: "global", name: .UserName, veda: false}]' <<<"$j")" || return 1
  j="$(aws iam list-open-id-connect-providers --output json)" || return 1
  out="$(jq -c --argjson o "$out" '$o + [.OpenIDConnectProviderList[] | {kind: "oidc providers", id: .Arn, region: "global", name: .Arn, veda: false}]' <<<"$j")" || return 1
  j="$(aws iam list-saml-providers --output json)" || return 1
  out="$(jq -c --argjson o "$out" '$o + [.SAMLProviderList[] | {kind: "saml providers", id: .Arn, region: "global", name: .Arn, veda: false}]' <<<"$j")" || return 1
  j="$(aws s3api list-buckets --output json)" || return 1
  out="$(jq -c --argjson o "$out" '$o + [.Buckets[] | {kind: "buckets", id: .Name, region: "global", name: .Name, veda: false}]' <<<"$j")" || return 1
  regions="$(aws ec2 describe-regions --output json | jq -r '.Regions[].RegionName')" || return 1
  [[ -n "$regions" ]] || return 1
  for r in $regions; do
    j="$(aws ec2 describe-instances --region "$r" --filters Name=instance-state-name,Values=pending,running,stopping,stopped --output json)" || return 1
    out="$(jq -c --argjson o "$out" --arg r "$r" '$o + [.Reservations[].Instances[] | {kind: "instances", id: .InstanceId, region: $r,
      name: ([.Tags[]? | .Value] | join(" ")), veda: ([.Tags[]? | select(.Key == "project" and .Value == "veda-spaces")] | length > 0)}]' <<<"$j")" || return 1
    j="$(aws ec2 describe-vpcs --region "$r" --filters Name=is-default,Values=false --output json)" || return 1
    out="$(jq -c --argjson o "$out" --arg r "$r" '$o + [.Vpcs[] | {kind: "vpcs", id: .VpcId, region: $r,
      name: ([.Tags[]? | .Value] | join(" ")), veda: ([.Tags[]? | select(.Key == "project" and .Value == "veda-spaces")] | length > 0)}]' <<<"$j")" || return 1
    j="$(aws lambda list-functions --region "$r" --output json)" || return 1
    out="$(jq -c --argjson o "$out" --arg r "$r" '$o + [.Functions[] | {kind: "lambda functions", id: .FunctionName, region: $r, name: .FunctionName, veda: false}]' <<<"$j")" || return 1
    j="$(aws rds describe-db-instances --region "$r" --output json)" || return 1
    out="$(jq -c --argjson o "$out" --arg r "$r" '$o + [.DBInstances[] | {kind: "rds instances", id: .DBInstanceIdentifier, region: $r, name: .DBInstanceIdentifier, veda: false}]' <<<"$j")" || return 1
    j="$(aws ecs list-clusters --region "$r" --output json)" || return 1
    out="$(jq -c --argjson o "$out" --arg r "$r" '$o + [.clusterArns[] | {kind: "ecs clusters", id: ., region: $r, name: ., veda: false}]' <<<"$j")" || return 1
    j="$(aws secretsmanager list-secrets --region "$r" --output json)" || return 1
    out="$(jq -c --argjson o "$out" --arg r "$r" '$o + [.SecretList[] | {kind: "secrets", id: .Name, region: $r, name: .Name, veda: false}]' <<<"$j")" || return 1
    # Customer-managed keys only (AWS-managed keys come with the services); a Veda key carries an alias/veda-* alias.
    j="$(aws kms list-aliases --region "$r" --output json)" || return 1
    keys="$(aws kms list-keys --region "$r" --output json | jq -r '.Keys[].KeyId')" || return 1
    for k in $keys; do
      meta="$(aws kms describe-key --region "$r" --key-id "$k" --output json)" || return 1
      out="$(jq -c --argjson o "$out" --arg r "$r" --arg k "$k" --argjson aliases "$j" '
        .KeyMetadata as $m | $o + (if $m.KeyManager == "CUSTOMER" and ($m.KeyState | test("^Pending.*Deletion$") | not)
          then [{kind: "kms keys", id: $k, region: $r,
                 name: ([$aliases.Aliases[] | select(.TargetKeyId == $k) | .AliasName] | join(" ")),
                 veda: ([$aliases.Aliases[] | select(.TargetKeyId == $k and (.AliasName | startswith("alias/veda-")))] | length > 0)}]
          else [] end)' <<<"$meta")" || return 1
    done
  done
  echo "$out"
}

# Prints "roles: a,b; instances: i-1@us-east-1" for inventoried resources that are neither Veda's nor allowed by the
# manifest. Nothing may exist outside ap-south-1 except account-wide IAM and S3 entries. Before the bootstrap (no
# state bucket yet) no veda-* resource may exist at all: a squatted name is not ours.
foreign_resources() {
  local inventory="$1" state_exists="$2" allow
  allow="$(jq -c '.allowed_foreign_resources // {}' "$VEDA_ACCOUNT_MANIFEST")" || return 1
  jq -r --argjson a "$allow" --argjson ours "$state_exists" --arg home "$VEDA_REGION" --arg prefix "$VEDA_PREFIX-" '
    def allowed($list): . as $id | ($a[$list] // []) | index($id) != null;
    [ .[] | select(
        if .kind == "roles" then (.id | allowed("iam_roles")) or ($ours and (.id | startswith($prefix)))
        elif .kind == "users" then (.id | allowed("iam_users"))
        elif .kind == "oidc providers" then (.id | endswith(":oidc-provider/token.actions.githubusercontent.com"))
        elif .kind == "saml providers" then (.id | allowed("saml_providers"))
        elif .kind == "buckets" then (.id | allowed("s3_buckets")) or ($ours and (.id | startswith($prefix)))
        elif .kind == "instances" then (.id | allowed("ec2_instances")) or ($ours and .region == $home and .veda)
        elif .kind == "vpcs" then $ours and .region == $home and .veda
        elif .kind == "lambda functions" then (.id | allowed("lambda_functions")) or ($ours and .region == $home and (.id | startswith($prefix)))
        elif .kind == "kms keys" then $ours and .region == $home and .veda
        else false end | not) ]
    | group_by(.kind) | map("\(.[0].kind): " + (map(.id + (if .region == "global" then "" else "@" + .region end)) | join(",")))
    | join("; ")' <<<"$inventory"
}

# F4: whether the GitHub OIDC provider was created by this bootstrap (tags stack=bootstrap, project=veda-spaces).
# A failed lookup stops the run: guessing "no" would pass our own provider in as existing.
oidc_provider_managed() {
  local arn="$1" tags
  tags="$(aws iam list-open-id-connect-provider-tags --open-id-connect-provider-arn "$arn" --output json)" ||
    die "cannot read the tags of $arn; refusing to guess whether the bootstrap manages it"
  if jq -e '[.Tags[]? | "\(.Key)=\(.Value)"] | (index("stack=bootstrap") != null and index("project=veda-spaces") != null)' \
    <<<"$tags" >/dev/null; then
    echo true
  else
    echo false
  fi
}

# F11: "exists" (ours), "absent" (404), anything else stops the run. --expected-bucket-owner turns a bucket of
# the same name in another account into a 403 instead of a silent "absent".
state_bucket_status() {
  local bucket="$1" account="$2" err
  if err="$(aws s3api head-bucket --bucket "$bucket" --expected-bucket-owner "$account" 2>&1 >/dev/null)"; then
    echo exists
  elif grep -Eq '\(404\)|Not Found|NoSuchBucket' <<<"$err"; then
    echo absent
  else
    die "cannot tell whether s3://$bucket exists in $account (${err:-no detail}): the name may be taken by another account, or the session lacks s3:ListBucket"
  fi
}

state_bucket_name() { echo "${VEDA_PREFIX}-tfstate-$1"; }

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{print $1}'
}

# RR-07: the environments the bootstrap relies on (bootstrap, and the one each role trusts) must exist with required
# reviewers, no admin bypass and the main-only branch policy, and main must be protected. Fails closed: a missing
# environment, an API error or no GitHub access stops the run.
require_github_protection() {
  "$INFRA_DIR/scripts/github-setup.sh" --repo "$1" --verify-environments ||
    die "GitHub environment protection is a prerequisite of apply and could not be verified for $1; refusing (make -C infra github-environments APPLY=1)"
}

# Policies compare equal after the normalisation AWS applies when it stores them (one-element arrays become
# scalars, element order, {"AWS":"*"} for "*").
canonical_policy() {
  jq -S 'walk(if type == "array" then (sort | if length == 1 then .[0] else . end)
              elif type == "object" and .Principal == {"AWS": "*"} then .Principal = "*" else . end)'
}
same_policy() { [[ "$(canonical_policy <<<"$1")" == "$(canonical_policy <<<"$2")" ]]; }

# RR-02: the state key is the one the state bucket encrypts with (its default-encryption rule), not whatever an
# alias points at. The alias must agree, the key must be this account's, enabled and customer-managed.
state_key_from_bucket() {
  local bucket="$1" account="$2" enc key meta
  enc="$(aws s3api get-bucket-encryption --bucket "$bucket" --expected-bucket-owner "$account" --output json)" ||
    die "cannot read the default encryption of s3://$bucket; refusing"
  key="$(jq -r '[.ServerSideEncryptionConfiguration.Rules[]?.ApplyServerSideEncryptionByDefault | select(.SSEAlgorithm == "aws:kms") | .KMSMasterKeyID] | if length == 1 then .[0] else empty end' <<<"$enc")"
  [[ "$key" =~ ^arn:aws[a-z-]*:kms:${VEDA_REGION}:${account}:key/[0-9a-f-]+$ ]] ||
    die "s3://$bucket is not encrypted with exactly one KMS key of account $account (got '${key:-none}'); refusing"
  meta="$(aws kms describe-key --key-id "$key" --output json)" || die "cannot describe the state key $key; refusing"
  jq -e '.KeyMetadata | .KeyState == "Enabled" and .KeyManager == "CUSTOMER"' <<<"$meta" >/dev/null ||
    die "state key $key is not an enabled customer-managed key; refusing"
  [[ "$(aws kms describe-key --key-id "alias/${VEDA_PREFIX}-tfstate" --output json | jq -r '.KeyMetadata.Arn // empty')" == "$key" ]] ||
    die "alias/${VEDA_PREFIX}-tfstate does not point at the key s3://$bucket encrypts with ($key); refusing"
  echo "$key"
}

# RR-01/RR-02: after an apply, the live protections must be exactly the reviewed ones: the bucket's policy and
# default encryption (state key, no S3 Bucket Key), and the key's policy and rotation. $3 is `terraform output -json`.
verify_state_protection() {
  local bucket="$1" account="$2" outputs="$3" key want live problems=()
  key="$(state_key_from_bucket "$bucket" "$account")"
  [[ "$key" == "$(jq -r '.state_kms_key_arn.value' <<<"$outputs")" ]] || problems+=("bucket encrypts with $key, not the state key")
  aws s3api get-bucket-encryption --bucket "$bucket" --expected-bucket-owner "$account" --output json |
    jq -e '[.ServerSideEncryptionConfiguration.Rules[]? | .BucketKeyEnabled // false] | all(. == false)' >/dev/null ||
    problems+=("S3 Bucket Key enabled: the key policy could not tell bootstrap/* from staging/*")
  want="$(jq -r '.policy_documents.value.state_bucket' <<<"$outputs")"
  live="$(aws s3api get-bucket-policy --bucket "$bucket" --expected-bucket-owner "$account" --output json | jq -r '.Policy // empty')" ||
    die "cannot read the policy of s3://$bucket; refusing"
  same_policy "$live" "$want" || problems+=("bucket policy differs from the reviewed plan")
  want="$(jq -r '.policy_documents.value.state_key' <<<"$outputs")"
  live="$(aws kms get-key-policy --key-id "$key" --policy-name default --output json | jq -r '.Policy // empty')" ||
    die "cannot read the policy of $key; refusing"
  same_policy "$live" "$want" || problems+=("key policy differs from the reviewed plan")
  aws kms get-key-rotation-status --key-id "$key" --output json | jq -e '.KeyRotationEnabled == true' >/dev/null ||
    problems+=("key rotation is off")
  if ((${#problems[@]})); then
    for p in "${problems[@]}"; do log "STATE PROTECTION: $p"; done
    die "the live protections of s3://$bucket and its key are not the reviewed ones; do not use this state until an owner has investigated"
  fi
  log "state protection verified: bucket and key policies as reviewed, key $key, no Bucket Key, rotation on"
}

# N-05 / PB-08: a plan is made only from a clean checkout of a commit. Tracked changes, untracked files and IGNORED
# files (override.tf, *_override.tf, terraform.tfvars, *.auto.tfvars other than the generated one) in the paths the
# plan reads all stop it; only Terraform working files and what the scripts themselves generate are tolerated.
require_clean_tree() {
  local status problems
  git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
    die "not a git checkout: a plan must be made from a reviewed commit; refusing"
  status="$(git -C "$REPO_ROOT" status --porcelain --ignored --untracked-files=all -- \
    infra/terraform/bootstrap infra/config infra/scripts .github/workflows)" || die "cannot read the git status; refusing"
  problems="$(grep -vE '^!! infra/terraform/bootstrap/(\.terraform/.*|\.terraform/|generated\.auto\.tfvars\.json|backend_s3\.tf|terraform\.tfstate|terraform\.tfstate\.backup|\.terraform\.tfstate\.lock\.info)$' <<<"$status" || true)"
  [[ -z "$problems" ]] ||
    die "the checkout is not clean (uncommitted, untracked or ignored files the plan could read): $(tr '\n' ';' <<<"$problems" | sed 's/;$//'); refusing"
}

# The commit being run: GITHUB_SHA in Actions, HEAD locally.
current_commit() { echo "${GITHUB_SHA:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"; }

# "owner/repo" from --repo, GITHUB_REPOSITORY, gh, or the origin remote, in that order.
resolve_repo() {
  local repo="${1:-${GITHUB_REPOSITORY:-}}"
  if [[ -z "$repo" ]] && command -v gh >/dev/null 2>&1; then
    repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
  fi
  if [[ -z "$repo" ]]; then
    repo="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null | sed -E 's#(git@|https://)github.com[:/]##; s#\.git$##')"
  fi
  [[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "cannot resolve GitHub repository (owner/repo); pass --repo"
  echo "$repo"
}
