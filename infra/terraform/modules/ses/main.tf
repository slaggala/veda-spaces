# Email delivery foundation (AUT-111), sandbox-aware. The account stays in the SES sandbox: it sends only to verified
# addresses, here the owner's (more recipients for rehearsals are added the same way, O11). Production access is an
# owner request, not Terraform.
#   - Sender: the staging domain identity with Easy DKIM. Its three CNAME records are published in Cloudflare by
#     AUT-202; until then SES reports the identity pending and refuses to send, which is safe: the outbox marks the
#     event FAILED and retries, and the lead is never rolled back (NOTIF-008, test_leads.py).
#   - Configuration set veda-stg: TLS required to the receiving server, reputation metrics, and the configuration-set
#     suppression list for bounces and complaints (a suppressed address is not sent to again).
#   - Alarms on the free account-level AWS/SES metrics: bounce rate and rejects.

resource "aws_sesv2_email_identity" "sender" {
  email_identity = var.sender_domain

  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }
}

resource "aws_sesv2_email_identity" "sandbox_recipient" {
  email_identity = var.sandbox_recipient
}

resource "aws_sesv2_configuration_set" "this" {
  configuration_set_name = var.name_prefix

  delivery_options {
    tls_policy = "REQUIRE"
  }

  reputation_options {
    reputation_metrics_enabled = true
  }

  sending_options {
    sending_enabled = true
  }

  suppression_options {
    suppressed_reasons = ["BOUNCE", "COMPLAINT"]
  }
}

resource "aws_cloudwatch_metric_alarm" "bounce_rate" {
  alarm_name          = "${var.name_prefix}-ses-bounce-rate"
  alarm_description   = "SES account bounce rate above ${var.bounce_rate_threshold} (AUT-111)"
  namespace           = "AWS/SES"
  metric_name         = "Reputation.BounceRate"
  statistic           = "Maximum"
  threshold           = var.bounce_rate_threshold
  comparison_operator = "GreaterThanThreshold"
  period              = 3600
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_topic_arn]
  ok_actions          = [var.alarm_topic_arn]
}

resource "aws_cloudwatch_metric_alarm" "rejects" {
  alarm_name          = "${var.name_prefix}-ses-rejects"
  alarm_description   = "SES rejected a message (AUT-111)"
  namespace           = "AWS/SES"
  metric_name         = "Reject"
  statistic           = "Sum"
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  period              = 3600
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_topic_arn]
  ok_actions          = [var.alarm_topic_arn]
}
