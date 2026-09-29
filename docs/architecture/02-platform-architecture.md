# 02 — Platform Architecture

Governing decisions: [ADR-010](decisions/ADR-010-account-control-and-privileged-protection.md) · [ADR-001](decisions/ADR-001-app-user-table.md) · [ADR-002](decisions/ADR-002-uuidv7-identifiers.md) · [ADR-003](decisions/ADR-003-audit-contract.md) · [ADR-004](decisions/ADR-004-security-event-log.md) · [ADR-007](decisions/ADR-007-technology-stack.md) · [ADR-008](decisions/ADR-008-aws-hosting.md) · [ADR-009](decisions/ADR-009-p0-scope.md)

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

1. On submit, the page POSTs JSON to `https://api.vedaspaces.com/api/v1/public/leads`. The body carries:
   - only the ADR-005 fields: required name, phone and consent; optional email, city, project type, budget range, **property type** and message;
   - a Turnstile token;
   - an `Idempotency-Key` generated when the form is first touched, and reused on retries;
   - attribution metadata.
2. **201:** show the accessible confirmation panel (09 §4.11) with the random public reference. Every 201 carries a reference, including quarantined suspected-spam submissions, so no genuine sender gets a false confirmation. Nothing internal is returned (LEAD-025). Offer "Continue on WhatsApp" as an optional extra.
3. **Field-level 422** (`VALIDATION_FAILED`, `CONSENT_REQUIRED`, `UNKNOWN_POLICY_VERSION`): show the accessible field errors. The user corrects them and resubmits with the same idempotency key.
4. **Every other outcome** (422 `CAPTCHA_FAILED`, 428, 413, 429, any 5xx, a network error, or an 8-second timeout): show the specific message **and** prominently offer today's `wa.me` hand-off with the same prefilled text. This matches 04 §5.1 and 09 §4.11 (F-05). No path ends without either a stored lead or a WhatsApp route.

`connect-src` in the site's `_headers` CSP adds `https://api.vedaspaces.com` and `https://challenges.cloudflare.com`.

## 3. Backend architecture (Flask)

### 3.1 Style: modular monolith, layered inside each module

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
| WSGI server | gunicorn with the **`gthread` worker class, exactly one worker process** and a configurable thread pool (initial 8 threads). Rationale (F-09, OPS-010): one process means the in-process rate limiter, idempotency store, permission cache and Argon2 semaphore are authoritative, not per worker. Argon2 and SQLite I/O release the GIL, and SQLite (WAL) has a single writer anyway. The worker and scheduler are separate processes with no request-path state. |
| ORM / migrations | SQLAlchemy 2.x (typed ORM) · Alembic (batch mode for SQLite ALTERs) |
| Validation / DTOs | Pydantic v2 models, used to generate the OpenAPI 3.1 document |
| Password hashing | argon2-cffi (Argon2id) |
| JWT | PyJWT with `cryptography` (ES256) |
| Phone normalization | `phonenumbers` (libphonenumber port) |
| Rate limiting | Flask-Limiter with its in-memory store, which is correct because there is exactly one application process (OPS-010). A deployment check fails if the worker count is not 1. It moves to Redis after the PostgreSQL gate. |
| Logging | structlog → JSON on stdout |
| Error tracking | Sentry SDK (PII scrubbing on) |
| Background work | Dedicated worker process polling the outbox. Scheduler process for periodic jobs. Same codebase and image. |

## 4. API architecture (summary; detail in 08)

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

```
0001_kernel            (no tables; extensions/pragmas docs)
0002_identity          app_user (+ seed SYSTEM, WEB_INTAKE, ANONYMOUS), user_credential   — no table named user (ADR-001)
0003_rbac              role, permission, user_role, role_permission, user_permission (+ seed roles, permissions, matrix)
0004_auth              user_session, refresh_token, user_action_token, user_mfa_factor, user_mfa_recovery_code,
                       mfa_challenge, security_event_log (+ immutability guards)
0005_audit             audit_log (+ immutability guards)
0006_reference         lookup_category, lookup_value (+ seed), number_sequence (+ seed)
0007_notifications     notification, outbox_event
0008_account_security  admin_approval_request (+ app_user proposed-email, protection_level and cooling-off columns)
0100_crm_leads         lead, lead_note, lead_activity
```

Module migrations may depend only on platform revisions and upstream modules.

## 9. Logging and observability architecture

