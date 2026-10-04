# GitHub Actions OIDC: after bootstrap no workflow holds long-lived AWS keys. AWS validates the GitHub
# issuer against its own trusted CA list, so no thumbprint is pinned.
resource "aws_iam_openid_connect_provider" "github" {
  count = var.existing_github_oidc_provider_arn == "" ? 1 : 0

  url            = "https://${local.oidc_host}"
  client_id_list = ["sts.amazonaws.com"]

  # A discovery mistake that passes our own provider in as "existing" must fail the plan, not delete the
  # provider every workflow federates through (F4).
  lifecycle {
    prevent_destroy = true
  }
}

# One trust policy per role: the exact repository AND the exact GitHub environment. Branch, pull-request
# and fork tokens carry a different subject and are refused. The subject is GitHub's immutable form, which names
# the owner and the repository by numeric ID as well (repo:<owner>@<owner id>/<repo>@<repo id>:environment:<env>), so a
# renamed, transferred or re-registered repository never matches (RR-A). The repository uses it
# (use_immutable_subject, checked by github-setup.sh --verify).
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
      values   = ["${local.oidc_subject_prefix}:environment:${each.value}"]
    }
  }
}
