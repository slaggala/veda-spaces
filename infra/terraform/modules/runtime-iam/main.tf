# Runtime identity of the staging host (AUT-106): role and instance profile veda-stg-host, bounded by veda-boundary.
# It may: be managed by SSM (AmazonSSMManagedInstanceCore); pull the application image; read and write exactly the
# buckets it serves (Litestream; locked snapshots and anchors; evidence) and read deploy bundles; use the data key
# (MFA secrets, S3, EBS) and the audit key only through S3 (evidence); write its own log groups and Veda metrics; read
# its configuration and seeded secrets; send email as the staging sender (AUT-111). It may not administer anything:
# an explicit Deny covers IAM, STS role assumption, the trail, key destruction, bucket configuration, EC2 changes, SSM
# writes and commands, image pushes, alarms and SES identities, whatever any other policy grants.
#
# D5 (anchor writer/reader separation) is not implemented: the application writes anchors with the host's own
# credentials (no VEDA_ANCHOR_WRITER_ROLE_ARN yet, critical-path C2). The bucket policy refuses unlocked writes and
# every delete, so the host can add anchors but never alter or remove one.

locals {
  b = var.bucket_arns
  # Built from names, so the whole policy is known at plan time and visible to the reviewer and the plan guard.
  keys_arn       = "arn:aws:kms:${var.region}:${var.account_id}:key/*"
  repository_arn = "arn:aws:ecr:${var.region}:${var.account_id}:repository/${var.repository_name}"
  logs_arn       = "arn:aws:logs:${var.region}:${var.account_id}:log-group:${var.log_group_prefix}/*"
  param_arn      = "arn:aws:ssm:${var.region}:${var.account_id}:parameter${var.parameter_path}"
}

resource "aws_iam_role" "host" {
  name                 = "${var.name_prefix}-host"
  description          = "Veda staging host runtime (AUT-106)"
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_instance_profile" "host" {
  name = "${var.name_prefix}-host"
  role = aws_iam_role.host.name
}

# The SSM agent: Session Manager, Run Command, inventory. Reviewed AWS managed policy (the plan guard allow-lists it).
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_policy" "runtime" {
  name        = "${var.name_prefix}-host-runtime"
  description = "Veda staging host: exact resources it serves, and an explicit deny of administration (AUT-106)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      { Sid = "EcrLogin", Effect = "Allow", Action = "ecr:GetAuthorizationToken", Resource = "*" },
      {
        Sid      = "EcrPullVedaApi"
        Effect   = "Allow"
        Action   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
        Resource = local.repository_arn
      },
      {
        Sid      = "LitestreamReplica"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${local.b.litestream}/*"
      },
      {
        Sid      = "LockedWrites"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:PutObjectRetention"]
        Resource = ["${local.b.snapshots}/*", "${local.b.anchor}/*"]
      },
      {
        # Catalog V3 media (targeted media enablement): the API stores, reads (and heads) and deletes content-hash
        # objects under source/ and variant/ only. No version deletes (old versions expire by lifecycle), no tagging,
        # no ACL, nothing else in the bucket.
        Sid      = "CatalogMediaObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["${local.b.media}/source/*", "${local.b.media}/variant/*"]
      },
      {
        Sid       = "CatalogMediaListPrefixes"
        Effect    = "Allow"
        Action    = "s3:ListBucket"
        Resource  = local.b.media
        Condition = { StringLike = { "s3:prefix" = ["source/*", "variant/*"] } }
      },
      { Sid = "DeployBundles", Effect = "Allow", Action = "s3:GetObject", Resource = "${local.b.artifacts}/*" },
      { Sid = "FileEvidence", Effect = "Allow", Action = "s3:PutObject", Resource = "${local.b.evidence}/*" },
      {
        Sid      = "ListServedBuckets"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = [local.b.litestream, local.b.snapshots, local.b.anchor, local.b.artifacts, local.b.evidence]
      },
      {
        Sid       = "DataKey"
        Effect    = "Allow"
        Action    = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
        Resource  = local.keys_arn
        Condition = { "ForAnyValue:StringEquals" = { "kms:ResourceAliases" = [var.data_key_alias] } }
      },
      {
        Sid      = "AuditKeyThroughS3Only"
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Encrypt"]
        Resource = local.keys_arn
        Condition = {
          "ForAnyValue:StringEquals" = { "kms:ResourceAliases" = [var.audit_key_alias] }
          StringEquals               = { "kms:ViaService" = "s3.${var.region}.amazonaws.com" }
        }
      },
      {
        Sid      = "OwnLogGroups"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = [local.logs_arn, "${local.logs_arn}:*"]
      },
      {
        # Session Manager checks that its transcript log group exists before streaming to it (AUT-107).
        Sid      = "FindLogGroups"
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:*"
      },
      {
        Sid       = "VedaMetrics"
        Effect    = "Allow"
        Action    = "cloudwatch:PutMetricData"
        Resource  = "*"
        Condition = { StringLike = { "cloudwatch:namespace" = ["Veda/*", "CWAgent"] } }
      },
      {
        Sid      = "ReadOwnConfiguration"
        Effect   = "Allow"
        Action   = ["ssm:GetParametersByPath", "ssm:GetParameters", "ssm:GetParameter"]
        Resource = [local.param_arn, "${local.param_arn}/*"]
      },
      {
        Sid    = "DenyAdministration"
        Effect = "Deny"
        Action = [
          "iam:*", "organizations:*", "account:*", "sts:AssumeRole", "sts:AssumeRoleWithWebIdentity", "cloudtrail:*",
          "kms:CreateKey", "kms:ScheduleKeyDeletion", "kms:DisableKey", "kms:PutKeyPolicy", "kms:CreateGrant", "kms:RetireGrant",
          "s3:PutBucket*", "s3:DeleteBucket*", "s3:PutAccountPublicAccessBlock", "s3:PutObjectAcl", "s3:PutObjectLegalHold",
          "s3:BypassGovernanceRetention", "s3:PutObjectLockConfiguration", "s3:PutLifecycleConfiguration",
          "ec2:Run*", "ec2:Terminate*", "ec2:Modify*", "ec2:Create*", "ec2:Delete*", "ec2:Authorize*", "ec2:Revoke*",
          "ec2:Associate*", "ec2:Disassociate*", "ec2:Attach*", "ec2:Detach*", "ec2:Replace*",
          "ssm:PutParameter", "ssm:DeleteParameter*", "ssm:SendCommand", "ssm:CreateDocument", "ssm:UpdateDocument*",
          "ssm:DeleteDocument", "ssm:StartSession", "ssm:ResumeSession",
          "logs:DeleteLogGroup", "logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy", "logs:AssociateKmsKey",
          "logs:DisassociateKmsKey", "logs:PutMetricFilter", "logs:DeleteMetricFilter",
          "ecr:PutImage", "ecr:BatchDeleteImage", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload",
          "ecr:Delete*", "ecr:Set*", "ecr:Put*",
          "cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms", "cloudwatch:DisableAlarmActions", "cloudwatch:SetAlarmState",
          "sns:*", "ses:Create*", "ses:Delete*", "ses:Put*", "ses:Update*",
        ]
        Resource = "*"
      },
      ],
      [for r in [var.ses_send] : {
        Sid       = "SendAsTheStagingSender"
        Effect    = "Allow"
        Action    = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource  = r.resources
        Condition = { StringEquals = { "ses:FromAddress" = r.from_address } }
      } if length(r.resources) > 0],
    )
  })
}

resource "aws_iam_role_policy_attachment" "runtime" {
  role       = aws_iam_role.host.name
  policy_arn = aws_iam_policy.runtime.arn
}
