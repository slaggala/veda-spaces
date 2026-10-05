output "instance_id" {
  description = "The host."
  value       = aws_instance.host.id
}

output "data_volume_id" {
  description = "The data volume (/var/lib/veda)."
  value       = aws_ebs_volume.data.id
}

output "ami_id" {
  description = "The AMI planned (record it in staging-platform.json compute.ami_id after the first plan)."
  value       = local.ami_id
}
