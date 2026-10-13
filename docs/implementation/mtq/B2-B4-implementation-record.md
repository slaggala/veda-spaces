# MTQ B2–B4 implementation record

**Branch:** `feature/mtq-b2-b3-b4-commercial-engine` · **Umbrella PR:** see the pull request of that branch · **Instruction:** `VEDA-SPACES-MTQ-B2-B3-B4-END-TO-END-COMMERCIAL-ENGINE` (2026-10-13).
**Source of truth:** main after PR #90 (B1 enabled in protected staging): the blueprint, the survey and scope templates (PR #84 package), the B1 scope freeze and blocker closure, the owner-decision register, decision log 26–30, Catalogue V3 and the estimator (ADR-012/013).
**Status of every result here:** SYNTHETIC_VALIDATED. No live site, real rate or owner decision was used; the B1 field-validation evidence (real sites) does not exist yet.

This record states what was built for B2 (scope and BOQ), B3 (internal estimate) and B4 (quotation), where the code departs from the letter of a design document and why, and exactly which owner decisions it waits for. Nothing here records or assumes an owner decision.

## 1. The one rule the whole build follows

The owner-decision register on main has OI-MTQ-03 to OI-MTQ-17 **blank**. The instruction says not to invent a business value to make anything work. So the engine is complete and every undecided value has a defined, visible effect instead of a default:

