#!/usr/bin/env bash
# Auto-discovery for the staging bootstrap (plan §13, AUT-003). READ-ONLY: every AWS, Cloudflare and GitHub
# call below is a Get/List/Describe/Head. Nothing is created or changed.
#
# It first proves the session is confined to ap-south-1 by IAM (PB-06) and is in the approved, dedicated staging
# account (F3, N-03: complete manifest, account name and alias, no production/Aurion name, organization member, a safe owner
# role, and no foreign resource in any region), then that the repository is the approved one by name and ID (PB-01),
# and stops otherwise. Lookups the plan depends on fail closed.
#
#   infra/scripts/discover.sh --expected-account-id 123456789012 [--repo owner/repo]
#
# Optional environment: CF_API_TOKEN (Cloudflare discovery), VEDA_ZONE (default vedaspaces.com),
# VEDA_SKIP_OPERATOR_IP=1 (do not look up this machine's public IP).
#
# Writes (gitignored):
#   infra/generated/discovered.json                          non-secret facts, archived with the run
#   infra/terraform/bootstrap/generated.auto.tfvars.json     variables for the bootstrap root
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

EXPECTED=""
REPO_ARG=""
while (($#)); do
  case "$1" in
    --expected-account-id) EXPECTED="${2:-}"; shift 2 ;;
    --repo) REPO_ARG="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,15p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

require_tools aws jq curl git gh
require_account_id "$EXPECTED"
require_region
require_region_guarded_session
verify_account_identity "$EXPECTED"
mkdir -p "$GENERATED_DIR"

REPO="$(resolve_repo "$REPO_ARG")"
require_repository_identity "$REPO"
log "account $EXPECTED, region $VEDA_REGION, repository $REPO"

# --- AWS ------------------------------------------------------------------------------------------------------
caller_arn="$(aws sts get-caller-identity --query Arn --output text)"

azs="$(aws ec2 describe-availability-zones --filters Name=state,Values=available \
  --query 'AvailabilityZones[].ZoneName' --output json)"

t4g_azs="$(aws ec2 describe-instance-type-offerings --location-type availability-zone \
  --filters Name=instance-type,Values=t4g.medium --query 'InstanceTypeOfferings[].Location' --output json)"
jq -e 'index("ap-south-1a") != null' <<<"$t4g_azs" >/dev/null ||
  warn "t4g.medium is not offered in ap-south-1a; AUT-108 must choose another zone"

ami="$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64 \
  --query Parameter.Value --output text 2>/dev/null || echo "")"

ses="$(aws sesv2 get-account --output json 2>/dev/null |
  jq '{production_access: .ProductionAccessEnabled, sending_enabled: .SendingEnabled, enforcement: .EnforcementStatus}' ||
  echo '{"error":"sesv2 get-account failed"}')"

oidc_arn="$(aws iam list-open-id-connect-providers --query 'OpenIDConnectProviderList[].Arn' --output json |
  jq -r '.[] | select(endswith("/token.actions.githubusercontent.com"))' | head -n1)"
# A provider this bootstrap created (default tags stack=bootstrap, project=veda-spaces) stays managed by it;
# only a provider that predates the bootstrap is passed in as "existing" (passing ours would plan its removal,
# which prevent_destroy and the plan guard also refuse). A failed tag lookup stops discovery (F4).
oidc_managed=false
[[ -z "$oidc_arn" ]] || oidc_managed="$(oidc_provider_managed "$oidc_arn")"
oidc_existing_input="$oidc_arn"
[[ "$oidc_managed" == true ]] && oidc_existing_input=""

bucket="$(state_bucket_name "$EXPECTED")"
# Assigned before comparing: a failed lookup must stop the run, not read as "absent".
bucket_status="$(state_bucket_status "$bucket" "$EXPECTED")"
state_exists=false
[[ "$bucket_status" == exists ]] && state_exists=true

# RR-02: the state key is the one the bucket encrypts with (the alias must agree); a failed lookup stops discovery.
state_key_arn=""
[[ "$state_exists" == true ]] && state_key_arn="$(state_key_from_bucket "$bucket" "$EXPECTED")"

if aws iam get-role --role-name "${VEDA_PREFIX}-gh-apply" >/dev/null 2>&1; then bootstrapped=true; else bootstrapped=false; fi

ebs_default="$(aws ec2 get-ebs-encryption-by-default --query EbsEncryptionByDefault --output text 2>/dev/null || echo unknown)"
account_pab="$(aws s3control get-public-access-block --account-id "$EXPECTED" --query PublicAccessBlockConfiguration \
  --output json 2>/dev/null || echo 'null')"

# --- GitHub ---------------------------------------------------------------------------------------------------
default_branch="main"
if command -v gh >/dev/null 2>&1 && [[ -n "${GH_TOKEN:-}${GITHUB_TOKEN:-}" || -z "${GITHUB_ACTIONS:-}" ]]; then
  default_branch="$(gh repo view "$REPO" --json defaultBranchRef --jq .defaultBranchRef.name 2>/dev/null || echo main)"
fi

