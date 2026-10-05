output "config_parameter_names" {
  description = "Configuration parameters written by Terraform."
  value       = sort([for p in aws_ssm_parameter.config : p.name])
}

output "owner_seeded_secrets" {
  description = "SecureString parameters the owner seeds under /veda/staging/app (AUT-302); never in Terraform or Git."
  value = [for n in [
    "VEDA_JWT_PRIVATE_KEY_PEM", "VEDA_JWT_KID", "VEDA_CHAIN_KEY", "VEDA_CHAIN_KEY_LABEL", "VEDA_RECOVERY_CODE_HMAC_KEY",
    "VEDA_EMAIL_HASH_HMAC_KEY", "VEDA_ACTION_TOKEN_KEY", "VEDA_TURNSTILE_SECRET",
  ] : "${var.parameter_path}/app/${n}"]
}

output "session_log_group" {
  description = "Session Manager transcripts."
  value       = aws_cloudwatch_log_group.sessions.name
}
