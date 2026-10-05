# Design package: AUT-101 (staging network foundation)

- **Date:** 2026-10-05
- **Status:** design for review. **Nothing is implemented, planned against AWS, applied or created.** Implementation
  starts once the owner decisions of §10 are recorded; applies stay disabled until OD-B7 and N-04-S are decided.
- **Scope:** the network of the single staging host (ADR-008): VPC, subnet, routes, security group, network ACL,
  endpoints, egress, flow logs. The host itself (AUT-108), keys (AUT-102), buckets (AUT-103) and the Cloudflare tunnel
  (AUT-201) are other stories; this package states what the network must give them.
- **Inputs:** [02 §12](../../architecture/02-platform-architecture.md) (single host, ECR, SSM deploy, Litestream to
  S3), [staging-critical-path-plan.md](../staging-critical-path-plan.md) §4.1, the API's outbound calls (below), the
  bootstrap's `veda-boundary`, guardrails and discovery, and the AUT-112 budget (**25 USD/month**, O16).

## 0. Findings that decide the design

| # | Finding | Consequence |
|---|---|---|
| F1 | The API calls **Cloudflare Turnstile** (`https://challenges.cloudflare.com/turnstile/v0/siteverify`, `api/veda/kernel/turnstile.py`) on every public enquiry | The host needs **internet** egress. No VPC endpoint reaches Cloudflare |
| F2 | The **Cloudflare tunnel** (`cloudflared`, AUT-201) dials Cloudflare's edge on port **7844** (QUIC/UDP, HTTP/2 over TCP as fallback) and its API on 443 | Internet egress again; **no inbound port** is needed (F7 of the critical path) |
| F3 | The Litestream image is pulled from **Docker Hub** (`litestream/litestream@sha256:…`, `api/deploy/docker-compose.yml`) | Internet egress, unless AUT-105 mirrors it to ECR (recommended, §8) |
| F4 | AWS calls from the host: S3 (Litestream, anchors, snapshots, ECR layers), ECR, KMS, STS, SES v2, SSM (three endpoints), CloudWatch Logs and metrics | All reachable over the internet; S3 for free through a gateway endpoint |
| F5 | The owner's staging budget is **25 USD/month** (AUT-112) | Network options with a NAT gateway (~41 USD) or interface endpoints (~8 USD each) exceed the whole budget before the host runs (§9) |
| F6 | `veda-boundary` confines every Veda role to ap-south-1; the account guardrails require IMDSv2; discovery accepts a VPC in ap-south-1 tagged `project=veda-spaces` (the provider's default tags) | No bootstrap change; the network carries the default tags |

**So an endpoint-only (no-internet) network is impossible** (F1–F3), and the budget (F5) rules out a managed NAT
gateway for staging. The recommended model (§6) is a **public subnet with no inbound access at all**, outbound
restricted by security group and network ACL, and S3 kept on the AWS network through a free gateway endpoint.

## 1. VPC design

| Item | Value | Why |
|---|---|---|
| VPC | `veda-stg-vpc`, **`10.60.0.0/20`** (4,096 addresses), ap-south-1 | Small, room for the reserved subnets; does not overlap common home/office ranges (`192.168.*`, `10.0.*`) or Docker's default bridge (`172.17.0.0/16`) |
| IPv6 | **None** | Not needed; one address family to reason about (option E, §6, rejected) |
| DNS | `enable_dns_support = true`, `enable_dns_hostnames = true` | Required for SSM and any later interface endpoint |
| Tenancy | default | |
| Default security group | Managed by Terraform with **no rules** (`aws_default_security_group`) | Nothing can use it by accident (checkov CKV2_AWS_12) |
| Default route table and default NACL | Managed with **no routes / deny all** | A subnet that is not explicitly associated reaches nothing |
| Flow logs | **All** traffic, to a CloudWatch log group `/veda/staging/vpc-flow`, retention 30 days (decision N6) | Evidence and incident review (FC-01, RR-09 attribution); a role `veda-stg-vpc-flow-logs` bounded by `veda-boundary`, trusted by `vpc-flow-logs.amazonaws.com` only |
| Tags | Provider default tags (`project`, `env`, `stack`, `managed-by`, `repository`) plus `Name` | Discovery recognises the VPC as Veda's (F6) |

The account's **default VPC** (if present in ap-south-1) is not used and not managed by Terraform. Removing it is an
owner choice (N7).

## 2. Subnet strategy

| Subnet | CIDR | AZ | Created by AUT-101 | Purpose |
|---|---|---|---|---|
| `veda-stg-public-a` | `10.60.0.0/24` | **one AZ, by AZ ID** (N5) | **Yes** | The host (AUT-108) |
| `veda-stg-private-a` | `10.60.1.0/24` | same AZ | No (reserved) | Only if the owner later chooses NAT (option B/D) |
| `veda-stg-public-b`, `-private-b` | `10.60.2.0/24`, `10.60.3.0/24` | a second AZ | No (reserved) | PostgreSQL gate, a second instance or a NAT instance in another AZ |

- **Single AZ** by design: one instance (ADR-008, OPS-006); no multi-AZ availability is claimed. Recovery is the EC2
  recovery alarm plus the rebuild runbook (AUT-108).
- **AZ by ID**, not name (`ap-south-1a` maps to different physical zones per account). The configuration names the AZ
  ID (for example `aps1-az1`); a plan-time precondition reads `aws_ec2_instance_type_offerings` and refuses the plan
  if the host's instance type is not offered there (the critical path's "t4g availability is checked by discovery").
