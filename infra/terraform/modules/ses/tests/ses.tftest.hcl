# Offline tests of the email foundation (AUT-111). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  name_prefix           = "veda-stg"
  account_id            = "111122223333"
  region                = "ap-south-1"
  sender_domain         = "staging.vedaspaces.com"
  sender_local_part     = "no-reply"
  sandbox_recipient     = "owner@example.com"
  alarm_topic_arn       = "arn:aws:sns:ap-south-1:111122223333:veda-stg-alarms"
  bounce_rate_threshold = 0.05
}

run "staging_domain_with_dkim" {
  command = plan

  assert {
    condition     = aws_sesv2_email_identity.sender.email_identity == "staging.vedaspaces.com" && one(aws_sesv2_email_identity.sender.dkim_signing_attributes).next_signing_key_length == "RSA_2048_BIT"
    error_message = "the sender is the staging subdomain with 2048-bit Easy DKIM"
  }

  assert {
    condition     = output.from_address == "no-reply@staging.vedaspaces.com" && output.sender == "Veda Spaces Staging <no-reply@staging.vedaspaces.com>"
    error_message = "one From address"
  }
}

run "configuration_set_suppresses_and_requires_tls" {
  command = plan

  assert {
    condition     = toset(one(aws_sesv2_configuration_set.this.suppression_options).suppressed_reasons) == toset(["BOUNCE", "COMPLAINT"])
    error_message = "bounced and complaining addresses are not sent to again"
  }

  assert {
    condition     = one(aws_sesv2_configuration_set.this.delivery_options).tls_policy == "REQUIRE" && one(aws_sesv2_configuration_set.this.reputation_options).reputation_metrics_enabled
    error_message = "TLS required to the receiving server; reputation metrics on"
  }
}

run "failure_alarms" {
  command = plan

  assert {
    condition     = aws_cloudwatch_metric_alarm.bounce_rate.namespace == "AWS/SES" && aws_cloudwatch_metric_alarm.bounce_rate.threshold == 0.05 && aws_cloudwatch_metric_alarm.rejects.metric_name == "Reject"
    error_message = "bounce rate and rejects, on the free account metrics"
  }
}

run "apex_domain_refused" {
  command = plan

  variables {
    sender_domain = "vedaspaces.com"
  }

  expect_failures = [var.sender_domain]
}

run "host_may_reach_sandbox_recipients_without_naming_them" {
  command = plan

  assert {
    condition     = contains(output.send_resources, "arn:aws:ses:ap-south-1:111122223333:identity/*@*") && !contains(output.send_resources, "arn:aws:ses:ap-south-1:111122223333:identity/*")
    error_message = "the sandbox recipients are email-address identities only, never every identity"
  }

  assert {
    condition     = length([for r in output.send_resources : r if strcontains(r, "owner@example.com")]) == 0
    error_message = "the sensitive recipient address is never named in the host policy"
  }
}
