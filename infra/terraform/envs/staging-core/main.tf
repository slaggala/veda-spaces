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
  permissions_boundary_arn = "arn:aws:iam::${local.account_id}:policy/veda-boundary"
  egress_model             = local.network.egress_model
  vpc_cidr                 = local.network.vpc_cidr
  public_subnet_cidr       = local.network.public_subnet_cidr
  az_id_preference         = local.network.az_id_preference
  host_instance_type       = local.network.host_instance_type
  flow_log_traffic_type    = local.network.flow_logs.traffic_type
  flow_log_retention_days  = local.network.flow_logs.retention_days
  tunnel_egress_cidrs      = local.network.tunnel_egress_cidrs
  aws_owned_s3_object_arns = local.network.aws_owned_s3_object_arns
}

