# 02 — Platform Architecture

Governing decisions: [ADR-001](decisions/ADR-001-app-user-table.md) · [ADR-002](decisions/ADR-002-uuidv7-identifiers.md) · [ADR-003](decisions/ADR-003-audit-contract.md) · [ADR-004](decisions/ADR-004-security-event-log.md) · [ADR-007](decisions/ADR-007-technology-stack.md) · [ADR-008](decisions/ADR-008-aws-hosting.md) · [ADR-009](decisions/ADR-009-p0-scope.md)

## 1. System context

```
                         ┌──────────────────────────── Cloudflare edge ────────────────────────────┐
                         │  DNS · TLS · WAF · DDoS · Rate limiting · Turnstile · Cache            │
                         │                                                                         │
  Prospect (browser) ───►│  www.vedaspaces.com   Cloudflare Pages  (marketing site, static, dist/) │
                         │        │  enquiry form POST                                             │
                         │        ▼                                                                │
  Staff (browser/phone) ►│  app.vedaspaces.com   Cloudflare Pages  (Veda Workspace, Lit SPA)       │
                         │        │  fetch() Bearer JWT + refresh cookie                           │
                         │        ▼                                                                │
                         │  api.vedaspaces.com   proxied (orange-cloud) → origin                   │
                         └────────┬────────────────────────────────────────────────────────────────┘
                                  │  HTTPS, Authenticated Origin Pulls (mTLS), CF IPs only
                                  ▼
                 ┌────────────────── AWS ap-south-1 (Mumbai) ──────────────────┐
                 │  VM / container host                                        │
                 │  ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐  │
                 │  │ Flask API    │   │ Outbox worker│   │ Scheduler (cron)│  │
                 │  │ (gunicorn)   │   │ (same image) │   │ (same image)    │  │
                 │  └──────┬───────┘   └──────┬───────┘   └───────┬─────────┘  │
                 │         └───────────┬──────┴───────────────────┘            │
                 │                     ▼                                       │
                 │         SQLite (WAL) on encrypted EBS volume                │
                 │                     │  Litestream (continuous)              │
                 │                     ▼                                       │
                 │               S3 (versioned, SSE-KMS)                       │
                 │  SSM Parameter Store / Secrets Manager  ·  CloudWatch Logs  │
                 └─────────────────────────────────────────────────────────────┘
                                  │
                 External: Amazon SES (dev/test: logging adapter) · Sentry · Turnstile verify API · AWS KMS (MFA secrets)

  SQLite is authoritative ⇒ exactly ONE active application instance (ADR-008). No horizontal scaling is claimed or configured
  until the PostgreSQL release gate (§8.1, 11 §3.3) is passed.
```

Three hostnames with three concerns:

| Host | Purpose | Indexable | Auth |
|---|---|---|---|
| `www.vedaspaces.com` | Marketing site (existing, unchanged except the form) | Yes | None |
| `app.vedaspaces.com` | Internal staff application | No (`X-Robots-Tag: noindex`) | Required |
| `api.vedaspaces.com` | REST API | No | Bearer JWT; public intake endpoint is anonymous and Turnstile-gated |

All three share the registrable domain `vedaspaces.com`. So the refresh cookie on `api.` counts as **same-site** for requests from `app.`, and `SameSite=Strict` works (see 05 §6).

## 2. Frontend architecture (Lit)

### 2.1 Decisions

> Traces: PLAT-002

