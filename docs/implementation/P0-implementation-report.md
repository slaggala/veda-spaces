# Veda Spaces P0 — Implementation Report

> **Not certified, not merged, not deployed.** This report is the author's evidence for independent
> implementation review. Nothing here approves the implementation or its deviations.

| Item | Value |
|---|---|
| Architecture baseline SHA | `778aa8fdd918da48340319696ada3ff673e9fb8e` (certified architecture, unchanged) |
| Implementation branch | `implementation/p0-foundation` (branch point = baseline) |
| Authorization | Owner briefs `VEDA-SPACES-P0-IMPLEMENTATION-01` and `…-IMPLEMENTATION-FREEZE-01` |
| Deviation register | [P0-implementation-deviations.md](P0-implementation-deviations.md) (4 entries, all PENDING INDEPENDENT REVIEW) |
| Evidence | [evidence/](evidence/) — raw command output from the clean-environment run |

## 1. Directory structure

Directories added by the implementation (every directory containing a committed file):

```
.github/workflows
api
api/deploy
api/migrations
api/migrations/versions
api/tests
api/tests/integration
api/tests/support
api/tests/unit
api/tools
api/veda
api/veda/cli
api/veda/kernel
api/veda/modules
api/veda/modules/crm
api/veda/modules/crm/leads
api/veda/platform
api/veda/platform/audit
api/veda/platform/auth
api/veda/platform/identity
api/veda/platform/lookups
api/veda/platform/notifications
api/veda/platform/notifications/templates
api/veda/platform/rbac
app
app/e2e
app/public
app/public/img
app/scripts
app/src
app/src/core/api
app/src/core/auth
app/src/core/authz
app/src/core/format
app/src/core/i18n
app/src/core/router
app/src/core/telemetry
app/src/design-system
app/src/modules/admin
app/src/modules/audit
app/src/modules/auth
app/src/modules/leads
app/src/shell
app/test
docs/implementation
docs/implementation/evidence
```

Top-level roles: `api/` Flask backend (02 §3.2) · `app/` Lit + TypeScript workspace (02 §2.2) · `dist/` marketing
site (enquiry form only) · `.github/workflows/` CI definition (not run here) · `docs/implementation/` this report,
deviation register and evidence.

## 2. Files added, modified and removed

| Change | Files |
|---|---|
| Added | 250 files: `api/` (143), `app/` (81), `docs/implementation/` (report, deviation register ×2, 23 evidence files), `.github/workflows/ci.yml` |
| Modified | `.gitignore` (generated/sensitive artifacts) · `README.md` (links to api/app/report) · `dist/index.html`, `dist/assets/app.js`, `dist/assets/enhancements.css` (enquiry form, §Q) |
| Removed | None |
| Unchanged | `docs/architecture/**` including review, remediation and validation documents (verified by `git diff --quiet 778aa8f -- docs/architecture`) |

### dist/ changes (enquiry-form integration only, LEAD-001/019, 09 §4.11)

- `dist/index.html`: three meta tags (`veda-api-base` — **empty, feature off**; `veda-turnstile-sitekey` — empty;
  `veda-policy-version`); the contact form replaced by the ADR-005 form (required name/phone/consent; optional email,
  property type with the Decision 4 options, service, budget, location, brief; off-screen honeypot; error summary;
  success and WhatsApp-fallback panels).
- `dist/assets/app.js`: only the contact-form submit handler is replaced. With `veda-api-base` empty the behaviour is the
  original WhatsApp hand-off (verified by `e2e-site.txt` check 5). Navigation, modal and reveal code unchanged.
- `dist/assets/enhancements.css`: styles appended for the new form states only.

## 3. Database tables and migrations

24 tables, 9 revisions, one Alembic head (`0100_crm_leads`). Every table carries the nine audit-contract
columns (ADR-003) with actor FKs to `app_user.id`; UUIDv7 32-hex ids (ADR-002); no table named `user` (ADR-001).

| Revision | Tables | Audit policy |
|---|---|---|
| 0001_kernel | — (SQLite pragma assertion) | — |
| 0002_identity | app_user, user_credential (+ SYSTEM, WEB_INTAKE, ANONYMOUS) | FULL |
| 0003_rbac | role, permission, user_role, role_permission, user_permission (+ roles, 45 permissions, matrix) | FULL |
| 0004_auth | user_session, refresh_token, user_action_token, user_mfa_factor, user_mfa_recovery_code, mfa_challenge, security_event_log (+ immutability guards) | EVENT_ONLY · factor FULL · security_event_log IMMUTABLE_STORE |
| 0005_audit | audit_log (+ guards; CREATE backfill for 0002–0003 seeds) | IMMUTABLE_STORE |
| 0006_reference | lookup_category, lookup_value, number_sequence (+ 6 categories, 47 values, LEAD sequence) | FULL |
| 0007_notifications | outbox_event, notification | EVENT_ONLY |
| 0008_account_security | admin_approval_request (+ app_user proposed-email, protection_level, cooling-off columns) | FULL |
| 0100_crm_leads | lead, lead_note, lead_activity | FULL |

Migration evidence (`evidence/migration-evidence.json`, produced by `evidence/migration_evidence.py` on fresh databases):

