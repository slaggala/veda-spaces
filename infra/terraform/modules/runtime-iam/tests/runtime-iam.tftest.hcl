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
    media      = "arn:aws:s3:::veda-stg-media-111122223333"
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
      s.Effect == "Deny" || !contains(flatten([s.Action]), "s3:DeleteObject") || s.Resource == "${var.bucket_arns.litestream}/*" ||
      toset(flatten([s.Resource])) == toset(["${var.bucket_arns.media}/source/*", "${var.bucket_arns.media}/variant/*"])
    ])
    error_message = "the host deletes only Litestream objects (WAL retention) and withdrawn media under source/ and variant/, never snapshots, anchors or evidence"
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

# Targeted media enablement: the host reaches the media bucket only under source/ and variant/, with no administration.
run "media_access_only_under_the_approved_prefixes" {
  command = plan

  assert {
    condition = toset(flatten([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : flatten([s.Resource])
      if s.Effect == "Allow" && strcontains(jsonencode(s.Resource), "veda-stg-media")])) == toset([
      "arn:aws:s3:::veda-stg-media-111122223333/source/*", "arn:aws:s3:::veda-stg-media-111122223333/variant/*",
      "arn:aws:s3:::veda-stg-media-111122223333",
    ])
    error_message = "the media bucket is reachable only under source/ and variant/ (and listed only there)"
  }

  assert {
    condition = toset(one([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s.Action if s.Sid == "CatalogMediaObjects"])) == toset([
    "s3:GetObject", "s3:PutObject", "s3:DeleteObject"])
    error_message = "get (and head), put and delete only: no version delete, tagging, ACL or policy action"
  }

  assert {
    condition     = one([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s.Condition.StringLike["s3:prefix"] if s.Sid == "CatalogMediaListPrefixes"]) == ["source/*", "variant/*"]
    error_message = "listing only under the approved prefixes"
  }

  assert {
    condition = alltrue([for s in jsondecode(aws_iam_policy.runtime.policy).Statement :
    !(s.Effect == "Allow" && strcontains(jsonencode(s.Resource), "veda-stg-media") && anytrue([for a in flatten([s.Action]) : startswith(a, "s3:PutBucket") || startswith(a, "s3:DeleteBucket") || a == "s3:PutObjectAcl" || a == "s3:DeleteObjectVersion"]))])
    error_message = "no bucket configuration, ACL or version-delete permission on the media bucket"
  }

  assert {
    condition = alltrue([for a in ["s3:PutBucket*", "s3:PutObjectAcl", "s3:PutLifecycleConfiguration", "s3:PutAccountPublicAccessBlock"] :
    contains(one([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s.Action if s.Sid == "DenyAdministration"]), a)])
    error_message = "the explicit deny of bucket administration still covers the media bucket"
  }

  assert {
    condition = length([for s in jsondecode(aws_iam_policy.runtime.policy).Statement : s
    if s.Effect == "Allow" && anytrue([for a in flatten([s.Action]) : startswith(a, "kms:")]) && s.Sid != "DataKey" && s.Sid != "AuditKeyThroughS3Only"]) == 0
    error_message = "no new KMS permission: media uses the existing data-key grant by alias"
  }
}

run "a_production_media_bucket_refused" {
  command = plan

  variables {
    bucket_arns = {
      litestream = "arn:aws:s3:::veda-stg-litestream-111122223333"
      snapshots  = "arn:aws:s3:::veda-stg-snapshots-111122223333"
      anchor     = "arn:aws:s3:::veda-stg-anchor-111122223333"
      artifacts  = "arn:aws:s3:::veda-stg-artifacts-111122223333"
      evidence   = "arn:aws:s3:::veda-evidence-111122223333"
      logs       = "arn:aws:s3:::veda-stg-logs-111122223333"
      media      = "arn:aws:s3:::veda-prod-media-111122223333"
    }
  }

  expect_failures = [var.bucket_arns]
}
