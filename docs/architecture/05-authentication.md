# 05 — Authentication, MFA and Security-Event Design

Governing decisions: [ADR-004](decisions/ADR-004-security-event-log.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-007](decisions/ADR-007-technology-stack.md)

## 1. Principles

1. **Staff only, invitation only.** There is no self-registration (AUTH-011).
2. **Short-lived bearer token plus a revocable server-side session.** Every JWT carries a `sid` that is checked against `user_session`.
3. **MFA is policy-driven, never role-name-driven** (ADR-006, §11.1).
4. **Enumeration-safe.** No response reveals whether an account exists (AUTH-009).
5. **Everything is recorded** in `security_event_log`. Nothing secret is recorded (ADR-004, §9).

## 2. Password hashing and policy (AUTH-002, AUTH-003)

### 2.1 Algorithm

> Traces: AUTH-002

| Item | Value |
|---|---|
| Algorithm | Argon2id (RFC 9106) |
| Parameters | Memory 64 MiB, iterations 3, parallelism 1. Never below the OWASP minimum (m = 19 MiB, t = 2, p = 1). Final values are set after benchmarking on the target host. |
| Salt | 16 random bytes per hash (inside the PHC string) |
| Storage | `user_credential.password_hash` (PHC string) |
| Rehash | On successful login, if the stored parameters are weaker than the current configuration |
| Concurrency guard | A semaphore of CPU count on concurrent hash operations (11 §1) |

### 2.2 Timing equalization

> Traces: AUTH-009

For unknown emails, the server still verifies against a fixed dummy hash, so response time does not reveal whether the account exists.

### 2.3 Password policy

> Traces: AUTH-003

| Rule | Value |
|---|---|
| Length | 12–128 characters, NFKC-normalized. All Unicode allowed. |
| Composition rules | None |
| Blocklist | Bundled common/breached password list, plus the user's email local part, name, "veda" and "vedaspaces" |
| Breach check | HIBP k-anonymity (only 5 hex characters of the SHA-1 prefix leave the server). P1. |
| Expiry | None. Change is forced only on compromise or by an admin reset. |
| History | Cannot reuse the current password |

## 3. Login (AUTH-001, AUTH-009, MFA-*)

```
Client                                    API
  │ POST /api/v1/auth/login {email,password}
  │───────────────────────────────────────►│ rate limits (IP, email)
  │                                        │ normalize email → load app_user + user_credential
  │                                        │ unknown → dummy verify → FAIL(UNKNOWN_USER)        ┐ security_event LOGIN FAILURE
  │                                        │ user_type≠HUMAN / locked / bad password / INVITED /│ (separate tx; actor ANONYMOUS
  │                                        │ DISABLED → FAIL (after verify, uniform timing)     ┘  or the subject user)
  │                                        │ password OK → evaluate MFA policy (§11.1)
  │                                        │
  │  ┌─ MFA not required and no active factor ──► create user_session + refresh_token; LOGIN SUCCESS
  │  │     200 {status:"AUTHENTICATED", access_token, …}  + Set-Cookie vs_rt
  │  ├─ active factor exists (required or opted-in) ──► mfa_challenge(LOGIN); LOGIN event outcome SUCCESS
  │  │     detail.stage="password"
  │  │     200 {status:"MFA_REQUIRED", mfa_token, methods:["totp","recovery_code"]}
  │  └─ MFA required but no active factor ──► mfa_challenge(ENROLLMENT)
  │        200 {status:"MFA_ENROLLMENT_REQUIRED", mfa_token}
  │
  │ POST /auth/mfa/verify {mfa_token, code | recovery_code}   (§11.4)
  │   → 200 {status:"AUTHENTICATED", access_token, …} + Set-Cookie vs_rt
```

- **Uniform failures.** Every failure returns `401 INVALID_CREDENTIALS`. A locked account is told nothing extra by the API. The account holder instead receives a lockout email.
- **A password alone never yields a session** when an MFA factor is active or required.
- **Must change password.** With `must_change_password`, the access token carries `pwd_change: true`. The API then allows only `/auth/me`, `/auth/password/change` and `/auth/logout` (`403 PASSWORD_CHANGE_REQUIRED` otherwise). MFA is completed before this state is reached.