- `map_public_ip_on_launch = false` on the subnet: the **host** asks for its public IPv4 explicitly (AUT-108), so
  nothing else launched there gets one by accident.

## 3. Route-table design

| Route table | Associated with | Routes |
|---|---|---|
| `veda-stg-public` | `veda-stg-public-a` | `10.60.0.0/20 → local`; `0.0.0.0/0 → igw`; **S3 prefix list `pl-…` → S3 gateway endpoint** (added by the endpoint) |
| Default (main) | none | `local` only (managed empty) |

- The S3 route is more specific than `0.0.0.0/0`, so **all in-region S3 traffic uses the gateway endpoint** and its
  endpoint policy (§5), not the internet.
- No IPv6 routes, no peering, VPN, transit gateway or second internet path. The plan guard refuses them (§11).

## 4. Security-group design

**`veda-stg-host`** (attached to the instance by AUT-108):

| Direction | Protocol / port | Peer | Why |
|---|---|---|---|
| Inbound | — | — | **No rule at all.** Admin is SSM Session Manager (outbound); browser traffic arrives through the tunnel (outbound) |
| Outbound | TCP 443 | `0.0.0.0/0` | AWS APIs (SSM, ECR, KMS, STS, SES, CloudWatch), Turnstile, Cloudflare API, package repositories |
| Outbound | TCP 443 | S3 prefix list | S3 through the gateway endpoint (explicit, so the rule survives a later narrowing of the 443 rule) |
| Outbound | TCP 7844, UDP 7844 | Cloudflare's published tunnel ranges (N8), or `0.0.0.0/0` | `cloudflared` to the Cloudflare edge (QUIC, HTTP/2 fallback) |

- No port 80, no 22, no outbound to other ports. DNS (Route 53 Resolver), NTP (`169.254.169.123`) and the instance
  metadata service are not subject to security groups.
- **Limit of every option:** a security group filters by address and port, not by host name. "443 to anywhere" lets a
  compromised host send HTTPS anywhere. Domain filtering needs AWS Network Firewall (~290 USD/month) or a proxy host;
  both are out of proportion for staging (§7). The compensating controls are: no inbound, IMDSv2, the host role's
  least privilege (AUT-106), the S3 endpoint policy, and flow logs.

**Default security group:** no rules (§1).

**Network ACL `veda-stg-public`** (defence in depth; stateless):

| Direction | Rule | Allows |
|---|---|---|
| Inbound | allow TCP 1024–65535 and UDP 1024–65535 from `0.0.0.0/0` | Replies to the host's own connections (ephemeral ports) |
| Inbound | deny everything else | Including 22, 3389, 80, 443: no service is reachable even if a security group is opened by mistake |
| Outbound | allow TCP 443, TCP 7844, UDP 7844 to `0.0.0.0/0` | The egress of §4 |
| Outbound | deny everything else | |

## 5. Endpoint strategy

| Endpoint | Type | Decision | Monthly cost |
|---|---|---|---|
| **S3** (`com.amazonaws.ap-south-1.s3`) | **Gateway** | **Yes** | Free |
| SSM, SSM Messages, EC2 Messages | Interface | No (internet path) | ~8 USD each |
| ECR API, ECR DKR | Interface | No | ~8 USD each |
| KMS, STS, Logs, Monitoring, SES | Interface | No | ~8 USD each |

