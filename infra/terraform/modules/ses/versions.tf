# The provider comes from the calling root (envs/staging-core), which pins the approved account and region. A module
# never configures its own AWS provider (the plan guard refuses one).
terraform {
  required_version = ">= 1.10.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
  }
}
