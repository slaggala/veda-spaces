# 06 — RBAC Design

Governing decisions: [ADR-001](decisions/ADR-001-app-user-table.md) · [ADR-006](decisions/ADR-006-mfa-policy.md) · [ADR-009](decisions/ADR-009-p0-scope.md) · [ADR-010](decisions/ADR-010-account-control-and-privileged-protection.md)

## 1. Model

```
                   ┌──────────────┐
                   │  permission  │  code, module, resource, action, supports_scope,
                   │              │  is_sensitive, sensitivity_class
                   └──────▲───────┘
            ┌─────────────┴───────────────┐
  ┌─────────┴────────┐          ┌─────────┴─────────┐
  │ role_permission  │          │  user_permission  │  effect GRANT|DENY, scope, validity (P1), reason
  │ scope            │          └─────────▲─────────┘
  └─────────▲────────┘                    │
      ┌─────┴────┐                        │
      │   role   │ mfa_required           │
      └─────▲────┘                        │
      ┌─────┴──────┐                      │
      │ user_role  │ validity (P1)        │
      └─────▲──────┘                      │
            └──── app_user (entity User): status, protection_level, MFA state ────┘
```

An **authorization decision** is `can(actor, session, permission_code, resource?) → allow | deny`.

- The session matters because sensitive permissions are effective only in an MFA-verified, full session (§5, MFA-012).
- With a resource, the permission's **scope** is checked against the row.

## 2. Principles (RBAC-002)

1. **Code checks permission codes only.** Nothing references role codes (`FOUNDER`, `ADMIN`, `SALES`), "is_admin" flags or specific user ids. A CI lint rejects role-code string literals outside migrations and seed files.
2. **The Founder is not special in authorization code.** Founder capabilities come from the seeded matrix. Founder *protection* comes from the data attribute `app_user.protection_level = 'FOUNDER'` (§7.2), which is set only by the bootstrap CLI and the Founder-governance workflow. Founder-only grantability comes from the data flag `grant_path = FOUNDER_WORKFLOW_ONLY` (G13). Neither is ever inferred from a role name.
3. **Deny by default.** No grant means deny.
4. **An explicit DENY beats any GRANT** (RBAC-006).
5. **Least privilege.** Sales gets OWN scope for leads, and **no sensitive permission** (RBAC-018).
6. **Server-authoritative.** UI checks are hints only (RBAC-012).
7. **MFA is data-driven.** Whether MFA is required comes from `role.mfa_required`, `app_user.mfa_required` and holding sensitive permissions (05 §11.1). Whether a sensitive permission is *effective* also depends on MFA state (§5).

## 3. Permission registry and naming (RBAC-003, RBAC-004, RBAC-015)

- **Naming:** `<resource>.<action>` or `<resource>.<sub>.<action>`, lowercase, singular resource.
- **Source of truth:** each module declares its permissions in a code registry. Each entry has `code`, `name`, `description`, `supports_scope`, `is_sensitive`, `sensitivity_class` and `requirement_ref`.
- **Sync:** a migration step upserts registry entries into `permission`.
  - New codes are inserted and changed metadata is updated.
  - Removed codes are soft-deleted.
  - Codes are never renamed. To rename, add the new code, migrate grants, then soft-delete the old one.
- **The API cannot create, delete or reclassify permissions.** Sensitivity is part of the code registry, reviewed in PRs. `permission.manage` edits `name` and `description` only.

### 3.1 Canonical sensitivity classification (RBAC-018, owner Decision 1)

A permission is **sensitive** if and only if its registry entry has a `sensitivity_class`. Classification depends on **what the permission can do**, never on which role holds it.

| Class | Criterion | Permissions (P0) |
|---|---|---|
| `ACCOUNT_CONTROL` | Changes another account's identity, credentials, MFA, status, sessions or protection level | `user.email.change`, `user.status.manage`, `user.delete`, `user.session.revoke`, `user.mfa.reset`, `user.mfa.require`, `user.founder.manage` |
| `ACCESS_CONTROL` | Changes who can do what | `user.role.manage`, `user.permission.manage`, `role.manage`, `permission.manage` |
| `SECURITY_DATA` | Reads audit or security telemetry | `audit.read`, `security_event.read` |
| `BULK_DATA` | Extracts business data in bulk | `lead.export` (P1) |
| `DESTRUCTIVE` | Removes or irreversibly alters business data | `lead.delete`, `lead.erase` |

**Registry rules, each enforced by tests (12 §4.4):**

1. Every permission whose action matches the class criteria must carry the class.
2. `is_sensitive = (sensitivity_class IS NOT NULL)`, enforced by a CHECK constraint (03 §4.4).
3. The seeded **SALES** role holds **no** sensitive permission.
4. Adding a sensitive permission to any role is itself a sensitive change: it needs a reason, step-up, and an email to `permission.manage` holders.
5. A permission with `grant_path = FOUNDER_WORKFLOW_ONLY` (`user.founder.manage`) may be contained **only** in the role with `grant_path = FOUNDER_WORKFLOW_ONLY` (FOUNDER). The seed migration asserts this, and I3 checks it nightly (§7.3).

