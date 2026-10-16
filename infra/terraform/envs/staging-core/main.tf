# The approved account and repository, from the reviewed manifest (F3, PB-01).
locals {
  manifest_path = var.account_manifest_path != "" ? var.account_manifest_path : "${path.module}/../../../config/staging-account.json"
  manifest      = jsondecode(file(local.manifest_path))
  account_id    = regex("^[0-9]{12}$", local.manifest.account_id)

  # AUT-112: the reviewed budget decision (O16); the recipient comes from var.budget_alert_email.
  budget_path = var.budget_config_path != "" ? var.budget_config_path : "${path.module}/../../../config/staging-budget.json"
  budget      = jsondecode(file(local.budget_path))

  # AUT-101: the reviewed network decision (N1-N8).
  network_path = var.network_config_path != "" ? var.network_config_path : "${path.module}/../../../config/staging-network.json"
  network      = jsondecode(file(local.network_path))

  # AUT-102 … AUT-111: the reviewed platform decisions.
  platform_path = var.platform_config_path != "" ? var.platform_config_path : "${path.module}/../../../config/staging-platform.json"
  platform      = jsondecode(file(local.platform_path))

  name_prefix      = "veda-stg"
  log_group_prefix = "/veda/staging"
  trail_name       = "veda-stg-trail"
}

# AUT-112: monthly cost budget with forecast alerts to the owner. Global service, no region.
module "budget" {
  source = "../../modules/budgets"

  name                              = local.budget.name
  monthly_limit_usd                 = local.budget.monthly_limit_usd
  forecast_alert_thresholds_percent = local.budget.forecast_alert_thresholds_percent
  alert_email                       = var.budget_alert_email
}

# AUT-101: network foundation, egress model A (public subnet, no inbound access, outbound-only tunnel).
module "network" {
  source = "../../modules/network"

  name_prefix              = "veda-stg"
  account_id               = local.account_id
  region                   = var.aws_region
  egress_model             = local.network.egress_model
  vpc_cidr                 = local.network.vpc_cidr
  public_subnet_cidr       = local.network.public_subnet_cidr
  az_id_preference         = local.network.az_id_preference
  az_id                    = try(local.network.az_id, null)
  host_instance_type       = local.network.host_instance_type
  flow_log_traffic_type    = local.network.flow_logs.traffic_type
  flow_log_destination_arn = module.storage.flow_log_destination_arn
  tunnel_egress_cidrs      = local.network.tunnel_egress_cidrs
  aws_owned_s3_object_arns = local.network.aws_owned_s3_object_arns
}

# AUT-102: customer-managed keys (data, audit).
module "kms" {
  source = "../../modules/kms"

  name_prefix          = local.name_prefix
  account_id           = local.account_id
  region               = var.aws_region
  log_group_prefix     = local.log_group_prefix
  trail_name           = local.trail_name
  deletion_window_days = local.platform.kms.deletion_window_days
  rotation_period_days = local.platform.kms.rotation_period_days
}

# AUT-103: buckets and Object Lock.
module "storage" {
  source = "../../modules/storage"

  name_prefix        = local.name_prefix
  account_id         = local.account_id
  region             = var.aws_region
  data_key_arn       = module.kms.data_key_arn
  data_key_alias_arn = local.data_key_alias_arn
  audit_key_arn      = module.kms.audit_key_arn
  trail_name         = local.trail_name
  retention = merge({
    for k in ["litestream_noncurrent_days", "snapshots_expire_days", "artifacts_expire_days", "artifacts_noncurrent_days",
    "logs_cloudtrail_expire_days", "logs_flow_expire_days", "evidence_lock_mode", "evidence_lock_days"] : k => local.platform.storage[k]
    }, {
    media_noncurrent_days          = local.media.noncurrent_days
    attachments_noncurrent_days    = local.attachments.noncurrent_days
    attachments_upload_expire_days = local.attachments.upload_expire_days
    attachments_tiering_days       = local.attachments.tiering_days
  })
}

# AUT-104: CloudTrail (management events; data events by the owner session).
module "cloudtrail" {
  source = "../../modules/cloudtrail"

