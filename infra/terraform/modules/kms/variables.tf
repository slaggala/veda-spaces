variable "name_prefix" {
  description = "Prefix of every name, e.g. veda-stg."
  type        = string

  validation {
    condition     = can(regex("^veda-[a-z0-9-]{1,20}$", var.name_prefix))
    error_message = "The name prefix must be veda-*."
  }
}

variable "account_id" {
  description = "The approved account; no other account may use the keys."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "account_id must be a 12-digit AWS account ID."
  }
}

variable "region" {
  description = "Deployment region (ap-south-1)."
  type        = string
}

variable "log_group_prefix" {
  description = "CloudWatch Logs groups the audit key may encrypt (e.g. /veda/staging)."
  type        = string
}

variable "trail_name" {
  description = "The CloudTrail trail the audit key may encrypt for (AUT-104)."
  type        = string
}

variable "deletion_window_days" {
  description = "Waiting period before a scheduled key deletion takes effect."
  type        = number

  validation {
    condition     = var.deletion_window_days >= 30 && var.deletion_window_days <= 30
    error_message = "The deletion window must be 30 days (the maximum): a key cannot be lost quickly."
  }
}

variable "rotation_period_days" {
  description = "Automatic rotation period."
  type        = number

  validation {
    condition     = var.rotation_period_days >= 90 && var.rotation_period_days <= 365
    error_message = "Rotation must be between 90 and 365 days."
  }
}
