variable "name_prefix" {
  description = "Prefix of every name (veda-stg)."
  type        = string

  validation {
    condition     = can(regex("^veda-[a-z0-9-]{1,20}$", var.name_prefix))
    error_message = "The name prefix must be veda-*."
  }
}

variable "account_id" {
  description = "The approved account."
  type        = string
}

variable "region" {
  description = "Deployment region (ap-south-1)."
  type        = string
}

variable "trail_name" {
  description = "Trail name; the audit key and the logs bucket admit CloudTrail for this trail only."
  type        = string
}

variable "logs_bucket_name" {
  description = "AUT-103 logs bucket (prefix cloudtrail/)."
  type        = string
}

variable "audit_key_arn" {
  description = "AUT-102 audit key."
  type        = string
}

variable "log_group_prefix" {
  description = "CloudWatch Logs prefix (/veda/staging)."
  type        = string
}

variable "log_group_retention_days" {
  description = "Retention of the trail's CloudWatch Logs copy."
  type        = number

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365], var.log_group_retention_days)
    error_message = "log_group_retention_days must be a CloudWatch Logs retention value up to 365."
  }
}

variable "permissions_boundary_arn" {
  description = "veda-boundary."
  type        = string
}
