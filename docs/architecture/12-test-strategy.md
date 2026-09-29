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
| Conformance | 03 §2.7 rules 1–9 on both engines. **Negative fixtures** that must fail: a missing `version`; an INTEGER primary key; a `user` table; a non-GUID FK; an unregistered unique index without a predicate; a native ENUM; a REAL money column; an unregistered exception. The FK-less identifier cases are in TD-H (§4.12). | SL |
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
| **Founder workflow and break-glass** | Covered by the concrete test design TD-G (§4.12): canonical eligibility, single-Founder mode, custodian distinctness, `not_before` and the cancel link |
| Time-bound grants | Non-null `valid_from` / `valid_until` in P0 → 422 `TIME_BOUND_GRANTS_NOT_ENABLED` (RBAC-007 is P1, F-16) |
| **Resolution (restored)** | DENY-over-GRANT, broadest scope wins, next-request propagation: concrete design **TD-A** (§4.12) |
| **Founder governance** | Concrete negative suite **TD-G** (§4.12) |
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
| **Recovery edge cases** | Expired RECOVERY session **TD-C**, challenge-token reuse after recovery **TD-D**, failed re-enrollment **TD-E** (§4.12) |
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
- `If-Match` 428/409, plus the two-writer conflict scenario on both engines: **TD-F** (§4.12).
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
| **Duplicate detection and retry (restored)** | Concrete design **TD-B** (§4.12): 180-day match flagged, never dropped, never disclosed, idempotent retry with a spent CAPTCHA token, email failure keeps the lead |
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

### 4.12 Concrete test designs for the remaining review conditions (N-01, N-02, N-03)

Each design below is concrete. It states preconditions, fixtures, action, expected result, events, negative assertions, cleanup and evidence. Designs run on both SQLite and PostgreSQL unless stated. "Evidence" means the CI artifact attached to the requirement IDs in the coverage report (§6).

#### TD-A. DENY-over-GRANT resolution and propagation (RBAC-006, RBAC-013, RBAC-005)

| Field | Design |
|---|---|
| Purpose | Prove an explicit DENY overrides every source of GRANT, and that the change is visible on the very next request |
| Preconditions | Seeded roles. User **U** (ACTIVE, SALES role, `lead.read` = OWN via role). Admin **A** with `user.permission.manage` equivalents: a Founder fixture with an MFA-verified session and step-up. |
| Fixtures | Leads L1 (assigned to U) and L2 (assigned to another user). A custom role **R_ALL** with `lead.read` = ALL. |
| Action | 1. Grant U direct `lead.read` = ALL. 2. Assign R_ALL to U. 3. U lists leads: sees L1 and L2 (broadest scope wins). 4. Add DENY `lead.read` for U. 5. **Within the same second**, U reuses the same access token for `GET /leads` and `GET /leads/{L1}`. 6. Remove the DENY. 7. U repeats. |
| Expected | Step 3: 200 with L1 and L2. Step 5: `403 PERMISSION_DENIED` on both (DENY beats role GRANT, direct GRANT and OWN-scoped role GRANT). `X-Authz-Version` has incremented. Step 7: 200 with L1 and L2 again. |
| Events | `audit_log` CREATE and DELETE (soft) rows for the `user_permission` rows. `PERMISSION_DENIED` security event (de-duplicated per minute). `SENSITIVE_ACTION` for the `user.permission.manage` uses. |
| Negative assertion | No request after the DENY commit returns any lead. The effective-permissions endpoint shows `lead.read` `status = DENIED` with sources listing both GRANTs and the DENY. A unit test over the resolver table covers all 3 × 3 combinations of {role GRANT, direct GRANT, none} × {DENY, no DENY} × {OWN, ALL}. |
| Cleanup | Per-test transaction rollback on the test database, and fixture users deleted by teardown |
| Evidence | Pytest report `test_RBAC_006_deny_over_grant[sqlite|postgresql]` and resolver-table unit results |

#### TD-B. Public intake retry, duplicate detection and non-disclosure (LEAD-010, LEAD-018, LEAD-025, API-007, NOTIF-008)