## 4. Brute-force protection (AUTH-010, SEC-011, MFA-009)

| Layer | Control |
|---|---|
| Cloudflare | Rate rules on `/api/v1/auth/login`, `/api/v1/auth/password/*`, `/api/v1/auth/mfa/*` → managed challenge |
| App, per IP | Failed logins above threshold → 429 for a cool-down |
| App, per account | 5 consecutive password failures within 15 min → `locked_until` (escalating, max 24 h), `ACCOUNT_LOCKED` event, email to the user |
| MFA | 5 wrong codes per challenge voids it. 10 MFA failures per account in 15 min lock the account (`ACCOUNT_LOCKED`, reason `MFA_FAILURES`). |
| Unlock | Timeout, admin (`user.update`), or password reset. A reset does not remove MFA. |

The thresholds above are initial configuration values, not measured tuning. They are reviewed after production telemetry exists (ASM-004).

## 5. Access token: JWT strategy (AUTH-004)

| Item | Value |
|---|---|
| Format | JWS, `typ: at+jwt` |
| Algorithm | ES256. `kid` header. Public keys at `/api/v1/auth/.well-known/jwks.json`. 90-day rotation. |
| Lifetime | 15 minutes. Clock-skew tolerance 30 s. |
| Client storage | Memory only |
| Transport | `Authorization: Bearer` |

**Claims:**

| Claim | Purpose |
|---|---|
| `iss`, `aud` (`veda-workspace`) | Issuer and audience checks |
| `sub` | `app_user.id` (32-hex) |
| `sid` | Session id, for the revocation check |
| `jti` | Token id |
| `iat`, `nbf`, `exp` | Validity window |
| `av` | `authz_version` |
| `amr` | `["pwd"]` or `["pwd","otp"]` (RFC 8176 values) |
| `pwd_change` | Present when set |

- There are no permissions and no PII in the token.
- Per request, the server verifies the signature and claims, checks that the session is active and the user is ACTIVE (cached ≤ 30 s), and loads effective permissions by (`sub`, `authz_version`).

## 6. Refresh token and sessions (AUTH-005, AUTH-006)

| Item | Value |
|---|---|
| Token | Opaque, 256-bit, base64url. Stored only as SHA-256 in `refresh_token.token_hash`. |
| Cookie | `vs_rt`, `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`, host-only on `api.vedaspaces.com` |
| Lifetime | Idle 7 days (sliding) and absolute 30 days, on `user_session` |
| Rotation | Every refresh consumes the token and issues a successor |
| Reuse | Presenting a used token outside the 20 s multi-tab grace window revokes the session (`TOKEN_REUSE`) and raises a `REFRESH_REUSE_DETECTED` event (CRITICAL) plus an email to the user |
| CSRF | Refresh and logout require an allow-listed `Origin` and `X-Requested-With: veda-workspace` |
| Security events | **Every refresh writes a `TOKEN_REFRESH` event** (success or failure) (ADR-004). The event never contains the token or its hash. |

`app.` and `api.vedaspaces.com` are same-site, so `SameSite=Strict` cookies flow on credentialed fetches. Tabs coordinate refresh through the Web Locks API and a `BroadcastChannel`. On a page reload the app silently refreshes.

Refreshing does **not** repeat MFA. The session's `auth_methods` and `mfa_verified_on` carry forward, capped by the session's absolute expiry.

## 7. Logout and session control (AUTH-007, AUTH-016, AUTH-017)

> Traces: AUTH-006