### 3.2 Sensitive-permission behavior (RBAC-017, MFA-004, MFA-012)

| Aspect | Rule |
|---|---|
| MFA requirement | Holding any sensitive permission, via any role or direct grant and at any scope, makes MFA mandatory for the holder (05 §11.1) |
| Activation | A sensitive permission is **effective only** when the holder has an ACTIVE MFA factor **and** the current session is MFA-verified (`auth_methods` includes `totp`) and of type `FULL`, **and** the holder is outside a recovery cooling-off window. That last condition applies to every sensitive class (N-A2). Otherwise the permission is **suspended**: present in grants, absent from the effective map (§5). |
| Assignment without MFA | Allowed. The grant shows as **Pending MFA** until the holder enrolls, and a `PERMISSION_SUSPENDED` security event is written at assignment. |
| MFA removed or reset | All of the user's sensitive permissions are suspended from the next request (the `authz_version` increment, §9) until re-enrollment and an MFA-verified login. Written as `PERMISSION_SUSPENDED` / `PERMISSION_REACTIVATED` events. |
| Step-up | `ACCOUNT_CONTROL`, `ACCESS_CONTROL`, `BULK_DATA` and `lead.erase` require MFA verified within the last 10 minutes (G10) |
| Recording (F-06) | **Mutations** using any sensitive permission write one `SENSITIVE_ACTION` event. **Reads** using a `SECURITY_DATA` or `BULK_DATA` permission write a `SENSITIVE_READ` event, de-duplicated per (actor, permission, 15-minute window). Reading the security log therefore records who looked, without a feedback loop. |

## 4. Data scope (RBAC-005)

| Scope | Meaning | P0 status |
|---|---|---|
| `ALL` | Every row of the resource | Active |
| `TEAM` | Rows owned by the actor's org unit(s) | **Reserved.** Rejected until `org_unit` exists (10 §4). |
| `OWN` | Rows the actor owns (below) | Active |

Scope ordering: `ALL > TEAM > OWN`.

| Resource | Actor "owns" a row when |
|---|---|
| `lead` | `assigned_to = actor` or `created_by = actor` |
| `lead_note` | Read: parent lead visible · update/delete: `created_by = actor` |
| `lead_activity` | Read: parent lead visible · update/delete: `owner_user_id = actor` or `created_by = actor` |
| `notification` | `recipient_user_id = actor` |
| `user_session` | `user_id = actor` |
| `app_user` (profile) | `id = actor` |

**Child visibility rule.** A child row is never visible unless its parent lead is visible under `lead.read`. Any client-supplied reference to another lead (for example `duplicate_of_lead_id`) is resolved through the scoped repository. Out of scope, it behaves as not found (404) (A-07).

`security_event.read` has `supports_scope = false`. It is ALL-only, so no OWN variant exists to grant (owner Decision 1).

## 5. Resolution algorithm

```
effective_permissions(user, session) → map<permission_code, scope>

 0. if user.status ≠ ACTIVE or user.is_deleted                               → ∅
 1. if session.session_type = RECOVERY                                        → ∅   (endpoint allow-list only, 05 §11.5)
 2. now = clock()
 3. denies = { p.code | user_permission(user,p) effect=DENY ∧ live(now) ∧ ¬p.is_deleted }
 4. grants = role grants of live user_roles ∪ direct GRANTs (live, ¬p.is_deleted)
 5. scope[code] = max(scope over grants)                                     (ALL > TEAM > OWN)
 6. remove codes ∈ denies
 7. permissions with supports_scope = false → scope := ALL
 8. MFA gate (MFA-012): for each sensitive code:
       if ¬(user has ACTIVE factor ∧ 'totp' ∈ session.auth_methods)          → suspend (remove)
       if user.security_cooling_off_until > now                             → suspend (remove)   (all sensitive classes, N-A2)
 9. return scope map        (suspended codes are reported separately to /auth/me as "suspended")

live(now) := ¬is_deleted ∧ (valid_from IS NULL ∨ valid_from ≤ now) ∧ (valid_until IS NULL ∨ valid_until > now)
```

Time-bound validity (`valid_from`, `valid_until`) is part of the schema. **Its use is P1 (RBAC-007).** In P0 the API rejects non-null validity with `422 TIME_BOUND_GRANTS_NOT_ENABLED`. When enabled in P1, a time-bound grant may never contain a sensitive permission, so expiry cannot remove an invariant holder (§7.3, F-16).

## 6. Permission catalog and default role matrix (RBAC-008)

Legend: **A** = scope ALL · **O** = scope OWN · **✓** = granted (scope not applicable) · blank = not granted · 🔒 = sensitive (class in brackets).

