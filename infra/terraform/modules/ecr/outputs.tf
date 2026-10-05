output "repository_name" {
  description = "Repository name."
  value       = aws_ecr_repository.api.name
}

output "repository_arn" {
  description = "Repository ARN (host pull permission, AUT-106)."
  value       = aws_ecr_repository.api.arn
}

output "repository_url" {
  description = "Registry URL of the repository (the deploy pulls by digest)."
  value       = aws_ecr_repository.api.repository_url
}
