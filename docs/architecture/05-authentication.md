# 05 — Authentication, MFA, Account Security and Security Events

Governing decisions: [ADR-004](decisions/ADR-004-security-event-log.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-007](decisions/ADR-007-technology-stack.md) · [ADR-010](decisions/ADR-010-account-control-and-privileged-protection.md)

## 1. Principles

1. **Staff only, invitation only.** No self-registration (AUTH-011).
2. **Short-lived bearer token plus a revocable server-side session.** Every JWT carries a `sid`. The session is checked **on every request, uncached** (§5, AUTH-006).
3. **MFA is policy-driven, never role-name-driven** (§11.1). Sensitive permissions are effective only in MFA-verified sessions (06 §3.2).
4. **A new authenticator is never enrolled on a single factor.** A password alone is not enough, and neither is a recovery code alone (§11.3, §11.5).
5. **Identity attributes change only through security workflows.** Email, password, MFA, status and protection level are never editable through generic profile endpoints (§8.6, ADR-010).
6. **Enumeration-safe** (AUTH-009).
7. **Everything is recorded** in `security_event_log`, and nothing secret is recorded there (§9).

## 2. Password hashing and policy (AUTH-002, AUTH-003)

### 2.1 Algorithm

| Item | Value |
|---|---|
| Algorithm | Argon2id (RFC 9106) |
| Parameters | Memory 64 MiB, iterations 3, parallelism 1. Never below OWASP m = 19 MiB, t = 2, p = 1. Final values are set by benchmark on the target host (ASM-010). |
| Salt | 16 random bytes per hash (PHC string) |
| Rehash | On successful login, if parameters have been strengthened |
| Concurrency guard | A semaphore bounds concurrent hash operations within the single application process (OPS-010) |

### 2.2 Timing equalization

For an unknown email, the server verifies against a fixed dummy hash, so response timing does not reveal whether the account exists.

### 2.3 Password policy

| Rule | Value |
|---|---|
| Length | 12–128 characters, NFKC-normalized |
| Composition rules | None |
| Blocklist | Bundled common/breached list, plus the user's email local-part, name, "veda" and "vedaspaces" |
| Breach check | HIBP k-anonymity. P1. |
| Expiry | None |
| History | Can't reuse the current password |

## 3. Login (AUTH-001, AUTH-009, MFA-*)

```
POST /auth/login {email, password}
  rate limits (IP, account+network) → load app_user + credential → uniform failure handling
  password OK →
   ├─ no ACTIVE factor and MFA not required        → FULL session (auth_methods = pwd) → AUTHENTICATED
   ├─ ACTIVE factor exists                           → mfa_challenge(LOGIN) → MFA_REQUIRED {mfa_token}
   │     POST /auth/mfa/verify {mfa_token, code}     → FULL session (pwd+totp)          → AUTHENTICATED
   │     POST /auth/mfa/recovery {mfa_token, password, recovery_code} → RECOVERY session (§11.5)
   └─ MFA required but no ACTIVE factor              → NO session. An MFA enrollment link is emailed to the
                                                       VERIFIED address (§11.3) → MFA_ENROLLMENT_EMAIL_SENT
```

- **Uniform failures.** Unknown user, bad password, INVITED, DISABLED and throttled all return `401 INVALID_CREDENTIALS`.
- **The password alone never yields a session or an enrollment** when MFA is active or required. This closes F-02 for the "policy became required" case.
- **Must change password.** With `must_change_password`, the access token carries `pwd_change: true`. Only `/auth/me`, `/auth/password/change` and `/auth/logout` are then allowed.

## 4. Brute-force protection (AUTH-010, SEC-011, MFA-009, A-01)

| Layer | Control |
|---|---|
| Cloudflare | Rate rules on `/api/v1/auth/login`, `/api/v1/auth/password/*` and `/api/v1/auth/mfa/*` → managed challenge |
| App, per IP | Failures above threshold → 429 cool-down |
| App, per account + network (A-01) | After 5 consecutive password failures for an account from one network (IPv4 /24 or IPv6 /64), that **(account, network) pair** is throttled: escalating delay, max 15 min. The next attempt from that pair requires a Turnstile token. The account is **not** globally locked, so an attacker who knows a Founder's email cannot lock the Founder out from the Founder's own network. |
| App, per account (global) | If failures come from ≥ 5 distinct networks within 15 minutes (distributed guessing), the account is globally throttled for 15 minutes. Holders of an ACTIVE MFA factor are exempt: password plus TOTP still succeeds, because the second factor defeats password guessing. |
| MFA | 5 wrong codes void a challenge. 10 MFA or recovery failures per account in 15 min throttle MFA for that account for 15 min. |
| Records | `ACCOUNT_THROTTLED` / `ACCOUNT_UNTHROTTLED` events. Email to the user on a global throttle. |
| Store | Throttle counters live in `user_credential` (global) and in the single-process limiter (per network), which is authoritative because exactly one application process runs (OPS-010, F-09) |

