# P0 release-readiness report

- **Date:** 2026-10-03
- **Scope:** the state after pull requests #3 to #11, and what remains before staging and before production.
- **Production deployment approval:** **PENDING**. Nothing is deployed, the staging bootstrap has not been run, and
  public lead intake stays disabled.
- **Sources:** [P0-open-issues.md](P0-open-issues.md) (register, updated today), the registry gates
  (`docs/architecture/gate-registry.json`, unchanged), [P0-production-gate-report.md](P0-production-gate-report.md),
  [P0-staging-gate-report.md](P0-staging-gate-report.md), the bootstrap runbook
  ([staging-bootstrap.md](../operations/staging-bootstrap.md)) and the pre-bootstrap closure
  ([AUT-001-003-pre-bootstrap-closure.md](staging/AUT-001-003-pre-bootstrap-closure.md)).
- **No new feature work** is proposed here. Where an item needs code, it is listed as remaining work, not started.

## 1. Merged pull requests and what they closed

| PR | Merge | What it changed | Items | Status now |
|---|---|---|---|---|
| #3 | `af3404c` | Staging account manifest (`veda-staging`, 813238078849, member of `o-q9ji0hj18c`) and member-account checks | PB-01, OD-B2 | Manifest complete (`check-manifest.sh --complete` passes); bootstrap **not run** |
| #4 | `5765248` | API base image digest and `libpcre2-8-0` upgrade (7 HIGH Debian CVEs) | image scan | Resolved |
| #5 | `100ff8a` | Escalated invitations expire in 24 h; unknown permission codes refused at startup; reset retires enrollment links; per-user limit 600 per 5 min; dev-audit exceptions governance | FC-09, FC-A04, IR-A04, IR-A08 | Resolved |
| #6 | `c6a7fea` | Per-run archive segment keys; no SQLite write lock across object-store I/O | FC-13, FC-14 | Resolved (real-S3 archival run stays in RR-06) |
| #7 | `72d260a` | Chain verification against every retained anchor | FC-01 | Resolved in code; staging evidence (separate writer role, FC-03) |
| #8 | `24b1a4a` | Break-glass custodian identity from the custodian's own credentials, never the host | RR-09, IR-06 | Resolved in code; OD-6, OWNER-INPUT-004 and staging rehearsal |
| #9 | `7f34261` | Personal data kept out of Sentry transactions, spans, errors and `outbox_event.last_error` | RR-13, DC-03 (part) | Resolved in code; AM-10 staging check |
| #10 | `35862ae` | Staff re-consent rules (a)–(d) of AM-4, database guard on consent history (migration 0010) | RR-12, IR-16, DEV-004 conditions | Resolved; owner confirms AM-4 option (a) |
| #11 | `a5a59a7` | Tabs/tabpanel wiring, command-palette combobox, account menu, step-up expiry warning | RR-18, IR-37 | Resolved in code; manual screen-reader run (OI-RM-5) |

CI: every PR from #4 to #11 passed all required checks (SQLite and PostgreSQL API suites, app, security, browser
E2E with axe), so OI-RM-1 is resolved.

Register corrections made today besides the PR outcomes: IR-01, IR-07, IR-10, RR-02, RR-03, RR-04, IR-23 and IR-A22
still read "amendment pending owner decision" although the owner decided their amendments on 2026-09-30 (AM-11, AM-5,
AM-6, AM-12, AM-13, AM-7, AM-8). They now carry that decision. The conditions attached to those amendments are
unchanged; for example, AM-7 still needs real Turnstile keys in staging.

## 2. Status matrix

### 2.1 Former application-code production blockers

