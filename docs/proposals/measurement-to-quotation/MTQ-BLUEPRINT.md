# Measurement-to-Quotation Intelligence Platform (MTQ) — Implementation Blueprint

**Status:** Proposal. Design only. No code, no migrations, no flags exist for this module yet.
**Instruction:** `VEDA-SPACES-MEASUREMENT-TO-QUOTATION-INTELLIGENCE-PLATFORM` (owner, 2026-10-13).
**Builds on:** P0 platform ([architecture/](../../architecture/README.md)), Lead Management (04), Budget Estimator ([ADR-012](../../architecture/decisions/ADR-012-budget-estimator.md)), Catalog V3 ([ADR-013](../../architecture/decisions/ADR-013-catalog-driven-estimator.md)), roadmap outlines for ATT, CUST, QUOTE and PROJ ([10-future-roadmap.md](../../architecture/10-future-roadmap.md)).
**Companion documents:** [owner-decision register](MTQ-owner-decisions.md) · [dependency matrix](MTQ-dependency-matrix.md) · [coverage matrix](MTQ-coverage-matrix.md) · [implementation-entry gate](MTQ-implementation-entry-gate.md) · [package README](README.md).
**Governance:** every item marked **Owner input** needs a recorded decision before the block that depends on it is implemented. Nothing in this document authorises implementation.

---

## 0. Executive summary

Veda Spaces today captures site measurements on paper or in a surveyor's phone, and a sales person or designer rebuilds the quotation by hand in a workbook. The budget estimator (ADR-012/013) already prices quotation-shaped lines from a versioned rate card, but it stops at "the official quotation is prepared separately".

This blueprint closes that gap with one lineage:

```
Lead ─► Property ─► Measurement Visit ─► Measurement Set (rev n)
            ─► Requirements ─► Scope (rev n) ─► BOQ (rev n) ─► Cost Estimate (rev n) ─► Quotation (v n) ─► Customer Decision
                                                                                                 └─► Knowledge store (outcomes, actuals, deviations)
```

Five design commitments make it valid for 2 BHK through commercial and custom projects without schema redesign:

1. **A property is a tree of spaces, not a BHK code.** Bedroom count, floor count and configuration are derived from spaces. "3 BHK" is a label, never a constraint.
2. **Space types, requirement types, scope rules and quantity formulas are data** (lookups and catalog records), not enumerations in code. New room kinds, products and rules are additions, not migrations.
3. **Dimensions are stored raw in millimetres**; areas and running lengths are derived by a deterministic quantity engine from walls and openings. The same engine covers a 1-wall niche and a 400 m² retail floor.
4. **One pricing engine.** The ADR-012 engine prices the BOQ. Finishes and tiers are rate dimensions in the compiled card, not a second calculator.
5. **Every aggregate is a revisioned, hash-sealed snapshot** with lineage to its upstream revision, so quotations are reproducible and the knowledge store can compare quoted versus actual without ambiguity.

---

# PHASE 1 — Architecture and models

## 1. Business architecture

### 1.1 Capabilities and owning roles

| # | Capability | Primary actor | Output | Feeds |
|---|---|---|---|---|
| C1 | Property registration | Sales | `property`, `property_space` tree | C2, C4 |
| C2 | Measurement visit scheduling | Sales / coordinator | `measurement_visit` + lead `SITE_VISIT` activity | C3 |
| C3 | Measurement capture | Surveyor (site) | `measurement_set` revision with walls, openings, photos | C4, C5 |
| C4 | Requirement discovery | Designer / Sales with customer | `requirement` rows per space and project | C5 |
| C5 | Scope creation | Designer (auto-recommended, manually overridden) | `scope` revision | C6 |
| C6 | BOQ generation | System (quantity engine), reviewed by estimator | `boq` revision | C7 |
| C7 | Cost estimation | Estimator | `cost_estimate` revision (tier, finishes, rates) | C8 |
| C8 | Quotation | Sales, approved by Sales Manager | `quotation` version, customer document | C9 |
| C9 | Customer decision | Customer (portal link) / Sales on their behalf | `quotation_decision`, lead status | C10, PROJ |
| C10 | Knowledge capture | System + Project Manager | outcomes, actuals, deviations, feature snapshots | Calibration, AI (B5) |

### 1.2 Business rules that shape the design

| Rule | Consequence in the model |
|---|---|
| A customer is quoted from **measured** dimensions, never typical sizes, once a measurement set is verified | `scope_item.dimension_source` must be `MEASURED` for every line of a quotation unless the line is explicitly marked `ASSUMED` with text shown to the customer |
| Prices are **private** until a quotation is sent (ADR-013 D5) | Rates live in `cost_estimate_line`, visible with `cost_estimate.read`; the customer document carries amounts, never unit rates unless the Sales Manager opts in per quotation |
| Quotation **versions are immutable** once sent | `quotation` rows freeze at `SENT`; changes create a new version that supersedes the old one |
| Customer-facing text is governed (promise matrix, ADR-012 §11 D8) | Quotation copy, inclusions, exclusions and warranty text come from catalog `copy` records in the ACTIVE release, pinned by release id in the quotation snapshot |
| Discounts need authority | `quotation.discount_minor` above the actor's limit requires `quotation.approve` from a second person (four-eyes, same pattern as catalog activation) |
| Luxury is consultation-only **in public** (ADR-012 D2) | Staff cost estimates price all three tiers. The public refusal stays in the public estimator only |

### 1.3 Integration with what exists

| Existing asset | How MTQ uses it | Change needed |
|---|---|---|
| `lead` (0100) | Commercial anchor for the whole journey. `property.lead_id`, `quotation.lead_id` | Additive only: lead `status` auto-moves on visit scheduling and quotation sent; `quoted_amount_minor` set on send |
| `lead_activity` SITE_VISIT / QUOTATION | Every visit and every send also writes a system activity | `metadata` carries `measurement_visit_id` / `quotation_id`; no schema change |
| `budget_estimate` + lines (0101) | Optional origin: a public estimate can seed requirements and is linked for variance analysis | `cost_estimate.budget_estimate_id` nullable; no change to estimator tables |
| Pricing engine (`estimator/engine.py`) and rate card (`estimator_rate_card`) | Prices every BOQ line | Engine accepts an opaque space label and a finish code (§9.3); room enumeration becomes data |
| Catalog V3 (`catalog_record`, `catalog_release`) | Source of space templates, products, materials, finishes, rules, copy | Three new record kinds: `space_template`, `scope_rule`, `quantity_formula` (CHECK widened, additive) |
| Lookups (`lookup_value`) | `SPACE_TYPE`, `REQUIREMENT_TYPE`, `OPENING_TYPE`, `FINISH`, `UOM`, `TIER`, `MEASUREMENT_METHOD`, `DEVIATION_REASON` | New categories only |
| Number sequences | `PROPERTY` → `VS-PR-…`, `QUOTATION` → `VS-Q-…`, `MEASUREMENT` → `VS-M-…` | New sequence keys |
| Outbox events | `measurement.verified`, `scope.confirmed`, `quotation.sent`, `quotation.accepted` | New event types |
| `attachment` (roadmap ATT) | Photos, sketches, floor plans, PDF quotation | **ATT is pulled forward as a B1 prerequisite** (§17) |
| RBAC registry | `property.*`, `measurement.*`, `requirement.*`, `scope.*`, `boq.*`, `cost_estimate.*`, `quotation.*`, `knowledge.*` | Registry entries plus four new roles (§15) |

---

## 2. Domain model

### 2.1 Bounded contexts

```
┌──────────────┐   ┌──────────────────────┐   ┌─────────────────────┐   ┌───────────────────┐   ┌────────────────────┐
│  CRM (P0)    │   │  SITE                │   │  ESTIMATION         │   │  COMMERCIAL       │   │  KNOWLEDGE         │
│  lead        │──►│  property            │──►│  requirement        │──►│  quotation        │──►│  quotation_outcome │
│  lead_note   │   │  property_space      │   │  scope / scope_item │   │  quotation_line   │   │  execution_actual  │
│  lead_activity│  │  measurement_visit   │   │  boq / boq_line     │   │  quotation_term   │   │  deviation         │
│              │   │  measurement_set     │   │  cost_estimate(_line)│  │  quotation_decision│  │  estimation_feature│
│              │   │  space_measurement   │   │                     │   │                   │   │  ai_suggestion     │
│              │   │  space_wall/_opening │   │                     │   │                   │   │                    │
└──────────────┘   └──────────────────────┘   └─────────────────────┘   └───────────────────┘   └────────────────────┘
         ▲                    ▲                          ▲                        ▲
         └──── CATALOG V3 (space_template, product, material, scope_rule, quantity_formula, pricing, copy) ────┘
```

Cross-context FKs point upstream only (roadmap §2 rule 4): COMMERCIAL → ESTIMATION → SITE → CRM. KNOWLEDGE references everything by `(entity_type, entity_id)` plus sealed snapshots, so it never blocks a purge.

### 2.2 Aggregates and invariants

| Aggregate | Root | Children | Invariants |
|---|---|---|---|
| Property | `property` | `property_space` (tree) | Exactly one root per space tree; a space has one `space_type_code`; `level_index` ≥ 0; derived counts recomputed on every change |
| Measurement set | `measurement_set` | `space_measurement`, `space_wall`, `space_opening`, `measurement_note` | Only `DRAFT` is editable; `VERIFIED` requires every included space to have ≥ 1 wall or an explicit `shape = FREEFORM` with a stated floor area; an opening's wall belongs to the same space |
| Scope | `scope` | `scope_item`, `scope_item_option` | References one measurement set; a `scope_item` has one space (or none for project-level); an item cannot be both excluded and quoted |
| BOQ | `boq` | `boq_line` | References one scope revision; every line records its formula kind, inputs and result; quantities are centi-units, never floats |
| Cost estimate | `cost_estimate` | `cost_estimate_line`, `cost_estimate_adjustment` | References one BOQ revision and one ACTIVE rate card/release; every line has a resolved `rate_minor`; `total_minor = Σ lines + Σ adjustments` checked on freeze |
| Quotation | `quotation` | `quotation_section`, `quotation_line`, `quotation_exclusion`, `quotation_term`, `quotation_event`, `quotation_decision` | Frozen at `SENT`; `snapshot_sha256` recomputed and compared on every read of a frozen version; one `ACCEPTED` version per lead at a time |

### 2.3 Lineage and staleness

Every downstream aggregate stores the **id and revision number** of the upstream revision it was built from. A read model flags `is_stale = true` when a newer `CONFIRMED`/`VERIFIED` upstream revision exists. Staleness never blocks reading; it blocks **sending a quotation** unless the Sales Manager records an override reason. This is the mechanism that keeps a re-measure or a scope change from silently diverging from the quoted document.

---

## 3. Entity model

Entity → table, all with the nine audit columns (ADR-003), UUIDv7 ids (ADR-002), soft delete, `version` for optimistic concurrency, `ON DELETE RESTRICT`.

