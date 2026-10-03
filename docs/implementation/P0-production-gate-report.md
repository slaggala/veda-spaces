# P0 production-gate report

- **Status on 2026-09-30:** production deployment approval is **PENDING**.
- **Updated 2026-10-03** after pull requests #3 to #11: production deployment approval is still **PENDING**. Every
  application-code production blocker named below on 2026-09-30 is resolved in code; what remains is staging
  evidence, owner decisions and the registry gates. Release readiness:
  [P0-release-readiness-report.md](P0-release-readiness-report.md).
- Nothing is deployed.
- Public lead intake is disabled.
- Every production gate below must pass on recorded evidence first (the registry rule: missing evidence is FAIL).

## Registry gates

| Gate | Title | Owner | Status |
|---|---|---|---|
| OWNER-INPUT-001 | Recovery objectives and availability target | Product Owner | **Blocked — awaiting owner input** |
| OWNER-INPUT-002 | Retention periods | Privacy Owner | **Blocked — awaiting owner input** |
| OWNER-INPUT-003 | Restore-rehearsal cadence | Operations Owner | **Blocked — awaiting owner input** |
| OWNER-INPUT-004 | Break-glass custodians | Security Owner | **Blocked — awaiting owner input** |
| TG-02 | Real KMS blob fits the MFA columns (F-13) | Security Owner | **Pending** |
| TG-03 | Security assessment tracked from F-19 | Security Owner | **Pending** |
| TG-04 | Retention values applied (F-15) | Privacy Owner | **Blocked — awaiting OWNER-INPUT-002** |
| TG-05 | Runbook rehearsal (F-12) | Operations Owner | **Pending** |
| TG-06 | Single-process performance and revocation under load (F-09, F-10) | Operations Owner | **Pending** |
| TG-07 | Targeted independent verification of the final minor remediation | Architecture Owner | **Pending** |
| RG-1 | Recovery objectives met | Operations Owner | **Pending** |
| RG-2 | Restore verification green | Operations Owner | **Pending** |
| RG-3 | Single instance and process enforced | Operations Owner | **Pending** |
| RG-4 | Load and contention | Operations Owner | **Pending** |
| RG-5 | Backup and disk alerts | Operations Owner | **Pending** |
| RG-6 | Encrypted persistent volume | Operations Owner | **Pending** |
| RG-7 | Migration runbook rehearsal | Operations Owner | **Pending** |
| RG-8 | PostgreSQL gate recorded | Architecture Owner | **Pending** |
| RG-9 | No SQLite-incompatible usage | Architecture Owner | **Pending** |
| PG-DAST | Security assessment | Security Owner | **Pending** |
| PG-RET | Retention values applied | Privacy Owner | **Blocked — awaiting OWNER-INPUT-002** |
| PG-BG | Break-glass readiness | Security Owner | **Blocked — awaiting OWNER-INPUT-004** |
| PG-EMAIL | Production email readiness | Operations Owner | **Pending** |
| PG-PRIV | Privacy notice and consent | Privacy Owner | **Pending** |
| PGM-1 | PostgreSQL migration rehearsal (includes A-13 criterion) | Architecture Owner | **Not applicable until post-P0** |

## Open items that block production

Updated 2026-10-03. Items resolved in code keep a row while their staging evidence or owner decision is outstanding.

