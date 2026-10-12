# 00 · Conventions used by every template

These conventions bind the space-type templates, the property templates and the playbook to the blueprint's capture contract (§4.1 `space_measurement`, `space_wall`, `space_opening`; §6 measurement model). They introduce **no new columns**: every code below maps to an existing column, a JSON attribute the blueprint already reserves, or a lookup value.

## 1. Units and precision

| Item | Rule | Blueprint ref |
|---|---|---|
| Entry | Feet-inches or millimetres, chosen once per set (`measurement_set.unit_system_code`) | §6.1 (1) |
| Storage | Millimetres, integers. The client converts before submit; the server never stores fractional feet | §6.1 (1) |
| Laser | Read to the nearest 5 mm; record as read | proposed |
| Tape | Read to the nearest 10 mm (⅜ in); record as read | proposed |
| Derived areas | Server-computed in centi-square-feet (§6.3). The surveyor never enters an area except for `FREEFORM` spaces | §6.1 (3), §6.3 |
| Tolerance | ±25 mm per wall length, ±1 % floor area per space (blueprint proposal for OI-MTQ-01; **not decided**) | §16 B1 |

## 2. Measurement codes

Each measurement a surveyor captures has a short code used in the templates, the checklists and the playbook. The code names the target column.

| Code | Name | Target | Notes |
|---|---|---|---|
| `SH` | Shape | `space_measurement.shape_code` | `RECTANGULAR` / `L_SHAPE` / `POLYGON` / `FREEFORM` |
| `L` | Length | `space_measurement.length_mm` | Longer principal dimension, wall to wall at floor level, plaster to plaster |
| `W` | Width | `space_measurement.width_mm` | Shorter principal dimension |
| `CH` | Ceiling height | `space_measurement.ceiling_height_mm` | Finished floor to underside of slab or existing false ceiling (state which in `attributes.has_false_ceiling_existing`) |
| `BB` | Beam bottom | `space_measurement.beam_bottom_height_mm` | Floor to the underside of the lowest beam crossing the space |
| `FL` | Floor to lintel | `space_measurement.floor_to_lintel_mm` | Floor to the top of the tallest door frame; loft planning |
| `SA` | Stated area | `space_measurement.stated_floor_area_sqft_centi` | Only for `FREEFORM`; sets `confidence_code = LOW` |
| `PG` | Polygon | `space_measurement.polygon` | Ordered vertices for `POLYGON` |
| `FLR` | Existing flooring | `space_measurement.flooring_code` | Lookup `FLOORING` (vitrified, marble, granite, wood, cement, none) |
| `CND` | Existing condition | `space_measurement.existing_condition_code` | Lookup `EXISTING_CONDITION` (bare shell, finished-new, occupied-good, occupied-worn, damp, cracked) |
| `CF` | Confidence | `space_measurement.confidence_code` | `HIGH` (laser or tape on a finished wall) / `MEDIUM` (plan, unplastered) / `LOW` (stated, obstructed) |
| `Wn` | Wall *n* | `space_wall` row | See §3 |
| `Wn.L` | Wall length | `space_wall.length_mm` | At floor level, corner to corner |
| `Wn.H` | Wall height | `space_wall.height_mm` | Only when it differs from `CH` (sloping ceilings, duct boxes) |
| `Wn.T` | Wall type | `space_wall.wall_type_code` | `MASONRY` / `RCC` / `PARTITION` / `GLASS` / `OPEN` |
| `Wn.X` | External wall | `space_wall.is_external` | Yes / no |
| `Wn.U` | Usable-for tags | `space_wall.usable_for_code` | `WARDROBE`, `TV_UNIT`, `KITCHEN_RUN`, `BED_HEAD`, plus proposed tags in §4 |
| `Wn.OB` | Obstructions | `space_wall.obstructions` | Switchboard, AC point, pipe, column, with offset and size in mm |
| `Wn.Om` | Opening *m* on wall *n* | `space_opening` row | See §3 |
| `Wn.Om.T` | Opening type | `space_opening.opening_type_code` | `DOOR`, `WINDOW`, `FRENCH_WINDOW`, `ARCH`, `NICHE`, `VENTILATOR`, `AC_SLEEVE`, `SHAFT`, `DUCT`, `CUSTOM` |
| `Wn.Om.W/H` | Opening width, height | `space_opening.width_mm`, `height_mm` | Frame outer to frame outer |
| `Wn.Om.S` | Sill height | `space_opening.sill_height_mm` | Floor to bottom of opening |
| `Wn.Om.O` | Offset | `space_opening.offset_from_wall_start_mm` | From the wall's start corner (clockwise start) to the nearest edge of the opening |
| `Wn.Om.SW` | Swing | `space_opening.swing_code` | `IN` / `OUT` / `SLIDING` / `NONE` |
| `AT.*` | Space attributes | `property_space.attributes` JSON | Typed extras the blueprint reserves: `has_false_ceiling_existing`, `ac_type`, `flooring_existing`, `wet_area`; proposed additions in §4 |
| `PH.*` | Photos | `attachment` with `entity_type` = `property_space` / `space_wall` / `space_opening` | See playbook §5 |
| `NT.*` | Notes | `measurement_note` with `note_type_code` | `OBSERVATION` / `RISK` / `CUSTOMER_REQUEST` / `VOICE_TRANSCRIPT` |

