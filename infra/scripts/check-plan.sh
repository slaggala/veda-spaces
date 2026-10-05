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
#   - creates a budget action (it would change the account automatically), or a budget (AUT-112) that is not named
#     <prefix>-*, is for another account or a billing view, has no known limit, alerts no one, or notifies an SNS
#     topic that is unknown at plan time or outside the account and ap-south-1. Budgets is a global service: a budget
#     has no region;
#   - breaks the staging network model A (AUT-101, owner decision N1): any security-group inbound rule; outbound rules
#     other than TCP 443, or TCP/UDP 7844 to a range narrower than 0.0.0.0/0 (the tunnel); IPv6 rules or ranges; a NACL
#     rule allowing inbound below port 1024 or all protocols, or any allow rule in the default NACL; rules in the
#     default security group or routes in the default route table; a subnet that assigns public or IPv6 addresses; a
#     VPC with IPv6; NAT gateways, elastic IPs, peering, VPN, Direct Connect, transit gateways, client VPN, egress-only
#     gateways, main-route-table associations, Instance Connect endpoints, VPC Lattice, Network Manager, Direct
#     Connect, Route 53 Resolver endpoints; inline routes, or an aws_route that sets anything but an IPv4 destination
#     and a gateway, or targets the main or default route table (read from the configuration, which sees references
#     unknown in the plan); a security-group rule attached to the default security group; an instance without a subnet
#     (it would land in the default VPC); a flow-log role the flow-logs service may assume for another account; a VPC
#     endpoint other than the S3 gateway, or an S3 endpoint whose policy is unknown, the AWS default (full access),
#     uses Not* elements, or allows S3 beyond the account's buckets and the named AWS-owned buckets of the region
#     (ECR layers, Amazon Linux 2023 repositories, SSM Agent, SSM documents, Distributor);
#   - creates a KMS key (AUT-102) without rotation, with a deletion window under 30 days, multi-region, not symmetric
#     encrypt/decrypt, with the policy lockout check bypassed, with a policy unknown at plan time, or without a Deny of
#     every caller outside the account (kms:CallerAccount); any replica, external or custom-store key, a separate key
#     policy resource, or an alias outside alias/<prefix>-*;
#   - creates an S3 bucket (AUT-103) not named <prefix>-*, or without, in the same plan and naming it by its name: all
#     four public access blocks, BucketOwnerEnforced ownership, versioning, SSE-KMS and a policy denying plain HTTP
#     (the bootstrap state bucket excepted); any bucket ACL, a public access block not fully on, suspended
#     versioning, SSE other than KMS, a GOVERNANCE or over-a-year default lock, replication, website hosting,
#     Transfer Acceleration, CORS, access points or Multi-Region Access Points (they bypass the S3 endpoint policy);
#   - creates a CloudTrail trail (AUT-104) that is not multi-region, omits global events or log-file validation, is not
#     logging, has no KMS key, writes outside a <prefix>-* bucket, or sets event, advanced or Insights selectors
#     (veda-boundary denies PutEventSelectors; data events are an owner-session step); a CloudTrail Lake event data
#     store or channel; a CloudWatch log group outside /<prefix>/, without a KMS key or with unlimited retention;
#   - creates an ECR repository (AUT-105) outside <prefix>-*, with mutable tags, without scan on push, without KMS
#     encryption, or force-deletable; a public repository, replication, pull-through cache or registry policy;
#   - attaches an AWS managed policy outside the reviewed list (AmazonSSMManagedInstanceCore, the DLM service role
#     policy; ReadOnlyAccess and SecurityAudit for the bootstrap plan and evidence roles); or gives, in a policy of a
#     role other than the bootstrap veda-gh-* roles (or the veda-boundary ceiling), an Allow on "*" or on a whole
#     service ("<service>:*"), or a policy unknown at plan time (AUT-106);
#   - creates an SSM SecureString (secrets are seeded by the owner, AUT-302) or a parameter outside /<prefix>/staging/
#     or under its app/ path; an SSM document other than <prefix>-* or the Session Manager preferences, of a type other
#     than Command or Session, or shared with another account; Session Manager preferences without encrypted
#     CloudWatch transcripts or with run-as; State Manager associations, hybrid activations, maintenance windows or
#     patch baselines (commands run only through the reviewed <prefix>-* documents) (AUT-107);
#   - creates an SNS topic without KMS encryption, a subscription other than email or an SQS queue of the account in
#     the region, an SQS queue without encryption, an alarm whose actions are anything but SNS topics of the account in
#     the region, or a log subscription filter, log destination, metric stream or cross-account sink (AUT-110);
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
    -h | --help) sed -n '2,72p' "$0"; exit 0 ;;
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
        | if .t == "Service" and .v == "vpc-flow-logs.amazonaws.com" then
            (if ((($s.Condition // {}).StringEquals // {})["aws:SourceAccount"] | arr) == [$acct] then empty
             else "\($addr): the flow-logs service may assume the role only for account \($acct) (aws:SourceAccount)" end)
          elif .t == "Service" then empty
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
  # AUT-101 network model A. Types that open another path in or out of the VPC.
  def network_forbidden_type: IN("aws_nat_gateway", "aws_eip", "aws_eip_association", "aws_vpc_peering_connection",
    "aws_vpc_peering_connection_accepter", "aws_vpc_peering_connection_options", "aws_vpn_connection", "aws_vpn_gateway",
    "aws_vpn_gateway_attachment", "aws_customer_gateway", "aws_egress_only_internet_gateway",
    "aws_vpc_ipv6_cidr_block_association", "aws_vpc_endpoint_policy", "aws_vpc_endpoint_subnet_association",
    "aws_ec2_client_vpn_endpoint", "aws_ec2_client_vpn_network_association", "aws_ec2_client_vpn_authorization_rule",
    "aws_main_route_table_association", "aws_ec2_instance_connect_endpoint", "aws_vpclattice_service_network_vpc_association",
    "aws_route53_resolver_endpoint")
    or startswith("aws_ec2_transit_gateway") or startswith("aws_dx_") or startswith("aws_networkmanager_");
  def tcp: tostring | IN("tcp", "6");
  def udp: tostring | IN("udp", "17");
  # An outbound rule of model A: TCP 443 anywhere (IPv4), or TCP/UDP 7844 to a known range that is not everything.
  def egress_ok($proto; $from; $to; $cidr; $v6):
    ($v6 // "") == "" and $from == $to and
    ((($proto | tcp) and $from == 443) or ((($proto | tcp) or ($proto | udp)) and $from == 7844 and ($cidr // "") != "" and $cidr != "0.0.0.0/0"));
  def statements: (.Statement | arr)[];
  # The AWS-owned buckets the host reads through the S3 endpoint, exactly: ECR layers, Amazon Linux 2023 repositories,
  # SSM Agent updates, SSM document modules, Distributor manifests (AUT-101 review M2).
  def owned_object($r): ($r | tostring) as $arn
    | ["prod-\($region)-starport-layer-bucket", "al2023-repos-\($region)-de612dc2", "amazon-ssm-\($region)", "aws-ssm-\($region)",
       "\($region)-birdwatcher-prod"] | any(. as $b | $arn == "arn:aws:s3:::\($b)/*");
  def endpoint_policy_findings($addr):
    statements | select(.Effect == "Allow") as $s
    | if $s.NotAction or $s.NotResource or $s.NotPrincipal then "\($addr): S3 endpoint policy uses NotAction/NotResource/NotPrincipal"
      elif ((($s.Condition // {}).StringEquals // {})["aws:ResourceAccount"] | arr) == [$acct] then empty
      elif ($s.Action | arr) == ["s3:GetObject"] and (($s.Resource | arr) | length) > 0 and all(($s.Resource | arr)[]; owned_object(.)) then empty
      else "\($addr): S3 endpoint policy allows S3 beyond the buckets of the account and the named AWS-owned objects (\($s.Sid // "unnamed statement"))" end;
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
  # AUT-106: AWS managed policies a Veda role may carry.
  def reviewed_managed: tostring | IN("arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole", "arn:aws:iam::aws:policy/ReadOnlyAccess",
    "arn:aws:iam::aws:policy/SecurityAudit");
  def broad_allows($addr):
    (.Statement | arr)[] | select(.Effect == "Allow") | (.Action | arr)[] | tostring | select(. == "*" or endswith(":*"))
    | "\($addr): Allow on \(.) (a whole service): name the actions (AUT-106)";
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

  # Checks on the configuration, which sees references unknown in the plan (AUT-101 review): routes only to the
  # internet gateway through a separate aws_route, never into the main or default route table; no inline routes;
  # no security-group rule attached to the default security group.
  def refs: [.references? // [] | .[] | tostring];
  def config_findings:
    [.configuration | .. | objects | select(has("type") and has("expressions") and has("address"))] as $cfg
    | ($cfg[] | select(.type == "aws_route") as $r
       | ($r.expressions | keys - ["route_table_id", "destination_cidr_block", "gateway_id", "timeouts"]) as $extra
       | (if ($extra | length) > 0 then "\($r.address): route sets \($extra | join(", ")): only an IPv4 destination to the internet gateway is allowed" else empty end),
         (if ($r.expressions.route_table_id | refs | any(test("main_route_table_id|default_route_table_id|aws_default_route_table")))
            then "\($r.address): route into the main or default route table" else empty end),
         (if (($r.expressions.gateway_id.constant_value // "") | startswith("vgw-")) then "\($r.address): route to a VPN gateway" else empty end)),
      ($cfg[] | select(.type == "aws_route_table" and (.expressions.route != null)) | "\(.address): inline routes are not allowed (use aws_route)"),
      ($cfg[] | select(.type | IN("aws_vpc_security_group_egress_rule", "aws_vpc_security_group_ingress_rule", "aws_security_group_rule"))
       | select(.expressions.security_group_id | refs | any(test("default_security_group_id|aws_default_security_group")))
       | "\(.address): rule attached to the default security group (it must have no rule)");

  # AUT-103: every new bucket comes with its controls, matched by bucket name (known at plan time).
  def bucket_findings:
    (.resource_changes // []) as $all
    | [$all[] | select(.change.actions | index("create") or index("update"))] as $live
    | $all[] | select(.type == "aws_s3_bucket" and ((.change.actions | index("create")) != null)) | .address as $addr
    | (.change.after.bucket // null) as $name
    | if $name == null then "\($addr): bucket name unknown at plan time"
      elif $name == "\($prefix)-tfstate-\($acct)" then empty
      elif ($name | startswith($prefix + "-") | not) then "\($addr): bucket \($name) is not \($prefix)-*"
      else
        [$live[] | select(.change.after.bucket == $name)] as $c
        | (if [$c[] | select(.type == "aws_s3_bucket_public_access_block") | .change.after
               | select(.block_public_acls and .block_public_policy and .ignore_public_acls and .restrict_public_buckets)] | length == 0
             then "\($addr): bucket \($name) has no public access block with all four settings on" else empty end),
          (if [$c[] | select(.type == "aws_s3_bucket_ownership_controls") | .change.after.rule[]? | select(.object_ownership == "BucketOwnerEnforced")] | length == 0
             then "\($addr): bucket \($name) has no BucketOwnerEnforced ownership (ACLs must be disabled)" else empty end),
          (if [$c[] | select(.type == "aws_s3_bucket_versioning") | .change.after.versioning_configuration[]? | select(.status == "Enabled")] | length == 0
             then "\($addr): bucket \($name) has no versioning" else empty end),
          (if [$c[] | select(.type == "aws_s3_bucket_server_side_encryption_configuration") | .change.after.rule[]?.apply_server_side_encryption_by_default[]?
               | select(.sse_algorithm | IN("aws:kms", "aws:kms:dsse"))] | length == 0
             then "\($addr): bucket \($name) has no SSE-KMS encryption" else empty end),
          (if [$c[] | select(.type == "aws_s3_bucket_policy") | .change.after.policy // "" | select(. != "") | fromjson | (.Statement | arr)[]
               | select(.Effect == "Deny" and (((.Condition // {}).Bool // {})["aws:SecureTransport"] | tostring) == "false")] | length == 0
             then "\($addr): bucket \($name) has no policy denying plain HTTP (aws:SecureTransport)" else empty end)
      end;

  [ region_findings ] + [ config_findings ] + [ bucket_findings ] + [ .resource_changes[]? | . as $rc | .address as $addr | (.change.after // {}) as $after | (.change.after_unknown // {}) as $unknown
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
      elif .type == "aws_iam_policy" then iam_name_path($addr; "policy"; $after; $unknown),
        # veda-boundary of the bootstrap (a ceiling: Allow * capped by its Denies) and veda-gh-* policies are reviewed there.
        (if (($after.name // "") | startswith($prefix + "-gh-")) or $after.name == "\($prefix)-boundary" then empty
         elif $unknown.policy == true then "\($addr): IAM policy unknown at plan time (build ARNs from names so the reviewer sees it)"
         elif ($after.policy // "") == "" then empty
         else ($after.policy | fromjson | broad_allows($addr)) end)
      elif .type == "aws_iam_instance_profile" then iam_name_path($addr; "instance profile"; $after; $unknown)
      elif .type == "aws_iam_role_policy_attachment" or .type == "aws_iam_policy_attachment" or .type == "aws_iam_role_policy_attachments_exclusive" then
        (([$after.policy_arn] + ($after.policy_arns // [])) | map(select(. != null))[] | select(privileged)
         | "\($addr): privileged managed policy \(.)"),
        (([$after.policy_arn] + ($after.policy_arns // [])) | map(select(. != null))[]
         | select(startswith("arn:aws:iam::aws:policy/") and (privileged | not) and (reviewed_managed | not))
         | "\($addr): AWS managed policy \(.) is not in the reviewed list (AUT-106)")
      elif .type == "aws_iam_role_policy" then
        (if (($after.role // "") | startswith($prefix + "-gh-")) then empty
         elif $unknown.policy == true then "\($addr): IAM policy unknown at plan time (build ARNs from names so the reviewer sees it)"
         elif ($after.policy // "") == "" then empty
         else ($after.policy | fromjson | broad_allows($addr)) end)
      elif .type == "aws_lambda_permission" then
        (if ($after.principal | tostring | test("\\.amazonaws\\.com$")) or ($after.principal | own) then empty
         else "\($addr): Lambda permission for \($after.principal)" end)
      elif .type == "aws_lambda_function_url" then
        (if $after.authorization_type == "NONE" then "\($addr): public function URL (authorization NONE)" else empty end)
      elif .type == "aws_ami_launch_permission" or .type == "aws_snapshot_create_volume_permission" then
        (if ($after.account_id // "") == $acct then empty else "\($addr): shares with \($after.account_id // $after.group // "?")" end)
      elif .type == "aws_kms_grant" then
        (if ($after.grantee_principal | tostring | own) then empty else "\($addr): KMS grant to \($after.grantee_principal)" end)
      elif (.type | network_forbidden_type) then
        "\($addr): \(.type) is not part of the staging network (egress model A, AUT-101 N1)"
      elif .type == "aws_vpc_security_group_ingress_rule" or (.type == "aws_security_group_rule" and $after.type == "ingress") then
        "\($addr): no inbound security-group rule in staging (AUT-101: access is SSM and the outbound tunnel)"
      elif .type == "aws_vpc_security_group_egress_rule" then
        (if egress_ok($after.ip_protocol; $after.from_port; $after.to_port; ($after.cidr_ipv4 // (if $after.prefix_list_id != null or $unknown.prefix_list_id == true then "prefix-list" else null end)); $after.cidr_ipv6)
           then empty else "\($addr): outbound \($after.ip_protocol)/\($after.from_port)-\($after.to_port) to \($after.cidr_ipv4 // $after.cidr_ipv6 // "?") is not TCP 443 or the tunnel (TCP/UDP 7844 to its ranges)" end)
      elif .type == "aws_security_group_rule" then
        (if (($after.cidr_blocks // []) | length) == 0 and ($after.prefix_list_ids // [] | length) == 0 and ($after.source_security_group_id // null) == null and $after.self != true then "\($addr): outbound rule without a known destination"
         else (((($after.cidr_blocks // []) | if length == 0 then ["prefix-list"] else . end)[]) as $c
           | if egress_ok($after.protocol; $after.from_port; $after.to_port; $c; (($after.ipv6_cidr_blocks // []) | join(","))) then empty
             else "\($addr): outbound \($after.protocol)/\($after.from_port)-\($after.to_port) to \($c) is not TCP 443 or the tunnel" end) end)
      elif .type == "aws_security_group" or .type == "aws_default_security_group" then
        (if $unknown.ingress != true and (($after.ingress // []) | length) > 0 then "\($addr): no inbound security-group rule in staging (AUT-101)" else empty end),
        (if .type == "aws_default_security_group" and $unknown.egress != true and (($after.egress // []) | length) > 0
           then "\($addr): the default security group must have no rule" else empty end),
        (if .type == "aws_security_group" and $unknown.egress != true then
           # Every destination of every inline rule: each CIDR, and prefix lists or groups as one non-CIDR destination.
           (($after.egress // [])[] | . as $r
            | (($r.cidr_blocks // []) + (if ((($r.prefix_list_ids // []) + ($r.security_groups // [])) | length) > 0 or $r.self == true then ["prefix-list"] else [] end)) as $dests
            | if ($dests | length) == 0 then "\($addr): outbound \($r.protocol)/\($r.from_port)-\($r.to_port) without a known destination"
              else ($dests[] | select(egress_ok($r.protocol; $r.from_port; $r.to_port; .; (($r.ipv6_cidr_blocks // []) | join(","))) | not)
                | "\($addr): outbound \($r.protocol)/\($r.from_port)-\($r.to_port) to \(.) is not TCP 443 or the tunnel") end)
         else empty end)
      elif .type == "aws_network_acl_rule" then
        (if ($after.ipv6_cidr_block // "") != "" then "\($addr): IPv6 NACL rule (the staging network is IPv4 only)"
         elif $after.rule_action != "allow" then empty
         elif ($after.protocol | tostring | IN("-1", "all")) then "\($addr): NACL allow rule for all protocols"
         elif $after.egress != true and (($after.from_port // 0) < 1024) then "\($addr): NACL allows inbound to port \($after.from_port) (only replies on ports 1024 and above)"
         else empty end)
      elif .type == "aws_network_acl" or .type == "aws_default_network_acl" then
        ((($after.ingress // []) + ($after.egress // []))[] | select(.action == "allow") as $r
         | if $rc.type == "aws_default_network_acl" then "\($addr): the default network ACL must allow nothing"
           elif ($r.protocol | tostring | IN("-1", "all")) then "\($addr): NACL allow rule for all protocols"
           else empty end),
        (($after.ingress // [])[] | select(.action == "allow" and (.from_port // 0) < 1024 and $rc.type != "aws_default_network_acl")
         | "\($addr): NACL allows inbound to port \(.from_port) (only replies on ports 1024 and above)")
      elif .type == "aws_route_table" then
        (if $unknown.route != true and (($after.route // []) | length) > 0
           then "\($addr): inline routes are not allowed (use aws_route, which the guard checks)" else empty end)
      elif .type == "aws_default_route_table" then
        (if $unknown.route != true and (($after.route // []) | length) > 0 then "\($addr): the default route table must have no route" else empty end)
      elif .type == "aws_route" then
        (if ($after.destination_ipv6_cidr_block // "") != "" then "\($addr): IPv6 route (the staging network is IPv4 only)"
         elif ([$after.nat_gateway_id, $after.vpc_peering_connection_id, $after.transit_gateway_id, $after.egress_only_gateway_id,
                $after.carrier_gateway_id, $after.local_gateway_id, $after.core_network_arn, $after.network_interface_id] | map(select(. != null and . != "")) | length) > 0
           then "\($addr): route to a target other than the internet gateway or a VPC endpoint" else empty end)
      elif .type == "aws_instance" then
        (if ($after.subnet_id // null) == null and $unknown.subnet_id != true and (($after.network_interface // []) | length) == 0
           then "\($addr): instance without a subnet would land in the default VPC (AUT-101: only the staging subnet)" else empty end)
      elif .type == "aws_subnet" then
        (if $after.map_public_ip_on_launch == true then "\($addr): the subnet assigns public addresses (the host asks for its own, AUT-108)" else empty end),
        (if ($after.ipv6_cidr_block // "") != "" or $after.assign_ipv6_address_on_creation == true then "\($addr): IPv6 subnet (the staging network is IPv4 only)" else empty end)
      elif .type == "aws_vpc" then
        (if $after.assign_generated_ipv6_cidr_block == true or ($after.ipv6_ipam_pool_id // "") != "" or ($after.ipv6_cidr_block // "") != ""
           then "\($addr): IPv6 VPC (the staging network is IPv4 only)" else empty end)
      elif .type == "aws_vpc_endpoint" then
        (if ($after.vpc_endpoint_type // "Gateway") != "Gateway" or $after.service_name != "com.amazonaws.\($region).s3"
           then "\($addr): only the S3 gateway endpoint is part of egress model A (got \($after.vpc_endpoint_type // "?") \($after.service_name // "?"))"
         elif $unknown.policy == true then "\($addr): S3 endpoint policy not known at plan time"
         elif ($after.policy // "") == "" then "\($addr): S3 endpoint without a policy (the AWS default allows full access)"
         else ($after.policy | fromjson | endpoint_policy_findings($addr)) end)
      elif .type == "aws_sns_topic" then
        (if ($after.kms_master_key_id // "") == "" and $unknown.kms_master_key_id != true then "\($addr): SNS topic without KMS encryption" else empty end)
      elif .type == "aws_sns_topic_subscription" then
        (if $after.protocol == "email" then empty
         elif $after.protocol == "sqs" and $unknown.endpoint != true and (($after.endpoint // "") | test("^arn:aws:sqs:" + ($region | esc) + ":" + $acct + ":") | not)
           then "\($addr): SQS subscription to \($after.endpoint) outside account \($acct) in \($region)"
         elif $after.protocol == "sqs" then empty
         else "\($addr): subscription protocol \($after.protocol // "?") (email or an SQS queue of the account only)" end)
      elif .type == "aws_sqs_queue" then
        (if $after.sqs_managed_sse_enabled != true and ($after.kms_master_key_id // "") == "" and $unknown.kms_master_key_id != true
           then "\($addr): SQS queue without encryption" else empty end)
      elif .type == "aws_cloudwatch_metric_alarm" or .type == "aws_cloudwatch_composite_alarm" then
        ((($after.alarm_actions // []) + ($after.ok_actions // []) + ($after.insufficient_data_actions // []))[] | tostring
         | select(test("^arn:aws:sns:" + ($region | esc) + ":" + $acct + ":") | not)
         | "\($addr): alarm action \(.) is not an SNS topic of account \($acct) in \($region)")
      elif .type | IN("aws_cloudwatch_log_subscription_filter", "aws_cloudwatch_log_destination", "aws_cloudwatch_log_destination_policy",
                      "aws_cloudwatch_metric_stream", "aws_oam_link", "aws_oam_sink", "aws_oam_sink_policy", "aws_cloudwatch_log_delivery",
                      "aws_cloudwatch_log_delivery_destination", "aws_cloudwatch_log_account_policy") then
        "\($addr): \(.type) is not allowed (logs and metrics stay in the account; AUT-110)"
      elif .type == "aws_ssm_parameter" then
        (if $after.type == "SecureString" then "\($addr): SecureString parameters are seeded by the owner, never by Terraform (AUT-302)" else empty end),
        (if (($after.name // "") | startswith("/\($prefix)/staging/") | not) or (($after.name // "") | startswith("/\($prefix)/staging/app/"))
           then "\($addr): parameter \($after.name // "?") is outside /\($prefix)/staging/ or under its secret app/ path" else empty end)
      elif .type == "aws_ssm_document" then
        (if (($after.name // "") | startswith($prefix + "-")) or $after.name == "SSM-SessionManagerRunShell" then empty
         else "\($addr): SSM document \($after.name // "?") is not \($prefix)-* (or the Session Manager preferences)" end),
        (if ($after.document_type // "") | IN("Command", "Session") | not then "\($addr): SSM document type \($after.document_type // "?") (Command or Session only)" else empty end),
        (if (($after.permissions // {}) | length) > 0 then "\($addr): SSM document shared with another account" else empty end),
        (if $after.name == "SSM-SessionManagerRunShell" then
           (($after.content // "{}") | fromjson | .inputs // {}) as $i
           | (if $i.cloudWatchEncryptionEnabled != true or ($i.cloudWatchLogGroupName // "") == "" then "\($addr): Session Manager transcripts must go to an encrypted CloudWatch log group" else empty end),
             (if $i.runAsEnabled == true then "\($addr): Session Manager run-as is not allowed" else empty end)
         else empty end)
      elif .type | IN("aws_ssm_association", "aws_ssm_activation", "aws_ssm_maintenance_window", "aws_ssm_maintenance_window_task",
                      "aws_ssm_maintenance_window_target", "aws_ssm_patch_baseline", "aws_ssm_default_patch_baseline", "aws_ssm_service_setting") then
        "\($addr): \(.type) is not allowed (commands run only through the reviewed \($prefix)-* documents; AUT-107)"
      elif .type == "aws_ecr_repository" then
        (if (($after.name // "") | startswith($prefix + "-") | not) then "\($addr): repository \($after.name // "?") is not \($prefix)-*" else empty end),
        (if $after.image_tag_mutability != "IMMUTABLE" then "\($addr): image tags are \($after.image_tag_mutability // "?"), not IMMUTABLE (a tag must always mean one image)" else empty end),
        (if [($after.image_scanning_configuration // [])[] | select(.scan_on_push == true)] | length == 0 then "\($addr): images are not scanned on push" else empty end),
        (if [($after.encryption_configuration // [])[] | select(.encryption_type == "KMS")] | length == 0 then "\($addr): repository not encrypted with KMS" else empty end),
        (if $after.force_delete == true then "\($addr): force_delete would delete every image with the repository" else empty end)
      elif .type | IN("aws_ecrpublic_repository", "aws_ecrpublic_repository_policy", "aws_ecr_replication_configuration",
                      "aws_ecr_pull_through_cache_rule", "aws_ecr_registry_policy", "aws_ecr_repository_creation_template") then
        "\($addr): \(.type) is not allowed (one private repository; no public, replicated or pull-through images; AUT-105)"
      elif .type == "aws_cloudtrail" then
        (if $after.is_multi_region_trail != true then "\($addr): trail is not multi-region (activity in other regions would go unrecorded)" else empty end),
        (if $after.include_global_service_events == false then "\($addr): trail omits global service events (IAM, STS)" else empty end),
        (if $after.enable_log_file_validation != true then "\($addr): trail without log-file validation (tampering would be undetectable)" else empty end),
        (if $after.enable_logging == false then "\($addr): trail created with logging off" else empty end),
        (if ($after.kms_key_id // "") == "" and $unknown.kms_key_id != true then "\($addr): trail without a KMS key" else empty end),
        (if (($after.s3_bucket_name // "") | startswith($prefix + "-") | not) and $unknown.s3_bucket_name != true
           then "\($addr): trail writes to \($after.s3_bucket_name // "?"), not a \($prefix)-* bucket" else empty end),
        (if ([$after.event_selector, $after.advanced_event_selector, $after.insight_selector] | map(. // [] | length) | add) > 0
           then "\($addr): trail selectors are set by the owner session (veda-boundary denies PutEventSelectors to every role)" else empty end)
      elif .type | IN("aws_cloudtrail_event_data_store", "aws_cloudtrail_channel", "aws_cloudtrail_organization_delegated_admin_account") then
        "\($addr): \(.type) is not allowed (one trail; no CloudTrail Lake; AUT-104)"
      elif .type == "aws_cloudwatch_log_group" then
        (if (($after.name // "") | startswith("/" + $prefix + "/") | not) then "\($addr): log group \($after.name // "?") is not under /\($prefix)/" else empty end),
        (if ($after.kms_key_id // "") == "" and $unknown.kms_key_id != true then "\($addr): log group without a KMS key" else empty end),
        (if ($after.retention_in_days // 0) == 0 then "\($addr): log group with unlimited retention" else empty end)
      elif .type | IN("aws_s3_bucket_acl", "aws_s3_bucket_replication_configuration", "aws_s3_bucket_website_configuration",
                      "aws_s3_bucket_cors_configuration", "aws_s3_access_point", "aws_s3control_access_point_policy",
                      "aws_s3control_multi_region_access_point", "aws_s3control_multi_region_access_point_policy",
                      "aws_s3control_object_lambda_access_point", "aws_s3_directory_bucket") then
        "\($addr): \(.type) is not allowed (ACLs are disabled; no replication, website, CORS or access points; AUT-103)"
      elif .type == "aws_s3_bucket_accelerate_configuration" then
        (if $after.status == "Enabled" then "\($addr): S3 Transfer Acceleration bypasses the S3 endpoint policy" else empty end)
      elif .type == "aws_s3_bucket_public_access_block" then
        (if ($after.block_public_acls and $after.block_public_policy and $after.ignore_public_acls and $after.restrict_public_buckets) | not
           then "\($addr): public access block with a setting off" else empty end)
      elif .type == "aws_s3_bucket_ownership_controls" then
        (if [($after.rule // [])[] | select(.object_ownership == "BucketOwnerEnforced")] | length == 0
           then "\($addr): bucket ownership other than BucketOwnerEnforced (ACLs must stay disabled)" else empty end)
      elif .type == "aws_s3_bucket_versioning" then
        (if [($after.versioning_configuration // [])[] | select(.status == "Enabled")] | length == 0 then "\($addr): bucket versioning not enabled" else empty end)
      elif .type == "aws_s3_bucket_server_side_encryption_configuration" then
        (if [($after.rule // [])[].apply_server_side_encryption_by_default[]? | select(.sse_algorithm | IN("aws:kms", "aws:kms:dsse") | not)] | length > 0
           then "\($addr): bucket encryption other than SSE-KMS" else empty end)
      elif .type == "aws_s3_bucket_object_lock_configuration" then
        (($after.rule // [])[].default_retention[]? | select(.mode != "COMPLIANCE" or ((.days // 0) > 365) or ((.years // 0) > 1))
         | "\($addr): default Object Lock \(.mode) for \(.days // 0) days \(.years // 0) years (COMPLIANCE, at most a year)")
      elif .type | IN("aws_kms_replica_key", "aws_kms_external_key", "aws_kms_replica_external_key", "aws_kms_custom_key_store", "aws_kms_key_policy") then
        "\($addr): \(.type) is not allowed (keys are single-region, AWS-generated, with their policy on the key; AUT-102)"
      elif .type == "aws_kms_alias" then
        (if ($after.name // "") | startswith("alias/" + $prefix + "-") then empty else "\($addr): KMS alias \($after.name // "(unknown)") is not alias/\($prefix)-*" end)
      elif .type == "aws_kms_key" then
        (if $after.enable_key_rotation != true then "\($addr): KMS key without automatic rotation" else empty end),
        (if ($after.deletion_window_in_days // 30) < 30 then "\($addr): KMS key deletion window \($after.deletion_window_in_days) days (30 required)" else empty end),
        (if $after.multi_region == true then "\($addr): multi-region KMS key" else empty end),
        (if ($after.key_usage // "ENCRYPT_DECRYPT") != "ENCRYPT_DECRYPT" or ($after.customer_master_key_spec // "SYMMETRIC_DEFAULT") != "SYMMETRIC_DEFAULT"
           then "\($addr): KMS key is not a symmetric encrypt/decrypt key" else empty end),
        (if $after.bypass_policy_lockout_safety_check == true then "\($addr): KMS key bypasses the policy lockout safety check" else empty end),
        (if $unknown.policy == true or ($after.policy // "") == "" then "\($addr): KMS key policy unknown or absent (the default policy is not reviewed)"
         else ($after.policy | fromjson) as $p
           | (if [($p.Statement | arr)[] | select(.Effect == "Deny" and ((.Action | arr) | index("kms:*")) != null
                    and ((((.Condition // {}).StringNotEquals // {})["kms:CallerAccount"]) | arr) == [$acct])] | length > 0
              then empty else "\($addr): KMS key policy does not deny callers outside account \($acct) (kms:CallerAccount)" end),
             ($p | open_statements($addr)) end)
      elif .type == "aws_budgets_budget_action" then
        "\($addr): budget actions are not allowed (they apply IAM or SCP policies or stop instances automatically; AUT-112)"
      elif .type == "aws_budgets_budget" then
        (if $unknown.name == true or (($after.name // "") | startswith($prefix + "-") | not)
           then "\($addr): budget name \($after.name // "(unknown)") is not \($prefix)-*" else empty end),
        (if $unknown.account_id != true and ($after.account_id // $acct) != $acct
           then "\($addr): budget for account \($after.account_id), not \($acct)" else empty end),
        (if $unknown.billing_view_arn == true or ($after.billing_view_arn // null) != null
           then "\($addr): budget on a billing view (\($after.billing_view_arn // "unknown")) is not allowed" else empty end),
        (if $unknown.limit_amount == true or ($after.limit_amount // "") == "" or ($after.limit_unit // "") != "USD"
           then "\($addr): budget without a known limit in USD (owner decision O16)" else empty end),
        (if $unknown.notification == true then "\($addr): budget notifications not known at plan time"
         elif (($after.notification // []) | length) == 0 then "\($addr): budget without a notification alerts no one" else empty end),
        # Each SNS subscriber must be known at plan time (a list or an element unknown is refused, never skipped) and
        # be a topic of the account in the region.
        (($after.notification // []) | to_entries[] | .key as $i | (.value.subscriber_sns_topic_arns // []) as $arns
         | (($unknown.notification // []) | if type == "array" then (.[$i] // {}) else {} end | .subscriber_sns_topic_arns) as $su
         | if $su == true or (($su | arr) | index(true)) != null or ($arns | index(null)) != null
             then "\($addr): budget notifies an SNS topic not known at plan time (only known topics of account \($acct) in \($region))"
           else ($arns[] | select(test("^arn:aws:sns:" + ($region | esc) + ":" + $acct + ":[A-Za-z0-9_-]+$") | not)
             | "\($addr): budget notifies \(.), outside account \($acct) in \($region)") end)
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