| Operation | Endpoint | Effect | Security event |
|---|---|---|---|
| Logout | `POST /auth/logout` | Revoke current session, clear cookie | `LOGOUT` |
| Logout all | `POST /auth/logout-all` | Revoke all own sessions | `LOGOUT` (detail.scope = all) |
| List / revoke own sessions | `GET /auth/sessions`, `DELETE /auth/sessions/{id}` | — | `SESSION_REVOKED` |
| Admin revoke | `POST /users/{id}/sessions/revoke` (`user.session.revoke`) | Revoke all | `SESSION_REVOKED` + `SENSITIVE_ACTION` |
| User disabled or deleted | User APIs | Revoke all sessions, invalidate tokens and challenges | `SESSION_REVOKED` (reason `USER_DISABLED`) |
| MFA reset | §11.7 | Revoke all sessions | `SESSION_REVOKED` (reason `MFA_RESET`) |

## 8. Password reset and account setup

### 8.1 Forgot password (AUTH-008, AUTH-009)

```
POST /auth/password/forgot {email}  → ALWAYS 202 generic message
  if HUMAN user in {ACTIVE, LOCKED}:
     invalidate open PASSWORD_RESET tokens; create token (256-bit; SHA-256 stored; 30 min)
     outbox auth.password_reset_requested → email link https://app.vedaspaces.com/reset-password#token=…
     security_event PASSWORD_RESET_REQUESTED SUCCESS (subject = user)
  else:
     security_event PASSWORD_RESET_REQUESTED FAILURE (actor ANONYMOUS, email_attempted_hash, reason)
```

The token travels in the URL fragment, so it never reaches server logs or Referer headers.

### 8.2 Reset

```
POST /auth/password/reset {token, new_password}
 1 hash lookup: purpose=PASSWORD_RESET, unused, not invalidated, unexpired  → else 400 RESET_TOKEN_INVALID
 2 policy check (422 does not consume the token)
 3 set hash; clear lockout; used_on=now; revoke ALL sessions (PASSWORD_RESET)
 4 security_event PASSWORD_RESET_COMPLETED; outbox → confirmation email
 5 204 → /login.  MFA is NOT reset or bypassed: the next login still requires the second factor.
```

### 8.3 Admin-initiated reset

`POST /users/{id}/password-reset` (`user.password.reset`) sends the §8.1 email to the target. Admins never see or set passwords. A `SENSITIVE_ACTION` event is written if the permission is sensitive.

### 8.4 Invitation (AUTH-011)

1. `POST /users` creates the user as INVITED with an INVITE token (72 h) and sends the email.
2. `POST /auth/invite/accept {token, new_password}` sets the password and makes the user ACTIVE. Events: `INVITE_SENT`, `INVITE_ACCEPTED`.
3. On first login, MFA enrollment is enforced if policy requires it (§11.3).

### 8.5 Change password (AUTH-012)

This requires the current password (with lockout counting). It revokes the user's other sessions and rotates the current refresh token. Event: `PASSWORD_CHANGED`. A confirmation email is sent.

## 9. Security event log (ADR-004, AUDIT-012, AUTH-013, SEVT-*)

The schema is in [03 §5.4](03-database-schema.md). This log is **separate from `audit_log`**. High-volume authentication telemetry never enters the entity audit log.

### 9.1 Event catalog (SEVT-002)

> Traces: AUTH-013, MFA-006

