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

variable "permissions_boundary_arn" {
  description = "veda-boundary (the snapshot-lifecycle role)."
  type        = string
}

variable "instance_type" {
  description = "Host instance type (owner decision N2)."
  type        = string

  validation {
    condition     = can(regex("^t4g\\.(small|medium)$", var.instance_type))
    error_message = "The host is a Graviton t4g.small or t4g.medium (N2; 02 §12.2)."
  }
}

variable "ami_id" {
  description = "Pinned AMI (recorded after the first plan) or null for the latest Amazon Linux 2023 arm64 at plan time. Changing it never replaces the host: AMI updates are a rebuild (runbook)."
  type        = string
  default     = null
}

variable "subnet_id" {
  description = "AUT-101 host subnet."
  type        = string
}

variable "security_group_id" {
  description = "AUT-101 host security group (no inbound)."
  type        = string
}

variable "instance_profile_name" {
  description = "AUT-106 instance profile."
  type        = string
}

variable "data_key_arn" {
  description = "AUT-102 data key (EBS)."
  type        = string
}

variable "root_volume_gb" {
  description = "Root volume size (OS, Docker images, logs)."
  type        = number

  validation {
    condition     = var.root_volume_gb >= 8 && var.root_volume_gb <= 30
    error_message = "root_volume_gb must be 8 to 30."
  }
}

variable "data_volume_gb" {
  description = "Data volume size (/var/lib/veda: SQLite, WAL, local snapshots)."
  type        = number

  validation {
    condition     = var.data_volume_gb >= 10 && var.data_volume_gb <= 100
    error_message = "data_volume_gb must be 10 to 100."
  }
}

variable "snapshot_retain_count" {
  description = "Daily EBS snapshots of the data volume kept (DLM)."
  type        = number

  validation {
    condition     = var.snapshot_retain_count >= 3 && var.snapshot_retain_count <= 35
    error_message = "snapshot_retain_count must be 3 to 35."
  }
}

variable "app_log_group" {
  description = "AUT-110 application log group (Docker awslogs)."
  type        = string
}
