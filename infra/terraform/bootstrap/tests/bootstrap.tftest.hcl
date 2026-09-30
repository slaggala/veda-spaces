# Offline tests: `terraform test` plans with fake credentials and overridden computed values; no AWS API is
# called and nothing is created. Run: make -C infra test

provider "aws" {
  region                      = "ap-south-1"
  access_key                  = "offline-test"
  secret_key                  = "offline-test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}

variables {
  expected_account_id   = "111122223333"
  github_owner          = "example-org"
  github_repo           = "veda-spaces-aws-source"
  account_manifest_path = "tests/fixtures/account.json"
}

override_data {
  target          = data.aws_caller_identity.current
  override_during = plan
  values = {
    account_id = "111122223333"
    arn        = "arn:aws:sts::111122223333:assumed-role/bootstrap/owner"
  }
}

override_data {
  target          = data.aws_partition.current
  override_during = plan
  values          = { partition = "aws" }
}

override_resource {
  target          = aws_kms_key.state
  override_during = plan
  values = {
    arn    = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000"
    key_id = "00000000-0000-0000-0000-000000000000"
  }
}

override_resource {
  target          = aws_s3_bucket.state
  override_during = plan
  values = {
    arn    = "arn:aws:s3:::veda-tfstate-111122223333"
    id     = "veda-tfstate-111122223333"
    bucket = "veda-tfstate-111122223333"
  }
}

override_resource {
  target          = aws_iam_openid_connect_provider.github
  override_during = plan
  values          = { arn = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com" }
}

override_resource {
  target          = aws_iam_policy.boundary
  override_during = plan
  values          = { arn = "arn:aws:iam::111122223333:policy/veda-boundary" }
}

run "defaults" {
  command = plan

  assert {
    condition     = aws_s3_bucket.state.bucket == "veda-tfstate-111122223333"
    error_message = "State bucket name must be veda-tfstate-<account>."
  }

  assert {
    condition = alltrue([for k, n in { plan = "veda-gh-plan", apply = "veda-gh-apply", deploy = "veda-gh-deploy", evidence = "veda-gh-evidence" } :
    aws_iam_role.github[k].name == n])
    error_message = "Unexpected GitHub role names."
  }

  assert {
    condition     = alltrue([for r in aws_iam_role.github : r.permissions_boundary == "arn:aws:iam::111122223333:policy/veda-boundary"])
    error_message = "Every GitHub role must carry the veda boundary."
  }

  assert {
    condition     = alltrue([for r in aws_iam_role.github : r.max_session_duration == 3600])
    error_message = "GitHub role sessions must be at most one hour."
  }

  # Each role is trusted by exactly its own environment and nothing broader.
  assert {
    condition = alltrue([for k, env in { plan = "staging-plan", apply = "staging-infra", deploy = "staging", evidence = "staging-evidence" } :
      strcontains(data.aws_iam_policy_document.github_trust[k].json, "\"repo:example-org/veda-spaces-aws-source:environment:${env}\"")
    ])
    error_message = "Trust subject must pin repository and environment."
  }

  assert {
    condition     = alltrue([for d in data.aws_iam_policy_document.github_trust : !strcontains(d.json, "*") && strcontains(d.json, "sts.amazonaws.com")])
    error_message = "Trust policies must not contain wildcards and must pin the STS audience."
  }

  # Customer-managed policy size limit is 6,144 characters excluding whitespace.
  assert {
    condition = alltrue([for p in [
      data.aws_iam_policy_document.boundary.json, data.aws_iam_policy_document.plan.json,
      data.aws_iam_policy_document.apply_services.json, data.aws_iam_policy_document.apply_iam.json,
      data.aws_iam_policy_document.deploy.json, data.aws_iam_policy_document.evidence.json,
    ] : length(replace(p, "/\\s/", "")) < 6144])
    error_message = "A managed policy exceeds the 6,144-character IAM limit."
  }

  assert {
    condition     = strcontains(data.aws_iam_policy_document.boundary.json, "\"aws:RequestedRegion\"") && strcontains(data.aws_iam_policy_document.boundary.json, "\"ap-south-1\"")
    error_message = "Boundary must refuse regions other than ap-south-1."
  }

  assert {
    condition     = strcontains(data.aws_iam_policy_document.apply_iam.json, "iam:PermissionsBoundary")
    error_message = "Apply role may create roles only with the boundary attached."
  }

  assert {
    condition     = strcontains(data.aws_iam_policy_document.deploy.json, "ssm:resourceTag/project") && strcontains(data.aws_iam_policy_document.evidence.json, "ssm:resourceTag/env")
    error_message = "SSM commands must be limited to the tagged staging host."
  }

  assert {
    condition = alltrue([for p in [
      data.aws_iam_policy_document.plan.json, data.aws_iam_policy_document.apply_services.json,
      data.aws_iam_policy_document.deploy.json, data.aws_iam_policy_document.evidence.json,
    ] : strcontains(p, "DenyApplicationDataReads") && strcontains(p, "DenyApplicationSecretReads")])
    error_message = "Every GitHub role must be denied application data and secret reads."
  }

  assert {
    condition     = length(aws_iam_openid_connect_provider.github) == 1
    error_message = "OIDC provider is created when none exists."
  }

  assert {
    condition     = length(aws_accessanalyzer_analyzer.account) == 1 && aws_ec2_instance_metadata_defaults.this[0].http_tokens == "required"
    error_message = "Account guardrails are on by default."
  }
}

run "workflows_cannot_write_bootstrap_state" {
  command = plan

  assert {
    condition = (
      strcontains(data.aws_iam_policy_document.state_rw.json, "arn:aws:s3:::veda-tfstate-111122223333/staging/*")
      && strcontains(data.aws_iam_policy_document.state_read_lock.json, "arn:aws:s3:::veda-tfstate-111122223333/staging/*.tflock")
      && !strcontains(data.aws_iam_policy_document.state_rw.json, "bootstrap/")
    )
    error_message = "GitHub roles may write only staging/ state keys."
  }
}

run "existing_oidc_provider_is_reused" {
  command = plan

  variables {
    existing_github_oidc_provider_arn = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"
  }

  assert {
    condition     = length(aws_iam_openid_connect_provider.github) == 0
    error_message = "An existing OIDC provider must not be recreated."
  }
}

run "guardrails_can_be_disabled" {
  command = plan

  # F5: the choice lives in the reviewed manifest, not in a command-line flag.
  variables {
    account_manifest_path = "tests/fixtures/account-no-guardrails.json"
  }

  assert {
    condition     = length(aws_s3_account_public_access_block.this) == 0 && length(aws_accessanalyzer_analyzer.account) == 0
    error_message = "Guardrails must be skippable when the manifest says the account already manages them."
  }
}

run "rejects_other_region" {
  command = plan

  variables {
    aws_region = "us-east-1"
  }

  expect_failures = [var.aws_region]
}

run "rejects_malformed_account" {
  command = plan

  variables {
    expected_account_id = "12345"
  }

  expect_failures = [var.expected_account_id]
}

run "rejects_production_environment" {
  command = plan

  variables {
    environment = "production"
  }

  expect_failures = [var.environment]
}

# --- F3: the account is approved in the committed manifest ---------------------------------------------------

run "rejects_account_missing_from_manifest" {
  command = plan

  variables {
    account_manifest_path = "tests/fixtures/account-unset.json"
  }

  expect_failures = [var.expected_account_id]
}

run "rejects_account_other_than_manifest" {
  command = plan

  variables {
    expected_account_id = "444455556666"
  }

  expect_failures = [var.expected_account_id]
}

run "rejects_session_longer_than_one_hour" {
  command = plan

  variables {
    role_max_session_seconds = 43200
  }

  expect_failures = [var.role_max_session_seconds]
}

# --- Policy evaluation ------------------------------------------------------------------------------------------
# Every run below feeds the rendered policies of the "defaults" run into tests/policy_eval, which applies IAM's
# evaluation logic (explicit deny, identity allow, boundary allow) to concrete requests.

run "f1_apply_role_cannot_escape_boundary" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [run.defaults.policy_documents.apply_services, run.defaults.policy_documents.apply_iam]
    boundary_policy   = run.defaults.policy_documents.boundary
    default_context   = { "aws:RequestedRegion" = "ap-south-1", "aws:ResourceAccount" = "111122223333" }
    probes = [
      { name = "create bounded veda role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-host", context = { "iam:PermissionsBoundary" = "arn:aws:iam::111122223333:policy/veda-boundary" }, expect = "allow" },
      { name = "create veda role without boundary", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-host", expect = "deny" },
      { name = "create veda role with another boundary", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-host", context = { "iam:PermissionsBoundary" = "arn:aws:iam::111122223333:policy/veda-open" }, expect = "deny" },
      { name = "inline policy on veda role", action = "iam:PutRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-host", expect = "allow" },
      { name = "AdministratorAccess on veda role", action = "iam:AttachRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-host", context = { "iam:PolicyARN" = "arn:aws:iam::aws:policy/AdministratorAccess" }, expect = "deny" },
      { name = "job-function policy on veda role", action = "iam:AttachRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-host", context = { "iam:PolicyARN" = "arn:aws:iam::aws:policy/job-function/SystemAdministrator" }, expect = "deny" },
      { name = "retrust OrganizationAccountAccessRole", action = "iam:UpdateAssumeRolePolicy", resource = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole", expect = "deny" },
      { name = "boundary change", action = "iam:CreatePolicyVersion", resource = "arn:aws:iam::111122223333:policy/veda-boundary", expect = "deny" },
      { name = "remove boundary", action = "iam:DeleteRolePermissionsBoundary", resource = "arn:aws:iam::111122223333:role/veda-host", expect = "deny" },
      { name = "squat a veda-gh role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-gh-extra", context = { "iam:PermissionsBoundary" = "arn:aws:iam::111122223333:policy/veda-boundary" }, expect = "deny" },
      { name = "retrust GitHub apply role", action = "iam:UpdateAssumeRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-gh-apply", expect = "deny" },
      { name = "service-linked role", action = "iam:CreateServiceLinkedRole", resource = "arn:aws:iam::111122223333:role/aws-service-role/ssm.amazonaws.com/AWSServiceRoleForAmazonSSM", context = { "iam:AWSServiceName" = "ssm.amazonaws.com" }, expect = "allow" },
    ]
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "F1 apply role: ${join("; ", output.failures)}"
  }
}

# The escalation from the review: a veda-* role with Allow *:* under the boundary (what the apply role can make).
run "f1_escalated_role_stays_inside_boundary" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "*", Resource = "*" }] })]
    boundary_policy   = run.defaults.policy_documents.boundary
    default_context   = { "aws:RequestedRegion" = "ap-south-1", "aws:ResourceAccount" = "111122223333" }
    probes = [
      { name = "unbounded admin role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/admin", expect = "deny" },
      { name = "bounded non-veda role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/admin", context = { "iam:PermissionsBoundary" = "arn:aws:iam::111122223333:policy/veda-boundary" }, expect = "deny" },
      { name = "veda role on another path", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/x/veda-host", context = { "iam:PermissionsBoundary" = "arn:aws:iam::111122223333:policy/veda-boundary" }, expect = "deny" },
      { name = "unbounded veda role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-x", expect = "deny" },
      { name = "re-bound veda role to nothing", action = "iam:PutRolePermissionsBoundary", resource = "arn:aws:iam::111122223333:role/veda-x", context = { "iam:PermissionsBoundary" = "arn:aws:iam::aws:policy/AdministratorAccess" }, expect = "deny" },
      { name = "attach admin to org role", action = "iam:AttachRolePolicy", resource = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole", expect = "deny" },
      { name = "inline policy on SSO role", action = "iam:PutRolePolicy", resource = "arn:aws:iam::111122223333:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_Admin", expect = "deny" },
      { name = "pass a non-veda role", action = "iam:PassRole", resource = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole", expect = "deny" },
      { name = "pass a GitHub role", action = "iam:PassRole", resource = "arn:aws:iam::111122223333:role/veda-gh-apply", expect = "deny" },
      { name = "create user", action = "iam:CreateUser", resource = "arn:aws:iam::111122223333:user/backdoor", expect = "deny" },
      { name = "access key", action = "iam:CreateAccessKey", resource = "arn:aws:iam::111122223333:user/existing", expect = "deny" },
      { name = "user inline policy", action = "iam:PutUserPolicy", resource = "arn:aws:iam::111122223333:user/existing", expect = "deny" },
      { name = "new OIDC provider", action = "iam:CreateOpenIDConnectProvider", resource = "arn:aws:iam::111122223333:oidc-provider/evil.example", expect = "deny" },
      { name = "add OIDC client", action = "iam:AddClientIDToOpenIDConnectProvider", resource = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com", expect = "deny" },
      { name = "password policy", action = "iam:UpdateAccountPasswordPolicy", resource = "*", expect = "deny" },
      { name = "organizations", action = "organizations:LeaveOrganization", resource = "*", expect = "deny" },
      { name = "other region", action = "ec2:RunInstances", resource = "*", context = { "aws:RequestedRegion" = "us-east-1" }, expect = "deny" },
      { name = "read GitHub role (SecurityAudit evidence)", action = "iam:GetRole", resource = "arn:aws:iam::111122223333:role/veda-gh-apply", expect = "allow" },
      { name = "read OIDC provider", action = "iam:GetOpenIDConnectProvider", resource = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com", expect = "allow" },
      { name = "bounded veda role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-worker", context = { "iam:PermissionsBoundary" = "arn:aws:iam::111122223333:policy/veda-boundary" }, expect = "allow" },
    ]
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "F1 escalation: ${join("; ", output.failures)}"
  }
}

# --- F2: bootstrap state and the state bucket --------------------------------------------------------------------

run "f2_apply_role_cannot_touch_bootstrap_state" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [run.defaults.policy_documents.apply_services, run.defaults.policy_documents.apply_iam]
    boundary_policy   = run.defaults.policy_documents.boundary
    resource_policies = [run.defaults.policy_documents.state_bucket]
    default_context = {
      "aws:RequestedRegion"                            = "ap-south-1"
      "aws:ResourceAccount"                            = "111122223333"
      "aws:SecureTransport"                            = "true"
      "aws:PrincipalArn"                               = "arn:aws:iam::111122223333:role/veda-gh-apply"
      "s3:x-amz-server-side-encryption-aws-kms-key-id" = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000"
    }
    probes = [
      { name = "overwrite bootstrap state", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", expect = "deny" },
      { name = "delete-mark bootstrap state", action = "s3:DeleteObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", expect = "deny" },
      { name = "bootstrap lock file", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate.tflock", expect = "deny" },
      { name = "delete a state version", action = "s3:DeleteObjectVersion", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", expect = "deny" },
      { name = "replication out", action = "s3:PutReplicationConfiguration", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
      { name = "inventory out", action = "s3:PutInventoryConfiguration", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
      { name = "access logging", action = "s3:PutBucketLogging", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
      { name = "event notifications", action = "s3:PutBucketNotification", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
      { name = "object lock on state", action = "s3:PutBucketObjectLockConfiguration", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
      { name = "bucket policy", action = "s3:PutBucketPolicy", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
      { name = "lifecycle", action = "s3:PutLifecycleConfiguration", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
      { name = "encryption", action = "s3:PutEncryptionConfiguration", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
      { name = "delete bucket", action = "s3:DeleteBucket", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
      { name = "state key deletion", action = "kms:ScheduleKeyDeletion", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ResourceAliases" = "alias/veda-tfstate" }, expect = "deny" },
      { name = "write staging state", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", expect = "allow" },
      { name = "read bootstrap state", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", expect = "allow" },
      { name = "object lock on anchor bucket (AUT-103)", action = "s3:PutBucketObjectLockConfiguration", resource = "arn:aws:s3:::veda-stg-anchor-111122223333", expect = "allow" },
    ]
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "F2 apply role: ${join("; ", output.failures)}"
  }
}

# Resource side: holds even for a veda-* role outside the boundary; the owner session is unaffected.
run "f2_bucket_policy_protects_bootstrap_state" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "*", Resource = "*" }] })]
    resource_policies = [run.defaults.policy_documents.state_bucket]
    default_context = {
      "aws:SecureTransport"                            = "true"
      "s3:x-amz-server-side-encryption-aws-kms-key-id" = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000"
    }
    probes = [
      { name = "unbounded veda role writes bootstrap state", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-rogue" }, expect = "deny" },
      { name = "unbounded veda role changes the bucket policy", action = "s3:PutBucketPolicy", resource = "arn:aws:s3:::veda-tfstate-111122223333", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-rogue" }, expect = "deny" },
      { name = "owner writes bootstrap state", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole" }, expect = "allow" },
      { name = "wrong KMS key", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole", "s3:x-amz-server-side-encryption-aws-kms-key-id" = "arn:aws:kms:ap-south-1:999999999999:key/other" }, expect = "deny" },
      { name = "plain HTTP", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole", "aws:SecureTransport" = "false" }, expect = "deny" },
    ]
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "F2 bucket policy: ${join("; ", output.failures)}"
  }
}

# --- F6 and F7: guardrails, audit and cross-account exits for any bounded role ---------------------------------

run "f6_f7_boundary_guardrails_and_cross_account" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "*", Resource = "*" }] })]
    boundary_policy   = run.defaults.policy_documents.boundary
    default_context   = { "aws:RequestedRegion" = "ap-south-1", "aws:ResourceAccount" = "111122223333" }
    probes = [
      { name = "F6 unblock snapshot sharing", action = "ec2:EnableSnapshotBlockPublicAccess", resource = "*", expect = "deny" },
      { name = "F6 disable snapshot block", action = "ec2:DisableSnapshotBlockPublicAccess", resource = "*", expect = "deny" },
      { name = "F6 delete trail", action = "cloudtrail:DeleteTrail", resource = "arn:aws:cloudtrail:ap-south-1:111122223333:trail/veda-audit", expect = "deny" },
      { name = "F6 update trail", action = "cloudtrail:UpdateTrail", resource = "arn:aws:cloudtrail:ap-south-1:111122223333:trail/veda-audit", expect = "deny" },
      { name = "F6 event selectors", action = "cloudtrail:PutEventSelectors", resource = "arn:aws:cloudtrail:ap-south-1:111122223333:trail/veda-audit", expect = "deny" },
      { name = "F6 stop logging", action = "cloudtrail:StopLogging", resource = "arn:aws:cloudtrail:ap-south-1:111122223333:trail/veda-audit", expect = "deny" },
      { name = "F6 create trail", action = "cloudtrail:CreateTrail", resource = "arn:aws:cloudtrail:ap-south-1:111122223333:trail/veda-audit", expect = "allow" },
      { name = "F6 archive rule", action = "access-analyzer:CreateArchiveRule", resource = "arn:aws:access-analyzer:ap-south-1:111122223333:analyzer/veda-account-analyzer", expect = "deny" },
      { name = "F6 archive findings", action = "access-analyzer:UpdateFindings", resource = "arn:aws:access-analyzer:ap-south-1:111122223333:analyzer/veda-account-analyzer", expect = "deny" },
      { name = "F6 read trail config (evidence)", action = "cloudtrail:GetEventDataStore", resource = "arn:aws:cloudtrail:ap-south-1:111122223333:eventdatastore/x", expect = "allow" },
      { name = "F6 list archive rules (evidence)", action = "access-analyzer:ListArchiveRules", resource = "arn:aws:access-analyzer:ap-south-1:111122223333:analyzer/veda-account-analyzer", expect = "allow" },
      { name = "F6 IMDSv1 on an instance", action = "ec2:ModifyInstanceMetadataOptions", resource = "arn:aws:ec2:ap-south-1:111122223333:instance/i-1", context = { "ec2:MetadataHttpTokens" = "optional" }, expect = "deny" },
      { name = "F6 IMDSv1 at launch", action = "ec2:RunInstances", resource = "arn:aws:ec2:ap-south-1:111122223333:instance/*", context = { "ec2:MetadataHttpTokens" = "optional" }, expect = "deny" },
      { name = "F6 IMDSv2 at launch", action = "ec2:RunInstances", resource = "arn:aws:ec2:ap-south-1:111122223333:instance/*", context = { "ec2:MetadataHttpTokens" = "required" }, expect = "allow" },
      { name = "F6 account S3 public access block", action = "s3:PutAccountPublicAccessBlock", resource = "*", expect = "deny" },
      { name = "F7 share a snapshot", action = "ec2:ModifySnapshotAttribute", resource = "arn:aws:ec2:ap-south-1::snapshot/snap-1", expect = "deny" },
      { name = "F7 share an AMI", action = "ec2:ModifyImageAttribute", resource = "arn:aws:ec2:ap-south-1::image/ami-1", expect = "deny" },
      { name = "F7 KMS grant to another account", action = "kms:CreateGrant", resource = "arn:aws:kms:ap-south-1:111122223333:key/k", context = { "kms:GrantIsForAWSResource" = "false", "kms:GranteePrincipal" = "arn:aws:iam::999999999999:root" }, expect = "deny" },
      { name = "F7 KMS grant inside the account", action = "kms:CreateGrant", resource = "arn:aws:kms:ap-south-1:111122223333:key/k", context = { "kms:GrantIsForAWSResource" = "false", "kms:GranteePrincipal" = "arn:aws:iam::111122223333:role/veda-host" }, expect = "allow" },
      { name = "F7 KMS grant for an AWS resource (EBS)", action = "kms:CreateGrant", resource = "arn:aws:kms:ap-south-1:111122223333:key/k", context = { "kms:GrantIsForAWSResource" = "true", "kms:GranteePrincipal" = "arn:aws:iam::999999999999:root" }, expect = "allow" },
      { name = "F7 write to another account's bucket", action = "s3:PutObject", resource = "arn:aws:s3:::veda-stg-artifacts-111122223333/x", context = { "aws:ResourceAccount" = "999999999999" }, expect = "deny" },
      { name = "F7 Lambda permission for another account", action = "lambda:AddPermission", resource = "arn:aws:lambda:ap-south-1:111122223333:function:veda-f", context = { "lambda:Principal" = "999999999999" }, expect = "deny" },
      { name = "F7 Lambda permission for a service", action = "lambda:AddPermission", resource = "arn:aws:lambda:ap-south-1:111122223333:function:veda-f", context = { "lambda:Principal" = "events.amazonaws.com" }, expect = "allow" },
      { name = "F7 public function URL", action = "lambda:CreateFunctionUrlConfig", resource = "arn:aws:lambda:ap-south-1:111122223333:function:veda-f", context = { "lambda:FunctionUrlAuthType" = "NONE" }, expect = "deny" },
    ]
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "F6/F7 boundary: ${join("; ", output.failures)}"
  }
}

# F7: the deploy and evidence roles' S3 rights stop at the account boundary (bucket-name squatting).
run "f7_deploy_and_evidence_s3_is_account_bound" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [run.defaults.policy_documents.deploy, run.defaults.policy_documents.evidence]
    boundary_policy   = run.defaults.policy_documents.boundary
    default_context   = { "aws:RequestedRegion" = "ap-south-1" }
    probes = [
      { name = "bundle to our bucket", action = "s3:PutObject", resource = "arn:aws:s3:::veda-stg-artifacts-111122223333/b.tgz", context = { "aws:ResourceAccount" = "111122223333" }, expect = "allow" },
      { name = "bundle from a squatted bucket", action = "s3:GetObject", resource = "arn:aws:s3:::veda-stg-artifacts-111122223333/b.tgz", context = { "aws:ResourceAccount" = "999999999999" }, expect = "implicit" },
      { name = "evidence to a squatted bucket", action = "s3:PutObject", resource = "arn:aws:s3:::veda-evidence-111122223333/e.json", context = { "aws:ResourceAccount" = "999999999999" }, expect = "deny" },
      { name = "evidence to our bucket", action = "s3:PutObject", resource = "arn:aws:s3:::veda-evidence-111122223333/e.json", context = { "aws:ResourceAccount" = "111122223333" }, expect = "allow" },
      { name = "Litestream object", action = "s3:GetObject", resource = "arn:aws:s3:::veda-stg-litestream-111122223333/db", context = { "aws:ResourceAccount" = "111122223333" }, expect = "deny" },
      { name = "app secret", action = "ssm:GetParameter", resource = "arn:aws:ssm:ap-south-1:111122223333:parameter/veda/staging/app/jwt", expect = "deny" },
      { name = "run an arbitrary document", action = "ssm:SendCommand", resource = "arn:aws:ssm:ap-south-1:111122223333:document/AWS-RunShellScript", expect = "implicit" },
    ]
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "F7 deploy/evidence: ${join("; ", output.failures)}"
  }
}

# --- F9: the plan role (ReadOnlyAccess itself is AWS-managed; these are the explicit denies on top of it) --------

run "f9_plan_role_cannot_read_secrets_or_data" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [run.defaults.policy_documents.plan]
    boundary_policy   = run.defaults.policy_documents.boundary
    default_context   = { "aws:RequestedRegion" = "ap-south-1", "aws:ResourceAccount" = "111122223333" }
    probes = [
      { name = "edge secret (Cloudflare)", action = "ssm:GetParameter", resource = "arn:aws:ssm:ap-south-1:111122223333:parameter/veda/staging/edge/tunnel-token", expect = "deny" },
      { name = "app secret", action = "ssm:GetParameter", resource = "arn:aws:ssm:ap-south-1:111122223333:parameter/veda/staging/app/jwt", expect = "deny" },
      { name = "any other parameter", action = "ssm:GetParametersByPath", resource = "arn:aws:ssm:ap-south-1:111122223333:parameter/other", expect = "deny" },
      { name = "non-secret config", action = "ssm:GetParameter", resource = "arn:aws:ssm:ap-south-1:111122223333:parameter/veda/staging/config/domain", expect = "not_deny" },
      { name = "public AMI parameter", action = "ssm:GetParameter", resource = "arn:aws:ssm:ap-south-1::parameter/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64", expect = "not_deny" },
      { name = "artifacts object", action = "s3:GetObject", resource = "arn:aws:s3:::veda-stg-artifacts-111122223333/b.tgz", expect = "deny" },
      { name = "evidence object", action = "s3:GetObject", resource = "arn:aws:s3:::veda-evidence-111122223333/e.json", expect = "deny" },
      { name = "state object", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", expect = "allow" },
      { name = "log contents", action = "logs:GetLogEvents", resource = "arn:aws:logs:ap-south-1:111122223333:log-group:/veda/staging/api:log-stream:s", expect = "deny" },
      { name = "console output", action = "ec2:GetConsoleOutput", resource = "arn:aws:ec2:ap-south-1:111122223333:instance/i-1", expect = "deny" },
      { name = "command output", action = "ssm:GetCommandInvocation", resource = "*", expect = "deny" },
      { name = "secret value", action = "secretsmanager:GetSecretValue", resource = "arn:aws:secretsmanager:ap-south-1:111122223333:secret:x", expect = "deny" },
      { name = "write staging state", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", expect = "implicit" },
      { name = "take the staging lock", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate.tflock", expect = "allow" },
    ]
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "F9 plan role: ${join("; ", output.failures)}"
  }
}
