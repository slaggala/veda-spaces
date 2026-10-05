output "role_name" {
  description = "Host role."
  value       = aws_iam_role.host.name
}

output "role_arn" {
  description = "Host role ARN."
  value       = aws_iam_role.host.arn
}

output "instance_profile_name" {
  description = "Instance profile for AUT-108."
  value       = aws_iam_instance_profile.host.name
}
