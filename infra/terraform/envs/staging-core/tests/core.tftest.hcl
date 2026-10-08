# Offline tests of the staging core root (AUT-301, AUT-112). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

override_data {
  target = module.network.data.aws_ec2_instance_type_offerings.host
  values = { locations = ["aps1-az1", "aps1-az2", "aps1-az3"] }
}

variables {
  account_manifest_path = "../../bootstrap/tests/fixtures/account.json"
  budget_config_path    = "tests/fixtures/budget.json"
  budget_alert_email    = "owner@example.com"
  warranty_policy_url   = "https://staging.vedaspaces.com/warranty"
}

run "root_reads_the_manifest" {
  command = plan

  assert {
    condition     = local.account_id == "111122223333"
    error_message = "the account must come from the manifest"
  }
}

run "region_other_than_mumbai_refused" {
  command = plan

  variables {
    aws_region = "us-east-1"
  }

  expect_failures = [var.aws_region]
}

# AUT-112: one monthly cost budget in USD with forecast alerts at 80% and 100% (O16), to the one recipient.
run "budget_monthly_cost_with_forecast_alerts" {
  command = plan

  assert {
    condition     = module.budget.name == "veda-staging-monthly-cost"
    error_message = "the budget name must come from the reviewed decision and be veda-*"
  }

  assert {
    condition     = module.budget.limit == { amount = "50.00", unit = "USD" }
    error_message = "the limit must be the decided amount in USD"
  }

  assert {
    condition     = module.budget.forecast_thresholds_percent == tolist(["080.00", "100.00"])
    error_message = "the forecast alerts must be at 80% and 100% (O16)"
  }
}

run "budget_alerts_are_forecasts_by_email_only" {
  command = plan

  # The reviewable summary (output budget) shows the alerts without the address.
  assert {
    condition = jsonencode(output.budget.alerts) == jsonencode([
      for t in [80, 100] : {
        comparison_operator = "GREATER_THAN", email_recipients = 1, notification_type = "FORECASTED",
        sns_topic_arns      = [], threshold = t, threshold_type = "PERCENTAGE"
      }
    ])
    error_message = "the plan text must show both alerts (type, comparison, threshold, no SNS topic, one recipient)"
  }

  assert {
    condition = alltrue([for n in module.budget.notifications : (
      n.notification_type == "FORECASTED" && n.comparison_operator == "GREATER_THAN" && n.threshold_type == "PERCENTAGE" &&
      length(n.subscriber_email_addresses) == 1 && length(coalesce(n.subscriber_sns_topic_arns, [])) == 0
    )])
    error_message = "every alert must be a percentage forecast to exactly one email address, with no SNS topic"
  }

  assert {
    condition     = length(module.budget.notifications) == 2
    error_message = "there must be exactly the two decided alerts"
  }
}

run "budget_with_an_undecided_limit_refused" {
  command = plan

  variables {
    budget_config_path = "tests/fixtures/budget-undecided.json"
  }

  expect_failures = [output.budget]
}

run "budget_without_a_recipient_refused" {
  command = plan

  variables {
    budget_alert_email = ""
  }

  expect_failures = [var.budget_alert_email]
}

run "budget_with_two_recipients_refused" {
  command = plan

  variables {
    budget_alert_email = "owner@example.com,other@example.com"
  }

  expect_failures = [var.budget_alert_email]
}

# AUT-101: the committed network decision (N1-N8) reaches the module.
run "network_from_the_committed_decision" {
  command = plan

  assert {
    condition = (
      output.network.egress_model == "A" && output.network.vpc_cidr == "10.60.0.0/20" &&
      output.network.public_subnet_cidr == "10.60.0.0/24" && output.network.availability_zone_id == "aps1-az1" &&
      output.network.flow_logs == "ALL to arn:aws:s3:::veda-stg-logs-111122223333/vpc-flow"
    )
    error_message = "the network must follow infra/config/staging-network.json"
  }
}

# D6: the anchor retention the application receives is the committed decision, as a whole number of days.
run "anchor_retention_parameter_is_the_decision" {
  command = plan

  assert {
    condition     = local.app_config["VEDA_ANCHOR_RETENTION_DAYS"] == "30"
    error_message = "VEDA_ANCHOR_RETENTION_DAYS must be the decided staging retention (anchor_retention.application_retention_days)"
  }

  assert {
    condition     = module.ssm.config_parameter_names == sort([for k in keys(local.app_config) : "/veda/staging/config/${k}"])
    error_message = "every configuration value, the anchor retention included, must be planned under /veda/staging/config/"
  }
}

# ADR-012 staging validation (decision log 20): the estimator flag and its policy link, staging only.
run "estimator_enabled_on_staging_with_its_policy_link" {
  command = plan

  assert {
    condition     = local.app_config["VEDA_ESTIMATOR_ENABLED"] == "true" && local.app_config["VEDA_WARRANTY_POLICY_URL"] == "https://staging.vedaspaces.com/warranty"
    error_message = "the staging estimator flag and its warranty policy link must reach SSM together"
  }

  assert {
    condition     = contains(module.ssm.config_parameter_names, "/veda/staging/config/VEDA_ESTIMATOR_ENABLED")
    error_message = "the flag is a staging configuration parameter"
  }
}

run "estimator_without_a_policy_link_refused" {
  command = plan

  variables {
    warranty_policy_url = ""
  }

  expect_failures = [output.estimator]
}

run "estimator_policy_link_must_be_a_vedaspaces_https_page" {
  command = plan

  variables {
    warranty_policy_url = "http://example.com/policy"
  }

  expect_failures = [var.warranty_policy_url]
}
