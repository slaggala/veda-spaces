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

# Targeted media enablement: the media bucket and settings are planned with every V3 flag off.
run "media_settings_planned_with_every_flag_off" {
  command = plan

  assert {
    condition     = module.storage.bucket_names["media"] == "veda-stg-media-${local.account_id}"
    error_message = "the media bucket follows the plan-guard naming convention"
  }

  assert {
    condition = (local.app_config["VEDA_CATALOG_MEDIA_BACKEND"] == "s3" && local.app_config["VEDA_CATALOG_MEDIA_SOURCE_PREFIX"] == "source/" &&
      local.app_config["VEDA_CATALOG_MEDIA_VARIANT_PREFIX"] == "variant/" &&
    local.app_config["VEDA_CATALOG_MEDIA_KMS_KEY_ARN"] == "arn:aws:kms:ap-south-1:${local.account_id}:alias/veda-stg-data")
    error_message = "media backend, prefixes and the existing data key by alias"
  }

  assert {
    condition = alltrue([for k in ["VEDA_CATALOG_MEDIA_DELIVERY_ENABLED", "VEDA_CATALOG_3D_ENABLED", "VEDA_CATALOG_VIDEO_ENABLED",
    "VEDA_CATALOG_ESTIMATOR_ENABLED", "VEDA_CATALOG_ADMIN_ENABLED"] : local.app_config[k] == "false"])
    error_message = "every V3, delivery, 3D and video flag is off"
  }

  assert {
    condition     = local.app_config["VEDA_CATALOG_MEDIA_SCANNER"] == "none" && local.app_config["VEDA_CATALOG_CLAMD_IMAGE"] == "none-selected" && local.app_config["VEDA_CATALOG_CLAMD_ADDRESS"] == "clamd:3310"
    error_message = "no scanner until the owner decides (uploads stay PENDING); its settings are present and inactive"
  }

  assert {
    condition     = !contains(keys(local.app_config), "VEDA_CATALOG_MEDIA_RIGHTS_APPROVER")
    error_message = "no media-rights approver is planned until the owner names one (never the placeholder)"
  }

  assert {
    condition     = alltrue([for k, v in local.app_config : !can(regex("(?i)secret|password|private", k))])
    error_message = "no secret in the planned configuration"
  }
}

run "a_partial_v3_activation_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-v3-partial.json"
  }
  expect_failures = [output.catalog_v3]
}

run "clamd_with_a_placeholder_digest_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-clamd-placeholder.json"
  }
  expect_failures = [output.catalog_v3]
}

run "a_scanner_the_application_cannot_use_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-scanner-option-c.json"
  }
  expect_failures = [output.catalog_v3]
}

run "a_decided_pinned_clamd_reaches_ssm_on_the_private_network" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-clamd-pinned.json"
  }

  assert {
    condition     = local.app_config["VEDA_CATALOG_MEDIA_SCANNER"] == "clamd" && local.app_config["VEDA_CATALOG_CLAMD_ADDRESS"] == "clamd:3310" && endswith(local.app_config["VEDA_CATALOG_CLAMD_IMAGE"], "@sha256:${join("", [for i in range(64) : "b"])}")
    error_message = "the clamd address is the Compose service name (no host port) and the image is the pinned digest"
  }

  assert {
    condition     = local.app_config["VEDA_CATALOG_ESTIMATOR_ENABLED"] == "false"
    error_message = "a scanner decision does not enable V3"
  }
}

# Pre-plan closure, gap 1: Terraform judges the approval record itself whenever a V3 flag is on.
run "a_current_independent_fully_evidenced_approved_record_opens_the_gate" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-approved.json"
    approval_record_path = "tests/fixtures/approval-approved.json"
  }
  assert {
    condition     = length(local.approval_problems) == 0 && local.app_config["VEDA_CATALOG_ESTIMATOR_ENABLED"] == "true"
    error_message = "the valid record opens the gate"
  }
}

run "approval_draft_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-draft.json"
    approval_record_path = "tests/fixtures/approval-draft.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_in_review_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-in-review.json"
    approval_record_path = "tests/fixtures/approval-in-review.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_revoked_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-revoked.json"
    approval_record_path = "tests/fixtures/approval-revoked.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_missing_evidence_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-missing-evidence.json"
    approval_record_path = "tests/fixtures/approval-missing-evidence.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_expired_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-expired.json"
    approval_record_path = "tests/fixtures/approval-expired.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_review_passed_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-review-passed.json"
    approval_record_path = "tests/fixtures/approval-review-passed.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_self_approved_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-self-approved.json"
    approval_record_path = "tests/fixtures/approval-self-approved.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_wrong_environment_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-wrong-environment.json"
    approval_record_path = "tests/fixtures/approval-wrong-environment.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_malformed_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-malformed.json"
    approval_record_path = "tests/fixtures/approval-malformed.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_digest_mismatch_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-digest-mismatch.json"
    approval_record_path = "tests/fixtures/approval-approved.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_record_missing_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on-approved.json"
    approval_record_path = "tests/fixtures/no-such-record.json"
  }
  expect_failures = [output.catalog_v3]
}

run "all_flags_off_plans_without_any_approval_record" {
  command = plan
  variables {
    approval_record_path = "tests/fixtures/no-such-record.json"
  }
  assert {
    condition     = !local.activation && length(local.approval_problems) == 0
    error_message = "infrastructure with every flag off needs no approval record"
  }
}

# Pre-plan closure, gap 2: a scanner rollback (clamd -> none) changes values in place and removes no parameter.
run "scanner_rollback_removes_no_parameter" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-clamd-pinned.json"
  }
  assert {
    condition = toset(module.ssm.config_parameter_names) == toset([for k in keys(merge(local.app_config, {
    VEDA_CATALOG_MEDIA_SCANNER = "none", VEDA_CATALOG_CLAMD_IMAGE = "none-selected" })) : "/veda/staging/config/${k}"])
    error_message = "the clamd configuration has exactly the parameter names of the none configuration"
  }
}

run "scanner_none_keeps_the_same_parameter_names_as_clamd" {
  command = plan
  assert {
    condition = alltrue([for k in ["VEDA_CATALOG_CLAMD_ADDRESS", "VEDA_CATALOG_CLAMD_IMAGE", "VEDA_CATALOG_MEDIA_BACKEND",
      "VEDA_CATALOG_MEDIA_BUCKET", "VEDA_CATALOG_MEDIA_KMS_KEY_ARN", "VEDA_CATALOG_MEDIA_SOURCE_PREFIX", "VEDA_CATALOG_MEDIA_VARIANT_PREFIX",
      "VEDA_CATALOG_MEDIA_DELIVERY_ENABLED", "VEDA_CATALOG_3D_ENABLED", "VEDA_CATALOG_VIDEO_ENABLED", "VEDA_CATALOG_ESTIMATOR_ENABLED",
    "VEDA_CATALOG_ADMIN_ENABLED"] : contains(keys(local.app_config), k)])
    error_message = "common and scanner-specific media settings are always planned (none is an inactive value, not a removal)"
  }

  assert {
    condition     = length(local.media_config) == 13
    error_message = "with none: 13 media parameters, the same names as with clamd"
  }
}

run "scanner_none_with_v3_flags_on_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-v3-partial.json"
  }
  expect_failures = [output.catalog_v3]
}