```
Flask/gunicorn/worker ─► structlog JSON ─► stdout ─► CloudWatch agent ─► CloudWatch Logs
         │                                                      └► metric filters → alarms → email/SNS
         └─► Sentry (exceptions, performance traces 10% sample, PII scrubbed)
Cloudflare ─► analytics + WAF events (edge)
Health: /health/live (process up)
        /health/ready  = DB reachable · migrations at head · foreign_keys=ON · immutability triggers present (A-02)
                         → the only signal that gates deploys and traffic
        /health/ready body also reports "degraded" signals that NEVER fail readiness (F-12):
                         outbox lag, email-provider errors, Litestream lag — alerted separately (below)
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
| Degraded | Outbox lag above threshold, or email-provider errors. These alert but never fail readiness or trigger rollback (F-12). |
| Spam queue ageing | SUSPECTED leads older than the configured review age (04 §5.5, N-A3) |
| Governance invariants | Nightly I1/I2/I3 failure (CRITICAL), or no effective recovery administrator (High) (06 §7.3) |
| Disk | > 80% used |

## 10. Notification architecture

### 10.1 Transactional outbox (NOTIF-003)

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

| Channel | P0 | Provider | Notes |
|---|---|---|---|
| In-app | Yes | `notification` table | Polled by the app every 60 s, plus on focus. SSE/WebSocket deferred. |
| Email | Yes | `EmailProvider` adapter (NOTIF-009): **Amazon SES** (ap-south-1) in production · **logging/capture adapter** in local, test and staging until SES production access is granted | SPF, DKIM and DMARC on `vedaspaces.com`. Sender `no-reply@vedaspaces.com`. |
| WhatsApp Business | P2 | Meta Cloud API via adapter | Needs template approval |
| SMS | Not planned | — | Adapter slot only |

### 10.3 P0 notification catalog

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
| `auth.mfa_reset_requested` / `auth.mfa_reset_completed` | Target (verified email) + holders of `user.mfa.reset` | Email | MFA-007, MFA-015 |
| `auth.mfa_enrollment_link` | User (verified email only) | Email | MFA-014 |
| `auth.mfa_recovery_completed` | User (current **verified** email, never the proposed one) + holders of `user.mfa.reset` | Email | MFA-013 |
| `auth.mfa_recovery_code_used` | User | Email | MFA-005 |
| `auth.email_change_requested` | **Current verified** address (alert + cancel link) and **proposed** address (verification link) | Email | USER-007 |
| `auth.email_change_completed` | Old and new addresses | Email | USER-007 |
| `auth.account_throttled` | User | Email | AUTH-010 |
| `approval.requested` / `approval.decided` | Eligible approvers + target | Email + in-app | RBAC-021 |
| `break_glass.requested` | All ACTIVE FOUNDER-protected users + target, with a cancel link | Email | RBAC-021 |
| `rbac.sensitive_grant` | Holders of `permission.manage` | Email | RBAC-017 |
| `invite.accepted` | Inviter | Email + in-app | AUTH-011 |

Security notifications always go to the **verified** email. The only message sent to a proposed address is its verification link.

Templates are versioned files: subject, HTML, plain text. They use brand tokens (serif headline, copper accent) and are rendered by the worker with an escaping template engine.

## 11. Security architecture

### 11.1 Defense in depth

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

| Secret | Store | Rotation |
|---|---|---|
| JWT signing keys (ES256; `kid` header, current + previous) | SSM SecureString | 90 days; the previous key stays valid for 1 day |
| Turnstile secret | SSM | On compromise |
| SES SMTP/API credentials | IAM role (no static keys) | n/a |
| Sentry DSN | SSM | n/a |
| Litestream S3 access | IAM instance role | n/a |
| MFA secret encryption key | AWS KMS customer-managed key; the app role may only Encrypt/Decrypt/GenerateDataKey | Annual automatic KMS rotation |
| HMAC keys (recovery codes, email-attempt hashes) | SSM SecureString | On compromise. Recovery codes are re-issued, because a keyed hash can't be migrated. |
| Security-log chain key (`chain_key_label`, 05 §9.6) | SSM SecureString, loaded at process start, never written to disk or logs | Annually or on compromise. A new `chain_key_label` starts a new segment; old keys stay retained for verification. |
| Anchor bucket writer | Dedicated IAM role with `s3:PutObject` only on the Object Lock (compliance) anchor bucket. The application role cannot delete or overwrite. | n/a |
| Break-glass custodians | Two named IAM principals in the `veda-breakglass` group, AWS MFA required (06 §7.5). Designation is OWNER-INPUT-004. | On personnel change |

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

| Item | Choice |
|---|---|
| Region | **ap-south-1 (Mumbai)**, approved by the owner (Decision 5, ADR-008). The region is a deployment parameter, not hard-coded, and every AWS resource name and ARN comes from configuration. **No multi-region availability is claimed for P0.** |
| Host | One EC2 instance (Graviton, e.g. t4g.small) in ap-south-1, or an equivalent Lightsail instance |
| Deploy unit | Container image built by CI, pushed to ECR, pulled and restarted by a deploy script over SSM |
| Processes | `api` (gunicorn, **one** gthread worker process), `worker` (outbox), `scheduler` (periodic jobs), `litestream` (exactly one replicator), all managed by systemd or docker compose. The maintenance CLI (purge, archival, break-glass) runs as a separate short-lived process (A-02). |
| Disk | **Dedicated** encrypted EBS gp3 volume (KMS), mounted at `/var/lib/veda`, `DeleteOnTermination=false`, daily EBS snapshots. The database file never lives in the container's writable layer. The container mounts the volume (OPS-007). |
| Instance count | **Exactly one** active app instance. No autoscaling group larger than one and no load-balanced replicas while SQLite is authoritative (OPS-006). Deploys incur a brief restart window, and zero-downtime deploys are not claimed. |
| Deploy sequence | The single runbook in §12.4 (F-12) |

**Why not ECS Fargate, App Runner or Lambda now:** they have no durable local disk, and SQLite on EFS/NFS is unsafe for locking. After the PostgreSQL release gate, the API holds no local state and can move to ECS Fargate or App Runner with no code changes.

### 12.3 Backup, restore verification and recovery objectives (ADR-008)

| Item | Design |
|---|---|
| Continuous backup | Litestream replicates the WAL to a versioned S3 bucket (SSE-KMS). The sync interval is configurable (default 1 s). |
| Snapshots | Nightly `VACUUM INTO` snapshot to a separate S3 prefix with Object Lock, plus daily EBS snapshots |
| Restore verification (OPS-009) | An automated scheduled job restores the latest replica to a scratch instance. It runs `PRAGMA integrity_check` and `foreign_key_check`, compares per-table row counts with production, and runs a read-only smoke test. It publishes a metric and alerts on failure. |
| RPO / RTO (OPS-005) | **Owner-approved values required.** They are not set by this architecture (OWNER-INPUT-001 in the coverage gate). The mechanisms above give an RPO bounded by the Litestream sync interval and alerting lag. RTO is bounded by the rehearsed rebuild runbook. Both are measured in the first restore rehearsal and reported to the owner for approval. |
| Rehearsal | A full rebuild and restore rehearsal before go-live, then at a cadence the owner sets (OWNER-INPUT-003) |
| Region and DR implications (Decision 5) | Primary data and backups are in ap-south-1. The Litestream replica bucket may be replicated cross-region (S3 CRR) for **backup durability only**. That is not a standby deployment: restoring in another region would be a manual rebuild using the §12.4 runbook, with configuration pointing at the replica. The achievable recovery time for a regional outage is **not** claimed. It is measured only if the owner commissions a cross-region rehearsal. |
| Litestream constraints (A-11) | Exactly one Litestream process per database. The application never runs `PRAGMA wal_checkpoint(TRUNCATE)` or `RESTART` (Litestream manages checkpoints), and `wal_autocheckpoint` is left at the value Litestream expects. The Litestream version is pinned in the image, and restore tooling uses the same version. Replication lag and snapshot age are exported as metrics and alerted (§9). The restore-verification job (OPS-009) proves each replica generation restorable. |

### 12.4 Deploy and migration runbook (OPS-004, F-12)

This is the single procedure. 11 §2 B3 refers to it.

| Step | Action |
|---|---|
| Migration policy | All P0+ migrations are **expand-only and compatible with release N-1**: add tables, add nullable columns, add indexes, widen CHECKs. Contract steps (drops, NOT NULL tightening, renames) ship in a later release, after the N-1 compatibility window. No down-migrations are relied on. |
| 1. Pre-flight | CI green, including the migration upgrade-with-data test (12 §4.1). Litestream lag within the alert threshold. |
| 2. Snapshot | Force a Litestream snapshot and record its generation id. Take an EBS snapshot. |
| 3. Quiesce | Pause the outbox worker and scheduler. Keep the API serving. |
| 4. Migrate | `alembic upgrade head` (expand-only, so it is safe while N-1 code serves) |
| 5. Deploy | Restart the API on the new image. `/health/ready` must pass. |
| 6. Resume | Resume the worker and scheduler. |
| **Rollback, normal** | Redeploy the N-1 image. The schema stays migrated, which is compatible by policy. No data is lost. |
| **Rollback, disaster** (a migration corrupted data) | Enable maintenance mode: the API returns 503, and the website falls back to WhatsApp. Restore the step-2 snapshot and redeploy N-1. **Data written after step 2 is lost**, and the exact window is reported from `audit_log.performed_on` and security events. Operators re-enter WhatsApp enquiries received during maintenance. |

### 12.5 CI/CD

```
PR → lint (ruff, mypy) · schema-lint (DATA-011) · unit · integration[SQLite] · integration[PostgreSQL]
   · OpenAPI diff (API-009 breaking-change guard) · pip-audit · container scan · frontend build + WTR + Playwright
main → build image → deploy staging → smoke E2E → manual approval → deploy production
```