Thresholds are initial configuration values (ASM-004).

## 5. Access token: JWT strategy (AUTH-004)

| Item | Value |
|---|---|
| Format | JWS `typ: at+jwt`, ES256, `kid`. JWKS at `/api/v1/auth/.well-known/jwks.json`. 90-day rotation. |
| Lifetime | 15 minutes for FULL sessions. 15 minutes and non-renewable for RECOVERY sessions. |
| Client storage | Memory only |

**Claims:**

| Claim | Meaning |
|---|---|
| `iss`, `aud` | Issuer and audience |
| `sub` | User id |
| `sid` | Session id |
| `jti` | Token id |
| `iat`, `nbf`, `exp` | Validity window |
| `av` | `authz_version` at issue |
| `amr` | `["pwd"]`, `["pwd","otp"]` or `["pwd","recovery"]` |
| `stp` | Session type: `full` or `recovery` |
| `pwd_change` | Present when a password change is forced |

- No permissions and no PII are carried.
- **Per-request verification (uncached, F-10):**
  1. Check the signature and claims.
  2. Run **one indexed read** of `user_session` joined with `app_user`: session not revoked and not expired; user ACTIVE; current `authz_version`, session type, `auth_methods`, `mfa_verified_on` and `security_cooling_off_until`.
  3. Take the effective-permission map from the in-process cache keyed by those values (06 §9).

  Revocation, deactivation and authorization changes therefore apply from the **next request** (AUTH-006, AUTH-017).

## 6. Refresh token and sessions (AUTH-005, AUTH-006)

| Item | Value |
|---|---|
| Token | Opaque 256-bit, SHA-256 hash only in `refresh_token.token_hash` |
| Cookie | `vs_rt`, `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`, host-only on `api.vedaspaces.com` |
| Lifetime | Idle 7 days (sliding), absolute 30 days |
| Rotation | Every refresh consumes the presented token (`used_on`) and issues a successor (`replaced_by_id`) |
| RECOVERY sessions | Receive **no** refresh token |
| CSRF | Allow-listed `Origin` plus `X-Requested-With: veda-workspace` on refresh and logout |
| Events | Every refresh attempt writes `TOKEN_REFRESH` (success or failure). No token material is recorded. |

### 6.1 Grace window (F-10)

A token presented again **within 20 seconds** of its first use is handled like this:

| Condition | Result |
|---|---|
| Its successor exists and is unused, and the token's `grace_used_on` is NULL | The server returns **a new access token only**, bound to the same session. There is **no new refresh token and no Set-Cookie**; the winning tab already set the successor cookie in the shared cookie jar. `grace_used_on` is set, so this happens at most once per token. |
| Any other reuse (outside 20 s, second grace use, or successor already used) | Treated as theft: the session is revoked (`TOKEN_REUSE`), a CRITICAL `REFRESH_REUSE_DETECTED` event is written, the user is emailed, and the response is 401 |

The client also serializes refreshes with Web Locks and a `BroadcastChannel`, so the grace path is only a safety net.

## 7. Logout and session control (AUTH-007, AUTH-016, AUTH-017)

| Operation | Endpoint | Effect | Event |
|---|---|---|---|
| Logout | `POST /auth/logout` | Revoke the current session, clear the cookie | `LOGOUT` |
| Logout all | `POST /auth/logout-all` | Revoke all own sessions | `LOGOUT` (scope = all) |
| Own sessions | `GET /auth/sessions`, `DELETE /auth/sessions/{id}` (`session.read`, `session.revoke`, P0) | — | `SESSION_REVOKED` |
| Admin revoke | `POST /users/{id}/sessions/revoke` (`user.session.revoke`, G9, step-up) | Revoke all of the target's sessions | `SESSION_REVOKED` + `SENSITIVE_ACTION` |
| Disable or delete user | User status workflow | Revoke all sessions and invalidate open tokens and challenges | `SESSION_REVOKED` |
| Password reset, MFA recovery, MFA reset, email change completion | Respective workflows | Revoke sessions as specified in each workflow | `SESSION_REVOKED` (reason) |

