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

# AUT-101: what the network plan creates, readable in the plan text, and the IDs AUT-108 attaches the host to.
output "network" {
  description = "Staging network summary and IDs."
  value = merge(module.network.summary, {
    vpc_id                 = module.network.vpc_id
    public_subnet_id       = module.network.public_subnet_id
    host_security_group_id = module.network.host_security_group_id
  })
}

