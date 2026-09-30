# Terraform state for every Veda staging stack (keys: bootstrap/, staging/core.tfstate, staging/edge.tfstate).
# Encrypted with its own customer-managed key; locking is S3-native (use_lockfile), so no DynamoDB table.

data "aws_iam_policy_document" "state_key" {
  #checkov:skip=CKV_AWS_109:Standard account-root key policy statement: delegates key use to IAM policies; tampering is denied by veda-boundary
  #checkov:skip=CKV_AWS_111:Standard account-root key policy statement: delegates key use to IAM policies; tampering is denied by veda-boundary
  #checkov:skip=CKV_AWS_356:Standard account-root key policy statement: delegates key use to IAM policies; tampering is denied by veda-boundary
  # The account root statement lets IAM policies grant use of the key (the GitHub roles below). Nothing else
  # is granted here; deletion and policy changes are refused to every veda-* role by the boundary.
  statement {
    sid       = "AccountAdministration"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:${local.partition}:iam::${local.account_id}:root"]
    }
  }
}

resource "aws_kms_key" "state" {
  description             = "Veda Terraform state encryption"
  enable_key_rotation     = true
  rotation_period_in_days = 365
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.state_key.json

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_kms_alias" "state" {
  name          = local.state_kms_alias
  target_key_id = aws_kms_key.state.key_id
}

resource "aws_s3_bucket" "state" {
  #checkov:skip=CKV_AWS_144:Cross-region replication is excluded: staging is approved for ap-south-1 only (ADR-008, D-1)
  #checkov:skip=CKV2_AWS_62:No consumer for state-object events; changes are audited through CloudTrail (AUT-104)
  #checkov:skip=CKV_AWS_18:Access to state is audited by CloudTrail S3 data events added in AUT-104 instead of server access logs
  bucket = local.state_bucket_name

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.state.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    id     = "expire-superseded-state"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.state_noncurrent_version_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.state]
}

# Resource-side controls that hold even for a role outside veda-boundary (F2): every veda-* role is refused
# bootstrap state writes and any bucket configuration change. Only the owner session maintains the bucket.
data "aws_iam_policy_document" "state_bucket" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      local.state_bucket_arn,
      "${local.state_bucket_arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # Keys outside this account and region are refused. The pattern (not the exact key ARN, which exists only after
  # apply) keeps the whole bucket policy known at plan time, so the reviewer and the plan guard see it on the
  # first run too. Default encryption still uses the state key.
  statement {
    sid       = "DenyWrongKmsKey"
    effect    = "Deny"
    actions   = ["s3:PutObject"]
    resources = ["${local.state_bucket_arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "StringNotLikeIfExists"
      variable = "s3:x-amz-server-side-encryption-aws-kms-key-id"
      values   = ["arn:${local.partition}:kms:${local.region}:${local.account_id}:key/*"]
    }
  }

  statement {
    sid       = "DenyVedaRolesBootstrapStateWrites"
    effect    = "Deny"
    actions   = ["s3:PutObject", "s3:DeleteObject", "s3:PutObjectTagging", "s3:DeleteObjectTagging"]
    resources = ["${local.state_bucket_arn}/bootstrap/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:PrincipalArn"
      values   = [local.veda_role_arn_pattern]
    }
  }

  statement {
    sid    = "DenyVedaRolesBucketChanges"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket*", "s3:PutBucket*", "s3:Put*Configuration", "s3:PutObjectAcl", "s3:PutObjectVersionAcl",
      "s3:PutObjectRetention", "s3:PutObjectLegalHold", "s3:DeleteObjectVersion*",
    ]
    resources = [local.state_bucket_arn, "${local.state_bucket_arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:PrincipalArn"
      values   = [local.veda_role_arn_pattern]
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.state]
}
