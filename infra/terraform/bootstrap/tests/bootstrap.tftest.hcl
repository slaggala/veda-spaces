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
  expected_account_id = "111122223333"
  github_owner        = "example-org"
  github_repo         = "veda-spaces-aws-source"
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
    condition     = !strcontains(data.aws_iam_policy_document.boundary.json, "PutBucketObjectLockConfiguration")
    error_message = "Boundary must not block Object Lock bucket creation (AUT-103)."
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

  variables {
    enable_account_guardrails = false
  }

  assert {
    condition     = length(aws_s3_account_public_access_block.this) == 0 && length(aws_accessanalyzer_analyzer.account) == 0
    error_message = "Guardrails must be skippable when the account already manages them."
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
