# Offline tests of the staging host (AUT-108). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

override_data {
  target = data.aws_ssm_parameter.al2023_arm64
  values = { insecure_value = "ami-0a1b2c3d4e5f67890" }
}

variables {
  name_prefix              = "veda-stg"
  account_id               = "111122223333"
  region                   = "ap-south-1"
  permissions_boundary_arn = "arn:aws:iam::111122223333:policy/veda-boundary"
  instance_type            = "t4g.small"
  subnet_id                = "subnet-0123456789abcdef0"
  security_group_id        = "sg-0123456789abcdef0"
  instance_profile_name    = "veda-stg-host"
  data_key_arn             = "arn:aws:kms:ap-south-1:111122223333:key/00000000-0000-0000-0000-00000000da7a"
  root_volume_gb           = 12
  data_volume_gb           = 20
  snapshot_retain_count    = 7
  app_log_group            = "/veda/staging/app"
}

run "hardened_graviton_host" {
  command = plan

  assert {
    condition     = aws_instance.host.instance_type == "t4g.small" && aws_instance.host.ami == "ami-0a1b2c3d4e5f67890"
    error_message = "t4g.small (N2) on the latest Amazon Linux 2023 arm64 at plan time"
  }

  assert {
    condition     = one(aws_instance.host.metadata_options).http_tokens == "required" && one(aws_instance.host.metadata_options).http_put_response_hop_limit == 2
    error_message = "IMDSv2 only, hop limit 2 (containers reach the role)"
  }

  assert {
    condition     = aws_instance.host.disable_api_termination && aws_instance.host.monitoring == false
    error_message = "termination protection, no paid detailed monitoring (no key pair: the plan guard refuses one)"
  }

  assert {
    condition     = one(aws_instance.host.credit_specification).cpu_credits == "standard" && one(aws_instance.host.maintenance_options).auto_recovery == "default"
    error_message = "burst credits capped (cost); automatic recovery"
  }

  assert {
    condition     = aws_instance.host.associate_public_ip_address && aws_instance.host.vpc_security_group_ids == toset(["sg-0123456789abcdef0"]) && aws_instance.host.subnet_id == "subnet-0123456789abcdef0"
    error_message = "the AUT-101 subnet and no-inbound group, with its own public IPv4 (egress model A)"
  }
}

run "encrypted_volumes_and_a_kept_data_volume" {
  command = plan

  assert {
    condition     = one(aws_instance.host.root_block_device).encrypted && one(aws_instance.host.root_block_device).kms_key_id == var.data_key_arn && one(aws_instance.host.root_block_device).volume_size == 12
    error_message = "the root volume is encrypted with the data key"
  }

  assert {
    condition     = aws_ebs_volume.data.encrypted && aws_ebs_volume.data.kms_key_id == var.data_key_arn && aws_ebs_volume.data.type == "gp3" && aws_ebs_volume.data.size == 20
    error_message = "the data volume is separate, gp3, encrypted with the data key"
  }

  assert {
    condition     = aws_ebs_volume.data.tags["veda-backup"] == "daily" && one(one(aws_dlm_lifecycle_policy.data.policy_details).schedule).retain_rule[0].count == 7
    error_message = "the data volume is snapshotted daily and seven snapshots are kept"
  }
}

run "boot_script_holds_no_secret" {
  command = plan

  assert {
    condition     = !strcontains(local.user_data, "SECRET") && !strcontains(local.user_data, "PRIVATE KEY") && strcontains(local.user_data, "\"log-driver\": \"awslogs\"") && strcontains(local.user_data, "172.30.0.0/16")
    error_message = "the boot script installs Docker and points its logs at CloudWatch; no secret"
  }
}

run "dlm_role_bounded_and_this_account_only" {
  command = plan

  assert {
    condition     = aws_iam_role.dlm.permissions_boundary == var.permissions_boundary_arn && jsondecode(aws_iam_role.dlm.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "111122223333"
    error_message = "the snapshot role is bounded and assumable by DLM for this account only"
  }
}

run "pinned_ami_wins" {
  command = plan

  variables {
    ami_id = "ami-00000000000000001"
  }

  assert {
    condition     = aws_instance.host.ami == "ami-00000000000000001"
    error_message = "a pinned AMI is used"
  }
}

run "x86_or_large_instance_refused" {
  command = plan

  variables {
    instance_type = "m5.large"
  }

  expect_failures = [var.instance_type]
}
