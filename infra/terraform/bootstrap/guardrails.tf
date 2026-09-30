# Account-wide defaults for the dedicated staging account (plan §1 step 1). Region-scoped settings apply to
# ap-south-1, the only region the boundary allows.
#
# Whether the bootstrap manages them is recorded in infra/config/staging-account.json
# (manage_account_guardrails), so it changes only through a reviewed pull request (F5). Once created, they are
# prevent_destroy: turning the setting off later makes the plan fail instead of removing a guardrail, and
# bootstrap.sh refuses any plan that deletes something.

resource "aws_s3_account_public_access_block" "this" {
  count = local.manage_guardrails ? 1 : 0

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ebs_encryption_by_default" "this" {
  count   = local.manage_guardrails ? 1 : 0
  enabled = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ebs_snapshot_block_public_access" "this" {
  count = local.manage_guardrails ? 1 : 0
  state = "block-all-sharing"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ec2_image_block_public_access" "this" {
  count = local.manage_guardrails ? 1 : 0
  state = "block-new-sharing"

  lifecycle {
    prevent_destroy = true
  }
}

# IMDSv2 for every new instance; hop limit 2 so bridge-networked containers can reach the instance role
# (Litestream, S3, KMS, SES). The compute module sets the same values explicitly (AUT-108).
resource "aws_ec2_instance_metadata_defaults" "this" {
  count = local.manage_guardrails ? 1 : 0

  http_tokens                 = "required"
  http_put_response_hop_limit = 2
  http_endpoint               = "enabled"
  instance_metadata_tags      = "disabled"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_accessanalyzer_analyzer" "account" {
  count         = local.manage_guardrails ? 1 : 0
  analyzer_name = "${local.prefix}-account-analyzer"
  type          = "ACCOUNT"

  lifecycle {
    prevent_destroy = true
  }
}
