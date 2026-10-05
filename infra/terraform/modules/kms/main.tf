# Customer-managed keys of the staging platform (AUT-102). Two keys, by duty:
#   data:  the application's MFA secret blobs (TG-02, VEDA_KMS_KEY_ARN), EBS volumes, the data buckets (Litestream,
#          snapshots, anchors, artifacts) and ECR;
#   audit: CloudTrail, the logs bucket (trail and VPC flow logs), the evidence bucket, CloudWatch Logs and the alarm
#          topic. Only AWS services named below use it directly, each bound to this account and these resources.
# Both: symmetric, single-region, yearly rotation, 30-day deletion window, never destroyed by Terraform. IAM
# policies grant use (the account root statement); a Deny refuses every caller of another account. The plan guard
# refuses a key without rotation, without that Deny, multi-region, or with a shorter deletion window.

locals {
  root_arn = "arn:aws:iam::${var.account_id}:root"

  # Shared by both keys: IAM decides who in the account may use the key; nobody outside the account may.
  base_statements = [
    {
      Sid       = "AccountIamPolicies"
      Effect    = "Allow"
      Principal = { AWS = local.root_arn }
      Action    = "kms:*"
      Resource  = "*"
    },
    {
      Sid       = "DenyOtherAccounts"
      Effect    = "Deny"
      Principal = "*"
      Action    = "kms:*"
      Resource  = "*"
      Condition = {
        StringNotEquals = { "kms:CallerAccount" = var.account_id }
        Bool            = { "aws:PrincipalIsAWSService" = "false" }
      }
    },
  ]

  audit_service_statements = [
    {
      Sid       = "CloudWatchLogsForVedaGroups"
      Effect    = "Allow"
      Principal = { Service = "logs.${var.region}.amazonaws.com" }
      Action    = ["kms:Encrypt*", "kms:Decrypt*", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:Describe*"]
      Resource  = "*"
      Condition = { ArnLike = { "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${var.region}:${var.account_id}:log-group:${var.log_group_prefix}/*" } }
    },
    {
      Sid       = "CloudTrailForTheVedaTrail"
      Effect    = "Allow"
      Principal = { Service = "cloudtrail.amazonaws.com" }
      Action    = ["kms:GenerateDataKey*", "kms:DescribeKey"]
      Resource  = "*"
      Condition = {
        StringEquals = { "aws:SourceArn" = "arn:aws:cloudtrail:${var.region}:${var.account_id}:trail/${var.trail_name}" }
        StringLike   = { "kms:EncryptionContext:aws:cloudtrail:arn" = "arn:aws:cloudtrail:*:${var.account_id}:trail/${var.trail_name}" }
      }
    },
    {
      Sid       = "LogDeliveryForFlowLogs"
      Effect    = "Allow"
      Principal = { Service = "delivery.logs.amazonaws.com" }
      Action    = ["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:DescribeKey"]
      Resource  = "*"
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:logs:${var.region}:${var.account_id}:*" }
      }
    },
    {
      Sid       = "CloudWatchAlarmsToTheAlarmTopic"
      Effect    = "Allow"
      Principal = { Service = "cloudwatch.amazonaws.com" }
      Action    = ["kms:Decrypt", "kms:GenerateDataKey*"]
      Resource  = "*"
      Condition = { StringEquals = { "aws:SourceAccount" = var.account_id } }
    },
  ]

  keys = {
    data  = { description = "Veda staging data: MFA secrets, EBS, data buckets, ECR (AUT-102)", statements = local.base_statements }
    audit = { description = "Veda staging audit: CloudTrail, logs, evidence, CloudWatch Logs, alarms (AUT-102)", statements = concat(local.base_statements, local.audit_service_statements) }
  }
}

resource "aws_kms_key" "this" {
  for_each = local.keys

  description              = each.value.description
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  multi_region             = false
  enable_key_rotation      = true
  rotation_period_in_days  = var.rotation_period_days
  deletion_window_in_days  = var.deletion_window_days
  policy                   = jsonencode({ Version = "2012-10-17", Statement = each.value.statements })

  tags = { Name = "${var.name_prefix}-${each.key}" }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_kms_alias" "this" {
  for_each = local.keys

  name          = "alias/${var.name_prefix}-${each.key}"
  target_key_id = aws_kms_key.this[each.key].key_id
}