| Check | SQLite | PostgreSQL 18.4 (embedded) |
|---|---|---|
| Empty database → head | 0100_crm_leads | 0100_crm_leads |
| Tables / indexes / FKs | 24 / 72 / 107 | 24 / 72 / 107 |
| Named CHECK constraints | 493 (incl. SQLite type CHECKs) | 161 |
| Schema conformance (03 §2.7 rules 1–9) | OK | OK |
| Nine audit columns on every table | True | True |
| Immutability guards present | True | True |
| Human users / password hashes after migration | 0 / 0 | 0 / 0 |
| Seed counts (roles, permissions, matrix, lookups, system users, sequences) | 3, 45, 101, 47, 3, 1 | 3, 45, 101, 47, 3, 1 |
| Seed deterministic across two fresh databases | True | True |
| Raw UUIDv4 insert rejected by the database | True | n/a — native `uuid` accepts any UUID; v7 enforced by the kernel GUID type on bind (03 §12) |
| `alembic downgrade -1` | refused (NotImplementedError) | refused (NotImplementedError) |
| Re-upgrade after refused downgrade | 0100_crm_leads | 0100_crm_leads |

**Rollback boundary.** Down-migrations are deliberately unsupported: 02 §12.4 makes every migration expand-only and
N-1-compatible, and rollback is (normal) redeploying the N-1 image on the migrated schema or (disaster) restoring
the pre-migration snapshot. Additional migration tests: upgrade-with-data from 0008 to head
(`test_migration_upgrade_with_data`, both engines), models-match-schema (`test_PLAT_005_…`), purge ordering with
`foreign_keys=ON` (`test_DATA_017_…`), TD-H negative fixtures (12 cases). No migration requires manual data editing.

## 4. API catalog

105 routes. Each declares a permission code or an RBX exception; startup fails otherwise (06 §8). 08 index row 75
(`POST /leads/exports`, P1) is not built. `POST /api/v1/approvals/cancel-link` implements the 06 §7.5 signed
break-glass cancel link (see §13 OI-2).

