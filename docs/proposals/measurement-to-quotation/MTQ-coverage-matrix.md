# MTQ coverage matrix (reviewer traceability)

**Status:** author self-check against [MTQ-BLUEPRINT.md](MTQ-BLUEPRINT.md), for the independent reviewer to confirm or refute. Section numbers refer to the blueprint.

## 1. Property-type coverage

| Property type | Property row | Space tree | Scope rules | BOQ | Estimate | Quotation | Blueprint refs |
|---|---|---|---|---|---|---|---|
| 2 BHK apartment | `property_type_code = APARTMENT`, `configuration_label` "2 BHK" (display only) | 2 `MASTER_BEDROOM`/`BEDROOM` instances; `derived_bedroom_count = 2` | residential groups | shared formulas | drivers `bedroom_count`, `floor_area_sqft` | standard document | §4.1, §5.3, §9.3, §20 |
| 3 BHK | same | 3 bedroom instances | same | same | same | same | §5.3, §20 |
| 4 BHK | same | 4 instances | same | same | same | same | §5.3, §20 |
| 5 BHK | same | 5 instances | same | same | same | same | §5.3, §20 |
| Duplex | `DUPLEX`; `floor_count` 2 | `level_index` 0/1; `STAIRCASE`, `TERRACE` | same + staircase | same | `FLOOR_FACTOR` adjustment, `level_count` driver | same | §4.1, §4.2, §5.3, §20 |
| Villa | `VILLA`; `plot_area_sqft_centi` | outdoor and semi-open spaces; `is_external` walls; 1–4 levels | villa group (porch, garden) | same | `level_count` driver | same | §4.1, §5.3, §20 |
| Independent house | `INDEPENDENT_HOUSE` | as villa | as villa | same | same | same | §5.3, §20 |
| Commercial (office, retail, clinic, hospitality) | `OFFICE`/`RETAIL`/`CLINIC`/`HOSPITALITY`; `usage_code = COMMERCIAL` | commercial `SPACE_TYPE` values (`RECEPTION`, `CABIN`, `WORKSTATION_AREA`, `CONFERENCE`, `PANTRY`, `RETAIL_FLOOR`, …) | commercial groups | workstations as `count`, partitions as `area_wh` | commercial card lines, per-line GST | commercial copy and terms via release | §4.1, §5.1, §5.3, §8.2, §20 |
| Custom projects | any type; `project_kind_code = PARTIAL`; `CUSTOM` spaces with labels | any subset | generic group plus manual items with `override_reason` | same | manual rates with reasons where the card has none | assumptions listed | §4.1, §5.1, §8.1, §9.1, §10.1, §20 |

**Finding:** every type maps onto the same tables with lookup values, catalogue records and rate lines only. No type requires a new column or table (§20).

## 2. BHK is a label, never a constraint

| Check | Where BHK could have leaked | Blueprint position | Ref |
|---|---|---|---|
| Schema | A `home_size`/BHK column with a CHECK on `property` | None. `configuration_label` is free text, display only; `derived_bedroom_count`, `derived_toilet_count`, `derived_level_count` are computed from spaces | §4.1 |
| Existing estimator CHECKs | `budget_estimate.home_size IN ('1BHK' … 'CUSTOM')`, `property_type IN ('APARTMENT','VILLA')` | Left untouched for the public estimator. MTQ never writes `budget_estimate`; the measured path uses `cost_estimate`, which has no home-size or property-type CHECK and references `property` instead | §4.2, §4.5, §9.3 |
| Pricing engine | Room enumeration in `engine.py` (KITCHEN … BEDROOM_4, WHOLE_HOME) | Engine takes `(space_label, space_type_code)` as opaque strings; rate items keyed by `line_code` | §9.3 |
| Project-level lines | Preparation package scaled by 1/2/3/4 BHK band | Scaled by a declared **driver** (`floor_area_sqft`, `bedroom_count`, `level_count`, `space_count`, `fixed`); the BHK band is one possible driver, not the only one | §9.3 |
| Scope rules | Rules keyed by BHK | Rules keyed by `space_category`, `space_type_code`, requirement type, wall tags and dimensions | §8.1 |
| Typical sizes | Medians per BHK (ADR-012 D3) | Medians live in `space_template.typical_dimensions`, selectable per property type; used only when `dimension_source ≠ MEASURED` and disclosed as assumptions | §5.2, §10.1 |

