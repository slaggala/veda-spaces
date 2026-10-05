# Staging network, egress model A (AUT-101, owner decision N1): one VPC, one public subnet in one AZ, no inbound
# access at all, outbound only on TCP 443 and to the Cloudflare tunnel edge on TCP/UDP 7844, in-region S3 through a
# gateway endpoint with a restricted policy, and flow logs to the logs bucket (C3). The host (AUT-108) attaches host_security_group_id and asks
# for its own public IPv4; nothing here gives an address to anything. Design: docs/implementation/staging/
# AUT-101-design-package.md.

# --- AZ: the first preferred AZ ID that offers the host's instance type (N2, N5) ----------------------------------
data "aws_ec2_instance_type_offerings" "host" {
  location_type = "availability-zone-id"

  filter {
    name   = "instance-type"
    values = [var.host_instance_type]
  }
}

locals {
  candidate_az_ids = var.az_id != null ? [var.az_id] : var.az_id_preference
  offered_az_ids   = [for z in local.candidate_az_ids : z if contains(data.aws_ec2_instance_type_offerings.host.locations, z)]
  az_id            = try(local.offered_az_ids[0], local.candidate_az_ids[0])
}

# --- VPC and its defaults, managed empty --------------------------------------------------------------------------
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.name_prefix}-vpc" }
}

# No rules: nothing can use the default security group (CKV2_AWS_12).
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id

  tags = { Name = "${var.name_prefix}-default-unused" }
}

# Local route only: a subnet that is not explicitly associated reaches nothing.
resource "aws_default_route_table" "this" {
  default_route_table_id = aws_vpc.this.default_route_table_id
  route                  = []

  tags = { Name = "${var.name_prefix}-default-unused" }
}

# No rules (deny all): a subnet that is not explicitly associated passes nothing.
resource "aws_default_network_acl" "this" {
  default_network_acl_id = aws_vpc.this.default_network_acl_id

  tags = { Name = "${var.name_prefix}-default-unused" }

  lifecycle {
    # AWS moves subnets to and from the default ACL as they are associated elsewhere.
    ignore_changes = [subnet_ids]
  }
}

# --- Subnet, internet gateway, routes ----------------------------------------------------------------------------
resource "aws_subnet" "public" {
  vpc_id               = aws_vpc.this.id
  cidr_block           = var.public_subnet_cidr
  availability_zone_id = local.az_id
  # The host requests its own public IPv4 (AUT-108); nothing else launched here gets one (CKV_AWS_130).
  map_public_ip_on_launch = false

  tags = { Name = "${var.name_prefix}-public-a" }

  lifecycle {
    precondition {
      condition     = length(local.offered_az_ids) > 0
      error_message = "None of the AZ IDs (${join(", ", local.candidate_az_ids)}) offers ${var.host_instance_type} (owner decisions N2, N5)."
    }
    precondition {
      # The subnet's network, read with the VPC's mask, is the VPC's network, and the subnet is no larger.
      condition     = tonumber(split("/", var.public_subnet_cidr)[1]) >= tonumber(split("/", var.vpc_cidr)[1]) && cidrhost("${cidrhost(var.public_subnet_cidr, 0)}/${split("/", var.vpc_cidr)[1]}", 0) == cidrhost(var.vpc_cidr, 0)
      error_message = "public_subnet_cidr must lie inside vpc_cidr."
    }
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = { Name = "${var.name_prefix}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  tags = { Name = "${var.name_prefix}-public" }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# --- S3 gateway endpoint: all in-region S3 traffic, restricted to this account's buckets and named AWS objects ------
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "OwnAccountBuckets"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:*"
        Resource  = "*"
        Condition = { StringEquals = { "aws:ResourceAccount" = var.account_id } }
      },
      {
        Sid       = "AwsOwnedObjectsReadOnly"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = var.aws_owned_s3_object_arns
      },
    ]
  })

  tags = { Name = "${var.name_prefix}-s3" }
}

# --- Network ACL (stateless, defence in depth) ---------------------------------------------------------------------
resource "aws_network_acl" "public" {
  vpc_id     = aws_vpc.this.id
  subnet_ids = [aws_subnet.public.id]

  tags = { Name = "${var.name_prefix}-public" }
}

