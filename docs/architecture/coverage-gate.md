# Coverage Gate — P0 Foundation Architecture

Generated 2026-09-29. Source: [requirements.json](requirements.json), [validation-report.json](validation-report.json).

## Verdict

**READY FOR INDEPENDENT ARCHITECTURE REVIEW**

There are no architecture blockers. The owner inputs listed below are **go-live preconditions**, not review blockers.

## Totals

| Metric | Value |
|---|---|
| Total requirements | 203 |
| P0 (in scope) | 186 |
| P1 (deferred) | 14 |
| P2 (deferred) | 3 |

## Coverage by dimension

A dimension applies to a requirement only where the registry gives a reference. **Covered** means the reference resolves and the section explicitly cites the ID. **Natively cited** is how many were already cited in prose before trace annotations were added.

| Dimension | Applicable | Covered | Coverage | Natively cited |
|---|---|---|---|---|
| Architecture | 203 | 203 | 100.0% | 145 |
| Schema | 79 | 79 | 100.0% | 27 |
| API | 75 | 75 | 100.0% | 16 |
| UI | 53 | 53 | 100.0% | 22 |
| Security | 61 | 61 | 100.0% | 40 |
| Test strategy | 199 | 199 | 100.0% | 95 |

## Uncovered P0 requirements

None.

## Deferred requirements (designed, not in P0)

| ID | Priority | Requirement | Gaps |
|---|---|---|---|
| AUDIT-007 | P1 | Bulk exports are audited (who, when, filter, row count). | — |
| AUDIT-009 | P1 | Configurable audit retention with verified archival. | — |
| AUDIT-011 | P1 | Personal-data anonymization of audit payloads only via an audited procedure. | — |
| AUDIT-013 | P2 | Tamper-evidence hash chain over audit_log. | — |
| AUTH-016 | P1 | Users list and revoke their sessions; admins revoke any user's sessions. | — |
| SEVT-007 | P1 | The daily chain head is anchored in S3 Object Lock. | — |
| RBAC-007 | P1 | Role and permission assignments can be time-bound. | — |
| RBAC-016 | P1 | An effective-permissions view explains every permission's source. | — |
| LEAD-017 | P1 | Leads can be exported to CSV (permission-gated, audited). | — |
| LEAD-021 | P1 | Quoted amount is recorded in minor units. | — |
| LEAD-022 | P2 | Auto-assignment (round robin). | test (no verification designed) |
| NOTE-003 | P1 | Notes can be pinned. | — |
| ACT-005 | P1 | Call and WhatsApp buttons prompt a prefilled activity quick-log. | test (no verification designed) |
| NOTIF-006 | P1 | Follow-up reminders and daily digest. | test (no verification designed) |
| NOTIF-007 | P2 | WhatsApp Business API notifications. | test (no verification designed) |
| SEC-010 | P1 | Target OWASP ASVS v4 Level 2. | — |
| NFR-004 | P1 | Initial JS below 200 KB gzipped and LCP below 2.5 s on 4G. | — |

## Assumptions (11 §10)

| ID | Assumption |
|---|---|
| ASM-001 | The staff user base during P0 is small (tens of people), within a single-instance deployment's capacity |
| ASM-002 | P0 write concurrency is within SQLite's single-writer capacity |
| ASM-003 | Table growth classes in 03 §11 are qualitative guesses |
| ASM-004 | Security-event volumes are unknown. Alert, lockout and rate-limit thresholds are initial configuration values. |
| ASM-005 | The website's existing "Property Type" field is not sent to the public API, because ADR-005 enumerates the public fields. Staff capture property type during enrichment. |
| ASM-006 | Retention defaults: audit 2 y online / 8 y total · security events 1 y / 2 y · closed-lead anonymization 3 y |
| ASM-007 | NFR-001 load-test fixture sizes (100k leads, 1M audit rows) are test fixtures, not forecasts |
| ASM-008 | Cloudflare stays in front of `api.vedaspaces.com` (proxied) |
| ASM-009 | SES production access will be granted. Until then, the capture adapter means no outbound email outside production. |
| ASM-010 | A host with at least 2 GB RAM is sufficient for Argon2id parameters |
| ASM-011 | The website will publish a versioned privacy notice whose version id is sent as `consent.policy_version` |
| ASM-012 | The AWS region is ap-south-1 (Mumbai). ADR-008 fixes AWS but not the region. |

## Exceptions

### Audit-contract behavioral exceptions (03 §2.9)

| ID | Tables | Exception |
|---|---|---|
| EXC-001 | `audit_log`, `security_event_log` | Rows are immutable: never updated or soft-deleted. `updated_on = created_on`, `updated_by = created_by`, `version = 1`, `is_deleted = false` for life. |
| EXC-002 | `audit_log`, `security_event_log` | Hard-deleted by the retention job after archival |
| EXC-003 | `refresh_token`, `mfa_challenge` | Hard-deleted by purge after expiry, never soft-deleted |
| EXC-004 | `outbox_event` | DONE rows hard-deleted after the configured retention |
| EXC-005 | `notification` | Hard-deleted after the configured retention once read |
| EXC-006 | `user_session`, `password_reset_token`, `user_mfa_recovery_code` | Never soft-deleted. The lifecycle uses `revoked_on`, `used_on` and `invalidated_on`. |
| EXC-007 | Token-hash and chain columns (`refresh_token.token_hash`, `password_reset_token.token_hash`, `mfa_challenge.token_hash`, `user_mfa_recovery_code.code_hash`, `security_event_log.chain_seq`) | Unique index **without** the `is_deleted` predicate |
| EXC-008 | `app_user` rows SYSTEM, WEB_INTAKE, ANONYMOUS | Cannot be soft-deleted, disabled or given credentials |

### Endpoints not gated by a permission code (06 §11)

| ID | Endpoints |
|---|---|
| RBX-001 | `POST /auth/login`, `POST /auth/mfa/verify`, `POST /auth/mfa/enroll/*` (with `mfa_token`) |
| RBX-002 | `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all` |
| RBX-003 | `POST /auth/password/forgot`, `POST /auth/password/reset`, `POST /auth/invite/accept` |
| RBX-004 | `POST /auth/password/change`, `POST /auth/mfa/step-up`, `POST /auth/mfa/recovery-codes`, `DELETE /auth/mfa/factor` |
| RBX-005 | `POST /public/leads` |
| RBX-006 | `GET /health/*`, `GET /auth/.well-known/jwks.json` |

## Owner inputs (go-live preconditions, 11 §7)

| ID | Input |
|---|---|
| OWNER-INPUT-001 | Approved RPO, RTO and API availability target |
| OWNER-INPUT-002 | Confirmation of retention durations (audit, security events, closed-lead anonymization) |
| OWNER-INPUT-003 | Restore-rehearsal cadence |

## Validation checks

14 of 14 passed. Details: [validation-report.md](validation-report.md).

## Unresolved blockers

None.

