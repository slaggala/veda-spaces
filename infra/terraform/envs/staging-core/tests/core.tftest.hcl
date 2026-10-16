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

  # AD-1 (2026-10-12) records option B and the pinned image; the scanner deployment change (2026-10-12) set the mode to
  # clamd: the next 12-deploy starts the pinned image on the private Compose network (deploy.sh step 4c). V3 stays off.
  assert {
    condition = (local.app_config["VEDA_CATALOG_MEDIA_SCANNER"] == "clamd" && local.scanner.status == "DECIDED" && local.scanner.option == "B" &&
      local.app_config["VEDA_CATALOG_CLAMD_IMAGE"] == "clamav/clamav:1.4.6-debian13-slim@sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b" &&
    local.app_config["VEDA_CATALOG_CLAMD_ADDRESS"] == "clamd:3310")
    error_message = "scanner decided and deployed by configuration: option B, mode clamd, the validated pinned image, the private Compose address"
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
# The approval rules themselves are proven case by case in modules/v3-approval (the shared conformance cases); here
# only the wiring: a passing record opens the gate and binds its digest, any failing code refuses the plan.
run "an_approval_the_shared_rules_accept_opens_the_gate_and_binds_its_digest" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on.json"
  }
  override_module {
    target  = module.v3_approval
    outputs = { codes = [], messages = [], record_sha256 = "" }
  }
  assert {
    condition     = length(local.approval_problems) == 0 && local.app_config["VEDA_CATALOG_ESTIMATOR_ENABLED"] == "true"
    error_message = "A record the shared rules accept opens the V3 gate."
  }
  assert {
    condition     = local.app_config["VEDA_CATALOG_APPROVAL_SHA256"] == local.catalog_v3.approval_record_sha256
    error_message = "The bound digest reaches SSM for the deployment check and the runtime."
  }
}

run "any_failing_approval_code_refuses_the_plan" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on.json"
  }
  override_module {
    target  = module.v3_approval
    outputs = { codes = ["EXPIRED"], messages = ["the approval has expired"], record_sha256 = "" }
  }
  expect_failures = [output.catalog_v3]
}

run "the_shared_rules_refuse_a_draft_record_at_plan" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on.json"
    approval_record_path = "../../../../api/tests/fixtures/v3_approval/draft.json"
  }
  expect_failures = [output.catalog_v3]
}

run "approval_record_missing_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-on.json"
    approval_record_path = "tests/fixtures/no-such-record.json"
  }
  expect_failures = [output.catalog_v3]
}

run "scanner_option_a_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-scanner-option-a.json"
  }
  expect_failures = [output.catalog_v3]
}

run "scanner_option_c_may_be_recorded_while_the_mode_stays_none" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-scanner-option-c-undecided-adapter.json"
  }
  assert {
    condition     = local.app_config["VEDA_CATALOG_MEDIA_SCANNER"] == "none"
    error_message = "Option C is a valid decision; until its adapter exists the scanner mode stays none."
  }
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
  assert {
    condition     = local.app_config["VEDA_CATALOG_APPROVAL_SHA256"] == "none"
    error_message = "with nothing bound the deployment check and the runtime get the inactive value none"
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
    "VEDA_CATALOG_ADMIN_ENABLED", "VEDA_CATALOG_APPROVAL_SHA256"] : contains(keys(local.app_config), k)])
    error_message = "common and scanner-specific media settings are always planned (none is an inactive value, not a removal)"
  }

  assert {
    condition     = length(local.media_config) == 14
    error_message = "with none: 14 media parameters, the same names as with clamd"
  }
}

run "scanner_none_with_v3_flags_on_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-v3-partial.json"
  }
  expect_failures = [output.catalog_v3]
}

