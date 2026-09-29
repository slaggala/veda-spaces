# Veda Spaces Platform — P0 Foundation Architecture

Status: **Remediated after independent review — ready for focused independent re-review (author verdict, not a certification)** · Version 1.1 · 2026-09-29 · Branch `architecture/p0-foundation-freeze`

| Milestone | Reference |
|---|---|
| Frozen architecture | commit `4dce177` |
| Independent review | `review/p0-foundation-independent-review` @ `7515b23`, verdict **NOT CERTIFIED** (3 MAJOR, 18 MINOR, 14 ADVISORY) |
| Remediation 01 | This version. Every finding is dispositioned in [review-remediation-matrix.md](review-remediation-matrix.md). |

This folder is the long-term foundation for the Veda Spaces business platform. P0 ships **Lead Management** on a platform layer that every later module reuses: authentication, MFA, RBAC, user management, audit, security events and notifications.

This is design only. There is no implementation code, no stubs and no credentials in this folder. The next authorized activity is a **focused independent re-review** of the remediation. Implementation, merge and deployment remain unauthorized.

## Scope (ADR-009)

| In scope for P0 | Roadmap only, not authorized |
|---|---|
| Authentication · MFA · RBAC · user management · audit logging · security-event logging · lead capture, notes, activities and administration · notification foundation · PostgreSQL migration readiness | Customer · quotation · project management · design · vendor · procurement · inventory · employee/onboarding · payroll · portal · warranty · finance · attachments · org units · AI |

## Deliverables

| # | Document | Contents |
|---|---|---|
| 1 | [01-requirements-traceability.md](01-requirements-traceability.md) | Requirement matrix with per-dimension coverage references (generated from [requirements.json](requirements.json)) |
| 2 | [02-platform-architecture.md](02-platform-architecture.md) | Frontend, backend, API, auth, RBAC, audit, database, logging, notification, security and deployment architecture |
| 3 | [03-database-schema.md](03-database-schema.md) | Audit contract, exception registry, every foundational table, SQLite/PostgreSQL mapping |
| 4 | [04-lead-management.md](04-lead-management.md) | Lead, lead_note, lead_activity, state machine, public intake, enrichment |
| 5 | [05-authentication.md](05-authentication.md) | Login, sessions, JWT, password reset, **security event log**, **MFA** |
| 6 | [06-rbac.md](06-rbac.md) | Permission catalog, scopes, resolution, role matrix, guards, RBAC exception register |
| 7 | [07-audit.md](07-audit.md) | Audit capture, payloads, immutability, retention, erasure |
| 8 | [08-api-design.md](08-api-design.md) | Conventions, errors, pagination, every endpoint with payloads |
| 9 | [09-ui-ux-design.md](09-ui-ux-design.md) | Design system, accessibility tokens, screens including MFA and public form states |
| 10 | [10-future-roadmap.md](10-future-roadmap.md) | Expansion without schema rewrites (roadmap only) |
| 11 | [11-production-readiness.md](11-production-readiness.md) | Risks, PostgreSQL release gate, assumptions register, owner inputs |
| 12 | [12-test-strategy.md](12-test-strategy.md) | Verification methods and test suites per requirement area |
| — | [decisions/](decisions/) | ADR-001 … ADR-010 (accepted owner decisions) and the [decision log](decisions/decision-log.md) |
| — | [review-remediation-matrix.md](review-remediation-matrix.md) · [.json](review-remediation-matrix.json) | Disposition of every independent-review finding |
| — | [requirements.json](requirements.json) | Machine-readable requirement registry (source of truth for 01) |
| — | [validation-report.md](validation-report.md) · [validation-report.json](validation-report.json) | Consistency validation results |
| — | [coverage-gate.md](coverage-gate.md) | Substantive coverage (independent-review taxonomy), owner-input dependencies, test-design depth, author verdict |

Suggested re-review order: review-remediation-matrix → ADR-006, ADR-010 → 06 → 05 → 03 → 08 → 04 → 07 → 09 → 12 → 11 → coverage-gate. Use 01 as the index.

## Accepted decisions

