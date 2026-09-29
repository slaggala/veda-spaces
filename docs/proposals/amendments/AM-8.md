# AM-8: proposed amendment to 05 / 03

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It lives outside `docs/architecture/`, does not modify the certified documents, and has no effect until the decision owner approves it. Nothing here claims owner approval or implementation authorization.

| Field | Value |
|---|---|
| Amendment ID | AM-8 |
| Amends | 05 / 03 |
| Related findings | IR-A22 (OI-3) |
| Related deviation | — |
| Targeted re-review assessment | Technically sound (documentation). |
| Existing certified behavior | Action tokens are described as random single-use tokens with only a hash stored. |
| Proposed behavior | Document that raw tokens are HMAC(K_action, row id ‖ purpose) so the worker can rebuild links without storing secrets; a K_action compromise together with row ids yields every live link; rotating K_action invalidates all open links. |
| Reason | Documentation of the implemented trade-off. |
| Code behavior at this commit | As described. |
| Security | As stated; K_action must differ from every other key (enforced in staging and production, RR-10). |
| Data impact | None. |
| API impact | None. |
| UI impact | None. |
| Compatibility | None. |
| Rollback | Not applicable (documentation). |
| Tests | `api/tests/integration/test_auth.py (token flows)`<br>`api/tests/unit/test_config_environments.py` |
| Owner decision requested | Accept the documented trade-off. |
| Staging evidence | None. |
| Production evidence | Key provisioning evidence. |
| Approval readiness | Ready to submit. |
| Decision owner | Architecture Owner, Security |
| Status | **PROPOSED, NOT APPROVED** |