# MTQ B1-T11: attachment storage planned and inert (closure §6.4).
run "attachment_storage_planned_with_the_site_flag_on_and_bound" {
  command = plan

  assert {
    condition     = module.storage.bucket_names["attachments"] == "veda-stg-attachments-${local.account_id}"
    error_message = "the attachments bucket follows the plan-guard naming convention"
  }

  assert {
    condition = (local.app_config["VEDA_ATTACHMENT_BACKEND"] == "s3" && local.app_config["VEDA_ATTACHMENT_BUCKET"] == "veda-stg-attachments-${local.account_id}" &&
      local.app_config["VEDA_ATTACHMENT_KMS_KEY_ARN"] == "arn:aws:kms:ap-south-1:${local.account_id}:alias/veda-stg-data" &&
    local.app_config["VEDA_ATTACHMENT_UPLOAD_TTL_SECONDS"] == "300")
    error_message = "S3 backend, the attachments bucket, the existing data key by alias, five-minute pre-signed uploads"
  }

  assert {
    condition     = local.app_config["VEDA_ATTACHMENT_SCANNER"] == local.app_config["VEDA_CATALOG_MEDIA_SCANNER"] && local.app_config["VEDA_ATTACHMENT_CLAMD_ADDRESS"] == local.app_config["VEDA_CATALOG_CLAMD_ADDRESS"]
    error_message = "attachments are scanned by the media scanner already on the host (same mode, same private address)"
  }

  assert {
    condition = (local.app_config["VEDA_MTQ_SITE_ENABLED"] == "true" && output.mtq_attachments.site_enabled == "true" &&
    local.app_config["VEDA_MTQ_SITE_ENABLEMENT_SHA256"] == filesha256("../../../config/mtq-site-enablement-record.json"))
    error_message = "owner approval of 2026-10-13 (decision log 30): the site flag is on in staging and bound to the committed record's SHA-256"
  }

  assert {
    condition     = output.mtq_attachments.noncurrent_days == 30 && output.mtq_attachments.tiering_days == 90 && output.mtq_attachments.upload_expire_days == 2
    error_message = "the closure §6.4 windows reach the bucket"
  }

  assert {
    condition     = length(local.attachment_config) == 8
    error_message = "the flag, its record digest and six attachment parameters"
  }
}

run "attachments_not_decided_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-attachments-undecided.json"
  }
  expect_failures = [output.mtq_attachments]
}

run "a_pre_signed_upload_longer_than_the_api_accepts_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-attachments-long-upload.json"
  }
  expect_failures = [output.mtq_attachments]
}

# MTQ B1-T12: the site flag turns on only with an owner-APPROVED enablement record bound by its SHA-256.
run "the_committed_enablement_record_is_approved_and_meets_every_gate" {
  command = plan

  assert {
    condition     = jsondecode(file("../../../config/mtq-site-enablement-record.json")).status == "APPROVED" && local.mtq_record_problems == [] && local.app_config["VEDA_ENV"] == "staging"
    error_message = "the committed record is the owner's approval (decision log 30): APPROVED, every evidence field filled, bound, staging only"
  }
}

run "the_flag_with_a_draft_record_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-mtq-on-draft.json"
    mtq_enablement_record_path = "tests/fixtures/mtq-record-draft.json"
  }
  expect_failures = [output.mtq_attachments]
}

run "an_approved_bound_record_turns_the_flag_on_in_staging" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-mtq-on.json"
    mtq_enablement_record_path = "tests/fixtures/mtq-record-approved.json"
  }

  assert {
    condition     = local.app_config["VEDA_MTQ_SITE_ENABLED"] == "true" && local.app_config["VEDA_MTQ_SITE_ENABLEMENT_SHA256"] == filesha256("tests/fixtures/mtq-record-approved.json")
    error_message = "the flag and the bound digest reach SSM together"
  }

  assert {
    condition     = local.app_config["VEDA_ENV"] == "staging" && local.mtq_record_problems == []
    error_message = "staging only, every gate met"
  }
}

run "the_flag_bound_to_another_record_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-mtq-on.json"
  }
  expect_failures = [output.mtq_attachments]
}

run "the_flag_with_unfilled_evidence_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-mtq-on-placeholder.json"
    mtq_enablement_record_path = "tests/fixtures/mtq-record-placeholder-evidence.json"
  }
  expect_failures = [output.mtq_attachments]
}

