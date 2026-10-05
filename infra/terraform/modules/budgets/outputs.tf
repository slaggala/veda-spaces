output "name" {
  description = "Budget name."
  value       = aws_budgets_budget.this.name
}

output "limit" {
  description = "Monthly limit as AWS stores it (amount and unit)."
  value       = { amount = aws_budgets_budget.this.limit_amount, unit = aws_budgets_budget.this.limit_unit }
}

output "forecast_thresholds_percent" {
  description = "Forecast alert thresholds, ascending."
  # The notification set is sensitive as a whole (it holds the address); the thresholds alone are not.
  value = nonsensitive(sort([for n in aws_budgets_budget.this.notification : format("%06.2f", n.threshold) if n.notification_type == "FORECASTED"]))
}

output "notifications" {
  description = "The alerts as planned (for the offline tests and the review)."
  value       = aws_budgets_budget.this.notification
  sensitive   = true
}
