# Offline tests of the trail (AUT-104). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  name_prefix              = "veda-stg"
  account_id               = "111122223333"
  region                   = "ap-south-1"
  trail_name               = "veda-stg-trail"
  logs_bucket_name         = "veda-stg-logs-111122223333"
  audit_key_arn            = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-0000000a0d17"
  log_group_prefix         = "/veda/staging"
  log_group_retention_days = 30
  permissions_boundary_arn = "arn:aws:iam::111122223333:policy/veda-boundary"
}

run "multi_region_validated_encrypted_trail" {
  command = plan

  assert {
    condition = (
      aws_cloudtrail.this.is_multi_region_trail && aws_cloudtrail.this.include_global_service_events &&
      aws_cloudtrail.this.enable_log_file_validation && aws_cloudtrail.this.enable_logging &&
      aws_cloudtrail.this.kms_key_id == var.audit_key_arn
    )
    error_message = "multi-region, global events, log-file validation, logging on, audit key"
  }

  assert {
    condition     = aws_cloudtrail.this.s3_bucket_name == "veda-stg-logs-111122223333" && aws_cloudtrail.this.s3_key_prefix == "cloudtrail"
    error_message = "delivered to the logs bucket under cloudtrail/ (the bucket policy admits that prefix only)"
  }

  assert {
    condition     = length(aws_cloudtrail.this.event_selector) == 0 && length(aws_cloudtrail.this.advanced_event_selector) == 0
    error_message = "no selectors: veda-boundary denies PutEventSelectors; data events are an owner-session step"
  }
}

run "cloudwatch_copy_encrypted_and_role_bound_to_the_trail" {
  command = plan

  assert {
    condition     = aws_cloudwatch_log_group.trail.name == "/veda/staging/cloudtrail" && aws_cloudwatch_log_group.trail.kms_key_id == var.audit_key_arn && aws_cloudwatch_log_group.trail.retention_in_days == 30
    error_message = "the CloudWatch copy is /veda/staging/cloudtrail, audit key, 30 days"
  }

  assert {
    condition = (
      jsondecode(aws_iam_role.trail_logs.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceArn"] == "arn:aws:cloudtrail:ap-south-1:111122223333:trail/veda-stg-trail" &&
      aws_iam_role.trail_logs.permissions_boundary == var.permissions_boundary_arn
    )
    error_message = "the delivery role is bounded and assumable by CloudTrail for this trail only"
  }

  assert {
    condition = (
      jsondecode(aws_iam_role_policy.trail_logs.policy).Statement[0].Action == ["logs:CreateLogStream", "logs:PutLogEvents"] &&
      jsondecode(aws_iam_role_policy.trail_logs.policy).Statement[0].Resource == "arn:aws:logs:ap-south-1:111122223333:log-group:/veda/staging/cloudtrail:log-stream:*" &&
      aws_cloudtrail.this.cloud_watch_logs_group_arn == "arn:aws:logs:ap-south-1:111122223333:log-group:/veda/staging/cloudtrail:*"
    )
    error_message = "the delivery role only writes streams of the trail's log group"
  }
}

run "tampering_filter_covers_trail_keys_and_buckets" {
  command = plan

  assert {
    condition = alltrue([for e in ["StopLogging", "DeleteTrail", "PutEventSelectors", "ScheduleKeyDeletion", "DisableKey", "PutBucketPolicy", "DeleteBucketPublicAccessBlock", "PutObjectLockConfiguration"] :
    strcontains(aws_cloudwatch_log_metric_filter.tampering.pattern, e)])
    error_message = "the tampering metric counts trail, key and bucket-protection changes"
  }
}