## 3. Wall and opening labelling

1. Stand inside the space with your back to the **entry door**. The wall containing the entry door is **W1**. Number the remaining walls **clockwise**: W2 is to the right of W1, and so on. This is `space_wall.wall_index`.
2. An L-shaped or polygonal space has as many walls as it has straight segments. An open edge (living into dining with no wall) is still a wall row with `Wn.T = OPEN` so the perimeter closes (§6.3).
3. A wall's start corner is the corner you reach first going clockwise. Opening offsets are measured from that corner.
4. Openings on a wall are numbered left to right from the wall's start corner: W2.O1, W2.O2.
5. A door that belongs to an attached space (toilet door inside a bedroom) is captured once, on the parent space's wall, with `Wn.Om.T = DOOR` and a note naming the child space. The child space's own W1 is that same door seen from inside.
6. Label walls on site with masking tape and a marker (W1, W2…) **before** measuring. Photographs must show the label.

## 4. Proposed lookup and tag additions (no migration; §5.1 rule)

| Kind | Proposed value | Why |
|---|---|---|
| `usable_for_code` tag | `STUDY_UNIT`, `CROCKERY_UNIT`, `VANITY`, `POOJA_UNIT`, `FEATURE_WALL`, `WORKSTATION_RUN`, `RECEPTION_DESK`, `SHOE_RACK` | Scope rules anchor these products to a tagged wall exactly as `WARDROBE` and `TV_UNIT` do |
| `property_space.attributes` keys | `ac_point_count`, `fan_point_count`, `has_gas_line`, `has_water_inlet`, `has_drain`, `has_loft_existing`, `ceiling_slab_type` (`FLAT` / `SLOPED` / `BEAM_GRID`), `natural_light` (`GOOD` / `FAIR` / `POOR`), `sunlight_side` | Validated per space type in the service layer (§4.1 reserves typed extras) |
| `obstructions[].kind` | `SWITCHBOARD`, `AC_INDOOR`, `AC_PIPE`, `COLUMN`, `BEAM_DROP`, `PIPE`, `GAS_LINE`, `WINDOW_GRILL`, `DB_BOX`, `GEYSER`, `OTHER` | Rules subtract these from usable runs |
| `OPENING_TYPE` | none needed; `CUSTOM` covers rarities | — |
| `FLOORING` lookup | `VITRIFIED`, `MARBLE`, `GRANITE`, `WOOD`, `CEMENT`, `TILE_CERAMIC`, `NONE_BARE` | `space_measurement.flooring_code` names a lookup without listing it |
| `EXISTING_CONDITION` lookup | `BARE_SHELL`, `FINISHED_NEW`, `OCCUPIED_GOOD`, `OCCUPIED_WORN`, `DAMP`, `CRACKED` | same |

## 5. Requiredness levels (measurements, checklist items)

