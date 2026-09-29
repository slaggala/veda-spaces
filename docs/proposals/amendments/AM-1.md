# AM-1: proposed amendment to 03 §5.5

> **Status: PROPOSED, NOT APPROVED.** Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`; reviewed implementation `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; final targeted check review/p0-independent-implementation-review @ 56c20ba992b519daa79aa3802a28343aab8c0b41. This proposal lives outside `docs/architecture/`, changes no certified document, and records no owner decision.

| Field | Value |
|---|---|
| Amendment ID | AM-1 |
| Status | **PROPOSED, NOT APPROVED** |
| Amends | 03 §5.5 |
| Affected requirements | MFA-005, MFA-013, MFA-014 |
| Related findings | DEV-001 (condition IR-20) |
| Related deviation | DEV-001 |
| Final targeted check classification | TECHNICALLY SOUND |
| Certified behavior | ux_user_mfa_factor__user_live UNIQUE (user_id, factor_type) WHERE status IN ('PENDING','ACTIVE') AND is_deleted = false. |
| Proposed behavior | Key the index on (user_id, factor_type, status) with the same predicate: at most one PENDING and one ACTIVE factor per user and type. Path C never replaces an ACTIVE factor; any confirmation ends every other open enrollment transaction and link (IR-20). |
| Reason | The certified key contradicts 05 §11.5 and TD-E, which keep the current factor ACTIVE while a replacement is PENDING. |
| Implementation at the reviewed SHA and after | Implemented in migration 0004_auth and mfa.py exactly as proposed; unchanged by this workstream. |
| Security impact | No weakening: one ACTIVE factor per user; a PENDING factor never authenticates; IR-20 closes replacement without step-up. |
| Data impact | Index key only; no column change. |
| API impact | None. |
| UI impact | None. |
| Compatibility impact | None: the index exists in every deployed schema since 0004. |
| Rollback or forward-fix | Not independently reversible: restoring the two-column key requires a different TD-E design first. Rollback of the release follows runbook §2 (no image older than the rollback floor). |
| Required tests | `api/tests/integration/test_mfa.py::test_TD_E_failed_reenrollment_commits_nothing_that_grants_access`<br>`api/tests/integration/test_auth_remediation.py::test_IR20_*` |
| Staging evidence | Migration upgrade-with-data on SQLite, PostgreSQL 16 and 18 (CI and local evidence); no staging host run yet. |
| Production evidence | Not applicable beyond the release gates. |
| Failure behavior | A second PENDING or ACTIVE factor of the same type is a unique violation (409); the transaction rolls back. |
| Owner decision required | Approve the three-column key (OD-1). |
| Approval readiness | Wording complete and behaviour matches (OD-1). Submit for owner approval after the reviewer's final targeted check confirms. |
| Decision owner | Architecture Owner |
