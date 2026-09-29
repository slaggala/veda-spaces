# 06 — RBAC Design

Governing decisions: [ADR-001](decisions/ADR-001-app-user-table.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-009](decisions/ADR-009-p0-scope.md)

## 1. Model

```
                   ┌──────────────┐
                   │  permission  │  code, module, resource, action, supports_scope, is_sensitive
                   └──────▲───────┘
            ┌─────────────┴───────────────┐
  ┌─────────┴────────┐          ┌─────────┴─────────┐
  │ role_permission  │          │  user_permission  │  effect GRANT|DENY, scope, validity, reason
  │ scope            │          └─────────▲─────────┘
  └─────────▲────────┘                    │
      ┌─────┴────┐                        │
      │   role   │                        │
      └─────▲────┘                        │
      ┌─────┴──────┐                      │
      │ user_role  │ validity             │
      └─────▲──────┘                      │
            └──────────── app_user (entity User) ───────┘
```

An **authorization decision** is `can(actor, permission_code, resource?) → allow | deny`.

- With no resource (a collection or create action), only the permission is checked.
- With a resource, the permission and its **scope** are checked against the row.

## 2. Principles (RBAC-002)

1. **Code checks permission codes only.** Nothing in the code references role codes (`FOUNDER`, `ADMIN`), "is_admin" flags, or specific user ids. A CI lint rejects role-code string literals outside migrations and seed files.
2. **The Founder is not special in code.** The Founder has every permission because the seeded matrix grants them all. A migration that adds a permission must also grant it to the roles meant to hold it. This is enforced by a registry test: every permission must be granted to at least one system role.
3. **Deny by default.** No grant means deny.
4. **An explicit DENY beats any GRANT** (RBAC-006).
5. **Least privilege.** Sales gets OWN scope by default.
6. **Server-authoritative.** UI checks are hints only (RBAC-012).
7. **MFA policy is data too.** Whether a user needs MFA comes from `role.mfa_required`, `app_user.mfa_required` and holding sensitive permissions (05 §11.1). It never comes from role names (MFA-002).

## 3. Permission registry and naming (RBAC-003, RBAC-004, RBAC-015)

- **Naming:** `<resource>.<action>` or `<resource>.<sub>.<action>`, lowercase, singular resource. Examples: `lead.read`, `lead.status.change`, `user.role.assign`.
- **Source of truth:** each module declares its permissions in a code registry. Each entry has code, name, description, `supports_scope`, `is_sensitive` and `requirement_ref`.
- **Sync:** a migration step (and a CLI `sync-permissions` used by migrations) upserts registry entries into `permission`.
  - New codes are inserted.
  - Changed metadata is updated.
  - Removed codes are soft-deleted.
  - Codes are never renamed. To rename, add the new code, migrate grants, and soft-delete the old one.
- **The API cannot create or delete permissions.** `permission.manage` allows editing `name` and `description`, and assigning permissions directly to users. Assigning to roles falls under `role.manage`.
- **Sensitive permissions** (`is_sensitive = true`, RBAC-017):
  - They are visually flagged.
  - Granting them requires a `reason` and step-up MFA (05 §11.6).
  - Holding any of them makes MFA mandatory for the holder (MFA-004).
  - Every use writes a `SENSITIVE_ACTION` security event (05 §9.1).
  - Grants trigger an email to all holders of `permission.manage`.

## 4. Data scope (RBAC-005)

| Scope | Meaning | P0 status |
|---|---|---|
| `ALL` | Every row of the resource | Active |
| `TEAM` | Rows owned by any member of the actor's org unit(s) | **Reserved.** The value is valid in schema but rejected by the service until `org_unit` exists (10 §4). |
| `OWN` | Rows the actor owns, as defined per resource below | Active |

Scope ordering for "broadest wins": `ALL > TEAM > OWN`.

**Ownership definitions:**

| Resource | Actor "owns" a row when |
|---|---|
| `lead` | `lead.assigned_to = actor` **or** `lead.created_by = actor` |
| `lead_note` | Read: the parent lead is visible to the actor · update/delete: `lead_note.created_by = actor` |
| `lead_activity` | Read: the parent lead is visible · update/delete: `owner_user_id = actor` or `created_by = actor` |
| `notification` | `recipient_user_id = actor` |
| `user_session` | `user_id = actor` |
| `app_user` (profile) | `id = actor` |

**Child visibility rule.** A child row (note, activity) is never visible unless its parent lead is visible to the actor under `lead.read`. The child permission's scope then narrows further.

## 5. Resolution algorithm

> Traces: RBAC-006, RBAC-007, RBAC-016

