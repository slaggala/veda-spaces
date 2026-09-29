# 01 — Requirement Traceability Matrix

Source of truth: [`requirements.json`](requirements.json). This matrix is generated from it, so the two cannot diverge. Decisions: [decisions/](decisions/). Review remediation: [review-remediation-matrix.md](review-remediation-matrix.md).

**Coverage model (F-21).** The **Class** column is a *substantive* classification using the independent reviewer's taxonomy. **The baseline is the focused independent re-review (`06a4f6e`): 202 fully covered, 3 partially covered, 1 contradictory, 2 not testable.** The four requirements it did not classify as fully covered (DATA-011, DATA-014, MFA-015, RBAC-021) were corrected in the final minor remediation and are shown as FC by **author assessment pending the targeted independent check TG-07**. Every requirement's full classification history is in `requirements.json` (`assessment.history`). The section columns are navigation references, checked only for resolvability. **They are not coverage evidence.**

## 1. ID scheme and traceability rules

`<PREFIX>-<NNN>`. IDs are never reused or renumbered. A retired requirement is marked **Withdrawn**.

| Field | Values |
|---|---|
| Priority | **P0**: in scope for this freeze (ADR-009) · **P1 / P2**: designed but **deferred** |
| Source | **B**: stated in the original brief · **D**: derived by architecture · **ADR-00x**: owner decision |
| Verify | **UT** unit · **IT** integration/API · **E2E** browser · **SL** schema conformance · **RV** review checklist · **OP** operational drill/job (defined in 12 §2) |
| Class | FC = Fully covered · NT = Not testable pending owner input · DEF = Deferred. Partially covered, Contradictory, Referenced-only and Not covered currently have no P0 members. |
| Test | Test design type: **auto** (UT/IT/E2E/SL with a concrete 12 §4 row) · **rv** (review checklist) · **op** (operational drill or job) · **owner** (owner-gated) |
| Section columns | Navigation to the design sections. "—" means not applicable. |

**Rules:**

1. Every PR lists `Implements:` / `Affects:` requirement IDs (PLAT-006).
2. Every test carries the requirement ID in its name or marker (12 §1).
3. Every seeded permission stores its requirement in `permission.requirement_ref`.
4. Every migration names the requirement IDs it serves.
5. A requirement is **Done** only when its verification passes.
6. New modules register requirements under their reserved prefix (§4) before design.
7. Every navigation reference resolves to a numbered section (checked mechanically in `validation-report.md`). Coverage is claimed only through the substantive classification, never through citation.

## 2. Prefix register

| Prefix | Domain | Primary doc |
|---|---|---|
| PLAT | Platform | 02 |
| DATA | Data standards and audit contract | 03 |
| AUDIT | Audit framework | 07 |
| AUTH | Authentication and sessions | 05 |
| SEVT | Security event log | 05 §9 |
| MFA | Multi-factor authentication and recovery | 05 §11 |
| RBAC | Authorization | 06 |
| USER | User administration | 03, 08 |
| LEAD | Lead management | 04 |
| NOTE | Lead notes | 04 |
| ACT | Lead activities | 04 |
| NOTIF | Notifications | 02 |
| LOG | Logging and observability | 02 |
| SEC | Security and privacy | 02, 11 |
| API | API conventions | 08 |
| UI | User interface | 09 |
| OPS | Operations, deployment, backup | 02, 11 |
| NFR | Non-functional targets | 11 |

## 3. Matrix

### 3.1 PLAT — Platform

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PLAT-001 | Backend is a Python Flask modular monolith exposing a versioned REST API. | P0 | B | RV | FC | rv | 02 §3.1 | — | — | — | — | 12 §2 |
| PLAT-002 | Internal application frontend is built with Lit and TypeScript and deployed separately from the marketing site. | P0 | B, ADR-007 | RV | FC | rv | 02 §2.1 | — | — | — | — | 12 §2 |
| PLAT-003 | Backend API is deployed on AWS, independently of Cloudflare Pages. | P0 | B, ADR-008 | OP | FC | op | 02 §12.2 | — | — | — | — | 12 §4.9 |
| PLAT-004 | All data access goes through SQLAlchemy; business code contains no engine-specific SQL, so SQLite to PostgreSQL requires no application changes. | P0 | B | IT | FC | auto | 02 §8.2 | 03 §12 | — | — | — | 12 §4.1 |
| PLAT-005 | All schema changes are versioned Alembic migrations; no manual DDL in any environment. | P0 | D | RV | FC | rv | 02 §8.3 | — | — | — | — | 12 §4.11 |
| PLAT-006 | Every module, PR and test references requirement IDs. | P0 | B | RV | FC | rv | 01 §1 | — | — | — | — | 12 §1 |
| PLAT-007 | Timestamps are stored in UTC; API datetimes require an offset; date filters use the user's timezone; display uses the user's IANA timezone (default Asia/Kolkata). | P0 | D | UT | FC | auto | 03 §2.2 | 03 §4.1 | — | 09 §3.2 | — | 12 §4.1 |
| PLAT-008 | Configuration comes from the environment; no secrets in the repository. | P0 | D | RV | FC | rv | 02 §11.4 | — | — | — | 02 §11.4 | 12 §4.11 |
| PLAT-009 | Business reference lists are configurable lookup data, not code enums. | P0 | D | IT | FC | auto | 03 §6 | 03 §6.2 | 08 §7 | — | — | 12 §4.11 |
| PLAT-010 | Human-readable record numbers are allocated from a central sequence table and are internal display values only. | P0 | D | IT | FC | auto | 03 §6.3 | 03 §6.3 | — | — | — | 12 §4.11 |
| PLAT-011 | A module accesses another module only through its service interface, never its tables or repositories. | P0 | D | RV | FC | rv | 02 §3.3 | — | — | — | — | 12 §4.11 |
| PLAT-012 | Roadmap modules (vendor, inventory, payroll, procurement, full project management and others in doc 10) are not authorized for implementation in P0. | P0 | ADR-009 | RV | FC | rv | 10 §3.2 | — | — | — | — | 12 §4.11 |
| PLAT-013 | The User entity's physical table is app_user; no physical table named user may exist. | P0 | ADR-001 | SL | FC | auto | 03 §4.1 | 03 §11 | — | — | — | 12 §4.1 |

