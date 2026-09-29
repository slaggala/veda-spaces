# 08 — API Design

Governing decisions: [ADR-002](decisions/ADR-002-uuidv7-identifiers.md) · [ADR-004](decisions/ADR-004-security-event-log.md) · [ADR-005](decisions/ADR-005-lead-required-fields.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-007](decisions/ADR-007-technology-stack.md)

Every endpoint either names its permission code, or is listed in the RBAC exception register (06 §11, RBX-*). No endpoint authorizes by role name.

## 1. Endpoint index

| # | Method & path | Permission | Req |
|---|---|---|---|
| **Ops** | | | |
| 1 | `GET /health/live` | public (RBX-006) | LOG-005 |
| 2 | `GET /health/ready` | public (RBX-006) | LOG-005 |
| **Auth** (§4) | | | |
| 3 | `POST /api/v1/auth/login` | public (RBX-001) | AUTH-001 |
| 4 | `POST /api/v1/auth/refresh` | refresh cookie (RBX-002) | AUTH-005 |
| 5 | `POST /api/v1/auth/logout` | own session (RBX-002) | AUTH-007 |
| 6 | `POST /api/v1/auth/logout-all` | own session (RBX-002) | AUTH-007 |
| 7 | `GET /api/v1/auth/me` | `profile.read` | USER-004 |
| 8 | `PATCH /api/v1/auth/me` | `profile.update` | USER-004 |
| 9 | `POST /api/v1/auth/password/forgot` | public (RBX-003) | AUTH-008 |
| 10 | `POST /api/v1/auth/password/reset` | single-use token (RBX-003) | AUTH-008 |
| 11 | `POST /api/v1/auth/password/change` | own credentials (RBX-004) | AUTH-012 |
| 12 | `POST /api/v1/auth/invite/accept` | single-use token (RBX-003) | AUTH-011 |
| 13 | `GET /api/v1/auth/sessions` | `session.read` | AUTH-016 |
| 14 | `DELETE /api/v1/auth/sessions/{session_id}` | `session.revoke` | AUTH-016 |
| 15 | `GET /api/v1/auth/.well-known/jwks.json` | public (RBX-006) | AUTH-004 |
| 15a | `POST /api/v1/auth/mfa/verify` | challenge token (RBX-001) | MFA-001 |
| 15b | `POST /api/v1/auth/mfa/enroll/start` · `POST /api/v1/auth/mfa/enroll/confirm` | challenge token or own session (RBX-001) | MFA-001 |
| 15c | `POST /api/v1/auth/mfa/step-up` | own session (RBX-004) | MFA-011 |
| 15d | `POST /api/v1/auth/mfa/recovery-codes` | own session + step-up (RBX-004) | MFA-005 |
| 15e | `DELETE /api/v1/auth/mfa/factor` | own session + step-up, only if policy doesn't require MFA (RBX-004) | MFA-003 |
| 15f | `GET /api/v1/auth/mfa` | `profile.read` | MFA-001 |
| **Users** (§5) | | | |
| 16 | `GET /api/v1/users` | `user.read` | USER-001 |
| 17 | `POST /api/v1/users` | `user.create` (+ `user.role.assign` if roles given) | USER-001 |
| 18 | `GET /api/v1/users/{user_id}` | `user.read` | USER-001 |
| 19 | `PATCH /api/v1/users/{user_id}` | `user.update` | USER-001 |
| 20 | `POST /api/v1/users/{user_id}/deactivate` | `user.deactivate` | USER-002 |
| 21 | `POST /api/v1/users/{user_id}/activate` | `user.deactivate` | USER-002 |
| 22 | `POST /api/v1/users/{user_id}/unlock` | `user.update` | AUTH-010 |
| 23 | `DELETE /api/v1/users/{user_id}` | `user.delete` | USER-001 |
| 24 | `POST /api/v1/users/{user_id}/restore` | `user.restore` | USER-001 |
| 25 | `POST /api/v1/users/{user_id}/invite/resend` | `user.create` | AUTH-011 |
| 26 | `POST /api/v1/users/{user_id}/password-reset` | `user.password.reset` | AUTH-008 |
| 27 | `POST /api/v1/users/{user_id}/sessions/revoke` | `user.session.revoke` | AUTH-016 |
| 28 | `GET /api/v1/users/{user_id}/roles` | `user.read` | RBAC-008 |
| 29 | `PUT /api/v1/users/{user_id}/roles` | `user.role.assign` | RBAC-009 |
| 30 | `GET /api/v1/users/{user_id}/permissions` | `user.read` | RBAC-006 |
| 31 | `POST /api/v1/users/{user_id}/permissions` | `user.permission.assign` | RBAC-006 |
| 32 | `DELETE /api/v1/users/{user_id}/permissions/{grant_id}` | `user.permission.assign` | RBAC-006 |
| 33 | `GET /api/v1/users/{user_id}/effective-permissions` | `user.read` + `permission.read` | RBAC-016 |
| 34 | `GET /api/v1/users/assignable` | `lead.assign` | LEAD-007 |
| 34a | `POST /api/v1/users/{user_id}/mfa/reset` | `user.mfa.manage` + step-up | MFA-007 |
| 34b | `PUT /api/v1/users/{user_id}/mfa-requirement` | `user.mfa.manage` + step-up | MFA-003 |
| **Roles and permissions** (§6) | | | |
| 35 | `GET /api/v1/roles` | `role.read` | RBAC-008 |
| 36 | `POST /api/v1/roles` | `role.manage` | RBAC-008 |
| 37 | `GET /api/v1/roles/{role_id}` | `role.read` | RBAC-008 |
| 38 | `PATCH /api/v1/roles/{role_id}` | `role.manage` | RBAC-008 |
| 39 | `DELETE /api/v1/roles/{role_id}` | `role.manage` | RBAC-015 |
| 40 | `GET /api/v1/roles/{role_id}/permissions` | `role.read` | RBAC-008 |
| 41 | `PUT /api/v1/roles/{role_id}/permissions` | `role.manage` | RBAC-009 |
| 42 | `GET /api/v1/roles/{role_id}/users` | `role.read` + `user.read` | RBAC-008 |
| 43 | `GET /api/v1/permissions` | `permission.read` | RBAC-004 |
| 44 | `GET /api/v1/permissions/{permission_id}` | `permission.read` | RBAC-004 |
| 45 | `PATCH /api/v1/permissions/{permission_id}` | `permission.manage` | RBAC-004 |
| 46 | `GET /api/v1/permissions/{permission_id}/holders` | `permission.read` + `user.read` | RBAC-016 |
| **Reference and notifications** (§7) | | | |
| 47 | `GET /api/v1/lookups` · `GET /api/v1/lookups/{category_code}` | `lookup.read` | PLAT-009 |
| 48 | `POST /api/v1/lookups/{category_code}/values` · `PATCH …/values/{value_id}` | `lookup.manage` | PLAT-009 |
| 49 | `GET /api/v1/notifications` · `POST /api/v1/notifications/{id}/read` · `POST /api/v1/notifications/read-all` | `notification.read` | NOTIF-001 |
| **Leads** (§8) | | | |
| 50 | `POST /api/v1/public/leads` | public, Turnstile (RBX-005) | LEAD-001 |
| 51 | `GET /api/v1/leads` | `lead.read` | LEAD-013 |
| 52 | `POST /api/v1/leads` | `lead.create` | LEAD-003 |
| 53 | `GET /api/v1/leads/{lead_id}` | `lead.read` | LEAD-013 |
| 54 | `PATCH /api/v1/leads/{lead_id}` | `lead.update` | LEAD-002 |
| 55 | `DELETE /api/v1/leads/{lead_id}` | `lead.delete` | LEAD-016 |
| 56 | `POST /api/v1/leads/{lead_id}/restore` | `lead.restore` | LEAD-016 |
| 57 | `POST /api/v1/leads/{lead_id}/status` | `lead.status.change` / `lead.reopen` | LEAD-005 |
| 58 | `POST /api/v1/leads/{lead_id}/assign` | `lead.assign` | LEAD-007 |
| 59 | `POST /api/v1/leads/{lead_id}/duplicate-resolution` | `lead.update` | LEAD-010 |
| 60 | `GET /api/v1/leads/duplicates` | `lead.read` | LEAD-010 |
| 61 | `GET /api/v1/leads/summary` | `lead.read` | LEAD-014 |
| 62 | `GET /api/v1/leads/{lead_id}/history` | `lead.read` + `audit.read` | AUDIT-006 |
| 63 | `POST /api/v1/leads/exports` (P1) | `lead.export` | LEAD-017 |
| **Lead notes** (§9) | | | |
| 64 | `GET /api/v1/leads/{lead_id}/notes` | `lead_note.read` | NOTE-001 |
| 65 | `POST /api/v1/leads/{lead_id}/notes` | `lead_note.create` | NOTE-001 |
| 66 | `PATCH /api/v1/leads/{lead_id}/notes/{note_id}` | `lead_note.update` | NOTE-002 |
| 67 | `DELETE /api/v1/leads/{lead_id}/notes/{note_id}` | `lead_note.delete` | NOTE-002 |
| **Lead activities** (§9) | | | |
| 68 | `GET /api/v1/leads/{lead_id}/activities` | `lead_activity.read` | ACT-001 |
| 69 | `POST /api/v1/leads/{lead_id}/activities` | `lead_activity.create` | ACT-001 |
| 70 | `PATCH /api/v1/leads/{lead_id}/activities/{activity_id}` | `lead_activity.update` | ACT-002 |
| 71 | `POST /api/v1/leads/{lead_id}/activities/{activity_id}/complete` | `lead_activity.update` | ACT-003 |
| 72 | `POST /api/v1/leads/{lead_id}/activities/{activity_id}/cancel` | `lead_activity.update` | ACT-002 |
| 73 | `DELETE /api/v1/leads/{lead_id}/activities/{activity_id}` | `lead_activity.delete` | ACT-002 |
| 74 | `GET /api/v1/activities?owner=me&status=PLANNED` | `lead_activity.read` | LEAD-015 |
| **Audit** (§10) | | | |
| 75 | `GET /api/v1/audit-logs` | `audit.read` | AUDIT-008 |
| 76 | `GET /api/v1/audit-logs/{audit_id}` | `audit.read` | AUDIT-008 |
| 77 | `GET /api/v1/security-events` | `security_event.read` (ALL or OWN) | SEVT-005 |