  name_prefix              = local.name_prefix
  account_id               = local.account_id
  region                   = var.aws_region
  trail_name               = local.trail_name
  logs_bucket_name         = module.storage.bucket_names["logs"]
  audit_key_arn            = module.kms.audit_key_arn
  log_group_prefix         = local.log_group_prefix
  log_group_retention_days = local.platform.cloudtrail.log_group_retention_days
  permissions_boundary_arn = "arn:aws:iam::${local.account_id}:policy/veda-boundary"

  # The bucket policy must admit CloudTrail before the trail is created.
  depends_on = [module.storage]
}

# AUT-105: application image repository.
module "ecr" {
  source = "../../modules/ecr"

  repository_name      = "veda-api"
  data_key_arn         = module.kms.data_key_arn
  keep_tagged_images   = local.platform.ecr.keep_tagged_images
  expire_untagged_days = local.platform.ecr.expire_untagged_days
}

# AUT-106: runtime identity of the host.
module "runtime_iam" {
  source = "../../modules/runtime-iam"

  name_prefix              = local.name_prefix
  account_id               = local.account_id
  region                   = var.aws_region
  permissions_boundary_arn = "arn:aws:iam::${local.account_id}:policy/veda-boundary"
  data_key_alias           = module.kms.aliases["data"]
  audit_key_alias          = module.kms.aliases["audit"]
  bucket_arns              = module.storage.bucket_arns
  repository_name          = module.ecr.repository_name
  log_group_prefix         = local.log_group_prefix
  parameter_path           = "/veda/staging"
  ses_send                 = { resources = module.ses.send_resources, from_address = module.ses.from_address }
}

# AUT-107: non-secret configuration and Session Manager preferences. VEDA_ANCHOR_RETENTION_DAYS is the Object Lock
# retention the application gives each anchor, from the owner decision D6 (anchor_retention, 30 days).
locals {
  app_config = merge({
    VEDA_ENV                   = "staging"
    VEDA_AWS_REGION            = var.aws_region
    VEDA_LOG_LEVEL             = "INFO"
    VEDA_KMS_PROVIDER          = "aws"
    VEDA_KMS_KEY_ARN           = "arn:aws:kms:${var.aws_region}:${local.account_id}:${module.kms.aliases["data"]}"
    VEDA_DATABASE_URL          = "sqlite:////var/lib/veda/veda.db"
    VEDA_SNAPSHOT_DIR          = "/var/lib/veda/snapshots"
    VEDA_SNAPSHOT_BUCKET       = module.storage.bucket_names["snapshots"]
    VEDA_ANCHOR_BUCKET         = module.storage.bucket_names["anchor"]
    VEDA_ANCHOR_RETENTION_DAYS = tostring(local.platform.anchor_retention.application_retention_days)
    LITESTREAM_BUCKET          = module.storage.bucket_names["litestream"]
    LITESTREAM_REGION          = var.aws_region
    LITESTREAM_RETENTION       = local.platform.ssm.litestream_retention
    VEDA_EMAIL_PROVIDER        = "ses"
    VEDA_EMAIL_SENDER          = module.ses.sender
    VEDA_SES_CONFIGURATION_SET = module.ses.configuration_set
    VEDA_TURNSTILE_MODE        = "cloudflare"
    VEDA_COOKIE_SECURE         = "true"
    VEDA_RATE_LIMITS_ENABLED   = "true"
    VEDA_BREAK_GLASS_IDENTITY  = "sts"
    VEDA_TRUSTED_PROXY_CIDRS   = local.platform.ssm.trusted_proxy_cidrs
    VEDA_APP_ORIGIN            = local.platform.ssm.app_origin
    VEDA_APP_BASE_URL          = local.platform.ssm.app_origin
    VEDA_API_BASE_URL          = local.platform.ssm.api_base_url
    VEDA_JWT_ISSUER            = local.platform.ssm.api_base_url
    VEDA_PUBLIC_SITE_ORIGINS   = local.platform.ssm.public_site_origins
    # The staging site is behind Cloudflare Access, so its intake call carries credentials (production refuses it).
    VEDA_PUBLIC_SITE_CREDENTIALS = local.platform.ssm.public_site_credentials ? "true" : "false"
    }, local.estimator_config, local.media_config, local.attachment_config, local.commercial_config, local.cqx_config, local.cpa_config, local.cpp_config
  )
}