| event_type | Category | Outcomes | Severity | When |
|---|---|---|---|---|
| `LOGIN` | AUTHENTICATION | SUCCESS / FAILURE | INFO / WARNING | Password step. `detail.stage` = `password` or `complete`. |
| `TOKEN_REFRESH` | SESSION | SUCCESS / FAILURE | INFO / WARNING | Every refresh attempt |
| `REFRESH_REUSE_DETECTED` | SESSION | FAILURE | CRITICAL | Rotated token replayed |
| `LOGOUT` | SESSION | SUCCESS | INFO | Logout / logout-all |
| `SESSION_REVOKED` | SESSION | SUCCESS | INFO / WARNING | Any revocation. `detail.reason`. |
| `PASSWORD_RESET_REQUESTED` | PASSWORD | SUCCESS / FAILURE | INFO | §8.1 |
| `PASSWORD_RESET_COMPLETED` | PASSWORD | SUCCESS / FAILURE | WARNING | §8.2 |
| `PASSWORD_CHANGED` | PASSWORD | SUCCESS / FAILURE | WARNING | §8.5 |
| `INVITE_SENT` / `INVITE_ACCEPTED` | ACCOUNT | SUCCESS / FAILURE | INFO | §8.4 |
| `MFA_ENROLLMENT_STARTED` | MFA | SUCCESS | INFO | §11.3 |
| `MFA_ENROLLMENT_COMPLETED` | MFA | SUCCESS / FAILURE | WARNING | §11.3 |
| `MFA_CHALLENGE` | MFA | SUCCESS / FAILURE | INFO / WARNING | Every code verification (login or step-up). `detail.method` = `totp` or `recovery_code`. |
| `MFA_RECOVERY_CODE_USED` | MFA | SUCCESS | WARNING | Plus an email to the user |
| `MFA_RECOVERY_CODES_REGENERATED` | MFA | SUCCESS | WARNING | §11.5 |
| `MFA_FACTOR_REMOVED` | MFA | SUCCESS | WARNING | Self-removal where policy allows |
| `MFA_RESET` | MFA | SUCCESS / FAILURE | CRITICAL | §11.7 |
| `ACCOUNT_LOCKED` / `ACCOUNT_UNLOCKED` | ACCOUNT | SUCCESS | WARNING | §4 |
| `PERMISSION_DENIED` | AUTHORIZATION | BLOCKED | WARNING | 403 responses. De-duplicated per (user, code, minute). |
| `SENSITIVE_ACTION` | AUTHORIZATION | SUCCESS / FAILURE | WARNING | Any use of a permission with `is_sensitive = true` (06 §3). Records `permission_code` and target. |
| `PUBLIC_INTAKE_BLOCKED` | PUBLIC_INTAKE | BLOCKED | INFO | Honeypot, CAPTCHA failure, rate limit (04 §5.1) |
| `SECURITY_LOG_ARCHIVED` / `SECURITY_LOG_CHAIN_ANCHORED` | ACCOUNT | SUCCESS / FAILURE | INFO / CRITICAL | Retention and tamper-evidence jobs (§9.4, §9.6) |

`failure_reason` vocabulary: `BAD_PASSWORD`, `UNKNOWN_USER`, `LOCKED`, `DISABLED`, `INVITED`, `NOT_HUMAN`, `RATE_LIMITED`, `TOKEN_INVALID`, `TOKEN_EXPIRED`, `TOKEN_REUSED`, `SESSION_REVOKED`, `CODE_INVALID`, `CODE_REPLAYED`, `CHALLENGE_EXPIRED`, `CHALLENGE_EXHAUSTED`, `POLICY`, `CAPTCHA_FAILED`, `HONEYPOT`, `ESCALATION_DENIED`, `STEP_UP_REQUIRED`.

### 9.2 Write rules (SEVT-001, SEVT-011)

- Events are written through a single security-event writer in the kernel. **Insert only.**
- Events accompanying a successful state change are written in the same transaction as the change.
- Failure and denial events are written in their **own** short transaction, so they persist even when the triggering request rolls back.
- The writer assigns `chain_seq`, `prev_hash` and `row_hash` inside its transaction (§9.6).
- If the writer fails, the request fails (fail closed) for SUCCESS events. For FAILURE events the original error response is still returned, and the logging failure raises a CRITICAL alert.

### 9.3 Redaction and prohibited content (SEVT-003)

**Never stored in any column, including `detail`:**

- Raw or hashed access tokens and refresh tokens
- Passwords or password hashes
- TOTP secrets or submitted OTP codes
- Recovery codes or their hashes
- Reset or invite tokens
- Cookies and `Authorization` headers
- Request or response bodies

**Controls:**

