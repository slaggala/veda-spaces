data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

# The IAM role (with its path) or user behind the owner session, so the plan can refuse a session that would lock
# itself out of the state it creates (RR-01).
data "aws_iam_session_context" "current" {
  arn = data.aws_caller_identity.current.arn
}

locals {
  # Approved account and account-wide choices, from the reviewed manifest (F3, F5).
  manifest_path       = var.account_manifest_path != "" ? var.account_manifest_path : "${path.module}/../../config/staging-account.json"
  manifest            = jsondecode(file(local.manifest_path))
  approved_account_id = try(regex("^[0-9]{12}$", local.manifest.account_id), "")
  manage_guardrails   = try(local.manifest.manage_account_guardrails, true) == true

  # RR-01/RR-02: the only principals that may read or write bootstrap state, change the state bucket or administer
  # the state key. An explicit allow-list from the reviewed manifest (exact IAM role or user ARNs, path included),
  # plus the account root for recovery. Every other principal is refused, whatever its name or path.
  manifest_owner_arns  = try([for a in local.manifest.bootstrap_principal_arns : tostring(a)], [])
  owner_principal_arns = distinct(concat(["arn:${local.partition}:iam::${local.account_id}:root"], local.manifest_owner_arns))

  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = var.aws_region
  prefix     = var.name_prefix

  state_bucket_name = "${local.prefix}-tfstate-${local.account_id}"
  state_bucket_arn  = "arn:${local.partition}:s3:::${local.state_bucket_name}"

  # Names the later stacks will create (AUT-103/105/107/108); the deploy and evidence roles are scoped to
  # them now so that no later stack has to widen a bootstrap role.
  artifacts_bucket_name = "${local.prefix}-stg-artifacts-${local.account_id}"
  evidence_bucket_name  = "${local.prefix}-evidence-${local.account_id}"
  data_bucket_patterns = [
    "${local.prefix}-stg-litestream-*",
    "${local.prefix}-stg-snapshots-*",
    "${local.prefix}-stg-anchor-*",
  ]
  ecr_repository = "${local.prefix}-api"

  role_names = {
    plan     = "${local.prefix}-gh-plan"
    apply    = "${local.prefix}-gh-apply"
    deploy   = "${local.prefix}-gh-deploy"
    evidence = "${local.prefix}-gh-evidence"
  }

  # RR-03: the only principal that may create a role or change a trust policy.
  apply_role_arn = "arn:${local.partition}:iam::${local.account_id}:role/${local.role_names.apply}"

  boundary_name = "${local.prefix}-boundary"
  boundary_arn  = "arn:${local.partition}:iam::${local.account_id}:policy/${local.boundary_name}"

  oidc_host = "token.actions.githubusercontent.com"
  # Built from the fixed provider URL (not read from the resource) so every policy is fully known at plan
  # time and can be reviewed before apply; roles depend_on the provider for ordering.
  oidc_provider_arn = var.existing_github_oidc_provider_arn != "" ? var.existing_github_oidc_provider_arn : "arn:${local.partition}:iam::${local.account_id}:oidc-provider/${local.oidc_host}"

  state_kms_alias = "alias/${local.prefix}-tfstate"

  # Global services that have no ap-south-1 endpoint; everything else is refused outside the region.
  global_actions = [
    "iam:*", "sts:*", "budgets:*", "ce:*", "cur:*", "health:*", "support:*", "trustedadvisor:*",
    "organizations:Describe*", "organizations:List*", "account:Get*", "account:List*",
  ]
}