| Entity | Table | Parent | Audit policy | Number |
|---|---|---|---|---|
| Property | `property` | lead | FULL | `VS-PR-YYYY-NNNNNN` |
| Space | `property_space` | property (self-ref parent) | FULL | — |
| Measurement visit | `measurement_visit` | property, lead | FULL | `VS-M-YYYY-NNNNNN` |
| Measurement set (revision) | `measurement_set` | property, visit | FULL | — |
| Space measurement | `space_measurement` | measurement_set, space | EVENT_ONLY (bulk rows; diff on verify) | — |
| Wall | `space_wall` | space_measurement | EVENT_ONLY | — |
| Opening | `space_opening` | space_wall | EVENT_ONLY | — |
| Measurement note | `measurement_note` | measurement_set, space (nullable) | FULL | — |
| Requirement | `requirement` | lead, property, space (nullable) | FULL | — |
| Scope (revision) | `scope` | lead, property, measurement_set | FULL | — |
| Scope item | `scope_item` | scope, space (nullable), requirement (nullable) | FULL | — |
| Scope item option | `scope_item_option` | scope_item | EVENT_ONLY | — |
| BOQ (revision) | `boq` | scope | FULL | — |
| BOQ line | `boq_line` | boq, scope_item | EVENT_ONLY | — |
| Cost estimate (revision) | `cost_estimate` | boq, rate card, release | FULL | — |
| Cost estimate line | `cost_estimate_line` | cost_estimate, boq_line | EVENT_ONLY | — |
| Cost estimate adjustment | `cost_estimate_adjustment` | cost_estimate | FULL | — |
| Quotation (version) | `quotation` | lead, property, cost_estimate | FULL | `VS-Q-YYYY-NNNNNN` (+ `-vN`) |
| Quotation section | `quotation_section` | quotation | EVENT_ONLY | — |
| Quotation line | `quotation_line` | section, cost_estimate_line (nullable) | EVENT_ONLY | — |
| Quotation exclusion | `quotation_exclusion` | quotation | EVENT_ONLY | — |
| Quotation term | `quotation_term` | quotation | EVENT_ONLY | — |
| Quotation event | `quotation_event` | quotation | append-only (exception registry) | — |
| Quotation decision | `quotation_decision` | quotation | FULL | — |
| Quotation outcome | `knowledge_quotation_outcome` | quotation (by id, no FK) | append-only | — |
| Execution actual | `knowledge_execution_actual` | quotation line (by id, no FK) | append-only | — |
| Deviation | `knowledge_deviation` | quotation (by id, no FK) | append-only | — |
| Estimation feature snapshot | `knowledge_estimation_feature` | quotation (by id, no FK) | append-only | — |
| AI suggestion | `ai_suggestion` | polymorphic `(entity_type, entity_id)` | FULL | — |

Entity relationship summary:

```
lead 1──* property 1──* property_space (tree via parent_space_id)
property 1──* measurement_visit 1──* measurement_set 1──* space_measurement 1──* space_wall 1──* space_opening
lead 1──* requirement *──1 property_space (optional)
measurement_set 1──* scope 1──* scope_item *──1 property_space (optional), *──1 requirement (optional)
scope 1──* boq 1──* boq_line *──1 scope_item
boq 1──* cost_estimate 1──* cost_estimate_line *──1 boq_line
cost_estimate 1──* quotation 1──* quotation_section 1──* quotation_line *──1 cost_estimate_line (optional)
quotation 1──* quotation_event · 1──0..1 quotation_decision · supersedes_quotation_id (self)
quotation ··· knowledge_* (by id, sealed snapshot, no FK)
```

---

## 4. Database schema

