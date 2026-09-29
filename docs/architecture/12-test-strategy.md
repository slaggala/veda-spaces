# 12 — Test Strategy

Governing decisions: all ADRs. This document defines **how** each requirement's verification is carried out. It is design only: no tests are implemented by this architecture.

## 1. Principles

1. Every P0 requirement has a verification design. A requirement is **Done** only when that verification passes (01 §1).
2. Tests carry requirement IDs in their name or marker (`test_MFA_013_recovery_requires_password_and_code`), so results roll up per ID.
3. Security behavior is tested **negatively** (what must be denied) as well as positively.
4. Database-dependent suites run on **both** SQLite and PostgreSQL (OPS-001).
5. **Honest reporting (F-19, F-21).** The coverage gate distinguishes two kinds of verification:
   - **automated test designs**: UT, IT, E2E and SL, each with a concrete row in §4;
   - **review or operational verification**: RV checklists and OP drills.

   A requirement verified only by RV or OP is never reported as "tested".

## 2. Verification methods

| Code | Method | Tooling (implementation phase) | Runs |
|---|---|---|---|
| UT | Unit test | pytest · Web Test Runner (Lit) | Every PR |
| IT | Integration/API test through HTTP against a real database | pytest + Flask test client, parametrized over SQLite and PostgreSQL | Every PR |
| E2E | Browser end-to-end with axe-core | Playwright, using the browser and device matrix in §4.8 | PR (smoke), nightly (full) |
| SL | Schema conformance check on a freshly migrated database | Introspection job, both engines | Every PR |
| RV | Review checklist item. **Not a test.** | PR template and reviewer sign-off | Per change |
| OP | Operational drill or scheduled verification in a deployed environment. **Not a unit or integration test.** | Runbooks, scheduled jobs, alert test-fires | Staging before go-live, then on schedule |

**RV checklist items.** These requirements are verified by review, and are listed as such in the coverage gate:

- PLAT-001, PLAT-002: stack and hosting conformance
- PLAT-006: requirement-ID referencing
- MFA-008: excluded MFA methods absent
- SEC-009: DPDP obligations
- SEC-010: ASVS L2 (P1)
- OPS-003: environments
- OPS-008: PostgreSQL gate enforced before gated modules
- SEC-005: secrets in managed stores

## 3. Environments and data

| Environment | Database | Data | Used for |
|---|---|---|---|
| CI | Ephemeral SQLite + PostgreSQL service container | Generated fixtures | UT, IT, SL, E2E |
| Staging | SQLite on an encrypted volume (+ PostgreSQL for rehearsals) | Synthetic/anonymized | E2E full, OP drills, load, DAST |
| Production | SQLite | Real | OP verification jobs only |

## 4. Suites

### 4.1 Schema, migrations and purge (DATA-*, PLAT-013, OPS-004)

| Test | Checks | Type |
|---|---|---|
| Conformance | 03 §2.7 rules 1–9 on both engines. **Negative fixtures** that must fail: a missing `version`; an INTEGER primary key; a `user` table; a non-GUID FK; an `*_id` column without a FK outside EXC-009; an unregistered unique index without a predicate; a native ENUM; a REAL money column; an unregistered exception. | SL |
| Exception registry | The allow-listed unique indexes are exactly those in EXC-007, including `ux_lead__public_reference`, `ux_lead__intake_idempotency_key` and `ux_notification__event_recipient` (F-08) | SL |
| Migration order | Identity and RBAC tables precede business tables (RBAC-001). `PRAGMA foreign_keys = 1` on every connection (DATA-010). | SL |
| **Upgrade with data (F-19)** | For each Alembic revision: seed representative data at N-1, run `upgrade`, then assert row counts, constraints and N-1 read/write paths still work (expand-only compatibility, 02 §12.4) | IT |
| **N-1 rollback** | After migrating, run the N-1 application test subset against the migrated schema. It must pass. | IT |
| **Purge ordering (F-07)** | Purge steps 1–6 of 03 §2.10 run with `foreign_keys=ON` on both engines over sessions with rotated refresh-token chains, challenges, notifications referencing outbox rows, and evidence rows referencing sessions. No FK violation. Evidence rows keep their `session_id`. | IT |
| Time handling (PLAT-007) | Offset-less datetimes are rejected. Date filters use the user's timezone (half-open UTC). DATE columns are not shifted. Display formatting uses the user's zone, not the device's. | UT, IT |

