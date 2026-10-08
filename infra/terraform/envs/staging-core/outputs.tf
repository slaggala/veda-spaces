# AUT-112: the budget as planned. Terraform hides each notification block of the resource (it holds the sensitive
# address), so this output is where the plan text shows the alerts to the reviewer. The precondition stops the plan
# while the owner's limit is undecided (O16).
output "budget" {
  description = "Name, monthly limit and alerts (without the recipient) of the staging cost budget."
  value       = { name = module.budget.name, limit = module.budget.limit, alerts = module.budget.alerts }

  precondition {
    condition     = try(local.budget.monthly_limit_usd > 0, false)
    error_message = "Owner decision O16: monthly_limit_usd in infra/config/staging-budget.json is undecided or not a positive number. Nothing is planned until it is decided."
  }
}

# ADR-012 staging validation: whether the Budgetary Estimate is enabled on staging and the policy page it links to.
output "estimator" {
  description = "Budgetary Estimate on staging (behind Cloudflare Access): enabled, and the warranty policy link."
  value       = { enabled = local.estimator_enabled, warranty_policy_url = var.warranty_policy_url }

  precondition {
    condition     = !local.estimator_enabled || var.warranty_policy_url != ""
    error_message = "The estimator is enabled in infra/config/staging-platform.json but no warranty policy link is set: set the WARRANTY_POLICY_URL variable of the staging-plan environment to the approved policy page. Nothing is planned until then (no broken or placeholder link)."
  }
}

# AUT-101: what the network plan creates, readable in the plan text, and the IDs AUT-108 attaches the host to.
output "network" {
  description = "Staging network summary and IDs."
  value = merge(module.network.summary, {
    vpc_id                 = module.network.vpc_id
    public_subnet_id       = module.network.public_subnet_id
    host_security_group_id = module.network.host_security_group_id
  })
}