```
effective_permissions(user) → map<permission_code, scope>

 0. if user.status ≠ ACTIVE or user.is_deleted  → ∅
 1. now = clock()
 2. denies  = { p.code | user_permission(user, p) where effect=DENY  ∧ live(now) ∧ ¬p.is_deleted }
 3. grants  = [ (p.code, rp.scope) | user_role(user, r) live(now) ∧ ¬r.is_deleted
                                      ∧ role_permission(r, p) live ∧ ¬p.is_deleted ]
            ∪ [ (p.code, up.scope) | user_permission(user, p) where effect=GRANT ∧ live(now) ∧ ¬p.is_deleted ]
 4. for each code in grants: scope[code] = max(scope over its grants)   // ALL > TEAM > OWN
 5. remove every code ∈ denies
 6. for permissions with supports_scope=false: scope := ALL
 7. return scope map

live(now) := ¬is_deleted ∧ (valid_from IS NULL ∨ valid_from ≤ now) ∧ (valid_until IS NULL ∨ valid_until > now)

can(actor, code)            := code ∈ effective(actor)
can(actor, code, row)       := code ∈ effective(actor) ∧ in_scope(effective(actor)[code], actor, row)
list_filter(actor, code)    := ALL → no filter · OWN → ownership predicate · none → deny (403)
```

**Worked example.** Priya holds SALES (`lead.read`=OWN) and a direct GRANT `lead.read`=ALL "Covering for Ravi, until 2026-10-15". Her effective scope is ALL until 2026-10-15, then OWN again with no manual cleanup. If an Admin adds DENY `lead.export` to her, she can't export even if a role grants it.

## 6. Permission catalog and default role matrix (RBAC-008)

Legend: **A** = granted with scope ALL · **O** = granted with scope OWN · **✓** = granted (scope not applicable) · blank = not granted. 🔒 = `is_sensitive`.

### 6.1 Platform: self-service

| Code | Description | Req | Founder | Admin | Sales |
|---|---|---|---|---|---|
| `profile.read` | View own profile and effective permissions | USER-004 | ✓ | ✓ | ✓ |
| `profile.update` | Edit own name, phone, timezone | USER-004 | ✓ | ✓ | ✓ |
| `session.read` | List own sessions (scope OWN only) | AUTH-016 | O | O | O |
| `session.revoke` | Revoke own sessions (scope OWN only) | AUTH-016 | O | O | O |
| `notification.read` | Read and mark own notifications | NOTIF-001 | O | O | O |

Some authentication capabilities are not data permissions:

- changing one's own password;
- password reset by token;
- logout;
- one's own MFA enrollment, verification and recovery-code regeneration.

They are available to the authenticated user, or to the holder of a valid single-use token, by design. They are listed in the RBAC exception table (§11).

### 6.2 Platform: users and access

| Code | Description | Req | Founder | Admin | Sales |
|---|---|---|---|---|---|
| `user.read` | List and view users | USER-001 | ✓ | ✓ | |
| `user.create` | Invite users | USER-001 | ✓ | ✓ | |
| `user.update` | Edit profile fields, unlock | USER-001 | ✓ | ✓ | |
| `user.deactivate` | Disable or re-enable | USER-001 | ✓ | ✓ | |
| `user.delete` 🔒 | Soft-delete a user | USER-001 | ✓ | | |
| `user.restore` | Restore a deleted user | USER-001 | ✓ | | |
| `user.password.reset` | Send a reset link to a user | AUTH-008 | ✓ | ✓ | |
| `user.session.revoke` | Revoke another user's sessions | AUTH-016 | ✓ | ✓ | |
| `user.role.assign` 🔒 | Add or remove roles on users | RBAC-009 | ✓ | ✓ | |
| `user.permission.assign` 🔒 | Direct GRANT/DENY on users | RBAC-006 | ✓ | | |
| `role.read` | View roles and their grants | RBAC-008 | ✓ | ✓ | |
| `role.manage` 🔒 | Create, edit or delete roles and edit role grants | RBAC-008 | ✓ | ✓ | |
| `permission.read` | View the permission catalog, who-has | RBAC-016 | ✓ | ✓ | |
| `permission.manage` 🔒 | Edit permission metadata | RBAC-004 | ✓ | | |
| `audit.read` 🔒 | View audit_log | AUDIT-008 | ✓ | ✓ | |
| `security_event.read` 🔒 | View `security_event_log`. ALL = everyone's events. OWN = own sign-in history. | SEVT-005 | A | A | O |
| `user.mfa.manage` 🔒 | Reset another user's MFA and set the per-user MFA requirement | MFA-007 | ✓ | ✓ | |
| `lookup.read` | Read reference lists (all authenticated users) | PLAT-009 | ✓ | ✓ | ✓ |
| `lookup.manage` | Add, edit or deactivate lookup values | PLAT-009 | ✓ | ✓ | |