## 3. Reuse of existing mechanisms

| Existing mechanism | How the blueprint reuses it | New things added | Ref |
|---|---|---|---|
| Versioned pricing engine (`estimator/engine.py`, `calculation_version`) | Prices every BOQ line; one engine, no second calculator | Opaque space labels, `finish_code` rate dimension, project-line drivers (additive) | §1.3, §9.3 |
| Approved rate-card mechanism (`estimator_rate_card`, `estimator_rate_item`, DRAFT/ACTIVE/RETIRED, one ACTIVE) | `cost_estimate` pins `rate_card_id`, `rate_card_version`; rates resolve from the ACTIVE card | `estimator_rate_item_finish` (per-finish rates), compiled from catalogue `pricing.finish_rates` | §4.2, §9.2 |
| Catalogue V3 versioning and release governance (`catalog_record`, `catalog_release`, DRAFT → … → ACTIVE, manifest sha256, four-eyes, rollback) | Space templates, scope rules, quantity formulas, finish pricing and all customer copy are catalogue records; scope, BOQ, estimate and quotation pin `catalog_release_id` | Three record kinds (`space_template`, `scope_rule`, `quantity_formula`); CHECK widened | §1.3, §4.5, §5.2, §8.1, §8.2, §14 |
| Existing RBAC (permission registry, `<resource>.<action>`, ALL/OWN scope, sensitivity classes, MFA for sensitive codes, child-visibility rule) | New codes under new resources; OWN resolves through lead visibility or `assigned_to`; code checks codes only | Four seeded roles; `permission_limit` (roadmap P3) for discount limits | §15 |
| Existing audit logging (nine-column contract, FULL/EVENT_ONLY policies, exception registry, polymorphic `audit_log`) | Every table carries the nine columns; audit policy declared per table; `quotation_event` registered as append-only | None to the kernel | §3, §4 |
| Outbox/event conventions (`outbox_event`, worker, `lead.won` pattern) | Thirteen MTQ event types; lead status sync and the knowledge projector are subscribers | None to the kernel | §1.3, §11.3, §12.3 |
| Existing document/media storage (catalogue media objects, S3, content-hash keys, scan status) | Photos, sketches, floor plans and quotation PDFs through the polymorphic `attachment` table using the same storage and scanner path | ATT module (roadmap) pulled forward | §1.3, §6.1, §16 B1 |
| Lookups and number sequences | `SPACE_TYPE`, `REQUIREMENT_TYPE`, `OPENING_TYPE`, `FINISH`, `UOM`, … ; `VS-PR-`, `VS-M-`, `VS-Q-` | Categories, values and sequence keys only | §4.5 |
| Lead state machine (forward skip, no automatic backward move) | `SITE_VISIT` on scheduling, `QUOTATION_SENT` plus `quoted_amount_minor` on send; WON/LOST stay manual | None | §12.3 |
| Public trust boundary (ADR-011) | Customer portal serves only the frozen snapshot by hashed token; rate-limited; CAPTCHA on decisions | Public quotation endpoints | §10.3, §11.1 |

## 4. Known gaps the reviewer should probe

| # | Gap | Why it matters |
|---|---|---|
| G-1 | Scope-rule expression language (§8.1) is illustrated, not specified: operators, functions (`usable_run`, `min`), evaluation order and failure behaviour need a grammar before B2 | Rules are data; an unspecified grammar becomes an unreviewable DSL |
| G-2 | Offline sync conflict rule (§13.2) is "last write wins within one surveyor's set"; two surveyors on one visit need an explicit second-set policy | Data loss on site is unrecoverable |
| G-3 | GST allocation of adjustments (§9.4) depends on OI-MTQ-07 | Totals cannot be frozen until decided |
| G-4 | `knowledge_*` tables carry ids without FKs by design; the purge and anonymisation ordering with the lead-retention job needs an explicit entry in the contract exception registry (03 §2.9) | Retention compliance |
| G-5 | PDF rendering engine and its determinism (same snapshot → same bytes, or sha256 over the snapshot only) is not chosen | Tamper evidence for the customer document |
| G-6 | SQLite single-writer behaviour under batch sync from several surveyors is asserted, not measured | B1 field reliability |