| Register row | Governs | Effect while blank (as committed) |
|---|---|---|
| OI-MTQ-03 / 04 | Scope rules; quantity derivations, rounding, wastage, clearances | The ruleset ships as PROPOSED (`fixtures/scope-rules-2026.10.1.json`); every recommendation needs a staff decision; quotations built on it are not customer-issuable (`RULESET_NOT_APPROVED`). No clearance, wastage or corner deduction is applied; rounding is the estimator's own (0.01, half up). |
| OI-MTQ-05 | Premium/Luxury staff rates; finish-variant rates; NEW LINE items | PREMIUM and LUXURY estimates refused (`RATE_CARD_NOT_APPROVED`); a finish variant without a rate stays unpriced (`FINISH_RATE_NOT_APPROVED`); items with no card line stay unpriced (`CATALOGUE_MAPPING_MISSING`) |
| OI-MTQ-06 | Discount authority | Every discount action refused (`OWNER_DECISION_REQUIRED`) |
| OI-MTQ-07 | GST treatment | No tax computed; no final total; not customer-issuable (`GST_POLICY_REQUIRED`) |
| OI-MTQ-08 | Validity, reminders, expiry | Not customer-issuable; the expiry job exists but is not scheduled |
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
| Scope revisions | `scope`, `scope_item`: built from ACCEPTED requirements over the current verified set; staff edits (options, finish, inclusion, dimension overrides with a reason) carry to the next revision (`carried_from_item_id`). Confirm needs every recommendation decided and the measurements still current; it seals a canonical digest and supersedes the previous confirmed revision. |
| Quantity engine | `quantity.py` (`QUANTITY_ENGINE_VERSION` 2026.10.1). Each rate-card input of an item's product (WIDTH, HEIGHT, RUN, AREA, DRAWERS…) is derived from the verified set with its source, a sentence, and the measurement rows read. Line quantities are the **rate card's own quantity bases** evaluated exactly from millimetres and rounded once. |
| BOQ | `boq`, `boq_line`: one line per applicable card line (the card's own option conditions) per included or optional item; room-wise and project views; calculated vs final quantity, override with reason and actor; issues per line and per BOQ; review seals; regeneration supersedes; diff between revisions. Items without a card line are kept (UNMAPPED or MEASURED_COUNT) and reported. |
| Validation | Blocking: missing measurement, impossible quantity (card bounds), missing quantity rule, unsupported unit, invalid option, stale or unverified measurement, Lite survey (B1-02), unexplained override. Warning: missing catalogue mapping, assumed dimension, duplicate scope, proposed ruleset. |

### B3 — internal estimate (`0201_mtq_estimation`, part two)

| Area | Implementation |
|---|---|
| Pricing | `cost_estimate`, `cost_estimate_line`: priced from the estimator's ACTIVE rate card (pinned by id, version and document digest) with the engine's own amount rule (`engine.line_amount_minor`, extracted additively — the budget estimator's results are unchanged). Provenance per line: BOQ line → card product and line → card version → tier → rate → amount → measurement source. |
| Tiers | ESSENTIAL approved by the card's own owner-approved activation. PREMIUM/LUXURY need the card to enable them **and** OI-MTQ-05. |
| Finishes and materials | Catalogue-backed option changes (door type, panelling finish, pooja door…) change the BOQ lines through the card's own conditions and are priced. A finish variant (laminate / acrylic / veneer / PU…) needs an approved finish rate (OI-MTQ-05). |
| Charges | The card's Project Preparation & Protection components are priced by the property's **derived** bedroom count (1–4 BHK keys); site and floor protection → SITE_PROTECTION, freight → TRANSPORT, debris/cleaning/pest → OTHER_SERVICE. 5 BHK and independent houses wait for OI-MTQ-15. Point shifting and sensor provisions are ELECTRICAL_SHIFTING lines without a card line yet. Labour and installation are inside the card's supply-and-install rates: nothing separate is charged. The Custom Features Allowance (ADR-012 D9) is not carried: a measured quotation replaces it with the actual items. |
| Versions | One draft and one approved estimate per property; approval seals; `compare` (quantity, rate, finish/tier, discount, pricing status); `reproduce` recomputes every amount from the pinned card document. |
| Blockers | DATA (rate missing, quantity basis changed, pending discount) block approval; OWNER_DECISION ones (tier, finish, mapping, preparation driver, GST, ruleset) stay visible and block only customer issuance. Stale lineage (measurement, scope, BOQ, rate card) blocks approval. |
| Discounts | `cost_estimate_adjustment`: line / category / project, percent or amount; pre, discount, post, reason, actor, authority, approval, policy version; allocated pro rata beside the lines, never changing a rate. Disabled until OI-MTQ-06. |
| GST | Per-line taxable value, rate, tax and total, only from a recorded OI-MTQ-07 (`tax.py`). |

### B4 — quotation (`0202_mtq_commercial`)

| Area | Implementation |
|---|---|
| Model | `quotation` (version, kind BASE/VARIATION, variation number, accepted baseline, full lineage with the estimate's digest, terms snapshot, totals, validity, frozen document and digest, decision), `quotation_section`, `quotation_line`, `quotation_event`. Number from the platform sequence `QUOTATION` (`VS-Q-YYYY-NNNNNN`) under the sequence row lock. |
| Lifecycle | DRAFT → INTERNAL_REVIEW → APPROVED → ISSUED → ACCEPTED / REJECTED / EXPIRED, SUPERSEDED by a newer version; only a draft changes; one open version per number and variation (database index); an issued version is frozen (CHECK). Issue requires customer-issuability; it syncs the lead as SYSTEM (activity, forward move to QUOTATION_SENT, quoted amount). Decisions record method, optional items chosen, accepted total. |
| Customer document | `rendering.py`: an allow-list model and an escaped, self-contained HTML page; issued versions render only their verified snapshot; drafts carry a staff-only "not a customer document" note. No customer name in the snapshot. |
| Variations | `variations.py`: change orders against the accepted baseline with ADD / OMIT / CHANGE_QUANTITY / CHANGE_FINISH / CHANGE_RATE / CHANGE_MATERIAL lines and the net impact; the base stays ACCEPTED and byte-identical; accepted value of the job = base + accepted variations. |
| Trace | `GET /quotation-lines/{id}/trace`: quotation line → estimate line → BOQ line → scope item → requirement → space → measurement set, revision, space measurement and wall. |

### Cross-cutting

| Area | Implementation |
|---|---|
| Flags | `VEDA_MTQ_ESTIMATION_ENABLED` (B2/B3) and `VEDA_MTQ_QUOTATION_ENABLED` (B4), the blueprint's names; off by default; production refuses both; estimation needs the B1 flag and quotation needs estimation in every environment. Not added to staging infrastructure: no SSM parameter, no plan change. Every commercial path answers 404 while off (the B1 MC-3 gate). `/auth/me` reports both. |
| RBAC | Roles ESTIMATOR and SALES_MANAGER (MFA). New codes `scope.*`, `boq.*`, `cost_estimate.*`, `quotation.*`; the new roles also get the B1 read codes and the workspace self-service rows; SALES_MANAGER gets `lead.read` (ALL). No grant of an existing role to an existing code changed. |
| Audit | Every new table FULL with its aggregate parent; free text erased with the lead (erasure cascade); the frozen quotation document is excluded from audit snapshots (reproducible from its digest, no personal data). |
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

Per-configuration evidence: [evidence/b2-b4-synthetic-2026-10-13.json](evidence/b2-b4-synthetic-2026-10-13.json). Replay against historical quotations (MTQ-G5) is not done: the replay quotation list is still the owner's private data, and only 3 BHK has references.

## 5. What stops a customer quotation today

1. Owner decisions OI-MTQ-03, 04, 07, 08, 09, 11 (all quotations); OI-MTQ-15 (5 BHK and independent houses); OI-MTQ-13 (variations); OI-MTQ-05 (Premium/Luxury, finish variants, items without a card line).
2. Items the rate card has no line for (tall unit, mirror panel, pelmet, point shifting, sensor provisions, custom items) cannot be priced; when accepted as included they block issue (`UNPRICED_LINES`).
3. Staging: the two flags are not set in staging infrastructure; turning them on needs its own enablement record, as B1 did (decision log 30).
4. Field validation: B1's ten-site validation and the MTQ-G5 replay are outstanding; nothing here is validated against a real site or a real quotation.