# Catalog V3 media (targeted media enablement; infra/config/staging-platform.json "media" and "catalog_v3").
# Settings are planned now, every flag stays off: the media backend and bucket are configured, the scanner is
# whatever the owner decided (none until then: uploads stay PENDING and nothing is served), delivery, 3D and video
# are off, and the catalog flags follow catalog_v3, which may turn on only all together and only bound to an APPROVED
# V3 staging approval record (output "catalog_v3" refuses anything else).
locals {
  data_key_alias_arn = "arn:aws:kms:${var.aws_region}:${local.account_id}:${module.kms.aliases["data"]}"
  media              = local.platform.media
  scanner            = local.platform.media_scanner
  rights             = local.platform.media_rights
  catalog_v3         = local.platform.catalog_v3
  catalog_v3_flags   = [local.catalog_v3.catalog_estimator_enabled, local.catalog_v3.catalog_admin_enabled, local.catalog_v3.media_delivery_enabled]
  approval_record    = var.approval_record_path != "" ? var.approval_record_path : "${path.module}/../../../../api/veda/modules/catalog/approved/v3-staging-approval.json"
  activation         = anytrue(local.catalog_v3_flags)
  # The approval record is judged by the shared rules (modules/v3-approval, from v3_approval_policy.json): the same
  # rules and codes as the staging build, the deployment check and the runtime. Only any flag on needs a record.
  approval_problems = local.activation ? [for i, c in module.v3_approval.codes : "${c}: ${module.v3_approval.messages[i]}"] : []
  media_config = merge({
    VEDA_CATALOG_MEDIA_BACKEND          = "s3"
    VEDA_CATALOG_MEDIA_BUCKET           = module.storage.bucket_names["media"]
    VEDA_CATALOG_MEDIA_KMS_KEY_ARN      = local.data_key_alias_arn
    VEDA_CATALOG_MEDIA_SOURCE_PREFIX    = "source/"
    VEDA_CATALOG_MEDIA_VARIANT_PREFIX   = "variant/"
    VEDA_CATALOG_MEDIA_SCANNER          = local.scanner.mode
    VEDA_CATALOG_MEDIA_DELIVERY_ENABLED = local.catalog_v3.media_delivery_enabled ? "true" : "false"
    VEDA_CATALOG_3D_ENABLED             = "false"
    VEDA_CATALOG_VIDEO_ENABLED          = "false"
    VEDA_CATALOG_ESTIMATOR_ENABLED      = local.catalog_v3.catalog_estimator_enabled ? "true" : "false"
    VEDA_CATALOG_ADMIN_ENABLED          = local.catalog_v3.catalog_admin_enabled ? "true" : "false"
    # The digest the deployment check and the runtime require of the packaged record ("none" while nothing is bound).
    VEDA_CATALOG_APPROVAL_SHA256 = coalesce(local.catalog_v3.approval_record_sha256, "none")
    # Scanner-specific settings are always present and inactive unless VEDA_CATALOG_MEDIA_SCANNER is clamd (pre-plan
    # closure, gap 2): a scanner rollback (clamd -> none) changes one value in place and removes no parameter, so
    # it needs no destroy and no plan-guard exception. The address is the Compose service on the private network.
    VEDA_CATALOG_CLAMD_ADDRESS = "clamd:3310"
    VEDA_CATALOG_CLAMD_IMAGE   = coalesce(local.scanner.clamd_image, "none-selected")
    }, local.rights.status == "DECIDED" ? {
    VEDA_CATALOG_MEDIA_RIGHTS_APPROVER = local.rights.approver
  } : {})
}