| Field | Design |
|---|---|
| Purpose | Prove enquiries are never lost or silently merged, and that responses reveal nothing about existing leads |
| Preconditions | Turnstile verification mocked (counting calls). The email adapter can be forced to fail. An existing lead **E** with phone `+919876543210`, created 30 days ago. |
| Fixtures | Body B1 (same phone as E, message "kitchen"), body B2 (same phone, message "wardrobes"), keys K1 and K2 |
| Action | 1. POST B1 with K1 → capture the response. 2. Repeat B1 with K1 and the **same, already-spent** Turnstile token. 3. POST B2 with K1. 4. POST B2 with K2 and a fresh token. 5. POST B1-variant with the honeypot filled and key K3. 6. Force email failure, then POST a new phone with K4. |
| Expected | 1: `201 {reference R1, message}`, a new lead N1 with `duplicate_status = SUSPECTED` and `duplicate_of_lead_id = E`. 2: `201` byte-identical to step 1; the Turnstile mock is **not** called; no new lead. 3: `422 IDEMPOTENCY_KEY_REUSED`, no new lead. 4: `201` with a **different** reference R2 and a new lead N2 (also SUSPECTED), so it is not discarded. 5: `201` with a real reference; the lead is stored with `spam_status = SUSPECTED`. 6: `201`, the lead is committed, and the outbox row becomes FAILED. |
| Events | `audit_log` CREATE per stored lead (actor WEB_INTAKE). `PUBLIC_INTAKE_QUARANTINED` for step 5. Outbox FAILED for step 6. No `PUBLIC_INTAKE_BLOCKED` for steps 1–6. |
| Negative assertion | Response bodies for steps 1, 4 and 5 have identical key sets `{reference, message}` and contain no id, lead number, status or duplicate or spam indicator. Response timing distribution is not a reviewed channel; it is tracked as advisory only. Lead count increases by exactly 4 (N1, N2, spam, step-6 lead). Nothing is ever deleted. |
| Cleanup | Test-database rollback. Outbox and notification rows truncated by fixture teardown. |
| Evidence | `test_LEAD_010_duplicate_and_retry_matrix` report with captured response bodies (hashed) and the Turnstile mock call count |

#### TD-C. Expired RECOVERY session (MFA-013, MFA-014)

| Field | Design |
|---|---|
| Purpose | Prove an expired recovery session grants nothing and doesn't restore the consumed code |
| Preconditions | User U with an ACTIVE factor and 10 recovery codes (batch B). A controllable clock. |
| Fixtures | Recovery code C1 from batch B |
| Action | 1. Login → `mfa_token`. 2. `/auth/mfa/recovery` with the password and C1 → RECOVERY token T. 3. Advance the clock 15 min + 1 s. 4. With T call `enroll/start`, `enroll/confirm`, `GET /auth/me`, `GET /leads`, `PUT /auth/me/email`. 5. Start again: login, then `/auth/mfa/recovery` with C1 again. 6. Recovery with a different unused code C2. |
| Expected | 4: every call → `401 SESSION_INVALID`, and any PENDING factor is REVOKED (`ENROLLMENT_ABANDONED`). 5: `401 MFA_RECOVERY_INVALID` (C1 is still consumed). 6: succeeds with a new RECOVERY session. |
| Events | `MFA_RECOVERY_SESSION_EXPIRED` (once per call, de-duplicated per minute). `MFA_RECOVERY_FAILED` for step 5. `MFA_RECOVERY_CODE_CONSUMED` only for C1 (step 2) and C2 (step 6). |
| Negative assertion | No FULL session, refresh cookie or cooling-off value exists after step 4. `user_mfa_recovery_code` for C1 keeps its `used_on`. The old factor is still ACTIVE. Event rows contain no code, token or hash (prohibited-content scan). |
| Cleanup | Reset the clock. Rollback. |
| Evidence | `test_MFA_013_expired_recovery_session` report plus the event-row scan output |

#### TD-D. Login challenge-token reuse after recovery (MFA-013, AUTH-006, SEVT-003)

| Field | Design |
|---|---|
| Purpose | Prove recovery completes the login challenge and invalidates all other challenges and sessions |
| Preconditions | User U with an ACTIVE factor. Two existing FULL sessions S1 and S2 (desktop and phone), each holding an access token and a refresh cookie. |
| Fixtures | Recovery code C1 |
| Action | 1. Login twice → `mfa_token` M1 and M2. 2. `/auth/mfa/recovery` with M1, the password and C1 → RECOVERY session. 3. Replay M1 at `/auth/mfa/verify` with a valid TOTP. 4. Present M2 at `/auth/mfa/verify` and at `/auth/mfa/recovery`. 5. Use S1's access token on `GET /auth/me`. Refresh S2's cookie. |
| Expected | 3: `401 MFA_CHALLENGE_INVALID`. 4: `401 MFA_CHALLENGE_INVALID` for both (M2 was invalidated). 5: `401 SESSION_INVALID` and `401 SESSION_INVALID` (both revoked with reason `MFA_RECOVERY`). |
| Events | `MFA_RECOVERY_COMPLETED`, `SESSION_REVOKED` ×2, `MFA_CHALLENGE_REPLAY_BLOCKED` ×3, `TOKEN_REFRESH` FAILURE |
| Negative assertion | No event `detail` or column contains M1, M2, a token hash, the password or C1 (prohibited-content scan). The `mfa_challenge` rows show M1 `completed_on` set and M2 expired. |
| Cleanup | Roll back the test transaction; delete fixture sessions and challenges |
| Evidence | `test_MFA_013_challenge_reuse_after_recovery` report plus the scan output |

