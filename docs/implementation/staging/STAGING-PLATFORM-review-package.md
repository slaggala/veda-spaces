# Consolidated review package: staging platform completion (AUT-102 … AUT-111)

- **For:** one independent integrated review of every module below. Each module gets its own verdict (CERTIFIED,
  CERTIFIED WITH CONDITIONS, NOT CERTIFIED); a finding in one module does not reopen another.
- **Branch:** `infra/staging-platform-completion`, one dependency-ordered commit per module (§2).
- **State:** implementation only. **Nothing is applied, no AWS resource is created, Veda is not deployed and public
  lead intake stays disabled.** Applies stay disabled by the apply gate (OD-B7, N-04-S) and by the decision gate (§3).
- **Base:** `main` after PR #21 (AUT-101 network), AUT-112 (budget) and AUT-301 (plan/apply workflows).
- **Owner decisions of 2026-10-05:** C1 keep the budget alerts (80% and 100% forecast); C2 the bootstrap is re-applied
  before the first AUT-101 apply; C3 VPC flow logs go to S3; C4 the default VPC stays for now.

## 1. Architecture summary

One Graviton host (t4g.small, Amazon Linux 2023) in the AUT-101 public subnet with no inbound access, running the
API, worker, scheduler and Litestream in Docker (02 §12). State lives on an encrypted data volume and replicates to
S3; nightly snapshots and anchors are Object-Locked; every AWS call is audited by CloudTrail; logs and alarms go to
CloudWatch and an SNS topic; email goes through SES in sandbox. The host is managed only through SSM; the image comes
from ECR; configuration comes from SSM parameters; secrets are seeded by the owner (AUT-302), never by Terraform.

```mermaid
flowchart LR
  KMS[AUT-102 KMS: data, audit] --> S3[AUT-103 buckets]
  KMS --> CT[AUT-104 CloudTrail]
  S3 --> CT
  KMS --> ECR[AUT-105 ECR]
  S3 --> IAM[AUT-106 runtime IAM]
  KMS --> IAM
  ECR --> IAM
  IAM --> SSM[AUT-107 SSM]
  S3 --> SSM
  KMS --> MON[AUT-110 monitoring]
  SSM --> MON
  NET[AUT-101 network] --> EC2[AUT-108 compute]
  IAM --> EC2
  MON --> EC2
  KMS --> EC2
  SES[AUT-111 SES] --> SSM
  EC2 --> DEP[deployment wiring]
  ECR --> DEP
  SSM --> DEP
```

## 2. Commits

| # | Commit | AUT | Protected requirements |
|---|---|---|---|
| 1 | KMS | AUT-102 | TG-02 (MFA secrets under a real KMS key), F7 (no cross-account use), region confinement |
| 2 | Buckets and Object Lock; flow logs to S3 (C3) | AUT-103, AUT-101 | OPS-002 (Litestream), RR-14 (snapshots), SEVT-007 and FC-01 (anchors), evidence, F2/F7 (no public or foreign access), N6 |
| 3 | CloudTrail | AUT-104 | F6 (audit cannot be weakened), FC-01 and RR-09 attribution, LOG-* tamper evidence |
| 4 | ECR | AUT-105 | IR-13 and SEC-007 (the tested image is the deployed image), RR-14 (deploy and rollback by tag) |
| 5 | Runtime IAM | AUT-106 | Least privilege (05 §9.6, F1), RR-03 (bounded roles at path `/`), FC-01 (anchors never altered), RR-09 (the host is not a custodian) |
| 6 | SSM | AUT-107 | SEC-005 and PLAT-008 (no secret in code or Git), F6 (staging start configuration), RR-09 (session transcripts) |
| 7 | Monitoring foundations | AUT-110 | LOG-005/006 and 02 §9 alerts, RG-5, RR-14 (snapshot heartbeat), FC-01 (anchor failures), NOTIF-008 (notification failures visible, lead kept), cost (bounded metrics) |
| 8 | Compute and EBS | AUT-108 | ADR-008 (one host), OPS-006/007 (single instance, dedicated encrypted volume, daily snapshots), IMDSv2 (F6), SSM-only access, egress model A, cost (credits capped) |
| 9 | SES | AUT-111 | NOTIF-* (email through SES in staging, F6), NOTIF-008 (a failed email never rolls back a lead), sender reputation (bounce and complaint suppression) |