| Control | Rule |
|---|---|
| Emails for unknown accounts | Stored only as `email_attempted_hash` (HMAC-SHA-256 with a server key) |
| `detail` | Must use the event type's **allow-list** of keys (for example `LOGIN: stage, method`; `SESSION_REVOKED: reason, scope`; `SENSITIVE_ACTION: summary, change_count`). The writer rejects unknown keys and values longer than 200 characters. |
| `user_agent` | Truncated to 500 characters |
| `ip_address` | Stored in full (security necessity). Masked in application logs (02 §9). |
| Test enforcement | An automated test scans every event type's fixtures for token-shaped strings, hash-shaped strings and field names on the prohibited list |

### 9.4 Retention and archival (SEVT-004)

| Setting (configuration, not code) | Default | Notes |
|---|---|---|
| `SECURITY_EVENT_ONLINE_RETENTION_DAYS` | 365 | Initial default. The owner may change it. |
| `SECURITY_EVENT_ARCHIVE_RETENTION_DAYS` | 730 | Total retention, including archive |
| `SECURITY_EVENT_ARCHIVE_BUCKET` | S3 bucket, SSE-KMS, Object Lock (governance) | |

**Archival job (monthly, actor SYSTEM):**

1. Select rows older than online retention, ordered by `chain_seq`.
2. Export them to JSONL with the chain columns intact.
3. Upload and verify the object checksum and row count.
4. Record the last archived `chain_seq` and `row_hash` as the new **anchor**.
5. Delete the archived rows (EXC-002).
6. Write `SECURITY_LOG_ARCHIVED`.

Archives past the archive retention are expired by the S3 lifecycle.

### 9.5 Access control (SEVT-005)

| Access | Permission |
|---|---|
| All events | `security_event.read` at scope ALL. Sensitive. Founder and Admin. |
| Own events ("recent sign-in activity") | `security_event.read` at scope OWN (`subject_user_id = actor`). All roles. |
| Write | None through the API. Kernel writer only. |
| Update / delete | None. DB triggers or grants block it (07 §6). |

Reading the log is itself a normal API request: it is logged in the application logs, not in `security_event_log`, to avoid feedback loops.

### 9.6 Tamper evidence (SEVT-006, SEVT-007)

- **Hash chain (P0).** `row_hash = SHA-256(prev_hash ‖ canonical_json(row minus hash columns))`.
  - `chain_seq` is gap-free and assigned under the writer's transaction. SQLite's single writer serializes it. On PostgreSQL, a transaction-scoped advisory lock serializes it.
- **Verification job (P0).** A nightly job recomputes the chain from the last anchor. Any mismatch or gap raises a CRITICAL alert.
- **External anchoring (P1).** Each day the current chain head (`chain_seq`, `row_hash`) is written to an S3 bucket with Object Lock (compliance mode) and recorded as `SECURITY_LOG_CHAIN_ANCHORED`. Rewriting history would then require defeating WORM storage.
- **Database guards.** Immutability triggers or grants (07 §6.2).

### 9.7 Pagination and indexing (SEVT-008)

- `GET /api/v1/security-events` uses cursor pagination keyed on (`occurred_on`, `id`), newest first (08 §10).
- Filters: `subject_user_id`, `event_type`, `event_category`, `outcome`, `severity`, `ip`, `from`, `to`.
- Every filter is served by an index in 03 §5.4. A time range is required for unfiltered queries over more than 31 days.

### 9.8 Monitoring and alerting (SEVT-009)

The initial thresholds below are configuration values to be tuned from measured traffic (ASM-004).

| Alert | Rule | Severity |
|---|---|---|
| Credential stuffing | `LOGIN` FAILURE count per minute across all accounts > threshold | High |
| Account under attack | `ACCOUNT_LOCKED` for any Founder/Admin-holding account | High |
| Token theft signal | Any `REFRESH_REUSE_DETECTED` | Critical |
| MFA guessing | `MFA_CHALLENGE` FAILURE per account > threshold in 15 min | High |
| MFA reset | Any `MFA_RESET` | Critical: notify all `user.mfa.manage` holders |
| Recovery code used | Any `MFA_RECOVERY_CODE_USED` | Medium: email the user |
| Sensitive action | `SENSITIVE_ACTION` on `role.manage`, `user.permission.assign`, `permission.manage`, `user.mfa.manage` | Medium: email Founders |
| Chain broken | Verification job failure | Critical |
| Writer failure | Security-event write failure | Critical |
| Intake abuse | `PUBLIC_INTAKE_BLOCKED` per minute > threshold | Medium |

