# Staging platform runbooks (AUT-102 … AUT-111)

Operating the staging platform built by `infra/terraform/envs/staging-core`. **Nothing here has been run**: the
platform is not applied, Veda is not deployed and public lead intake is disabled. Every procedure becomes evidence
the first time it runs (§5). Review: [consolidated review package](../implementation/staging/STAGING-PLATFORM-review-package.md).

Roles: **owner session** = the bootstrap owner role (MFA, Mumbai-only session policy, runbook staging-bootstrap §3);
**workflows** = `10-infra-plan`/`11-infra-apply` (`veda-gh-plan`/`-apply`), `12-deploy` (`veda-gh-deploy`),
`13-evidence` (`veda-gh-evidence`), each behind its protected environment and reviewer.

## 0. Gates that keep everything off today

| Gate | Where | Opens when |
|---|---|---|
| Apply gate | `infra/config/apply-gate.json` (OD-B7, N-04-S) | Both decided with a committed record |
| Decision gate | `infra/config/staging-*.json`: no section `PROPOSED` (`stack.sh decisions`) | The owner records every proposed value |
| Deploy gate | `staging-platform.json` `deploy.enabled` | The owner sets it true in a reviewed pull request |
| Public path | No tunnel, DNS or Turnstile widget (AUT-201 … 203, out of scope) | Those stories are built |

## 1. Deployment

**First deploy** (after the apply sequence, §7, and the secrets, §6.3):
1. Set `deploy.enabled: true` in `infra/config/staging-platform.json` (reviewed pull request, merged to `main`).
2. Actions → `12-deploy` → Run workflow on `main`. Approve the `staging` environment.
3. The job builds the image of this commit, pushes `veda-api:<12-hex>`, waits for the scan (stops on HIGH or
   CRITICAL), uploads `deploy/<tag>/bundle.tgz` with its SHA-256, and runs `veda-deploy` on the host:
   bundle verified → `host-setup.sh` (mount, Compose, agent, heartbeat) → `render-env.sh` (refuses until every secret
   is seeded) → pull by digest → `api/deploy/deploy.sh <tag>` (floors, snapshot, quiesce, expand-only migration,
   readiness, resume; [api-runbooks §1](api-runbooks.md)).
4. Pass: the job ends `deployed <tag> (<digest>) to staging`; `veda-stg-api-health` is OK within 5 minutes.

**Later deploys:** the same, from the new commit. **Rollback** to N-1 follows [api-runbooks §2](api-runbooks.md)
(`deploy.sh --rollback <n-1-tag>`), run on the host through an owner Session Manager session in
`/opt/veda/releases/<n-1-tag>/api/deploy` (the N-1 bundle and image are still there; ECR keeps 30 tagged images).

**Failure:** `deploy.sh` stops with worker and scheduler paused when readiness fails; the command output is in
`/veda/staging/host` (stream `<instance>/veda`) and `/var/log/veda/deploy.log`. Decide forward fix or rollback
(api-runbooks §2).

## 2. Backup and recovery

| Layer | What | Recovery |
|---|---|---|
| Litestream | WAL to `veda-stg-litestream-<acct>` every second; 7 days of WAL | Point-in-time restore of `veda.db` ([api-runbooks §3](api-runbooks.md)) |
| Nightly snapshot | `VACUUM INTO` snapshot to `veda-stg-snapshots-<acct>`, COMPLIANCE-locked 35 days (application); `snapshot-missing` alarm after 24 h of silence | Disaster rollback (api-runbooks §3) |
| EBS snapshot | DLM, daily 02:00 IST, 7 kept, data volume only | Create a volume from the snapshot in the same AZ, stop the API, swap the attachment on `/dev/sdf` (owner session), start |

**Host loss or rebuild.** EC2 automatic recovery handles a failed system check. A rebuild (new AMI, corrupt root) is
an **owner-session** procedure, because the plan guard refuses a replace in the workflows and the data volume has
`prevent_destroy`. Outline (the exact commands are reviewed as their own change the first time it is needed):
1. Stop the API (`docker compose stop`) through Session Manager; the data volume keeps the database.
2. Owner session: detach the data volume, disable termination protection, terminate the instance.
3. A reviewed change records the new `compute.ami_id`; the plan creates the instance and the attachment again (the
   volume itself is unchanged), applied by the owner session because a replace is outside the workflow guard.
4. `12-deploy` the current release: `host-setup.sh` finds the existing filesystem and does **not** format it.
5. Evidence: `13-evidence` with label `host-rebuild`.