**Session retention (F-07).** Revoked or expired sessions are hard-deleted by the purge job after the configurable `USER_SESSION_RETENTION_DAYS`. The retention period is an owner input (OWNER-INPUT-002). Purge order and referential integrity are defined in 03 §2.10.

## 8. Password reset, invitation and email change

### 8.1 Forgot password (AUTH-008, AUTH-009)

- The request always returns `202`.
- If the account is an ACTIVE or throttled HUMAN:
  - all open PASSWORD_RESET tokens are invalidated;
  - a new token is created (256-bit; SHA-256 stored; 30 minutes) in `user_action_token`;
  - the link `…/reset-password#token=…` is emailed to the **verified** `email`, and **never** to `proposed_email`.
- Events: `PASSWORD_RESET_REQUESTED` (SUCCESS, or FAILURE with actor ANONYMOUS and the email hash).

### 8.2 Reset

1. Validate the token (purpose, unused, not invalidated, not expired) → `400 RESET_TOKEN_INVALID` otherwise.
2. Check the password policy.
3. Set the hash and clear throttles. Revoke **all** sessions.
4. Write `PASSWORD_RESET_COMPLETED`. Send a confirmation email.
5. **MFA is not reset or bypassed.**

### 8.3 Admin-initiated reset

`POST /users/{id}/password-reset` (`user.password.reset`, G9, G11) emails the §8.1 link to the target's **verified** email. The admin never sees or sets a password, and never chooses the destination.

### 8.4 Invitation (AUTH-011, A-05)

1. `POST /users` creates the user as INVITED with an INVITE token.
   - Expiry is 72 h, or **24 h if the invited roles contain any sensitive permission**.
   - It is emailed to the invitee's address, which becomes the verified email on acceptance.
2. `POST /auth/invite/accept {token, new_password}`:
   - Sets the password.
   - If the MFA policy requires MFA, **enrollment happens inside the same flow**. The invite token is the out-of-band proof. See §11.3 path B. The account becomes ACTIVE only after enrollment confirmation.
   - `email_verified_on` is set.
   - The inviter is emailed that the invite was accepted.
   - Events: `INVITE_ACCEPTED`, and `MFA_ENROLLMENT_COMPLETED` when applicable.

### 8.5 Change password (AUTH-012)

- Requires the current password.
- Blocked during a recovery cooling-off window (§11.5). The emailed reset (§8.1) remains available.
- Revokes the user's other sessions and rotates the current refresh token.
- Event: `PASSWORD_CHANGED`, plus an email.

### 8.6 Email change: proposed-email workflow (USER-007, owner Decision 3)

The verified `app_user.email` **never** changes until the new address is verified. No endpoint can overwrite it directly (08 §5.4).

```
Self-service:  PUT /auth/me/email {new_email}                     (RBX-004)
Admin:         POST /users/{id}/email-change {new_email, reason}   (user.email.change, G9, G11, G12 if the target is privileged)

 1 Step-up (§11.6): MFA code if the user (or the admin) has a factor; otherwise password re-entry (/auth/reauth)
   within 10 minutes. Blocked during the requester's recovery cooling-off.
 2 Validate new_email (format, not equal to current, not used by another live user's email or proposed_email)
 3 Store proposed_email, proposed_email_normalized, proposed_email_requested_on, proposed_email_requested_by
   (audit_log UPDATE). Any earlier pending proposal is superseded (its tokens invalidated).
 4 Create two single-use tokens in user_action_token (256-bit, hashed):
     EMAIL_VERIFICATION → sent to the PROPOSED address, expires in 60 min (configuration value)
     EMAIL_CHANGE_CANCEL → sent to the CURRENT verified address with an alert:
       "A change of your sign-in email to p***@example.com was requested by <you | an administrator>.
        If this wasn't you, cancel it and contact the Founder."
 5 Until completion: login, password reset and all notifications keep using the CURRENT verified email.
 6 POST /auth/email/verify {token}  (RBX-003)
     token valid → re-check uniqueness → email = proposed_email; email_verified_on = now; clear proposed_*;
     invalidate open PASSWORD_RESET / INVITE / MFA_ENROLLMENT tokens; revoke ALL sessions and refresh tokens
     (the user signs in again); notify BOTH addresses of completion.
 7 POST /auth/email/cancel {token}  (RBX-003) → clears the proposal and invalidates its tokens.
 8 Expiry → proposal cleared by the purge job (EMAIL_CHANGE_EXPIRED).
Events: EMAIL_CHANGE_REQUESTED, EMAIL_CHANGE_VERIFIED, EMAIL_CHANGE_COMPLETED, EMAIL_CHANGE_CANCELLED,
EMAIL_CHANGE_EXPIRED (security_event_log) + audit_log UPDATE rows for app_user at request, completion and cancellation.
```

