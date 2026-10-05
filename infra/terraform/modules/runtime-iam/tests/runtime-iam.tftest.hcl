# Offline tests of the host's runtime identity (AUT-106). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  name_prefix              = "veda-stg"
  account_id               = "111122223333"
  region                   = "ap-south-1"
  permissions_boundary_arn = "arn:aws:iam::111122223333:policy/veda-boundary"
  data_key_alias           = "alias/veda-stg-data"
  audit_key_alias          = "alias/veda-stg-audit"
  bucket_arns = {
    litestream = "arn:aws:s3:::veda-stg-litestream-111122223333"
    snapshots  = "arn:aws:s3:::veda-stg-snapshots-111122223333"
    anchor     = "arn:aws:s3:::veda-stg-anchor-111122223333"
    artifacts  = "arn:aws:s3:::veda-stg-artifacts-111122223333"
    evidence   = "arn:aws:s3:::veda-evidence-111122223333"
    logs       = "arn:aws:s3:::veda-stg-logs-111122223333"
  }
  repository_name  = "veda-api"
  log_group_prefix = "/veda/staging"
  parameter_path   = "/veda/staging"
}

run "bounded_role_and_profile" {
  command = plan

  assert {
    condition     = aws_iam_role.host.name == "veda-stg-host" && aws_iam_role.host.permissions_boundary == var.permissions_boundary_arn && aws_iam_instance_profile.host.name == "veda-stg-host"
    error_message = "role and instance profile veda-stg-host, bounded by veda-boundary"
  }

  assert {
    condition     = jsondecode(aws_iam_role.host.assume_role_policy).Statement[0].Principal == { Service = "ec2.amazonaws.com" }
    error_message = "assumable by EC2 only"
  }

  assert {
    condition     = aws_iam_role_policy_attachment.ssm_core.policy_arn == "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
    error_message = "the only AWS managed policy is the SSM core"
  }
}

run "every_allow_names_its_resources" {
  command = plan

  assert {
    condition = alltrue([for s in jsondecode(aws_iam_policy.runtime.policy).Statement :
      s.Effect == "Deny" || s.Resource != "*" || contains(["EcrLogin", "VedaMetrics"], s.Sid)
    ])
    error_message = "only ecr:GetAuthorizationToken and namespaced PutMetricData use Resource * (no resource-level permission)"
  }

  assert {
    condition = alltrue([for s in jsondecode(aws_iam_policy.runtime.policy).Statement :
      s.Effect == "Deny" || alltrue([for a in flatten([s.Action]) : !endswith(a, ":*") && a != "*"])
    ])
    error_message = "no Allow of a whole service"
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s.Condition.StringLike["cloudwatch:namespace"] if s.Sid == "VedaMetrics"]) == ["Veda/*", "CWAgent"]
    error_message = "metrics only in the Veda and CloudWatch agent namespaces"
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s.Condition.StringEquals["kms:ViaService"] if s.Sid == "AuditKeyThroughS3Only"]) == "s3.ap-south-1.amazonaws.com"
    error_message = "the audit key only through S3 (evidence uploads)"
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s.Condition["ForAnyValue:StringEquals"]["kms:ResourceAliases"] if s.Sid == "DataKey"]) == ["alias/veda-stg-data"]
    error_message = "the data key is matched by its alias"
  }
}

run "locked_buckets_never_deleted_by_the_host" {
  command = plan

  assert {
    condition = alltrue([for s in jsondecode(aws_iam_policy.runtime.policy).Statement :
      s.Effect == "Deny" || !contains(flatten([s.Action]), "s3:DeleteObject") || s.Resource == "${var.bucket_arns.litestream}/*"
    ])
    error_message = "the host deletes only Litestream objects (WAL retention), never snapshots, anchors or evidence"
  }
}

run "explicit_deny_of_administration" {
  command = plan

  assert {
    condition = alltrue([for a in ["iam:*", "sts:AssumeRole", "cloudtrail:*", "kms:ScheduleKeyDeletion", "s3:PutBucket*", "s3:DeleteBucket*", "ec2:Run*", "ssm:SendCommand", "ssm:PutParameter", "ecr:PutImage", "cloudwatch:DeleteAlarms", "sns:*", "ses:Create*"] :
      contains(one([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s.Action if s.Sid == "DenyAdministration"]), a)
    ])
    error_message = "the host may not administer IAM, roles, the trail, keys, buckets, EC2, SSM, images, alarms, SNS or SES"
  }
}

run "ses_send_only_as_the_staging_sender" {
  command = plan

  variables {
    ses_send = { resources = ["arn:aws:ses:ap-south-1:111122223333:identity/staging.vedaspaces.com"], from_address = "no-reply@staging.vedaspaces.com" }
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s.Condition.StringEquals["ses:FromAddress"] if s.Sid == "SendAsTheStagingSender"]) == "no-reply@staging.vedaspaces.com"
    error_message = "email is sent only from the staging sender"
  }
}

run "no_ses_permission_before_aut111" {
  command = plan

  assert {
    condition     = length([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s if s.Sid == "SendAsTheStagingSender"]) == 0
    error_message = "no send permission until the SES identities exist"
  }
}
