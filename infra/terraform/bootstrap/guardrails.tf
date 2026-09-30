# Account-wide defaults for the dedicated staging account (plan §1 step 1). Region-scoped settings apply to
# ap-south-1, the only region the boundary allows.

resource "aws_s3_account_public_access_block" "this" {
  count = var.enable_account_guardrails ? 1 : 0

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_ebs_encryption_by_default" "this" {
  count   = var.enable_account_guardrails ? 1 : 0
  enabled = true
}

resource "aws_ebs_snapshot_block_public_access" "this" {
  count = var.enable_account_guardrails ? 1 : 0
  state = "block-all-sharing"
}

resource "aws_ec2_image_block_public_access" "this" {
  count = var.enable_account_guardrails ? 1 : 0
  state = "block-new-sharing"
}

# IMDSv2 for every new instance; hop limit 2 so bridge-networked containers can reach the instance role
# (Litestream, S3, KMS, SES). The compute module sets the same values explicitly (AUT-108).
resource "aws_ec2_instance_metadata_defaults" "this" {
  count = var.enable_account_guardrails ? 1 : 0

  http_tokens                 = "required"
  http_put_response_hop_limit = 2
  http_endpoint               = "enabled"
  instance_metadata_tags      = "disabled"
}

resource "aws_accessanalyzer_analyzer" "account" {
  count         = var.enable_account_guardrails ? 1 : 0
  analyzer_name = "${local.prefix}-account-analyzer"
  type          = "ACCOUNT"
}