# MTQ B1 site attachments (B1-T11; closure §6, infra/config/staging-platform.json "attachments") and the site flag
# (B1-T12, "mtq_site"). The attachment storage settings are always planned. The flag stays false until the owner
# approves enablement: it turns on only with site_enabled true AND enablement_record_sha256 equal to the SHA-256 of an
# APPROVED infra/config/mtq-site-enablement-record.json with every evidence field filled (output "mtq_attachments"
# refuses anything else). The scanner is the media scanner already running on the host (same Compose service).
locals {
  attachments     = local.platform.attachments
  mtq_site        = local.platform.mtq_site
  mtq_record_path = var.mtq_enablement_record_path != "" ? var.mtq_enablement_record_path : "${path.module}/../../../config/mtq-site-enablement-record.json"
  mtq_record      = try(jsondecode(file(local.mtq_record_path)), {})
  mtq_evidence    = try(local.mtq_record.evidence, {})
  # Every reason the record cannot enable the flag; empty means it can (read only when site_enabled is true).
  mtq_record_problems = concat(
    fileexists(local.mtq_record_path) ? [] : ["the record file is missing"],
    try(local.mtq_record.status, "") == "APPROVED" ? [] : ["the record is not APPROVED"],
    try(local.mtq_record.environment, "") == "staging" && try(local.mtq_record.production, true) == false ? [] : ["the record is not staging-only"],
    can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", try(local.mtq_record.approved_on, ""))) ? [] : ["approved_on is not a date"],
    (trimspace(try(local.mtq_record.approved_by, "")) != "" && !strcontains(upper(try(local.mtq_record.approved_by, "")), "OWNER TO FILL") &&
    try(local.mtq_record.approved_by, "") != try(local.mtq_record.author, "")) ? [] : ["approved_by is not an approver other than the author"],
    [for k in ["independent_review", "ci_run_id", "infra_apply_run_id", "drift_run_id", "migration_verification_run_id", "rollback_verification_run_id"] :
    "evidence.${k} is not filled" if trimspace(tostring(try(local.mtq_evidence[k], ""))) == "" || strcontains(upper(tostring(try(local.mtq_evidence[k], ""))), "OWNER TO FILL")],
    [for k in ["ci_run_id", "infra_apply_run_id", "drift_run_id", "migration_verification_run_id", "rollback_verification_run_id"] :
    "evidence.${k} is not a run id" if !can(regex("^[0-9]{6,}$", tostring(try(local.mtq_evidence[k], ""))))],
    fileexists(local.mtq_record_path) && try(local.mtq_site.enablement_record_sha256, null) == (fileexists(local.mtq_record_path) ? filesha256(local.mtq_record_path) : "-") ? [] : ["enablement_record_sha256 is not the record's SHA-256"],
  )
  attachment_config = {
    VEDA_MTQ_SITE_ENABLED              = local.mtq_site.site_enabled ? "true" : "false"
    VEDA_MTQ_SITE_ENABLEMENT_SHA256    = coalesce(local.mtq_site.enablement_record_sha256, "none")
    VEDA_ATTACHMENT_BACKEND            = "s3"
    VEDA_ATTACHMENT_BUCKET             = module.storage.bucket_names["attachments"]
    VEDA_ATTACHMENT_KMS_KEY_ARN        = local.data_key_alias_arn
    VEDA_ATTACHMENT_SCANNER            = local.scanner.mode
    VEDA_ATTACHMENT_CLAMD_ADDRESS      = "clamd:3310"
    VEDA_ATTACHMENT_UPLOAD_TTL_SECONDS = tostring(local.attachments.upload_ttl_seconds)
  }
}

