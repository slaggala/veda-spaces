# Offline tests of the monitoring foundation (AUT-110). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  name_prefix          = "veda-stg"
  account_id           = "111122223333"
  region               = "ap-south-1"
  audit_key_arn        = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-0000000a0d17"
  audit_key_alias      = "alias/veda-stg-audit"
  log_group_prefix     = "/veda/staging"
  log_retention_days   = 30
  alert_email          = "owner@example.com"
  trail_log_group_name = "/veda/staging/cloudtrail"
  tampering_metric     = { namespace = "Veda/Audit", name = "AuditTampering" }
  thresholds           = { server_errors_per_5min = 5, cpu_percent = 80, memory_percent = 85, data_disk_percent = 80, root_disk_percent = 85 }
}

run "logs_encrypted_and_expiring" {
  command = plan

  assert {
    condition     = toset([for g in aws_cloudwatch_log_group.this : g.name]) == toset(["/veda/staging/app", "/veda/staging/host"]) && alltrue([for g in aws_cloudwatch_log_group.this : g.kms_key_id == var.audit_key_arn && g.retention_in_days == 30])
    error_message = "application and host log groups, audit key, 30 days"
  }
}

run "a_fixed_set_of_metric_filters_not_emf" {
  command = plan

  assert {
    condition     = length(aws_cloudwatch_log_metric_filter.app) == 7 && alltrue([for f in aws_cloudwatch_log_metric_filter.app : one(f.metric_transformation).namespace == "Veda/App"])
    error_message = "seven application metrics, one namespace: the custom-metric count is bounded (cost)"
  }

  assert {
    condition     = strcontains(aws_cloudwatch_log_metric_filter.app["LeadIntakeFailures"].pattern, "/api/v1/public/leads") && strcontains(aws_cloudwatch_log_metric_filter.app["LeadIntakeFailures"].pattern, "$.status >= 500")
    error_message = "lead-submission failures are 5xx answers of the public lead route"
  }

  assert {
    condition     = output.custom_metric_count == 8
    error_message = "before the host exists: 7 filters and the tampering metric"
  }
}

run "alarms_notify_the_encrypted_topic" {
  command = plan

  assert {
    condition     = aws_sns_topic.alarms.name == "veda-stg-alarms" && aws_sns_topic.alarms.kms_master_key_id == "alias/veda-stg-audit"
    error_message = "the alarm topic is encrypted with the audit key"
  }

  assert {
    condition     = alltrue([for a in aws_cloudwatch_metric_alarm.app : startswith(a.alarm_name, "veda-stg-") && length(a.alarm_actions) == 1])
    error_message = "every alarm is veda-stg-* (the drill scope of the bootstrap) and notifies the topic"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.app["snapshot-missing"].treat_missing_data == "breaching" && aws_cloudwatch_metric_alarm.trail_delivery.treat_missing_data == "breaching"
    error_message = "silence is an alarm for the snapshot heartbeat and the trail delivery"
  }

  assert {
    condition     = one([for s in jsondecode(aws_sns_topic_policy.alarms.policy).Statement : s.Condition.StringEquals["aws:SourceAccount"] if s.Sid == "CloudWatchAlarmsOfThisAccount"]) == "111122223333"
    error_message = "only CloudWatch alarms of this account publish"
  }

  assert {
    condition     = aws_sqs_queue.alarm_capture.name == "veda-stg-alarm-capture" && aws_sqs_queue.alarm_capture.sqs_managed_sse_enabled
    error_message = "the drill capture queue the bootstrap deploy role reads, encrypted"
  }
}

run "no_host_alarm_before_the_host" {
  command = plan

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.host) == 0
    error_message = "host alarms need the instance (AUT-108)"
  }
}

run "host_alarms_with_the_instance" {
  command = plan

  variables {
    host_alarms_enabled = true
    instance_id         = "i-0123456789abcdef0"
  }

  assert {
    condition     = toset(keys(aws_cloudwatch_metric_alarm.host)) == toset(["host-status-check", "host-cpu", "host-memory", "host-data-disk", "host-root-disk", "api-health"])
    error_message = "status, CPU, memory, both disks and the health heartbeat"
  }

  assert {
    condition     = aws_cloudwatch_metric_alarm.host["api-health"].treat_missing_data == "breaching" && aws_cloudwatch_metric_alarm.host["host-data-disk"].dimensions.path == "/var/lib/veda"
    error_message = "a silent health check is an outage; the data disk is /var/lib/veda"
  }

  assert {
    condition     = output.custom_metric_count == 12
    error_message = "with the host: plus memory, two disks and the health metric"
  }
}

run "another_prefix_refused" {
  command = plan

  variables {
    name_prefix = "veda-x"
  }

  expect_failures = [var.name_prefix]
}