run "the_flag_approved_by_its_author_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-mtq-on-self.json"
    mtq_enablement_record_path = "tests/fixtures/mtq-record-self-approved.json"
  }
  expect_failures = [output.mtq_attachments]
}

run "the_flag_with_another_records_digest_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-mtq-on.json"
    mtq_enablement_record_path = "tests/fixtures/mtq-record-placeholder-evidence.json"
  }
  expect_failures = [output.mtq_attachments]
}

run "the_flag_without_the_clamd_scanner_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-mtq-on-no-scanner.json"
    mtq_enablement_record_path = "tests/fixtures/mtq-record-approved.json"
  }
  expect_failures = [output.mtq_attachments]
}

run "a_bound_digest_without_the_flag_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-mtq-digest-without-flag.json"
    mtq_enablement_record_path = "tests/fixtures/mtq-record-approved.json"
  }
  expect_failures = [output.mtq_attachments]
}

# MTQ B2-B4 (decision log 33): both commercial flags are planned false; they turn on only with an owner-APPROVED,
# internal-validation-only enablement record bound by its SHA-256, quotation only with estimation, estimation only
# with the B1 site flag.
run "the_commercial_flags_are_planned_false_when_off" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-commercial-off.json"
    mtq_commercial_record_path = "tests/fixtures/mtq-commercial-record-draft.json"
  }

  assert {
    condition = (local.app_config["VEDA_MTQ_ESTIMATION_ENABLED"] == "false" && local.app_config["VEDA_MTQ_QUOTATION_ENABLED"] == "false" &&
    output.mtq_commercial.enablement_record == null && length(local.commercial_config) == 2)
    error_message = "two parameters, both false, no record bound (also the rollback state)"
  }

  assert {
    condition     = jsondecode(file("tests/fixtures/mtq-commercial-record-draft.json")).status == "DRAFT" && contains(local.commercial_record_problems, "the record is not APPROVED")
    error_message = "a DRAFT record is never enough"
  }
}

run "the_committed_commercial_record_is_approved_and_turns_both_flags_on" {
  command = plan

  assert {
    condition = (jsondecode(file("../../../config/mtq-commercial-enablement-record.json")).status == "APPROVED" && local.commercial_record_problems == [] &&
      local.app_config["VEDA_ENV"] == "staging" && local.app_config["VEDA_MTQ_ESTIMATION_ENABLED"] == "true" && local.app_config["VEDA_MTQ_QUOTATION_ENABLED"] == "true" &&
    output.mtq_commercial.enablement_record == filesha256("../../../config/mtq-commercial-enablement-record.json"))
    error_message = "owner approval of 2026-10-14 (decision log 34): APPROVED, every evidence field filled, internal validation only, bound, staging only"
  }

  assert {
    condition     = local.commercial_record.scope.customer_issuance == false && local.commercial_record.scope.internal_protected_staging_validation_only == true
    error_message = "the approval never authorises customer issuance"
  }
}

run "an_approved_bound_record_turns_both_commercial_flags_on_in_staging" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-commercial-on.json"
    mtq_commercial_record_path = "tests/fixtures/mtq-commercial-record-approved.json"
  }

  assert {
    condition = (local.app_config["VEDA_MTQ_ESTIMATION_ENABLED"] == "true" && local.app_config["VEDA_MTQ_QUOTATION_ENABLED"] == "true" &&
    output.mtq_commercial.enablement_record == filesha256("tests/fixtures/mtq-commercial-record-approved.json") && local.commercial_record_problems == [])
    error_message = "both flags reach SSM with the record bound and every gate met"
  }
}

run "estimation_may_turn_on_without_quotation" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-commercial-estimation-only.json"
    mtq_commercial_record_path = "tests/fixtures/mtq-commercial-record-approved.json"
  }

  assert {
    condition     = local.app_config["VEDA_MTQ_ESTIMATION_ENABLED"] == "true" && local.app_config["VEDA_MTQ_QUOTATION_ENABLED"] == "false"
    error_message = "estimation without quotation is allowed"
  }
}

