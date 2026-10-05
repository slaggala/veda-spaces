# AUT-002 evidence: first controlled bootstrap of `veda-staging`

- **Result:** **APPLIED** on 2026-10-03. 33 resources created, 0 changed, 0 destroyed. Every stop condition passed.
- **Account / region:** `veda-staging` (813238078849), member of `o-q9ji0hj18c`; ap-south-1 only.
- **Operator:** Srinivasulu Laggala, on the approved local workstation, following the local procedure (runbook §3,
  Option A) under the owner authorization of 2026-10-03
  ([AUT-002-bootstrap-authorization.md](../../implementation/staging/AUT-002-bootstrap-authorization.md)).
- **Code applied:** `main` at `9361d104fef8dcef608ac6e925157eb8896a5ae3` (PR #15), clean checkout, CI green.
- **Raw evidence:** held privately by the owner, not committed, because the repository is public and the files contain
  IP addresses and key IDs. This page records their SHA-256 (§7) so that any copy can be checked against it.

## 1. Timeline (UTC)

| Time | Step | Record |
|---|---|---|
| 17:00:16 | Temporary access key for `bootstrap-operator` created (by `org-admin` via `OrganizationAccountAccessRole`) | CloudTrail `CreateAccessKey` |
| 17:20:13 | Run started on the workstation (preflight passed: `make -C infra check`, `github-verify`, clean tree) | Operator log |
| 17:21:14 | `AssumeRole` of `bootstrap-owner` by `user/bootstrap-operator`, MFA `mfa/Bootstrap`, session `veda-bootstrap-20261003`, 3600 s, region-deny session policy attached; session expiry 18:21:14 | CloudTrail `AssumeRole` |
| 17:22:05 | Region guard proved: `DescribeAvailabilityZones` in us-east-1 refused (explicit deny in a session policy) | CloudTrail; operator log |
| 17:24:07–17:31:51 | Account inventory (PB-02): name and alias `veda-staging`, member of `o-q9ji0hj18c`, owner session, every enabled region scanned; only the 3 allowlisted identities | `account-inventory.json` |
| 17:37:46 | Plan made: digest `cf534e10f512e3b6cfe65869e3558a1c9d718016e484f91f5887ae50ba285c7f`, text digest `51c819a43c0cc20db4f19ae35288db1d8df43f60a7df4047c808fb25f174a709` | `bootstrap-plan.meta.json` |
| 17:37:48–17:38:03 | Plan guard passed; IAM simulation of the rendered boundary matched the review (7 probes) | Operator log; CloudTrail `SimulateCustomPolicy` |
| 17:40:46 | **Owner approval** of the plan digest | `approval.txt` |
| 17:45:35–17:45:50 | Apply of the approved digest (the re-rendered plan text is byte-identical to the reviewed text) | CloudTrail write events; `applying-plan.txt` |
| 17:46:35–17:46:47 | State migrated to `s3://veda-tfstate-813238078849/bootstrap/terraform.tfstate`; local copy removed; live bucket and key policies verified as reviewed | Operator log |
| ~17:48 | Post-apply checks (§4) | Operator log |
| 17:50:00–17:50:05 | Eight GitHub repository variables set; `github-verify` passed | `gh variable list` |
| after 17:50 | Temporary access key deactivated and deleted; `list-access-keys` empty | CloudShell output |

## 2. Approved plan

`Plan: 33 to add, 0 to change, 0 to destroy.` There were no replace, import or forget actions; every resource is in
ap-south-1; and the only account referenced is 813238078849.

| Group | Created |
|---|---|
| State (8) | Bucket `veda-tfstate-813238078849` (`force_destroy` false) with versioning, SSE-KMS, ownership controls, public-access block, policy and lifecycle; KMS key `e7422777-f464-4789-9825-0f7aa0c7da37` (rotation 365 days, 30-day deletion window) with alias `alias/veda-tfstate` |
| GitHub OIDC (1) | `token.actions.githubusercontent.com` |
| IAM (17) | `veda-gh-plan`, `veda-gh-apply`, `veda-gh-deploy`, `veda-gh-evidence`: path `/`, 3600 s, boundary `veda-boundary`; each trusts only `repo:slaggala/veda-spaces:environment:` + `staging-plan` / `staging-infra` / `staging` / `staging-evidence` as applied on 2026-10-03 (since 2026-10-04: immutable GitHub subject ID trust, `repo:slaggala@37840263/veda-spaces@1392733148:environment:<env>`, [AUT-002-trust-subject-reapply.md](../../implementation/staging/AUT-002-trust-subject-reapply.md)); 6 policies (`veda-boundary` and the 5 role policies); 7 attachments |
| Account guardrails (6) | S3 account public-access block; EBS encryption by default; EBS snapshot and AMI public-access blocks; instance metadata defaults (IMDSv2 required, hop limit 2); IAM Access Analyzer `veda-account-analyzer` |

State bucket policy: deny insecure transport, any other KMS key and access points. Only `role/bootstrap-owner` and the
account root may touch `bootstrap/*` or move state. The state key is administered only by `bootstrap-owner` and the
account root.

**One resource outside the plan:** `AWSServiceRoleForAccessAnalyzer`, created by AWS itself when the analyzer was
created (CloudTrail `CreateServiceLinkedRole`). Discovery ignores AWS service-linked roles (`/aws-service-role/`), so
later runs are not affected.

## 3. Security requirements of the authorization

| Requirement | Evidence |
|---|---|
| `bootstrap-owner` role only | All session events carry `assumed-role/bootstrap-owner/veda-bootstrap-20261003`; session issuer `role/bootstrap-owner` |
| MFA required | `AssumeRole` request carries `serialNumber` `arn:aws:iam::813238078849:mfa/Bootstrap`; the role's trust (read back after the run) allows only `user/bootstrap-operator` with `aws:MultiFactorAuthPresent` true and `aws:MultiFactorAuthAge` under 3600 |
| Temporary access key on the run day only | `CreateAccessKey` at 17:00:16, run day; `bootstrap-operator` had no key before (checked in CloudShell) |
| Key deleted after completion | `update-access-key --status Inactive`, `delete-access-key`; `list-access-keys` returns nothing |
| No root credentials | Root credentials were not used: the key was created through `org-admin` → `OrganizationAccountAccessRole`, the run used only `bootstrap-owner` |
| No permanent credentials | The bootstrap used only `ASIA…` session credentials, held in environment variables with the AWS config files disabled (`AWS_CONFIG_FILE`, `AWS_SHARED_CREDENTIALS_FILE` set to `/dev/null`); no key or secret stored in GitHub (0 secrets); the operator key was deleted |
| Mumbai only | us-east-1 refused 5 times (region-guard probes); all regional writes in ap-south-1; IAM (global) writes in us-east-1 as AWS records them |

CloudTrail on the session lists no unexpected calls. The non-success entries are all expected: the 5 region-guard
refusals; discovery's "not found" reads before the resources existed (`GetRole`, `GetBucketPolicy`,
`GetBucketCors`, `GetBucketLifecycle`, `GetAccountPublicAccessBlock`); and one `PutBucketOwnershipControls`
`OperationAborted` that the provider retried successfully, as is normal right after a bucket is created.

