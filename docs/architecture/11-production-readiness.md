# 11 — Production Readiness Review

Governing decisions: [ADR-002](decisions/ADR-002-uuidv7-identifiers.md) · [ADR-003](decisions/ADR-003-audit-contract.md) · [ADR-004](decisions/ADR-004-security-event-log.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-008](decisions/ADR-008-aws-hosting.md)

This document is a deliberate critique of documents 02–10.

| Severity | Meaning |
|---|---|
| **High** | Resolve before go-live |
| **Medium** | Resolve soon after go-live |
| **Low** | Monitor or accept |

**No capacity figure in this document is a measurement.** Sizing statements are assumptions (§10) until production traffic exists.

## 1. Scalability and capacity

### 1.1 Position

- P0 serves a small internal staff user base (ASM-001) plus public enquiries.
- The design deliberately runs **one application instance on SQLite** (ADR-008, OPS-006), so no horizontal scaling is claimed.
- Scaling out is possible only after the PostgreSQL release gate (§3.3). Before that, the controls are:
  - efficient indexed queries (NFR-001);
  - edge protection for public endpoints;
  - early detection of write contention (§3.3 signals).

### 1.2 Findings

| # | Finding | Sev | Recommendation |
|---|---|---|---|
| S1 | A single host is a single point of failure. A VM, volume or AZ outage stops the app. The website stays up, and enquiries fall back to WhatsApp (LEAD-019). | Medium | Accept for the MVP. Scripted rebuild, rehearsed restore (§2), owner-approved RTO (OPS-005). |
| S2 | In-process caches (session status, effective permissions, idempotency, rate limits) assume one instance | Low | Consistent with OPS-006. Interfaces are abstracted, and they move to Redis at the PostgreSQL gate. |
| S3 | Exact `COUNT(*)` on large filtered lists | Low | Capped totals (08 §2.5) |
| S4 | `LIKE '%term%'` search can't use B-tree indexes | Medium (at scale) | Acceptable on SQLite at the NFR-001 fixture size (ASM-007). `pg_trgm` after the gate. |
| S5 | Live dashboard aggregates | Low | Add a read model if the NFR-001 p95 target is missed in load tests |
| S6 | Security-event writes serialize on the hash chain (05 §9.6) | Low | SQLite serializes writers anyway. On PostgreSQL a transaction-scoped advisory lock serializes chain appends. Measure append latency in load tests (ASM-004). |
| S7 | Argon2id memory per login | Medium | Semaphore on concurrent hashes. Host sizing confirmed by benchmark (ASM-010). |
| S8 | TOKEN_REFRESH events are written on every refresh (ADR-004) | Low | Indexed, cursor-paginated and retention-managed. Volume is measured, not assumed (SEVT-010). |

## 2. Availability, backup and recovery (ADR-008)

| # | Finding | Sev | Recommendation |
|---|---|---|---|
| B1 | SQLite file corruption or deletion | High | Litestream continuous replication plus nightly `VACUUM INTO` snapshots with Object Lock plus EBS snapshots (02 §12.3, OPS-002) |
| B2 | Untested backups | High | Automated restore verification job with alerting (OPS-009, SEC-008) |
| B3 | Migrations on a live single file | High | Pause the worker → snapshot → migrate → health check → resume. Rollback by snapshot restore (OPS-004). |
| B4 | Region outage | Low | Cross-region replica bucket. DR runbook. |
| B5 | Volume lost on instance rebuild | Medium | Dedicated volume, `DeleteOnTermination=false` (OPS-007) |
| B6 | **RPO and RTO are not yet approved by the owner** | High (go-live) | OWNER-INPUT-001. Architecture provides the mechanisms, and the first rehearsal measures achievable values for approval. Alert thresholds derive from the approved RPO. |

## 3. SQLite limitations and PostgreSQL migration readiness

### 3.1 PostgreSQL hazards designed out

| Hazard | Mitigation |
|---|---|
| `user` is a reserved word in PostgreSQL (`SELECT * FROM user` returns the session role) | Physical table `app_user`. No table named `user` exists or may be created (ADR-001, conformance check 03 §2.7). |
| SQLite's dynamic typing and unenforced `VARCHAR(n)` | Generated CHECK constraints for types, lengths, booleans and JSON validity (03 §12). Server-side validation at the API. |
| Booleans stored as 0/1 | Kernel BOOL type, explicit mapping (03 §12) |
| Text datetimes | Fixed-width UTC ISO format → `timestamptz` |
| JSON1 vs `jsonb` | No JSON-path queries in business code |
| `LIKE` case behavior differs | `lower()` on both sides. Dual-engine tests. |
| Partial indexes | Generated per dialect |
| SQLite `ALTER TABLE` limits | Alembic batch mode. Additive-only evolution (10 §2). |
| FKs off by default in SQLite | Pragma set per connection and verified at readiness |
| Money precision | Integer minor units on both engines (DATA-016) |
| Triggers syntax | Per-engine immutability guards in migrations (07 §6.2) |

