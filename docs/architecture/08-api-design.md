# 08 — API Design

Governing decisions: [ADR-002](decisions/ADR-002-uuidv7-identifiers.md) · [ADR-004](decisions/ADR-004-security-event-log.md) · [ADR-005](decisions/ADR-005-lead-required-fields.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-007](decisions/ADR-007-technology-stack.md)

Every endpoint either names its permission code, or is listed in the RBAC exception register (06 §11, RBX-*). No endpoint authorizes by role name.

## 1. Endpoint index

Every row names its permission code(s), or an RBAC exception (06 §11, RBX-*). "Step-up" means G10, and "dual" means G12 dual control (06 §7). **P1** rows are designed but not built in P0 (ADR-009).

| # | Method & path | Permission / gate | Req |
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
| 8 | `PATCH /api/v1/auth/me` | `profile.update` (profile fields only) | USER-004 |
| 9 | `PUT /api/v1/auth/me/email` | own account + step-up (RBX-004) | USER-007 |
| 10 | `POST /api/v1/auth/email/verify` · `POST /api/v1/auth/email/cancel` | single-use token (RBX-003) | USER-007 |
| 11 | `POST /api/v1/auth/password/forgot` | public (RBX-003) | AUTH-008 |
| 12 | `POST /api/v1/auth/password/reset` | single-use token (RBX-003) | AUTH-008 |
| 13 | `POST /api/v1/auth/password/change` | own credentials (RBX-004) | AUTH-012 |
| 14 | `POST /api/v1/auth/invite/accept` | single-use token (RBX-003) | AUTH-011 |
| 15 | `POST /api/v1/auth/reauth` | own session (RBX-004) | MFA-011 |
| 16 | `GET /api/v1/auth/sessions` | `session.read` | AUTH-016 |
| 17 | `DELETE /api/v1/auth/sessions/{session_id}` | `session.revoke` | AUTH-016 |
| 18 | `GET /api/v1/auth/.well-known/jwks.json` | public (RBX-006) | AUTH-004 |
| 19 | `POST /api/v1/auth/mfa/verify` | challenge token (RBX-001) | MFA-001 |
| 20 | `POST /api/v1/auth/mfa/recovery` | challenge token + password + recovery code (RBX-001) | MFA-013 |
| 21 | `POST /api/v1/auth/mfa/enroll/start` · `POST /api/v1/auth/mfa/enroll/confirm` | one of the four two-proof paths in 05 §11.3 (RBX-004) | MFA-014 |
| 22 | `POST /api/v1/auth/mfa/step-up` | own session (RBX-004) | MFA-011 |
| 23 | `POST /api/v1/auth/mfa/recovery-codes` | own session + step-up, not in cooling-off (RBX-004) | MFA-005 |
| 24 | `DELETE /api/v1/auth/mfa/factor` | own session + step-up, only if policy does not require MFA (RBX-004) | MFA-003 |
| 25 | `GET /api/v1/auth/mfa` | `profile.read` | MFA-001 |
| **Users** (§5) | | | |
| 26 | `GET /api/v1/users` · `GET /api/v1/users/{user_id}` | `user.read` | USER-001 |
| 27 | `POST /api/v1/users` | `user.create` (+ `user.role.manage` if roles are given) | USER-001 |
| 28 | `PATCH /api/v1/users/{user_id}` | `user.profile.update` (profile fields only) | RBAC-019 |
| 29 | `POST /api/v1/users/{user_id}/email-change` | `user.email.change` + step-up + G9/G11 (+ dual if privileged) | USER-007 |
| 30 | `POST /api/v1/users/{user_id}/status` | `user.status.manage` + step-up + G3/G4/G9/G11 | RBAC-019 |
| 31 | `POST /api/v1/users/{user_id}/unlock` | `user.status.manage` + step-up + G9/G11 | AUTH-010 |
| 32 | `DELETE /api/v1/users/{user_id}` | `user.delete` + step-up + G3/G4/G9/G11 | USER-001 |
| 33 | `POST /api/v1/users/{user_id}/restore` | `user.restore` + G9 | USER-001 |
| 34 | `POST /api/v1/users/{user_id}/invite/resend` | `user.create` + G9 | AUTH-011 |
| 35 | `POST /api/v1/users/{user_id}/password-reset` | `user.password.reset` + G9/G11 | AUTH-008 |
| 36 | `POST /api/v1/users/{user_id}/sessions/revoke` | `user.session.revoke` + step-up + G9/G11 | AUTH-016 |
| 37 | `GET /api/v1/users/{user_id}/roles` | `user.read` | RBAC-008 |
| 38 | `PUT /api/v1/users/{user_id}/roles` | `user.role.manage` + step-up + G1–G4/G9/G11/G13 | RBAC-009 |
| 39 | `GET /api/v1/users/{user_id}/permissions` | `user.read` | RBAC-006 |
| 40 | `POST /api/v1/users/{user_id}/permissions` · `DELETE …/permissions/{grant_id}` | `user.permission.manage` + step-up + G1/G3/G4/G9/G11/G13 | RBAC-006 |
| 41 | `GET /api/v1/users/{user_id}/effective-permissions` | `user.read` + `permission.read` | RBAC-016 |
| 42 | `POST /api/v1/users/{user_id}/mfa/reset` | `user.mfa.reset` + step-up + G3/G9/G11 (+ dual if privileged) | MFA-007 |
| 43 | `PUT /api/v1/users/{user_id}/mfa-requirement` | `user.mfa.require` + step-up + G3/G9/G11 | MFA-003 |
| 44 | `GET /api/v1/users/assignable` | `lead.assign` | LEAD-007 |
| **Approvals and Founder workflow** (§5.11) | | | |
| 45 | `GET /api/v1/approvals` · `GET /api/v1/approvals/{approval_id}` | the permission of the request's action. The list is filtered to requests the caller may approve (06 §7.2.3 for Founder class, 06 §7.4 for standard) or has requested. | RBAC-021 |
| 46 | `POST /api/v1/approvals/{approval_id}/approve` · `…/deny` | the action's permission + step-up + eligibility: 06 §7.2.3 for FOUNDER class, 06 §7.4 for STANDARD | RBAC-021 |
| 47 | `POST /api/v1/approvals/{approval_id}/cancel` | requester only (the action's permission) | RBAC-021 |
| 48 | `POST /api/v1/founder-actions` | `user.founder.manage` (effective) + step-up + the canonical Founder-governance workflow (06 §7.2) | RBAC-021 |
| **Roles and permissions** (§6) | | | |
| 49 | `GET /api/v1/roles` · `GET /api/v1/roles/{role_id}` · `GET …/permissions` | `role.read` | RBAC-008 |
| 50 | `POST /api/v1/roles` · `PATCH /api/v1/roles/{role_id}` · `DELETE /api/v1/roles/{role_id}` | `role.manage` + step-up + G2/G5/G13 | RBAC-008 |
| 51 | `PUT /api/v1/roles/{role_id}/permissions` | `role.manage` + step-up + G2/G3/G4/G13 | RBAC-009 |
| 52 | `GET /api/v1/roles/{role_id}/users` | `role.read` + `user.read` | RBAC-008 |
| 53 | `GET /api/v1/permissions` · `GET /api/v1/permissions/{permission_id}` | `permission.read` | RBAC-004 |
| 54 | `PATCH /api/v1/permissions/{permission_id}` | `permission.manage` + step-up | RBAC-004 |
| 55 | `GET /api/v1/permissions/{permission_id}/holders` | `permission.read` + `user.read` | RBAC-016 |
| **Reference and notifications** (§7) | | | |
| 56 | `GET /api/v1/lookups` · `GET /api/v1/lookups/{category_code}` | `lookup.read` | PLAT-009 |
| 57 | `POST /api/v1/lookups/{category_code}/values` · `PATCH …/values/{value_id}` | `lookup.manage` | PLAT-009 |
| 58 | `GET /api/v1/notifications` · `POST …/{id}/read` · `POST …/read-all` | `notification.read` | NOTIF-001 |
| **Leads** (§8) | | | |
| 59 | `POST /api/v1/public/leads` | public, Turnstile (RBX-005) | LEAD-001 |
| 60 | `GET /api/v1/leads` | `lead.read` | LEAD-013 |
| 61 | `POST /api/v1/leads` | `lead.create` | LEAD-003 |
| 62 | `GET /api/v1/leads/{lead_id}` | `lead.read` | LEAD-013 |
| 63 | `PATCH /api/v1/leads/{lead_id}` | `lead.update` | LEAD-024 |
| 64 | `DELETE /api/v1/leads/{lead_id}` | `lead.delete` | LEAD-016 |
| 65 | `POST /api/v1/leads/{lead_id}/restore` | `lead.restore` | LEAD-016 |
| 66 | `POST /api/v1/leads/{lead_id}/status` | `lead.status.change` / `lead.reopen` | LEAD-005 |
| 67 | `POST /api/v1/leads/{lead_id}/assign` | `lead.assign` | LEAD-007 |
| 68 | `POST /api/v1/leads/{lead_id}/duplicate-resolution` | `lead.update` | LEAD-010 |
| 69 | `POST /api/v1/leads/{lead_id}/spam-resolution` | `lead.update` | LEAD-018 |
| 70 | `POST /api/v1/leads/{lead_id}/consent/withdraw` | `lead.update` | LEAD-027 |
| 71 | `POST /api/v1/leads/{lead_id}/erasure` | `lead.erase` + step-up | LEAD-029 |
| 72 | `GET /api/v1/leads/duplicates` | `lead.read` | LEAD-010 |
| 73 | `GET /api/v1/leads/summary` | `lead.read` | LEAD-014 |
| 74 | `GET /api/v1/leads/{lead_id}/history` | `lead.read` + `audit.read` | AUDIT-006 |
| 75 | `POST /api/v1/leads/exports` (**P1**) | `lead.export` + step-up | LEAD-017 |
| **Lead notes** (§9) | | | |
| 76 | `GET /api/v1/leads/{lead_id}/notes` | `lead_note.read` | NOTE-001 |
| 77 | `POST /api/v1/leads/{lead_id}/notes` | `lead_note.create` | NOTE-001 |
| 78 | `PATCH /api/v1/leads/{lead_id}/notes/{note_id}` | `lead_note.update` | NOTE-002 |
| 79 | `DELETE /api/v1/leads/{lead_id}/notes/{note_id}` | `lead_note.delete` | NOTE-002 |
| **Lead activities** (§9) | | | |
| 80 | `GET /api/v1/leads/{lead_id}/activities` | `lead_activity.read` | ACT-001 |
| 81 | `POST /api/v1/leads/{lead_id}/activities` | `lead_activity.create` | ACT-001 |
| 82 | `PATCH /api/v1/leads/{lead_id}/activities/{activity_id}` | `lead_activity.update` | ACT-002 |
| 83 | `POST …/activities/{activity_id}/complete` · `…/cancel` | `lead_activity.update` | ACT-003 |
| 84 | `DELETE /api/v1/leads/{lead_id}/activities/{activity_id}` | `lead_activity.delete` | ACT-002 |
| 85 | `GET /api/v1/activities?owner=me&status=PLANNED` | `lead_activity.read` | LEAD-015 |
| **Audit and security** (§10) | | | |
| 86 | `GET /api/v1/audit-logs` · `GET /api/v1/audit-logs/{audit_id}` | `audit.read` | AUDIT-008 |
| 87 | `GET /api/v1/security-events` · `GET /api/v1/security-events/{event_id}` | `security_event.read` (Founder, Admin; **not** Sales) | SEVT-005 |

## 2. Conventions

### 2.1 Contract (API-008)

- OpenAPI 3.1 is generated from DTO definitions and served at `/api/v1/openapi.json` (staging) or as a build artifact (production).
- The frontend generates its types from it.
- CI diffs it against `main` and fails on breaking changes (API-009).

### 2.2 Formats

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

| Pattern | Example | Meaning |
|---|---|---|
| Equality / IN | `status=NEW,CONTACTED` | Comma = OR within a field. Different fields AND. |
| Special values | `assigned_to=me` · `assigned_to=unassigned` | Resolved server-side |
| Ranges | `created_on_from=2026-09-01&created_on_to=2026-09-30` | Date-only values are calendar days in the requesting user's `timezone`. They are converted to the UTC half-open range [start of `from`, start of the day after `to`). Datetime values must carry an offset (03 §2.2, PLAT-007). |
| Boolean | `overdue=true` | Named, documented filters |
| Search | `q=priya 98480` | Tokenized, each token matched (AND) against allowlisted fields with prefix/contains. Min 2 chars per token. |
| Sort | `sort=-created_on,name` | `-` = descending. Allowlist per resource. Default is documented. The tie-breaker `id` is always appended. |
| Deleted | `include_deleted=true` / `deleted_only=true` | Requires `<resource>.restore` |

Unknown filter or sort fields → 422 `INVALID_QUERY_PARAM`. They are never silently ignored.

### 2.7 Optimistic concurrency (API-006)

- `PATCH`, `PUT` of sub-collections, `DELETE`, and action endpoints that modify a resource (`/status`, `/assign`, `/complete`) **require** `If-Match: "<version>"`.
  - Missing → `428 PRECONDITION_REQUIRED`.
  - Mismatch → `409 VERSION_CONFLICT`. The response includes `current_version` and `updated_by`/`updated_on`, so the UI can explain "Ravi updated this 2 minutes ago".
- Creates don't need it.

### 2.8 Idempotency (API-007, F-04, F-09)

| Item | Rule |
|---|---|
| Key | `Idempotency-Key`: an opaque client string, 16–64 characters from `[A-Za-z0-9_-]`. Not an entity id. **Required** on `POST /public/leads`, optional on authenticated `POST` creates. |
| Fingerprint | SHA-256 of the RFC 8785 (JCS) canonical request body, excluding transient fields (`turnstile_token`, the honeypot field) |
| Lookup order | Rate limiting → **idempotency lookup** → CAPTCHA and business processing. A replay never re-verifies a spent CAPTCHA token. |
| Same key, same fingerprint | The original status and body are returned. Nothing is re-executed. |
| Same key, different fingerprint | `422 IDEMPOTENCY_KEY_REUSED` |
| Public intake store | Durable: `lead.intake_idempotency_key` and `lead.intake_request_fingerprint` (unique key, EXC-007). No expiry. |
| Authenticated store | In-process TTL store (24 h) keyed by (actor, route, key). It is authoritative because exactly one application process runs (OPS-010). It is lost on restart, which is documented: a replay after a restart may re-execute, and the client-side double-submit guards remain. It moves to Redis with the same semantics after the PostgreSQL gate. |

### 2.9 Versioning and compatibility (API-009)

- Major version in the path (`/api/v1`).
- Within v1, changes are additive only: new endpoints, new optional request fields, new response fields, new enum values (clients must tolerate unknown enum values).
- Breaking changes go to `/api/v2`, with v1 kept ≥ 6 months, a `Deprecation` header and a `Sunset` header.

## 3. Ops endpoints

```
GET /health/live   → 200 {"status":"ok"}
GET /health/ready  → 200 {"status":"ok","checks":{"db":"ok","migrations":"head","outbox_lag_s":3}}
                   → 503 {"status":"degraded","checks":{…}}   (no data, no versions of dependencies)
```

## 4. Authentication endpoints

### 4.1 `POST /auth/login`

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
{ "data": { "status": "MFA_REQUIRED", "mfa_token": "q3Z…", "methods": ["totp"], "recovery_available": true, "expires_in": 300 } }
```

MFA required but no active factor. **No token is returned.** An enrollment link is emailed to the verified address (05 §11.3 path C):

```json
{ "data": { "status": "MFA_ENROLLMENT_EMAIL_SENT", "message": "Check your email to set up two-step verification." } }
```

Errors:

| Status | Code | When |
|---|---|---|
| 401 | `INVALID_CREDENTIALS` | Every failure reason (05 §3) |
| 422 | `VALIDATION_FAILED` | Malformed body |
| 429 | `RATE_LIMITED` | With `Retry-After` |

### 4.2 `POST /auth/refresh`

- Requires the cookie `vs_rt` and the header `X-Requested-With: veda-workspace`. The body is empty.
- `200`: `{ "data": { "access_token": "…", "token_type": "Bearer", "expires_in": 900 } }`, plus a rotated cookie.
- Errors: `401 SESSION_INVALID` (cookie cleared) · `403 CSRF_REJECTED`.

### 4.3 `POST /auth/logout` · `POST /auth/logout-all`

`204`. The cookie is cleared.

### 4.4 `GET /auth/me`

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
    "suspended_permissions": [],
    "session": { "type": "FULL", "auth_methods": ["pwd"], "mfa_verified_on": null, "cooling_off_until": null },
    "mfa": { "required": false, "required_by": [], "enrolled": false },
    "email_change": null,
    "version": 3
  }
}
```

The example is a standard Sales user. It shows **no `security_event.read`**, optional MFA, and no suspended permissions (owner Decision 1). For an Admin who hasn't yet completed MFA in this session, `suspended_permissions` lists the sensitive codes with `"reason": "MFA_REQUIRED"`.

`PATCH /auth/me` accepts **only** `full_name`, `display_name`, `phone`, `timezone` and `locale` (closed DTO, `If-Match`). `email`, `password`, `mfa_required`, `status` and roles → `422 FIELD_NOT_UPDATABLE`.

### 4.5 Password endpoints

| Endpoint | Request | Success | Errors |
|---|---|---|---|
| `POST /auth/password/forgot` | `{ "email": "…" }` | `202 { "data": { "message": "If an account exists, we've emailed a reset link." } }` | 422, 429 |
| `POST /auth/password/reset` | `{ "token": "…", "new_password": "…" }` | `204` | `400 RESET_TOKEN_INVALID` · `422 PASSWORD_POLICY` (errors[] lists rules: `TOO_SHORT`, `TOO_COMMON`, `CONTAINS_PERSONAL_INFO`) |
| `POST /auth/password/change` | `{ "current_password": "…", "new_password": "…" }` | `204` | `401 INVALID_CREDENTIALS` · `422 PASSWORD_POLICY` · `422 PASSWORD_REUSED` |
| `POST /auth/invite/accept` | `{ "token": "…", "new_password": "…", "full_name": "optional" }` | `204` | `400 INVITE_TOKEN_INVALID` · `422 PASSWORD_POLICY` |

### 4.6 Sessions (see also 4.7 MFA)

`GET /auth/sessions` returns:

```json
{ "data": [ { "id": "0192…", "device_label": "Chrome on Android", "ip_city": "Hyderabad, IN",
              "started_on": "2026-09-28T04:10:00.000Z", "last_seen_on": "2026-09-29T09:58:12.000Z", "current": true } ],
  "meta": { "limit": 50, "next_cursor": null, "has_more": false } }
```

`DELETE /auth/sessions/{id}` → `204` · `404 NOT_FOUND` (not own).

### 4.7 MFA endpoints (ADR-006)

| Endpoint | Request | Success | Errors |
|---|---|---|---|
| `POST /auth/mfa/verify` | `{ "mfa_token": "…", "code": "123456" }` | `200` AUTHENTICATED shape (§4.1) + cookie. FULL session with `pwd+totp`. | `401 MFA_CODE_INVALID` · `401 MFA_CHALLENGE_INVALID` · `429` |
| `POST /auth/mfa/recovery` | `{ "mfa_token": "…", "password": "…", "recovery_code": "K7M3Q-9TDXR" }`. **Password re-entry and a recovery code are both required.** | `200 { "data": { "status": "RECOVERY_SESSION", "access_token": "…", "expires_in": 900, "allowed": ["GET /auth/me", "POST /auth/mfa/enroll/start", "POST /auth/mfa/enroll/confirm", "POST /auth/logout"] } }`. **No refresh cookie.** All other sessions are revoked, and a notification is sent to the verified email. | `401 MFA_RECOVERY_INVALID` (uniform for a bad password or code) · `429` |
| `POST /auth/reauth` | `{ "password": "…" }` | `204`. Sets `reauth_on` (valid 5 min). | `401 INVALID_CREDENTIALS` |
| `POST /auth/mfa/enroll/start` | **Exactly one** of: `{ "reauth": true }` (FULL session; `reauth_on` within 5 min, or step-up if a factor exists: path A) · `{ "invite_context": "…" }` (inside invite acceptance: path B) · `{ "enrollment_token": "…", "password": "…" }` (emailed link: path C) · `{}` in a RECOVERY session (path D) | `200 { "data": { "otpauth_uri": "otpauth://totp/Veda%20Spaces:priya%40vedaspaces.com?secret=<BASE32-SECRET-SHOWN-ONCE>&issuer=Veda%20Spaces", "secret": "<BASE32-SECRET-SHOWN-ONCE>", "challenge_token": "…", "expires_in": 900 } }`. The secret is returned **only here, once** (A-10: the placeholder is shown). | `401 ENROLLMENT_PROOF_INVALID` · `403 STEP_UP_REQUIRED` · `409 MFA_ALREADY_ENROLLED` (path A without replacement intent) |
| `POST /auth/mfa/enroll/confirm` | `{ "challenge_token": "…", "code": "123456", "label": "Priya's phone" }` | `200` AUTHENTICATED shape + `"recovery_codes": [10 codes]` (**shown once**) + `"cooling_off_until"` (path D only). Previous factor and codes revoked. | `401 MFA_CODE_INVALID` |
| `POST /auth/mfa/step-up` | `{ "mfa_token": "…", "code": "123456" }` (token from `STEP_UP_REQUIRED`) | `204`. Sets `mfa_verified_on`. | `401 MFA_CODE_INVALID` |
| `POST /auth/mfa/recovery-codes` | `{}` (step-up) | `200 { "data": { "recovery_codes": [ … ] } }`. The previous batch is invalidated. | `403 STEP_UP_REQUIRED` · `403 COOLING_OFF` |
| `DELETE /auth/mfa/factor` | step-up | `204`. Sensitive permissions are suspended (if any). | `409 MFA_REQUIRED_BY_POLICY` · `403 STEP_UP_REQUIRED` · `403 COOLING_OFF` |
| `GET /auth/mfa` | — | `200 { "data": { "required": true, "required_by": ["ROLE_POLICY"], "factor": { "type": "TOTP", "label": "…", "confirmed_on": "…", "last_used_on": "…" }, "recovery_codes_remaining": 8, "cooling_off_until": null } }` | — |

- There is no endpoint where a password alone or a recovery code alone yields a new authenticator (MFA-014).
- `STEP_UP_REQUIRED` bodies include `"kind": "mfa" | "password"` and, for `mfa`, an `mfa_token`.
- Any call from a RECOVERY session outside `allowed` returns `403 RECOVERY_SESSION_RESTRICTED`.

### 4.8 Self-service email change (USER-007, 05 §8.6)

| Endpoint | Request | Success | Errors |
|---|---|---|---|
| `PUT /auth/me/email` | `{ "new_email": "priya.s@vedaspaces.com" }` (step-up: MFA if enrolled, else `POST /auth/reauth`) | `202 { "data": { "status": "VERIFICATION_SENT", "proposed_email": "p***@vedaspaces.com", "expires_on": "…" } }`. The verified email is unchanged. | `403 STEP_UP_REQUIRED` · `403 COOLING_OFF` · `409 DUPLICATE` · `422 INVALID_EMAIL` · `422 SAME_AS_CURRENT` |
| `POST /auth/email/verify` | `{ "token": "…" }` | `204`. The email is replaced, and all sessions are revoked (sign in again). | `400 EMAIL_TOKEN_INVALID` · `409 DUPLICATE` (address taken meanwhile) |
| `POST /auth/email/cancel` | `{ "token": "…" }` (from the alert sent to the current address) | `204`. The proposal is cleared. | `400 EMAIL_TOKEN_INVALID` |

`GET /auth/me` shows a pending change as `"email_change": { "proposed_email": "p***@…", "requested_on": "…", "expires_on": "…" }`.

## 5. Users

Security-sensitive user attributes are changed **only** through dedicated endpoints with their own permissions and guards (ADR-010, RBAC-019). No generic endpoint can mass-assign them (§5.4).

### 5.1 `GET /users`

- **Filters:** `q` · `status` · `role_id` · `protection_level` · `mfa=enrolled|required_not_enrolled|none` · `include_deleted`
- **Sort:** `full_name`, `-created_on`, `-last_login_on`

```json
{
  "data": [
    { "id": "0192a3aa…", "email": "priya@vedaspaces.com", "email_change_pending": false, "full_name": "Priya Sharma",
      "display_name": "Priya", "status": "ACTIVE", "protection_level": "STANDARD", "is_privileged": false,
      "roles": [ { "id": "…", "code": "SALES", "name": "Sales" } ],
      "mfa": { "required": false, "enrolled": true },
      "last_login_on": "2026-09-29T04:10:00.000Z", "created_on": "2026-09-01T06:00:00.000Z", "is_deleted": false, "version": 3 }
  ],
  "meta": { "page": 1, "page_size": 25, "total": 6, "total_pages": 1 },
  "links": { "self": "/api/v1/users?page=1&page_size=25", "next": null, "prev": null }
}
```

`is_privileged` = holds any sensitive permission, including suspended ones. It is computed, not stored.

### 5.2 `POST /users` (invite)

```json
{ "email": "ravi@vedaspaces.com", "full_name": "Ravi Kumar", "phone": "+919111111111", "timezone": "Asia/Kolkata", "role_ids": ["0192…"] }
```

- `201` with the user (INVITED). The invite expires in 72 h, or 24 h if the roles contain a sensitive permission (A-05).
- Errors: `409 DUPLICATE` · `403 ESCALATION_DENIED` · `403 PERMISSION_DENIED` (roles without `user.role.manage`).
- The request cannot set `protection_level`, `mfa_required` or `status`.

### 5.3 `GET /users/{id}`

Returns the list item plus `phone`, `timezone`, `locale`, `email_verified_on`, `email_change` (masked proposal, if pending), `security_cooling_off_until`, `throttled_until`, `must_change_password`, `pending_approvals`, and the audit fields.

### 5.4 `PATCH /users/{id}`: profile fields only (RBAC-019, owner Decision 3)

| Aspect | Rule |
|---|---|
| Permission | `user.profile.update`, with `If-Match` |
| Closed DTO: the **only** accepted fields | `full_name`, `display_name`, `phone`, `timezone`, `locale` |
| `email`, `proposed_email`, `password`, `status`, `roles`, `permissions`, `mfa_required`, `protection_level`, `is_founder` | → `422 FIELD_NOT_UPDATABLE`. Each has its own workflow. |
| Anything else | → `422 UNKNOWN_FIELD` |
| Self | Allowed only through `PATCH /auth/me` |

This is verified by the mass-assignment tests (12 §4.4).

### 5.5 Email change for another user (USER-007)

`POST /users/{id}/email-change { "new_email": "…", "reason": "…" }` (`user.email.change`, step-up, G3, G9, G11, `If-Match`):

| Target | Result |
|---|---|
| Non-privileged | `202 { "status": "VERIFICATION_SENT" }`. Same workflow as 05 §8.6: the proposed address must verify, and the current address receives an alert with a cancel link. |
| Privileged (holds any sensitive permission) | `202 { "status": "APPROVAL_REQUIRED", "approval_id": "…" }`. The proposal is created only after approval (G12). |
| FOUNDER-protected | `403 FOUNDER_PROTECTED`. Use `POST /founder-actions` with `FOUNDER_EMAIL_CHANGE`. |

- An administrator can **never** set the verified email directly.
- Errors: `403 SELF_MODIFICATION_DENIED` · `403 ESCALATION_DENIED` · `403 STEP_UP_REQUIRED` · `409 DUPLICATE` · `422 REASON_REQUIRED`.

### 5.6 Account status (RBAC-019, RBAC-020)

| Endpoint | Body | Effect | Errors |
|---|---|---|---|
| `POST /users/{id}/status` | `{ "status": "DISABLED" \| "ACTIVE", "reason": "…" }` (`If-Match`) | DISABLED revokes all sessions and invalidates tokens, challenges and pending proposals. ACTIVE restores sign-in (INVITED if never accepted). | `403 SELF_MODIFICATION_DENIED` (own account) · `403 ESCALATION_DENIED` (G9) · `403 FOUNDER_PROTECTED` (G11) · `409 LAST_FOUNDER` / `409 LAST_ADMINISTRATOR` (G4) · `403 STEP_UP_REQUIRED` |
| `POST /users/{id}/unlock` | `{}` | Clears the global throttle | G9 |
| `DELETE /users/{id}` | `If-Match`, `{ "reason": "…" }` | Soft delete + DISABLED effects | Same as status |
| `POST /users/{id}/restore` | `{}` | Restored as DISABLED | `409 DUPLICATE` · G9 |
| `POST /users/{id}/invite/resend` | `{}` | New INVITE token | `409 INVALID_STATE` · G9 |
| `POST /users/{id}/password-reset` | `{}` | Reset link to the **verified** email | G9 · G11 |
| `POST /users/{id}/sessions/revoke` | `{ "reason": "…" }` | Revoke all | G9 · G11 · step-up |

### 5.7 Role assignment: `PUT /users/{id}/roles` (`user.role.manage`)

```json
{ "roles": [ { "role_id": "0192…sales" } ], "reason": "Joined sales team" }
```

- `200` with the user_role items.
- Errors: G1–G4, G9, G11, step-up. `valid_from` / `valid_until` → `422 TIME_BOUND_GRANTS_NOT_ENABLED` (RBAC-007 is P1).
- Assigning a role that contains sensitive permissions to a user without MFA succeeds. Those permissions are returned as `"pending_mfa": true` and stay suspended until enrollment (MFA-012).
- **Founder governance (G13).** Adding or removing a role with `grant_path = FOUNDER_WORKFLOW_ONLY` (the FOUNDER role) → `403 FOUNDER_GOVERNANCE_REQUIRED` plus a `FOUNDER_GOVERNANCE_BYPASS_BLOCKED` event. The same applies to any change to a Founder's roles (G11). Use `POST /founder-actions`.

### 5.8 Direct permissions (`user.permission.manage`)

`POST /users/{id}/permissions { "permission_code": "lead.read", "effect": "GRANT", "scope": "ALL", "reason": "…" }`

- `201`.
- Errors: `422 REASON_REQUIRED` · `422 SCOPE_NOT_SUPPORTED` · `422 TIME_BOUND_GRANTS_NOT_ENABLED` · `403 ESCALATION_DENIED` · `409 DUPLICATE` · `409 LAST_ADMINISTRATOR` (for a DENY that breaks I2).
- `DELETE …/permissions/{grant_id}` → `204`.
- **Founder governance (G13).** A GRANT **or DENY** of any `FOUNDER_WORKFLOW_ONLY` permission (`user.founder.manage`), and deletion of such a row → `403 FOUNDER_GOVERNANCE_REQUIRED`.

### 5.9 `GET /users/{id}/effective-permissions` (RBAC-016, P0)

```json
{ "data": { "authz_version": 9, "mfa": { "enrolled": false, "required": true, "required_by": ["SENSITIVE_PERMISSION"] },
  "permissions": [
    { "code": "lead.read", "scope": "ALL", "status": "EFFECTIVE", "sources": [ { "type": "ROLE", "role_code": "ADMIN", "scope": "ALL" } ] },
    { "code": "user.role.manage", "scope": "ALL", "status": "SUSPENDED", "suspended_reason": "MFA_REQUIRED",
      "sources": [ { "type": "ROLE", "role_code": "ADMIN", "scope": "ALL" } ] },
    { "code": "lead.export", "status": "DENIED", "sources": [ { "type": "USER_DENY", "grant_id": "0192…", "reason": "Policy" } ] } ] } }
```

### 5.10 User MFA administration (MFA-003, MFA-007, MFA-015)

| Endpoint | Request | Success | Errors |
|---|---|---|---|
| `POST /users/{id}/mfa/reset` | `{ "reason": "Lost phone; identity verified by video call" }` (`If-Match`, step-up) | Non-privileged target: `204` executed. Privileged target: `202 { "status": "APPROVAL_REQUIRED", "approval_id": "…" }`. On execution: factors revoked, codes invalidated, sessions revoked, enrollment link emailed to the **target's verified address**. | `403 SELF_MODIFICATION_DENIED` · `403 ESCALATION_DENIED` · `403 FOUNDER_PROTECTED` · `403 STEP_UP_REQUIRED` · `422 REASON_REQUIRED` |
| `PUT /users/{id}/mfa-requirement` | `{ "mfa_required": true, "reason": "…" }` (`If-Match`, step-up) | `200` user | `403 SELF_MODIFICATION_DENIED` · G9 |

### 5.11 Approvals and Founder actions (RBAC-021)

| Endpoint | Request | Success | Errors |
|---|---|---|---|
| `GET /approvals?status=PENDING&role=approver\|requester` | — | Requests the caller may decide or has made. Target email masked. | — |
| `POST /approvals/{id}/approve` | `{ "reason": "Verified with Priya on call" }` (step-up) | `200`. Eligibility of **both** principals is re-checked, and the action executes in the same transaction under the write lock. Status becomes EXECUTED, or FAILED with a `status_reason`. | `403 APPROVER_NOT_ELIGIBLE` (is the requester, is the target, fails G9, or, for FOUNDER class, is not a Founder with effective `user.founder.manage` per 06 §7.2.3) · `409 INVALID_STATE` (already approved, denied, expired or cancelled, which also covers a second approver) · `409 LAST_FOUNDER` · `403 STEP_UP_REQUIRED` |
| `POST /approvals/{id}/deny` | `{ "reason": "…" }` (step-up) | `200` DENIED | Same |
| `POST /approvals/{id}/cancel` | `{}` (requester) | `200` CANCELLED | `409 INVALID_STATE` |
| `POST /founder-actions` | `{ "action": "GRANT_FOUNDER" \| "REVOKE_FOUNDER" \| "FOUNDER_MFA_RESET" \| "FOUNDER_STATUS_CHANGE" \| "FOUNDER_EMAIL_CHANGE", "target_user_id": "…", "reason": "…", "status": "only for status change", "new_email": "only for email change", "post_roles": "optional for REVOKE_FOUNDER" }` (requester eligibility per 06 §7.2.3, step-up) | Steady state: `202 { "approval_id": "…", "channel": "IN_APP" }`. **Single-Founder mode:** `202 { "approval_id": "…", "channel": "BREAK_GLASS", "not_before": "…" }`, where the second principal is a custodian (06 §7.2.4, §7.5). | `403 APPROVER_NOT_ELIGIBLE` (requester ineligible) · `403 SELF_MODIFICATION_DENIED` (self as target, except REVOKE_FOUNDER step-down) · `409 REQUEST_ALREADY_OPEN` (open Founder-level request for this target) · `409 LAST_FOUNDER` · `422 REASON_REQUIRED` |

### 5.12 `GET /users/assignable`

This returns active HUMAN users holding `lead.read`: `[{ "id", "display_name", "open_lead_count" }]`.

## 6. Roles and permissions

### 6.1 Roles

`GET /roles` returns:

```json
{ "data": [ { "id": "…", "code": "SALES", "name": "Sales", "description": "Sales & design consultants",
              "is_system": true, "is_assignable": true, "user_count": 4, "permission_count": 18, "version": 2 } ],
  "meta": { "page": 1, "page_size": 25, "total": 3, "total_pages": 1 }, "links": { … } }
```

| Endpoint | Request | Response / errors |
|---|---|---|
| `POST /roles` | `{ "code": "SALES_MANAGER", "name": "Sales Manager", "description": "…", "copy_from_role_id": "optional" }` | `201`. `409 DUPLICATE` (code, or case-insensitive name). `403 ESCALATION_DENIED` if the copied role contains permissions the actor doesn't hold (G2, A-06). |
| `PATCH /roles/{id}` | `{ "name", "description", "is_assignable" }` with `If-Match` | `code` is immutable (`422 IMMUTABLE_FIELD`) |
| `DELETE /roles/{id}` | — | `409 SYSTEM_OBJECT` · `409 ROLE_IN_USE` (has live assignments; unassign first) |

**Founder governance (G13).** `PATCH`, `DELETE` or `PUT …/permissions` on a role with `grant_path = FOUNDER_WORKFLOW_ONLY`, adding a `FOUNDER_WORKFLOW_ONLY` permission to any role, and `POST /roles` with `copy_from_role_id` of such a role → `403 FOUNDER_GOVERNANCE_REQUIRED`. FOUNDER role definition changes arrive only by migration (06 §7.2.2 `FOUNDER_POLICY_CHANGE`).

`PUT /roles/{id}/permissions` is a declarative full replace:

```json
{ "permissions": [ { "permission_code": "lead.read", "scope": "ALL" },
                   { "permission_code": "lead.assign", "scope": "ALL" } ],
  "reason": "Create sales manager role" }
```

`200` returns a grants list with diff counts `{ "added": 2, "removed": 0, "changed": 0 }`. Errors: G2, G4, G6, G8.

### 6.2 Permissions

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
    "duplicate_status": "NONE", "duplicate_of": null, "spam_status": "NONE",
    "consent": { "contact": true, "policy_version": "2026-09-v1", "captured_on": "2026-09-25T14:02:00.000Z",
                 "channel": "WEBSITE_FORM", "source_page": "/#contact", "ip_address": "49.205.xxx.xxx",
                 "withdrawn_on": null, "withdrawal_channel": null },
    "intake_unmapped": null,
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
| `spam_status` | `SUSPECTED`, `CONFIRMED_SPAM`, `NOT_SPAM`. By default, lists exclude SUSPECTED and CONFIRMED_SPAM (spam review queue, 04 §5.5). |
| `consent` | `withdrawn` (Do-not-contact list) |
| `include_deleted`, `deleted_only` | Needs `lead.restore` |
| `sort` | `created_on`, `status_changed_on`, `next_follow_up_on`, `name`, `priority` (±). Default `-created_on`. |
| `page`, `page_size` | |

The list items are a compact projection: `id, lead_number, name, phone, city, locality, project_type, budget_range, status, priority, source, assigned_to, next_follow_up_on, is_follow_up_overdue, duplicate_status, created_on, version`.

### 8.3 `POST /leads` (manual)

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

Headers: `Idempotency-Key: 5f0c2b1e-9d7a-4c3f-8e6b-5a4d3c2b1a09` · `Origin: https://www.vedaspaces.com`

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
  "property_type_code": "APARTMENT",
  "message": "3BHK handover in December…",

  "attribution": { "utm_source": "instagram", "utm_medium": "paid", "utm_campaign": "diwali-2026",
                   "utm_term": null, "utm_content": null,
                   "landing_page": "/?utm_source=instagram", "referrer_url": "https://l.instagram.com/", "form_page": "/#contact" },
  "turnstile_token": "0.AbCd…",
  "company_website_url": ""
}
```

| Field | Required | Notes |
|---|---|---|
| `name`, `phone`, `consent.acknowledged` (= true), `consent.policy_version` | Yes | ADR-005 |
| `email`, `city`, `project_type_code`, `budget_range_code`, `property_type_code`, `message` | No | May be enriched by staff later (LEAD-024). `property_type_code` ∈ APARTMENT, INDEPENDENT_HOUSE, VILLA, OFFICE, RETAIL, OTHER (owner Decision 4). Unknown or inactive optional codes are **not** errors: the value is stored in `intake_unmapped` and the field left empty (LEAD-030). |
| `attribution`, `turnstile_token`, `company_website_url` (honeypot, must be empty) | Machine-supplied | Not user-entered data. Honeypot markup per 04 §5.1. |

**`201`: the complete response.** No other fields are ever returned (LEAD-025):

```json
{ "data": { "reference": "K7M3-Q9TD", "message": "Thank you. Our design team will call you within one working day." } }
```

Errors:

| Status | Code | Body |
|---|---|---|
| 422 | `VALIDATION_FAILED` | `errors[]` with `REQUIRED`, `INVALID_PHONE`, `INVALID_EMAIL`, `TOO_LONG`, `UNKNOWN_FIELD` (never `INVALID_LOOKUP` for optional codes) |
| 422 | `IDEMPOTENCY_KEY_REUSED` | Same key, different request fingerprint (§2.8) |
| 422 | `CONSENT_REQUIRED` · `UNKNOWN_POLICY_VERSION` | |
| 422 | `CAPTCHA_FAILED` | |
| 428 | `IDEMPOTENCY_KEY_REQUIRED` | |
| 429 | `RATE_LIMITED` | With `Retry-After` |
| 413 | `PAYLOAD_TOO_LARGE` | |
| 5xx | `INTERNAL_ERROR` / `SERVICE_UNAVAILABLE` | The website then falls back to WhatsApp (LEAD-019) |

- Error bodies contain only the problem fields and `request_id`. They never contain internal lead data or state.
- **Honeypot hit:** the **same `201` shape** with a real reference. The lead is stored with `spam_status = SUSPECTED` for staff review (04 §5.1, §5.5), so nothing is silently dropped (F-05) and bots can't distinguish the trap (A-14).
- **Idempotent replay** (same key and fingerprint): the original `201` body unchanged. It is checked **before** CAPTCHA, so a genuine retry with a spent Turnstile token still succeeds (F-04).
- **Website handling:** see the non-success table in 04 §5.1. Every non-2xx except field-level 422 offers the WhatsApp path.

### 8.5 `PATCH /leads/{id}`

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

`If-Match` is required. Body is `{ "assigned_to": "0192…" | null, "comment": "optional" }`. It returns `200` with the lead. Errors: `422 INVALID_ASSIGNEE` · `422 NO_OP_ASSIGNMENT`.

### 8.8 Other lead endpoints

| Endpoint | Request | Response |
|---|---|---|
| `DELETE /leads/{id}` | `If-Match`. Optional body `{ "reason": "Test entry" }`. | `204` |
| `POST /leads/{id}/restore` | `{}` (`If-Match`) | `200` lead. `409 DUPLICATE` never occurs (no unique business key besides number). |
| `POST /leads/{id}/duplicate-resolution` | `{ "resolution": "CONFIRMED" \| "NOT_DUPLICATE", "duplicate_of_lead_id": "…" }` | `200` lead. A `duplicate_of_lead_id` outside the actor's scope → `404 NOT_FOUND`, identical to a missing lead (A-07). |
| `POST /leads/{id}/spam-resolution` | `{ "resolution": "NOT_SPAM" \| "CONFIRMED_SPAM" }` (`If-Match`) | `200` lead. NOT_SPAM emits `lead.created`. |
| `POST /leads/{id}/consent/withdraw` | `{ "channel": "PHONE_VERBAL", "note": "Asked not to be contacted" }` (`If-Match`) | `200` lead. Planned contact activities are cancelled (04 §5.4). |
| `POST /leads/{id}/erasure` | `{ "request_ref": "DPR-2026-004", "legal_basis": "DPDP s.12 erasure", "reason": "…" }` (`lead.erase`, step-up, `If-Match`) | `200` anonymized lead with `"erasure": { "audit_status": "PENDING" }`. It becomes `COMPLETED` when the maintenance job has anonymized the audit payloads (04 §14.2). `422 ERASURE_BLOCKED` with the basis when retention applies. |
| `GET /leads/duplicates?phone=&email=&exclude_id=` | — | `{ "data": [ { "id", "lead_number", "name", "status", "assigned_to", "created_on" } ] }` (actor scope) |
| `GET /leads/{id}/history?cursor=` | — | Cursor list of audit entries for the lead and its children (§10 shape) |
| `POST /leads/exports` (P1) | Same filters as the list, plus `format: "csv"` | `202 { "export_id" }` → poll `GET /leads/exports/{id}` → signed URL (15 min) |

### 8.9 `GET /leads/summary`

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
| `DELETE …/notes/{note_id}` | `If-Match` | `204`. Soft delete after a UI confirmation. **There is no Undo and no note-restore endpoint** (F-20). |

All note and activity endpoints return `404 NOT_FOUND` when the parent lead is soft-deleted or out of scope.

### 9.2 Activities

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

`email_attempted_hash`, `chain_seq`, `prev_hash`, `chain_key_label` and `row_hash` are never returned. Chain integrity is reported by the verification job, not exposed per row.

**Access (owner Decision 1).** Requires `security_event.read`, held by Founder and Admin only and effective only in MFA-verified sessions. **A standard Sales user receives `403 PERMISSION_DENIED`** for every security-events request, including `subject_user_id` = self. There is no OWN scope. Each allowed read writes a de-duplicated `SENSITIVE_READ` event (06 §3.2).

## 11. Error code catalog

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `MALFORMED_JSON` | Body isn't valid JSON |
| 422 | `INVALID_ID` | An id isn't canonical 32-hex UUIDv7 (ADR-002) |
| 422 | `INVALID_DATETIME` | A datetime without an offset (03 §2.2) |
| 401 | `MFA_CODE_INVALID` · `MFA_CHALLENGE_INVALID` · `MFA_RECOVERY_INVALID` · `ENROLLMENT_PROOF_INVALID` | MFA verification, recovery or enrollment proof failed |
| 403 | `STEP_UP_REQUIRED` | Recent MFA or password re-entry needed. Body: `kind`, and `mfa_token` for MFA. |
| 403 | `RECOVERY_SESSION_RESTRICTED` | A RECOVERY session called a non-allow-listed endpoint |
| 403 | `COOLING_OFF` | Post-recovery cooling-off blocks this change (05 §11.5) |
| 403 | `FOUNDER_PROTECTED` · `FOUNDER_GOVERNANCE_REQUIRED` · `APPROVER_NOT_ELIGIBLE` | Guards G11/G12/G13 and Founder governance (06 §7) |
| 409 | `REQUEST_ALREADY_OPEN` · `FOUNDER_STATE_INCONSISTENT` | Founder-governance concurrency and I3 (06 §7.2.5, §7.3) |
| 202 | `APPROVAL_REQUIRED` | Not an error: the action was queued for dual control (returned in the body `status`) |
| 409 | `MFA_ALREADY_ENROLLED` · `MFA_REQUIRED_BY_POLICY` | MFA state conflicts |
| 400 | `RESET_TOKEN_INVALID` · `INVITE_TOKEN_INVALID` · `EMAIL_TOKEN_INVALID` | Unknown, used or expired token |
| 401 | `AUTH_REQUIRED` | No or invalid bearer token |
| 401 | `TOKEN_EXPIRED` | Access token expired, so the client should refresh |
| 401 | `SESSION_INVALID` | Session revoked or expired, so the client should log in again |
| 401 | `INVALID_CREDENTIALS` | Login failed |
| 403 | `PERMISSION_DENIED` | Missing or suspended permission code. `detail` names it. For suspended codes, `reason` is `MFA_REQUIRED`. |
| 403 | `PASSWORD_CHANGE_REQUIRED` | Must change password first |
| 403 | `CSRF_REJECTED` | Refresh or logout without proper Origin/header |
| 403 | `ESCALATION_DENIED` · `SELF_MODIFICATION_DENIED` | RBAC guards G1–G3 |
| 404 | `NOT_FOUND` | Missing, soft-deleted or out of scope |
| 405 | `METHOD_NOT_ALLOWED` | |
| 409 | `VERSION_CONFLICT` | Stale `If-Match` |
| 409 | `DUPLICATE` | Unique business key collision (`errors[].field`) |
| 409 | `LAST_ADMINISTRATOR` · `LAST_FOUNDER` · `SYSTEM_OBJECT` · `ROLE_IN_USE` · `INVALID_STATE` | Guard violations |
| 413 | `PAYLOAD_TOO_LARGE` | |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | |
| 422 | `VALIDATION_FAILED` | See `errors[]` (field codes such as `REQUIRED`, `TOO_LONG`, `INVALID_PHONE`, `INVALID_LOOKUP`, `UNKNOWN_FIELD`) |
| 422 | `INVALID_STATUS_TRANSITION` · `NO_OP_TRANSITION` · `LOST_REASON_REQUIRED` · `COMMENT_REQUIRED` | Lead state machine |
| 422 | `SAME_AS_CURRENT` · `CONSENT_WITHDRAWN` · `ERASURE_BLOCKED` · `TIME_BOUND_GRANTS_NOT_ENABLED` | Workflow rules (05 §8.6, 04 §5.4, §14, 06 §5) |
| 422 | `UNKNOWN_POLICY_VERSION` · `PASSWORD_POLICY` · `PASSWORD_REUSED` · `CAPTCHA_FAILED` · `CONSENT_REQUIRED` · `REASON_REQUIRED` · `SCOPE_NOT_SUPPORTED` · `FIELD_NOT_UPDATABLE` · `IMMUTABLE_FIELD` · `INVALID_QUERY_PARAM` · `IDEMPOTENCY_KEY_REUSED` | |
| 428 | `PRECONDITION_REQUIRED` · `IDEMPOTENCY_KEY_REQUIRED` | Missing `If-Match` or `Idempotency-Key` |
| 429 | `RATE_LIMITED` | With `Retry-After` |
| 500 | `INTERNAL_ERROR` | Includes `request_id` |
| 503 | `SERVICE_UNAVAILABLE` | Maintenance or DB busy beyond timeout. Includes `Retry-After`. |

## 12. Rate limits (application layer)

These sit behind the Cloudflare limits in 02 §11. They are initial configuration values, to be tuned from measured traffic (ASM-004).

| Scope | Limit |
|---|---|
| Authenticated user, all endpoints | 600 req / 5 min |
| `POST /auth/login` | 10/min per IP · 5/min per email |
| `POST /auth/password/forgot` | 5/min per IP · 3/hour per email |
| `POST /public/leads` | 20/min per IP · 120/hour per IP. Relaxed for carrier-grade NAT on Indian mobile networks (F-05). Turnstile is the primary bot control. Blocked requests are offered the WhatsApp path. |
| `POST /auth/mfa/*` | 10/min per IP · 5 attempts per challenge · 10 failures per account per 15 min |
| `POST /auth/login` failures | Per (account, network) throttling and distributed-guessing throttle (05 §4) |
| Store | The single-process limiter (OPS-010). Limits are exact, not multiplied by worker count (F-09). |
| Exports (P1) | 5/hour per user |

Responses carry `RateLimit-Limit`, `RateLimit-Remaining` and `RateLimit-Reset`.
