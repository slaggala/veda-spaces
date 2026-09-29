# 12 — Test Strategy

Governing decisions: all ADRs. This document defines **how** each requirement's verification method (01, "Verify" column) is carried out. It is design only: no tests are implemented by this freeze.

## 1. Principles

> Traces: PLAT-006

1. Every requirement has at least one verification method. A requirement is **Done** only when that verification passes (01 §1).
2. Tests carry requirement IDs in their name or marker, for example `test_LEAD_005_rejects_two_step_backward`, so coverage is reported per ID.
3. Security and authorization behavior is tested **negatively** (what must be denied), not only positively.
4. The database-dependent suites run on **both** SQLite and PostgreSQL from day one (OPS-001).

## 2. Verification methods

| Code | Method | Tooling (implementation phase) | Runs |
|---|---|---|---|
| UT | Unit test: pure logic (state machine, policy resolution, validation, hashing parameters) | pytest · Web Test Runner for Lit components | Every PR |
| IT | Integration / API test through the HTTP layer against a real database | pytest + Flask test client, parametrized over SQLite and PostgreSQL | Every PR |
| E2E | Browser end-to-end test, including axe-core accessibility checks | Playwright | Every PR (smoke) · nightly (full) |
| SL | Schema lint: the conformance check (03 §2.7) against a freshly migrated database | Introspection job on both engines | Every PR |
| RV | Review: a documented checklist item in PR review or architecture review. RV checklist items: stack and hosting conformance (PLAT-001, PLAT-002), requirement-ID referencing (PLAT-006), excluded MFA methods absent (MFA-008), DPDP obligations (SEC-009), ASVS L2 (SEC-010), PostgreSQL release gate enforced before gated modules (OPS-008), secrets kept in managed stores (SEC-005). | PR template + reviewer sign-off | Per change |
| OP | Operational drill or verification in a deployed environment | Runbooks, scheduled jobs, alert test-fires | Staging before go-live, then on schedule |

## 3. Environments and data

| Environment | Database | Data | Used for |
|---|---|---|---|
| CI | Ephemeral SQLite file + PostgreSQL service container | Generated fixtures only | UT, IT, SL, E2E |
| Staging | SQLite on an encrypted volume (plus PostgreSQL for rehearsals) | Synthetic or anonymized | E2E full, OP drills, load tests |
| Production | SQLite | Real | OP verification jobs only (restore verification, chain verification, health) |

Fixtures never contain real customer data (OPS-003).

## 4. Platform suites

### 4.1 Schema conformance (DATA-001…016, PLAT-013, SL)

> Traces: DATA-002, DATA-004, DATA-007, DATA-009, DATA-011, DATA-012, DATA-014

The conformance check (03 §2.7) runs on both engines. The suite also includes **negative fixtures**: deliberately broken migrations that must fail the check. These include:

- a table missing `version`;
- an `INTEGER` primary key;
- a `user` table;
- an FK without the GUID type;
- a unique index without the soft-delete predicate;
- an unregistered exception;
- a `REAL` or `NUMERIC` money column instead of integer minor units (DATA-016).

It also checks that the migration order creates the identity and RBAC tables before any business-module table (RBAC-001), and that SQLite connections report `foreign_keys = 1` (DATA-010).

### 4.2 Audit capture (AUDIT-*, DATA-015)

> Traces: AUDIT-001, AUDIT-002, AUDIT-003, AUDIT-005, DATA-003, DATA-005, LEAD-017

For each FULL-policy entity, the suite checks:

- CREATE, UPDATE, soft DELETE and RESTORE produce exactly the expected `audit_log` rows, with redaction applied;
- a forced exception after flush leaves **no** business row **and no** audit row (atomicity);
- a write without ActorContext fails (AUDIT-010);
- UPDATE and DELETE on `audit_log` are rejected by the database on both engines (AUDIT-004);
- default repository queries exclude soft-deleted rows, and `include_deleted` requires the resource's restore permission (DATA-008);
- child changes carry `parent_entity_type` and `parent_entity_id`, and the parent's history query returns them (AUDIT-006);
- an export writes one EXPORT row with filters and row count (AUDIT-007, P1);
- the archival job exports, verifies and deletes, then writes its summary row (AUDIT-009, P1);
- the anonymization procedure rewrites only `pii_fields` and writes an ANONYMIZE row (AUDIT-011, P1);
- (P2) the audit hash-chain verification detects tampering (AUDIT-013).