## 4. Post-apply checks (runbook §5)

| Check | Result |
|---|---|
| Bucket versioning | `Enabled` |
| Bucket encryption | `aws:kms`, the state key, `BucketKeyEnabled` false, SSE-C blocked |
| Bucket public-access block | all four true |
| State object | `bootstrap/terraform.tfstate`, 262,580 bytes, `aws:kms` with the state key |
| Key rotation | true, 365 days |
| `veda-gh-apply` | boundary `policy/veda-boundary`, max session 3600 |
| EBS encryption by default | true |
| Instance metadata defaults | `HttpTokens` required, hop limit 2 |
| Access Analyzer | `veda-account-analyzer` |
| Account public-access block | all four true |
| Local state | none left; backend is the S3 bucket |

## 5. GitHub

The repository variables set (none are secret): `AWS_ACCOUNT_ID`, `AWS_REGION`, `TF_STATE_BUCKET`,
`TF_STATE_KMS_KEY_ARN`, `AWS_ROLE_ARN_PLAN`, `AWS_ROLE_ARN_APPLY`, `AWS_ROLE_ARN_DEPLOY`, `AWS_ROLE_ARN_EVIDENCE`.
`CF_ACCOUNT_ID` and `CF_ZONE_ID` are not set (no Cloudflare token, OD-B3); they are needed before AUT-201.
`github-verify` passed afterwards.

