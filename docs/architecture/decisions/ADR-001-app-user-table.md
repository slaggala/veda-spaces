# ADR-001: User table physical name is `app_user`

- **Status:** Accepted
- **Date:** 2026-09-29
- **Decision owner:** Veda Spaces (owner approval recorded in the architecture sign-off)

## Context

The brief names a mandatory `user` table. `user` is a reserved word in PostgreSQL, which is the committed migration target (ADR-008).

In PostgreSQL, `SELECT * FROM user` doesn't query a table. It returns the current session role. Raw SQL, BI tools, ad-hoc queries and hand-written migrations would all need quoting (`"user"`). A missed quote fails silently with wrong data rather than an error.

## Decision

- The physical database table is **`app_user`**.
- Domain terminology remains **User**.
- The API resource remains **`/users`**. Permission codes remain `user.*`.
- The SQLAlchemy model class may be named `User` (`__tablename__ = "app_user"`).
- **No physical table named `user` may be introduced**, in any schema or engine. The schema conformance check fails the build if one appears (03 §2.7 rule 8).
- Every FK to the user entity, including the audit-contract actor columns `created_by`, `updated_by` and `deleted_by`, references `app_user.id`.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Keep `user` with mandatory quoting | A permanent PostgreSQL trap. One unquoted query returns the session role silently. |
| `users` (plural) | Breaks the singular naming convention (03 §1) and is still easy to confuse |
| A PostgreSQL schema prefix (`identity.user`) | SQLite has no schemas. `user` is still reserved when unqualified. |
| `account` / `principal` | Diverges from the brief's domain language more than necessary |

## Consequences

- Documentation, ERDs, migrations and FKs use `app_user`. Business language, the API and the UI say "user".
- Developers must know the model/table name split. It is documented in 03 §4.1.

## Risks

| Risk | Mitigation |
|---|---|
| Someone later creates a `user` table or view | Conformance check rule 8 (SL, PLAT-013) |
| Confusion between entity and table names in docs | Convention stated in 03 §1 |

## Affected requirement IDs

PLAT-013, RBAC-001, DATA-004, USER-001, USER-003, USER-005

## Affected documents

README, 01, 02 (§3.2, §8.3), 03 (§1, §2, §3, §4.1, §11), 06 (§1), 08, 11 (§3.1), 12 (§4.1)

## Future review triggers

- Adoption of a database engine where `app_user` conflicts with a reserved word
- Introduction of database schemas or namespaces per module