| Level | Meaning | Effect |
|---|---|---|
| **REQ** | Required for every instance of the space type | The space cannot be marked complete (`is_complete`) without it; submit is blocked |
| **COND** | Required when its stated condition holds | Same as REQ once the condition is true; the condition is evaluated from captured data |
| **OPT** | Optional | Absence is allowed; absence of an OPT value that a rule needs makes the resulting scope item `dimension_source = ASSUMED` and lists it under quotation assumptions (§10.1 item 9) |

## 6. Recommendation levels (scope)

| Level | Blueprint mapping | Customer-facing effect |
|---|---|---|
| **MANDATORY** | `requirement.necessity_code = MANDATORY`, seeded `PROPOSED` / `RECOMMENDED`; scope rule `auto: true`, emits `necessity: MANDATORY` | Marked mandatory on the quotation; declining needs a staff conversation (§10.1 item 6) |
| **RECOMMENDED** | `necessity_code = OPTIONAL`, seeded `PROPOSED` / `RECOMMENDED`; rule fires only when confirmed | Appears as an included line once confirmed; otherwise listed as optional (§10.1 item 5) |
| **OPTIONAL** | Seeded `PROPOSED` / `RECOMMENDED` with `necessity_code = WISHLIST`; rule fires only when confirmed | Optional section; customer may tick on the portal |

Everything is **RECOMMENDED** until the rules are calibrated, per the blueprint's own recommendation for OI-MTQ-03; this package proposes which items are MANDATORY and says why in each case.

## 7. BOQ driver vocabulary

A BOQ driver names, for one scope product, the `line_code`, the formula kind (§8.2), the named inputs, and where those inputs come from.

| Column | Values |
|---|---|
| Line code | Essential 1.1 line codes as they exist (`KITCHEN.BASE`, `WARDROBE.BODY`, …) or **NEW LINE** for lines the card does not carry |
| Formula kind | `area_wh`, `area_wd`, `run_length`, `count`, `lump`, `floor_area`, `ceiling_area`, `wall_area_net`, `perimeter`, `rolls`, `shutter_area` |
| Inputs | Named inputs in mm or counts, referencing measurement codes or derived values (`space.floor_area`, `wall.usable_run`) |
| Source | `MEASURED` (directly captured), `DERIVED` (computed from walls), `ASSUMED` (template default), `TYPICAL` (ADR-012 D3 median) |

Line-code status legend used throughout:

| Mark | Meaning |
|---|---|
| (card) | Exists on the Essential 1.1 rate card; the quantity basis is unchanged |
| **NEW LINE** | Not on the card; a B3 rate-card addition under OI-MTQ-05, or a `MANUAL` rate with `rate_override_reason` until then |
| (project) | Project-level line scaled by a declared driver (§9.3): `floor_area_sqft`, `bedroom_count`, `level_count`, `space_count`, `fixed` |

## 8. Estimate driver vocabulary

| Driver | Where it acts | Values |
|---|---|---|
| Tier | `scope.tier_code`, `scope_item.tier_code` | `ESSENTIAL` / `PREMIUM` / `LUXURY` |
| Finish | `scope_item.finish_code` | `LAMINATE`, `ACRYLIC`, `VENEER`, `PU`, `GLASS`, `MEMBRANE`, `CUSTOM` |
| Project-line driver | `estimator_rate_item` driver (§9.3) | `floor_area_sqft`, `bedroom_count`, `level_count`, `space_count`, `fixed` |
| Adjustment | `cost_estimate_adjustment` | `FLOOR_FACTOR` (duplex, upper floors), `SITE_FACTOR` (no lift, restricted hours, distance), `TRANSPORT`, `ALLOWANCE` (custom features, ADR-012 D9), `DISCOUNT_*` |
| Pricing basis | `cost_estimate.pricing_basis_code` | `MEASURED` when every included line's dimensions are MEASURED or DERIVED; else `MIXED` or `TYPICAL`, which produce a range |
| Confidence | `space_measurement.confidence_code` | A `LOW` space forces `MIXED` basis for its lines |

## 9. Photo and note minimums

Every space: one photo from the entry door, one per wall showing the label, one of the ceiling, one of the floor, one per opening, one per obstruction. Every risk observed: a `RISK` note with a photo. Details in the playbook §5.