### 4.2 Audit capture (AUDIT-*, DATA-015)

- Every FULL entity: CREATE, UPDATE, soft DELETE, RESTORE and ANONYMIZE produce the expected rows, with redaction applied (`password_hash`, `secret_ciphertext`, `wrapped_data_key`).
- A forced exception after flush leaves no business row, no audit row and no outbox row (atomicity).
- A write without ActorContext fails (AUDIT-010).
- UPDATE and DELETE on `audit_log` are rejected by the database on both engines. `/health/ready` fails if the triggers are missing (A-02).
- Default queries exclude soft-deleted rows. `include_deleted` requires restore permission (DATA-008).
- Parent linkage for children (AUDIT-006).
- **Anonymization (AUDIT-011, LEAD-028, LEAD-029).** After the procedure, no `pii_fields` value of the lead or its children remains in `audit_log` (property-based search). The ANONYMIZE row is present. It runs only from the maintenance process.
- Audit viewer PII masking for out-of-scope leads (A-12).
- Export writes an EXPORT row (AUDIT-007, P1). Archival (AUDIT-009, P1). Audit chain (AUDIT-013, P2).

### 4.3 Security event log (SEVT-*, AUTH-013, MFA-006)

| Test | Checks |
|---|---|
| Catalog | Every event type in 05 §9.1 is emitted by its flow, including the recovery, approval, email-change, break-glass and `PERMISSION_SUSPENDED` events |
| Prohibited content | A scan of all event fixtures finds no token-, hash- or code-shaped values and no prohibited field names (SEVT-003) |
| Allow-list | Unknown `detail` keys are rejected |
| Failure persistence | Failure and denial events survive request rollback (SEVT-011) |
| **Keyed chain (F-11)** | Appends verify. A tampered row or gap is detected. **Recomputing with a wrong key fails.** JCS canonical bytes are identical for the same logical row read from SQLite and from PostgreSQL (cross-engine fixture). |
| External anchor | The daily anchor is written through the write-only role. Verification starts from the latest anchor. The application role cannot delete anchors (SEVT-007). |
| Access (Decision 1) | Founder and Admin with an MFA-verified session: 200. Admin without an MFA-verified session: 403 (suspended). **Standard Sales: 403 on the list, on `?subject_user_id=self`, and on detail of their own event.** Hash and chain columns are never returned (SEVT-005). |
| Sensitive reads (F-06) | Reading audit and security logs writes a `SENSITIVE_READ`, de-duplicated within 15 minutes |
| Retention | Archival exports, verifies and anchors, then deletes. The job refuses to run without configured retention values (SEVT-004). |
| Query paths | Indexed plans for every filter, on both engines. Cursor stability (SEVT-008). |

### 4.4 Authorization and account control (RBAC-*, USER-*, owner Decisions 1 and 3)

| Test | Checks |
|---|---|
| Matrix | Every (role, permission, scope) × endpoint → allow or deny |
| **Sensitivity registry** | Rules 1–4 of 06 §3.1. `is_sensitive` matches `sensitivity_class`. **Seeded SALES holds no sensitive permission.** The migration assertion fails if it does. (RBAC-018) |
| **Sensitive activation (MFA-012)** | A sensitive grant to a user without MFA → 403 `MFA_REQUIRED` and `pending_mfa` in `/auth/me`. After enrollment and an MFA-verified login → effective. MFA reset or factor removal → suspended on the **next request**. Cooling-off suspends ACCOUNT_CONTROL and ACCESS_CONTROL. |
| **Propagation (Decision 1.5)** | A role or grant change, deactivation or session revocation takes effect on the very next request, with no cache window (RBAC-013, AUTH-006, AUTH-017) |
| **Mass assignment (F-03)** | `PATCH /users/{id}` and `PATCH /auth/me` with each of `email`, `proposed_email`, `password`, `status`, `roles`, `permissions`, `mfa_required`, `protection_level`, `is_founder` → 422 `FIELD_NOT_UPDATABLE`. An unknown field → 422 `UNKNOWN_FIELD`. |
| **Email change (USER-007)** | See §4.5 |
| **Guards G1–G12** | Positive and negative for each (06 §7.1). Specifically: an Admin **cannot** deactivate, delete, email-change, MFA-reset, demote or revoke sessions of the Founder (403). A user cannot deactivate themselves through `/users/{id}/status` (403). Copy-from-role escalation is denied (A-06). The duplicate-resolution target outside scope → 404 (A-07). |
| **Last Founder / last recovery admin (G4)** | Disabling, deleting or demoting the last Founder → 409 `LAST_FOUNDER`. The same for the last recovery administrator → 409 `LAST_ADMINISTRATOR`. **Concurrency:** two concurrent requests disabling the last two recovery administrators, and exactly one succeeds (run on both engines). The nightly invariant job alerts on a seeded violation. |
| **Dual control** | A privileged-target MFA reset or email change → 202 `APPROVAL_REQUIRED`. The same actor cannot approve. The target cannot approve. An ineligible approver (G9) cannot approve. Approval executes atomically. Expiry → EXPIRED. |
| **Founder workflow and break-glass** | With fewer than two eligible Founders → 403 `APPROVER_POOL_INSUFFICIENT`. The break-glass CLI refuses the same IAM principal for request and approval. Execution respects `not_before`. A cancel link cancels. |
| Time-bound grants | Non-null `valid_from` / `valid_until` in P0 → 422 `TIME_BOUND_GRANTS_NOT_ENABLED` (RBAC-007 is P1, F-16) |
| Lint | No role-code literals. Every route has a permission or an RBX entry. |
| User lifecycle | Invite → accept (with MFA enrollment if required) → disable → enable → delete → restore. Case-insensitive unique email and role name (A-04). System users can't log in (USER-001…005). |