| Concern | Choice | Notes |
|---|---|---|
| Component model | Lit 3 web components | Brief mandate |
| Language | TypeScript (ADR-007), compiled to ES2020 | Typed API contracts generated from OpenAPI (API-008) |
| Build | Vite | Output is static files. Deployed as its own Cloudflare Pages project. |
| Routing | Vaadin Router with lazy route chunks | Each module's routes load on demand |
| State | `@lit/context` for app-wide state (session, effective permissions, lookups) plus per-feature stores exposed as Reactive Controllers | No global Redux-style store |
| API client | One module wrapping `fetch`: base URL, bearer injection, single-flight refresh on 401 `TOKEN_EXPIRED`, problem+json parsing, request-id surfacing | All HTTP goes through it |
| Performance budget | Initial JS < 200 KB gzipped, LCP < 2.5 s on 4G (NFR-004) | Route-level code splitting |
| Forms | Native form elements inside components, with validation messages mirroring server validation codes | Server stays authoritative |
| Styling | Design tokens as CSS custom properties (09 §2) and shared constructable stylesheets. No CSS framework. | Keeps brand fidelity |
| i18n | Strings externalized from day 1 (English only in P0) | Hindi/Telugu later without refactor |
| Testing | Web Test Runner (components), Playwright (E2E) | |

### 2.2 Structure

```
app/                                   (separate folder or repo; NOT inside dist/)
├── index.html
├── src/
│   ├── main.ts                        bootstraps shell, router, session restore
│   ├── core/
│   │   ├── api/                       http client, generated types, error mapping
│   │   ├── auth/                      session controller, silent refresh, BroadcastChannel sync
│   │   ├── authz/                     effective-permission context, <vs-can> gate
│   │   ├── router/                    route table, guards (auth + permission)
│   │   ├── i18n/  format/             dates (tz-aware), INR currency, phone
│   │   └── telemetry/                 error reporting, request-id capture
│   ├── design-system/                 vs-* primitives (09 §3.3), tokens.css
│   ├── modules/
│   │   ├── auth/                      login, forgot, reset, accept-invite
│   │   ├── leads/                     dashboard, list, detail, form
│   │   ├── admin/                     users, roles, permissions
│   │   └── audit/                     audit viewer
│   └── shell/                         vs-app-shell, sidebar, top bar, notifications tray
└── public/_headers                    CSP, HSTS, noindex, cache rules
```

Every future module adds a folder under `modules/` with its own routes. It registers into the shell's navigation with a required permission, so the nav menu is permission-driven.

### 2.3 Runtime flow

```
Browser loads app.vedaspaces.com
  └─► main.ts → session controller: POST /auth/refresh (cookie)
        ├─ 200 → access token (memory) → GET /auth/me (profile + effective permissions + authz_version)
        │          → provide context → router renders requested route (guards check permission)
        └─ 401 → router redirects to /login?next=…
Any API call
  └─► 401 TOKEN_EXPIRED → single-flight refresh → retry once → on failure → logout to /login
  └─► 403 PERMISSION_DENIED → toast + refetch /auth/me (permissions may have changed)
  └─► 409 VERSION_CONFLICT → conflict dialog (reload / view changes)
```

### 2.4 Marketing site integration (LEAD-001, LEAD-019)

The existing `dist/assets/app.js` form gains progressive enhancement. The site stays static with no build step.

1. On submit, the page POSTs JSON to `https://api.vedaspaces.com/api/v1/public/leads`. The body carries only the ADR-005 fields (required: name, phone, consent; optional: email, city, project type, budget range, message), plus a Turnstile token, an `Idempotency-Key` generated when the form is first touched, and attribution metadata.
2. **2xx:** show the accessible confirmation panel (09 §4.11) with the random public reference. Nothing internal is returned (LEAD-025). Offer "Continue on WhatsApp" as an optional extra.
3. **Network error, 5xx, or timeout (8 s):** fall back to today's `wa.me` hand-off with the same prefilled text. The enquiry is never lost.
4. **422:** show field errors inline.

`connect-src` in the site's `_headers` CSP adds `https://api.vedaspaces.com` and `https://challenges.cloudflare.com`.

## 3. Backend architecture (Flask)

### 3.1 Style: modular monolith, layered inside each module

> Traces: PLAT-001