| # | Method | Path | Gate | Req |
|---|---|---|---|---|
| 1 | GET | `/health/live` | RBX-006 | LOG-005 |
| 2 | GET | `/health/ready` | RBX-006 | LOG-005 |
| 3 | GET | `/api/v1/activities` | `lead_activity.read` | LEAD-015 |
| 4 | GET | `/api/v1/approvals` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 5 | GET | `/api/v1/approvals/{approval_id}` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 6 | POST | `/api/v1/approvals/{approval_id}/approve` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 7 | POST | `/api/v1/approvals/{approval_id}/cancel` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 8 | POST | `/api/v1/approvals/{approval_id}/deny` | `user.mfa.reset` / `user.email.change` / `user.founder.manage` (any) | RBAC-021 |
| 9 | POST | `/api/v1/approvals/cancel-link` | RBX-003 | RBAC-021 |
| 10 | GET | `/api/v1/audit-logs` | `audit.read` | AUDIT-008 |
| 11 | GET | `/api/v1/audit-logs/{audit_id}` | `audit.read` | AUDIT-008 |
| 12 | GET | `/api/v1/auth/.well-known/jwks.json` | RBX-006 | AUTH-004 |
| 13 | POST | `/api/v1/auth/email/cancel` | RBX-003 | USER-007 |
| 14 | POST | `/api/v1/auth/email/verify` | RBX-003 | USER-007 |
| 15 | POST | `/api/v1/auth/invite/accept` | RBX-003 | AUTH-011 |
| 16 | POST | `/api/v1/auth/login` | RBX-001 | AUTH-001 |
| 17 | POST | `/api/v1/auth/logout` | RBX-002 | AUTH-007 |
| 18 | POST | `/api/v1/auth/logout-all` | RBX-002 | AUTH-007 |
| 19 | GET | `/api/v1/auth/me` | `profile.read` | USER-004 |
| 20 | PATCH | `/api/v1/auth/me` | `profile.update` · If-Match | USER-004 |
| 21 | PUT | `/api/v1/auth/me/email` | RBX-004 | USER-007 |
| 22 | GET | `/api/v1/auth/mfa` | `profile.read` | MFA-001 |
| 23 | POST | `/api/v1/auth/mfa/enroll/confirm` | RBX-004 | MFA-014 |
| 24 | POST | `/api/v1/auth/mfa/enroll/start` | RBX-004 | MFA-014 |
| 25 | DELETE | `/api/v1/auth/mfa/factor` | RBX-004 | MFA-003 |
| 26 | POST | `/api/v1/auth/mfa/recovery` | RBX-001 | MFA-013 |
| 27 | POST | `/api/v1/auth/mfa/recovery-codes` | RBX-004 | MFA-005 |
| 28 | POST | `/api/v1/auth/mfa/step-up` | RBX-004 | MFA-011 |
| 29 | POST | `/api/v1/auth/mfa/verify` | RBX-001 | MFA-001 |
| 30 | POST | `/api/v1/auth/password/change` | RBX-004 | AUTH-012 |
| 31 | POST | `/api/v1/auth/password/forgot` | RBX-003 | AUTH-008 |
| 32 | POST | `/api/v1/auth/password/reset` | RBX-003 | AUTH-008 |
| 33 | POST | `/api/v1/auth/reauth` | RBX-004 | MFA-011 |
| 34 | POST | `/api/v1/auth/refresh` | RBX-002 | AUTH-005 |
| 35 | GET | `/api/v1/auth/sessions` | `session.read` | AUTH-016 |
| 36 | DELETE | `/api/v1/auth/sessions/{session_id}` | `session.revoke` | AUTH-016 |
| 37 | POST | `/api/v1/founder-actions` | `user.founder.manage` | RBAC-021 |
| 38 | GET | `/api/v1/leads` | `lead.read` | LEAD-013 |
| 39 | POST | `/api/v1/leads` | `lead.create` | LEAD-003 |
| 40 | DELETE | `/api/v1/leads/{lead_id}` | `lead.delete` · If-Match | LEAD-016 |
| 41 | GET | `/api/v1/leads/{lead_id}` | `lead.read` | LEAD-013 |
| 42 | PATCH | `/api/v1/leads/{lead_id}` | `lead.update` · If-Match | LEAD-024 |
| 43 | GET | `/api/v1/leads/{lead_id}/activities` | `lead_activity.read` | ACT-001 |
| 44 | POST | `/api/v1/leads/{lead_id}/activities` | `lead_activity.create` | ACT-001 |
| 45 | DELETE | `/api/v1/leads/{lead_id}/activities/{activity_id}` | `lead_activity.delete` · If-Match | ACT-002 |
| 46 | PATCH | `/api/v1/leads/{lead_id}/activities/{activity_id}` | `lead_activity.update` · If-Match | ACT-002 |
| 47 | POST | `/api/v1/leads/{lead_id}/activities/{activity_id}/cancel` | `lead_activity.update` · If-Match | ACT-003 |
| 48 | POST | `/api/v1/leads/{lead_id}/activities/{activity_id}/complete` | `lead_activity.update` · If-Match | ACT-003 |
| 49 | POST | `/api/v1/leads/{lead_id}/assign` | `lead.assign` · If-Match | LEAD-007 |
| 50 | POST | `/api/v1/leads/{lead_id}/consent/withdraw` | `lead.update` · If-Match | LEAD-027 |
| 51 | POST | `/api/v1/leads/{lead_id}/duplicate-resolution` | `lead.update` | LEAD-010 |
| 52 | POST | `/api/v1/leads/{lead_id}/erasure` | `lead.erase` · If-Match | LEAD-029 |
| 53 | GET | `/api/v1/leads/{lead_id}/history` | `lead.read` + `audit.read` | AUDIT-006 |
| 54 | GET | `/api/v1/leads/{lead_id}/notes` | `lead_note.read` | NOTE-001 |
| 55 | POST | `/api/v1/leads/{lead_id}/notes` | `lead_note.create` | NOTE-001 |
| 56 | DELETE | `/api/v1/leads/{lead_id}/notes/{note_id}` | `lead_note.delete` · If-Match | NOTE-002 |
| 57 | PATCH | `/api/v1/leads/{lead_id}/notes/{note_id}` | `lead_note.update` · If-Match | NOTE-002 |
| 58 | POST | `/api/v1/leads/{lead_id}/restore` | `lead.restore` · If-Match | LEAD-016 |
| 59 | POST | `/api/v1/leads/{lead_id}/spam-resolution` | `lead.update` · If-Match | LEAD-018 |
| 60 | POST | `/api/v1/leads/{lead_id}/status` | `lead.status.change` / `lead.reopen` (any) · If-Match | LEAD-005 |
| 61 | GET | `/api/v1/leads/duplicates` | `lead.read` | LEAD-010 |
| 62 | GET | `/api/v1/leads/summary` | `lead.read` | LEAD-014 |
| 63 | GET | `/api/v1/lookups` | `lookup.read` | PLAT-009 |
| 64 | GET | `/api/v1/lookups/{category_code}` | `lookup.read` | PLAT-009 |
| 65 | POST | `/api/v1/lookups/{category_code}/values` | `lookup.manage` | PLAT-009 |
| 66 | PATCH | `/api/v1/lookups/{category_code}/values/{value_id}` | `lookup.manage` · If-Match | PLAT-009 |
| 67 | GET | `/api/v1/notifications` | `notification.read` | NOTIF-001 |
| 68 | POST | `/api/v1/notifications/{notification_id}/read` | `notification.read` | NOTIF-001 |
| 69 | POST | `/api/v1/notifications/read-all` | `notification.read` | NOTIF-001 |
| 70 | GET | `/api/v1/permissions` | `permission.read` | RBAC-004 |
| 71 | GET | `/api/v1/permissions/{permission_id}` | `permission.read` | RBAC-004 |
| 72 | PATCH | `/api/v1/permissions/{permission_id}` | `permission.manage` · If-Match | RBAC-004 |
| 73 | GET | `/api/v1/permissions/{permission_id}/holders` | `permission.read` + `user.read` | RBAC-016 |
| 74 | POST | `/api/v1/public/leads` | RBX-005 | LEAD-001 |
| 75 | GET | `/api/v1/roles` | `role.read` | RBAC-008 |
| 76 | POST | `/api/v1/roles` | `role.manage` | RBAC-008 |
| 77 | DELETE | `/api/v1/roles/{role_id}` | `role.manage` · If-Match | RBAC-008 |
| 78 | GET | `/api/v1/roles/{role_id}` | `role.read` | RBAC-008 |
| 79 | PATCH | `/api/v1/roles/{role_id}` | `role.manage` · If-Match | RBAC-008 |
| 80 | GET | `/api/v1/roles/{role_id}/permissions` | `role.read` | RBAC-008 |
| 81 | PUT | `/api/v1/roles/{role_id}/permissions` | `role.manage` | RBAC-009 |
| 82 | GET | `/api/v1/roles/{role_id}/users` | `role.read` + `user.read` | RBAC-008 |
| 83 | GET | `/api/v1/security-events` | `security_event.read` | SEVT-005 |
| 84 | GET | `/api/v1/security-events/{event_id}` | `security_event.read` | SEVT-005 |
| 85 | GET | `/api/v1/users` | `user.read` | USER-001 |
| 86 | POST | `/api/v1/users` | `user.create` | USER-001 |
| 87 | DELETE | `/api/v1/users/{user_id}` | `user.delete` · If-Match | USER-001 |
| 88 | GET | `/api/v1/users/{user_id}` | `user.read` | USER-001 |
| 89 | PATCH | `/api/v1/users/{user_id}` | `user.profile.update` · If-Match | RBAC-019 |
| 90 | GET | `/api/v1/users/{user_id}/effective-permissions` | `user.read` + `permission.read` | RBAC-016 |
| 91 | POST | `/api/v1/users/{user_id}/email-change` | `user.email.change` · If-Match | USER-007 |
| 92 | POST | `/api/v1/users/{user_id}/invite/resend` | `user.create` | AUTH-011 |
| 93 | PUT | `/api/v1/users/{user_id}/mfa-requirement` | `user.mfa.require` · If-Match | MFA-003 |
| 94 | POST | `/api/v1/users/{user_id}/mfa/reset` | `user.mfa.reset` · If-Match | MFA-007 |
| 95 | POST | `/api/v1/users/{user_id}/password-reset` | `user.password.reset` | AUTH-008 |
| 96 | GET | `/api/v1/users/{user_id}/permissions` | `user.read` | RBAC-006 |
| 97 | POST | `/api/v1/users/{user_id}/permissions` | `user.permission.manage` | RBAC-006 |
| 98 | DELETE | `/api/v1/users/{user_id}/permissions/{grant_id}` | `user.permission.manage` | RBAC-006 |
| 99 | POST | `/api/v1/users/{user_id}/restore` | `user.restore` | USER-001 |
| 100 | GET | `/api/v1/users/{user_id}/roles` | `user.read` | RBAC-008 |
| 101 | PUT | `/api/v1/users/{user_id}/roles` | `user.role.manage` | RBAC-009 |
| 102 | POST | `/api/v1/users/{user_id}/sessions/revoke` | `user.session.revoke` | AUTH-016 |
| 103 | POST | `/api/v1/users/{user_id}/status` | `user.status.manage` · If-Match | RBAC-019 |
| 104 | POST | `/api/v1/users/{user_id}/unlock` | `user.status.manage` | AUTH-010 |
| 105 | GET | `/api/v1/users/assignable` | `lead.assign` | LEAD-007 |