### 3.2 GUID mapping (ADR-002, DATA-012)

**Decision.** SQLite stores `CHAR(32)` canonical text. PostgreSQL stores native `uuid`. The kernel `GUID` type converts at the driver boundary, so code, JSON and APIs only ever carry the 32-lowercase-hex form. Data migration is `CAST(col AS uuid)`, which PostgreSQL accepts for unhyphenated input, verified by checksums (§3.4).

**Risk.** PostgreSQL tools display hyphenated UUIDs. This is mitigated by a documented `replace(id::text,'-','')` view convention for ad-hoc SQL, and by the rule that APIs never emit hyphenated ids.

### 3.3 SQLite limits and the release gate (ADR-008, OPS-008)

| Limit | Impact |
|---|---|
| One writer at a time | Contention under concurrent writes |
| Local disk, one host | No multiple instances, no managed HA |
| No network access for BI | Reporting via APIs and exports |
| No row-level locking | Unsuitable for stock and money workflows |
| No DB roles or grants | Immutability via triggers only |

**Mandatory gate.** PostgreSQL migration must be complete before **any** of the following goes live:

- procurement;
- inventory;
- finance;
- more than one application instance (multi-instance scale).

**Early-warning signals** bring the gate forward. These thresholds are owner-reviewable configuration:

- sustained `SQLITE_BUSY` errors;
- write latency above the NFR-001 target;
- restore time exceeding the owner-approved RTO;
- a business need for live BI.

### 3.4 Migration runbook (outline)

> Traces: OPS-004

1. **Readiness (continuous from day 1).**
   - Dual-engine CI (OPS-001), including the conformance check on both engines.
   - RDS PostgreSQL provisioned.
   - Roles created: app role without DELETE on evidence tables; retention role; read-only role.
2. **Rehearsal (staging, at least twice).**
   - Restore an anonymized production snapshot, then copy in FK order with type casts (GUID → uuid).
   - Verify:
     - per-table row counts;
     - canonical-JSON checksums per table;
     - FK integrity;
     - the `security_event_log` hash chain (recomputed on PostgreSQL; must match);
     - a field-level sample;
     - the full E2E suite.
3. **Cutover (announced window).**
   - Maintenance mode. The website automatically falls back to WhatsApp.
   - Stop the worker, take a final snapshot, copy, verify, switch `DATABASE_URL`, smoke test, reopen.
4. **Rollback.** The SQLite snapshot stays read-only for a defined window. Changes after cutover are identifiable via `audit_log.performed_on`.
5. **After cutover.** Enable `pg_trgm`, `LISTEN/NOTIFY` and audit partitioning. Retire Litestream. Obtain new owner-approved RPO/RTO values.

## 4. Audit and security-event concerns

| # | Finding | Sev | Recommendation |
|---|---|---|---|
| A1 | ORM bulk statements and raw SQL bypass the flush hook | High | Lint ban, `bulk_mutate` helper, and tests counting audit rows per service call (07 §3) |
| A2 | Direct file access could alter SQLite | Medium | SSM-only break-glass (CloudTrail). The security-event hash chain detects tampering with that log (SEVT-006). Audit-log chain in P2 (AUDIT-013). |
| A3 | PII in audit payloads vs DPDP erasure | Medium | `pii_fields` plus the anonymization procedure (07 §8.2) |
| A4 | Evidence stores vs the generic contract (never updated, purge by retention) | Resolved | Exception registry EXC-001 and EXC-002 (03 §2.9). Columns are still present. |
| A5 | Authentication telemetry volume polluting the entity audit | Resolved | Dedicated `security_event_log` (ADR-004) |
| A6 | Secrets leaking into security events | High | Allow-listed `detail` keys, writer rejects unknown keys, prohibited-content test (05 §9.3, SEVT-003) |
| A7 | Failure events lost on rollback | Resolved | Separate transaction for failure and denial events (SEVT-011) |
| A8 | Chain serialization under PostgreSQL concurrency | Low | Advisory lock. Measured in the migration rehearsal. |
| A9 | Retention durations need legal confirmation | Medium | Configurable defaults (ASM-006) |

## 5. Security concerns

> Traces: RBAC-014, SEC-004, SEC-010