- **Privileged targets.** When an admin changes the email of a privileged user (one holding any sensitive permission), the request needs dual-control approval before step 3 (06 §7.4). A Founder target requires the Founder workflow (06 §7.2).

## 9. Security event log (ADR-004, AUDIT-012, AUTH-013, SEVT-*)

The schema is in 03 §5.4. This log is separate from `audit_log`.

### 9.1 Event catalog (SEVT-002)

| event_type | Category | Outcomes | Severity |
|---|---|---|---|
| `LOGIN` | AUTHENTICATION | SUCCESS / FAILURE | INFO / WARNING |
| `TOKEN_REFRESH` | SESSION | SUCCESS / FAILURE | INFO / WARNING |
| `REFRESH_REUSE_DETECTED` | SESSION | FAILURE | CRITICAL |
| `LOGOUT` | SESSION | SUCCESS | INFO |
| `SESSION_REVOKED` | SESSION | SUCCESS | INFO / WARNING |
| `PASSWORD_RESET_REQUESTED` · `PASSWORD_RESET_COMPLETED` · `PASSWORD_CHANGED` | PASSWORD | SUCCESS / FAILURE | INFO / WARNING |
| `INVITE_SENT` · `INVITE_ACCEPTED` | ACCOUNT | SUCCESS / FAILURE | INFO |
| `EMAIL_CHANGE_REQUESTED` · `EMAIL_CHANGE_VERIFIED` · `EMAIL_CHANGE_COMPLETED` · `EMAIL_CHANGE_CANCELLED` · `EMAIL_CHANGE_EXPIRED` | ACCOUNT | SUCCESS / FAILURE | WARNING |
| `MFA_ENROLLMENT_EMAIL_SENT` · `MFA_ENROLLMENT_STARTED` · `MFA_ENROLLMENT_COMPLETED` | MFA | SUCCESS / FAILURE | INFO / WARNING |
| `MFA_CHALLENGE` | MFA | SUCCESS / FAILURE | INFO / WARNING |
| `MFA_RECOVERY_INITIATED` · `MFA_RECOVERY_FAILED` · `MFA_RECOVERY_COMPLETED` | MFA | SUCCESS / FAILURE | WARNING / CRITICAL |
| `MFA_RECOVERY_CODE_CONSUMED` | MFA | SUCCESS | WARNING |
| `MFA_AUTHENTICATOR_RE_ENROLLED` | MFA | SUCCESS | WARNING |
| `MFA_RECOVERY_CODES_REGENERATED` · `MFA_FACTOR_REMOVED` | MFA | SUCCESS | WARNING |
| `ADMIN_MFA_RESET_REQUESTED` · `ADMIN_MFA_RESET_APPROVED` · `ADMIN_MFA_RESET_DENIED` · `ADMIN_MFA_RESET_COMPLETED` | MFA | SUCCESS / FAILURE | CRITICAL |
| `APPROVAL_REQUESTED` · `APPROVAL_APPROVED` · `APPROVAL_DENIED` · `APPROVAL_EXPIRED` · `APPROVAL_CANCELLED` | AUTHORIZATION | SUCCESS | WARNING |
| `BREAK_GLASS_REQUESTED` · `BREAK_GLASS_APPROVED` · `BREAK_GLASS_CANCELLED` · `BREAK_GLASS_EXECUTED` | AUTHORIZATION | SUCCESS / FAILURE | CRITICAL |
| `FOUNDER_TRANSITION` | ACCOUNT | SUCCESS / FAILURE | CRITICAL |
| `ACCOUNT_THROTTLED` · `ACCOUNT_UNTHROTTLED` | ACCOUNT | SUCCESS | WARNING |
| `PERMISSION_DENIED` | AUTHORIZATION | BLOCKED | WARNING (de-duplicated per user, code, minute) |
| `PERMISSION_SUSPENDED` · `PERMISSION_REACTIVATED` | AUTHORIZATION | SUCCESS | WARNING |
| `SENSITIVE_ACTION` | AUTHORIZATION | SUCCESS / FAILURE | WARNING. Mutations using a sensitive permission (06 §3.2). |
| `SENSITIVE_READ` | AUTHORIZATION | SUCCESS | INFO. Reads using `SECURITY_DATA` or `BULK_DATA` permissions, de-duplicated per (actor, permission, 15 min). |
| `RECOVERY_SESSION_BLOCKED` | AUTHORIZATION | BLOCKED | WARNING. A recovery session called a non-allow-listed endpoint. |
| `PUBLIC_INTAKE_BLOCKED` | PUBLIC_INTAKE | BLOCKED | INFO (CAPTCHA failure, rate limit) |
| `PUBLIC_INTAKE_QUARANTINED` | PUBLIC_INTAKE | SUCCESS | INFO. Honeypot hit: the lead is stored as `spam_status = SUSPECTED` (04 §5.1). |
| `SECURITY_LOG_ARCHIVED` · `SECURITY_LOG_CHAIN_ANCHORED` · `SECURITY_LOG_CHAIN_BROKEN` | ACCOUNT | SUCCESS / FAILURE | INFO / CRITICAL |