## 2. Conventions

> Traces: API-001

### 2.1 Contract (API-008)

- OpenAPI 3.1 is generated from DTO definitions and served at `/api/v1/openapi.json` (staging) or as a build artifact (production).
- The frontend generates its types from it.
- CI diffs it against `main` and fails on breaking changes (API-009).

### 2.2 Formats

> Traces: DATA-013, SEC-004

| Item | Rule |
|---|---|
| Content type | `application/json; charset=utf-8`. Errors use `application/problem+json`. |
| Field naming | snake_case |
| IDs | UUIDv7 as exactly 32 lowercase hex characters (ADR-002). Every id in a path, query or body is validated against `^[0-9a-f]{12}7[0-9a-f]{3}[89ab][0-9a-f]{15}$`. Anything else → `422 INVALID_ID`, before any lookup, so format errors reveal nothing about existence. Integer ids and sequence values are never accepted or returned as identifiers. |
| Timestamps | RFC 3339 UTC with `Z` and milliseconds: `2026-09-29T10:02:11.004Z` |
| Dates | `YYYY-MM-DD` |
| Money | Decimal as string plus currency: `{"amount":"1850000.00","currency":"INR"}` |
| Lookups | Written as `*_code` (for example `"project_type_code":"MODULAR_KITCHEN"`). Read as `{"code":"MODULAR_KITCHEN","label":"Modular Kitchen"}`. |
| User references | Read as `{"id":"…","display_name":"Priya S"}` (no email unless the actor holds `user.read`) |
| Nulls | Returned explicitly. Omitting a field in PATCH leaves it unchanged. Sending `null` clears it (where allowed). |
| Unknown fields | Rejected with 422 `UNKNOWN_FIELD` (catches client typos and mass-assignment) |
| Request headers | `Authorization`, `If-Match`, `Idempotency-Key`, `X-Request-ID` (optional, echoed) |
| Response headers | `X-Request-ID`, `ETag` (single resources), `X-Authz-Version`, `RateLimit-*` |

### 2.3 Success envelope (API-002)

```json
// single resource
{ "data": { "id": "…", "…": "…", "version": 5 } }

// collection (offset)
{
  "data": [ { … }, { … } ],
  "meta": { "page": 2, "page_size": 25, "total": 132, "total_pages": 6 },
  "links": { "self": "/api/v1/leads?page=2&page_size=25",
             "next": "/api/v1/leads?page=3&page_size=25",
             "prev": "/api/v1/leads?page=1&page_size=25" }
}

// collection (cursor)
{ "data": [ … ], "meta": { "limit": 50, "next_cursor": "eyJ0IjoiMjAyNi0wOS0yOVQxMDowMjoxMS4wMDRaIiwiaWQiOiIwMTkyYTUwZSJ9", "has_more": true } }
```

`version` is included in every resource body, and in `ETag: "5"`.

### 2.4 Errors (API-003): RFC 9457 problem details

> Traces: LOG-002

```json
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://api.vedaspaces.com/problems/validation-failed",
  "title": "Validation failed",
  "status": 422,
  "code": "VALIDATION_FAILED",
  "detail": "2 fields are invalid.",
  "request_id": "8c2f1e0a9b7d4c3e",
  "errors": [
    { "field": "phone", "code": "INVALID_PHONE", "message": "Enter a valid phone number." },
    { "field": "project_type_code", "code": "INVALID_LOOKUP", "message": "Unknown project type." }
  ]
}
```

- `code` is stable and machine-readable (§11). `message` is human-readable, safe to display, and localizable later.
- 5xx responses never include stack traces or internal messages, only `code: INTERNAL_ERROR` and `request_id`.

### 2.5 Pagination (API-004)

| Style | Used by | Params | Limits |
|---|---|---|---|
| Offset | users, roles, permissions, leads, lookups | `page` (1-based), `page_size` | default 25, max 100 |
| Cursor | audit-logs, security-events, activities, notifications, lead history | `cursor`, `limit` | default 50, max 200 |

- Cursors are opaque base64url of the last row's (sort key, id), which is stable under concurrent inserts.
- `total` is exact for offset lists. It is capped at 10,000 with `meta.total_is_estimate: true` beyond that.

### 2.6 Filtering, search and sorting (API-005)

> Traces: DATA-008

