# 07 — Audit Framework

Governing decisions: [ADR-003](decisions/ADR-003-audit-contract.md) · [ADR-004](decisions/ADR-004-security-event-log.md)

## 1. Goals

1. Every create, update, delete and restore on business, configuration, junction and identity data is traceable: who, what, when, from where, and old → new.
2. Capture is **automatic and atomic**, done by the kernel in the same transaction (03 §2.8).
3. Audit records are **immutable** and outlive the data they describe.
4. Secrets never enter the trail. Personal data can be lawfully anonymized.
5. Authentication and security telemetry go to the **separate** `security_event_log` (ADR-004, 05 §9). They never go to `audit_log`.

## 2. Audit policy registry

Every table is registered with exactly one policy. The schema conformance check fails on unregistered tables (03 §2.7).

| Policy | Behavior | Tables |
|---|---|---|
| `FULL` | Row-level diffs to `audit_log` for CREATE / UPDATE / DELETE / RESTORE / HARD_DELETE | app_user, user_credential, role, permission, user_role, role_permission, user_permission, user_mfa_factor, lookup_category, lookup_value, number_sequence (configuration columns), lead, lead_note, lead_activity |
| `EVENT_ONLY` | No row diffs. The lifecycle is recorded as `security_event_log` events or is operational state. Behavioral exceptions are registered in 03 §2.9. | user_session, refresh_token, password_reset_token, user_mfa_recovery_code, mfa_challenge, outbox_event, notification |
| `IMMUTABLE_STORE` | Insert-only evidence store | audit_log, security_event_log |

Each FULL registration declares:

| Setting | Values |
|---|---|
| `excluded_fields` | `updated_on`, `updated_by`, `version` for all tables · `last_login_on`, `authz_version` (app_user) · lockout counters (user_credential) · `last_used_step`, `last_used_on` (user_mfa_factor) · `next_value`, `current_period` (number_sequence) · `next_follow_up_on`, `last_activity_on` (lead) |
| `redacted_fields` | `password_hash` · `secret_ciphertext` · `secret_key_ref` |
| `parent` | lead_note / lead_activity → lead · user_role, user_permission, user_credential, user_mfa_factor → app_user · role_permission → role · lookup_value → lookup_category |
| `pii_fields` | lead: `name`, `phone`, `phone_raw`, `email`, `email_normalized`, `message`, `locality`, `consent_ip_address` · app_user: `email`, `email_normalized`, `full_name`, `phone_e164` |

An UPDATE that changes only excluded fields produces no audit row.

## 3. Capture mechanism (AUDIT-001, AUDIT-010, DATA-015)

```
ActorContext {actor_id (app_user.id — user or seeded system user), via, request_id, session_id, ip, ua, reason?}
     │
 Service mutates ORM objects inside ONE unit of work (03 §2.8)
     │
 session.flush() ──► kernel before_flush hook
                       for obj in new ∪ dirty ∪ deleted:
                         require AuditedBase subclass; require ActorContext  (else AuditContextMissing → rollback)
                         stamp contract columns (03 §2.8)
                         if registry[obj.table] == FULL:
                           action = CREATE | UPDATE | DELETE (is_deleted false→true) | RESTORE | HARD_DELETE
                           diff   = attribute history minus excluded; redact; skip empty UPDATE
                           add audit_log row {…, performed_by = actor, performed_on = tx_time, transaction_id}
     │
 COMMIT ──► business rows + contract columns + audit_log + outbox_event commit atomically
```

- `tx_time` is one clock reading per unit of work, shared by every row written.
- `transaction_id` is a UUIDv7 per unit of work.
- `audit_log.performed_by` is a DB-enforced FK to `app_user.id` (03 §7).

**Bypass controls:**

| Bypass | Control |
|---|---|
| ORM bulk `update()` / `delete()` statements | Banned in business code by lint. The kernel `bulk_mutate` helper mutates through the ORM or writes explicit audit rows. |
| Raw SQL in services | Banned by lint. Allowed only in migrations. |
| Data migrations | Run with ActorContext {SYSTEM, MIGRATION}. Data-changing migrations use the ORM path or explicit audit rows. |
| Direct DB access | Break-glass only, via SSM (CloudTrail-logged), with the owner notified (11 §4) |
| Background jobs | Run as SYSTEM with `SYSTEM_JOB` |

## 4. Payload format (AUDIT-002, AUDIT-003, AUDIT-006)

`payload_schema = 1`.

| Type | Serialization |
|---|---|
| GUID | 32-hex |
| Datetime | RFC 3339 UTC |
| Money | Integer minor units |
| Booleans, integers | Native JSON |
| Lookup FKs | Stored as ids. Labels are resolved at read time. |

| Action | `old_value` | `new_value` | `changed_fields` |
|---|---|---|---|
| CREATE | `null` | Full snapshot (excluded fields removed, secrets redacted) | Populated fields |
| UPDATE | Changed fields only | Changed fields only | Changed fields |
| DELETE (soft) | `{is_deleted:false, …}` + `_snapshot` | `{is_deleted:true, deleted_on, deleted_by}` | The three soft-delete fields |
| RESTORE | Reverse of DELETE | | |
| HARD_DELETE | Full snapshot (PII anonymized if erasure) | `null` | — |
| EXPORT | `null` | `{resource, filters, row_count, format}` | — |
| ANONYMIZE | `null` | `{fields, legal_basis, request_ref}` | Anonymized fields |

### 4.1 Example: status change to LOST