| Item | Code | Remaining condition | Owner of the condition |
|---|---|---|---|
| RR-09 | Done (PR #8) | OD-6 credential model, OWNER-INPUT-004 custodians, staging rehearsal with CloudTrail (PG-BG) | Security Owner |
| RR-12 | Done (PR #10) | Record the AM-4 choice of option (a) and the earlier-version rule | Architecture Owner, Data Protection lead |
| RR-13 | Done (PR #9) | AM-10 decision and its staging check (Sentry test project, provider-error outbox row, erasure run) | Privacy Owner |
| RR-18 | Done (PR #11) | Manual screen-reader run (OI-RM-5) | Product Owner (accessibility) |
| FC-01 | Done (PR #7) | Anchors written by a separate writer role into real Object Lock (FC-03, RR-05) | Operations / Security |
| FC-09, FC-13, FC-14 | Done (PR #5, #6) | None | — |

### 2.2 Items that still need code or CI changes (not started)

Calling the application code "complete" holds only for items labelled *production blocker*. These open items also
need code before staging or production:

| Item | Scope | What is missing |
|---|---|---|
| FC-03 | Staging evidence and production gate; prerequisite of the FC-01 evidence | The S3 anchor store writes without a conditional `IfNoneMatch` and reads the current object version (`anchor_store.py`), so an overwrite with the host credential creates a new version that verification trusts. Needs conditional writes, reads by the version id recorded in the manifest, and a bucket policy that refuses writes without `If-None-Match` |
| RR-15 | Staging blocker; blocks production (RG-1, RG-2) | `restore-verify` of a Litestream-restored file; stopping Litestream before the swap; the metric on one failure path; off-host replica verification (runbook §3 lists them) |
| FC-10 | Staging blocker (before Founders use governance) | Approvals card and approve dialog must show the requested Founder status (RESTORE vs DELETE vs DISABLE) |
| FC-15 | Production (site accessibility) | Site focus-ring colour is 2.60:1; needs ≥ 3:1 |
| DC-05 | Staging (CI gate integrity) | mypy ratchet ignores `*.pyi` stubs, which can hide baselined and new errors |
| RD-02 | Staging, before AUT-301 | `make -C infra check` is not a required CI check |
| OI-RM-2 | Production | Firefox and WebKit legs of the browser E2E |

Tracked, not P0-release blocking: RD-06 (PostgreSQL two-writer 409 body; PostgreSQL release gate), RD-05 (lead search
in the query string), RR-A20 (SPA shows only subject and note of superseded consent evidence), OI-RM-3 (mypy backlog
of 157).

### 2.3 Registry gates

The registry holds 27 gates. TG-01 and TG-08 were approved by the owner on 2026-09-30, and PGM-1 applies after P0.
The other 24 are unchanged since 2026-09-30 and none has passed: each needs evidence that does not exist yet. PG-PRIV
applies only when public intake is enabled, so §3 counts 23 for a P0 release.

| Gate | Needs first | Status |
|---|---|---|
| OWNER-INPUT-001…004 | Owner values | Blocked — awaiting owner input |
| TG-02 (real KMS blob) | Staging KMS (AUT-102) | Pending |
| TG-03, PG-DAST | An assessor and a staging target | Pending |
| TG-04, PG-RET | OWNER-INPUT-002 | Blocked |
| TG-05, RG-7 | Staging host, deploy pipeline | Pending |
| TG-06, RG-4 | Staging host, k6 load (AUT-405) | Pending |
| TG-07 | Independent verification of the final minor remediation | Pending |
| RG-1, RG-2 | OWNER-INPUT-001, OWNER-INPUT-003, RR-15 code | Pending |
| RG-3, RG-6, RG-8, RG-9 | Staging host and configuration | Pending |
| RG-5 | Observability (AUT-110), SNS routing, test-fire | Pending |
| PG-BG | OWNER-INPUT-004, OD-6, custodian roles | Blocked |
| PG-EMAIL | SES production access, DNS records (AUT-111, AUT-202) | Pending |
| PG-PRIV | Privacy notice (IR-A23); only for enabling public intake | Pending |

## 3. Readiness

The counting rule is shown so the figure can be recomputed. One release condition = one row below. A condition is
met only with recorded evidence.

| Group | Conditions | Met |
|---|---|---|
| A. Former application-code production blockers (RR-09 code, RR-12, RR-13, RR-18, FC-01 code, FC-09, FC-13, FC-14) and the first CI proof (OI-RM-1) | 9 | 9 |
| B. Remaining code or CI changes (§2.2: FC-03, RR-15, FC-10, FC-15, DC-05, RD-02, OI-RM-2) | 7 | 0 |
| C. Staging bootstrap; staging stacks (RD-01) | 2 | 0 |
| D. Staging evidence not covered by a gate (anchor writer role and Object Lock: FC-01/FC-03/RR-05/IR-03; RR-06 archival run; RR-14 deploy; AM-10 check; AM-7 Turnstile and proxy; OI-RM-5 manual run) | 6 | 0 |
| E. Owner decisions and authorizations outside the registry (§6, items 1–12) | 12 | 0 |
| F. Registry gates for a P0 release without public intake (OWNER-INPUT-001…004, TG-02…TG-07, RG-1…RG-9, PG-DAST, PG-RET, PG-BG, PG-EMAIL) | 23 | 0 |
| G. Production deployment approval | 1 | 0 |
| **Total** | **60** | **9** |

- **Production readiness: 9 of 60 conditions, 15 %.**
- **Application code readiness (A + B):** 9 of 16, 56 %. All code for items labelled production blocker is done;
  seven code and CI items remain (§2.2), FC-03 and RR-15 being the largest.
- **Staging bootstrap readiness:** 11 of 16 prerequisites, 69 % (§4).

## 4. Bootstrap prerequisites

| # | Prerequisite | Status | Evidence |
|---|---|---|---|
| 1 | Account manifest complete (PB-01) | Met | PR #3; `infra/scripts/check-manifest.sh --complete` passes on 2026-10-03 |
| 2 | Dedicated member account, alias, owner role validated | Met | CloudShell validation 12/12 (2026-10-02), recorded in PR #3 |
| 3 | GitHub environments and `main` protection (PB-03) | Met | Read back 2026-10-03: five environments, admin bypass off; `main` requires five checks and a pull request, enforced for admins |
| 4 | PR #2 checks and merge (PB-04) | Met | PR #2 merged |
| 5 | Owner decisions OD-B1…OD-B8 (PB-05) | Met | [AUT-001-003-owner-decisions.md](staging/AUT-001-003-owner-decisions.md) |
| 6 | Region-guarded owner session (PB-06) | Met in code; proven live by the run | `infra/config/bootstrap-session-policy.json` |
| 7 | No Cloudflare token (PB-07) | Met | OD-B3 |
| 8 | Clean-tree enforcement (PB-08) | Met | `require_clean_tree` |
| 9 | Dedicated owner role (PB-09) | Met | `bootstrap-owner`: path `/`, 1-hour sessions, trusted only by `bootstrap-operator` with MFA |
| 10 | Live IAM simulation (PB-10) | Met in code; runs live | `infra/scripts/simulate-boundary.sh` |
| 11 | No `GH_ADMIN_TOKEN` (PB-11) | Met | OD-B4 |
| 12 | Operator MFA device and temporary credentials (RD-03) | **Not met** | PR #3 validation: 0 MFA devices, 0 access keys |
| 13 | Independent review of the pre-bootstrap closure, or an owner waiver (RD-04) | **Not met** | The closure document requires it |
| 14 | Operator workstation: `aws` v2, Terraform 1.16.4, `jq`, `curl`, `git`, `gh`, plus tflint 0.64.0, checkov, shellcheck and actionlint for `make -C infra check` | **Not met** | On the current workstation only `aws`, `jq` and `gh` were found (2026-10-03) |
| 15 | `make -C infra check` passes on a clean checkout of `main` on that workstation | **Not met** | Not run (toolchain missing) |
| 16 | The owner's written authorization to run the bootstrap | **Not given** | Standing instruction: do not execute the bootstrap |

The repository is public, so only the local procedure (runbook §3, Option A) is available; the `00-bootstrap`
workflow refuses to run (N-04).

## 5. AWS and Cloudflare dependencies

| Dependency | Needed for | Created by | Notes |
|---|---|---|---|
| State bucket, state KMS key, GitHub OIDC provider, `veda-gh-*` roles, `veda-boundary`, account guardrails | Everything after the bootstrap | Bootstrap (AUT-002) | The only step that uses owner credentials |
| VPC/network, KMS keys (app, MFA blobs) | Host, TG-02 | AUT-101, AUT-102 | TG-02 needs a real `GenerateDataKey` blob |
| Buckets: anchors and archives with **Object Lock (COMPLIANCE)** and versioning; Litestream replica; snapshots; evidence; artifacts | FC-01, FC-03, RR-05, RR-06, RG-1, RG-2 | AUT-103 | Object Lock must be enabled when the bucket is created |
| CloudTrail trail with S3 data events on the anchor bucket | FC-01 and RR-09 evidence | AUT-104 | Until then, Event History covers management events only (OD-B6) |
| ECR `veda-api` | Deploy | AUT-105 | |
| IAM: host role (anchors: `PutObject` only), verifier role (`GetObject`, `ListBucket`), operator, **custodian roles** | FC-01, RR-09, PG-BG | AUT-106 | Custodian trust and MFA are OD-6 |
| SSM parameters and documents (`veda-deploy`, `veda-collect`, `veda-drill-*`, `veda-seed-fixtures`), Session Manager | Deploy, drills, break-glass sessions | AUT-107 | Secrets are seeded outside Terraform (AUT-302) |
| EC2 t4g.medium, encrypted data volume, recovery, DLM | Every staging gate | AUT-108, AUT-109 | RG-3, RG-6 |
| CloudWatch agent, alarms, SNS to the owner | RG-5, RR-07, FC-02, IR-12 | AUT-110 | Each alarm is test-fired |
| SES (sandbox, then production access), DKIM | PG-EMAIL, break-glass notifications | AUT-111 | Production access is an AWS support request and can take days |
| Budgets | Cost control | AUT-112 | |
| Cloudflare tunnel, DNS, Turnstile, Pages, WAF | Staging reachability, AM-7 Turnstile checks | AUT-201…AUT-205 | Needs a scoped Cloudflare token (owner decision; OD-B3 covers only the bootstrap) |
| Infra workflows (plan/apply with digest binding) | Applying every stack | AUT-301 | Gated by OD-B7 (trust-writing gap), RR-A and RR-C |
| Evidence collectors | Every gate's evidence | AUT-401 | Summaries with SHA-256 under `docs/release-evidence/` |

AUT-101 to AUT-112, AUT-201 to AUT-205, AUT-301, AUT-302 and AUT-401 have **not started** (`infra/README.md`). This
is the critical path (RD-01): FC-01 evidence, the RR-09 rehearsal and every staging gate depend on it.

## 6. Owner input still required

| # | Item | Decides | Blocks | Reference |
|---|---|---|---|---|
| 1 | Authorize the staging bootstrap run (time window, operator) | Owner | Bootstrap | Runbook §3 |
| 2 | Give `bootstrap-operator` an MFA device and temporary credentials, and delete them afterwards | Owner (action) | Bootstrap | RD-03 |
| 3 | Independent review of the pre-bootstrap closure and the member-account change, or a recorded waiver | Owner | Bootstrap | RD-04 |
| 4 | Authorize starting the staging infrastructure stories (AUT-101…AUT-112, AUT-2xx, AUT-301, AUT-302, AUT-401) | Owner | All staging evidence | RD-01 |
| 5 | AUT-301 gate: the `veda-gh-apply` trust-writing gap (OD-B7), with an SCP/RCP from the management account (RR-C); repository-name trust acknowledgement (RR-A) | Owner / Security | Any workflow assuming `veda-gh-apply` | Owner decisions doc |
| 6 | A scoped Cloudflare token for the edge stacks (zone, DNS records, tunnel, Turnstile) | Owner | AUT-201…AUT-205, AM-7 checks | OD-B3 |
| 7 | OD-6: the custodian credential model (assume-role with MFA per command, as proposed in runbook §7) | Security Owner | RR-09, PG-BG | RR-09 |
| 8 | Confirm AM-4 option (a) (database guard) and the "no earlier version after a withdrawal" rule | Architecture Owner, Data Protection lead | RR-12 closure | AM-4 |
| 9 | AM-9: choose R, (a) or (b) for the break-glass cancellation rule; accept the IR-05 residual | Architecture Owner | PG-BG rehearsal design | AM-9, IR-A11 |
| 10 | AM-10: PII field list, IP/user-agent retention after erasure; accept or fix RD-05 (search in the query string) | Privacy Owner | RR-13 closure, DC-03 | AM-10, IR-A15 |
| 11 | IR-A06: the PATCH /roles self-held-role check and the `mfa_required` field | Architecture Owner | Tracked | IR-A06 |
| 12 | Accept or require mitigation for disclosed residuals FC-05 (reset-email cap, AM-7), FC-08 (AM-13) and FC-A12 (AM-12) | Architecture Owner | Production | AM-7, AM-12, AM-13 |
| 13 | OWNER-INPUT-001: RPO, RTO, monthly availability | Product Owner | RG-1 | Gate registry |
| 14 | OWNER-INPUT-002: retention periods with legal basis | Privacy Owner | TG-04, PG-RET, RR-06 archival | Gate registry |
| 15 | OWNER-INPUT-003: restore-rehearsal cadence | Operations Owner | RG-2 | Gate registry |
| 16 | OWNER-INPUT-004: two custodians, IAM principals with MFA, custodian register | Security Owner | PG-BG, RR-09 | Gate registry |
| 17 | Commission the security assessment (DAST, authenticated scan, manual penetration test) | Security Owner | TG-03, PG-DAST | Gate registry |
| 18 | Privacy notice content, only when public intake is to be enabled | Privacy Owner, legal | PG-PRIV | IR-A23 |
| 19 | SES production access request | Owner (AWS account) | PG-EMAIL | AUT-111 |
| 20 | Production deployment approval, once everything above has evidence | Product Owner | Release | Production gate report |

Items 1–12 are group E of §3. Items 13–20 are gates or gate inputs (group F or G).

## 7. Execution plans

None of these plans has been started. Each step names its stop condition. Credentials are never pasted into chat,
issues, pull requests or logs.

### 7.1 AWS bootstrap (AUT-002, AUT-003), local first run

**Entry:** §4 prerequisites 12–16 met.

1. **Workstation (no AWS).**
   - Install `aws` v2, Terraform 1.16.4, tflint 0.64.0 (AWS ruleset 0.49.0), checkov, shellcheck, actionlint, `jq`, `gh`.
   - Make a fresh clone of `main`. Run `infra/scripts/check-manifest.sh --complete`, then `make -C infra check`, then `make -C infra github-verify`.
   - *Stop if any check fails.*
2. **Session.** As `bootstrap-operator`, run `aws sts assume-role` for `arn:aws:iam::813238078849:role/bootstrap-owner`:
   - with MFA (`--serial-number`, `--token-code`);
   - with `--duration-seconds 3600`;
   - with `--policy file://infra/config/bootstrap-session-policy.json`.

   Export the three values and `AWS_REGION=ap-south-1`, and `unset CF_API_TOKEN`. The whole run must fit in the one-hour session; if the session expires, re-assume and rerun, which is idempotent.
3. **Inventory evidence (PB-02).**
   - Run `infra/scripts/account-inventory.sh --expected-account-id 813238078849`, which writes `infra/generated/account-inventory.json`.
   - *Stop on any foreign resource.*
4. **Plan.**
   - Run `make -C infra bootstrap-plan EXPECTED_ACCOUNT_ID=813238078849`.
   - Read `infra/generated/bootstrap-plan.txt` and note the printed plan SHA-256.
   - Automatic stops: the us-east-1 read is not denied; discovery refuses the account; the plan guard or the IAM simulation reports a finding.
   - Expected plan: the state bucket, the KMS key and alias, the OIDC provider, four `veda-gh-*` roles, `veda-boundary`, and the account guardrails. Nothing else.
5. **Apply.**
   - Run `make -C infra bootstrap-apply EXPECTED_ACCOUNT_ID=813238078849 PLAN_FILE=generated/bootstrap.tfplan PLAN_SHA256=<reviewed digest>`, then type the account ID.
   - The script migrates state to S3, checks the object exists, deletes the local copy, and compares the live bucket and key policies.
   - *If it fails before state migration, keep the local state file* (runbook §6).
6. **Post-apply checks.**
   - Run the read-only commands of runbook §5.
   - Run `make -C infra github-variables`, then again with `APPLY=1`.
   - Run `make -C infra github-verify`.
7. **Evidence.**
   - Export the session's CloudTrail Event History (OD-B6).
   - Commit the inventory, the plan text, the plan digest, the outputs (no secrets) and their SHA-256 to `docs/release-evidence/AUT-002/` through a pull request.
8. **Clean-up.** Delete the operator's access key. The session expires on its own.

**Exit:** `bootstrap-outputs.json` exists; the repository variables `AWS_ROLE_ARN_*` are set; the evidence pull request is open.

### 7.2 Staging infrastructure needed before FC-01 and RR-09 (RD-01; development, needs authorization)

The minimum order for the two evidence runs:
1. AUT-301 (gated by owner item 5).
2. AUT-102.
3. AUT-103: the anchor and archive buckets with Object Lock COMPLIANCE and versioning.
4. AUT-104: a trail with S3 data events on the anchor bucket.
5. AUT-106: host role with `PutObject` only on anchors, verifier role, custodian roles per OD-6.
6. AUT-101, AUT-105, AUT-107, AUT-108 and AUT-109.
7. AUT-302: secret seeding.
8. AUT-110 and AUT-111.
9. AUT-401.

Then deploy the API with `deploy.sh`, which also gives the RR-14 evidence.

### 7.3 FC-01 evidence (with FC-03, RR-05, IR-03)

**Entry:** the FC-03 code change (§2.2) merged; §7.2 steps 1–6 applied; the API deployed with the S3 anchor store.

1. **Read back the bucket.**
   - `get-object-lock-configuration` (COMPLIANCE, retention), `get-bucket-versioning` (Enabled), `get-bucket-policy`.
   - *Stop if Object Lock is off.*
2. **Simulate the roles.**
   - `iam simulate-principal-policy` for the host role: `s3:PutObject` on `anchors/*` allowed; `s3:DeleteObject`, `s3:DeleteObjectVersion`, `s3:PutObjectRetention` and `s3:BypassGovernanceRetention` denied.
   - The verifier role: `s3:GetObject`, `s3:ListBucket` allowed; `s3:PutObject` denied.
3. **Write an anchor.**
   - Run `veda maintenance anchor-chain` on the host through the `veda-drill` SSM document.
   - The trail shows `PutObject` by the host-role session only.
4. **Negative writes.**
   - With the host role, overwrite an existing anchor key without `If-None-Match`; the bucket policy must refuse it (FC-03).
   - With the host role, delete a version; expect AccessDenied or an Object Lock refusal.
   - Confirm that verification reads the version id recorded in the manifest.
   - Record all three.
5. **Verify.** Run `veda maintenance verify-chain` with the verifier role: `ok`.
6. **Tamper drill, on a staging copy of the database only.**
   - Rewrite an old row, recompute the chain with the chain key, post a fresh anchor.
   - `verify-chain` must report `anchor mismatch` at the earliest contradicted anchor, and `ChainVerificationFailed` must fire (RG-5 routing).
7. **Archival.** Once staging retention values exist (OWNER-INPUT-002, or a staging-only value the owner approves), run `archive-security-events`, then `verify-chain`: anchors inside the archive verify against the export (RR-06).

**Evidence:** the collector summary with SHA-256 under `docs/release-evidence/FC-01/`.

**Closes:** FC-01, FC-03, RR-05 and IR-03; RR-06 after step 7.

### 7.4 RR-09 break-glass rehearsal (with IR-06, PG-BG, AM-9)

**Entry:** owner items 7, 9 and 16 decided; the custodian roles (AUT-106), the host and Session Manager (AUT-107, AUT-108), SES (AUT-111) and the seeded fixtures in place; `VEDA_BREAK_GLASS_CUSTODIANS` set to the two custodian role ARNs.

1. **Negative cases first.** Each must be refused and must write the named FAILURE event:
   - the CLI run with the host instance role (`HOST_IDENTITY`);
   - the CLI run with no credentials (`NO_CUSTODIAN_CREDENTIALS`);
   - custodian A requesting and approving the same request (the same-human refusal);
   - a request while an eligible Founder exists (IR-05).
2. **Positive run.**
   - In a single-Founder fixture, custodian A, in their own SSM session with their own MFA-backed session, runs `break-glass request`.
   - Founders and the target receive the cancel-link email.
   - Custodian B, in a separate session, runs `approve`.
3. **Cancellation.**
   - On a second request, a notified Founder cancels it through `/approvals/cancel`.
   - If AM-9 chooses R, a cancellation by the target is refused.
4. **Cooling-off.** Execution happens only after `not_before` (24 h) and only if no eligible Founder has reappeared.
5. **Evidence.**
   - CloudTrail `AssumeRole` events for both custodians with MFA present.
   - Session Manager session records.
   - The `BREAK_GLASS_*` security events.
   - The notification and outbox rows.
   - The timeline.

**Closes:** RR-09 and IR-06; PG-BG together with OWNER-INPUT-004.

### 7.5 Accessibility verification

1. **Automated, already in CI:**
   - axe-core on 16 screens and states (0 serious or critical);
   - the component tests with axe;
   - the token contrast test.
2. **Code still open:**
   - FC-15 (site focus ring);
   - OI-RM-2 (Firefox and WebKit E2E legs).

   Both are small changes, but they need authorization.
3. **Manual:** run [accessibility-manual-script.md](../operations/accessibility-manual-script.md) on the staging build:
   - NVDA with Firefox and Chrome;
   - VoiceOver on macOS and iOS;
   - keyboard only at 320 px, 200 % and 400 % zoom.

   A local release build can be used for a rehearsal run; it does not close OI-RM-5.
4. **Close:** OI-RM-5 and the manual part of UI-016 close on the script's pass rule. Any FAIL becomes a tracked item.

## 8. Exact next actions

| # | Action | Who | Unblocks |
|---|---|---|---|
| 1 | Review and merge this status update | Owner | A current register |
| 2 | Decide RD-04: commission the independent review of the pre-bootstrap closure, or record a waiver | Owner | Bootstrap |
| 3 | Set up the operator workstation (§4 item 14) and run `make -C infra check` on a clean clone of `main` | Owner | Bootstrap |
| 4 | Add a virtual MFA device to `bootstrap-operator`; create its access key only on the day of the run | Owner | Bootstrap |
| 5 | Give written authorization for the bootstrap window, then run §7.1 | Owner | Staging |
| 6 | Decide owner items 4, 5 and 6 (start of infrastructure work, AUT-301 gate, Cloudflare token) | Owner | RD-01 |
| 7 | Decide OD-6 and name the custodians (owner items 7, 16) | Security Owner | RR-09 rehearsal |
| 8 | Record the AM-4 option (a) confirmation, AM-9 and AM-10 (owner items 8–10) | Architecture Owner, Privacy Owner | RR-12, RR-13, PG-BG |
| 9 | Provide OWNER-INPUT-001, -002 and -003 | Product, Privacy and Operations Owners | RG-1, RG-2, PG-RET |
| 10 | Authorize the remaining code items of §2.2 (FC-03 and RR-15 first, then FC-10, DC-05, RD-02, FC-15, OI-RM-2) | Owner | FC-01 evidence, RG-1, RG-2, governance use, CI integrity |
| 11 | Commission the security assessment and request SES production access | Security Owner, Owner | PG-DAST, PG-EMAIL |
