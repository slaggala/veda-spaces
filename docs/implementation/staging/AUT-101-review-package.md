# Review package: AUT-101 (staging network foundation)

- **For:** independent review, the same process as AUT-112.
- **Scope:** the network module and its wiring into `envs/staging-core`, the plan-guard rules for the network, tests,
  and one bootstrap policy line (§3, B8). **Nothing is applied and no AWS resource is created by this change.** Applies
  stay disabled until OD-B7 and N-04-S are decided.
- **Design:** [AUT-101-design-package.md](AUT-101-design-package.md). This pull request (#21) contains PR #20's only
  commit unchanged (its first commit). The design document differs only in its Status header (updated here to
  record the owner decisions and point to §10); the one other file of PR #20
  (`infra/terraform/modules/README.md`) is updated here from "designed" to "written". **PR #20 is superseded** and
  should be closed without merging. The design was not reviewed separately: this review covers design and
  implementation together.
- **Owner decisions (2026-10-05):** N1 egress model **A** (public subnet, no inbound access, outbound-only Cloudflare
  tunnel); N2 host **t4g.small**; N3 budget stays **25 USD**; N4–N8 the design's defaults.

## 1. Files

| File | What it is |
|---|---|
| `infra/config/staging-network.json` | The decision (N1–N8): model A, `10.60.0.0/20`, subnet `10.60.0.0/24`, AZ preference `aps1-az1, aps1-az3, aps1-az2` and `az_id` (pinned after the first plan), `t4g.small`, flow logs `ALL` / 30 days, tunnel ranges, the five AWS-owned S3 buckets |
| `infra/terraform/modules/network/` (`main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `tests/network.tftest.hcl`) | The network: 30 resources (§2) and 14 offline tests |
| `infra/terraform/envs/staging-core/main.tf`, `variables.tf`, `outputs.tf`, `tests/core.tftest.hcl` | `module "network"`; output `network` (the summary the plan text shows); 1 new test |
| `infra/scripts/check-plan.sh` | Network rules (§4) |
| `infra/terraform/bootstrap/roles.tf` | `vpc-flow-logs.amazonaws.com` added to the services `veda-gh-apply` may pass Veda roles to (B8) |
| `infra/tests/run.sh`, `infra/tests/fixtures/aut101-network-plan.json` | 68 new checks; the fixture is the network part (changes and configuration) of a real plan of the root (§5) |
| `infra/Makefile` | `make test` also runs the tests of every module that has them |

## 2. What the module creates (30 resources)

| Resource | Count | Notes |
|---|---|---|
| `aws_vpc` | 1 | `10.60.0.0/20`, DNS support and host names, IPv4 only |
| `aws_default_security_group`, `aws_default_route_table`, `aws_default_network_acl` | 3 | Adopted and emptied: no rule, no route, no allow |
| `aws_subnet` | 1 | `10.60.0.0/24` in the first preferred AZ ID that offers `t4g.small` (read at plan time); `map_public_ip_on_launch = false` |
| `aws_internet_gateway`, `aws_route_table`, `aws_route`, `aws_route_table_association` | 4 | `0.0.0.0/0` → IGW |
| `aws_vpc_endpoint` (S3 gateway) | 1 | Policy: `s3:*` only where `aws:ResourceAccount` is the account; `s3:GetObject` only on five AWS-owned buckets of ap-south-1: ECR layers, Amazon Linux 2023 repositories, SSM Agent updates (`amazon-ssm-`), SSM document modules (`aws-ssm-`), Distributor (`-birdwatcher-prod`). Patch Manager is not used (its buckets carry a regional suffix): the host is patched with `dnf` (AUT-108); the CloudWatch agent is installed with `dnf` |
| `aws_network_acl` | 1 | Attached to the subnet; inline rules none |
| `aws_network_acl_rule` | 8 | In: TCP 1024–65535 from anywhere, UDP 1024–65535 from the two tunnel ranges. Out: TCP 443 anywhere, TCP and UDP 7844 to the two tunnel ranges. Keyed by range (a reordered list changes nothing) |
| `aws_security_group` (`veda-stg-host`) | 1 | No inline rules; Terraform removes AWS's default allow-all egress |
| `aws_vpc_security_group_egress_rule` | 6 | TCP 443 to `0.0.0.0/0`; TCP 443 to the S3 prefix list; TCP and UDP 7844 to `198.41.192.0/24` and `198.41.200.0/24`. **No ingress rule exists** |
| `aws_cloudwatch_log_group` | 1 | `/veda/staging/vpc-flow`, 30 days |
| `aws_iam_role` + `aws_iam_role_policy` | 2 | `veda-stg-vpc-flow-logs`, `veda-boundary`, trusted only by `vpc-flow-logs.amazonaws.com` for this account's flow logs; writes only that log group |
| `aws_flow_log` | 1 | VPC, `ALL`, 10-minute aggregation |

The host (AUT-108) attaches `host_security_group_id` and requests its own public IPv4. Nothing in AUT-101 gives any
resource an address.

## 3. Design decisions for review

| # | Decision | Why |
|---|---|---|
| B1 | Model A exactly as designed; `egress_model` is an input that accepts only `A` | B or D later is a reviewed change of the decision file, the module and the guard together |
| B2 | AZ by **ID**, chosen at plan time from `aws_ec2_instance_type_offerings`; a precondition refuses the plan if no candidate AZ offers the type. Once the first plan shows the chosen AZ, it is **pinned** in the decision file (`az_id`), so later changes of offerings or preferences cannot replace the subnet | `ap-south-1a` is a different zone per account; the plan role can read offerings (`ReadOnlyAccess`) |
| B3 | Security-group rules as separate `aws_vpc_security_group_egress_rule` resources, none inline | Each rule is visible and checkable in the plan; the guard refuses inline rules that are not 443/7844 |
| B4 | NACL rules as separate resources, the subnet attached on the NACL itself | Same reason; attaching inline is what checkov recognises (CKV2_AWS_1) |
| B5 | Inbound UDP replies only from the tunnel ranges; inbound TCP replies from anywhere | UDP is only QUIC to the tunnel; TCP replies come from every HTTPS peer |
| B6 | Endpoint policy: account buckets by `aws:ResourceAccount`, AWS-owned objects by exact bucket, read-only | Requests to the **regional S3 endpoints of ap-south-1** pass the gateway endpoint (the prefix-list route is more specific than `0.0.0.0/0`), so through them the host cannot read or write another account's bucket. It does **not** cover S3 Transfer Acceleration, Multi-Region Access Points or S3 in other regions, which leave over the internet: "443 to anywhere" remains the accepted exfiltration limit of every option (design §4) |
| B7 | Flow logs to CloudWatch Logs with the service key (checkov CKV_AWS_158 skipped until AUT-102's keys exist); 30-day retention (CKV_AWS_338 skipped: owner decision N6) | The decided destination; the skips are inline and justified |
| B8 | **Bootstrap change:** `vpc-flow-logs.amazonaws.com` added to `PassVedaRolesToStagingServices` | `aws_flow_log` passes `veda-stg-vpc-flow-logs` to the flow-logs service; without this line the first apply fails at `CreateFlowLogs` (`iam:PassRole` denied). It still passes only `veda-*` roles, which carry `veda-boundary`. **The bootstrap must be re-applied by the owner before AUT-101's first apply** (expected plan: 0 to add, 1 to change — `aws_iam_policy.apply_iam` — 0 to destroy) |
| B9 | Plan text: root output `network` summarises the model, CIDRs, AZ, outbound rules and flow logs | The reviewer of an apply reads the network from the plan text |

## 4. Plan guard additions (`check-plan.sh`)

Refused on create or update, for any root:
- **Inbound:** `aws_vpc_security_group_ingress_rule`; `aws_security_group_rule` of type ingress; inline `ingress` on a
  security group; any rule in the default security group.
- **Outbound:** anything but TCP 443, or TCP/UDP 7844 to a known range that is not `0.0.0.0/0`; all protocols; IPv6
  destinations (separate rules, legacy rules and inline rules).
- **NACLs:** an allow rule for all protocols; an inbound allow below port 1024; an IPv6 rule; any allow rule in the
  default NACL.
- **Routes:** any route in the default route table; a route to a NAT gateway, peering, transit gateway, egress-only
  gateway, carrier or local gateway, Cloud WAN or a network interface; an IPv6 route.
- **Subnet / VPC:** a subnet that assigns public or IPv6 addresses; an IPv6 VPC.
- **Other paths:** NAT gateways, elastic IPs, peering, VPN, customer gateways, Direct Connect, transit gateways, client
  VPN, egress-only gateways, IPv6 CIDR associations, `aws_vpc_endpoint_policy` and endpoint subnet associations.
- **Endpoints:** anything but the S3 gateway endpoint; an S3 endpoint policy that is unknown at plan time, absent (the
  AWS default allows everything), uses `NotAction`/`NotResource`/`NotPrincipal`, or has an Allow statement that is
  neither limited to the account (`aws:ResourceAccount`) nor `s3:GetObject` on the AWS-owned objects of ap-south-1.

**Added after the independent review (§11):** every destination of an inline rule is checked, and an update of a
group with inline rules (a prefix-list rule has no CIDR) no longer crashes the guard; an `aws_route` may set only an
IPv4 destination and a gateway, and may not target the main or default route table; inline routes, main-route-table
associations, Instance Connect endpoints, VPC Lattice, Network Manager, all Direct Connect and Route 53 Resolver
endpoints are refused; a rule attached to the default security group is refused; an instance without a subnet is
refused; the flow-logs service may assume a role only with `aws:SourceAccount` = the account; the AWS-owned buckets are
matched exactly. The route and default-group rules read the **configuration** of the plan, so they hold when the plan
cannot know a reference (for example `aws_vpc.this.main_route_table_id`).

The rules are generic: they apply to every later stack, so AUT-108 cannot add an inbound rule or a NAT without a
reviewed guard change.

## 5. Tests

**`terraform test`:**
- `modules/network`: **14 passed** — VPC and subnet; routes and the empty default route table; the host group's rules
  (443 anywhere, 443 to the S3 prefix list, exactly four tunnel rules on 7844 to the two ranges); NACL (inbound only
  ephemeral ports, outbound only 443 and 7844, no all-protocol rule); endpoint policy (two statements, account
  condition, read-only AWS objects); flow-log role (name, boundary, trust); refusals: no preferred AZ offers the type,
  subnet outside the VPC, model other than A, tunnel open to everyone, a pinned AZ without the type; the fallback to
  the next preferred AZ; a pinned AZ used; NACL rules keyed and numbered by range whatever the list order.
- `envs/staging-core`: **8 passed** (1 new: the committed decision reaches the module).
- `bootstrap`: 33 passed (unchanged).

**`infra/tests/run.sh`: 545 passed, 0 failed** (477 on `main`; 68 new). The guard checks start from a **real plan** of
the root (sandboxed: local backend, a local AWS mock answering the two plan-time reads, nothing reached AWS), saved as
`infra/tests/fixtures/aut101-network-plan.json`; each check changes one thing:
- the real plan passes; it has the 30 network creates;
- refused: inbound rules (separate, legacy, inline), a default-group rule, outbound on all protocols or another port,
  the tunnel to `0.0.0.0/0`, IPv6 outbound, an inline outbound rule to another port; a legacy 443 rule passes;
- refused: NACL inbound SSH, all protocols, IPv6, an allow in the default NACL, an inline inbound 443;
- refused: a default-route-table route, a route to a NAT gateway, an IPv6 route, a public-IP subnet, an IPv6 subnet,
  an IPv6 VPC;
- refused: NAT gateway, EIP, peering, transit-gateway attachment, egress-only gateway, VPN, client VPN, separate
  endpoint policy;
- refused: an interface endpoint, a gateway endpoint for another service, an endpoint policy unknown, absent, open to
  all S3, for another account, extended to another bucket, allowing writes to AWS objects, using `NotResource`, or
  naming another region's ECR bucket;
- review fixes: an update of the host group with inline rules passes (M1); an inline tunnel rule with a second open
  range, a route into the main route table, a route to a network interface, an IPv6 route, inline routes (plan and
  configuration), a main-route-table association, a rule on the default group, a flow-log role without or with another
  `aws:SourceAccount`, a look-alike Amazon Linux bucket, another region's SSM bucket, five more network types and an
  instance without a subnet are refused; the SSM buckets and an instance in a subnet pass;
- the committed decision (A, t4g.small, CIDRs, flow logs, tunnel ranges), the root wiring, the bootstrap line (inside
  the PassRole statement), and `make test` covering the module.

**Linters:** tflint and checkov on the module: 38 passed, 0 failed, 3 skipped (CKV_AWS_158, CKV_AWS_338, CKV2_AWS_5:
the group is attached by AUT-108), each inline and justified.

**Mutation check:** §6.

## 6. Mutation results

Each control was removed on its own in a copy of the repository tree and the suites re-run. **All 16 are detected.**

| # | Control removed | Detected by |
|---|---|---|
| G1 | Guard refuses inbound security-group rules | 2 checks |
| G2 | Guard limits outbound to 443 and the tunnel | 4 checks |
| G3 | Guard refuses NACL inbound below 1024 | 1 check |
| G4 | Guard refuses NAT, EIP, peering, VPN, transit gateway, … | 8 checks |
| G5 | Guard checks the S3 endpoint policy | 6 checks |
| G6 | Guard refuses a subnet assigning public addresses | 1 check |
| G7 | Guard refuses routes in the default route table | 1 check |
| G8 | Guard refuses rules in the default security group | 1 check |
| T1 | Subnet gives no public address (mutated to `true`) | 1 module test |
| T2 | Endpoint policy limited to the account (condition widened) | 1 module test |
| T3 | Tunnel ranges may not be `0.0.0.0/0` (validation removed) | 1 module test |
| T4 | Plan refused when no preferred AZ offers the type (precondition always true) | 1 module test |
| T5 | NACL inbound only from port 1024 (mutated to 22) | 1 module test |
| T6 | Committed flow logs `ALL` (mutated to `REJECT`) | 1 root test (a `run.sh` check also covers it) |
| T7 | Committed egress model `A` (mutated to `B`) | 1 check (the module validation and the root test also cover it) |
| T8 | Bootstrap passes roles to VPC flow logs (line removed) | 1 check |

## 7. Cost validation

Prices from the AWS Price List API for ap-south-1 (`AmazonVPC`, `AmazonEC2` version 20260925174521, `awskms`,
`AmazonCloudWatch`), read on 2026-10-05; 730 hours per month.

| Price (verified) | USD |
|---|---|
| Public IPv4 address in use | 0.005 / hour |
| t4g.small Linux on demand | 0.0112 / hour |
| t4g.medium Linux on demand | 0.0224 / hour |
| NAT gateway | 0.056 / hour + 0.056 / GB |
| Interface VPC endpoint | 0.013 / hour per AZ + 0.01 / GB |
| gp3 storage | 0.0912 / GB-month |
| EBS snapshot storage | 0.05 / GB-month |
| KMS customer-managed key | 1.00 / key-month |
| Vended logs (flow logs) ingested to CloudWatch Logs | 0.50–0.67 / GB (first 10 TB) |
| CloudWatch Logs storage | 0.03 / GB-month |

**AUT-101 alone:** VPC, subnet, routes, IGW, security group, NACL and the S3 gateway endpoint are free. Flow logs of
one quiet host are well under 1 GB a month: **< 0.50 USD**. The public IPv4 address belongs to the host (AUT-108).

**Staging run rate with model A and t4g.small (monthly):**

| Item | USD |
|---|---|
| EC2 t4g.small (0.0112 × 730) | 8.18 |
| Public IPv4 (0.005 × 730) | 3.65 |
| EBS gp3: 8 GB root + 20 GB data (28 × 0.0912) | 2.55 |
| EBS snapshots (incremental, ~5 GB) | ~0.25 |
| KMS: the state key + ~3 AUT-102 keys | ~4.00 |
| Flow logs | < 0.50 |
| CloudWatch agent logs, metrics, alarms (AUT-110), S3, CloudTrail data events (AUT-104) | ~2–3 |
| Budget (AUT-112) | 0 |
| **Total** | **~21–22 USD** |

**For comparison:** a NAT gateway alone is 40.88 USD/month (B); each interface endpoint 9.49 USD/month; t4g.medium
instead of small adds 8.18 USD.

**Consequence for the budget:** staging fits the 25 USD limit with ~3 USD of margin, but the forecast will sit around
21–22 USD, **above the 80% alert (20 USD)**. Expect the 80% forecast alert every month once the host runs (§9, C1).

## 8. Expected plan proof

A `10-infra-plan` run of this branch (pull request or `main`) must show **`Plan: 31 to add, 0 to change, 0 to
destroy.`**: the 30 network resources plus the AUT-112 budget, which is planned but not applied yet. Once the budget
is applied, AUT-101 alone is 30. The output `network` shows model A, `10.60.0.0/20`, `10.60.0.0/24`, the AZ ID, the six
outbound rules and `ALL, 30 days`. The plan guard passes and nothing is created. The sandbox plan of the same root gave
exactly that count.

## 9. Owner decisions and actions remaining

| # | Item | Needed before |
|---|---|---|
| **C1** | The forecast (~21–22 USD) is above the 80% alert (20 USD): accept a monthly 80% alert, or move it (for example to 90%) | The host runs (AUT-108); optional |
| **C2** | **Re-apply the bootstrap** for B8 (one in-place policy update), by the controlled owner procedure used on 2026-10-04 | AUT-101's first apply |
| C3 | Alternative to C2: flow logs to S3 in the AUT-103 evidence bucket (no role to pass, no bootstrap change), changing N6 | Instead of C2 |
| C4 | N7: delete the default VPC of ap-south-1 with an owner session, if present | Optional hygiene |
| — | OD-B7, N-04-S | The first apply |

**To verify on the first host (AUT-108):** the Amazon Linux 2023 repository bucket of ap-south-1. AWS documents the
form `al2023-repos-<region>-de612dc2`; the policy uses `al2023-repos-ap-south-1-de612dc2`. If `dnf` fails through the
endpoint, the decision file and the guard's bucket list are corrected in a reviewed pull request.

**Conditions for AUT-108 (from the review):** the instance sets `subnet_id` (enforced by the guard) and, until N7 removes
the default VPC, nothing may be launched without one; the host MTU stays 1500 (ICMP "fragmentation needed" is not
allowed in); after the first plan, `az_id` is pinned in the decision file.

## 10. Deviations from the design package

| # | Design | Implementation | Why |
|---|---|---|---|
| D1 | "About 15–17 to add" (§12) | 30 resources | Every NACL and security-group rule is its own resource (B3, B4); counted from a real sandbox plan |
| D2 | Interface endpoints ~8 USD/month (§5, §9) | 9.49 USD/month (0.013 USD/h) | Verified price (§7); model A uses none, so no cost effect |
| D3 | Flow-log role "bounded by veda-boundary" (§1) | Same, plus one bootstrap line (B8) | The apply role could not pass a role to `vpc-flow-logs.amazonaws.com`; found while implementing |
| D4 | NACL inbound TCP and UDP 1024–65535 from anywhere (§4) | UDP replies only from the two tunnel ranges | UDP is only the tunnel (QUIC); narrower |
| D5 | Separate NACL association | Subnet attached on the NACL (`subnet_ids`) | Checkov CKV2_AWS_1 recognises only the inline form; one resource fewer |
| D6 | Guard: "a flow-log role trusted by anything but `vpc-flow-logs.amazonaws.com`" (§11) | The flow-logs service may assume a role only with `aws:SourceAccount` = the account; other trust rules unchanged | The confused-deputy condition is the part that matters; implemented after the review |
| D7 | Endpoint policy: "ECR layers and Amazon Linux repositories" (§5) | Also the three SSM buckets (agent, documents, Distributor) | Found by the independent review (M2): Session Manager works without them, agent updates and Distributor do not |

## 11. Independent review (2026-10-05)

A fresh-context reviewer ran `make check`, planned the root against a local AWS mock, applied it to the mock and
re-planned (no perpetual diff), planned 16 realistic mutations through the real provider and ran the guard on them.
Verdict: **CERTIFIED WITH CONDITIONS** (M1 before merge; M2 fixed or accepted before AUT-108). Phase 0 confirmed.
Every finding has been handled in this pull request:

| # | Finding | Handling |
|---|---|---|
| M1 (major) | jq precedence bug: an update of a group with inline rules (a prefix-list rule without CIDR) crashed the guard | **Fixed**, with an update-shaped check; mutation R1 |
| M2 (major) | The S3 endpoint blocked the SSM buckets (agent updates, Distributor) | **Fixed:** the three SSM buckets added to the decision and to the guard's exact list; Patch Manager not used (host patched with `dnf`) |
| m1 | Inline egress checked only the first CIDR | **Fixed** (every destination); mutation R1 |
| m2 | Routes bypassable (inline routes, main route table, association, unknown ENI target) | **Fixed** with configuration-based checks; mutations R2, R3, R8 |
| m3 | Rules on the default security group not refused | **Fixed** (configuration); mutation R4 |
| m4 | Flow-log trust rule of the design not implemented | **Fixed** (`aws:SourceAccount`); D6; mutation R5 |
| m5 | Amazon Linux bucket regex accepted any suffix | **Fixed:** exact bucket names; mutation R6 |
| m6 | B6 overstated the S3 control | **Corrected** (§3 B6) |
| m7 | AZ recomputed on every plan (replacement risk) | **Fixed:** `az_id` pin, used when set; condition for AUT-108 |
| m8 | NACL rules keyed by list index | **Fixed:** keyed by range, numbered by sorted position |
| m9 | Gaps in the forbidden network types | **Fixed:** five more types and prefixes |
| m10 | An instance without a subnet lands in the default VPC | **Fixed** in the guard; mutation R7; N7 stays recommended |
| Nit | "identical" design document | **Corrected** (header) |
| Notes | ICMP fragmentation, T6/T7 counts, weak grep tests, cost items not modelled | MTU condition for AUT-108 (§9); counts corrected (§6); PassRole check now reads the statement; S3 requests, KMS requests and ECR storage go into the integrated cost report |

## 12. Mutations of the review fixes

All 8 are detected.

| # | Control removed | Detected by |
|---|---|---|
| R1 | Every destination of an inline rule (mutated to the first only) | 1 check |
| R2 | An `aws_route` sets only destination and gateway | 2 checks |
| R3 | No route into the main or default route table | 1 check |
| R4 | No rule on the default security group | 1 check |
| R5 | Flow-log trust limited by `aws:SourceAccount` | 2 checks |
| R6 | AWS-owned buckets matched exactly (mutated to a prefix) | 3 checks |
| R7 | No instance without a subnet | 1 check |
| R8 | No inline routes (plan form) | 1 check (the configuration form has its own check) |