`failure_reason` vocabulary:

`BAD_PASSWORD`, `UNKNOWN_USER`, `THROTTLED`, `DISABLED`, `INVITED`, `NOT_HUMAN`, `RATE_LIMITED`, `TOKEN_INVALID`, `TOKEN_EXPIRED`, `TOKEN_REUSED`, `SESSION_REVOKED`, `CODE_INVALID`, `CODE_REPLAYED`, `RECOVERY_CODE_INVALID`, `CHALLENGE_EXPIRED`, `CHALLENGE_EXHAUSTED`, `POLICY`, `CAPTCHA_FAILED`, `ESCALATION_DENIED`, `STEP_UP_REQUIRED`, `MFA_REQUIRED`, `COOLING_OFF`, `FOUNDER_PROTECTED`, `APPROVAL_REQUIRED`

### 9.2 Write rules (SEVT-001, SEVT-011)

- Events are insert-only, through the kernel security-event writer.
- Success events share the business transaction. Failure and denial events use their own short transaction, so they survive rollbacks.
- If the writer fails: for success events the request fails (fail closed). For failure events the original response is still returned, and a CRITICAL alert is raised.

### 9.3 Redaction and prohibited content (SEVT-003)

**Never stored:**

- access or refresh tokens, or their hashes;
- passwords or their hashes;
- TOTP secrets and submitted OTP codes;
- recovery codes and their hashes;
- reset, invite, enrollment and email tokens;
- cookies and `Authorization` headers;
- request and response bodies;
- full email addresses of unknown accounts (these are stored as an HMAC).

`detail` uses per-event allow-listed keys. The writer rejects unknown keys and values longer than 200 characters. Proposed email addresses appear only masked (`p***@example.com`).

### 9.4 Retention and archival (SEVT-004)

- Retention is configurable (`SECURITY_EVENT_ONLINE_RETENTION_DAYS`, `SECURITY_EVENT_ARCHIVE_RETENTION_DAYS`). **The values are owner input OWNER-INPUT-002** and gate production.
- Monthly archival (actor SYSTEM, run from the separate maintenance CLI, A-02):
  1. Export rows older than online retention, in `chain_seq` order, to JSONL in S3 (SSE-KMS, Object Lock).
  2. Verify the checksum and count.
  3. Write the **anchor** (`chain_seq`, `row_hash`, `chain_key_label`) to the anchor bucket (§9.6), not only to the database.
  4. Delete the rows (EXC-002).
  5. Write `SECURITY_LOG_ARCHIVED`.

### 9.5 Access control (SEVT-005, owner Decision 1)

| Access | Rule |
|---|---|
| Read | `security_event.read` (sensitive, `SECURITY_DATA`, ALL-only), held by Founder and Admin. It is effective only in MFA-verified sessions. **Standard Sales has no access, including to their own events.** |
| Recording of reads | Each read is recorded as a de-duplicated `SENSITIVE_READ` event (06 §3.2). |
| Write, update, delete | None through the API. |

### 9.6 Tamper evidence (SEVT-006, SEVT-007, F-11)

| Element | Design |
|---|---|
| Keyed chain | `row_hash = HMAC-SHA-256(K[chain_key_label], prev_hash ‖ JCS(row))`. The chain key comes from SSM SecureString, is loaded at process start, and is never stored in the database or in logs. `chain_key_label` is stored per row for rotation. An attacker with only the database file cannot recompute valid hashes. |
| Canonicalization | RFC 8785 JCS over the **application-level** representation of every non-hash column. GUIDs are 32-hex lowercase. Datetimes are RFC 3339 UTC with exactly six fractional digits and `Z`. Integers are JSON numbers. Nulls are explicit. Booleans are JSON booleans. JSON columns are embedded and canonicalized. Keys use the column names. This makes the chain engine-independent, so it recomputes identically after the PostgreSQL migration (11 §3.4). |
| Ordering | `chain_seq` is gap-free and assigned inside the writer transaction. SQLite's single writer serializes it. On PostgreSQL an advisory lock serializes it (A-13). |
| Nightly verification (P0) | Recompute from the last external anchor. A mismatch or gap raises `SECURITY_LOG_CHAIN_BROKEN` (CRITICAL). |
| External anchor (P0, SEVT-007) | Daily, the chain head (`chain_seq`, `row_hash`, `chain_key_label`) is written to a dedicated S3 bucket with **Object Lock in compliance mode**, using a write-only IAM role distinct from the application's read role. Archival anchors go to the same bucket. |
| Residual risk | An attacker with root on the host can read the chain key from process memory and rewrite recent rows back to the last external anchor. The daily anchor bounds this to one day. This is recorded in 11 §4 A2. |