**Never:** delete a locked snapshot or anchor (impossible by design), or format a volume that carries a filesystem
(`host-setup.sh` refuses to).

## 3. Monitoring

Every alarm notifies `veda-stg-alarms` (owner email, after the one-time subscription confirmation) and the drill queue
`veda-stg-alarm-capture`. Dashboard: CloudWatch → `veda-stg-overview`.

| Alarm | Meaning | First action |
|---|---|---|
| `veda-stg-api-health` | `/health/ready` failing or the heartbeat silent | `docker compose ps`; `deploy.log`; api-runbooks §1 readiness |
| `veda-stg-app-5xx` | ≥ 5 API 5xx in 5 minutes | Dashboard "Recent API errors"; logs `/veda/staging/app` |
| `veda-stg-lead-intake-failures` | Public lead submissions answered 5xx | Same; leads are never half-written (transaction) |
| `veda-stg-notification-failures` | Outbox handlers failing (email) | SES identity verified? recipient verified (sandbox)? The lead is kept (NOTIF-008) |
| `veda-stg-outbox-dead` | Events dead-lettered | api-runbooks outbox section |
| `veda-stg-scheduled-job-failed` | A scheduled job failed | Logs of the scheduler container |
| `veda-stg-snapshot-missing` | No completed snapshot in 24 h | Scheduler; snapshot bucket permissions; disk |
| `veda-stg-chain-anchor-failed` | A security-chain anchor failed (FC-01) | Anchor bucket, Object Lock headers, KMS |
| `veda-stg-audit-tampering` | Trail, key or bucket protection changed | **Incident**: CloudTrail event history, who and what |
| `veda-stg-trail-delivery` | No trail events for an hour | Trail status (owner session); logs-bucket policy |
| `veda-stg-host-status-check` | EC2 status check failed | EC2 recovers automatically; else §2 rebuild |
| `veda-stg-host-cpu` / `-memory` / `-data-disk` / `-root-disk` | Resource pressure | `docker stats`; prune old images; grow the volume (decision) |
| `veda-stg-ses-bounce-rate` / `-ses-rejects` | Sending reputation | Suppression list; recipients; SES console |

**Drill (RG-5):** `aws cloudwatch set-alarm-state --alarm-name veda-stg-app-5xx --state-value ALARM --state-reason drill`
(deploy role or owner), then read `veda-stg-alarm-capture` and the owner mailbox; record with `13-evidence`.

## 4. SES readiness

1. AUT-202 publishes the three DKIM CNAMEs (`terraform output` of `module.ses.dkim_tokens`:
   `<token>._domainkey.staging.vedaspaces.com CNAME <token>.dkim.amazonses.com`). SES shows the identity verified
   within hours.
2. The owner clicks the verification link AWS mails to the recipient address (sandbox recipient), and confirms the
   alarm-topic subscription (another link).
3. Sandbox limits: 200 messages a day, 1 per second, verified recipients only. Rehearsal recipients (O11) are added as
   identities in a reviewed change.
4. Test: after the first deploy, trigger an email (password reset of a staging user) and check delivery; a failure
   shows in `veda-stg-notification-failures` without touching the lead or the user.
5. Production access (leaving the sandbox) is an owner request to AWS with the use case; it is not needed for
   staging.

## 5. Evidence

`13-evidence` (environment `staging-evidence`) runs `veda-collect` and prints `evidence s3://veda-evidence-<acct>/host/<date>/<instance>/<label>-<ts>.tgz sha256 <hex>`.
The object is COMPLIANCE-locked (30 days, decision). The summary (label, object key, SHA-256, what it shows) goes to
`docs/release-evidence/<gate>/` by pull request. No secrets or personal data are collected; `/etc/veda/api.env` is
never read.

## 6. Owner-session steps

### 6.1 Bootstrap verification (decision C2)
Re-run the bootstrap plan with the controlled procedure of 2026-10-04. Since the flow-log role is gone (C3), the
bootstrap code equals what was applied: the plan must show **No changes**. Any change is a stop condition.

### 6.2 CloudTrail data events (after the first apply)
`veda-boundary` denies every role `PutEventSelectors`; the owner session adds the S3 data events once:
```sh
aws cloudtrail put-event-selectors --region ap-south-1 --trail-name veda-stg-trail --advanced-event-selectors '[
 {"Name":"Management","FieldSelectors":[{"Field":"eventCategory","Equals":["Management"]}]},
 {"Name":"Anchor and evidence objects","FieldSelectors":[{"Field":"eventCategory","Equals":["Data"]},
  {"Field":"resources.type","Equals":["AWS::S3::Object"]},
  {"Field":"resources.ARN","StartsWith":["arn:aws:s3:::veda-stg-anchor-813238078849/","arn:aws:s3:::veda-evidence-813238078849/"]}]}]'
```
Evidence: `aws cloudtrail get-event-selectors --trail-name veda-stg-trail`.

