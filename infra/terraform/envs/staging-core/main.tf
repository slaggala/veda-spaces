# The approved account and repository, from the reviewed manifest (F3, PB-01).
locals {
  manifest_path = var.account_manifest_path != "" ? var.account_manifest_path : "${path.module}/../../../config/staging-account.json"
  manifest      = jsondecode(file(local.manifest_path))
  account_id    = regex("^[0-9]{12}$", local.manifest.account_id)

  # AUT-112: the reviewed budget decision (O16); the recipient comes from var.budget_alert_email.
  budget_path = var.budget_config_path != "" ? var.budget_config_path : "${path.module}/../../../config/staging-budget.json"
  budget      = jsondecode(file(local.budget_path))
}

# AUT-112: monthly cost budget with forecast alerts to the owner. Global service, no region.
module "budget" {
  source = "../../modules/budgets"

  name                              = local.budget.name
  monthly_limit_usd                 = local.budget.monthly_limit_usd
  forecast_alert_thresholds_percent = local.budget.forecast_alert_thresholds_percent
  alert_email                       = var.budget_alert_email
}
