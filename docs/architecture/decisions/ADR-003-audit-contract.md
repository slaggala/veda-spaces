# ADR-003: Mandatory audit contract on every persisted table

- **Status:** Accepted
- **Date:** 2026-09-29

## Context

The brief requires every business table to inherit an audit model. Traceability, soft delete and concurrency control must be uniform across domain, security, junction, configuration and business tables, so that future modules inherit them without design work.

## Decision

Every persisted table includes:

`id`, `created_on`, `updated_on`, `created_by`, `updated_by`, `is_deleted`, `deleted_on`, `deleted_by`, `version`

**Rules:**

| Rule | Detail |
|---|---|
| Identifier | `id` is UUIDv7 in canonical 32-character form (ADR-002) |
| Time | `created_on` and `updated_on` are UTC and NOT NULL, set from one transaction clock reading |
| Actors | `created_by` and `updated_by` are **NOT NULL database FKs to `app_user.id`**. `deleted_by` is a nullable FK. |
| Non-human writers | Documented seeded system users: SYSTEM (jobs, migrations), WEB_INTAKE (website submissions), ANONYMOUS (unauthenticated security events) (03 §2.3) |
| Concurrency | `version` provides optimistic concurrency (`If-Match` / 409) |
| Soft delete | Enforced where applicable via partial unique indexes and a default query filter |
| Exceptions | Only in the **exception registry** (03 §2.9, EXC-001…008). Exceptions relax behavior only. No table omits a column. |
| Enforcement | A schema conformance check fails CI on any violation, on both engines (03 §2.7) |

**Atomic population (03 §2.8):**

1. Contract fields are populated only by the platform kernel's unit-of-work hook, from the ActorContext and a single transaction timestamp.
2. The same database transaction contains the business rows, their contract fields, the `audit_log` rows and the `outbox_event` rows.
3. Commit is all-or-nothing. On SQLite, write units of work use `BEGIN IMMEDIATE`.
4. Side effects such as email run after commit from the outbox.
5. Failure and denial security events are written in a separate transaction so they survive rollbacks (ADR-004).

## Alternatives considered

| Option | Why rejected |
|---|---|
| Logical actor references without DB FKs | Weaker integrity. The owner required references to `app_user.id`. |
| Nullable actors for anonymous or system writes | Breaks accountability. Seeded system users are used instead. |
| Database triggers to stamp fields | Engine-specific. Would duplicate logic across SQLite and PostgreSQL. |
| Exempting log and token tables from the contract | Inconsistent. Replaced by behavior-only exceptions in a registry. |

## Consequences

- Every table has three FKs to `app_user`. The `SYSTEM` row self-references at bootstrap. PostgreSQL `KEY SHARE` locks from FK checks don't contend with profile updates (03 §2.3).
- Evidence stores (`audit_log`, `security_event_log`) carry contract columns with fixed values for life (EXC-001).

## Risks

| Risk | Mitigation |
|---|---|
| ORM bulk statements or raw SQL bypass stamping | Lint ban, `bulk_mutate` helper, tests (07 §3) |
| Registry drift | Conformance rule 9 (unregistered deviation fails) |
| Missing actor context in jobs | Fail closed (AUDIT-010) |

## Affected requirement IDs

DATA-001, DATA-003, DATA-004, DATA-005, DATA-006, DATA-007, DATA-008, DATA-009, DATA-010, DATA-011, DATA-014, DATA-015, AUDIT-001, AUDIT-010, USER-005

## Affected documents

03 (§2, §10, §11), 07 (§2, §3), 02 (§7), 11 (§4), 12 (§4.1, §4.2)

## Future review triggers

- Adding table partitioning (PostgreSQL) for evidence stores
- Any proposal to hard-delete business data outside retention or erasure
- A new actor type (for example portal users or AI identities)