Conventions: logical types from [03-database-schema.md §1](../../architecture/03-database-schema.md); `MM` = INTEGER millimetres; `CENTI` = INTEGER hundredths (the estimator's existing `*_centi` convention for feet and square feet); `BP` = INTEGER basis points. Enumerations are `CODE(n)` with CHECK constraints, widened by migration. Migrations take the **`0200` block** (`0200_mtq_site`, `0201_mtq_estimation`, `0202_mtq_commercial`, `0203_mtq_knowledge`), after ATT (`0106_attachment`).

Audit columns are omitted from the tables below for brevity. Every table has them.

### 4.1 SITE context

**`property`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `property_number` | VARCHAR(20) | NOT NULL | Sequence `PROPERTY`. Unique |
| `lead_id` | GUID | NOT NULL | FK → `lead`. Commercial anchor |
| `customer_id` | GUID | NULL | Reserved for CUST; added when `customer` exists |
| `property_type_code` | CODE(30) | NOT NULL | Lookup `PROPERTY_TYPE` (extended: `APARTMENT`, `DUPLEX`, `PENTHOUSE`, `VILLA`, `INDEPENDENT_HOUSE`, `ROW_HOUSE`, `OFFICE`, `RETAIL`, `HOSPITALITY`, `CLINIC`, `OTHER`) |
| `usage_code` | CODE(20) | NOT NULL | `RESIDENTIAL` / `COMMERCIAL` / `MIXED` |
| `project_kind_code` | CODE(20) | NOT NULL | `NEW` / `RENOVATION` / `PARTIAL` |
| `configuration_label` | VARCHAR(40) | NULL | Free label such as "3 BHK", "Duplex 4 BHK", "Office 2,400 sq ft". **Display only** |
| `built_up_area_sqft_centi` | CENTI | NULL | As stated by the customer or plan |
| `carpet_area_sqft_centi` | CENTI | NULL | |
| `plot_area_sqft_centi` | CENTI | NULL | Villas and independent houses |
| `floor_count` | INTEGER | NULL | Stated; `derived_level_count` is computed from spaces |
| `derived_bedroom_count` | INTEGER | NOT NULL default 0 | Computed: spaces whose type has `counts_as_bedroom` |
| `derived_toilet_count` | INTEGER | NOT NULL default 0 | Computed |
| `derived_level_count` | INTEGER | NOT NULL default 1 | Computed: distinct `level_index` |
| `derived_measured_floor_area_sqft_centi` | CENTI | NULL | From the latest VERIFIED measurement set |
| `address_line_1/2`, `locality`, `city`, `state`, `pincode` | VARCHAR | NULL | Site address (becomes `customer_address` SITE later; dual-write during CUST migration) |
| `geo_lat`, `geo_lng` | DECIMAL(9,6) | NULL | |
| `possession_status_code` | CODE(20) | NULL | `UNDER_CONSTRUCTION` / `READY` / `OCCUPIED` |
| `possession_on` | DATE | NULL | |
| `floor_plan_attachment_id` | GUID | NULL | FK → `attachment` |
| `notes` | TEXT | NULL | |

Indexes: `ux_property__property_number`, `ix_property__lead_id`, `ix_property__city`.

**`property_space`** (the room model; see §5)

| Column | Type | Null | Notes |
|---|---|---|---|
| `property_id` | GUID | NOT NULL | FK |
| `parent_space_id` | GUID | NULL | FK → `property_space`. Dressing inside master bedroom, attached toilet, pantry inside office |
| `space_type_code` | CODE(40) | NOT NULL | Lookup `SPACE_TYPE` (§5.1). `CUSTOM` allowed |
| `custom_type_label` | VARCHAR(60) | NULL | Required when `space_type_code = 'CUSTOM'` |
| `label` | VARCHAR(80) | NOT NULL | "Master Bedroom", "Bedroom 2 (Kids)", "Cabin 3" |
| `instance_no` | INTEGER | NOT NULL default 1 | Nth space of this type on this property |
| `level_index` | INTEGER | NOT NULL default 0 | 0 = ground/entry level; negative for basements |
| `zone_code` | CODE(20) | NOT NULL | `INDOOR` / `SEMI_OPEN` / `OUTDOOR` |
| `sort_order` | INTEGER | NOT NULL | Walk order used by surveyors and documents |
| `is_in_scope` | BOOL | NOT NULL default true | Customer excluded the room entirely |
| `space_template_key` | VARCHAR(80) | NULL | Catalog `space_template` key used for defaults |
| `attributes` | JSON | NOT NULL default `{}` | Typed extras validated per space type: `has_false_ceiling_existing`, `ac_type`, `flooring_existing`, `wet_area` |

Constraints: `ux_property_space__property_type_instance (property_id, space_type_code, instance_no) WHERE is_deleted = false`; `ck_property_space__custom_label` (`space_type_code <> 'CUSTOM' OR custom_type_label IS NOT NULL`); a trigger-free service check that `parent_space_id` belongs to the same property.

**`measurement_visit`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `visit_number` | VARCHAR(20) | NOT NULL | Sequence `MEASUREMENT` |
| `property_id`, `lead_id` | GUID | NOT NULL | FKs |
| `visit_type_code` | CODE(20) | NOT NULL | `INITIAL` / `RE_MEASURE` / `VERIFICATION` / `DESIGN_CHECK` |
| `status` | CODE(20) | NOT NULL | `REQUESTED` → `SCHEDULED` → `IN_PROGRESS` → `COMPLETED` / `CANCELLED` / `NO_SHOW` |
| `scheduled_start_on`, `scheduled_end_on` | UTCDATETIME | NULL | |
| `started_on`, `completed_on` | UTCDATETIME | NULL | Device clock + server receipt |
| `assigned_to` | GUID | NULL | FK → `app_user` (surveyor). Drives OWN scope |
| `lead_activity_id` | GUID | NULL | FK → `lead_activity` (SITE_VISIT) created on schedule |
| `customer_contact_name`, `customer_contact_phone` | VARCHAR | NULL | PII: included in lead anonymisation set |
| `access_notes` | TEXT | NULL | |
| `cancel_reason` | TEXT | NULL | |

**`measurement_set`** (one revision of a property's measurements)

| Column | Type | Null | Notes |
|---|---|---|---|
| `property_id` | GUID | NOT NULL | FK |
| `measurement_visit_id` | GUID | NULL | FK. NULL when imported from a plan without a visit |
| `revision_no` | INTEGER | NOT NULL | 1..n per property |
| `supersedes_set_id` | GUID | NULL | FK → `measurement_set` |
| `status` | CODE(20) | NOT NULL | `DRAFT` → `SUBMITTED` → `VERIFIED` → `SUPERSEDED`; `REJECTED` from SUBMITTED |
| `method_code` | CODE(20) | NOT NULL | Lookup `MEASUREMENT_METHOD`: `TAPE`, `LASER`, `PLAN_DRAWING`, `LIDAR_SCAN`, `TYPICAL` |
| `unit_system_code` | CODE(10) | NOT NULL | `FT_IN` / `MM` as entered. Storage is always MM |
| `captured_by` | GUID | NOT NULL | FK → `app_user` |
| `submitted_on`, `verified_on` | UTCDATETIME | NULL | |
| `verified_by` | GUID | NULL | FK → `app_user`; must differ from `captured_by` when four-eyes is on |
| `summary` | JSON | NOT NULL | Computed on verify: spaces count, total floor area, total wall area, counts of openings |
| `snapshot_sha256` | CHAR(64) | NULL | Canonical JSON of the whole set, set on VERIFIED |
| `device_info` | JSON | NULL | App version, device model, offline sync batches |

Constraints: `ux_measurement_set__property_revision (property_id, revision_no)`; at most one `VERIFIED` per property that is not superseded (partial unique index on `(property_id) WHERE status='VERIFIED' AND is_deleted=false`).

**`space_measurement`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `measurement_set_id`, `space_id` | GUID | NOT NULL | FKs; unique together |
| `shape_code` | CODE(20) | NOT NULL | `RECTANGULAR` / `L_SHAPE` / `POLYGON` / `FREEFORM` |
| `length_mm`, `width_mm` | MM | NULL | Principal dimensions for RECTANGULAR / L_SHAPE |
| `ceiling_height_mm` | MM | NULL | Finished floor to ceiling |
| `beam_bottom_height_mm` | MM | NULL | Lowest beam, if any |
| `floor_to_lintel_mm` | MM | NULL | Loft planning |
| `stated_floor_area_sqft_centi` | CENTI | NULL | Required when `shape_code = 'FREEFORM'` |
| `derived_floor_area_sqft_centi` | CENTI | NULL | Computed from walls/polygon |
| `derived_perimeter_mm` | MM | NULL | |
| `derived_wall_area_gross_sqft_centi`, `derived_wall_area_net_sqft_centi` | CENTI | NULL | Net = gross − openings |
| `polygon` | JSON | NULL | Ordered vertices in mm for POLYGON |
| `flooring_code`, `existing_condition_code` | CODE(30) | NULL | Lookups |
| `is_complete` | BOOL | NOT NULL default false | Surveyor marked done |
| `confidence_code` | CODE(10) | NOT NULL default `HIGH` | `HIGH` / `MEDIUM` / `LOW` (feeds range bands) |

**`space_wall`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `space_measurement_id` | GUID | NOT NULL | FK |
| `wall_index` | INTEGER | NOT NULL | Clockwise from the entry door; unique per space measurement |
| `label` | VARCHAR(40) | NULL | "Wall A", "TV wall", "Window wall" |
| `length_mm` | MM | NOT NULL | |
| `height_mm` | MM | NULL | Defaults to ceiling height |
| `wall_type_code` | CODE(20) | NOT NULL default `MASONRY` | `MASONRY` / `RCC` / `PARTITION` / `GLASS` / `OPEN` (an OPEN edge of an L-shaped living/dining) |
| `is_external` | BOOL | NOT NULL default false | |
| `usable_for_code` | JSON | NOT NULL default `[]` | Surveyor tags: `WARDROBE`, `TV_UNIT`, `KITCHEN_RUN`, `BED_HEAD` |
| `obstructions` | JSON | NOT NULL default `[]` | Switchboards, AC points, pipes with offsets in mm |

**`space_opening`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `space_wall_id` | GUID | NOT NULL | FK |
| `opening_type_code` | CODE(20) | NOT NULL | Lookup `OPENING_TYPE`: `DOOR`, `WINDOW`, `FRENCH_WINDOW`, `ARCH`, `NICHE`, `VENTILATOR`, `AC_SLEEVE`, `SHAFT`, `DUCT`, `CUSTOM` |
| `width_mm`, `height_mm` | MM | NOT NULL | |
| `sill_height_mm` | MM | NULL | Floor to bottom of the opening |
| `offset_from_wall_start_mm` | MM | NULL | Position along the wall |
| `swing_code` | CODE(10) | NULL | `IN` / `OUT` / `SLIDING` / `NONE` |
| `deducts_from_wall_area` | BOOL | NOT NULL default true | |

**`measurement_note`**: `measurement_set_id`, `space_id` (nullable), `note_type_code` (`OBSERVATION` / `RISK` / `CUSTOMER_REQUEST` / `VOICE_TRANSCRIPT`), `body`, `attachment_id` (nullable; photos and sketches go through `attachment` with `entity_type = 'measurement_set'` or `'property_space'`).

### 4.2 ESTIMATION context

**`requirement`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `lead_id`, `property_id` | GUID | NOT NULL | FKs |
| `space_id` | GUID | NULL | FK. NULL = project-level (painting whole home, electrical, deep cleaning) |
| `requirement_type_code` | CODE(40) | NOT NULL | Lookup `REQUIREMENT_TYPE` (§7.1). `CUSTOM` allowed |
| `custom_label` | VARCHAR(80) | NULL | Required for CUSTOM |
| `necessity_code` | CODE(10) | NOT NULL | `MANDATORY` / `OPTIONAL` / `WISHLIST` |
| `priority` | INTEGER | NOT NULL default 3 | 1 high … 5 low |
| `status` | CODE(20) | NOT NULL | `PROPOSED` → `CONFIRMED` / `DECLINED` / `DEFERRED` |
| `source_code` | CODE(20) | NOT NULL | `CUSTOMER` / `RECOMMENDED` / `DESIGNER` / `PUBLIC_ESTIMATE` |
| `budget_estimate_id` | GUID | NULL | FK → `budget_estimate` when seeded from a public estimate |
| `preferences` | JSON | NOT NULL default `{}` | Validated per type: `finish_code`, `colour_family`, `style`, `shutter_type`, `storage_type`, `brand_preference`, `must_have`, `avoid` |
| `target_dimensions` | JSON | NULL | Customer-stated size wishes in mm; not authoritative |
| `budget_hint_minor` | MONEY_MINOR | NULL | Customer's stated ceiling for this item |
| `notes` | TEXT | NULL | |
| `discovered_on`, `discovered_by` | UTCDATETIME, GUID | NOT NULL | |

**`scope`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `lead_id`, `property_id` | GUID | NOT NULL | |
| `measurement_set_id` | GUID | NOT NULL | FK; must be `VERIFIED` to reach `CONFIRMED` |
| `revision_no` | INTEGER | NOT NULL | per property |
| `supersedes_scope_id` | GUID | NULL | |
| `status` | CODE(20) | NOT NULL | `DRAFT` → `PROPOSED` → `CONFIRMED` → `SUPERSEDED` |
| `catalog_release_id` | GUID | NOT NULL | FK → `catalog_release`; the `scope_rule` set used for generation |
| `generation_run` | JSON | NULL | Rule ids fired, inputs, warnings. Reproducibility |
| `tier_code` | CODE(10) | NOT NULL | `ESSENTIAL` / `PREMIUM` / `LUXURY` default for items (engine package codes; customer labels Budget/Premium/Luxury are copy) |
| `is_stale` | BOOL | NOT NULL default false | Read-model flag maintained by the service |
| `confirmed_on`, `confirmed_by` | UTCDATETIME, GUID | NULL | |
| `snapshot_sha256` | CHAR(64) | NULL | Set on CONFIRMED |

**`scope_item`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `scope_id` | GUID | NOT NULL | |
| `space_id` | GUID | NULL | NULL = project-level |
| `requirement_id` | GUID | NULL | Traceability to discovery |
| `product_key` | VARCHAR(80) | NOT NULL | Catalog `product` key in the pinned release (for example `WARDROBE_HINGED`, `KITCHEN_BASE_UNIT`, `FALSE_CEILING_GYPSUM`, `PAINTING_INTERIOR`, `CUSTOM_ITEM`) |
| `product_version` | INTEGER | NOT NULL | Pinned |
| `label` | VARCHAR(120) | NOT NULL | Customer-visible item name |
| `instance_no` | INTEGER | NOT NULL default 1 | Two wardrobes in one room |
| `origin_code` | CODE(20) | NOT NULL | `AUTO_RULE` / `REQUIREMENT` / `MANUAL` / `TEMPLATE` |
| `rule_key` | VARCHAR(80) | NULL | `scope_rule` that produced it |
| `inclusion_code` | CODE(10) | NOT NULL | `INCLUDED` / `OPTIONAL` / `EXCLUDED` |
| `necessity_code` | CODE(10) | NOT NULL | `MANDATORY` / `OPTIONAL` (customer-facing grouping) |
| `tier_code` | CODE(10) | NULL | Overrides scope tier for this item |
| `finish_code` | CODE(30) | NULL | Lookup `FINISH`: `LAMINATE`, `ACRYLIC`, `VENEER`, `PU`, `GLASS`, `MEMBRANE`, `CUSTOM`; validated against the product's allowed finishes |
| `material_key`, `hardware_key` | VARCHAR(80) | NULL | Catalog keys |
| `dimension_source_code` | CODE(10) | NOT NULL | `MEASURED` / `DERIVED` / `ASSUMED` / `TYPICAL` |
| `dimensions` | JSON | NOT NULL | Resolved in mm: `width_mm`, `height_mm`, `depth_mm`, `run_mm`, `area_sqft_centi`, `count`, plus `anchor_wall_id` when derived from a wall |
| `override_reason` | TEXT | NULL | Required when a MANUAL edit changes an AUTO_RULE item's dimensions or inclusion |
| `sort_order` | INTEGER | NOT NULL | |
| `notes` | TEXT | NULL | |

**`scope_item_option`**: `scope_item_id`, `option_group_key`, `option_key`, `quantity` (nullable INTEGER), `is_selected`. Mirrors catalog product option groups (soft-close, tandem drawers, glass profile, loft).

**`boq`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `scope_id` | GUID | NOT NULL | FK |
| `scope_revision_no` | INTEGER | NOT NULL | Copied for staleness checks |
| `revision_no` | INTEGER | NOT NULL | per scope |
| `status` | CODE(20) | NOT NULL | `GENERATED` → `REVIEWED` → `SUPERSEDED` |
| `quantity_engine_version` | VARCHAR(20) | NOT NULL | Semantic version of the formula implementation |
| `catalog_release_id` | GUID | NOT NULL | `quantity_formula` records pinned |
| `rounding_policy` | JSON | NOT NULL | Per UOM: step, mode (for example SFT to 0.01 then line to 0.1; RFT to 0.1) |
| `summary` | JSON | NOT NULL | Totals by UOM and by space; the "project BOQ" view |
| `snapshot_sha256` | CHAR(64) | NULL | Set on REVIEWED |

**`boq_line`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `boq_id`, `scope_item_id` | GUID | NOT NULL | |
| `space_id` | GUID | NULL | Denormalised for room-wise BOQ |
| `position` | INTEGER | NOT NULL | |
| `line_code` | VARCHAR(60) | NOT NULL | Rate-card line (for example `WARDROBE_CARCASS`, `WARDROBE_LOFT`, `SOFT_CLOSE_SHUTTER`, `GYPSUM_CEILING`) |
| `label` | VARCHAR(120) | NOT NULL | |
| `uom_code` | CODE(10) | NOT NULL | Lookup `UOM`: `SFT`, `RFT`, `NOS`, `LUMP`, `SQM`, `RMT`, `ROLL`, `LTR`, `KG` |
| `quantity_centi` | CENTI | NOT NULL | |
| `formula_kind` | CODE(30) | NOT NULL | §8.2 |
| `formula_inputs` | JSON | NOT NULL | Named inputs in mm/counts actually used |
| `derivation` | VARCHAR(255) | NOT NULL | Human-readable: "2 440 × 2 134 mm = 56.1 sq ft" |
| `is_optional` | BOOL | NOT NULL | From scope item inclusion |
| `is_wastage_applied` | BOOL | NOT NULL default false | Wastage factors come from `quantity_formula` records |

**`cost_estimate`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `lead_id`, `property_id`, `boq_id` | GUID | NOT NULL | |
| `boq_revision_no` | INTEGER | NOT NULL | |
| `revision_no` | INTEGER | NOT NULL | per BOQ |
| `supersedes_estimate_id` | GUID | NULL | |
| `status` | CODE(20) | NOT NULL | `DRAFT` → `REVIEWED` → `APPROVED` → `SUPERSEDED` |
| `rate_card_id`, `rate_card_version` | GUID, VARCHAR | NOT NULL | FK → `estimator_rate_card` (ACTIVE at pricing time) |
| `catalog_release_id` | GUID | NOT NULL | |
| `calculation_version` | VARCHAR(20) | NOT NULL | Engine rules version, same field the estimator uses |
| `budget_estimate_id` | GUID | NULL | FK → `budget_estimate` for public-vs-measured variance |
| `tier_code` | CODE(10) | NOT NULL | Default tier; lines may differ |
| `pricing_basis_code` | CODE(20) | NOT NULL | `MEASURED` (narrow band) / `MIXED` / `TYPICAL` |
| `subtotal_minor` | MONEY_MINOR | NOT NULL | Σ included lines |
| `optional_minor` | MONEY_MINOR | NOT NULL | Σ optional lines |
| `adjustment_minor` | MONEY_MINOR | NOT NULL | Σ adjustments (discounts negative, site factors positive) |
| `taxable_minor`, `gst_minor`, `total_minor` | MONEY_MINOR | NOT NULL | GST per line rate (§9.4) |
| `currency` | CHAR(3) | NOT NULL default INR | |
| `margin_bp` | BP | NULL | Internal; visible with `cost_estimate.margin.view` |
| `cost_basis_minor` | MONEY_MINOR | NULL | Internal cost from `pricing` records when available |
| `range_low_minor`, `range_high_minor` | MONEY_MINOR | NULL | Only for `MIXED`/`TYPICAL` bases |
| `notes` | TEXT | NULL | |
| `snapshot_sha256` | CHAR(64) | NULL | Set on APPROVED |

**`cost_estimate_line`**: `cost_estimate_id`, `boq_line_id`, `space_id` (nullable), `position`, `product_key`, `line_code`, `label`, `spec_text` (from the specification record), `uom_code`, `quantity_centi`, `tier_code`, `finish_code`, `rate_minor`, `rate_source` (`CARD` / `CARD_FINISH_VARIANT` / `MANUAL`), `rate_override_reason` (required when MANUAL), `amount_minor`, `gst_rate_bp`, `is_optional`, `is_mandatory`, `cost_minor` (nullable internal).

**`cost_estimate_adjustment`**: `cost_estimate_id`, `adjustment_type_code` (`DISCOUNT_PCT`, `DISCOUNT_AMOUNT`, `SITE_FACTOR`, `FLOOR_FACTOR`, `TRANSPORT`, `ALLOWANCE`, `ROUNDING`), `scope_code` (`PROJECT` / `SPACE` / `LINE`), `target_id` (nullable), `value_bp` or `amount_minor`, `reason`, `approved_by` (nullable; required above limits).

### 4.3 COMMERCIAL context

**`quotation`**

| Column | Type | Null | Notes |
|---|---|---|---|
| `quotation_number` | VARCHAR(20) | NOT NULL | Sequence `QUOTATION`; stable across versions |
| `version_no` | INTEGER | NOT NULL | Unique with `quotation_number` |
| `supersedes_quotation_id` | GUID | NULL | |
| `lead_id`, `property_id`, `cost_estimate_id` | GUID | NOT NULL | |
| `cost_estimate_revision_no` | INTEGER | NOT NULL | |
| `status` | CODE(20) | NOT NULL | `DRAFT` → `IN_REVIEW` → `APPROVED` → `SENT` → (`VIEWED`) → `ACCEPTED` / `REJECTED` / `EXPIRED` / `WITHDRAWN` / `SUPERSEDED` |
| `title` | VARCHAR(120) | NOT NULL | "Interior works — 3 BHK, Whitefield" |
| `tier_code` | CODE(10) | NOT NULL | Headline tier |
| `catalog_release_id` | GUID | NOT NULL | Copy, inclusions, warranty text pinned |
| `terms_version` | VARCHAR(20) | NOT NULL | Commercial terms document version (**Owner input**) |
| `payment_schedule` | JSON | NOT NULL | Milestones with percentages (**Owner input**; no schedule exists in the repo today) |
| `valid_until` | DATE | NOT NULL | Default created + validity days (**Owner input**; estimator uses 30) |
| `subtotal_minor`, `optional_minor`, `discount_minor`, `taxable_minor`, `gst_minor`, `total_minor` | MONEY_MINOR | NOT NULL | Copied from the estimate at freeze, re-validated |
| `currency` | CHAR(3) | NOT NULL | |
| `show_unit_rates` | BOOL | NOT NULL default false | Sales Manager may expose rates |
| `show_room_subtotals` | BOOL | NOT NULL default true | |
| `cover_note` | TEXT | NULL | Customer-facing |
| `prepared_by`, `approved_by` | GUID | NOT NULL / NULL | `approved_by` required ≥ SENT; must differ from `prepared_by` when discount > 0 |
| `sent_on`, `sent_via_code` | UTCDATETIME, CODE(20) | NULL | `EMAIL` / `WHATSAPP` / `PORTAL` / `IN_PERSON` |
| `first_viewed_on` | UTCDATETIME | NULL | From portal events |
| `expires_on` | UTCDATETIME | NULL | Computed from `valid_until` |
| `customer_token_hash` | CHAR(64) | NULL | Hash of the unguessable portal token; raw token never stored |
| `document_attachment_id` | GUID | NULL | Generated PDF |
| `snapshot` | JSON | NULL | Complete customer document model, set on SENT |
| `snapshot_sha256` | CHAR(64) | NULL | |
| `stale_override_reason` | TEXT | NULL | When sent against a stale lineage |

**`quotation_section`**: `quotation_id`, `position`, `section_type_code` (`SPACE` / `PROJECT` / `OPTIONAL` / `ALLOWANCE`), `space_id` (nullable), `title`, `subtotal_minor`, `optional_minor`.

**`quotation_line`**: `quotation_id`, `section_id`, `cost_estimate_line_id` (nullable for free-text lines), `position`, `description`, `spec_text`, `uom_code`, `quantity_centi`, `rate_minor` (nullable in the document when `show_unit_rates = false`; always stored), `amount_minor`, `gst_rate_bp`, `is_optional`, `is_mandatory`, `is_selected_by_customer` (optional lines the customer ticked).

**`quotation_exclusion`**: `quotation_id`, `position`, `exclusion_code` (lookup `EXCLUSION`: `CIVIL_WORK`, `TILES`, `GRANITE`, `SINK_TAPS`, `APPLIANCES`, `DECOR`, `ELECTRICAL_MAINS`, `CUSTOM`), `text`.

**`quotation_term`**: `quotation_id`, `position`, `term_type_code` (`PAYMENT`, `TIMELINE`, `WARRANTY`, `VALIDITY`, `SCOPE_CHANGE`, `GENERAL`), `text`, `copy_record_key` (catalog copy pinned).

**`quotation_event`** (append-only): `quotation_id`, `event_type` (`CREATED`, `SUBMITTED_FOR_REVIEW`, `APPROVED`, `SENT`, `VIEWED`, `DOWNLOADED`, `OPTION_TOGGLED`, `ACCEPTED`, `REJECTED`, `EXPIRED`, `WITHDRAWN`, `SUPERSEDED`, `REMINDER_SENT`), `actor_type` (`STAFF` / `CUSTOMER` / `SYSTEM`), `actor_user_id` (nullable), `occurred_on`, `ip_hash`, `payload` JSON.

**`quotation_decision`**: `quotation_id` (unique), `decision_code` (`ACCEPTED` / `REJECTED` / `NEGOTIATE`), `decided_on`, `decided_via_code` (`PORTAL` / `STAFF_RECORDED` / `SIGNED_COPY`), `recorded_by` (nullable staff), `selected_optional_line_ids` JSON, `accepted_total_minor`, `rejection_reason_code` (lookup `LOST_REASON` reused), `rejection_note`, `signature_attachment_id` (nullable), `consent_text_version`.

### 4.4 KNOWLEDGE context (append-only, no FKs to business tables)

| Table | Key columns | Purpose |
|---|---|---|
| `knowledge_quotation_outcome` | `quotation_id`, `quotation_number`, `version_no`, `lead_id`, `property_id`, `outcome_code` (`ACCEPTED`/`REJECTED`/`EXPIRED`/`SUPERSEDED`), `sent_on`, `decided_on`, `days_to_decision`, `total_minor`, `discount_minor`, `tier_code`, `versions_before_decision`, `rejection_reason_code` | Win/loss facts |
| `knowledge_execution_actual` | `quotation_id`, `quotation_line_id`, `space_id`, `line_code`, `quoted_quantity_centi`, `actual_quantity_centi`, `quoted_amount_minor`, `actual_cost_minor`, `actual_sell_minor`, `source_code` (`PROJECT_CLOSEOUT`/`PROCUREMENT`/`MANUAL`), `recorded_on` | Filled by PROJ/PROC later; manual entry in B4 |
| `knowledge_deviation` | `quotation_id`, `deviation_type_code` (`QUANTITY`/`RATE`/`SCOPE_ADD`/`SCOPE_DROP`/`TIMELINE`), `space_id`, `line_code`, `reason_code` (lookup `DEVIATION_REASON`: `MEASUREMENT_ERROR`, `SITE_CONDITION`, `CUSTOMER_CHANGE`, `DESIGN_CHANGE`, `RATE_CHANGE`, `ESTIMATION_ERROR`), `delta_quantity_centi`, `delta_amount_minor`, `note` | Why actual ≠ quoted |
| `knowledge_estimation_feature` | `quotation_id`, `feature_version`, `features` JSON (property type, usage, derived counts, measured floor area, per-space type and area, scope item mix, tier, finish mix, city, totals, discount, outcome), `embedding` (reserved; pgvector after the PostgreSQL gate) | Flat feature store for calibration and models |
| `knowledge_rate_observation` | `line_code`, `finish_code`, `tier_code`, `city`, `observed_on`, `quoted_rate_minor`, `accepted` BOOL, `source_quotation_id` | Market acceptance of rates over time |
| `ai_suggestion` | `entity_type`, `entity_id`, `suggestion_type` (`SCOPE_ITEM`, `DIMENSION`, `RATE`, `DISCOUNT_RISK`, `MISSING_ITEM`), `payload`, `confidence_bp`, `model_version`, `status` (`PROPOSED`/`ACCEPTED`/`DISMISSED`), `decided_by`, `decided_on` | From roadmap "AI features"; suggestions never write business fields |

Retention: knowledge rows are **not** PII-bearing (ids and measurements only), so they survive lead anonymisation. `quotation.snapshot` is PII-bearing (customer name on the document) and is anonymised with the lead.

### 4.5 Additive changes to existing tables

| Table | Change | Rule |
|---|---|---|
| `lead` | none in B1–B4; `converted_customer_id` arrives with CUST | — |
| `lead_activity.metadata` | carries `measurement_visit_id`, `quotation_id` | JSON, no schema change |
| `estimate_event` | no change; `QUOTATION_PROCESS_STARTED` now carries `scope_id` in payload | additive |
| `catalog_record.kind` CHECK | add `space_template`, `scope_rule`, `quantity_formula` | widen CHECK (roadmap §2 rule 1) |
| `lookup_category` | add `SPACE_TYPE`, `REQUIREMENT_TYPE`, `OPENING_TYPE`, `FINISH`, `UOM`, `MEASUREMENT_METHOD`, `EXCLUSION`, `DEVIATION_REASON`, `TIER` | seed |
| `lookup_value` PROPERTY_TYPE | add `DUPLEX`, `PENTHOUSE`, `ROW_HOUSE`, `HOSPITALITY`, `CLINIC` | seed; public form unchanged |
| `number_sequence` | add `PROPERTY`, `MEASUREMENT`, `QUOTATION` | seed |
| `permission` | registry sync for the new codes | migration |

---

## 5. Room (space) model

### 5.1 `SPACE_TYPE` lookup

Values with `attributes` JSON (`category`, `counts_as_bedroom`, `counts_as_toilet`, `wet_area`, `default_template_key`):

| Category | Codes |
|---|---|
| LIVING | `LIVING`, `DINING`, `LIVING_DINING`, `FAMILY_LOUNGE`, `FOYER`, `PASSAGE`, `STAIRCASE`, `MEDIA_ROOM`, `HOME_THEATRE`, `POOJA`, `LIBRARY` |
| SLEEPING (`counts_as_bedroom`) | `MASTER_BEDROOM`, `BEDROOM`, `CHILDREN_BEDROOM`, `GUEST_BEDROOM`, `PARENTS_BEDROOM`, `SERVANT_ROOM`, `GUEST_SUITE` |
| ATTACHED | `DRESSING`, `WALK_IN_CLOSET`, `TOILET` (`counts_as_toilet`, `wet_area`), `POWDER_ROOM` |
| WORK | `STUDY`, `HOME_OFFICE`, `CABIN`, `WORKSTATION_AREA`, `CONFERENCE`, `RECEPTION`, `WAITING_AREA`, `TRAINING_ROOM` |
| SERVICE (`wet_area` where relevant) | `KITCHEN`, `UTILITY`, `PANTRY`, `STORE`, `LAUNDRY`, `SERVER_ROOM`, `WASH_AREA` |
| OUTDOOR / SEMI-OPEN | `BALCONY`, `TERRACE`, `SIT_OUT`, `GARDEN`, `PARKING`, `PORCH` |
| COMMERCIAL | `RETAIL_FLOOR`, `BACK_OFFICE`, `TRIAL_ROOM`, `BILLING_COUNTER`, `TREATMENT_ROOM`, `GUEST_ROOM` |
| OTHER | `CUSTOM` (label required) |

Adding a space type is a lookup insert plus, optionally, a catalog `space_template` record. No migration.

### 5.2 `space_template` (new catalog kind)

```
key: MASTER_BEDROOM_DEFAULT
space_type_code: MASTER_BEDROOM
applies_when: { usage: RESIDENTIAL }
default_attributes: { ceiling_height_mm: 2900 }
survey_checklist: [ "Wardrobe wall length", "Bed wall", "AC position", "Window sill", "Loft height" ]
recommended_requirements: [ WARDROBE, BED, SIDE_TABLE, DRESSER, FALSE_CEILING, TV_UNIT? ]
scope_rule_group: BEDROOM_RULES
typical_dimensions: { length_mm: 4270, width_mm: 3660 }   # ADR-012 D3 medians; per property type
```

Templates are versioned, approved and released like every other catalog record, so "what we recommend for a kitchen" is auditable and can differ between a 2 BHK apartment and a villa without touching code.

### 5.3 How each property type maps (no schema change)

| Property | Spaces | Levels | Notes |
|---|---|---|---|
| 2 BHK apartment | ~8 spaces, 2 bedrooms, 2 toilets | 1 | `configuration_label` "2 BHK" derived from counts |
| 3 BHK / 4 BHK / 5 BHK | more bedroom instances (`instance_no` 1..n) | 1 | Nothing else changes |
| Duplex / penthouse | same types, `level_index` 0 and 1, `STAIRCASE`, `TERRACE` | 2 | Floor factor via `cost_estimate_adjustment FLOOR_FACTOR` |
| Villa / independent house | plus `PORCH`, `GARDEN`, `SERVANT_ROOM`, `PARKING`, more levels | 1..4 | `plot_area`, external walls (`is_external`) |
| Office | `RECEPTION`, `CABIN` ×n, `WORKSTATION_AREA`, `CONFERENCE`, `PANTRY`, `SERVER_ROOM` | n | `usage_code = COMMERCIAL` selects commercial scope rules and copy |
| Retail / clinic / hospitality | commercial types above | n | Same tables |
| Custom project (a single kitchen renovation, a clubhouse) | any subset; `CUSTOM` spaces; `project_kind = PARTIAL` | any | Scope rules fall back to the generic group |

---

## 6. Measurement model

### 6.1 Principles

1. **Raw in millimetres, derived in centi-feet.** Surveyors enter feet-inches or mm (`unit_system_code`); the client converts to mm before submission; the server never stores fractional feet. Derived areas use the estimator's `*_centi` convention so the pricing engine is unchanged.
2. **Walls are the unit of truth.** Modular furniture is anchored to walls (wardrobe wall, kitchen run, TV wall). Storing walls with openings lets the scope engine derive item widths (`wall.length − openings − clearances`) and lets the BOQ deduct openings from paint and wallpaper areas.
3. **Shapes degrade gracefully.** RECTANGULAR needs two dimensions; L_SHAPE needs walls; POLYGON stores vertices; FREEFORM takes a stated area with `confidence = LOW`. All four price through the same formulas.
4. **Offline-first capture.** Flats and villas under construction have poor connectivity. The mobile client works on a local draft and syncs in batches (§13.3). Ids stay service-generated (ADR-002): the client sends a `client_ref` per row, the server returns the mapping, and `(measurement_set_id, client_ref)` is the idempotency key.
5. **Photos per wall.** Each wall and opening may carry attachments (`entity_type = 'space_wall'`). The verifier sees the photo beside the number.

### 6.2 Revisions

| Event | Result |
|---|---|
| First visit | `measurement_set` rev 1 DRAFT by the surveyor |
| Surveyor finishes | SUBMITTED; summary computed; cannot edit |
| Designer/estimator checks | VERIFIED (sets `snapshot_sha256`, emits `measurement.verified`) or REJECTED with notes → new DRAFT rev 2 |
| Re-measure after design | New visit `RE_MEASURE`, rev n+1; on VERIFIED, rev n → SUPERSEDED, downstream scopes flagged stale |
| Plan-based pre-measure | rev 0 with `method = PLAN_DRAWING`, `confidence = MEDIUM`; a later TAPE/LASER set supersedes it |

Verification rules (fail closed): every in-scope space has a measurement; every RECTANGULAR/L_SHAPE/POLYGON space has ceiling height; walls close within a tolerance for POLYGON; every opening fits inside its wall; no negative derived areas; totals within ±25 % of the stated built-up area or a warning is acknowledged.

### 6.3 Derived values (computed on the server, never trusted from the client)

| Derived | Formula |
|---|---|
| Floor area | RECTANGULAR: L × W · L_SHAPE/POLYGON: shoelace over vertices or wall-derived rectangles · FREEFORM: stated |
| Perimeter | Σ wall lengths (OPEN edges excluded from wall area, included in perimeter) |
| Gross wall area | Σ (length × height) for non-OPEN walls |
| Net wall area | Gross − Σ openings with `deducts_from_wall_area` |
| Ceiling area | Floor area (flat) − Σ shafts/ducts |
| Usable wall run for product X | wall.length − openings on that wall − clearances from the `quantity_formula` record |

---

## 7. Requirement model

### 7.1 `REQUIREMENT_TYPE` lookup

`WARDROBE`, `LOFT`, `TV_UNIT`, `CROCKERY_UNIT`, `KITCHEN`, `KITCHEN_LOFT`, `BREAKFAST_COUNTER`, `STUDY_UNIT`, `BOOKSHELF`, `VANITY`, `BED`, `SIDE_TABLE`, `DRESSER`, `SHOE_RACK`, `FOYER_UNIT`, `POOJA_UNIT`, `BAR_UNIT`, `WINDOW_SEATING`, `STORAGE_BOX`, `FALSE_CEILING`, `CEILING_LIGHTING`, `WALLPAPER`, `WALL_PANELLING`, `TEXTURE_PAINT`, `PAINTING`, `ELECTRICAL`, `PLUMBING`, `PARTITION`, `GLASS_PARTITION`, `FLOORING`, `WORKSTATION`, `RECEPTION_DESK`, `STORAGE_CABINET`, `SOFT_FURNISHING`, `CUSTOM`.

Each value's `attributes` carries `default_products` (catalog product keys), `allowed_space_categories`, `is_project_level`, `discovery_questions` (prompt text shown to the designer).

### 7.2 Discovery flow

1. On property creation, `recommended_requirements` from each space's template are inserted as `PROPOSED` / `RECOMMENDED`.
2. If a public `budget_estimate` is linked to the lead, its rooms and products become `PROPOSED` / `PUBLIC_ESTIMATE` requirements with the customer's package and the public inputs as `preferences` and `target_dimensions`.
3. The designer walks the customer through each space: confirm, decline, defer, add custom; capture `necessity_code`, finish and style preferences, budget hints.
4. Project-level requirements (painting, electrical, deep cleaning, false ceiling throughout) sit with `space_id = NULL`.
5. `CONFIRMED` requirements are the input to scope generation; `DECLINED` ones become quotation exclusions automatically ("Not included: TV unit in Bedroom 2, as discussed").

---

## 8. BOQ model

### 8.1 Scope generation (feeds the BOQ)

A `scope_rule` catalog record:

```
key: BEDROOM_WARDROBE_FROM_WALL
group: BEDROOM_RULES
when:
  space_category: SLEEPING
  requirement_type: WARDROBE            # fires only if confirmed, or always when `auto: true`
  wall_tagged: WARDROBE                 # surveyor tag; fallback: longest wall without a door
emit:
  product_key: WARDROBE_HINGED
  dimensions:
    width_mm:  wall.usable_run(clearance_mm: 50)
    height_mm: min(space.floor_to_lintel_mm, 2134)   # 7 ft default (ADR-012)
    depth_mm:  600
  options: { LOFT: when space.ceiling_height_mm - 2134 >= 450 }
  dimension_source: DERIVED
  necessity: MANDATORY
priority: 10
```

Rules are evaluated server-side per space in priority order; later rules may refine earlier emissions (`refines: key`). The run is recorded in `scope.generation_run`. Manual overrides keep `origin = AUTO_RULE` but require `override_reason`, so calibration (B5) can learn where the rules are wrong.

Customer preferences enter as rule inputs (`requirement.preferences.shutter_type = SLIDING` selects `WARDROBE_SLIDING`), and the tier sets default finishes.

### 8.2 Quantity engine

`quantity_formula` catalog records map `(product_key, line_code)` to a formula kind and parameters. The closed set of kinds extends ADR-012's five:

| Kind | Inputs | Output UOM | Example line |
|---|---|---|---|
| `area_wh` | width, height | SFT | Wardrobe carcass, TV panelling, study unit |
| `area_wd` | width, depth | SFT | Counter top laying |
| `run_length` | width or run | RFT | Kitchen base/wall units priced per running foot variant, beading, cove |
| `count` | n | NOS | Drawers, lights, fan points, mirrors |
| `lump` | — | LUMP | Plumbing package, hydraulic fitting |
| `floor_area` | space derived | SFT | Flooring, deep cleaning |
| `ceiling_area` | space derived − shafts | SFT | Gypsum ceiling |
| `wall_area_net` | space derived, optional wall subset | SFT | Painting, texture, panelling on a wall |
| `perimeter` | space derived | RFT | Skirting, cornice, profile light channel |
| `rolls` | wall_area_net, roll coverage | ROLL | Wallpaper (ceil) |
| `shutter_area` | width, height, shutter fraction | SFT | Soft-close hardware (ADR-012 interpretation 1) |
| `volume_or_weight` | reserved | LTR / KG | Paint litres, if ever priced that way |

Every formula has `rounding` (step and mode), optional `wastage_bp`, and `min_quantity`. Results are integers in centi-units; floating point is never persisted.

### 8.3 Views

- **Room-wise BOQ:** `boq_line` grouped by `space_id`, then by product.
- **Project BOQ:** grouped by `line_code` with Σ quantity per UOM (what procurement needs). Stored in `boq.summary` at REVIEWED and recomputable.
- **Diff between BOQ revisions:** by `(scope_item_id, line_code)`, showing quantity deltas and the derivation change (re-measure vs scope change).

---

## 9. Estimate model

### 9.1 Tiers and finishes

| Customer label (copy) | Engine tier | Typical finishes | Status today |
|---|---|---|---|
| Budget | `ESSENTIAL` | Laminate | Priced (ADR-012) |
| Premium | `PREMIUM` | High-gloss laminate, acrylic | Own rates, hidden publicly until validated (D1); **staff may price** |
| Luxury | `LUXURY` | PU, veneer, lacquered glass | Public consultation-only (D2); **staff may price** |

Finish is a **line attribute**, tier a **default**. A Budget quotation can carry one acrylic kitchen. The rate resolution order is:

1. explicit rate for `(line_code, finish_code)` in the compiled card (`rate_source = CARD_FINISH_VARIANT`),
2. else the tier rate for `line_code` (`CARD`),
3. else a manual rate with `rate_override_reason` and `cost_estimate.rate.override` permission (`MANUAL`).

### 9.2 Rate card extension (compiled, not a second engine)

`estimator_rate_item` keeps its three tier columns. An additive table **`estimator_rate_item_finish`** (`rate_item_id`, `finish_code`, `rate_minor`, `spec_text`) carries per-finish rates. The catalog `pricing` record kind gains an optional `finish_rates` map; the release compiler writes both tables. Cards remain versioned, approved and immutable once ACTIVE, so finish pricing inherits the existing governance.

### 9.3 Engine changes (additive)

| Today | Blueprint |
|---|---|
| Rooms are an enumeration in `engine.py` (KITCHEN … BEDROOM_4, WHOLE_HOME) | The engine takes `(space_label, space_type_code)` as opaque strings; rate items are keyed by `line_code`, never by room. `budget_estimate_line.room` is already VARCHAR, so the public estimator is unaffected |
| Inputs are typical or customer-entered sizes | Inputs come from `boq_line.quantity_centi`; the engine prices, it does not measure |
| Package is the only rate dimension | `finish_code` added as a rate dimension (§9.1) |
| Project lines scale by BHK (preparation package per home size) | Project lines scale by a **driver** declared in the card: `floor_area_sqft`, `bedroom_count`, `level_count`, `space_count` or `fixed`. BHK bands become one possible driver (`bedroom_count`), so villas, duplexes and offices price without new code |

### 9.4 Totals

```
line.amount_minor   = round_half_up(quantity_centi × rate_minor / 100)
space.subtotal      = Σ included lines in the space
subtotal_minor      = Σ space subtotals + Σ project-level included lines
optional_minor      = Σ optional lines (never in subtotal)
adjustment_minor    = Σ adjustments (discounts negative; floor/site factors positive)
taxable_minor       = subtotal_minor + adjustment_minor
gst_minor           = Σ per-line (line.amount × gst_rate_bp / 10 000) after allocating adjustments pro rata   # Owner input: single rate vs per-line
total_minor         = taxable_minor + gst_minor
```

Ranges exist only when `pricing_basis_code ≠ MEASURED`; a fully measured estimate is a single number.

### 9.5 Revisions

A `cost_estimate` is re-priced (new revision) when: the BOQ changes, the tier or a finish changes, the rate card changes, or an adjustment changes. `APPROVED` seals the snapshot. Comparing two revisions shows per-line deltas tagged `QUANTITY`, `RATE`, `FINISH`, `ADJUSTMENT`.

---

## 10. Quotation model

### 10.1 Document structure

1. Cover: customer, property, configuration label, tier, validity, prepared by.
2. Summary: subtotal, discount, GST, total; optional items total shown separately; payment schedule.
3. Room-wise sections (`quotation_section SPACE`): lines with description, spec text, quantity and UOM; amount per line; unit rates only when `show_unit_rates`.
4. Project section: preparation and protection package (grouped, ADR-012 D5), painting, electrical.
5. Optional items section: customer may tick on the portal; `is_selected_by_customer`.
6. Mandatory items are marked; declining a mandatory item requires a staff conversation (portal shows "talk to your designer").
7. Exclusions (auto from declined requirements plus the standard list).
8. Terms: payment, timeline band, warranty summary (filtered to selected products, ADR-012 D8), validity, scope-change policy.
9. Assumptions: every `ASSUMED`/`TYPICAL` dimension is listed with its value.

### 10.2 Lifecycle

```
DRAFT ──► IN_REVIEW ──► APPROVED ──► SENT ──► VIEWED ──► ACCEPTED
  ▲           │              │          │                └─► lead: NEGOTIATION or WON (sales records), outbox quotation.accepted
  │           └── rejected ──┘          ├──► REJECTED (customer)   → lead stays open; sales may create v+1
  │                                     ├──► EXPIRED  (valid_until passed, nightly job)
  │                                     └──► WITHDRAWN (staff)
  └── new version supersedes any non-terminal older version → SUPERSEDED
```

- `SENT` freezes the row and its children, stores `snapshot`, `snapshot_sha256`, generates the PDF attachment, moves the lead to `QUOTATION_SENT`, sets `lead.quoted_amount_minor = total_minor`, writes a QUOTATION activity, emits `quotation.sent`.
- Only one version per `quotation_number` may be non-terminal.
- A customer can accept **only** the latest SENT version. Accepting records `quotation_decision`, emits `quotation.accepted`, and (when PROJ exists) creates the project.

### 10.3 Customer portal view (public trust boundary, ADR-011)

`GET /api/v1/public/quotations/{token}` serves the frozen snapshot only. The token is 128-bit, single-quotation, expires with the quotation, is rate-limited and revocable (`WITHDRAWN`). Views, downloads and option toggles are `quotation_event` rows with `actor_type = CUSTOMER`. Acceptance requires re-typing the quotation number and ticking the terms version (recorded as `consent_text_version`). No prices beyond the document are exposed; no staff names beyond `prepared_by` display name.

---

# PHASE 2 — API, workflow, UX, versioning, RBAC

## 11. API design

All under `/api/v1`, following [08-api-design.md §2](../../architecture/08-api-design.md): snake_case, `If-Match` on mutations, `Idempotency-Key` on creates and state changes, RFC 9457 errors, cursor pagination, OpenAPI generated from DTOs, `*_code` lookups.

### 11.1 Resources

| Method & path | Permission | Notes |
|---|---|---|
| `GET/POST /properties` · `GET/PATCH /properties/{id}` | `property.read` / `property.create` / `property.update` | Filter by `lead_id`, `city`, `property_type_code` |
| `GET/POST /properties/{id}/spaces` · `PATCH/DELETE /spaces/{id}` · `PUT /properties/{id}/spaces/order` | `property.update` | `POST /properties/{id}/spaces/from-template` seeds from `space_template`s |
| `GET /properties/{id}/summary` | `property.read` | Derived counts, latest verified set, latest quotation |
| `GET/POST /measurement-visits` · `GET/PATCH /measurement-visits/{id}` · `POST …/{id}/status` | `measurement.visit.read/create/update/schedule` | Status transitions only via `/status` (same pattern as leads) |
| `POST /measurement-visits/{id}/measurement-sets` | `measurement.capture` | Creates DRAFT rev n+1 |
| `GET /measurement-sets/{id}` · `GET /properties/{id}/measurement-sets` | `measurement.read` | Full tree in one response for the capture client |
| `PUT /measurement-sets/{id}/spaces/{space_id}` | `measurement.capture` | Upsert the space measurement with walls and openings in one call; `client_ref` per row |
| `POST /measurement-sets/{id}/sync` | `measurement.capture` | Offline batch: array of space payloads + notes; returns `client_ref → id` map; idempotent per `(set, client_ref)` |
| `POST /measurement-sets/{id}/submit` · `/verify` · `/reject` | `measurement.capture` / `measurement.verify` | `verify` runs the fail-closed checks and returns problems with pointers |
| `GET /measurement-sets/{id}/diff/{other_id}` | `measurement.read` | Per-space dimension deltas |
| `GET/POST /requirements` · `PATCH /requirements/{id}` · `POST /requirements/{id}/status` | `requirement.read/create/update` | Filter by `lead_id`, `property_id`, `space_id`, `status` |
| `POST /properties/{id}/requirements/seed` | `requirement.create` | From templates and/or `budget_estimate_id` |
| `POST /scopes` (body: `measurement_set_id`, `tier_code`) · `GET /scopes/{id}` | `scope.create` / `scope.read` | Create runs generation and returns items plus `generation_run` |
| `POST /scopes/{id}/regenerate` | `scope.update` | Re-run rules keeping MANUAL items |
| `POST/PATCH/DELETE /scopes/{id}/items[/{item_id}]` · `PUT …/items/{item_id}/options` | `scope.update` | Manual override; `override_reason` enforced |
| `POST /scopes/{id}/status` | `scope.confirm` for CONFIRMED | Requires VERIFIED measurement set |
| `POST /scopes/{id}/boqs` · `GET /boqs/{id}` · `GET /boqs/{id}/summary` · `GET /boqs/{id}/diff/{other}` · `POST /boqs/{id}/review` | `boq.generate` / `boq.read` / `boq.review` | Generation is deterministic; same inputs → same lines |
| `POST /boqs/{id}/cost-estimates` · `GET /cost-estimates/{id}` | `cost_estimate.create` / `cost_estimate.read` | Prices with the ACTIVE card; `rate_minor` visible only with `cost_estimate.rate.view` |
| `PATCH /cost-estimates/{id}/lines/{line_id}` | `cost_estimate.update` (+ `.rate.override` for MANUAL rates) | Tier/finish per line; re-prices the revision |
| `POST/PATCH/DELETE /cost-estimates/{id}/adjustments[/{adj_id}]` | `cost_estimate.update`; `cost_estimate.discount.approve` above limit | |
| `POST /cost-estimates/{id}/status` | `cost_estimate.review` / `.approve` | APPROVED seals |
| `GET /cost-estimates/{id}/variance` | `cost_estimate.read` | vs linked `budget_estimate` and vs previous revision |
| `POST /cost-estimates/{id}/quotations` · `GET /quotations` · `GET /quotations/{id}` | `quotation.create` / `quotation.read` | Create builds sections and lines from the estimate and the ACTIVE release copy |
| `PATCH /quotations/{id}` · `PUT …/sections` · `PUT …/exclusions` · `PUT …/terms` | `quotation.update` | DRAFT only |
| `POST /quotations/{id}/preview` | `quotation.read` | Renders the document model (and PDF) without freezing |
| `POST /quotations/{id}/status` (`IN_REVIEW`, `APPROVED`, `WITHDRAWN`) | `quotation.update` / `quotation.approve` | Four-eyes when discount > 0 |
| `POST /quotations/{id}/send` (body: channel, recipients) | `quotation.send` | Freezes, generates PDF, portal token, lead side effects. Refuses when stale unless `stale_override_reason` + `quotation.approve` |
| `POST /quotations/{id}/versions` | `quotation.create` | Clones into DRAFT v+1 bound to a (possibly new) estimate |
| `POST /quotations/{id}/decision` | `quotation.decision.record` | Staff-recorded acceptance/rejection |
| `GET /quotations/{id}/events` · `GET /quotations/{id}/document` | `quotation.read` | Download the frozen PDF |
| `GET /leads/{id}/journey` | `lead.read` | Read model: property, visits, latest set, scope, BOQ, estimate, quotation versions with staleness flags |
| **Public** `GET /public/quotations/{token}` · `POST …/{token}/options` · `POST …/{token}/accept` · `POST …/{token}/reject` · `GET …/{token}/document` | none (token) | Rate-limited; CAPTCHA on accept/reject; events recorded |
| `GET /knowledge/outcomes` · `GET /knowledge/deviations` · `GET /knowledge/rate-observations` · `POST /knowledge/execution-actuals` | `knowledge.read` / `knowledge.actual.record` | Filters by period, property type, city, tier |
| `GET /ai/suggestions?entity_type&entity_id` · `POST /ai/suggestions/{id}/decision` | `ai_suggestion.read` / `.decide` | B5 |

### 11.2 Error codes added

`MEASUREMENT_INCOMPLETE` (with `pointers[]`), `OPENING_EXCEEDS_WALL`, `SET_NOT_VERIFIED`, `SCOPE_STALE`, `BOQ_STALE`, `ESTIMATE_STALE`, `RATE_UNRESOLVED` (line, finish), `DISCOUNT_LIMIT_EXCEEDED`, `QUOTATION_FROZEN`, `QUOTATION_SUPERSEDED`, `TOKEN_EXPIRED`, `OVERRIDE_REASON_REQUIRED`, `FOUR_EYES_REQUIRED`.

### 11.3 Events (outbox)

`property.created`, `measurement_visit.scheduled`, `measurement_visit.completed`, `measurement.verified`, `requirement.confirmed`, `scope.confirmed`, `boq.reviewed`, `cost_estimate.approved`, `quotation.sent`, `quotation.viewed`, `quotation.accepted`, `quotation.rejected`, `quotation.expired`. Subscribers: lead status sync, notifications (WhatsApp/email to the customer and the owner), the knowledge projector, and later PROJ.

## 12. Workflow design

### 12.1 End-to-end happy path

| Step | Actor | System effect |
|---|---|---|
| 1 Lead reaches CONTACTED; sales creates the property and spaces (or seeds from a template, or imports from the public estimate) | Sales | `property`, `property_space`, PROPOSED requirements |
| 2 Sales schedules a visit | Sales | `measurement_visit SCHEDULED`; lead → `SITE_VISIT`; SITE_VISIT activity PLANNED; surveyor notified |
| 3 Surveyor measures, walks space by space, photographs walls, tags walls, submits | Surveyor | set rev 1 SUBMITTED; visit COMPLETED; activity COMPLETED |
| 4 Designer verifies; fixes typos by rejecting back or verifying with notes | Designer | set VERIFIED; `measurement.verified` |
| 5 Designer runs requirement discovery with the customer (on site or later) | Designer | requirements CONFIRMED/DECLINED |
| 6 Designer generates scope, reviews auto items, overrides, confirms | Designer | scope CONFIRMED; `scope.confirmed` |
| 7 System generates BOQ; estimator reviews quantities | Estimator | boq REVIEWED |
| 8 Estimator prices, sets finishes, proposes discount | Estimator | cost_estimate REVIEWED |
| 9 Sales Manager approves estimate and quotation (four-eyes when discounted) | Sales Manager | APPROVED |
| 10 Sales sends | Sales | quotation SENT; lead `QUOTATION_SENT`; `quoted_amount_minor`; PDF; portal link |
| 11 Customer views, toggles optional items, accepts or rejects | Customer | events; decision; lead moves on acceptance |
| 12 Knowledge projector writes outcome and features | System | `knowledge_*` |

### 12.2 Change paths

| Trigger | Path |
|---|---|
| Customer changes scope after the quote | Requirements edited → scope rev n+1 → BOQ → estimate → quotation v+1; v n SUPERSEDED |
| Re-measure finds different dimensions | New visit → set rev n+1 VERIFIED → scope flagged stale → regenerate keeps MANUAL items → downstream revisions |
| Rate card changes between estimate and send | Estimate flagged stale against the card; re-price or send with override (Sales Manager) |
| Quotation expires | Nightly job: `EXPIRED`; reminder notifications before expiry (**Owner input**: cadence) |
| Customer accepts an older version | Refused with `QUOTATION_SUPERSEDED`; portal shows the latest |

### 12.3 Lead synchronisation

Lead status moves forward automatically (`SITE_VISIT` on schedule, `QUOTATION_SENT` on send) using the existing forward-skip rule; it never moves backward automatically. WON/LOST remain explicit sales decisions, consistent with 04 §7.

## 13. UX design

### 13.1 Surfaces

| Surface | Users | Form factor |
|---|---|---|
| Lead journey panel (inside the existing lead page) | Sales, Designer | Workspace (Lit) |
| Property & spaces editor | Sales, Designer | Workspace |
| **Measurement capture** | Surveyor | Mobile-first PWA (same Lit app, installable, offline cache); large touch targets, feet-inch keypad, camera |
| Verification review | Designer, Estimator | Workspace, split view: numbers beside photos |
| Requirement discovery | Designer with customer | Tablet-friendly; one space per screen; swipe confirm/decline |
| Estimation workbench | Estimator | Workspace three-pane: spaces · scope/BOQ lines · pricing; staleness banner |
| Quotation composer | Sales, Sales Manager | Workspace; live document preview; approval checklist |
| Customer quotation page | Customer | Public, mobile-first, brand page; no login; optional-item toggles; accept flow |
| Knowledge dashboards | Founder, Sales Manager | Workspace; win rate by tier/city/property type, quoted vs actual, deviation reasons |

### 13.2 Capture flow (the critical path for adoption)

1. Pick visit → property overview with the space walk order.
2. For each space: shape → principal dimensions → ceiling → walls in clockwise order (length, height defaults, tags) → openings per wall → photos → notes → "mark complete".
3. Running completeness indicator; the summary screen lists incomplete spaces and verification warnings before submit.
4. Works offline; "pending sync" badge; conflicts resolved server-side by `version` (last write wins within one surveyor's set; a second surveyor needs a second DRAFT set).

### 13.3 Trust and transparency cues

- Every quantity in the workbench shows its derivation string from `boq_line.derivation`.
- Every auto item shows the rule that produced it; overrides are visibly marked.
- The customer page shows assumptions explicitly, and labels mandatory vs optional.
- Accessibility follows 09-ui-ux-design tokens; all money via the existing formatter.

## 14. Versioning strategy

| Layer | Mechanism |
|---|---|
| Rows | `version` optimistic concurrency (ADR-003); `If-Match` on every mutation |
| Aggregates | `revision_no` (measurement set, scope, BOQ, cost estimate) or `version_no` (quotation) with `supersedes_*_id`; terminal statuses freeze the row and its children |
| Snapshots | `snapshot_sha256` over canonical JSON at freeze; recomputed on read of frozen rows and compared (tamper evidence, same pattern as `catalog_release.manifest_sha256`) |
| Lineage | Each aggregate stores upstream id **and** upstream revision number; the journey read model computes `is_stale` |
| Configuration | `catalog_release_id` pinned on scope, BOQ, estimate and quotation; `rate_card_id` + `calculation_version` + `quantity_engine_version` pinned; a quotation is reproducible from its pins and the sealed BOQ |
| Schema | `0200` migration block; additive only; CHECKs widened by migration; no renames (roadmap §2) |
| Formula and rule semantics | `quantity_engine_version` bumps on any formula change; old BOQs are never re-derived; regeneration creates a new revision |
| Customer document | `quotation.snapshot` is the only thing the portal renders; the PDF is an attachment with its own sha256 |
| API | `/api/v1` unchanged; new resources only; OpenAPI diff gate in CI |

## 15. RBAC model

### 15.1 Roles (seeded, additive)

| Role | Purpose | Notes |
|---|---|---|
| FOUNDER, ADMIN, SALES | Existing | SALES gains property/visit/requirement/quotation grants with OWN scope |
| **SURVEYOR** | Measurement capture on assigned visits | OWN = `measurement_visit.assigned_to = actor`; no prices anywhere |
| **DESIGNER** | Spaces, requirements, scope, verification | OWN via lead visibility; reads BOQ; no rates |
| **ESTIMATOR** | BOQ review, pricing, adjustments | Sees rates; cannot approve own discounts |
| **SALES_MANAGER** | Approvals, discounts, send overrides, knowledge | ALL scope on the journey |

Code checks permission codes only (06 §3); role names are seed data.

### 15.2 Permission catalog (excerpt)

| Code | Scope? | Sensitive | F | A | SM | S | D | E | SV |
|---|---|---|---|---|---|---|---|---|---|
| `property.read` / `.create` / `.update` | yes | | A | A | A | O | O | O | O (read) |
| `measurement.visit.read` / `.create` / `.schedule` | yes | | A | A | A | O | O | | O (read) |
| `measurement.capture` | yes | | A | A | A | | O | | O |
| `measurement.read` | yes | | A | A | A | O | O | O | O |
| `measurement.verify` | yes | | A | A | A | | O | O | |
| `requirement.read` / `.create` / `.update` | yes | | A | A | A | O | O | O | |
| `scope.read` / `.create` / `.update` | yes | | A | A | A | O | O | O | |
| `scope.confirm` | yes | | A | A | A | | O | O | |
| `boq.read` / `.generate` / `.review` | yes | | A | A | A | O (read) | O | O | |
| `cost_estimate.read` | yes | | A | A | A | O | O | O | |
| `cost_estimate.rate.view` | yes | 🔒 [COMMERCIAL] | A | A | A | | | O | |
| `cost_estimate.create` / `.update` / `.review` | yes | | A | A | A | | | O | |
| `cost_estimate.rate.override` | yes | 🔒 [COMMERCIAL] | A | A | A | | | O | |
| `cost_estimate.margin.view` | no | 🔒 [COMMERCIAL] | ✓ | ✓ | ✓ | | | | |
| `cost_estimate.approve` | yes | | A | A | A | | | | |
| `cost_estimate.discount.approve` | yes | 🔒 [COMMERCIAL] | A | A | A | | | | |
| `quotation.read` / `.create` / `.update` | yes | | A | A | A | O | O | O | |
| `quotation.approve` | yes | 🔒 [COMMERCIAL] | A | A | A | | | | |
| `quotation.send` | yes | | A | A | A | O | | | |
| `quotation.decision.record` | yes | | A | A | A | O | | | |
| `quotation.withdraw` | yes | | A | A | A | | | | |
| `knowledge.read` | no | | ✓ | ✓ | ✓ | | | ✓ | |
| `knowledge.actual.record` | no | | ✓ | ✓ | ✓ | | | ✓ | |
| `ai_suggestion.read` / `.decide` | yes | | A | A | A | O | O | O | |
| `mtq.config.manage` (templates, rules, formulas via catalog) | no | 🔒 [CONFIG] | ✓ | ✓ | | | | | |

Sensitive codes require MFA (ADR-006). Discount limits use the roadmap's `permission_limit` table (P3): `cost_estimate.discount.approve` with `limit_bp` per role; above the limit, FOUNDER approval through the existing `admin_approval_request` flow.

### 15.3 Scope resolution additions

| Resource | Actor owns a row when |
|---|---|
| `property`, `requirement`, `scope`, `boq`, `cost_estimate`, `quotation` | Parent lead visible under `lead.read` (child visibility rule) |
| `measurement_visit` | `assigned_to = actor` or parent lead visible |
| `measurement_set` | `captured_by = actor` or visit owned or parent lead visible |

Public portal requests carry no principal; they are scoped by token to one quotation version.

---

# PHASE 3 — Implementation roadmap

Each block ends with the repo's usual gates: independent review package, staging evidence, owner decision record, feature flag default off in production. Flags: `VEDA_MTQ_SITE_ENABLED`, `VEDA_MTQ_ESTIMATION_ENABLED`, `VEDA_MTQ_QUOTATION_ENABLED`, `VEDA_MTQ_PORTAL_ENABLED`, `VEDA_MTQ_KNOWLEDGE_ENABLED`, `VEDA_MTQ_AI_ENABLED`. Requirement id prefixes: `PROP-`, `MEAS-`, `REQ-`, `SCOPE-`, `BOQ-`, `CEST-`, `QUOT-`, `KNOW-`.

## 16. Block plan

### B1 — Measurement Foundation

| Item | Content |
|---|---|
| Prerequisite | **ATT module** (`0106_attachment`, polymorphic, S3 with pre-signed URLs, reusing the catalog media scanner path) |
| Migrations | `0200_mtq_site`: `property`, `property_space`, `measurement_visit`, `measurement_set`, `space_measurement`, `space_wall`, `space_opening`, `measurement_note`; lookups `SPACE_TYPE`, `OPENING_TYPE`, `MEASUREMENT_METHOD`, PROPERTY_TYPE additions; sequences `PROPERTY`, `MEASUREMENT` |
| Catalog | `space_template` kind + schema; first templates for apartment, villa, office |
| Services | Property tree, derived counts, visit state machine, set revisions, derivation engine (§6.3), verification checks, offline sync endpoint, lead sync (`SITE_VISIT`) |
| UI | Property editor; capture PWA; verification review; journey panel v1 |
| RBAC | SURVEYOR and DESIGNER roles; `property.*`, `measurement.*` |
| Validation gate | 10 real sites measured in parallel with the current method; dimension agreement within tolerance (**Owner input**: tolerance, proposal ±1 % floor area); surveyor time per site recorded as the baseline |
| Exit | Flag `VEDA_MTQ_SITE_ENABLED` on in staging; evidence package; decision record |

### B2 — Scope & BOQ Engine

| Item | Content |
|---|---|
| Migrations | `0201_mtq_estimation` (part 1): `requirement`, `scope`, `scope_item`, `scope_item_option`, `boq`, `boq_line`; lookups `REQUIREMENT_TYPE`, `UOM`, `FINISH`, `TIER` |
| Catalog | `scope_rule` and `quantity_formula` kinds; initial rule groups for bedroom, kitchen, living, toilet, study, commercial generic; formulas for every ADR-012 line plus the new area kinds; release validation extended (every product has formulas for all its lines; rules reference existing products) |
| Services | Requirement seeding (templates, public estimate); rule engine with recorded runs; quantity engine with rounding and wastage; room-wise and project BOQ; revision diff |
| UI | Discovery flow; estimation workbench (spaces · scope · BOQ) |
| Validation gate | Replay the E6 historical quotations: regenerate scope and BOQ from their recorded measurements; quantity agreement per line within tolerance (**Owner input**; proposal ±5 %); manual override rate tracked |
| Exit | `VEDA_MTQ_ESTIMATION_ENABLED` (scope/BOQ only) in staging |

### B3 — Estimate Engine

| Item | Content |
|---|---|
| Migrations | `0201` (part 2): `cost_estimate`, `cost_estimate_line`, `cost_estimate_adjustment`, `estimator_rate_item_finish`; `permission_limit` (roadmap P3) |
| Engine | Opaque space labels; `finish_code` rate dimension; project-line drivers; BOQ-fed pricing; per-line GST; adjustments; variance vs public estimate |
| Catalog | `pricing.finish_rates`; compiler writes finish variants; card validation for finish completeness |
| Rate data | Premium and Luxury rates loaded for staff use (**Owner input**: the Premium/Luxury rate sheets; D1/D2 public rules unchanged) |
| RBAC | ESTIMATOR and SALES_MANAGER roles; `cost_estimate.*`; discount limits (**Owner input**) |
| Validation gate | Price the replayed E6 quotations with the card in force at their date; total within tolerance (**Owner input**; proposal ±3 %); every deviation explained as rate, quantity or scope |
| Exit | Full `VEDA_MTQ_ESTIMATION_ENABLED` in staging |

### B4 — Quotation Intelligence

| Item | Content |
|---|---|
| Migrations | `0202_mtq_commercial`: `quotation`, `quotation_section`, `quotation_line`, `quotation_exclusion`, `quotation_term`, `quotation_event`, `quotation_decision`; sequence `QUOTATION`; lookup `EXCLUSION`; `0203_mtq_knowledge`: `knowledge_quotation_outcome`, `knowledge_execution_actual`, `knowledge_deviation`, `knowledge_estimation_feature`, `knowledge_rate_observation` |
| Services | Composer, approval, four-eyes, send (freeze, PDF, token, lead sync, notifications), expiry job, versions, decisions, public portal endpoints, knowledge projector (outbox subscriber), manual execution-actual entry |
| Documents | PDF renderer from `snapshot` with governed copy; versioned terms (**Owner input**: terms text, payment schedule, validity days, GST treatment, reminder cadence, whether unit rates may ever be shown) |
| UI | Quotation composer with live preview; customer page; knowledge dashboards v1 (win rate, cycle time, quoted vs actual once actuals exist) |
| Validation gate | Side-by-side with the workbook on 10 live leads: preparation time (target: from hours to under 60 minutes after verification), zero arithmetic differences, customer page usability check; legal review of terms and acceptance flow recorded |
| Exit | `VEDA_MTQ_QUOTATION_ENABLED` and `VEDA_MTQ_PORTAL_ENABLED` in staging, then production activation by owner decision |

### B5 — AI Recommendation Foundation

| Item | Content |
|---|---|
| Prerequisite | PostgreSQL release gate passed (pgvector); ≥ 100 quotations with outcomes in the knowledge store (**Owner input**: threshold) |
| Migrations | `ai_suggestion`; `knowledge_estimation_feature.embedding` populated |
| Capabilities (in order) | 1. **Rule calibration reports**: where manual overrides cluster (rule, space type, property type) → proposed rule changes as catalog DRAFTs for review. 2. **Missing-item suggestions**: items usually quoted together for this space mix but absent from the scope. 3. **Dimension sanity**: flag measurements outside learned distributions per space type. 4. **Rate and discount risk**: acceptance probability by tier/city/discount from `knowledge_rate_observation`. 5. **Similar past projects**: embedding search over feature snapshots to show comparable accepted quotations beside the workbench |
| Guardrails | AI identity `AI_ASSISTANT` as a principal (roadmap); suggestions only, never business writes; every accepted suggestion is a normal audited user action; PII stripped from any external model call; model version pinned on each suggestion |
| Validation gate | Suggestion acceptance rate and measured effect on override count and quotation cycle time over one quarter |
| Exit | `VEDA_MTQ_AI_ENABLED` per capability |

## 17. Dependencies and sequencing

```
ATT ──► B1 ──► B2 ──► B3 ──► B4 ──► B5
                 ▲             ▲      ▲
      Catalog V3 active ───────┘      │
      (templates, rules, formulas,    │
       pricing finish variants)       │
                                      PostgreSQL gate + CUST/PROJ (actuals) ─┘
```

B1 can start as soon as ATT lands; B2–B4 need Catalog V3 admin to be active for templates, rules and formulas (today `catalog_admin_enabled` is off in production). CUST and PROJ are not prerequisites: `property.customer_id` and execution actuals are additive when those modules arrive.

## 18. Owner inputs register

| # | Input | Needed by |
|---|---|---|
| OI-MTQ-01 | Measurement tolerance for B1 validation | B1 |
| OI-MTQ-02 | Space templates and survey checklists per property type (confirm the proposed lists) | B1 |
| OI-MTQ-03 | Scope rule content per space category; what is "recommended" vs "always" | B2 |
| OI-MTQ-04 | Quantity rounding, wastage factors, clearances | B2 |
| OI-MTQ-05 | Premium and Luxury rate sheets for staff pricing; finish-variant rates | B3 |
| OI-MTQ-06 | Discount authority limits per role; four-eyes threshold | B3 |
| OI-MTQ-07 | GST treatment on quotations (single rate vs per-line) | B3 |
| OI-MTQ-08 | Quotation validity days, reminder cadence, expiry behaviour | B4 |
| OI-MTQ-09 | Commercial terms text, payment schedule milestones, warranty summary wording (legal review) | B4 |
| OI-MTQ-10 | Whether unit rates may ever be shown to customers | B4 |
| OI-MTQ-11 | Customer acceptance mechanism (portal click vs signed copy) and its legal standing | B4 |
| OI-MTQ-12 | Knowledge thresholds and which AI capabilities to enable first | B5 |

## 19. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Surveyors reject the app for paper | Offline-first, feet-inch keypad, photo-per-wall, under 20 minutes per space target measured in B1 |
| Rules over-generate scope and erode trust | Every auto item shows its rule; override reasons feed calibration; rules ship as catalog DRAFTs reviewed by the owner |
| Rate card lacks finish variants and staff price manually | `RATE_UNRESOLVED` surfaces gaps; manual rates need a reason and a permission; release validation checks finish completeness |
| Quotation differs from the workbook during transition | B4 side-by-side gate with zero arithmetic difference before activation |
| Lineage becomes stale silently | `is_stale` on the journey read model; send refuses without an override |
| SQLite single-writer under offline batch sync | Batches are small per set; PostgreSQL gate precedes B5; sync endpoint is idempotent and retryable |
| PII in snapshots and portal | Snapshot anonymised with the lead; tokens hashed; events store IP hashes only |

## 20. Validity check against the required project types

| Type | Property | Spaces | Scope rules | BOQ | Estimate | Quotation |
|---|---|---|---|---|---|---|
| 2 BHK | APARTMENT, label "2 BHK" | 2 bedrooms via `instance_no` | residential groups | same formulas | drivers: bedroom_count, floor_area | same document |
| 3 / 4 / 5 BHK | same | more instances | same | same | same | same |
| Duplex | DUPLEX, 2 levels | `level_index` 0/1, STAIRCASE | same + staircase rules | same | FLOOR_FACTOR adjustment | same |
| Villa | VILLA, plot area | outdoor spaces, external walls | villa group adds porch/garden | same | level_count driver | same |
| Independent house | INDEPENDENT_HOUSE | any | same as villa | same | same | same |
| Commercial | OFFICE/RETAIL/CLINIC, usage COMMERCIAL | commercial space types | commercial groups | same formulas (workstations as `count`, partitions as `area_wh`) | commercial card lines, per-line GST | commercial copy and terms via release |
| Custom | any type, `PARTIAL`, CUSTOM spaces | CUSTOM with labels | generic group, manual items | same | manual rates with reasons where needed | assumptions listed |

No row above needs a new column or table. New kinds of work need new lookup values, catalog records and rate lines, which are data under the existing release governance.
