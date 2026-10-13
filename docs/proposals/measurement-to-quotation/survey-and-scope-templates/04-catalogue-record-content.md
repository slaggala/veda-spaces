# 04 · Catalogue-record content (keying guide)

The templates in 01 and 02 expressed as the catalogue records the blueprint defines (§5.2 `space_template`, §8.1 `scope_rule`, §8.2 `quantity_formula`), in the blueprint's own notation. These are **data to be keyed into Catalogue V3** once it is active (dependency matrix row 2) and approved through the normal DRAFT → review → ACTIVE release path with four-eyes. They are not code and nothing here executes. Where the rule-expression grammar is not yet specified (coverage matrix G-1), the `when` / `emit` blocks use the blueprint's illustrative syntax and must be re-expressed once the grammar is fixed.

Numbers marked **proposed** depend on OI-MTQ-01…04 and the Essential 1.1 card's default params; they are placeholders for the owner's decision, not decisions.

## 1. `space_template` records

One record per template key in 01. The full record for the master bedroom (the blueprint's example, completed) and the pattern for the rest.

```
kind: space_template
key: MASTER_BEDROOM_DEFAULT
space_type_code: MASTER_BEDROOM
applies_when: { usage: RESIDENTIAL }
default_attributes: { ac_type: SPLIT, ac_point_count: 1, fan_point_count: 1 }
required_measurements:            # codes from 00-conventions §2; level per 00 §5
  - { code: CORE }                # expands to the CORE set
  - { code: Wn.U, tag: WARDROBE, level: REQ }
  - { code: Wn.U, tag: BED_HEAD, level: REQ }
  - { code: Wn.OB, on_tag: WARDROBE, level: REQ }
  - { code: FL, level: REQ }
  - { code: Wn.Om.S, on_tag: [WARDROBE, BED_HEAD], level: COND, when: opening_present }
  - { code: AT.ac_type, level: REQ }
  - { code: AT.ac_point_count, level: REQ }
  - { code: AT.fan_point_count, level: REQ }
  - { code: BB, level: COND, when: beam_present }
optional_measurements: [ Wn.U:TV_UNIT, Wn.U:VANITY, Wn.U:STUDY_UNIT, Wn.U:FEATURE_WALL, NT:bed_size, NT:window_seating, AT.has_false_ceiling_existing ]
survey_checklist:                  # shown in the app in this order, after the CORE list
  - "Tag the wardrobe wall; AC unit, AC pipe, switchboard, window grill offsets on it"
  - "Floor to lintel; loft clearance above 7 ft; beam bottom"
  - "Tag the bed-head wall; usable run; window sill behind the bed"
  - "Doors to toilet and dressing: width, height, swing; not on the wardrobe wall"
  - "AC type and count; fan points"
  - "TV wall, dresser wall, study corner if wanted"
  - "Window seating candidate: window run and sill"
  - "Ask: bed size, storage, headboard, hinged/sliding, mirror, loft"
  - "Renovation: existing wardrobe and ceiling, staying or going; photos"
recommended_requirements:          # seeded PROPOSED / RECOMMENDED on property creation (§7.2)
  - { type: WARDROBE, necessity: MANDATORY }
  - { type: LOFT, necessity: MANDATORY, when: "ceiling_height_mm - 2134 >= 450" }
  - { type: FALSE_CEILING, necessity: MANDATORY, when: "project_kind = NEW", else: OPTIONAL }
  - { type: CEILING_LIGHTING, necessity: MANDATORY, with: FALSE_CEILING }
  - { type: BED, necessity: OPTIONAL }
  - { type: SIDE_TABLE, necessity: OPTIONAL, with: BED }
  - { type: DRESSER, necessity: OPTIONAL, unless: child_space DRESSING }
  - { type: TV_UNIT, necessity: OPTIONAL }
  - { type: WALL_PANELLING, necessity: WISHLIST }
  - { type: STUDY_UNIT, necessity: WISHLIST }
  - { type: WINDOW_SEATING, necessity: WISHLIST }
scope_rule_group: BEDROOM_RULES
typical_dimensions: { source: ADR-012 D3 medians, per_property_type: true }     # values loaded by the owner, not here
sanity_ranges_mm: { length: [3600, 5500], width: [3300, 4900], ceiling_height: [2750, 3200], wardrobe_run: [1800, 3600] }
```

Pattern for the others (content in 01 §n.1, n.2, n.3/n.4, n.8):

| Key | `space_type_code` | `applies_when` | `scope_rule_group` | Mandatory requirements | Notes |
|---|---|---|---|---|---|
| `LIVING_DEFAULT` | `LIVING`, `LIVING_DINING`, `FAMILY_LOUNGE` | RESIDENTIAL | `LIVING_RULES` | TV_UNIT (not for FAMILY_LOUNGE), FALSE_CEILING (NEW), CEILING_LIGHTING | 01 §1 |
| `DINING_DEFAULT` | `DINING` | RESIDENTIAL | `LIVING_RULES` | CROCKERY_UNIT; FALSE_CEILING when the living ceiling is included | 01 §2 |
| `KITCHEN_DEFAULT` | `KITCHEN` | RESIDENTIAL (variant `applies_when usage COMMERCIAL` for `PANTRY`) | `KITCHEN_RULES` | KITCHEN base, KITCHEN wall, KITCHEN_LOFT (clearance), soft-close, tandems, PLUMBING | 01 §3 |
| `UTILITY_DEFAULT` | `UTILITY`, `WASH_AREA`, `LAUNDRY` | RESIDENTIAL | `KITCHEN_RULES` | none | 01 §4 |
| `MASTER_BEDROOM_DEFAULT` | `MASTER_BEDROOM` | RESIDENTIAL | `BEDROOM_RULES` | above | 01 §5 |
| `DRESSING_DEFAULT` | `DRESSING`, `WALK_IN_CLOSET` | RESIDENTIAL | `BEDROOM_RULES` | WARDROBE per tagged wall | 01 §5.9 |
| `BEDROOM_DEFAULT` | `BEDROOM`, `PARENTS_BEDROOM`, `SERVANT_ROOM` (no mandatory) | RESIDENTIAL | `BEDROOM_RULES` | WARDROBE (+LOFT, soft-close) | 01 §6 |
| `CHILDREN_BEDROOM_DEFAULT` | `CHILDREN_BEDROOM` | RESIDENTIAL | `BEDROOM_RULES` | WARDROBE | + STUDY_UNIT RECOMMENDED | 
| `GUEST_BEDROOM_DEFAULT` | `GUEST_BEDROOM`, `GUEST_SUITE` | RESIDENTIAL | `BEDROOM_RULES` | none | 01 §7 |
| `STUDY_DEFAULT` | `STUDY`, `HOME_OFFICE` | RESIDENTIAL | `STUDY_RULES` | STUDY_UNIT | 01 §8 |
| `POOJA_DEFAULT` | `POOJA` | RESIDENTIAL | `LIVING_RULES` | POOJA_UNIT | 01 §9 |
| `BALCONY_DEFAULT` | `BALCONY`, `SIT_OUT` | any | `OUTDOOR_RULES` | none | 01 §10 |
| `TERRACE_DEFAULT` | `TERRACE`, `GARDEN`, `PORCH`, `PARKING` | any | `OUTDOOR_RULES` | none | 01 §11, 02 §6 |
| `TOILET_DEFAULT` | `TOILET`, `POWDER_ROOM` | any | `TOILET_RULES` | none | 01 §12 |
| `COMMERCIAL_RECEPTION_DEFAULT` | `RECEPTION` | COMMERCIAL | `COMMERCIAL_RULES` | RECEPTION_DESK, PARTITION (zone edges) | 01 §13 |
| `COMMERCIAL_CABIN_DEFAULT` | `CABIN` | COMMERCIAL | `COMMERCIAL_RULES` | STUDY_UNIT, PARTITION | |
| `COMMERCIAL_WORKSTATION_DEFAULT` | `WORKSTATION_AREA` | COMMERCIAL | `COMMERCIAL_RULES` | WORKSTATION, PARTITION | |
| `COMMERCIAL_CONFERENCE_DEFAULT` | `CONFERENCE`, `TRAINING_ROOM` | COMMERCIAL | `COMMERCIAL_RULES` | conference table (CUSTOM), PARTITION | |
| `COMMERCIAL_WAITING_DEFAULT` | `WAITING_AREA` | COMMERCIAL | `COMMERCIAL_RULES` | none | |
| `COMMERCIAL_RETAIL_DEFAULT` | `RETAIL_FLOOR` | COMMERCIAL | `COMMERCIAL_RULES` | PARTITION (zone edges) | display units RECOMMENDED |
| `COMMERCIAL_BILLING_DEFAULT` | `BILLING_COUNTER` | COMMERCIAL | `COMMERCIAL_RULES` | billing counter | |
| `COMMERCIAL_TRIAL_DEFAULT` | `TRIAL_ROOM` | COMMERCIAL | `COMMERCIAL_RULES` | PARTITION, mirror | |
| `COMMERCIAL_TREATMENT_DEFAULT` | `TREATMENT_ROOM` | COMMERCIAL | `COMMERCIAL_RULES` | PARTITION | vanity, storage RECOMMENDED |
| `COMMERCIAL_BACKOFFICE_DEFAULT` | `BACK_OFFICE`, `SERVER_ROOM`, `STORE` | COMMERCIAL | `COMMERCIAL_RULES` | none | |
| `COMMERCIAL_GUEST_ROOM_DEFAULT` | `GUEST_ROOM` | COMMERCIAL | `BEDROOM_RULES` | WARDROBE, BED, TV_UNIT (panel) | 02 §8.4 |
| `CUSTOM_DEFAULT` | `CUSTOM` | any | `GENERIC_RULES` | none | 01 §14 |
| `SHELL_DEFAULT` | `CUSTOM` (label "Shell L<n>") | COMMERCIAL | — (no rules; derived areas only) | none | 01 §13 shell capture |

## 2. `scope_rule` records (by group)

The blueprint's example `BEDROOM_WARDROBE_FROM_WALL` is kept verbatim as the first rule. Each rule below gives key, `when`, `emit`, `necessity`, `priority`, and `refines` where it refines an earlier emission. Dimensions use the §6.3 derived functions. "Proposed" numbers are OI-MTQ-04 placeholders.

### BEDROOM_RULES

| Key | When | Emit | Necessity | Prio |
|---|---|---|---|---|
| `BEDROOM_WARDROBE_FROM_WALL` | category SLEEPING; type ∈ {MASTER_BEDROOM, BEDROOM, CHILDREN_BEDROOM, PARENTS_BEDROOM, DRESSING, WALK_IN_CLOSET} auto; GUEST_BEDROOM / SERVANT_ROOM / GUEST_ROOM only when confirmed; wall tagged WARDROBE (fallback longest wall without a door, `dimension_source ASSUMED`) | `WARDROBE_HINGED` (or `WARDROBE_SLIDING` when `preferences.shutter_type = SLIDING` and run ≥ 1 800); width `wall.usable_run(clearance 50)` − obstruction spans; height `min(FL, 2134)`; depth 600; option LOFT when `CH − 2134 ≥ 450` with loft height `CH − 2134` | MANDATORY (OPTIONAL for guest / servant / hotel) | 10 |
| `BEDROOM_WARDROBE_SPLIT_AT_WINDOW` | refines above; a window on the tagged wall | takes the larger segment; warning | — | 11 |
| `BEDROOM_BED_FROM_HEAD_WALL` | confirmed BED; wall tagged BED_HEAD | `BED` size from `preferences.bed_size` (QUEEN default); option HYDRAULIC from `preferences.storage_type`; headboard PANEL (width bed + 300, height 1 200 **proposed**) or CUSHION | OPTIONAL | 20 |
| `BEDROOM_SIDE_TABLES` | refines BED; (head-wall usable run − bed width) ÷ 2 ≥ 400 | `STORAGE_BOXES` bedside × 2 (or 1 when only one side fits), width min(600, side) | OPTIONAL | 21 |
| `BEDROOM_HEADBOARD_SUPPRESS_FEATURE_WALL` | BED.PANEL emitted and head wall tagged FEATURE_WALL | suppresses `FEATURE_WALL` panelling on that wall | — | 22 |
| `BEDROOM_DRESSER` | confirmed DRESSER; wall tagged VANITY; no child DRESSING | `VANITY_UNIT` dresser, width min(usable_run, 1 200), + mirror | OPTIONAL | 30 |
| `BEDROOM_TV_UNIT` | confirmed TV_UNIT; wall tagged TV_UNIT | as `LIVING_TV_UNIT_FROM_WALL` (box; panel option) | OPTIONAL | 31 |
| `BEDROOM_STUDY_UNIT` | confirmed STUDY_UNIT; wall tagged STUDY_UNIT | as `STUDY_DESK_FROM_WALL` | OPTIONAL (RECOMMENDED seed for CHILDREN_BEDROOM) | 32 |
| `BEDROOM_CEILING` | FALSE_CEILING confirmed, or auto when project NEW and type MASTER_BEDROOM | `FALSE_CEILING_GYPSUM`, area `space.ceiling_area`; cove `perimeter` when `preferences.design = COVE`; AC cassette cut-out count | MANDATORY (NEW, master) / OPTIONAL | 40 |
| `BEDROOM_CEILING_LIGHTS` | refines CEILING | `FALSE_CEILING_LIGHTS` count = ceiling_area ÷ density (card default) + `ELECTRICAL.SPOTS` | with ceiling | 41 |
| `BEDROOM_WINDOW_SEATING` | confirmed WINDOW_SEATING; a window with sill 400–700 and usable run ≥ 1 200 | `WINDOW_SEATING` seat width × 450 height; arch W × H | OPTIONAL | 50 |
| `BEDROOM_FEATURE_WALL` | confirmed WALL_PANELLING / WALLPAPER / TEXTURE_PAINT; wall tagged FEATURE_WALL | `FEATURE_WALL` by preference; area `wall_area_net` of that wall | OPTIONAL | 51 |
| `DRESSING_WARDROBE_FROM_WALLS` | type DRESSING / WALK_IN_CLOSET; every wall tagged WARDROBE | one `WARDROBE_HINGED` (or open-shelf variant) per tagged wall; corner deduction 600 **proposed** once per internal corner between tagged walls; door-swing arc excluded | MANDATORY | 10 |

### LIVING_RULES

| Key | When | Emit | Necessity | Prio |
|---|---|---|---|---|
| `LIVING_TV_UNIT_FROM_WALL` | type ∈ {LIVING, LIVING_DINING} auto; FAMILY_LOUNGE / bedrooms when confirmed; wall tagged TV_UNIT (fallback longest wall without a door, ASSUMED) | `TV_UNIT`: box width from `preferences.unit_style` (BOX_ONLY: 1 800 **proposed**; BOX_SIDE_STORAGE: usable_run; FULL_PANELLING: usable_run with panel to `CH` − ceiling drop); side-storage height capped at window sill − 50 | MANDATORY (living) | 10 |
| `LIVING_CEILING` | auto when project NEW; else confirmed | `FALSE_CEILING_GYPSUM` area `ceiling_area` − cassette cut-outs; cove `perimeter` − OPEN edges; cloud run designer-stated (ASSUMED) | MANDATORY (NEW) / RECOMMENDED | 20 |
| `LIVING_CEILING_LIGHTS` | refines CEILING | panel / COB / spot counts by density; profile light `run_length` = cove run when `preferences.profile = true` | with ceiling | 21 |
| `LIVING_FEATURE_WALL` | confirmed; wall tagged FEATURE_WALL; not the TV wall when `TV_UNIT.PANEL` emitted | `FEATURE_WALL` panelling (`area_wh` usable_run × `CH`), wallpaper (`rolls`), texture (`wall_area_net`) | OPTIONAL | 30 |
| `LIVING_CROCKERY` | confirmed CROCKERY_UNIT or (no DINING space on the property and auto seed); wall tagged CROCKERY_UNIT | `CROCKERY_UNIT` width usable_run (cap 2 400 **proposed**), height 2 134 or `FL` | RECOMMENDED | 40 |
| `DINING_CROCKERY_FROM_WALL` | type DINING auto; wall tagged CROCKERY_UNIT | same | MANDATORY | 10 |
| `DINING_CEILING` | type DINING; `LIVING_CEILING` emitted INCLUDED on the same property, or confirmed | `FALSE_CEILING_GYPSUM` | MANDATORY when living ceiling included | 20 |
| `DINING_WASH_VANITY` | basin counter observed (note) on a DINING or passage wall; confirmed VANITY | `VANITY_UNIT` dresser style, width counter − 50, height counter − 100 | RECOMMENDED | 30 |
| `LIVING_PARTITION` | confirmed PARTITION; partition line sketched | `PARTITION` laminate / fluted, `area_wh` length × height | OPTIONAL | 50 |
| `LIVING_FOYER_UNIT` | confirmed FOYER_UNIT / SHOE_RACK; W1 stretch tagged SHOE_RACK ≥ 900 | `STORAGE_BOXES` tall (or `FOYER_UNIT`), width stretch, height `FL` | RECOMMENDED | 60 |
| `LIVING_WINDOW_SEATING` | as bedroom | | OPTIONAL | 70 |
| `LIVING_BAR_UNIT` | confirmed BAR_UNIT | `CUSTOM_ITEM`, dimensions from `target_dimensions`, `override_reason` required | OPTIONAL | 80 |
| `POOJA_UNIT_FROM_WALL` | type POOJA auto, or a wall tagged POOJA_UNIT on LIVING / DINING | `POOJA_UNIT` width usable_run (cap 1 500 **proposed** for niche form), height `FL` or stated; options DOOR / DOOR_CNC when a door frame exists (W × H from the opening), BEADING perimeter, ASTA_CHAKRA count 1, drawers | MANDATORY (POOJA space) / RECOMMENDED (niche) | 10 |
| `POOJA_CEILING_LIGHTS` | confirmed CEILING_LIGHTING in POOJA | spots count 2 **proposed**, profile run = unit width | RECOMMENDED | 20 |

### KITCHEN_RULES

| Key | When | Emit | Necessity | Prio |
|---|---|---|---|---|
| `KITCHEN_BASE_FROM_RUNS` | type KITCHEN (PANTRY commercial) auto; walls tagged KITCHEN_RUN | `KITCHEN_BASE_UNIT`: run = Σ usable_run(tagged walls, clearance 25 **proposed**) − 600 per internal corner **proposed** − fridge niche − utility door span; height = counter height − top (observed) else card default | MANDATORY | 10 |
| `KITCHEN_SINK_BASE` | refines BASE; drain offset known | sink base 900 **proposed** centred on the drain (or stated); warning if a window-sill conflict | — | 11 |
| `KITCHEN_HOB_BASE` | refines BASE; gas line or chimney outlet offset known | hob base 600–900 centred on the outlet; warning if gas line and outlet differ by > 300 | — | 12 |
| `KITCHEN_WALL_FROM_RUNS` | auto (declinable); tagged walls | `KITCHEN_WALL_UNIT`: run = Σ usable_run − window spans (+ 50 each side) − chimney span (900 **proposed**); height card default; bottom at 1 450 **proposed** from floor | MANDATORY (declinable → exclusion) | 20 |
| `KITCHEN_LOFT_FROM_CLEARANCE` | refines WALL; clearance = min(FL, BB, CH) − (base + 600 gap + wall-unit height) ≥ 450 | `KITCHEN_LOFT_UNIT`: run = wall-unit run; height = clearance | MANDATORY when emitted | 21 |
| `KITCHEN_TALL_UNIT` | fridge niche or appliance list present; confirmed | tall unit (NEW LINE) width niche − 50, height `FL` | RECOMMENDED | 30 |
| `KITCHEN_ISLAND` | confirmed BREAKFAST_COUNTER; island sketch | `KITCHEN_BASE_UNIT` island: run = island length (× 2 when double-sided); overhang (NEW LINE) `area_wd` | OPTIONAL | 40 |
| `KITCHEN_TANDEMS` | refines BASE | `KITCHEN.TANDEM` count = card default per run (overridable with reason) | with base | 50 |
| `KITCHEN_SOFT_CLOSE` | refines BASE / WALL / LOFT | `KITCHEN.SOFT_CLOSE*` shutter_area per product | with product | 51 |
| `KITCHEN_PLUMBING_LUMP` | type KITCHEN; one per property (shared with UTILITY) | plumbing lump; `RISK` warning when inlet or drain absent | MANDATORY | 60 |
| `KITCHEN_DISMANTLE` | project RENOVATION; existing cabinets noted "going" | dismantling (NEW LINE / preparation note) | RECOMMENDED | 70 |
| `UTILITY_WALL_UNIT` | type UTILITY / WASH_AREA / LAUNDRY; confirmed; tagged wall | `UTILITY_WALL_UNIT` run usable_run, height min(card default, sill − 50); bottom ≥ 1 000 above a washing machine **proposed**; finish MEMBRANE when zone SEMI_OPEN | RECOMMENDED | 10 |
| `UTILITY_BASE` / `UTILITY_LOFT` / `UTILITY_TALL` | confirmed | as kitchen formulas | OPTIONAL | 20 |

### STUDY_RULES

| Key | When | Emit | Necessity | Prio |
|---|---|---|---|---|
| `STUDY_DESK_FROM_WALL` | type STUDY / HOME_OFFICE / CABIN auto; bedrooms when confirmed; wall tagged STUDY_UNIT | `STUDY_UNIT` desk width usable_run(clearance 50), depth 600, height 750 **proposed**; stops at a window with sill < 900 | MANDATORY (study, cabin) | 10 |
| `STUDY_OVERHEAD_STORAGE` | refines DESK; confirmed (RECOMMENDED seed) | storage width = desk width − window span − 100; height = min(FL, 2 134) − 750 − 450 **proposed** | RECOMMENDED | 11 |
| `STUDY_BOOKSHELF` | confirmed BOOKSHELF; second wall tagged WARDROBE / STUDY_UNIT | `STORAGE_BOXES` tall or `STUDY_UNIT.STORAGE` full height | RECOMMENDED (HOME_OFFICE) | 20 |
| `STUDY_PARTITION` | study carved from living (parent LIVING); sketch | `PARTITION` or glass (NEW LINE) | OPTIONAL | 30 |
| `STUDY_ELECTRICAL_POINTS` | HOME_OFFICE / CABIN; points count captured | contributes `count` to `PROJECT_ELECTRICAL` | — | 40 |

### TOILET_RULES

| Key | When | Emit | Necessity | Prio |
|---|---|---|---|---|
| `TOILET_VANITY` | confirmed VANITY; wall tagged VANITY | counter present → `VANITY_UNIT` width counter − 50, height counter − 100, depth ≤ 450 when the door arc overlaps; else `VANITY_UNIT.TOILET` 2×2 lump; finish moisture-resistant (assumption) | RECOMMENDED | 10 |
| `TOILET_MIRROR` | refines VANITY | `VANITY_UNIT.MIRROR` count 1 (size from preference) | with vanity | 11 |
| `TOILET_STORAGE_ABOVE` | confirmed; dado height known | storage above: width vanity width, height from dado / counter + 450 to sill or 2 134 | OPTIONAL | 12 |
| `TOILET_TALL_STORAGE` | confirmed; tagged wall in the dry zone | `STORAGE_BOXES` tall (marine) | OPTIONAL | 20 |
| `TOILET_CEILING` | confirmed | `FALSE_CEILING_GYPSUM` moisture-resistant variant | OPTIONAL | 30 |

### OUTDOOR_RULES

| Key | When | Emit | Necessity | Prio |
|---|---|---|---|---|
| `OUTDOOR_FINISH_OVERRIDE` | any furniture item emitted in a SEMI_OPEN / OUTDOOR space | sets `finish_code = MEMBRANE` (or marine option) and lists the assumption | — | 1 |
| `OUTDOOR_UTILITY_SUBSET` | BALCONY with `has_drain` and a washing-machine note | enables `UTILITY_WALL_UNIT` on this instance | — | 5 |
| `OUTDOOR_COUNTER` | confirmed BAR_UNIT / outdoor kitchen; wall tagged KITCHEN_RUN in the covered part | `KITCHEN_BASE_UNIT` outdoor variant | OPTIONAL | 10 |
| `OUTDOOR_SEATING` | confirmed; sketch | `CUSTOM_ITEM` with reason | OPTIONAL | 20 |
| `OUTDOOR_FLOORING` | confirmed FLOORING | deck / turf (NEW LINE) `floor_area` | OPTIONAL | 30 |
| `OUTDOOR_PAINT_EXTERIOR` | confirmed PAINTING on an outdoor space | contributes `wall_area_net` to `PROJECT_PAINTING_EXTERIOR` | — | 40 |

### COMMERCIAL_RULES

| Key | When | Emit | Necessity | Prio |
|---|---|---|---|---|
| `COMMERCIAL_PARTITIONS_FROM_ZONE_EDGES` | usage COMMERCIAL; any wall row with type PARTITION and note "proposed" | one `PARTITION` (laminate / fluted) or glass (NEW LINE) per row, `area_wh` length × (CH or ceiling height per preference); both faces count for painting | MANDATORY | 5 |
| `COMMERCIAL_RECEPTION_DESK` | type RECEPTION auto; tag or sketch | reception desk (NEW LINE) `area_wd` + front panel `area_wh` | MANDATORY | 10 |
| `COMMERCIAL_WORKSTATIONS_FROM_LAYOUT` | type WORKSTATION_AREA auto; sketch rows × seats, module | workstation (NEW LINE) `count`; validate Σ module widths ≤ run; warning + ASSUMED otherwise | MANDATORY | 10 |
| `COMMERCIAL_CABIN_DESK` | type CABIN auto | `STUDY_DESK_FROM_WALL` + credenza `STORAGE_BOXES`/`WARDROBE_HINGED` on the storage wall | MANDATORY (desk) / RECOMMENDED (storage) | 10 |
| `COMMERCIAL_CONFERENCE_TABLE` | type CONFERENCE / TRAINING_ROOM auto; table footprint | conference table (NEW LINE) `area_wd`; screen wall `TV_UNIT.PANEL`; credenza | MANDATORY (table) | 10 |
| `COMMERCIAL_DISPLAY_UNITS` | type RETAIL_FLOOR; walls tagged DISPLAY_RUN (proposed tag) | display units (NEW LINE) `area_wh` | RECOMMENDED | 10 |
| `COMMERCIAL_BILLING_COUNTER` | type BILLING_COUNTER auto; sketch | billing counter (NEW LINE) `area_wd` + front | MANDATORY | 10 |
| `COMMERCIAL_TRIAL_ROOM` | type TRIAL_ROOM auto | partitions (edges) + mirror `count` 1 | MANDATORY | 10 |
| `COMMERCIAL_TREATMENT_ROOM` | type TREATMENT_ROOM | `TOILET_VANITY` subset + storage; washable finish assumption | RECOMMENDED | 10 |
| `COMMERCIAL_CEILING` | confirmed per zone or throughout | `FALSE_CEILING_GYPSUM` or grid (NEW LINE) `ceiling_area` | RECOMMENDED | 20 |
| `COMMERCIAL_LIGHTING` | refines CEILING | panel / spot counts by commercial density (card default) | with ceiling | 21 |
| `COMMERCIAL_FLOORING` | confirmed | carpet / vinyl (NEW LINE) `floor_area` | OPTIONAL | 30 |
| `COMMERCIAL_ELECTRICAL_POINTS` | seats / desks / counters captured | contributes counts to `PROJECT_ELECTRICAL` | — | 40 |

### GENERIC_RULES

Each of `BEDROOM_WARDROBE_FROM_WALL`, `LIVING_TV_UNIT_FROM_WALL`, `STUDY_DESK_FROM_WALL`, `KITCHEN_BASE_FROM_RUNS` / `KITCHEN_WALL_FROM_RUNS`, `LIVING_FEATURE_WALL`, `LIVING_CEILING`, `LIVING_CEILING_LIGHTS` cloned with `when.space_category = OTHER`, `auto: false`, `necessity: OPTIONAL`; plus `GENERIC_CUSTOM_ITEM` (confirmed CUSTOM requirement → `CUSTOM_ITEM` with `target_dimensions`, manual rate, reason required).

### PROJECT_RULES

As [02-property-templates.md](02-property-templates.md) §10.

## 3. `quantity_formula` records (by product and line)

Each record: `(product_key, line_code)` → kind, inputs, rounding, wastage, min_quantity. Rounding and wastage columns are OI-MTQ-04 placeholders (blueprint proposal: SFT and RFT to 0.1 per line; wastage only where the workbook applies it).

| Product key | Line code | Kind | Inputs (mm / counts) | Rounding (proposed) | Wastage | Min |
|---|---|---|---|---|---|---|
| `WARDROBE_HINGED` / `WARDROBE_SLIDING` | `WARDROBE.BODY` | `area_wh` | width_mm, height_mm | SFT 0.1 | — | 1 |
| same | `WARDROBE.LOFT` | `area_wh` | width_mm, loft_height_mm | SFT 0.1 | — | — |
| same | `WARDROBE.SOFT_CLOSE` / `.SOFT_CLOSE_LOFT` | `shutter_area` | body / loft area, shutter_fraction (card) | SFT 0.1 | — | — |
| `WARDROBE_SLIDING` | `WARDROBE.SLIDING` | `lump` | 1 per wardrobe | NOS 1 | — | 1 |
| option GLASS | `WARDROBE.GLASS` | `area_wh` | glass shutter width × height | SFT 0.1 | — | — |
| `KITCHEN_BASE_UNIT` | `KITCHEN.BASE` | `area_wh` | run_mm (corner-deducted), base_height_mm | SFT 0.1 | — | 1 |
| `KITCHEN_WALL_UNIT` | `KITCHEN.WALL` | `area_wh` | run_mm, wall_height_mm | SFT 0.1 | — | — |
| `KITCHEN_LOFT_UNIT` | `KITCHEN.LOFT` | `area_wh` | run_mm, clearance_mm | SFT 0.1 | — | — |
| `KITCHEN_BASE_UNIT` | `KITCHEN.TANDEM` | `count` | drawer_count | NOS 1 | — | — |
| kitchen products | `KITCHEN.SOFT_CLOSE*` | `shutter_area` | area, fraction | SFT 0.1 | — | — |
| `KITCHEN_PLUMBING` | plumbing lump (card code to confirm) | `lump` | 1 | — | — | 1 |
| `UTILITY_WALL_UNIT` | `UTILITY.WALL` | `area_wh` | run, height | SFT 0.1 | — | — |
| `TV_UNIT` | `TV_UNIT.BOX` / `.STORAGE` / `.PANEL` | `area_wh` | width, height each | SFT 0.1 | — | — |
| `TV_UNIT` | `TV_UNIT.SOFT_CLOSE*` | `shutter_area` | — | SFT 0.1 | — | — |
| `CROCKERY_UNIT` | `CROCKERY_UNIT.BODY` / `.GLASS` | `area_wh` | width, height / glass area | SFT 0.1 | — | — |
| `STUDY_UNIT` | `STUDY_UNIT.DESK` / `.STORAGE` | `area_wh` | width, height per card basis | SFT 0.1 | — | — |
| `VANITY_UNIT` | `VANITY_UNIT.TOILET` | `lump` or `area_wh` per card | — | — | — | — |
| `VANITY_UNIT` | `VANITY_UNIT.DRESSER` | `area_wh` | width, height | SFT 0.1 | — | — |
| `VANITY_UNIT` | `VANITY_UNIT.MIRROR` | `count` | 1 | NOS 1 | — | — |
| `BED` | `BED.QUEEN` / `BED.KING` | `area_wh` (W × L) | card standard | SFT 0.1 | — | — |
| `BED` | `BED.HYDRAULIC` / `BED.CUSHION` | `lump` | 1 | — | — | — |
| `BED` | `BED.PANEL` | `area_wh` | headboard width, height | SFT 0.1 | — | — |
| `STORAGE_BOXES` | `STORAGE_BOXES.TALL` / `.BEDSIDE_BOX` / `.BEDSIDE_TABLE` | `area_wh` or `count` per card | — | — | — | — |
| `POOJA_UNIT` | `POOJA_UNIT.UNIT` / `.DOOR` / `.DOOR_CNC` | `area_wh` | — | SFT 0.1 | — | — |
| `POOJA_UNIT` | `POOJA_UNIT.BEADING` | `run_length` | perimeter | RFT 0.1 | — | — |
| `POOJA_UNIT` | `POOJA_UNIT.ASTA_CHAKRA` | `count` | 1 | — | — | — |
| `WINDOW_SEATING` | `WINDOW_SEATING.SEAT` / `.ARCH` | `area_wh` | — | SFT 0.1 | — | — |
| `PARTITION` | `PARTITION.LAMINATE` / `.FLUTED` | `area_wh` | length, height | SFT 0.1 | — | — |
| `FEATURE_WALL` | `FEATURE_WALL.PANELLING` | `area_wh` | usable_run, height | SFT 0.1 | — | — |
| `FEATURE_WALL` | wallpaper (card family) | `rolls` | wall_area_net, roll_coverage (card) | ROLL ceil | — | 1 |
| `FEATURE_WALL` | texture (card family) | `wall_area_net` | wall subset = tagged wall | SFT 0.1 | — | — |
| `FALSE_CEILING_GYPSUM` | `FALSE_CEILING.GYPSUM` | `ceiling_area` | floor_area − shafts − cassette cut-outs | SFT 0.1 | — | — |
| same | `FALSE_CEILING.COVE` | `perimeter` | perimeter − OPEN edges | RFT 0.1 | — | — |
| same | `FALSE_CEILING.CLOUD` | `run_length` | designer-stated run | RFT 0.1 | — | — |
| `FALSE_CEILING_LIGHTS` | `FALSE_CEILING.PANEL_LIGHTS` | `count` | ceiling_area ÷ density (card) | NOS 1 | — | — |
| `ELECTRICAL` | `ELECTRICAL.SPOTS` | `count` | spots | NOS 1 | — | — |
| `CEILING_PROFILE_LIGHTING` | `CEILING_PROFILE_LIGHTING.*` | `run_length` | cove run | RFT 0.1 | — | — |
| `PAINTING_INTERIOR` | `PAINTING.REPAINT` (and full-prep variant) | `wall_area_net` | Σ over in-scope indoor spaces; kitchen above dado; toilets excluded; ceilings when no false ceiling | SFT 1 | per workbook | — |
| `ELECTRICAL` | `ELECTRICAL.WIRING` | project driver | floor_area_sqft (carpet) + points | — | — | — |
| preparation package | card components (D5) | project driver | bedroom_count / level_count / floor_area_sqft / space_count / fixed | — | — | 1 |
| NEW LINE items (tall unit, overhang, glass partition, workstation, reception desk, conference table, display units, billing counter, grid ceiling, flooring, exterior painting, skirting, beading, soft furnishing, dismantling, drying rod) | — | as listed in 01 | — | — | — | — |

NEW LINE items need a rate-card line (B3, OI-MTQ-05) before a formula record can be released; until then the scope item is priced `MANUAL` with `rate_override_reason`.

## 4. Lookup content proposed (inserts only)

| Lookup | Values |
|---|---|
| `FLOORING` | `VITRIFIED`, `MARBLE`, `GRANITE`, `WOOD`, `CEMENT`, `TILE_CERAMIC`, `NONE_BARE` |
| `EXISTING_CONDITION` | `BARE_SHELL`, `FINISHED_NEW`, `OCCUPIED_GOOD`, `OCCUPIED_WORN`, `DAMP`, `CRACKED` |
| `usable_for_code` tags (JSON, validated list) | existing `WARDROBE`, `TV_UNIT`, `KITCHEN_RUN`, `BED_HEAD` + `STUDY_UNIT`, `CROCKERY_UNIT`, `VANITY`, `POOJA_UNIT`, `FEATURE_WALL`, `WORKSTATION_RUN`, `RECEPTION_DESK`, `SHOE_RACK`, `DISPLAY_RUN` |
| `obstructions[].kind` (JSON, validated list) | `SWITCHBOARD`, `AC_INDOOR`, `AC_PIPE`, `COLUMN`, `BEAM_DROP`, `PIPE`, `GAS_LINE`, `WINDOW_GRILL`, `DB_BOX`, `GEYSER`, `OTHER` |
| `property_space.attributes` keys (validated per type) | `ac_point_count`, `fan_point_count`, `has_gas_line`, `has_water_inlet`, `has_drain`, `has_loft_existing`, `ceiling_slab_type`, `natural_light`, `sunlight_side`, `kitchen_layout` (service-derived) |

## 5. What the owner is asked to confirm (feeds OI-MTQ-02 and OI-MTQ-03)

1. The template keys and `applies_when` in §1, and the MANDATORY set per space type (01 §n.3) with the reasons given.
2. The rule keys, `when` conditions and `auto` flags in §2; in particular: TV unit mandatory in living, wardrobe mandatory in master / secondary bedrooms but not guest rooms, kitchen wall units mandatory-but-declinable, loft automatic at ≥ 450 mm, partitions mandatory from commercial zone edges.
3. The proposed numeric placeholders (clearance 25/50 mm, corner deduction 600 mm, sink base 900 mm, chimney span 900 mm, wall-unit bottom 1 450 mm, headboard 1 200 mm, desk 750 mm, sliding minimum 1 800 mm, shelf clearance 450 mm) as the starting values for OI-MTQ-04, to be calibrated on the E6 replay.
4. The NEW LINE list as the input to the next rate-card version (OI-MTQ-05).
5. The lookup and tag additions in §4.
6. The quotation-readiness rows 7–13 in the playbook §10 as service checks for B2.
