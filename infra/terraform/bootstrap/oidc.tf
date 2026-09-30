# GitHub Actions OIDC: after bootstrap no workflow holds long-lived AWS keys. AWS validates the GitHub
# issuer against its own trusted CA list, so no thumbprint is pinned.
resource "aws_iam_openid_connect_provider" "github" {
  count = var.existing_github_oidc_provider_arn == "" ? 1 : 0

  url            = "https://${local.oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
}

# One trust policy per role: the exact repository AND the exact GitHub environment. Branch, pull-request
# and fork tokens carry a different subject and are refused.
data "aws_iam_policy_document" "github_trust" {
  for_each = var.github_environments

  statement {
    sid     = "GitHubEnvironment${title(each.key)}"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["repo:${var.github_owner}/${var.github_repo}:environment:${each.value}"]
    }
  }
}
