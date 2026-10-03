# Offline tests of the staging core root (AUT-301). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  account_manifest_path = "../../bootstrap/tests/fixtures/account.json"
}

run "empty_root_plans_no_change" {
  command = plan

  assert {
    condition     = local.account_id == "111122223333"
    error_message = "the account must come from the manifest"
  }
}

run "region_other_than_mumbai_refused" {
  command = plan

  variables {
    aws_region = "us-east-1"
  }

  expect_failures = [var.aws_region]
}
