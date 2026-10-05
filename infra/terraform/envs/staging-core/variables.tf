variable "account_manifest_path" {
  description = "Path of the approved-account manifest. Empty means infra/config/staging-account.json; only the offline tests override it."
  type        = string
  default     = ""
}

variable "aws_region" {
  description = "Deployment region. Fixed by ADR-008 (owner decision OD-B1)."
  type        = string
  default     = "ap-south-1"

  validation {
    condition     = var.aws_region == "ap-south-1"
    error_message = "Veda staging is approved for ap-south-1 only."
  }

  validation {
    condition     = try(local.manifest.region, "") == var.aws_region
    error_message = "The account manifest must approve ap-south-1 (Mumbai) only."
  }
}

variable "budget_config_path" {
  description = "Path of the budget decision (AUT-112). Empty means infra/config/staging-budget.json; only the offline tests override it. Its values are validated by modules/budgets: an undecided limit stops the plan."
  type        = string
  default     = ""
}

variable "budget_alert_email" {
  description = "The owner's alert address (O16): budget alerts (AUT-112), the alarm topic (AUT-110) and the SES sandbox recipient (AUT-111). From the BUDGET_ALERT_EMAIL secret of the staging-plan environment; never committed (public repository)."
  type        = string
  default     = ""
  sensitive   = true
  nullable    = false

  validation {
    condition     = can(regex("^[^@[:space:],;]+@[^@[:space:],;]+\\.[^@[:space:],;]+$", var.budget_alert_email))
    error_message = "budget_alert_email is not one email address: set the BUDGET_ALERT_EMAIL secret of the staging-plan environment (docs/operations/staging-infra-workflows.md)."
  }
}

variable "network_config_path" {
  description = "Path of the network decision (AUT-101). Empty means infra/config/staging-network.json; only the offline tests override it."
  type        = string
  default     = ""
}

variable "platform_config_path" {
  description = "Path of the platform decisions (AUT-102 … AUT-111). Empty means infra/config/staging-platform.json; only the offline tests override it."
  type        = string
  default     = ""
}