| Pattern | Example | Meaning |
|---|---|---|
| Equality / IN | `status=NEW,CONTACTED` | Comma = OR within a field. Different fields AND. |
| Special values | `assigned_to=me` · `assigned_to=unassigned` | Resolved server-side |
| Ranges | `created_on_from=2026-09-01&created_on_to=2026-09-30` | Inclusive from, exclusive to. Dates are interpreted in the user's timezone. |
| Boolean | `overdue=true` | Named, documented filters |
| Search | `q=priya 98480` | Tokenized, each token matched (AND) against allowlisted fields with prefix/contains. Min 2 chars per token. |
| Sort | `sort=-created_on,name` | `-` = descending. Allowlist per resource. Default is documented. The tie-breaker `id` is always appended. |
| Deleted | `include_deleted=true` / `deleted_only=true` | Requires `<resource>.restore` |

Unknown filter or sort fields → 422 `INVALID_QUERY_PARAM`. They are never silently ignored.

### 2.7 Optimistic concurrency (API-006)

> Traces: DATA-006

- `PATCH`, `PUT` of sub-collections, `DELETE`, and action endpoints that modify a resource (`/status`, `/assign`, `/complete`) **require** `If-Match: "<version>"`.
  - Missing → `428 PRECONDITION_REQUIRED`.
  - Mismatch → `409 VERSION_CONFLICT`. The response includes `current_version` and `updated_by`/`updated_on`, so the UI can explain "Ravi updated this 2 minutes ago".
- Creates don't need it.

### 2.8 Idempotency (API-007)

- `Idempotency-Key` (opaque client string, 16–64 characters from `[A-Za-z0-9_-]`, typically a random UUID) is optional on authenticated `POST` creates, and **required** on `POST /public/leads`. It is not an entity id.
- The key plus actor plus route is remembered for 24 h. A replay returns the original status and body.
  - For public leads, the key is stored durably as `lead.intake_idempotency_key`.
  - For other routes it lives in an in-process TTL store, which moves to Redis at multi-host.
- Same key with a different body → `422 IDEMPOTENCY_KEY_REUSED`.

### 2.9 Versioning and compatibility (API-009)

- Major version in the path (`/api/v1`).
- Within v1, changes are additive only: new endpoints, new optional request fields, new response fields, new enum values (clients must tolerate unknown enum values).
- Breaking changes go to `/api/v2`, with v1 kept ≥ 6 months, a `Deprecation` header and a `Sunset` header.

## 3. Ops endpoints

> Traces: LOG-005

```
GET /health/live   → 200 {"status":"ok"}
GET /health/ready  → 200 {"status":"ok","checks":{"db":"ok","migrations":"head","outbox_lag_s":3}}
                   → 503 {"status":"degraded","checks":{…}}   (no data, no versions of dependencies)
```

## 4. Authentication endpoints

### 4.1 `POST /auth/login`

> Traces: AUTH-001, AUTH-004

Request:

```json
{ "email": "priya@vedaspaces.com", "password": "correct horse battery staple" }
```

`200` has three possible shapes, depending on the MFA policy (05 §3, §11).

Authenticated (MFA not required and no active factor):

```json
{
  "data": {
    "status": "AUTHENTICATED",
    "access_token": "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIwMjYtMDkiLCJ0eXAiOiJhdCtqd3QifQ.…",
    "token_type": "Bearer",
    "expires_in": 900,
    "must_change_password": false,
    "user": { "id": "0192a3aa55e07c01b2c3d4e5f6a7b8c9", "full_name": "Priya Sharma", "display_name": "Priya", "timezone": "Asia/Kolkata" }
  }
}
```

This shape also sets `Set-Cookie: vs_rt=…; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth; Max-Age=604800`.

Second factor needed. No session or cookie is created yet:

```json
{ "data": { "status": "MFA_REQUIRED", "mfa_token": "q3Z…", "methods": ["totp", "recovery_code"], "expires_in": 300 } }
```

Enrollment needed first:

```json
{ "data": { "status": "MFA_ENROLLMENT_REQUIRED", "mfa_token": "Hk8…", "expires_in": 900 } }
```

Errors:

| Status | Code | When |
|---|---|---|
| 401 | `INVALID_CREDENTIALS` | Every failure reason (05 §3) |
| 422 | `VALIDATION_FAILED` | Malformed body |
| 429 | `RATE_LIMITED` | With `Retry-After` |

### 4.2 `POST /auth/refresh`

> Traces: AUTH-005

- Requires the cookie `vs_rt` and the header `X-Requested-With: veda-workspace`. The body is empty.
- `200`: `{ "data": { "access_token": "…", "token_type": "Bearer", "expires_in": 900 } }`, plus a rotated cookie.
- Errors: `401 SESSION_INVALID` (cookie cleared) · `403 CSRF_REJECTED`.

### 4.3 `POST /auth/logout` · `POST /auth/logout-all`

> Traces: AUTH-007

`204`. The cookie is cleared.

### 4.4 `GET /auth/me`

> Traces: USER-004

```json
{
  "data": {
    "id": "0192a3aa55e07c01b2c3d4e5f6a7b8c9",
    "email": "priya@vedaspaces.com",
    "full_name": "Priya Sharma",
    "display_name": "Priya",
    "phone": "+919000000000",
    "timezone": "Asia/Kolkata",
    "locale": "en-IN",
    "status": "ACTIVE",
    "roles": [ { "id": "…", "code": "SALES", "name": "Sales" } ],
    "authz_version": 7,
    "permissions": {
      "lead.create": "ALL", "lead.read": "OWN", "lead.update": "OWN", "lead.status.change": "OWN",
      "lead_note.create": "ALL", "lead_note.read": "ALL", "lead_note.update": "OWN",
      "lead_activity.create": "ALL", "lead_activity.read": "ALL", "lead_activity.update": "OWN",
      "profile.read": "ALL", "profile.update": "ALL", "notification.read": "OWN", "lookup.read": "ALL",
      "session.read": "OWN", "session.revoke": "OWN"
    },
    "version": 3
  }
}
```

`PATCH /auth/me` takes `{ "full_name", "display_name", "phone", "timezone" }` with `If-Match`, and returns 200 with the same shape. Email changes are admin-only in P0.

### 4.5 Password endpoints

> Traces: AUTH-003, AUTH-008, AUTH-009, AUTH-012

| Endpoint | Request | Success | Errors |
|---|---|---|---|
| `POST /auth/password/forgot` | `{ "email": "…" }` | `202 { "data": { "message": "If an account exists, we've emailed a reset link." } }` | 422, 429 |
| `POST /auth/password/reset` | `{ "token": "…", "new_password": "…" }` | `204` | `400 RESET_TOKEN_INVALID` · `422 PASSWORD_POLICY` (errors[] lists rules: `TOO_SHORT`, `TOO_COMMON`, `CONTAINS_PERSONAL_INFO`) |
| `POST /auth/password/change` | `{ "current_password": "…", "new_password": "…" }` | `204` | `401 INVALID_CREDENTIALS` · `422 PASSWORD_POLICY` · `422 PASSWORD_REUSED` |
| `POST /auth/invite/accept` | `{ "token": "…", "new_password": "…", "full_name": "optional" }` | `204` | `400 INVITE_TOKEN_INVALID` · `422 PASSWORD_POLICY` |

### 4.6 Sessions (see also 4.7 MFA)

> Traces: AUTH-016

