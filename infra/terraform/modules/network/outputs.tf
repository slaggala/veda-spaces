output "vpc_id" {
  description = "The staging VPC."
  value       = aws_vpc.this.id
}

output "public_subnet_id" {
  description = "The host subnet (AUT-108)."
  value       = aws_subnet.public.id
}

output "availability_zone_id" {
  description = "The AZ ID chosen for the host subnet (the first preferred AZ that offers the host type)."
  value       = local.az_id
}

output "host_security_group_id" {
  description = "Security group for the host (AUT-108): no inbound, outbound 443 and the tunnel only."
  value       = aws_security_group.host.id
}

output "summary" {
  description = "What the plan creates, for the reviewer (the plan text)."
  value = {
    egress_model         = var.egress_model
    vpc_cidr             = var.vpc_cidr
    public_subnet_cidr   = var.public_subnet_cidr
    availability_zone_id = local.az_id
    host_egress          = concat(["tcp/443 0.0.0.0/0", "tcp/443 s3-prefix-list"], [for k, r in aws_vpc_security_group_egress_rule.tunnel : "${r.ip_protocol}/7844 ${r.cidr_ipv4}"])
    flow_logs            = "${var.flow_log_traffic_type} to ${var.flow_log_destination_arn}"
  }
}
