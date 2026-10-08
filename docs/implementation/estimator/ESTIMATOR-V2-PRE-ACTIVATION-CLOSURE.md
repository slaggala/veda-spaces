# Estimator V2: pre-activation closure

**Instruction:** `VEDA-SPACES-ESTIMATOR-V2-PRE-ACTIVATION-CLOSURE`. PR #59 is merged (certified with pre-activation
conditions). **ESSENTIAL-1.1 is not activated, UX V2 is not enabled (`STAGING_ESTIMATOR_UX=v1`), public intake is
disabled, and nothing is deployed to production.**

**Unchanged:** the pricing engine (`engine.py`, `ratecard.py`), the rate card and the estimate mathematics. No
migration. Nothing under `dist/`, `infra/` or `.github/` changed.

**Additive changes:**
- **Public response:** `project_preparation.component_codes` (codes only, no amounts) and `specification.room_promises`.
- **CLI:** the `activation-check` action, and the `--matrix`, `--expect-sha` and `--ux-v1-confirmed` flags.

## F1: room-detail specification filtering

- **Applicability:** a category applies to a room only through the priced lines it names (`applies_to.lines`). There
  is no room-level or product-level fallback. ESSENTIAL-1.0, which has no line applicability, therefore gives no line
  and no categories in any room. The expanded room details use the same applicability as the one-line promise, from
  the estimate's own snapshot and stored lines.
- **Room scope:** ESSENTIAL-1.1 was re-authored so that every category covers every room. The priced lines alone
  decide. This closes the gap where the card prices a light, ceiling or vanity outside its usual room. The new
  document SHA-256 is `6f798ef6cd3cea06f491041a4143e35776900107e73e6c953fbed4bd37ad286d`.
- **V2 behaviour:** V2 treats a specification without room promises as none. It shows no room line, no material
  details, no specification overview and no "Material specification available" marker.
- **Tests:**
  - every priced line of every product, alone in every room the card allows (two sets of 300+ parametrised cases): the categories shown are exactly those carried by that line;
  - soft-close appears only with a soft-close or tandem line;
  - lighting only with a lighting line;
  - no plywood for gypsum, glass, veneer, mirrors, cushions, fittings, wall finishes, pooja units, paint or wiring;
  - a feature-wall-only room shows the decorative final-selection statement only;
  - ESSENTIAL-1.0 never reaches any room (unit test, API integration test and e2e through the page).

## Package-picker wording

"Branded materials and approved hardware, according to the selected rooms and product configuration." This replaces
"Branded plywood, laminate finishes and soft-close hardware". A test refuses "soft-close" in this subtitle. The
matrix row `package_subtitle` is BLOCKED on sales (checklist item 9).

## Scope-aware package content

V2 lists exactly the components the engine priced for the selected scope, from `component_codes`, in the owner's T5
wording. The engine already priced them by scope:
- plywood protection and pest-control preparation only with carpentry;
- freight only with carpentry or ceilings;
- floor protection and debris handling with carpentry, ceilings or finishes;
- cleaning for every scope.

The package value stays visible. The detailed quotation and the staff view keep the per-component breakdown.

**Reconciliation tests:**
- **Integration:** the public `component_codes` equal the staff view's priced components; their amounts sum to the public package amount; and the stored `BudgetEstimateProjectItem` rows equal the priced codes and amounts. Run for a kitchen-and-wardrobe scope and a ceiling-only scope.
- **e2e:** the listed components equal the response's. A ceiling-only home lists no plywood protection and no pest-control preparation.

## Customer-promise matrix: complete

[essential-1.1-promise-matrix.json](specifications/essential-1.1-promise-matrix.json) (schema
`veda.estimator.promise-matrix/2`, [rendered](specifications/essential-1.1-promise-matrix.md)) has 49 rows:
- 14 specification categories;
- the package-level statements;
- 30 page rows, covering every entry of `estimate-v2-copy.js` (39 keys) and the consent line;
- 4 engine and card rows: disclaimer, assumption text, exclusions, client scope.

**Each row records:**
- source of truth, responsible role and accountable owner;
- quotation mapping;
- procurement, receipt, execution and installation checks;
- handover evidence, warranty-document check and warranty source;
- the equivalent rule and the exception process;
- status and what it is blocked on.

**Status today:**
- 12 rows are `OWNER_CONFIRMED` in wording, each where you gave the exact text: the "includes" list, trust markers, "Included in your estimated range", package text, allowance text and examples, service sentence, Luxury, disclaimer, assumption text, exclusions, client scope.
- 37 rows are `BLOCKED`, on sales, operations or owner wording.
- Every row's accountable owner is `UNASSIGNED`. No names were invented.
- So all 49 rows block activation, and nothing is "PROPOSED".