```json
{
  "id": "0192a50e7c1a7b3e8f2d4c6a1b3e5f70",
  "entity_type": "lead",
  "entity_id": "0192a4f1c3b27e8d9f10a2b3c4d5e6f7",
  "action": "UPDATE",
  "old_value": { "status": "NEGOTIATION", "lost_on": null, "lost_reason_id": null },
  "new_value": { "status": "LOST", "lost_on": "2026-09-29T10:02:11.004211Z", "lost_reason_id": "0192a3b0c1d27e4f8a9b0c1d2e3f4a5b" },
  "changed_fields": ["status", "status_changed_on", "lost_on", "lost_reason_id"],
  "performed_by": "0192a3aa55e07c01b2c3d4e5f6a7b8c9",
  "performed_on": "2026-09-29T10:02:11.004211Z",
  "performed_via": "API",
  "transaction_id": "0192a50e7c197aa0b1c2d3e4f5a6b7c8",
  "request_id": "8c2f1e0a9b7d4c3e",
  "session_id": "0192a4ff00117c3d8e9f0a1b2c3d4e5f",
  "reason": "Client chose competitor",
  "payload_schema": 1
}
```

### 4.2 Parent linkage

> Traces: AUDIT-006

The hook fills `parent_entity_type` and `parent_entity_id` from the registry. A record's full history (itself plus its children) is one indexed query.

### 4.3 Read and export auditing (AUDIT-007)

> Traces: LEAD-017

- Reads aren't audited in P0.
- CSV export (P1) writes an EXPORT row.
- Future payroll and HR modules require ACCESS auditing (10 §3.3).
- Use of sensitive permissions is recorded as a `SENSITIVE_ACTION` security event (05 §9.1).

## 5. Redaction and minimization (AUDIT-005)

- `redacted_fields` are written as `"[REDACTED]"`, so the fact of a change is visible without the value.
- Token, recovery-code and challenge tables are EVENT_ONLY, so their hashes never reach `audit_log`.
- Free-text business fields are stored in full and are covered by anonymization (§8.2).

## 6. Immutability (AUDIT-004, SEVT-006)

### 6.1 Application

- The audit and security-event repositories have no update or delete paths.
- The hook raises if an `audit_log` or `security_event_log` object becomes dirty.

### 6.2 Database

> Traces: AUDIT-004, SEVT-001

| Engine | Guard on `audit_log` and `security_event_log` |
|---|---|
| SQLite | `BEFORE UPDATE` and `BEFORE DELETE` triggers `RAISE(ABORT, 'immutable')`. The retention procedure (§8) runs as a documented maintenance step that drops and recreates the delete trigger inside the same transaction as the archival delete, and writes a summary event. |
| PostgreSQL | The application role has `INSERT, SELECT` only. A separate retention role has `DELETE`. Triggers block UPDATE. |

### 6.3 Tamper evidence

| Store | P0 | Later |
|---|---|---|
| `security_event_log` | Hash chain + nightly verification (05 §9.6, SEVT-006) | P1: daily external anchor to S3 Object Lock (SEVT-007) |
| `audit_log` | DB guards + break-glass controls | P2: hash chain with the same design (AUDIT-013), added as nullable columns (additive migration) |

## 7. Querying and the viewer (AUDIT-008)

| Query | Index |
|---|---|
| Record history (+ children) | `ix_audit_log__entity`, `ix_audit_log__parent` |
| Actor history | `ix_audit_log__performed_by` |
| Time window | `ix_audit_log__performed_on` |
| One transaction | `ix_audit_log__transaction_id` |

- `GET /api/v1/audit-logs` uses cursor pagination (08 §10).
- The viewer is described in 09 §4.9.
- The lead "History" tab requires `lead.read` on the lead **and** `audit.read`.

## 8. Retention, archival and erasure (AUDIT-009, AUDIT-011, DATA-009)

### 8.1 Retention

> Traces: AUDIT-009

| Store | Configuration | Initial default (owner may change) |
|---|---|---|
| `audit_log` | `AUDIT_ONLINE_RETENTION_DAYS`, `AUDIT_ARCHIVE_RETENTION_DAYS` | 730 online · 2,920 total (8 years, pending legal confirmation, ASM-006) |
| `security_event_log` | 05 §9.4 | 365 online · 730 total |
| Application logs | CloudWatch retention setting | 30 days hot · 365 archive |

**Archival (actor SYSTEM):**

1. Export the partition to S3 (SSE-KMS, Object Lock governance).
2. Verify the row count and checksum.
3. Delete (EXC-002).
4. Write a HARD_DELETE summary row (entity_type `audit_log_partition`).

### 8.2 Personal data erasure (DPDP Act 2023)

> Traces: AUDIT-011

When an erasure request is valid:

1. **Live lead fields.** PII is replaced through the ORM, with a normal UPDATE audit row whose old values are redacted.
2. **Audit history.** A controlled procedure rewrites `pii_fields` values in `audit_log.old_value` and `new_value` to `"[ERASED]"`. It is the only permitted mutation. It runs under the retention role or procedure and writes an ANONYMIZE row.
3. **Security events.** These contain no lead PII by design (SEVT-003).
4. **Operational rows.** Outbox and notification rows for the lead are purged.

## 9. Rules for future modules

1. Register every new table with a policy (conformance check).
2. Declare `parent` for child tables.
3. Declare `pii_fields`.
4. HR and payroll: FULL plus ACCESS auditing.
5. Never write outside the ORM unit of work.
6. Send authentication-like telemetry to `security_event_log`, never `audit_log`.
