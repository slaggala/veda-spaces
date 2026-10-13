# MTQ B1 — Measurement Foundation: final scope (proposed freeze)

**Status:** RECORDED AS FROZEN on 2026-10-13 by [MTQ-B1-blocker-closure.md](MTQ-B1-blocker-closure.md) (frozen-scope reference d4f14c3 plus the Δ values in closure §6); the §6 blocker table below is superseded by closure §8. Documentation only; binds on the owner's approval of PR #85.
**Instruction:** `VEDA-SPACES-MTQ-B1-SCOPE-FREEZE` (2026-10-13).
**Inputs:** [MTQ-BLUEPRINT.md](MTQ-BLUEPRINT.md) (PR #83) · survey and scope templates (PR #84, branch `docs/mtq-survey-scope-templates` at e7e319d) · the architecture review verdict "READY WITH REQUIRED CHANGES" and the business-reality review, **both reported by the owner and not recorded on either PR** · the owner-decisions workshop of 2026-10-13 (recommended defaults, **none recorded in [MTQ-owner-decisions.md](MTQ-owner-decisions.md) yet**).
**Supersedes:** blueprint §16 B1 where the two differ. Everything else in the blueprint stands.
**Review intake:** the business-reality review's "required before B1" list (2026-10-13, session record, not posted on the PRs) is addressed item by item in §2.9 and §5; the items that bind B2–B4 are listed in §6.

---

## 1. B1 final scope

**Purpose.** Replace paper site measurement with a verified, revisioned, photo-backed measurement set for residential properties, ready for scope generation in B2. B1 produces no scope, BOQ, estimate or quotation.

### 1.1 Supported in B1

| Dimension | In B1 | How |
|---|---|---|
| Configurations | 2 BHK, 3 BHK, 4 BHK, 5 BHK | Property templates seed the space tree; BHK is `configuration_label` plus `derived_bedroom_count` |
| Property types | Apartment, independent house | `PROPERTY_TYPE` values already seeded; independent house uses `level_index` 0..n and `STAIRCASE` spaces |
| Survey levels | **Lite survey**, **Full survey** | `measurement_set.survey_level_code` (§2.3) |
| Staircases | Internal staircases in independent houses (and any apartment with one) | `STAIRCASE` space type with typed measurement attributes (§2.4) |
| Electrical capture | Light, fan, socket, switchboard, AC and DB points; **sensor lights**; **point shifting** (existing → new position) | `space_electrical_point` (§2.5) |
| Kitchen | Base, wall, loft runs and **tall units** (fridge niche, appliance tower, pantry pull-out) | `TALL_UNIT` wall tag, `NICHE` openings with `purpose_code`, `floor_to_lintel_mm` (§2.6) |
| Photos, sketches, floor plans | Per property, space, wall, opening, electrical point and note | Attachments module (ATT) with the scaling strategy in §2.8 |
| Verification | Designer or estimator verifies; four-eyes; fail-closed checks | Blueprint §6.2 plus the Full-survey rules in §2.3 |
| Lead integration | Visit scheduling moves the lead to `SITE_VISIT`; a system activity per visit | Blueprint §12.3 |
| Offline capture | Mobile PWA, batch sync, `client_ref` idempotency | Blueprint §6.1, §11.1 |
| Variation quotation model | **Defined and frozen in B1; implemented in B4** (§2.7). B1 guarantees the identity rules it needs | `property_space` ids stable across measurement revisions; `space_measurement` rows keyed by space |

### 1.2 Deferred from B1 (explicit)

| Deferred | To | Reason |
|---|---|---|
| Commercial properties (office, retail, clinic, hospitality) and the commercial `SPACE_TYPE` values | B2+ (owner call) | No commercial rule groups, card lines or terms exist; the schema already allows them |
| Duplex, villa, penthouse, row house templates | B2 | Data model supports them (levels, outdoor zones); templates and validation deferred to keep B1 validation to two property types |
| Requirement discovery, scope, BOQ | B2 | As in the blueprint |
| Cost estimate, rate-card finish variants, discount limits, GST | B3 | OI-MTQ-05/06/07 |
| Quotation, variation quotations, terms, customer portal | B4 | OI-MTQ-08…11; portal explicitly deferred |
| Project lifecycle, procurement, execution actuals | PROJ / PROC modules | Not MTQ |
| AI suggestions, knowledge store, embeddings | B5 | PostgreSQL gate |
| Catalogue-held `space_template` records | B2 | Catalogue V3 admin is not active; B1 ships templates as code fixtures (§4.4) |
| Lite-survey-to-revised-budget-estimate | B1.5 (optional, not in the freeze) | Needs an engine input change; valuable but not required for B2 |

### 1.3 Out of scope by rule

No change to V1, V2 or V3 estimator behaviour, to pricing, to `budget_estimate` tables, to the public site, or to any production flag. `VEDA_MTQ_SITE_ENABLED` defaults to false everywhere; every MTQ route answers 404 while it is off.

---

## 2. Included entities (B1 schema, frozen)

All tables carry the nine audit columns (ADR-003), UUIDv7 ids (ADR-002), `version`, soft delete, `ON DELETE RESTRICT`. Columns are as in the blueprint §4.1 **plus** the additions marked **B1+** below. No column in §4.1 is removed.

### 2.1 Table list

| # | Table | Change vs blueprint | Audit |
|---|---|---|---|
| 1 | `attachment` (ATT) | New module, migration `0106` (§4.1) | FULL |
| 2 | `property` | as §4.1 | FULL |
| 3 | `property_space` | as §4.1; **B1+** `template_version` VARCHAR(20) NULL (code-fixture version that seeded it) | FULL |
| 4 | `measurement_visit` | as §4.1; **B1+** `survey_level_code` CODE(10) NOT NULL (`LITE` / `FULL`), planned level for the visit | FULL |
| 5 | `measurement_set` | as §4.1; **B1+** `survey_level_code` CODE(10) NOT NULL; `property_capture` JSON NOT NULL default `{}` (property-level items: main door, lift, staircase width, DB location, access) | FULL |
| 6 | `space_measurement` | as §4.1; **B1+** `attributes` JSON NOT NULL default `{}`, validated per space type (staircase geometry, L-shape legs, AC and fan counts); **B1+** `captured_by` GUID FK → `app_user` NOT NULL (per-space author for two-surveyor sets) | EVENT_ONLY |
| 7 | `space_wall` | as §4.1; `usable_for_code` vocabulary frozen (§2.6) | EVENT_ONLY |
| 8 | `space_opening` | as §4.1; **B1+** `purpose_code` CODE(20) NULL (`FRIDGE`, `APPLIANCE`, `STORAGE`, `WASH`, `OTHER`) for `NICHE`; **B1+** `depth_mm` MM NULL (niche and recess depth); `is_existing` BOOL NOT NULL default true | EVENT_ONLY |
| 9 | **`space_electrical_point`** | **New table** (§2.5) | EVENT_ONLY |
| 10 | `measurement_note` | as §4.1; `note_type_code` adds `RISK_ACK` (verifier acknowledgement) | FULL |

Lookups added: `SPACE_TYPE` (residential subset only in B1 seed: LIVING, DINING, LIVING_DINING, FAMILY_LOUNGE, FOYER, PASSAGE, STAIRCASE, POOJA, MASTER_BEDROOM, BEDROOM, CHILDREN_BEDROOM, GUEST_BEDROOM, PARENTS_BEDROOM, SERVANT_ROOM, DRESSING, WALK_IN_CLOSET, TOILET, POWDER_ROOM, STUDY, HOME_OFFICE, MEDIA_ROOM, KITCHEN, UTILITY, STORE, LAUNDRY, BALCONY, TERRACE, SIT_OUT, PORCH, PARKING, GARDEN, CUSTOM), `OPENING_TYPE`, `MEASUREMENT_METHOD`, `ELECTRICAL_POINT_TYPE`, `SENSOR_TYPE`, `WALL_TAG`. Sequences: `PROPERTY`, `MEASUREMENT`. Permissions: `property.*`, `measurement.*`, `attachment.*`. Roles: `SURVEYOR`, `DESIGNER`.

### 2.2 Property templates shipped in B1

`APARTMENT_2BHK`, `APARTMENT_3BHK`, `APARTMENT_4BHK`, `APARTMENT_5BHK`, `INDEPENDENT_HOUSE` (PR #84 02 §1–§4, §7), plus the fourteen residential space-type templates (PR #84 01) as code fixtures, `template_version 2026.10.1`. Duplex, villa and commercial templates are present in PR #84 but **not shipped** in B1 fixtures.

### 2.3 Lite survey and Full survey

| | Lite survey | Full survey |
|---|---|---|
| Purpose | Qualify the lead and tighten the budget band before design effort; 45–60 minutes | Quotation-ready measurement; 3–6 hours |
| Per space | Shape, L, W, ceiling height, `confidence_code`, one overview photo, furniture walls tagged with **length only** | **Trimmed Full capture:** every wall with length, height and tags; openings with offsets and swing, obstructions, electrical points and photos **REQ only on tagged furniture walls** and on walls whose door or window bounds a tagged wall; untagged walls carry length and height only; one overview photo per space; ceiling points per space |
| Property-level | Floor, lift availability, access notes | Full `property_capture` (PR #84 02 §0) |
| Completeness rule | Space complete when L, W, CH and one photo exist | Space complete when PR #84 00 §5 REQ and COND items hold |
| Verification | `VERIFIED` allowed; sets `summary.survey_level = LITE` | `VERIFIED` requires the §6.2 fail-closed checks plus: every in-scope space has ≥ 1 tagged furniture wall with obstructions captured or an explicit "none" marker |
| Downstream (B2+) | A scope may be **generated** from a LITE set for indicative purposes but **cannot be CONFIRMED**; `pricing_basis_code` can only be `TYPICAL`/`MIXED` | Scope may be CONFIRMED; `pricing_basis_code = MEASURED` |
| Revision rule | A FULL set supersedes any LITE set for the property; a LITE set never supersedes a FULL set | — |
| Who | Sales or surveyor | Surveyor; two surveyors on **one** DRAFT set with disjoint spaces for multi-level houses (§2.9.3) |

`survey_level_code` lives on both the visit (planned) and the set (actual); a set may be upgraded from LITE to FULL only by a new revision.

### 2.4 Staircase support

`STAIRCASE` is a space with `zone_code = INDOOR`, `level_index` = the lower level, and `space_measurement.attributes` validated by the staircase schema:

| Attribute | Type | Required |
|---|---|---|
| `from_level`, `to_level` | INTEGER | REQ |
| `turn_type_code` | `STRAIGHT` / `L` / `U` / `SPIRAL` / `CUSTOM` | REQ |
| `flight_count` | INTEGER | REQ |
| `run_length_mm`, `width_mm` | MM | REQ |
| `riser_count`, `riser_height_mm`, `tread_depth_mm` | INTEGER, MM, MM | REQ |
| `headroom_mm` | MM | REQ (RISK when < 2 000) |
| `landing_l_mm`, `landing_w_mm` | MM | COND (turn_type ≠ STRAIGHT) |
| `under_stair_void` | `{ l_mm, w_mm, h_mm }` | optional |
| `largest_panel_mm` | MM | REQ (material movement; RISK when < 900) |
| `handrail_wall_index` | INTEGER | optional (feature-wall treatment) |

Walls of the stairwell are ordinary `space_wall` rows (tag `FEATURE_WALL` for panelling or wallpaper). The derivation engine computes `derived_floor_area` for a staircase as `run_length × width` and excludes it from bedroom and toilet counts. Independent-house templates seed one `STAIRCASE` per level transition.

### 2.5 Electrical capture: `space_electrical_point`

| Column | Type | Notes |
|---|---|---|
| `space_measurement_id` | GUID FK | |
| `space_wall_id` | GUID FK NULL | NULL for ceiling points |
| `point_type_code` | CODE(20) | Lookup `ELECTRICAL_POINT_TYPE`: `LIGHT_POINT`, `SENSOR_LIGHT`, `FAN_POINT`, `SWITCHBOARD`, `SOCKET_5A`, `SOCKET_15A`, `AC_POINT`, `DB_BOX`, `TV_POINT`, `DATA_POINT`, `GEYSER_POINT`, `EXHAUST_POINT`, `CHIMNEY_POINT`, `APPLIANCE_POINT`, `PROFILE_LIGHT_FEED`, `CUSTOM` |
| `status_code` | CODE(10) | `EXISTING` (as found) · `SHIFT` (existing point moves) · `NEW` (additional point) · `REMOVE` |
| `from_offset_mm`, `from_height_mm` | MM NULL | Current position along the wall and from floor (ceiling points: x/y from the entry corner) |
| `to_wall_id` | GUID FK NULL | Target wall for `SHIFT` |
| `to_offset_mm`, `to_height_mm` | MM NULL | Target position for `SHIFT` and `NEW` |
| `sensor_type_code` | CODE(10) NULL | `PIR`, `MICROWAVE`, `NONE`; required for `SENSOR_LIGHT` |
| `switching_code` | CODE(10) NULL | `SENSOR`, `MANUAL`, `BOTH` |
| `location_code` | CODE(20) NULL | `CEILING`, `WALL`, `IN_WARDROBE`, `UNDER_CABINET`, `FOYER_ENTRY`, `TOILET`, `STAIRCASE` (sensor strips and step lights) |
| `quantity` | INTEGER NOT NULL default 1 | For identical points on one run (for example 4 spots) |
| `reason_code` | CODE(20) NULL | `FURNITURE_CLASH`, `CEILING_DESIGN`, `CUSTOMER_REQUEST`, `SAFETY` |
| `notes`, `attachment_id` | TEXT, GUID NULL | Photo of the existing point |

Rules: a `SHIFT` row needs both from- and to-positions; a `NEW` row needs a to-position; wall obstructions of kind `SWITCHBOARD`/`DB_BOX` and the matching electrical point are linked by the same offset (the capture UI creates both). Counts by `(point_type_code, status_code)` per space are the inputs to the B3 `ELECTRICAL.*` count lines; B1 stores them only.

### 2.6 Kitchen tall-unit support and the frozen wall-tag vocabulary

`WALL_TAG` lookup (values of `space_wall.usable_for_code`), **frozen in B1 because B2 scope rules key on them**:
`WARDROBE`, `LOFT`, `BED_HEAD`, `TV_UNIT`, `STUDY_UNIT`, `CROCKERY_UNIT`, `KITCHEN_RUN`, `KITCHEN_WALL_RUN`, `TALL_UNIT`, `VANITY`, `SHOE_RACK`, `POOJA_UNIT`, `FEATURE_WALL`, `WINDOW_SEATING`, `STORAGE_WALL`, `PARTITION_EDGE`, `NONE`.

Kitchen capture for tall units: the `TALL_UNIT` tag on the wall stretch, the fridge niche as a `NICHE` opening with `purpose_code = FRIDGE` and `depth_mm`, `floor_to_lintel_mm` captured in every kitchen, and the appliance list as a `CUSTOMER_REQUEST` note. The `KITCHEN_TALL_UNIT` product and card line are a B3 addition (PR #84 marks it NEW LINE); B1 only guarantees the measurements exist.

### 2.7 Variation quotation model (frozen design, implemented in B4)

Two kinds of variation, one lineage:

| Kind | When | Model | Identity rule B1 must honour |
|---|---|---|---|
| **Alternatives** (Option A / Option B) | Before acceptance | Sibling `quotation` rows share `variant_group_id` and carry `variant_label`; each binds its own `cost_estimate` (different tier, finishes, options) over the same `scope` revision or sibling scope revisions. The customer accepts one; siblings become `SUPERSEDED` | Space ids are the join key across sibling scopes |
| **Variations** (change orders) | After acceptance, before or during execution | `quotation.quotation_kind = VARIATION`, `variation_of_quotation_id` → the accepted base; lines are **deltas** (`ADD`, `OMIT`, `CHANGE`) computed from the scope diff by `(space_id, carried_from_item_id, line_code)`; accepted value = base + Σ accepted variations; `lead.quoted_amount_minor` tracks the sum | `scope_item.carried_from_item_id` (B2) and stable `property_space.id` across measurement revisions (B1) |

B1 commitments: `property_space.id` never changes across measurement revisions (a re-measure writes new `space_measurement` rows for the same space); deleting a space soft-deletes it and keeps the id; `space_measurement` diff between revisions is keyed by `space_id`. Nothing else in B1 is needed.

### 2.8 Attachment scaling strategy (ATT, B1)

| Concern | Decision |
|---|---|
| Volume | A full 3 BHK survey is ~120–200 photos; at 2–4 MB each that is 0.5–0.8 GB raw. Target ≤ 100 MB per survey after client-side scaling |
| Client scaling | The PWA downsizes to 2048 px long edge, JPEG quality 80 (~400–700 KB), applies EXIF orientation, strips all other EXIF (GPS included), and generates a 256 px thumbnail locally for the capture UI |
| Upload path | Direct-to-S3 with a pre-signed PUT per object (API never proxies bytes); `sha256` computed on device and verified server-side; duplicate hashes reuse the object |
| Server processing | The catalogue media pipeline (Pillow re-encode, variants 256 / 1024, content-hash keys) reused as a library; variants generated asynchronously; the source is retained |
| Scanning | The deployed ClamAV path; objects stay `PENDING_SCAN` and are not shown to verifiers until `CLEAN`; `INFECTED` objects are quarantined and the set cannot be verified while any infected object is attached |
| Storage | A separate private bucket per environment (`veda-attachments-<env>`), never public, SSE-KMS, TLS-only policy, bucket-owner-enforced; Intelligent-Tiering after 90 days; versioning on with a 30-day noncurrent expiry |
| Limits | 15 MB per object, 6 photos per wall (soft), 400 objects and 1 GB per measurement set (hard) |
| Offline | Photos queue in IndexedDB with a quota check before capture; resumable batch upload; the sync endpoint accepts metadata before bytes so a set can be `SUBMITTED` with uploads still draining, but cannot be `VERIFIED` until all are `CLEAN` |
| Retention and PII | Survey photos may show people and documents; attachments on a lead's property follow the lead-retention job (OWNER-INPUT-002): deleted, not anonymised. Floor plans supplied by customers are `visibility = INTERNAL` |
| Polymorphism | `attachment.entity_type` ∈ {`property`, `property_space`, `measurement_set`, `space_wall`, `space_opening`, `space_electrical_point`, `measurement_note`} in B1; permissions evaluated against the parent lead's visibility |
| Cost | ~50 surveys/month × 100 MB ≈ 5 GB/month; negligible against the existing media budget |

### 2.9 Capture rules added from the business-reality review

**2.9.1 L-shape geometry.** `shape_code = L_SHAPE` stores two rectangular legs in `attributes.l_shape = { turn_code: LEFT | RIGHT, leg_a: { l_mm, w_mm }, leg_b: { l_mm, w_mm } }`, where leg A contains the entry (or W1) and the turn is read standing at W1 facing into the room. Derived floor area = leg A + leg B; perimeter and wall areas come from the six walls, which must be entered individually. Verification fails when the six wall lengths do not close within 50 mm of the leg dimensions.

**2.9.2 W1 convention for door-less spaces.** Where a space has no door (open living/dining, foyer continuing into a passage, open kitchen), W1 is the first solid wall clockwise from the OPEN edge through which the surveyor entered, and the OPEN edge is recorded as a `space_wall` with `wall_type_code = OPEN` and `wall_index` 0. A space with several OPEN edges records all of them; the derivation engine excludes OPEN edges from wall area and includes them in perimeter.

**2.9.3 Two-surveyor policy.** One DRAFT `measurement_set` per revision. Surveyors claim spaces: `space_measurement.captured_by` is set on first write and only that user (or the set's `captured_by` lead surveyor) may edit the space until submission. A write to a space claimed by someone else returns 409 `SPACE_CLAIMED`. Submission is by the lead surveyor once every in-scope space is complete. There is no merge step; the verifier sees one set with per-space authorship.

**2.9.4 Driver rules.** `derived_bedroom_count` counts spaces whose type has `counts_as_bedroom = true`; `SERVANT_ROOM`, `GUEST_SUITE` and `STUDY` are **not** bedrooms for the preparation-package driver, and `MASTER_BEDROOM`, `BEDROOM`, `CHILDREN_BEDROOM`, `GUEST_BEDROOM`, `PARENTS_BEDROOM` are. `derived_level_count` counts distinct `level_index` values among in-scope spaces, so a terrace-only upper level still counts as a level. The card today keys the preparation package by 1BHK–4BHK plus CUSTOM; a 5 BHK amount and the driver choice are owner input OI-MTQ-15 (B3). B1 only guarantees the counts exist.

**2.9.5 Niche depth.** `space_opening.depth_mm` is REQ for `NICHE`, optional otherwise.

---

## 3. Deferred entities

Not created in B1 (the blueprint keeps their design): `requirement`, `scope`, `scope_item`, `scope_item_option`, `boq`, `boq_line`, `cost_estimate`, `cost_estimate_line`, `cost_estimate_adjustment`, `estimator_rate_item_finish`, `permission_limit`, `quotation`, `quotation_section`, `quotation_line`, `quotation_exclusion`, `quotation_term`, `quotation_event`, `quotation_decision`, `knowledge_*`, `ai_suggestion`, `customer`, `project`, catalogue kinds `space_template`, `scope_rule`, `quantity_formula`. Roles `ESTIMATOR` and `SALES_MANAGER` are seeded in B3, not B1.

---

## 4. Migration strategy

| Step | Migration | Contents | Rollback |
|---|---|---|---|
| 1 | `0106_attachment` | `attachment` table; permissions `attachment.read/create/delete`; lookup `ATTACHMENT_CATEGORY` | Drop table; additive only |
| 2 | `0200_mtq_site` | Tables 2–10 of §2.1; CHECK constraints; partial unique indexes; lookups and values (`SPACE_TYPE`, `OPENING_TYPE`, `MEASUREMENT_METHOD`, `ELECTRICAL_POINT_TYPE`, `SENSOR_TYPE`, `WALL_TAG`, PROPERTY_TYPE additions); sequences `PROPERTY`, `MEASUREMENT`; permission registry sync; roles `SURVEYOR`, `DESIGNER` | Drop the ten tables; soft-delete the permission codes; lookups stay (harmless) |
| 3 | — | **No change to any existing table.** `catalog_record.kind` is not widened in B1 (§4.4) | — |

### 4.1 Rules

- Both engines (SQLite authoritative, PostgreSQL gate) in CI, as today; the nine-column conformance check runs on every new table.
- `MM` columns are INTEGER; `CENTI` columns INTEGER; `JSON` columns validated by pydantic schemas keyed by space type (`attributes`) and by `point_type_code` (electrical points).
- Lookup seeds go through `migration_support` like the existing categories; no seed is ever edited in place, only added.
- Flag `VEDA_MTQ_SITE_ENABLED` gates routes and the UI module; the migration runs regardless of the flag (tables are inert).
- Reserved and untouched in B1: `0201_mtq_estimation`, `0202_mtq_commercial`, `0203_mtq_knowledge`.

### 4.2 Data migration

None. There is no existing measurement data to import. Paper surveys taken before B1 are not back-filled; a property measured on paper gets a `PLAN_DRAWING` LITE set keyed in by staff if a quotation later needs it.

### 4.3 Forward compatibility checks (the B2–B4 columns B1 must not block)

`property.customer_id` (CUST), `scope.measurement_set_id` → `measurement_set.id`, `scope_item.dimensions.anchor_wall_id` → `space_wall.id`, electrical counts → B3 `ELECTRICAL.*` lines, `quotation.variant_group_id` / `variation_of_quotation_id` (B4). All are additive FKs onto B1 ids; none needs a B1 column.

### 4.4 Templates as code fixtures (tracked deviation)

Blueprint §5.2 holds space templates as Catalogue V3 records. Catalogue administration is not active, so B1 ships the residential templates as versioned JSON fixtures in the API module, read-only, with `template_version` recorded on each seeded space. B2 migrates them into `space_template` records (expand → migrate → contract: records added, fixtures retired after one release). This is recorded as a deviation so the reviewer can object.

---

## 5. Owner decisions frozen

**Recorded in the register today: none.** The table below separates what this freeze proposes as B1 values from what must be written into [MTQ-owner-decisions.md](MTQ-owner-decisions.md) by the owner before gate MTQ-G3 can pass.

| Decision | Proposed B1 value | Register status |
|---|---|---|
| OI-MTQ-01 measurement tolerance | ±1 % floor area per space; ±25 mm per wall; B1 validation on 10 real sites, 5 apartments and 5 independent houses | **Blank** — needed for G3 |
| OI-MTQ-02 templates and checklists | PR #84 content accepted as `template_version 2026.10.1` for the five residential property templates and fourteen space types; duplex, villa, commercial withheld | **Blank** — needed for G3 |
| B1-01 (new) supported scope | 2–5 BHK apartments and independent houses; everything else deferred per §1.2 | **Proposed here** |
| B1-02 (new) survey levels | LITE and FULL as in §2.3; only FULL is quotation-ready | **Proposed here** |
| B1-03 (new) electrical capture | `space_electrical_point` with sensor and shift semantics as in §2.5 | **Proposed here** |
| B1-04 (new) wall-tag vocabulary | The seventeen `WALL_TAG` values in §2.6, frozen for B2 rules | **Proposed here** |
| B1-05 (new) attachment limits and retention | §2.8: 15 MB/object, 400 objects and 1 GB per set, 2048 px client scaling, delete-on-lead-retention | **Proposed here** |
| B1-06 (new) templates as fixtures | §4.4 deviation accepted for B1 | **Proposed here** |
| OI-MTQ-03/05/06/07/09 | Workshop defaults of 2026-10-13 | **Blank** — not B1 blockers; needed for B2–B4 |
| OI-MTQ-13…17 (new, from the business-reality review) | Variation policy, provisional sums, preparation-package drivers (incl. 5 BHK), design-stage linkage, commercial go/no-go | **Added to the register as blank rows** in this freeze; none blocks B1 |

Workshop decisions do not change any B1 table. The one workshop consequence inside B1 is B1-04 (the wall-tag vocabulary).

---

## 6. Remaining blockers

| # | Blocker | Gate | Owner action |
|---|---|---|---|
| 1 | The architecture and business-reality review findings exist only as a session record; they are not posted on PR #83 or #84, so they cannot be formally dispositioned. The B1 items are addressed in §2.9; the B2–B4 items (PROJECT_ALLOWANCE range contradicting §9.4, card line labels in PR #84, GST on part of the value, commercial partition double count) are not | MTQ-G1 | Post the findings on the PRs; author dispositions each in a remediation matrix |
| 2 | OI-MTQ-01 and OI-MTQ-02 blank | MTQ-G3 | Record the two values (proposed above) in the register with date and instruction |
| 3 | B1-01…B1-06 are proposed, not recorded | MTQ-G2 | Record them with this document's commit SHA as the frozen-scope reference |
| 4 | Migration range `0106`, `0200`–`0203` not approved | MTQ-G4 | Decision-log entry |
| 5 | Historical replay criteria not approved, and the E6 set is three 3 BHK quotations (two in one building), which cannot validate 2, 4 or 5 BHK or independent houses | MTQ-G5 | Approve ±5 % quantity / ±3 % total or other values, and widen the replay set to at least one 2 BHK, one 4 BHK and one independent house with recorded measurements |
| 6 | ATT has a strategy (§2.8) but no table specification or permission matrix of its own | MTQ-G2 (B1 scope) | Accept §2.8 and the blueprint's roadmap `attachment` columns as the ATT spec, or request a separate ATT package |
| 7 | PR #83 and PR #84 unmerged; this freeze lives on the PR #83 branch | — | Merge after review disposition |

Design work is complete for B1. Every remaining blocker is a recording or approval action.

**Verdict: B1 NOT READY** for implementation. Scope is complete and proposed for freeze; implementation entry waits on the seven items above, all of which are owner or reviewer actions.