**S3 gateway endpoint policy** (the only endpoint): allow S3 actions only on
- buckets of this account (`aws:ResourceAccount` = `813238078849`): Litestream, anchors, snapshots, artifacts,
  evidence (AUT-103); and
- the AWS-owned buckets the host needs: the ECR layer bucket of ap-south-1 and the Amazon Linux 2023 repository
  buckets (exact ARNs confirmed during implementation from AWS documentation).

Everything else in-region S3 is refused at the endpoint, so the host cannot copy data to another account's bucket in
Mumbai. (Out-of-region S3 would go over the internet; the host role allows no S3 action there and `veda-boundary`
denies every action outside ap-south-1 for Veda roles.)

Interface endpoints are **deferred, not forbidden**: they become worthwhile if the host moves to a private subnet
(production, or option B). Their policies would then restrict principals to this account.

## 6. Egress architecture options

| | **A. Public subnet, no inbound** (recommended) | B. Private subnet + NAT gateway | C. Private subnet + interface endpoints only | D. Private subnet + NAT instance | E. IPv6 egress-only |
|---|---|---|---|---|---|
| Internet for Turnstile, tunnel, Docker Hub | Yes (IGW) | Yes (NAT) | **No: does not work** (F1–F3) | Yes | Partly (depends on IPv6 support of every service) |
| Host has a public IPv4 | Yes (no inbound allowed) | No | No | No (the NAT instance has one) | No |
| Inbound exposure | None: SG with no inbound rule, NACL deny, no listening public service | None | None | NAT instance must be hardened | None |
| Moving parts | VPC, subnet, IGW, routes, SG, NACL, S3 endpoint | + NAT gateway, EIP, second route table | + 8–10 endpoints | + an instance to patch, `source_dest_check = false`, iptables, its recovery | IPv6 CIDR, EIGW; AWS endpoint IPv6 coverage to verify |
| Single point of failure | The host only | NAT gateway (zonal) | Endpoints (zonal) | The NAT instance | EIGW (regional, managed) |
| Network cost / month | **~4 USD** | ~45 USD | ~65–80 USD (and still needs NAT) | ~8 USD | ~0 USD |
| Fits the 25 USD budget | **Yes** | No | No | Yes, barely | Yes |

**Recommendation: A.** It is the only option that works (F1–F3), fits the budget (F5), and adds no host to operate.
The public IPv4 address is not an inbound path: the security group has no inbound rule, the NACL denies inbound
connections, and nothing listens publicly (the API binds `127.0.0.1:8000`; `cloudflared` dials out).

**Production** should revisit this: a private subnet with NAT (B) or a NAT instance (D) plus interface endpoints, once
the budget is a production budget. The module keeps the reserved private subnet CIDRs and an `egress_model` input so
that change is a reviewed configuration change, not a redesign.

## 7. NAT versus endpoint trade-offs

| Concern | Public IPv4 + IGW (A) | NAT gateway (B) | Interface endpoints |
|---|---|---|---|
| Inbound reachability | None by policy (SG, NACL); an address exists | None by construction | None |
| Outbound filtering | SG/NACL by IP and port | Same (NAT does not filter) | Per-service, with endpoint policies |
| Reaches Cloudflare | Yes | Yes | No |
| Keeps AWS traffic off the internet | S3 only (gateway) | S3 only (gateway) | Yes, per service |
| Cost (staging) | ~4 USD | ~45 USD + 0.056 USD/GB | ~8 USD per endpoint per AZ + data |
| Operations | None | None (managed) | None (managed) |
| Evidence | Flow logs show every outbound peer | Flow logs on the NAT ENI and the host | Endpoint and flow logs |

The security difference between A and B for this host is **the existence of a public address**, not exposure: both
filter outbound by address and port only, and both reach the same internet. A's risk is a misconfiguration that opens
inbound; the plan guard, the NACL and the tests close that (§11).

## 8. Cloudflare tunnel requirements (for AUT-201)

