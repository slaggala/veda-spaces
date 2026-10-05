# Monthly cost budget of the staging account with forecast alerts by email (AUT-112). AWS Budgets is a global service:
# the resource has no region, and veda-boundary lists budgets:* among the global actions. No budget action is created
# (the plan guard refuses aws_budgets_budget_action): the budget alerts, it never changes the account.
resource "aws_budgets_budget" "this" {
  name         = var.name
  budget_type  = "COST"
  time_unit    = "MONTHLY"
  limit_amount = try(format("%.2f", var.monthly_limit_usd), null)
  limit_unit   = "USD"

  dynamic "notification" {
    for_each = toset(var.forecast_alert_thresholds_percent)
    content {
      notification_type          = "FORECASTED"
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      subscriber_email_addresses = [var.alert_email]
    }
  }
}