### 3.2 DATA — Data standards and audit contract

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DATA-001 | Every persisted table includes the nine audit-contract columns; deviations are behavioral only and registered. | P0 | B, ADR-003 | SL | FC | auto | 03 §2.1 | 03 §2.1 | — | — | — | 12 §4.1 |
| DATA-002 | id is UUIDv7 as 32 lowercase hex characters, generated in the service layer, immutable. | P0 | B, ADR-002 | SL, UT | FC | auto | 03 §2.2 | 03 §2.2 | — | — | — | 12 §4.1 |
| DATA-003 | created_on and updated_on are NOT NULL UTC values set by the platform from one transaction clock reading. | P0 | B, ADR-003 | UT | FC | auto | 03 §2.8 | 03 §2.1 | — | — | — | 12 §4.2 |
| DATA-004 | created_by and updated_by are NOT NULL foreign keys to app_user.id; non-human writes use seeded system users. | P0 | B, ADR-003 | SL | FC | auto | 03 §2.3 | 03 §2.1 | — | — | — | 12 §4.1 |
| DATA-005 | Soft delete via is_deleted, deleted_on, deleted_by with a consistency constraint. | P0 | B, ADR-003 | SL, IT | FC | auto | 03 §2.4 | 03 §2.1 | — | — | — | 12 §4.2 |
| DATA-006 | Optimistic concurrency via version; stale updates are rejected. | P0 | B, ADR-003 | IT | FC | auto | 03 §2.5 | 03 §2.1 | 08 §2.7 | — | — | 12 §4.12 |
| DATA-007 | Business-key uniqueness applies only among non-deleted rows (partial unique indexes). | P0 | D | IT | FC | auto | 03 §2.6 | 03 §2.6 | — | — | — | 12 §4.1 |
| DATA-008 | Default reads exclude soft-deleted rows; including them requires explicit opt-in and permission. | P0 | D | IT | FC | auto | 03 §2.4 | — | 08 §2.6 | — | — | 12 §4.2 |
| DATA-009 | Business records are never hard-deleted outside retention, erasure or registered exceptions. | P0 | D | RV | FC | rv | 03 §2.4 | 03 §2.9 | — | — | — | 12 §4.1 |
| DATA-010 | Foreign keys are enforced by the database on every engine. | P0 | D | IT | FC | auto | 03 §1 | 03 §12 | — | — | — | 12 §4.1 |
| DATA-011 | A schema conformance check on SQLite and PostgreSQL fails CI on any contract violation, including any ID-like column without a FK that is not exactly one of the ten registered FK-less identifier columns. | P0 | D, ADR-003 | SL | FC | auto | 03 §2.7 | — | — | — | — | 12 §4.12 |
| DATA-012 | GUID maps to CHAR(32) on SQLite and native uuid on PostgreSQL; every foreign key uses the GUID type; all type mappings are explicit. | P0 | ADR-002 | SL | FC | auto | 03 §12 | 03 §12 | — | — | — | 12 §4.1 |
| DATA-013 | Malformed ids are rejected with 422 INVALID_ID; integer ids and sequence values are never exposed as identifiers. | P0 | ADR-002 | IT | FC | auto | 03 §2.2 | — | 08 §2.2 | — | 11 §5 | 12 §4.6 |
| DATA-014 | Behavioral exceptions to the contract are listed in the exception registry, including the fully documented allow-list of ten FK-less identifier columns (correlation, polymorphic and group ids); unregistered deviations fail CI. | P0 | ADR-003 | SL | FC | auto | 03 §2.9 | 03 §2.11 | — | — | — | 12 §4.12 |
| DATA-015 | Contract fields, audit rows and outbox rows are written in the same database transaction as the business change. | P0 | ADR-003 | IT | FC | auto | 03 §2.8 | — | — | — | — | 12 §4.2 |
| DATA-016 | Money is stored as integer minor units with an ISO currency code. | P0 | D | SL | FC | auto | 03 §1 | 03 §12 | — | — | — | 12 §4.1 |
| DATA-017 | Purge jobs follow a defined order that never violates referential integrity; evidence rows use registered non-FK correlation ids; operational retention values are owner inputs. | P0 | D (F-07) | IT | FC | auto | 03 §2.10 | 03 §2.9 | — | — | — | 12 §4.1 |

### 3.3 AUDIT — Audit framework

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AUDIT-001 | Every create, update, soft-delete, restore and hard-delete of an audited entity writes an audit_log row in the same transaction. | P0 | B | IT | FC | auto | 07 §3 | 03 §7 | — | — | — | 12 §4.2 |
| AUDIT-002 | Audit rows capture entity_type, entity_id, action, old_value, new_value, performed_by, performed_on. | P0 | B | IT | FC | auto | 07 §4 | 03 §7 | 08 §10 | — | — | 12 §4.2 |
| AUDIT-003 | Audit rows also capture changed_fields, request_id, transaction_id, performed_via, ip_address, user_agent. | P0 | D | IT | FC | auto | 07 §4 | 03 §7 | — | — | — | 12 §4.2 |
| AUDIT-004 | audit_log is append-only, enforced by the database. | P0 | D | IT | FC | auto | 07 §6 | 03 §2.9 | — | — | 07 §6.2 | 12 §4.2 |
| AUDIT-005 | Secret fields are never written to audit payloads. | P0 | D | UT | FC | auto | 07 §5 | — | — | — | 07 §5 | 12 §4.2 |
| AUDIT-006 | Child-entity changes record their parent so parent history includes children. | P0 | D | IT | FC | auto | 07 §4.2 | 03 §7 | 08 §8.8 | — | — | 12 §4.2 |
| AUDIT-007 | Bulk exports are audited (who, when, filter, row count). | P1 | D | IT | DEF | auto | 07 §4.3 | — | 08 §8.8 | — | 07 §4.3 | 12 §4.2 |
| AUDIT-008 | Audit Log Viewer with filters by entity, actor, action, date, gated by audit.read. | P0 | B | E2E | FC | auto | 07 §7 | — | 08 §10 | 09 §4.9 | 06 §6.2 | 12 §4.8 |
| AUDIT-009 | Configurable audit retention with verified archival. | P1 | D | RV | DEF | rv | 07 §8.1 | — | — | — | — | 12 §4.2 |
| AUDIT-010 | A write without an actor context fails (fail closed). | P0 | D | UT | FC | auto | 07 §3 | — | — | — | — | 12 §4.2 |
| AUDIT-011 | Personal-data anonymization of live and audit data runs only via an audited procedure from the maintenance process. | P0 | D | IT | FC | auto | 07 §8.2 | — | — | — | 11 §5.6 | 12 §4.2 |
| AUDIT-012 | Authentication and security events are recorded in security_event_log, never in audit_log. | P0 | ADR-004 | IT | FC | auto | 05 §9 | 03 §5.4 | — | — | — | 12 §4.3 |
| AUDIT-013 | Tamper-evidence hash chain over audit_log. | P2 | D | UT | DEF | auto | 07 §6.3 | — | — | — | 07 §6.3 | 12 §4.2 |