#### TD-E. Failed re-enrollment during recovery (MFA-013, MFA-014, MFA-012)

| Field | Design |
|---|---|
| Purpose | Prove incomplete enrollment commits nothing that grants access, and retry stays within policy |
| Preconditions | User U, a Founder fixture holding sensitive permissions, with an ACTIVE factor F0 and batch B. Other sessions exist. |
| Fixtures | Recovery code C1. A mock that forces a DB error on the confirm transaction. |
| Action | 1. Recovery → RECOVERY session. 2. `enroll/start` → PENDING F1. 3. `enroll/confirm` with a wrong code 5 times. 4. `enroll/start` again → PENDING F2 (F1 now REVOKED). 5. `enroll/confirm` with the correct code while the forced DB error fires. 6. Retry the confirm with the correct code, no error. |
| Expected | After 3: F1 REVOKED (`ENROLLMENT_ABANDONED`), F0 still ACTIVE, still in the RECOVERY session, no FULL session. After 5: rolled back, so F2 is still PENDING, F0 ACTIVE, batch B unchanged, no cooling-off, `authz_version` unchanged. After 6: F2 ACTIVE, F0 REPLACED, new batch, B invalidated, FULL session issued, cooling-off set, other sessions still revoked. |
| Events | `MFA_CHALLENGE` FAILURE ×5 (own transactions), `MFA_ENROLLMENT_STARTED` ×2, `MFA_AUTHENTICATOR_RE_ENROLLED` only after step 6 |
| Negative assertion | Between steps 1 and 6 no sensitive permission is effective (any sensitive endpoint → 403), and `/auth/me` shows `suspended_permissions`. C1 is never restored. Only one PENDING factor exists at any time. Old sessions S1/S2 never become valid again. |
| Cleanup | Rollback. Remove the DB-error mock. |
| Evidence | `test_MFA_014_failed_reenrollment_atomicity` report plus a factor-state table snapshot per step |

#### TD-F. Optimistic-concurrency conflict (API-006, DATA-006, AUDIT-001, UI-013)

| Field | Design |
|---|---|
| Purpose | Prove a stale writer cannot overwrite, and that audit reflects only committed changes |
| Preconditions | Lead L at version 4. Two authorized actors, X and Y, each holding `lead.update` at ALL. |
| Fixtures | Two HTTP clients, one per actor, with barrier synchronization |
| Action | 1. X and Y both `GET /leads/{L}` (ETag "4"). 2. Barrier. X sends `PATCH {priority: HIGH}` with `If-Match: "4"` and Y sends `PATCH {city: "Pune"}` with `If-Match: "4"` concurrently, on both engines (SQLite `BEGIN IMMEDIATE`; PostgreSQL row versioning). 3. Y re-GETs and retries with `If-Match: "5"`. 4. E2E: a UI session editing L when the other actor saves. |
| Expected | 2: exactly one `200` with version 5, and one `409 VERSION_CONFLICT` whose body has `current_version = 5` and `updated_by` = the winner. 3: `200`, version 6, both changes present. 4: the UI shows the conflict dialog with "Reload theirs" / "Re-apply mine" and no data loss. |
| Events | `audit_log`: exactly one UPDATE row for the winner at v5 and one for the retry at v6. **No** audit row for the rejected write. |
| Negative assertion | The loser's field never appears at version 5. There is no audit or outbox row for the 409. No 500 or `SQLITE_BUSY` reaches the client. |
| Cleanup | Rollback. Reset the barrier. |
| Evidence | `test_API_006_two_writer_conflict[sqlite|postgresql]` plus the Playwright trace for step 4 |

#### TD-G. Founder-governance negative suite (RBAC-021, MFA-015, RBAC-020, N-01)

**Preconditions:**

- Founders **F1** and **F2**: ACTIVE, MFA-verified, step-up fresh.
- Admin **A** with `role.manage`, `user.role.manage` and `user.permission.manage` fixtures: an A variant with `user.permission.manage` is created by a Founder, for the bypass cases.
- Sales **S**. Custodian register: **K1** ↔ F1 (human), **K2** ↔ external person.

**Common assertions for every case:**

- Each blocked case writes the listed event and no `audit_log` mutation of roles, permissions or `app_user`.
- I1–I3 hold after every case.

**Evidence:** `test_RBAC_021_founder_governance_*` reports on both engines. **Cleanup:** rollback per case.