### 4.3 Security event log (SEVT-*, AUTH-013)

> Traces: AUDIT-012, MFA-006, SEVT-001, SEVT-002

| Test | Checks |
|---|---|
| Catalog completeness | Each event type in 05 §9.1 is emitted by the flow that should emit it |
| Prohibited content | Every event fixture is scanned for token-shaped strings, 64-hex hashes outside allowed columns, password/OTP/recovery-code field names and request bodies (SEVT-003) |
| Allow-list | The writer rejects unknown `detail` keys |
| Failure persistence | A failed login inside a rolled-back request still leaves its event (SEVT-011) |
| Chain | Appends produce a valid chain. A tampered row or a gap is detected by the verification routine (SEVT-006). |
| Access | ALL vs OWN scope filtering. Chain and hash columns are absent from API output (SEVT-005). |
| Retention | The archival job exports, verifies, anchors and deletes, and chain verification continues from the anchor (SEVT-004) |
| External anchor (P1) | The daily chain head is written to the Object Lock bucket, and verification compares against it (SEVT-007) |
| Query paths | Every filter in 08 §10.1 uses an index (query-plan assertion on both engines). Cursor pagination is stable under concurrent inserts (SEVT-008). |

### 4.4 Authorization (RBAC-*)

> Traces: AUTH-018, RBAC-005, RBAC-008, RBAC-009, RBAC-010, RBAC-011, RBAC-012, RBAC-015

| Test | Checks |
|---|---|
| Matrix | Generated from the seeded role matrix: every (role, permission, scope) × protected endpoint returns allow or deny as expected |
| Scope | OWN users see only owned rows in lists, detail (404 otherwise), dashboards and child lists (RBAC-014) |
| Guards | G1–G10 positive and negative cases (06 §7) |
| No role-name authorization | Lint (RBAC-002) plus a test that renaming a role's code changes no authorization or MFA outcome |
| Exception register | Every route is either permission-gated or listed in RBX-* (06 §11). Startup fails otherwise. |
| Registry | Permission codes match the naming pattern. The sync migration inserts, updates and soft-deletes codes. Every code is granted to at least one system role (RBAC-003, RBAC-004). |
| Resolution | Unit tests of the algorithm in 06 §5: DENY beats GRANT, broadest scope wins, validity windows honored (RBAC-006, RBAC-007) |
| Propagation | A grant change increments `authz_version`, and the next request (within the cache TTL) sees it (RBAC-013) |
| Sensitive permissions | Granting needs a reason and step-up. Use emits `SENSITIVE_ACTION`. Holding one forces MFA (RBAC-017). |
| Explain view | The effective-permissions endpoint lists every source (RBAC-016, P1) |

### 4.5 Authentication and MFA (AUTH-*, MFA-*)

> Traces: AUTH-001, AUTH-004, AUTH-005, AUTH-006, AUTH-008, AUTH-009, AUTH-015, MFA-001, MFA-002, MFA-003, MFA-004, MFA-005, MFA-007, MFA-009, MFA-010, MFA-011

| Test | Checks |
|---|---|
| Login outcomes | Uniform `INVALID_CREDENTIALS` and timing band for unknown, bad, locked, disabled and invited users |
| Password hashing and policy | Argon2id parameters at or above the minimum. Transparent rehash on weaker parameters. Policy rules and error codes (AUTH-002, AUTH-003). |
| Lockout | Account lockout after the configured failures, escalating windows, unlock paths (AUTH-010) |
| Logout and sessions | Logout, logout-all, own-session list and revoke (AUTH-007, AUTH-016) |
| Change password | Requires the current password. Revokes other sessions. (AUTH-012) |
| Tokens | JWT claims and expiry. Refresh rotation. Reuse → session revoked + CRITICAL event. |
| MFA policy | Each of the three sources in 05 §11.1 independently requires MFA. Sales without a source doesn't. Opting in means always challenged. |
| TOTP | RFC 6238 test vectors. Drift window. Replay rejection (`last_used_step`). Attempt limits. |
| Recovery codes | Shown once, stored only as keyed hashes (a database scan finds no plaintext), single use, regeneration invalidates the old batch |
| Step-up | Protected operations return `STEP_UP_REQUIRED` without a recent verification |
| MFA reset | Permission, step-up, reason, no-self, no-stronger-target, all side effects and notifications |
| Secrets | TOTP secret absent from every response after enrollment and from all logs and events |
| Password reset | Doesn't bypass MFA. Revokes sessions. |