`GET /auth/sessions` returns:

```json
{ "data": [ { "id": "0192…", "device_label": "Chrome on Android", "ip_city": "Hyderabad, IN",
              "started_on": "2026-09-28T04:10:00.000Z", "last_seen_on": "2026-09-29T09:58:12.000Z", "current": true } ],
  "meta": { "limit": 50, "next_cursor": null, "has_more": false } }
```

`DELETE /auth/sessions/{id}` → `204` · `404 NOT_FOUND` (not own).

### 4.7 MFA endpoints (ADR-006)

> Traces: MFA-001, MFA-005, MFA-011

| Endpoint | Request | Success | Errors |
|---|---|---|---|
| `POST /auth/mfa/verify` | `{ "mfa_token": "…", "code": "123456" }` or `{ "mfa_token": "…", "recovery_code": "K7M3Q-9TDXR" }` | `200` AUTHENTICATED shape (§4.1) + cookie | `401 MFA_CODE_INVALID` · `401 MFA_CHALLENGE_INVALID` (expired, exhausted or unknown) · `429 RATE_LIMITED` |
| `POST /auth/mfa/enroll/start` | `{ "mfa_token": "…" }` (or a session + step-up for voluntary re-enrollment) | `200 { "data": { "otpauth_uri": "otpauth://totp/Veda%20Spaces:priya%40vedaspaces.com?secret=…&issuer=Veda%20Spaces", "secret": "JBSWY3DPEHPK3PXP…", "expires_in": 900 } }`. The secret is returned **only here, once**. | `401 MFA_CHALLENGE_INVALID` · `409 MFA_ALREADY_ENROLLED` |
| `POST /auth/mfa/enroll/confirm` | `{ "mfa_token": "…", "code": "123456", "label": "Priya's phone" }` | `200` AUTHENTICATED shape + `"recovery_codes": ["K7M3Q-9TDXR", … 10 items]` (**shown once**) | `401 MFA_CODE_INVALID` |
| `POST /auth/mfa/step-up` | `{ "mfa_token": "…", "code": "123456" }` (token from a `STEP_UP_REQUIRED` response) | `204`. Sets `mfa_verified_on` on the session. | `401 MFA_CODE_INVALID` |
| `POST /auth/mfa/recovery-codes` | `{}` (step-up required) | `200 { "data": { "recovery_codes": [ … ] } }`. The previous batch is invalidated. | `403 STEP_UP_REQUIRED` |
| `DELETE /auth/mfa/factor` | step-up required | `204` | `409 MFA_REQUIRED_BY_POLICY` · `403 STEP_UP_REQUIRED` |
| `GET /auth/mfa` | — | `200 { "data": { "required": true, "required_by": ["ROLE_POLICY"], "factor": { "type": "TOTP", "label": "Priya's phone", "confirmed_on": "…", "last_used_on": "…" }, "recovery_codes_remaining": 8 } }`. `required_by` values are `ROLE_POLICY`, `USER_POLICY` and `SENSITIVE_PERMISSION`. They describe the source generically and never name a role code. | — |

A `STEP_UP_REQUIRED` error body includes `"mfa_token"` for the step-up call.

## 5. Users

> Traces: USER-001

### 5.1 `GET /users`

- **Filters:** `q` (name, email) · `status=ACTIVE,INVITED,LOCKED,DISABLED` · `role_id` · `include_deleted`
- **Sort:** `full_name`, `-created_on`, `-last_login_on`

```json
{
  "data": [
    { "id": "0192a3aa…", "email": "priya@vedaspaces.com", "full_name": "Priya Sharma", "display_name": "Priya",
      "status": "ACTIVE", "roles": [ { "id": "…", "code": "SALES", "name": "Sales" } ],
      "last_login_on": "2026-09-29T04:10:00.000Z", "created_on": "2026-09-01T06:00:00.000Z",
      "is_deleted": false, "version": 3 }
  ],
  "meta": { "page": 1, "page_size": 25, "total": 6, "total_pages": 1 },
  "links": { "self": "/api/v1/users?page=1&page_size=25", "next": null, "prev": null }
}
```

### 5.2 `POST /users` (invite)

> Traces: AUTH-011

```json
{ "email": "ravi@vedaspaces.com", "full_name": "Ravi Kumar", "phone": "+919111111111",
  "timezone": "Asia/Kolkata", "role_ids": ["0192…sales"] }
```

- `201` with the user (status `INVITED`), and a `Location` header.
- Errors:

| Status | Code |
|---|---|
| 409 | `DUPLICATE` (field `email`) |
| 403 | `ESCALATION_DENIED` (role exceeds actor) |
| 403 | `PERMISSION_DENIED` (roles given without `user.role.assign`) |

### 5.3 `GET /users/{id}`

Same shape as a list item, plus `phone`, `timezone`, `locale`, `locked_until`, `must_change_password`, `created_by`, `updated_by`, `updated_on`.

### 5.4 `PATCH /users/{id}`

- `If-Match` required. Body is any of `full_name`, `display_name`, `phone`, `timezone`, `locale`, `email` (changing email re-sends verification in P1).
- `status` can't be changed here. Use the action endpoints.

### 5.5 Lifecycle actions

> Traces: AUTH-017, USER-002

| Endpoint | Body | Effect | Errors |
|---|---|---|---|
| `POST …/deactivate` | `{ "reason": "Left company" }` | status DISABLED · sessions revoked · tokens invalidated | `409 LAST_ADMINISTRATOR` · `403 SELF_MODIFICATION_DENIED` |
| `POST …/activate` | `{}` | DISABLED → ACTIVE (or INVITED if never accepted) | 409 `INVALID_STATE` |
| `POST …/unlock` | `{}` | Clears lockout | |
| `DELETE /users/{id}` | — (`If-Match`) | Soft delete + deactivate effects | G3, G4 |
| `POST …/restore` | `{}` | Restore as DISABLED | `409 DUPLICATE` (email reused) |
| `POST …/invite/resend` | `{}` | New INVITE token | `409 INVALID_STATE` (not INVITED) |
| `POST …/password-reset` | `{}` | Emails a reset link | |
| `POST …/sessions/revoke` | `{ "reason": "…" }` | Revoke all | |

### 5.6 Role assignment: `PUT /users/{id}/roles`

This declarative replace diffs the current set and writes soft-deletes and inserts:

```json
{ "roles": [ { "role_id": "0192…sales" },
             { "role_id": "0192…admin", "valid_until": "2026-10-15T18:30:00.000Z", "reason": "Covering during leave" } ] }
```

`200` returns `{ "data": [ user_role items ] }`. Errors: G1–G4 codes (06 §7).

### 5.7 Direct permissions

> Traces: RBAC-006

`POST /users/{id}/permissions`:

```json
{ "permission_code": "lead.read", "effect": "GRANT", "scope": "ALL",
  "valid_until": "2026-10-15T18:30:00.000Z", "reason": "Covering for Ravi" }
```

- `201`. Errors: `422 REASON_REQUIRED` · `422 SCOPE_NOT_SUPPORTED` · `403 ESCALATION_DENIED` · `409 DUPLICATE`.
- `DELETE /users/{id}/permissions/{grant_id}` → `204` (soft delete).

### 5.8 `GET /users/{id}/effective-permissions` (RBAC-016)

