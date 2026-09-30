# GitHub OIDC roles (plan §6). Each is trusted by exactly one GitHub environment, carries the boundary, and
# lives at most one hour. No role can read application data (Litestream/snapshot/anchor objects) or the
# seeded application secrets (/veda/staging/app/*): only the host role will (AUT-106).

locals {
  state_bucket_arn = "arn:${local.partition}:s3:::${local.state_bucket_name}"
  param_arn_prefix = "arn:${local.partition}:ssm:${local.region}:${local.account_id}:parameter/${local.prefix}/staging"
  instance_arns    = "arn:${local.partition}:ec2:${local.region}:${local.account_id}:instance/*"
  document_arn     = "arn:${local.partition}:ssm:${local.region}:${local.account_id}:document"
  log_group_arn    = "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/${local.prefix}/staging/*"
}

resource "aws_iam_role" "github" {
  for_each = local.role_names

  name                 = each.value
  description          = "GitHub Actions (${var.github_environments[each.key]} environment) for ${var.github_owner}/${var.github_repo}"
  assume_role_policy   = data.aws_iam_policy_document.github_trust[each.key].json
  permissions_boundary = aws_iam_policy.boundary.arn
  max_session_duration = var.role_max_session_seconds

  depends_on = [aws_iam_openid_connect_provider.github]
}

# --- shared statements ---------------------------------------------------------------------------------------