### 9.7 Pagination and indexing (SEVT-008)

- Cursor on (`occurred_on`, `id`).
- Filters are served by the indexes in 03 §5.4.
- Unfiltered queries over more than 31 days require a time range.

### 9.8 Monitoring and alerting (SEVT-009)

The rules below are initial configuration values (ASM-004).

| Rule | Severity |
|---|---|
| Credential-stuffing spike (LOGIN failures per minute) | High |
| `ACCOUNT_THROTTLED` (global) for a privileged account | High |
| Any `REFRESH_REUSE_DETECTED` | Critical |
| MFA or recovery failure spikes | High |
| Any `MFA_RECOVERY_COMPLETED` | High. The user and all `user.mfa.reset` holders are emailed. |
| Any `ADMIN_MFA_RESET_*`, `BREAK_GLASS_*` or `FOUNDER_TRANSITION` | Critical |
| Any `EMAIL_CHANGE_REQUESTED` for a privileged account | High |
| `SENSITIVE_ACTION` for ACCESS_CONTROL | Medium. Founders are emailed. |
| `SECURITY_LOG_CHAIN_BROKEN` or writer failure | Critical |
| Nightly invariant I1/I2 failure (06 §7.3) | Critical |
| `PUBLIC_INTAKE_BLOCKED` spike | Medium |

### 9.9 Capacity (SEVT-010)

No volumes are asserted. Volumes are measured over the first 30 days of production (ASM-004), and retention and thresholds are reviewed then.

## 10. Bootstrap (AUTH-014)

- A one-time CLI `bootstrap-founder --email --name` runs through SSM.
- It refuses to run if any ACTIVE user already has `protection_level = FOUNDER`.
- It creates an INVITED user with the FOUNDER role and `protection_level = FOUNDER`, and prints a one-hour INVITE link.
- Invite acceptance forces MFA enrollment inside the invite flow (§8.4, §11.3 path B).
- No default credentials exist anywhere.

## 11. Multi-factor authentication (ADR-006, AUTH-015, MFA-*)

### 11.1 Policy (MFA-002, MFA-003, MFA-004, owner Decision 1)

MFA is **required** when any of these is true, evaluated from data only:

1. The user holds a live role with `role.mfa_required = true`. FOUNDER and ADMIN are seeded `true`; SALES is seeded `false`.
2. `app_user.mfa_required = true` (per-user switch, set with `user.mfa.require`).
3. The user holds any sensitive permission (06 §3.1), including suspended ones.

**Consequences:**

- **Standard Sales:** MFA is optional by default, because rules 1–3 are all false. Voluntary enrollment is allowed. Once a factor is ACTIVE, it is always challenged.
- **Sensitive-permission activation (MFA-012):** sensitive permissions are effective only with an ACTIVE factor in an MFA-verified FULL session (06 §3.2, §5).
- **Policy newly requires MFA** (for example a sensitive grant or a flag change): the user's `authz_version` increments. The next request shows the sensitive permissions as suspended with reason `MFA_REQUIRED`, and the UI prompts enrollment. Enrollment then follows §11.3 path A (logged in) or path C (emailed link). It never uses the password alone.

### 11.2 TOTP parameters (MFA-001, MFA-009, MFA-010)

| Item | Value |
|---|---|
| Standard | RFC 6238, SHA-1, 6 digits, 30 s |
| Secret | 160-bit from a CSPRNG. AES-256-GCM encrypted under a KMS-wrapped data key. The wrapped key is stored in `wrapped_data_key` (TEXT) and the key ARN in `kms_key_arn` (03 §5.5, F-13). |
| Drift | T-1, T, T+1 |
| Replay | Reject steps ≤ `last_used_step` |
| Attempts | 5 per challenge; account limits per §4 |
| Secret display | Once, at enrollment start. Never returned again. |