## 6. CloudTrail record counts

| Export | Events |
|---|---|
| ap-south-1, user `veda-bootstrap-20261003` | 167 (17:21:52–17:49:28) |
| us-east-1, user `veda-bootstrap-20261003` | 136 (17:22:05–17:50:54): `CreateRole` 4, `CreatePolicy` 6, `AttachRolePolicy` 7, `CreateOpenIDConnectProvider` 1, `CreateServiceLinkedRole` 1, `SimulateCustomPolicy` 14 |
| `AssumeRole`, ap-south-1 / us-east-1 | 42 events in the window, one of them for `bootstrap-owner` / 0 (the call used the Mumbai endpoint) |
| `CreateAccessKey`, us-east-1 | 1 |

## 7. Raw evidence files (SHA-256)

| File | SHA-256 |
|---|---|
| `account-inventory.json` | `ea9896235331c95f4eaf0db99f0e7b89ec27a3cd78731e8eba9dd23302297e09` |
| `discovered.json` | `95e822dbcec49c18ab02a30faf90f7ae52dc6c6317a275d3f879eb4fcdd9b5cc` |
| `bootstrap-plan.txt` | `51c819a43c0cc20db4f19ae35288db1d8df43f60a7df4047c808fb25f174a709` |
| `applying-plan.txt` (identical to the reviewed text) | `51c819a43c0cc20db4f19ae35288db1d8df43f60a7df4047c808fb25f174a709` |
| `bootstrap-plan.meta.json` | `44586f278e3f55843dae9d129b1b26f7c55a60a9d6ec728bec3f4093b18a4dc9` |
| `bootstrap-plan.json` | `df6db30cc77dc748f595a765f62de9065f6495920e8fecdaa39505640cac73f2` |
| `approval.txt` | `16a540318b91e5bd631dceeb68a13b51dd7e85db89b4e828a44874a700cbb92b` |
| `bootstrap-outputs.json` | `437455e463a9c871403814d6f350b6b3e282be105e6d6e0df34dd865fb7f63cd` |
| `cloudtrail-ap-south-1-veda-bootstrap-20261003.json` | `cb2bcc5067a33db22a30fe8954b7dcdbec66550d9a3d10479ca50f1585c9b12d` |
| `cloudtrail-us-east-1-veda-bootstrap-20261003.json` | `2666ae6258c5653d5257e3a226ada20e0204dd75c600143b01e516a81d3ee56a` |
| `cloudtrail-assumerole-ap-south-1.json` | `cf961934e865a26f5b46ad3ca9b0f98e9c653f7e064e86dfffbdb01e0b197c59` |
| `cloudtrail-assumerole-us-east-1.json` | `450e0ee55f895199f4b307725acfc2edd9d1a11aa63b457c0ed5aa221be0476f` |
| `cloudtrail-createaccesskey.json` | `51601168d4c69d87d1a533a14eab7739b5ff9eceac872619e67118156d1c8471` |
| `aut002-cloudtrail.tgz` (CloudShell export bundle) | `536fbcbc4b1caf777ff81e4193874beb36c33310db5b74ba51cbde23f08d42c2` |

These files are retained by the owner until the evidence bucket (AUT-103) exists. CloudTrail Event History keeps
these events for 90 days, until about 2027-01-01 (OD-B6).

## 8. What this unblocks, and what it does not

- **Unblocked:** the infrastructure workflows (AUT-301) can now assume the `veda-gh-*` roles through OIDC, using the
  repository variables.
- **Still gated:** no workflow may assume `veda-gh-apply` until OD-B7 (the trust-writing gap) is decided; RR-C
  comes before AUT-301. RR-A is closed by immutable GitHub subject ID trust (re-applied 2026-10-04). AUT-101 onward has not started.