locals {
  # Inbound: replies to the host's own connections only (ephemeral ports); nothing below 1024 is ever allowed in.
  # Outbound: TCP 443 anywhere; TCP and UDP 7844 to the tunnel edge. Keyed by range, so a reordered list changes
  # nothing; a rule number is the range's position in the sorted list (adding a range can renumber, a reviewed plan).
  tunnel_cidrs = sort(var.tunnel_egress_cidrs)
  nacl_rules = merge(
    {
      "in-tcp-ephemeral" = { egress = false, rule_number = 100, protocol = "tcp", cidr = "0.0.0.0/0", from = 1024, to = 65535 }
      "out-tcp-443"      = { egress = true, rule_number = 100, protocol = "tcp", cidr = "0.0.0.0/0", from = 443, to = 443 }
    },
    { for i, c in local.tunnel_cidrs : "in-udp-ephemeral-${c}" => { egress = false, rule_number = 200 + i, protocol = "udp", cidr = c, from = 1024, to = 65535 } },
    { for i, c in local.tunnel_cidrs : "out-tcp-7844-${c}" => { egress = true, rule_number = 200 + i, protocol = "tcp", cidr = c, from = 7844, to = 7844 } },
    { for i, c in local.tunnel_cidrs : "out-udp-7844-${c}" => { egress = true, rule_number = 300 + i, protocol = "udp", cidr = c, from = 7844, to = 7844 } },
  )
}

resource "aws_network_acl_rule" "public" {
  for_each = local.nacl_rules

  network_acl_id = aws_network_acl.public.id
  egress         = each.value.egress
  rule_number    = each.value.rule_number
  protocol       = each.value.protocol
  rule_action    = "allow"
  cidr_block     = each.value.cidr
  from_port      = each.value.from
  to_port        = each.value.to
}

# --- Host security group: no inbound rule, outbound 443 and the tunnel only ----------------------------------------
data "aws_ec2_managed_prefix_list" "s3" {
  name = "com.amazonaws.${var.region}.s3"
}

# Terraform removes AWS's default allow-all egress rule when it creates the group; the rules below are the only ones.
resource "aws_security_group" "host" {
  #checkov:skip=CKV2_AWS_5:Attached to the staging host by AUT-108 (compute), which consumes host_security_group_id
  name        = "${var.name_prefix}-host"
  description = "Veda staging host: no inbound; outbound HTTPS and the Cloudflare tunnel only (AUT-101)"
  vpc_id      = aws_vpc.this.id

  tags = { Name = "${var.name_prefix}-host" }
}

resource "aws_vpc_security_group_egress_rule" "https" {
  security_group_id = aws_security_group.host.id
  description       = "HTTPS: AWS APIs, Cloudflare API, Turnstile, package repositories"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "https_s3" {
  security_group_id = aws_security_group.host.id
  description       = "HTTPS to S3 through the gateway endpoint"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  prefix_list_id    = data.aws_ec2_managed_prefix_list.s3.id
}

resource "aws_vpc_security_group_egress_rule" "tunnel" {
  for_each = { for p in setproduct(["tcp", "udp"], var.tunnel_egress_cidrs) : "${p[0]}-${p[1]}" => { protocol = p[0], cidr = p[1] } }

  security_group_id = aws_security_group.host.id
  description       = "Cloudflare tunnel edge (${upper(each.value.protocol)} 7844)"
  ip_protocol       = each.value.protocol
  from_port         = 7844
  to_port           = 7844
  cidr_ipv4         = each.value.cidr
}

# --- Flow logs (N6, owner decision C3): delivered to the logs bucket (AUT-103), no role passed ----------------------
resource "aws_flow_log" "vpc" {
  vpc_id                   = aws_vpc.this.id
  traffic_type             = var.flow_log_traffic_type
  log_destination_type     = "s3"
  log_destination          = var.flow_log_destination_arn
  max_aggregation_interval = 600

  destination_options {
    file_format        = "plain-text"
    per_hour_partition = true
  }

  tags = { Name = "${var.name_prefix}-vpc-flow" }
}