Alerts route through CloudWatch metric filters on structured logs, which mirror a counter per event type, plus the job outcomes.

### 9.9 Capacity (SEVT-010)

**No event volumes are asserted.** The indexes, retention job and cursor pagination above are designed to scale with volume without schema change. Actual volumes will be measured during the first 30 days of production traffic (ASM-004). Retention defaults and alert thresholds will then be reviewed, and the review recorded in ADR-004's review section.

## 10. Bootstrap (AUTH-014)

- A one-time CLI `bootstrap-founder --email --name` runs through SSM Session Manager.
- It refuses to run if any active human user already holds the FOUNDER role.
- It creates the user as INVITED with the FOUNDER role and prints a 1-hour INVITE link. No password passes through the CLI.
- Because FOUNDER has `mfa_required = true`, the first login forces MFA enrollment.
- It writes audit rows (actor SYSTEM, via CLI) and an `INVITE_SENT` event.
- There are no default credentials in any environment.

## 11. Multi-factor authentication (ADR-006, AUTH-015, MFA-*)

### 11.1 Policy (MFA-002, MFA-003, MFA-004)

A user **must** use MFA when **any** of the following is true. It is evaluated from data, never from role names.

1. They hold any live role with `role.mfa_required = true`. FOUNDER and ADMIN are seeded `true`. SALES is seeded `false`, and an owner may set it to `true`.
2. `app_user.mfa_required = true`. This is the per-user switch, for example for individual Sales users (MFA-003).
3. They hold any permission with `is_sensitive = true`, at any scope, via a role or a direct grant.

**Consequences:**

- **Optional MFA.** A user not required by policy may still enrol voluntarily. Once they have an ACTIVE factor, it is always challenged.
- **Policy becomes required later.** If policy starts requiring MFA for a user without a factor (for example after a role assignment), their next login returns `MFA_ENROLLMENT_REQUIRED`. Their `authz_version` is incremented, so existing sessions are forced to re-authenticate within the session-check cache window.
- **Enforcement.** Enforcement is in the auth service using the resolved policy. Authorization of every action remains permission-based (06).

### 11.2 TOTP parameters (MFA-001, MFA-009, MFA-010)

| Item | Value |
|---|---|
| Standard | RFC 6238 TOTP. SHA-1, 6 digits, 30-second step. These are the defaults supported by all mainstream authenticator apps. |
| Secret | 160-bit random. Encrypted at rest with AES-256-GCM and a KMS-wrapped data key (03 §5.5). |
| Clock drift | Accept steps T-1, T, T+1 |
| Replay | Reject any step ≤ `last_used_step` for the factor |
| Attempts | 5 per challenge. Account-level limit per §4. |
| Secret display | Once, during enrollment (QR code and manual key). It is never returned afterwards. |

### 11.3 Enrollment (MFA-001, MFA-006)

```
(after password, status MFA_ENROLLMENT_REQUIRED — or voluntarily from Profile › Security with a live session + step-up if a factor exists)
POST /auth/mfa/enroll/start {mfa_token}          → factor PENDING; return otpauth:// URI + base32 secret (once)
                                                   security_event MFA_ENROLLMENT_STARTED
POST /auth/mfa/enroll/confirm {mfa_token, code}  → verify code → factor ACTIVE, confirmed_on
                                                   generate 10 recovery codes (shown once, §11.5)
                                                   create session → 200 {status:"AUTHENTICATED", access_token, recovery_codes:[…]}
                                                   security_event MFA_ENROLLMENT_COMPLETED
Abandoned PENDING factors are revoked (ENROLLMENT_ABANDONED) when their challenge expires.
```

### 11.4 Login challenge

`POST /auth/mfa/verify {mfa_token, code}` or `{mfa_token, recovery_code}`:

