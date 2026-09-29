# ADR-006: MFA policy

- **Status:** Accepted
- **Date:** 2026-09-29

## Context

Founder and Admin accounts can change access for everyone and read all customer data. Credential stuffing and phishing are the most likely attack paths for a small business. The platform forbids role-name authorization checks, so MFA enforcement must also avoid role-name logic.

## Decision

| Role | MFA |
|---|---|
| Founder | **Mandatory** |
| Admin | **Mandatory** |
| Sales | **Configurable**, per user or per role |

**Policy mechanism (data-driven, 05 §11.1).** MFA is required if any of these is true:

1. The user holds a live role with `role.mfa_required = true`. Seeded true for FOUNDER and ADMIN.
2. `app_user.mfa_required = true`.
3. The user holds any `is_sensitive` permission.

No code compares role names.

**Requirements:**

| Requirement | Design |
|---|---|
| Factor | TOTP authenticator apps (RFC 6238). Secrets are KMS-envelope-encrypted and shown once. |
| Recovery codes | 10 one-time codes, stored **only as keyed hashes**, shown once, single use |
| Events | Enrollment, challenges, recovery-code use, regeneration and resets are recorded in `security_event_log` |
| Reset | A privileged workflow: `user.mfa.manage`, step-up, a reason, no self-reset, no stronger target, all sessions revoked, notifications, CRITICAL alert. The break-glass CLI is for a sole Founder. |
| Excluded | Security questions, SMS or email OTP as a factor, device-remember bypass |
| Authorization | Remains permission-based. MFA gates authentication, not permissions. |

## Alternatives considered

| Option | Why rejected |
|---|---|
| Check the role code (`if role in [FOUNDER, ADMIN]`) | Violates RBAC-002 |
| SMS OTP | SIM-swap and phishing risk, plus cost |
| WebAuthn/passkeys only | Excellent, but device and browser readiness varies among staff. The schema allows adding it later (`factor_type`). |
| MFA optional for all in P0 | The owner requires it for privileged roles |

## Consequences

- New tables: `user_mfa_factor`, `user_mfa_recovery_code`, `mfa_challenge`. New columns: `role.mfa_required`, `app_user.mfa_required`, `user_session.mfa_verified_on`.
- New permission `user.mfa.manage`. New guards G9 and G10.
- The login flow has multi-step responses (`MFA_REQUIRED`, `MFA_ENROLLMENT_REQUIRED`).
- A KMS key is required in AWS.

## Risks

| Risk | Mitigation |
|---|---|
| Lost device plus lost codes locks out the sole Founder | Break-glass CLI via SSM, audited |
| MFA reset social engineering | Identity-verification procedure, step-up, alerts to all holders |
| TOTP replay | `last_used_step` |

## Affected requirement IDs

AUTH-015, MFA-001 through MFA-011, RBAC-017, USER-006, UI-015, SEC-005

## Affected documents

03 (§4.1, §4.3, §5.1, §5.5–5.7), 05 (§3, §4, §9, §11, §12), 06 (§2, §3, §6.2, §7, §9, §11), 08 (§4.1, §4.7, §5.9), 09 (§4.1, §4.6, §4.10), 11 (§5, §6), 12 (§4.5)

## Future review triggers

- Adding WebAuthn/passkeys
- Customer or vendor portal launch (different MFA posture)
- Any MFA-related security incident