Admin holds `role.manage`, but the anti-escalation rule (§7) prevents granting any role or permission Admin doesn't already hold. So Admin can't create a "super role" or assign FOUNDER.

### 6.3 CRM: leads

| Code | Scope? | Description | Req | Founder | Admin | Sales |
|---|---|---|---|---|---|---|
| `lead.create` | no | Create leads manually | LEAD-003 | ✓ | ✓ | ✓ |
| `lead.read` | yes | View leads, dashboard, duplicates | LEAD-013 | A | A | O |
| `lead.update` | yes | Edit lead fields, resolve duplicates | LEAD-002 | A | A | O |
| `lead.status.change` | yes | Pipeline transitions, WON/LOST | LEAD-005 | A | A | O |
| `lead.reopen` | yes | Reopen WON/LOST | LEAD-005 | A | A | |
| `lead.assign` | yes | Assign, reassign or unassign | LEAD-007 | A | A | |
| `lead.delete` 🔒 | yes | Soft-delete | LEAD-016 | A | A | |
| `lead.restore` | no | Restore, view deleted | LEAD-016 | ✓ | ✓ | |
| `lead.export` 🔒 | no | CSV export (P1) | LEAD-017 | ✓ | | |
| `lead_note.create` | no | Add note to a visible lead | NOTE-001 | ✓ | ✓ | ✓ |
| `lead_note.read` | yes | Read notes on visible leads | NOTE-001 | A | A | A¹ |
| `lead_note.update` | yes | Edit notes | NOTE-002 | A | A | O |
| `lead_note.delete` | yes | Delete notes | NOTE-002 | A | A | O |
| `lead_activity.create` | no | Log or plan activity on a visible lead | ACT-001 | ✓ | ✓ | ✓ |
| `lead_activity.read` | yes | Read the timeline of visible leads | ACT-001 | A | A | A¹ |
| `lead_activity.update` | yes | Edit, complete, cancel or reschedule | ACT-002 | A | A | O |
| `lead_activity.delete` | yes | Delete non-system activities | ACT-002 | A | A | O |

¹ Sales has ALL for child reads so they can see teammates' notes on leads they can see. The parent lead's OWN scope still limits which leads those are (§4 child rule).

### 6.4 Adding a persona later (example, no code change)

A **Designer** role can be added entirely through the UI: `lead.read`=O, `lead_note.*`=O, `lead_activity.create`, `lead_activity.read`=A. A **Sales Manager** gets `lead.read`=A, `lead.assign`=A and `lead.status.change`=A. When org units arrive, a team lead gets TEAM instead of ALL.

## 7. Guard rules (RBAC-009, RBAC-010, RBAC-011, MFA-007, MFA-011)

> Traces: RBAC-017

| Rule | Detail | Error |
|---|---|---|
| **G1 No escalation via user grants** | To give user U a GRANT on permission P at scope S (directly or via a role), the actor must hold P at scope ≥ S | 403 `ESCALATION_DENIED` |
| **G2 No escalation via roles** | To assign role R, the actor must hold every permission in R at ≥ its scope. To add P@S to role R, the actor must hold P@≥S. | 403 `ESCALATION_DENIED` |
| **G3 No self-modification** | Actors can't change their own `user_role` or `user_permission` rows, or grants of any role they hold | 403 `SELF_MODIFICATION_DENIED` |
| **G4 Keep the keys** | Reject any change after which zero ACTIVE HUMAN users would hold both `role.manage` and `user.role.assign` at effective scope ALL (checked by re-running the resolver in the transaction). Covers role edits, user disable or delete, unassignments and denies. | 409 `LAST_ADMINISTRATOR` |
| **G5 System objects** | Can't delete `is_system` roles, rename role codes, or delete or rename permission codes | 409 `SYSTEM_OBJECT` |
| **G6 Reason required** | Sensitive grants and all `user_permission` rows need `reason` | 422 `REASON_REQUIRED` |
| **G7 DENY is always allowed** | An actor with `user.permission.assign` may DENY any permission to others (reducing access is never escalation), subject to G3 and G4 | — |
| **G8 TEAM reserved** | Reject scope TEAM until org units exist | 422 `SCOPE_NOT_SUPPORTED` |
| **G9 No takeover of stronger accounts** | MFA reset, admin password-reset link and admin session revocation of user U require U's effective permissions ⊆ the actor's (each permission at ≤ scope) | 403 `ESCALATION_DENIED` |
| **G10 Step-up for sensitive changes** | Granting a sensitive permission or a role containing one, changing `role.mfa_required`, and `user.mfa.manage` actions require MFA verified within 10 minutes | 403 `STEP_UP_REQUIRED` |