run "quotation_without_estimation_refused" {
  command = plan
  variables {
    platform_config_path = "tests/fixtures/platform-commercial-quotation-only.json"
  }
  expect_failures = [output.mtq_commercial]
}

run "the_commercial_flags_with_the_draft_record_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-commercial-on-draft.json"
    mtq_commercial_record_path = "tests/fixtures/mtq-commercial-record-draft.json"
  }
  expect_failures = [output.mtq_commercial]
}

run "a_record_allowing_customer_issuance_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-commercial-on-customer-issuance.json"
    mtq_commercial_record_path = "tests/fixtures/mtq-commercial-record-customer-issuance.json"
  }
  expect_failures = [output.mtq_commercial]
}

run "the_commercial_record_approved_by_its_author_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-commercial-on-self.json"
    mtq_commercial_record_path = "tests/fixtures/mtq-commercial-record-self-approved.json"
  }
  expect_failures = [output.mtq_commercial]
}

run "the_commercial_flags_bound_to_another_record_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-commercial-on.json"
    mtq_commercial_record_path = "tests/fixtures/mtq-commercial-record-self-approved.json"
  }
  expect_failures = [output.mtq_commercial]
}

run "estimation_without_the_site_flag_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-commercial-on-no-site.json"
    mtq_commercial_record_path = "tests/fixtures/mtq-commercial-record-approved.json"
  }
  expect_failures = [output.mtq_commercial]
}

run "a_bound_commercial_digest_without_the_flag_refused" {
  command = plan
  variables {
    platform_config_path       = "tests/fixtures/platform-commercial-digest-without-flag.json"
    mtq_commercial_record_path = "tests/fixtures/mtq-commercial-record-approved.json"
  }
  expect_failures = [output.mtq_commercial]
}

# Customer quotation experience (decision log 35): three flags planned false; each turns on only with an owner-APPROVED,
# synthetic-customers-only record bound by its SHA-256 whose scope names it; viewing needs the quotation flag,
# interaction needs viewing, acceptance needs interaction.
run "the_customer_proposal_flags_are_planned_false" {
  command = plan

  assert {
    condition = (local.app_config["VEDA_CUSTOMER_PROPOSAL_ENABLED"] == "false" && local.app_config["VEDA_CUSTOMER_PROPOSAL_INTERACTION_ENABLED"] == "false" &&
    local.app_config["VEDA_CUSTOMER_QUOTATION_ACCEPTANCE_ENABLED"] == "false" && output.customer_proposal.enablement_record == null && length(local.cqx_config) == 3)
    error_message = "three parameters, all false, no record bound (also the rollback state)"
  }

  assert {
    condition     = jsondecode(file("../../../config/customer-proposal-enablement-record.json")).status == "DRAFT" && contains(local.cqx_record_problems, "the record is not APPROVED")
    error_message = "the committed record is a DRAFT: nothing is enabled by this change"
  }
}

run "an_approved_record_scoped_to_viewing_turns_viewing_on_only" {
  command = plan
  variables {
    platform_config_path          = "tests/fixtures/platform-cqx-viewing-on.json"
    customer_proposal_record_path = "tests/fixtures/cqx-record-approved-viewing.json"
  }

  assert {
    condition = (output.customer_proposal.proposal_enabled == "true" && output.customer_proposal.interaction_enabled == "false" &&
    output.customer_proposal.acceptance_enabled == "false" && local.cqx_record_problems == [])
    error_message = "viewing alone, bound to an approved record that authorises viewing"
  }
}

run "an_approved_record_scoped_to_all_three_turns_them_on" {
  command = plan
  variables {
    platform_config_path          = "tests/fixtures/platform-cqx-all-on.json"
    customer_proposal_record_path = "tests/fixtures/cqx-record-approved-all.json"
  }

  assert {
    condition     = output.customer_proposal.acceptance_enabled == "true" && local.cqx_record_problems == []
    error_message = "acceptance testing on only when the approved record's scope says so"
  }
}

run "acceptance_outside_the_records_scope_refused" {
  command = plan
  variables {
    platform_config_path          = "tests/fixtures/platform-cqx-acceptance-not-in-scope.json"
    customer_proposal_record_path = "tests/fixtures/cqx-record-approved-viewing.json"
  }
  expect_failures = [output.customer_proposal]
}