| ADR | Decision |
|---|---|
| [ADR-001](decisions/ADR-001-app-user-table.md) | The User entity's physical table is `app_user`. No table named `user`. The API stays `/users`. |
| [ADR-002](decisions/ADR-002-uuidv7-identifiers.md) | UUIDv7 ids as 32 lowercase hex characters, generated in the service layer. `CHAR(32)` on SQLite, native `uuid` on PostgreSQL. |
| [ADR-003](decisions/ADR-003-audit-contract.md) | Nine-column audit contract on every table. Actors are NOT NULL FKs to `app_user.id`. Exception registry. Atomic population. |
| [ADR-004](decisions/ADR-004-security-event-log.md) | Dedicated append-only, **keyed**-chain `security_event_log` with an external anchor. Founder/Admin read access only. |
| [ADR-005](decisions/ADR-005-lead-required-fields.md) | Public form requires name, phone and consent. Email, city, project type, budget, **property type** and message are optional. CAPTCHA, fingerprinted idempotency, quarantine not drop, WhatsApp fallback, no internal data exposed. |
| [ADR-006](decisions/ADR-006-mfa-policy.md) | TOTP MFA mandatory for Founder, Admin and all sensitive-permission holders. Optional by default for Sales. Sensitive permissions are inactive without MFA. Two-proof enrollment. Restricted recovery session with cooling-off. Dual-controlled admin reset. |
| [ADR-007](decisions/ADR-007-technology-stack.md) | Lit + TypeScript. Flask, SQLAlchemy and Alembic with service and repository layers. SES with a dev/test adapter. |
| [ADR-008](decisions/ADR-008-aws-hosting.md) | AWS **ap-south-1** single-instance, single-process backend on an encrypted persistent volume. No multi-region claim. PostgreSQL release gate. Owner-approved RPO/RTO. |
| [ADR-009](decisions/ADR-009-p0-scope.md) | Freeze scope. Roadmap modules not authorized. Remediation scope adjustments. |
| [ADR-010](decisions/ADR-010-account-control-and-privileged-protection.md) | Granular account-control permissions. Proposed-email workflow. Founder protection, last-administrator invariants, dual control, break-glass. |

## Architecture principles

These are design conventions established in the documents. They carry no separate ADRs.

| Principle | Where |
|---|---|
| Modular monolith. Modules talk through service interfaces. | 02 §3 |
| Permission codes plus data scope (ALL/TEAM/OWN). No role-name checks anywhere. | 06 §2 |
| Permissions are defined in code and synchronized by migration | 06 §3 |
| Audit rows written in the same transaction by an ORM unit-of-work hook | 03 §2.8, 07 §3 |
| Reference lists are data (lookups). Workflow states are code. | 03 §6 |
| Side effects via the transactional outbox, never inside the request transaction | 02 §10 |
| Additive-only schema evolution (expand → migrate → contract) | 10 §2 |

## Glossary

| Term | Meaning |
|---|---|
| Audit contract | The nine standard columns every table carries (ADR-003) |
| Actor | The `app_user` performing a write: a human, or a seeded system user (SYSTEM, WEB_INTAKE, ANONYMOUS) |
| Scope | The extent of a permission: `ALL` rows, `TEAM` (reserved), or `OWN` rows |
| Effective permissions | The resolved (permission, scope) set after roles, grants and denies |
| Security event | A row in `security_event_log`: authentication, session, MFA, account or sensitive-permission activity |
| Step-up | Re-verifying MFA (or re-entering the password, for users without MFA) shortly before a sensitive operation |
| Sensitive permission | A permission with a `sensitivity_class` in the code registry. Requires MFA and is inactive until MFA is verified. |
| Recovery session | A restricted 15-minute session created by password + recovery code. It can only enroll a new authenticator. |
| Proposed email | A pending new sign-in address. It becomes active only after verification. |
| Founder protection | `app_user.protection_level = FOUNDER`. Founder accounts change only through the dual-control Founder workflow. |
| Dual control | An action executes only after a second eligible person approves it (`admin_approval_request`) |
| Outbox | Pending side effects written in the business transaction and drained after commit |
| Public reference | A random code given to website enquirers instead of any internal identifier |