### 6.1 Platform: self-service

| Code | Description | Req | Founder | Admin | Sales |
|---|---|---|---|---|---|
| `profile.read` | View own profile, MFA status and effective permissions | USER-004 | ✓ | ✓ | ✓ |
| `profile.update` | Edit own name, display name, phone, timezone and locale **only** | USER-004 | ✓ | ✓ | ✓ |
| `session.read` | List own sessions | AUTH-016 | O | O | O |
| `session.revoke` | Revoke own sessions | AUTH-016 | O | O | O |
| `notification.read` | Own notifications | NOTIF-001 | O | O | O |
| `lookup.read` | Reference lists | PLAT-009 | ✓ | ✓ | ✓ |

These capabilities are available to authenticated users by design (06 §11, RBX-004), not granted as data permissions:

- one's own password change;
- one's own email change (the proposed-email workflow);
- one's own MFA enrollment and recovery-code regeneration;
- logout.

**Sales has no security-event access of any kind** (owner Decision 1). There is no self-service view of security events for users without `security_event.read`. Users learn about security-relevant activity through email notifications instead (02 §10.3).

### 6.2 Platform: users, access and security

| Code | Description | Req | Founder | Admin | Sales |
|---|---|---|---|---|---|
| `user.read` | List and view users | USER-001 | ✓ | ✓ | |
| `user.create` | Invite users and resend invites. Roles in an invite also need `user.role.manage`. | USER-001 | ✓ | ✓ | |
| `user.profile.update` | Edit another user's **profile fields only**: name, display name, phone, timezone, locale | RBAC-019 | ✓ | ✓ | |
| `user.email.change` 🔒 [ACCOUNT_CONTROL] | Start the proposed-email workflow for another user (05 §8.6) | USER-007 | ✓ | ✓ | |
| `user.status.manage` 🔒 [ACCOUNT_CONTROL] | Deactivate, reactivate or unlock another user | RBAC-019 | ✓ | ✓ | |
| `user.delete` 🔒 [ACCOUNT_CONTROL] | Soft-delete a user | USER-001 | ✓ | | |
| `user.restore` | Restore a deleted user (returns as DISABLED) | USER-001 | ✓ | | |
| `user.password.reset` | Send a reset link to the user's **verified** email | AUTH-008 | ✓ | ✓ | |
| `user.session.revoke` 🔒 [ACCOUNT_CONTROL] | Revoke another user's sessions | AUTH-016 | ✓ | ✓ | |
| `user.role.manage` 🔒 [ACCESS_CONTROL] | Add or remove roles on users | RBAC-009 | ✓ | ✓ | |
| `user.permission.manage` 🔒 [ACCESS_CONTROL] | Direct GRANT/DENY on users | RBAC-006 | ✓ | | |
| `user.mfa.reset` 🔒 [ACCOUNT_CONTROL] | Request, approve or execute another user's MFA reset (05 §11.7) | MFA-007 | ✓ | ✓ | |
| `user.mfa.require` 🔒 [ACCOUNT_CONTROL] | Set or clear the per-user MFA requirement | MFA-003 | ✓ | ✓ | |
| `user.founder.manage` 🔒 [ACCOUNT_CONTROL] | Request or approve Founder-level actions (§7.2). `grant_path = FOUNDER_WORKFLOW_ONLY`: held **only** through the FOUNDER role, never grantable directly (G13). | RBAC-021 | ✓ | | |
| `role.read` | View roles and grants | RBAC-008 | ✓ | ✓ | |
| `role.manage` 🔒 [ACCESS_CONTROL] | Create, edit or delete roles and role grants | RBAC-008 | ✓ | ✓ | |
| `permission.read` | View the catalog and holders | RBAC-016 | ✓ | ✓ | |
| `permission.manage` 🔒 [ACCESS_CONTROL] | Edit permission name and description | RBAC-004 | ✓ | | |
| `audit.read` 🔒 [SECURITY_DATA] | View `audit_log` | AUDIT-008 | ✓ | ✓ | |
| `security_event.read` 🔒 [SECURITY_DATA] | View `security_event_log` (ALL only) | SEVT-005 | ✓ | ✓ | |
| `lookup.manage` | Manage lookup values | PLAT-009 | ✓ | ✓ | |

**Retired permission codes.** These codes from the frozen draft were never implemented, so no grants exist to migrate:

| Retired code | Replaced by |
|---|---|
| `user.update` | `user.profile.update`, plus the dedicated account-control permissions |
| `user.deactivate` | `user.status.manage` |
| `user.role.assign` | `user.role.manage` |
| `user.permission.assign` | `user.permission.manage` |
| `user.mfa.manage` | `user.mfa.reset` and `user.mfa.require` |

### 6.3 CRM: leads