### 4.6 API contract (API-*, DATA-013)

> Traces: API-001, API-002, API-003, API-004, API-005, API-006, API-007, API-008, API-009, DATA-006

| Test | Checks |
|---|---|
| OpenAPI | Diff vs `main` fails on breaking changes |
| Envelope and errors | Every endpoint returns documented shapes and problem codes |
| ID validation | Malformed, hyphenated, uppercase and non-v7 ids → `422 INVALID_ID` |
| Concurrency | Missing `If-Match` → 428. Stale → 409. |
| Idempotency | Replay returns the original response. Same key with a different body → 422. |
| Closed schemas | Unknown fields → `UNKNOWN_FIELD`. Server-side length limits enforced (SEC-004). |
| Request id | Every response carries `X-Request-ID`. Error bodies include it (LOG-002). |
| Health | `/health/live` and `/health/ready` return their documented shapes. Readiness fails when the DB is unreachable, migrations aren't at head, or foreign keys are off (LOG-005). |

### 4.7 Leads (LEAD-*, NOTE-*, ACT-*)

> Traces: ACT-001, ACT-002, ACT-003, ACT-004, LEAD-001, LEAD-002, LEAD-004, LEAD-005, LEAD-006, LEAD-009, LEAD-010, LEAD-012, LEAD-015, LEAD-018, LEAD-023, NOTE-001, NOTE-002, NOTE-003, NOTE-004

| Test | Checks |
|---|---|
| State machine | Every (from, to) pair: allowed, rejected or needing input (UT) |
| Public intake | Required and optional fields. Unknown fields rejected. Consent context stored. Phone rules (Indian default, international with `+cc`, invalid rejected). CAPTCHA and honeypot paths emit `PUBLIC_INTAKE_BLOCKED`. Duplicate submissions stored and flagged, never dropped. |
| Public response | The **complete** response body equals exactly `{reference, message}`. A property-based test asserts that no lead id, number, status or input echo appears in any public response, including errors (LEAD-025). |
| Email isolation | With the email adapter forced to fail, the lead is still committed, the response is still 201, and the outbox row becomes FAILED (NOTIF-008) |
| Notes and activities | Scope rules, note pinning, system activities immutable, `next_follow_up_on` recomputation |
| Lead numbers | Unique under concurrent creation. Never present in public responses (LEAD-008). |
| Attribution | UTM, landing page and referrer are stored from public intake (LEAD-011) |
| List queries | Search, filters, sort allow-list and pagination per 08 §8.2 (LEAD-013) |
| Soft delete and restore | Delete hides a lead. Restore needs `lead.restore`. (LEAD-016) |
| Quoted amount (P1) | Stored as minor units. Rendered as a decimal string. (LEAD-021) |

### 4.8 UI (UI-*)

> Traces: AUDIT-008, LEAD-003, LEAD-007, LEAD-014, LEAD-024, UI-001, UI-002, UI-003, UI-004, UI-005, UI-006, UI-007, UI-008, UI-009, UI-010, UI-011, UI-015

| Test | Checks |
|---|---|
| E2E journeys | Login with MFA · enrollment · forgot and reset password · dashboard widgets · lead create and enrich · status change · assignment · user invite · role edit · permission catalog view · effective-permission explain · MFA reset · audit and security-event viewing |
| Permission-aware UI | Controls hidden or disabled per the effective permission map. Route guards show the no-access page (UI-013). |
| Performance budget | Bundle size and LCP budget checks (NFR-004, P1) |
| Accessibility | axe-core on every screen, **including the public form's error and success states** (LEAD-026). Keyboard-only journeys for login, MFA and lead create. |
| Tokens | Design-system lint rejects raw hex. An automated contrast check over the token table (UI-014). |
| Responsive | Lead screens at 360 px (UI-012) |
| Fallback | Website form with the API blocked opens the WhatsApp hand-off (LEAD-019) |

### 4.9 Operational verification (OPS-*, SEC-*, LOG-*)

> Traces: LOG-006, OPS-002, PLAT-003, SEC-001, SEC-008, SEVT-009, SEVT-010

