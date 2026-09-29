# AM-6: proposed amendment to LOG-005, 08 §3, 02 §12.4

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It lives outside `docs/architecture/`, does not modify the certified documents, and has no effect until the decision owner approves it. Nothing here claims owner approval or implementation authorization.

| Field | Value |
|---|---|
| Amendment ID | AM-6 |
| Amends | LOG-005, 08 §3, 02 §12.4 |
| Related findings | IR-10, IR-A17, RR-17 |
| Related deviation | DEV-008 |
| Targeted re-review assessment | Technically sound; incomplete: rollback of this release is snapshot restore; details unreachable from the host. |
| Existing certified behavior | /health/ready: 'migrations at head'; body shows checks publicly. |
| Proposed behavior | Readiness: head → ready; known older revision → not ready; revision unknown to the image → ready only if the operator declared it expand-only compatible (VEDA_SCHEMA_AHEAD_ACCEPTED, set by the N-1 rollback runbook); otherwise not ready. Check details only to loopback callers; the edge and the host (through the Docker bridge) get {status}; deploy tooling reads details inside the container (veda schema-status, in-container readiness). Rollback boundary: each release declares a rollback floor revision; an image that does not know it is never a rollback target. For this release the floor is 0009_mfa_challenge_binding, so the previous image (9236aa3) is not a valid rollback target — it cannot pass readiness on the migrated schema and would reintroduce IR-01. Recovery from a defect in this release is a forward fix, or a snapshot restore to the pre-deploy snapshot followed by redeploying a fixed image (runbook §3). |
| Reason | The normal rollback (N-1 image on a migrated schema) must be able to pass readiness, and must never reintroduce a fixed security defect. |
| Code behavior at this commit | Readiness states implemented (health.py). deploy.sh now reads the revision and readiness inside the container and refuses a rollback target that does not know ROLLBACK_FLOOR; `veda schema-status` added. |
| Security | Less public disclosure; a rollback cannot silently restore the IR-01-vulnerable image. |
| Data impact | None. |
| API impact | Readiness body at the edge is {status} only. |
| UI impact | None. |
| Compatibility | Operators must use deploy.sh or veda schema-status for details. |
| Rollback | Revert to strict head equality (every rollback then requires snapshot restore). |
| Tests | `api/tests/integration/test_ops_remediation.py`<br>`api/tests/integration/test_archive_ordering.py::test_RR17_*` |
| Owner decision requested | Approve the readiness states, the rollback floor mechanism and the statement that this release rolls back only by forward fix or snapshot restore (OD-1). |
| Staging evidence | RG-7 rollback rehearsal (not performed). |
| Production evidence | RG-7 evidence. |
| Approval readiness | Wording complete and behaviour matches; submit with the reviewer's confirmation (OD-1). No rehearsal is claimed. |
| Decision owner | Architecture Owner, Operations |
| Status | **PROPOSED, NOT APPROVED** |
