output "collect_document" {
  description = "The evidence collector."
  value       = aws_ssm_document.collect.name
}

output "deploy_document" {
  description = "The deploy document."
  value       = aws_ssm_document.deploy.name
}
