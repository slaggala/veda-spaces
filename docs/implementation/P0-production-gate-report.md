# P0 production-gate report

- **Status on 2026-09-30:** production deployment approval is **PENDING**.
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

| ID | Severity | Title | Status |
|---|---|---|---|
| IR-03 | MAJOR | Security-event chain verification never consults the external anchor and accepts deletion of the anchored prefix and tail truncation | CODE RESOLVED (RR-05/06/07); STAGING S3 EVIDENCE REQUIRED |
| IR-06 | MAJOR | Break-glass CLI trusts a caller-supplied --principal-arn (two-person control is self-asserted) | PARTIALLY RESOLVED |
| IR-11 | MAJOR | Backup (Litestream config, nightly snapshot), restore verification and API deploy/migrate runbooks are absent from the deliverable | PARTIALLY RESOLVED (RR-14 fixed; RR-15 open) |
| IR-12 | MAJOR | No metrics, no alert routing, error tracker optional (LOG-006 is mandatory in P0) | CODE RESOLVED (RR-07); RG-5 REQUIRED |
| IR-38 | MINOR | Browser E2E evidence overstates coverage and security-critical modules have the lowest coverage | PARTIALLY RESOLVED |
| DEV-004 | DECISION | Staff lead update accepts a re-consent object | APPROVED WITH CONDITIONS (via AM-4, 2026-09-30) |
| OI-RM-1 | MAJOR | First CI run of the remediation commit | OPEN |
| OI-RM-2 | MINOR | Browser matrix: Firefox and WebKit legs (12 §4.8) | OPEN |
| OI-RM-4 | MINOR | Developer machines on Node ≥ 22.13 | OPEN |
| OI-RM-5 | MINOR | Manual screen-reader script (NVDA/VoiceOver) and 200 % zoom | OPEN |
| RR-09 | MAJOR | Break-glass STS identity check sees the host instance role, not the custodian, when the CLI runs via docker compose as the runbook prescribes; with no credentia | OPEN — PRODUCTION BLOCKER (OWNER DECISION OD-6) |
| RR-12 | MINOR | DEV-004 residuals: alternating between published policy versions is accepted without withdrawal; consent history activity is mutable at DB level; staff create-t | OPEN — PRODUCTION BLOCKER |
| RR-13 | MINOR | Residual PII paths: Sentry transaction events carry request query strings (e.g. lead search by email); outbox_event.last_error stores provider errors containing | OPEN — PRODUCTION BLOCKER |
| RR-15 | MINOR | Disaster-restore runbook does not work as written: restore-verify fails on a Litestream-restored file, Litestream is not stopped before the swap, one failure pa | OPEN — STAGING BLOCKER |
| RR-18 | MINOR | Accessibility remnants: step-up dialog has no pre-expiry warning; command palette listbox/option semantics and vs-tabs tabpanel wiring unchanged; account menu s | OPEN — PRODUCTION BLOCKER |

## Deferred decisions

- **AM-9, AM-10:** deferred to staging/production, and required before production.
- **AM-4:** approved with conditions. Its completion (RR-12, rules (a)–(d) and the choice of option (a) or (b)) is required before production.

## Public-intake enablement

Enabling public intake is a separate, gated change. It needs:
- PG-PRIV (the Privacy Notice);
- real Turnstile keys;
- the CSP `connect-src` for the API origin;
- CORS;
- staging verification;
- production approval.