# MTQ B2-B4 commercial flags (decision log 33, infra/config/staging-platform.json "mtq_commercial"). Both parameters are
# always planned and false by default. VEDA_MTQ_ESTIMATION_ENABLED (scope, BOQ, estimate) turns on only with the B1 site
# flag on, estimation_enabled true AND enablement_record_sha256 equal to the SHA-256 of an APPROVED, staging-only,
# internal-validation-only infra/config/mtq-commercial-enablement-record.json with every evidence field filled.
# VEDA_MTQ_QUOTATION_ENABLED (B4 quotations) needs the estimation flag; estimation may be on without it. Output
# "mtq_commercial" refuses anything else; the API refuses both flags in production and the same dependencies at start.
locals {
  mtq_commercial = try(local.platform.mtq_commercial, {
    status = "DECIDED", estimation_enabled = false, quotation_enabled = false, enablement_record_sha256 = null
  })
  commercial_record_path = var.mtq_commercial_record_path != "" ? var.mtq_commercial_record_path : "${path.module}/../../../config/mtq-commercial-enablement-record.json"
  commercial_record      = try(jsondecode(file(local.commercial_record_path)), {})
  commercial_evidence    = try(local.commercial_record.evidence, {})
  commercial_run_ids     = ["ci_run_id", "deploy_flags_off_run_id", "migration_verification_run_id", "infra_apply_run_id", "drift_run_id"]
  # Every reason the record cannot enable the flags; empty means it can (read only when estimation_enabled is true).
  commercial_record_problems = concat(
    fileexists(local.commercial_record_path) ? [] : ["the record file is missing"],
    try(local.commercial_record.status, "") == "APPROVED" ? [] : ["the record is not APPROVED"],
    try(local.commercial_record.environment, "") == "staging" && try(local.commercial_record.production, true) == false ? [] : ["the record is not staging-only"],
    try(local.commercial_record.scope.internal_protected_staging_validation_only, false) == true && try(local.commercial_record.scope.customer_issuance, true) == false ? [] : ["the record does not limit itself to internal validation without customer issuance"],
    can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", try(local.commercial_record.approved_on, ""))) ? [] : ["approved_on is not a date"],
    (trimspace(try(local.commercial_record.approved_by, "")) != "" && !strcontains(upper(try(local.commercial_record.approved_by, "")), "OWNER TO FILL") &&
    try(local.commercial_record.approved_by, "") != try(local.commercial_record.author, "")) ? [] : ["approved_by is not an approver other than the author"],
    [for k in concat(["independent_review", "regression_checks", "production_isolation"], local.commercial_run_ids) :
    "evidence.${k} is not filled" if trimspace(tostring(try(local.commercial_evidence[k], ""))) == "" || strcontains(upper(tostring(try(local.commercial_evidence[k], ""))), "OWNER TO FILL")],
    [for k in local.commercial_run_ids : "evidence.${k} is not a run id" if !can(regex("^[0-9]{6,}$", tostring(try(local.commercial_evidence[k], ""))))],
    fileexists(local.commercial_record_path) && try(local.mtq_commercial.enablement_record_sha256, null) == (fileexists(local.commercial_record_path) ? filesha256(local.commercial_record_path) : "-") ? [] : ["enablement_record_sha256 is not the record's SHA-256"],
  )
  commercial_config = {
    VEDA_MTQ_ESTIMATION_ENABLED = local.mtq_commercial.estimation_enabled ? "true" : "false"
    VEDA_MTQ_QUOTATION_ENABLED  = local.mtq_commercial.quotation_enabled ? "true" : "false"
  }
}

