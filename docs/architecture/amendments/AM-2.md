# AM-2: proposed amendment to 08 §4.5, 05 §11.3

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It does not modify the certified documents and has no effect until the decision owner approves it.

| Field | Value |
|---|---|
| Amendment ID | AM-2 |
| Related finding | DEV-002 (conditions IR-01, IR-21, IR-25) |
| Related deviation | DEV-002 |
| Amends | 08 §4.5, 05 §11.3 |
| Existing certified behavior | POST /auth/invite/accept → 204. |
| Proposed behavior | When MFA is required: 200 {status: MFA_ENROLLMENT_REQUIRED, invite_context, expires_in}. The context is an INVITE_CONTEXT enrollment challenge: single-use, 15 min, one live per invitee (a resend or repeated acceptance supersedes earlier ones), confirmable only through PATH_B without a bearer. Acknowledge that path B's second proof (the new password) is chosen by whoever holds the link. |
| Reason | A 204 cannot carry the enrollment continuation required by 05 §11.3 path B. |
| Security impact | Two out-of-band proofs; no session before confirmation; binding per AM-11. |
| Data impact | None beyond AM-11. |
| API impact | New 200 response shape on invite/accept. |
| UI impact | Accept-invite routes to enrollment. |
| Compatibility impact | Additive (API-009). |
| Tests | `api/tests/integration/test_mfa.py::test_MFA_014_path_b_invitation_enrollment`<br>`api/tests/integration/test_auth_remediation.py::test_IR21_*`<br>`api/tests/integration/test_mfa_binding.py::test_IR01_invitation_context_is_single_account_and_unauthenticated` |
| Rollback | None without an alternative path-B design. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
