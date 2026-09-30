# Bootstrap root (AUT-002). Applied once with a temporary owner session; everything after it runs through
# GitHub OIDC. The S3 backend is written by infra/scripts/bootstrap.sh (backend_s3.tf, gitignored) once the
# state bucket exists: the first apply uses local state and is migrated into the bucket it just created.
terraform {
  required_version = ">= 1.10.0, < 2.0.0" # 1.10+: S3 native state locking (use_lockfile)

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # The provider itself refuses to run against any other account: a wrong session cannot touch another
  # account (Aurion or anything else), whatever the variables say.
  allowed_account_ids = [var.expected_account_id]

  default_tags {
    tags = {
      project    = "veda-spaces"
      env        = var.environment
      stack      = "bootstrap"
      managed-by = "terraform"
      repository = "${var.github_owner}/${var.github_repo}"
    }
  }
}
