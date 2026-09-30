# ADR-004: Dedicated append-only `security_event_log`

- **Status:** Accepted (amended by remediation 01)
- **Date:** 2026-09-29

## Context

Authentication and session telemetry (logins, refreshes, MFA challenges, lockouts) is high-frequency and security-critical. Mixing it into the entity `audit_log` would flood record histories and complicate retention. It would also blur two different questions: "who changed this data" versus "who accessed the system, and how".

## Decision

A dedicated append-only table, **`security_event_log`** (03 §5.4, 05 §9), records:

- login success and failure;
- token refresh;
- logout and session revocation;
- password reset request and completion;
- MFA enrollment, challenge success or failure, recovery-code use, reset;
- account lockout and unlock;
- permission denials and **permission-sensitive actions** (any use of an `is_sensitive` permission);
- blocked public-intake submissions.

This telemetry is **never** written to `audit_log`.

| Aspect | Decision |
|---|---|
| Retention | Configurable (`SECURITY_EVENT_ONLINE_RETENTION_DAYS`, `SECURITY_EVENT_ARCHIVE_RETENTION_DAYS`). **Values are owner input OWNER-INPUT-002.** No values are asserted, and nothing is purged until they are set. |
| Archival | Monthly export to S3 (SSE-KMS, Object Lock) with checksum verification. The chain anchor is written to the external Object Lock anchor bucket, **not only the database**. Then delete (EXC-002). It runs only from the maintenance CLI. |
| Redaction | Per-event allow-listed `detail` keys. Unknown-account emails stored only as an HMAC. User agent truncated. |
| Prohibited content | Raw or hashed access and refresh tokens, passwords, OTP secrets or codes, recovery codes, reset tokens, cookies, Authorization headers, request/response bodies |
| Access control | `security_event.read` (sensitive, `SECURITY_DATA`, **ALL-only**) for Founder and Admin, effective only in MFA-verified sessions. **Standard Sales has no access, including to their own events** (owner Decision 1, F-01). No API writes, updates or deletes. |
| Tamper evidence (F-11) | DB immutability guards · **keyed** chain `row_hash = HMAC-SHA-256(K[chain_key_label], prev_hash ‖ JCS(row))`, with the key in SSM and never in the DB · RFC 8785 canonicalization of application-level values, engine-independent · nightly verification · **daily external anchor in S3 Object Lock compliance mode (P0)** |
| Pagination and indexing | Cursor on (`occurred_on`, `id`). Indexes on time, subject, type, IP and non-success outcomes. |
| Monitoring | Alert rules in 05 §9.8 |
| Sensitive reads (F-06) | Mutations with sensitive permissions → `SENSITIVE_ACTION`. Reads with `SECURITY_DATA` or `BULK_DATA` permissions → `SENSITIVE_READ`, de-duplicated per (actor, permission, 15 min). |
| Correlation | `session_id` is a non-FK correlation id (EXC-009), so session purge never conflicts with evidence rows (F-07) |
| Transactions | Success events share the business transaction. Failure and denial events use their own transaction. |
| Capacity | **No volumes asserted.** Measured over the first 30 days of production. Thresholds and retention reviewed then (ASM-004). |

## Alternatives considered

| Option | Why rejected |
|---|---|
| Store in `audit_log` | Owner rejected. It mixes concerns and volumes. |
| Application logs only (CloudWatch) | Not queryable in the app, weaker integrity, and no FK to users |
| External SIEM only | Cost and operational weight for the MVP. The log can be forwarded to a SIEM later. |
| Not logging token refreshes | Owner requires refresh events |

## Consequences

- An extra write per refresh, serialized through the hash chain. Acceptable on SQLite's single writer, and handled by an advisory lock on PostgreSQL.
- The Audit Log Viewer has a separate Security events tab (09 §4.9).
- The seeded ANONYMOUS system user exists to satisfy the actor FK for unauthenticated events.

## Risks

| Risk | Mitigation |
|---|---|
| Secret leakage | Allow-list writer, prohibited-content test (12 §4.3) |
| Log growth | Retention and archival job |
| Chain append contention | Measured in load tests |
| Logger failure hiding attacks | Fail closed for success events. CRITICAL alert on writer failure. |

## Affected requirement IDs

AUDIT-012, AUTH-013, SEVT-001 through SEVT-011, MFA-006, LEAD-018

## Affected documents

02 (§5, §7, §9), 03 (§5.4, §2.9), 05 (§9), 06 (§6.2), 07 (§1, §2, §6), 08 (§10.1), 09 (§4.9), 11 (§4), 12 (§4.3)

## Future review triggers

- 30 days after production launch (volume and threshold review, ASM-004)
- Integration with a SIEM or managed log platform
- A regulatory requirement for different retention

## Approval record

| Item | Value |
|---|---|
| Approver | Veda Spaces owner (repository owner) |
| Approval | 2026-09-29, `VEDA-SPACES-P0-ARCHITECTURE-SIGNOFF-AND-FREEZE`, decision ADR-004; amended by `VEDA-SPACES-P0-ARCHITECTURE-REMEDIATION-01` Decisions 1 and 6 (F-01, F-06, F-07, F-11) |
| Evidence | [decision-log.md](decision-log.md). A verifiable owner sign-off (owner approval of the architecture pull request) is tracked gate TG-01 before implementation (F-18). |
