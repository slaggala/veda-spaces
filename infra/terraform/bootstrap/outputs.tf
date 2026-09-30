output "account_id" {
  value = local.account_id
}

output "region" {
  value = local.region
}

output "state_bucket" {
  value = aws_s3_bucket.state.bucket
}

output "state_kms_key_arn" {
  value = aws_kms_key.state.arn
}

output "github_oidc_provider_arn" {
  value = local.oidc_provider_arn
}

output "permissions_boundary_arn" {
  value = aws_iam_policy.boundary.arn
}

output "github_role_arns" {
  description = "Role ARN per purpose; infra/scripts/github-setup.sh stores each as AWS_ROLE_ARN in its environment."
  value       = { for k, r in aws_iam_role.github : k => r.arn }
}

output "github_environments" {
  value = var.github_environments
}

# Consumed by later stacks as -backend-config (AUT-301): same bucket and key, one state key per stack.
output "backend_config" {
  value = {
    bucket       = aws_s3_bucket.state.bucket
    region       = local.region
    encrypt      = true
    kms_key_id   = aws_kms_key.state.arn
    use_lockfile = true
    keys = {
      bootstrap = "bootstrap/terraform.tfstate"
      core      = "staging/core.tfstate"
      edge      = "staging/edge.tfstate"
    }
  }
}

# Rendered policies, for review and for the offline policy evaluator in tests/ (no secrets).
output "policy_documents" {
  description = "Boundary, role and state-bucket policy JSON exactly as applied."
  value = {
    boundary       = data.aws_iam_policy_document.boundary.json
    plan           = data.aws_iam_policy_document.plan.json
    apply_services = data.aws_iam_policy_document.apply_services.json
    apply_iam      = data.aws_iam_policy_document.apply_iam.json
    deploy         = data.aws_iam_policy_document.deploy.json
    evidence       = data.aws_iam_policy_document.evidence.json
    state_bucket   = data.aws_iam_policy_document.state_bucket.json
  }
}
