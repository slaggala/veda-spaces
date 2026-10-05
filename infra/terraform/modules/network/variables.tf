variable "name_prefix" {
  description = "Prefix of every resource name, e.g. veda-stg."
  type        = string

  validation {
    condition     = can(regex("^veda-[a-z0-9-]{1,20}$", var.name_prefix))
    error_message = "The name prefix must be veda-*."
  }
}

variable "account_id" {
  description = "The approved account (S3 endpoint policy, flow-log role trust)."
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

variable "egress_model" {
  description = "Owner decision N1. Only A is implemented: public subnet, no inbound access, outbound restricted to 443 and the tunnel."
  type        = string

  validation {
    condition     = var.egress_model == "A"
    error_message = "Only egress model A (owner decision N1) is implemented."
  }
}

variable "vpc_cidr" {
  description = "VPC range (owner decision N4)."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && tonumber(split("/", var.vpc_cidr)[1]) >= 16 && tonumber(split("/", var.vpc_cidr)[1]) <= 24
    error_message = "vpc_cidr must be an IPv4 CIDR between /16 and /24."
  }
}

variable "public_subnet_cidr" {
  description = "The host subnet, inside vpc_cidr."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.public_subnet_cidr))
    error_message = "public_subnet_cidr must be an IPv4 CIDR."
  }
}

variable "az_id_preference" {
  description = "Availability-zone IDs in order of preference (owner decision N5); the first that offers host_instance_type is used."
  type        = list(string)

  validation {
    condition     = length(var.az_id_preference) > 0 && alltrue([for z in var.az_id_preference : can(regex("^aps1-az[0-9]$", z))])
    error_message = "az_id_preference must list ap-south-1 AZ IDs (aps1-azN)."
  }
}

variable "az_id" {
  description = "The pinned AZ ID of the host subnet (recorded after the first plan), or null to choose from az_id_preference. Pinning keeps a change of offerings or preferences from replacing the subnet."
  type        = string
  default     = null

  validation {
    condition     = var.az_id == null || can(regex("^aps1-az[0-9]$", var.az_id))
    error_message = "az_id must be null or an ap-south-1 AZ ID (aps1-azN)."
  }
}

variable "host_instance_type" {
  description = "Instance type of the host (owner decision N2); the subnet's AZ must offer it."
  type        = string
}

variable "flow_log_traffic_type" {
  description = "Owner decision N6."
  type        = string

  validation {
    condition     = contains(["ALL", "REJECT", "ACCEPT"], var.flow_log_traffic_type)
    error_message = "flow_log_traffic_type must be ALL, REJECT or ACCEPT."
  }
}

variable "flow_log_retention_days" {
  description = "Owner decision N6."
  type        = number

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365], var.flow_log_retention_days)
    error_message = "flow_log_retention_days must be a CloudWatch Logs retention value up to 365."
  }
}

variable "tunnel_egress_cidrs" {
  description = "Cloudflare tunnel edge ranges for TCP and UDP 7844 (owner decision N8)."
  type        = list(string)

  validation {
    condition     = length(var.tunnel_egress_cidrs) > 0 && alltrue([for c in var.tunnel_egress_cidrs : can(cidrnetmask(c)) && c != "0.0.0.0/0"])
    error_message = "tunnel_egress_cidrs must be IPv4 CIDRs, not 0.0.0.0/0."
  }
}

variable "aws_owned_s3_object_arns" {
  description = "AWS-owned S3 objects the host may read through the endpoint (ECR layers, Amazon Linux repositories)."
  type        = list(string)

  validation {
    condition     = alltrue([for a in var.aws_owned_s3_object_arns : can(regex("^arn:aws:s3:::[a-z0-9.-]+/\\*$", a))])
    error_message = "aws_owned_s3_object_arns must be S3 object ARNs of the form arn:aws:s3:::bucket/*."
  }
}

variable "permissions_boundary_arn" {
  description = "veda-boundary; every role carries it (the apply role cannot create a role without it)."
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:policy/veda-boundary$", var.permissions_boundary_arn))
    error_message = "permissions_boundary_arn must be the account's veda-boundary policy."
  }
}