# Customer quotation experience flags (decision log 35, infra/config/staging-platform.json "customer_proposal"). All
# three parameters are always planned and false by default. Viewing (VEDA_CUSTOMER_PROPOSAL_ENABLED) needs the B4
# quotation flag; interaction needs viewing; acceptance needs interaction. A flag turns on only with an owner-APPROVED,
# staging-only, synthetic-customers-only infra/config/customer-proposal-enablement-record.json bound by its SHA-256,
# every evidence field filled, whose scope names that capability (viewing, interaction, acceptance_testing): acceptance
# is never enabled merely to test viewing. Output "customer_proposal" refuses anything else; the API refuses all three in
# production and the same dependencies at start.
locals {
  cqx = try(local.platform.customer_proposal, {
    status = "DECIDED", proposal_enabled = false, interaction_enabled = false, acceptance_enabled = false, enablement_record_sha256 = null
  })
  cqx_any         = local.cqx.proposal_enabled || local.cqx.interaction_enabled || local.cqx.acceptance_enabled
  cqx_record_path = var.customer_proposal_record_path != "" ? var.customer_proposal_record_path : "${path.module}/../../../config/customer-proposal-enablement-record.json"
  cqx_record      = try(jsondecode(file(local.cqx_record_path)), {})
  cqx_evidence    = try(local.cqx_record.evidence, {})
  cqx_scope       = try(local.cqx_record.scope, {})
  cqx_run_ids     = ["ci_run_id", "deploy_flags_off_run_id", "migration_verification_run_id", "infra_apply_run_id", "drift_run_id"]
  # Every reason the record cannot enable the flags that are on; empty means it can (read only when a flag is on).
  cqx_record_problems = concat(
    fileexists(local.cqx_record_path) ? [] : ["the record file is missing"],
    try(local.cqx_record.status, "") == "APPROVED" ? [] : ["the record is not APPROVED"],
    try(local.cqx_record.environment, "") == "staging" && try(local.cqx_record.production, true) == false ? [] : ["the record is not staging-only"],
    try(local.cqx_scope.protected_staging_only, false) == true && try(local.cqx_scope.synthetic_customers_only, false) == true && try(local.cqx_scope.real_customers, true) == false ? [] : ["the record does not limit itself to protected staging with synthetic customers"],
    !local.cqx.proposal_enabled || try(local.cqx_scope.viewing, false) == true ? [] : ["the record's scope does not authorise viewing"],
    !local.cqx.interaction_enabled || try(local.cqx_scope.interaction, false) == true ? [] : ["the record's scope does not authorise interaction"],
    !local.cqx.acceptance_enabled || try(local.cqx_scope.acceptance_testing, false) == true ? [] : ["the record's scope does not authorise acceptance testing"],
    can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", try(local.cqx_record.approved_on, ""))) ? [] : ["approved_on is not a date"],
    (trimspace(try(local.cqx_record.approved_by, "")) != "" && !strcontains(upper(try(local.cqx_record.approved_by, "")), "OWNER TO FILL") &&
    try(local.cqx_record.approved_by, "") != try(local.cqx_record.author, "")) ? [] : ["approved_by is not an approver other than the author"],
    [for k in concat(["independent_review", "smoke_test", "production_isolation"], local.cqx_run_ids) :
    "evidence.${k} is not filled" if trimspace(tostring(try(local.cqx_evidence[k], ""))) == "" || strcontains(upper(tostring(try(local.cqx_evidence[k], ""))), "OWNER TO FILL")],
    [for k in local.cqx_run_ids : "evidence.${k} is not a run id" if !can(regex("^[0-9]{6,}$", tostring(try(local.cqx_evidence[k], ""))))],
    fileexists(local.cqx_record_path) && try(local.cqx.enablement_record_sha256, null) == (fileexists(local.cqx_record_path) ? filesha256(local.cqx_record_path) : "-") ? [] : ["enablement_record_sha256 is not the record's SHA-256"],
  )
  cqx_config = {
    VEDA_CUSTOMER_PROPOSAL_ENABLED             = local.cqx.proposal_enabled ? "true" : "false"
    VEDA_CUSTOMER_PROPOSAL_INTERACTION_ENABLED = local.cqx.interaction_enabled ? "true" : "false"
    VEDA_CUSTOMER_QUOTATION_ACCEPTANCE_ENABLED = local.cqx.acceptance_enabled ? "true" : "false"
  }
}

# Customer Promise administration (decision log 37, infra/config/staging-platform.json "customer_promise"). One
# staff-only flag, always planned and false by default, separate from the customer-proposal flags. It turns on only with
# an owner-APPROVED, staging-only, synthetic-content-only infra/config/customer-promise-enablement-record.json bound by
# its SHA-256 with every evidence field filled. Output "customer_promise" refuses anything else; the API refuses the flag
# in production.
locals {
  cpa = try(local.platform.customer_promise, {
    status = "DECIDED", admin_enabled = false, enablement_record_sha256 = null
  })
  cpa_record_path = var.customer_promise_record_path != "" ? var.customer_promise_record_path : "${path.module}/../../../config/customer-promise-enablement-record.json"
  cpa_record      = try(jsondecode(file(local.cpa_record_path)), {})
  cpa_evidence    = try(local.cpa_record.evidence, {})
  cpa_scope       = try(local.cpa_record.scope, {})
  cpa_run_ids     = ["ci_run_id", "deploy_flags_off_run_id", "migration_verification_run_id", "infra_apply_run_id", "drift_run_id"]
  # Every reason the record cannot enable the flag; empty means it can (read only when the flag is on).
  cpa_record_problems = concat(
    fileexists(local.cpa_record_path) ? [] : ["the record file is missing"],
    try(local.cpa_record.status, "") == "APPROVED" ? [] : ["the record is not APPROVED"],
    try(local.cpa_record.environment, "") == "staging" && try(local.cpa_record.production, true) == false ? [] : ["the record is not staging-only"],
    try(local.cpa_scope.protected_staging_only, false) == true && try(local.cpa_scope.synthetic_content_only, false) == true && try(local.cpa_scope.real_customers, true) == false ? [] : ["the record does not limit itself to protected staging with synthetic content"],
    can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", try(local.cpa_record.approved_on, ""))) ? [] : ["approved_on is not a date"],
    (trimspace(try(local.cpa_record.approved_by, "")) != "" && !strcontains(upper(try(local.cpa_record.approved_by, "")), "OWNER TO FILL") &&
    try(local.cpa_record.approved_by, "") != try(local.cpa_record.author, "")) ? [] : ["approved_by is not an approver other than the author"],
    [for k in concat(["independent_review", "smoke_test", "production_isolation"], local.cpa_run_ids) :
    "evidence.${k} is not filled" if trimspace(tostring(try(local.cpa_evidence[k], ""))) == "" || strcontains(upper(tostring(try(local.cpa_evidence[k], ""))), "OWNER TO FILL")],
    [for k in local.cpa_run_ids : "evidence.${k} is not a run id" if !can(regex("^[0-9]{6,}$", tostring(try(local.cpa_evidence[k], ""))))],
    fileexists(local.cpa_record_path) && try(local.cpa.enablement_record_sha256, null) == (fileexists(local.cpa_record_path) ? filesha256(local.cpa_record_path) : "-") ? [] : ["enablement_record_sha256 is not the record's SHA-256"],
  )
  cpa_config = {
    VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED = local.cpa.admin_enabled ? "true" : "false"
  }
}