| ID | Severity | Title | Status |
|---|---|---|---|
| RD-01 | MAJOR | Staging infrastructure (AUT-101…AUT-112, AUT-201…AUT-205, AUT-301, AUT-302, AUT-401) not built; every staging gate depends on it | OPEN — STAGING BLOCKER (CRITICAL PATH) |
| IR-03 | MAJOR | Security-event chain verification never consults the external anchor and accepts deletion of the anchored prefix and tail truncation | CODE RESOLVED (RR-05/06/07); STAGING S3 EVIDENCE REQUIRED |
| FC-01 | MAJOR | Verification checked only the latest anchor | RESOLVED IN CODE (PR #7) — STAGING EVIDENCE REQUIRED (SEPARATE ANCHOR WRITER ROLE, FC-03) |
| FC-03 | MAJOR | S3 anchor/archive store writes without IfNoneMatch and reads the current object version | OPEN — CODE CHANGE AND STAGING EVIDENCE REQUIRED (PREREQUISITE OF FC-01 EVIDENCE) |
| IR-06 | MAJOR | Break-glass CLI trusts a caller-supplied --principal-arn (two-person control is self-asserted) | RESOLVED IN CODE (RR-09, PR #8) — STAGING REHEARSAL REQUIRED (PG-BG) |
| RR-09 | MAJOR | Break-glass STS identity check sees the host instance role, not the custodian | RESOLVED IN CODE (PR #8) — OWNER DECISION OD-6, OWNER-INPUT-004 AND STAGING REHEARSAL REQUIRED |
| IR-11 | MAJOR | Backup, restore verification and deploy/migrate runbooks | PARTIALLY RESOLVED (RR-14 fixed; RR-15 open) |
| RR-15 | MINOR | Disaster-restore runbook does not work as written: restore-verify fails on a Litestream-restored file, Litestream is not stopped before the swap, one failure path emits no metric, the off-host replica is never verified | OPEN — STAGING BLOCKER (code and runbook changes still required) |
| IR-12 | MAJOR | No metrics, no alert routing, error tracker optional (LOG-006 is mandatory in P0) | CODE RESOLVED (RR-07); RG-5 REQUIRED |
| IR-38 | MINOR | Browser E2E evidence overstates coverage | PARTIALLY RESOLVED (Firefox and WebKit legs, OI-RM-2) |
| OI-RM-2 | MINOR | Browser matrix: Firefox and WebKit legs (12 §4.8) | OPEN |
| OI-RM-4 | MINOR | Developer machines on Node ≥ 22.13 | OPEN |
| OI-RM-5 | MINOR | Manual screen-reader script (NVDA/VoiceOver) and 200 % zoom | OPEN — script: [accessibility-manual-script.md](../operations/accessibility-manual-script.md) |
| FC-15 | MINOR | Site focus-ring colour below 3:1 non-text contrast | OPEN — PRODUCTION (SITE ACCESSIBILITY) |
| RR-12 | MINOR | DEV-004 residuals | RESOLVED (PR #10) — OWNER CONFIRMATION OF AM-4 OPTION (a) REQUIRED |
| RR-13 | MINOR | Residual PII paths in Sentry and outbox_event.last_error | RESOLVED IN CODE (PR #9) — AM-10 STAGING CHECK REQUIRED |
| RR-18 | MINOR | Accessibility remnants (step-up expiry, palette semantics, tabpanel wiring, account menu) | RESOLVED IN CODE (PR #11) — MANUAL SCREEN-READER RUN REQUIRED (OI-RM-5) |
| DEV-004 | DECISION | Staff lead update accepts a re-consent object | APPROVED WITH CONDITIONS (via AM-4, 2026-09-30); conditions met in code by RR-12 |
| OI-RM-1 | MAJOR | First CI run of the remediation commit | RESOLVED (CI green on PRs #4 to #11) |

Resolved in code with no further production condition: FC-09, FC-A04, IR-A04, IR-A08 (PR #5); FC-13, FC-14 (PR #6).

## Deferred decisions

- **AM-9, AM-10:** deferred to staging/production, and required before production.
- **AM-4:** approved with conditions. RR-12 (PR #10) completed rules (a)–(d) with option (a); the owner still records the choice of option (a) and the earlier-version rule before production.

## Public-intake enablement

Enabling public intake is a separate, gated change. It needs:
- PG-PRIV (the Privacy Notice);
- real Turnstile keys;
- the CSP `connect-src` for the API origin;
- CORS;
- staging verification;
- production approval.