```json
{
  "data": {
    "authz_version": 9,
    "permissions": [
      { "code": "lead.read", "scope": "ALL",
        "sources": [ { "type": "ROLE", "role_code": "SALES", "scope": "OWN" },
                     { "type": "USER_GRANT", "grant_id": "0192…", "scope": "ALL", "valid_until": "2026-10-15T18:30:00.000Z" } ] },
      { "code": "lead.export", "scope": null, "denied": true,
        "sources": [ { "type": "USER_DENY", "grant_id": "0192…", "reason": "Policy" } ] }
    ]
  }
}
```

### 5.9 User MFA administration (MFA-003, MFA-007)

> Traces: USER-006

| Endpoint | Request | Success | Errors |
|---|---|---|---|
| `POST /users/{id}/mfa/reset` | `{ "reason": "Lost phone; identity verified by video call with Founder" }` (`If-Match`) | `204`. Factors revoked, codes invalidated, sessions revoked, notifications sent (05 §11.7). | `403 STEP_UP_REQUIRED` · `403 SELF_MODIFICATION_DENIED` · `403 ESCALATION_DENIED` (G9) · `422 REASON_REQUIRED` |
| `PUT /users/{id}/mfa-requirement` | `{ "mfa_required": true, "reason": "Handles high-value clients" }` (`If-Match`) | `200` user. Setting `false` only removes the *user-level* source. Role and sensitive-permission sources still apply. | `403 STEP_UP_REQUIRED` · `422 REASON_REQUIRED` |

The user resource (§5.1, §5.3) includes `"mfa": { "required": true, "enrolled": true, "required_by": ["ROLE_POLICY"] }`.

### 5.10 `GET /users/assignable`

This returns active HUMAN users holding `lead.read`: `[{ "id", "display_name", "open_lead_count" }]`. It exists so that Sales-facing screens never need `user.read`.

## 6. Roles and permissions

### 6.1 Roles

> Traces: RBAC-008, RBAC-015

`GET /roles` returns:

```json
{ "data": [ { "id": "…", "code": "SALES", "name": "Sales", "description": "Sales & design consultants",
              "is_system": true, "is_assignable": true, "user_count": 4, "permission_count": 18, "version": 2 } ],
  "meta": { "page": 1, "page_size": 25, "total": 3, "total_pages": 1 }, "links": { … } }
```

| Endpoint | Request | Response / errors |
|---|---|---|
| `POST /roles` | `{ "code": "SALES_MANAGER", "name": "Sales Manager", "description": "…", "copy_from_role_id": "optional" }` | `201`. `409 DUPLICATE` (code/name) |
| `PATCH /roles/{id}` | `{ "name", "description", "is_assignable" }` with `If-Match` | `code` is immutable (`422 IMMUTABLE_FIELD`) |
| `DELETE /roles/{id}` | — | `409 SYSTEM_OBJECT` · `409 ROLE_IN_USE` (has live assignments; unassign first) |

`PUT /roles/{id}/permissions` is a declarative full replace:

```json
{ "permissions": [ { "permission_code": "lead.read", "scope": "ALL" },
                   { "permission_code": "lead.assign", "scope": "ALL" } ],
  "reason": "Create sales manager role" }
```

`200` returns a grants list with diff counts `{ "added": 2, "removed": 0, "changed": 0 }`. Errors: G2, G4, G6, G8.

### 6.2 Permissions

> Traces: RBAC-004

`GET /permissions?module=crm&resource=lead&q=status`:

```json
{ "data": [ { "id": "…", "code": "lead.status.change", "module": "crm", "resource": "lead", "action": "status.change",
              "name": "Change lead status", "description": "Move leads through the pipeline, including WON/LOST.",
              "supports_scope": true, "is_sensitive": false, "requirement_ref": "LEAD-005",
              "granted_to_roles": [ { "code": "FOUNDER", "scope": "ALL" }, { "code": "SALES", "scope": "OWN" } ],
              "version": 1 } ], "meta": { … } }
```

- `PATCH /permissions/{id}` takes `{ "name", "description" }` only. Everything else returns `422 IMMUTABLE_FIELD`.
- `GET /permissions/{id}/holders` returns users with the effective scope and source.

## 7. Reference data and notifications

> Traces: NOTIF-001, PLAT-009

- `GET /lookups/PROJECT_TYPE?include_inactive=false` returns `{ "data": [ { "id", "code", "label", "description", "sort_order", "is_active", "attributes" } ] }`.
- `GET /lookups` returns every category with its active values in one call (cached by the SPA, `ETag` plus `Cache-Control: private, max-age=300`).
- `POST /lookups/{category}/values` and `PATCH …/values/{id}` (`label`, `description`, `sort_order`, `is_active`, `attributes`) need `lookup.manage`. `code` is immutable.

`GET /notifications?unread=true` returns:

```json
{ "data": [ { "id": "…", "notification_type": "LEAD_ASSIGNED", "title": "New lead assigned: VS-L-2026-000123",
              "body": "Anita R · Modular Kitchen · Gachibowli", "link_path": "/leads/0192…",
              "read_on": null, "created_on": "2026-09-29T09:58:12.000Z" } ],
  "meta": { "limit": 50, "next_cursor": null, "has_more": false, "unread_count": 3 } }
```

## 8. Leads

### 8.1 Lead resource (read shape)

> Traces: LEAD-002

```json
{
  "data": {
    "id": "0192a4f1c3b27e8d9f10a2b3c4d5e6f7",
    "lead_number": "VS-L-2026-000123",
    "name": "Anita Reddy",
    "phone": "+919876543210",
    "phone_raw": "98765 43210",
    "public_reference": "K7M3-Q9TD",
    "email": "anita@example.com",
    "city": "Hyderabad",
    "locality": "Gachibowli",
    "project_type": { "code": "MODULAR_KITCHEN", "label": "Modular Kitchen" },
    "property_type": { "code": "APARTMENT", "label": "Apartment / Flat" },
    "budget_range": { "code": "5L_10L", "label": "₹5–10 L" },
    "message": "3BHK handover in December, want kitchen + wardrobes.",
    "status": "SITE_VISIT",
    "status_changed_on": "2026-09-27T05:30:00.000Z",
    "priority": "HIGH",
    "source": { "code": "WEBSITE", "label": "Website" },
    "source_detail": null,
    "attribution": { "utm_source": "instagram", "utm_medium": "paid", "utm_campaign": "diwali-2026",
                     "utm_term": null, "utm_content": null, "landing_page": "/?utm_source=instagram…", "referrer_url": null },
    "assigned_to": { "id": "0192a3aa…", "display_name": "Priya" },
    "assigned_on": "2026-09-26T04:00:00.000Z",
    "next_follow_up_on": "2026-09-30T05:30:00.000Z",
    "is_follow_up_overdue": false,
    "last_activity_on": "2026-09-28T10:00:00.000Z",
    "expected_close_on": "2026-10-20",
    "quoted": null,
    "won_on": null, "lost_on": null, "lost_reason": null, "lost_reason_note": null,
    "duplicate_status": "NONE", "duplicate_of": null,
    "consent": { "contact": true, "policy_version": "2026-09-v1", "captured_on": "2026-09-25T14:02:00.000Z",
                 "channel": "WEBSITE_FORM", "source_page": "/#contact", "ip_address": "49.205.xxx.xxx" },
    "allowed_transitions": ["QUOTATION_SENT", "NEGOTIATION", "WON", "LOST", "CONTACTED"],
    "created_on": "2026-09-25T14:02:00.000Z", "created_by": { "id": "0000…0002", "display_name": "Website" },
    "updated_on": "2026-09-28T10:00:00.000Z", "updated_by": { "id": "0192a3aa…", "display_name": "Priya" },
    "is_deleted": false,
    "version": 6
  }
}
```

