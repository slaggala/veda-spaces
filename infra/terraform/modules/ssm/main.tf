# Host-management foundation (AUT-107). Two things only:
#   1. Non-secret configuration under /veda/staging/config/<NAME> (String, standard tier): the host renders it, with
#      the owner-seeded secrets of /veda/staging/app/<NAME> (SecureString, AUT-302, never Terraform), into
#      /etc/veda/api.env. The plan guard refuses any SecureString and any parameter outside config/.
#   2. Session Manager preferences: every session transcript goes to an encrypted log group, session data is encrypted
#      with the data key, sessions end when idle and after a maximum duration, and no session runs as root by default.

resource "aws_ssm_parameter" "config" {
  #checkov:skip=CKV2_AWS_34:Non-secret configuration by design (plain String); secrets are SecureStrings seeded by the owner under /veda/staging/app, and the plan guard refuses SecureString here
  for_each = var.config

  name        = "${var.parameter_path}/config/${each.key}"
  description = "Veda staging configuration (non-secret, AUT-107)"
  type        = "String"
  tier        = "Standard"
  value       = each.value
}

resource "aws_cloudwatch_log_group" "sessions" {
  name              = var.session_log_group
  retention_in_days = var.session_log_retention_days
  kms_key_id        = var.audit_key_arn
}

# The account's Session Manager preferences document (its name is fixed by AWS).
resource "aws_ssm_document" "session_preferences" {
  name            = "SSM-SessionManagerRunShell"
  document_type   = "Session"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "1.0"
    description   = "Veda staging Session Manager preferences (AUT-107)"
    sessionType   = "Standard_Stream"
    inputs = {
      s3BucketName                = ""
      s3EncryptionEnabled         = true
      cloudWatchLogGroupName      = aws_cloudwatch_log_group.sessions.name
      cloudWatchEncryptionEnabled = true
      cloudWatchStreamingEnabled  = true
      kmsKeyId                    = var.session_key_alias
      runAsEnabled                = false
      runAsDefaultUser            = ""
      idleSessionTimeout          = tostring(var.idle_session_timeout_minutes)
      maxSessionDuration          = tostring(var.max_session_duration_minutes)
      shellProfile                = { linux = "cd ~ && exec bash -l", windows = "" }
    }
  })
}
