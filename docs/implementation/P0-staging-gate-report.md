# P0 staging-gate report

As of 2026-09-30, no staging environment has been built or evaluated. None of the items below has passed.

**Updated 2026-10-03:** still no staging environment. The account is chosen and its manifest committed (PR #3,
`veda-staging`, 813238078849); the bootstrap has not been run (prerequisites RD-03, RD-04 and the owner's run
authorization), and no staging stack beyond the bootstrap exists (RD-01). Release readiness and the execution plans:
[P0-release-readiness-report.md](P0-release-readiness-report.md).

## Findings with staging scope

| ID | Title | Staging requirement | Status |
|---|---|---|---|
| IR-01 | MFA enrollment confirmation is not bound to the caller: a bearer token plus any unbound enrollment challenge grants MFA verification and step-up to the token's  | Cleared | RESOLVED — AM-11 APPROVED WITH CONDITIONS (2026-09-30) |
| IR-09 | Production-safety validation is fail-open: any VEDA_ENV other than exactly 'production' (including staging, unset, 'prod') runs with publicly derivable dev keys | Cleared by the fix; confirmation by targeted re-review | RESOLVED |
| IR-16 | DEV-004 staff re-consent overwrites consent evidence, mixes provenance and is accepted without prior withdrawal | Cleared | RESOLVED (completed by RR-12, PR #10; AM-4 APPROVED WITH CONDITIONS on 2026-09-30) |
| IR-39 | No Python formatter or type checker enforced, no ESLint/Prettier; frontend dev toolchain carries dev-only advisories (upgrade needs Node ≥ 20.19) | Cleared by the fix; confirmation by targeted re-review | RESOLVED |
| DEV-001 | MFA factor uniqueness permits the current authenticator and a pending replacement to coexist during controlled re-enrollment | Blocks with merge | APPROVED (via AM-1, 2026-09-30) |
| DEV-002 | Invitation acceptance returns an MFA-enrollment step when MFA is required instead of immediate final success | Blocks with merge | APPROVED WITH CONDITIONS (via AM-2, 2026-09-30) |
| DEV-003 | Login accepts an optional CAPTCHA token | Blocks with merge | APPROVED (via AM-3, 2026-09-30) |
| DEV-004 | Staff lead update accepts a re-consent object | Blocks with merge | APPROVED WITH CONDITIONS (via AM-4, 2026-09-30) |
| DEV-005 | Break-glass cancel link endpoint and page (06 §7.5 step 5) | Blocks with merge | APPROVED WITH CONDITIONS (via AM-5, 2026-09-30) |
| DEV-006 | mfa_challenge binds enrollment transactions to a factor and a path | Blocks with merge | APPROVED WITH CONDITIONS (via AM-11, 2026-09-30) |
| DEV-007 | Per-email login and forgot-password limits keyed by (email, network) | Blocks with merge | APPROVED WITH CONDITIONS (via AM-7, 2026-09-30) |
| DEV-008 | Readiness accepts a declared newer schema and hides details at the edge | Blocks with merge | APPROVED WITH CONDITIONS (via AM-6, 2026-09-30) |
| OI-RM-4 | Developer machines on Node ≥ 22.13 | Blocks | OPEN |
| RR-04 | DEV-007 keys per-email login/forgot limits by (email, network), removing the only cross-network bound on password guessing for MFA holders and multiplying reset | Real Turnstile keys and deployed proxy CIDR to be verified | RESOLVED — AM-7 APPROVED WITH CONDITIONS (2026-09-30) |
| RR-05 | A forged archive manifest written with the host credential hides deletion of any prefix of the security-event chain, including anchored rows | Real S3 Object Lock and role separation to be evidenced | RESOLVED IN CODE — STAGING EVIDENCE (S3 OBJECT LOCK, WRITER/VERIFIER ROLES) REQUIRED |
| RR-06 | Archival writes the write-once manifest before the database commit; any later failure produces a permanent false 'prefix removed' alarm and blocks archival fore | Archival stays disabled until OWNER-INPUT-002 | RESOLVED IN CODE — STAGING EVIDENCE REQUIRED BEFORE ARCHIVAL IS ENABLED |
| RR-07 | CLI, scheduler and worker processes never configure logging, so every maintenance/worker metric (backup, chain, anchor, invariants, dead outbox) is dropped and  | Alarm acceptance (RG-5) | RESOLVED IN CODE — ALARM WIRING (RG-5) REQUIRED IN STAGING |
| RR-09 | Break-glass STS identity check sees the host instance role, not the custodian, when the CLI runs via docker compose as the runbook prescribes; with no credentia | Rehearsal with two custodian principals and CloudTrail | RESOLVED IN CODE (PR #8) — OWNER DECISION OD-6, OWNER-INPUT-004 AND STAGING REHEARSAL REQUIRED |
| RR-14 | Snapshot directory defaults to container storage and is not required in staging/production, so deploy.sh's pre-deploy snapshot in a --rm container is lost | Staging deploy evidence | RESOLVED IN CODE — STAGING DEPLOY EVIDENCE REQUIRED |
| RR-15 | Disaster-restore runbook does not work as written: restore-verify fails on a Litestream-restored file, Litestream is not stopped before the swap, one failure pa | Blocks (RG-1, RG-2) | OPEN — STAGING BLOCKER |
| FC-02 | NoEffectiveRecoveryAdmin metric value is redacted by the log scrubber, so its CRITICAL alarm can never fire (RR-07 residual) | staging (alarm acceptance); one-line fix recommended before merge | RESOLVED IN CODE — ALARM ROUTING AND TEST-FIRE REMAIN RG-5 (STAGING) |
| FC-03 | S3 anchor/archive store writes without IfNoneMatch and reads the current object version, so an overwrite with the app credential creates a new version that veri | staging evidence / production gate | OPEN — CODE CHANGE AND STAGING EVIDENCE REQUIRED (PREREQUISITE OF FC-01 EVIDENCE) |
| FC-10 | Approvals card does not show the requested Founder status, so an approver cannot distinguish RESTORE from DELETE or DISABLE except through the requester's free- | staging (before Founders use governance) | OPEN — STAGING BLOCKER |
| FC-01 | Verification checked only the latest anchor; anchors must also come from a separate writer role | Writer/verifier role separation and real Object Lock (AUT-103, AUT-106) | RESOLVED IN CODE (PR #7) — STAGING EVIDENCE REQUIRED (SEPARATE ANCHOR WRITER ROLE, FC-03) |
| RD-01 | Staging infrastructure (AUT-101…AUT-112, AUT-201…AUT-205, AUT-301, AUT-302, AUT-401) not built | Blocks | OPEN — STAGING BLOCKER (CRITICAL PATH) |
| RD-02 | Infra offline checks are not a required CI check | Blocks (before AUT-301) | OPEN — STAGING (CI gate integrity) |
| RD-03 | Bootstrap operator has no MFA device or access key | Blocks (bootstrap) | OPEN — OWNER ACTION BEFORE BOOTSTRAP |
| RD-04 | Pre-bootstrap closure not independently reviewed | Blocks (bootstrap) | OPEN — OWNER DECISION REQUIRED |
| FC-11 | mypy ratchet suppression detection incomplete: inline '# mypy:' config comments, per-module strict_optional overrides, shadow mypy.ini/.mypy.ini and a spoof 'my | staging (CI gate integrity) | RESOLVED |

## Staging evidence required by amendment conditions

| Amendment | Owner decision | Staging dependency |
|---|---|---|
| AM-1 | APPROVED | Migration upgrade-with-data on SQLite, PostgreSQL 16 and 18 (CI and local evidence); no staging host run yet. |
| AM-2 | APPROVED WITH CONDITIONS | None. |
| AM-3 | APPROVED | Real Turnstile keys in staging (IR-18) before production. |
| AM-4 | APPROVED WITH CONDITIONS | None required. |
| AM-5 | APPROVED WITH CONDITIONS | Staging check that outbox retention ≥ break-glass window (IR-A10). |
| AM-6 | APPROVED WITH CONDITIONS | RG-7 rollback rehearsal (not performed). |
| AM-7 | APPROVED WITH CONDITIONS | Real Turnstile keys (success, failure, outage simulated by a blocked siteverify); deployed trusted-proxy CIDR; load probe of the thresholds; alarm on ACCOUNT_THROTTLED account_* and aggregate escalation. |
| AM-8 | APPROVED | None. |
| AM-9 | DEFERRED TO STAGING / PRODUCTION | Staging-required: custodian identity rehearsal with two principals and CloudTrail (RR-09, PG-BG), including a cancellation by a notified Founder; if R is chosen, a refused cancellation by the target. |
| AM-10 | DEFERRED TO STAGING / PRODUCTION | Staging-required: an erasure run on a staging copy showing every listed field rewritten; a provider-error outbox row showing last_error redacted; a Sentry test project receiving a transaction without query strings or addresses. The code side is in place (RR-13, PR #9). |
| AM-11 | APPROVED WITH CONDITIONS | Migration on the staging copy; RG-7 rehearsal (not performed). |
| AM-12 | APPROVED WITH CONDITIONS | None. |
| AM-13 | APPROVED WITH CONDITIONS | None. |

## Registry gates first evidenced in staging

Each of these gates needs staging evidence before its production evaluation:
- RG-1 to RG-9, including the RG-5 alarm test-fire and the RG-7 rollback rehearsal;
- TG-05 and TG-06;
- PG-BG, PG-EMAIL and PG-DAST.

All of them are unchanged from the registry: Pending, or Blocked on owner input.
