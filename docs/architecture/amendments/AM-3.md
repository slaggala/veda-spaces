# AM-3: proposed amendment to 08 §4.1, §4.7

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It does not modify the certified documents and has no effect until the decision owner approves it.

| Field | Value |
|---|---|
| Amendment ID | AM-3 |
| Related finding | DEV-003 (conditions IR-22, IR-09, IR-02) |
| Related deviation | DEV-003 |
| Amends | 08 §4.1, §4.7 |
| Existing certified behavior | Login body {email, password}; no CAPTCHA field or signal. |
| Proposed behavior | Optional turnstile_token (≤ 2048) on login; 401 INVALID_CREDENTIALS carries captcha_required; MFA 401s carry attempts_remaining. Verification runs outside the write lock (IR-02); networks are parsed /24 and /64 (IR-22); the development verifier exists only in local/test (IR-09). |
| Reason | 05 §4 cannot be implemented with the closed 08 §4.1 schema. |
| Security impact | Implements the certified control; uniform responses kept. |
| Data impact | None. |
| API impact | Optional fields. |
| UI impact | Login shows the widget when required. |
| Compatibility impact | Additive. |
| Tests | `api/tests/integration/test_auth.py::test_DEV_003_optional_captcha_token_after_network_throttle`<br>`api/tests/integration/test_intake_lock.py`<br>`api/tests/integration/test_auth_remediation.py::test_IR22_*` |
| Rollback | Remove the field; throttling falls back to the delay only. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
