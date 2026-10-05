output "topic_arn" {
  description = "The alarm topic."
  value       = local.topic_arn
}

output "app_log_group" {
  description = "Application container logs (Docker awslogs)."
  value       = aws_cloudwatch_log_group.this["app"].name
}

output "host_log_group" {
  description = "Host system and deploy logs (CloudWatch agent)."
  value       = aws_cloudwatch_log_group.this["host"].name
}

output "agent_config_parameter" {
  description = "SSM parameter holding the CloudWatch agent configuration."
  value       = aws_ssm_parameter.agent_config.name
}

output "alarm_names" {
  description = "Every alarm."
  value       = sort(concat([for a in aws_cloudwatch_metric_alarm.app : a.alarm_name], [aws_cloudwatch_metric_alarm.trail_delivery.alarm_name], [for a in aws_cloudwatch_metric_alarm.host : a.alarm_name]))
}

output "custom_metric_count" {
  description = "Billed custom metrics this monitoring creates (cost report): the log filters, the tampering metric, the agent's memory and two disks, and the health metric."
  value       = length(local.filters) + 1 + (var.host_alarms_enabled ? 4 : 0)
}