| Code | Scope? | Description | Req | Founder | Admin | Sales |
|---|---|---|---|---|---|---|
| `lead.create` | no | Create leads manually | LEAD-003 | ✓ | ✓ | ✓ |
| `lead.read` | yes | View leads, dashboard, duplicates, spam queue | LEAD-013 | A | A | O |
| `lead.update` | yes | Edit and enrich fields, resolve duplicate and spam flags, record consent withdrawal | LEAD-024 | A | A | O |
| `lead.status.change` | yes | Pipeline transitions, WON/LOST | LEAD-005 | A | A | O |
| `lead.reopen` | yes | Reopen WON/LOST | LEAD-005 | A | A | |
| `lead.assign` | yes | Assign, reassign or unassign | LEAD-007 | A | A | |
| `lead.delete` 🔒 [DESTRUCTIVE] | yes | Soft-delete | LEAD-016 | A | A | |
| `lead.restore` | no | Restore, view deleted | LEAD-016 | ✓ | ✓ | |
| `lead.erase` 🔒 [DESTRUCTIVE] | no | Execute a personal-data erasure request (07 §8.2) | LEAD-029 | ✓ | | |
| `lead.export` 🔒 [BULK_DATA] | no | CSV export (P1) | LEAD-017 | ✓ | | |
| `lead_note.create` | no | Add a note to a visible lead | NOTE-001 | ✓ | ✓ | ✓ |
| `lead_note.read` | yes | Read notes on visible leads | NOTE-001 | A | A | A¹ |
| `lead_note.update` | yes | Edit notes | NOTE-002 | A | A | O |
| `lead_note.delete` | yes | Delete notes | NOTE-002 | A | A | O |
| `lead_activity.create` | no | Log or plan an activity on a visible lead | ACT-001 | ✓ | ✓ | ✓ |
| `lead_activity.read` | yes | Read the timeline | ACT-001 | A | A | A¹ |
| `lead_activity.update` | yes | Edit, complete, cancel or reschedule | ACT-002 | A | A | O |
| `lead_activity.delete` | yes | Delete non-system activities | ACT-002 | A | A | O |

¹ Child reads are limited by the parent lead's OWN scope (§4).

**Resulting MFA posture (05 §11.1).**

| Role | MFA | Why |
|---|---|---|
| Founder | Mandatory | `role.mfa_required = true` and holds sensitive permissions |
| Admin | Mandatory | Same |
| Sales (standard) | **Optional by default** | No sensitive permission (verified by registry rule 3) and `role.mfa_required = false`. Becomes mandatory if the user or the role is flagged, or if a sensitive permission is granted. |

### 6.4 Adding a persona later (example, no code change)

- **Designer:** `lead.read`=O, `lead_note.*`=O, `lead_activity.create`, `lead_activity.read`=A. No sensitive permissions, so MFA is optional.
- **Sales Manager:** `lead.read`=A, `lead.assign`=A. Non-sensitive.

A custom role with broad data access (for example `lead.read`=ALL) but no sensitive permission does not require MFA unless flagged. Owner Decision 1 limits mandatory MFA to Founder, Admin and holders of sensitive permissions, and `role.mfa_required` is available for such roles.

## 7. Guard rules (RBAC-009, RBAC-010, RBAC-011, RBAC-019, RBAC-020, RBAC-021, MFA-007, MFA-011, MFA-015)

### 7.1 Guard table

