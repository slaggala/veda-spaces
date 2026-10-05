# Staging platform: owner decisions (decision record)

- **Date:** 2026-10-05
- **Owner:** repository owner (`slaggala`)
- **Context:** the decision package that followed the merge of the staging platform remediation (PR #23). This record
  closes the apply gate (`infra/config/apply-gate.json`) and the decision gate (no `PROPOSED` entry in
  `infra/config/staging-*.json`).
- **What it does not authorize:**
  - an apply;
  - a deployment (`deploy.enabled` stays `false`);
  - public lead intake (`deploy.public_intake` stays `disabled`).
- Each apply still needs the `staging-plan` and `staging-infra` approvals of the exact plan.

## Apply gate

| Gate | Decision | Conditions |
|---|---|---|
| OD-B7 | **ACCEPTED for staging.** `veda-gh-apply` keeps the ability to write IAM trust policies through raw API calls in the staging account; no SCP or RCP is applied now | Reaching the gap needs a reviewed workflow change on `main` and a `staging-infra` approval. Every apply runs a guarded plan (`check-plan.sh`: every role bounded, no trust outside the account) approved by its SHA-256 digest. `veda-boundary` bounds every role. CloudTrail and the tampering alarm record and report changes. **Not carried into production:** close it with an SCP or RCP from the management account (RR-C) before any production apply |
| N-04-S | **PRIVATE_REPOSITORY.** Plan artifacts (which hold the alert recipient, the account layout and the IAM policies) are published only from a private repository | The owner makes the repository private on a GitHub plan that keeps environment protection rules for private repositories (Pro or Team) **before** the plan whose artifact is applied. Until then `10-infra-plan` plans but uploads nothing, so nothing can be applied |

## Platform decisions (`infra/config/staging-platform.json`)

| Section | Decision | Values |
|---|---|---|
| `storage` | Accepted as proposed | <ul><li>Litestream old versions: 7 days.</li><li>Snapshots: expire after 42 days (35-day lock).</li><li>Artifacts: 90 days, old versions 30 days.</li><li>CloudTrail logs: 90 days.</li><li>Flow logs: 30 days.</li><li>Evidence: COMPLIANCE lock, 30 days.</li></ul> |
| `anchor_retention` (D6) | **Option B: configurable anchor retention, 30 days in staging** | `application_retention_days: 30`. See below. |
| `cloudtrail` | Accepted as proposed | <ul><li>CloudWatch copy kept 30 days.</li><li>The owner session adds the S3 data events on the anchor and evidence buckets once, after the first apply (runbook §6.2).</li></ul> |
| `ecr` | Accepted as proposed | <ul><li>Keep the last 30 tagged images.</li><li>Untagged images expire after 7 days.</li></ul> |
| `ssm` (D7) | **Accepted**: `https://app-staging.vedaspaces.com`, `https://api-staging.vedaspaces.com`, `https://staging.vedaspaces.com` | <ul><li>Trusted proxy: `172.30.0.1/32`.</li><li>Litestream WAL: `168h`.</li><li>Session transcripts: 90 days.</li><li>Sessions end after 20 idle / 60 total minutes.</li></ul> |
| `monitoring` | Accepted as proposed | <ul><li>Logs kept 30 days.</li><li>5 or more 5xx errors in 5 minutes.</li><li>CPU 80%, memory 85%.</li><li>Data disk 80%, root disk 85%.</li></ul> |
| `compute` | Accepted as proposed | <ul><li>t4g.small, burst credits `standard`.</li><li>12 GB root, 20 GB data.</li><li>7 daily snapshots.</li><li>`ami_id` stays `null` until the first live plan names the AMI; pinning it is a later reviewed change.</li></ul> |
| `ses` | Accepted as proposed | <ul><li>Sender: `no-reply@staging.vedaspaces.com`.</li><li>Bounce-rate alarm above 5%.</li></ul> |

## D6: anchor retention

The owner chose **option B**: the application's anchor retention becomes configurable, and staging uses **30 days**.

- **Today the application still hard-codes 3,650 days.** The constant is `RETENTION` in
  `api/veda/platform/anchor_store.py`.
- **The infrastructure does not need the change.** The anchor bucket has Object Lock enabled with no default
  retention, so the first apply is unaffected.
- **The change must merge before the first anchor is written,** that is, before `deploy.enabled` becomes `true`. Any
  anchor written first would be locked for ten years, irreversibly.
- **A check enforces this order.** `infra/tests/run.sh` refuses `deploy.enabled: true` while the application's
  retention differs from `anchor_retention.application_retention_days`.
- **The change is a separate, reviewed application pull request.** It is not part of this record.

## D8: staging Turnstile

**Cloudflare's published always-pass test secret** is used in staging, seeded as `VEDA_TURNSTILE_SECRET` with the
other AUT-302 secrets.

- **It accepts every token,** so it offers no bot protection.
- **Public lead intake stays disabled while it is in use.**
- **A real widget (AUT-203) is still required:**
  - before any public intake;
  - for AM-7;
  - for production.
- **This decision has no configuration value in the repository.** The secret is seeded by the owner and never committed.

## Still open (not decided here)

| Item | Needed before |
|---|---|
| Repository private on GitHub Pro or Team (N-04-S) | The staging plan whose artifact is applied |
| Bootstrap verification (C2): bootstrap plan shows `No changes` | The first staging-core apply |
| `compute.ami_id` and `az_id` pins from the live plan (optional) | Before or after the first apply |
| CloudTrail data events; SNS subscription and SES recipient confirmations | Immediately after the first apply |
| D6 application change (configurable retention, 30 days) | `deploy.enabled = true` |
| AUT-302 secrets (8, including the test Turnstile secret) | `deploy.enabled = true` |
| `deploy.enabled` and the second plan and apply (deployment alarms, R4) | `12-deploy` |
| AUT-201 … 204; O15 (scoped Cloudflare token) | End-to-end lead validation |
| `deploy.public_intake` | End-to-end lead validation |
| D5, OD-B7 closure, custodians (O12, O13), AM-9, SES production access, production account | Production |
