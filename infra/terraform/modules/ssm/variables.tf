variable "parameter_path" {
  description = "Root of the staging parameters (/veda/staging). Terraform writes only <path>/config/*; <path>/app/* is seeded by the owner (AUT-302)."
  type        = string

  validation {
    condition     = var.parameter_path == "/veda/staging"
    error_message = "The parameter path is /veda/staging: the bootstrap roles' read and deny rules are scoped to it."
  }
}

variable "config" {
  description = "Non-secret application configuration, rendered into /etc/veda/api.env on the host (name => value). Never a secret."
  type        = map(string)

  validation {
    condition     = alltrue([for k, v in var.config : can(regex("^(VEDA|LITESTREAM)_[A-Z0-9_]+$", k))])
    error_message = "Configuration names must be VEDA_* or LITESTREAM_* environment variable names."
  }

  validation {
    condition     = !anytrue([for k, v in var.config : can(regex("(SECRET|PRIVATE|PASSWORD|TOKEN_KEY|HMAC|CHAIN_KEY$|DSN)", k))])
    error_message = "Secrets never go through Terraform: they are seeded by the owner under /veda/staging/app (AUT-302)."
  }
}

variable "session_log_group" {
  description = "Session Manager transcripts (CloudWatch Logs group under /veda/staging)."
  type        = string
}

variable "session_key_alias" {
  description = "KMS key alias that encrypts Session Manager session data (the data key)."
  type        = string
}

variable "audit_key_arn" {
  description = "AUT-102 audit key: encrypts the session log group."
  type        = string
}

variable "session_log_retention_days" {
  description = "Retention of the session transcripts."
  type        = number
}

variable "idle_session_timeout_minutes" {
  description = "Idle Session Manager sessions end after this many minutes."
  type        = number

  validation {
    condition     = var.idle_session_timeout_minutes >= 5 && var.idle_session_timeout_minutes <= 60
    error_message = "idle_session_timeout_minutes must be 5 to 60."
  }
}

variable "max_session_duration_minutes" {
  description = "A Session Manager session ends after this many minutes."
  type        = number

  validation {
    condition     = var.max_session_duration_minutes >= 15 && var.max_session_duration_minutes <= 240
    error_message = "max_session_duration_minutes must be 15 to 240."
  }
}
