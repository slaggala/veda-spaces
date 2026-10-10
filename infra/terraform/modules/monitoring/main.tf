# Monitoring foundation (AUT-110). Logs: the application's container output (/veda/staging/app, Docker awslogs) and the
# host's system and deploy logs (/veda/staging/host, CloudWatch agent). Metrics: a FIXED set of log metric filters, not
# Embedded Metric Format. The application's EMF request metrics carry Route x StatusClass dimensions; every combination
# is a billed custom metric, which alone could exceed the 25 USD budget (cost report). The filters bound the count.
# Alarms notify the encrypted topic veda-stg-alarms: the owner's address by email, and the queue veda-stg-alarm-capture
# that drills read (bootstrap deploy role). Host alarms are added once the instance exists (AUT-108).
# Alarms fed by the deployed application, the CloudWatch agent or the heartbeat ("deployed = true") keep their actions
# off until deployment is enabled (deployment_alarms_enabled = deploy.enabled, review R4): before the first deploy they
# would only report missing data. The audit, trail, EC2 status, CPU and SES alarms are always active.

locals {
  p          = var.name_prefix
  app_group  = "${var.log_group_prefix}/app"
  host_group = "${var.log_group_prefix}/host"
  # Built from the name so every alarm action is known at plan time (the plan guard checks them).
  topic_arn = "arn:aws:sns:${var.region}:${var.account_id}:${var.name_prefix}-alarms"

  # Application signals, from the structured JSON log lines (structlog: event, route, status; EMF fields by name).
  filters = {
    ServerErrors         = { pattern = "{ $.event = \"request\" && $.status >= 500 }", value = "1" }
    LeadIntakeFailures   = { pattern = "{ $.event = \"request\" && $.route = \"/api/v1/public/leads\" && $.status >= 500 }", value = "1" }
    NotificationFailures = { pattern = "{ $.event = \"outbox_handler_failed*\" }", value = "1" }
    OutboxDead           = { pattern = "{ $.OutboxDead >= 1 }", value = "$.OutboxDead" }
    ScheduledJobFailed   = { pattern = "{ $.ScheduledJobFailed >= 1 }", value = "1" }
    SnapshotCompleted    = { pattern = "{ $.SnapshotCompleted >= 1 }", value = "1" }
    ChainAnchorFailed    = { pattern = "{ $.ChainAnchorFailed >= 1 }", value = "1" }
    # Catalog V3 media (targeted media enablement). The signals carry counts and ages only: no filename, key,
    # customer identifier, rate or content reaches a metric or an alarm.
    MediaScannerUnavailable   = { pattern = "{ $.MediaScannerUnavailable >= 1 }", value = "1" }
    MediaScanFailed           = { pattern = "{ $.MediaScanFailed >= 1 }", value = "1" }
    MediaInfected             = { pattern = "{ $.MediaInfected >= 1 }", value = "1" }
    MediaPendingMaxAgeSeconds = { pattern = "{ $.MediaPendingMaxAgeSeconds >= 0 }", value = "$.MediaPendingMaxAgeSeconds" }
    MediaSignatureAgeHours    = { pattern = "{ $.MediaSignatureAgeHours >= 0 }", value = "$.MediaSignatureAgeHours" }
    MediaNonCleanRequested    = { pattern = "{ $.MediaNonCleanRequested >= 1 }", value = "1" }
    MediaStorageAccessDenied  = { pattern = "{ $.MediaStorageAccessDenied >= 1 }", value = "1" }
    MediaKmsAccessDenied      = { pattern = "{ $.MediaKmsAccessDenied >= 1 }", value = "1" }
  }

  # name => metric, statistic, threshold, comparison, period, missing-data treatment, description
  app_alarms = {
    "app-5xx"                   = { deployed = true, ns = "Veda/App", metric = "ServerErrors", stat = "Sum", threshold = var.thresholds.server_errors_per_5min, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "API 5xx responses" }
    "lead-intake-failures"      = { deployed = true, ns = "Veda/App", metric = "LeadIntakeFailures", stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "Public lead submissions failing (5xx)" }
    "notification-failures"     = { deployed = true, ns = "Veda/App", metric = "NotificationFailures", stat = "Sum", threshold = 3, cmp = "GreaterThanOrEqualToThreshold", period = 900, missing = "notBreaching", what = "Email and other outbox handlers failing (the lead stays committed, NOTIF-008)" }
    "outbox-dead"               = { deployed = true, ns = "Veda/App", metric = "OutboxDead", stat = "Maximum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "Outbox events dead-lettered" }
    "scheduled-job-failed"      = { deployed = true, ns = "Veda/App", metric = "ScheduledJobFailed", stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "A scheduled job failed" }
    "snapshot-missing"          = { deployed = true, ns = "Veda/App", metric = "SnapshotCompleted", stat = "Sum", threshold = 1, cmp = "LessThanThreshold", period = 86400, missing = "breaching", what = "No completed snapshot in 24 hours (RR-14)" }
    "chain-anchor-failed"       = { deployed = true, ns = "Veda/App", metric = "ChainAnchorFailed", stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "A security-chain anchor failed (FC-01)" }
    "media-scanner-unavailable" = { deployed = true, ns = "Veda/App", metric = "MediaScannerUnavailable", stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "The malware scanner could not be reached (uploads stay FAILED and are never served)" }
    "media-scan-failed"         = { deployed = true, ns = "Veda/App", metric = "MediaScanFailed", stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "A media scan did not complete (the object stays FAILED and is retried)" }
    "media-infected"            = { deployed = true, ns = "Veda/App", metric = "MediaInfected", stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "An uploaded file was detected as malware (refused, nothing stored)" }
    "media-pending-age"         = { deployed = true, ns = "Veda/App", metric = "MediaPendingMaxAgeSeconds", stat = "Maximum", threshold = var.thresholds.media_pending_seconds, cmp = "GreaterThanThreshold", period = 900, missing = "notBreaching", what = "Media waiting for a scan for too long" }
    "media-signatures-outdated" = { deployed = true, ns = "Veda/App", metric = "MediaSignatureAgeHours", stat = "Maximum", threshold = var.thresholds.scanner_signature_hours, cmp = "GreaterThanThreshold", period = 3600, missing = "notBreaching", what = "The scanner's signatures are older than allowed (freshclam not updating)" }
    "media-non-clean-requested" = { deployed = true, ns = "Veda/App", metric = "MediaNonCleanRequested", stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "Delivery was asked for a released object that is not CLEAN (refused)" }
    "media-s3-access-denied"    = { deployed = true, ns = "Veda/App", metric = "MediaStorageAccessDenied", stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "S3 refused the host on the media bucket" }
    "media-kms-access-denied"   = { deployed = true, ns = "Veda/App", metric = "MediaKmsAccessDenied", stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "KMS refused the host for media" }
    "audit-tampering"           = { deployed = false, ns = var.tampering_metric.namespace, metric = var.tampering_metric.name, stat = "Sum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "notBreaching", what = "Trail, key or bucket protection changed (AUT-104)" }
  }

  host_alarms = !var.host_alarms_enabled ? {} : {
    "host-status-check" = { deployed = false, ns = "AWS/EC2", metric = "StatusCheckFailed", dims = { InstanceId = var.instance_id }, stat = "Maximum", threshold = 1, cmp = "GreaterThanOrEqualToThreshold", period = 300, missing = "breaching", what = "Instance or system status check failed (EC2 recovers it automatically)" }
    "host-cpu"          = { deployed = false, ns = "AWS/EC2", metric = "CPUUtilization", dims = { InstanceId = var.instance_id }, stat = "Average", threshold = var.thresholds.cpu_percent, cmp = "GreaterThanThreshold", period = 900, missing = "notBreaching", what = "CPU high for 15 minutes" }
    "host-memory"       = { deployed = true, ns = "CWAgent", metric = "mem_used_percent", dims = { InstanceId = var.instance_id }, stat = "Average", threshold = var.thresholds.memory_percent, cmp = "GreaterThanThreshold", period = 300, missing = "breaching", what = "Memory high (or the agent stopped reporting)" }
    "host-data-disk"    = { deployed = true, ns = "CWAgent", metric = "disk_used_percent", dims = { InstanceId = var.instance_id, path = "/var/lib/veda" }, stat = "Maximum", threshold = var.thresholds.data_disk_percent, cmp = "GreaterThanThreshold", period = 300, missing = "breaching", what = "Data volume (/var/lib/veda) filling up" }
    "host-root-disk"    = { deployed = true, ns = "CWAgent", metric = "disk_used_percent", dims = { InstanceId = var.instance_id, path = "/" }, stat = "Maximum", threshold = var.thresholds.root_disk_percent, cmp = "GreaterThanThreshold", period = 300, missing = "breaching", what = "Root volume filling up (images, logs)" }
    "scanner-restarts"  = { deployed = true, ns = "Veda/Host", metric = "ScannerRestarts", dims = { InstanceId = var.instance_id }, stat = "Maximum", threshold = var.thresholds.scanner_restarts, cmp = "GreaterThanOrEqualToThreshold", period = 900, missing = "notBreaching", what = "The malware scanner keeps restarting (memory or signature reload)" }
    "api-health"        = { deployed = true, ns = "Veda/Host", metric = "HealthReady", dims = { InstanceId = var.instance_id }, stat = "Minimum", threshold = 1, cmp = "LessThanThreshold", period = 300, missing = "breaching", what = "/health/ready failing or not reporting (uptime)" }
  }
}

resource "aws_cloudwatch_log_group" "this" {
  for_each = { app = local.app_group, host = local.host_group }

  name              = each.value
  retention_in_days = var.log_retention_days
  kms_key_id        = var.audit_key_arn
}

resource "aws_cloudwatch_log_metric_filter" "app" {
  for_each = local.filters

  name           = "${local.p}-${lower(replace(each.key, "/([a-z])([A-Z])/", "$1-$2"))}"
  log_group_name = aws_cloudwatch_log_group.this["app"].name
  pattern        = each.value.pattern

  metric_transformation {
    name      = each.key
    namespace = "Veda/App"
    value     = each.value.value
  }
}

resource "aws_sns_topic" "alarms" {
  name              = "${local.p}-alarms"
  kms_master_key_id = var.audit_key_alias
}

resource "aws_sns_topic_policy" "alarms" {
  arn = aws_sns_topic.alarms.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "CloudWatchAlarmsOfThisAccount"
        Effect    = "Allow"
        Principal = { Service = "cloudwatch.amazonaws.com" }
        Action    = "sns:Publish"
        Resource  = local.topic_arn
        Condition = { StringEquals = { "aws:SourceAccount" = var.account_id } }
      },
    ]
  })
}