### 3.4 AUTH — Authentication and sessions

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AUTH-001 | Users sign in with email and password. | P0 | B | E2E | FC | auto | 05 §3 | — | 08 §4.1 | 09 §4.1 | 05 §3 | 12 §4.5 |
| AUTH-002 | Passwords are hashed with Argon2id and rehashed when parameters strengthen. | P0 | B | UT | FC | auto | 05 §2.1 | 03 §4.2 | — | — | 05 §2.1 | 12 §4.5 |
| AUTH-003 | Password policy: 12 to 128 characters, blocklist, no composition rules. | P0 | D | UT | FC | auto | 05 §2.3 | — | 08 §4.5 | 09 §4.2 | 05 §2.3 | 12 §4.5 |
| AUTH-004 | Access token is a 15-minute ES256 JWT held in memory only. | P0 | B | IT | FC | auto | 05 §5 | — | 08 §4.1 | — | 05 §5 | 12 §4.5 |
| AUTH-005 | Opaque refresh token rotated on every use in an HttpOnly SameSite=Strict cookie; a single 20-second grace response returns an access token only; any other reuse revokes the session. | P0 | B | IT | FC | auto | 05 §6 | 03 §5.2 | 08 §4.2 | — | 05 §6 | 12 §4.5 |
| AUTH-006 | Sessions are persisted server-side and checked uncached on every request, so revocation takes effect on the next request. | P0 | B | IT | FC | auto | 05 §5 | 03 §5.1 | — | — | 05 §7 | 12 §4.5 |
| AUTH-007 | Logout ends the current session; logout-all ends every session. | P0 | B | IT | FC | auto | 05 §7 | — | 08 §4.3 | — | — | 12 §4.5 |
| AUTH-008 | Forgot and reset password with a single-use, 30-minute, hashed token delivered only to the verified email. | P0 | B | IT | FC | auto | 05 §8.1 | 03 §5.3 | 08 §4.5 | 09 §4.2 | 05 §8.1 | 12 §4.5 |
| AUTH-009 | Login and forgot-password responses do not reveal account existence. | P0 | D | IT | FC | auto | 05 §3 | — | 08 §4.5 | — | 05 §2.2 | 12 §4.5 |
| AUTH-010 | Brute-force protection: per (account, network) throttling, distributed-guessing throttle that never blocks password+TOTP, per-IP and edge rate limits. | P0 | D | IT | FC | auto | 05 §4 | 03 §4.2 | — | — | 05 §4 | 12 §4.5 |
| AUTH-011 | No self-registration; staff accounts are invited. | P0 | D | IT | FC | auto | 05 §8.4 | — | 08 §5.2 | 09 §4.2 | — | 12 §4.11 |
| AUTH-012 | Users can change their password; other sessions are revoked. | P0 | D | IT | FC | auto | 05 §8.5 | — | 08 §4.5 | — | — | 12 §4.5 |
| AUTH-013 | All authentication events, including every token refresh, are recorded in security_event_log. | P0 | ADR-004 | IT | FC | auto | 05 §9.1 | 03 §5.4 | — | — | — | 12 §4.3 |
| AUTH-014 | The first Founder is created by a one-time CLI bootstrap; no default credentials exist. | P0 | D | OP | FC | op | 05 §10 | — | — | — | 05 §10 | 12 §4.9 |
| AUTH-015 | MFA is enforced according to the amended MFA policy (ADR-006). | P0 | ADR-006 | E2E | FC | auto | 05 §11 | — | — | 09 §4.10 | 05 §11 | 12 §4.5 |
| AUTH-016 | Users list and revoke their sessions; authorized admins revoke another user's sessions (G9, step-up). | P0 | D | IT | FC | auto | 05 §7 | — | 08 §4.6 | 09 §4.6 | — | 12 §4.5 |
| AUTH-017 | Deactivating or deleting a user revokes all their sessions with effect on the next request. | P0 | D | IT | FC | auto | 05 §7 | — | 08 §5.5 | — | — | 12 §4.11 |
| AUTH-018 | Initial personas Founder, Admin (MFA mandatory) and Sales (MFA optional by default) are supported. | P0 | B | IT | FC | auto | 05 §12 | — | — | — | — | 12 §4.4 |

### 3.5 SEVT — Security event log

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SEVT-001 | A dedicated append-only security_event_log exists, separate from audit_log. | P0 | ADR-004 | IT | FC | auto | 05 §9.2 | 03 §5.4 | — | — | 07 §6.2 | 12 §4.3 |
| SEVT-002 | The event catalog covers authentication, refresh, logout, session revocation, password reset, email change, MFA enrollment/challenge/recovery, administrative MFA reset stages, approvals, break-glass, throttling, permission suspension, sensitive actions/reads and public-intake blocks. | P0 | ADR-004 | IT | FC | auto | 05 §9.1 | 03 §5.4 | — | — | — | 12 §4.3 |
| SEVT-003 | No raw or hashed tokens, passwords, OTP secrets or codes, recovery codes or request bodies are stored; detail keys are allow-listed. | P0 | ADR-004 | UT | FC | auto | 05 §9.3 | 03 §5.4 | — | — | 05 §9.3 | 12 §4.3 |
| SEVT-004 | Retention is configurable with values supplied by the owner (OWNER-INPUT-002); archival verifies and anchors externally before deletion. | P0 | ADR-004 | OP | FC | op | 05 §9.4 | — | — | — | — | 12 §4.3 |
| SEVT-005 | security_event.read is ALL-only, held by Founder and Admin, effective only in MFA-verified sessions; standard Sales has no access, including to their own events. | P0 | ADR-004 | IT | FC | auto | 05 §9.5 | — | 08 §10.1 | 09 §4.9 | 06 §6.2 | 12 §4.3 |
| SEVT-006 | Tamper evidence: DB immutability, keyed HMAC chain (key outside the DB) with RFC 8785 canonicalization, nightly verification. | P0 | ADR-004 | UT | FC | auto | 05 §9.6 | 03 §5.4 | — | — | 07 §6.3 | 12 §4.3 |
| SEVT-007 | Daily chain head and archival anchors are written to an S3 Object Lock (compliance) bucket through a write-only role. | P0 | ADR-004 | OP | FC | op | 05 §9.6 | — | — | — | 07 §6.3 | 12 §4.3 |
| SEVT-008 | Indexed, cursor-paginated queries by time, subject, type, IP and outcome. | P0 | ADR-004 | IT | FC | auto | 05 §9.7 | 03 §5.4 | 08 §10.1 | — | — | 12 §4.3 |
| SEVT-009 | Monitoring and alerting rules for security events. | P0 | ADR-004 | OP | FC | op | 05 §9.8 | — | — | — | 02 §9 | 12 §4.9 |
| SEVT-010 | Capacity figures are assumptions until measured; review after 30 days of production traffic. | P0 | ADR-004 | RV | FC | rv | 05 §9.9 | — | — | — | — | 12 §4.9 |
| SEVT-011 | Failure and denial events persist even when the triggering request rolls back. | P0 | ADR-004 | IT | FC | auto | 05 §9.2 | 03 §2.8 | — | — | — | 12 §4.3 |

