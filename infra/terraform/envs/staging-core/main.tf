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
}

# AUT-107: non-secret configuration and Session Manager preferences.
locals {
  app_config = {
    VEDA_ENV                  = "staging"
    VEDA_AWS_REGION           = var.aws_region
    VEDA_LOG_LEVEL            = "INFO"
    VEDA_KMS_PROVIDER         = "aws"
    VEDA_KMS_KEY_ARN          = "arn:aws:kms:${var.aws_region}:${local.account_id}:${module.kms.aliases["data"]}"
    VEDA_DATABASE_URL         = "sqlite:////var/lib/veda/veda.db"
    VEDA_SNAPSHOT_DIR         = "/var/lib/veda/snapshots"
    VEDA_SNAPSHOT_BUCKET      = module.storage.bucket_names["snapshots"]
    VEDA_ANCHOR_BUCKET        = module.storage.bucket_names["anchor"]
    LITESTREAM_BUCKET         = module.storage.bucket_names["litestream"]
    LITESTREAM_REGION         = var.aws_region
    LITESTREAM_RETENTION      = local.platform.ssm.litestream_retention
    VEDA_EMAIL_PROVIDER       = "ses"
    VEDA_TURNSTILE_MODE       = "cloudflare"
    VEDA_COOKIE_SECURE        = "true"
    VEDA_RATE_LIMITS_ENABLED  = "true"
    VEDA_BREAK_GLASS_IDENTITY = "sts"
    VEDA_TRUSTED_PROXY_CIDRS  = local.platform.ssm.trusted_proxy_cidrs
    VEDA_APP_ORIGIN           = local.platform.ssm.app_origin
    VEDA_APP_BASE_URL         = local.platform.ssm.app_origin
    VEDA_API_BASE_URL         = local.platform.ssm.api_base_url
    VEDA_JWT_ISSUER           = local.platform.ssm.api_base_url
    VEDA_PUBLIC_SITE_ORIGINS  = local.platform.ssm.public_site_origins
  }
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

