output "bucket_names" {
  description = "Bucket names by purpose."
  value       = { for k, b in aws_s3_bucket.this : k => b.bucket }
}

output "bucket_arns" {
  description = "Bucket ARNs by purpose."
  value       = { for k, b in local.buckets : k => "arn:aws:s3:::${b.name}" }
}

output "flow_log_destination_arn" {
  description = "Where the VPC flow logs are delivered (C3): the logs bucket, prefix vpc-flow/."
  value       = "arn:aws:s3:::${local.buckets.logs.name}/vpc-flow"
}
