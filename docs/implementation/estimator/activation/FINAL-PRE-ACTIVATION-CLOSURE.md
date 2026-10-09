# Estimator V2: final pre-activation closure

**Instruction:** `VEDA-SPACES-ESTIMATOR-V2-FINAL-PRE-ACTIVATION-CLOSURE`.

**Current state:**
- ESSENTIAL-1.1 is not activated, and V2 is not enabled (`STAGING_ESTIMATOR_UX=v1`).
- Public intake is disabled, and nothing is deployed to production.
- The pricing engine, rate card and estimate mathematics are unchanged, and there is no migration.

## M1: activation uses only the reviewed, repository-controlled records

- **Packaged records only.** The promise matrix, the sales decisions and the owner approval record live in
  `api/veda/modules/estimator/approved/`. The API image is built from the reviewed commit (`COPY . .`), so each release
  carries the records of its commit.
- **No other source.** `activate-spec`, `rollback-spec` and `activation-check` refuse `--matrix` ("an externally
  supplied matrix is not accepted").
- **Checkout integrity.** In a checkout, each record must be tracked and unmodified against `HEAD`, and inside the
  approved folder. Untracked, modified or outside files are refused (`activation.repository_blockers`).
- **Digests.** The approval record's digests must equal the release's records. A mismatch or a missing digest is
  refused as stale.
- **What each activation and reactivation records** (in the `SPEC_ACTIVATED` or `SPEC_ROLLED_BACK` event): the release
  commit (`--release`, required on staging and production; the checkout `HEAD` locally), the specification digest,
  the matrix digest, the operations-confirmation version, the sales-decision version and digest, the approval-record
  version and digest, the approval reference, the operator, the environment and the timestamp.
- **Tests:**
  - positive: an approved, current set activates and records every field;
  - negative and mutation (13 cases): a re-opened matrix row, an undecided sales item, a CHANGE decision, PENDING, no owner, stale specification, copy or warranty digests, out-of-scope environment, public intake in scope, a different card, no equivalence, a mismatched approval reference;
  - the committed PENDING records refuse;
  - the repository check with a real temporary git repository (tracked, untracked, modified, outside).

## M2: every activation and reactivation reruns the whole gate

- `activate_spec` and `rollback_spec` both go through `_gate_or_refuse`. No earlier activation counts as standing
  approval.
- **The gate verifies:**
  - the approved specification digest and the promise-matrix digest;
  - every sales decision APPROVE, named and dated;
  - every promise operationally confirmed, with named owners;
  - the promise statuses;
  - the customer and warranty copy digests (in a checkout; the staging build checks them too);
  - a passing real-card equivalence on the currently active card;
  - the environment and scope (staging, Essential, no public intake);
  - for a specification without room promises, `--ux-v1-confirmed`.
- **Fails closed** on any stale or missing approval or digest.
- **Tests:** `test_reactivation_after_rollback_to_v1_reruns_the_whole_gate` (approve, activate 1.1, roll back to 1.0
  under V1, reactivate 1.1, then refuse after a matrix row is re-opened, and refuse after the card changes) and
  `test_rollback_revalidates_and_refuses_a_tampered_specification`.

## M3: only registered customer text reaches V2

- **Inventory:** [CUSTOMER-TEXT-INVENTORY.md](CUSTOMER-TEXT-INVENTORY.md) lists every text source and its control.
- **Runtime:** the public view adds `v2_copy`, the disclaimer, exclusions, client scope and per-room assumptions that the
  packaged matrix of the estimate's own specification registers (exact statements or `{field}` templates).
  Unregistered text is suppressed. V2 renders runtime text only from `v2_copy`, and shows material promises only when
  `v2_copy.approved` and `room_promises` are both true. V1's response is unchanged.
- **Customer copy:** every V2 string now lives in `estimate-v2-copy.js` (JSON). Every `promise` entry must be in the
  matrix. The staging site build refuses `STAGING_ESTIMATOR_UX=v2` unless the owner approval record is APPROVED and
  carries this copy's digests.
- **Tests:**
  - unit suppression;
  - integration (an unregistered card exclusion is dropped; no matrix means nothing approved);
  - e2e (raw response fields tampered with in flight never reach the page; an unapproved block shows only approved fallbacks);
  - a staging-build test that refuses any V2 code reading unregistered API fields.
- **Found while doing this:** count assumptions ("drawers assumed 4 …") carry no unit and were being suppressed. Their
  template is now registered.

## Low findings

| Finding | Resolution |
|---|---|
| L1: the "no amounts in the matrix" guard was dropped | `promise_matrix.validate` refuses ₹, Rs, INR, rupee, lakh, `rate_minor`, `amount_minor`, "per sheet" and "per sq" anywhere in the matrix (tests) |
| L2: `activation-check` said "ready" for ESSENTIAL-1.0 | It now reports "no room promises: UX V2 must not run on it…", reports "already active", and exits 3 (test) |
| L3: stray customer strings in the V2 script | All moved into the copy file. The staging-build test refuses any multi-word literal left in the script |
| L4: page-row verification ran only in the Node test | The copy file is JSON, so `test_promise_matrix.py` (API CI job) runs the same both-way page checks |
| L5: rollback skipped validation, and integrity refusal was untested | Rollback re-checks the SHA-256 and revalidates the document (tests for both) |

## Records awaiting people

- **Sales:** [ESSENTIAL-1.1-SALES-DECISION-SHEET.md](ESSENTIAL-1.1-SALES-DECISION-SHEET.md). Ten items with every field
  you asked for; the owner decision, name and date are empty.
- **Operations:** [ESSENTIAL-1.1-OPERATIONS-OWNER-SHEET.md](ESSENTIAL-1.1-OPERATIONS-OWNER-SHEET.md). All 54 visible
  promises need an accountable person, a backup and the seven checks. All are BLOCKED and UNASSIGNED.
- **Owner:** [ESSENTIAL-1.1-OWNER-APPROVAL-RECORD.md](ESSENTIAL-1.1-OWNER-APPROVAL-RECORD.md). PENDING, with the full
  specification and matrix digests.
- **Round 1:** [ROUND-1-RUN-SHEET.md](../validation/ROUND-1-RUN-SHEET.md). ROUND 1 READY TO RUN; no session held.