data "aws_iam_policy_document" "deny_data_reads" {
  statement {
    sid       = "DenyApplicationDataReads"
    effect    = "Deny"
    actions   = ["s3:GetObject", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:RestoreObject"]
    resources = [for p in local.data_bucket_patterns : "arn:${local.partition}:s3:::${p}/*"]
  }

  statement {
    sid       = "DenyApplicationSecretReads"
    effect    = "Deny"
    actions   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath", "ssm:GetParameterHistory"]
    resources = ["${local.param_arn_prefix}/app/*", "${local.param_arn_prefix}/app"]
  }

  statement {
    sid       = "DenySecretsManagerValues"
    effect    = "Deny"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:BatchGetSecretValue"]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "state_rw" {
  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = [local.state_bucket_arn]
  }
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject"]
    resources = ["${local.state_bucket_arn}/*"]
  }
  # Workflows write only the staging stacks' state; bootstrap/ stays writable by the owner session alone.
  statement {
    sid       = "StagingStateWrite"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.state_bucket_arn}/staging/*"]
  }
  statement {
    sid       = "StateKey"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = ["arn:${local.partition}:kms:${local.region}:${local.account_id}:key/*"]
    condition {
      test     = "ForAnyValue:StringEquals"
      variable = "kms:ResourceAliases"
      values   = [local.state_kms_alias]
    }
  }
}

data "aws_iam_policy_document" "state_read_lock" {
  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = [local.state_bucket_arn]
  }
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject"]
    resources = ["${local.state_bucket_arn}/*"]
  }
  statement {
    sid       = "StateLockFileOnly"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.state_bucket_arn}/staging/*.tflock"]
  }
  statement {
    sid       = "StateKey"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = ["arn:${local.partition}:kms:${local.region}:${local.account_id}:key/*"]
    condition {
      test     = "ForAnyValue:StringEquals"
      variable = "kms:ResourceAliases"
      values   = [local.state_kms_alias]
    }
  }
}

# --- plan: read-only view of the account plus state read and lock ------------------------------------------

data "aws_iam_policy_document" "plan" {
  source_policy_documents = [
    data.aws_iam_policy_document.state_read_lock.json,
    data.aws_iam_policy_document.deny_data_reads.json,
  ]
}

resource "aws_iam_policy" "plan" {
  name   = "${local.role_names.plan}-permissions"
  policy = data.aws_iam_policy_document.plan.json
}

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.github["plan"].name
  policy_arn = "arn:${local.partition}:iam::aws:policy/ReadOnlyAccess"
}

resource "aws_iam_role_policy_attachment" "plan" {
  role       = aws_iam_role.github["plan"].name
  policy_arn = aws_iam_policy.plan.arn
}

# --- apply: create the staging stacks (AUT-101..112, AUT-201..205 AWS side) --------------------------------

data "aws_iam_policy_document" "apply_services" {
  #checkov:skip=CKV_AWS_107:Apply role builds the staging stacks; capped by veda-boundary, gated by the staging-infra environment approval (review package §4)
  #checkov:skip=CKV_AWS_108:Apply role builds the staging stacks; capped by veda-boundary, gated by the staging-infra environment approval (review package §4)
  #checkov:skip=CKV_AWS_109:Apply role builds the staging stacks; capped by veda-boundary, gated by the staging-infra environment approval (review package §4)
  #checkov:skip=CKV_AWS_110:Apply role builds the staging stacks; capped by veda-boundary, gated by the staging-infra environment approval (review package §4)
  #checkov:skip=CKV_AWS_111:Apply role builds the staging stacks; capped by veda-boundary, gated by the staging-infra environment approval (review package §4)
  #checkov:skip=CKV_AWS_356:Apply role builds the staging stacks; capped by veda-boundary, gated by the staging-infra environment approval (review package §4)
  source_policy_documents = [
    data.aws_iam_policy_document.state_rw.json,
    data.aws_iam_policy_document.deny_data_reads.json,
  ]

  statement {
    sid = "StagingServices"
    actions = [
      "ec2:*", "kms:*", "s3:*", "cloudtrail:*", "cloudwatch:*", "logs:*", "synthetics:*", "lambda:*",
      "sns:*", "sqs:*", "ses:*", "ssm:*", "ecr:*", "dlm:*", "budgets:*", "access-analyzer:*",
      "tag:GetResources", "sts:GetCallerIdentity",
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "apply_iam" {
  #checkov:skip=CKV_AWS_356:Resource * only where the API has no resource-level permission (iam:Get*/List*, ecr:GetAuthorizationToken, ssm:GetCommandInvocation, cloudwatch reads) or where a condition key scopes it
  statement {
    sid       = "IamRead"
    actions   = ["iam:Get*", "iam:List*"]
    resources = ["*"]
  }

  statement {
    sid       = "CreateRolesOnlyWithBoundary"
    actions   = ["iam:CreateRole", "iam:PutRolePermissionsBoundary"]
    resources = ["arn:${local.partition}:iam::${local.account_id}:role/${local.prefix}-*"]
    condition {
      test     = "StringEquals"
      variable = "iam:PermissionsBoundary"
      values   = [local.boundary_arn]
    }
  }

  statement {
    sid = "ManageVedaRoles"
    actions = [
      "iam:DeleteRole", "iam:UpdateRole", "iam:UpdateAssumeRolePolicy", "iam:UpdateRoleDescription",
      "iam:TagRole", "iam:UntagRole", "iam:PutRolePolicy", "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy", "iam:DetachRolePolicy",
    ]
    resources = ["arn:${local.partition}:iam::${local.account_id}:role/${local.prefix}-*"]
  }

  statement {
    sid       = "DenyPrivilegedManagedPolicies"
    effect    = "Deny"
    actions   = ["iam:AttachRolePolicy"]
    resources = ["*"]
    condition {
      test     = "ArnEquals"
      variable = "iam:PolicyARN"
      values = [
        "arn:${local.partition}:iam::aws:policy/AdministratorAccess",
        "arn:${local.partition}:iam::aws:policy/PowerUserAccess",
        "arn:${local.partition}:iam::aws:policy/IAMFullAccess",
        "arn:${local.partition}:iam::aws:policy/AWSOrganizationsFullAccess",
      ]
    }
  }

  statement {
    sid = "ManageVedaPolicies"
    actions = [
      "iam:CreatePolicy", "iam:DeletePolicy", "iam:CreatePolicyVersion", "iam:DeletePolicyVersion",
      "iam:SetDefaultPolicyVersion", "iam:TagPolicy", "iam:UntagPolicy",
    ]
    resources = ["arn:${local.partition}:iam::${local.account_id}:policy/${local.prefix}-*"]
  }

  statement {
    sid = "ManageVedaInstanceProfiles"
    actions = [
      "iam:CreateInstanceProfile", "iam:DeleteInstanceProfile", "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile", "iam:TagInstanceProfile", "iam:UntagInstanceProfile",
    ]
    resources = ["arn:${local.partition}:iam::${local.account_id}:instance-profile/${local.prefix}-*"]
  }

  statement {
    sid       = "PassVedaRolesToStagingServices"
    actions   = ["iam:PassRole"]
    resources = ["arn:${local.partition}:iam::${local.account_id}:role/${local.prefix}-*"]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values = [
        "ec2.amazonaws.com", "lambda.amazonaws.com", "cloudtrail.amazonaws.com", "dlm.amazonaws.com",
        "ssm.amazonaws.com", "synthetics.amazonaws.com",
      ]
    }
  }

  statement {
    sid       = "ServiceLinkedRoles"
    actions   = ["iam:CreateServiceLinkedRole"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values = [
        "access-analyzer.amazonaws.com", "ssm.amazonaws.com", "ecr.amazonaws.com", "ses.amazonaws.com",
      ]
    }
  }
}