### 4.5 Authentication, MFA, recovery and email change (AUTH-*, MFA-*, USER-007)

| Test | Checks |
|---|---|
| Login outcomes | Uniform `INVALID_CREDENTIALS` and timing for unknown, bad, invited and disabled users |
| **Throttling (A-01)** | Failures from network A don't block a login from network B for the same account. The distributed-guessing throttle doesn't block password + TOTP for an MFA-enrolled user. |
| Hashing and policy | Argon2id parameters, rehash, policy codes (AUTH-002, AUTH-003) |
| **Tokens after revocation (F-19)** | After logout, logout-all, admin revoke, disable, password reset and email-change completion, the **existing access token** is rejected on the next request (401 `SESSION_INVALID`) |
| **Refresh grace window (F-10)** | A second presentation within 20 s → access token only, no Set-Cookie, `grace_used_on` set. A third presentation, or any presentation after 20 s → session revoked + `REFRESH_REUSE_DETECTED`. |
| **CSRF (F-19)** | `/auth/refresh` and `/auth/logout` without the `X-Requested-With` header, with a foreign `Origin`, or with a missing `Origin` → 403 `CSRF_REJECTED` |
| MFA policy | Each of the three sources requires MFA. Standard Sales without a source is **not** required (it now passes because Sales holds no sensitive permission). Voluntary enrollment is always challenged afterwards. |
| TOTP | RFC 6238 vectors, drift, replay (`last_used_step`), attempt limits |
| **Enrollment proofs (MFA-014)** | `enroll/start` with only an `mfa_token` from a password login → 401 `ENROLLMENT_PROOF_INVALID`. With only a recovery code → rejected. Each of paths A–D succeeds only with both proofs. Login with MFA required and no factor returns `MFA_ENROLLMENT_EMAIL_SENT` and **no token**. |
| **Recovery (MFA-013)** | Password alone, code alone, wrong password + right code, and right password + used code → uniform 401. Password + valid code → RECOVERY session: other sessions revoked, notification sent to the verified email (never the proposed one), no refresh cookie. RECOVERY session calls to `/users`, `/roles`, `/auth/me/email`, `/auth/password/change`, `/leads` and `/security-events` → 403 `RECOVERY_SESSION_RESTRICTED`. `enroll/confirm` → new factor, **new code batch (old codes rejected)**, FULL session, cooling-off set. During cooling-off, email change, password change, factor removal and code regeneration → 403 `COOLING_OFF`. All recovery events are present. |
| Recovery codes (MFA-005) | CSPRNG length and alphabet. Only HMAC stored (a DB scan finds no plaintext). Single use. Never in logs (log scan). Never returned after issuance (API scan). |
| Step-up and reauth | Protected operations without recent MFA or password → 403 `STEP_UP_REQUIRED` with the right `kind` |
| **Admin MFA reset** | Self → 403. Stronger target → 403. Founder by Admin → 403. Privileged target → approval required. After execution, the enrollment link goes to the **target's verified** email. The admin never receives it. Sessions are revoked. |
| **Email change (USER-007)** | `PATCH` cannot change email. `PUT /auth/me/email` without step-up → 403. With step-up → `proposed_email` stored, **login and password reset still use the old email**, the alert with cancel link goes to the old address, verification goes to the new one. Verify → email replaced, all sessions revoked, old tokens invalidated, both notified. Cancel → proposal cleared. Expired token → 400. Token reuse → 400. Only token hashes are stored. Admin-initiated change for a privileged target → approval. Every stage appears in `audit_log` and `security_event_log`. |
| **KMS blob size (F-13)** | Enrollment with a real KMS `GenerateDataKey` ciphertext (staging) and with a maximum-length ARN stores successfully on both engines |
| Password reset | Doesn't bypass MFA. Revokes sessions. Always targets the verified email. |

