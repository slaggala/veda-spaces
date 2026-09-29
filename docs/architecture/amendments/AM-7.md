# AM-7: proposed amendment to 08 §12

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It does not modify the certified documents and has no effect until the decision owner approves it.

| Field | Value |
|---|---|
| Amendment ID | AM-7 |
| Related finding | IR-23 |
| Related deviation | DEV-007 |
| Amends | 08 §12 |
| Existing certified behavior | POST /auth/login 5/min per email; POST /auth/password/forgot 3/hour per email. |
| Proposed behavior | Key both per-email limits on (email, client network /24 or /64). |
| Reason | A third party must not be able to lock an account holder out from every network. |
| Security impact | Distributed guessing is still bounded by the per-account throttles of 05 §4. |
| Data impact | None. |
| API impact | Limit keys only. |
| UI impact | None. |
| Compatibility impact | None. |
| Tests | `api/tests/integration/test_auth_remediation.py::test_IR23_P5_third_party_cannot_rate_limit_the_victim_from_elsewhere` |
| Rollback | Key on the email alone. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