resource "aws_iam_policy" "apply_services" {
  name   = "${local.role_names.apply}-services"
  policy = data.aws_iam_policy_document.apply_services.json
}

resource "aws_iam_policy" "apply_iam" {
  name   = "${local.role_names.apply}-iam"
  policy = data.aws_iam_policy_document.apply_iam.json
}

resource "aws_iam_role_policy_attachment" "apply_services" {
  role       = aws_iam_role.github["apply"].name
  policy_arn = aws_iam_policy.apply_services.arn
}

resource "aws_iam_role_policy_attachment" "apply_iam" {
  role       = aws_iam_role.github["apply"].name
  policy_arn = aws_iam_policy.apply_iam.arn
}

# --- deploy: push the image, publish the deploy bundle, run the veda-* SSM documents on the staging host -----

data "aws_iam_policy_document" "deploy" {
  #checkov:skip=CKV_AWS_356:Resource * only where the API has no resource-level permission (iam:Get*/List*, ecr:GetAuthorizationToken, ssm:GetCommandInvocation, cloudwatch reads) or where a condition key scopes it
  source_policy_documents = [data.aws_iam_policy_document.deny_data_reads.json]

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "EcrPushVedaApi"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
      "ecr:DescribeImages", "ecr:DescribeImageScanFindings",
    ]
    resources = ["arn:${local.partition}:ecr:${local.region}:${local.account_id}:repository/${local.ecr_repository}"]
  }

  statement {
    sid       = "ArtifactsBundle"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["arn:${local.partition}:s3:::${local.artifacts_bucket_name}/*"]
  }

  statement {
    sid       = "ArtifactsList"
    actions   = ["s3:ListBucket"]
    resources = ["arn:${local.partition}:s3:::${local.artifacts_bucket_name}"]
  }

  statement {
    sid     = "RunVedaDocuments"
    actions = ["ssm:SendCommand"]
    resources = [
      "${local.document_arn}/${local.prefix}-deploy",
      "${local.document_arn}/${local.prefix}-drill-*",
      "${local.document_arn}/${local.prefix}-seed-fixtures",
    ]
  }

  statement {
    sid       = "OnlyOnTheStagingHost"
    actions   = ["ssm:SendCommand"]
    resources = [local.instance_arns]
    condition {
      test     = "StringEquals"
      variable = "ssm:resourceTag/project"
      values   = ["veda-spaces"]
    }
    condition {
      test     = "StringEquals"
      variable = "ssm:resourceTag/env"
      values   = ["staging"]
    }
  }

  statement {
    sid = "CommandResults"
    actions = [
      "ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "ssm:ListCommands",
      "ssm:DescribeInstanceInformation", "cloudwatch:DescribeAlarms", "cloudwatch:DescribeAlarmHistory",
      "cloudwatch:GetMetricData",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "CommandLogs"
    actions   = ["logs:GetLogEvents", "logs:FilterLogEvents", "logs:DescribeLogStreams"]
    resources = [local.log_group_arn, "${local.log_group_arn}:*"]
  }

  statement {
    sid       = "DrillAlarmState"
    actions   = ["cloudwatch:SetAlarmState"]
    resources = ["arn:${local.partition}:cloudwatch:${local.region}:${local.account_id}:alarm:${local.prefix}-stg-*"]
  }

  statement {
    sid       = "DrillAlarmCapture"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = ["arn:${local.partition}:sqs:${local.region}:${local.account_id}:${local.prefix}-stg-alarm-capture"]
  }
}

