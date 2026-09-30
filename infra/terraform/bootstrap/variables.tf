variable "expected_account_id" {
  description = "The dedicated Veda staging AWS account. The provider refuses every other account."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must be a 12-digit AWS account ID."
  }

  # F3: the account is approved in code (infra/config/staging-account.json, changed only by a reviewed pull
  # request), not by whatever is typed at run time.
  validation {
    condition     = var.expected_account_id == local.approved_account_id
    error_message = "expected_account_id is not the approved staging account in infra/config/staging-account.json. Commit the account there in a reviewed change first."
  }
}

variable "account_manifest_path" {
  description = "Path of the approved-account manifest. Empty means infra/config/staging-account.json; only the offline tests override it."
  type        = string
  default     = ""
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

  # RR-03/RR-07: each role is trusted only by the protected environment that infra/scripts/github-setup.sh creates
  # and verifies for it. An override would point a role at an environment nobody protects.
  validation {
    condition = jsonencode(var.github_environments) == jsonencode({
      plan = "staging-plan", apply = "staging-infra", deploy = "staging", evidence = "staging-evidence"
    })
    error_message = "github_environments is fixed: plan=staging-plan, apply=staging-infra, deploy=staging, evidence=staging-evidence (the protected environments github-setup.sh verifies)."
  }
}

variable "existing_github_oidc_provider_arn" {
  description = "Set when the account already has the GitHub OIDC provider (auto-discovered); empty creates it."
  type        = string
  default     = ""
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

  validation {
    condition     = var.role_max_session_seconds >= 900 && var.role_max_session_seconds <= 3600
    error_message = "GitHub role sessions must last between 15 minutes and one hour."
  }
}