### 3.6 MFA — Multi-factor authentication and recovery

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MFA-001 | TOTP authenticator-app MFA with enrollment and login challenge. | P0 | ADR-006 | E2E | FC | auto | 05 §11.2 | 03 §5.5 | 08 §4.7 | 09 §4.10 | 05 §11.2 | 12 §4.5 |
| MFA-002 | MFA is mandatory for Founder and Admin through data-driven policy (role.mfa_required), never role-name checks. | P0 | ADR-006 | IT | FC | auto | 05 §11.1 | 03 §4.3 | — | — | 06 §2 | 12 §4.5 |
| MFA-003 | MFA is optional by default for standard Sales and configurable per user (app_user.mfa_required) or per role (role.mfa_required). | P0 | ADR-006 | IT | FC | auto | 05 §11.1 | 03 §4.1 | 08 §5.9 | 09 §4.6 | — | 12 §4.5 |
| MFA-004 | Holders of any sensitive permission (including suspended) must use MFA. | P0 | ADR-006 | IT | FC | auto | 05 §11.1 | 03 §4.4 | — | — | 06 §3 | 12 §4.5 |
| MFA-005 | Ten CSPRNG recovery codes, stored only as keyed hashes, single-use, rotated at every (re-)enrollment including after recovery, never logged and never returned after issuance. | P0 | ADR-006 | IT | FC | auto | 05 §11.5 | 03 §5.6 | 08 §4.7 | 09 §4.10 | 05 §11.5 | 12 §4.5 |
| MFA-006 | MFA enrollment, challenges, recovery stages, code consumption, re-enrollment and administrative reset stages are security events. | P0 | ADR-006 | IT | FC | auto | 05 §9.1 | 03 §5.4 | — | — | — | 12 §4.3 |
| MFA-007 | Administrative MFA reset uses the separate user.mfa.reset permission with step-up and reason, never self (G3), never a stronger target (G9), Founder only via the Founder workflow, and sends the enrollment link to the target's verified email. | P0 | ADR-006 | IT | FC | auto | 05 §11.7 | — | 08 §5.9 | 09 §4.6 | 06 §7 | 12 §4.5 |
| MFA-008 | No security questions, SMS/email OTP factors or device-remember bypass. | P0 | ADR-006 | RV | FC | rv | 05 §11.8 | — | — | — | 05 §11.8 | 12 §2 |
| MFA-009 | TOTP replay protection and attempt limits. | P0 | ADR-006 | UT | FC | auto | 05 §11.2 | 03 §5.5 | — | — | 05 §4 | 12 §4.5 |
| MFA-010 | TOTP secrets are KMS-envelope-encrypted (wrapped key TEXT, ARN separate) and never returned after enrollment. | P0 | ADR-006 | IT | FC | auto | 05 §11.2 | 03 §5.5 | — | — | 02 §11.4 | 12 §4.5 |
| MFA-011 | Step-up (MFA within 10 minutes) and password re-authentication (within 5 minutes) gate sensitive operations. | P0 | ADR-006 | IT | FC | auto | 05 §11.6 | 03 §5.1 | 08 §4.7 | — | 06 §7 | 12 §4.5 |
| MFA-012 | Sensitive permissions are effective only with an active factor in an MFA-verified full session; they are suspended when MFA is absent, removed or reset, and account/access-control classes are suspended during recovery cooling-off. | P0 | Decision 1 | IT | FC | auto | 06 §3.2 | 03 §5.1 | 08 §4.4 | 09 §4.6 | 06 §5 | 12 §4.4 |
| MFA-013 | Self-service recovery requires password re-entry and a recovery code, completes the login challenge and invalidates all other challenges, creates a restricted RECOVERY session limited to re-enrollment, revokes all other sessions, notifies the verified email, commits re-enrollment atomically with code rotation, and applies a cooling-off period. | P0 | Decision 2 | IT | FC | auto | 05 §11.5 | 03 §5.1 | 08 §4.7 | 09 §4.10 | 06 §8 | 12 §4.12 |
| MFA-014 | A new authenticator is enrolled only through a two-proof path; never with a password alone or a recovery code alone. | P0 | D (F-02) | IT | FC | auto | 05 §11.3 | 03 §5.3 | 08 §4.7 | 09 §4.10 | 05 §11.3 | 12 §4.12 |
| MFA-015 | Administrative MFA reset of a privileged account needs dual control; a Founder's MFA reset is the Founder-level action FOUNDER_MFA_RESET under the canonical Founder-governance workflow. | P0 | Decision 2 | IT | FC | auto | 06 §7.4 | 03 §5.8 | 08 §5.11 | 09 §4.12 | 06 §7.5 | 12 §4.12 |

### 3.7 RBAC — Authorization

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RBAC-001 | Tables app_user, role, permission, user_role, role_permission, user_permission exist before any business module. | P0 | B | SL | FC | auto | 02 §8.3 | 03 §4 | — | — | — | 12 §4.1 |
| RBAC-002 | Authorization checks permission codes only; no role-name, is-admin or user-id checks. | P0 | B | RV | FC | rv | 06 §2 | — | — | — | 06 §2 | 12 §4.4 |
| RBAC-003 | Permission codes follow the resource.action convention. | P0 | B | SL | FC | auto | 06 §3 | 03 §4.4 | — | — | — | 12 §4.4 |
| RBAC-004 | Permissions are declared in a code registry and synchronized by migration. | P0 | D | IT | FC | auto | 06 §3 | 03 §4.4 | 08 §6.2 | — | — | 12 §4.4 |
| RBAC-005 | Each grant carries a data scope: ALL, TEAM (reserved) or OWN. | P0 | D | IT | FC | auto | 06 §4 | 03 §4.6 | — | — | — | 12 §4.4 |
| RBAC-006 | Direct user GRANT and DENY; DENY always wins. | P0 | B | UT | FC | auto | 06 §5 | 03 §4.7 | 08 §5.7 | 09 §4.6 | — | 12 §4.12 |
| RBAC-007 | Time-bound grants (P1): disabled in P0 with 422; when enabled, never allowed on sensitive permissions. | P1 | D | UT | DEF | auto | 06 §5 | 03 §4.5 | 08 §5.7 | — | — | 12 §4.4 |
| RBAC-008 | Founder, Admin and Sales roles are seeded with the default matrix. | P0 | B | IT | FC | auto | 06 §6 | 03 §10 | 08 §6.1 | 09 §4.7 | — | 12 §4.4 |
| RBAC-009 | Anti-escalation: no granting of permissions or scopes the actor lacks (G1, G2 including role copy) and no account-control action on stronger accounts (G9). | P0 | D | IT | FC | auto | 06 §7 | — | — | — | 06 §7 | 12 §4.4 |
| RBAC-010 | No self-administration through admin endpoints: own roles, permissions, status, email, MFA or protection level (G3). | P0 | D | IT | FC | auto | 06 §7 | — | — | — | 06 §7 | 12 §4.4 |
| RBAC-011 | Invariants I1 (an active Founder) and I2 (an active recovery administrator) are enforced transactionally under the write lock and checked nightly. | P0 | D | IT | FC | auto | 06 §7.3 | — | — | — | 06 §7 | 12 §4.4 |
| RBAC-012 | Enforcement at route, service and query layers; UI checks are cosmetic. | P0 | D | IT | FC | auto | 06 §8 | — | — | 09 §3.4 | 06 §8 | 12 §4.4 |
| RBAC-013 | Authorization changes, including MFA-state changes, take effect on the next request. | P0 | D | IT | FC | auto | 06 §9 | 03 §4.1 | — | — | — | 12 §4.4 |
| RBAC-014 | A record outside the actor's scope returns 404. | P0 | D | IT | FC | auto | 06 §8 | — | 08 §11 | — | 11 §5 | 12 §4.4 |
| RBAC-015 | System roles and permissions cannot be deleted; their codes are immutable. | P0 | D | IT | FC | auto | 06 §3 | 03 §4.3 | 08 §6.1 | — | — | 12 §4.4 |
| RBAC-016 | An effective-permissions view explains every permission's source. | P0 | D | E2E | FC | auto | 06 §5 | — | 08 §5.8 | 09 §4.6 | — | 12 §4.4 |
| RBAC-017 | Sensitive permissions need reason and step-up to grant, require MFA of holders, and emit SENSITIVE_ACTION on mutations and de-duplicated SENSITIVE_READ on reads. | P0 | ADR-006 | IT | FC | auto | 06 §3.2 | 03 §4.4 | — | — | 06 §7 | 12 §4.4 |
| RBAC-018 | Sensitivity is a canonical, code-registry classification (sensitivity_class) independent of role names; the seeded Sales role holds no sensitive permission. | P0 | Decision 1 | IT | FC | auto | 06 §3.1 | 03 §4.4 | — | — | 06 §3.1 | 12 §4.4 |
| RBAC-019 | Profile editing and identity/security editing use separate granular permissions; generic endpoints cannot mass-assign email, password, MFA, roles, permissions, status or Founder/privileged status. | P0 | Decision 3 | IT | FC | auto | 06 §6.2 | 03 §4.1 | 08 §5.4 | 09 §4.6 | 06 §8 | 12 §4.4 |
| RBAC-020 | Privileged-account protection: no action on stronger accounts, no Admin action on Founder accounts, no self-deactivation, and last-Founder / last-recovery-administrator invariants. | P0 | Decision 3 | IT | FC | auto | 06 §7.3 | — | 08 §5.6 | 09 §4.6 | 06 §7 | 12 §4.4 |
| RBAC-021 | Founder-level actions (grant/remove Founder status incl. user.founder.manage, Founder MFA recovery, status and email/identity change, break-glass activation, approval-policy change) run only through the canonical Founder-governance workflow: Founder requester and a different Founder approver (or a distinct-human break-glass custodian in single-Founder mode), eligibility re-checked at execution, no generic-API grant path, one open request per target. | P0 | Decision 3 | IT | FC | auto | 06 §7.2 | 03 §5.8 | 08 §5.11 | 09 §4.12 | 06 §7.5 | 12 §4.12 |

