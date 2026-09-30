# Permissions boundary for every veda-* role, including the GitHub roles and every workload role later
# stacks create. A boundary never grants: it caps. It is self-propagating (F1): a role under it can create or
# re-bound a role only with this same boundary, and can write IAM only on veda-* roles, policies and instance
# profiles, so no chain of created roles ever ends outside it.
#
# What it removes, whatever an identity policy says:
#   - any region other than ap-south-1 (global services excepted);
#   - roles without this boundary, IAM writes outside veda-*, the privileged AWS managed policies;
#   - IAM users, access keys, identity providers, Organizations and account settings;
#   - changes to this boundary, to the GitHub roles and to the OIDC provider (bootstrap-owned);
#   - IAM roles, policies and instance profiles under a path, which name patterns cannot bound (RR-03);
#   - creating a role or changing a trust policy by any role but veda-gh-apply (RR-03);
#   - using a web-identity (OIDC) session of any role but the veda-gh-* roles (RR-03). SAML sessions are NOT covered:
#     AWS sets aws:FederatedProvider for OIDC sessions only (N-01). SAML is closed outside the boundary instead: no
#     Veda role can create a SAML provider, and discovery refuses an account that has one;
#   - any S3 action on bootstrap state, and any change or replication into the state bucket (F2, RR-01). The state
#     key is protected by its own key policy (RR-02), not here;
#   - weakening the account guardrails, CloudTrail or Access Analyzer, IMDSv1, GOVERNANCE bypass (F6);
#   - sharing snapshots/AMIs, KMS grants, S3 writes and Lambda access across accounts (F7).
# The IAM action patterns below are written to fit the 6,144-character managed-policy limit (asserted in tests).

locals {
  veda_iam_arns = [
    "arn:${local.partition}:iam::${local.account_id}:role/${local.prefix}-*",
    "arn:${local.partition}:iam::${local.account_id}:policy/${local.prefix}-*",
    "arn:${local.partition}:iam::${local.account_id}:instance-profile/${local.prefix}-*",
    # Service-linked roles: only AWS can change their trust or policies.
    "arn:${local.partition}:iam::${local.account_id}:role/aws-service-role/*",
  ]
}

