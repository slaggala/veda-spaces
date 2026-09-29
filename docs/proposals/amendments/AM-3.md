# AM-3: proposed amendment to 08 §4.1, §4.7

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It lives outside `docs/architecture/`, does not modify the certified documents, and has no effect until the decision owner approves it. Nothing here claims owner approval or implementation authorization.

| Field | Value |
|---|---|
| Amendment ID | AM-3 |
| Amends | 08 §4.1, §4.7 |
| Related findings | DEV-003 (conditions IR-22, IR-09, IR-02) |
| Related deviation | DEV-003 |
| Targeted re-review assessment | Technically sound. |
| Existing certified behavior | Login body {email, password}; no CAPTCHA field or signal. |
| Proposed behavior | Optional turnstile_token (≤ 2048) on login; 401 INVALID_CREDENTIALS carries captcha_required; MFA 401s carry attempts_remaining. Verification runs outside the write lock (IR-02); networks are parsed /24 and /64 (IR-22); the development verifier exists only in local and test (IR-09). The same field carries the challenge escalation of AM-7. |
| Reason | 05 §4 cannot be implemented with the closed 08 §4.1 schema. |
| Code behavior at this commit | Implemented as proposed. |
| Security | Implements the certified control; responses stay uniform for known and unknown accounts. |
| Data impact | None. |
| API impact | Optional fields. |
| UI impact | Login shows the widget when required. |
| Compatibility | Additive. |
| Rollback | Remove the field; throttling falls back to delays only and AM-7's challenge tier is lost. |
| Tests | `api/tests/integration/test_auth.py::test_DEV_003_optional_captcha_token_after_network_throttle`<br>`api/tests/integration/test_intake_lock.py`<br>`api/tests/integration/test_auth_remediation.py::test_IR22_*` |
| Owner decision requested | Approve. |
| Staging evidence | Real Turnstile keys in staging (IR-18) before production. |
| Production evidence | Turnstile production secret provisioned. |
| Approval readiness | Ready to submit. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
