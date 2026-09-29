# ADR-006: MFA policy, sensitive-permission activation and MFA recovery

- **Status:** Accepted (amended by remediation 01)
- **Date:** 2026-09-29
- **Amended:** 2026-09-29, by owner Decisions 1 and 2 of `VEDA-SPACES-P0-ARCHITECTURE-REMEDIATION-01`. These resolve review findings F-01 and F-02.

## Context

- Founder and Admin accounts control access for everyone and can read all customer data.
- Independent review found two problems:
  - **F-01.** The frozen design made Sales MFA "configurable" while the seeded matrix gave Sales a sensitive permission (`security_event.read` OWN), which forced MFA on every Sales user.
  - **F-02.** A new authenticator could be enrolled with a password alone after an MFA reset or a policy change.
- The platform forbids role-name authorization checks, so MFA policy must be data-driven.

## Decision

### 1. Who must use MFA (owner Decision 1)

| Subject | MFA |
|---|---|
| Founder | **Mandatory** |
| Admin | **Mandatory** |
| Any user holding a privileged or sensitive permission | **Mandatory** |
| Standard Sales | **Optional by default.** Configurable per user (`app_user.mfa_required`) or per role (`role.mfa_required`). |

**Mechanism (05 §11.1).** MFA is required if the user holds a role with `role.mfa_required`, **or** `app_user.mfa_required` is set, **or** the user holds any sensitive permission. No code compares role names.

**Sensitivity classification** is canonical and data-driven (06 §3.1): a permission is sensitive if and only if its code-registry entry has a `sensitivity_class` (`ACCOUNT_CONTROL`, `ACCESS_CONTROL`, `SECURITY_DATA`, `BULK_DATA`, `DESTRUCTIVE`). It never depends on role names.

**`security_event.read` is removed from the default Sales role.** It is ALL-only (no OWN variant), so standard Sales users cannot read any security-event records, including their own.

**Activation (MFA-012).** A sensitive permission is **not effective** until the holder has completed MFA enrollment and the current session is MFA-verified (06 §3.2, §5).

- Assigning one to a user without MFA leaves it suspended ("Pending MFA").
- Removing or resetting MFA suspends all sensitive permissions until re-enrollment.
- Authorization caches are keyed on `authz_version`, which increments on every MFA-state change. Sessions are checked uncached on every request, so the effect is immediate (06 §9).

### 2. Enrollment is never single-factor (F-02)

A new authenticator may be enrolled only via one of the four two-proof paths in 05 §11.3:

| Path | Proofs |
|---|---|
| A | Logged-in session + password re-entry, or step-up with the existing factor |
| B | Invite token + password set |
| C | Emailed single-use enrollment token + password re-entry |
| D | Recovery session (password + recovery code) |

A password alone, or a recovery code alone, never enrolls an authenticator.

### 3. Self-service recovery (owner Decision 2, 05 §11.5)

1. Recovery requires **password re-entry and one valid single-use recovery code**.
2. Success establishes only a **restricted RECOVERY session**. It lasts 15 minutes, has no refresh token, and can call only the endpoint allow-list: `me`, `enroll/start`, `enroll/confirm`, `logout`.
3. The recovery session cannot perform role, permission or email changes, password-reset-destination changes or API-token creation (none exist in P0, and any future token feature must honor this), or any privileged administration.
4. All other sessions and refresh tokens are revoked on successful recovery.
5. A security notification goes to the **current verified** email.
6. **Cooling-off.** After re-enrollment, `security_cooling_off_until` blocks the following for `MFA_RECOVERY_COOLING_OFF_HOURS` (a documented configuration value, initial default 24 h):
   - own email change;
   - password change (the emailed reset remains available);
   - factor removal;
   - recovery-code regeneration;
   - the user's ACCOUNT_CONTROL and ACCESS_CONTROL permissions.
7. **Recovery codes:**
   - generated with a CSPRNG;
   - stored only as keyed HMAC hashes;
   - single use;
   - rotated at every (re-)enrollment, including after recovery;
   - never logged;
   - never returned after initial issuance.