`allowed_transitions` is computed for the actor from the state machine plus their permissions. The UI renders only these.

### 8.2 `GET /leads`

> Traces: LEAD-013

| Param | Values |
|---|---|
| `q` | Matches name, phone (digits), email, lead_number, locality, city |
| `status` | CSV of statuses · `open=true` (the five open statuses) |
| `assigned_to` | `me`, `unassigned`, user id(s) |
| `project_type`, `budget_range`, `source`, `priority` | CSV of lookup codes / values |
| `city` | CSV |
| `created_on_from/to`, `status_changed_on_from/to` | Dates |
| `follow_up` | `overdue`, `today`, `this_week`, `none` |
| `duplicate_status` | `SUSPECTED`, … |
| `include_deleted`, `deleted_only` | Needs `lead.restore` |
| `sort` | `created_on`, `status_changed_on`, `next_follow_up_on`, `name`, `priority` (±). Default `-created_on`. |
| `page`, `page_size` | |

The list items are a compact projection: `id, lead_number, name, phone, city, locality, project_type, budget_range, status, priority, source, assigned_to, next_follow_up_on, is_follow_up_overdue, duplicate_status, created_on, version`.

### 8.3 `POST /leads` (manual)

> Traces: LEAD-003

```json
{
  "name": "Rahul Menon", "phone": "+91 90000 12345", "email": null,
  "city": "Hyderabad", "locality": "Kondapur",
  "project_type_code": "FULL_HOME", "property_type_code": "VILLA", "budget_range_code": "35L_50L",
  "message": "Referred by Mr. Rao. New villa, possession in Jan.",
  "source_code": "REFERRAL", "source_detail": "Mr. Rao (VS-L-2025-000812)",
  "priority": "HIGH",
  "assigned_to": "0192a3aa55e07c01b2c3d4e5f6a7b8c9",
  "initial_note": "Prefers calls after 6pm."
}
```

- `201` returns the lead resource plus `meta.possible_duplicates: [{ "id", "lead_number", "name", "status" }]`, containing matches visible to the actor.
- Errors:

| Status | Code |
|---|---|
| 422 | `VALIDATION_FAILED` (field codes from 04 §13) |
| 422 | `SOURCE_NOT_ALLOWED` (WEBSITE) |
| 422 | `INVALID_ASSIGNEE` |
| 403 | `PERMISSION_DENIED` (assigned_to ≠ self without `lead.assign`) |

### 8.4 `POST /public/leads` (ADR-005, LEAD-023, LEAD-025)

> Traces: LEAD-001, LEAD-009, LEAD-011, LEAD-012, LEAD-018

Headers: `Idempotency-Key: 5f0c2b1e9d7a4c3f8e6b5a4d3c2b1a09` · `Origin: https://www.vedaspaces.com`

The request schema is **closed**. Only these fields are accepted:

```json
{
  "name": "Anita Reddy",
  "phone": "98765 43210",
  "consent": { "acknowledged": true, "policy_version": "2026-09-v1" },

  "email": "anita@example.com",
  "city": "Hyderabad",
  "project_type_code": "MODULAR_KITCHEN",
  "budget_range_code": "5L_10L",
  "message": "3BHK handover in December…",

  "attribution": { "utm_source": "instagram", "utm_medium": "paid", "utm_campaign": "diwali-2026",
                   "utm_term": null, "utm_content": null,
                   "landing_page": "/?utm_source=instagram", "referrer_url": "https://l.instagram.com/", "form_page": "/#contact" },
  "turnstile_token": "0.AbCd…",
  "website": ""
}
```

| Field | Required | Notes |
|---|---|---|
| `name`, `phone`, `consent.acknowledged` (= true), `consent.policy_version` | Yes | ADR-005 |
| `email`, `city`, `project_type_code`, `budget_range_code`, `message` | No | May be enriched by staff later (LEAD-024) |
| `attribution`, `turnstile_token`, `website` (honeypot, must be empty) | Machine-supplied | Not user-entered data |

**`201`: the complete response.** No other fields are ever returned (LEAD-025):

```json
{ "data": { "reference": "K7M3-Q9TD", "message": "Thank you. Our design team will call you within one working day." } }
```

Errors:

| Status | Code | Body |
|---|---|---|
| 422 | `VALIDATION_FAILED` | `errors[]` with `REQUIRED`, `INVALID_PHONE`, `INVALID_EMAIL`, `INVALID_LOOKUP`, `TOO_LONG`, `UNKNOWN_FIELD` |
| 422 | `CONSENT_REQUIRED` · `UNKNOWN_POLICY_VERSION` | |
| 422 | `CAPTCHA_FAILED` | |
| 428 | `IDEMPOTENCY_KEY_REQUIRED` | |
| 429 | `RATE_LIMITED` | With `Retry-After` |
| 413 | `PAYLOAD_TOO_LARGE` | |
| 5xx | `INTERNAL_ERROR` / `SERVICE_UNAVAILABLE` | The website then falls back to WhatsApp (LEAD-019) |

- Error bodies contain only the problem fields and `request_id`. They never contain internal lead data or state.
- A honeypot hit returns `202` with `{ "data": { "message": "Thank you." } }` and creates no lead. It is recorded as a `PUBLIC_INTAKE_BLOCKED` security event.
- An idempotent replay returns the original `201` body unchanged.

### 8.5 `PATCH /leads/{id}`

> Traces: LEAD-021

- `If-Match: "6"` is required.
- **Updatable (enrichment, LEAD-024):** `name, phone, email, city, locality, project_type_code, property_type_code, budget_range_code, message, priority, source_code, source_detail, expected_close_on, quoted_amount` (P1).
- **Rejected with `422 FIELD_NOT_UPDATABLE`:** `status`, `assigned_to`, `lead_number`, `public_reference`, audit fields, `duplicate_*`, `consent_*`, `intake_idempotency_key`.
- `200` returns the lead. `409 VERSION_CONFLICT` returns:

```json
{ "type": "https://api.vedaspaces.com/problems/version-conflict", "title": "This lead was changed by someone else",
  "status": 409, "code": "VERSION_CONFLICT", "request_id": "…",
  "current_version": 7, "updated_by": { "id": "…", "display_name": "Ravi" }, "updated_on": "2026-09-29T09:59:40.000Z" }
```

### 8.6 `POST /leads/{id}/status`

> Traces: LEAD-005, LEAD-006

`If-Match` is required.

```json
{ "to_status": "LOST", "lost_reason_code": "CHOSE_COMPETITOR", "lost_reason_note": "Went with a local carpenter",
  "comment": "Price was the deciding factor" }
```

```json
{ "to_status": "WON", "won_on": "2026-09-29T10:00:00.000Z", "comment": "Advance received" }
```

- `200` returns the lead (new version) plus `meta.activity_id` for the STATUS_CHANGE activity.
- Errors:

| Status | Code |
|---|---|
| 422 | `INVALID_STATUS_TRANSITION` (detail lists `allowed_transitions`) |
| 422 | `NO_OP_TRANSITION` |
| 422 | `LOST_REASON_REQUIRED` |
| 422 | `COMMENT_REQUIRED` |
| 403 | `PERMISSION_DENIED` (reopen without `lead.reopen`) |
| 409 | `VERSION_CONFLICT` |

