# ADR-007: Frontend, backend, database and email stack

- **Status:** Accepted
- **Date:** 2026-09-29

## Context

The brief fixes Lit, Flask, SQLAlchemy and SQLite-then-PostgreSQL. It left open TypeScript, the layering conventions, and the email provider.

## Decision

| Layer | Decision |
|---|---|
| Frontend | **Lit + TypeScript**, Vite build, the Veda Spaces design system (09 §2–3), deployed as its own Cloudflare Pages project |
| Backend | **Python Flask** modular monolith · **SQLAlchemy** ORM · **Alembic** migrations · explicit **service layer** and **repository layer** · URI **API versioning** (`/api/v1`) · structured request/response validation (Pydantic v2) · RFC 9457 problem responses |
| Database | **SQLite** for the controlled MVP. **PostgreSQL migration readiness is mandatory**: dual-engine CI and explicit type mappings (03 §12). |
| Email | **Amazon SES** in production. A **development/test adapter** (log or capture, no external delivery) until SES production sending access is granted. |
| Email failure isolation | Emails are sent only from the transactional outbox after commit. **A delivery failure never rolls back or blocks a persisted lead** (NOTIF-008). |

## Alternatives considered

| Option | Why rejected |
|---|---|
| Plain JavaScript Lit | Loses typed API contracts generated from OpenAPI |
| FastAPI | Stack fixed on Flask |
| Sending email inline in the request | Couples lead persistence to provider availability |
| Other email providers | SES fits the AWS hosting decision (ADR-008) and IAM-based credentials |

## Consequences

- A separate frontend build pipeline from the build-free marketing site.
- An `EmailProvider` adapter interface with at least two implementations.
- The outbox worker is a required process.

## Risks

| Risk | Mitigation |
|---|---|
| SES production access delayed | Capture adapter. Go-live decision recorded in the checklist (11 §8). |
| Dual-engine CI cost | Accepted. It is the price of migration readiness. |

## Affected requirement IDs

PLAT-001, PLAT-002, PLAT-004, PLAT-005, API-001, API-003, API-008, NOTIF-002, NOTIF-003, NOTIF-008, NOTIF-009, OPS-001

## Affected documents

02 (§2, §3, §10), 03 (§12), 05 (§8), 08 (§2), 12 (§2, §5)

## Future review triggers

- The PostgreSQL release gate (ADR-008)
- A major Lit, Flask or SQLAlchemy version change
- Email deliverability problems
