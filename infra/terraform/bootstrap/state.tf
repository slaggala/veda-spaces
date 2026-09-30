# Terraform state for every Veda staging stack (keys: bootstrap/, staging/core.tfstate, staging/edge.tfstate).
# Encrypted with its own customer-managed key; locking is S3-native (use_lockfile), so no DynamoDB table.

# RR-02: the key policy itself enforces the key's protection; no statement depends on an alias, a role name or a
# permissions boundary. Whoever calls, and whatever their IAM policies allow:
#   - only the owner principals (manifest bootstrap_principal_arns, and the account root) can administer the key:
#     every other principal may only describe it, read its metadata and use it for S3;
#   - the key encrypts and decrypts only through S3, only for objects of the state bucket, one object at a time
#     (a bucket-level S3 Bucket Key context is refused, so every use is bound to one object ARN);
#   - bootstrap/* objects are decrypted and encrypted for the owner principals only;
#   - no other account uses it.
# The account-root statement is kept so the key can never become unmanageable (KMS lockout safety check).
locals {
  state_key_crypto_actions = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*"]
  state_s3_via_service     = "s3.${local.region}.amazonaws.com"
}

data "aws_iam_policy_document" "state_key" {
  #checkov:skip=CKV_AWS_109:Account-root delegation is required by KMS (lockout safety); administration is denied to every non-owner principal by DenyKeyAdministrationExceptOwner in this policy
  #checkov:skip=CKV_AWS_111:Account-root delegation is required by KMS (lockout safety); administration is denied to every non-owner principal by DenyKeyAdministrationExceptOwner in this policy
  #checkov:skip=CKV_AWS_356:A key policy's Resource "*" means this key only
  statement {
    sid       = "AccountAdministration"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:${local.partition}:iam::${local.account_id}:root"]
    }
  }

  statement {
    sid         = "DenyKeyAdministrationExceptOwner"
    effect      = "Deny"
    not_actions = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey", "kms:Get*", "kms:List*"]
    resources   = ["*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = local.owner_principal_arns
    }
  }

  statement {
    sid       = "DenyUseOutsideS3"
    effect    = "Deny"
    actions   = local.state_key_crypto_actions
    resources = ["*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "StringNotEquals"
      variable = "kms:ViaService"
      values   = [local.state_s3_via_service]
    }
  }

  statement {
    sid       = "DenyUseOutsideStateObjects"
    effect    = "Deny"
    actions   = local.state_key_crypto_actions
    resources = ["*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "StringNotLike"
      variable = "kms:EncryptionContext:aws:s3:arn"
      values   = ["${local.state_bucket_arn}/*"]
    }
  }

  statement {
    sid       = "DenyBootstrapStateExceptOwner"
    effect    = "Deny"
    actions   = local.state_key_crypto_actions
    resources = ["*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "StringLike"
      variable = "kms:EncryptionContext:aws:s3:arn"
      values   = ["${local.state_bucket_arn}/bootstrap/*"]
    }
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = local.owner_principal_arns
    }
  }

  statement {
    sid       = "DenyOtherAccounts"
    effect    = "Deny"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "StringNotEquals"
      variable = "kms:CallerAccount"
      values   = [local.account_id]
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

    # RR-01/RR-02: the owner allow-list must be committed, exact, free of veda-* identities, and must include the
    # session running this plan (otherwise it would lock itself out of the state it is about to write).
    precondition {
      condition     = length(local.manifest_owner_arns) > 0
      error_message = "bootstrap_principal_arns is empty in the account manifest: commit the owner session's IAM role or user ARN in a reviewed change first (runbook §2)."
    }
    precondition {
      condition = alltrue([for a in local.manifest_owner_arns :
      can(regex("^arn:${local.partition}:iam::${local.approved_account_id}:(role|user)/[A-Za-z0-9+=,.@_/-]+$", a))])
      error_message = "bootstrap_principal_arns must list exact IAM role or user ARNs (path included, no wildcards) in the approved account."
    }
    precondition {
      condition     = !anytrue([for a in local.manifest_owner_arns : can(regex(":(role|user)/(.*/)?${local.prefix}-", a))])
      error_message = "bootstrap_principal_arns must not name a ${local.prefix}-* identity: no Veda role may own the bootstrap state."
    }
    precondition {
      condition     = contains(local.owner_principal_arns, data.aws_iam_session_context.current.issuer_arn)
      error_message = "This session (${data.aws_iam_session_context.current.issuer_arn}) is not in bootstrap_principal_arns; it would lock itself out of the state it creates."
    }
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
    # Off on purpose (RR-02): with an S3 Bucket Key the KMS encryption context is the bucket, and the key policy
    # could no longer tell bootstrap/* from staging/* objects. State objects are few; the extra KMS calls are free-tier.
    bucket_key_enabled = false
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

# RR-01: resource-side controls that hold for every principal, bounded or not, whatever its name or path. The
# owner principals (manifest bootstrap_principal_arns, and the account root) are the only ones that can:
#   - perform any S3 action on bootstrap/* objects: read, copy out, write, copy in, replicate in, restore, tag,
#     delete or roll back a version;
#   - change the bucket's configuration (policy, replication, inventory, logging, notifications, lifecycle,
#     encryption, versioning, Object Lock, ownership, CORS, website, ...), delete it, or delete any object version;
#   - replicate into any key of the bucket.
# No principal reaches the bucket through an access point (identity policies see an access-point ARN there, so
# name-based denies elsewhere would not match).
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
  # first run too. Default encryption still uses the state key, and the state key's own policy (RR-02) binds it
  # to this bucket's objects.
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
    sid     = "DenyAccessPoints"
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
      test     = "Null"
      variable = "s3:DataAccessPointArn"
      values   = ["false"]
    }
  }

  statement {
    sid       = "DenyBootstrapStateExceptOwner"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = ["${local.state_bucket_arn}/bootstrap/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = local.owner_principal_arns
    }
  }

  statement {
    sid    = "DenyStateMovementExceptOwner"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket*", "s3:PutBucket*", "s3:Put*Configuration", "s3:PutObjectAcl", "s3:PutObjectVersionAcl",
      "s3:PutObjectRetention", "s3:PutObjectLegalHold", "s3:DeleteObjectVersion*", "s3:BypassGovernanceRetention",
      "s3:Replicate*", "s3:ObjectOwnerOverrideToBucketOwner",
    ]
    resources = [local.state_bucket_arn, "${local.state_bucket_arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = local.owner_principal_arns
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.state]
}
