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

  name_prefix   = local.name_prefix
  account_id    = local.account_id
  region        = var.aws_region
  data_key_arn  = module.kms.data_key_arn
  audit_key_arn = module.kms.audit_key_arn
  trail_name    = local.trail_name
  retention = {
    for k in ["litestream_noncurrent_days", "snapshots_expire_days", "artifacts_expire_days", "artifacts_noncurrent_days",
    "logs_cloudtrail_expire_days", "logs_flow_expire_days", "evidence_lock_mode", "evidence_lock_days"] : k => local.platform.storage[k]
  }
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
    }, local.estimator_config
  )
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

