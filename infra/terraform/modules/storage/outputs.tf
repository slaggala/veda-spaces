output "bucket_names" {
  description = "Bucket names by purpose."
  value       = { for k, b in aws_s3_bucket.this : k => b.bucket }
}

output "bucket_arns" {
  description = "Bucket ARNs by purpose."
  value       = { for k, b in local.buckets : k => "arn:aws:s3:::${b.name}" }
}

output "flow_log_destination_arn" {
  description = "Where the VPC flow logs are delivered (C3): the logs bucket, prefix vpc-flow/. Usable only once the bucket, its delivery policy, encryption and public access block exist (review R1): whatever references this output is created after them."
  value       = "arn:aws:s3:::${local.buckets.logs.name}/vpc-flow"

  depends_on = [
    aws_s3_bucket.this["logs"],
    aws_s3_bucket_policy.this["logs"],
    aws_s3_bucket_server_side_encryption_configuration.this["logs"],
    aws_s3_bucket_public_access_block.this["logs"],
  ]
}