### 4.6 API contract (API-*, DATA-013)

- OpenAPI diff guard.
- Envelope and error shapes.
- Malformed, hyphenated, uppercase and non-v7 ids → 422 `INVALID_ID`.
- `If-Match` 428/409.
- **Idempotency (F-04):**
  - same key + same body → original response, **with the Turnstile token already spent**;
  - same key + different body → 422 `IDEMPOTENCY_KEY_REUSED`;
  - the lookup happens before Turnstile (asserted by a mock call count).
- Closed schemas (SEC-004).
- `X-Request-ID` present (LOG-002).
- Health: readiness passes while outbox lag is high (F-12), and fails when the DB is unavailable, foreign keys are off or triggers are missing (LOG-005).

### 4.7 Leads (LEAD-*, NOTE-*, ACT-*, NOTIF-008)

| Test | Checks |
|---|---|
| State machine | All (from, to) pairs. WON and LOST cancel PLANNED activities (LEAD-005). |
| Public intake | Required and optional fields including **`property_type_code`** (Decision 4). Unknown or inactive optional codes → 201 with `intake_unmapped`, never 422 (LEAD-030). Consent context stored. Phone rules. |
| **No silent loss (F-05)** | Honeypot filled → 201 with a real reference and a lead with `spam_status = SUSPECTED`. Responses are identical (bytes differ only in the reference). CAPTCHA failure and 429 → the website offers WhatsApp (E2E). NOT_SPAM releases the lead. |
| Public response | The complete body equals `{reference, message}`. A property-based test asserts no id, number, status or echo in any public response or error (LEAD-025). |
| Email isolation | With the email adapter failing, the lead is committed and the response is 201 (NOTIF-008) |
| Consent withdrawal (LEAD-027) | Planned contact activities cancelled. New contact activity → 422 `CONSENT_WITHDRAWN`. The original consent is retained. |
| Retention job (LEAD-028) | With test configuration: eligible closed leads anonymized, open leads untouched. The job refuses to run in production configuration without an approved period. |
| Erasure (LEAD-029) | Needs `lead.erase` and step-up. Live fields anonymized immediately. Audit status goes PENDING → COMPLETED after the maintenance job. `ERASURE_BLOCKED` path. |
| Notes and activities | Scope rules. On a soft-deleted lead → 404. **No note restore endpoint exists** (F-20). |
| Other | Lead numbers unique and never public (LEAD-008). Attribution (LEAD-011). List filters, including `spam_status` (LEAD-013). Soft delete and restore (LEAD-016). Quoted amount in minor units (LEAD-021, P1). Search via casefolded `search_text` returns the same results on both engines for non-ASCII names (A-03). |

### 4.8 UI and accessibility (UI-*, AX-01…AX-10)

| Test | Checks |
|---|---|
| E2E journeys | Login with MFA · recovery · enrollment via emailed link · forgot/reset · email change (self and admin) · approvals · dashboard · lead create and enrich · status change · assignment · spam review · consent withdrawal · user invite · role edit · permission catalog · explain view · audit and security-event viewing as Admin |
| **Browser and device matrix (F-19)** | Chromium, Firefox and WebKit (desktop, latest two versions) · Android Chrome at 360×800 · iOS Safari (WebKit) at 390×844. The public form runs on all of them. |
| **Accessibility (09 §5)** | AX-01 keyboard journeys · AX-02 focus visibility · AX-03 error announcements (focus on summary, `aria-*` assertions) · AX-04 labels · AX-05 **token-pair contrast in light and dark themes, which fails the build below threshold (F-14)** · AX-06 mobile widths, targets and 200% zoom · AX-07 login/MFA · AX-08 public form states (idle, error, success, fallback) · AX-09 admin lead workflow keyboard alternative to drag · AX-10 reduced motion |
| Permission-aware UI | Hidden or disabled controls. "Pending MFA" badges. **The Sales profile shows no security-event panel and makes no security-events request (Decision 1).** |
| Recovery shell | A RECOVERY session renders only the setup and sign-out actions |
| `?next=` (A-08) | Only `^/(?![/\\])` paths are honored. `//evil.com`, `/\evil.com` and absolute URLs are ignored. |
| Performance | Bundle and LCP budget (NFR-004, P1) |