| # | Finding | Sev | Recommendation |
|---|---|---|---|
| X1 | XSS exposes the in-memory access token | High | Strict CSP, Lit auto-escaping, `unsafeHTML` banned, Trusted Types (later) |
| X2 | Refresh-token theft | Medium | Rotation, reuse detection, session revoke, MFA |
| X3 | Credential stuffing against privileged accounts | Resolved in design | **MFA mandatory for Founder and Admin, and for any holder of a sensitive permission** (ADR-006), plus lockout and rate limits |
| X4 | Public intake abuse | Medium | Turnstile, honeypot, rate limits, idempotency, `PUBLIC_INTAKE_BLOCKED` telemetry (LEAD-018) |
| X5 | Enumeration | Low | Uniform responses and timing (05 §2.2) |
| X6 | JWT signing key compromise | Medium | ES256 in SSM, `kid` rotation, emergency runbook |
| X7 | CSRF on cookie endpoints | Low | SameSite=Strict + Origin check + custom header |
| X8 | Broken object-level authorization (OWASP API1) | High | Scoped repositories, 404 for out-of-scope rows, matrix and scope tests (06 §8, §10) |
| X9 | Mass assignment | Medium | Closed DTOs, `UNKNOWN_FIELD` (08 §2.2) |
| X10 | PII in logs, Sentry or email | Medium | Masking, scrubbing, minimal email content |
| X11 | Supply chain | Medium | Lockfiles with hashes, audits, image scanning (SEC-007) |
| X12 | Origin bypass | Medium | Cloudflare-only security group + authenticated origin pulls (SEC-006) |
| X13 | TOTP secret exposure | High | KMS envelope encryption, shown once, never logged or returned (MFA-010) |
| X14 | MFA reset used for account takeover | High | Privileged, step-up, reason-required, no-self, no-stronger-target workflow with CRITICAL alerting (MFA-007) |
| X15 | Recovery code theft | Medium | Keyed hashes only, single use, user email on use (MFA-005) |
| X16 | Malformed or guessable ids | Low | UUIDv7 validation, `INVALID_ID`, no sequential identifiers exposed (DATA-013). `lead_number` is internal only (LEAD-025). |

### 5.6 Privacy and DPDP Act 2023 (SEC-009)

> Traces: AUDIT-011

| Obligation | Design response |
|---|---|
| Notice and consent | Required consent on the public form, with policy version, timestamp and source context (channel, page, IP) (LEAD-012, ADR-005) |
| Purpose limitation | Enquiry response and service delivery only. Marketing consent is a separate future field (additive). |
| Data principal rights | P0: a manual process via the published privacy contact. The anonymization procedure is in 07 §8.2. |
| Retention limitation | Configurable anonymization of closed, non-converted leads (default proposed: 3 years, ASM-006) |
| Safeguards and breach notification | This document's controls, plus an incident runbook |
| Residency | Primary data in the chosen AWS region (ASM-012) |

## 6. RBAC and MFA-policy concerns

| # | Finding | Sev | Recommendation |
|---|---|---|---|
| R1 | Admin holds `role.manage` | High | Anti-escalation guards G1, G2, G9 and G10 (06 §7) |
| R2 | Lockout of all administrators | High | G4, plus the break-glass CLI via SSM (audited, notifies) |
| R3 | Permission explosion | Medium | Grouping, search, scope instead of new codes |
| R4 | Role explosion | Medium | Time-bound direct grants. Access review report. |
| R5 | UI and server drift | Low | Server-computed `allowed_transitions` and capability flags |
| R6 | Stale permissions within the cache window | Low | `authz_version`, TTL ≤ 30 s |
| R7 | Ambiguous OWN scope | Medium | Per-resource ownership registry (06 §4) |
| R8 | Role-name checks creeping in, including in MFA code | Medium | Lint on role-code literals. MFA policy uses `role.mfa_required`, `app_user.mfa_required` and sensitive permissions (MFA-002). |
| R9 | A role with sensitive permissions set `mfa_required = false` | Low | Irrelevant: holding any sensitive permission independently requires MFA (MFA-004) |

## 7. Decisions resolved and remaining owner inputs

All decisions previously open in this document are now resolved by accepted ADRs:

| Previously open item | Resolution |
|---|---|
| Physical name of the user table | ADR-001: `app_user` |
| Identifier format and PostgreSQL mapping | ADR-002: UUIDv7, 32-hex, `CHAR(32)` / native `uuid` |
| Actor columns, extra production columns | ADR-003: all nine columns everywhere, actors NOT NULL FKs, exception registry |
| Where authentication telemetry lives | ADR-004: `security_event_log` |
| Required lead fields | ADR-005: name, phone, consent required; the rest optional |
| MFA timing and scope | ADR-006: mandatory Founder/Admin in P0, configurable for Sales |
| TypeScript, email provider | ADR-007: Lit + TypeScript. SES in production with a dev/test adapter. |
| Backend host | ADR-008: AWS, single instance on SQLite, PostgreSQL release gate |
| Scope of this freeze | ADR-009 |

