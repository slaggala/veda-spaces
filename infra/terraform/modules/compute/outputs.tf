output "instance_id" {
  description = "The host."
  value       = aws_instance.host.id
}

output "data_volume_id" {
  description = "The data volume (/var/lib/veda)."
  value       = aws_ebs_volume.data.id
}

output "data_device" {
  description = "Device name of the data volume attachment (the deploy document mounts it)."
  value       = aws_volume_attachment.data.device_name
}

output "ami_id" {
  description = "The AMI planned (record it in staging-platform.json compute.ami_id after the first plan)."
  value       = local.ami_id
}
