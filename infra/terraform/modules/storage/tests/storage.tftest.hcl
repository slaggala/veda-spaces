# Offline tests of the staging buckets (AUT-103). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  name_prefix   = "veda-stg"
  account_id    = "111122223333"
  region        = "ap-south-1"
  data_key_arn  = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-00000000da7a"
  audit_key_arn = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-0000000a0d17"
  trail_name    = "veda-stg-trail"
  retention = {
    litestream_noncurrent_days  = 7
    snapshots_expire_days       = 42
    artifacts_expire_days       = 90
    artifacts_noncurrent_days   = 30
    logs_cloudtrail_expire_days = 90
    logs_flow_expire_days       = 30
    evidence_lock_mode          = "COMPLIANCE"
    evidence_lock_days          = 30
  }
}

run "the_six_bootstrap_names" {
  command = plan

  assert {
    condition = toset([for b in aws_s3_bucket.this : b.bucket]) == toset([
      "veda-stg-litestream-111122223333", "veda-stg-snapshots-111122223333", "veda-stg-anchor-111122223333",
      "veda-stg-artifacts-111122223333", "veda-evidence-111122223333", "veda-stg-logs-111122223333",
    ])
    error_message = "the bucket names the bootstrap roles and data-read denies are scoped to"
  }

  assert {
    condition     = [for k in ["snapshots", "anchor", "evidence"] : aws_s3_bucket.this[k].object_lock_enabled] == [true, true, true] && !aws_s3_bucket.this["litestream"].object_lock_enabled
    error_message = "Object Lock on snapshots, anchors and evidence only"
  }
}

run "every_bucket_private_encrypted_versioned" {
  command = plan

  assert {
    condition = alltrue([for p in aws_s3_bucket_public_access_block.this :
    p.block_public_acls && p.block_public_policy && p.ignore_public_acls && p.restrict_public_buckets])
    error_message = "all public access blocked"
  }

  assert {
    condition     = alltrue([for o in aws_s3_bucket_ownership_controls.this : one(o.rule).object_ownership == "BucketOwnerEnforced"])
    error_message = "ACLs disabled"
  }

  assert {
    condition     = alltrue([for v in aws_s3_bucket_versioning.this : one(v.versioning_configuration).status == "Enabled"])
    error_message = "versioning on every bucket"
  }

  assert {
    condition = (
      alltrue([for e in aws_s3_bucket_server_side_encryption_configuration.this : one(one(e.rule).apply_server_side_encryption_by_default).sse_algorithm == "aws:kms" && one(e.rule).bucket_key_enabled]) &&
      one(one(aws_s3_bucket_server_side_encryption_configuration.this["evidence"].rule).apply_server_side_encryption_by_default).kms_master_key_id == var.audit_key_arn &&
      one(one(aws_s3_bucket_server_side_encryption_configuration.this["anchor"].rule).apply_server_side_encryption_by_default).kms_master_key_id == var.data_key_arn
    )
    error_message = "SSE-KMS with bucket keys: audit key for evidence and logs, data key for the rest"
  }
}

run "policies_tls_only_and_account_only" {
  command = plan

  assert {
    condition = alltrue([for p in aws_s3_bucket_policy.this : length([for s in jsondecode(p.policy).Statement : s
    if s.Effect == "Deny" && contains(["DenyInsecureTransport", "DenyOtherAccounts"], s.Sid)]) == 2])
    error_message = "every bucket denies plain HTTP and other accounts"
  }

  assert {
    condition = alltrue([for k in ["snapshots", "anchor"] : length([for s in jsondecode(aws_s3_bucket_policy.this[k].policy).Statement : s
    if contains(["DenyUnlockedWrites", "DenyDeletes"], s.Sid)]) == 2])
    error_message = "snapshot and anchor writes must carry a lock; nothing is deleted"
  }

  assert {
    condition = alltrue([for k, p in aws_s3_bucket_policy.this : alltrue([for s in jsondecode(p.policy).Statement :
    alltrue([for r in flatten([s.Resource]) : startswith(r, "arn:aws:s3:::${aws_s3_bucket.this[k].bucket}")])])])
    error_message = "every statement names its own bucket (S3 rejects other resources)"
  }

  assert {
    condition = alltrue([for s in jsondecode(aws_s3_bucket_policy.this["logs"].policy).Statement :
    s.Effect == "Deny" || length(try(s.Condition, {})) > 0])
    error_message = "every service write to the logs bucket is bound by a condition"
  }

  assert {
    condition     = length([for s in jsondecode(aws_s3_bucket_policy.this["litestream"].policy).Statement : s if s.Effect == "Allow"]) == 0
    error_message = "data buckets allow nothing by policy (IAM decides inside the account)"
  }
}

run "evidence_compliance_lock" {
  command = plan

  assert {
    condition     = one(one(aws_s3_bucket_object_lock_configuration.evidence.rule).default_retention).mode == "COMPLIANCE" && one(one(aws_s3_bucket_object_lock_configuration.evidence.rule).default_retention).days == 30
    error_message = "evidence is locked in COMPLIANCE mode for the decided period"
  }
}

run "governance_lock_refused" {
  command = plan

  variables {
    retention = {
      litestream_noncurrent_days  = 7
      snapshots_expire_days       = 42
      artifacts_expire_days       = 90
      artifacts_noncurrent_days   = 30
      logs_cloudtrail_expire_days = 90
      logs_flow_expire_days       = 30
      evidence_lock_mode          = "GOVERNANCE"
      evidence_lock_days          = 30
    }
  }

  expect_failures = [var.retention]
}

run "snapshots_expiring_inside_their_lock_refused" {
  command = plan

  variables {
    retention = {
      litestream_noncurrent_days  = 7
      snapshots_expire_days       = 30
      artifacts_expire_days       = 90
      artifacts_noncurrent_days   = 30
      logs_cloudtrail_expire_days = 90
      logs_flow_expire_days       = 30
      evidence_lock_mode          = "COMPLIANCE"
      evidence_lock_days          = 30
    }
  }

  expect_failures = [var.retention]
}

run "bucket_names_outside_the_bootstrap_scope_refused" {
  command = plan

  variables {
    name_prefix = "veda-prod"
  }

  expect_failures = [var.name_prefix]
}