1. Look up the challenge by hash. It must be unexpired, not completed, and have fewer than 5 attempts.
2. Verify TOTP with the replay check, or consume a recovery code.
3. On success:
   - Create `user_session` with `auth_methods = pwd+totp` (or `pwd+recovery`) and `mfa_verified_on = now`.
   - Issue tokens.
   - Write `MFA_CHALLENGE` SUCCESS and `LOGIN` SUCCESS (`stage = complete`).
4. On failure: increment attempts and write `MFA_CHALLENGE` FAILURE. Return `401 MFA_CODE_INVALID`, or `401 MFA_CHALLENGE_INVALID` once the challenge is exhausted or expired.

### 11.5 Recovery codes (MFA-005)

| Item | Value |
|---|---|
| Count and format | 10 codes. 10 characters from a 32-symbol alphabet with no ambiguous characters, shown as `XXXXX-XXXXX`. |
| Storage | HMAC-SHA-256 with a server key, in `user_mfa_recovery_code.code_hash`. Plaintext is never stored and never logged. |
| Use | Each code works once. Use writes `MFA_RECOVERY_CODE_USED` and emails the user. When 2 or fewer remain, the UI prompts regeneration. |
| Regeneration | `POST /auth/mfa/recovery-codes` requires step-up (§11.6). It invalidates the previous batch. Event `MFA_RECOVERY_CODES_REGENERATED`. |

### 11.6 Step-up (MFA-011)

These operations require `user_session.mfa_verified_on` within the last 10 minutes:

- MFA reset of another user (§11.7)
- Recovery-code regeneration
- Removing one's own factor (where policy allows)
- Granting any sensitive permission or role

If the check fails, the API returns `403 STEP_UP_REQUIRED` with a new `mfa_token` (purpose `STEP_UP`). The UI prompts for a code, calls `POST /auth/mfa/step-up`, and retries.

### 11.7 Privileged MFA reset workflow (MFA-007)

> Traces: USER-006

This is used when a user loses their authenticator and their recovery codes.

| Step | Rule |
|---|---|
| Request | The user contacts an administrator out of band. The actor verifies identity by a documented procedure (video call or in person). |
| Permission | `user.mfa.manage` (sensitive) |
| Step-up | The actor completed MFA within the last 10 minutes |
| Reason | Required. Stored in `audit_log.reason` and in the security event detail summary. |
| No self-reset | Actors cannot reset their own MFA (G3 in 06 §7) |
| No stronger target | The target's effective permissions must be a subset of the actor's (G9 in 06 §7) |
| Effect | All factors REVOKED (`ADMIN_RESET`). All recovery codes invalidated. All sessions revoked (`MFA_RESET`). The next login forces enrollment if policy requires it. |
| Records | `MFA_RESET` (CRITICAL) + `SENSITIVE_ACTION` + `audit_log` UPDATE on `user_mfa_factor` |
| Notification | Email to the target and to every holder of `user.mfa.manage` |
| Break-glass | If no other eligible actor exists (for example a sole Founder), the CLI `mfa-reset --user --reason` runs via SSM Session Manager (logged in CloudTrail). It writes the same events and notifications with actor SYSTEM and `performed_via = CLI`. |

### 11.8 Explicitly excluded (MFA-008)

- No security questions.
- No SMS or email one-time codes as a second factor. These are phishing-prone and depend on external channels.
- No "remember this device" bypass in P0.
- No bypass based on role names, IP allow-lists or user IDs.

## 12. Initial personas (AUTH-018)

| Persona | Role code | MFA | Notes |
|---|---|---|---|
| Founder | FOUNDER | Mandatory (`role.mfa_required = true`, plus sensitive permissions) | Holds every permission via the matrix |
| Admin | ADMIN | Mandatory (same mechanism) | |
| Sales | SALES | Configurable: per user (`app_user.mfa_required`) or for the whole role (`role.mfa_required`) | Mobile-first usage |

Role codes are data. Neither the authorization code nor the MFA code references them (RBAC-002, MFA-002).