### 3.8 USER — User administration

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| USER-001 | Authorized users can invite, read, edit profile fields of, deactivate and soft-delete users, each through its dedicated permission and workflow. | P0 | B | IT | FC | auto | 03 §4.1 | 03 §4.1 | 08 §5 | 09 §4.6 | — | 12 §4.11 |
| USER-002 | User status lifecycle INVITED, ACTIVE, LOCKED, DISABLED. | P0 | D | UT | FC | auto | 03 §4.1 | 03 §4.1 | 08 §5.6 | — | — | 12 §4.11 |
| USER-003 | Email is unique case-insensitively among non-deleted users. | P0 | D | IT | FC | auto | 03 §4.1 | 03 §4.1 | — | — | — | 12 §4.11 |
| USER-004 | Users can view their own profile and edit profile fields only (name, display name, phone, timezone, locale). | P0 | D | IT | FC | auto | 06 §6.1 | — | 08 §4.4 | — | — | 12 §4.11 |
| USER-005 | Seeded non-login system users SYSTEM, WEB_INTAKE and ANONYMOUS exist. | P0 | D | IT | FC | auto | 03 §2.3 | 03 §10 | — | — | — | 12 §4.11 |
| USER-006 | User management shows MFA status and offers MFA administration. | P0 | ADR-006 | E2E | FC | auto | 05 §11.7 | — | 08 §5.9 | 09 §4.6 | — | 12 §4.11 |
| USER-007 | Email changes use the proposed-email workflow: step-up, verification to the new address, alert with cancel to the current address, recovery on the verified address until completion, hashed single-use tokens, session revocation and full audit. | P0 | Decision 3 | IT | FC | auto | 05 §8.6 | 03 §4.1 | 08 §5.5 | 09 §4.13 | 05 §8.6 | 12 §4.5 |

### 3.9 LEAD — Lead management

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LEAD-001 | The website enquiry form creates leads through a public API endpoint. | P0 | B | E2E | FC | auto | 04 §5.1 | — | 08 §8.4 | 09 §4.11 | 04 §5.1 | 12 §4.7 |
| LEAD-002 | A lead holds name, phone, email, city, project_type, budget_range and message plus the audit contract. | P0 | B | SL | FC | auto | 04 §2 | 04 §2 | 08 §8.1 | — | — | 12 §4.7 |
| LEAD-003 | Authorized staff can create leads manually. | P0 | B | E2E | FC | auto | 04 §5.2 | — | 08 §8.3 | 09 §4.5 | — | 12 §4.8 |
| LEAD-004 | Lead status is NEW, CONTACTED, SITE_VISIT, QUOTATION_SENT, NEGOTIATION, WON or LOST. | P0 | B | SL | FC | auto | 04 §3 | 04 §2 | — | — | — | 12 §4.7 |
| LEAD-005 | Status changes follow the state machine; illegal transitions are rejected. | P0 | D | UT | FC | auto | 04 §3 | — | 08 §8.6 | 09 §4.4 | — | 12 §4.7 |
| LEAD-006 | LOST requires a lost reason; WON records won_on. | P0 | D | IT | FC | auto | 04 §3 | 04 §2 | 08 §8.6 | — | — | 12 §4.7 |
| LEAD-007 | Leads can be assigned to users who hold lead.read. | P0 | D | IT | FC | auto | 04 §6 | 04 §2 | 08 §8.7 | 09 §4.4 | — | 12 §4.8 |
| LEAD-008 | Each lead has a unique internal number VS-L-YYYY-NNNNNN, never shown publicly. | P0 | D | IT | FC | auto | 04 §2 | 03 §6.3 | — | — | — | 12 §4.7 |
| LEAD-009 | Phone numbers are validated and normalized to E.164 with India as the default region, accepting international numbers with a country code. | P0 | ADR-005 | UT | FC | auto | 04 §13 | 04 §2 | 08 §8.4 | — | — | 12 §4.7 |
| LEAD-010 | Likely duplicates are flagged and never rejected or silently discarded. | P0 | ADR-005 | IT | FC | auto | 04 §7 | 04 §2 | 08 §8.8 | 09 §4.5 | — | 12 §4.12 |
| LEAD-011 | Source and campaign attribution are captured. | P0 | D | IT | FC | auto | 04 §2 | 04 §2 | 08 §8.4 | — | — | 12 §4.7 |
| LEAD-012 | Consent records policy version, timestamp and source context. | P0 | ADR-005 | IT | FC | auto | 04 §2 | 04 §2 | 08 §8.4 | 09 §4.11 | 11 §5.6 | 12 §4.7 |
| LEAD-013 | Lead list supports search, filter, sort and pagination. | P0 | B | IT | FC | auto | 08 §8.2 | — | 08 §8.2 | 09 §4.3 | — | 12 §4.7 |
| LEAD-014 | Dashboard shows pipeline, new leads, follow-ups, conversion and sources. | P0 | B | E2E | FC | auto | 04 §11 | — | 08 §8.9 | 09 §4.3 | — | 12 §4.8 |
| LEAD-015 | next_follow_up_on is maintained from planned activities; overdue is highlighted. | P0 | D | IT | FC | auto | 04 §8 | 04 §2 | — | 09 §4.3 | — | 12 §4.7 |
| LEAD-016 | Leads can be soft-deleted and restored by authorized users. | P0 | D | IT | FC | auto | 04 §12 | — | 08 §8.8 | — | — | 12 §4.7 |
| LEAD-017 | Leads can be exported to CSV (permission-gated, audited). | P1 | D | IT | DEF | auto | 04 §1 | — | 08 §8.8 | — | 07 §4.3 | 12 §4.2 |
| LEAD-018 | Public intake requires Turnstile and rate limiting (relaxed for mobile NAT); rate limit and idempotency run before CAPTCHA; honeypot hits are quarantined as suspected spam, never dropped. | P0 | ADR-005 | IT | FC | auto | 04 §5.1 | — | 08 §8.4 | 09 §4.3 | 02 §11.1 | 12 §4.7 |
| LEAD-019 | Every public-intake outcome other than 201 or field-level 422 offers the existing WhatsApp hand-off. | P0 | ADR-005 | E2E | FC | auto | 04 §5.1 | — | — | 09 §4.11 | — | 12 §4.8 |
| LEAD-020 | New and assigned leads notify permission-resolved recipients in-app and by email. | P0 | D | IT | FC | auto | 02 §10.3 | — | — | — | — | 12 §4.10 |
| LEAD-021 | Quoted amount is recorded in minor units. | P1 | D | IT | DEF | auto | 04 §2 | 04 §2 | 08 §8.5 | — | — | 12 §4.7 |
| LEAD-022 | Auto-assignment (round robin). | P2 | D | IT | DEF | auto | 04 §6 | — | — | — | — | — |
| LEAD-023 | Public form requires name, phone and consent; email, city, project_type, budget_range, property_type and message are optional. | P0 | ADR-005 | IT | FC | auto | 04 §2 | 04 §2 | 08 §8.4 | 09 §4.11 | — | 12 §4.7 |
| LEAD-024 | Staff can enrich optional fields after capture. | P0 | ADR-005 | IT | FC | auto | 04 §5.3 | — | 08 §8.5 | 09 §4.4 | — | 12 §4.8 |
| LEAD-025 | The public API returns only a random public reference and a message, identical for every accepted submission; no lead id, number, status or internal field is exposed. | P0 | ADR-005 | IT | FC | auto | 04 §5.1 | 04 §2 | 08 §8.4 | — | 11 §5 | 12 §4.7 |
| LEAD-026 | The public form has an accessible error state. | P0 | ADR-005 | E2E | FC | auto | 09 §4.11 | — | — | 09 §4.11 | — | 12 §4.8 |
| LEAD-027 | Consent withdrawal is recorded with channel and blocks contact activities while retaining the original consent evidence. | P0 | D (F-15) | IT | FC | auto | 04 §5.4 | 04 §2 | 08 §8.8 | 09 §4.4 | 11 §5.6 | 12 §4.7 |
| LEAD-028 | A closed-lead retention job anonymizes eligible leads; it ships disabled until the owner approves the period (OWNER-INPUT-002). | P0 | D (F-15) | IT | FC | auto | 04 §14 | 04 §2 | — | — | 11 §5.6 | 12 §4.7 |
| LEAD-029 | Personal-data erasure requests are executed through an audited, step-up-protected anonymization of live and audit data. | P0 | D (F-15) | IT | FC | auto | 04 §14 | 04 §2 | 08 §8.8 | 09 §4.4 | 07 §8.2 | 12 §4.7 |
| LEAD-030 | Unknown or inactive optional lookup codes on public intake are kept raw for staff review and never reject the enquiry or corrupt records. | P0 | Decision 4 | IT | FC | auto | 04 §5.1 | 04 §2 | 08 §8.4 | 09 §4.4 | — | 12 §4.7 |

