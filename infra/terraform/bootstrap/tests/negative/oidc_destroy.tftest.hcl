# NEGATIVE test (F4), run by infra/tests/run.sh: it MUST fail. A discovery error that passes the bootstrap's own
# OIDC provider in as "existing" must fail the plan (prevent_destroy), not delete the provider.

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

run "create_oidc_provider" {
  command = apply
}

run "passing_our_provider_as_existing_must_not_destroy_it" {
  command = plan

  variables {
    existing_github_oidc_provider_arn = "arn:aws:iam::111122223333:oidc-provider/token.actions.githubusercontent.com"
  }
}