| Guard | Rule | Error |
|---|---|---|
| **G1 No escalation via user grants** | To grant permission P at scope S to anyone, the actor must hold P at scope ≥ S | 403 `ESCALATION_DENIED` |
| **G2 No escalation via roles** | To assign role R, edit R's grants, or create a role **by copying** R (`copy_from_role_id`, A-06), the actor must hold every permission in R at ≥ its scope | 403 `ESCALATION_DENIED` |
| **G3 No self-administration** | Through administrative endpoints, actors cannot change their own roles, permissions, status, email, MFA (reset or requirement) or protection level. The only exception is the Founder-governance step-down request, `REVOKE_FOUNDER` on oneself (§7.2), which still needs a second Founder's approval. Self-service uses the self-service workflows (05 §8.5, §8.6, §11). | 403 `SELF_MODIFICATION_DENIED` |
| **G4 Recovery invariants** | Reject any change after which invariant I1, I2 or I3 (§7.3) would fail | 409 `LAST_ADMINISTRATOR` / `LAST_FOUNDER` / `FOUNDER_STATE_INCONSISTENT` |
| **G5 System objects** | Can't delete `is_system` roles or rename role and permission codes | 409 `SYSTEM_OBJECT` |
| **G6 Reason required** | Every sensitive action and every `user_permission` row needs `reason` | 422 `REASON_REQUIRED` |
| **G7 DENY is always allowed** | Reducing another user's access is never escalation (subject to G3, G4, G11 and G13) | — |
| **G8 TEAM reserved** | Scope TEAM is rejected until org units exist | 422 `SCOPE_NOT_SUPPORTED` |
| **G9 No action on stronger accounts** | Every account-control action on user U requires U's effective (including suspended) permissions ⊆ the actor's, each at ≤ scope. This covers email change, status change, unlock, delete, restore, session revocation, admin password-reset link, invite resend, MFA reset, MFA requirement change and role/permission removal. | 403 `ESCALATION_DENIED` |
| **G10 Step-up** | Every `ACCOUNT_CONTROL`, `ACCESS_CONTROL` and `BULK_DATA` permission use (including unlock) and `lead.erase` require MFA verified in this session within 10 minutes | 403 `STEP_UP_REQUIRED` |
| **G11 Founder protection** | Any account-control or access-control change targeting a user with `protection_level = FOUNDER` goes **only** through the Founder-governance workflow (§7.2). Admin-level actors can never deactivate, delete, demote, email-change, MFA-reset or revoke a Founder, and G9 independently prevents it. | 403 `FOUNDER_PROTECTED` |
| **G12 Dual control (non-Founder)** | An approved `admin_approval_request` from a second eligible actor (§7.4) is required for MFA reset of a **privileged** user (holds any sensitive permission, including suspended) and for email change of a privileged user. Founder-level actions use §7.2 instead. | 202 `APPROVAL_REQUIRED` (request created) |
| **G13 Founder-governance grant path (N-01)** | Roles and permissions whose `grant_path = FOUNDER_WORKFLOW_ONLY` (the FOUNDER role and `user.founder.manage`) can **never** be added, removed, denied, copied or edited through generic APIs: `PUT /users/{id}/roles`, `POST`/`DELETE /users/{id}/permissions` (GRANT and DENY), `PUT /roles/{id}/permissions`, `PATCH`/`DELETE /roles/{id}`, and `POST /roles` with `copy_from_role_id`. Such changes occur only as the effect of an executed Founder-governance action (§7.2), or by migration for role definitions. No other role may contain a `FOUNDER_WORKFLOW_ONLY` permission. | 403 `FOUNDER_GOVERNANCE_REQUIRED` |

### 7.2 Founder-governance workflow: canonical (RBAC-021, MFA-015, owner Decision 3, N-01)

This section is the **single authoritative definition** of Founder governance. ADR-010, 05, 08, 09 and 12 refer to it and must not restate eligibility differently.

#### 7.2.1 Founder state

A user **is a Founder** if and only if `app_user.protection_level = FOUNDER` **and** the user holds the FOUNDER role.

- Invariant I3 (§7.3) keeps these two facts identical.
- The FOUNDER role and the `user.founder.manage` permission have `grant_path = FOUNDER_WORKFLOW_ONLY` (03 §4.3, §4.4), and the FOUNDER role has `is_assignable = false`.
- `user.founder.manage` is contained **only** in the FOUNDER role. A registry rule and a migration assertion enforce this.

So "holding Founder powers" and "being FOUNDER-protected" can never diverge. No other path confers them (G13).

#### 7.2.2 Founder-level actions

Every action below is a Founder-level action. Each runs only through `POST /api/v1/founder-actions` (08 §5.11), or the break-glass CLI (§7.5), and executes only after approval.

| Code | Action | Effect on execution |
|---|---|---|
| `GRANT_FOUNDER` | Grant Founder status. This also grants `user.founder.manage`, via the FOUNDER role. | `protection_level = FOUNDER` + FOUNDER role assigned, in one transaction |
| `REVOKE_FOUNDER` | Remove Founder status. This also revokes `user.founder.manage`. Self step-down is allowed as the requester (G3 exception). | FOUNDER role removed + `protection_level = STANDARD`, in one transaction. The request may also specify the roles to hold afterwards. |
| `FOUNDER_MFA_RESET` | Founder MFA recovery performed administratively. Self-service recovery (05 §11.5) needs no approval. | As 05 §11.7, with the enrollment link to the target's verified email |
| `FOUNDER_STATUS_CHANGE` | Deactivate, reactivate, unlock or delete a Founder | Status change with the 06 §7.3 invariants |
| `FOUNDER_EMAIL_CHANGE` | Founder email or identity change | Starts the proposed-email workflow (05 §8.6) |
| `FOUNDER_BREAK_GLASS` | Activation of break-glass for any of the above, when §7.2.4 cannot be satisfied in-app | §7.5 |
| `FOUNDER_POLICY_CHANGE` | A change to Founder approval policy: the FOUNDER role's grants, its `mfa_required`, `grant_path` flags, or the Founder-governance configuration (approval expiry, break-glass delay) | **No runtime API exists.** Only through a migration or configuration change reviewed as an ADR amendment by the Architecture Owner and approved by the Product Owner (outside the application). The deploy records a `FOUNDER_POLICY_CHANGED` security event. |