run "interaction_without_viewing_refused" {
  command = plan
  variables {
    platform_config_path          = "tests/fixtures/platform-cqx-interaction-only.json"
    customer_proposal_record_path = "tests/fixtures/cqx-record-approved-all.json"
  }
  expect_failures = [output.customer_proposal]
}

run "viewing_without_the_quotation_flag_refused" {
  command = plan
  variables {
    platform_config_path          = "tests/fixtures/platform-cqx-no-quotation.json"
    customer_proposal_record_path = "tests/fixtures/cqx-record-approved-viewing.json"
  }
  expect_failures = [output.customer_proposal]
}

run "the_customer_proposal_draft_record_refused" {
  command = plan
  variables {
    platform_config_path          = "tests/fixtures/platform-cqx-draft.json"
    customer_proposal_record_path = "tests/fixtures/cqx-record-draft.json"
  }
  expect_failures = [output.customer_proposal]
}

run "a_bound_customer_proposal_digest_without_a_flag_refused" {
  command = plan
  variables {
    platform_config_path          = "tests/fixtures/platform-cqx-digest-without-flag.json"
    customer_proposal_record_path = "tests/fixtures/cqx-record-approved-viewing.json"
  }
  expect_failures = [output.customer_proposal]
}

# Customer Promise administration (decision log 37): one staff-only flag planned false; it turns on only with an
# owner-APPROVED, staging-only, synthetic-content-only record bound by its SHA-256 whose approver is not its author.
run "the_customer_promise_flag_is_planned_false_when_off" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-cpa-off.json"
    customer_promise_record_path = "tests/fixtures/cpa-record-draft.json"
  }

  assert {
    condition     = local.app_config["VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED"] == "false" && output.customer_promise.enablement_record == null && length(local.cpa_config) == 1
    error_message = "one parameter, false, no record bound (also the rollback state)"
  }

  assert {
    condition     = jsondecode(file("tests/fixtures/cpa-record-draft.json")).status == "DRAFT" && contains(local.cpa_record_problems, "the record is not APPROVED")
    error_message = "a DRAFT record is never enough"
  }
}

run "the_committed_customer_promise_record_is_approved_and_turns_the_portal_on" {
  command = plan

  assert {
    condition = (jsondecode(file("../../../config/customer-promise-enablement-record.json")).status == "APPROVED" && local.cpa_record_problems == [] &&
      local.app_config["VEDA_ENV"] == "staging" && local.app_config["VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED"] == "true" &&
    output.customer_promise.enablement_record == filesha256("../../../config/customer-promise-enablement-record.json"))
    error_message = "owner approval of 2026-10-15 (decision log 39): APPROVED, every evidence field filled, synthetic content only, bound, staging only"
  }

  assert {
    condition = (local.app_config["VEDA_CUSTOMER_PROPOSAL_ENABLED"] == "false" && local.app_config["VEDA_CUSTOMER_PROPOSAL_INTERACTION_ENABLED"] == "false" &&
    local.app_config["VEDA_CUSTOMER_QUOTATION_ACCEPTANCE_ENABLED"] == "false")
    error_message = "the portal is separate: every customer-proposal flag stays off"
  }
}

run "an_approved_record_turns_the_portal_on" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-cpa-on.json"
    customer_promise_record_path = "tests/fixtures/cpa-record-approved.json"
  }

  assert {
    condition     = output.customer_promise.admin_enabled == "true" && local.cpa_record_problems == [] && local.app_config["VEDA_CUSTOMER_PROPOSAL_ENABLED"] == "false"
    error_message = "the portal on, bound to an approved record; customer-proposal viewing untouched"
  }
}

run "the_customer_promise_draft_record_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-cpa-on-draft.json"
    customer_promise_record_path = "tests/fixtures/cpa-record-draft.json"
  }
  expect_failures = [output.customer_promise]
}

