# 02 · Property templates

A property template is the **seed** for a `property` row and its `property_space` tree (blueprint §4.1, §5.3): which spaces to create, with which `space_type_code`, `instance_no`, `level_index`, `zone_code`, `sort_order` (walk order) and `space_template_key`; which project-level requirements to propose; which estimate drivers the property contributes; and what the property-level survey must capture before any space is measured. Space-level content lives in [01-space-type-templates.md](01-space-type-templates.md).

BHK is a label (§5.3, coverage matrix §2). The 2/3/4/5 BHK templates below differ only in the number of bedroom and toilet instances and in walk order; nothing else is keyed on the label. The surveyor **adds or removes spaces freely** on site; the seed is a starting point, never a constraint, and `derived_bedroom_count` is computed from what was actually measured.

## 0. Property-level capture (every template)

Captured on `property` and as `measurement_note` rows with `space_id = NULL` before the first space is measured.

| Item | Target | Level |
|---|---|---|
| Property type, usage, project kind | `property_type_code`, `usage_code`, `project_kind_code` | REQ |
| Configuration label as the customer says it | `configuration_label` | REQ (display only) |
| Stated built-up, carpet, plot area | `*_area_sqft_centi` | REQ built-up or carpet; plot REQ for villa / independent house |
| Stated floor count | `floor_count` | REQ for duplex / villa / independent house / multi-level commercial |
| Possession status and date | `possession_status_code`, `possession_on` | REQ |
| Address, geo | address columns, `geo_lat/lng` | REQ (geo from the device at visit start) |
| Floor plan (builder's drawing or photo of it) | `floor_plan_attachment_id` | REQ when one exists; `RISK` note when none |
| Floor number, lift availability and size, staircase width, service-lift rules | `NT.OBSERVATION` (project) | REQ (material movement; `SITE_FACTOR` input) |
| Society / building working-hours and permissions | `NT.OBSERVATION` | REQ |
| Main door width and height; passage widths (narrowest point) | `NT.OBSERVATION` with values | REQ (largest carcass that can enter) |
| Electrical: DB location, phase, sanctioned load if known | `NT.OBSERVATION` | REQ |
| Water, drainage condition; dampness anywhere | `NT.RISK` | REQ when observed |
| Occupied / vacant; furniture to protect or move | `NT.OBSERVATION` | REQ (preparation package) |
| Parking for material vehicles | `NT.OBSERVATION` | OPT |
| Customer contact on site | `measurement_visit.customer_contact_*` | REQ |
| Customer walk-through order preference | `sort_order` | OPT (default order below) |

## 1. Apartment · 2 BHK

`property_type_code = APARTMENT`, `usage = RESIDENTIAL`, `configuration_label` "2 BHK", `level_index` 0 throughout.

| Walk order | Space | `space_type_code` | `instance_no` | Zone | Template key | Parent |
|---|---|---|---|---|---|---|
| 1 | Foyer / entrance (only when a distinct alcove) | `FOYER` | 1 | INDOOR | — (CORE only; shoe tag on W1) | Living |
| 2 | Living | `LIVING` or `LIVING_DINING` | 1 | INDOOR | `LIVING_DEFAULT` | — |
| 3 | Dining (only when separate) | `DINING` | 1 | INDOOR | `DINING_DEFAULT` | — |
| 4 | Kitchen | `KITCHEN` | 1 | INDOOR | `KITCHEN_DEFAULT` | — |
| 5 | Utility | `UTILITY` | 1 | INDOOR / SEMI_OPEN | `UTILITY_DEFAULT` | — |
| 6 | Pooja (room or niche) | `POOJA` (or a niche on the living wall) | 1 | INDOOR | `POOJA_DEFAULT` | — |
| 7 | Common toilet | `TOILET` | 1 | INDOOR | `TOILET_DEFAULT` | Passage / living |
| 8 | Master bedroom | `MASTER_BEDROOM` | 1 | INDOOR | `MASTER_BEDROOM_DEFAULT` | — |
| 9 | Attached toilet | `TOILET` | 2 | INDOOR | `TOILET_DEFAULT` | Master bedroom |
| 10 | Bedroom 2 | `BEDROOM` | 1 | INDOOR | `BEDROOM_DEFAULT` (or `CHILDREN_BEDROOM_DEFAULT`) | — |
| 11 | Balcony (each) | `BALCONY` | 1..n | SEMI_OPEN | `BALCONY_DEFAULT` | adjoining room |

Expected derived counts: bedrooms 2, toilets 2, levels 1. Sanity: built-up 850–1 250 sq ft; measured floor area within ±25 % of stated built-up (§6.2) or an acknowledged warning.

Project-level requirements proposed (`space_id = NULL`, `PROPOSED` / `RECOMMENDED`): `PAINTING` (OPTIONAL, ADR-012 D6), `ELECTRICAL` (OPTIONAL, D6), preparation and protection package (MANDATORY, D5: floor protection, plywood protection, freight, debris handling, deep cleaning, pest control; driver `bedroom_count`), `FALSE_CEILING` throughout (OPTIONAL bundle that confirms the per-space ceiling requirements together).

Estimate drivers contributed: `bedroom_count` 2, `floor_area_sqft` from the verified set, `level_count` 1, `space_count` indoor spaces; adjustments: `SITE_FACTOR` only when no lift or restricted hours; `TRANSPORT` by distance band.

Typical visit: 1 surveyor, 2.0–2.5 h including discovery.

## 2. Apartment · 3 BHK

As 2 BHK, with: Bedroom 3 (`BEDROOM` instance 2, walk order after Bedroom 2), a third toilet when present (`TOILET` instance 3, attached to Bedroom 2 or 3), and a study if the plan has one (`STUDY`). Expected counts: bedrooms 3, toilets 2–3. Sanity: built-up 1 250–1 850 sq ft. Driver `bedroom_count` 3. Visit 2.5–3.5 h.

## 3. Apartment · 4 BHK

As 3 BHK, with: Bedroom 4 (`BEDROOM` instance 3 or `GUEST_BEDROOM` instance 1 by use), toilets 3–4, `DRESSING` child of the master bedroom when present, `FAMILY_LOUNGE` when the plan has a second living area, `SERVANT_ROOM` + its toilet when present (`SERVANT_ROOM` has CORE only and `BEDROOM_DEFAULT` with no mandatory items). Expected counts: bedrooms 4 (servant room counts: it has `counts_as_bedroom` in §5.1; the configuration label stays what the customer says), toilets 3–5. Sanity: built-up 1 850–2 800 sq ft. Driver `bedroom_count` 4 (or 5 with the servant room: the preparation-package card line must say whether `bedroom_count` includes `SERVANT_ROOM`; **proposed: excluded**, implemented as the driver reading `counts_as_bedroom AND space_type_code <> 'SERVANT_ROOM'`; this is card content, not schema). Visit 3.5–4.5 h, consider 2 surveyors.

## 4. Apartment · 5 BHK

As 4 BHK, with the fifth bedroom, up to 6 toilets, `WALK_IN_CLOSET` likely, `MEDIA_ROOM` / `HOME_THEATRE` (custom-space template with `TV_UNIT` + `FEATURE_WALL` tags, acoustic note) when present, `STORE`, `LIBRARY`. Sanity: built-up 2 800–4 500 sq ft. Driver `bedroom_count` 5. Visit 4.5–6 h, 2 surveyors; split by zone, **one measurement set per surveyor** (blueprint §13.2 G-2: two DRAFT sets; the verifier merges by accepting one and re-keying the other's spaces, until the second-set policy is decided).

## 5. Duplex

`property_type_code = DUPLEX` (penthouse: `PENTHOUSE`, same template), `floor_count` 2, `level_index` 0 and 1.

| Walk order | Space | Type | Level | Zone | Template |
|---|---|---|---|---|---|
| 1–7 | Lower level as the apartment template: foyer, living, dining, kitchen, utility, pooja, common toilet | as above | 0 | INDOOR | as above |
| 8 | Guest bedroom or parents' bedroom on the lower level (common in duplexes) | `GUEST_BEDROOM` / `PARENTS_BEDROOM` | 0 | INDOOR | respective |
| 9 | Staircase | `STAIRCASE` | 0→1 | INDOOR | CORE: run length, width, riser count, headroom (`BB`), under-stair void (L, W, H) as a `NICHE`-style note, landing size, handrail wall tag `FEATURE_WALL` if treatment wanted | 
| 10 | Upper-level lounge / family area | `FAMILY_LOUNGE` | 1 | INDOOR | `LIVING_DEFAULT` with no mandatory TV unit (rule `when` excludes `FAMILY_LOUNGE` from the mandatory TV rule; RECOMMENDED instead) |
| 11–14 | Master bedroom + dressing + toilet; bedrooms 2..n + toilets | as apartment | 1 | INDOOR | respective |
| 15 | Study | `STUDY` | 0 or 1 | INDOOR | `STUDY_DEFAULT` |
| 16 | Terrace / upper balcony | `TERRACE` / `BALCONY` | 1 | OUTDOOR / SEMI_OPEN | respective |

Additional property-level capture: internal staircase width and turn (largest panel that can go up; `RISK` when < 900 mm); double-height volume over the living (`CH` of the void, `Wn.H` on the tall walls, feature-wall tag on the double-height wall for panelling / wallpaper `wall_area_net` with the full height); railing / balustrade (client scope note); upper-level material route (via staircase or external lift / hoist, `SITE_FACTOR`).

Project-level: as apartment; plus `FLOOR_FACTOR` adjustment on upper-level lines (`cost_estimate_adjustment FLOOR_FACTOR`, `scope_code = SPACE` per upper space, value from the card's default, staff-adjustable with reason); under-stair storage (`STORAGE_BOXES.TALL` or `CUSTOM_ITEM`, OPTIONAL); staircase wall panelling (`FEATURE_WALL`, OPTIONAL).

Drivers: `level_count` 2 (the preparation package card may scale freight and protection by `level_count`), `bedroom_count` as measured, `floor_area_sqft` summed across levels. Sanity: built-up 1 800–4 000 sq ft. Visit 4–6 h, 2 surveyors (one per level, separate sets).

## 6. Villa

`property_type_code = VILLA`, `plot_area_sqft_centi` REQ, `floor_count` 1–4, `level_index` −1..3, external walls flagged (`Wn.X` REQ on every wall of every ground-floor and top-floor space).

| Walk order | Space | Type | Level | Zone | Template |
|---|---|---|---|---|---|
| 1 | Porch / car park | `PORCH`, `PARKING` | 0 | SEMI_OPEN / OUTDOOR | CORE outline; ceiling / pergola; shoe unit tag; `OUTDOOR_RULES` |
| 2 | Garden / sit-out | `GARDEN`, `SIT_OUT` | 0 | OUTDOOR / SEMI_OPEN | Terrace template (outline, services, seating sketch) |
| 3 | Foyer | `FOYER` | 0 | INDOOR | shoe / foyer unit tag; often a full space in villas: `LIVING_DEFAULT` minus the TV rule |
| 4–9 | Living, dining, kitchen, utility, pooja, common toilet / powder room | as apartment (`POWDER_ROOM` for a half-toilet) | 0 | INDOOR | respective |
| 10 | Guest bedroom / parents' bedroom + toilet | respective | 0 | INDOOR | respective |
| 11 | Servant room + toilet | `SERVANT_ROOM`, `TOILET` | 0 / −1 | INDOOR | CORE; `BEDROOM_DEFAULT` with no mandatory items |
| 12 | Store | `STORE` | 0 / −1 | INDOOR | CORE; `STORAGE_BOXES.TALL` on tagged walls, OPTIONAL |
| 13 | Staircase(s) | `STAIRCASE` | per flight | INDOOR | as Duplex |
| 14 | Family lounge / upper living | `FAMILY_LOUNGE` | 1 | INDOOR | as Duplex |
| 15–20 | Master suite (bedroom + dressing / walk-in + toilet), bedrooms 2..n + toilets, study | respective | 1 (2) | INDOOR | respective |
| 21 | Home theatre / media room / gym | `HOME_THEATRE` / `MEDIA_ROOM` / `CUSTOM` ("Gym") | −1 / 1 / 2 | INDOOR | custom-space template with tags; acoustic and AV notes |
| 22 | Balconies per bedroom | `BALCONY` | 1 (2) | SEMI_OPEN | respective |
| 23 | Terrace | `TERRACE` | top | OUTDOOR | respective |
| 24 | Basement (if any) | `CUSTOM` ("Basement") + its rooms | −1 | INDOOR | custom; dampness `RISK` mandatory check |

Additional property-level capture: compound gate width and vehicle access for a truck; external staircase; water tank, sump, pump room positions; solar / inverter; boundary wall (client scope); façade elements that affect window sills (bay windows → window-seating candidates); `Wn.X` on every external wall so dampness-risk and panelling advice are correct; independent electrical meter / phase; rainwater and drainage.

Project-level: as apartment, plus the villa factor on the preparation package (ADR-012 D5 "a villa factor" → declared as the card's `level_count` driver or a `SITE_FACTOR` default for `VILLA`; card content, OI-MTQ-05); `FLOOR_FACTOR` per upper level; outdoor and exterior-grade painting as separate project lines (**NEW LINE**); `ELECTRICAL` sized by `floor_area_sqft` plus points count.

Drivers: `level_count` as measured, `bedroom_count` as measured, `floor_area_sqft` indoor only, `space_count` indoor; `plot_area` is captured but is **not** a driver (no card line uses it). Sanity: built-up 2 000–6 000 sq ft, plot 1 200–6 000 sq ft; measured-vs-stated check applies to built-up only. Visit 6–10 h over one or two days; 2–3 surveyors; one set per surveyor; a `PLAN_DRAWING` pre-measure (rev 0, `MEDIUM` confidence) from the architect's drawing is strongly recommended before the visit so the tree is pre-seeded.

## 7. Independent house

`property_type_code = INDEPENDENT_HOUSE`; template as Villa with these differences: older stock (renovations dominate), so `project_kind_code = RENOVATION` is the default and `AT.has_false_ceiling_existing`, existing wardrobes / kitchen (dismantling notes), `CND` (`OCCUPIED_WORN`, `DAMP`, `CRACKED`) and `FLR` are REQ on every space; `ROW_HOUSE` uses the same template with shared walls flagged `Wn.X = false` and a note "party wall" (no external-wall treatment); plot area REQ; drivers as Villa.

Additional capture: structural observations (`RISK`: cracks, seepage, sagging slabs, exposed wiring), which never price but block `VERIFIED` until the designer acknowledges each; load-bearing wall identification where partitions might be removed (`RCC` / `MASONRY` wall types and a note; civil work is excluded, flagged for an engineer).

Visit as Villa; add 1 h for renovation photo documentation.

## 8. Commercial

`usage_code = COMMERCIAL`; `property_type_code` `OFFICE` / `RETAIL` / `CLINIC` / `HOSPITALITY`; `project_kind_code` usually `NEW` (bare shell) or `RENOVATION` (fit-out replacement). One `CUSTOM` shell space per level (`POLYGON`, label "Shell L<n>") with zones as child spaces (01 §13).

### 8.1 Office

| Walk order | Space | Type | Template |
|---|---|---|---|
| 1 | Shell per level | `CUSTOM` "Shell L0" | 01 §13 shell capture |
| 2 | Reception + waiting | `RECEPTION`, `WAITING_AREA` | `COMMERCIAL_RECEPTION_DEFAULT`, `COMMERCIAL_WAITING_DEFAULT` |
| 3 | Workstation area(s) | `WORKSTATION_AREA` 1..n | `COMMERCIAL_WORKSTATION_DEFAULT` |
| 4 | Cabins | `CABIN` 1..n | `COMMERCIAL_CABIN_DEFAULT` |
| 5 | Conference / meeting rooms | `CONFERENCE` 1..n | `COMMERCIAL_CONFERENCE_DEFAULT` |
| 6 | Pantry | `PANTRY` | `KITCHEN_DEFAULT` with `applies_when usage COMMERCIAL` (no loft rule, no plumbing lump unless services exist) |
| 7 | Server / store / back office | `SERVER_ROOM`, `STORE`, `BACK_OFFICE` | respective |
| 8 | Toilets | `TOILET` 1..n | `TOILET_DEFAULT` (vanity RECOMMENDED) |
| 9 | Training room | `TRAINING_ROOM` | `COMMERCIAL_CONFERENCE_DEFAULT` |

Expected counts: bedrooms 0, toilets as measured, levels as measured. Project-level: partitions bundle (MANDATORY, from zone edges), `ELECTRICAL` (RECOMMENDED; driver `space_count` × points-per-seat), `PAINTING` (RECOMMENDED; `wall_area_net` including partition faces), `FALSE_CEILING` throughout (RECOMMENDED), `FLOORING` (OPTIONAL, **NEW LINE**), preparation package with a commercial driver (`floor_area_sqft`; card content). Adjustments: `SITE_FACTOR` (night work, building management rules), `TRANSPORT`. Sanity: 400–20 000 sq ft per level. Visit 1 h per 1 000 sq ft shell plus 15 min per zone; 2 surveyors above 3 000 sq ft.

### 8.2 Retail

Shell → `RETAIL_FLOOR` (display walls, window display, signage band), `BILLING_COUNTER`, `TRIAL_ROOM` 1..n, `STORE` / `BACK_OFFICE`, `TOILET`. Mandatory: partitions from zone edges, billing counter (**NEW LINE**, `auto: true` on the `BILLING_COUNTER` zone), trial-room partitions and mirror. Recommended: display units (**NEW LINE**), `FALSE_CEILING`, lighting (track lighting **NEW LINE**), `FLOORING`, `FEATURE_WALL`. Exclusions: signage, façade, shutters, security systems. Visit as Office.

### 8.3 Clinic

Shell → `RECEPTION` + `WAITING_AREA`, `CABIN` (consultation) 1..n, `TREATMENT_ROOM` 1..n, `PANTRY`, `STORE` (records / pharmacy: tall storage RECOMMENDED), `TOILET` (accessible toilet note), `BACK_OFFICE`. Mandatory: partitions, reception desk, consultation desks (`STUDY_UNIT`). Recommended: treatment-room vanities, storage, washable wall finish note (finish variant), `FALSE_CEILING`, lighting. Risks: medical-gas, equipment loads, stretcher widths (`RISK` notes, never priced). Visit as Office + 15 min per treatment room.

### 8.4 Hospitality (guest house / small hotel)

Shell → `RECEPTION`, `WAITING_AREA` (lobby), `GUEST_ROOM` 1..n (template = `MASTER_BEDROOM_DEFAULT` with `applies_when usage COMMERCIAL`: wardrobe, bed, side tables, TV panel, dresser, mini-bar niche MANDATORY set reduced to wardrobe + bed + TV panel), each with a `TOILET` child, `PANTRY` / kitchen, `BACK_OFFICE`. Expect many identical rooms: measure one fully, then every other room with CORE (shape, L, W, CH, walls, openings) and the template copies the tags; the verifier checks each room's walls against the first (`RISK` on any deviation > 50 mm). Drivers: `space_count` (rooms) is the natural driver for the preparation package; card content.

## 9. Custom projects

`project_kind_code = PARTIAL` with any property type (a single kitchen renovation, one bedroom, a clubhouse, a farmhouse). Seed **only** the spaces in scope plus any space the project-level lines need (a kitchen-only project does not seed the bedrooms; painting of one room needs only that room). Property-level capture stays REQ (access, lift, hours, main door). Project-level lines use `space_count` or `fixed` drivers (not `bedroom_count`); the preparation package has a `PARTIAL` card variant or is priced `fixed` with reason (card content). `CUSTOM` spaces carry `custom_type_label`; the generic rule group applies. Quotation assumptions list "measured spaces only; other spaces excluded" automatically from `is_in_scope = false` rows if the surveyor seeded them, or from the absence of spaces otherwise (the designer adds a standard exclusion line).

## 10. Project-level rule group (`PROJECT_RULES`), all templates

| Rule key | When | Emit | Necessity | Driver / formula |
|---|---|---|---|---|
| `PROJECT_PREP_PACKAGE` | always, `usage = RESIDENTIAL` | preparation and protection package (ADR-012 D5 components only) | MANDATORY | card driver `bedroom_count` (apartment), `level_count` or `SITE_FACTOR` villa factor, `space_count` / `fixed` for `PARTIAL`; `applies_zone INDOOR` |
| `PROJECT_PREP_PACKAGE_COMMERCIAL` | `usage = COMMERCIAL` | same components | MANDATORY | `floor_area_sqft` (card content needed, OI-MTQ-05) |
| `PROJECT_PAINTING` | confirmed `PAINTING` requirement | `PAINTING_INTERIOR` (`PAINTING.REPAINT` or full preparation variant by `CND`) | OPTIONAL (D6) | `wall_area_net` Σ over in-scope indoor spaces; kitchens above dado; toilets excluded; ceilings included only when no false ceiling |
| `PROJECT_PAINTING_EXTERIOR` | villa / independent house / balcony confirmed | exterior painting (**NEW LINE**) | OPTIONAL | `wall_area_net` of `Wn.X` faces (outside face assumed = inside length × height; assumption listed) |
| `PROJECT_ELECTRICAL` | confirmed `ELECTRICAL` requirement | `ELECTRICAL.WIRING` + `ELECTRICAL.SPOTS` | OPTIONAL (D6) | wiring by `floor_area_sqft` (carpet) + points `count` from all spaces' AC / fan / light / power counts; full rewiring is a site-measurement case flagged `RISK` |
| `PROJECT_FALSE_CEILING_BUNDLE` | ≥ 2 spaces confirm `FALSE_CEILING` | none (groups per-space ceiling items in the quotation section) | — | — |
| `PROJECT_DEEP_CLEANING` | inside the package (D5) | — | — | — |
| `PROJECT_ALLOWANCE` | always | custom-features allowance (ADR-012 D9) | shown as its own range | % of room work from the card (5–15 %) |
| `PROJECT_FLOOR_FACTOR` | any space with `level_index ≥ 1` (duplex / villa) or apartment floor without lift | `cost_estimate_adjustment FLOOR_FACTOR` per space | adjustment | card default %, staff-editable with reason |
| `PROJECT_SITE_FACTOR` | property notes flag no lift / restricted hours / narrow access | `SITE_FACTOR` proposal (not auto-applied; staff confirms) | adjustment | reason required |