## 5. UI screens (`app/`, 09 §4)

Login · MFA challenge · recovery · recovery-mode shell · enrollment (paths A–D) · recovery codes · forgot/reset password
· accept invitation · verify/cancel email change · change password · dashboard · lead list (filters, spam-review queue,
mobile cards) · lead detail (stepper, transitions, assignment, timeline, notes, activities, duplicate/spam review,
consent withdrawal, delete, erasure, history) · lead create/edit · follow-ups · users (invite; profile/access/security/
sessions) · roles (matrix editor; FOUNDER locked) · permissions · audit log and security events · approvals · Founder
actions · profile · notifications tray · command palette · step-up and version-conflict dialogs · no-access page.
Website: enquiry-form states of 09 §4.11.

## 6. Permissions and role mappings (06 §6, code registry `api/veda/platform/rbac/registry.py`)

45 permissions, 16 sensitive. ALL/OWN = scope; ✓ = granted without scope; — = not granted. SALES holds no sensitive
permission; `user.founder.manage` exists only in FOUNDER (asserted by migration 0003 and unit tests).

| Permission | Module | Sensitivity | Grant path | FOUNDER | ADMIN | SALES |
|---|---|---|---|---|---|---|
| `profile.read` | platform | — | STANDARD | ✓ | ✓ | ✓ |
| `profile.update` | platform | — | STANDARD | ✓ | ✓ | ✓ |
| `session.read` | platform | — | STANDARD | OWN | OWN | OWN |
| `session.revoke` | platform | — | STANDARD | OWN | OWN | OWN |
| `notification.read` | platform | — | STANDARD | OWN | OWN | OWN |
| `lookup.read` | platform | — | STANDARD | ✓ | ✓ | ✓ |
| `user.read` | platform | — | STANDARD | ✓ | ✓ | — |
| `user.create` | platform | — | STANDARD | ✓ | ✓ | — |
| `user.profile.update` | platform | — | STANDARD | ✓ | ✓ | — |
| `user.email.change` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.status.manage` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.delete` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | — | — |
| `user.restore` | platform | — | STANDARD | ✓ | — | — |
| `user.password.reset` | platform | — | STANDARD | ✓ | ✓ | — |
| `user.session.revoke` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.role.manage` | platform | ACCESS_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.permission.manage` | platform | ACCESS_CONTROL | STANDARD | ✓ | — | — |
| `user.mfa.reset` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.mfa.require` | platform | ACCOUNT_CONTROL | STANDARD | ✓ | ✓ | — |
| `user.founder.manage` | platform | ACCOUNT_CONTROL | FOUNDER_WORKFLOW_ONLY | ✓ | — | — |
| `role.read` | platform | — | STANDARD | ✓ | ✓ | — |
| `role.manage` | platform | ACCESS_CONTROL | STANDARD | ✓ | ✓ | — |
| `permission.read` | platform | — | STANDARD | ✓ | ✓ | — |
| `permission.manage` | platform | ACCESS_CONTROL | STANDARD | ✓ | — | — |
| `audit.read` | platform | SECURITY_DATA | STANDARD | ✓ | ✓ | — |
| `security_event.read` | platform | SECURITY_DATA | STANDARD | ✓ | ✓ | — |
| `lookup.manage` | platform | — | STANDARD | ✓ | ✓ | — |
| `lead.create` | crm | — | STANDARD | ✓ | ✓ | ✓ |
| `lead.read` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead.update` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead.status.change` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead.reopen` | crm | — | STANDARD | ALL | ALL | — |
| `lead.assign` | crm | — | STANDARD | ALL | ALL | — |
| `lead.delete` | crm | DESTRUCTIVE | STANDARD | ALL | ALL | — |
| `lead.restore` | crm | — | STANDARD | ✓ | ✓ | — |
| `lead.erase` | crm | DESTRUCTIVE | STANDARD | ✓ | — | — |
| `lead.export` | crm | BULK_DATA | STANDARD | ✓ | — | — |
| `lead_note.create` | crm | — | STANDARD | ✓ | ✓ | ✓ |
| `lead_note.read` | crm | — | STANDARD | ALL | ALL | ALL |
| `lead_note.update` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead_note.delete` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead_activity.create` | crm | — | STANDARD | ✓ | ✓ | ✓ |
| `lead_activity.read` | crm | — | STANDARD | ALL | ALL | ALL |
| `lead_activity.update` | crm | — | STANDARD | ALL | ALL | OWN |
| `lead_activity.delete` | crm | — | STANDARD | ALL | ALL | OWN |

