output "trail_arn" {
  description = "The trail."
  value       = local.trail_arn
}

output "log_group_name" {
  description = "The trail's CloudWatch Logs copy (delivery alarm: AWS/Logs IncomingLogEvents)."
  value       = aws_cloudwatch_log_group.trail.name
}

output "tampering_metric" {
  description = "Namespace and name of the tampering metric (alarm in AUT-110)."
  value       = { namespace = "Veda/Audit", name = "AuditTampering" }
}
