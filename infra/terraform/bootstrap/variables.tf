variable "expected_account_id" {
  description = "The dedicated Veda staging AWS account. The provider refuses every other account."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must be a 12-digit AWS account ID."
  }
}

variable "aws_region" {
  description = "Deployment region. Fixed by ADR-008 (owner Decision 5)."
  type        = string
  default     = "ap-south-1"

  validation {
    condition     = var.aws_region == "ap-south-1"
    error_message = "Veda staging is approved for ap-south-1 only."
  }
}

variable "environment" {
  description = "Environment tag value."
  type        = string
  default     = "staging"

  validation {
    condition     = var.environment == "staging"
    error_message = "This bootstrap serves the staging account only; production gets its own account and review."
  }
}

variable "name_prefix" {
  description = "Prefix of every named resource (roles, policies, buckets, aliases)."
  type        = string
  default     = "veda"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,15}$", var.name_prefix))
    error_message = "name_prefix must be lowercase alphanumeric/hyphen, 2-16 characters."
  }
}

variable "github_owner" {
  description = "GitHub organisation or user that owns the repository (auto-discovered)."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name (auto-discovered)."
  type        = string
}

variable "github_environments" {
  description = "GitHub environment trusted by each role. The OIDC subject is pinned to repo:<owner>/<repo>:environment:<name>."
  type = object({
    plan     = string
    apply    = string
    deploy   = string
    evidence = string
  })
  default = {
    plan     = "staging-plan"
    apply    = "staging-infra"
    deploy   = "staging"
    evidence = "staging-evidence"
  }
}

variable "existing_github_oidc_provider_arn" {
  description = "Set when the account already has the GitHub OIDC provider (auto-discovered); empty creates it."
  type        = string
  default     = ""
}

variable "enable_account_guardrails" {
  description = "Account-wide defaults: S3/EBS-snapshot/AMI public-access blocks, EBS encryption by default, IMDSv2 by default, IAM Access Analyzer."
  type        = bool
  default     = true
}

variable "state_noncurrent_version_days" {
  description = "Days a superseded state version is kept."
  type        = number
  default     = 90
}

variable "role_max_session_seconds" {
  description = "Maximum session length of the GitHub roles."
  type        = number
  default     = 3600
}
