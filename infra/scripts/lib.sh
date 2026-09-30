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

# F3: the account typed at run time must be the one committed in the manifest.
require_approved_account() {
  local expected="$1" approved
  [[ -f "$VEDA_ACCOUNT_MANIFEST" ]] || die "account manifest not found: $VEDA_ACCOUNT_MANIFEST"
  approved="$(manifest_get .account_id)"
  [[ "$approved" =~ ^[0-9]{12}$ ]] ||
    die "no approved staging account in ${VEDA_ACCOUNT_MANIFEST#"$REPO_ROOT"/}: commit account_id and account_name in a reviewed change first (runbook §2)"
  [[ "$expected" == "$approved" ]] ||
    die "account $expected is not the approved staging account ($approved) in ${VEDA_ACCOUNT_MANIFEST#"$REPO_ROOT"/}; refusing"
}

# Refuses to continue unless the active AWS session belongs to the expected (dedicated Veda) account.
require_expected_account() {
  local expected="$1" actual
  actual="$(aws sts get-caller-identity --output json 2>/dev/null | jq -r '.Account // empty')" ||
    die "no usable AWS credentials (aws sts get-caller-identity failed)"
  [[ -n "$actual" ]] || die "no usable AWS credentials (aws sts get-caller-identity failed)"
  [[ "$actual" == "$expected" ]] || die "AWS session is for account $actual, expected $expected; refusing"
}

# F3: prove the session is in the dedicated staging account, not merely in the account whose ID was typed:
# manifest approval, the live account name and alias, a production/Aurion name check, and no resources that
# the bootstrap did not create (unless the manifest lists them). Every lookup fails closed.
verify_account_identity() {
  local expected="$1" name alias want_name want_alias foreign
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

  foreign="$(foreign_resources)" || die "cannot list account resources; refusing"
  [[ -z "$foreign" ]] ||
    die "the account holds resources the bootstrap did not create and the manifest does not allow: $foreign"
  log "account $expected verified: name '$name', alias '${alias:-<none>}', no foreign resources"
}

# Prints "roles: a,b; buckets: c" for resources that are neither Veda's nor allowed by the manifest.
foreign_resources() {
  local allow roles users buckets instances functions out=""
  allow="$(jq -c '.allowed_foreign_resources // {}' "$VEDA_ACCOUNT_MANIFEST")"
  roles="$(aws iam list-roles --output json | jq -r --argjson a "$allow" '
    [.Roles[] | select((.Path | startswith("/aws-service-role/") or startswith("/aws-reserved/")) | not)
      | .RoleName | select(startswith("veda-") | not) | select(. as $n | ($a.iam_roles // []) | index($n) | not)]
    | join(",")')" || return 1
  users="$(aws iam list-users --output json | jq -r --argjson a "$allow" '
    [.Users[].UserName | select(. as $n | ($a.iam_users // []) | index($n) | not)] | join(",")')" || return 1
  buckets="$(aws s3api list-buckets --output json | jq -r --argjson a "$allow" '
    [.Buckets[].Name | select(startswith("veda-") | not) | select(. as $n | ($a.s3_buckets // []) | index($n) | not)]
    | join(",")')" || return 1
  instances="$(aws ec2 describe-instances --filters Name=instance-state-name,Values=pending,running,stopping,stopped \
    --output json | jq -r --argjson a "$allow" '
    [.Reservations[].Instances[]
      | select(([.Tags[]? | select(.Key == "project" and .Value == "veda-spaces")] | length) == 0)
      | .InstanceId | select(. as $n | ($a.ec2_instances // []) | index($n) | not)] | join(",")')" || return 1
  functions="$(aws lambda list-functions --output json | jq -r --argjson a "$allow" '
    [.Functions[].FunctionName | select(startswith("veda-") | not)
      | select(. as $n | ($a.lambda_functions // []) | index($n) | not)] | join(",")')" || return 1
  [[ -n "$roles" ]] && out+="roles: $roles; "
  [[ -n "$users" ]] && out+="users: $users; "
  [[ -n "$buckets" ]] && out+="buckets: $buckets; "
  [[ -n "$instances" ]] && out+="instances: $instances; "
  [[ -n "$functions" ]] && out+="lambda functions: $functions; "
  printf '%s' "${out%; }"
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