### 3.10 NOTE — Lead notes

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NOTE-001 | Users with access to a lead can add notes. | P0 | B | IT | FC | auto | 04 §9 | 04 §9 | 08 §9.1 | 09 §4.4 | — | 12 §4.7 |
| NOTE-002 | Authors edit and delete their own notes (confirmed soft delete, no Undo); ALL scope allows others. | P0 | D | IT | FC | auto | 04 §9 | — | 08 §9.1 | 09 §3.2 | 06 §6.3 | 12 §4.7 |
| NOTE-003 | Notes can be pinned. | P1 | D | E2E | DEF | auto | 04 §9 | 04 §9 | — | 09 §4.4 | — | 12 §4.7 |
| NOTE-004 | Notes are INTERNAL; CUSTOMER_VISIBLE is reserved and rejected in P0. | P0 | D | SL | FC | auto | 04 §9 | 04 §9 | 08 §9.1 | — | — | 12 §4.7 |

### 3.11 ACT — Lead activities

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ACT-001 | Activities of type CALL, WHATSAPP, EMAIL, MEETING, SITE_VISIT, QUOTATION, FOLLOW_UP can be recorded. | P0 | B | IT | FC | auto | 04 §10 | 04 §10 | 08 §9.2 | 09 §4.4 | — | 12 §4.7 |
| ACT-002 | Activities can be planned, completed or cancelled. | P0 | D | IT | FC | auto | 04 §10 | 04 §10 | 08 §9.2 | 09 §4.4 | — | 12 §4.7 |
| ACT-003 | Completing an activity records outcome and time. | P0 | D | IT | FC | auto | 04 §10 | — | 08 §9.2 | — | — | 12 §4.7 |
| ACT-004 | Status changes and assignments generate immutable system activities. | P0 | D | IT | FC | auto | 04 §10 | 04 §10 | — | — | — | 12 §4.7 |
| ACT-005 | Call and WhatsApp buttons prompt a prefilled activity quick-log. | P1 | D | E2E | DEF | auto | 04 §10 | — | — | 09 §4.4 | — | — |

### 3.12 NOTIF — Notifications

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NOTIF-001 | In-app notifications with unread count and mark-as-read. | P0 | B | IT | FC | auto | 02 §10.2 | 03 §8.2 | 08 §7 | 09 §3.1 | — | 12 §4.10 |
| NOTIF-002 | Transactional email through a pluggable provider adapter. | P0 | B | IT | FC | auto | 02 §10.2 | — | — | — | — | 12 §4.10 |
| NOTIF-003 | Side effects go through a transactional outbox. | P0 | D | IT | FC | auto | 02 §10.1 | 03 §8.1 | — | — | — | 12 §4.10 |
| NOTIF-004 | Outbox retries with backoff and dead-letters with alerting. | P0 | D | IT | FC | auto | 02 §10.1 | 03 §8.1 | — | — | — | 12 §4.10 |
| NOTIF-005 | Email templates are versioned, branded, with plain-text alternatives. | P0 | D | RV | FC | rv | 02 §10.3 | — | — | — | — | 12 §4.10 |
| NOTIF-006 | Follow-up reminders and daily digest. | P1 | D | IT | DEF | auto | 04 §8 | — | — | — | — | — |
| NOTIF-007 | WhatsApp Business API notifications. | P2 | D | IT | DEF | auto | 02 §10.2 | — | — | — | — | — |
| NOTIF-008 | Email delivery failures never roll back or block a persisted lead. | P0 | ADR-007 | IT | FC | auto | 02 §10.3 | — | — | — | — | 12 §4.7 |
| NOTIF-009 | Amazon SES in production; a development/test adapter elsewhere until SES production access exists. | P0 | ADR-007 | IT | FC | auto | 02 §10.2 | — | — | — | — | 12 §4.10 |