data "aws_iam_policy_document" "boundary" {
  #checkov:skip=CKV_AWS_1:A permissions boundary only caps: Allow * is the ceiling and the explicit Deny statements are the control
  #checkov:skip=CKV_AWS_49:A permissions boundary only caps: Allow * is the ceiling and the explicit Deny statements are the control
  #checkov:skip=CKV_AWS_107:A permissions boundary only caps: Allow * is the ceiling and the explicit Deny statements are the control
  #checkov:skip=CKV_AWS_108:A permissions boundary only caps: Allow * is the ceiling and the explicit Deny statements are the control
  #checkov:skip=CKV_AWS_109:A permissions boundary only caps: Allow * is the ceiling and the explicit Deny statements are the control
  #checkov:skip=CKV_AWS_110:A permissions boundary only caps: Allow * is the ceiling and the explicit Deny statements are the control
  #checkov:skip=CKV_AWS_111:A permissions boundary only caps: Allow * is the ceiling and the explicit Deny statements are the control
  #checkov:skip=CKV_AWS_356:A permissions boundary only caps: Allow * is the ceiling and the explicit Deny statements are the control
  statement {
    sid       = "AllowWithinBoundary"
    actions   = ["*"]
    resources = ["*"]
  }

  statement {
    sid         = "DenyOutsideApprovedRegion"
    effect      = "Deny"
    not_actions = local.global_actions
    resources   = ["*"]
    condition {
      test     = "StringNotEquals"
      variable = "aws:RequestedRegion"
      values   = [local.region]
    }
  }

  # F1: a role may only be created or re-bounded with this boundary, whoever creates it.
  statement {
    sid       = "DenyRoleWithoutBoundary"
    effect    = "Deny"
    actions   = ["iam:CreateRole", "iam:PutRolePermissionsBoundary"]
    resources = ["*"]
    condition {
      test     = "StringNotEquals"
      variable = "iam:PermissionsBoundary"
      values   = [local.boundary_arn]
    }
  }

  # RR-03: only veda-gh-apply sets trust. A role created by any other bounded role (a workload role, or one that
  # was given *:*) can neither create a role nor re-trust one, so no trust policy is written outside the reviewed,
  # guarded apply (check-plan.sh). IAM has no condition key for trust content; this limits who can write it.
  statement {
    sid       = "DenyTrustWritesExceptApplyRole"
    effect    = "Deny"
    actions   = ["iam:CreateRole", "iam:UpdateAssumeRolePolicy"]
    resources = ["*"]
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = [local.apply_role_arn]
    }
  }

  # RR-03: a web-identity (OIDC) session is usable only as a veda-gh-* role. Even a trust policy that let GitHub, or
  # any other OIDC provider, into a workload role yields a session that can do nothing. aws:FederatedProvider is
  # absent from SAML sessions, so this statement does not see them (N-01; see the header).
  statement {
    sid       = "DenyFederatedSessionsOutsideGitHubRoles"
    effect    = "Deny"
    actions   = ["*"]
    resources = ["*"]
    condition {
      test     = "Null"
      variable = "aws:FederatedProvider"
      values   = ["false"]
    }
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = [for n in values(local.role_names) : "arn:${local.partition}:iam::${local.account_id}:role/${n}"]
    }
  }

  # F1: IAM writes only on veda-* roles, policies and instance profiles. Everything else (users, groups,
  # OrganizationAccountAccessRole, SSO roles, identity providers, account settings) is out of reach.
  statement {
    sid    = "DenyIamWritesOutsideVeda"
    effect = "Deny"
    actions = [
      "iam:Add*", "iam:Attach*", "iam:Change*", "iam:Create*", "iam:Deactivate*", "iam:Delete*", "iam:Detach*",
      "iam:Enable*", "iam:PassRole", "iam:Put*", "iam:Remove*", "iam:Reset*", "iam:Resync*", "iam:Set*",
      "iam:Tag*", "iam:Untag*", "iam:Update*", "iam:Upload*",
    ]
    not_resources = local.veda_iam_arns
  }

  # RR-03: "*" in role/veda-* also matches "/", so role/veda-x/admin (path /veda-x/, name admin) would pass the
  # statement above. Nothing under a path is created, passed or changed; Veda identities live at "/" only.
  statement {
    sid     = "DenyIamPaths"
    effect  = "Deny"
    actions = ["iam:Add*", "iam:Attach*", "iam:Create*", "iam:PassRole", "iam:Put*", "iam:Update*"]
    resources = [
      "arn:${local.partition}:iam::${local.account_id}:role/${local.prefix}-*/*",
      "arn:${local.partition}:iam::${local.account_id}:policy/${local.prefix}-*/*",
      "arn:${local.partition}:iam::${local.account_id}:instance-profile/${local.prefix}-*/*",
    ]
  }

  # Users, keys, identity providers and account settings are already outside veda-* above; these are named
  # again so they stay denied if the veda-* list ever changes, plus the two that act on veda-* resources.
  statement {
    sid    = "DenyIdentityAndAccountAdministration"
    effect = "Deny"
    actions = [
      "iam:CreateUser", "iam:CreateAccessKey", "iam:CreateLoginProfile", "iam:CreateOpenIDConnectProvider",
      "iam:DeleteOpenIDConnectProvider", "iam:CreateSAMLProvider", "iam:DeleteRolePermissionsBoundary",
      "iam:DeleteServiceLinkedRole", "organizations:*", "account:Put*", "account:Delete*", "account:Enable*",
      "account:Disable*", "account:Accept*", "account:Close*", "account:Start*",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "DenyPrivilegedManagedPolicies"
    effect    = "Deny"
    actions   = ["iam:AttachRolePolicy"]
    resources = ["*"]
    condition {
      test     = "ArnLike"
      variable = "iam:PolicyARN"
      values = [
        "arn:${local.partition}:iam::aws:policy/AdministratorAccess*",
        "arn:${local.partition}:iam::aws:policy/PowerUserAccess",
        "arn:${local.partition}:iam::aws:policy/IAMFullAccess",
        "arn:${local.partition}:iam::aws:policy/AWSOrganizationsFullAccess",
        "arn:${local.partition}:iam::aws:policy/job-function/*",
      ]
    }
  }

  # Bootstrap-owned identities (writes only; reads stay available to SecurityAudit). CreateRole/CreatePolicy stop
  # a later stack squatting a veda-gh-* name (the plan guard lets only veda-gh-* roles trust GitHub); PassRole
  # stops handing a GitHub role to a service.
  statement {
    sid    = "DenyBootstrapIdentityTampering"
    effect = "Deny"
    actions = [
      "iam:CreateRole", "iam:DeleteRole*", "iam:UpdateRole*", "iam:UpdateAssumeRolePolicy", "iam:PutRole*",
      "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:TagRole", "iam:UntagRole", "iam:PassRole",
      "iam:CreatePolicy*", "iam:DeletePolicy*", "iam:SetDefaultPolicyVersion", "iam:TagPolicy", "iam:UntagPolicy",
    ]
    resources = [
      local.boundary_arn,
      "arn:${local.partition}:iam::${local.account_id}:role/${local.prefix}-gh-*",
      "arn:${local.partition}:iam::${local.account_id}:policy/${local.prefix}-gh-*",
    ]
  }

  # F2, RR-01: bootstrap state is the owner's alone (read, copy, write, replicate, restore, tag, delete), and no role
  # changes the bucket's configuration or replicates into it. The bucket policy refuses the same to every non-owner.
  statement {
    sid       = "DenyBootstrapState"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = ["${local.state_bucket_arn}/bootstrap/*"]
  }

  statement {
    sid    = "DenyStateTampering"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket*", "s3:PutBucket*", "s3:Put*Configuration", "s3:PutObjectAcl", "s3:PutObjectVersionAcl",
      "s3:PutObjectRetention", "s3:PutObjectLegalHold", "s3:DeleteObjectVersion*", "s3:BypassGovernanceRetention",
      "s3:Replicate*", "s3:ObjectOwnerOverrideToBucketOwner",
    ]
    resources = [local.state_bucket_arn, "${local.state_bucket_arn}/*"]
  }

  # F6. CloudTrail: trails can be created and started, never stopped, deleted or re-scoped by a role, so the
  # AUT-104 trail's event selectors are set at creation or by the owner session. Access Analyzer findings
  # cannot be archived. Object Lock configuration stays allowed: creating the lock buckets needs it (AUT-103).
  statement {
    sid    = "DenyGuardrailAndAuditWeakening"
    effect = "Deny"
    actions = [
      "s3:PutAccountPublicAccessBlock", "s3:DeleteAccountPublicAccessBlock",
      "ec2:DisableEbsEncryptionByDefault", "ec2:DisableSnapshotBlockPublicAccess",
      "ec2:EnableSnapshotBlockPublicAccess", "ec2:DisableImageBlockPublicAccess",
      "ec2:ModifyInstanceMetadataDefaults",
      "cloudtrail:StopLogging", "cloudtrail:DeleteTrail", "cloudtrail:UpdateTrail", "cloudtrail:Put*Selectors",
      "cloudtrail:RemoveTags", "cloudtrail:DeleteEventDataStore", "cloudtrail:UpdateEventDataStore",
      "cloudtrail:StopEventDataStoreIngestion", "access-analyzer:DeleteAnalyzer", "access-analyzer:CreateArchiveRule",
      "access-analyzer:UpdateArchiveRule", "access-analyzer:ApplyArchiveRule", "access-analyzer:UpdateFindings",
      "s3:BypassGovernanceRetention",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "DenyImdsV1"
    effect    = "Deny"
    actions   = ["ec2:RunInstances", "ec2:ModifyInstanceMetadataOptions"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "ec2:MetadataHttpTokens"
      values   = ["optional"]
    }
  }

  # F7: nothing leaves the account through sharing or grants.
  statement {
    sid       = "DenyCrossAccountSharing"
    effect    = "Deny"
    actions   = ["ec2:ModifySnapshotAttribute", "ec2:ModifyImageAttribute", "ec2:ModifyFpgaImageAttribute"]
    resources = ["*"]
  }

  statement {
    sid       = "DenyExternalKmsGrants"
    effect    = "Deny"
    actions   = ["kms:CreateGrant"]
    resources = ["*"]
    condition {
      test     = "Bool"
      variable = "kms:GrantIsForAWSResource"
      values   = ["false"]
    }
    condition {
      test     = "StringNotLike"
      variable = "kms:GranteePrincipal"
      values   = ["arn:${local.partition}:iam::${local.account_id}:*", "arn:${local.partition}:sts::${local.account_id}:*"]
    }
  }

  statement {
    sid       = "DenyWritesToOtherAccounts"
    effect    = "Deny"
    actions   = ["s3:PutObject", "s3:ReplicateObject"]
    resources = ["*"]
    condition {
      test     = "StringNotEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }

  statement {
    sid       = "DenyExternalLambdaAccess"
    effect    = "Deny"
    actions   = ["lambda:AddPermission", "lambda:AddLayerVersionPermission"]
    resources = ["*"]
    condition {
      test     = "StringNotLike"
      variable = "lambda:Principal"
      values   = [local.account_id, "arn:${local.partition}:iam::${local.account_id}:*", "*.amazonaws.com"]
    }
  }

  statement {
    sid       = "DenyPublicFunctionUrls"
    effect    = "Deny"
    actions   = ["lambda:CreateFunctionUrlConfig", "lambda:UpdateFunctionUrlConfig"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "lambda:FunctionUrlAuthType"
      values   = ["NONE"]
    }
  }
}

resource "aws_iam_policy" "boundary" {
  name        = local.boundary_name
  description = "Permissions boundary for every Veda staging role (AUT-002)."
  policy      = data.aws_iam_policy_document.boundary.json
}