run "a_self_approved_customer_promise_record_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-cpa-on-self.json"
    customer_promise_record_path = "tests/fixtures/cpa-record-self-approved.json"
  }
  expect_failures = [output.customer_promise]
}

run "a_customer_promise_record_for_production_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-cpa-on-production.json"
    customer_promise_record_path = "tests/fixtures/cpa-record-production.json"
  }
  expect_failures = [output.customer_promise]
}

run "a_bound_customer_promise_digest_without_the_flag_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-cpa-digest-without-flag.json"
    customer_promise_record_path = "tests/fixtures/cpa-record-approved.json"
  }
  expect_failures = [output.customer_promise]
}

# Customer Project Portal (decision log 41): one customer-facing flag planned false; it turns on only with an
# owner-APPROVED, staging-only, synthetic-content-only record bound by its SHA-256 whose approver is not its author.
run "the_customer_portal_flag_is_planned_false_when_off" {
  command = plan
  variables {
    platform_config_path        = "tests/fixtures/platform-cpp-off.json"
    customer_portal_record_path = "tests/fixtures/cpp-record-draft.json"
  }

  assert {
    condition     = local.app_config["VEDA_CUSTOMER_PORTAL_ENABLED"] == "false" && output.customer_portal.enablement_record == null && length(local.cpp_config) == 1
    error_message = "one parameter, false, no record bound (also the rollback state)"
  }

  assert {
    condition     = jsondecode(file("tests/fixtures/cpp-record-draft.json")).status == "DRAFT" && contains(local.cpp_record_problems, "the record is not APPROVED")
    error_message = "a DRAFT record is never enough"
  }
}

run "the_committed_customer_portal_record_is_approved_and_turns_the_portal_on" {
  command = plan

  assert {
    condition = (jsondecode(file("../../../config/customer-portal-enablement-record.json")).status == "APPROVED" && local.cpp_record_problems == [] &&
      local.app_config["VEDA_ENV"] == "staging" && local.app_config["VEDA_CUSTOMER_PORTAL_ENABLED"] == "true" &&
    output.customer_portal.enablement_record == filesha256("../../../config/customer-portal-enablement-record.json"))
    error_message = "owner approval of 2026-10-16 (decision log 43): APPROVED, every evidence field filled, synthetic content only, bound, staging only"
  }

  assert {
    condition     = local.app_config["VEDA_PROJECT_LIFECYCLE_ENABLED"] == "false" && local.app_config["VEDA_CUSTOMER_PROPOSAL_ENABLED"] == "false"
    error_message = "the portal is separate: the Project Lifecycle stays off (set only by project_delivery) and customer-proposal viewing is untouched"
  }
}

run "an_approved_record_turns_the_customer_portal_on" {
  command = plan
  variables {
    platform_config_path        = "tests/fixtures/platform-cpp-on.json"
    customer_portal_record_path = "tests/fixtures/cpp-record-approved.json"
  }

  assert {
    condition     = output.customer_portal.enabled == "true" && local.cpp_record_problems == [] && local.app_config["VEDA_PROJECT_LIFECYCLE_ENABLED"] == "false"
    error_message = "the portal on, bound to an approved record; the Project Lifecycle untouched"
  }
}

run "the_customer_portal_draft_record_refused" {
  command = plan
  variables {
    platform_config_path        = "tests/fixtures/platform-cpp-on-draft.json"
    customer_portal_record_path = "tests/fixtures/cpp-record-draft.json"
  }
  expect_failures = [output.customer_portal]
}

run "a_self_approved_customer_portal_record_refused" {
  command = plan
  variables {
    platform_config_path        = "tests/fixtures/platform-cpp-on-self.json"
    customer_portal_record_path = "tests/fixtures/cpp-record-self-approved.json"
  }
  expect_failures = [output.customer_portal]
}

run "a_customer_portal_record_for_production_refused" {
  command = plan
  variables {
    platform_config_path        = "tests/fixtures/platform-cpp-on-production.json"
    customer_portal_record_path = "tests/fixtures/cpp-record-production.json"
  }
  expect_failures = [output.customer_portal]
}

