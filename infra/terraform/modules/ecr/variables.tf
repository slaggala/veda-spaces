variable "repository_name" {
  description = "The application repository; the bootstrap deploy role pushes only to veda-api."
  type        = string

  validation {
    condition     = var.repository_name == "veda-api"
    error_message = "The repository is veda-api: the veda-gh-deploy role is scoped to it."
  }
}

variable "data_key_arn" {
  description = "AUT-102 data key."
  type        = string
}

variable "keep_tagged_images" {
  description = "Tagged images kept (older ones expire)."
  type        = number

  validation {
    condition     = var.keep_tagged_images >= 10 && var.keep_tagged_images <= 100
    error_message = "Keep between 10 and 100 tagged images (rollback needs N-1, the release floor and history)."
  }
}

variable "expire_untagged_days" {
  description = "Untagged images expire after this many days."
  type        = number

  validation {
    condition     = var.expire_untagged_days >= 1 && var.expire_untagged_days <= 30
    error_message = "expire_untagged_days must be 1 to 30."
  }
}