### 8.7 `POST /leads/{id}/assign`

> Traces: LEAD-007

`If-Match` is required. Body is `{ "assigned_to": "0192…" | null, "comment": "optional" }`. It returns `200` with the lead. Errors: `422 INVALID_ASSIGNEE` · `422 NO_OP_ASSIGNMENT`.

### 8.8 Other lead endpoints

> Traces: AUDIT-006, AUDIT-007, LEAD-010, LEAD-016, LEAD-017

| Endpoint | Request | Response |
|---|---|---|
| `DELETE /leads/{id}` | `If-Match`. Optional body `{ "reason": "Test entry" }`. | `204` |
| `POST /leads/{id}/restore` | `{}` (`If-Match`) | `200` lead. `409 DUPLICATE` never occurs (no unique business key besides number). |
| `POST /leads/{id}/duplicate-resolution` | `{ "resolution": "CONFIRMED" \| "NOT_DUPLICATE", "duplicate_of_lead_id": "…" }` | `200` lead |
| `GET /leads/duplicates?phone=&email=&exclude_id=` | — | `{ "data": [ { "id", "lead_number", "name", "status", "assigned_to", "created_on" } ] }` (actor scope) |
| `GET /leads/{id}/history?cursor=` | — | Cursor list of audit entries for the lead and its children (§10 shape) |
| `POST /leads/exports` (P1) | Same filters as the list, plus `format: "csv"` | `202 { "export_id" }` → poll `GET /leads/exports/{id}` → signed URL (15 min) |

### 8.9 `GET /leads/summary`

> Traces: LEAD-014

Params: `period=today|7d|30d|90d|custom&from=&to=`. Everything is scoped by `lead.read`.

```json
{
  "data": {
    "period": { "from": "2026-08-30T18:30:00.000Z", "to": "2026-09-29T18:30:00.000Z", "timezone": "Asia/Kolkata" },
    "pipeline": { "NEW": 12, "CONTACTED": 9, "SITE_VISIT": 5, "QUOTATION_SENT": 4, "NEGOTIATION": 3 },
    "closed_in_period": { "WON": 3, "LOST": 7 },
    "new_leads": { "count": 38, "previous_period_count": 29 },
    "unassigned_open": 4,
    "follow_ups": { "due_today": 6, "overdue": 2 },
    "conversion_rate": 0.30,
    "median_hours_to_first_contact": 3.5,
    "by_source": [ { "code": "WEBSITE", "label": "Website", "count": 21 }, { "code": "REFERRAL", "label": "Referral", "count": 9 } ],
    "needs_reassignment": 0
  }
}
```

## 9. Lead notes and activities

Every nested route first resolves the parent lead within the actor's `lead.read` scope. If the lead isn't visible, the result is `404 NOT_FOUND`.

### 9.1 Notes

> Traces: NOTE-001, NOTE-002, NOTE-004

`GET /leads/{id}/notes?page=1&page_size=50`. Default sort is pinned first, then `-created_on`.

```json
{ "data": [ { "id": "…", "lead_id": "…", "body": "Wants handle-less shutters, matte finish.", "is_pinned": true,
              "visibility": "INTERNAL", "created_by": { "id": "…", "display_name": "Priya" },
              "created_on": "2026-09-26T06:00:00.000Z", "updated_on": "2026-09-26T06:05:00.000Z",
              "is_edited": true, "can_edit": true, "can_delete": true, "version": 2 } ],
  "meta": { "page": 1, "page_size": 50, "total": 4, "total_pages": 1 } }
```

| Endpoint | Request | Response / errors |
|---|---|---|
| `POST …/notes` | `{ "body": "…", "is_pinned": false }` | `201`. `422 VISIBILITY_NOT_SUPPORTED` if `CUSTOMER_VISIBLE`. |
| `PATCH …/notes/{note_id}` | `{ "body"?, "is_pinned"? }` with `If-Match` | `200`. A note outside update scope → `403 PERMISSION_DENIED` (the note is visible, so 403 not 404). |
| `DELETE …/notes/{note_id}` | `If-Match` | `204` |

### 9.2 Activities

> Traces: ACT-001, ACT-002, ACT-003

`GET /leads/{id}/activities?type=CALL,SITE_VISIT&status=PLANNED&cursor=` (default sort `-created_on`):

```json
{ "data": [ { "id": "…", "lead_id": "…", "activity_type": "SITE_VISIT", "activity_status": "PLANNED",
              "is_system_generated": false, "subject": "Site measurement", "description": "Bring laser measure",
              "direction": null, "scheduled_on": "2026-09-30T05:30:00.000Z", "completed_on": null,
              "duration_minutes": 60, "outcome": null, "location": "Tower B, My Home Avatar, Gachibowli",
              "owner": { "id": "…", "display_name": "Priya" }, "from_status": null, "to_status": null,
              "is_overdue": false, "can_edit": true, "created_on": "…", "version": 1 },
            { "id": "…", "activity_type": "STATUS_CHANGE", "activity_status": "COMPLETED", "is_system_generated": true,
              "subject": "Status changed: Contacted → Site visit", "from_status": "CONTACTED", "to_status": "SITE_VISIT",
              "owner": { "id": "…", "display_name": "Priya" }, "completed_on": "2026-09-27T05:30:00.000Z",
              "can_edit": false, "version": 1 } ],
  "meta": { "limit": 50, "next_cursor": "…", "has_more": true } }
```

`POST …/activities`:

Log a completed call:

```json
{ "activity_type": "CALL", "activity_status": "COMPLETED", "direction": "OUTBOUND",
  "subject": "Intro call", "description": "Discussed scope and timelines", "completed_on": "2026-09-29T09:40:00.000Z",
  "duration_minutes": 12, "outcome_code": "VISIT_SCHEDULED" }
```

Plan a follow-up:

```json
{ "activity_type": "SITE_VISIT", "activity_status": "PLANNED", "subject": "Site measurement",
  "scheduled_on": "2026-09-30T05:30:00.000Z", "duration_minutes": 60,
  "location": "Tower B, My Home Avatar, Gachibowli", "owner_user_id": "0192…" }
```

- `201` returns the activity and `meta.lead_next_follow_up_on`.
- Errors:

| Status | Code |
|---|---|
| 422 | `SYSTEM_TYPE_NOT_ALLOWED` (STATUS_CHANGE/ASSIGNMENT/SYSTEM) |
| 422 | `SCHEDULE_REQUIRED` |
| 422 | `INVALID_OWNER` |
| 422 | `LEAD_CLOSED` (planning on WON/LOST leads) |

| Endpoint | Request | Notes |
|---|---|---|
| `PATCH …/activities/{aid}` | `If-Match`. `subject, description, scheduled_on, duration_minutes, location, owner_user_id` | `422 SYSTEM_ACTIVITY_READ_ONLY` on system rows |
| `POST …/{aid}/complete` | `{ "completed_on"?, "outcome_code"?, "description"?, "duration_minutes"? }` | PLANNED → COMPLETED. `422 INVALID_ACTIVITY_STATE`. |
| `POST …/{aid}/cancel` | `{ "reason": "Client rescheduled" }` | PLANNED → CANCELLED |
| `DELETE …/{aid}` | `If-Match` | Non-system only |

