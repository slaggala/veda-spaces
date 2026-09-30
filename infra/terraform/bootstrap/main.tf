data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = var.aws_region
  prefix     = var.name_prefix

  state_bucket_name = "${local.prefix}-tfstate-${local.account_id}"

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