`GRANT_FOUNDER_MANAGE` and `REVOKE_FOUNDER_MANAGE` are **not** separate actions. `user.founder.manage` exists only inside the FOUNDER role, so granting or revoking it is `GRANT_FOUNDER` or `REVOKE_FOUNDER`.

#### 7.2.3 Eligibility: the only rule

| Role in the request | Eligible when **all** of these hold, **at request time, at approval time, and again at execution time** in the executing transaction |
|---|---|
| **Requester** | ACTIVE HUMAN user · is a Founder (§7.2.1) · `user.founder.manage` is **effective** (not suspended: ACTIVE MFA factor, MFA-verified FULL session, not in cooling-off) · step-up within 10 minutes · **not the target**, except `REVOKE_FOUNDER` self step-down |
| **Approver** | ACTIVE HUMAN user · is a Founder · `user.founder.manage` effective · step-up within 10 minutes · **not the requester** · **not the target** |

- Exactly **one** in-app approval is required, which gives **two distinct human principals** in total: requester ≠ approver. The request records one `approver_user_id`. A second approval attempt, whether by the same or another user, returns `409 INVALID_STATE`, so there are no duplicate approvers.
- **Eligibility lost before approval.** If the requester stops being eligible before approval (demoted, deactivated, MFA reset, cooling-off), the request becomes `CANCELLED` with reason `REQUESTER_INELIGIBLE`.
- **Eligibility lost before execution.** Execution re-checks both principals under the write lock. If either is ineligible, the request becomes `FAILED` and nothing is applied.
- **Holders of a Founder-level permission who aren't Founders.** By G13 and I3 no such user can exist. If the nightly I3 check ever finds one (for example after an out-of-band database edit), they are treated as ineligible, and a CRITICAL alert is raised.

#### 7.2.4 Operating modes

| Mode | Condition | Rule |
|---|---|---|
| **Steady state** | ≥ 2 eligible Founders, excluding the target | In-app request plus in-app approval (§7.2.3) |
| **Single-Founder mode** | Exactly one eligible Founder (other than the target), for example the normal P0 situation with one Founder | The sole Founder may **request** in-app. The second principal is a break-glass custodian (§7.5), who approves through the CLI and must not be the same human as the requester. The cooling-off, notification and cancel window of §7.5 apply. A Founder can never self-approve. |
| **No eligible Founder** | The sole Founder is the target (lost device and codes, or departure) or ineligible | Full break-glass: custodian A requests and custodian B approves (§7.5). Both are distinct humans, neither is the target. |
| **Bootstrap** | Zero Founders have ever existed (empty `app_user` Founder history) | `bootstrap-founder` CLI (05 §10) creates exactly one INVITED Founder. It refuses to run if any non-deleted user has `protection_level = FOUNDER` **or** a prior `BOOTSTRAP_FOUNDER` security event exists. So bootstrap can never be used to mint a second Founder in steady state. Every later Founder comes from `GRANT_FOUNDER`. |

#### 7.2.5 Concurrency and last-Founder safety

- At most **one open Founder-level request per target** across all Founder actions (`ux_admin_approval_request__open_founder_target`, 03 §5.8). A second request for the same target → `409 REQUEST_ALREADY_OPEN`.
- Requests for **different** targets may be open together. Execution happens under the write lock (SQLite `BEGIN IMMEDIATE`; PostgreSQL `SELECT … FOR UPDATE` on both principals' and the target's `app_user` rows), and re-evaluates I1–I3. Of two concurrent `REVOKE_FOUNDER` requests that would leave no Founder, the second executes as `FAILED` (`LAST_FOUNDER`).
- `REVOKE_FOUNDER` and `FOUNDER_STATUS_CHANGE` (deactivate or delete) against the last Founder are rejected at request time **and** at execution time with `409 LAST_FOUNDER`.

#### 7.2.6 Records

Every stage writes security events: `FOUNDER_ACTION_REQUESTED`, `…_APPROVED`, `…_DENIED`, `…_CANCELLED`, `…_EXECUTED`, `…_FAILED`, and `FOUNDER_GOVERNANCE_BYPASS_BLOCKED` for G13 rejections. `FOUNDER_TRANSITION` is kept for GRANT and REVOKE executions. Audit rows are written for `admin_approval_request`, `app_user`, `user_role` and `user_mfa_factor`. Notifications go to all Founders, the target (verified email) and the custodians (break-glass).

### 7.3 Recovery invariants (G4, RBAC-020)

| Invariant | Rule |
|---|---|
| **I1 Last Founder** | At least one ACTIVE, non-deleted Founder (§7.2.1) |
| **I2 Last recovery administrator** | At least one ACTIVE, non-deleted HUMAN user whose granted permissions (suspension ignored) include `user.role.manage`, `role.manage`, `user.mfa.reset` and `user.status.manage` at scope ALL. The Founder may satisfy this. |
| **I3 Founder-state consistency** | For every user: `protection_level = FOUNDER` ⇔ holds the FOUNDER role. No role other than FOUNDER contains a `FOUNDER_WORKFLOW_ONLY` permission. No `user_permission` row references a `FOUNDER_WORKFLOW_ONLY` permission. |