# Customer Project Portal (decision log 41, infra/config/staging-platform.json "customer_portal"). One customer-facing
# flag, always planned and false by default, separate from every other flag. It turns on only with an owner-APPROVED,
# staging-only, synthetic-content-only infra/config/customer-portal-enablement-record.json bound by its SHA-256 with every
# evidence field filled. Output "customer_portal" refuses anything else; the API refuses the flag in production.
locals {
  cpp = try(local.platform.customer_portal, {
    status = "DECIDED", enabled = false, enablement_record_sha256 = null
  })
  cpp_record_path = var.customer_portal_record_path != "" ? var.customer_portal_record_path : "${path.module}/../../../config/customer-portal-enablement-record.json"
  cpp_record      = try(jsondecode(file(local.cpp_record_path)), {})
  cpp_evidence    = try(local.cpp_record.evidence, {})
  cpp_scope       = try(local.cpp_record.scope, {})
  cpp_run_ids     = ["ci_run_id", "deploy_flags_off_run_id", "migration_verification_run_id", "infra_apply_run_id", "drift_run_id"]
  # Every reason the record cannot enable the flag; empty means it can (read only when the flag is on).
  cpp_record_problems = concat(
    fileexists(local.cpp_record_path) ? [] : ["the record file is missing"],
    try(local.cpp_record.status, "") == "APPROVED" ? [] : ["the record is not APPROVED"],
    try(local.cpp_record.environment, "") == "staging" && try(local.cpp_record.production, true) == false ? [] : ["the record is not staging-only"],
    try(local.cpp_scope.protected_staging_only, false) == true && try(local.cpp_scope.synthetic_content_only, false) == true && try(local.cpp_scope.real_customers, true) == false ? [] : ["the record does not limit itself to protected staging with synthetic content"],
    can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", try(local.cpp_record.approved_on, ""))) ? [] : ["approved_on is not a date"],
    (trimspace(try(local.cpp_record.approved_by, "")) != "" && !strcontains(upper(try(local.cpp_record.approved_by, "")), "OWNER TO FILL") &&
    try(local.cpp_record.approved_by, "") != try(local.cpp_record.author, "")) ? [] : ["approved_by is not an approver other than the author"],
    [for k in concat(["independent_review", "smoke_test", "production_isolation"], local.cpp_run_ids) :
    "evidence.${k} is not filled" if trimspace(tostring(try(local.cpp_evidence[k], ""))) == "" || strcontains(upper(tostring(try(local.cpp_evidence[k], ""))), "OWNER TO FILL")],
    [for k in local.cpp_run_ids : "evidence.${k} is not a run id" if !can(regex("^[0-9]{6,}$", tostring(try(local.cpp_evidence[k], ""))))],
    fileexists(local.cpp_record_path) && try(local.cpp.enablement_record_sha256, null) == (fileexists(local.cpp_record_path) ? filesha256(local.cpp_record_path) : "-") ? [] : ["enablement_record_sha256 is not the record's SHA-256"],
  )
  cpp_config = {
    VEDA_CUSTOMER_PORTAL_ENABLED = local.cpp.enabled ? "true" : "false"
  }
}

