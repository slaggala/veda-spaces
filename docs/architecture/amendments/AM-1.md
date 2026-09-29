# AM-1: proposed amendment to 03 §5.5

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It does not modify the certified documents and has no effect until the decision owner approves it.

| Field | Value |
|---|---|
| Amendment ID | AM-1 |
| Related finding | DEV-001 (condition IR-20) |
| Related deviation | DEV-001 |
| Amends | 03 §5.5 |
| Existing certified behavior | ux_user_mfa_factor__user_live UNIQUE (user_id, factor_type) WHERE status IN ('PENDING','ACTIVE') AND is_deleted = false. |
| Proposed behavior | Key the index on (user_id, factor_type, status) with the same predicate: at most one PENDING and one ACTIVE factor per user and type. Path C may never replace an ACTIVE factor; any confirmation ends every other open enrollment transaction and link (IR-20). |
| Reason | The certified key contradicts 05 §11.5 and TD-E, which keep the current factor ACTIVE while a replacement is PENDING. |
| Security impact | None negative: one ACTIVE factor; a PENDING factor never authenticates. IR-20 closes the replacement-without-step-up path. |
| Data impact | Index key only (0004_auth); no column change. |
| API impact | None. |
| UI impact | None. |
| Compatibility impact | None. |
| Tests | `api/tests/integration/test_mfa.py::test_TD_E_failed_reenrollment_commits_nothing_that_grants_access`<br>`api/tests/integration/test_auth_remediation.py::test_IR20_*` |
| Rollback | Restore the two-column key; needs a different TD-E design first. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