**Where the invariants are checked:**

- Inside the transaction of every change that can affect them, re-running the resolver over the post-change state before commit, under the write lock (SQLite `BEGIN IMMEDIATE`; PostgreSQL `SELECT … FOR UPDATE` on the affected `app_user` rows). Concurrent changes therefore cannot both pass.
- Time-bound grants are disabled in P0 and may never contain sensitive permissions, so expiry cannot break the invariants (§5).
- A **nightly invariant job** raises a CRITICAL alert if I1, I2 or I3 is false. It also raises a **High** alert if no **effective** recovery administrator exists: I2 holds, but every such holder is suspended, for example because none has MFA (N-A4).
- **Self-deactivation** through `/users/{id}/status` is refused by G3 regardless of the invariants.

### 7.4 Dual-control approvals for non-Founder actions (RBAC-021, MFA-015)

Stored in `admin_approval_request` (03 §5.8) with `action_class = STANDARD`. Founder-level actions (`action_class = FOUNDER`) follow §7.2 exclusively.

| Step | Rule |
|---|---|
| Request | The actor holding the action's permission submits the action with a reason and step-up. The API returns `202 APPROVAL_REQUIRED` with the request id. Event: `APPROVAL_REQUESTED`. |
| Approve / deny | A **different** actor who holds the same permission **effectively**, satisfies G9 against the target, is step-up verified, and is neither the requester nor the target. Eligibility is re-checked at execution. |
| Execute | On approval the service executes the action in the same transaction as the status change to EXECUTED. |
| Expiry | Pending requests expire after the configured approval expiry (initial default 24 hours) → EXPIRED |
| Notification | The target (at the verified email) and all eligible approvers are notified at request and at decision |

### 7.5 Break-glass governance (RBAC-021)

This is used in single-Founder mode (as the second principal) and when no eligible Founder exists (§7.2.4).

1. **Custodians.** The owner designates **two break-glass custodians** (OWNER-INPUT-004). They are AWS IAM principals in a dedicated group with AWS MFA required.
   - Each custodian principal is mapped in the owner-approved custodian register (configuration) to **one human**: an `app_user.id`, or a named external person.
   - One human may hold at most one custodian principal.
2. **Separation.**
   - A custodian can never approve a request they requested.
   - A custodian can never approve a request whose in-app requester is the same human, by register mapping.
   - A custodian can never act on a request targeting themselves.
   - The CLI refuses when requester and approver resolve to the same human, and records both IAM principal ARNs (verified from the SSM session identity and CloudTrail).
3. **Request.** Either an in-app `founder-actions` request in single-Founder mode, or custodian A running `break-glass request --action … --target … --reason` via SSM Session Manager. A CRITICAL `BREAK_GLASS_REQUESTED` event is written.
4. **Approval.** In single-Founder mode, one custodian who is not the requester human approves. In full break-glass, custodian B (a different human from custodian A) approves. Either way, at least two distinct human principals are involved.
5. **Cooling-off.** Execution happens no earlier than the break-glass delay (a configuration value, initial default 24 h).
   - Every ACTIVE Founder and the target (at their verified email) are notified at request time.
   - Any of them can cancel through the signed link.
6. **Execution.** Audit rows are written (actor SYSTEM, via CLI, with both principals recorded) and `BREAK_GLASS_EXECUTED`.

## 8. Enforcement layers (RBAC-012, RBAC-014)

