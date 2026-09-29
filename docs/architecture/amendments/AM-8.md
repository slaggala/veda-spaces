# AM-8: proposed amendment to 05 / 03

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It does not modify the certified documents and has no effect until the decision owner approves it.

| Field | Value |
|---|---|
| Amendment ID | AM-8 |
| Related finding | IR-A22 (OI-3) |
| Related deviation | — |
| Amends | 05 / 03 |
| Existing certified behavior | Action tokens are described as random single-use tokens with only a hash stored. |
| Proposed behavior | Document that raw tokens are HMAC(K_action, row id ‖ purpose) so the worker can rebuild links without storing secrets; a K_action compromise together with row ids yields every live link; rotating K_action invalidates all open links. |
| Reason | Documentation of the implemented trade-off. |
| Security impact | As stated. |
| Data impact | None. |
| API impact | None. |
| UI impact | None. |
| Compatibility impact | None. |
| Tests | `api/tests/integration/test_auth.py (token flows)` |
| Rollback | n/a |
| Decision owner | Architecture Owner, Security |
| Status | **PROPOSED, NOT APPROVED** |