### 6.3 Secrets (AUT-302)
Generate and write, with the owner session, the eight `SecureString` parameters under `/veda/staging/app/`
(`VEDA_JWT_PRIVATE_KEY_PEM` P-256, `VEDA_JWT_KID`, `VEDA_CHAIN_KEY`, `VEDA_CHAIN_KEY_LABEL`,
`VEDA_RECOVERY_CODE_HMAC_KEY`, `VEDA_EMAIL_HASH_HMAC_KEY`, `VEDA_ACTION_TOKEN_KEY` — each key ≥ 32 random bytes,
distinct, labels not `dev-*` — and `VEDA_TURNSTILE_SECRET`, D8). Values never leave the owner's terminal and are never
committed. `render-env.sh` refuses to start the application until all eight exist.

### 6.4 Pins after the first plan
Record `compute.ami_id` and `az_id` (staging-network.json) from the first real plan, so later plans cannot replace the
host or the subnet.

## 7. Staging apply sequence

Every apply: `10-infra-plan` on `main` → review the plan text and the guard → approve the digest → `11-infra-apply`.
Prerequisites: OD-B7 and N-04-S decided; every `PROPOSED` decision recorded; §6.1 shows No changes.

| Step | Scope | Check after |
|---|---|---|
| 1 | AUT-112 budget, AUT-102 keys, AUT-103 buckets, AUT-101 network, AUT-104 trail (one plan, dependency order is Terraform's) | Keys rotate; buckets private (S3 console "Access: Bucket and objects not public"); trail logging; flow logs arriving under `vpc-flow/` |
| 2 | Owner session §6.2 (data events) | `get-event-selectors` |
| 3 | AUT-105, AUT-106, AUT-107, AUT-110, AUT-108, AUT-111 (same plan if applied together) | Host `Online` in Systems Manager; agent metrics; alarms OK or INSUFFICIENT_DATA; SES identity pending until AUT-202 |
| 4 | Owner session §6.3 (secrets), §6.4 (pins) | Parameters exist (names only) |
| 5 | `12-deploy` (after `deploy.enabled`) | §1 pass criteria |
| 6 | `13-evidence` label `staging-platform-first-apply` | Evidence PR |

Single-plan apply is possible (Terraform orders the 158 resources); the steps above split it where an owner action
sits between resources. Zero destroys; any destroy or replace is refused by the plan guard.

## 8. End-to-end lead-flow validation plan

**Goal:** a public enquiry travels browser → Cloudflare → tunnel → API → SQLite → Litestream → outbox → SES → staff
inbox, with every control observed.

**Prerequisites (not in this workstream):** AUT-201 tunnel, AUT-202 DNS (D7 host names and DKIM), AUT-203 Turnstile
widget (D8), AUT-204 the staging SPA; secrets seeded (§6.3); a deployed release (§1); SES recipient verified (§4).

| # | Step | Pass criterion | Evidence |
|---|---|---|---|
| 1 | Submit the public form on the staging site with a valid Turnstile | `201`, a lead number | Browser capture; request log line (route `/api/v1/public/leads`, status 201) |
| 2 | Submit with a failed Turnstile | Refused; no lead | Log line; lead count unchanged |
| 3 | Duplicate submission (same idempotency key) | One lead | Lead list |
| 4 | Staff login with MFA; open the lead | Lead visible with source and consent | Screenshot; audit log entry |
| 5 | Notification email | Delivered to the verified mailbox | Mailbox; `AWS/SES Delivery` |
| 6 | SES failure drill: unverify the recipient, submit | Lead committed; outbox event FAILED then retried; `notification-failures` alarm | Lead list; outbox status; alarm history |
| 7 | Replication | Litestream lag < 5 s; WAL objects in the bucket | `13-evidence` |
| 8 | Snapshot | Next nightly snapshot locked 35 days | Object retention in the console |
| 9 | Chain anchor | Anchor object locked; trail data event | CloudTrail event |
| 10 | No public inbound | `ss -lntu` shows only loopback and the agent; the security group has no inbound rule | `13-evidence` |

Record the run with `13-evidence` label `e2e-lead-flow` and a summary in `docs/release-evidence/E2E-LEAD-FLOW/`.
