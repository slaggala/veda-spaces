variable "name_prefix" {
  description = "Document prefix (veda): the bootstrap deploy role may run veda-deploy, the evidence role veda-collect."
  type        = string

  validation {
    condition     = var.name_prefix == "veda"
    error_message = "Document names are veda-deploy and veda-collect: the bootstrap roles are scoped to them."
  }
}

variable "region" {
  description = "Deployment region (ap-south-1)."
  type        = string
}

variable "artifacts_bucket" {
  description = "AUT-103 artifacts bucket (deploy bundles)."
  type        = string
}

variable "evidence_bucket" {
  description = "AUT-103 evidence bucket (veda-collect output)."
  type        = string
}

variable "repository_url" {
  description = "AUT-105 repository URL built from the account and region (known at plan time); the image is pulled by digest."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/veda-api$", var.repository_url))
    error_message = "repository_url must be <account>.dkr.ecr.<region>.amazonaws.com/veda-api."
  }
}

variable "data_device" {
  description = "Device name of the data volume attachment (AUT-108); Amazon Linux links it to the NVMe device. A constant, so the document is known at plan time."
  type        = string

  validation {
    condition     = can(regex("^/dev/sd[f-p]$", var.data_device))
    error_message = "data_device must be an EBS attachment device name /dev/sdf to /dev/sdp."
  }
}

variable "agent_config_file" {
  description = "Path on the host of the CloudWatch agent configuration from the deploy bundle (review R2: not an SSM parameter, which the plan role could not read)."
  type        = string
  default     = "/opt/veda/host/cloudwatch-agent.json"

  validation {
    condition     = startswith(var.agent_config_file, "/opt/veda/host/")
    error_message = "The agent configuration comes from the verified deploy bundle under /opt/veda/host/."
  }
}