locals {
  # ADR-012 staging validation (decision log 20): the Budgetary Estimate is enabled on staging only, behind
  # Cloudflare Access. Every estimate links the warranty policy, so the flag goes together with that link
  # (output "estimator" refuses an enabled estimator without one; the API refuses it in production).
  estimator_enabled = try(local.platform.ssm.estimator_enabled, false)
  estimator_config = local.estimator_enabled ? {
    VEDA_ESTIMATOR_ENABLED   = "true"
    VEDA_WARRANTY_POLICY_URL = var.warranty_policy_url
  } : {}
}

# The V3 staging approval record, judged by the shared rules (no resource; read only when a catalog_v3 flag is on).
module "v3_approval" {
  source = "../../modules/v3-approval"

  record_path  = local.approval_record
  bound_sha256 = local.catalog_v3.approval_record_sha256
  today        = formatdate("YYYY-MM-DD", plantimestamp())
}

module "ssm" {
  source = "../../modules/ssm"

  parameter_path               = "/veda/staging"
  config                       = local.app_config
  session_log_group            = "${local.log_group_prefix}/ssm-sessions"
  session_key_alias            = module.kms.aliases["data"]
  audit_key_arn                = module.kms.audit_key_arn
  session_log_retention_days   = local.platform.ssm.session_log_retention_days
  idle_session_timeout_minutes = local.platform.ssm.idle_session_timeout_minutes
  max_session_duration_minutes = local.platform.ssm.max_session_duration_minutes
}

# AUT-110: logs, metric filters, alarms, the alarm topic and the drill queue (host alarms once AUT-108 exists).
module "monitoring" {
  source = "../../modules/monitoring"

  name_prefix          = local.name_prefix
  account_id           = local.account_id
  region               = var.aws_region
  audit_key_arn        = module.kms.audit_key_arn
  audit_key_alias      = module.kms.aliases["audit"]
  log_group_prefix     = local.log_group_prefix
  log_retention_days   = local.platform.monitoring.log_retention_days
  alert_email          = var.budget_alert_email
  trail_log_group_name = module.cloudtrail.log_group_name
  tampering_metric     = module.cloudtrail.tampering_metric
  thresholds           = local.platform.monitoring.thresholds
  host_alarms_enabled  = true
  # Review R4: the alarms of the deployed application stay silent until deployment is enabled.
  deployment_alarms_enabled = local.platform.deploy.enabled
  instance_id               = module.compute.instance_id
}

# AUT-108: the host, its data volume and daily snapshots.
module "compute" {
  source = "../../modules/compute"

  name_prefix              = local.name_prefix
  account_id               = local.account_id
  region                   = var.aws_region
  permissions_boundary_arn = "arn:aws:iam::${local.account_id}:policy/veda-boundary"
  instance_type            = local.platform.compute.instance_type
  ami_id                   = local.platform.compute.ami_id
  subnet_id                = module.network.public_subnet_id
  security_group_id        = module.network.host_security_group_id
  instance_profile_name    = module.runtime_iam.instance_profile_name
  data_key_arn             = module.kms.data_key_arn
  root_volume_gb           = local.platform.compute.root_volume_gb
  data_volume_gb           = local.platform.compute.data_volume_gb
  snapshot_retain_count    = local.platform.compute.snapshot_retain_count
  app_log_group            = module.monitoring.app_log_group
}

# AUT-111: email delivery (SES sandbox): staging sender with DKIM, configuration set, failure alarms.
module "ses" {
  source = "../../modules/ses"

  name_prefix           = local.name_prefix
  account_id            = local.account_id
  region                = var.aws_region
  sender_domain         = local.platform.ses.sender_domain
  sender_local_part     = local.platform.ses.sender_local_part
  sandbox_recipient     = var.budget_alert_email
  alarm_topic_arn       = module.monitoring.topic_arn
  bounce_rate_threshold = local.platform.ses.bounce_rate_threshold
}

# Deployment wiring: veda-deploy, the only way code reaches the host (run by 12-deploy with veda-gh-deploy).
module "deploy" {
  source = "../../modules/deploy"

  name_prefix      = "veda"
  region           = var.aws_region
  artifacts_bucket = module.storage.bucket_names["artifacts"]
  evidence_bucket  = module.storage.bucket_names["evidence"]
  repository_url   = "${local.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${module.ecr.repository_name}"
  data_device      = module.compute.data_device
}

