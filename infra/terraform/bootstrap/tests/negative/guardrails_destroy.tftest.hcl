# NEGATIVE test (F5), run by infra/tests/run.sh, never by `terraform test` in the bootstrap directory: it MUST
# fail. With a mock provider (no AWS call) it creates the guardrails, then flips the manifest to
# manage_account_guardrails = false; Terraform must refuse the plan (prevent_destroy) instead of removing them.

mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "111122223333" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }
  mock_resource "aws_iam_policy" {
    defaults = { arn = "arn:aws:iam::111122223333:policy/veda-mock" }
  }
  mock_resource "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com" }
  }
  mock_resource "aws_kms_key" {
    defaults = { arn = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-000000000000" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::veda-tfstate-111122223333" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::111122223333:role/veda-mock" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Deny\",\"Action\":\"none:null\",\"Resource\":\"*\"}]}" }
  }
}

variables {
  expected_account_id   = "111122223333"
  github_owner          = "example-org"
  github_repo           = "veda-spaces-aws-source"
  account_manifest_path = "tests/fixtures/account.json"
}

run "create_with_guardrails" {
  command = apply
}

run "turning_guardrails_off_must_not_destroy_them" {
  command = plan

  variables {
    account_manifest_path = "tests/fixtures/account-no-guardrails.json"
  }
}