run "a_bound_customer_portal_digest_without_the_flag_refused" {
  command = plan
  variables {
    platform_config_path        = "tests/fixtures/platform-cpp-digest-without-flag.json"
    customer_portal_record_path = "tests/fixtures/cpp-record-approved.json"
  }
  expect_failures = [output.customer_portal]
}

# Project delivery (decision log 46): the Project Lifecycle, Project Commercials and the customer's delivery view, three
# flags planned false; they turn on only with an owner-APPROVED, staging-only, synthetic-content-only record that names
# each flag, bound by its SHA-256, whose approver is not its author; the delivery view needs the lifecycle and the portal.
run "the_project_delivery_flags_are_planned_false_when_off" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-off.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-draft.json"
  }

  assert {
    condition = (local.app_config["VEDA_PROJECT_LIFECYCLE_ENABLED"] == "false" && local.app_config["VEDA_PROJECT_COMMERCIALS_ENABLED"] == "false" &&
    local.app_config["VEDA_PROJECT_DELIVERY_PORTAL_ENABLED"] == "false" && output.project_delivery.enablement_record == null && length(local.pdl_config) == 3)
    error_message = "three parameters, false, no record bound (also the rollback state)"
  }

  assert {
    condition     = jsondecode(file("tests/fixtures/pdl-record-draft.json")).status == "DRAFT" && contains(local.pdl_record_problems, "the record is not APPROVED")
    error_message = "a DRAFT record is never enough"
  }
}

run "the_committed_project_delivery_wiring_is_off_with_a_draft_record" {
  command = plan

  assert {
    condition = (jsondecode(file("../../../config/project-delivery-enablement-record.json")).status == "DRAFT" &&
      local.app_config["VEDA_PROJECT_LIFECYCLE_ENABLED"] == "false" && local.app_config["VEDA_PROJECT_COMMERCIALS_ENABLED"] == "false" &&
    local.app_config["VEDA_PROJECT_DELIVERY_PORTAL_ENABLED"] == "false" && output.project_delivery.enablement_record == null)
    error_message = "wired off with a DRAFT record until the owner approves it (decision log 46)"
  }
}

run "an_approved_record_turns_project_delivery_on" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-on.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-approved.json"
  }

  assert {
    condition = (output.project_delivery.VEDA_PROJECT_LIFECYCLE_ENABLED == "true" && output.project_delivery.VEDA_PROJECT_COMMERCIALS_ENABLED == "true" &&
    output.project_delivery.VEDA_PROJECT_DELIVERY_PORTAL_ENABLED == "true" && local.pdl_record_problems == [] && local.app_config["VEDA_CUSTOMER_PROPOSAL_ENABLED"] == "false")
    error_message = "the three flags on, bound to an approved record; customer-proposal flags untouched"
  }
}

run "the_project_delivery_draft_record_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-on-draft.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-draft.json"
  }
  expect_failures = [output.project_delivery]
}

run "a_self_approved_project_delivery_record_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-on-self.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-self-approved.json"
  }
  expect_failures = [output.project_delivery]
}

run "a_project_delivery_record_for_production_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-on-production.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-production.json"
  }
  expect_failures = [output.project_delivery]
}

run "a_flag_the_record_does_not_name_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-on-unnamed-flag.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-lifecycle-only.json"
  }
  expect_failures = [output.project_delivery]
}

run "a_record_bound_by_another_digest_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-wrong-digest.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-approved.json"
  }
  expect_failures = [output.project_delivery]
}

run "a_bound_project_delivery_digest_without_a_flag_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-digest-without-flag.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-approved.json"
  }
  expect_failures = [output.project_delivery]
}

run "the_delivery_view_without_the_lifecycle_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-delivery-without-lifecycle.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-approved.json"
  }
  expect_failures = [output.project_delivery]
}

run "the_delivery_view_without_the_customer_portal_refused" {
  command = plan
  variables {
    platform_config_path         = "tests/fixtures/platform-pdl-delivery-without-portal.json"
    project_delivery_record_path = "tests/fixtures/pdl-record-approved.json"
  }
  expect_failures = [output.project_delivery]
}