### 4.9 Operational verification (OPS-*, SEC-*, LOG-*, NFR-*)

| Drill / job | Checks | Type |
|---|---|---|
| Restore verification | Scheduled restore, integrity check, row counts, alert (OPS-009) | OP |
| Rebuild rehearsal | Measured RPO/RTO reported for approval (OPS-005, **not testable until OWNER-INPUT-001**) | OP |
| Single process and instance | Deployment config has exactly one instance, one gunicorn worker and one Litestream process (OPS-006, OPS-010, RG-3) | OP + CI config check |
| Volume | The DB path is on the dedicated KMS volume with `DeleteOnTermination=false` (OPS-007, RG-6) | OP |
| Alert test-fire | Every alert in 02 §9 and 05 §9.8, including chain-broken and invariant failure (RG-5) | OP |
| Header, CORS and origin scan | SEC-001…003, SEC-006 | OP |
| **Load and contention (F-19)** | NFR-001 / NFR-003 at ASM-007 fixture sizes. **SQLite contention:** concurrent writers under `BEGIN IMMEDIATE` produce no `SQLITE_BUSY` surfaced to clients at target concurrency (the busy_timeout path is exercised and measured). Chain-append latency. (RG-4) | IT (load) |
| **DAST / penetration test (F-19)** | OWASP ZAP baseline plus an authenticated scan on staging, and a manual penetration test of the auth, MFA-recovery, account-control and public-intake surfaces **before production** (production gate PG-DAST) | OP |
| Migration runbook rehearsal | 02 §12.4, including both rollback paths (RG-7, OPS-004) | OP |
| Bootstrap drill | AUTH-014 | OP |
| Logging | JSON shape, masking scan (LOG-001, LOG-003). Error tracking (LOG-004). | UT, OP |
| Availability | Measured against the owner target (NFR-002, **not testable until OWNER-INPUT-001**) | OP |

### 4.10 Notifications and outbox (NOTIF-*, LEAD-020)

- Outbox atomicity, retry and backoff, DEAD and alert, idempotent handlers.
- In-app inbox with OWN scope.
- Capture adapter records emails (NOTIF-009).
- Templates are escaped with a plain-text alternative (NOTIF-005, RV).
- Recipients are resolved by permission.
- `lead.created` and `lead.assigned` recipients (LEAD-020).
- **Security notifications go to the verified email only.** The proposed address receives only its verification link.

### 4.11 Platform conformance (PLAT-*)

Checks:

- import-lint for module boundaries (PLAT-011);
- models match the migrated schema (PLAT-005);
- secret scanning (PLAT-008);
- scope-boundary review, with no roadmap objects (PLAT-012);
- lookup CRUD and sequence allocation under concurrency (PLAT-009, PLAT-010);
- time handling (PLAT-007, §4.1).

## 5. CI gates

```
PR:   lint (role literals, unsafeHTML, raw hex, import boundaries) · types · SL[SQLite] · SL[PostgreSQL]
      · migration upgrade-with-data + N-1 test · UT · IT[SQLite] · IT[PostgreSQL] · OpenAPI diff
      · dependency + image scan · secret scan · token contrast (light + dark) · E2E smoke + axe
main: build → staging → E2E full (browser matrix) → OP checks → manual approval → production
Pre-production (once): DAST + penetration test (PG-DAST), load/contention (RG-4), restore + rebuild rehearsal (RG-1, RG-2, RG-7)
```

## 6. Coverage reporting

Results are aggregated by requirement ID into the coverage gate format (`coverage-gate.md`), which reports automated tests separately from RV/OP verification and from owner-gated items. A P0 requirement without a passing verification blocks release.
