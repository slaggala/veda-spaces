# AM-2: proposed amendment to 08 §4.5, 05 §11.3

> **Status: PROPOSED, NOT APPROVED.** Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`; reviewed implementation `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; final targeted check review/p0-independent-implementation-review @ 56c20ba992b519daa79aa3802a28343aab8c0b41. This proposal lives outside `docs/architecture/`, changes no certified document, and records no owner decision.

| Field | Value |
|---|---|
| Amendment ID | AM-2 |
| Status | **PROPOSED, NOT APPROVED** |
| Amends | 08 §4.5, 05 §11.3 |
| Affected requirements | AUTH-011, MFA-014, UI-015 |
| Related findings | DEV-002 (conditions IR-01, IR-21, IR-25) |
| Related deviation | DEV-002 |
| Final targeted check classification | TECHNICALLY SOUND WITH OWNER CONDITIONS (accept invite-link password-overwrite residual) |
| Certified behavior | POST /auth/invite/accept → 204. |
| Proposed behavior | When MFA is required, POST /auth/invite/accept returns 200 {status: MFA_ENROLLMENT_REQUIRED, invite_context, expires_in} instead of 204. Precise state machine: (1) acceptance sets the password and leaves the account INVITED with no session; the invitation link stays live (72 h, 24 h for a sensitive invite) and is not marked used. (2) The context is an INVITE_CONTEXT enrollment challenge: single use, 15 minutes, confirmable only on PATH_B without a bearer token. (3) Replay: presenting the live link again sets a new password (replacing the earlier one), revokes every earlier context and PENDING factor, and issues a new context. (4) Abandonment: if the context expires unused, the account stays INVITED with the chosen password; a PENDING factor created by enroll/start remains inert (never authenticates, RR-A06) until the next acceptance or enrollment replaces it; sign-in is refused (INVITED) because the account is not active. (5) Activation happens only when the factor is confirmed; then the link is consumed. The two proofs of path B are possession of the invitation link and possession of the TOTP secret shown to whoever holds it; the password is chosen by the link holder. |
| Reason | A 204 cannot carry the enrollment continuation required by 05 §11.3 path B. |
| Implementation at the reviewed SHA and after | Implemented as proposed (service.accept_invite, mfa.enroll_start/confirm with PATH_B binding). Replay behaviour described above is the current code: api/veda/platform/auth/service.py accept_invite accepts the live INVITE token again while the user is INVITED. |
| Security impact | Residual the owner must accept: anyone holding the invitation link before activation can set the password and enrol their own factor, and can replace an earlier acceptance. The invitation email is the trust anchor, as in the certified invite flow (05 §8.4). |
| Data impact | None beyond AM-11. |
| API impact | New 200 response shape on invite/accept. |
| UI impact | Accept-invite routes to enrollment. |
| Compatibility impact | Additive (API-009). |
| Rollback or forward-fix | None without an alternative path-B design (the certified 204 cannot express the continuation). |
| Required tests | `api/tests/integration/test_mfa.py::test_MFA_014_path_b_invitation_enrollment`<br>`api/tests/integration/test_auth_remediation.py::test_IR21_*`<br>`api/tests/integration/test_mfa_binding.py::test_IR01_invitation_context_is_single_account_and_unauthenticated` |
| Staging evidence | None. |
| Production evidence | Invitation email delivery through SES in staging before production. |
| Failure behavior | An expired or superseded context, a bearer on path B, or a confirmation outside the binding is answered as an unknown challenge (401); nothing is activated. |
| Owner decision required | Approve the response shape and accept the stated link-possession residual, or require an additional proof before activation. |
| Approval readiness | Wording corrected per RR assessment; submit with the reviewer's confirmation. |
| Decision owner | Architecture Owner |
