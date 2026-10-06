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
| N-04-S | **ACCEPTED_FOR_STAGING** (recorded as `ACCEPTED`; correction of 2026-10-05, replacing `PRIVATE_REPOSITORY`, see below). The repository stays public for staging and the staging plan artifacts are published | See *N-04-S correction* below |

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

- **Implemented by the D6 change** ([review package](D6-anchor-retention-review-package.md)):
  - the application reads `VEDA_ANCHOR_RETENTION_DAYS` (whole days; anything else refuses to load);
  - staging refuses to start without it, and production refuses anything below 3,650 days;
  - the S3 anchor store locks every object until now plus that retention;
  - `staging-core` plans `/veda/staging/config/VEDA_ANCHOR_RETENTION_DAYS` from `anchor_retention.application_retention_days`.
- **The infrastructure applied on 2026-10-06 did not need the change.** The anchor bucket has Object Lock enabled with
  no default retention. The parameter is added by the plan and apply that follow `deploy.enabled` (runbook §1).
- **The order is still enforced.** `infra/tests/run.sh` refuses `deploy.enabled: true` unless the application change,
  the mapping and the planned parameter are all in place.

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

## N-04-S correction (2026-10-05)

`PRIVATE_REPOSITORY` was recorded on the assumption that GitHub Pro or Team keeps environment protection in a private
repository. That assumption was wrong. On GitHub Free, Pro and Team, required reviewers and wait timers apply only to
public repositories; in a private repository they need GitHub Enterprise.

**What was checked:**
- The repository `slaggala/veda-spaces` is public.
- Its owner is a personal account (`User`), not an organization, so GitHub Enterprise is not available to it.
- Each environment's required reviewers are in place: `staging-plan`, `staging-infra` and `staging` require
  `slaggala`, and `staging-evidence` is limited by branch policy.

Making the repository private would therefore have removed the plan and apply approvals. The owner chose not to weaken
them, so N-04-S is decided **ACCEPTED_FOR_STAGING**. The gate's status is `ACCEPTED`, the value `stack.sh` and
`10-infra-plan` accept. The conditions are:

| Condition | How it holds |
|---|---|
| The repository remains public for staging | Owner decision; required reviewers stay functional |
| Publishing the staging plan artifacts is explicitly accepted | `10-infra-plan` uploads `core-plan-<run>` (plan file, text, metadata) from `main` runs only; pull-request runs upload nothing |
| No secret values in the artifacts | The eight application secrets are SecureStrings seeded by the owner outside Terraform (AUT-302); the plan guard refuses any SecureString and any parameter outside `config/`. The plan text goes to the artifact, never to the job log |
| Minimal, documented artifact retention | `retention-days: 7` on the plan artifact, checked by `infra/tests/run.sh` |
| Production uses a private repository or an independently approved protected-plan mechanism | Production gate; not decided here |
| Staging plan and apply reviewers remain functional | Verified above; this decision changes no environment |

**Accepted exposure:**
- **What is published:** the owner's alert address (`BUDGET_ALERT_EMAIL`).
- **Why:** it is not a credential. Terraform shows it as `(sensitive value)` in the plan text, but the binary plan file
  holds it in plain form.
- **Who can read it:** any signed-in GitHub user, for 7 days per plan run.
- **Also published:** the account layout, resource names and IAM policies, which are already in the public Terraform
  source.
- **To keep the personal address out:** set `BUDGET_ALERT_EMAIL` to a dedicated alias before the plan run.

## Still open (not decided here)

| Item | Needed before |
|---|---|
| Bootstrap verification (C2): bootstrap plan shows `No changes` | The first staging-core apply |
| `compute.ami_id` and `az_id` pins from the live plan (optional) | Before or after the first apply |
| CloudTrail data events; SNS subscription and SES recipient confirmations | Immediately after the first apply |
| D6 application change (configurable retention, 30 days) | `deploy.enabled = true` |
| AUT-302 secrets (8, including the test Turnstile secret) | `deploy.enabled = true` |
| `deploy.enabled` and the second plan and apply (deployment alarms, R4) | `12-deploy` |
| AUT-201 … 204; O15 (scoped Cloudflare token) | End-to-end lead validation |
| `deploy.public_intake` | End-to-end lead validation |
| D5, OD-B7 closure, N-04 for production (private repository or another protected-plan mechanism), custodians (O12, O13), AM-9, SES production access, production account | Production |
