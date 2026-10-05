# Offline tests of the image repository (AUT-105). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  repository_name      = "veda-api"
  data_key_arn         = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-00000000da7a"
  keep_tagged_images   = 30
  expire_untagged_days = 7
}

run "immutable_scanned_encrypted" {
  command = plan

  assert {
    condition     = aws_ecr_repository.api.image_tag_mutability == "IMMUTABLE" && aws_ecr_repository.api.force_delete == false
    error_message = "immutable tags; never force-deleted"
  }

  assert {
    condition     = one(aws_ecr_repository.api.image_scanning_configuration).scan_on_push
    error_message = "every push is scanned"
  }

  assert {
    condition     = one(aws_ecr_repository.api.encryption_configuration).encryption_type == "KMS" && one(aws_ecr_repository.api.encryption_configuration).kms_key == var.data_key_arn
    error_message = "encrypted with the data key"
  }
}

run "lifecycle_keeps_history_and_expires_untagged" {
  command = plan

  assert {
    condition = (
      jsondecode(aws_ecr_lifecycle_policy.api.policy).rules[0].selection.tagStatus == "untagged" &&
      jsondecode(aws_ecr_lifecycle_policy.api.policy).rules[0].selection.countNumber == 7 &&
      jsondecode(aws_ecr_lifecycle_policy.api.policy).rules[1].selection.countNumber == 30
    )
    error_message = "untagged images expire after 7 days; the last 30 tagged images are kept"
  }
}

run "another_repository_name_refused" {
  command = plan

  variables {
    repository_name = "veda-other"
  }

  expect_failures = [var.repository_name]
}

run "too_short_history_refused" {
  command = plan

  variables {
    keep_tagged_images = 2
  }

  expect_failures = [var.keep_tagged_images]
}
