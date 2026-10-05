# GitHub OIDC roles (plan §6). Each is trusted by exactly one GitHub environment, carries the boundary, and
# lives at most one hour. The plan, deploy and evidence roles cannot read application data (Litestream,
# snapshot and anchor objects) or the seeded application secrets (/veda/staging/app/*). The apply role carries
# the same explicit denies, but it administers the staging account (SSM commands, EC2, Lambda and PassRole of
# veda-* roles), so it could reach that data through the host role: it is controlled by the staging-infra
# approval, not by these denies (review package R1).

locals {
  param_arn_prefix = "arn:${local.partition}:ssm:${local.region}:${local.account_id}:parameter/${local.prefix}/staging"
  instance_arns    = "arn:${local.partition}:ec2:${local.region}:${local.account_id}:instance/*"
  document_arn     = "arn:${local.partition}:ssm:${local.region}:${local.account_id}:document"
  log_group_arn    = "arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:/${local.prefix}/staging/*"
}

resource "aws_iam_role" "github" {
  for_each = local.role_names

  name               = each.value
  description        = "GitHub Actions (${var.github_environments[each.key]} environment) for ${var.github_owner}/${var.github_repo}"
  assume_role_policy = data.aws_iam_policy_document.github_trust[each.key].json
  # Built from the name so the plan shows it (the plan guard refuses a role whose boundary is unknown).
  permissions_boundary = local.boundary_arn
  max_session_duration = var.role_max_session_seconds

  depends_on = [aws_iam_openid_connect_provider.github, aws_iam_policy.boundary]
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

# RR-02: the state key is usable only through S3 and only for staging/* state objects, the same bounds its key
# policy enforces. Not matched by alias: the key policy, not the alias, decides.
data "aws_iam_policy_document" "state_key_use" {
  statement {
    sid       = "StateKeyViaS3ForStagingState"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = ["arn:${local.partition}:kms:${local.region}:${local.account_id}:key/*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = [local.state_s3_via_service]
    }
    condition {
      test     = "StringLike"
      variable = "kms:EncryptionContext:aws:s3:arn"
      values   = ["${local.state_bucket_arn}/staging/*"]
    }
  }
}

data "aws_iam_policy_document" "state_rw" {
  source_policy_documents = [data.aws_iam_policy_document.state_key_use.json]

  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = [local.state_bucket_arn]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject"]
    resources = ["${local.state_bucket_arn}/staging/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }
  # Workflows write only the staging stacks' state; bootstrap/ stays writable by the owner session alone.
  statement {
    sid       = "StagingStateWrite"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.state_bucket_arn}/staging/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }
}

data "aws_iam_policy_document" "state_read_lock" {
  source_policy_documents = [data.aws_iam_policy_document.state_key_use.json]

  statement {
    sid       = "StateList"
    actions   = ["s3:ListBucket"]
    resources = [local.state_bucket_arn]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }
  statement {
    sid       = "StateRead"
    actions   = ["s3:GetObject"]
    resources = ["${local.state_bucket_arn}/staging/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }
  statement {
    sid       = "StateLockFileOnly"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.state_bucket_arn}/staging/*.tflock"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }
}

# --- plan: read-only view of the account plus state read and lock ------------------------------------------

# ReadOnlyAccess is what terraform plan needs to refresh every staging resource, but it also reads data. The
# plan role runs from the staging-plan environment (reviewer required, F9) and is further denied:
#   - parameter values outside /veda/staging/config (so every SecureString, including /edge/*);
#   - object reads in every bucket except Terraform state;
#   - log contents, console output, command output and data-plane reads.
data "aws_iam_policy_document" "plan" {
  source_policy_documents = [
    data.aws_iam_policy_document.state_read_lock.json,
    data.aws_iam_policy_document.deny_data_reads.json,
  ]

  statement {
    sid     = "DenyParameterValuesOutsideConfig"
    effect  = "Deny"
    actions = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath", "ssm:GetParameterHistory"]
    not_resources = [
      "${local.param_arn_prefix}/config",
      "${local.param_arn_prefix}/config/*",
      "arn:${local.partition}:ssm:${local.region}::parameter/aws/*",
    ]
  }

  statement {
    sid           = "DenyObjectReadsOutsideState"
    effect        = "Deny"
    actions       = ["s3:GetObject", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:GetObjectTorrent"]
    not_resources = ["${local.state_bucket_arn}/*"]
  }

  statement {
    sid    = "DenyLogAndDataPlaneReads"
    effect = "Deny"
    actions = [
      "logs:GetLogEvents", "logs:FilterLogEvents", "logs:StartQuery", "logs:GetQueryResults", "logs:StartLiveTail",
      "logs:GetLogRecord", "ec2:GetConsoleOutput", "ec2:GetConsoleScreenshot", "ec2:GetPasswordData",
      "ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "dynamodb:GetItem", "dynamodb:BatchGetItem",
      "dynamodb:Query", "dynamodb:Scan", "sqs:ReceiveMessage", "kinesis:GetRecords", "athena:GetQueryResults",
    ]
    resources = ["*"]
  }
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
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }

  statement {
    sid       = "ArtifactsList"
    actions   = ["s3:ListBucket"]
    resources = ["arn:${local.partition}:s3:::${local.artifacts_bucket_name}"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
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
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
  }

  statement {
    sid       = "ListEvidence"
    actions   = ["s3:ListBucket"]
    resources = ["arn:${local.partition}:s3:::${local.evidence_bucket_name}"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [local.account_id]
    }
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
