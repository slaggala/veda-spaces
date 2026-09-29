# ADR-010: Account-control permissions, email-change workflow and privileged-account protection

- **Status:** Accepted
- **Date:** 2026-09-29
- **Source:** owner Decision 3 of `VEDA-SPACES-P0-ARCHITECTURE-REMEDIATION-01`. It resolves review finding F-03.

## Context

The review (F-03) found that the generic, non-sensitive `user.update` could change another user's email with no verification. A password reset to that email could then take the account over.

It also found that account deactivation was not covered by the stronger-target guard, and that the last-administrator guard (G4) counted only Admin-level holders. An Admin could therefore disable the Founder.

## Decision

### 1. Granular account-control permissions (06 §6.2)

The generic `user.update` is retired. Profile editing and identity/security editing use separate permissions and workflows.

| Permission | Allows | Sensitive |
|---|---|---|
| `user.profile.update` | Name, display name, phone, timezone, locale **only** | No |
| `user.email.change` | Start the proposed-email workflow for another user | Yes, ACCOUNT_CONTROL |
| `user.status.manage` | Deactivate, reactivate, unlock | Yes |
| `user.role.manage` | Role assignment | Yes, ACCESS_CONTROL |
| `user.permission.manage` | Direct grants and denies | Yes, ACCESS_CONTROL |
| `user.mfa.reset` | MFA reset (request, approve, execute) | Yes |
| `user.mfa.require` | Per-user MFA requirement | Yes |
| `user.founder.manage` | Founder transition, deactivation and protection changes | Yes |

The generic profile endpoints (`PATCH /users/{id}`, `PATCH /auth/me`) use **closed DTOs**. The following return `422 FIELD_NOT_UPDATABLE`: verified email, proposed email, password, MFA configuration, roles, permissions, status, Founder status (`protection_level`) and privileged status. Mass-assignment tests enforce this (12 §4.4).

### 2. Email-change workflow (05 §8.6)

1. Requires recent step-up. For MFA-enabled or privileged accounts, the step-up is MFA confirmation; otherwise password re-entry.
2. The new address is stored as `proposed_email`. The verified `email` is unchanged.
3. An **alert with a cancel link** goes to the current verified email. A **time-limited verification** (60 minutes, a configuration value) goes to the proposed email.
4. Password recovery and all notifications keep using the verified email until the change completes.
5. Tokens are 256-bit, single-use, expiring and stored only as SHA-256 hashes (`user_action_token`).
6. On completion:
   - all sessions and refresh tokens are revoked;
   - open reset, invite and enrollment tokens are invalidated;
   - both addresses are notified.
7. Every stage is recorded in `audit_log` (`app_user` UPDATE) and `security_event_log` (`EMAIL_CHANGE_*`).
8. Administrators can only **initiate** the workflow for others (`user.email.change`, G9, G11, dual control for privileged targets). They can **never** directly replace a verified email.

### 3. Privileged-account protection (06 §7)

1. **Founder status** is the data attribute `app_user.protection_level = FOUNDER`, not a role-name check.
2. Admins cannot deactivate, delete, demote, email-change or MFA-reset a Founder. G9 blocks it (the Founder holds permissions Admin lacks), and G11 blocks it independently.
3. No user can deactivate their own account (or change their own roles, permissions, email or MFA) through an administrative endpoint (G3).
4. **Invariants (G4):**
   - I1: at least one ACTIVE Founder.
   - I2: at least one ACTIVE recovery administrator holding `user.role.manage`, `role.manage`, `user.mfa.reset` and `user.status.manage` at ALL.

   They are enforced in the transaction under the write lock (SQLite `BEGIN IMMEDIATE`; PostgreSQL `SELECT … FOR UPDATE`), plus a nightly check. Time-bound grants are disabled in P0 and may never carry sensitive permissions, so expiry cannot break the invariants.
5. **Founder transition and deactivation** are separately permissioned (`user.founder.manage`) and audited. They need **step-up and dual control** by two different eligible Founders. If fewer than two exist, **break-glass** requires two distinct AWS IAM custodians (OWNER-INPUT-004), a cooling-off with notification and a cancel link to all Founders and the target, CRITICAL events, and CloudTrail evidence (06 §7.5).
6. **Tests** cover all of the above, negatively as well as positively (12 §4.4).

## Alternatives considered

| Option | Why rejected |
|---|---|
| Keep `user.update` and mark it sensitive | Still mixes profile and identity edits, and still allows direct email replacement |
| Allow admin direct email replacement with notification | Owner Decision 3 forbids it |
| Founder identified by role code | Violates RBAC-002 |
| Single-approver Founder actions | Owner Decision 3 requires dual control |

## Consequences

- New columns on `app_user`: `proposed_email*`, `email_verified_on`, `protection_level`, `security_cooling_off_until`.
- New table `admin_approval_request`. New endpoints under `/users/{id}/…`, `/approvals` and `/founder-actions`.
- The Admin role gains the granular sensitive permissions, so Admin MFA is mandatory, which is consistent with ADR-006.

## Risks

| Risk | Mitigation |
|---|---|
| Approval fatigue | Dual control only for privileged targets and Founder actions |
| Break-glass custodians unavailable | Two custodians, and OWNER-INPUT-004 requires a named designation |
| Proposed-email enumeration | Uniqueness errors are shown only to the requester, after step-up |

## Affected requirement IDs

RBAC-009, RBAC-010, RBAC-011, RBAC-019, RBAC-020, RBAC-021, USER-001, USER-002, USER-007, AUTH-008, MFA-007, MFA-015

## Affected documents

03 (§4.1, §5.8), 05 (§7, §8), 06 (§6.2, §7, §10), 08 (§4.8, §5), 09 (§4.6, §4.12, §4.13), 11, 12 (§4.4)

## Future review triggers

- Adding a customer or vendor portal (external principals)
- Adding API tokens or service accounts
- Personnel change among the Founders or custodians

## Approval record

| Item | Value |
|---|---|
| Approver | Veda Spaces owner (repository owner) |
| Approval | 2026-09-29, `VEDA-SPACES-P0-ARCHITECTURE-REMEDIATION-01`, Decision 3 |
| Evidence | [decision-log.md](decision-log.md). Verifiable owner sign-off tracked as TG-01. |
