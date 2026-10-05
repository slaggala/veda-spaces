# Offline tests of the staging network module (AUT-101). The provider is mocked: nothing reaches AWS.
mock_provider "aws" {}

override_data {
  target = data.aws_ec2_instance_type_offerings.host
  values = { locations = ["aps1-az1", "aps1-az2", "aps1-az3"] }
}

override_data {
  target = data.aws_ec2_managed_prefix_list.s3
  values = { id = "pl-78a54011" }
}

variables {
  name_prefix              = "veda-stg"
  account_id               = "111122223333"
  region                   = "ap-south-1"
  egress_model             = "A"
  vpc_cidr                 = "10.60.0.0/20"
  public_subnet_cidr       = "10.60.0.0/24"
  az_id_preference         = ["aps1-az1", "aps1-az3", "aps1-az2"]
  host_instance_type       = "t4g.small"
  flow_log_traffic_type    = "ALL"
  flow_log_destination_arn = "arn:aws:s3:::veda-stg-logs-111122223333/vpc-flow"
  tunnel_egress_cidrs      = ["198.41.192.0/24", "198.41.200.0/24"]
  aws_owned_s3_object_arns = ["arn:aws:s3:::prod-ap-south-1-starport-layer-bucket/*", "arn:aws:s3:::al2023-repos-ap-south-1-de612dc2/*", "arn:aws:s3:::amazon-ssm-ap-south-1/*"]
}

run "vpc_and_subnet" {
  command = plan

  assert {
    condition     = aws_vpc.this.cidr_block == "10.60.0.0/20" && aws_vpc.this.enable_dns_support && aws_vpc.this.enable_dns_hostnames
    error_message = "the VPC must be 10.60.0.0/20 with DNS support and host names"
  }

  assert {
    condition     = aws_subnet.public.cidr_block == "10.60.0.0/24" && aws_subnet.public.availability_zone_id == "aps1-az1"
    error_message = "one public subnet, 10.60.0.0/24, in the first preferred AZ that offers the host type"
  }

  assert {
    condition     = aws_subnet.public.map_public_ip_on_launch == false
    error_message = "the subnet must not give public addresses (the host asks for its own, AUT-108)"
  }
}

run "routes_internet_and_s3_only" {
  command = plan

  assert {
    condition     = aws_route.internet.destination_cidr_block == "0.0.0.0/0" && aws_vpc_endpoint.s3.vpc_endpoint_type == "Gateway"
    error_message = "the public route table sends 0.0.0.0/0 to the internet gateway, S3 to the gateway endpoint"
  }

  assert {
    condition     = length(aws_default_route_table.this.route) == 0
    error_message = "the default route table must stay empty"
  }
}

run "host_security_group_has_no_inbound_and_narrow_outbound" {
  command = plan

  assert {
    condition = (
      aws_vpc_security_group_egress_rule.https.ip_protocol == "tcp" && aws_vpc_security_group_egress_rule.https.from_port == 443 &&
      aws_vpc_security_group_egress_rule.https.to_port == 443 && aws_vpc_security_group_egress_rule.https.cidr_ipv4 == "0.0.0.0/0"
    )
    error_message = "outbound HTTPS to anywhere on TCP 443 only"
  }

  assert {
    condition     = aws_vpc_security_group_egress_rule.https_s3.prefix_list_id == "pl-78a54011" && aws_vpc_security_group_egress_rule.https_s3.from_port == 443
    error_message = "outbound HTTPS to the S3 prefix list"
  }

  assert {
    condition = length(aws_vpc_security_group_egress_rule.tunnel) == 4 && alltrue([
      for r in aws_vpc_security_group_egress_rule.tunnel : r.from_port == 7844 && r.to_port == 7844 && contains(["tcp", "udp"], r.ip_protocol) &&
      contains(["198.41.192.0/24", "198.41.200.0/24"], r.cidr_ipv4)
    ])
    error_message = "the tunnel rules are TCP and UDP 7844 to the two Cloudflare ranges only"
  }
}

