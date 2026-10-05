# CloudTrail (AUT-104). One multi-region trail of management events with log-file validation (tamper evidence),
# encrypted with the audit key, delivered to the logs bucket and copied to CloudWatch Logs for alarms (AUT-110).
#
# veda-boundary denies every role cloudtrail:StopLogging, DeleteTrail, UpdateTrail and Put*Selectors: once created, the
# trail cannot be stopped, re-scoped or deleted by any workflow. Event selectors therefore cannot be set by Terraform
# (it calls PutEventSelectors): the trail records management events (the default), and the S3 data events on the
# anchor and evidence buckets are added once by the owner session (runbook). The plan guard refuses selectors here.

locals {
  trail_arn = "arn:aws:cloudtrail:${var.region}:${var.account_id}:trail/${var.trail_name}"
  # Built from known values so the role policy and the trail settings are fully visible in the plan.
  log_group_name = "${var.log_group_prefix}/cloudtrail"
  log_group_arn  = "arn:aws:logs:${var.region}:${var.account_id}:log-group:${local.log_group_name}"
}

resource "aws_cloudwatch_log_group" "trail" {
  #checkov:skip=CKV_AWS_338:Retention is a staging decision (cloudtrail.log_group_retention_days); the S3 copy is the record
  name              = local.log_group_name
  retention_in_days = var.log_group_retention_days
  kms_key_id        = var.audit_key_arn
}

resource "aws_iam_role" "trail_logs" {
  name                 = "${var.name_prefix}-cloudtrail-logs"
  description          = "CloudTrail delivery of ${var.trail_name} to ${local.log_group_name} (AUT-104)"
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudtrail.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = var.account_id, "aws:SourceArn" = local.trail_arn } }
    }]
  })
}

resource "aws_iam_role_policy" "trail_logs" {
  name = "write-trail-log-group"
  role = aws_iam_role.trail_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "${local.log_group_arn}:log-stream:*"
    }]
  })
}

resource "aws_cloudtrail" "this" {
  #checkov:skip=CKV_AWS_252:No SNS notification per log file: delivery and tampering alarms come from CloudWatch Logs (AUT-110)
  #checkov:skip=CKV2_AWS_10:Integrated with CloudWatch Logs (cloud_watch_logs_group_arn); checkov does not resolve the reference
  name                          = var.trail_name
  s3_bucket_name                = var.logs_bucket_name
  s3_key_prefix                 = "cloudtrail"
  is_multi_region_trail         = true
  include_global_service_events = true
  enable_log_file_validation    = true
  enable_logging                = true
  kms_key_id                    = var.audit_key_arn
  cloud_watch_logs_group_arn    = "${local.log_group_arn}:*"
  cloud_watch_logs_role_arn     = aws_iam_role.trail_logs.arn

  depends_on = [aws_iam_role_policy.trail_logs, aws_cloudwatch_log_group.trail]

  lifecycle {
    prevent_destroy = true
  }
}

# Tampering with the audit trail, the keys or the bucket protections (alarm in AUT-110). Read from the trail's own
# CloudWatch copy; a single metric keeps the custom-metric count (and its cost) bounded.
resource "aws_cloudwatch_log_metric_filter" "tampering" {
  name           = "${var.name_prefix}-audit-tampering"
  log_group_name = aws_cloudwatch_log_group.trail.name
  pattern = join(" ", [
    "{ ($.eventSource = cloudtrail.amazonaws.com && ($.eventName = StopLogging || $.eventName = DeleteTrail || $.eventName = UpdateTrail || $.eventName = PutEventSelectors || $.eventName = PutInsightSelectors)) ||",
    "($.eventSource = kms.amazonaws.com && ($.eventName = ScheduleKeyDeletion || $.eventName = DisableKey || $.eventName = PutKeyPolicy)) ||",
    "($.eventSource = s3.amazonaws.com && ($.eventName = PutBucketPolicy || $.eventName = DeleteBucketPolicy || $.eventName = PutBucketPublicAccessBlock || $.eventName = DeleteBucketPublicAccessBlock || $.eventName = PutObjectLockConfiguration)) }",
  ])

  metric_transformation {
    name          = "AuditTampering"
    namespace     = "Veda/Audit"
    value         = "1"
    default_value = "0"
  }
}