| # | Case | Action | Expected | Event |
|---|---|---|---|---|
| G1 | Self-approval | F1 requests `GRANT_FOUNDER`(S), then F1 approves | `403 APPROVER_NOT_ELIGIBLE`. The request stays PENDING. | `FOUNDER_ACTION_DENIED` not written. A `PERMISSION_DENIED` event is written. |
| G2 | Requester approves the same request through another channel | F1 requests, then the break-glass CLI approval is attempted as K1 (mapped to F1) | CLI refuses (same human) | `BREAK_GLASS_*` FAILURE |
| G3 | Duplicate approvers | F2 approves, then F2 (or any user) approves again | Second attempt: `409 INVALID_STATE`. One `approver_user_id` recorded. | — |
| G4 | Direct FOUNDER-role grant | F1 calls `PUT /users/{S}/roles` adding FOUNDER. Also A. | `403 FOUNDER_GOVERNANCE_REQUIRED` (both) | `FOUNDER_GOVERNANCE_BYPASS_BLOCKED` |
| G5 | Direct `user.founder.manage` grant or deny | `POST /users/{S}/permissions` GRANT, and `POST /users/{F2}/permissions` DENY | `403 FOUNDER_GOVERNANCE_REQUIRED` | Same |
| G6 | Role-definition bypass | `PUT /roles/{SALES}/permissions` adding `user.founder.manage`; `POST /roles` with `copy_from_role_id = FOUNDER`; `PATCH /roles/{FOUNDER}` | `403 FOUNDER_GOVERNANCE_REQUIRED` | Same |
| G7 | Approval after eligibility revoked | F1 requests. F2's MFA is reset (F2 suspended). F2 tries to approve. | `403 APPROVER_NOT_ELIGIBLE` | `FOUNDER_ACTION_*` not executed |
| G8 | Requester loses eligibility | F1 requests, F1 enters cooling-off, F2 approves | Request `CANCELLED` / `REQUESTER_INELIGIBLE` at approval, and nothing executes | `FOUNDER_ACTION_CANCELLED` |
| G9 | Non-Founder approver | A (not a Founder, even with every other permission) approves | `403 APPROVER_NOT_ELIGIBLE` | — |
| G10 | Concurrent Founder changes | Two parallel `founder-actions` for the same target → one 202 and one `409 REQUEST_ALREADY_OPEN`. Two approved `REVOKE_FOUNDER` (F1, F2) executed in parallel with a barrier. | Exactly one EXECUTED and one FAILED (`LAST_FOUNDER`) | `FOUNDER_ACTION_EXECUTED` + `FOUNDER_ACTION_FAILED` |
| G11 | Last-Founder removal | With only F1: `REVOKE_FOUNDER`(F1) and `FOUNDER_STATUS_CHANGE`(F1, DISABLED) | `409 LAST_FOUNDER` at request time | — |
| G12 | Single-Founder mode | With only F1: request `GRANT_FOUNDER`(S) → `channel = BREAK_GLASS`. K1 approval refused (same human as F1). K2 approval accepted. Execution before `not_before` refused, after it succeeds. Cancel link by a notified party → CANCELLED. | As stated | `BREAK_GLASS_*` |
| G13 | Bootstrap misuse | Run `bootstrap-founder` while F1 exists, and again after F1 is soft-deleted (history exists) | Refused both times | — |
| G14 | I3 drift detection | Insert a FOUNDER role row for S directly in the test database, then run the nightly job | CRITICAL `FOUNDER_STATE_INCONSISTENT` alert. S is ineligible as an approver. | Alert event |

#### TD-H. FK-less identifier conformance (DATA-011, DATA-014, DATA-012, N-02)

| Field | Design |
|---|---|
| Purpose | Prove the allow-list is exact and constrained, without relaxing rule 3 |
| Preconditions | A freshly migrated schema on both engines, plus fixture migrations applied one at a time on a scratch database |
| Action / expected | H1: the real schema passes, and all ten registered columns in 03 §2.11 are accepted. H2: add `lead.foo_id GUID` with no FK → **fail** (unregistered ID-like column). H3: change `audit_log.entity_id` to `VARCHAR(64)` → **fail** (wrong type). H4: add a registry row for `notification.bar_id` with the "why no FK" field empty → **fail** (undocumented). H5: drop `ck_audit_log__entity_id_format` → **fail**. H6: drop the pair CHECK on `security_event_log.target_entity_*` → **fail**. H7: insert `audit_log.entity_id = '0192A4F1C3B27E8D9F10A2B3C4D5E6F7'` (uppercase), a v4 UUID, and a hyphenated value → rejected by CHECK or kernel type on each engine. H8: run the purge sequence (03 §2.10) with `foreign_keys=ON` → no FK violation, so F-07 is not reintroduced. |
| Events | None (schema tests) |
| Negative assertion | The conformance tool's allow-list equals the 10 names in 03 §2.11 exactly (set equality) |
| Cleanup | Scratch database dropped |
| Evidence | Conformance-check output per fixture, `test_DATA_011_fkless_allow_list` report |

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
