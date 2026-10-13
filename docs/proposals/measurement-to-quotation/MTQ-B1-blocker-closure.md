# MTQ B1 — blocker closure record

**Status:** DECISIONS RECORDED under owner-delegated authority. Documentation only: no code, migration, table, flag or pricing change. Every decision below is recorded exactly once here, mirrored into the register, the entry gate log and the owner decision log, and takes verifiable effect when the owner approves and merges PR #83, #84 and #85 from the owner's GitHub account (the repository's TG-01 pattern: a decision log entry is the communicated decision, the PR approval is the sign-off).
**Instruction:** `VEDA-SPACES-MTQ-B1-BLOCKER-CLOSURE` (2026-10-13), roles Principal Architect, Product Owner, Governance Coordinator.
**Inputs:** [MTQ-B1-SCOPE.md](MTQ-B1-SCOPE.md) at d4f14c3 (PR #85, the proposed freeze) · [MTQ-BLUEPRINT.md](MTQ-BLUEPRINT.md) (PR #83, faf7bb8) · [survey-and-scope-templates/](survey-and-scope-templates/README.md) (PR #84, e7e319d) · the business-reality review of 2026-10-13 (session record; findings transcribed in §1) · the architecture review verdict "READY WITH REQUIRED CHANGES" **reported by the owner; its finding list is not available in the repository, on any PR, or in any session record this closure could reach** (§1.3).
**Constraints honoured:** no architecture redesigned, no feature added, no scope changed. Where this record departs from a value *proposed* in MTQ-B1-SCOPE.md, the departure and its reason are stated in the row.

Verdict at the end: **§8**.

---

## 1. MTQ-G1 — review-finding resolution matrix

Owner categories follow [gate-registry.md](../../architecture/gate-registry.md) rule 2 (Product, Architecture, Privacy, Operations Owner). Status vocabulary: **CLOSED** (already addressed in d4f14c3), **DECIDED** (addressed by this record), **OPEN-B2 / B3 / B4** (accepted, tracked, does not bind B1), **PENDING-OWNER** (needs data or a verdict only the owner holds).

### 1.1 Business-reality review findings (2026-10-13)

| # | Finding | Disposition | Action | Owner | Status |
|---|---|---|---|---|---|
| BR-01 | The rate card keys the preparation package by `HOME_SIZES` 1BHK–4BHK + CUSTOM with a per-component `villa_factor`; engine `PROPERTY_TYPES` are APARTMENT and VILLA only. No pricing basis exists for 5 BHK, duplex levels or commercial (`api/veda/modules/estimator/ratecard.py`) | Accepted | B1 stores `derived_bedroom_count` and `derived_level_count` only (B1-SCOPE §2.9.4). Pricing drivers and the 5 BHK amount are OI-MTQ-15, decided before B3 | Product Owner | OPEN-B3 |
| BR-02 | The E6 replay set is three 3 BHK quotations, two in one building (C is an execution-stage revision of B); it cannot validate 2, 4, 5 BHK or an independent house | Accepted | Replay criteria frozen in §5 of this record; the quotation reference list is owner data (§5.4) | Product Owner | DECIDED (criteria) · PENDING-OWNER (reference list) |
| BR-03 | PR #84 mislabels card lines: `VENEER_ACCENTS.BEADING` exists on the Essential 1.1 card but the template says NEW LINE; the plumbing lump is `KITCHEN.PLUMBING`; `UTILITY.SINK_LAYING` is unreferenced; ADR-012 §3.1 lists granite laying as priced but the card has no line and the template calls it client scope | Accepted | Correct 01 §n "BOQ drivers" and 04 §3 before OI-MTQ-03 is recorded. The affected sections are deferred from B1 (§3.2), so B1 is not blocked | Architecture Owner (author) | OPEN-B2 |
| BR-04 | 02 §10 `PROJECT_RULES` emits a `PROJECT_ALLOWANCE` 5–15 % range on every quotation, contradicting blueprint §9.4 ("a fully measured estimate is a single number") | Accepted | Delete the range from `PROJECT_RULES`; allowances exist only as declared provisional sums under OI-MTQ-14. 02 §10 is deferred from the B1 acceptance (§3.2) | Product Owner | OPEN-B3 |
| BR-05 | Today's workbook applies GST to only part of the value (ADR-012 §3.3); the payment schedule exists only in the private workbook tab | Accepted | OI-MTQ-07 (GST) and OI-MTQ-09 (terms, schedule) stay blank until B3/B4; nothing in B1 computes tax or schedules | Product Owner | OPEN-B3/B4 |
| BR-06 | No post-acceptance variation or change-order model; `ACCEPTED` is terminal while E6 quotation C is itself an execution-stage revision | Accepted | Variation model designed and frozen in B1-SCOPE §2.7; B1 guarantees the identity rules (stable `property_space.id`, space-keyed diffs). Policy is OI-MTQ-13 | Architecture Owner · Product Owner | CLOSED (design) · OPEN-B4 (policy) |
| BR-07 | NICHE depth has no column | Accepted | `space_opening.depth_mm`, REQ for `NICHE` (B1-SCOPE §2.9.5) | Architecture Owner | CLOSED |
| BR-08 | L_SHAPE turn direction has no column | Accepted | `space_measurement.attributes.l_shape` with `turn_code`, two legs, 50 mm closure rule (B1-SCOPE §2.9.1) | Architecture Owner | CLOSED |
| BR-09 | Commercial partitions are triggered by a free-text "proposed" note and partitions shared between zones double count | Accepted, deferred with commercial | Resolved inside the commercial package when OI-MTQ-17 is decided; no commercial `SPACE_TYPE` is seeded in B1 | Product Owner | OPEN-B2 (OI-MTQ-17) |
| BR-10 | Capture burden: the Full template set (every wall, every photo) is 3–6 h per site and will not be followed | Accepted | Lite and Full tiers; Full trimmed to tagged walls and their bounding openings (B1-SCOPE §2.3) | Product Owner | CLOSED |
| BR-11 | L_SHAPE geometry rule missing | Accepted | See BR-08 | — | CLOSED |
| BR-12 | W1 convention undefined for door-less spaces | Accepted | OPEN edge as `wall_index 0`, W1 the first solid wall clockwise (B1-SCOPE §2.9.2) | Architecture Owner | CLOSED |
| BR-13 | Second-surveyor merge policy missing | Accepted | One DRAFT set, per-space claim via `captured_by`, 409 `SPACE_CLAIMED`, no merge step (B1-SCOPE §2.9.3) | Architecture Owner | CLOSED |
| BR-14 | No STAIRCASE template | Accepted | `STAIRCASE` space type with typed attributes (B1-SCOPE §2.4); accepted into the B1 template package in §3.1 of this record | Architecture Owner | CLOSED |
| BR-15 | `derived_level_count` and servant-room driver rules undefined | Accepted | Rules in B1-SCOPE §2.9.4 (which types count as bedrooms; terrace-only level counts) | Architecture Owner | CLOSED |
| BR-16 | B1 template seeding without Catalogue V3 administration | Accepted as a tracked deviation | Templates as versioned code fixtures, `template_version 2026.10.1`, migrated to `space_template` records in B2 (B1-SCOPE §4.4; B1-06 below) | Architecture Owner | DECIDED |
| BR-17 | ATT photo throughput and the anonymisation cascade undefined | Accepted | Attachment policy frozen in §6 of this record (limits, resize, scan, retention, deletion cascade) | Architecture Owner · Privacy Owner | DECIDED |
| BR-18 | New owner inputs not registered: variation policy, provisional sums, preparation-package drivers, design-stage linkage, commercial go/no-go | Accepted | OI-MTQ-13…17 registered as blank rows in d4f14c3; none binds B1 | Product Owner | CLOSED (registered) · OPEN-B2…B4 (decisions) |
| BR-19 | The owner-input ranking (High: 05, 07, 09, 03, 06 · Medium: 02, 04, 01, 10, 11 · Low: 08, 12) | Noted | Used as the order of the B2–B4 decision workshops; OI-MTQ-01 and 02 are closed here regardless of rank because they gate B1 | Product Owner | DECIDED |

### 1.2 Findings raised by the proposed freeze itself (MTQ-B1-SCOPE §6)

| # | Finding | Disposition | Action | Owner | Status |
|---|---|---|---|---|---|
| SF-01 | Review findings existed only as a session record | Accepted | Transcribed in §1.1; PR comments on #83 and #84 point here | Governance Coordinator | DECIDED (business review) · PENDING-OWNER (architecture review, §1.3) |
| SF-02 | OI-MTQ-01 and OI-MTQ-02 blank | Accepted | Recorded in §2 and §3 and in [MTQ-owner-decisions.md](MTQ-owner-decisions.md) | Product Owner | DECIDED |
| SF-03 | B1-01…B1-06 proposed, not recorded | Accepted | Recorded in §7.1 with d4f14c3 as the frozen-scope reference | Product Owner | DECIDED |
| SF-04 | Migration range not approved | Accepted | §4 and decision log entry 26 | Architecture Owner | DECIDED |
| SF-05 | Replay criteria not approved; set too narrow | Accepted | §5 | Product Owner | DECIDED (criteria) · PENDING-OWNER (reference list) |
| SF-06 | ATT has a strategy but no policy of its own | Accepted | §6 adopts B1-SCOPE §2.8 plus the blueprint's roadmap `attachment` columns as the ATT specification, with the amendments listed there | Architecture Owner | DECIDED |
| SF-07 | PR #83, #84, #85 unmerged | Accepted | Owner approval and merge, in stack order | Product Owner | PENDING-OWNER |

### 1.3 Architecture review findings — not recordable

The owner reports an architecture review with verdict "READY WITH REQUIRED CHANGES". No finding list, reviewer identity or verdict text exists on PR #83, PR #84, PR #85, in `docs/`, in `~/veda-private`, or in any session record available to this closure. **Nothing can be transcribed without inventing it.** MTQ-G1 requires a non-author reviewer's verdict with every condition dispositioned, so this gate stays OPEN until the owner posts (or pastes for posting) the review's findings and verdict on PR #83. The disposition procedure for them is the same table shape as §1.1; where a finding is already covered by a BR row, the AR row will cite it.

---

## 2. OI-MTQ-01 — measurement tolerance policy (DECIDED)

Two distinct things are frozen: the **agreement tolerance** used by the B1 validation gate (app capture versus the current tape-and-paper method on the same site), and the **runtime thresholds** the verification service enforces on every set. They are different numbers for different purposes and neither is a pricing default.

### 2.1 Agreement tolerance (B1 validation gate)

| Quantity | Tolerance | Note |
|---|---|---|
| Wall length, walls ≤ 6 000 mm | ±25 mm | Blueprint proposal, kept |
| Wall length, walls > 6 000 mm | ±50 mm | **Departure from the proposal.** Tape sag and reading position on long living or terrace walls exceed 25 mm between two competent operators; a single tolerance would fail sites for instrument reasons, not capture reasons |
| Ceiling height | ±25 mm | Per space, at the recorded point |
| Opening width and height | ±20 mm | Doors and windows are small; 25 mm on a 900 mm door is 2.8 % |
| Opening offset from its W-corner, sill height | ±25 mm | |
| Derived floor area per space | ±1 % **or ±0.1 m², whichever is larger** | The absolute floor stops a 2.5 m² toilet failing on a 25 mm wall difference that is inside the wall tolerance |
| Derived floor area, property total | ±1 % | |
| Staircase run, width, riser, tread | ±10 mm | Material-movement and panel numbers; measured by laser in both methods |

### 2.2 Validation thresholds (when is the B1 gate passed)

| Level | Rule |
|---|---|
| Wall | Within tolerance = PASS. Outside tolerance but inside 2× tolerance = EXPLAINED if a cause is recorded (instrument, method, reading position, data entry). Outside 2× tolerance = FAIL |
| Space | PASS when every opening and the area are within tolerance and no wall is FAIL |
| Site | PASS when ≥ 95 % of compared walls PASS, no wall FAIL, every space PASS, and the property total is within ±1 %; surveyor time per site recorded against the 03 §13 baseline |
| Gate | PASS when ≥ 9 of 10 sites PASS and no FAIL shares a root cause with another site (a repeated cause is systemic and reopens the capture design). Site mix: 5 apartments covering at least one 2 BHK, one 3 BHK and one 4 BHK; 5 independent houses, at least two with two or more levels |

### 2.3 Runtime verification thresholds (every set, fail closed)

Unchanged from the blueprint §6.2 and B1-SCOPE §2.9.1, frozen here so they are not re-opened: L_SHAPE and POLYGON closure 50 mm; every opening fits inside its wall (width + offset ≤ wall length); no negative derived area; property derived total within ±25 % of the stated built-up area or a `RISK_ACK` note by the verifier.

### 2.4 Recording

`OI-MTQ-01` row in the register filled with the values above; source `VEDA-SPACES-MTQ-B1-BLOCKER-CLOSURE`, 2026-10-13.

---

## 3. OI-MTQ-02 — survey-template package (DECIDED)

PR #84 (e7e319d) is accepted as the proposed default and split into **accepted for B1** and **deferred** at section level. Accepted sections become the content of the B1 code fixtures, `template_version 2026.10.1` (B1-06). Deferred sections keep their text in the package and bind nothing until the owner input they belong to is recorded.

### 3.1 Accepted for B1

| Document | Sections | Binding as |
|---|---|---|
| 00 conventions | §1 units and precision (tolerance row replaced by §2 of this record) · §2 measurement codes · §3 wall and opening labelling · §4 lookup and tag additions **as frozen in B1-SCOPE §2.6** (`WALL_TAG` seventeen values; any §4 value not in §2.6 is deferred) · §5 requiredness levels · §9 photo and note minimums **as trimmed by the Lite/Full rules in B1-SCOPE §2.3** | Capture contract and fixture schema |
| 01 space-type templates | CORE capture set · §1 Living · §2 Dining · §3 Kitchen · §4 Utility · §5 Master Bedroom · §6 Bedroom · §7 Guest Bedroom · §8 Study · §9 Pooja · §10 Balcony · §11 Terrace · §12 Toilet · §14 Custom — **the measurement and survey-checklist sub-sections only** (required and optional measurements, dependencies that are measurements, checklist). B1-SCOPE §2.4 is the STAIRCASE template. B1 `SPACE_TYPE` values without a dedicated template (FOYER, PASSAGE, SERVANT_ROOM, DRESSING, WALK_IN_CLOSET, MEDIA_ROOM, STORE, LAUNDRY, SIT_OUT, PORCH, PARKING, GARDEN, HOME_OFFICE, FAMILY_LOUNGE, LIVING_DINING, POWDER_ROOM, PARENTS_BEDROOM, CHILDREN_BEDROOM) inherit the CORE set or the named template's alias list as 01 states | Fixtures, one per B1 `SPACE_TYPE` |
| 02 property templates | §0 property-level capture (Lite subset per B1-SCOPE §2.3) · §1 2 BHK · §2 3 BHK · §3 4 BHK · §4 5 BHK · §7 Independent house (one `STAIRCASE` per level transition) | Fixtures `APARTMENT_2BHK` … `APARTMENT_5BHK`, `INDEPENDENT_HOUSE` |
| 03 playbook | §1 roles · §2 pre-visit · §3 arrival · §4 per-space procedure · §5 photo protocol (with the Lite/Full trim) · §7 closing · §8 submit self-check · §9 verification checklist · §10 rows 1–2 · §11 paper fallback · §12 kit · §13 timing baselines · §14 common errors | B1 operating procedure; §13 numbers are the baselines the validation gate measures against |

### 3.2 Deferred

| Document | Sections | Deferred to | Reason |
|---|---|---|---|
| 00 conventions | §6 recommendation levels · §7 BOQ driver vocabulary · §8 estimate driver vocabulary | B2 (OI-MTQ-03), B3 | Scope and pricing vocabulary; carries BR-03 corrections |
| 01 space-type templates | Every "scope recommendations", "BOQ drivers" and "estimate drivers" sub-section of §1–§12, §14 · §13 Commercial Space entirely · the `WASH_AREA` and `GUEST_SUITE` aliases (not in the B1 `SPACE_TYPE` seed; captured as UTILITY and GUEST_BEDROOM with a note until seeded) | B2 (OI-MTQ-03, OI-MTQ-04), OI-MTQ-17 | Rule content, not measurement content; BR-03 and BR-09 apply |
| 02 property templates | §5 Duplex · §6 Villa · §8 Commercial (§8.1–§8.4) · §9 Custom projects · §10 `PROJECT_RULES` | B2 (B1-SCOPE §1.2), OI-MTQ-17, OI-MTQ-14 (BR-04) | Property types outside B1; §10 carries the allowance-range contradiction |
| 03 playbook | §6 discovery with the customer · §10 rows 3–14 | B2 (requirements and scope do not exist in B1) | |
| 04 catalogue-record content | All of §1–§5 | B2 | Catalogue V3 administration is not active (B1-06); §1 is the **source text** for the fixture schema but is not keyed as records in B1 |

### 3.3 Recording

`OI-MTQ-02` row in the register: "PR #84 e7e319d accepted as the B1 template package per MTQ-B1-blocker-closure.md §3.1; §3.2 sections deferred"; source `VEDA-SPACES-MTQ-B1-BLOCKER-CLOSURE`, 2026-10-13. Later changes to accepted sections bump `template_version` and go through the amendment procedure in §7.2.

---

## 4. MTQ-G4 — migration range (APPROVED)

**Evidence checked on 2026-10-13 after an HTTPS fetch of every branch on `slaggala/veda-spaces`:** highest existing revision `0105_catalog_claim_control`; no file matching `0106_*` or `02xx_*` exists under `api/migrations/versions` on any of the 100+ remote branches. No in-flight module collides.

| Revision | Decision | Content (as frozen) | Rollback |
|---|---|---|---|
| `0106_attachment` | **APPROVED for B1** | `attachment` table; permissions `attachment.read/create/delete`; lookup `ATTACHMENT_CATEGORY` (B1-SCOPE §4) | Drop table; additive only |
| `0200_mtq_site` | **APPROVED for B1** | Tables 2–10 of B1-SCOPE §2.1 including `space_electrical_point`; lookups, sequences, permission sync, roles `SURVEYOR`, `DESIGNER` | Drop the ten tables; soft-delete permission codes; lookups stay |
| `0201_mtq_estimation` | **RESERVED** (B2 part 1, B3 part 2 per blueprint §16) | Not authored in B1 | — |
| `0202_mtq_commercial` | **RESERVED** (B4) | Not authored in B1 | — |
| `0203_mtq_knowledge` | **RESERVED** (B5) | Not authored in B1 | — |

Rules: `0107`–`0199` remain free for non-MTQ modules and MTQ never takes them; a corrective B1 migration, if one is ever needed, takes `0204` onward by a logged amendment and never repurposes `0201`–`0203`; `0200` depends only on platform revisions plus `0106` and `0100_crm_leads` (02-platform-architecture §8.3 rule); both engines in CI; the nine-column conformance check runs on every new table. Recorded as entry 26 in [decision-log.md](../../architecture/decisions/decision-log.md).

---

## 5. MTQ-G5 — historical replay validation criteria (DECIDED; reference list PENDING-OWNER)

The replay runs at the B2 exit (quantities) and the B3 exit (prices); the criteria are frozen now because the B1 capture contract must make the replay possible. Confidence is a property of the evidence, so each configuration is validated to a stated confidence rather than silently passed.

### 5.1 Replay set composition

| Configuration | Minimum set | Known today |
|---|---|---|
| 2 BHK apartment | 1 quotation with recorded measurements | None in E6 (the "fourth, independent quotation, 2 BHK preferred" is already an open owner input in E6 §1) |
| 3 BHK apartment | 2 independent quotations | A and B. C is B's execution-stage revision: replayed only as a **variation case** (B → C delta), never as a base |
| 4 BHK apartment | 1 | None |
| 5 BHK apartment | 1 | None; see 5.3 |
| Independent house | 1, with two or more levels | None |

A quotation enters the set only with: its measurement source (workbook sheet or drawing, kept private), its date, the rate card in force at that date (or the statement that it cannot be reconstructed), and whether it is a base or a revision. Two quotations from the same building count as one for the "independent" requirement.

### 5.2 Pass, fail, confidence

| Level | PASS | FAIL | Notes |
|---|---|---|---|
| Line (B2) | Quantity within ±5 % of the quoted quantity, or within one rounding unit of the line's UOM, whichever is larger | Outside ±15 % with no recorded cause | Between 5 % and 15 %: EXPLAINED when the cause is classified rate, quantity, scope or measurement class |
| Quotation (B2) | ≥ 90 % of lines PASS and no line FAIL; manual-override rate recorded | Any line FAIL, or < 80 % of lines PASS | 80–90 % with every exception EXPLAINED is PASS-WITH-NOTES |
| Quotation (B3) | Pre-GST total within ±3 % **with the card in force at the quotation date**; every room subtotal within ±5 % | Total outside ±5 % or any room outside ±10 % | With only the current card available the comparison is rate-normalised and confidence drops one level |
| Variation case (C) | B3: the B → C delta reproduced within ±5 % of the quoted delta | Delta sign wrong, or outside ±10 % | Validates OI-MTQ-13's delta model, not the base |
| Configuration | Every quotation in its set PASS or PASS-WITH-NOTES | Any FAIL | |
| Gate (B2 exit, B3 exit) | Every configuration with ≥ 1 quotation PASS; every configuration with 0 quotations listed as UNVALIDATED in the exit evidence | Any configuration FAIL | UNVALIDATED is not FAIL; it is a disclosed limit carried into B3/B4 activation decisions |

Confidence per quotation: **HIGH** = measured inputs, card at date, base quotation, independent building · **MEDIUM** = one of those missing · **LOW** = two or more missing. Confidence per configuration: **HIGH** ≥ 2 HIGH quotations · **MEDIUM** 1 HIGH or 2 MEDIUM · **LOW** otherwise · **NONE** no quotation.

### 5.3 Configurations with no history

Where Veda has never quoted a configuration (5 BHK is the likely case), the configuration is recorded UNVALIDATED at B2/B3 exit and its first live quotation is compared against the engine before it is sent, under the same line and total tolerances, by the estimator with four-eyes. This is a criterion for an existing validation step, not a feature.

### 5.4 What remains owner data

The list of quotation references (private identifiers, configuration, date, measurement source, card at date, base or revision) for the rows in 5.1. The repository is public, so the list lives with the owner (as E6 §0 already rules) and the evidence package records only relative results. **MTQ-G5 passes when that list exists and covers 5.1; the criteria part is closed by this record.**

---

## 6. ATT — attachment policy (FROZEN for B1)

The B1-SCOPE §2.8 strategy is adopted as the ATT specification together with the blueprint's roadmap `attachment` columns (polymorphic `entity_type`/`entity_id`, `sha256`, `scan_status`, `visibility`, `category_code`), with the amendments marked **Δ**. The policy reuses the certified catalogue media pipeline (`api/veda/modules/catalog/media.py`) as a library; nothing in it is re-implemented.

### 6.1 Upload limits

| Limit | Value | Basis |
|---|---|---|
| Per object | 15 MB | Equals `MAX_IMAGE_BYTES` in the catalogue pipeline |
| Accepted types in B1 | JPEG, PNG, WebP images only; content-sniffed, declared type and filename ignored | **Δ** PDF floor plans are not accepted in B1: no sanitiser exists for PDF and writing one is a new feature. A builder's PDF is photographed or exported to images (02 §0 already allows "photo of it"). PDF intake is tracked for B2 |
| Per wall | 6 photos soft (UI warns), 12 hard | §2.8 soft limit kept; hard limit added |
| Per space | 40 objects soft | New guard; a 03 §5 Full capture of a kitchen is ~25 |
| Per measurement set | **800 objects, 1 GB (hard)** | **Δ from 400.** 03 §13 puts a villa or independent house at 400–700 photos before the Lite/Full trim; 400 would block the configuration B1 is meant to support. 800 × ~0.7 MB stays under 1 GB |
| Upload path | Direct-to-S3 pre-signed PUT per object; device-computed `sha256` verified server-side; duplicate hashes reuse the object; metadata may precede bytes (set may be SUBMITTED while uploads drain, never VERIFIED) | §2.8 |

### 6.2 Image limits and resize policy

| Stage | Rule |
|---|---|
| Client (PWA), before upload | Long edge 2048 px, JPEG quality 80, EXIF orientation applied, **all EXIF stripped including GPS**, 256 px local thumbnail for the capture UI only (never uploaded) |
| Server, on receipt | Catalogue pipeline unchanged: header-checked limits 24 MP and 8 000 px per side, minimum side 320 px, re-encode with every metadata block dropped, WebP variants at widths **320 / 768 / 1600** quality 82 (**Δ** from the proposed 256 / 1024: the existing `IMAGE_WIDTHS` are reused as-is rather than adding a second variant set); the re-encoded source is retained, the uploaded bytes are not |
| Delivery | Variants served to staff only, through the API with permission checks against the parent lead; sources never served; nothing public |

### 6.3 Scanning

ClamAV as deployed (`media_scanner.mode = clamd`): objects are `PENDING` until `CLEAN`; verifiers never see a non-CLEAN object; a set cannot reach `VERIFIED` while any attached object is `PENDING`, `FAILED` or `INFECTED`; `FAILED` is retried by the existing scheduler; `INFECTED` objects are quarantined (bytes retained for 30 days for investigation, then deleted) and must be removed from the set before verification.

### 6.4 Retention and deletion

| Case | Rule |
|---|---|
| Attachments on a lead's property | Follow the lead-retention job (OWNER-INPUT-002). **No retention period is invented here**; the job ships disabled exactly as the lead job does until the owner sets the period (decision log entry 15). When it runs: bytes of source and variants deleted, rows kept with hashes (the catalogue "withdrawal" semantics) |
| Deletion request or withdrawn consent (DSAR) | Immediate byte deletion of every attachment under the lead's properties, cascading property → space → wall / opening / electrical point → note; rows kept with hashes; event written to the audit log |
| Orphaned objects (no live row references the hash) | Purged after `catalog_media_retention_days` (180 by default, bounds 30–3650) by the existing purge job |
| Attachments on a DRAFT set | Deletable by the uploader; after SUBMITTED, soft delete only, by the verifier, with a reason note |
| S3 | Bucket `${name_prefix}-attachments-${account_id}` in the storage module (**Δ** from `veda-attachments-<env>`: the module's naming convention), data KMS key, no Object Lock, versioning on with 30-day noncurrent expiry, Intelligent-Tiering after 90 days, TLS-only, bucket-owner-enforced, no public access. Provisioned through the normal plan and apply runs when B1 implementation starts |

### 6.5 Permissions and visibility

`attachment.read`, `attachment.create`, `attachment.delete` evaluated against the parent lead's visibility (blueprint §15.3); `visibility = INTERNAL` for customer-supplied floor plans and for anything a verifier marks sensitive; the playbook §5 rules (no faces, no documents other than the floor plan, no valuables, customer informed) stay procedural and are part of the surveyor checklist, not enforced by code.

---

## 7. Decisions recorded

### 7.1 Register rows written today

| ID | Decision | Where |
|---|---|---|
| OI-MTQ-01 | §2 of this record | [MTQ-owner-decisions.md](MTQ-owner-decisions.md) |
| OI-MTQ-02 | §3 of this record | same |
| B1-01 supported scope | 2–5 BHK apartments and independent houses; B1-SCOPE §1.2 deferrals stand | same (new rows) |
| B1-02 survey levels | LITE and FULL per B1-SCOPE §2.3; only FULL is quotation-ready | same |
| B1-03 electrical capture | `space_electrical_point` per B1-SCOPE §2.5 | same |
| B1-04 wall-tag vocabulary | the seventeen `WALL_TAG` values of B1-SCOPE §2.6 | same |
| B1-05 attachment limits and retention | §6 of this record (supersedes the §2.8 values where Δ is marked) | same |
| B1-06 templates as fixtures | B1-SCOPE §4.4 deviation accepted for B1 | same |
| MTQ-G4 | §4 of this record | [decision-log.md](../../architecture/decisions/decision-log.md) entry 26; gate log |
| MTQ-G5 criteria | §5 of this record | gate log |

The frozen-scope reference for MTQ-G2 is **d4f14c3** (MTQ-B1-SCOPE.md as amended) **plus this record** for the values marked Δ.

### 7.2 Amendment procedure

A change to any frozen value (B1-01…06, OI-MTQ-01, OI-MTQ-02, the migration range, the replay criteria, the attachment policy) is a new row in the register or a new decision log entry with date and instruction, never an edit; the implementation branch may not start from an amended value until the amendment is merged.

---

## 8. Remaining blockers and verdict

| # | Blocker | Gate | Who can clear it | Why this record could not |
|---|---|---|---|---|
| 1 | Architecture review findings and verdict not on any PR or in any record | MTQ-G1 | Owner posts them on PR #83 (or pastes them for posting); then they are dispositioned in a §1.3 table | Nothing to transcribe; inventing findings is not recording them |
| 2 | Replay quotation reference list (private) not enumerated for 5.1 | MTQ-G5 | Owner, from the quotation workbooks | Owner-held data outside the repository |
| 3 | Verifiable owner approval: PR #83, #84, #85 (with this commit) approved and merged in stack order from the owner's GitHub account | MTQ-G1…G5 evidence · TG-01 pattern | Owner | Sign-off cannot be delegated to the recording session |

Gates after this record: **MTQ-G2 RECORDED**, **MTQ-G3 RECORDED**, **MTQ-G4 RECORDED** (each passes on the owner's PR approval); **MTQ-G1 OPEN** (blocker 1); **MTQ-G5 PARTIAL** (criteria recorded, blocker 2).

**Verdict: B1 STILL BLOCKED.** Every design and policy decision B1 needs is now written down; what remains is one review artefact and one data list that only the owner holds, plus the merge. No engineering decision is outstanding.
