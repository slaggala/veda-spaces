output "data_key_arn" {
  description = "Data key: MFA secrets (VEDA_KMS_KEY_ARN), EBS, data buckets, ECR."
  value       = aws_kms_key.this["data"].arn
}

output "audit_key_arn" {
  description = "Audit key: CloudTrail, logs and evidence buckets, CloudWatch Logs, the alarm topic."
  value       = aws_kms_key.this["audit"].arn
}

output "aliases" {
  description = "Key aliases."
  value       = { for k, a in aws_kms_alias.this : k => a.name }
}