```
┌─ Layer 0: Session type gate ─────────────────────────────────────────────────────────┐
│ RECOVERY sessions may call only the recovery allow-list (05 §11.5); all else → 403
│ RECOVERY_SESSION_RESTRICTED, before any permission logic.
├─ Layer 1: Route gate ────────────────────────────────────────────────────────────────┤
│ Each route declares its permission code. Missing (or suspended) → 403 PERMISSION_DENIED
│ (+ PERMISSION_DENIED event; if suspended, detail.reason = MFA_REQUIRED and the client
│ is told to enroll/step-up). Startup fails if a non-public route lacks a declaration.
├─ Layer 2: Service (row + guards) ────────────────────────────────────────────────────┤
│ Scoped load → 404 outside scope. Guards G1–G12 for account and access control.
├─ Layer 3: Repository (set) ──────────────────────────────────────────────────────────┤
│ Every list/aggregate ANDs the scope predicate. No unscoped API query path.
├─ Layer 4: DTO (fields) ──────────────────────────────────────────────────────────────┤
│ Closed request schemas per endpoint. Security attributes are never writable through
│ generic endpoints (08 §5.4).
├─ Layer 5: UI (cosmetic) ─────────────────────────────────────────────────────────────┤
│ <vs-can> hides/disables; "Pending MFA" badges for suspended permissions.
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**Audit PII masking (A-12).** `GET /audit-logs` masks `pii_fields` in `old_value` and `new_value` for lead entities outside the actor's `lead.read` scope. Only ids and changed field names are shown.

## 9. Caching and propagation (RBAC-013, owner Decision 1.5)

- `app_user.authz_version` is incremented in the same transaction as any change that can alter effective permissions:
  - role, grant or DENY changes;
  - role-grant edits;
  - role deletion;
  - permission soft-deletion;
  - user status or protection-level change;
  - `role.mfa_required` or `app_user.mfa_required` change;
  - **MFA factor activation, revocation or reset**;
  - start or end of a recovery cooling-off.
- **Per-request check, uncached.** Every request reads its session and user state in one indexed query:
  - `user_session` (revoked, expiry, type, `auth_methods`, `mfa_verified_on`);
  - `app_user` (status, `authz_version`, `security_cooling_off_until`).

  This is a local SQLite read on the single instance (ASM-002). Revocation, deactivation and permission changes therefore take effect on the **next request**, with no cache window (F-10).
- The **effective-permission map** is cached in-process, keyed by (`user_id`, `authz_version`, `session_type`, MFA-verified flag, cooling-off flag). A single application process holds all caches (OPS-010), so there is no cross-worker staleness.
- Every response carries `X-Authz-Version`. The SPA refetches `/auth/me` when it changes.
- Multi-instance (after the PostgreSQL gate): the same per-request read runs against PostgreSQL, and caches move to Redis keyed identically.

## 10. Verification strategy

- **Matrix test:** every (role, permission, scope) × protected endpoint → allow or deny.
- **Registry tests:** sensitivity classification rules 1–4 (§3.1). Seeded SALES holds no sensitive permission. `is_sensitive` matches `sensitivity_class`.
- **Negative security-event tests (owner Decision 1):**
  - A standard Sales user gets `403 PERMISSION_DENIED` on `GET /security-events` with and without `subject_user_id = self`, and on `GET /security-events/{id}` for their own events.
  - `/auth/me` for Sales lists no `security_event.read`.
  - The Profile › Security UI makes no security-events call for Sales.
- **MFA-gated activation:**
  - A sensitive grant to a user without a factor is not effective (403 with `MFA_REQUIRED`).
  - It becomes effective after enrollment in an MFA-verified session.
  - An MFA reset suspends it on the next request.
- **Founder governance (N-01):** the negative tests in 12 §4.12 (TD-G) cover self-approval, requester-approves-own, duplicate approvers, direct FOUNDER-role and `user.founder.manage` grants and denies, role copy, approval after eligibility revoked, non-Founder approver, concurrency and last-Founder removal.
- **Guards:** G1–G13 positive and negative, including:
  - Admin cannot deactivate, delete, email-change or MFA-reset the Founder.
  - No user can deactivate themselves through `/users/{id}/status`.
  - Concurrent deactivation of the last two recovery administrators leaves exactly one (the invariant holds under the write lock).
  - Copy-from-role escalation is denied.
- **Mass-assignment:** `PATCH /users/{id}` with `email`, `status`, `roles`, `mfa_required`, `protection_level` or `password` → `422 FIELD_NOT_UPDATABLE`.
- **Lint:** no role-code literals, and no route without a declared permission or RBX entry.

## 11. RBAC exception register

These endpoints are intentionally not gated by a permission code. None is privileged. Each is bounded to the caller's own identity or to a single-use secret.

| ID | Endpoint(s) | Gate instead | Why no permission |
|---|---|---|---|
| RBX-001 | `POST /auth/login`, `POST /auth/mfa/verify`, `POST /auth/mfa/recovery` | Credentials plus challenge token | Before an identity is established |
| RBX-002 | `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all` | Refresh cookie or own session | Own sessions only |
| RBX-003 | `POST /auth/password/forgot`, `POST /auth/password/reset`, `POST /auth/invite/accept`, `POST /auth/email/verify`, `POST /auth/email/cancel` | Single-use token | Recovery, onboarding and email-verification flows |
| RBX-004 | `POST /auth/password/change`, `POST /auth/reauth`, `POST /auth/mfa/step-up`, `POST /auth/mfa/enroll/start`, `POST /auth/mfa/enroll/confirm`, `POST /auth/mfa/recovery-codes`, `DELETE /auth/mfa/factor`, `PUT /auth/me/email` | Authenticated caller + password re-entry, step-up or single-use enrollment token (05 §11.3) | Own credentials only. Enrollment never on password alone or recovery code alone. |
| RBX-005 | `POST /public/leads` | Turnstile, rate limit, idempotency | Anonymous public intake |
| RBX-006 | `GET /health/*`, `GET /auth/.well-known/jwks.json` | None | No data |
