output "deploy_document" {
  description = "The deploy document."
  value       = aws_ssm_document.deploy.name
}
