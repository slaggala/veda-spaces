# AM-2: proposed amendment to 08 §4.5, 05 §11.3

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It lives outside `docs/architecture/`, does not modify the certified documents, and has no effect until the decision owner approves it. Nothing here claims owner approval or implementation authorization.

| Field | Value |
|---|---|
| Amendment ID | AM-2 |
| Amends | 08 §4.5, 05 §11.3 |
| Related findings | DEV-002 (conditions IR-01, IR-21, IR-25) |
| Related deviation | DEV-002 |
| Targeted re-review assessment | Technically sound; incomplete: link replay before activation overwrites the password. |
| Existing certified behavior | POST /auth/invite/accept → 204. |
| Proposed behavior | When MFA is required: 200 {status: MFA_ENROLLMENT_REQUIRED, invite_context, expires_in}. The context is an INVITE_CONTEXT enrollment challenge: single use, 15 minutes, one live per invitee (a resend or a repeated acceptance supersedes earlier contexts), confirmable only through PATH_B without a bearer token. Until the invitee confirms the factor the account stays INVITED and the invitation link stays live: presenting it again sets a new password, replacing the one chosen at the earlier acceptance, and revokes the earlier context. Path B's two proofs are therefore possession of the invitation link and the TOTP secret shown to whoever holds it; the password is chosen by the link holder and is not an independent proof. |
| Reason | A 204 cannot carry the enrollment continuation required by 05 §11.3 path B. |
| Code behavior at this commit | Implemented as proposed (service.accept_invite, mfa.enroll_start/confirm with PATH_B binding). Replay behaviour described above is the current code: api/veda/platform/auth/service.py accept_invite accepts the live INVITE token again while the user is INVITED. |
| Security | No session before confirmation; binding per AM-11. Residual accepted by this proposal: anyone who obtains the invitation link before activation can set the password and enrol their own factor. The invitation email is the trust anchor, as in the certified invite flow (05 §8.4). |
| Data impact | None beyond AM-11. |
| API impact | New 200 response shape on invite/accept. |
| UI impact | Accept-invite routes to enrollment. |
| Compatibility | Additive (API-009). |
| Rollback | None without an alternative path-B design (the certified 204 cannot express the continuation). |
| Tests | `api/tests/integration/test_mfa.py::test_MFA_014_path_b_invitation_enrollment`<br>`api/tests/integration/test_auth_remediation.py::test_IR21_*`<br>`api/tests/integration/test_mfa_binding.py::test_IR01_invitation_context_is_single_account_and_unauthenticated` |
| Owner decision requested | Approve the response shape and accept the stated link-possession residual, or require an additional proof before activation. |
| Staging evidence | None. |
| Production evidence | Invitation email delivery through SES in staging before production. |
| Approval readiness | Wording corrected per RR assessment; submit with the reviewer's confirmation. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
