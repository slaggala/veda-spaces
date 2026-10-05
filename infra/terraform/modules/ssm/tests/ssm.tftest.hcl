# Offline tests of the host-management foundation (AUT-107). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  parameter_path               = "/veda/staging"
  config                       = { VEDA_ENV = "staging", VEDA_KMS_PROVIDER = "aws", LITESTREAM_RETENTION = "168h" }
  session_log_group            = "/veda/staging/ssm-sessions"
  session_key_alias            = "alias/veda-stg-data"
  audit_key_arn                = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-0000000a0d17"
  session_log_retention_days   = 90
  idle_session_timeout_minutes = 20
  max_session_duration_minutes = 60
}

run "configuration_is_plain_text_under_config" {
  command = plan

  assert {
    condition     = alltrue([for p in aws_ssm_parameter.config : p.type == "String" && p.tier == "Standard" && startswith(p.name, "/veda/staging/config/")])
    error_message = "configuration parameters are String, standard tier, under /veda/staging/config/"
  }

  assert {
    condition     = aws_ssm_parameter.config["VEDA_ENV"].name == "/veda/staging/config/VEDA_ENV" && aws_ssm_parameter.config["VEDA_ENV"].value == "staging"
    error_message = "one parameter per environment variable"
  }
}

run "sessions_logged_encrypted_and_bounded" {
  command = plan

  assert {
    condition = (
      jsondecode(aws_ssm_document.session_preferences.content).inputs.cloudWatchLogGroupName == "/veda/staging/ssm-sessions" &&
      jsondecode(aws_ssm_document.session_preferences.content).inputs.cloudWatchEncryptionEnabled &&
      jsondecode(aws_ssm_document.session_preferences.content).inputs.kmsKeyId == "alias/veda-stg-data"
    )
    error_message = "every session transcript goes to the encrypted log group; session data is encrypted with the data key"
  }

  assert {
    condition = (
      jsondecode(aws_ssm_document.session_preferences.content).inputs.idleSessionTimeout == "20" &&
      jsondecode(aws_ssm_document.session_preferences.content).inputs.maxSessionDuration == "60" &&
      jsondecode(aws_ssm_document.session_preferences.content).inputs.runAsEnabled == false
    )
    error_message = "sessions end when idle and after an hour"
  }

  assert {
    condition     = aws_cloudwatch_log_group.sessions.kms_key_id == var.audit_key_arn && aws_cloudwatch_log_group.sessions.retention_in_days == 90
    error_message = "the transcripts are encrypted with the audit key and expire"
  }
}

run "a_secret_through_terraform_refused" {
  command = plan

  variables {
    config = { VEDA_TURNSTILE_SECRET = "x" }
  }

  expect_failures = [var.config]
}

run "a_parameter_path_outside_the_bootstrap_scope_refused" {
  command = plan

  variables {
    parameter_path = "/veda/prod"
  }

  expect_failures = [var.parameter_path]
}