run "nacl_allows_no_inbound_service_port" {
  command = plan

  assert {
    condition     = alltrue([for k, r in aws_network_acl_rule.public : r.egress || r.from_port >= 1024])
    error_message = "inbound NACL rules allow ephemeral ports only (replies), never a service port"
  }

  assert {
    condition     = alltrue([for k, r in aws_network_acl_rule.public : !r.egress || contains([443, 7844], r.from_port) && r.from_port == r.to_port])
    error_message = "outbound NACL rules allow 443 and 7844 only"
  }

  assert {
    condition     = alltrue([for k, r in aws_network_acl_rule.public : r.rule_action == "allow" && r.protocol != "-1"])
    error_message = "no all-protocol NACL rule"
  }
}

run "s3_endpoint_policy_is_restricted" {
  command = plan

  assert {
    condition     = jsondecode(aws_vpc_endpoint.s3.policy).Statement[0].Condition.StringEquals["aws:ResourceAccount"] == "111122223333"
    error_message = "full S3 actions only on buckets of the approved account"
  }

  assert {
    condition = (
      jsondecode(aws_vpc_endpoint.s3.policy).Statement[1].Action == "s3:GetObject" &&
      jsondecode(aws_vpc_endpoint.s3.policy).Statement[1].Resource == ["arn:aws:s3:::prod-ap-south-1-starport-layer-bucket/*", "arn:aws:s3:::al2023-repos-ap-south-1-de612dc2/*", "arn:aws:s3:::amazon-ssm-ap-south-1/*"]
    )
    error_message = "AWS-owned buckets are read-only and named"
  }

  assert {
    condition     = length(jsondecode(aws_vpc_endpoint.s3.policy).Statement) == 2
    error_message = "exactly the two reviewed statements"
  }
}

run "flow_logs_to_the_logs_bucket" {
  command = plan

  assert {
    condition = (
      aws_flow_log.vpc.traffic_type == "ALL" && aws_flow_log.vpc.log_destination_type == "s3" &&
      aws_flow_log.vpc.log_destination == "arn:aws:s3:::veda-stg-logs-111122223333/vpc-flow" && aws_flow_log.vpc.iam_role_arn == null
    )
    error_message = "all traffic to the logs bucket (C3), with no role passed"
  }
}

run "next_preferred_az_when_the_first_lacks_the_type" {
  command = plan

  override_data {
    target = data.aws_ec2_instance_type_offerings.host
    values = { locations = ["aps1-az2", "aps1-az3"] }
  }

  assert {
    condition     = aws_subnet.public.availability_zone_id == "aps1-az3"
    error_message = "the second preference (aps1-az3) when aps1-az1 does not offer the type"
  }
}

run "pinned_az_is_used" {
  command = plan

  variables {
    az_id = "aps1-az2"
  }

  assert {
    condition     = aws_subnet.public.availability_zone_id == "aps1-az2"
    error_message = "a pinned AZ ID overrides the preference list (no replacement when offerings change)"
  }
}

run "pinned_az_without_the_type_refused" {
  command = plan

  variables {
    az_id = "aps1-az2"
  }

  override_data {
    target = data.aws_ec2_instance_type_offerings.host
    values = { locations = ["aps1-az1"] }
  }

  expect_failures = [aws_subnet.public]
}

run "nacl_rules_are_keyed_by_range" {
  command = plan

  variables {
    tunnel_egress_cidrs = ["198.41.200.0/24", "198.41.192.0/24"]
  }

  assert {
    condition     = aws_network_acl_rule.public["out-udp-7844-198.41.192.0/24"].rule_number == 300 && aws_network_acl_rule.public["out-udp-7844-198.41.200.0/24"].rule_number == 301
    error_message = "rules are keyed and numbered by range, whatever the order of the list"
  }
}

run "no_preferred_az_offers_the_type_refused" {
  command = plan

  override_data {
    target = data.aws_ec2_instance_type_offerings.host
    values = { locations = ["aps1-az9"] }
  }

  expect_failures = [aws_subnet.public]
}

run "subnet_outside_the_vpc_refused" {
  command = plan

  variables {
    public_subnet_cidr = "10.61.0.0/24"
  }

  expect_failures = [aws_subnet.public]
}

run "egress_model_other_than_a_refused" {
  command = plan

  variables {
    egress_model = "B"
  }

  expect_failures = [var.egress_model]
}

run "tunnel_open_to_everyone_refused" {
  command = plan

  variables {
    tunnel_egress_cidrs = ["0.0.0.0/0"]
  }

  expect_failures = [var.tunnel_egress_cidrs]
}