| Requirement | Network side (AUT-101) | Elsewhere |
|---|---|---|
| Outbound TCP and UDP 7844 to the Cloudflare edge | SG and NACL rules (§4) | `cloudflared` may force `--protocol http2` (TCP only) if UDP is ever blocked |
| Outbound TCP 443 to `api.cloudflare.com` (remotely managed tunnel) | 443 rule | Tunnel token as an SSM SecureString seeded by the owner (AUT-302), never in Terraform |
| DNS resolution of the edge host names | Route 53 Resolver (`enable_dns_support`) | |
| **No inbound port** | SG without inbound rules; NACL denies | |
| Origin | — | `http://127.0.0.1:8000` on the host (the API binds loopback) |
| Client IP | — | `VEDA_TRUSTED_PROXY_CIDRS` = the address `cloudflared` connects from (loopback, or the Docker bridge if it runs in a container) |
| `cloudflared` binary or image | 443 rule (Cloudflare package repository or Docker Hub) | Recommended: mirror the pinned `cloudflared` and Litestream images into ECR (AUT-105), so the host pulls only from AWS and Cloudflare's edge is the only non-AWS peer besides Turnstile |

Cloudflare publishes the tunnel edge address ranges. Restricting 7844 to them (N8) narrows egress further, at the cost
of updating the rule if Cloudflare changes them.

## 9. Cost estimate

Approximate on-demand list prices for ap-south-1 as known when this package was written. **Confirm them in the AWS
Pricing Calculator before the owner decides** (implementation step 1).

**Network only (per month):**

