# Offline tests of the deploy document (deployment wiring). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  name_prefix      = "veda"
  region           = "ap-south-1"
  artifacts_bucket = "veda-stg-artifacts-111122223333"
  evidence_bucket  = "veda-evidence-111122223333"
  repository_url   = "111122223333.dkr.ecr.ap-south-1.amazonaws.com/veda-api"
  data_device      = "/dev/sdf"
}

run "the_document_the_deploy_role_may_run" {
  command = plan

  assert {
    condition     = aws_ssm_document.deploy.name == "veda-deploy" && aws_ssm_document.deploy.document_type == "Command"
    error_message = "veda-deploy, a Command document (the bootstrap deploy role is scoped to that name)"
  }
}

run "parameters_accept_only_a_tag_a_digest_and_a_sha256" {
  command = plan

  assert {
    condition = (
      jsondecode(aws_ssm_document.deploy.content).parameters.imageDigest.allowedPattern == "^sha256:[0-9a-f]{64}$" &&
      jsondecode(aws_ssm_document.deploy.content).parameters.bundleSha256.allowedPattern == "^[0-9a-f]{64}$" &&
      can(regex(jsondecode(aws_ssm_document.deploy.content).parameters.releaseTag.allowedPattern, "0123456789ab")) &&
      !can(regex(jsondecode(aws_ssm_document.deploy.content).parameters.releaseTag.allowedPattern, "latest; rm -rf /"))
    )
    error_message = "the parameters cannot carry a command"
  }
}

run "bundle_verified_image_by_digest_then_deploy_sh" {
  command = plan

  assert {
    condition = alltrue([for want in ["sha256sum -c -", "host-setup.sh /dev/sdf ap-south-1 /opt/veda/host/cloudwatch-agent.json", "render-env.sh ap-south-1", "docker pull \"111122223333.dkr.ecr.ap-south-1.amazonaws.com/veda-api@$DIGEST\"", "./deploy.sh \"$TAG\""] :
      anytrue([for c in jsondecode(aws_ssm_document.deploy.content).mainSteps[0].inputs.runCommand : strcontains(c, want)])
    ])
    error_message = "verify the bundle, set up the host, render the configuration, pull by digest, run deploy.sh"
  }
}

run "collector_records_facts_into_the_evidence_bucket" {
  command = plan

  assert {
    condition     = aws_ssm_document.collect.name == "veda-collect" && jsondecode(aws_ssm_document.collect.content).parameters.label.allowedPattern == "^[a-z0-9][a-z0-9-]{0,39}$"
    error_message = "veda-collect (the bootstrap evidence role is scoped to it), with a constrained label"
  }

  assert {
    condition     = anytrue([for c in jsondecode(aws_ssm_document.collect.content).mainSteps[0].inputs.runCommand : strcontains(c, "s3://veda-evidence-111122223333/$KEY")]) && anytrue([for c in jsondecode(aws_ssm_document.collect.content).mainSteps[0].inputs.runCommand : strcontains(c, "sha256sum")])
    error_message = "the tarball and its SHA-256 go to the evidence bucket"
  }

  assert {
    condition     = !anytrue([for c in jsondecode(aws_ssm_document.collect.content).mainSteps[0].inputs.runCommand : strcontains(c, "/etc/veda/api.env")])
    error_message = "the collector never reads the rendered environment (secrets)"
  }

  assert {
    condition     = length(regexall("[{][{]", aws_ssm_document.collect.content)) == 1
    error_message = "the only {{ }} is the label parameter (SSM would read any other as a parameter)"
  }
}

run "another_document_prefix_refused" {
  command = plan

  variables {
    name_prefix = "ops"
  }

  expect_failures = [var.name_prefix]
}