resource "aws_iam_policy" "deploy" {
  name   = "${local.role_names.deploy}-permissions"
  policy = data.aws_iam_policy_document.deploy.json
}

resource "aws_iam_role_policy_attachment" "deploy" {
  role       = aws_iam_role.github["deploy"].name
  policy_arn = aws_iam_policy.deploy.arn
}

# --- evidence: read configuration (SecurityAudit), run the collector, file hashed evidence -------------------

data "aws_iam_policy_document" "evidence" {
  #checkov:skip=CKV_AWS_356:Resource * only where the API has no resource-level permission (iam:Get*/List*, ecr:GetAuthorizationToken, ssm:GetCommandInvocation, cloudwatch reads) or where a condition key scopes it
  source_policy_documents = [data.aws_iam_policy_document.deny_data_reads.json]

  statement {
    sid       = "RunCollector"
    actions   = ["ssm:SendCommand"]
    resources = ["${local.document_arn}/${local.prefix}-collect"]
  }

  statement {
    sid       = "CollectorOnlyOnTheStagingHost"
    actions   = ["ssm:SendCommand"]
    resources = [local.instance_arns]
    condition {
      test     = "StringEquals"
      variable = "ssm:resourceTag/project"
      values   = ["veda-spaces"]
    }
    condition {
      test     = "StringEquals"
      variable = "ssm:resourceTag/env"
      values   = ["staging"]
    }
  }

  statement {
    sid = "ReadResults"
    actions = [
      "ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "cloudwatch:Describe*", "cloudwatch:Get*",
      "cloudwatch:List*",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "ReadLogs"
    actions   = ["logs:GetLogEvents", "logs:FilterLogEvents", "logs:DescribeLogStreams"]
    resources = [local.log_group_arn, "${local.log_group_arn}:*"]
  }

  statement {
    sid       = "ReadNonSecretConfig"
    actions   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
    resources = ["${local.param_arn_prefix}/config/*", "${local.param_arn_prefix}/config"]
  }

  statement {
    sid       = "FileEvidence"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["arn:${local.partition}:s3:::${local.evidence_bucket_name}/*"]
  }

  statement {
    sid       = "ListEvidence"
    actions   = ["s3:ListBucket"]
    resources = ["arn:${local.partition}:s3:::${local.evidence_bucket_name}"]
  }
}

resource "aws_iam_policy" "evidence" {
  name   = "${local.role_names.evidence}-permissions"
  policy = data.aws_iam_policy_document.evidence.json
}

resource "aws_iam_role_policy_attachment" "evidence_audit" {
  role       = aws_iam_role.github["evidence"].name
  policy_arn = "arn:${local.partition}:iam::aws:policy/SecurityAudit"
}

resource "aws_iam_role_policy_attachment" "evidence" {
  role       = aws_iam_role.github["evidence"].name
  policy_arn = aws_iam_policy.evidence.arn
}
