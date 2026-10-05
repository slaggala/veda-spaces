# Consolidated plan proof: staging-core (AUT-101 … AUT-112)

- **Date:** 2026-10-05. **Commit:** the head of `infra/staging-platform-completion` (the pull request records it).
- **How:** `terraform plan` of `infra/terraform/envs/staging-core` exactly as committed, in a sandbox: local backend,
  fake credentials, every AWS call answered by a local mock (moto), `-refresh=false`, the test account manifest
  (`111122223333`). **Nothing reached AWS; nothing was created.** The plan JSON was then checked by the plan guard
  (`infra/scripts/check-plan.sh`), and each module's part of it is a test fixture under `infra/tests/fixtures/`.
- **Live plan:** a `10-infra-plan` run of the pull request plans the same root against the staging account through
  `veda-gh-plan`, after the owner approves the `staging-plan` environment. It is approval-gated and creates nothing.
  It is **not approved or applied** in this workstream.

## Summary

**`Plan: 159 to add, 0 to change, 0 to destroy.`** The plan guard passes: no destroy, everything in ap-south-1,
every role bounded at path `/`, no trust or resource policy outside the account.

| Module | AUT | Resources |
|---|---|---|
| budget | AUT-112 | 1 |
| kms | AUT-102 | 4 |
| storage | AUT-103 | 43 |
| network | AUT-101 | 27 |
| cloudtrail | AUT-104 | 5 |
| ecr | AUT-105 | 2 |
| runtime_iam | AUT-106 | 5 |
| ssm | AUT-107 | 27 |
| monitoring | AUT-110 | 32 |
| compute | AUT-108 | 6 |
| ses | AUT-111 | 5 |
| deploy | wiring | 2 |
| **Total** | | **159 (all create)** |

## Required properties

| Property | Result |
|---|---|
| Zero destroys | 0 delete, 0 replace (159 create) |
| Only approved changes | Every resource is one of the reviewed modules; nothing outside `module.*` |
| No public inbound access | **0** security-group ingress rules; NACL inbound only TCP 1024–65535 (replies) and UDP 1024–65535 from the two tunnel ranges; default security group, route table and NACL emptied |
| Region | 149 resources in ap-south-1; 10 global: IAM roles, policies, attachments, the instance profile, the budget |
| No Aurion or swing-trader-vm dependency | No planned resource names or references either (checked in `run.sh`) |
| Public intake disabled | No tunnel, DNS or Turnstile resource (AUT-201 … 203 not built); `deploy.enabled` is false; nothing is deployed |

## Protected resources (`prevent_destroy`)

| Resource | Why |
|---|---|
| `module.kms.aws_kms_key.this["data"]`, `["audit"]` | Losing a key loses every object and secret it encrypts |
| `module.storage.aws_s3_bucket.this[...]` (6) | Replicas, locked snapshots and anchors, evidence, logs |
| `module.cloudtrail.aws_cloudtrail.this` | The audit record (and `veda-boundary` forbids deleting it) |
| `module.ecr.aws_ecr_repository.api` | Deployed and rollback images |
| `module.compute.aws_ebs_volume.data` | The database volume |

## IAM roles and policies

| Role | Boundary | Trusted by | Permissions |
|---|---|---|---|
| `veda-stg-host` | `veda-boundary` | `ec2.amazonaws.com` | `AmazonSSMManagedInstanceCore`; `veda-stg-host-runtime` (exact resources; explicit Deny of administration) |
| `veda-stg-cloudtrail-logs` | `veda-boundary` | `cloudtrail.amazonaws.com` for `veda-stg-trail` only | `write-trail-log-group` (streams of `/veda/staging/cloudtrail`) |
| `veda-stg-dlm` | `veda-boundary` | `dlm.amazonaws.com` for this account | `service-role/AWSDataLifecycleManagerServiceRole` |

Key policies (AUT-102) additionally let the bootstrap's `veda-gh-deploy` and `veda-gh-evidence` use their bucket's key
through S3 only. No bootstrap change.

## Network rules

| Direction | Rule |
|---|---|
| Security group outbound | TCP 443 to `0.0.0.0/0`; TCP 443 to the S3 prefix list; TCP and UDP 7844 to `198.41.192.0/24` and `198.41.200.0/24` |
| NACL inbound | TCP 1024–65535 from `0.0.0.0/0`; UDP 1024–65535 from the two tunnel ranges |
| NACL outbound | TCP 443 to `0.0.0.0/0`; TCP and UDP 7844 to the two tunnel ranges |
| Routes | `0.0.0.0/0` to the internet gateway; S3 through the gateway endpoint (policy: account buckets; five named AWS-owned buckets read-only) |

## External dependencies

| Dependency | Used by | Control |
|---|---|---|
| AWS regional endpoints (SSM, ECR, KMS, STS, SES, CloudWatch, S3) | Host | HTTPS; S3 through the gateway endpoint |
| Amazon Linux repositories, SSM and ECR layer buckets | Host | S3 endpoint policy, exact bucket names |
| Docker Hub (`litestream/litestream`, pinned by digest) | Host | Digest pin in `docker-compose.yml` |
| GitHub releases (Docker Compose v5.6.0) | Host | SHA-256 pin in `host-setup.sh` |
| Cloudflare Turnstile (`challenges.cloudflare.com`) | API | HTTPS; secret seeded by the owner |
| Cloudflare tunnel edge | AUT-201 (not built) | TCP/UDP 7844 to the two published ranges |
| Owner mailbox | Alarms, SES sandbox | Sensitive in the plan; never committed |
