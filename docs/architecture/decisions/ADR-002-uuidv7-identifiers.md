# ADR-002: Entity identifiers are UUIDv7 in canonical 32-hex form

- **Status:** Accepted
- **Date:** 2026-09-29

## Context

The brief mandates `id` as GUID(32). The platform must:

- start on SQLite and migrate to PostgreSQL without identifier rewrites;
- avoid exposing business volumes through sequential ids;
- keep index locality good for time-ordered inserts;
- let modules reference each other without coordination.

## Decision

- All entity ids are **UUID version 7** (RFC 9562).
- **Canonical external representation:** exactly 32 lowercase hexadecimal characters, no hyphens.
- **Generation** happens in the application service layer, before insert. It never happens in the database, and never from client-supplied values for entity ids.
- ids are **immutable** after creation.

**Database mapping:**

| Engine | Storage |
|---|---|
| SQLite | `CHAR(32)` with a CHECK on format, version nibble and variant nibble (03 §12) |
| PostgreSQL | **Native `uuid`**. The kernel `GUID` type converts to and from the canonical 32-hex string at the driver boundary. |

**API and validation:**

- APIs carry ids only as 32-character lowercase strings.
- Validation rejects malformed ids (pattern `^[0-9a-f]{12}7[0-9a-f]{3}[89ab][0-9a-f]{15}$`) with `422 INVALID_ID`, before any lookup.

**Prohibited:**

- sequential integer entity ids;
- exposing database sequence values;
- using human-readable business numbers (such as `lead_number`) as identifiers.

Business numbers are internal display values only and never public (LEAD-025).

Seeded system users use fixed ids that are valid UUIDv7 in form (timestamp 0) (03 §2.3).

## Alternatives considered

| Option | Why rejected |
|---|---|
| Auto-increment integers | Leak volume, need coordination, and complicate the migration |
| UUIDv4 | Random inserts fragment B-tree indexes |
| ULID | Not an RFC UUID, so PostgreSQL has no native type |
| `CHAR(32)` on PostgreSQL too | Simpler migration, but indexes are twice as large and there is no native validation. The owner chose native `uuid`. |
| Hyphenated 36-character form | Inconsistent with the brief's GUID(32) |

## Consequences

- The kernel owns one `GUID` type with per-dialect mapping.
- Every FK column uses the GUID type. The conformance check enforces this (03 §2.7 rule 4).
- PostgreSQL tooling displays hyphenated values. Ad-hoc SQL uses a documented conversion convention (11 §3.2).
- Idempotency keys and other opaque client strings are **not** entity ids and are typed as strings (08 §2.8).

## Risks

| Risk | Mitigation |
|---|---|
| Accidental hyphenated or uppercase ids in APIs | Validation and tests (12 §4.6) |
| Clock skew affecting ordering | Lists sort by explicit columns with `id` only as a tie-breaker |
| Data-migration cast errors | Checksum-verified copy (11 §3.4) |

## Affected requirement IDs

DATA-002, DATA-012, DATA-013, API-001, LEAD-008, LEAD-025

## Affected documents

03 (§2.1, §2.2, §2.3, §12), 04 (§2), 08 (§2.2, §2.8), 10 (§1, §5), 11 (§3.2), 12 (§4.6)

## Future review triggers

- A need for client-generated ids (offline sync). This would require an amendment defining a trusted id-minting path.
- Any engine change beyond SQLite and PostgreSQL