**Remaining owner inputs.** These are go-live preconditions, not architecture-review blockers:

| ID | Input needed | Where it is used |
|---|---|---|
| OWNER-INPUT-001 | Approved RPO, RTO and API availability target | OPS-005, NFR-002, backup and availability alerts (02 §9, §12.3) |
| OWNER-INPUT-002 | Confirmation of retention durations (audit, security events, closed-lead anonymization) | ASM-006, 07 §8.1, 05 §9.4 |
| OWNER-INPUT-003 | Restore-rehearsal cadence | 02 §12.3 |

## 8. Go-live checklist (P0 exit criteria)

This is for the implementation phase and is not part of this freeze.

- [ ] Every P0 requirement verified per its method in 01 and the test strategy (12)
- [ ] Conformance check green on SQLite and PostgreSQL
- [ ] RBAC matrix, scope and guard (G1–G10) suites green. MFA policy tests green.
- [ ] Security-event prohibited-content test green. Chain verification job green.
- [ ] Restore verification passing. RPO/RTO measured and approved (OWNER-INPUT-001).
- [ ] OWASP API Top 10 review on staging
- [ ] Security headers and Cloudflare rules verified. Origin locked.
- [ ] SES production access, SPF, DKIM and DMARC verified (or go-live without outbound email explicitly accepted by the owner)
- [ ] Website form: API path, accessible error states and WhatsApp fallback tested
- [ ] Founder bootstrapped and MFA enrolled
- [ ] Alerts test-fired
- [ ] Privacy notice versioned and published
- [ ] Runbooks: deploy, rollback, restore, key rotation, MFA break-glass, incident response

## 9. Top risks

| Rank | Risk | Mitigation |
|---|---|---|
| 1 | Broken object-level authorization | 06 §8, §10 |
| 2 | Single-instance SQLite recovery without approved objectives | §2, OWNER-INPUT-001 |
| 3 | MFA reset abused for takeover | 05 §11.7, X14 |
| 4 | Audit bypass via bulk or raw SQL | 07 §3 |
| 5 | PostgreSQL gate ignored under business pressure | §3.3. The gate is written into ADR-008 and ADR-009. |
| 6 | XSS leading to token misuse | X1 |
| 7 | Secrets leaking into logs or security events | 05 §9.3 |

## 10. Assumptions register

Each assumption is explicit and has a validation trigger. None is a measured fact.

| ID | Assumption | Used by | Validate / replace when |
|---|---|---|---|
| ASM-001 | The staff user base during P0 is small (tens of people), within a single-instance deployment's capacity | S1, S2, OPS-006 | Monitor active users and latency. Revisit at the PostgreSQL gate. |
| ASM-002 | P0 write concurrency is within SQLite's single-writer capacity | §3.3 | Load test before go-live. `SQLITE_BUSY` and latency metrics in production. |
| ASM-003 | Table growth classes in 03 §11 are qualitative guesses | 03 §11 | Replace with measured row growth after 30 days |
| ASM-004 | Security-event volumes are unknown. Alert, lockout and rate-limit thresholds are initial configuration values. | 05 §4, §9.8, 08 §12, 02 §9 | Review after 30 days of production traffic. Record the outcome in ADR-004. |
| ASM-005 | The website's existing "Property Type" field is not sent to the public API, because ADR-005 enumerates the public fields. Staff capture property type during enrichment. | 04 §5.1 | Owner may amend ADR-005 to add it as an optional public field |
| ASM-006 | Retention defaults: audit 2 y online / 8 y total · security events 1 y / 2 y · closed-lead anonymization 3 y | 07 §8.1, 05 §9.4, 11 §5.6 | Legal confirmation (OWNER-INPUT-002) |
| ASM-007 | NFR-001 load-test fixture sizes (100k leads, 1M audit rows) are test fixtures, not forecasts | NFR-001 | Replace with measured growth × planning horizon |
| ASM-008 | Cloudflare stays in front of `api.vedaspaces.com` (proxied) | SEC-006, SEC-011, LEAD-018 | Any change of edge provider |
| ASM-009 | SES production access will be granted. Until then, the capture adapter means no outbound email outside production. | NOTIF-009 | SES approval |
| ASM-010 | A host with at least 2 GB RAM is sufficient for Argon2id parameters | 05 §2.1 | Benchmark on the target instance type |
| ASM-011 | The website will publish a versioned privacy notice whose version id is sent as `consent.policy_version` | LEAD-012 | Website implementation of LEAD-001 |
| ASM-012 | The AWS region is ap-south-1 (Mumbai). ADR-008 fixes AWS but not the region. | 02 §1, §12 | Owner confirmation |