**Completeness is enforced:**
- Every sentence of the V2 script lives in the copy file; a test refuses stray sentences.
- Every promise in the copy file is in the matrix, and every page statement in the matrix is on the page; REMOVED ones must not be.
- Every specification statement is in its category row.
- Every row carries the full chain.

## Warranty status

The separation is unchanged:
- manufacturer-backed protection applies to the exact selected and documented product;
- Veda Spaces workmanship and fitment support lasts one year from handover, subject to the policy.

V2 shows no material duration. Publishing one now requires four sources to agree: the manufacturer certificate,
ESSENTIAL-1.1, the quotation wording and the policy ([WARRANTY-RECONCILIATION.md](WARRANTY-RECONCILIATION.md)).

## Activation guards (implemented)

| Guard | How |
|---|---|
| 1–3, 6: sales, operations, no unconfirmed promise, matrix complete | `promise_matrix.validate` and `blockers`. On staging and production, `activate-spec` refuses ESSENTIAL-1.1 without a structurally complete matrix in which every row is confirmed (or REMOVED) and names its owner |
| 4: F1 filtering | Unit, integration and e2e tests above |
| 5: scope-aware package | Integration and e2e reconciliation |
| 7: owner-approved digest | `activation-check --expect-sha <digest>` refuses any other document |
| 8–9: exactly one active Essential version, and it is ESSENTIAL-1.1 | A unique index (one ACTIVE per package). `activation-check` and `list-specs` report what is active |
| 10: rollback to 1.0 forces V1 | `rollback-spec` and `activate-spec` refuse a specification without room promises unless `--ux-v1-confirmed` is given, after `STAGING_ESTIMATOR_UX=v1` is deployed. V2 also withholds every material promise for such a specification. The API cannot change a Pages variable, so the switch is enforced, not automatic |
| 11: V1 remains available | V1 is unchanged and remains the staging default |

## Validation

| Run | Result |
|---|---|
| API tests (SQLite and PostgreSQL) | see the PR; all pass locally |
| Unit: room applicability (every product line in every room, ESSENTIAL-1.1 and 1.0) | pass |
| Integration: guards, `activation-check`, F1 through the API, package reconciliation | pass |
| Promise-matrix completeness (Python and staging-build) | pass |
| e2e: V1 estimator | 33/33 |
| e2e: V2 estimator (synthetic card) | **50/50** |
| e2e: workspace, access, site, prototype, axe | all pass (26/26 axe screens) |
| Real draft-4 card (`app/e2e/run-real-card.sh`, committed) | **50/50**. The card's SHA-256 is identical to the card active on staging. Amounts are never printed |
| Secret scan and production isolation | clean; no `dist/`, `infra/` or `.github/` change |

**Real-card equivalence.** V1 and V2 were compared on every field of the response:
- the lower and upper range;
- every room subtotal;
- the package (amount, inclusions, components);
- the allowance low and high;
- GST;
- optional items;
- assumptions;
- exclusions and client scope;
- warranty copy;
- the specification snapshot;
- the card version;
- room details.

All are identical.

## Remaining decisions

**Owner:**
- approve the ESSENTIAL-1.1 digest above;
- approve the page wording in every row marked "owner approval of the wording";
- name the accountable owners;
- decide the card question in sales item 6 if sales says TV units lack soft-close.

**Sales:** the 10 items in [ESSENTIAL-1.1-SALES-DECISIONS.md](ESSENTIAL-1.1-SALES-DECISIONS.md).

**Operations:** the sign-off sheet in [ESSENTIAL-1.1-OPERATIONS-CONFIRMATION.md](ESSENTIAL-1.1-OPERATIONS-CONFIRMATION.md).

## Staging activation checklist (later, not in this workstream)

1. Merge this branch after review, then run `12-deploy`.
2. Record the sales, operations and owner decisions in the matrix (and in a new specification version where a decision
   changes the wording or scope), through review.
3. On the host, `activation-check` shows `ready: true`, with the owner-approved digest.
4. `activate-spec --spec ESSENTIAL-1.1 --matrix … --approval …`; then `list-specs` shows only ESSENTIAL-1.1 ACTIVE.
5. Optionally re-run `run-real-card.sh` against the card staging uses, and compare the SHA-256.
6. Set `STAGING_ESTIMATOR_UX=v2` and retry the Pages deployment. V1 stays available as `v1`.
7. Keep `public_intake` disabled and staging behind Cloudflare Access. Production is unchanged.

**Rollback:** runbook §6.8 (V1 first, then `rollback-spec --ux-v1-confirmed`).
