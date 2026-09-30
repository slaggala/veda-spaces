# Permissions boundary for every veda-* role, including the GitHub roles and every workload role later
# stacks create (the apply role can only create roles that carry it). A boundary never grants: it caps.
# What it removes, whatever an identity policy says:
#   - any region other than ap-south-1 (global services excepted);
#   - IAM users, access keys, identity providers, Organizations and account settings;
#   - changes to this boundary, to the GitHub roles and to the OIDC provider (bootstrap-owned);
#   - weakening the state bucket/key, the account guardrails or CloudTrail logging, or bypassing GOVERNANCE
#     Object Lock retention (COMPLIANCE retention cannot be bypassed by anyone).

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

  statement {
    sid    = "DenyIdentityAndAccountAdministration"
    effect = "Deny"
    actions = [
      "iam:CreateUser", "iam:CreateAccessKey", "iam:CreateLoginProfile", "iam:UpdateLoginProfile",
      "iam:CreateServiceSpecificCredential", "iam:UploadSSHPublicKey", "iam:CreateVirtualMFADevice",
      "iam:CreateSAMLProvider", "iam:UpdateSAMLProvider", "iam:DeleteSAMLProvider",
      "iam:CreateOpenIDConnectProvider", "iam:DeleteOpenIDConnectProvider",
      "iam:UpdateOpenIDConnectProviderThumbprint", "iam:AddClientIDToOpenIDConnectProvider",
      "iam:RemoveClientIDFromOpenIDConnectProvider", "iam:TagOpenIDConnectProvider",
      "iam:UntagOpenIDConnectProvider", "iam:UpdateAccountPasswordPolicy", "iam:DeleteAccountPasswordPolicy",
      "iam:CreateAccountAlias", "iam:DeleteAccountAlias",
      "iam:DeleteRolePermissionsBoundary", "iam:DeleteUserPermissionsBoundary",
      "organizations:*", "account:Put*", "account:Delete*", "account:Enable*", "account:Disable*",
      "account:Accept*", "account:Close*", "account:Start*",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DenyBootstrapIdentityTampering"
    effect = "Deny"
    actions = [
      "iam:CreatePolicyVersion", "iam:DeletePolicy", "iam:DeletePolicyVersion", "iam:SetDefaultPolicyVersion",
      "iam:TagPolicy", "iam:UntagPolicy",
      "iam:DeleteRole", "iam:UpdateRole", "iam:UpdateAssumeRolePolicy", "iam:UpdateRoleDescription",
      "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:AttachRolePolicy", "iam:DetachRolePolicy",
      "iam:PutRolePermissionsBoundary", "iam:TagRole", "iam:UntagRole",
    ]
    resources = [
      local.boundary_arn,
      "arn:${local.partition}:iam::${local.account_id}:role/${local.prefix}-gh-*",
      "arn:${local.partition}:iam::${local.account_id}:policy/${local.prefix}-gh-*",
    ]
  }

  statement {
    sid    = "DenyStateTampering"
    effect = "Deny"
    actions = [
      "s3:DeleteBucket", "s3:PutBucketPolicy", "s3:DeleteBucketPolicy", "s3:PutBucketVersioning",
      "s3:PutEncryptionConfiguration", "s3:PutLifecycleConfiguration", "s3:PutBucketPublicAccessBlock",
      "s3:PutBucketOwnershipControls", "s3:PutBucketAcl", "s3:DeleteObjectVersion",
    ]
    resources = [
      "arn:${local.partition}:s3:::${local.state_bucket_name}",
      "arn:${local.partition}:s3:::${local.state_bucket_name}/*",
    ]
  }

  statement {
    sid    = "DenyStateKeyTampering"
    effect = "Deny"
    actions = [
      "kms:ScheduleKeyDeletion", "kms:DisableKey", "kms:PutKeyPolicy", "kms:DisableKeyRotation",
      "kms:CreateGrant",
    ]
    # Matched by alias rather than key ARN so the boundary is fully known at plan time.
    resources = ["*"]
    condition {
      test     = "ForAnyValue:StringEquals"
      variable = "kms:ResourceAliases"
      values   = [local.state_kms_alias]
    }
  }

  statement {
    sid       = "DenyStateAliasTampering"
    effect    = "Deny"
    actions   = ["kms:DeleteAlias", "kms:UpdateAlias", "kms:CreateAlias"]
    resources = ["arn:${local.partition}:kms:${local.region}:${local.account_id}:${local.state_kms_alias}"]
  }

  statement {
    sid    = "DenyGuardrailAndAuditWeakening"
    effect = "Deny"
    actions = [
      "s3:PutAccountPublicAccessBlock", "s3:DeleteAccountPublicAccessBlock",
      "ec2:DisableEbsEncryptionByDefault", "ec2:DisableSnapshotBlockPublicAccess",
      "ec2:DisableImageBlockPublicAccess", "ec2:ModifyInstanceMetadataDefaults",
      "access-analyzer:DeleteAnalyzer", "cloudtrail:StopLogging",
      # Object Lock *configuration* stays allowed: creating the lock buckets needs it (AUT-103), and each
      # lock bucket's own policy then refuses changes. Bypassing GOVERNANCE retention is never allowed.
      "s3:BypassGovernanceRetention",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "boundary" {
  name        = local.boundary_name
  description = "Permissions boundary for every Veda staging role (AUT-002)."
  policy      = data.aws_iam_policy_document.boundary.json
}
