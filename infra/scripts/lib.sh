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
export VEDA_REGION VEDA_PREFIX VEDA_ZONE

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

# Refuses to continue unless the active AWS session belongs to the expected (dedicated Veda) account.
require_expected_account() {
  local expected="$1" actual
  actual="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" ||
    die "no usable AWS credentials (aws sts get-caller-identity failed)"
  [[ "$actual" == "$expected" ]] || die "AWS session is for account $actual, expected $expected; refusing"
}

state_bucket_name() { echo "${VEDA_PREFIX}-tfstate-$1"; }

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
