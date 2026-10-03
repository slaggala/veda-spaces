#!/usr/bin/env bash
# GitHub OIDC session for a staging workflow role (AUT-301). No stored AWS credential exists for these roles.
#
#   infra/scripts/oidc-session.sh --role plan|apply
#
# Requests the job's OIDC token (audience sts.amazonaws.com; the job needs "id-token: write" and the role's protected
# environment), exchanges it for a one-hour session of veda-gh-<role> in the approved account, checks the session is
# that role, and exports it to later steps through $GITHUB_ENV with every value masked. The role ARN comes from the
# reviewed manifest; the repository variable AWS_ROLE_ARN_<ROLE>, when set, must name the same role. The role's trust
# policy (bootstrap, RR-03) admits only repo:<repo>:environment:<that role's environment>.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

ROLE=""
while (($#)); do
  case "$1" in
    --role) ROLE="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,10p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done
[[ "$ROLE" == plan || "$ROLE" == apply ]] || die "--role must be plan or apply"

require_tools aws jq curl
require_region
[[ -n "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" && -n "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" ]] ||
  die "no OIDC token available: the job needs 'permissions: id-token: write' (and is not a fork pull request)"
[[ -n "${GITHUB_ENV:-}" ]] || die "GITHUB_ENV is not set: run inside a GitHub Actions job"

ACCOUNT="$(manifest_get .account_id)"
require_account_id "$ACCOUNT"
ROLE_ARN="arn:aws:iam::$ACCOUNT:role/$VEDA_PREFIX-gh-$ROLE"
upper="$(tr '[:lower:]' '[:upper:]' <<<"$ROLE")"
var="AWS_ROLE_ARN_$upper"
[[ -z "${!var:-}" || "${!var}" == "$ROLE_ARN" ]] ||
  die "$var is ${!var}, the approved account's $ROLE role is $ROLE_ARN; refusing"

token="$(curl -fsS -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
  "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=sts.amazonaws.com" | jq -r '.value // empty')" ||
  die "cannot obtain the OIDC token"
[[ -n "$token" ]] || die "the OIDC token response has no value"

session_name="gh-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}-$ROLE"
creds="$(env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u AWS_SESSION_TOKEN -u AWS_PROFILE \
  aws sts assume-role-with-web-identity --region "$VEDA_REGION" --role-arn "$ROLE_ARN" \
  --role-session-name "$session_name" --web-identity-token "$token" --duration-seconds 3600 --output json)" ||
  die "AssumeRoleWithWebIdentity for $ROLE_ARN failed (the role trusts only its protected environment)"
unset token

key="$(jq -r '.Credentials.AccessKeyId // empty' <<<"$creds")"
secret="$(jq -r '.Credentials.SecretAccessKey // empty' <<<"$creds")"
session="$(jq -r '.Credentials.SessionToken // empty' <<<"$creds")"
[[ "$key" == ASIA* && -n "$secret" && -n "$session" ]] || die "the STS response holds no temporary credentials"
echo "::add-mask::$secret"
echo "::add-mask::$session"

arn="$(AWS_ACCESS_KEY_ID="$key" AWS_SECRET_ACCESS_KEY="$secret" AWS_SESSION_TOKEN="$session" \
  aws sts get-caller-identity --output json | jq -r '.Arn // empty')" || die "the new session cannot call STS"
[[ "$arn" == "arn:aws:sts::$ACCOUNT:assumed-role/$VEDA_PREFIX-gh-$ROLE/$session_name" ]] ||
  die "the session is '$arn', not $VEDA_PREFIX-gh-$ROLE; refusing"

{
  echo "AWS_ACCESS_KEY_ID=$key"
  echo "AWS_SECRET_ACCESS_KEY=$secret"
  echo "AWS_SESSION_TOKEN=$session"
  echo "AWS_REGION=$VEDA_REGION"
  echo "AWS_DEFAULT_REGION=$VEDA_REGION"
} >>"$GITHUB_ENV"
log "OIDC session: $arn (expires $(jq -r '.Credentials.Expiration' <<<"$creds"))"
