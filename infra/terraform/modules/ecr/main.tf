# Application image repository (AUT-105). Image identity is controlled: tags are immutable (a release tag always means
# the same digest) and the deploy pins the digest it pushed. Every push is scanned; the deploy workflow reads the
# findings before running the deploy document. Encrypted with the data key; no repository policy, so no principal of
# another account can reach it; never destroyed by Terraform.

resource "aws_ecr_repository" "api" {
  name                 = var.repository_name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = var.data_key_arn
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images"
        selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = var.expire_untagged_days }
        action       = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the most recent tagged images"
        selection    = { tagStatus = "tagged", tagPatternList = ["*"], countType = "imageCountMoreThan", countNumber = var.keep_tagged_images }
        action       = { type = "expire" }
      },
    ]
  })
}
