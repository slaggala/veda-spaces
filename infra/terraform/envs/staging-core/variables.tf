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