### 11.3 Enrollment: never on a single factor (MFA-014, F-02)

A new authenticator can be enrolled only through one of these paths. Each combines **two independent proofs**.

| Path | When | Proofs | Flow |
|---|---|---|---|
| **A. Logged-in** | Voluntary enrollment, or policy newly required while the user has a FULL session | An existing FULL session **plus** fresh password re-entry (`POST /auth/reauth`, within 5 minutes). If a factor already exists, **step-up with that factor** instead (replacement). | `enroll/start {reauth}` → `enroll/confirm {code}` |
| **B. Invitation** | First sign-in of an invited user whose policy requires MFA | Invite token (out-of-band, email) **plus** the new password being set | Inside `POST /auth/invite/accept` → `enroll/start {invite_context}` → `enroll/confirm` |
| **C. Emailed enrollment link** | Login when MFA is required and no ACTIVE factor exists (never enrolled, or after an admin MFA reset) | Password (at login) **plus** a single-use `MFA_ENROLLMENT` token emailed to the **verified** address (30 min) **plus** password re-entry on the enrollment page | Login → `MFA_ENROLLMENT_EMAIL_SENT` → link → `enroll/start {enrollment_token, password}` → `enroll/confirm` |
| **D. Recovery re-enrollment** | After successful self-service recovery (§11.5) | Password re-entry **plus** a valid recovery code, which together established the RECOVERY session | `enroll/start` (recovery session) → `enroll/confirm` |

- **Never allowed:** enrollment with only an `mfa_token` from a password login, or with only a recovery code.
- **On confirm:**
  - The previous factor, if any, is REVOKED (`REPLACED`).
  - A new recovery-code batch is generated and the old one invalidated (§11.5).
  - `authz_version` increments.
  - Events: `MFA_ENROLLMENT_COMPLETED` or `MFA_AUTHENTICATOR_RE_ENROLLED`.
  - Enrollment from a network or device not seen in the user's last 30 days of sessions raises a High alert after an MFA reset or recovery (§9.8).

### 11.4 Login challenge

`POST /auth/mfa/verify {mfa_token, code}`:

- **Success:** creates a FULL session (`auth_methods = pwd+totp`, `mfa_verified_on = now`) and writes `MFA_CHALLENGE` SUCCESS plus `LOGIN` SUCCESS.
- **Failure:** `401 MFA_CODE_INVALID` or `401 MFA_CHALLENGE_INVALID`.
- Recovery codes are **not** accepted at this endpoint. They go only to `/auth/mfa/recovery` (§11.5).

### 11.5 Recovery codes and self-service recovery (MFA-005, MFA-013, owner Decision 2)

#### Recovery codes

| Item | Value |
|---|---|
| Generation | 10 codes per batch from a CSPRNG. 10 symbols from a 32-symbol alphabet without ambiguous characters (50 bits), shown as `XXXXX-XXXXX`. |
| Storage | Only `HMAC-SHA-256(K_recovery, normalized code)`, with the key from SSM. Never stored in plaintext, never logged, never returned after initial issuance. |
| Use | Single use. Consumption writes `MFA_RECOVERY_CODE_CONSUMED`. |
| Rotation | A new batch is issued at every enrollment or re-enrollment, **including after recovery**, and the previous batch is invalidated. Regeneration is also available (`POST /auth/mfa/recovery-codes`, step-up required, blocked during cooling-off). |

#### Recovery flow

```
1  POST /auth/login {email, password}                       → MFA_REQUIRED {mfa_token}
2  POST /auth/mfa/recovery {mfa_token, password, recovery_code}
     - password RE-ENTERED and re-verified (fresh Argon2 verify) — owner requirement
     - recovery code verified (HMAC lookup, unused, current batch)
     failure → MFA_RECOVERY_FAILED; counts toward MFA throttle (§4); 401 MFA_RECOVERY_INVALID
     success (one transaction):
       - code consumed                                    → MFA_RECOVERY_CODE_CONSUMED
       - ALL other sessions and refresh tokens revoked    → SESSION_REVOKED (reason MFA_RECOVERY)
       - RECOVERY session created: session_type = RECOVERY, auth_methods = pwd+recovery,
         absolute expiry 15 min, NO refresh token
       - security notification e-mailed to the CURRENT VERIFIED email (never proposed_email)
       - events MFA_RECOVERY_INITIATED, MFA_RECOVERY_COMPLETED (stage=session)
3  In the RECOVERY session, only this allow-list is callable (06 §8 Layer 0):
       GET /auth/me · POST /auth/mfa/enroll/start · POST /auth/mfa/enroll/confirm · POST /auth/logout
     Everything else → 403 RECOVERY_SESSION_RESTRICTED (+ RECOVERY_SESSION_BLOCKED event). Explicitly prohibited:
     role and permission changes, email change (self or others), password-reset destination changes, API-token
     creation (no API tokens exist in P0; any future token feature must honor this rule), all privileged
     administration, lead data access.
4  enroll/confirm (§11.3 path D):
       - old factor REVOKED (REPLACED); new factor ACTIVE; new recovery-code batch issued (shown once)
       - RECOVERY session revoked; a new FULL session is issued (auth_methods = pwd+totp)
       - app_user.security_cooling_off_until = now + MFA_RECOVERY_COOLING_OFF_HOURS (initial default 24 h)
       - authz_version incremented                        → MFA_AUTHENTICATOR_RE_ENROLLED
```

