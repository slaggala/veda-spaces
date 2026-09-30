# Offline tests: `terraform test` plans with fake credentials and overridden computed values; no AWS API is
# called and nothing is created. Run: make -C infra test

provider "aws" {
  region                      = "ap-south-1"
  access_key                  = "offline-test"
  secret_key                  = "offline-test" # pragma: allowlist secret
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
}

variables {
  expected_account_id   = "111122223333"
  github_owner          = "example-org"
  github_repo           = "veda-spaces"
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

# The owner session runs as OrganizationAccountAccessRole, which the fixture manifest lists as a bootstrap principal.
override_data {
  target          = data.aws_iam_session_context.current
  override_during = plan
  values          = { issuer_arn = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole" }
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
      strcontains(data.aws_iam_policy_document.github_trust[k].json, "\"repo:example-org/veda-spaces:environment:${env}\"")
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

  # Bucket policies may be 20 KB and key policies 32 KB.
  assert {
    condition     = length(data.aws_iam_policy_document.state_bucket.json) < 20480 && length(data.aws_iam_policy_document.state_key.json) < 32768
    error_message = "The state bucket or state key policy exceeds its size limit."
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

  # RR-01/RR-02: the owners are the manifest's principals plus the account root, nothing else.
  assert {
    condition     = jsonencode(output.owner_principal_arns) == jsonencode(["arn:aws:iam::111122223333:root", "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole"])
    error_message = "Owner principals must be exactly the account root and the manifest's bootstrap_principal_arns."
  }

  # RR-02: no protection depends on an alias, and every KMS call for state carries the object ARN.
  assert {
    condition     = alltrue([for k, p in output.policy_documents : !strcontains(p, "kms:ResourceAliases")])
    error_message = "No policy may rely on kms:ResourceAliases (RR-02)."
  }

  assert {
    condition     = alltrue([for r in aws_s3_bucket_server_side_encryption_configuration.state.rule : r.bucket_key_enabled == false])
    error_message = "S3 Bucket Keys must stay off: the key policy binds each use to one object ARN (RR-02)."
  }

  assert {
    condition     = aws_kms_key.state.policy == output.policy_documents.state_key
    error_message = "The state key must carry the reviewed key policy."
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
    default_context   = { "aws:RequestedRegion" = "ap-south-1", "aws:ResourceAccount" = "111122223333", "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-apply" }
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
    default_context   = { "aws:RequestedRegion" = "ap-south-1", "aws:ResourceAccount" = "111122223333", "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-host" }
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
      { name = "RR-03 bounded veda role, created by a workload role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-worker", context = { "iam:PermissionsBoundary" = "arn:aws:iam::111122223333:policy/veda-boundary" }, expect = "deny" },
      { name = "bounded veda role, created by the apply role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-worker", context = { "iam:PermissionsBoundary" = "arn:aws:iam::111122223333:policy/veda-boundary", "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-apply" }, expect = "allow" },
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
    key_policies      = [run.defaults.policy_documents.state_key]
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
      { name = "state key deletion (no alias in the request)", action = "kms:ScheduleKeyDeletion", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:CallerAccount" = "111122223333" }, expect = "deny" },
      { name = "write staging state", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", expect = "allow" },
      { name = "RR-01 read bootstrap state", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", expect = "deny" },
      { name = "read staging state", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", expect = "allow" },
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

# --- RR-01: bootstrap state is the owner's alone, whoever else asks ----------------------------------------------
# Worst case for the resource side: every non-owner principal holds Allow *:* and no boundary (a role outside
# veda-boundary, a veda-* role under a path, a role named without the prefix, an SSO role, a user, a service). Only
# the state bucket policy stands between it and bootstrap state.

run "rr01_bucket_policy_bootstrap_state_owner_only" {
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
    probes = concat(
      # Object actions on bootstrap state: read, export, copy out, overwrite, copy in, multipart, replicate in,
      # restore, retag, re-ACL, delete, roll back to an older version.
      flatten([for who, arn in {
        "veda-gh-apply"          = "arn:aws:iam::111122223333:role/veda-gh-apply"
        "veda-rogue"             = "arn:aws:iam::111122223333:role/veda-rogue"
        "path role x/veda-rogue" = "arn:aws:iam::111122223333:role/x/veda-rogue"
        "path role veda-x/rogue" = "arn:aws:iam::111122223333:role/veda-x/rogue"
        "non-veda legacy-admin"  = "arn:aws:iam::111122223333:role/legacy-admin"
        "SSO admin"              = "arn:aws:iam::111122223333:role/aws-reserved/sso.amazonaws.com/ap-south-1/AWSReservedSSO_Admin_0123"
        "IAM user"               = "arn:aws:iam::111122223333:user/alice"
        "other account"          = "arn:aws:iam::999999999999:role/OrganizationAccountAccessRole"
        } : [for a in [
          "s3:GetObject", "s3:GetObjectVersion", "s3:GetObjectAttributes", "s3:GetObjectTorrent", "s3:PutObject",
          "s3:DeleteObject", "s3:DeleteObjectVersion", "s3:ReplicateObject", "s3:ReplicateDelete", "s3:ReplicateTags",
          "s3:RestoreObject", "s3:PutObjectTagging", "s3:PutObjectVersionTagging", "s3:PutObjectAcl",
          "s3:ObjectOwnerOverrideToBucketOwner", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts",
          ] : {
          name     = "${who}: ${a} bootstrap/terraform.tfstate"
          action   = a
          resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate"
          context  = { "aws:PrincipalArn" = arn }
          expect   = "deny"
      }]]),
      # Any other path out or in: bucket configuration, replication, inventory, logging, notifications, versioning,
      # ownership, deletion; replication into any key.
      flatten([for who, arn in {
        "veda-gh-apply"          = "arn:aws:iam::111122223333:role/veda-gh-apply"
        "path role x/veda-rogue" = "arn:aws:iam::111122223333:role/x/veda-rogue"
        "non-veda legacy-admin"  = "arn:aws:iam::111122223333:role/legacy-admin"
        } : [for a in [
          "s3:PutReplicationConfiguration", "s3:PutInventoryConfiguration", "s3:PutBucketLogging",
          "s3:PutBucketNotification", "s3:PutBucketPolicy", "s3:DeleteBucketPolicy", "s3:PutBucketVersioning",
          "s3:PutLifecycleConfiguration", "s3:PutEncryptionConfiguration", "s3:PutBucketOwnershipControls",
          "s3:PutBucketObjectLockConfiguration", "s3:PutBucketAcl", "s3:DeleteBucket",
          ] : {
          name     = "${who}: ${a}"
          action   = a
          resource = "arn:aws:s3:::veda-tfstate-111122223333"
          context  = { "aws:PrincipalArn" = arn }
          expect   = "deny"
      }]]),
      [
        { name = "veda role replicates into staging state", action = "s3:ReplicateObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-replicator" }, expect = "deny" },
        { name = "veda role deletes a staging state version", action = "s3:DeleteObjectVersion", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-apply" }, expect = "deny" },
        { name = "a service principal (no principal ARN) reads bootstrap state", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", expect = "deny" },
        { name = "owner via an access point", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole", "s3:DataAccessPointArn" = "arn:aws:s3:ap-south-1:111122223333:accesspoint/state" }, expect = "deny" },
        { name = "veda role via an access point", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-plan", "s3:DataAccessPointArn" = "arn:aws:s3:ap-south-1:111122223333:accesspoint/state" }, expect = "deny" },
        { name = "owner writes bootstrap state", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole" }, expect = "allow" },
        { name = "owner reads bootstrap state", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole" }, expect = "allow" },
        { name = "owner changes the bucket policy", action = "s3:PutBucketPolicy", resource = "arn:aws:s3:::veda-tfstate-111122223333", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole" }, expect = "allow" },
        { name = "account root recovers the bucket policy", action = "s3:DeleteBucketPolicy", resource = "arn:aws:s3:::veda-tfstate-111122223333", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:root" }, expect = "allow" },
        { name = "apply role writes staging state", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-apply" }, expect = "allow" },
        { name = "plan role reads staging state", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-plan" }, expect = "allow" },
      ],
    )
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "RR-01 bucket policy: ${join("; ", output.failures)}"
  }
}

# Identity side, independently of the bucket policy: any bounded role, even with *:*, is refused bootstrap state
# and every movement path.
run "rr01_boundary_alone_protects_bootstrap_state" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "*", Resource = "*" }] })]
    boundary_policy   = run.defaults.policy_documents.boundary
    default_context   = { "aws:RequestedRegion" = "ap-south-1", "aws:ResourceAccount" = "111122223333", "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-apply" }
    probes = concat(
      [for a in ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject", "s3:DeleteObject", "s3:DeleteObjectVersion", "s3:ReplicateObject", "s3:ReplicateDelete", "s3:RestoreObject", "s3:PutObjectTagging"] : {
        name     = "bounded role: ${a} bootstrap/terraform.tfstate"
        action   = a
        resource = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate"
        expect   = "deny"
      }],
      [
        { name = "bounded role: replicate into staging state", action = "s3:ReplicateObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", expect = "deny" },
        { name = "bounded role: replication configuration", action = "s3:PutReplicationConfiguration", resource = "arn:aws:s3:::veda-tfstate-111122223333", expect = "deny" },
        { name = "bounded role: write staging state", action = "s3:PutObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", expect = "allow" },
      ],
    )
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "RR-01 boundary: ${join("; ", output.failures)}"
  }
}

# The owner allow-list itself is checked at plan time, so a mistake fails the plan instead of locking out the owner
# or admitting a Veda role.
run "rr01_owner_list_required" {
  command = plan
  variables {
    account_manifest_path = "tests/fixtures/account-owner-empty.json"
  }
  expect_failures = [aws_kms_key.state]
}

run "rr01_owner_list_rejects_veda_role" {
  command = plan
  variables {
    account_manifest_path = "tests/fixtures/account-owner-veda.json"
  }
  expect_failures = [aws_kms_key.state]
}

run "rr01_owner_list_rejects_veda_role_under_a_path" {
  command = plan
  variables {
    account_manifest_path = "tests/fixtures/account-owner-veda-path.json"
  }
  expect_failures = [aws_kms_key.state]
}

run "rr01_owner_list_rejects_wildcards" {
  command = plan
  variables {
    account_manifest_path = "tests/fixtures/account-owner-wildcard.json"
  }
  expect_failures = [aws_kms_key.state]
}

run "rr01_owner_list_rejects_other_account" {
  command = plan
  variables {
    account_manifest_path = "tests/fixtures/account-owner-other-account.json"
  }
  expect_failures = [aws_kms_key.state]
}

run "rr01_owner_session_must_be_listed" {
  command = plan
  override_data {
    target = data.aws_iam_session_context.current
    values = { issuer_arn = "arn:aws:iam::111122223333:role/SomeOtherAdmin" }
  }
  expect_failures = [aws_kms_key.state]
}

# PB-09 / N-12: the root user may own the state for recovery but may not run the bootstrap; owners are roles only.
run "pb09_root_session_cannot_run_the_bootstrap" {
  command = plan
  override_data {
    target = data.aws_iam_session_context.current
    values = { issuer_arn = "arn:aws:iam::111122223333:root" }
  }
  expect_failures = [aws_kms_key.state]
}

run "pb09_owner_list_rejects_iam_users" {
  command = plan
  variables {
    account_manifest_path = "tests/fixtures/account-owner-user.json"
  }
  expect_failures = [aws_kms_key.state]
}

# PB-01: the OIDC subjects may name only the repository approved in the manifest.
run "pb01_rejects_repository_other_than_manifest" {
  command = plan
  variables {
    github_repo = "veda-spaces-fork"
  }
  expect_failures = [var.github_repo]
}

# PB-06: the manifest itself must approve Mumbai only.
run "pb06_rejects_manifest_region_other_than_mumbai" {
  command = plan
  variables {
    account_manifest_path = "tests/fixtures/account-region-other.json"
  }
  expect_failures = [var.aws_region]
}

# --- RR-02: the state key's own policy decides, not an alias -----------------------------------------------------
# The apply role's real policies (kms:* on *) with NO boundary, so every refusal below comes from the key policy.
# No request carries kms:ResourceAliases; one carries a foreign alias to show it changes nothing.

run "rr02_key_policy_enforces_state_key_protection" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [run.defaults.policy_documents.apply_services, run.defaults.policy_documents.apply_iam]
    key_policies      = [run.defaults.policy_documents.state_key]
    default_context   = { "aws:ResourceAccount" = "111122223333", "kms:CallerAccount" = "111122223333", "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-apply" }
    probes = concat(
      flatten([for who, arn in {
        "veda-gh-apply"          = "arn:aws:iam::111122223333:role/veda-gh-apply"
        "path role x/veda-rogue" = "arn:aws:iam::111122223333:role/x/veda-rogue"
        "non-veda legacy-admin"  = "arn:aws:iam::111122223333:role/legacy-admin"
        } : [for a in [
          "kms:PutKeyPolicy", "kms:ScheduleKeyDeletion", "kms:DisableKey", "kms:DisableKeyRotation", "kms:CreateGrant",
          "kms:RetireGrant", "kms:RevokeGrant", "kms:CreateAlias", "kms:UpdateAlias", "kms:DeleteAlias", "kms:TagResource",
          "kms:UntagResource", "kms:UpdateKeyDescription", "kms:ImportKeyMaterial", "kms:DeleteImportedKeyMaterial",
          "kms:ReplicateKey", "kms:UpdatePrimaryRegion", "kms:ReEncryptFrom", "kms:GenerateDataKeyWithoutPlaintext",
          ] : {
          name     = "${who}: ${a}"
          action   = a
          resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000"
          context  = { "aws:PrincipalArn" = arn }
          expect   = "deny"
      }]]),
      [
        { name = "key deletion with a foreign alias in the request", action = "kms:ScheduleKeyDeletion", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ResourceAliases" = "alias/something-else" }, expect = "deny" },
        { name = "decrypt bootstrap state through S3", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ViaService" = "s3.ap-south-1.amazonaws.com", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate" }, expect = "deny" },
        { name = "encrypt bootstrap state through S3", action = "kms:GenerateDataKey", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ViaService" = "s3.ap-south-1.amazonaws.com", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate" }, expect = "deny" },
        { name = "decrypt directly (not through S3)", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate" }, expect = "deny" },
        { name = "decrypt through another service", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ViaService" = "ec2.ap-south-1.amazonaws.com", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate" }, expect = "deny" },
        { name = "bucket-level context (S3 Bucket Key requested per object)", action = "kms:GenerateDataKey", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ViaService" = "s3.ap-south-1.amazonaws.com", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333" }, expect = "deny" },
        { name = "another bucket's object", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ViaService" = "s3.ap-south-1.amazonaws.com", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-stg-artifacts-111122223333/x" }, expect = "deny" },
        { name = "no encryption context", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ViaService" = "s3.ap-south-1.amazonaws.com" }, expect = "deny" },
        { name = "another account through S3", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:CallerAccount" = "999999999999", "kms:ViaService" = "s3.ap-south-1.amazonaws.com", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate" }, expect = "deny" },
        { name = "apply role decrypts staging state through S3", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ViaService" = "s3.ap-south-1.amazonaws.com", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate" }, expect = "allow" },
        { name = "apply role encrypts staging state through S3", action = "kms:GenerateDataKey", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:ViaService" = "s3.ap-south-1.amazonaws.com", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate" }, expect = "allow" },
        { name = "evidence reads the key policy", action = "kms:GetKeyPolicy", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", expect = "allow" },
        { name = "describe the key", action = "kms:DescribeKey", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", expect = "allow" },
        { name = "owner changes the key policy", action = "kms:PutKeyPolicy", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole" }, expect = "allow" },
        { name = "owner decrypts bootstrap state through S3", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole", "kms:ViaService" = "s3.ap-south-1.amazonaws.com", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate" }, expect = "allow" },
        { name = "owner decrypts directly", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/OrganizationAccountAccessRole", "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate" }, expect = "deny" },
        { name = "account root schedules deletion (recovery)", action = "kms:ScheduleKeyDeletion", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:root" }, expect = "allow" },
      ],
    )
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "RR-02 key policy: ${join("; ", output.failures)}"
  }
}

# The plan role's own key permission, under the boundary and the key policy: staging state only.
run "rr02_plan_role_uses_the_key_for_staging_state_only" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [run.defaults.policy_documents.plan]
    boundary_policy   = run.defaults.policy_documents.boundary
    key_policies      = [run.defaults.policy_documents.state_key]
    default_context   = { "aws:RequestedRegion" = "ap-south-1", "kms:CallerAccount" = "111122223333", "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-plan", "kms:ViaService" = "s3.ap-south-1.amazonaws.com" }
    probes = [
      { name = "decrypt staging state", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate" }, expect = "allow" },
      { name = "encrypt the staging lock", action = "kms:GenerateDataKey", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate.tflock" }, expect = "allow" },
      { name = "decrypt bootstrap state", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-tfstate-111122223333/bootstrap/terraform.tfstate" }, expect = "deny" },
      { name = "decrypt another bucket's object", action = "kms:Decrypt", resource = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000", context = { "kms:EncryptionContext:aws:s3:arn" = "arn:aws:s3:::veda-stg-artifacts-111122223333/x" }, expect = "deny" },
    ]
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "RR-02 plan role: ${join("; ", output.failures)}"
  }
}

# --- RR-03: IAM paths and trust policies ------------------------------------------------------------------------
# A bounded principal holding *:* (the review's escalation), as the apply role (the only one allowed to write trust)
# unless a probe says otherwise.

run "rr03_boundary_closes_path_and_trust_bypass" {
  command = plan
  module {
    source = "./tests/policy_eval"
  }

  variables {
    identity_policies = [jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "*", Resource = "*" }] })]
    boundary_policy   = run.defaults.policy_documents.boundary
    default_context   = { "aws:RequestedRegion" = "ap-south-1", "aws:ResourceAccount" = "111122223333", "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-apply", "iam:PermissionsBoundary" = "arn:aws:iam::111122223333:policy/veda-boundary" }
    probes = [
      # IAM path bypass: role/veda-* matches role/veda-x/admin; nothing under a path is created, passed or changed.
      { name = "path: create role/veda-x/admin", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-x/admin", expect = "deny" },
      { name = "path: create role/veda-gh-x/plan", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-gh-x/plan", expect = "deny" },
      { name = "path: create role/x/veda-host", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/x/veda-host", expect = "deny" },
      { name = "path: create policy/veda-x/admin", action = "iam:CreatePolicy", resource = "arn:aws:iam::111122223333:policy/veda-x/admin", expect = "deny" },
      { name = "path: new version of policy/veda-x/admin", action = "iam:CreatePolicyVersion", resource = "arn:aws:iam::111122223333:policy/veda-x/admin", expect = "deny" },
      { name = "path: create instance-profile/veda-x/p", action = "iam:CreateInstanceProfile", resource = "arn:aws:iam::111122223333:instance-profile/veda-x/p", expect = "deny" },
      { name = "path: add a role to instance-profile/veda-x/p", action = "iam:AddRoleToInstanceProfile", resource = "arn:aws:iam::111122223333:instance-profile/veda-x/p", expect = "deny" },
      { name = "path: pass role/veda-x/admin", action = "iam:PassRole", resource = "arn:aws:iam::111122223333:role/veda-x/admin", expect = "deny" },
      { name = "path: inline policy on role/veda-x/admin", action = "iam:PutRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-x/admin", expect = "deny" },
      { name = "path: attach to role/veda-x/admin", action = "iam:AttachRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-x/admin", expect = "deny" },
      { name = "path: re-trust role/veda-x/admin", action = "iam:UpdateAssumeRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-x/admin", expect = "deny" },
      { name = "no path: create role/veda-host", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-host", expect = "allow" },
      { name = "no path: pass role/veda-host", action = "iam:PassRole", resource = "arn:aws:iam::111122223333:role/veda-host", expect = "allow" },
      { name = "service-linked role (AWS path) still created", action = "iam:CreateServiceLinkedRole", resource = "arn:aws:iam::111122223333:role/aws-service-role/ssm.amazonaws.com/AWSServiceRoleForAmazonSSM", expect = "allow" },
      # Trust bypass: only veda-gh-apply writes trust.
      { name = "trust: apply role re-trusts a workload role", action = "iam:UpdateAssumeRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-host", expect = "allow" },
      { name = "trust: workload role re-trusts itself", action = "iam:UpdateAssumeRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-host", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-host" }, expect = "deny" },
      { name = "trust: workload role re-trusts another", action = "iam:UpdateAssumeRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-worker", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-host" }, expect = "deny" },
      { name = "trust: workload role creates a role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-worker", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-host" }, expect = "deny" },
      { name = "trust: deploy role creates a role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-worker", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-deploy" }, expect = "deny" },
      { name = "trust: role under a path named like apply", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-worker", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/x/veda-gh-apply" }, expect = "deny" },
      { name = "trust: apply role re-trusts a GitHub role", action = "iam:UpdateAssumeRolePolicy", resource = "arn:aws:iam::111122223333:role/veda-gh-plan", expect = "deny" },
      # Trust bypass at use time: a federated session of any role but veda-gh-* can do nothing.
      { name = "federated session of a workload role reads state", action = "s3:GetObject", resource = "arn:aws:s3:::veda-tfstate-111122223333/staging/core.tfstate", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-host", "aws:FederatedProvider" = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com" }, expect = "deny" },
      { name = "SAML session of a workload role is not seen by the boundary (N-01: aws:FederatedProvider is OIDC-only; closed by discovery)", action = "ec2:DescribeInstances", resource = "*", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-host" }, expect = "not_deny" },
      { name = "federated session of a path role named like a GitHub role", action = "ec2:DescribeInstances", resource = "*", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/x/veda-gh-deploy", "aws:FederatedProvider" = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com" }, expect = "deny" },
      { name = "federated session of veda-gh-deploy works", action = "ecr:GetAuthorizationToken", resource = "*", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-gh-deploy", "aws:FederatedProvider" = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com" }, expect = "allow" },
      { name = "federated session of veda-gh-apply creates a bounded role", action = "iam:CreateRole", resource = "arn:aws:iam::111122223333:role/veda-host", context = { "aws:FederatedProvider" = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com" }, expect = "allow" },
      { name = "instance-role session of a workload role works", action = "ec2:DescribeInstances", resource = "*", context = { "aws:PrincipalArn" = "arn:aws:iam::111122223333:role/veda-host" }, expect = "allow" },
    ]
  }

  assert {
    condition     = length(output.failures) == 0
    error_message = "RR-03 boundary: ${join("; ", output.failures)}"
  }
}

# RR-03/RR-07: a role cannot be pointed at an environment other than its protected one.
run "rr03_rejects_other_github_environment" {
  command = plan

  variables {
    github_environments = { plan = "staging-plan", apply = "unprotected", deploy = "staging", evidence = "staging-evidence" }
  }

  expect_failures = [var.github_environments]
}
