# MTQ B2–B4 implementation record

**Branch:** `feature/mtq-b2-b3-b4-commercial-engine` · **Umbrella PR:** see the pull request of that branch · **Instruction:** `VEDA-SPACES-MTQ-B2-B3-B4-END-TO-END-COMMERCIAL-ENGINE` (2026-10-13).
**Source of truth:** main after PR #90 (B1 enabled in protected staging): the blueprint, the survey and scope templates (PR #84 package), the B1 scope freeze and blocker closure, the owner-decision register, decision log 26–30, Catalogue V3 and the estimator (ADR-012/013).
**Status of every result here:** SYNTHETIC_VALIDATED. No live site, real rate or owner decision was used; the B1 field-validation evidence (real sites) does not exist yet.

This record states what was built for B2 (scope and BOQ), B3 (internal estimate) and B4 (quotation), where the code departs from the letter of a design document and why, and exactly which owner decisions it waits for. Nothing here records or assumes an owner decision.

## 1. The one rule the whole build follows

The owner-decision register on main has OI-MTQ-03 to OI-MTQ-17 **blank**. The instruction says not to invent a business value to make anything work. So the engine is complete and every undecided value has a defined, visible effect instead of a default:

| Register row | Governs | Effect while blank (as committed) |
|---|---|---|
| OI-MTQ-03 / 04 | Scope rules; quantity derivations, rounding, wastage, clearances | The ruleset ships as PROPOSED (`fixtures/scope-rules-2026.10.3.json`); every recommendation needs a staff decision; quotations built on it are not customer-issuable (`RULESET_NOT_APPROVED`). No clearance, wastage or corner deduction is applied; rounding is the estimator's own (0.01, half up). |
| OI-MTQ-05 | Premium/Luxury staff rates; finish-variant rates; NEW LINE items | PREMIUM and LUXURY estimates refused (`RATE_CARD_NOT_APPROVED`); a finish variant without a rate stays unpriced (`FINISH_RATE_NOT_APPROVED`); items with no card line stay unpriced (`CATALOGUE_MAPPING_MISSING`) |
| OI-MTQ-06 | Discount authority | Every discount action refused (`OWNER_DECISION_REQUIRED`) |
| OI-MTQ-07 | GST treatment | No tax computed; no final total; not customer-issuable (`GST_POLICY_REQUIRED`) |
| OI-MTQ-08 | Validity, reminders, expiry | Not customer-issuable. Expiry is the maintenance job `veda maintenance mtq-quotation-expiry`; it is **not scheduled**, so nothing expires automatically (recording a decision on a version past its validity expires it instead). Scheduling it is a pre-customer-issuance operational requirement. |
| OI-MTQ-09 | Terms, payment milestones, warranty, assumptions, exclusions, change-order and cancellation terms | Not customer-issuable; the document shows only facts from the scope (declined items, assumed dimensions) |
| OI-MTQ-10 | Unit rates shown to customers | Never shown |
| OI-MTQ-11 | Acceptance mechanism | Not customer-issuable; a decision cannot be recorded |
| OI-MTQ-13 | Variation policy | Variations can be drafted and reviewed, not issued |
| OI-MTQ-14 | Provisional sums | Not implemented (no allowance section) |
| OI-MTQ-15 | Preparation-package drivers (5 BHK, independent house) | Those charges stay unpriced (`OWNER_DECISION_REQUIRED`); not customer-issuable |
| OI-MTQ-16 | Design-stage linkage | Not modelled beyond the general rule: any change is a new scope revision |
| OI-MTQ-17 | Commercial go/no-go | Commercial properties stay out (B1 vocabularies refuse them) |

These slots live in one versioned record, `veda/modules/mtq_commercial/fixtures/commercial-policy.json` (all null, status `OWNER_DECISIONS_PENDING`). A decision is recorded by a reviewed pull request that fills its slot from the register row and changes the version; the shapes are validated strictly (`policy.py`). Tests install a policy marked `SYNTHETIC_TEST_ONLY` to exercise the decided paths; the loader refuses that marker outside the test environment, so no synthetic value can reach staging or production.

## 2. What was built

### B2 — scope and BOQ (`0201_mtq_estimation`, part one)

