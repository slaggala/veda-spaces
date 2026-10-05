variable "name_prefix" {
  description = "Prefix of every name (veda-stg)."
  type        = string
}

variable "account_id" {
  description = "The approved account."
  type        = string
}

variable "region" {
  description = "Deployment region (ap-south-1)."
  type        = string
}

variable "sender_domain" {
  description = "Staging sending domain (DKIM records published by AUT-202). A subdomain, so the apex records never change."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+\\.vedaspaces\\.com$", var.sender_domain))
    error_message = "The staging sender is a subdomain of vedaspaces.com (the apex SPF, MX and verification records must not change)."
  }
}

variable "sender_local_part" {
  description = "Local part of the From address (e.g. no-reply)."
  type        = string
}

variable "sandbox_recipient" {
  description = "Owner address verified as a sandbox recipient (the BUDGET_ALERT_EMAIL secret). Sensitive."
  type        = string
  sensitive   = true
}

variable "alarm_topic_arn" {
  description = "AUT-110 alarm topic."
  type        = string
}

variable "bounce_rate_threshold" {
  description = "Alarm when the account bounce rate exceeds this fraction (AWS reviews accounts above 0.05)."
  type        = number

  validation {
    condition     = var.bounce_rate_threshold > 0 && var.bounce_rate_threshold <= 0.05
    error_message = "bounce_rate_threshold must be above 0 and at most 0.05."
  }
}