#### Cooling-off

Until `security_cooling_off_until` passes, the following are refused with `403 COOLING_OFF`:

- the user's own email change;
- password change (the emailed reset in §8.1 remains available);
- MFA factor removal;
- recovery-code regeneration;
- use of the user's `ACCOUNT_CONTROL` and `ACCESS_CONTROL` permissions. These are suspended by the resolver (06 §5).

The UI shows a banner with the end time.

### 11.6 Step-up and re-authentication (MFA-011)

| Mechanism | Rule |
|---|---|
| Step-up (MFA) | `POST /auth/mfa/step-up {mfa_token, code}` sets `user_session.mfa_verified_on`. It is required within 10 minutes for G10 operations (06 §7.1). |
| Re-authentication (password) | `POST /auth/reauth {password}` sets `user_session.reauth_on`. It serves users without a factor (email change by a non-MFA Sales user) and enrollment path A. It is valid for 5 minutes. |
| Denial | Protected operations return `403 STEP_UP_REQUIRED` with the needed kind (`mfa` or `password`) and, for MFA, a new `mfa_token`. |

### 11.7 Administrative MFA reset (MFA-007, MFA-015, owner Decision 2)

| Step | Rule |
|---|---|
| Permission | `user.mfa.reset` (sensitive, ACCOUNT_CONTROL). It is separate from every other user-administration permission. |
| Preconditions | Step-up (G10). Reason required. The requester verifies the target's identity out of band by the documented procedure (video call or in person), recorded in the reason. |
| No self-reset | G3: no administrator can reset their own MFA. They use self-service recovery (§11.5). |
| No stronger target | G9: the target's permissions ⊆ the requester's |
| Dual control | If the target is **privileged** (holds any sensitive permission, including suspended), the reset requires approval by a second eligible holder of `user.mfa.reset` (06 §7.4). Events: `ADMIN_MFA_RESET_REQUESTED`, then `ADMIN_MFA_RESET_APPROVED` or `ADMIN_MFA_RESET_DENIED`. Standard (non-privileged) targets execute directly after step-up. |
| Founder target | Only through the Founder workflow (06 §7.2, G11). The requester and approver must be two different eligible FOUNDER-protected users. **An Admin can never reset a Founder's MFA**: G9 and G11 both block it. With fewer than two eligible Founders, use break-glass (06 §7.5). |
| Effect | All factors REVOKED (`ADMIN_RESET`). All recovery codes invalidated. All sessions revoked. Sensitive permissions suspended (`authz_version`++). An `MFA_ENROLLMENT` link is emailed to the target's **verified** address (§11.3 path C). The admin never receives an enrollment token. |
| Records | `ADMIN_MFA_RESET_COMPLETED` (CRITICAL) + `SENSITIVE_ACTION` + `audit_log` UPDATE rows on `user_mfa_factor`. Notification to the target and to all `user.mfa.reset` holders. |

### 11.8 Explicitly excluded (MFA-008)

- Security questions.
- SMS or email OTP as a second factor.
- "Remember this device".
- Recovery-code-only enrollment.
- Any bypass by role name, IP allow-list or user id.

## 12. Initial personas (AUTH-018)

| Persona | Role code | MFA | Notes |
|---|---|---|---|
| Founder | FOUNDER | Mandatory (`role.mfa_required = true` and sensitive permissions) | `protection_level = FOUNDER` via bootstrap or Founder transition |
| Admin | ADMIN | Mandatory (same mechanism) | Cannot act on Founder accounts (G9, G11) |
| Sales | SALES | **Optional by default.** Mandatory only if flagged per user or role, or granted a sensitive permission. | No sensitive permissions and no security-event access (owner Decision 1) |

Role codes are data. No authorization or MFA code references them (RBAC-002, MFA-002).