## 3. Decisions

`infra/config/staging-platform.json` holds every platform decision. An entry marked `PROPOSED` is a value the owner
has not yet decided: plans run with it, applies refuse it. **Decision gate:** `stack.sh apply` refuses while any
`infra/config/staging-*.json` section has `"status": "PROPOSED"` (checked after the apply gate, before any AWS
session); a malformed decision file also refuses.

| Section | Status | Content |
|---|---|---|
| `kms` | DECIDED | Two keys (data, audit); yearly rotation; 30-day deletion window |
| `storage` | **PROPOSED** | Lifecycle periods; evidence locked in COMPLIANCE mode for 30 days |
| `cloudtrail` | **PROPOSED** | CloudWatch copy 30 days; S3 data events on anchor and evidence added by the owner session |
| `ecr` | **PROPOSED** | Keep the last 30 tagged images; untagged expire after 7 days |
| `ssm` | **PROPOSED** | D7 host names (`app-staging`, `api-staging`, `staging` .vedaspaces.com); trusted proxy `127.0.0.1/32` (cloudflared on the host network); Litestream 7 days; transcripts 90 days; sessions 20 idle / 60 total minutes |
| `monitoring` | **PROPOSED** | Logs 30 days; 5xx ≥ 5 per 5 minutes; CPU 80 %, memory 85 %, data disk 80 %, root disk 85 % |
| `compute` | **PROPOSED** | t4g.small (N2), credits capped; 12 GB root, 20 GB data (gp3); 7 daily snapshots; AMI pinned after the first plan |
| `ses` | **PROPOSED** | Sender `no-reply@staging.vedaspaces.com` (subdomain; DKIM by AUT-202); sandbox with the owner's address; bounce-rate alarm above 5 % |
| `anchor_retention` | **PROPOSED** | D6: the application locks each anchor for **3650 days** in COMPLIANCE mode (`anchor_store.py`); accept, or change the application first |

## 4. Modules

### 4.1 AUT-102 KMS (`modules/kms`)

| Item | Implementation |
|---|---|
| Keys | `alias/veda-stg-data`: MFA secret blobs (`VEDA_KMS_KEY_ARN`, TG-02), EBS, Litestream/snapshot/anchor/artifact buckets, ECR. `alias/veda-stg-audit`: CloudTrail, logs and evidence buckets, CloudWatch Logs, the alarm topic |
| Why two, not three | One application key and one storage key would cost 1 USD/month more; the host needs both anyway. Duty separation is kept where it matters: audit data (trail, logs, evidence) is under a key the application does not use for its data |
| Shape | Symmetric `ENCRYPT_DECRYPT`, single-region, rotation every 365 days, 30-day deletion window, `prevent_destroy` |
| Policy | Account root (IAM decides use inside the account); **Deny `kms:*` to any caller outside the account** (`kms:CallerAccount`, AWS service principals excepted); audit key only: CloudWatch Logs for `/veda/staging/*` log groups (encryption context), CloudTrail for the `veda-stg-trail` trail (source ARN and context), log delivery for flow logs (source account and ARN), CloudWatch alarms for the topic (source account) |
| Plan guard | Refuses a key without rotation, a deletion window under 30 days, multi-region, asymmetric or HMAC keys, a lockout-check bypass, an unknown or default policy, a policy without the cross-account Deny, any Allow to another account; replica, external and custom-store keys, a separate `aws_kms_key_policy`, an alias outside `alias/veda-*` |
| Tests | `modules/kms`: 4 (shape and rotation; cross-account Deny; audit-key services bound by conditions; short window refused). `run.sh`: 15 |

### 4.2 AUT-103 buckets and Object Lock (`modules/storage`)

