# Staging buckets (AUT-103). Names are fixed by the bootstrap: the deploy role writes only the artifacts bucket, the
# evidence role only the evidence bucket, and the plan, deploy and evidence roles may not read the Litestream,
# snapshot and anchor objects. Every bucket: SSE-KMS with a bucket key, versioning, all public access blocked, ACLs
# disabled (BucketOwnerEnforced), TLS only, no principal of another account, prevent_destroy.
#
# Companion resources name the bucket by its name (known at plan time), not its id: the plan guard checks that each
# new bucket has every control above.

locals {
  buckets = {
    litestream = { name = "${var.name_prefix}-litestream-${var.account_id}", key = var.data_key_arn, lock = false }
    snapshots  = { name = "${var.name_prefix}-snapshots-${var.account_id}", key = var.data_key_arn, lock = true }
    anchor     = { name = "${var.name_prefix}-anchor-${var.account_id}", key = var.data_key_arn, lock = true }
    artifacts  = { name = "${var.name_prefix}-artifacts-${var.account_id}", key = var.data_key_arn, lock = false }
    evidence   = { name = "veda-evidence-${var.account_id}", key = var.audit_key_arn, lock = true }
    logs       = { name = "${var.name_prefix}-logs-${var.account_id}", key = var.audit_key_arn, lock = false }
  }

  arn       = { for k, b in local.buckets : k => "arn:aws:s3:::${b.name}" }
  trail_arn = "arn:aws:cloudtrail:${var.region}:${var.account_id}:trail/${var.trail_name}"

  # Lifecycle per bucket; every bucket also aborts incomplete multipart uploads after 7 days.
  lifecycle = {
    litestream = [{ id = "noncurrent-versions", prefix = "", expire_days = null, noncurrent_days = var.retention.litestream_noncurrent_days }]
    # The application locks each snapshot for 35 days (COMPLIANCE); expiry acts once the lock has ended.
    snapshots = [{ id = "expire-snapshots", prefix = "", expire_days = var.retention.snapshots_expire_days, noncurrent_days = 1 }]
    anchor    = []
    artifacts = [{ id = "expire-artifacts", prefix = "", expire_days = var.retention.artifacts_expire_days, noncurrent_days = var.retention.artifacts_noncurrent_days }]
    evidence  = []
    logs = [
      { id = "expire-cloudtrail", prefix = "cloudtrail/", expire_days = var.retention.logs_cloudtrail_expire_days, noncurrent_days = 1 },
      { id = "expire-vpc-flow", prefix = "vpc-flow/", expire_days = var.retention.logs_flow_expire_days, noncurrent_days = 1 },
    ]
  }

  common_statements = {
    for k, b in local.buckets : k => [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [local.arn[k], "${local.arn[k]}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
      {
        Sid       = "DenyOtherAccounts"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [local.arn[k], "${local.arn[k]}/*"]
        Condition = {
          StringNotEquals = { "aws:PrincipalAccount" = var.account_id }
          Bool            = { "aws:PrincipalIsAWSService" = "false" }
        }
      },
    ]
  }

  # Locked buckets: nothing is written without an Object Lock mode, and nothing is deleted (lifecycle expiry is not a
  # principal and still applies to the snapshots once their lock ends).
  lock_statements = [
    {
      Sid       = "DenyUnlockedWrites"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:PutObject"
      Resource  = "bucket/*" # replaced per bucket below
      Condition = { Null = { "s3:object-lock-mode" = "true" } }
    },
    {
      Sid       = "DenyDeletes"
      Effect    = "Deny"
      Principal = "*"
      Action    = ["s3:DeleteObject", "s3:DeleteObjectVersion"]
      Resource  = "bucket/*" # replaced per bucket below
    },
  ]

  # The logs bucket: CloudTrail (the Veda trail) and VPC flow-log delivery write their own prefixes.
  delivery_statements = [
    {
      Sid       = "CloudTrailAclCheck"
      Effect    = "Allow"
      Principal = { Service = "cloudtrail.amazonaws.com" }
      Action    = "s3:GetBucketAcl"
      Resource  = local.arn["logs"]
      Condition = { StringEquals = { "aws:SourceArn" = local.trail_arn } }
    },
    {
      Sid       = "CloudTrailWrite"
      Effect    = "Allow"
      Principal = { Service = "cloudtrail.amazonaws.com" }
      Action    = "s3:PutObject"
      Resource  = "${local.arn["logs"]}/cloudtrail/AWSLogs/${var.account_id}/*"
      Condition = { StringEquals = { "aws:SourceArn" = local.trail_arn, "s3:x-amz-acl" = "bucket-owner-full-control" } }
    },
    {
      Sid       = "FlowLogDeliveryCheck"
      Effect    = "Allow"
      Principal = { Service = "delivery.logs.amazonaws.com" }
      Action    = ["s3:GetBucketAcl", "s3:ListBucket"]
      Resource  = local.arn["logs"]
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:logs:${var.region}:${var.account_id}:*" }
      }
    },
    {
      Sid       = "FlowLogDeliveryWrite"
      Effect    = "Allow"
      Principal = { Service = "delivery.logs.amazonaws.com" }
      Action    = "s3:PutObject"
      Resource  = "${local.arn["logs"]}/vpc-flow/AWSLogs/${var.account_id}/*"
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.account_id, "s3:x-amz-acl" = "bucket-owner-full-control" }
        ArnLike      = { "aws:SourceArn" = "arn:aws:logs:${var.region}:${var.account_id}:*" }
      }
    },
  ]
}