## 7. Test commands and results (clean environment)

Environment: macOS (darwin 25.6, arm64) · Python 3.13.7 in a new venv from `api/requirements-dev.txt` · Node 20.9.0,
npm 10.1.0 with `npm ci` · SQLite 3.50.4 (Python module) · PostgreSQL 18.4 (embedded via `pixeltable-pgserver`) ·
Chromium (Playwright). The working tree's commit set was copied to an empty directory (`git ls-files -co
--exclude-standard`) and verified byte-identical before the final runs.

| # | Command (from `api/` or `app/`) | Exit | Result |
|---|---|---|---|
| 1 | `ruff check veda tests migrations tools` | 0 | All checks passed |
| 2 | `ruff format --check veda tests migrations tools` | 1 | 82 files would be reformatted — **no formatter is configured or enforced**; not applied (would be unrelated churn) |
| 3 | static type analysis (mypy) | — | **Not configured** |
| 4 | `VEDA_TEST_ENGINES=sqlite python -m pytest -o addopts="" -q -rs` | 0 | **273 passed, 0 failed, 0 skipped** |
| 5 | `VEDA_TEST_ENGINES=postgresql python -m pytest -o addopts="" -q -rs` | 0 | **271 passed, 0 failed, 2 skipped** (SQLite-only checks) |
| 6 | `python evidence/migration_evidence.py` | 0 | §3 |
| 7 | `pip-audit -r requirements.txt` | 0 | No known vulnerabilities |
| 8 | `bandit -q -r veda` | 1 | 1 High, 2 Medium, 18 Low — all triaged false positives (§12) |
| 9 | `npm ci` | 0 | Installed; reports 195 advisories in **dev** tooling (runtime: see #15) |
| 10 | `npm run typecheck` | 0 | tsc strict, no errors |
| 11 | `npm run lint:tokens` | 0 | No raw colours outside tokens (the only frontend lint configured; no ESLint) |
| 12 | `npm test` (Web Test Runner, Chromium) | 0 | **47 passed, 0 failed** |
| 13 | `npm run build` | 0 | Initial JS 39.48 KB gzip (budget 200 KB) |
| 14 | `npm run test:contrast` | 0 | 58 token pairs pass, light + dark |
| 15 | `npm audit --omit=dev` | 0 | **0 vulnerabilities** in shipped dependencies |
| 16 | `node e2e/workspace.e2e.mjs` | 0 | 7/7 |
| 17 | `node e2e/access.e2e.mjs` | 0 | 12/12 |
| 18 | `node e2e/site.e2e.mjs` | 0 | 7/7 |
| 19 | `node e2e/axe.e2e.mjs` | 1 | Workspace 8/8 screens with 0 violations; website 19 serious contrast nodes, **all pre-existing at 778aa8f** (§10) |

Per-suite breakdown (JUnit: `evidence/pytest-sqlite.xml`, `evidence/pytest-postgresql.xml`). Unit suites are
engine-independent and ran in both invocations; each engine executed all 208 integration tests itself:

| Suite file | SQLite pass/fail/skip | PostgreSQL pass/fail/skip |
|---|---|---|
| `tests/integration/test_api_contract` | 21/0/0 | 21/0/0 |
| `tests/integration/test_audit_security` | 17/0/0 | 17/0/0 |
| `tests/integration/test_auth` | 23/0/0 | 23/0/0 |
| `tests/integration/test_founder_governance` | 16/0/0 | 16/0/0 |
| `tests/integration/test_leads` | 53/0/0 | 53/0/0 |
| `tests/integration/test_mfa` | 15/0/0 | 15/0/0 |
| `tests/integration/test_rbac` | 33/0/0 | 33/0/0 |
| `tests/integration/test_schema` | 28/0/0 | 26/0/2 |
| `tests/integration/test_smoke` | 2/0/0 | 2/0/0 |
| `tests/unit/test_email_templates` | 2/0/0 | 2/0/0 |
| `tests/unit/test_ids_time_jcs` | 14/0/0 | 14/0/0 |
| `tests/unit/test_lint` | 8/0/0 | 8/0/0 |
| `tests/unit/test_registry_resolver` | 24/0/0 | 24/0/0 |
| `tests/unit/test_totp_passwords` | 17/0/0 | 17/0/0 |
| **Total** | **273/0/0** | **271/0/2** |

Coverage by requested category: API (`test_api_contract`, `test_leads`), authentication (`test_auth`), MFA and recovery
(`test_mfa`: TD-C, TD-D, TD-E), RBAC and DENY-over-GRANT (`test_rbac` incl. TD-A, `test_registry_resolver` 3×3×2 table),
Founder governance (`test_founder_governance`, TD-G G1–G14), audit and security events (`test_audit_security`),
migrations and schema (`test_schema` incl. TD-H), concurrency (TD-F two-writer, TD-G G10, sequence allocation).

## 8. Browser-test evidence (live stack, from the clean copy)

API: `flask --app wsgi run` on SQLite (`VEDA_COOKIE_SECURE=false`, capture email adapter); SPA: Vite dev server;
site: static server with `veda-api-base` set (a copy; the committed site keeps it empty). Founder created with the real
`bootstrap-founder` CLI. Browser runs used **SQLite only**; PostgreSQL browser runs were not executed.

| Journey | Script | Result |
|---|---|---|
| Invitation + forced MFA enrollment (path B), recovery codes | workspace | PASS |
| Dashboard | workspace | PASS |
| Lead submitted from the website appears in the admin list | workspace, site | PASS |
| Lead detail + status change | workspace | PASS |
| Audit visibility | workspace | PASS |
| Sign out (account menu) and sign in with authenticator code | workspace | PASS |
| Mobile layout 360 px (lead list, website) | workspace, site | PASS |
| Permission denial (Sales: no admin nav, no-access page, API 401/403) | access | PASS |
| Session expiry by admin revoke (reload → sign-in; in-app → banner) | access | PASS |
| Logout ends the session; protected routes redirect | access | PASS |
| Repeated submission (same key) → original reference; different body → refused | access | PASS |
| Invalid website submission → field errors only | access, site | PASS |
| Duplicate submission stored and flagged, visible in admin | access | PASS |
| Website: error summary focus, honeypot, WhatsApp fallback, flag-off hand-off | site | PASS |
| Console/page errors | all | 0 |
| Email-adapter failure | — | **Not browser-testable**; covered by API tests `test_TD_B_…` (step 6), `test_NOTIF_003_…` |
| Re-consent (DEV-004) | — | Staff API only; covered by `test_DEV_004_…` |

Defects found by these journeys during this freeze and fixed: account-menu and forced-password "Sign out" did not
navigate to sign-in (`app/src/shell/app.ts`, `app/src/modules/auth/password-pages.ts`); two accessibility issues
introduced by the enquiry form (optional-label contrast 4.06:1 → `#5d574f`; error-summary link target size).