```
            HTTP
             │
┌────────────▼─────────────────────────────────────────────────────────────┐
│ Edge middleware (in order)                                               │
│  request-id → security headers → CORS → body-size limit → JSON parse →   │
│  authentication (JWT verify, session check) → actor context → rate limit │
├──────────────────────────────────────────────────────────────────────────┤
│ API layer (Flask blueprints per module, /api/v1/<resource>)              │
│  route → permission gate (code only) → request schema validation →       │
│  call service → response schema serialization → envelope                 │
├──────────────────────────────────────────────────────────────────────────┤
│ Service layer (use cases; transaction boundary)                          │
│  scope/ownership checks · business rules · state machines ·              │
│  emits domain events to outbox · calls other modules via their services  │
├──────────────────────────────────────────────────────────────────────────┤
│ Repository layer                                                         │
│  SQLAlchemy queries · soft-delete filter · scope filter · pagination     │
├──────────────────────────────────────────────────────────────────────────┤
│ Platform kernel (shared)                                                 │
│  AuditedBase model · GUID type · UTC datetime type · actor context ·     │
│  audit hook · outbox · number sequences · lookups · errors · clock       │
└──────────────────────────────────────────────────────────────────────────┘
             │
          SQLAlchemy Engine → SQLite (now) / PostgreSQL (later)
```

### 3.2 Package layout

```
api/                                    (backend repository or top-level folder)
├── veda/
│   ├── app.py                          application factory; registers modules
│   ├── config.py                       env-driven settings per environment
│   ├── kernel/                         audit contract, GUID/UTC types, actor context,
│   │                                   audit hook, outbox, sequences, errors, pagination
│   ├── platform/
│   │   ├── identity/                   User model (table app_user), user_credential, profile
│   │   ├── auth/                       login, sessions, tokens, reset, MFA, security_event_log
│   │   ├── rbac/                       role, permission, grants, resolver, registry
│   │   ├── audit/                      audit_log read APIs
│   │   ├── lookups/                    lookup_category, lookup_value
│   │   └── notifications/              notification, email adapter, templates
│   ├── modules/
│   │   └── crm/
│   │       └── leads/                  lead, lead_note, lead_activity
│   │       (future: crm/customers, projects/, procurement/, inventory/, hr/, payroll/)
│   └── cli/                            bootstrap-founder, sync-permissions, worker, scheduler
├── migrations/                         Alembic; platform revisions precede module revisions
└── tests/                              unit, integration (dual-engine), contract (OpenAPI)
```