### 3.13 LOG — Logging and observability

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LOG-001 | Structured JSON application logs. | P0 | B, ADR-008 | RV | FC | rv | 02 §9 | — | — | — | — | 12 §4.9 |
| LOG-002 | Every request has a request_id returned in headers and error bodies and present in logs, audit and security events. | P0 | D | IT | FC | auto | 02 §9 | — | 08 §2.4 | — | — | 12 §4.6 |
| LOG-003 | Logs never contain passwords, tokens or unmasked personal data. | P0 | D | UT | FC | auto | 02 §9 | — | — | — | 02 §9 | 12 §4.9 |
| LOG-004 | Unhandled exceptions are reported to an error tracker. | P0 | D | OP | FC | op | 02 §9 | — | — | — | — | 12 §4.9 |
| LOG-005 | Health and readiness endpoints; readiness reflects only DB, migrations, FK pragma and immutability triggers, never outbox or email health. | P0 | D, ADR-008 | IT | FC | auto | 02 §9 | — | 08 §3 | — | — | 12 §4.6 |
| LOG-006 | Metrics and alerting are mandatory in P0. | P0 | ADR-008 | OP | FC | op | 02 §9 | — | — | — | 02 §9 | 12 §4.9 |

### 3.14 SEC — Security and privacy

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SEC-001 | TLS end to end and HSTS. | P0 | D | OP | FC | op | 02 §11.1 | — | — | — | 02 §11.2 | 12 §4.9 |
| SEC-002 | CORS allow-list with credentials only for the app origin. | P0 | D | IT | FC | auto | 02 §11.3 | — | — | — | 02 §11.3 | 12 §4.9 |
| SEC-003 | Strict security headers and CSP. | P0 | D | IT | FC | auto | 02 §11.2 | — | — | — | 02 §11.2 | 12 §4.9 |
| SEC-004 | All input validated against closed schemas with length limits. | P0 | D | UT | FC | auto | 08 §2.2 | — | 08 §2.2 | — | 11 §5 | 12 §4.6 |
| SEC-005 | Secrets in AWS SSM, Secrets Manager or KMS with documented rotation. | P0 | D, ADR-008 | RV | FC | rv | 02 §11.4 | — | — | — | 02 §11.4 | 12 §4.11 |
| SEC-006 | The origin accepts traffic only from Cloudflare. | P0 | D | OP | FC | op | 02 §11.1 | — | — | — | 02 §11.1 | 12 §4.9 |
| SEC-007 | Dependency and container vulnerability scanning in CI. | P0 | D | OP | FC | op | 02 §12.5 | — | — | — | 11 §5 | 12 §5 |
| SEC-008 | Backups are encrypted and restore is verified automatically. | P0 | D, ADR-008 | OP | FC | op | 02 §12.3 | — | — | — | 02 §11.1 | 12 §4.9 |
| SEC-009 | DPDP Act 2023 alignment. | P0 | D | RV | FC | rv | 11 §5.6 | — | — | — | 11 §5.6 | 12 §2 |
| SEC-010 | Target OWASP ASVS v4 Level 2. | P1 | D | RV | DEF | rv | 11 §5 | — | — | — | 11 §5 | 12 §2 |
| SEC-011 | Rate limiting at edge and application (single-process limiter) for auth, MFA and public endpoints. | P0 | D | IT | FC | auto | 02 §11.1 | — | 08 §12 | — | 05 §4 | 12 §4.9 |

### 3.15 API — API conventions

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| API-001 | REST over HTTPS with JSON under /api/v1. | P0 | B | IT | FC | auto | 02 §4 | — | 08 §2 | — | — | 12 §4.6 |
| API-002 | Standard success envelope. | P0 | D | IT | FC | auto | 08 §2.3 | — | 08 §2.3 | — | — | 12 §4.6 |
| API-003 | Errors use RFC 9457 problem details with stable codes. | P0 | B | IT | FC | auto | 08 §2.4 | — | 08 §2.4 | — | — | 12 §4.6 |
| API-004 | Offset pagination for admin lists and cursor pagination for streams. | P0 | B | IT | FC | auto | 08 §2.5 | — | 08 §2.5 | — | — | 12 §4.6 |
| API-005 | Filtering, search and allow-listed sorting. | P0 | B | IT | FC | auto | 08 §2.6 | — | 08 §2.6 | — | — | 12 §4.6 |
| API-006 | Updates require If-Match; stale versions return 409. | P0 | D | IT | FC | auto | 08 §2.7 | — | 08 §2.7 | — | — | 12 §4.12 |
| API-007 | Idempotency-Key with request fingerprint; replay returns the original response; key reuse with a different body returns 422; lookup precedes CAPTCHA. | P0 | D | IT | FC | auto | 08 §2.8 | — | 08 §2.8 | — | — | 12 §4.6 |
| API-008 | OpenAPI 3.1 is the contract source of truth. | P0 | D | RV | FC | rv | 08 §2.1 | — | 08 §2.1 | — | — | 12 §4.6 |
| API-009 | Only additive changes within v1; breaking changes require v2. | P0 | D | RV | FC | rv | 08 §2.9 | — | 08 §2.9 | — | — | 12 §4.6 |

### 3.16 UI — User interface

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| UI-001 | Login screen. | P0 | B | E2E | FC | auto | 09 §4.1 | — | — | 09 §4.1 | — | 12 §4.8 |
| UI-002 | Forgot password and reset screens. | P0 | B | E2E | FC | auto | 09 §4.2 | — | — | 09 §4.2 | — | 12 §4.8 |
| UI-003 | Lead dashboard. | P0 | B | E2E | FC | auto | 09 §4.3 | — | — | 09 §4.3 | — | 12 §4.8 |
| UI-004 | Lead details. | P0 | B | E2E | FC | auto | 09 §4.4 | — | — | 09 §4.4 | — | 12 §4.8 |
| UI-005 | Lead create and edit. | P0 | B | E2E | FC | auto | 09 §4.5 | — | — | 09 §4.5 | — | 12 §4.8 |
| UI-006 | User management. | P0 | B | E2E | FC | auto | 09 §4.6 | — | — | 09 §4.6 | — | 12 §4.8 |
| UI-007 | Role management. | P0 | B | E2E | FC | auto | 09 §4.7 | — | — | 09 §4.7 | — | 12 §4.8 |
| UI-008 | Permission management. | P0 | B | E2E | FC | auto | 09 §4.8 | — | — | 09 §4.8 | — | 12 §4.8 |
| UI-009 | Audit log viewer, including security events. | P0 | B | E2E | FC | auto | 09 §4.9 | — | — | 09 §4.9 | — | 12 §4.8 |
| UI-010 | Visual language derives from Veda Spaces brand tokens. | P0 | B | RV | FC | rv | 09 §2 | — | — | 09 §2 | — | 12 §4.8 |
| UI-011 | WCAG 2.2 AA conformance in light and dark themes. | P0 | D | E2E | FC | auto | 09 §5 | — | — | 09 §5 | — | 12 §4.8 |
| UI-012 | Lead screens are fully usable at 360 px width. | P0 | D | E2E | FC | auto | 09 §3.1 | — | — | 09 §3.1 | — | 12 §4.8 |
| UI-013 | UI hides or disables actions the user lacks permission for (cosmetic). | P0 | D | E2E | FC | auto | 09 §3.4 | — | — | 09 §3.4 | — | 12 §4.8 |
| UI-014 | Accessibility corrections are encoded as design-system tokens, including on-color tokens and dark-theme values, checked automatically. | P0 | D | RV | FC | rv | 09 §2.5 | — | — | 09 §2.5 | — | 12 §4.8 |
| UI-015 | MFA challenge, enrollment, recovery (restricted mode, cooling-off) and step-up screens. | P0 | ADR-006 | E2E | FC | auto | 09 §4.10 | — | — | 09 §4.10 | — | 12 §4.8 |
| UI-016 | Testable accessibility criteria AX-01…AX-10 for keyboard, focus, error announcements, labels, contrast, mobile, login/MFA, public form and admin lead workflow. | P0 | D (F-14) | E2E | FC | auto | 09 §5 | — | — | 09 §5 | — | 12 §4.8 |
| UI-017 | Approvals inbox and self-service email-change screens. | P0 | Decision 3 | E2E | FC | auto | 09 §4.12 | — | — | 09 §4.12 | — | 12 §4.8 |

