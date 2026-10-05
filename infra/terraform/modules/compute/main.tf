# The staging host (AUT-108): one Graviton instance, Amazon Linux 2023 arm64, in the AUT-101 subnet with the
# no-inbound security group and its own public IPv4 (egress model A). Managed only through SSM: no key pair, no SSH.
# IMDSv2 only (hop limit 2 so the containers reach the instance role); encrypted root and data volumes with the data
# key; burstable credits capped (standard) so a runaway process cannot exceed the budget; EC2 automatic recovery;
# termination protection. The data volume (/var/lib/veda: SQLite, WAL, local snapshots) is separate, never deleted
# with the instance, and snapshotted daily (DLM). The boot script only installs Docker and the CloudWatch agent and
# points Docker's logs at CloudWatch; the deploy document (veda-deploy) mounts the volume, installs the pinned Compose
# plugin, renders the configuration and starts the containers. No dependency on any other workload (Aurion,
# swing-trader-vm).

data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

locals {
  ami_id = coalesce(var.ami_id, data.aws_ssm_parameter.al2023_arm64.insecure_value)

  user_data = <<-EOT
    #!/bin/bash
    # Veda staging host boot (AUT-108). No secret is written here: configuration comes from SSM at deploy time.
    set -euo pipefail
    dnf install -y docker amazon-cloudwatch-agent
    mkdir -p /etc/docker /var/log/veda /var/lib/veda
    cat >/etc/docker/daemon.json <<'JSON'
    {"default-address-pools": [{"base": "172.30.0.0/16", "size": 24}], "log-driver": "awslogs", "log-opts": {"mode": "non-blocking", "awslogs-region": "${var.region}", "awslogs-group": "${var.app_log_group}", "awslogs-create-group": "false", "tag": "{{.Name}}/{{.ID}}"}}
    JSON
    systemctl enable --now docker
    EOT
}

resource "aws_instance" "host" {
  #checkov:skip=CKV_AWS_88:Egress model A (owner decision N1): the host has its own public IPv4 and no inbound rule (AUT-101)
  #checkov:skip=CKV_AWS_126:Detailed monitoring is paid; the 5-minute basic metrics and the agent feed the alarms (cost, 25 USD budget)
  ami                         = local.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [var.security_group_id]
  associate_public_ip_address = true
  iam_instance_profile        = var.instance_profile_name
  monitoring                  = false
  disable_api_termination     = true
  ebs_optimized               = true
  user_data                   = local.user_data
  user_data_replace_on_change = false

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "disabled"
  }

  credit_specification {
    cpu_credits = "standard"
  }

  maintenance_options {
    auto_recovery = "default"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    encrypted             = true
    kms_key_id            = var.data_key_arn
    delete_on_termination = true
  }

  tags = { Name = "${var.name_prefix}-host" }

  lifecycle {
    # A new AMI or boot script must never replace the host (the plan guard refuses a replace): rebuilds follow the
    # runbook, with the data volume moved across.
    ignore_changes = [ami, user_data]
  }
}

resource "aws_ebs_volume" "data" {
  availability_zone = aws_instance.host.availability_zone
  type              = "gp3"
  size              = var.data_volume_gb
  encrypted         = true
  kms_key_id        = var.data_key_arn

  tags = { Name = "${var.name_prefix}-data", "veda-backup" = "daily" }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_volume_attachment" "data" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.data.id
  instance_id = aws_instance.host.id
}

# Daily snapshots of the data volume (OPS-007, 02 §12.2), kept for snapshot_retain_count days.
resource "aws_iam_role" "dlm" {
  name                 = "${var.name_prefix}-dlm"
  description          = "Data Lifecycle Manager snapshots of the Veda staging data volume (AUT-108)"
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "dlm.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = var.account_id } }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "data" {
  description        = "Veda staging data volume daily"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]
    target_tags    = { "veda-backup" = "daily" }

    schedule {
      name      = "daily"
      copy_tags = true

      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["20:30"] # 02:00 IST
      }

      retain_rule {
        count = var.snapshot_retain_count
      }
    }
  }
}