# Email requires the owner to confirm the subscription once (the confirmation link AWS sends).
resource "aws_sns_topic_subscription" "owner" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Drills (RR-09, FC-01 tamper drill) read alarm notifications here; the bootstrap deploy role may receive and delete.
resource "aws_sqs_queue" "alarm_capture" {
  name                      = "${local.p}-alarm-capture"
  message_retention_seconds = 86400
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue_policy" "alarm_capture" {
  queue_url = aws_sqs_queue.alarm_capture.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AlarmTopicOnly"
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = "arn:aws:sqs:${var.region}:${var.account_id}:${local.p}-alarm-capture"
      Condition = { ArnEquals = { "aws:SourceArn" = local.topic_arn } }
    }]
  })
}

resource "aws_sns_topic_subscription" "capture" {
  topic_arn            = aws_sns_topic.alarms.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.alarm_capture.arn
  raw_message_delivery = true
}

resource "aws_cloudwatch_metric_alarm" "app" {
  for_each = local.app_alarms

  alarm_name          = "${local.p}-${each.key}"
  actions_enabled     = !each.value.deployed || var.deployment_alarms_enabled
  alarm_description   = each.value.what
  namespace           = each.value.ns
  metric_name         = each.value.metric
  statistic           = each.value.stat
  threshold           = each.value.threshold
  comparison_operator = each.value.cmp
  period              = each.value.period
  evaluation_periods  = 1
  treat_missing_data  = each.value.missing
  alarm_actions       = [local.topic_arn]
  ok_actions          = [local.topic_arn]

  depends_on = [aws_sns_topic.alarms]
}