# --- Cloudflare (optional) ------------------------------------------------------------------------------------
cf='{"discovered":false}'
if [[ -n "${CF_API_TOKEN:-}" ]]; then
  cf_get() { curl -fsS -H "Authorization: Bearer $CF_API_TOKEN" "https://api.cloudflare.com/client/v4$1"; }
  if zone="$(cf_get "/zones?name=${VEDA_ZONE}" | jq -c '.result[0] // empty')" && [[ -n "$zone" ]]; then
    zone_id="$(jq -r .id <<<"$zone")"
    # Every page, so a large zone cannot hide a collision (F13).
    records='[]'
    page=1
    while :; do
      resp="$(cf_get "/zones/${zone_id}/dns_records?per_page=100&page=${page}")"
      records="$(jq -c --argjson acc "$records" '$acc + [.result[] | {name, type}]' <<<"$resp")"
      (("$(jq -r '.result_info.total_pages // 1' <<<"$resp")" > page)) || break
      page=$((page + 1))
    done
    # Names the staging stacks will create must not exist yet; the live-site names must.
    planned='["api-staging","app-staging","staging","bounce.staging","_dmarc.staging"]'
    cf="$(jq -n --argjson z "$zone" --argjson r "$records" --argjson p "$planned" --arg zone "$VEDA_ZONE" '
      def fq($n): if $n == "@" then $zone else "\($n).\($zone)" end;
      {
        discovered: true,
        zone: $zone, zone_id: $z.id, account_id: $z.account.id, plan: $z.plan.name, status: $z.status,
        planned_name_collisions: [ $p[] as $n | $r[] | select(.name == fq($n)) ],
        live_site_records: [ $r[] | select(.name == $zone or .name == "www.\($zone)") ]
      }')"
    [[ "$(jq '.planned_name_collisions | length' <<<"$cf")" == "0" ]] ||
      warn "planned staging DNS names already exist in Cloudflare: $(jq -c .planned_name_collisions <<<"$cf")"
  else
    warn "Cloudflare zone $VEDA_ZONE not visible to CF_API_TOKEN"
    cf='{"discovered":false,"error":"zone not visible"}'
  fi
else
  log "CF_API_TOKEN not set: Cloudflare discovery skipped (needed before AUT-201)"
fi

# --- Operator IP (default WAF allowlist entry, D-10) ------------------------------------------------------------
operator_ip=""
operator_ip_source="skipped"
if [[ -z "${VEDA_SKIP_OPERATOR_IP:-}" ]]; then
  operator_ip="$(curl -fsS --max-time 5 https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)"
  operator_ip_source="${GITHUB_ACTIONS:+github-runner (not an operator address)}"
  operator_ip_source="${operator_ip_source:-local-operator}"
fi

jq -n \
  --arg account "$EXPECTED" --arg caller "$caller_arn" --arg region "$VEDA_REGION" --arg repo "$REPO" \
  --arg branch "$default_branch" --argjson azs "$azs" --argjson t4g "$t4g_azs" --arg ami "$ami" \
  --argjson ses "$ses" --arg oidc "$oidc_arn" --argjson oidc_managed "$oidc_managed" --arg bucket "$bucket" --argjson state_exists "$state_exists" \
  --arg state_key "$state_key_arn" --argjson bootstrapped "$bootstrapped" --arg ebs "$ebs_default" \
  --argjson pab "$account_pab" --argjson cf "$cf" --arg ip "$operator_ip" --arg ip_src "$operator_ip_source" \
  --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '
  {
    discovered_at: $at,
    aws: {
      account_id: $account, caller_arn: $caller, region: $region,
      availability_zones: $azs, t4g_medium_zones: $t4g, al2023_arm64_ami: $ami,
      ses: $ses,
      github_oidc_provider_arn: $oidc, github_oidc_provider_managed_by_bootstrap: $oidc_managed,
      state_bucket: $bucket, state_bucket_exists: $state_exists, state_kms_key_arn: $state_key,
      bootstrap_roles_exist: $bootstrapped,
      ebs_encryption_by_default: $ebs, account_public_access_block: $pab
    },
    github: { repository: $repo, default_branch: $branch },
    cloudflare: $cf,
    operator: { public_ip: $ip, source: $ip_src }
  }' >"$GENERATED_DIR/discovered.json"

jq -n --arg account "$EXPECTED" --arg repo "$REPO" --arg oidc "$oidc_existing_input" '
  {
    expected_account_id: $account,
    github_owner: ($repo | split("/")[0]),
    github_repo: ($repo | split("/")[1]),
    existing_github_oidc_provider_arn: $oidc
  }' >"$BOOTSTRAP_DIR/generated.auto.tfvars.json"

log "wrote $GENERATED_DIR/discovered.json and bootstrap/generated.auto.tfvars.json"
jq -c '{state_bucket_exists: .aws.state_bucket_exists, bootstrap_roles_exist: .aws.bootstrap_roles_exist,
        oidc_provider: (.aws.github_oidc_provider_arn != ""), ses: .aws.ses, cloudflare: .cloudflare.discovered}' \
  "$GENERATED_DIR/discovered.json" >&2
