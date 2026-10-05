# AUT-112: the budget as planned. The precondition stops the plan while the owner's limit is undecided (O16).
output "budget" {
  description = "Name and monthly limit of the staging cost budget."
  value       = { name = module.budget.name, limit = module.budget.limit }

  precondition {
    condition     = try(local.budget.monthly_limit_usd > 0, false)
    error_message = "Owner decision O16: monthly_limit_usd in infra/config/staging-budget.json is undecided or not a positive number. Nothing is planned until it is decided."
  }
}
