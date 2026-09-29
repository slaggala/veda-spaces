# AM-1: proposed amendment to 03 §5.5

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It lives outside `docs/architecture/`, does not modify the certified documents, and has no effect until the decision owner approves it. Nothing here claims owner approval or implementation authorization.

| Field | Value |
|---|---|
| Amendment ID | AM-1 |
| Amends | 03 §5.5 |
| Related findings | DEV-001 (condition IR-20) |
| Related deviation | DEV-001 |
| Targeted re-review assessment | Technically sound (targeted re-review §11). |
| Existing certified behavior | ux_user_mfa_factor__user_live UNIQUE (user_id, factor_type) WHERE status IN ('PENDING','ACTIVE') AND is_deleted = false. |
| Proposed behavior | Key the index on (user_id, factor_type, status) with the same predicate: at most one PENDING and one ACTIVE factor per user and type. Path C never replaces an ACTIVE factor; any confirmation ends every other open enrollment transaction and link (IR-20). |
| Reason | The certified key contradicts 05 §11.5 and TD-E, which keep the current factor ACTIVE while a replacement is PENDING. |
| Code behavior at this commit | Implemented in migration 0004_auth and mfa.py exactly as proposed; unchanged by this workstream. |
| Security | No weakening: one ACTIVE factor per user; a PENDING factor never authenticates; IR-20 closes replacement without step-up. |
| Data impact | Index key only; no column change. |
| API impact | None. |
| UI impact | None. |
| Compatibility | None: the index exists in every deployed schema since 0004. |
| Rollback | Not independently reversible: restoring the two-column key requires a different TD-E design first. Rollback of the release follows runbook §2 (no image older than the rollback floor). |
| Tests | `api/tests/integration/test_mfa.py::test_TD_E_failed_reenrollment_commits_nothing_that_grants_access`<br>`api/tests/integration/test_auth_remediation.py::test_IR20_*` |
| Owner decision requested | Approve the three-column key (OD-1). |
| Staging evidence | Migration upgrade-with-data on SQLite, PostgreSQL 16 and 18 (CI and local evidence); no staging host run yet. |
| Production evidence | Not applicable beyond the release gates. |
| Approval readiness | Wording complete and behaviour matches (OD-1). Submit for owner approval after the reviewer's final targeted check confirms. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
