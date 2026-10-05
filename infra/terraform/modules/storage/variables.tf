variable "name_prefix" {
  description = "Prefix of the staging bucket names (veda-stg)."
  type        = string

  validation {
    condition     = var.name_prefix == "veda-stg"
    error_message = "The bucket names are fixed by the bootstrap (veda-stg-*, veda-evidence-*): the deploy and evidence roles and the data-read denies are scoped to them."
  }
}

variable "account_id" {
  description = "The approved account (bucket names, policies)."
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

variable "data_key_arn" {
  description = "AUT-102 data key: Litestream, snapshots, anchors, artifacts."
  type        = string
}

variable "audit_key_arn" {
  description = "AUT-102 audit key: logs (trail, flow logs) and evidence."
  type        = string
}

variable "trail_name" {
  description = "The CloudTrail trail allowed to write to the logs bucket (AUT-104)."
  type        = string
}

variable "retention" {
  description = "Lifecycle and lock periods (infra/config/staging-platform.json, storage)."
  type = object({
    litestream_noncurrent_days  = number
    snapshots_expire_days       = number
    artifacts_expire_days       = number
    artifacts_noncurrent_days   = number
    logs_cloudtrail_expire_days = number
    logs_flow_expire_days       = number
    evidence_lock_mode          = string
    evidence_lock_days          = number
  })

  validation {
    condition     = var.retention.evidence_lock_mode == "COMPLIANCE" && var.retention.evidence_lock_days >= 1 && var.retention.evidence_lock_days <= 365
    error_message = "Evidence is locked in COMPLIANCE mode for 1 to 365 days (GOVERNANCE could be bypassed; longer is a reviewed change)."
  }

  validation {
    condition     = var.retention.snapshots_expire_days > 35
    error_message = "Snapshots must outlive their 35-day application lock (VEDA_SNAPSHOT_LOCK_DAYS default)."
  }

  validation {
    condition     = alltrue([for k, v in var.retention : (k == "evidence_lock_mode" || try(tonumber(v) > 0, false))])
    error_message = "Every period must be a positive number of days."
  }
}
