variable "name_prefix" {
  description = "Prefix of every name (veda-stg); the bootstrap deploy role may set the state of veda-stg-* alarms (drills)."
  type        = string

  validation {
    condition     = var.name_prefix == "veda-stg"
    error_message = "The prefix is veda-stg: the bootstrap scopes alarm drills and the alarm-capture queue to it."
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

variable "audit_key_arn" {
  description = "AUT-102 audit key (log groups)."
  type        = string
}

variable "audit_key_alias" {
  description = "AUT-102 audit key alias (the alarm topic)."
  type        = string
}

variable "log_group_prefix" {
  description = "/veda/staging"
  type        = string
}

variable "log_retention_days" {
  description = "Retention of the application and host log groups."
  type        = number
}

variable "alert_email" {
  description = "Owner address subscribed to the alarm topic (the BUDGET_ALERT_EMAIL secret of staging-plan). Sensitive."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[^@[:space:],;]+@[^@[:space:],;]+\\.[^@[:space:],;]+$", var.alert_email))
    error_message = "alert_email must be exactly one email address."
  }
}

variable "trail_log_group_name" {
  description = "AUT-104 trail log group (delivery alarm)."
  type        = string
}

variable "tampering_metric" {
  description = "AUT-104 tampering metric."
  type        = object({ namespace = string, name = string })
}

variable "deployment_alarms_enabled" {
  description = "Actions of the alarms fed by the deployed application, the agent or the heartbeat (deploy.enabled; review R4). False: those alarms exist but notify no one."
  type        = bool
  default     = false
}

variable "host_alarms_enabled" {
  description = "Create the host alarms (AUT-108). A known boolean: the instance id itself is unknown until apply."
  type        = bool
  default     = false
}

variable "instance_id" {
  description = "The host (AUT-108), used as the alarm dimension when host_alarms_enabled."
  type        = string
  default     = null
}

variable "thresholds" {
  description = "Alarm thresholds (staging-platform.json monitoring)."
  type = object({
    server_errors_per_5min = number
    cpu_percent            = number
    memory_percent         = number
    data_disk_percent      = number
    root_disk_percent      = number
  })
}
