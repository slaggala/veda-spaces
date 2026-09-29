# AM-6: proposed amendment to LOG-005, 08 §3, 02 §12.4

> **Status: PROPOSED, NOT APPROVED.** Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`; implementation logic `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; reviewed tree `3f5920b17d21214b39414d080d34246746c8c40d`; document-level check review/p0-independent-implementation-review @ 093cfa6872c209deb9991910c457afcdb4ad2d04. This proposal lives outside `docs/architecture/`, changes no certified document, and records no owner decision.

| Field | Value |
|---|---|
| Amendment ID | AM-6 |
| Status | **PROPOSED, NOT APPROVED** |
| Amends | LOG-005, 08 §3, 02 §12.4 |
| Affected requirements | LOG-005, OPS-004 |
| Related findings | IR-10, IR-A17, RR-17 |
| Related deviation | DEV-008 |
| Final targeted check classification (56c20ba, verbatim) | TECHNICALLY SOUND WITH OWNER CONDITIONS (resolve FC-12 release floor) |
| Document-level check classification (093cfa6, verbatim) | TECHNICALLY SOUND WITH OWNER CONDITIONS |
| Certified behavior | /health/ready: 'migrations at head'; body shows checks publicly. |
| Proposed behavior | Readiness: head → ready; known older revision → not ready; revision unknown to the image → ready only if the operator declared it expand-only compatible (VEDA_SCHEMA_AHEAD_ACCEPTED, set by the N-1 rollback runbook); otherwise not ready. Check details only to loopback callers; the edge and the host (through the Docker bridge) get {status}; deploy tooling reads details inside the container (veda schema-status, in-container readiness). Release and schema floors: each image reports a release sequence (veda/release.py) and the revisions it knows; deploy.sh refuses, in every mode (normal deploy and --rollback), an image whose sequence is below RELEASE_FLOOR or that does not know ROLLBACK_FLOOR, before stopping, migrating or starting anything. No flag or variable overrides them. For this release the floor is 0009_mfa_challenge_binding, so the previous image (9236aa3) is not a valid rollback target — it cannot pass readiness on the migrated schema and would reintroduce IR-01. Recovery from a defect in this release is a forward fix, or a snapshot restore to the pre-deploy snapshot followed by redeploying a fixed image (runbook §3). |
| Reason | The normal rollback (N-1 image on a migrated schema) must be able to pass readiness, and must never reintroduce a fixed security defect. |
| Implementation (provenance) | Readiness states implemented (health.py). deploy.sh reads revision, release and readiness inside the target image's container; RELEASE_FLOOR=3 and ROLLBACK_FLOOR=0009_mfa_challenge_binding are enforced in every mode (FC-12); images too old to report (9236aa3, 2f6b59a) are refused. The release floor (FC-12) was added at 3f5920b. |
| Security impact | Less public disclosure; a rollback cannot silently restore the IR-01-vulnerable image. |
| Data impact | None. |
| API impact | Readiness body at the edge is {status} only. |
| UI impact | None. |
| Compatibility impact | Operators must use deploy.sh or veda schema-status for details. |
| Rollback or forward-fix | Revert to strict head equality (every rollback then requires snapshot restore). |
| Required tests | `api/tests/integration/test_ops_remediation.py`<br>`api/tests/integration/test_archive_ordering.py::test_RR17_*`<br>`api/tests/unit/test_deploy_floor.py (stubbed docker; not a rehearsal)` |
| Staging evidence | RG-7 rollback rehearsal (not performed). |
| Production evidence | RG-7 evidence. |
| Failure behavior | Readiness 503 for behind, missing or undeclared-ahead schemas; deploy.sh refuses any image below either floor before changing anything. |
| Owner decision required | Approve the readiness states, the rollback floor mechanism and the statement that this release rolls back only by forward fix or snapshot restore (OD-1). |
| Approval readiness | Wording complete and behaviour matches; submit with the reviewer's confirmation (OD-1). No rehearsal is claimed. |
| Decision owner | Architecture Owner, Operations |
