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

  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "account_id must be a 12-digit AWS account ID."
  }
}

variable "region" {
  description = "Deployment region (ap-south-1)."
  type        = string
}

variable "permissions_boundary_arn" {
  description = "veda-boundary."
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:policy/veda-boundary$", var.permissions_boundary_arn))
    error_message = "permissions_boundary_arn must be the account's veda-boundary policy."
  }
}

variable "data_key_alias" {
  description = "AUT-102 data key alias (MFA secrets used directly; S3 and EBS). Matched by kms:ResourceAliases so the policy is known at plan time."
  type        = string

  validation {
    condition     = startswith(var.data_key_alias, "alias/veda-")
    error_message = "data_key_alias must be an alias/veda-* alias."
  }
}

variable "audit_key_alias" {
  description = "AUT-102 audit key alias (evidence uploads through S3 only)."
  type        = string

  validation {
    condition     = startswith(var.audit_key_alias, "alias/veda-")
    error_message = "audit_key_alias must be an alias/veda-* alias."
  }
}

variable "bucket_arns" {
  description = "AUT-103 bucket ARNs by purpose (litestream, snapshots, anchor, artifacts, evidence, logs, media)."
  type        = map(string)

  validation {
    condition     = alltrue([for k in ["litestream", "snapshots", "anchor", "artifacts", "evidence", "media"] : contains(keys(var.bucket_arns), k)])
    error_message = "bucket_arns must name the litestream, snapshots, anchor, artifacts, evidence and media buckets."
  }

  validation {
    condition     = can(regex("^arn:aws:s3:::veda-stg-media-[0-9]{12}$", try(var.bucket_arns["media"], "")))
    error_message = "the media bucket is the staging media bucket veda-stg-media-<account> (never a production bucket)."
  }
}

variable "repository_name" {
  description = "AUT-105 repository the host pulls from."
  type        = string
}

variable "log_group_prefix" {
  description = "CloudWatch Logs prefix the host writes to (/veda/staging)."
  type        = string
}

variable "parameter_path" {
  description = "SSM parameter path the host reads (/veda/staging): config/* (Terraform) and app/* (seeded by the owner, AUT-302)."
  type        = string
}

variable "ses_send" {
  description = "SES identities and configuration set the host may send through, and the only From address (AUT-111). Empty until AUT-111."
  type = object({
    resources    = list(string)
    from_address = string
  })
  default = { resources = [], from_address = "" }
}
