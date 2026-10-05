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

output "alerts" {
  description = "Every alert without its recipient (type, comparison, threshold, SNS topics, number of email recipients), ascending by threshold, so the plan text shows what the hidden notification blocks contain."
  # The notification set is sensitive as a whole because it holds the address; this summary leaves the address out.
  value = nonsensitive([for k, n in { for n in aws_budgets_budget.this.notification : format("%010.2f-%s", n.threshold, n.notification_type) => n } : {
    notification_type   = n.notification_type
    comparison_operator = n.comparison_operator
    threshold           = n.threshold
    threshold_type      = n.threshold_type
    sns_topic_arns      = coalesce(n.subscriber_sns_topic_arns, [])
    email_recipients    = length(n.subscriber_email_addresses)
  }])
}

output "notifications" {
  description = "The alerts as planned (for the offline tests and the review)."
  value       = aws_budgets_budget.this.notification
  sensitive   = true
}
