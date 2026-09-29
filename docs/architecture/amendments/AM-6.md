# AM-6: proposed amendment to LOG-005, 08 §3, 02 §12.4

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It does not modify the certified documents and has no effect until the decision owner approves it.

| Field | Value |
|---|---|
| Amendment ID | AM-6 |
| Related finding | IR-10, IR-A17 |
| Related deviation | DEV-008 |
| Amends | LOG-005, 08 §3, 02 §12.4 |
| Existing certified behavior | /health/ready: 'migrations at head'; body shows checks publicly. |
| Proposed behavior | Readiness: head → ready; known older revision → not ready; revision unknown to the image → ready only if the operator declared it expand-only compatible (VEDA_SCHEMA_AHEAD_ACCEPTED, set by the N-1 rollback runbook); otherwise not ready. Check details only to direct local callers; the edge gets {status}. |
| Reason | The normal rollback (N-1 image on a migrated schema) must be able to pass readiness. |
| Security impact | Less public disclosure of internals. |
| Data impact | None. |
| API impact | Readiness body at the edge is {status} only. |
| UI impact | None. |
| Compatibility impact | Deploy gate on the host keeps the full body. |
| Tests | `api/tests/integration/test_ops_remediation.py` |
| Rollback | Revert to strict head equality (rollback path then requires snapshot restore). |
| Decision owner | Architecture Owner, Operations |
| Status | **PROPOSED, NOT APPROVED** |