## 9. SQLite evidence

Test run #4 (273/0/0), migration evidence §3, and all browser journeys §8. SQLite enforces UUIDv7 format, JSON validity,
booleans and lengths with CHECK constraints; WAL, `foreign_keys=ON`, `busy_timeout=5000` verified at startup and in
`test_DATA_010_…`.

## 10. PostgreSQL evidence

Test run #5 (271/0/2) executed independently against embedded PostgreSQL 18.4; migration evidence §3. The two skipped
tests are SQLite-only by design (`PRAGMA` checks and SQLite format CHECK fixture). Not executed on PostgreSQL: browser
journeys, the migration from an existing SQLite dataset to PostgreSQL (11 §3.4 release gate), PostgreSQL 16 (the
architecture's stated target version; 18.4 was used).

**Website accessibility.** axe (reduced motion, error state) finds 19 serious `color-contrast` nodes on the site; the
same 19 exist at `778aa8f` (`evidence/axe-site-baseline-diff.txt`; the one "introduced" entry is the pre-existing
`.form-note` paragraph whose selector changed because it gained an `id`). These are existing marketing-site styles
outside this change and were not altered.

## 11. Deviations

See [P0-implementation-deviations.md](P0-implementation-deviations.md). DEV-001 MFA factor uniqueness · DEV-002 invitation
enrollment step · DEV-003 optional login CAPTCHA token · DEV-004 staff re-consent object (the brief's description of
DEV-004 is corrected in the register: public or repeated submissions accept **no** re-consent object). All PENDING
INDEPENDENT REVIEW; none approved.

## 12. Security-check evidence

Automated checks are supporting evidence only; manual security review is still required.

| Area | Evidence |
|---|---|
| Dependency vulnerabilities | pip-audit: none · npm runtime: none · npm dev tooling: 195 advisories (17 critical, 5 high, 173 low) (Vite 5 dev server, Web Test Runner) — §13 OI-10 |
| Secret scanning | detect-secrets over the commit set: only test fixtures, fixed test UUIDs, alphabets, error titles, CI ephemeral Postgres credentials, and pre-existing architecture-doc samples; regex scan (AWS keys, private keys, tokens): none; no db/pem/key/env/eml files |
| Static analysis | bandit: High B701 (plain-text email Jinja env; HTML env autoescapes — `test_NOTIF_009_…`, `test_email_templates`), Medium B608 (migration DDL from constants), Medium B310 (constant https Turnstile URL): false positives |
| Unsafe Flask config / debug | No `debug=True`/`app.run`; production refuses dev secrets, insecure cookies, non-SES/KMS/Turnstile and weak Argon2 (`config.validate_production`) |
| CORS | Exact allowlist; credentials only for the app origin; site origin only on public endpoints (`test_SEC_002_cors_allowlist`) |
| Missing authorization | Startup route-declaration check; `test_RBAC_012_…`, `test_startup_fails_for_undeclared_route`, role × endpoint matrix |
| Mass assignment | `test_RBAC_019_mass_assignment_rejected` (9 fields × 2 endpoints), closed DTOs (`test_SEC_004_…`) |
| SQL injection | ORM parameterized queries; lint bans raw SQL/bulk mutation in services (`test_no_raw_sql_or_bulk_mutation_in_services`) |
| Unsafe deserialization | No pickle/yaml/eval/exec (grep) |
| Password hashing | Argon2id (`test_AUTH_002_…`), policy (`test_AUTH_003_…`), timing-equalized unknown users |
| JWT validation | ES256, typ/kid/aud/iss, expiry via platform clock (`test_AUTH_004_…`), per-request uncached session check (`test_AUTH_006_…`) |
| Refresh rotation | Rotation, 20 s grace, reuse → revoke (`test_AUTH_005_…` ×2), CSRF (`test_CSRF_…` ×3) |
| MFA recovery | `test_MFA_013_…`, TD-C, TD-D, TD-E, replay (`test_MFA_009_…`) |
| Authorization-cache invalidation | TD-A next-request propagation, `test_RBAC_013_…` |
| Founder governance | TD-G G1–G14 |
| Last privileged user | G11 LAST_FOUNDER, I2 LAST_ADMINISTRATOR, concurrent execution (G10) |
| PII in logs | Masking processor; E2E API log: 0 emails, phone numbers or tokens in structured lines (Werkzeug dev-server access lines include search query strings; production gunicorn has `accesslog = None`) |
| Tamper-evident chain | `test_SEVT_006_…` (tamper, wrong key, gap), anchor and archival (`test_SEVT_007_…`, `test_SEVT_004_…`), live DB verify |
| Email header injection | Subjects are whitespace-collapsed (`test_subject_cannot_carry_header_injection`); SES receives subject as data |
| CAPTCHA bypass | Idempotency before CAPTCHA only replays the original response (`test_TD_B_…`); `test_captcha_failure_blocks_and_records`; login captcha (`test_DEV_003_…`) |
| Lead enumeration | Public response is exactly `{reference, message}`; no public read endpoint; duplicates undisclosed (`test_TD_B_…`, `test_LEAD_001_…`) |
| Request throttling | `test_rate_limits_public_intake`, `test_AUTH_010_…` ×2, MFA attempt limits |

## 13. Open issues

| # | Issue |
|---|---|
| OI-1 | Deviations DEV-001…DEV-004 need an architecture decision (register). |
| OI-2 | Break-glass cancel link `POST /api/v1/approvals/cancel-link` is not in the 08 index (capability from 06 §7.5). Not in the deviation register because the brief fixed the register at four entries; reviewer to classify. |
| OI-3 | Single-use action tokens are derived as `HMAC(K_action, row id ‖ purpose)` so the worker can build email links without storing secrets (only SHA-256 stored). Implementation detail for review. |
| OI-4 | `ERASURE_BLOCKED` has no legal-hold data model in P0; blocking is configured by `VEDA_ERASURE_BLOCKED_STATUSES` (empty). |
| OI-5 | Website: Privacy Notice page `/privacy` (v2026-09-v1) does not exist; Turnstile site key and site CSP `connect-src` not configured. Intake stays off until they are. |
| OI-6 | AWS adapters (SES, KMS, S3 Object Lock anchor) untested without AWS; security-event archival writes JSONL locally (no S3 upload). |
| OI-7 | Alerts are structured CRITICAL/ERROR logs only; the "enrollment from an unseen network" High alert (05 §11.3) is not implemented. |
| OI-8 | No formatter or type checker configured (`ruff format --check` → 82 files; mypy absent); no ESLint. |
| OI-9 | Browser E2E scripts are standalone, need a running stack, and are not in CI; CI workflow was written but not executed. |
| OI-10 | Dev tooling pinned to Vite 5 / Web Test Runner 0.20 (Node 20.9 on this machine); `npm audit` reports critical advisories in these dev-only packages. Upgrade requires Node ≥ 20.19. |
| OI-11 | Pre-existing marketing-site contrast issues (19 nodes) outside this change. |

## 14. Known limitations

P1 items intentionally absent: time-bound grants (422), CSV export, quoted amount, HIBP breach check, compare-roles,
reminder email digest. Scheduler is a simple loop spawning maintenance processes. In-process rate limits, throttles and
authenticated idempotency are lost on restart (by design for the single-process deployment). PostgreSQL native `uuid`
accepts non-v7 UUIDs from raw SQL (kernel-enforced only). Security-event chain key and HMAC keys come from environment
variables; SSM wiring is deployment work.

## 15. Risks

| # | Risk | Likelihood | Impact | Mitigation / action |
|---|---|---|---|---|
| R1 | SQLite write contention at peak | Low | Medium | BEGIN IMMEDIATE, busy_timeout, 503 mapping; load test RG-4 |
| R2 | More than one app process deployed | Medium | High | gunicorn 1 worker, `deploy-check`; enforce in deploy pipeline |
| R3 | Host/chain-key compromise rewrites recent security events | Low | High | Keyed chain, nightly verify; configure S3 Object Lock anchor |
| R4 | Retention values unset → unbounded growth | Certain until owner input | Low | Jobs refuse; OWNER-INPUT-002 |
| R5 | No break-glass custodians → single-Founder actions blocked | Certain until owner input | High | OWNER-INPUT-004 |
| R6 | Intake enabled without privacy notice / Turnstile | Medium | Medium | Flag off by default (OI-5) |
| R7 | AWS adapters fail at first use | Medium | Medium | Staging verification (OI-6) |
| R8 | Deviations rejected in review | Medium | Low–Medium | Each has a rollback path (register) |
| R9 | Dev-tooling vulnerabilities on developer machines | Medium | Low | Upgrade Node/Vite/WTR (OI-10) |

## 16. Production gates not executed

From `docs/architecture/gate-registry.md` and 12 §4.9 — none were executed in this workstream:
owner approvals TG-01 (and recording TG-08); OWNER-INPUT-001 (RPO/RTO, availability), -002 (retention values),
-003 (restore-rehearsal cadence), -004 (break-glass custodians); DAST and manual penetration test (PG-DAST); load and
SQLite contention at ASM-007 sizes (RG-4); restore verification, rebuild and migration-runbook rehearsals (RG-1, RG-2,
RG-7); alert test-fires (RG-5); volume/instance/worker-count checks on the real host (RG-3, RG-6); Litestream
replication; PostgreSQL release gate (11 §3.3) including data migration; browser/device matrix (Firefox, WebKit,
Android, iOS) and screen-reader scripts; staging deployment and SES production access.

## 17. Manual actions still required

1. Independent implementation review of the commit, this report and the deviation register.
2. Architecture Owner decisions on DEV-001…DEV-004 and OI-2/OI-3 (architecture amendments if accepted).
3. Owner inputs OWNER-INPUT-001…004; record TG-01/TG-08 in the gate registry.
4. Publish the Privacy Notice (v2026-09-v1); provision Turnstile; then set `veda-api-base` and the site CSP.
5. Provision production secrets in SSM (JWT ES256 key, HMAC keys, chain key, Turnstile secret), KMS key, SES identity,
   S3 anchor bucket (Object Lock), Litestream bucket.
6. Stand up staging; run the staging E2E, AWS adapter verification and all §16 gates.
7. Decide on formatter/type-checker adoption and upgrade the frontend dev toolchain (OI-8, OI-10).

## 18. Corrections to earlier claims

- The first report's "473 passed" combined both engines in one run; the independently evidenced figures are SQLite
  273/0/0 and PostgreSQL 271/0/2 (each includes the 65 engine-independent unit tests).
- "Browser E2E 14 checks" is superseded by §8 (7 + 12 + 7 journeys/checks + axe).
- The first report called the result "implementation complete"; the accurate status is below.

## 19. Status

**The implementation is not certified, not merged and not deployed.** It is committed on
`implementation/p0-foundation` for independent implementation review. The certified architecture documents are
unchanged, and all four deviations await review.