| Item | A (recommended) | B (NAT gateway) |
|---|---|---|
| VPC, subnet, route tables, IGW, SG, NACL | 0 | 0 |
| S3 gateway endpoint | 0 | 0 |
| Public IPv4 (0.005 USD/h) | 3.65 (host) | 3.65 (NAT EIP) |
| NAT gateway (~0.056 USD/h + ~0.056 USD/GB) | — | ~41 + data |
| Flow logs (a few hundred MB to CloudWatch) | < 1 | < 1 |
| Data out to the internet (staging volumes; AWS's free monthly allowance covers it) | ~0 | ~0 |
| **Total** | **~4–5 USD** | **~45–46 USD** |

**Whole staging run rate with A** (to show the budget, not only the network):

| Item | t4g.small host | t4g.medium host |
|---|---|---|
| EC2 (~0.0112 / ~0.0224 USD/h) | ~8.2 | ~16.4 |
| EBS gp3: root 8 GB + data 20 GB, plus daily snapshots | ~3.5 | ~3.5 |
| KMS keys (state key exists; AUT-102 adds ~3), 1 USD each | ~4 | ~4 |
| S3, CloudTrail (S3 data events on one bucket), CloudWatch logs and metrics | ~2–4 | ~2–4 |
| Network (A) | ~4–5 | ~4–5 |
| **Total** | **~22–25 USD** | **~30–33 USD** |

**The 25 USD budget is tight.** With a t4g.medium host (the critical path's size) the forecast alert at 100% will
fire every month; with a t4g.small (02 §12.2's example size) staging runs at about the limit. This is an owner decision
(N2, N3), recorded here because it decides whether option A's ~4 USD or option B's ~45 USD is even discussable.

## 10. Owner decisions

| # | Decision | Options | Recommendation | Blocks |
|---|---|---|---|---|
| **N1** | Egress model | A, B, D (C does not work; E not ready) | **A** | Implementation |
| **N2** | Host size (AUT-108, decided now for the cost model) | t4g.small, t4g.medium | t4g.small for staging, measured before the rehearsal | Cost model; the AZ precondition's instance type |
| **N3** | Staging budget | Keep 25 USD, or raise (for example 40 USD) | Keep 25 with t4g.small; raise to ~40 with t4g.medium | AUT-112 decision file |
| N4 | VPC CIDR | `10.60.0.0/20` or another | `10.60.0.0/20` | Implementation |
| N5 | AZ | An AZ ID where the host type is offered | The first of `aps1-az1`, `aps1-az3`, `aps1-az2` that offers it (checked at plan time) | Implementation |
| N6 | Flow logs | All or reject-only; retention | All, 30 days, CloudWatch Logs | Implementation |
| N7 | Default VPC in ap-south-1 | Keep, or delete with an owner session | Delete (unused attack surface; not Terraform's to manage) | Nothing (owner hygiene) |
| N8 | Tunnel egress | 7844 to Cloudflare's ranges, or to `0.0.0.0/0` | Cloudflare's ranges | Implementation (rule values) |
| — | OD-B7, N-04-S | (existing gates) | — | The first apply of anything |

## 11. Review requirements

**Plan guard additions** (`check-plan.sh`, with tests and mutations, as for AUT-112):
- refuse any security-group **ingress** rule in staging (`aws_security_group` ingress blocks,
  `aws_vpc_security_group_ingress_rule`, `aws_security_group_rule` of type ingress), and any ingress open to
  `0.0.0.0/0` or `::/0` in any case;
- refuse egress rules other than the decided ports (443/TCP, 7844/TCP+UDP);
- refuse NACL entries that allow inbound to ports below 1024;
- refuse `aws_vpc_peering_connection*`, `aws_vpn_*`, `aws_customer_gateway`, `aws_ec2_transit_gateway*`,
  `aws_ec2_client_vpn_*`, `aws_egress_only_internet_gateway`, IPv6 CIDR associations, and (under option A)
  `aws_nat_gateway` and `aws_eip`;
- refuse a subnet with `map_public_ip_on_launch = true`;
- refuse a VPC endpoint whose policy is unknown, the AWS default (full access), or allows S3 outside this account
  except the reviewed AWS-owned buckets;
- refuse a flow-log role trusted by anything but `vpc-flow-logs.amazonaws.com` (the existing trust rules already
  refuse other accounts).

**Tests:** `terraform test` for the module (CIDRs, one public subnet, routes, SG without ingress, NACL rules, endpoint
policy, flow logs, AZ precondition with a mocked offering list); `infra/tests/run.sh` checks for every guard rule;
checkov and tflint on the module (CKV2_AWS_11 flow logs, CKV2_AWS_12 default SG, CKV_AWS_130 subnet public IP).
Any checkov skip is inline and justified (for example CKV_AWS_158, log-group KMS key, until AUT-102).

**Reviews:**
1. Independent design review of this package (same process as AUT-112), before implementation.
2. Independent code review of the implementation, with the mutation check.
3. Plan proof: a `10-infra-plan` run with the expected counts (§12), the guard passing, nothing created.
4. Owner review of the plan text and the cost before the first apply.

## 12. Implementation plan

| Step | Work | Output |
|---|---|---|
| 1 | Confirm prices (Pricing Calculator) and the AWS-owned bucket ARNs for the endpoint policy; read-only `describe-availability-zones` / instance-type offerings through a plan | Values for N2–N5, N8 |
| 2 | Owner records N1–N8 | `infra/config/staging-network.json` (reviewed PR): `egress_model`, CIDRs, AZ ID, host instance type, flow-log settings, tunnel ranges |
| 3 | Module `infra/terraform/modules/network/` | VPC, default SG/RT/NACL managed empty, public subnet, IGW, route table, S3 gateway endpoint with policy, NACL, host SG, flow logs (log group, bounded role, `aws_flow_log`); outputs `vpc_id`, `public_subnet_id`, `host_security_group_id` for AUT-108 |
| 4 | Wire into `envs/staging-core` | `module "network"`; AZ precondition |
| 5 | Plan guard rules and tests (§11) | `check-plan.sh`, `run.sh`, mutation check |
| 6 | Review package, runbook, READMEs | `AUT-101-review-package.md` |
| 7 | Independent review; fixes | |
| 8 | Plan proof (PR run) | Expected below |
| 9 | First apply, after OD-B7 and N-04-S, together with or after AUT-112's | Evidence: CloudTrail `CreateVpc`, `CreateSubnet`, …; flow logs arriving |

**Expected plan for AUT-101 alone (option A):** about **15–17 to add, 0 to change, 0 to destroy** (VPC, default SG,
default route table, default NACL, subnet, IGW, route table, route, association, S3 endpoint, endpoint-route
association, NACL and its association, host SG and its egress rules, log group, flow-log role and policy, flow log).
The exact count is fixed by the implementation and stated in its review package. Nothing in the bootstrap changes:
`veda-gh-apply` already has `ec2:*`, `logs:*` and bounded IAM role creation; Mumbai and IMDSv2 are already enforced.

**Out of scope:** the instance, its role and its public IPv4 (AUT-108, AUT-106), keys (AUT-102), buckets (AUT-103),
the tunnel and DNS (AUT-201, AUT-202), image mirroring (AUT-105).