| Bucket | Key | Lock | Lifecycle (PROPOSED) | Writers |
|---|---|---|---|---|
| `veda-stg-litestream-<acct>` | data | — | noncurrent versions 7 days | Host (Litestream) |
| `veda-stg-snapshots-<acct>` | data | Enabled; the application locks each snapshot 35 days (COMPLIANCE) | expire after 42 days | Host (nightly snapshot) |
| `veda-stg-anchor-<acct>` | data | Enabled; the application locks each anchor **3650 days** (COMPLIANCE) | none | Host (chain anchors) |
| `veda-stg-artifacts-<acct>` | data | — | expire 90 days, noncurrent 30 | `veda-gh-deploy` (bundles) |
| `veda-evidence-<acct>` | audit | **Default COMPLIANCE 30 days** | none | `veda-gh-evidence`, the collector on the host |
| `veda-stg-logs-<acct>` | audit | — | `cloudtrail/` 90 days, `vpc-flow/` 30 days | CloudTrail (the Veda trail), VPC flow-log delivery |

- **Every bucket:** SSE-KMS with a bucket key; versioning; all four public access blocks; `BucketOwnerEnforced`;
  incomplete uploads aborted after 7 days; `prevent_destroy`; a policy that **denies plain HTTP** and **denies every
  principal of another account** (AWS services excepted, each bound by its own statement).
- **Snapshots and anchors:** the policy denies any write without an Object Lock mode, and every delete.
- **Logs:** CloudTrail may write `cloudtrail/AWSLogs/<acct>/` only for the Veda trail (source ARN); flow-log delivery
  may write `vpc-flow/AWSLogs/<acct>/` only for this account's log sources.
- **Names are the bootstrap's:** the deploy role writes only artifacts, the evidence role only evidence; the plan,
  deploy and evidence roles cannot read Litestream, snapshot or anchor objects (`deny_data_reads`).
- **D6, anchor retention (owner decision):** the anchor writer in the application sets a 10-year COMPLIANCE lock
  (`api/veda/platform/anchor_store.py`, `RETENTION`). In staging every anchor, and the bucket, then lives ten years;
  no one, the root user included, can delete them. The infrastructure cannot shorten it. Options: accept it, or a
  reviewed application change making the retention configurable before the first anchor is written.

**AUT-101 change in this commit (owner decision C3):** VPC flow logs go to the logs bucket (`vpc-flow/`, plain text,
hourly partitions) instead of CloudWatch Logs. The flow-log role, its policy and the log group are gone (network: 27
resources), and **the bootstrap line letting `veda-gh-apply` pass roles to `vpc-flow-logs.amazonaws.com` is removed**:
nothing passes a role to flow logs any more. The bootstrap code is again exactly what was applied on 2026-10-04, so the
re-apply of C2 would plan **no changes**; it stays in the apply sequence only as a verification step.

**Plan guard:** every bucket created with a name (not an unknown id) and, in the same plan and naming it, all four
public access blocks, `BucketOwnerEnforced`, versioning, SSE-KMS and a TLS-only policy; refused: bucket ACLs, a block
with a setting off, other ownership, suspended versioning, SSE-S3, a GOVERNANCE or over-a-year default lock,
replication, website, CORS, access points, Multi-Region Access Points and Transfer Acceleration (the last two bypass
the S3 endpoint policy, AUT-101 review m6).

**Tests:** `modules/storage`: 7 (the six bootstrap names; locks; private, encrypted, versioned; TLS-only and
account-only policies with each statement on its own bucket; evidence lock; GOVERNANCE, early snapshot expiry and
foreign names refused). `run.sh`: 30, starting from a real sandboxed plan of the storage module (each check removes or
changes one thing), plus the decision gate (committed decisions refuse; recorded decisions pass; malformed file
refuses).

### 4.3 AUT-104 CloudTrail (`modules/cloudtrail`)