| Area | Implementation |
|---|---|
| Requirements | `requirement`: necessity MANDATORY / RECOMMENDED / OPTIONAL; status PROPOSED / ACCEPTED / EXCLUDED / NOT_APPLICABLE; source SURVEY_TEMPLATE / MEASUREMENT_RULE / STAFF_SELECTION / CUSTOMER_REQUEST / MANUAL; provenance (rule, measured fact, ruleset version and digest, measurement revision, template). The instruction's six classifications are read from these three fields (`classification`). Duplicate keys refused. |
| Recommendation | Seeding evaluates 31 rules against the current verified set: by space type (template recommendation, origin RECOMMENDED) or by measured fact (tagged wall, captured electrical point, proposed partition, window; origin AUTO). Everything is PROPOSED; staff accept, exclude (reason needed for a mandatory one), mark not applicable, or add (accepted by the act). A seed never touches a decided requirement. |
| Scope revisions | `scope`, `scope_item`: built from ACCEPTED requirements over the current verified set; staff edits (options, finish, inclusion, dimension overrides with a reason) carry to the next revision (`carried_from_item_id`), except that a dimension override made on a superseded measurement set is held in `carried_overrides`, not applied, until staff confirm, replace or drop it. Each revision pins the digest of the property's requirement decisions (`requirements_sha256`); any later decision (accept, exclude, re-decide, add, preferences) makes it stale. Confirm needs every recommendation decided, the decisions unchanged, no pending carried override and the measurements still current; it seals a canonical digest and supersedes the previous confirmed revision. |
| Quantity engine | `quantity.py` (`QUANTITY_ENGINE_VERSION` 2026.10.3). Each rate-card input of an item's product (WIDTH, HEIGHT, RUN, AREA, DRAWERS…) is derived from the verified set with its source, a sentence, and the measurement rows read. Line quantities are the **rate card's own quantity bases** evaluated exactly from millimetres and rounded once. A window seat spans its window; a kitchen counter run (base units, base shutters) continues beneath windows and is cut only by doors and other floor-level openings, while the wall-unit run (wall units, lofts and their shutters; the utility unit) loses every opening whose sill is below the lintel, and is UNRESOLVED and blocking, never the counter run, when an opening has no sill or offset, openings overlap or the lintel and ceiling heights are both missing (quantity roles: `line_inputs`); a wall the openings take entirely has no usable stretch (0, never its full length); a pooja shutter is the pooja room's own door frame, and a staff entry for a niche unit; counts are whole numbers; sensor provisions count only NEW sensor lights with a sensor type and sensor switching. Parity with the estimator engine is a test (`tests/unit/test_mtq_estimator_parity.py`). |
| BOQ | `boq`, `boq_line`: one line per applicable card line (the card's own option conditions) per included or optional item; room-wise and project views; calculated vs final quantity, override with reason and actor; issues per line and per BOQ; review seals and supersedes the property's previously reviewed BOQ (one reviewed BOQ per property, database index); regeneration supersedes; diff between revisions. Items without a card line are kept (UNMAPPED or MEASURED_COUNT) and reported. No line is dropped for a zero or missing quantity: every line carries `quantity_status` VALID, VALID_ZERO, UNRESOLVED or INVALID. Excluded and not-applicable requirements are not lines: they are recorded on the scope and listed in the BOQ summary. |
| Validation | Blocking: missing measurement, missing final quantity, impossible quantity (card bounds, including a zero length or area), fractional count, quantity-kind mismatch between the ruleset and the card, missing quantity rule, unsupported unit, invalid option, unresolved source points, a mandatory requirement quoted as optional, an **included** item with no catalogue line, stale scope or measurements (requirements, measurement revision, catalogue), unverified measurement, Lite survey (B1-02), unexplained override. Warning: an optional item with no catalogue line, assumed dimension, duplicate scope, proposed ruleset. |

### B3 — internal estimate (`0201_mtq_estimation`, part two)

| Area | Implementation |
|---|---|
| Pricing | `cost_estimate`, `cost_estimate_line`: priced from the estimator's ACTIVE rate card (pinned by id, version and document digest), which must be exactly the card the BOQ was built against (`PRICING_CONTEXT_MISMATCH`; a BOQ is stale once another card is active, `CATALOGUE_CHANGED`) with the engine's own amount rule (`engine.line_amount_minor`, extracted additively — the budget estimator's results are unchanged). Provenance per line: BOQ line → card product and line → card version → tier → rate → amount → measurement source. |
| Tiers | ESSENTIAL approved by the card's own owner-approved activation. PREMIUM/LUXURY need the card to enable them **and** OI-MTQ-05. |
| Finishes and materials | Catalogue-backed option changes (door type, panelling finish, pooja door…) change the BOQ lines through the card's own conditions and are priced. A finish variant (laminate / acrylic / veneer / PU…) needs an approved finish rate (OI-MTQ-05). |
| Charges | The card's Project Preparation & Protection components are priced by the property's **derived** bedroom count (1–4 BHK keys); site and floor protection → SITE_PROTECTION, freight → TRANSPORT, debris/cleaning/pest → OTHER_SERVICE. 5 BHK and independent houses wait for OI-MTQ-15. Point shifting and sensor provisions are ELECTRICAL_SHIFTING lines without a card line yet. Labour and installation are inside the card's supply-and-install rates: nothing separate is charged. The Custom Features Allowance (ADR-012 D9) is not carried: a measured quotation replaces it with the actual items. |
| Versions | One draft and one approved estimate per property; approval seals; `compare` (quantity, rate, finish/tier, discount, pricing status); `reproduce` recomputes every amount from the pinned card document. |
| Blockers | DATA (rate missing, quantity missing, pending discount) block approval; OWNER_DECISION ones (tier, finish, mapping, preparation driver, GST, ruleset) stay visible and block only customer issuance. Stale lineage (measurement, scope, BOQ, rate card) blocks approval. |
| Discounts | `cost_estimate_adjustment`: line / category / project, percent or amount; pre, discount, post, reason, actor, authority, approval, policy version; allocated pro rata beside the lines, never changing a rate. Disabled until OI-MTQ-06. |
| GST | Per-line taxable value, rate, tax and total, only from a recorded OI-MTQ-07 (`tax.py`). |

### B4 — quotation (`0202_mtq_commercial`)

| Area | Implementation |
|---|---|
| Model | `quotation` (version, kind BASE/VARIATION, variation number, accepted baseline, full lineage with the estimate's digest, terms snapshot, totals, validity, frozen document and digest, decision), `quotation_section`, `quotation_line`, `quotation_event`. Number from the platform sequence `QUOTATION` (`VS-Q-YYYY-NNNNNN`) under the sequence row lock. |
| Lifecycle | DRAFT → INTERNAL_REVIEW → APPROVED → ISSUED → ACCEPTED / REJECTED / EXPIRED, SUPERSEDED by a newer version; only a draft changes; one open version per number and variation (database index); an issued version is frozen (CHECK). Issue requires customer-issuability; it syncs the lead as SYSTEM (activity, forward move to QUOTATION_SENT, quoted amount). Decisions record method, optional items chosen, accepted total, and freeze the **effective accepted baseline** (included lines plus the chosen optional items, with its digest). Every quotation and variation version is built only from an estimate whose BOQ, scope and measurement set belong to the quotation's property (`LINEAGE_MISMATCH`). |
| Customer document | `rendering.py`: an allow-list model and an escaped, self-contained HTML page. At issue the model (with the customer's name as issued) and its HTML from the template version in force are frozen, each with its digest, and the template version pinned; an issued version is served only from those bytes, never re-rendered with a later template, and refused (`SNAPSHOT_INTEGRITY_FAILED`) if either digest fails. Drafts render live with a staff-only "not a customer document" note. |
| Variations | `variations.py`: change orders against the frozen effective accepted baseline (an optional item the customer chose is part of it: kept, it shows no change; changed, a quantity change; removed, an omission) with ADD / OMIT / CHANGE_QUANTITY / CHANGE_FINISH / CHANGE_RATE / CHANGE_MATERIAL lines and the net impact; the base stays ACCEPTED and byte-identical; accepted value of the job = base + accepted variations. |
| Trace | `GET /quotation-lines/{id}/trace` (permission `quotation.lineage.read`, not held by SALES): quotation line → estimate line → BOQ line → scope item → requirement → space → measurement set, revision, space measurement and wall; rate-card version, digest and pricing provenance only with `cost_estimate.rate.view`. |

### Cross-cutting

| Area | Implementation |
|---|---|
| Flags | `VEDA_MTQ_ESTIMATION_ENABLED` (B2/B3) and `VEDA_MTQ_QUOTATION_ENABLED` (B4), the blueprint's names; off by default; production refuses both; estimation needs the B1 flag and quotation needs estimation in every environment. Wired to staging-core false by default (decision log 33, §8): turning them on needs the owner-APPROVED, digest-bound `infra/config/mtq-commercial-enablement-record.json`. Every commercial path answers 404 while off (the B1 MC-3 gate). `/auth/me` reports both. |
| RBAC | Roles ESTIMATOR and SALES_MANAGER (MFA). New codes `scope.*`, `boq.*`, `cost_estimate.*`, `quotation.*`; the new roles also get the B1 read codes and the workspace self-service rows; SALES_MANAGER gets `lead.read` (ALL). No grant of an existing role to an existing code changed. `0201` stops, changing nothing, if a custom role already uses the code or name of ESTIMATOR or SALES_MANAGER (`refuse_role_collisions`). |
| Audit and erasure | Every new table FULL with its aggregate parent. Lead erasure replaces every free-text field that may describe the customer (notes, decision and override reasons, carried override reasons, quotation title, cover note, decision note, reasons in lifecycle events) and redacts the frozen document's customer name, subject and cover note, re-sealing it with a SNAPSHOT_REDACTED event that keeps the previous digests. Retained as the commercial record: quantities, derivations, measurement references, rates, amounts, tax, decisions and methods, statuses, dates, actor ids, digests, quotation number, property reference, configuration and city, terms. |
| UI | `/site/properties/:id/commercial`: overview (lineage, stale, undecided owner decisions), scope, BOQ, estimate and quotation tabs, each room by room. |

## 3. Deviations from the design documents

| Document says | Implementation | Reason |
|---|---|---|
| Scope rules and quantity formulas as Catalogue V3 records `scope_rule`, `quantity_formula` (blueprint §8; B1-06 "migrated to records in B2") | A versioned, digest-pinned code fixture, like B1-06 | Catalogue V3 administration is off and its governance incomplete; widening `catalog_record.kind` would change a governed system for content the owner has not approved. The fixture is the record's content; moving it into the catalogue is mechanical once both are approved. |
| Separate `quantity_formula` per (product, line) | The card's own quantity specs; the ruleset only derives the card's inputs from measurements | One source of quantity bases (the approved card), no duplicated formulas, no second pricing engine |
| `estimator_rate_item_finish` table, `permission_limit` table (blueprint §9.2, §15.2) | Not created; finish rates and discount limits are policy slots | Their content is undecided (OI-MTQ-05, OI-MTQ-06); no structure is frozen around values nobody has approved |
| Sensitive [COMMERCIAL] permission class (blueprint §15.2) | No sensitivity class; SALES_MANAGER requires MFA at role level | The `permission.sensitivity_class` CHECK admits only the platform's four classes |
| `quotation_term`, `quotation_exclusion`, `quotation_decision` tables (blueprint §4.3) | Terms snapshot and decision columns on `quotation` | The content is undecided (OI-MTQ-08…11) |
| Quotation status SENT, VIEWED, WITHDRAWN (blueprint §4.3) | ISSUED; no VIEWED (no portal); no WITHDRAWN | The instruction's lifecycle; the portal is out of scope; withdrawal has no decision |
| `cost_estimate` REVIEWED state, ranges for MIXED bases (blueprint §4.2, §9.4) | DRAFT → APPROVED; basis MEASURED/MIXED shown, no range | The range bands are the public estimator's; a quotation has a single number with assumptions disclosed |
| Knowledge tables (`0203_mtq_knowledge`) | Not created; `0203` stays reserved | Out of this instruction's scope (knowledge / AI) |
| Outbox events (`scope.confirmed`, `quotation.sent`…) | Not emitted | Each event type needs a subscriber; none exists yet. Lifecycle facts are in `quotation_event` and the audit log |

## 4. Validation scenarios (SYNTHETIC_VALIDATED)

| # | Scenario | Test |
|---|---|---|
| 1 | Standard apartment | `test_mtq_end_to_end.py` (2/3/4/5 BHK, independent house; as committed and with SYNTHETIC decisions) |
| 2 | Custom scope addition | `test_mtq_scope_boq.py::test_staff_additions_customer_requests_and_duplicates`; variations add a customer-requested TV unit |
| 3 | Optional item | `test_mtq_quotation.py::test_issue_freeze_accept_with_optional_items` |
| 4 | Quantity override | `test_mtq_scope_boq.py::test_missing_measurement_blocks_review_until_overridden_with_a_reason` |
| 5 | Material change | `test_mtq_scope_boq.py::test_material_change_and_invalid_option_and_impossible_quantity`; `test_mtq_commercial_controls.py::test_finish_variant_without_an_approved_rate_is_unpriced`; variation CHANGE_MATERIAL |
| 6 | Discount approval | `test_mtq_commercial_controls.py::test_discounts_disabled_until_decided_then_authority_and_four_eyes` |
| 7 | Missing rate card | `test_unapproved_tiers_are_refused_never_invented`, `test_no_active_rate_card_prices_nothing` |
| 8 | Stale measurement revision | `test_mtq_scope_boq.py::test_new_measurement_revision_makes_downstream_stale` |
| 9 | Quotation revision | `test_mtq_quotation.py::test_revision_supersedes_and_history_stays_stable_after_a_rate_change` |
| 10 | Accepted quotation + change order | `test_mtq_variations.py` |
| 11 | GST-blocked issuance | `test_mtq_quotation.py::test_drafted_but_never_issued_while_owner_decisions_are_missing` |
| 12 | Missing catalogue mapping | `test_mtq_scope_boq.py::test_unmapped_items_stay_in_the_boq_and_are_reported` |
| 13 | Concurrent quotation numbering | `test_mtq_quotation.py::test_concurrent_quotation_numbers_are_unique` (both engines) |
| 14 | Historical quotation stable after a rate change | `test_mtq_quotation.py::test_revision_supersedes_…`, `test_mtq_estimate_versions.py::test_rate_card_change_never_moves_a_stored_estimate` |

Per-configuration evidence after the certification remediation: [evidence/b2-b4-synthetic-2026-10-14.json](evidence/b2-b4-synthetic-2026-10-14.json) (subtotals unchanged from the reviewed head; one more estimate line per configuration, a zero-quantity line the BOQ now keeps instead of dropping). The reviewed head's run is kept as [evidence/b2-b4-synthetic-2026-10-13.json](evidence/b2-b4-synthetic-2026-10-13.json). Replay against historical quotations (MTQ-G5) is not done: the replay quotation list is still the owner's private data, and only 3 BHK has references.

## 5. What stops a customer quotation today

1. Owner decisions OI-MTQ-03, 04, 07, 08, 09, 11 (all quotations); OI-MTQ-15 (5 BHK and independent houses); OI-MTQ-13 (variations); OI-MTQ-05 (Premium/Luxury, finish variants, items without a card line).
2. Items the rate card has no line for (tall unit, mirror panel, pelmet, point shifting, sensor provisions, custom items) cannot be priced; when included they block BOQ review (`UNRESOLVED_CATALOGUE_MAPPING`), as optional items they stay unpriced and disclosed.
3. Staging: the two flags are wired false (decision log 33); turning them on needs the owner-APPROVED enablement record (§8), as B1 did (decision log 30). Staging enablement is internal validation only: customer issuance stays blocked by the undecided policies above.
4. Field validation: B1's ten-site validation and the MTQ-G5 replay are outstanding; nothing here is validated against a real site or a real quotation.
5. Operations: the quotation expiry job (`veda maintenance mtq-quotation-expiry`) must be scheduled before any customer issuance.

## 6. Certification remediation (independent review of PR #91 at 851809e: NOT CERTIFIED)

The architecture was found sound; the review confirmed implementation defects, each reproduced by a probe. Every probe was re-run against the remediated code and now shows the corrected behaviour. Nothing below records an owner decision.

| Finding | Fix | Tests |
|---|---|---|
| MB-1 A variation version accepted another property's estimate | `quotations.require_lineage`: the quotation (and a variation's base and baseline), the estimate, its BOQ, the BOQ's scope and the measurement set must all belong to the quotation's property; checked before anything is created, on every create and version path (422 `LINEAGE_MISMATCH`). BOQ generation and estimate creation check their own lineage the same way. | `test_mtq_lineage_integrity.py`: property A + estimate B refused, A + A allowed, variation and variation version from another property refused, manipulated BOQ and scope lineage refused, nothing partially created |
| MB-2 An estimate could be priced on a newer card than its BOQ's, silently losing the lines it added | Exact consistency: an estimate is priced only with the card (row and document digest) the BOQ was built against (`PRICING_CONTEXT_MISMATCH`); a BOQ is stale once another card is active (`CATALOGUE_CHANGED`), so it can be neither reviewed nor priced; regenerate the BOQ. Stored estimates are never re-priced; `reproduce` still proves them. | `test_an_estimate_is_priced_only_with_its_boqs_card`; `test_rate_card_change_never_moves_a_stored_estimate` |
| MB-3 Requirement decisions after scope confirmation did not stale scope/BOQ; an excluded wardrobe stayed reviewable | Scope revisions pin `requirements_sha256` (the property's requirement decisions); any later decision, addition or preference change makes the scope stale (`REQUIREMENTS_CHANGED`), hence its BOQs, estimates and quotations (no BOQ, no estimate, no issue). Reviewing a BOQ supersedes the previously reviewed one (one per property). | `test_requirement_decision_after_confirm_stales_everything_downstream`, `test_additions_and_preference_changes_stale_the_scope` |
| MB-4A Window seat measured beside the window | `window_span`: the span across the window openings of the tagged wall (3000 mm wall, 1500 mm window → 1500 mm); no window → a staff entry, never the wall | `test_mtq_quantity_matrix.py` |
| MB-4B Kitchen base runs lost every window's width | The counter run is cut only by doors and other floor-level openings (`deduct: floor_openings`); windows, ventilators and AC sleeves are kept unless B1 recorded them at floor level (sill 0); no clearance invented (OI-MTQ-04) (3000 + 2400 mm with a 1200 mm window → 5400 mm) | matrix: with window, without, with a door, floor-level window |
| MB-4C A fully opened wall fell back to its full length (ASSUMED) | A wall the openings take entirely has 0 mm usable stretch; the line is kept, INVALID, blocking (`IMPOSSIBLE_QUANTITY`). An opening with no offset (stretch unknown) remains the documented ASSUMED fallback. | matrix |
| MB-4D The pooja shutter took the room's entrance door | `door_width` applies only to a POOJA space (its own door frame, exactly one door); a niche unit's shutter is a staff entry | matrix |
| MB-4E A count override accepted 2.5 drawers | Count inputs must be whole numbers, as in the estimator: refused at entry (422 `NOT_WHOLE`), on a count line override, and blocking in the BOQ (`INVALID_COUNT`) | matrix; `test_a_fractional_count_entry_is_refused`; parity |
| MB-4F A wrong-kind card input passed review with no quantity | `QUANTITY_KIND_MISMATCH` (blocking, not cleared by an override); a line without a final quantity is blocking (`MISSING_QUANTITY`) | matrix; parity |
| MB-4G Sensor points counted on too little information | Sensor provisions count only NEW sensor lights with a sensor (PIR, MICROWAVE) and sensor switching (SENSOR, BOTH); others are unresolved and blocking (`UNRESOLVED_SOURCE_POINTS`); a shifted sensor light is point shifting | matrix |
| MB-5 A BOQ could be reviewed with an invalid or missing quantity | `quantity_status` on every line; the blocking set above; an included item without a catalogue line is blocking (`UNRESOLVED_CATALOGUE_MAPPING`); a mandatory requirement quoted as optional is blocking; zero lines are kept and classified | `test_only_one_reviewed_boq_and_count_quantities_are_whole`, `test_an_included_item_without_a_catalogue_line_blocks_review` |
| MB-6 Optional items chosen at acceptance were ADDed again by a variation | At ACCEPTED the effective accepted baseline (included lines plus the chosen optional items) is frozen with its digest (`accepted_baseline`); variations diff against it; an item chosen and still offered as optional is retained | `test_optional_item_chosen_at_acceptance_is_part_of_the_baseline`: kept → no line, quantity change → CHANGE_QUANTITY only, removal → OMIT only |
| MC-1 No parity test between MTQ quantities and the estimator | `tests/unit/test_mtq_estimator_parity.py`: identical quantities and amounts for area (height input and card height), direct, direct × factor, count input, count constant and lump lines; half-up rounding once; whole-number counts; bounds; incompatible kinds. Documented, tested differences: the budget substitutes a typical value for a missing input (the BOQ never does), drops zero lines (the BOQ keeps them), and receives feet (MTQ derives feet from millimetres exactly). | parity |
| MC-2 Staff dimension overrides carried silently across a re-measure | Overrides made on a superseded measurement set are held in `carried_overrides`, not applied; confirm is refused (`OVERRIDES_NEED_RECONFIRMATION`) until staff confirm, replace or drop each (the UI offers Confirm / Drop); history keeps the original override | `test_new_measurement_revision_makes_downstream_stale` |
| MC-3 Expiry documentation named the wrong command | The command is `veda maintenance mtq-quotation-expiry`; it is not scheduled; scheduling is a pre-customer-issuance operational requirement (§5) | — |
| A Lead erasure left the cover note and title in the frozen document and the return reason in event detail | See "Audit and erasure" in §2: titles, cover notes and event reasons erased; the frozen document redacted and re-sealed (SNAPSHOT_REDACTED, previous digests kept) | `test_lead_erasure_redacts_the_frozen_document_and_events` |
| B Issued HTML was re-rendered with the current template; a tampered snapshot still rendered | Issued HTML frozen with a pinned template version; served only from the frozen bytes; any digest mismatch refuses to render (`SNAPSHOT_INTEGRITY_FAILED`); the customer's name comes from the issuance snapshot | `test_issued_document_survives_a_template_change`, `test_a_tampered_document_is_refused` |
| C The line trace exposed the rate-card version to roles that cannot see rates | New permission `quotation.lineage.read` (not SALES) for the trace; pricing provenance only with `cost_estimate.rate.view` | `test_lineage_trace_needs_its_own_permission` |
| D A custom ESTIMATOR / SALES_MANAGER role would be taken over by the seed | `0201` refuses, before any change, a live custom role with either code or name (main's own role test created a custom SALES_MANAGER) | `test_mtq_role_collision.py` (both engines) |

Schema changes stay inside the unreleased `0201` / `0202` (not applied anywhere): `scope.requirements_sha256`, `scope_item.carried_overrides`, `boq_line.quantity_status`, the one-reviewed-BOQ index, `quotation.template_version` / `issued_html` / `issued_html_sha256` / `accepted_baseline` / `accepted_baseline_sha256`, event `SNAPSHOT_REDACTED`, permission `quotation.lineage.read`. The ruleset and the quantity engine move to 2026.10.2 (content change; still PROPOSED).

## 7. Final merge condition: kitchen wall units (focused re-review of d4b7066)

The focused re-review (B2-B4 CERTIFIED WITH REMAINING MERGE CONDITIONS) found one defect introduced by MB-4B: the card's single kitchen RUN was the counter run for every kitchen line, so wall units and their soft-close shutters ran across windows (reviewer fixture: 3000 mm wall with a 1200 mm window plus a 2400 mm wall gave WALL 35.43 sq ft).

| Area | Result |
|---|---|
| Design | Quantity roles. The ruleset (2026.10.3, still PROPOSED) derives `RUN` (the counter run) and `WALL_UNIT_RUN` for a kitchen and maps card lines to roles: BASE and SOFT_CLOSE use `RUN`; WALL, SOFT_CLOSE_WALL, LOFT and SOFT_CLOSE_LOFT use `WALL_UNIT_RUN` (the proposal's loft run is the wall-unit run, 04 KITCHEN_LOFT_FROM_CLEARANCE). The card, its quantity bases and the pricing engine are unchanged; each line is evaluated on its role's value under the card's input name (`quantity.for_line`). Each derived value carries role, source, wall and opening ids, millimetres and the rounded value, unit, rule kind, ruleset version and status; the BOQ line's inputs carry the role. The utility unit's only measured line is a wall unit, so its WIDTH is a wall-unit run. The tall unit is still unmapped (unchanged, no rate). |
| Base units | Unchanged: the reviewed fixture's counter run stays 5400 mm (BASE 53.15 sq ft). |
| Wall units | Σ over tagged walls of the wall length less every opening whose sill is below the lintel (else the ceiling); an opening wholly above it (e.g. a high ventilator) is not deducted. Doors, French windows and arches start at the floor. No wall-unit band, chimney span or clearance is assumed (OI-MTQ-04). Reviewer fixture: 4200 mm → WALL and SOFT_CLOSE_WALL 27.56 sq ft (LOFT likewise). |
| Unresolved geometry | A window without a sill or offset, overlapping openings, an opening outside its wall, or no lintel and no ceiling height: `WALL_UNIT_RUN` MISSING with the reason, the wall-unit lines UNRESOLVED and blocking (`MISSING_MEASUREMENT`), never the counter run. A staff entry for `WALL_UNIT_RUN` (with a reason) resolves it; an entry for the counter run never does. A wall the openings take entirely is 0, INVALID and blocking. |
| Parity | Base lines agree with an estimator run on the counter run, wall-unit and loft lines with an estimator run on the wall-unit run; the estimator's single RUN is a documented difference. |
| Erasure integrity (low residual) | Redaction re-seals only a verified document. A document already failing its digests is still redacted, its HTML withdrawn and its original digests kept, so it stays SNAPSHOT_INTEGRITY_FAILED; the SNAPSHOT_REDACTED event records INTEGRITY_FAILED_BEFORE_REDACTION. |
| Tests | `tests/unit/test_mtq_kitchen_roles.py` (matrix A-J and the reviewer fixture), `test_mtq_estimator_parity.py::test_kitchen_roles_agree_line_by_line_with_the_estimator`, `test_mtq_quotation_integrity.py::test_erasure_never_reseals_a_tampered_document`. The SYNTHETIC end-to-end evidence is unchanged (no synthetic kitchen has a window on a counter wall). |

## 8. Protected-staging enablement (decision log 33)

**Status: wired, both flags false; the enablement record is a DRAFT.**

| Layer | Refuses |
|---|---|
| staging-core (`output "mtq_commercial"`) | quotation without estimation; estimation without the B1 site flag; estimation unless `infra/config/mtq-commercial-enablement-record.json` is APPROVED by someone other than its author, dated, staging-only, `scope.internal_protected_staging_validation_only` true and `scope.customer_issuance` false, with every evidence field filled (run ids numeric) and `mtq_commercial.enablement_record_sha256` equal to the file's SHA-256; a digest without the flag |
| API start (`veda/config.py`) | the same flag dependencies in every environment; either flag in production |
| Routes | every commercial path answers 404, before authentication, while its flag is off |
| Policy record | customer issuance while any required OI-MTQ slot is null (unchanged by enablement) |

**Owner sequence:**

1. Read-only role check on the staging database: no custom role uses the code or name ESTIMATOR or SALES_MANAGER (otherwise `0201` stops the deploy, changing nothing).
2. `12-deploy` of main with the flags absent (false): migrations `0201_mtq_estimation`, `0202_mtq_commercial` run (head `0202_mtq_commercial`); readiness reports migrations head.
3. Access checks with the flags off: `/auth/me` reports both false; commercial API paths answer 404; Site visits, V1, V2, Catalogue and the budget estimator unchanged.
4. Merge the wiring change; `10-infra-plan` by dispatch on main: exactly **2 to add, 0 to change, 0 to destroy** (`/veda/staging/VEDA_MTQ_ESTIMATION_ENABLED` and `/veda/staging/VEDA_MTQ_QUOTATION_ENABLED`, both "false"). Anything else stops the sequence. Apply, then a drift run with no changes.
5. The owner fills and approves the record; a reviewed change sets `estimation_enabled`, `quotation_enabled` true and the digest. Plan: exactly **0 / 2 / 0** (the two parameters in place). Apply, drift, deploy, readiness.
6. Walkthrough on a synthetic property (scope, BOQ, fail-closed wall-unit geometry, override after re-measure, estimate, draft quotation to APPROVED, customer issue **refused**, lineage trace and its denial), then the flags-off rollback proof (step 5 reversed: 0 / 2 / 0), then restore through the approved record if validation continues.

Results from staging are SYNTHETIC_VALIDATED at most; LIVE_VALIDATED needs genuine field measurements and reference quotations.