| Drill / job | Checks |
|---|---|
| Restore verification (automated) | Restore, integrity check, row-count comparison, alert on failure (OPS-009) |
| Rebuild rehearsal | Measured RPO and RTO reported for owner approval (OPS-005) |
| Single-instance guard | The deployment config is checked to have exactly one app instance (OPS-006) |
| Volume check | The database path is on the dedicated encrypted volume, not the container layer (OPS-007) |
| Alert test-fire | Every alert in 02 §9 and 05 §9.8 fires once in staging |
| Header scan | Security headers and CSP on API and app (SEC-003) |
| Load test | NFR-001 at fixture sizes (ASM-007). NFR-003 public intake latency. Chain-append latency (ASM-004). |
| Availability | Uptime computed from external health probes against the owner-approved target (NFR-002) |
| Logging | Log lines are valid JSON with the documented fields. A masking test finds no phone, email, token or password values (LOG-001, LOG-003). |
| Error tracking | A forced exception in staging appears in the error tracker with PII scrubbed (LOG-004) |
| CORS and origin | Only allow-listed origins receive CORS headers. The origin rejects non-Cloudflare traffic (SEC-002, SEC-006). |
| Rate limits | Edge and application limits return 429 with `Retry-After` on auth and public endpoints (SEC-011) |
| Migration rehearsal | The PostgreSQL copy-and-verify runbook (11 §3.4) is executed on staging (OPS-004) |
| Bootstrap drill | `bootstrap-founder` refuses a second Founder and issues a one-hour invite. There are no default credentials (AUTH-014). |

### 4.10 Notifications and outbox (NOTIF-*)

| Test | Checks |
|---|---|
| Outbox atomicity | Events are written in the business transaction. A rollback leaves no event (NOTIF-003). |
| Retry and dead-letter | Forced handler failures follow the backoff schedule, move to DEAD after the maximum attempts, and fire an alert (NOTIF-004) |
| Idempotent handlers | Reprocessing an event creates no duplicate notification (unique `source_event_id` + recipient) |
| In-app inbox | Unread count, mark-read, OWN scope only (NOTIF-001) |
| Lead notifications | `lead.created` and `lead.assigned` reach permission-resolved recipients in-app and by email (LEAD-020) |
| Email adapter | The capture adapter records the rendered subject, HTML and text in test. Templates render with escaping and a plain-text alternative (NOTIF-002, NOTIF-005, NOTIF-009). |
| Recipient resolution | Recipients are resolved by permission holders, never by role names |

### 4.11 User administration and platform conformance (USER-*, PLAT-*)

> Traces: AUTH-011, SEC-005, USER-002, USER-003, USER-005

| Test / check | Checks |
|---|---|
| User lifecycle | Invite → accept → disable → enable → soft delete → restore. Case-insensitive unique email. System users can't log in or be disabled (USER-001…005, EXC-008). |
| MFA administration view | MFA status, required-by sources and reset action gating (USER-006) |
| Self profile | Own profile read and update. The email change path is admin-only (USER-004). |
| Deactivation effects | Disabling or deleting a user revokes all sessions and invalidates tokens and challenges (AUTH-017) |
| Module boundaries | Import-lint forbids a module importing another module's models or repositories (PLAT-011) |
| Migration-only DDL | Review checklist + CI check that models and the migrated schema are in sync (PLAT-005) |
| Secrets | Secret scanning (gitleaks-style) in CI. No secrets in the repository (PLAT-008). |
| Scope boundary | Review checklist: no roadmap-module tables or endpoints in P0 migrations (PLAT-012) |
| Lookups and sequences | Lookup CRUD and deactivation. Sequence allocation under concurrent creates is unique (PLAT-009, PLAT-010). |
| Time handling | UTC storage and timezone display conversion (PLAT-007) |

## 5. CI gates

> Traces: OPS-001, PLAT-004, SEC-007

```
PR:   lint (incl. role-literal + unsafeHTML + raw-hex rules) · type checks · SL[SQLite] · SL[PostgreSQL]
      · UT · IT[SQLite] · IT[PostgreSQL] · OpenAPI diff · dependency + image scan · E2E smoke + axe
main: build → staging deploy → E2E full → OP checks (headers, alerts) → manual approval → production
```

A PR that adds a table, endpoint, permission or event type must add the corresponding tests. The conformance check, route-permission startup check and event allow-list enforce this mechanically.

## 6. Coverage reporting

- Test results are aggregated by requirement ID into a per-release coverage report in the format of the coverage gate (`coverage-gate.md`).
- A P0 requirement without a passing verification blocks release.