| Item | Implementation |
|---|---|
| Trail | `veda-stg-trail`: multi-region, global service events, **log-file validation**, logging on, audit key; S3 copy in the logs bucket under `cloudtrail/` (kept per `storage.logs_cloudtrail_expire_days`); `prevent_destroy` |
| CloudWatch copy | `/veda/staging/cloudtrail`, audit key, 30 days; delivered by `veda-stg-cloudtrail-logs` (bounded, assumable by CloudTrail only for this trail, writes only that group's streams) |
| Tampering metric | `Veda/Audit AuditTampering`: StopLogging, DeleteTrail, UpdateTrail, Put*Selectors; ScheduleKeyDeletion, DisableKey, PutKeyPolicy; PutBucketPolicy, DeleteBucketPolicy, Put/DeleteBucketPublicAccessBlock, PutObjectLockConfiguration. Alarm in AUT-110. Delivery failure: AWS/Logs `IncomingLogEvents` on the group (alarm in AUT-110) |
| Boundary interplay | `veda-boundary` denies every role `StopLogging`, `DeleteTrail`, `UpdateTrail` and `Put*Selectors`. The trail is therefore created with management events only and can never be stopped or re-scoped by a workflow. **Any later change to the trail is an owner-session task.** The S3 data events on the anchor and evidence buckets (FC-01, RR-09) are added once by the owner session after the first apply (runbook) |
| Plan guard | Refuses a trail that is single-region, omits global events or log-file validation, is created with logging off, has no KMS key, writes outside a `veda-*` bucket, or sets any selector; CloudTrail Lake data stores and channels; a log group outside `/veda/`, without a KMS key or kept forever |
| Tests | `modules/cloudtrail`: 3 (trail settings and no selectors; CloudWatch copy and bounded delivery role, all values visible at plan time; tampering pattern). `run.sh`: 16, from a real sandboxed plan of the module |

### 4.4 AUT-105 ECR (`modules/ecr`)

| Item | Implementation |
|---|---|
| Repository | `veda-api`, the only repository the bootstrap's deploy role may push to; `IMMUTABLE` tags (a release tag always names one digest); scan on push (basic scanning, no charge); encrypted with the data key; `force_delete = false`; `prevent_destroy`; **no repository policy**, so no principal of another account can pull or push |
| Lifecycle | Untagged images expire after 7 days; the last 30 tagged images are kept (rollback to N-1 and to the release floor of `deploy.sh`) |
| Other images | Litestream and cloudflared stay on Docker Hub, pinned by digest in `docker-compose.yml` and the host setup; mirroring them would need a bootstrap change to the deploy role |
| Plan guard | Refuses a repository outside `veda-*`, with mutable tags, without scan on push or KMS, or force-deletable; any public repository, replication, pull-through cache, registry policy or creation template; a repository policy admitting another account (existing F7 rule) |
| Tests | `modules/ecr`: 4 (immutable, scanned, encrypted; lifecycle; another name and a too-short history refused). `run.sh`: 13, from a real sandboxed plan of the module, including the name the bootstrap scopes the deploy role to |

### 4.5 AUT-106 runtime IAM (`modules/runtime-iam`)

| Item | Implementation |
|---|---|
| Identity | Role and instance profile `veda-stg-host`, path `/`, bounded by `veda-boundary`, assumable by EC2 only |
| AWS managed | `AmazonSSMManagedInstanceCore` only (Session Manager, Run Command); the plan guard allow-lists it |
| Customer policy `veda-stg-host-runtime` | ECR login and pull on `veda-api`; Litestream get/put/delete; snapshots and anchors get/put with retention (no delete); artifacts get; evidence put; list on those five buckets; data key encrypt/decrypt/generate (MFA secrets used directly, `VEDA_KMS_KEY_ARN`); audit key only through S3 (`kms:ViaService`); write its own `/veda/staging/*` log groups; `PutMetricData` only in `Veda/*` and `CWAgent`; read `/veda/staging/*` parameters |
| Explicit Deny | IAM, Organizations, account, `sts:AssumeRole*`, CloudTrail, key creation/deletion/disable/policy/grants, bucket configuration and ACLs and locks, legal holds, governance bypass, every EC2 change, SSM writes/commands/sessions/documents, log-group retention and keys and filters, image pushes and deletes, alarm changes, SNS, SES identity administration |
| Reviewable | Keys are matched by alias (`kms:ResourceAliases`) and the repository ARN is built from its name, so **the whole policy is known at plan time**; the guard now refuses any Veda IAM policy unknown at plan time |
| D5 (open) | The writer/reader separation of anchors is not implemented: the application has no `VEDA_ANCHOR_WRITER_ROLE_ARN` yet (critical-path C2). The bucket policy refuses unlocked writes and every delete, so the host can add anchors but never change or remove one |
| Not here | Custodian roles (`veda-custodian-a/-b`): they need two named humans (OWNER-INPUT-004, O12, O13) and stay out of this workstream |
| Plan guard | AWS managed policies only from the reviewed list (SSM core, DLM service role, and the bootstrap's ReadOnlyAccess and SecurityAudit); no Allow on `*` or a whole service (`<service>:*`) in any Veda policy except the bootstrap's `veda-gh-*` policies and the `veda-boundary` ceiling; no Veda IAM policy unknown at plan time |
| Tests | `modules/runtime-iam`: 6 (bounded role and profile; every Allow names its resources, no whole-service Allow, namespaces, keys by alias; no delete outside Litestream; the explicit Deny; SES only as the staging sender; no SES before AUT-111). `run.sh`: 13, from a real sandboxed plan |

### 4.6 AUT-107 SSM (`modules/ssm`)

| Item | Implementation |
|---|---|
| Configuration | 23 non-secret `String` parameters `/veda/staging/config/<NAME>`, one per environment variable the API, worker, scheduler and Litestream read: environment, region, KMS provider and **the data key alias ARN** (`VEDA_KMS_KEY_ARN`, accepted by the application's `_KMS_ARN` pattern and known at plan time), database URL and snapshot directory on the data volume, snapshot and anchor buckets, Litestream bucket/region/retention, SES as provider, Cloudflare Turnstile mode, secure cookies, rate limits, STS break-glass identity, trusted proxy, and the D7 origins. Each value satisfies `validate_environment` for staging; the sender and configuration set are added by AUT-111 |
| Secrets | **Never Terraform, never Git.** The owner seeds `SecureString` parameters under `/veda/staging/app/` (AUT-302): `VEDA_JWT_PRIVATE_KEY_PEM`, `VEDA_JWT_KID`, `VEDA_CHAIN_KEY`, `VEDA_CHAIN_KEY_LABEL`, `VEDA_RECOVERY_CODE_HMAC_KEY`, `VEDA_EMAIL_HASH_HMAC_KEY`, `VEDA_ACTION_TOKEN_KEY`, `VEDA_TURNSTILE_SECRET`. The plan, deploy and evidence roles are denied reads of `app/*` by the bootstrap; the host reads both paths. The module's validation refuses a secret-looking name in the configuration map |
| Session Manager | The account preferences document `SSM-SessionManagerRunShell`: transcripts streamed to `/veda/staging/ssm-sessions` (audit key, 90 days), session data encrypted with the data key, sessions end after 20 idle minutes and 60 minutes in all, no run-as |
| Host access to it | `logs:DescribeLogGroups` added to the runtime role (Session Manager checks its group exists); reading parameters was already there (AUT-106) |
| Plan guard | Refuses any `SecureString` parameter, any parameter outside `/veda/staging/` or under `app/`; any document other than `veda-*` or the preferences, of a type other than Command or Session, or shared with another account; preferences without encrypted CloudWatch transcripts or with run-as; associations, hybrid activations, maintenance windows, patch baselines and service settings |
| Tests | `modules/ssm`: 4 (plain text under `config/`; transcripts encrypted and sessions bounded; a secret refused; another path refused). `run.sh`: 18, from a real sandboxed plan |
| Scanner notes | checkov CKV2_AWS_34 ("SSM parameter should be encrypted") is skipped inline on the configuration parameters: they are non-secret by design and the guard refuses SecureString there. The secret scanner read the parameter *names* in the plan fixture (`/veda/staging/config/LITESTREAM_BUCKET`, …) as high-entropy strings: 9 entries of `infra/tests/fixtures/aut107-ssm-plan.json` are recorded in `.secrets.baseline` (reviewed false positives; no value) |

### 4.7 AUT-110 monitoring (`modules/monitoring`)

| Item | Implementation |
|---|---|
| Logs | `/veda/staging/app` (container output through Docker's `awslogs` driver, configured on the host) and `/veda/staging/host` (CloudWatch agent: system log, cloud-init, `/var/log/veda/*.log`); audit key; 30 days. With `/veda/staging/cloudtrail` (AUT-104) and `/veda/staging/ssm-sessions` (AUT-107), every log group is under `/veda/staging`, encrypted and expiring |
| Metrics | **A fixed set of log metric filters, not EMF.** The application writes CloudWatch Embedded Metric Format, but its request metrics carry `Route` × `StatusClass` dimensions: every combination would be a billed custom metric (0.30 USD each), enough to exceed the budget. Docker ships the logs as plain JSON, and 7 filters (`Veda/App`) read them: `ServerErrors` (request status ≥ 500), `LeadIntakeFailures` (`/api/v1/public/leads` ≥ 500), `NotificationFailures` (`outbox_handler_failed*`), `OutboxDead`, `ScheduledJobFailed`, `SnapshotCompleted`, `ChainAnchorFailed`. Host: CWAgent memory and two disks, `Veda/Host HealthReady` (AUT-108). Total custom metrics: 12 with the host |
| Alarms | 9 now: 5xx, lead-intake failures, notification failures, dead outbox events, scheduled-job failures, **snapshot missing for 24 h** (silence alarms), chain-anchor failures, audit tampering (AUT-104), **trail delivery** (no events reached the trail group for an hour; silence alarms). 6 more with the host (AUT-108): status check, CPU, memory, data disk, root disk, **API health** (silence alarms). SES alarms come with AUT-111 |
| Notification path | `veda-stg-alarms` topic, audit key; its policy admits only CloudWatch of this account to publish (principals of the account act through IAM); every alarm action is the topic ARN built from its name, so the guard checks it at plan time; the owner's address by email (the `BUDGET_ALERT_EMAIL` secret, sensitive in the plan; AWS sends one confirmation link); the queue `veda-stg-alarm-capture` (SQS-managed encryption, 1 day) that the bootstrap's deploy role reads during drills |
| Dashboard | `veda-stg-overview`: every alarm, the application counters, the latest API errors (Logs Insights widget) |
| Agent configuration | SSM parameter `/veda/staging/cloudwatch-agent` (not under `config/`, so it is not rendered into the application environment) |
| Plan guard | Refuses an unencrypted topic; any subscription other than email or an SQS queue of the account; an unencrypted queue; an alarm action that is not an SNS topic of the account in Mumbai (no EC2 stop or terminate actions); log subscription filters, log destinations and deliveries, metric streams and cross-account observability links |
| Tests | `modules/monitoring`: 6 (logs encrypted and expiring; a bounded set of filters; alarms on the encrypted topic, silence alarms, publish policy, drill queue; no host alarm before the host; host alarms with it; another prefix refused). `run.sh`: 16, from a real sandboxed plan, including that the plan text shows the subscription address only as `(sensitive value)` |

### 4.8 AUT-108 compute and EBS (`modules/compute`)

| Item | Implementation |
|---|---|
| Host | `veda-stg-host`: t4g.small (N2), Amazon Linux 2023 arm64 (latest at the first plan, then pinned in `compute.ami_id`; AMI and boot-script changes are ignored, so they can never replace the host); the AUT-101 subnet and no-inbound security group; its own public IPv4 (egress model A); instance profile `veda-stg-host` (AUT-106) |
| Hardening | **IMDSv2 required**, hop limit 2 (containers reach the role; the account default is the same, guardrails); **no key pair** (SSM only; the guard refuses one); **termination protection**; detailed monitoring off (paid); **burst credits capped (`standard`)**, so a runaway process slows down instead of adding cost; EC2 **automatic recovery** on system-check failure |
| Volumes | Root 12 GB gp3 and data 20 GB gp3, both encrypted with the data key. The data volume (`/var/lib/veda`: SQLite, WAL, local snapshots) is a separate resource with `prevent_destroy`, never deleted with the instance (OPS-007) |
| Snapshots | DLM policy, daily at 02:00 IST, 7 kept, on volumes tagged `veda-backup=daily`; role `veda-stg-dlm` (bounded, assumable by DLM for this account only, AWS managed `AWSDataLifecycleManagerServiceRole`, allow-listed). Backups are threefold: Litestream (continuous), the nightly Object-Locked snapshot (application), and the EBS snapshot (DLM) |
| Boot script | Installs Docker and the CloudWatch agent, and points Docker's logs at `/veda/staging/app` (`awslogs`). No secret; no mount; no application start. The deploy document (§4.10) mounts the volume, installs the pinned Compose plugin, renders the configuration and starts the containers |
| Host alarms | Now on (AUT-110): status check, CPU, memory, data disk, root disk, API health heartbeat (a known boolean enables them: the instance id is unknown until apply) |
| No foreign dependency | Nothing references Aurion or swing-trader-vm; a check asserts no planned resource does |
| Plan guard | Refuses an instance without IMDSv2 required, with an unencrypted root or inline volume, a key pair, or source/destination checking off (a NAT host would break model A); an unencrypted EBS volume; key pairs and serial-console access; snapshot schedules that copy across regions or share snapshots |
| Tests | `modules/compute`: 6 (hardened host; encrypted and kept volumes, daily snapshots; boot script without secrets; bounded DLM role; pinned AMI wins; other instance types refused). `run.sh`: 16, from a real sandboxed plan |

### 4.9 AUT-111 SES (`modules/ses`)

| Item | Implementation |
|---|---|
| Sender | Domain identity `staging.vedaspaces.com`, Easy DKIM 2048-bit. A **subdomain**, so the apex records (SPF, MX, Google verification) are never touched; the three DKIM CNAMEs (`module.ses` output `dkim_tokens`) are published by AUT-202 in Cloudflare. Until then SES reports the identity pending and refuses to send |
| Sandbox | The account stays in the SES sandbox: it sends only to verified addresses. The owner's address (the `BUDGET_ALERT_EMAIL` secret, sensitive in the plan) is verified as a recipient; AWS mails one verification link. Rehearsal recipients are added the same way (O11). Production access is an owner request to AWS, not Terraform |
| Configuration set | `veda-stg`: TLS required to the receiving server; reputation metrics; **suppression of bounces and complaints** (a suppressed address is not sent to again) |
| Failure tracking | Alarms on the free account metrics `AWS/SES` `Reputation.BounceRate` (above 5 %) and `Reject`; application-side, `NotificationFailures` and `OutboxDead` (AUT-110) |
| Failure isolation | The application sends after commit through the outbox; a provider failure marks the event FAILED and retries, and **never rolls back the lead** (NOTIF-008, `api/tests/integration/test_leads.py`); the check is part of `run.sh` |
| Wiring | The host may send only from `no-reply@staging.vedaspaces.com` through the identity and the configuration set (AUT-106 `ses:FromAddress`); the application gets `VEDA_EMAIL_SENDER` and `VEDA_SES_CONFIGURATION_SET` (AUT-107) |
| Plan guard | Refuses inbound email (receipt rules and sets, filters), dedicated IPs and Virtual Deliverability Manager (cost), a configuration set without bounce and complaint suppression or without required TLS, and the apex domain as an identity |
| Tests | `modules/ses`: 4 (subdomain with DKIM; suppression, TLS, reputation; failure alarms; apex refused). `run.sh`: 14, from a real sandboxed plan, including the host's From-address condition and the application's NOTIF-008 test |

