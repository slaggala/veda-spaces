# Offline tests of the deploy document (deployment wiring). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

variables {
  name_prefix            = "veda"
  region                 = "ap-south-1"
  artifacts_bucket       = "veda-stg-artifacts-111122223333"
  repository_url         = "111122223333.dkr.ecr.ap-south-1.amazonaws.com/veda-api"
  data_device            = "/dev/sdf"
  agent_config_parameter = "/veda/staging/cloudwatch-agent"
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
    condition = alltrue([for want in ["sha256sum -c -", "host-setup.sh /dev/sdf ap-south-1 /veda/staging/cloudwatch-agent", "render-env.sh ap-south-1", "docker pull \"111122223333.dkr.ecr.ap-south-1.amazonaws.com/veda-api@$DIGEST\"", "./deploy.sh \"$TAG\""] :
      anytrue([for c in jsondecode(aws_ssm_document.deploy.content).mainSteps[0].inputs.runCommand : strcontains(c, want)])
    ])
    error_message = "verify the bundle, set up the host, render the configuration, pull by digest, run deploy.sh"
  }
}

run "another_document_prefix_refused" {
  command = plan

  variables {
    name_prefix = "ops"
  }

  expect_failures = [var.name_prefix]
}