### 4. Administrative MFA reset (owner Decision 2, 05 §11.7)

- It uses the separate permission `user.mfa.reset`, and requires step-up, a reason and an audit trail.
- **No administrator can reset their own MFA** (G3).
- No action on a stronger account (G9).
- **Dual control** for any privileged target (G12).
- **No single Admin can reset the Founder's MFA.** Founder targets use the Founder workflow, which needs two different eligible Founders (G11), or break-glass with two distinct AWS IAM custodians and a notification-and-cancel window (06 §7.5).
- The enrollment link after a reset goes to the target's **verified** email, never to an administrator.

### 5. Security events

Every stage is recorded in `security_event_log` (05 §9.1):

- recovery initiated, failed and completed;
- recovery code consumed;
- sessions revoked;
- authenticator re-enrolled;
- administrative MFA reset requested, approved, denied and completed;
- permission suspended and reactivated.

### 6. Factor

TOTP (RFC 6238). The secret is KMS-envelope-encrypted (wrapped key stored as TEXT, ARN stored separately) and shown once.

**Excluded:**

- security questions;
- SMS or email OTP as a factor;
- "remember device";
- recovery-code-only enrollment.

## Alternatives considered

| Option | Why rejected |
|---|---|
| Keep `security_event.read` OWN for Sales and exempt OWN from the MFA rule | The owner chose to remove Sales access entirely |
| MFA for all staff | Contradicts owner Decision 1 (Sales optional) |
| Recovery code alone restores full access | Owner Decision 2 requires password + code, a restricted session and re-enrollment |
| Admin-delivered enrollment codes after reset | The admin would become a single point of account takeover |
| Role-name checks for Founder/Admin MFA | Violates RBAC-002 |

## Consequences

- New or changed schema:
  - `role.mfa_required` and `app_user.mfa_required`;
  - `app_user.security_cooling_off_until`;
  - `user_session.session_type` and `reauth_on`;
  - `user_action_token` purposes `MFA_ENROLLMENT` and `EMAIL_*`;
  - `user_mfa_factor.wrapped_data_key` and `kms_key_arn`;
  - `admin_approval_request`.
- New endpoints: `/auth/mfa/recovery`, `/auth/reauth`, `/approvals/*`.
- New permissions: `user.mfa.reset`, `user.mfa.require`, `user.founder.manage`.
- An Admin who has not enrolled works with sensitive permissions suspended until enrollment.

## Risks

| Risk | Mitigation |
|---|---|
| Sole Founder loses device and codes | Break-glass with two custodians and a cancel window (06 §7.5) |
| Attacker holds password and a recovery code | Restricted session, notification to the verified email, revocation of other sessions, cooling-off, High alert, new-network enrollment alert |
| Admin enrollment friction | "Pending MFA" UI and emailed links |

## Affected requirement IDs

AUTH-015, AUTH-018, MFA-001 … MFA-015, RBAC-017, RBAC-018, SEVT-005, USER-006, UI-015

## Affected documents

03 (§4.1, §4.3, §4.4, §5.1, §5.3, §5.5–§5.8), 05 (§3, §4, §5, §9, §11, §12), 06 (§2, §3, §5, §6, §7, §9, §10, §11), 08 (§4.1, §4.4, §4.7, §5.9, §5.10, §5.11), 09 (§4.6, §4.10, §4.12), 11, 12 (§4.4, §4.5)

## Future review triggers

- Adding WebAuthn/passkeys
- Portal launch
- Any MFA-related incident
- A change of the cooling-off default

## Approval record

| Item | Value |
|---|---|
| Approver | Veda Spaces owner (repository owner) |
| Original approval | 2026-09-29, `VEDA-SPACES-P0-ARCHITECTURE-SIGNOFF-AND-FREEZE`, decision ADR-006 |
| Amendment approval | 2026-09-29, `VEDA-SPACES-P0-ARCHITECTURE-REMEDIATION-01`, Decisions 1 and 2 |
| Evidence | [decision-log.md](decision-log.md). A verifiable owner sign-off (owner approval of the architecture pull request) is tracked gate TG-01 before implementation. |
