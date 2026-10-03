# Staging core root (AUT-101 … AUT-112), planned and applied only through GitHub OIDC (AUT-301). The S3 backend is
# configured at init by infra/scripts/stack.sh (bucket, key staging/core.tfstate, state key, use_lockfile).
terraform {
  required_version = ">= 1.10.0, < 2.0.0" # 1.10+: S3 native state locking (use_lockfile)

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  # The provider refuses to run against any account but the approved one, whatever session it is given.
  allowed_account_ids = [local.account_id]

  default_tags {
    tags = {
      project    = "veda-spaces"
      env        = "staging"
      stack      = "core"
      managed-by = "terraform"
      repository = local.manifest.repository
    }
  }
}
