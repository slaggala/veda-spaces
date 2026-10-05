# Offline tests of the staging keys (AUT-102). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  name_prefix          = "veda-stg"
  account_id           = "111122223333"
  region               = "ap-south-1"
  log_group_prefix     = "/veda/staging"
  trail_name           = "veda-stg-trail"
  deletion_window_days = 30
  rotation_period_days = 365
}

run "two_symmetric_single_region_keys_with_rotation" {
  command = plan

  assert {
    condition     = length(aws_kms_key.this) == 2 && alltrue([for k in aws_kms_key.this : k.enable_key_rotation && k.rotation_period_in_days == 365 && k.deletion_window_in_days == 30])
    error_message = "two keys, yearly rotation, 30-day deletion window"
  }

  assert {
    condition     = alltrue([for k in aws_kms_key.this : k.multi_region == false && k.key_usage == "ENCRYPT_DECRYPT" && k.customer_master_key_spec == "SYMMETRIC_DEFAULT"])
    error_message = "symmetric, single-region keys only"
  }

  assert {
    condition     = aws_kms_alias.this["data"].name == "alias/veda-stg-data" && aws_kms_alias.this["audit"].name == "alias/veda-stg-audit"
    error_message = "aliases are alias/veda-stg-*"
  }
}

run "no_caller_outside_the_account" {
  command = plan

  assert {
    condition = alltrue([for k in aws_kms_key.this : anytrue([for s in jsondecode(k.policy).Statement :
      s.Effect == "Deny" && s.Action == "kms:*" && try(s.Condition.StringNotEquals["kms:CallerAccount"], "") == "111122223333"
    ])])
    error_message = "each key refuses callers of another account"
  }

  assert {
    condition     = length(jsondecode(aws_kms_key.this["data"].policy).Statement) == 2
    error_message = "the data key admits no AWS service directly (EBS, S3 and ECR use it through IAM callers)"
  }
}

run "audit_key_services_bound_to_this_account_and_resources" {
  command = plan

  assert {
    condition = alltrue([for s in jsondecode(aws_kms_key.this["audit"].policy).Statement :
      try(s.Principal.Service, null) == null || length(try(s.Condition, {})) > 0
    ])
    error_message = "every service statement of the audit key carries a condition"
  }

  assert {
    condition = one([for s in jsondecode(aws_kms_key.this["audit"].policy).Statement : s.Condition.ArnLike["kms:EncryptionContext:aws:logs:arn"]
    if try(s.Principal.Service, "") == "logs.ap-south-1.amazonaws.com"]) == "arn:aws:logs:ap-south-1:111122223333:log-group:/veda/staging/*"
    error_message = "CloudWatch Logs may use the audit key for /veda/staging/* only"
  }

  assert {
    condition = one([for s in jsondecode(aws_kms_key.this["audit"].policy).Statement : s.Condition.StringEquals["aws:SourceArn"]
    if try(s.Principal.Service, "") == "cloudtrail.amazonaws.com"]) == "arn:aws:cloudtrail:ap-south-1:111122223333:trail/veda-stg-trail"
    error_message = "CloudTrail may use the audit key for the Veda trail only"
  }
}

run "short_deletion_window_refused" {
  command = plan

  variables {
    deletion_window_days = 7
  }

  expect_failures = [var.deletion_window_days]
}