# The trail's CloudWatch copy stops arriving: delivery failed or the trail stopped (AUT-104).
resource "aws_cloudwatch_metric_alarm" "trail_delivery" {
  alarm_name          = "${local.p}-trail-delivery"
  actions_enabled     = true # always active (review R4)
  alarm_description   = "No CloudTrail events reached ${var.trail_log_group_name} for an hour (AUT-104)"
  namespace           = "AWS/Logs"
  metric_name         = "IncomingLogEvents"
  dimensions          = { LogGroupName = var.trail_log_group_name }
  statistic           = "Sum"
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  period              = 3600
  evaluation_periods  = 1
  treat_missing_data  = "breaching"
  alarm_actions       = [local.topic_arn]
  ok_actions          = [local.topic_arn]

  depends_on = [aws_sns_topic.alarms]
}

resource "aws_cloudwatch_metric_alarm" "host" {
  for_each = local.host_alarms

  alarm_name          = "${local.p}-${each.key}"
  actions_enabled     = !each.value.deployed || var.deployment_alarms_enabled
  alarm_description   = each.value.what
  namespace           = each.value.ns
  metric_name         = each.value.metric
  dimensions          = each.value.dims
  statistic           = each.value.stat
  threshold           = each.value.threshold
  comparison_operator = each.value.cmp
  period              = each.value.period
  evaluation_periods  = 1
  treat_missing_data  = each.value.missing
  alarm_actions       = [local.topic_arn]
  ok_actions          = [local.topic_arn]

  depends_on = [aws_sns_topic.alarms]
}

resource "aws_cloudwatch_dashboard" "staging" {
  dashboard_name = "${local.p}-overview"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "alarm", x = 0, y = 0, width = 24, height = 4
        properties = {
          title  = "Veda staging alarms"
          alarms = concat([for a in aws_cloudwatch_metric_alarm.app : a.arn], [aws_cloudwatch_metric_alarm.trail_delivery.arn], [for a in aws_cloudwatch_metric_alarm.host : a.arn])
        }
      },
      {
        type = "metric", x = 0, y = 4, width = 12, height = 6
        properties = {
          title   = "Application", region = var.region, stat = "Sum", period = 300
          metrics = [for m in ["ServerErrors", "LeadIntakeFailures", "NotificationFailures", "OutboxDead"] : ["Veda/App", m]]
        }
      },
      {
        type = "log", x = 12, y = 4, width = 12, height = 6
        properties = {
          title  = "Recent API errors"
          region = var.region
          query  = "SOURCE '${local.app_group}' | fields @timestamp, route, status | filter event = 'request' and status >= 500 | sort @timestamp desc | limit 20"
        }
      },
    ]
  })
}