resource "aws_s3_bucket" "this" {
  #checkov:skip=CKV_AWS_18:No server access logs: CloudTrail data events cover the anchor and evidence buckets (AUT-104); access logs would add cost and a log loop
  #checkov:skip=CKV_AWS_144:No cross-region replication: Mumbai only (owner decision OD-B1); backups are Litestream and Object-Locked snapshots
  #checkov:skip=CKV2_AWS_62:No event notifications: nothing consumes them in staging
  for_each = local.buckets

  bucket              = each.value.name
  object_lock_enabled = each.value.lock

  tags = { Name = each.value.name, purpose = each.key }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_ownership_controls" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].bucket

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = local.buckets

  bucket                  = aws_s3_bucket.this[each.key].bucket
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].bucket

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].bucket

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = each.value.key
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].bucket

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  dynamic "rule" {
    for_each = local.lifecycle[each.key]
    content {
      id     = rule.value.id
      status = "Enabled"

      filter {
        prefix = rule.value.prefix
      }

      dynamic "expiration" {
        for_each = rule.value.expire_days == null ? [] : [rule.value.expire_days]
        content {
          days = expiration.value
        }
      }

      noncurrent_version_expiration {
        noncurrent_days = rule.value.noncurrent_days
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}

resource "aws_s3_bucket_policy" "this" {
  for_each = local.buckets

  bucket = aws_s3_bucket.this[each.key].bucket
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      local.common_statements[each.key],
      [for s in local.lock_statements : merge(s, { Resource = "${local.arn[each.key]}/*" }) if contains(["snapshots", "anchor"], each.key)],
      [for s in local.delivery_statements : s if each.key == "logs"],
    )
  })

  depends_on = [aws_s3_bucket_public_access_block.this]
}

# Evidence: every object locked in COMPLIANCE mode for the decided period (storage.evidence_lock_*). The snapshot and
# anchor buckets have Object Lock enabled without a default: the application sets each object's lock (35 days for
# snapshots; 3650 days for anchors, decision anchor_retention).
resource "aws_s3_bucket_object_lock_configuration" "evidence" {
  bucket = aws_s3_bucket.this["evidence"].bucket

  rule {
    default_retention {
      mode = var.retention.evidence_lock_mode
      days = var.retention.evidence_lock_days
    }
  }
}