### 3.17 OPS — Operations, deployment, backup

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OPS-001 | CI runs the full suite on SQLite and PostgreSQL. | P0 | D, ADR-007 | OP | FC | op | 02 §12.5 | — | — | — | — | 12 §5 |
| OPS-002 | Continuous SQLite replication to S3 plus nightly snapshots. | P0 | D, ADR-008 | OP | FC | op | 02 §12.3 | — | — | — | — | 12 §4.9 |
| OPS-003 | Local, staging and production environments; staging uses synthetic or anonymized data. | P0 | D | RV | FC | rv | 02 §12.1 | — | — | — | — | 12 §3 |
| OPS-004 | Single deploy and migration runbook: expand-only N-1-compatible migrations, normal rollback by redeploying N-1, disaster rollback by snapshot restore with a stated data-loss window. | P0 | D | OP | FC | op | 02 §12.4 | — | — | — | — | 12 §4.1 |
| OPS-005 | RPO and RTO are owner-approved values (OWNER-INPUT-001), measured in rehearsal. | P0 | ADR-008 | OP | NT | owner | 02 §12.3 | — | — | — | — | 12 §4.9 |
| OPS-006 | Exactly one active application instance while SQLite is authoritative. | P0 | ADR-008 | OP | FC | op | 02 §12.2 | — | — | — | — | 12 §4.9 |
| OPS-007 | SQLite lives on a dedicated, persistent, encrypted volume, never only in a container layer. | P0 | ADR-008 | OP | FC | op | 02 §12.2 | — | — | — | 02 §11.1 | 12 §4.9 |
| OPS-008 | PostgreSQL migration is a release gate before procurement, inventory, finance or multi-instance scale. | P0 | ADR-008 | RV | FC | rv | 11 §3.3 | — | — | — | — | 12 §2 |
| OPS-009 | Automated restore verification with alerting. | P0 | ADR-008 | OP | FC | op | 02 §12.3 | — | — | — | — | 12 §4.9 |
| OPS-010 | Exactly one application process (gunicorn gthread, one worker) so in-process limiter, idempotency and permission caches are authoritative. | P0 | D (F-09) | OP | FC | op | 02 §3.5 | — | — | — | — | 12 §4.9 |
| OPS-011 | The backend region is ap-south-1 as configuration; no multi-region availability is claimed; DR implications are documented. | P0 | Decision 5 | OP | FC | op | 02 §12.2 | — | — | — | — | 12 §4.9 |

### 3.18 NFR — Non-functional targets

| ID | Requirement | Pri | Src | Verify | Class | Test | Arch | Schema | API | UI | Security | Test design |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NFR-001 | p95 API latency below 300 ms for list and detail endpoints at the load-test fixture sizes (ASM-007). | P0 | D | IT | FC | auto | 11 §1 | — | — | — | — | 12 §4.9 |
| NFR-002 | API availability meets the owner-approved target (OWNER-INPUT-001). | P0 | D, ADR-008 | OP | NT | owner | 02 §9 | — | — | — | — | 12 §4.9 |
| NFR-003 | Public intake p95 below 800 ms including CAPTCHA verification. | P0 | D | IT | FC | auto | 04 §5.1 | — | — | — | — | 12 §4.9 |
| NFR-004 | Initial JS below 200 KB gzipped and LCP below 2.5 s on 4G. | P1 | D | E2E | DEF | auto | 02 §2.1 | — | — | — | — | 12 §4.8 |

## 4. Reserved prefixes for future modules (not authorized, ADR-009)

| Prefix | Module | Prefix | Module |
|---|---|---|---|
| CUST | Customer management | INV | Inventory |
| QUOTE | Quotations and estimates | EMP | Employee records |
| PROJ | Project management | ONB | Employee onboarding |
| DSGN | Design workflow | PAY | Payroll |
| VEND | Vendor management | PORT | Customer portal |
| PROC | Procurement | WARR | Warranty and support |
| ATT | Attachments/documents | AI | AI features |
| ORG | Organization, branches, teams | FIN | Invoicing and payments |

## 5. Brief and decision coverage

| Source item | Requirements |
|---|---|
| Audit contract on every table (brief, ADR-003) | DATA-001…011, DATA-014, DATA-015 |
| UUIDv7 identifiers (ADR-002) | DATA-002, DATA-012, DATA-013 |
| Purge integrity (F-07) | DATA-017 |
| `app_user` physical table (ADR-001) | PLAT-013, RBAC-001 |
| Sales MFA and security-event access (remediation Decision 1) | MFA-003, MFA-004, MFA-012, RBAC-018, SEVT-005 |
| MFA recovery (Decision 2) | MFA-005, MFA-007, MFA-013, MFA-014, MFA-015 |
| Account control and privileged protection (Decision 3) | RBAC-019, RBAC-020, RBAC-021, USER-007 |
| Property type (Decision 4) | LEAD-023, LEAD-030 |
| AWS region (Decision 5) | OPS-011 |
| Consent withdrawal, retention, erasure (F-15) | LEAD-027, LEAD-028, LEAD-029, AUDIT-011 |
| user/role/permission/user_role/role_permission/user_permission first (brief) | RBAC-001 |
| Authentication from day 1 (brief) | AUTH-001…018 |
| Security event log (ADR-004) | SEVT-001…011, AUDIT-012, AUTH-013 |
| MFA (ADR-006) | AUTH-015, MFA-001…011, RBAC-017, USER-006, UI-015 |
| Lead fields and statuses (brief, ADR-005) | LEAD-002, LEAD-004, LEAD-009, LEAD-012, LEAD-023…026 |
| lead_note, lead_activity (brief) | NOTE-*, ACT-* |
| Founder/Admin/Sales (brief) | AUTH-018, RBAC-008 |
| Permission-based, no hardcoded admin (brief) | RBAC-002, RBAC-003, MFA-002 |
| Audit capture fields (brief) | AUDIT-002 |
| REST with pagination/search/filter/errors (brief) | API-001…009 |
| Screens, premium brand, accessibility (brief) | UI-001…017 |
| Stack (ADR-007) | PLAT-001, PLAT-002, PLAT-004, NOTIF-008, NOTIF-009 |
| AWS hosting (ADR-008) | PLAT-003, OPS-002…011, LOG-006, NFR-002 |
| P0 scope (ADR-009) | PLAT-012 |
| Future modules without rewrites (brief) | PLAT-011, DATA-001, 10 §2 |
