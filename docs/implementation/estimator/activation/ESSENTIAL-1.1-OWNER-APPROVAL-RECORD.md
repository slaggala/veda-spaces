# ESSENTIAL-1.1 owner approval record

**Record:** [`essential-1.1-approval.json`](../../../../api/veda/modules/estimator/approved/essential-1.1-approval.json). **Status: PENDING.**

Do not activate until the owner explicitly approves the complete record. The owner fills it in a reviewed pull
request, using the digests that `veda estimator activation-check` prints for the reviewed commit. Activation and
every reactivation fail closed if any digest is stale (gate in `api/veda/modules/estimator/activation.py`).

## Values for this branch

These are current at this branch's head. They change whenever sales or operations record a decision, so the final
values are taken from `activation-check` on the commit the owner approves.

| Field | Value |
|---|---|
| Specification | ESSENTIAL-1.1 |
| Full specification digest (`specification_sha256`) | `6f798ef6cd3cea06f491041a4143e35776900107e73e6c953fbed4bd37ad286d` |
| Full promise-matrix digest (`promise_matrix_sha256`) | `ed3b14e0afadecfbb350d022f3bbd028407f7b3f790ff4ec85f0aacf53bbcb3b` |
| Operations-confirmation version | 1 (the matrix version) |
| Sales-decision version and digest | 1, `4aefa90ae5ab225ad395b9871cf1c97620e8279d5153d1af35542c9ba1283863` |
| Customer-copy digest (`customer_copy_sha256`) | `8bf40f41c26a4b4af3d7a146c8faf53c30738899d0cbbfacddafef0e75e552f8` |
| Warranty-copy digest (`warranty_copy_sha256`) | `9837f67c9e60f7510d3c5f43a097b41444e58fb8facda72802601d37f88a4785` |
| Reviewed commit (`reviewed_commit`) | The merge commit of the reviewed change that carries these digests (to be filled) |
| Real-card equivalence | `app/e2e/run-real-card.sh` on that commit: card version, card SHA-256 (it must equal the card active on staging), result PASS, date (to be filled) |
| Approval scope | {"environments": ["staging"], "package": "ESSENTIAL", "ux": "v2", "public_intake": false, "purpose": "Protected staging activation behind Cloudflare Access, with V1 kept available. Not public release."} |
| Approval reference | The exact text later passed as `--approval` (to be filled) |
| Approval date | (to be filled by the owner) |
| Owner identity | (to be filled by the owner) |

## What activation checks against this record

- `status` is `APPROVED`, and `owner`, `approved_on`, `approval_reference` and `reviewed_commit` are filled.
- The scope covers the package and the environment, and excludes public intake.
- The digests equal the stored specification, the packaged matrix, the sales record and (in a checkout) the customer and warranty copy. The staging site build also refuses V2 unless the copy digests match.
- Every matrix promise is operationally confirmed with named owners. Every sales decision is APPROVE, named and dated (CHANGE means a new version).
- The active rate card is the card the equivalence passed on.
- `--approval` equals `approval_reference`, and `--release` names the deployed commit.
- The activation event records: release, specification digest, matrix digest, sales and approval versions and digests, the approval reference, the operator, the environment and the time.
