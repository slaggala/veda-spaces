# Catalog V3: incident runbook (rollback stays fail-closed)

**Status:** V3 is off in every environment. This runbook applies once V3 is enabled anywhere.

Tests: `api/tests/integration/test_catalog_incident_runbook.py`, `api/tests/integration/test_catalog_claim_validity.py`.

**The rule: never bypass public-payload governance during an incident.** Every path below goes through the same
release validation, payload digest and four-eyes approvals as a normal release. There is no override flag, no
force-activate and no manual edit of a released record.

## 1. Diagnose the invalid dependency

When V3 answers `503 ESTIMATOR_UNAVAILABLE`, or a rollback is refused:

1. Read the API log event `catalog.public_payload_refused`. It names the payload (`catalog`, `estimate` or `claims`)
   and the failing fields. It never includes the text itself or any rate.
2. List the governed claims: `GET /api/v1/catalog/claims` (permission `catalog.view`). Each claim shows `valid`, its
   `problems`, its review date and its latest control.
3. Run the active release's validation: `POST /api/v1/catalog/releases/<id>/validate` (`catalog.admin`). The report
   lists every failing check: `copy`, `promises`, `public_payload`, and so on.

Typical causes:
- A claim has reached its review date.
- A claim was withdrawn, or its owner was removed.
- A claim's applicability was narrowed.
- The active customer specification or a promise-matrix row changed.
- Media was withdrawn.

## 2. Is the last known-good manifest still resolvable on its own?

`POST /api/v1/catalog/rollback` (`catalog.admin`, with the expected active release code) restores the manifest that
was active immediately before the current one. It does this only if both hold:
- the restored manifest still validates under today's rules and controls, including every governed claim;
- its resolved public payload has exactly the digest it had when it was activated.

If anything it depends on has changed since (a specification, a promise-matrix row, a claim's standing), the rollback
is refused, and the active release stays as it was. That refusal is correct: the old payload is no longer the one
that was approved.

## 3. Restore through a new reviewed release

When a rollback is refused, recover forward:

1. Correct the cause in records. For example, remove the badge that references the claim and retire the claim record
   (`exclude` when creating the release), or update the copy.
2. Create the recovery release.
3. Validate it.
4. Approve the preview. The approver is someone other than the author and contributors, and reviews the "new and
   changed public copy" report.
5. Submit the release.
6. Approve the release (four eyes) with an approval reference.
7. Activate it.

A claim can also be withdrawn without a release: `POST /api/v1/catalog/claims/<key>/control` with action `WITHDRAW`
and a reason. Its effect is to make V3 fail closed until a recovery release without the claim is active. It does not
silently hide the claim.

## 4. Emergency: switch V3 off

Set `VEDA_CATALOG_ESTIMATOR_ENABLED=false` and redeploy or restart. The public V3 routes then answer `404`.

V1 and V2 are unaffected: their routes and switches (`VEDA_ESTIMATOR_ENABLED`, `STAGING_ESTIMATOR_UX`) are separate,
and the V2 estimate route keeps answering on its own terms.

Switch V3 back on only after a valid release is active.

## 5. What is tested

| Scenario | Test |
|---|---|
| Ordinary rollback | `test_an_ordinary_rollback_restores_the_previous_manifest` |
| Rollback blocked by an invalid (withdrawn) claim | `test_a_rollback_to_a_release_whose_claim_is_now_invalid_is_refused` |
| Rollback blocked by a changed specification | `test_a_rollback_blocked_by_a_changed_specification_is_refused` |
| Emergency V3 disable, V1 and V2 unaffected | `test_the_emergency_action_switches_v3_off_and_leaves_v1_v2_alone` |
| New reviewed recovery release | `test_recovery_is_a_new_reviewed_release` |