`GET /activities?owner=me&status=PLANNED&scheduled_to=…` is the cross-lead "my follow-ups" list, scoped by lead visibility. Each item includes `lead: { id, lead_number, name }`.

## 10. Audit logs and security events

> Traces: AUDIT-002, AUDIT-008

`GET /audit-logs`:

| Param | Values |
|---|---|
| `entity_type` | CSV |
| `entity_id` | — |
| `include_children` | `true` (with entity filter → uses parent index) |
| `action` | CSV |
| `performed_by` | User id or `system` |
| `performed_via` | — |
| `from`, `to` | Timestamps |
| `transaction_id`, `request_id` | — |
| `cursor`, `limit` | Sort fixed at `-performed_on,-id` |

```json
{ "data": [ { "id": "…", "entity_type": "lead", "entity_id": "0192a4f1…", "entity_label": "VS-L-2026-000123 · Anita Reddy",
              "action": "UPDATE", "changed_fields": ["status", "status_changed_on", "lost_on", "lost_reason_id"],
              "old_value": { "status": "NEGOTIATION", "lost_reason_id": null },
              "new_value": { "status": "LOST", "lost_reason_id": { "id": "…", "code": "CHOSE_COMPETITOR", "label": "Chose competitor" } },
              "performed_by": { "id": "…", "display_name": "Priya" }, "performed_on": "2026-09-29T10:02:11.004Z",
              "performed_via": "API", "parent_entity_type": null, "parent_entity_id": null,
              "transaction_id": "…", "request_id": "8c2f1e0a9b7d4c3e", "ip_address": "49.205.xxx.xxx", "reason": null } ],
  "meta": { "limit": 50, "next_cursor": "…", "has_more": true } }
```

- `entity_label` and lookup labels are resolved at read time. Labels of entities outside the actor's `lead.read` scope are shown as the id only.
- `GET /audit-logs/{id}` returns the full row, including `user_agent` and `session_id`.
### 10.1 `GET /security-events` (SEVT-005, SEVT-008)

- **Filters:** `subject_user_id`, `event_type`, `event_category`, `outcome`, `severity`, `ip`, `from`, `to`.
- **Pagination:** cursor, `limit` ≤ 200. Sort is fixed at `-occurred_on,-id`.
- **Scope:** with scope OWN, the server forces `subject_user_id = actor`.
- A time range is required for unfiltered queries over more than 31 days.

```json
{ "data": [ { "id": "0192a5…", "event_type": "MFA_CHALLENGE", "event_category": "MFA", "outcome": "FAILURE",
              "severity": "WARNING", "subject_user": { "id": "0192a3aa…", "display_name": "Priya" },
              "actor": { "id": "0192a3aa…", "display_name": "Priya" }, "failure_reason": "CODE_INVALID",
              "occurred_on": "2026-09-29T04:10:02.114Z", "ip_address": "49.205.xxx.xxx",
              "user_agent": "Mozilla/5.0 (Linux; Android 14) …", "request_id": "…", "detail": { "method": "totp" } } ],
  "meta": { "limit": 50, "next_cursor": "…", "has_more": true } }
```

`email_attempted_hash`, `chain_seq`, `prev_hash` and `row_hash` are never returned. Chain integrity is reported by the verification job, not exposed per row.

## 11. Error code catalog

> Traces: RBAC-014

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `MALFORMED_JSON` | Body isn't valid JSON |
| 422 | `INVALID_ID` | An id isn't canonical 32-hex UUIDv7 (ADR-002) |
| 401 | `MFA_CODE_INVALID` · `MFA_CHALLENGE_INVALID` | MFA verification failed |
| 403 | `STEP_UP_REQUIRED` | Recent MFA needed. Body includes `mfa_token`. |
| 409 | `MFA_ALREADY_ENROLLED` · `MFA_REQUIRED_BY_POLICY` | MFA state conflicts |
| 400 | `RESET_TOKEN_INVALID` / `INVITE_TOKEN_INVALID` | Unknown, used or expired token |
| 401 | `AUTH_REQUIRED` | No or invalid bearer token |
| 401 | `TOKEN_EXPIRED` | Access token expired, so the client should refresh |
| 401 | `SESSION_INVALID` | Session revoked or expired, so the client should log in again |
| 401 | `INVALID_CREDENTIALS` | Login failed |
| 403 | `PERMISSION_DENIED` | Missing permission code (`detail` names it) |
| 403 | `PASSWORD_CHANGE_REQUIRED` | Must change password first |
| 403 | `CSRF_REJECTED` | Refresh or logout without proper Origin/header |
| 403 | `ESCALATION_DENIED` · `SELF_MODIFICATION_DENIED` | RBAC guards G1–G3 |
| 404 | `NOT_FOUND` | Missing, soft-deleted or out of scope |
| 405 | `METHOD_NOT_ALLOWED` | |
| 409 | `VERSION_CONFLICT` | Stale `If-Match` |
| 409 | `DUPLICATE` | Unique business key collision (`errors[].field`) |
| 409 | `LAST_ADMINISTRATOR` · `SYSTEM_OBJECT` · `ROLE_IN_USE` · `INVALID_STATE` | Guard violations |
| 413 | `PAYLOAD_TOO_LARGE` | |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | |
| 422 | `VALIDATION_FAILED` | See `errors[]` (field codes such as `REQUIRED`, `TOO_LONG`, `INVALID_PHONE`, `INVALID_LOOKUP`, `UNKNOWN_FIELD`) |
| 422 | `INVALID_STATUS_TRANSITION` · `NO_OP_TRANSITION` · `LOST_REASON_REQUIRED` · `COMMENT_REQUIRED` | Lead state machine |
| 422 | `UNKNOWN_POLICY_VERSION` · `PASSWORD_POLICY` · `PASSWORD_REUSED` · `CAPTCHA_FAILED` · `CONSENT_REQUIRED` · `REASON_REQUIRED` · `SCOPE_NOT_SUPPORTED` · `FIELD_NOT_UPDATABLE` · `IMMUTABLE_FIELD` · `INVALID_QUERY_PARAM` · `IDEMPOTENCY_KEY_REUSED` | |
| 428 | `PRECONDITION_REQUIRED` · `IDEMPOTENCY_KEY_REQUIRED` | Missing `If-Match` or `Idempotency-Key` |
| 429 | `RATE_LIMITED` | With `Retry-After` |
| 500 | `INTERNAL_ERROR` | Includes `request_id` |
| 503 | `SERVICE_UNAVAILABLE` | Maintenance or DB busy beyond timeout. Includes `Retry-After`. |

## 12. Rate limits (application layer)

> Traces: SEC-011

These sit behind the Cloudflare limits in 02 §11. They are initial configuration values, to be tuned from measured traffic (ASM-004).

| Scope | Limit |
|---|---|
| Authenticated user, all endpoints | 600 req / 5 min |
| `POST /auth/login` | 10/min per IP · 5/min per email |
| `POST /auth/password/forgot` | 5/min per IP · 3/hour per email |
| `POST /public/leads` | 5/min per IP · 30/hour per IP |
| `POST /auth/mfa/*` | 10/min per IP · 5 attempts per challenge · 10 failures per account per 15 min |
| Exports (P1) | 5/hour per user |

Responses carry `RateLimit-Limit`, `RateLimit-Remaining` and `RateLimit-Reset`.