Each module folder has the same shape: `models`, `schemas` (request/response DTOs), `repository`, `service`, `routes`, `permissions` (the module's permission registry entries), `events` (outbox event types), `README` (requirement IDs owned).

### 3.3 Module rules (PLAT-011)

1. A module may import another module's **service interface and DTOs only**, never its models or repository.
2. Foreign keys **across modules** are allowed only toward platform tables (`app_user`, `lookup_value`) or toward an upstream module's aggregate root, such as `project.customer_id → customer.id`.
3. Cross-module reactions use **outbox events**. For example, `lead.won` leads CRM to create a customer. Synchronous cross-module writes in one request aren't allowed.
4. Each module owns a permission namespace (06 §3) and a requirement prefix (01 §4).

### 3.4 Request lifecycle (write path)

```
PATCH /api/v1/leads/{id}   If-Match: "4"
 1 request-id assigned (or taken from CF-Ray) → logged
 2 JWT verified (sig, exp, iss, aud) → session active? (cached ≤30 s) → user ACTIVE?
 3 actor context set: {user_id, session_id, request_id, ip, ua, via=API}
 4 permission gate: resolver.has(actor, "lead.update") → else 403
 5 body validated (schema) → else 422
 6 service: load lead within actor scope (OWN → assigned_to|created_by = actor) → else 404
 7 version check: row.version == 4 → else 409 VERSION_CONFLICT
 8 apply changes; business rules; emit outbox events
 9 flush → audit hook writes audit_log rows (same transaction)
10 commit (single transaction: business rows + audit rows + outbox rows)
11 respond 200 {data} with ETag: "5"
```

### 3.5 Technology choices (backend)

| Concern | Choice |
|---|---|
| Runtime | Python 3.12+ |
| WSGI server | gunicorn (sync workers; 2×CPU+1; SQLite needs WAL for concurrent readers) |
| ORM / migrations | SQLAlchemy 2.x (typed ORM) · Alembic (batch mode for SQLite ALTERs) |
| Validation / DTOs | Pydantic v2 models, used to generate the OpenAPI 3.1 document |
| Password hashing | argon2-cffi (Argon2id) |
| JWT | PyJWT with `cryptography` (ES256) |
| Phone normalization | `phonenumbers` (libphonenumber port) |
| Rate limiting | Flask-Limiter with an in-memory store (single host). Move to Redis when there are multiple hosts. |
| Logging | structlog → JSON on stdout |
| Error tracking | Sentry SDK (PII scrubbing on) |
| Background work | Dedicated worker process polling the outbox. Scheduler process for periodic jobs. Same codebase and image. |

## 4. API architecture (summary; detail in 08)

> Traces: API-001

- Resource-oriented REST under `/api/v1`. Nouns are plural and kebab-case in paths (`/lead-notes` only when top-level; notes are nested under leads).
- JSON bodies with snake_case fields. UTC ISO-8601 timestamps with a `Z` suffix. IDs are 32-hex strings.
- State transitions that carry business rules are **explicit action sub-resources** (`POST /leads/{id}/status`, `/assign`, `/restore`) rather than free-form PATCH of `status`.
- Contract-first: the OpenAPI document is generated from DTOs, published per environment, and used to generate frontend types.
- There are three audiences: **public** (`/api/v1/public/*`, anonymous, Turnstile), **app** (everything else, Bearer), and **ops** (`/health/*`, unauthenticated, no data).

## 5. Authentication architecture (summary; detail in 05)

```
 ┌──────────┐  POST /auth/login {email,password}      ┌───────────┐
 │  Lit SPA │ ───────────────────────────────────────►│  Flask    │── verify Argon2id (user_credential)
 │          │◄─── 200 {access_token (JWT,15m)}        │  auth     │── create user_session + refresh_token(hash)
 │ memory:  │     Set-Cookie: vs_rt=<opaque>;         │  module   │── security_event_log LOGIN SUCCESS
 │ JWT only │     HttpOnly;Secure;SameSite=Strict;    └───────────┘
 └────┬─────┘     Path=/api/v1/auth
      │ Authorization: Bearer <JWT>  (every API call)
      │ POST /auth/refresh (cookie) → rotate → new JWT + new cookie
```

## 6. RBAC architecture (summary; detail in 06)

```
app_user ──< user_role >── role ──< role_permission(scope) >── permission
    └──────────< user_permission(effect GRANT|DENY, scope) >──────┘

resolver(user) → { "lead.read": OWN, "lead.update": OWN, "lead.create": ALL, ... }
   cached per (user_id, authz_version); authz_version++ on any grant change
enforcement:  route gate (has code?) → service (row in scope?) → repository (list filtered by scope)
```

## 7. Audit architecture (summary; detail in 07)

```
Service mutates ORM objects ─► session.flush()
                                 │  before_flush hook (kernel)
                                 ├─ stamps contract columns (created_*/updated_*/version)
                                 ├─ diffs each dirty AuditedBase object (old vs new)
                                 └─ adds audit_log rows (same session)
                               commit ─► business rows + audit rows are atomic (03 §2.8)
security events ─► security_event_log (kernel writer; own tx for failures) — never audit_log (ADR-004)
```

Three distinct records, never conflated:

| Record | Question it answers | Store | Retention |
|---|---|---|---|
| `audit_log` | Who changed what data, from what to what | DB, append-only | Configurable (07 §8.1) |
| `security_event_log` | Who signed in, refreshed, failed MFA, used a sensitive permission | DB, append-only, hash-chained | Configurable (05 §9.4) |
| Application logs | What the software did (debugging, performance) | stdout → CloudWatch | Configurable CloudWatch retention |

## 8. Database architecture

### 8.1 Engine strategy

| Phase | Engine | Topology |
|---|---|---|
| P0 MVP | SQLite 3.45+ with WAL, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL` | Single file on a **dedicated encrypted EBS volume** (not the container layer). **Exactly one active application instance** (single writer). Litestream to S3. |
| After the PostgreSQL release gate (11 §3.3, ADR-008) | PostgreSQL 16+ (Amazon RDS) | Only then may the application run more than one instance |

### 8.2 Portability rules (PLAT-004)

1. Only the kernel logical types are used (GUID, UTCDATETIME, BOOL, JSON, CODE, MONEY_MINOR, strings, integers). Their explicit SQLite and PostgreSQL mappings are in 03 §12. GUID is `CHAR(32)` on SQLite and native `uuid` on PostgreSQL, always the 32-hex form in code and APIs (ADR-002).
2. Enumerations are `VARCHAR` plus a `CHECK` constraint, never native `ENUM` types.
3. No triggers for business logic. The only triggers are the audit-immutability guards (07 §6), which are defined per engine in migrations.
4. No engine-specific SQL in services. Search uses `LIKE` via the ORM behind a repository method, which can be swapped for `pg_trgm` or FTS without changing callers.
5. Case-insensitive uniqueness uses normalized shadow columns (`email_normalized`), not collations.
6. CI runs the full integration suite against both engines (OPS-001).

### 8.3 Migration ordering (RBAC-001)

> Traces: PLAT-005

```
0001_kernel            (no tables; extensions/pragmas docs)
0002_identity          app_user (+ seed SYSTEM, WEB_INTAKE, ANONYMOUS), user_credential   — no table named user (ADR-001)
0003_rbac              role, permission, user_role, role_permission, user_permission (+ seed roles, permissions, matrix)
0004_auth              user_session, refresh_token, password_reset_token, user_mfa_factor, user_mfa_recovery_code,
                       mfa_challenge, security_event_log (+ immutability guards)
0005_audit             audit_log (+ immutability guards)
0006_reference         lookup_category, lookup_value (+ seed), number_sequence (+ seed)
0007_notifications     notification, outbox_event
0100_crm_leads         lead, lead_note, lead_activity
```

Module migrations may depend only on platform revisions and upstream modules.

## 9. Logging and observability architecture

> Traces: LOG-001, LOG-002, LOG-004, LOG-005, NFR-002, SEVT-009

```
Flask/gunicorn/worker ─► structlog JSON ─► stdout ─► CloudWatch agent ─► CloudWatch Logs
         │                                                      └► metric filters → alarms → email/SNS
         └─► Sentry (exceptions, performance traces 10% sample, PII scrubbed)
Cloudflare ─► analytics + WAF events (edge)
Health: /health/live (process up) · /health/ready (DB reachable, migrations at head, outbox lag < 5 min)
```

**Log line schema:** `ts, level, logger, event, request_id, session_id, user_id, method, route (templated, not raw path), status, duration_ms, ip (truncated /24), error.type, error.fingerprint`.

**Masking (LOG-003):**

| Data | Rule |
|---|---|
| Password, token, cookie, Authorization header | Never logged. A denylist is applied to headers and bodies. |
| Phone | `+91******5153` |
| Email | `s***@gmail.com` |
| Request/response bodies | Not logged. Validation errors log field names only. |

**Correlation:** `request_id` flows HTTP → logs → `audit_log.request_id` → `security_event_log.request_id` → `outbox_event.payload.request_id` → email headers. One ID reconstructs a whole user action.

**Metrics (LOG-006, P0).** Request count, latency and status by templated route · outbox depth and age · security-event counts by type and outcome · Litestream replication lag · last successful snapshot and restore-verification time · disk usage · process restarts. They are published as CloudWatch metrics from structured-log metric filters plus the CloudWatch agent.

**Alerts (LOG-006, P0).** The thresholds are initial configuration values, tuned from measured traffic (ASM-004).

| Alert | Condition |
|---|---|
| API error rate | 5xx rate above threshold over 5 min |
| Latency | p95 above the NFR-001 target over 10 min |
| Security | Rules in 05 §9.8 (stuffing, token reuse, MFA guessing, MFA reset, chain broken, writer failure) |
| Outbox | Oldest PENDING above threshold, or any DEAD row |
| Backups | Litestream lag exceeding the owner-approved RPO (OPS-005) · daily snapshot missing · restore verification failed or overdue |
| Health | `/health/ready` failing for 2 consecutive checks |
| Disk | > 80% used |

## 10. Notification architecture

### 10.1 Transactional outbox (NOTIF-003)

> Traces: NOTIF-004

```
Service (in business transaction)
  └─ insert outbox_event {event_type:"lead.created", aggregate_type:"lead", aggregate_id, payload, status:PENDING}
commit
Outbox worker (loop every 2 s)
  1 claim batch: status=PENDING AND next_attempt_on<=now  → set PROCESSING, locked_by, locked_on
  2 dispatch to handlers registered for event_type
       ├─ notifications handler → insert notification rows (in-app)
       ├─ email handler         → render template → provider.send()
       └─ (future) webhook / WhatsApp / AI indexing / module reactions
  3 success → DONE, processed_on ; failure → attempts++, next_attempt_on = now + backoff(2^n, max 1h)
  4 attempts ≥ 8 → DEAD + alert
Stale PROCESSING (> 5 min) reclaimed (worker crash safety). Handlers must be idempotent (key: outbox_event.id).
```

### 10.2 Channels

> Traces: NOTIF-001, NOTIF-002, NOTIF-007

| Channel | P0 | Provider | Notes |
|---|---|---|---|
| In-app | Yes | `notification` table | Polled by the app every 60 s, plus on focus. SSE/WebSocket deferred. |
| Email | Yes | `EmailProvider` adapter (NOTIF-009): **Amazon SES** (ap-south-1) in production · **logging/capture adapter** in local, test and staging until SES production access is granted | SPF, DKIM and DMARC on `vedaspaces.com`. Sender `no-reply@vedaspaces.com`. |
| WhatsApp Business | P2 | Meta Cloud API via adapter | Needs template approval |
| SMS | Not planned | — | Adapter slot only |

### 10.3 P0 notification catalog

> Traces: NOTIF-005

| Event | Recipients | Channels | Req |
|---|---|---|---|
| `lead.created` (public) | Users holding `lead.assign` (intake owners) | In-app + email | LEAD-020 |
| `lead.assigned` | New assignee | In-app + email | LEAD-020 |
| `lead.won` | Users holding `lead.read` at ALL scope | In-app | LEAD-020 |
| `lead.reopened` | Assignee | In-app | LEAD-005 |
| `user.invited` | Invitee | Email | AUTH-011 |
| `auth.password_reset_requested` | User | Email | AUTH-008 |
| `auth.password_changed` | User | Email | AUTH-008, AUTH-012 |
| `auth.refresh_reuse_detected` | User + holders of `user.session.revoke` | Email | AUTH-005 |
| `activity.follow_up_due` | Activity owner | In-app (P1: email digest) | NOTIF-006 |

Recipient resolution is **permission-based** ("users holding `lead.assign`"), never role-name-based (RBAC-002).

**Delivery failure isolation (NOTIF-008, ADR-007).** Emails are sent only by the outbox worker **after** the business transaction commits. An SES error, a throttle or an outage marks the outbox row FAILED or DEAD and alerts. It never rolls back, blocks or delays a persisted lead, and the public intake response doesn't wait for email.

| Additional security notifications | Recipients | Channel | Req |
|---|---|---|---|
| `auth.mfa_reset` | Target user + holders of `user.mfa.manage` | Email | MFA-007 |
| `auth.mfa_recovery_code_used` | User | Email | MFA-005 |
| `auth.account_locked` | User | Email | AUTH-010 |
| `rbac.sensitive_grant` | Holders of `permission.manage` | Email | RBAC-017 |

Templates are versioned files: subject, HTML, plain text. They use brand tokens (serif headline, copper accent) and are rendered by the worker with an escaping template engine.

## 11. Security architecture

### 11.1 Defense in depth

> Traces: LEAD-018, OPS-007, SEC-001, SEC-006, SEC-008, SEC-011

```
Layer 1  Edge (Cloudflare)   TLS 1.2+ (1.3 preferred) · HSTS preload · WAF managed rules · bot fight ·
                             rate limits: /auth/login 10/min/IP, /auth/password/* 5/min/IP, /public/leads 5/min/IP
Layer 2  Network             Origin SG allows 443 only from Cloudflare IP ranges · Authenticated Origin Pulls (mTLS)
                             · SSH disabled; access via SSM Session Manager
Layer 3  Application         JWT verify · session check · permission gate · scope filter · schema validation ·
                             body size 1 MB (public 16 KB) · CORS allowlist · security headers · app-level rate limits
Layer 4  Data                Parameterized ORM queries · secrets never in rows or logs · Argon2id ·
                             token hashes only · encrypted EBS + S3 SSE-KMS · least-privilege IAM
Layer 5  Detection           security_event_log (hash-chained) · audit_log · alerts (§9, 05 §9.8) · Sentry
Layer 6  Recovery            Litestream PITR · daily snapshots · automated restore verification (OPS-009)
```

### 11.2 Headers

> Traces: SEC-001, SEC-003

| Surface | Headers |
|---|---|
| API | `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` · `X-Content-Type-Options: nosniff` · `Cache-Control: no-store` on authenticated responses · `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` · `Referrer-Policy: no-referrer` |
| App (`_headers`) | `Content-Security-Policy: default-src 'self'; script-src 'self' https://challenges.cloudflare.com; connect-src 'self' https://api.vedaspaces.com; img-src 'self' data:; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; frame-src https://challenges.cloudflare.com; frame-ancestors 'none'; base-uri 'none'; form-action 'self'` · `X-Robots-Tag: noindex, nofollow` · `Permissions-Policy: camera=(), microphone=(), geolocation=()` |

### 11.3 CORS (SEC-002)

`Access-Control-Allow-Origin` is echoed only for the exact allowlist:

| Environment | Allowed origins |
|---|---|
| Production | `https://app.vedaspaces.com`, `https://www.vedaspaces.com` (public endpoints only) |
| Staging | The staging origins |

- `Allow-Credentials: true` is set only for the app origin.
- Preflight is cached for 600 s.
- Wildcards are never used.

### 11.4 Secrets (SEC-005)

> Traces: MFA-010, PLAT-008

| Secret | Store | Rotation |
|---|---|---|
| JWT signing keys (ES256; `kid` header, current + previous) | SSM SecureString | 90 days; the previous key stays valid for 1 day |
| Turnstile secret | SSM | On compromise |
| SES SMTP/API credentials | IAM role (no static keys) | n/a |
| Sentry DSN | SSM | n/a |
| Litestream S3 access | IAM instance role | n/a |
| MFA secret encryption key | AWS KMS customer-managed key; the app role may only Encrypt/Decrypt/GenerateDataKey | Annual automatic KMS rotation |
| HMAC keys (recovery codes, email-attempt hashes) | SSM SecureString | On compromise, with a documented re-hash procedure |

### 11.5 Data classification

| Class | Examples | Controls |
|---|---|---|
| Secret | password hashes, token hashes, signing keys | Never serialized, logged or audited |
| Personal (PII) | lead name/phone/email/message, user profile | Masked in logs · access permission-gated · DPDP rights handling |
| Internal | lead status, activities, notes | Permission-gated |
| Public | lookup labels, marketing content | — |

## 12. Deployment architecture

### 12.1 Environments (OPS-003)

| Env | Web | API | DB | Data |
|---|---|---|---|---|
| Local | Vite dev server | Flask dev server | SQLite file | Seed + fixtures |
| Staging | Pages preview branch `staging` → `app-staging.vedaspaces.com` | Small VM `api-staging.vedaspaces.com` | SQLite (and PG for migration rehearsal) | Synthetic/anonymized only |
| Production | Pages `main` → `app.vedaspaces.com` | VM `api.vedaspaces.com` | SQLite + Litestream → S3 | Real |

### 12.2 Production host (P0)

> Traces: PLAT-003

| Item | Choice |
|---|---|
| Host | One EC2 instance (Graviton, e.g. t4g.small) in ap-south-1, or an equivalent Lightsail instance |
| Deploy unit | Container image built by CI, pushed to ECR, pulled and restarted by a deploy script over SSM |
| Processes | `api` (gunicorn), `worker` (outbox), `scheduler` (periodic jobs), `litestream` (replicate) — managed by systemd or docker compose |
| Disk | **Dedicated** encrypted EBS gp3 volume (KMS), mounted at `/var/lib/veda`, `DeleteOnTermination=false`, daily EBS snapshots. The database file never lives in the container's writable layer. The container mounts the volume (OPS-007). |
| Instance count | **Exactly one** active app instance. No autoscaling group larger than one and no load-balanced replicas while SQLite is authoritative (OPS-006). Deploys incur a brief restart window, and zero-downtime deploys are not claimed. |
| Deploy sequence | Pull image → run `alembic upgrade head` (after Litestream confirms a fresh snapshot) → restart api/worker → `/health/ready` check → rollback to the previous image on failure |

**Why not ECS Fargate, App Runner or Lambda now:** they have no durable local disk, and SQLite on EFS/NFS is unsafe for locking. After the PostgreSQL release gate, the API holds no local state and can move to ECS Fargate or App Runner with no code changes.

### 12.3 Backup, restore verification and recovery objectives (ADR-008)

> Traces: OPS-002, SEC-008

| Item | Design |
|---|---|
| Continuous backup | Litestream replicates the WAL to a versioned S3 bucket (SSE-KMS). The sync interval is configurable (default 1 s). |
| Snapshots | Nightly `VACUUM INTO` snapshot to a separate S3 prefix with Object Lock, plus daily EBS snapshots |
| Restore verification (OPS-009) | An automated scheduled job restores the latest replica to a scratch instance. It runs `PRAGMA integrity_check` and `foreign_key_check`, compares per-table row counts with production, and runs a read-only smoke test. It publishes a metric and alerts on failure. |
| RPO / RTO (OPS-005) | **Owner-approved values required.** They are not set by this architecture (OWNER-INPUT-001 in the coverage gate). The mechanisms above give an RPO bounded by the Litestream sync interval and alerting lag. RTO is bounded by the rehearsed rebuild runbook. Both are measured in the first restore rehearsal and reported to the owner for approval. |
| Rehearsal | A full rebuild and restore rehearsal before go-live, then at a cadence the owner sets |

### 12.4 CI/CD

> Traces: OPS-001, SEC-007

```
PR → lint (ruff, mypy) · schema-lint (DATA-011) · unit · integration[SQLite] · integration[PostgreSQL]
   · OpenAPI diff (API-009 breaking-change guard) · pip-audit · container scan · frontend build + WTR + Playwright
main → build image → deploy staging → smoke E2E → manual approval → deploy production
```
