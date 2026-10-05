variable "name" {
  description = "Budget name; veda-* like every Veda resource."
  type        = string

  validation {
    condition     = can(regex("^veda-[a-z0-9-]{1,90}$", var.name))
    error_message = "The budget name must be veda-* (lowercase letters, digits and hyphens)."
  }
}

variable "monthly_limit_usd" {
  description = "Monthly cost limit in USD (owner decision O16). The forecast thresholds are percentages of it. null: undecided."
  type        = number
  nullable    = true

  # null is the undecided state: the calling root stops the plan (envs/staging-core output budget), and the plan
  # guard refuses a budget without a limit.
  validation {
    condition     = try(var.monthly_limit_usd > 0, var.monthly_limit_usd == null)
    error_message = "The monthly limit must be a positive number of USD (owner decision O16)."
  }
}

variable "forecast_alert_thresholds_percent" {
  description = "Forecast alerts, as percentages of the monthly limit (owner decision O16: 80 and 100)."
  type        = list(number)

  validation {
    condition = try(
      length(var.forecast_alert_thresholds_percent) > 0 &&
      length(distinct(var.forecast_alert_thresholds_percent)) == length(var.forecast_alert_thresholds_percent) &&
      alltrue([for t in var.forecast_alert_thresholds_percent : t > 0 && t <= 1000]),
      false
    )
    error_message = "Give at least one forecast threshold, each distinct and between 0 (exclusive) and 1000 percent."
  }
}

variable "alert_email" {
  description = "The one address that receives the alerts. Sensitive: it stays out of the plan text and the job log."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[^@[:space:],;]+@[^@[:space:],;]+\\.[^@[:space:],;]+$", var.alert_email))
    error_message = "alert_email must be exactly one email address."
  }
}