## 8. Enforcement layers (RBAC-012, RBAC-014)

```
┌─ Layer 1: Route gate ────────────────────────────────────────────────────────────────┐
│ Each route declares its permission code in metadata (e.g. PATCH /leads/{id} → lead.update).
│ Missing code in effective set → 403 PERMISSION_DENIED (+ security_event_log PERMISSION_DENIED)
│ A startup check fails boot if any non-public route lacks a declared permission.
├─ Layer 2: Service (row) ─────────────────────────────────────────────────────────────┤
│ Load the target through the scoped repository. Not found OR out of scope → 404 NOT_FOUND
│ (never 403 for a row, so existence of other people's leads isn't leaked).
│ Business-rule permissions (e.g. transition to LOST needs lead.status.change) checked here.
├─ Layer 3: Repository (set) ──────────────────────────────────────────────────────────┤
│ Every list/aggregate query calls list_filter(actor, code) and ANDs the predicate.
│ Dashboards and exports use the same filter. There is no unscoped query path for API use.
├─ Layer 4: UI (cosmetic) ─────────────────────────────────────────────────────────────┤
│ <vs-can permission="lead.assign"> hides/disables controls; router guards hide pages.
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**Field-level control (future).** When needed (for example hiding `quoted_amount_minor` from some roles), add permissions like `lead.financials.read`. The response serializer omits fields the actor lacks, which is an additive change. P0 has no field-level restrictions.

## 9. Caching and propagation (RBAC-013)

- `app_user.authz_version` is incremented in the same transaction as any change that can alter that user's effective permissions:
  - their `user_role` or `user_permission` rows;
  - `role_permission` rows of a role they hold (all holders are incremented);
  - a role's deletion;
  - a permission's soft-deletion (all users are incremented);
  - the user's status;
  - any change to `role.mfa_required` of a role they hold, or to their own `app_user.mfa_required` (MFA policy, 05 §11.1).
- Effective permissions are cached in-process keyed by `(user_id, authz_version)`. The per-request user/session lookup (05 §5) reads the current `authz_version`, which is cached ≤ 30 s. So a change takes effect within 30 seconds, and immediately in the process that made it.
- `/auth/me` returns `authz_version` and the effective map. The SPA refetches when a response carries the header `X-Authz-Version` that differs from its copy. Every authenticated response sets this header.
- Multi-host (post-PostgreSQL): the cache moves to Redis or relies on the ≤ 30 s TTL. No design change.

## 10. Verification strategy

- **Matrix test:** a generated test iterates the seeded matrix. For every (role, permission, scope) it asserts that the protected endpoints allow or deny accordingly.
- **Scope tests:** for every scoped permission, users with OWN see only owned rows in list, detail (404 for others), dashboard counts and child lists.
- **Guard tests:** G1–G8 each have positive and negative cases.
- **Lint:** no role-code literals in business code, and no route without a declared permission.
- **MFA policy tests:** for each of the three policy sources in 05 §11.1, login requires MFA. Removing all sources removes the requirement, but never removes an active factor's challenge.

## 11. RBAC exception register

These endpoints are intentionally not gated by a permission code. None of them is privileged. Each is bounded to the caller's own identity or to a single-use secret.

| ID | Endpoint(s) | Gate instead | Why no permission |
|---|---|---|---|
| RBX-001 | `POST /auth/login`, `POST /auth/mfa/verify`, `POST /auth/mfa/enroll/*` (with `mfa_token`) | Credentials / challenge token | Happens before an identity is established |
| RBX-002 | `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all` | Refresh cookie / own session | Acts only on the caller's own sessions |
| RBX-003 | `POST /auth/password/forgot`, `POST /auth/password/reset`, `POST /auth/invite/accept` | Single-use token | Recovery and onboarding flows |
| RBX-004 | `POST /auth/password/change`, `POST /auth/mfa/step-up`, `POST /auth/mfa/recovery-codes`, `DELETE /auth/mfa/factor` | Authenticated caller + current password or step-up | Own credentials only |
| RBX-005 | `POST /public/leads` | Turnstile + rate limit + idempotency | Anonymous public intake (LEAD-001) |
| RBX-006 | `GET /health/*`, `GET /auth/.well-known/jwks.json` | None | Contain no data |
