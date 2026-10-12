# 01 · Space-type templates

One template per space type the mission names. Each template is the content of one catalogue `space_template` record (blueprint §5.2) plus the scope rules of its group (§8.1) and the BOQ drivers of the products those rules emit (§8.2). Codes, levels and driver vocabulary are defined in [00-conventions.md](00-conventions.md). Nothing here changes the schema; every value lands in an existing column, JSON attribute or lookup.

**Product keys** named below (`WARDROBE_HINGED`, `KITCHEN_BASE_UNIT`, `TV_UNIT`, …) are catalogue product keys that must exist in the pinned release before a rule references them (B2 release validation). The blueprint names the first few; the rest are proposed here with the same naming pattern and map one-to-one onto the Essential 1.1 line families.

**Typical dimensions** are not given as numbers. Each template says which medians it needs from ADR-012 D3 and gives a **sanity range** the verifier uses to flag a suspicious value. A sanity range is never a pricing default.

## Index

| # | Space type (mission) | Blueprint code(s) | Category | Template key | Rule group |
|---|---|---|---|---|---|
| 1 | Living | `LIVING`, `LIVING_DINING` (combined), `FAMILY_LOUNGE`, `FOYER` (child) | LIVING | `LIVING_DEFAULT` | `LIVING_RULES` |
| 2 | Dining | `DINING` | LIVING | `DINING_DEFAULT` | `LIVING_RULES` |
| 3 | Kitchen | `KITCHEN` | SERVICE (`wet_area`) | `KITCHEN_DEFAULT` | `KITCHEN_RULES` |
| 4 | Utility | `UTILITY`, `WASH_AREA`, `LAUNDRY` | SERVICE (`wet_area`) | `UTILITY_DEFAULT` | `KITCHEN_RULES` |
| 5 | Master Bedroom | `MASTER_BEDROOM` (+ `DRESSING` / `WALK_IN_CLOSET` / `TOILET` children) | SLEEPING | `MASTER_BEDROOM_DEFAULT` | `BEDROOM_RULES` |
| 6 | Bedroom | `BEDROOM`, `CHILDREN_BEDROOM`, `PARENTS_BEDROOM` | SLEEPING | `BEDROOM_DEFAULT`, `CHILDREN_BEDROOM_DEFAULT` | `BEDROOM_RULES` |
| 7 | Guest Bedroom | `GUEST_BEDROOM`, `GUEST_SUITE` | SLEEPING | `GUEST_BEDROOM_DEFAULT` | `BEDROOM_RULES` |
| 8 | Study | `STUDY`, `HOME_OFFICE` | WORK | `STUDY_DEFAULT` | `STUDY_RULES` |
| 9 | Pooja | `POOJA` | LIVING | `POOJA_DEFAULT` | `LIVING_RULES` |
| 10 | Balcony | `BALCONY`, `SIT_OUT` | OUTDOOR / SEMI-OPEN | `BALCONY_DEFAULT` | `OUTDOOR_RULES` |
| 11 | Terrace | `TERRACE` | OUTDOOR / SEMI-OPEN | `TERRACE_DEFAULT` | `OUTDOOR_RULES` |
| 12 | Toilet | `TOILET`, `POWDER_ROOM` | ATTACHED (`counts_as_toilet`, `wet_area`) | `TOILET_DEFAULT` | `TOILET_RULES` |
| 13 | Commercial Space | `RECEPTION`, `CABIN`, `WORKSTATION_AREA`, `CONFERENCE`, `PANTRY`, `RETAIL_FLOOR`, `TRIAL_ROOM`, `BILLING_COUNTER`, `TREATMENT_ROOM`, `BACK_OFFICE`, `SERVER_ROOM`, `WAITING_AREA` | WORK / SERVICE / COMMERCIAL | `COMMERCIAL_<TYPE>_DEFAULT` | `COMMERCIAL_RULES` |
| 14 | Custom Space | `CUSTOM` (label required) | OTHER | `CUSTOM_DEFAULT` | `GENERIC_RULES` |

Rule groups proposed beyond the blueprint's examples (`BEDROOM_RULES`): `LIVING_RULES`, `KITCHEN_RULES`, `STUDY_RULES`, `TOILET_RULES`, `OUTDOOR_RULES`, `COMMERCIAL_RULES`, `GENERIC_RULES`, and the project-level group `PROJECT_RULES` (painting, electrical, preparation package; see [02-property-templates.md](02-property-templates.md) §9).

---

## CORE — the capture set every indoor space inherits

Every template below says "CORE applies" and then lists only what it adds or relaxes.

### CORE required measurements

| Code | What | Level | Notes |
|---|---|---|---|
| `SH` | Shape | REQ | `RECTANGULAR` is the default; choose `L_SHAPE` or `POLYGON` the moment a space has more than four walls or an open edge |
| `L`, `W` | Principal dimensions | COND: `SH ∈ {RECTANGULAR, L_SHAPE}` | For `L_SHAPE` give the overall envelope; the walls carry the true outline |
| `PG` | Polygon vertices | COND: `SH = POLYGON` | Must close within the verification tolerance (§6.2) |
| `SA` | Stated area | COND: `SH = FREEFORM` | Sets `CF = LOW`; allowed only with a `RISK` note saying why the space could not be measured |
| `CH` | Ceiling height | REQ | Verification rule (§6.2) fails the set without it for every non-FREEFORM space |
| `Wn.L` | Every wall length | REQ | Including `OPEN` edges, so the perimeter closes |
| `Wn.T` | Every wall type | REQ | Default `MASONRY`; `RCC` matters for drilling and anchoring, `PARTITION` for load, `GLASS` for nothing anchored |
| `Wn.Om.T/W/H` | Every opening's type, width, height | REQ | Every door, window, ventilator, arch, niche, shaft, duct and AC sleeve |
| `Wn.Om.S` | Sill height | COND: opening type ∈ {`WINDOW`, `FRENCH_WINDOW`, `VENTILATOR`, `NICHE`, `AC_SLEEVE`} | Drives wall-unit and window-seating heights |
| `Wn.Om.O` | Opening offset | REQ for every opening | Without it `wall.usable_run` cannot be split around the opening; rules fall back to "longest wall without a door" and mark the item `ASSUMED` |
| `FLR` | Existing flooring | REQ | Protection package and flooring lines |
| `CND` | Existing condition | REQ | Preparation package, painting preparation |
| `CF` | Confidence | REQ | Defaults `HIGH`; the surveyor lowers it, never raises it |
| `PH.*` | Photo minimums | REQ | Conventions §9 |

### CORE optional measurements

| Code | What | When it matters |
|---|---|---|
| `BB` | Beam bottom | Any beam crosses the space; drives false-ceiling drop and loft clearance. Becomes COND = REQ when `AT.ceiling_slab_type = BEAM_GRID` or any beam is visible |
| `FL` | Floor to lintel | Any space that may take a loft (wardrobe, kitchen, storage) |
| `Wn.H` | Wall height differing from `CH` | Sloping ceilings, duct boxing, split levels |
| `Wn.X` | External wall | Villas and independent houses: REQ there (see 02 §4); apartments: optional, used for dampness risk |
| `Wn.OB` | Obstructions | Any switchboard, AC unit, pipe, column or DB box on a wall that may carry furniture. Becomes REQ on every wall tagged `Wn.U` |
| `AT.has_false_ceiling_existing` | Existing false ceiling | Renovations: REQ when `project_kind_code = RENOVATION` |
| `AT.ac_type`, `AT.ac_point_count` | AC provision | Any space with AC; drives ceiling design and electrical |
| `AT.fan_point_count` | Fan points | Electrical, ceiling |
| `AT.natural_light`, `AT.sunlight_side` | Light | Designer input; finish fading advice; no pricing effect |

### CORE survey checklist (prefix for every space's own list)

1. Stand at the entry door; label W1 and continue clockwise; photograph each label.
2. Shape → principal dimensions → ceiling height → beam bottom if any.
3. Each wall: length, type, obstructions with offsets; tag usable-for.
4. Each opening: type, width, height, sill, offset, swing.
5. Flooring, condition, confidence.
6. Photos: entry view, each wall, ceiling, floor, each opening, each obstruction.
7. Notes: risks, customer requests heard in this room.
8. Mark complete only when the app's completeness check is green.

---

## 1. Living (`LIVING`, `LIVING_DINING`, `FAMILY_LOUNGE`)

Template key `LIVING_DEFAULT` (`applies_when: {usage: RESIDENTIAL}`); rule group `LIVING_RULES`; zone `INDOOR`. A combined living-dining is one `LIVING_DINING` space with an `OPEN` edge recorded where the dining zone begins, plus a `NT.OBSERVATION` naming the split; it must not be split into two spaces unless a wall or partition exists. A foyer is a child space (`parent_space_id`) when it is a distinct alcove; otherwise it is W1's stretch, tagged `SHOE_RACK`.

### 1.1 Required measurements

CORE applies, plus:

| Code | What | Level | Notes |
|---|---|---|---|
| `Wn.U = TV_UNIT` | The TV wall, tagged | REQ | Exactly one wall; if the customer has not decided, tag the longest wall without a door and add a `CUSTOMER_REQUEST` note |
| `Wn.U = FEATURE_WALL` | The feature wall, tagged | COND: customer asks for panelling, wallpaper or texture | May coincide with the TV wall |
| `Wn.OB` on the TV wall | Switchboard, AC indoor unit, window grill, DB box | REQ | Offsets and sizes; the TV unit width is `usable_run` minus these |
| `Wn.Om.S` on the TV wall | Sill of any window on the TV wall | REQ when present | Side storage height is limited by it |
| `AT.ac_type`, `AT.ac_point_count` | AC provision | REQ | Split or cassette changes the ceiling design and the cove run |
| `AT.fan_point_count` | Fan points | REQ | Ceiling lighting layout |
| `BB` | Beam bottom | COND: any beam | Cove and cloud ceilings are set out from the beam |

### 1.2 Optional measurements

| Code | What | Why |
|---|---|---|
| `Wn.U = CROCKERY_UNIT` | Crockery wall when it sits in the living space | Crockery unit width |
| `Wn.U = SHOE_RACK` | Foyer stretch of W1 | Foyer or shoe unit |
| Partition line (`NT` + sketch) | Where a living/dining or living/foyer partition would stand: length and height wanted | `PARTITION.LAMINATE` / `PARTITION.FLUTED` width × height |
| Sofa-back wall length (`Wn.L` of the tagged wall) | Beading length | Beading `run_length` |
| `AT.has_false_ceiling_existing` | Existing ceiling | Renovation: demolition note and ceiling area |
| `AT.natural_light` | Light | Designer only |
| Window curtain-rod wall widths | `Wn.L` and `Wn.Om.W` already give this | Soft furnishing (not priced on Essential 1.1; **NEW LINE**) |

### 1.3 Mandatory scope recommendations

| Requirement type | Product key | Anchor | Why mandatory |
|---|---|---|---|
| `TV_UNIT` | `TV_UNIT` (box; side storage and panelling as options) | Wall tagged `TV_UNIT` | Every residential quotation Veda issues carries a TV unit for the living space; its absence is the single most common later add-on. Rule `LIVING_TV_UNIT_FROM_WALL`, `auto: true` |
| `FALSE_CEILING` | `FALSE_CEILING_GYPSUM` | `space.ceiling_area` | Lighting, AC concealment and the cove run depend on it; mandatory for `NEW` projects, RECOMMENDED for `RENOVATION` when `AT.has_false_ceiling_existing = true` |
| `CEILING_LIGHTING` | `FALSE_CEILING_LIGHTS` (panel, COB, spot) | Ceiling area, lighting density | Follows the ceiling; mandatory whenever the ceiling is included |

### 1.4 Optional scope recommendations

| Requirement type | Product key | Anchor | Level |
|---|---|---|---|
| `WALL_PANELLING` | `FEATURE_WALL` (panelling) | Wall tagged `FEATURE_WALL` | RECOMMENDED |
| `WALLPAPER` | `FEATURE_WALL` (wallpaper) | Same wall; `wall_area_net` of that wall | OPTIONAL |
| `TEXTURE_PAINT` | `FEATURE_WALL` (texture) | Same wall | OPTIONAL |
| `CROCKERY_UNIT` | `CROCKERY_UNIT` | Wall tagged `CROCKERY_UNIT` | RECOMMENDED when no dining space exists |
| `PARTITION` | `PARTITION` (laminate or fluted) | Partition line | OPTIONAL |
| `FOYER_UNIT` / `SHOE_RACK` | `STORAGE_BOXES` (tall) or `FOYER_UNIT` | Wall tagged `SHOE_RACK` | RECOMMENDED when a foyer stretch ≥ 900 mm exists |
| `BAR_UNIT` | `CUSTOM_ITEM` | Customer-stated | OPTIONAL |
| `WINDOW_SEATING` | `WINDOW_SEATING` | Window with sill 400–700 mm and `usable_run` ≥ 1 200 mm | OPTIONAL |
| `CEILING_LIGHTING` (profile) | `CEILING_PROFILE_LIGHTING` | Perimeter or cove run | OPTIONAL |
| `SOFT_FURNISHING` | **NEW LINE** | Window widths | OPTIONAL, priced manually until a line exists |
| `PAINTING` | project-level (02 §9) | — | — |

### 1.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| TV wall tagged → TV unit width | measurement → rule | Width = `usable_run(TV_UNIT wall, clearance 50 mm)` minus obstruction widths; missing tag → longest wall without a door, `ASSUMED` |
| Window on TV wall → side storage | measurement → rule | Side-storage height capped at `Wn.Om.S − 50 mm` on the window side |
| Ceiling included → lighting | rule → rule (`refines`) | `LIVING_CEILING_LIGHTS` refines `LIVING_CEILING` |
| `BB` present → ceiling drop | measurement → formula | Ceiling area unchanged; cove run set out at `BB`; a note on the BOQ line |
| AC cassette → ceiling cut-out | attribute → rule | `FALSE_CEILING.GYPSUM` area less the cassette; `count` of AC cut-outs on the electrical line |
| `LIVING_DINING` combined → dining rules | space → rules | `LIVING_RULES` and the dining subset both fire on the one space; crockery unit anchors to its tagged wall |
| Feature wall = TV wall | rule → rule | Panelling area excludes the TV box footprint (`TV_UNIT.PANEL` prices the panelling; `FEATURE_WALL.PANELLING` must not double-count: the rule emits one or the other) |
| Renovation + existing ceiling | attribute → rule | Adds a dismantling note; the ceiling rule drops to RECOMMENDED |

### 1.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `TV_UNIT.BOX` | (card) | `area_wh` | width = TV box width (rule), height = box height | DERIVED |
| `TV_UNIT.STORAGE` | (card) | `area_wh` | width = side-storage width(s), height = min(storage height, sill − 50) | DERIVED |
| `TV_UNIT.PANEL` | (card) | `area_wh` | width = `usable_run`, height = `CH` − skirting or ceiling drop | DERIVED |
| `TV_UNIT.SOFT_CLOSE`, `TV_UNIT.SOFT_CLOSE_STORAGE` | (card) | `shutter_area` | box / storage area × shutter fraction | DERIVED |
| `FALSE_CEILING.GYPSUM` | (card) | `ceiling_area` | `space.floor_area` − shafts/ducts − cassette cut-outs | DERIVED |
| `FALSE_CEILING.COVE` / `.CLOUD` | (card) | `perimeter` or `run_length` | cove: `space.perimeter` minus OPEN edges; cloud: designer-stated run | DERIVED / ASSUMED |
| `FALSE_CEILING.PANEL_LIGHTS` | (card) | `count` | ceiling area ÷ density from the card's default params | DERIVED |
| `ELECTRICAL.SPOTS` | (card) | `count` | spot count from the lighting rule | DERIVED |
| `CEILING_PROFILE_LIGHTING.*` | (card) | `run_length` | cove run | DERIVED |
| `FEATURE_WALL.PANELLING` | (card) | `area_wh` | feature wall `usable_run` × `CH` | DERIVED |
| `FEATURE_WALL.WALLPAPER` | (card family `FEATURE_WALL.*`) | `rolls` | `wall_area_net` of the feature wall ÷ roll coverage, ceil | DERIVED |
| `FEATURE_WALL.TEXTURE` | (card family) | `wall_area_net` | feature wall only | DERIVED |
| `CROCKERY_UNIT.BODY`, `.GLASS` | (card) | `area_wh` | tagged wall `usable_run` × height (default 2 134 mm, ADR-012) | DERIVED |
| `PARTITION.LAMINATE` / `.FLUTED` | (card) | `area_wh` | partition line length × height | MEASURED (sketch) |
| `STORAGE_BOXES.TALL` (foyer) | (card) | `area_wh` | `SHOE_RACK` stretch × height | DERIVED |
| `WINDOW_SEATING.SEAT`, `.ARCH` | (card) | `area_wh` / `area_wh` | window `usable_run` × seat height; arch W × H | DERIVED |
| Beading (sofa back) | **NEW LINE** | `run_length` | tagged wall length | MEASURED |
| Skirting (if replaced) | **NEW LINE** | `perimeter` | `space.perimeter` − openings at floor | DERIVED |
| `PAINTING.REPAINT` | (card, project) | `wall_area_net` | Σ net wall area of included spaces | DERIVED |

### 1.7 Estimate drivers

| Driver | Living-specific effect |
|---|---|
| Tier | Default finishes: ESSENTIAL laminate on TV unit and crockery; PREMIUM acrylic or high-gloss; LUXURY veneer or PU, glass profiles. Panelling and wallpaper are "decorative finishes" (tier-independent card lines) |
| Finish | `scope_item.finish_code` per item; a Budget quotation may carry a veneer TV panel (`CARD_FINISH_VARIANT`, B3) |
| Project-line driver | Living floor area feeds `floor_area_sqft`; `space_count` +1 |
| Adjustments | None specific; `ALLOWANCE` (ADR-012 D9 custom-features band) is computed on room work, so the living subtotal contributes |
| Pricing basis | `MEASURED` when the TV wall and ceiling come from captured walls; any `ASSUMED` width makes the line banded |
| Typical medians needed (ADR-012 D3) | TV unit width, panelling area, crockery width, ceiling area per home size; sanity ranges: living 3.0–4.9 m wide, 3.6–6.7 m long, TV wall 2.4–4.3 m |

### 1.8 Survey checklist (`survey_checklist`)

CORE list, then:

1. Tag the TV wall; measure every obstruction on it (switchboard, AC indoor unit, DB box, window grill) with offsets.
2. Note window sill heights on the TV wall and on any wall that may carry window seating.
3. Tag the feature wall if the customer wants one; say which treatment they mentioned.
4. Count AC points and fan points; record AC type (split / cassette / none / provision only).
5. Beam bottom height if any beam crosses the room; photograph the beam.
6. Record an OPEN edge toward dining or foyer with its length.
7. Sketch and measure any partition the customer wants; height too.
8. Crockery wall tag if the crockery unit will live here.
9. Foyer stretch length and depth if a shoe or foyer unit is wanted.
10. Existing false ceiling (renovation): condition, drop, and whether it stays.
11. Ask and note: TV size planned, sofa size, any pooja niche wanted here.

---

## 2. Dining (`DINING`)

Template key `DINING_DEFAULT`; rule group `LIVING_RULES` (dining subset); zone `INDOOR`. A dining alcove with no wall separating it from the living space is **not** a separate space (see 1).

### 2.1 Required measurements

CORE applies, plus:

| Code | What | Level | Notes |
|---|---|---|---|
| `Wn.U = CROCKERY_UNIT` | Crockery wall, tagged | REQ | The dining space's principal product |
| `Wn.OB` on the crockery wall | Switchboard, wash-basin counter, window grill | REQ | Usable run |
| `Wn.Om` toward kitchen | Kitchen door or pass-through opening | REQ | Width, height, swing; a serving hatch is `NICHE` |
| `AT.fan_point_count` | Fan point | REQ | Ceiling design |

### 2.2 Optional measurements

| Code | What | Why |
|---|---|---|
| Wash-basin counter: width, depth, height (`NT` + sketch, `Wn.OB kind = PIPE`) | Vanity below the dining wash basin | `VANITY_UNIT.DRESSER` style unit or **NEW LINE** |
| Partition line toward living or kitchen | Partition | `PARTITION.*` |
| `BB` | Beam bottom | Cove or cloud ceiling |
| `AT.ac_type` | AC | Ceiling |
| Pass-through hatch `NICHE` dimensions | Hatch shutters | `CUSTOM_ITEM` |

### 2.3 Mandatory scope recommendations

| Requirement type | Product key | Anchor | Why mandatory |
|---|---|---|---|
| `CROCKERY_UNIT` | `CROCKERY_UNIT` | Wall tagged `CROCKERY_UNIT` | The dining space exists in the quotation only through its storage; without a crockery unit the space has no room work and is listed as painting-only. Rule `DINING_CROCKERY_FROM_WALL`, `auto: true` |
| `FALSE_CEILING` | `FALSE_CEILING_GYPSUM` | `space.ceiling_area` | Mandatory when the living ceiling is included (continuity); otherwise RECOMMENDED |

### 2.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| `VANITY` (wash-basin counter unit) | `VANITY_UNIT` (dresser style) | RECOMMENDED when a wash basin is present |
| `PARTITION` | `PARTITION` | OPTIONAL |
| `CEILING_LIGHTING` | `FALSE_CEILING_LIGHTS`, `CEILING_PROFILE_LIGHTING` | RECOMMENDED with the ceiling |
| `WALL_PANELLING` / `WALLPAPER` / `TEXTURE_PAINT` | `FEATURE_WALL` | OPTIONAL |
| `BAR_UNIT` | `CUSTOM_ITEM` | OPTIONAL |

### 2.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Crockery wall tagged → unit width | measurement → rule | `usable_run` − obstructions; height 2 134 mm default (ADR-012) or `FL` when a loft is wanted |
| Living ceiling included → dining ceiling | rule → rule across spaces | `DINING_CEILING` fires MANDATORY when `LIVING_CEILING` emitted INCLUDED on the same property; the rule reads sibling scope items, which §8.1 allows through `refines` within one generation run |
| Wash basin present → vanity below | measurement → rule | Width = counter width − 50 mm; height = counter height − 100 mm |
| Dining inside `LIVING_DINING` | space → rules | Dining subset fires on the combined space; no second ceiling |

### 2.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `CROCKERY_UNIT.BODY` | (card) | `area_wh` | `usable_run` × height | DERIVED |
| `CROCKERY_UNIT.GLASS` | (card) | `area_wh` | glass-shutter fraction × body area, or designer-stated | DERIVED / ASSUMED |
| `VANITY_UNIT.DRESSER` | (card) | `area_wh` | counter width × unit height | MEASURED |
| `VANITY_UNIT.MIRROR` | (card) | `count` | 1 when a mirror is wanted | ASSUMED |
| `FALSE_CEILING.GYPSUM`, `.COVE`, `.PANEL_LIGHTS` | (card) | as Living | — | DERIVED |
| `PARTITION.*` | (card) | `area_wh` | sketch | MEASURED |
| `FEATURE_WALL.*` | (card) | as Living | — | DERIVED |
| `PAINTING.REPAINT` | (card, project) | `wall_area_net` | — | DERIVED |

### 2.7 Estimate drivers

| Driver | Dining-specific effect |
|---|---|
| Tier / finish | Crockery unit glass shutters are a decorative finish line; tier sets the body finish |
| Project-line driver | Floor area; `space_count` +1 only when the dining is a separate space |
| Pricing basis | `MEASURED` when the crockery wall is tagged and measured |
| Typical medians needed | Crockery unit width per home size; sanity: 1.2–2.4 m |

### 2.8 Survey checklist

CORE list, then:

1. Tag the crockery wall; obstructions with offsets.
2. Measure the wash-basin counter (width, depth, height) and the pipe positions below it.
3. Kitchen door or hatch: width, height, swing; note if the customer wants a sliding door or a pass-through.
4. Fan point and AC provision.
5. Sketch any partition wanted toward the living space or kitchen.
6. Ask and note: dining table size (4 / 6 / 8 seats) for the designer.

---

## 3. Kitchen (`KITCHEN`)

Template key `KITCHEN_DEFAULT`; rule group `KITCHEN_RULES`; zone `INDOOR`; `wet_area = true`. The kitchen has the most measurements and the most rules; an incomplete kitchen blocks the quotation more often than any other space.

### 3.1 Required measurements

CORE applies, plus:

| Code | What | Level | Notes |
|---|---|---|---|
| `Wn.U = KITCHEN_RUN` | Every wall that will carry cabinets, tagged | REQ | One tag per wall; the layout (straight, L, U, parallel, island) is **derived** from the count and adjacency of tagged walls and recorded in `AT.kitchen_layout` by the service, not entered |
| `Wn.OB kind = PIPE / GAS_LINE / DB_BOX / SWITCHBOARD / COLUMN` on tagged walls | Every service point: water inlet, drain, gas line, chimney duct outlet, geyser, switchboard, electrical DB | REQ | Offsets from the wall start, height from floor, size |
| Sink position | `Wn.OB kind = PIPE` with a `NT` "sink" and offset | REQ | Fixes the sink base cabinet; the drain offset decides it when the customer has no preference |
| Hob position | `Wn.OB kind = GAS_LINE` offset, or customer-stated offset with `CUSTOMER_REQUEST` note | REQ | Fixes the hob base and the chimney above |
| Chimney duct outlet | `Wn.Om.T = DUCT` or `AC_SLEEVE`, offset and height | REQ | Wall-unit cut-out; the hob must align |
| Window(s) on tagged walls | `Wn.Om` with `S` | REQ | Wall units stop at the window; the sink usually sits under it |
| `CH` and `BB` | Ceiling, beam bottom | REQ (`BB` COND: beam present) | Loft height = `BB` or `CH` − wall-unit top |
| `FL` | Floor to lintel | REQ | Loft top when no beam |
| `Wn.H` where a duct box lowers the ceiling over a run | Wall height | COND | Loft height on that run |
| Counter top: existing or not; height and depth if existing (`NT.OBSERVATION`, photo) | Counter | REQ | Base unit height = counter height − top thickness; granite laying is client scope (ADR-012) |
| `AT.has_gas_line`, `AT.has_water_inlet`, `AT.has_drain` | Services present | REQ | Plumbing lump line |
| `AT.ac_point_count` | AC | OPT → REQ when provision exists | Ceiling |
| Utility door / opening to utility | `Wn.Om` | REQ when a utility exists | Cabinet run ends at it |

### 3.2 Optional measurements

| Code | What | Why |
|---|---|---|
| Island or breakfast counter footprint (`NT` + sketch: length, depth, height, clearances to runs) | Island / breakfast counter | `KITCHEN.BASE` on the island; **NEW LINE** for a counter overhang |
| Refrigerator niche width, depth, height | Fridge slot | Run split; a tall unit beside it |
| Appliance list (`NT.CUSTOMER_REQUEST`): built-in oven, microwave, dishwasher, water purifier, washing machine in kitchen | Appliance garages and tall units | Tall unit widths; electrical points |
| Loft existing (`AT.has_loft_existing`) and its depth | Existing civil loft | Loft line dropped or reduced |
| Dado tile height (`NT`) | Tiles already laid | Wall units sit on the dado; client scope |
| Existing cabinets to dismantle (renovation) | Dismantling | **NEW LINE** or preparation package note |
| Door swing into the kitchen | `Wn.Om.SW` | Cabinet clearance on W1 |
| `AT.natural_light` | Light | Designer |

### 3.3 Mandatory scope recommendations

| Requirement type | Product key | Anchor | Why mandatory |
|---|---|---|---|
| `KITCHEN` (base units) | `KITCHEN_BASE_UNIT` | Every wall tagged `KITCHEN_RUN` | A kitchen space in scope without base units is a contradiction; rule `KITCHEN_BASE_FROM_RUNS`, `auto: true` |
| `KITCHEN` (wall units) | `KITCHEN_WALL_UNIT` | Tagged walls, less windows and the chimney span | Every Veda kitchen quotation carries wall units; the customer may decline (recorded as a declined requirement → exclusion) |
| `KITCHEN_LOFT` | `KITCHEN_LOFT_UNIT` | Tagged walls, height = min(`FL`, `BB`, `CH`) − wall-unit top | Mandatory when the loft height ≥ 450 mm (blueprint §8.1 option rule); otherwise not emitted |
| Soft-close hardware | `KITCHEN.SOFT_CLOSE*` lines on the base, wall and loft products | Shutter area | Essential 1.1 specification promise; never a separate requirement |
| Tandem drawers | `KITCHEN.TANDEM` | Drawer count (card default per run length) | Specification promise; count derived from base run (card default params), adjustable |
| `PLUMBING` | `KITCHEN_PLUMBING` (lump) | Services present | Plumbing labour and materials is a lump on every kitchen (ADR-012 §3.1) |

### 3.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| `BREAKFAST_COUNTER` | `KITCHEN_BASE_UNIT` (island) + **NEW LINE** overhang | OPTIONAL |
| Tall unit / pantry pull-out / appliance garage | `KITCHEN_TALL_UNIT` (**NEW LINE** family, or priced as base run per card default) | RECOMMENDED when a fridge niche or appliance list exists |
| Kitchen accessories (wicker baskets, rolling shutters, pull-outs) | Catalogue option group on `KITCHEN_BASE_UNIT` | OPTIONAL; Essential 1.1 places them in the Design Personalisation Allowance, not the kitchen subtotal |
| `FALSE_CEILING` | `FALSE_CEILING_GYPSUM` | OPTIONAL (kitchens often keep the slab) |
| `CEILING_LIGHTING` | `FALSE_CEILING_LIGHTS` | OPTIONAL |
| `ELECTRICAL` (additional points for appliances) | project-level `ELECTRICAL` with a per-space count | RECOMMENDED when the appliance list has ≥ 1 item without an existing point |
| Granite / quartz counter laying | Client scope on Essential 1.1 (ADR-012); quotation exclusion | — |
| Dado tiling, sink, taps | Client scope; exclusion | — |

### 3.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Tagged runs → layout → base run length | measurement → derived | Run = Σ `usable_run` of tagged walls, corners counted once (the formula record's corner deduction, proposed 600 mm per internal corner) |
| Window on a tagged wall → wall-unit run | measurement → rule | Wall-unit run excludes `Wn.Om.W` + 50 mm each side; under-window base continues |
| Chimney outlet → hob position → wall-unit cut-out | measurement → rule | The hob base is centred on the duct unless the customer states otherwise; a mismatch raises a `RISK` note and a warning in `generation_run` |
| Sink drain offset → sink base | measurement → rule | Sink base 900 mm (card default) centred on the drain |
| `FL` / `BB` → loft | measurement → option | Loft emitted when clearance ≥ 450 mm; height = clearance |
| Utility door → run end | measurement → rule | Run stops at the opening offset |
| Counter existing → base height | observation → rule | Base height = counter height − top; else card default |
| Fridge niche → tall unit | measurement → rule | Tall unit width = niche width − 50 mm |
| Services absent → plumbing scope | attribute → rule | `has_water_inlet = false` or `has_drain = false` raises a `RISK` note; plumbing lump stays, civil work is excluded |
| Appliances → electrical points | request → project rule | Counts feed the electrical project line |
| Utility space exists → `UTILITY.WALL` | space → sibling rules | See 4 |

### 3.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `KITCHEN.BASE` | (card) | `area_wh` (run × base height) | run = Σ usable runs − corner deduction; height = card default (counter − top) | DERIVED |
| `KITCHEN.WALL` | (card) | `area_wh` | run = Σ usable runs − windows − chimney span; height = card default wall-unit height | DERIVED |
| `KITCHEN.LOFT` | (card) | `area_wh` | run = wall-unit run; height = min(`FL`, `BB`, `CH`) − (base + gap + wall-unit) | DERIVED |
| `KITCHEN.TANDEM` | (card) | `count` | drawer count: card default per run, overridable | DERIVED / ASSUMED |
| `KITCHEN.SOFT_CLOSE`, `.SOFT_CLOSE_WALL`, `.SOFT_CLOSE_LOFT` | (card) | `shutter_area` | respective areas × shutter fraction | DERIVED |
| Plumbing labour and materials | (card, lump; code to confirm on the card) | `lump` | 1 | ASSUMED |
| `KITCHEN.BASE` (island) | (card) | `area_wh` | island length × base height, both long sides if double-sided | MEASURED (sketch) |
| Tall unit | **NEW LINE** | `area_wh` | niche width − 50 × (`FL` or 2 134) | DERIVED |
| Counter overhang / breakfast ledge | **NEW LINE** | `area_wd` | length × overhang depth | MEASURED |
| `FALSE_CEILING.GYPSUM`, `.PANEL_LIGHTS` | (card) | `ceiling_area`, `count` | — | DERIVED |
| `ELECTRICAL.SPOTS` | (card) | `count` | under-cabinet / spot count | ASSUMED |
| Dismantling existing kitchen | **NEW LINE** or preparation note | `lump` | — | — |
| `PAINTING.REPAINT` | (card, project) | `wall_area_net` | kitchen walls above dado only when included; the formula record for kitchens subtracts dado height × tagged-wall length | DERIVED |

### 3.7 Estimate drivers

| Driver | Kitchen-specific effect |
|---|---|
| Tier | ESSENTIAL laminate; PREMIUM acrylic or high-gloss laminate shutters with the same carcass; LUXURY PU or glass shutters; hardware tier follows the tier's specification |
| Finish | Shutter finish is per item; a PREMIUM finish on an ESSENTIAL quotation resolves through `CARD_FINISH_VARIANT` |
| Accessories | Priced inside the ADR-012 D9 allowance on Essential 1.1; on PREMIUM/LUXURY per OI-MTQ-05 |
| Project-line driver | Floor area; the kitchen's dado reduces painting area |
| Adjustments | `SITE_FACTOR` when the counter must be cut or civil work is needed for services (staff judgement with reason) |
| Pricing basis | `MEASURED` only when every tagged wall has its openings and service offsets captured; a kitchen without a chimney offset is `MIXED` |
| Typical medians needed | Base run, wall run, loft height, drawer count per home size; sanity: run 2.4–7.3 m, counter height 820–900 mm, wall-unit bottom 1 400–1 500 mm from floor |

### 3.8 Survey checklist

CORE list, then:

1. Tag every wall that will carry cabinets; confirm the layout with the customer (straight / L / U / parallel / island).
2. Water inlet, drain, gas line: offset along the wall and height from floor, photograph each.
3. Chimney duct outlet or sleeve: offset, height, diameter.
4. Switchboards and DB box on tagged walls: offset, size, height.
5. Window on each tagged wall: width, height, sill, offset; note the grill projection.
6. Existing counter: height, depth, top thickness; is it staying?
7. Floor to lintel and beam bottom over each run; ceiling drops from duct boxing.
8. Door to utility: width, height, swing; door to dining likewise.
9. Fridge slot: width, depth, height; where the customer wants it if not fixed.
10. Appliance list from the customer: hob size, chimney width, oven, microwave, dishwasher, purifier, washing machine here or in utility.
11. Dado height; tiles present or planned (client scope).
12. Existing loft or cabinets: staying, going; photograph.
13. Island or breakfast counter wanted: sketch with clearances to runs (minimum 900 mm aisle, note if less).
14. Ask and note: sink type and size preference, hob position preference, tall unit wish.

---

## 4. Utility (`UTILITY`, `WASH_AREA`, `LAUNDRY`)

Template key `UTILITY_DEFAULT`; rule group `KITCHEN_RULES` (utility subset); zone `INDOOR` or `SEMI_OPEN` (set per instance: a utility balcony is `SEMI_OPEN`); `wet_area = true`.

### 4.1 Required measurements

CORE applies, plus:

| Code | What | Level | Notes |
|---|---|---|---|
| `Wn.U = KITCHEN_RUN` | The wall that will carry the utility wall unit, tagged | REQ | Usually one |
| Washing-machine position and tap/drain offsets (`Wn.OB kind = PIPE`) | Services | REQ | The unit sits above or beside |
| Window / ventilator / grill opening | `Wn.Om` with `S` | REQ | Wall unit height limited by the sill or grill |
| `AT.has_water_inlet`, `AT.has_drain` | Services | REQ | |
| Zone | `property_space.zone_code` | REQ | `SEMI_OPEN` utility: weather exposure note; finish advice (membrane / marine ply option) |

### 4.2 Optional measurements

| Code | What | Why |
|---|---|---|
| `FL`, `BB` | Loft | Loft storage above the unit |
| Geyser / gas cylinder / water purifier position (`Wn.OB`) | Obstructions | Unit cut-outs |
| Clothes-drying provision (`NT`) | Pulley or rod | **NEW LINE** or exclusion |
| Sink present: size (`NT`) | Utility sink base | `KITCHEN.BASE` run |

### 4.3 Mandatory scope recommendations

| Requirement type | Product key | Anchor | Why mandatory |
|---|---|---|---|
| None | — | — | A utility is frequently left bare. The utility wall unit is RECOMMENDED, not mandatory; marking it mandatory would force a staff conversation on every quotation that omits it |

### 4.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| `KITCHEN` (utility wall unit) | `UTILITY_WALL_UNIT` → `UTILITY.WALL` | RECOMMENDED |
| `KITCHEN` (utility base / sink base) | `KITCHEN_BASE_UNIT` | OPTIONAL |
| `LOFT` | `KITCHEN_LOFT_UNIT` | OPTIONAL when clearance ≥ 450 mm |
| `STORAGE_BOX` (tall broom / store unit) | `STORAGE_BOXES` (tall) | OPTIONAL |
| `PLUMBING` | shared with kitchen lump | — |

### 4.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Kitchen exists → plumbing lump shared | space → space | One plumbing lump per property for kitchen + utility; the formula record marks `min_quantity 1`, `max 1` |
| `SEMI_OPEN` zone → finish | attribute → rule | Rule sets `finish_code = MEMBRANE` or marine-grade option; a note under assumptions |
| Window or grill → wall-unit height | measurement → rule | Height = min(card default, sill − 50) |
| Washing machine position → run split | measurement → rule | Wall unit above the machine keeps 1 000 mm clearance from floor to bottom (proposed) |

### 4.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `UTILITY.WALL` | (card) | `area_wh` | `usable_run` × wall-unit height | DERIVED |
| `KITCHEN.BASE` (utility base) | (card) | `area_wh` | run × base height | DERIVED |
| `KITCHEN.LOFT` (utility loft) | (card) | `area_wh` | run × clearance | DERIVED |
| `STORAGE_BOXES.TALL` | (card) | `area_wh` | width × `FL` | DERIVED |
| Drying rod / pulley | **NEW LINE** | `count` | 1 | — |

### 4.7 Estimate drivers

| Driver | Utility-specific effect |
|---|---|
| Finish | Exposure forces membrane / marine option (finish variant rate, B3) |
| Project-line driver | Floor area counts; painting usually excluded (open or tiled) |
| Pricing basis | `MEASURED` with one tagged wall captured |
| Typical medians | Utility wall-unit run; sanity 0.9–2.4 m |

### 4.8 Survey checklist

CORE list, then:

1. Zone: enclosed room or open balcony? Grill present? Weather exposure?
2. Tag the wall for the unit; washing-machine position, tap and drain offsets.
3. Window / grill: width, height, sill.
4. Loft clearance above the planned unit.
5. Geyser, cylinder, purifier positions.
6. Sink present: size; staying?
7. Ask and note: washing machine type (front / top load) and size; drying arrangement wanted.

---

## 5. Master Bedroom (`MASTER_BEDROOM`)

Template key `MASTER_BEDROOM_DEFAULT` (the blueprint's §5.2 example); rule group `BEDROOM_RULES`; zone `INDOOR`; `counts_as_bedroom`. Attached dressing, walk-in closet and toilet are **child spaces** (`parent_space_id`) with their own templates (dressing below; toilet in 12). The master bedroom carries the richest bedroom rule set; Bedroom (6) and Guest Bedroom (7) are the same template with fewer mandatory items.

### 5.1 Required measurements

CORE applies, plus:

| Code | What | Level | Notes |
|---|---|---|---|
| `Wn.U = WARDROBE` | Wardrobe wall, tagged | REQ | One wall; two when the customer wants two wardrobes (two tags, two instances). The rule's fallback (longest wall without a door) applies only when no tag exists and marks the item `ASSUMED` |
| `Wn.U = BED_HEAD` | Bed-head wall, tagged | REQ | Fixes the headboard and the side-table wall; must not be the wardrobe wall |
| `Wn.OB` on the wardrobe wall | Switchboard, AC indoor unit, AC pipe, window grill | REQ | Wardrobe `usable_run` |
| `FL` | Floor to lintel | REQ | Loft height = `CH` − 2 134 mm when ≥ 450 mm (§8.1); `FL` caps the wardrobe when the door frame is on the wardrobe wall |
| `Wn.Om.S` of windows on the wardrobe and bed-head walls | Sills | REQ when present | A wardrobe cannot cross a window; a low sill behind the bed limits the headboard |
| `AT.ac_type`, `AT.ac_point_count` | AC | REQ | AC indoor unit is the commonest wardrobe obstruction |
| `AT.fan_point_count` | Fan | REQ | Ceiling |
| Door to attached toilet / dressing | `Wn.Om` with swing | REQ | Wardrobe wall cannot include it |
| `BB` | Beam bottom | COND: beam present | Ceiling and loft |

### 5.2 Optional measurements

| Code | What | Why |
|---|---|---|
| `Wn.U = TV_UNIT` | TV wall in the bedroom | TV unit or panel |
| `Wn.U = VANITY` | Dresser wall | Dresser vanity width |
| `Wn.U = STUDY_UNIT` | Study corner wall | Study unit in the bedroom |
| `Wn.U = FEATURE_WALL` | Head-wall treatment | Panelling / wallpaper / cushion headboard |
| Bed size wanted (`NT.CUSTOMER_REQUEST`: queen / king / custom with W × L) | Bed | `BED.QUEEN` / `BED.KING` |
| Window seating candidate: window `usable_run` and sill | Window seating | `WINDOW_SEATING.*` |
| `AT.has_false_ceiling_existing` | Renovation | Ceiling |
| Side-table clearances (`NT`): distance from bed-head wall ends to nearest obstruction | Bedside tables | `STORAGE_BOXES.BEDSIDE_*` |
| Existing wardrobe (renovation): width, staying or going | Dismantling | note / **NEW LINE** |

### 5.3 Mandatory scope recommendations

| Requirement type | Product key | Anchor | Why mandatory |
|---|---|---|---|
| `WARDROBE` | `WARDROBE_HINGED` (or `WARDROBE_SLIDING` when `preferences.shutter_type = SLIDING`) | Wall tagged `WARDROBE` | The blueprint's own example rule (`BEDROOM_WARDROBE_FROM_WALL`, `auto: true`, `necessity: MANDATORY`); a master bedroom quotation without a wardrobe is the exception that needs a conversation |
| `LOFT` | `WARDROBE_LOFT` (option on the wardrobe) | Same wall | Emitted automatically when `CH − 2134 ≥ 450` (§8.1); mandatory because it is the cheapest storage per square foot and omitting it is the commonest regret |
| Soft-close hardware | `WARDROBE.SOFT_CLOSE*` | Shutter area | Specification promise |
| `FALSE_CEILING` | `FALSE_CEILING_GYPSUM` | Ceiling area | Mandatory for `NEW` projects (AC concealment, lighting); RECOMMENDED for renovations |
| `CEILING_LIGHTING` | `FALSE_CEILING_LIGHTS` | Follows the ceiling | With the ceiling |

### 5.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| `BED` | `BED` (queen / king; hydraulic storage option; headboard panel or cushion) | RECOMMENDED |
| `SIDE_TABLE` | `STORAGE_BOXES` (bedside table / bedside box) | RECOMMENDED with the bed |
| `DRESSER` | `VANITY_UNIT` (dresser) | RECOMMENDED |
| `TV_UNIT` | `TV_UNIT` (box; panel optional) | RECOMMENDED when a TV wall is tagged |
| `WALL_PANELLING` / `WALLPAPER` / `TEXTURE_PAINT` on the bed-head wall | `FEATURE_WALL` or `BED.PANEL` | OPTIONAL |
| `STUDY_UNIT` | `STUDY_UNIT` | OPTIONAL |
| `WINDOW_SEATING` | `WINDOW_SEATING` | OPTIONAL |
| `WARDROBE` glass profile shutters | `WARDROBE.GLASS` option | OPTIONAL (decorative) |
| `CEILING_LIGHTING` (profile) | `CEILING_PROFILE_LIGHTING` | OPTIONAL |
| Walk-in closet / dressing | child-space template (5.9) | — |

### 5.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Wardrobe tag → width | measurement → rule | `usable_run(clearance 50)` − obstructions; a window on the tagged wall splits it: the rule takes the larger segment and warns |
| `CH`, `FL` → wardrobe height and loft | measurement → rule | Height = min(`FL`, 2 134); loft = `CH` − height when ≥ 450 |
| Bed-head tag → bed → side tables | rule → rule (`refines`) | Side-table widths = (bed-head wall `usable_run` − bed width) ÷ 2, each capped at 600 mm; emitted only when ≥ 400 mm |
| Bed size preference → bed line | requirement → rule | `BED.QUEEN` or `BED.KING`; custom W × L → `CUSTOM_ITEM` with reason |
| Hydraulic storage preference → `BED.HYDRAULIC` | requirement → line | lump |
| Headboard preference → `BED.PANEL` or `BED.CUSHION` | requirement → line | panel W × H or cushion lump; if the bed-head wall is also tagged `FEATURE_WALL`, the panel line is used and `FEATURE_WALL.PANELLING` is suppressed (no double count) |
| Dressing child space exists → dresser moves there | space → rules | `DRESSER` recommendation is suppressed in the parent and emitted in the child |
| AC on the wardrobe wall → split run | obstruction → rule | Wardrobe stops 100 mm short of the AC unit's lower edge projection; a note |
| Sliding preference + run < 1 800 mm | requirement + measurement → rule | Rule refuses sliding below 1 800 mm (proposed) and warns; hinged emitted |

### 5.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `WARDROBE.BODY` | (card) | `area_wh` | width = `usable_run`; height = min(`FL`, 2 134) | DERIVED |
| `WARDROBE.LOFT` | (card) | `area_wh` | width = same; height = `CH` − 2 134 (≥ 450) | DERIVED |
| `WARDROBE.SOFT_CLOSE`, `.SOFT_CLOSE_LOFT` | (card) | `shutter_area` | body / loft area × shutter fraction | DERIVED |
| `WARDROBE.SLIDING` | (card) | `lump` (per wardrobe) | 1 when sliding | DERIVED |
| `WARDROBE.GLASS` | (card) | `area_wh` | glass-profile shutter area (option) | ASSUMED |
| `BED.QUEEN` / `BED.KING` | (card) | `area_wh` (W × L per ADR-012) | card standard sizes | ASSUMED (standard) |
| `BED.HYDRAULIC` | (card) | `lump` | 1 | — |
| `BED.PANEL` | (card) | `area_wh` | headboard width × height (default bed width + 300, 1 200 high; proposed) | DERIVED |
| `BED.CUSHION` | (card) | `lump` | 1 | — |
| `STORAGE_BOXES.BEDSIDE_TABLE` / `.BEDSIDE_BOX` | (card) | `count` or `area_wh` per card | 2 when both sides fit | DERIVED |
| `VANITY_UNIT.DRESSER`, `.MIRROR` | (card) | `area_wh`, `count` | tagged wall `usable_run` (cap 1 200) × height; 1 mirror | DERIVED |
| `TV_UNIT.BOX`, `.PANEL` | (card) | `area_wh` | as Living | DERIVED |
| `STUDY_UNIT.DESK`, `.STORAGE` | (card) | `area_wh` | as Study | DERIVED |
| `FALSE_CEILING.*`, `ELECTRICAL.SPOTS`, `CEILING_PROFILE_LIGHTING.*` | (card) | as Living | — | DERIVED |
| `FEATURE_WALL.*` | (card) | as Living | bed-head wall | DERIVED |
| `WINDOW_SEATING.*` | (card) | as Living | — | DERIVED |
| `PAINTING.REPAINT` | (card, project) | `wall_area_net` | — | DERIVED |

### 5.7 Estimate drivers

| Driver | Master-bedroom-specific effect |
|---|---|
| Tier | ESSENTIAL laminate wardrobe; PREMIUM acrylic / high-gloss; LUXURY veneer / PU / lacquered glass. Sliding hardware is a lump at every tier |
| Finish | Per item; a mirror-finish or glass-profile shutter is a decorative line |
| Project-line driver | `bedroom_count` +1 (the preparation package on Essential 1.1 scales by home size, which becomes this driver); floor area |
| Pricing basis | `MEASURED` when wardrobe and bed-head walls are tagged with obstructions captured |
| Typical medians | Wardrobe width, loft height, dresser width per home size; sanity: room 3.3–4.9 m × 3.6–5.5 m, wardrobe 1.8–3.6 m, `CH` 2 750–3 200 mm |

### 5.8 Survey checklist

CORE list, then:

1. Tag the wardrobe wall; measure the AC unit, AC pipe drop, switchboard and window grill on it with offsets.
2. Floor to lintel; loft clearance above 7 ft; beam bottom if any.
3. Tag the bed-head wall; its usable run; window sill behind the bed if any.
4. Doors to toilet and dressing: width, height, swing; confirm they are not on the wardrobe wall.
5. AC type and count; fan points.
6. TV wall if a TV is wanted; dresser wall; study corner if wanted.
7. Window seating candidate: window run and sill.
8. Ask and note: bed size (queen / king), storage (none / hydraulic), headboard (panel / cushioned), wardrobe shutters (hinged / sliding), mirror on shutter wanted, loft wanted.
9. Renovation: existing wardrobe and ceiling, staying or going; photograph.

### 5.9 Child space: Dressing / Walk-in closet (`DRESSING`, `WALK_IN_CLOSET`)

Template key `DRESSING_DEFAULT`; rule group `BEDROOM_RULES`; `parent_space_id` = the bedroom.

| Section | Content |
|---|---|
| Required | CORE; every wall that will carry units tagged `WARDROBE` (a walk-in is typically two or three); `FL`; mirror wall tagged `VANITY` when a dresser is wanted; door swing (a hinged door into a walk-in blocks a run) |
| Optional | Island / drawer bank footprint sketch; window / ventilator; `AT.ac_point_count` |
| Mandatory | `WARDROBE` on each tagged wall (open-shelf or shuttered per preference), rule `DRESSING_WARDROBE_FROM_WALLS` |
| Optional scope | `DRESSER` (`VANITY_UNIT.DRESSER` + `.MIRROR`), `LOFT`, `CEILING_LIGHTING`, `FALSE_CEILING` |
| Dependencies | Suppresses the parent's dresser; corner deduction once per internal corner between tagged walls (same formula record as the kitchen, 600 mm proposed); door swing excludes the arc from usable run |
| BOQ drivers | `WARDROBE.BODY`, `.LOFT`, `.SOFT_CLOSE*`, `.SLIDING`, `VANITY_UNIT.DRESSER`, `.MIRROR`, `FALSE_CEILING.*` |
| Estimate | Tier / finish as the bedroom; floor area adds to the property total; `space_count` +1 |
| Checklist | Tag unit walls; corner count; door swing; mirror wall; ask open shelves vs shutters, drawer bank, dressing stool |

---

## 6. Bedroom (`BEDROOM`, `CHILDREN_BEDROOM`, `PARENTS_BEDROOM`)

Template keys `BEDROOM_DEFAULT`, `CHILDREN_BEDROOM_DEFAULT` (child-specific recommendations), `PARENTS_BEDROOM_DEFAULT` (= `BEDROOM_DEFAULT` with the accessibility checklist additions); rule group `BEDROOM_RULES`; `counts_as_bedroom`. Label by use: "Bedroom 2 (Kids)". `instance_no` increments per type.

### 6.1 Required measurements

As Master Bedroom §5.1, with one relaxation: `Wn.U = BED_HEAD` is COND (required only when a bed is wanted); a second bedroom used as a store or study has no bed-head wall. A `CHILDREN_BEDROOM` additionally requires the study-unit wall tag when a study unit is wanted (`Wn.U = STUDY_UNIT`, COND).

### 6.2 Optional measurements

As §5.2, plus for `CHILDREN_BEDROOM`: bunk-bed clearance (`CH` is already captured; the rule needs it), two-bed layout sketch; for `PARENTS_BEDROOM`: bed height preference, grab-bar wall note (not priced; `RISK`/`CUSTOMER_REQUEST`).

### 6.3 Mandatory scope recommendations

| Requirement type | Product key | Why mandatory |
|---|---|---|
| `WARDROBE` (+ `LOFT` when clearance allows, + soft-close) | `WARDROBE_HINGED` / `WARDROBE_SLIDING` | Same reasoning as the master bedroom; a bedroom in scope without a wardrobe needs a conversation |

False ceiling drops to RECOMMENDED in secondary bedrooms (it is the first thing customers cut).

### 6.4 Optional scope recommendations

As §5.4, plus for `CHILDREN_BEDROOM`: `STUDY_UNIT` RECOMMENDED; `BED` single / bunk (`CUSTOM_ITEM` for bunk, or `BED.QUEEN` when a standard size is wanted); `BOOKSHELF` (`STUDY_UNIT.STORAGE`). For `PARENTS_BEDROOM`: `BED` with hydraulic storage is OPTIONAL not RECOMMENDED (lifting), `SIDE_TABLE` RECOMMENDED.

### 6.5 Dependencies

As §5.5. Additional: a bedroom with `is_in_scope = true` but **no** confirmed requirement is still measured in full (painting, ceiling and the preparation package use it), and the quotation lists it under "measured, no furniture work".

### 6.6 BOQ drivers

As §5.6. `STUDY_UNIT.DESK` / `.STORAGE` for the children's bedroom; bunk bed → `CUSTOM_ITEM` with manual rate and reason until a line exists (**NEW LINE**).

### 6.7 Estimate drivers

As §5.7. `bedroom_count` +1 per bedroom; the preparation-package driver is `bedroom_count` (the blueprint's replacement for the BHK band).

### 6.8 Survey checklist

As §5.8, with: (a) confirm the room's use (sleeping / study / guest / store) before tagging; (b) children's room: ask single or bunk, study unit, bookshelf, and note the window side for the desk; (c) parents' room: bed height, no hydraulic storage unless asked, night-light point.

---

## 7. Guest Bedroom (`GUEST_BEDROOM`, `GUEST_SUITE`)

Template key `GUEST_BEDROOM_DEFAULT`; rule group `BEDROOM_RULES`; `counts_as_bedroom`. A `GUEST_SUITE` is a guest bedroom with an attached toilet child and, often, a small pantry niche.

### 7.1 Required measurements

As §5.1 with `Wn.U = BED_HEAD` COND and `FL` COND (required only when a wardrobe is wanted). Guest rooms are often wardrobe-light; the template must not block submit on a tag the customer has declined.

### 7.2 Optional measurements

As §5.2, plus: luggage-rack niche, sofa-cum-bed footprint, kitchenette niche (`GUEST_SUITE`).

### 7.3 Mandatory scope recommendations

None. Every guest-room item is RECOMMENDED or OPTIONAL: guest rooms are the most frequently descoped space and a mandatory flag would generate needless staff conversations.

### 7.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| `WARDROBE` (compact, 1 200–1 800 mm) + `LOFT` | `WARDROBE_HINGED` | RECOMMENDED |
| `BED` (queen, hydraulic storage optional) | `BED` | RECOMMENDED |
| `SIDE_TABLE` | `STORAGE_BOXES` | OPTIONAL |
| `FALSE_CEILING`, `CEILING_LIGHTING` | — | OPTIONAL |
| `STUDY_UNIT` (doubles as desk) | `STUDY_UNIT` | OPTIONAL |
| `TV_UNIT` | `TV_UNIT` | OPTIONAL |
| Kitchenette (`GUEST_SUITE`) | `KITCHEN_BASE_UNIT` short run | OPTIONAL |

### 7.5 Dependencies

As §5.5. The wardrobe rule in this group runs with `auto: false` for `GUEST_BEDROOM` (fires only on a confirmed requirement), which is the only behavioural difference from `BEDROOM`; it is expressed as the rule's `when.space_type_code` list, not as a separate rule.

### 7.6 BOQ drivers

As §5.6 (subset).

### 7.7 Estimate drivers

As §5.7; `bedroom_count` +1 (a guest bedroom is a bedroom for the preparation package and for the configuration label).

### 7.8 Survey checklist

As §5.8, prefixed by: confirm whether the room is in scope for furniture at all; if not, capture CORE only and mark `is_in_scope` per the customer's wish (painting still needs the walls).

---

## 8. Study (`STUDY`, `HOME_OFFICE`)

Template key `STUDY_DEFAULT`; rule group `STUDY_RULES`; zone `INDOOR`. A study corner inside a bedroom is **not** a study space; it is a `STUDY_UNIT` tag in that bedroom.

### 8.1 Required measurements

CORE applies, plus:

| Code | What | Level | Notes |
|---|---|---|---|
| `Wn.U = STUDY_UNIT` | Desk wall, tagged | REQ | |
| `Wn.Om.S` on the desk wall | Window sill | REQ when present | Overhead storage stops at the window; the desk may run under it when the sill ≥ 900 mm |
| `Wn.OB` on the desk wall | Switchboard, data point, AC unit | REQ | Desk run and overhead storage |
| `FL`, `BB` | Lintel, beam | COND: overhead storage or loft wanted | |
| `AT.ac_point_count`, `AT.fan_point_count` | AC, fan | REQ | |
| Data / power points count and positions (`Wn.OB kind = SWITCHBOARD`, `NT`) | Electrical | REQ for `HOME_OFFICE` | Electrical project line |

### 8.2 Optional measurements

| Code | What | Why |
|---|---|---|
| `Wn.U = WARDROBE` or second `STUDY_UNIT` | Bookshelf / storage wall | `STUDY_UNIT.STORAGE` full height |
| Second-seat run (`NT`) | Two-person desk | Desk run |
| Printer / CPU niche | Desk storage | option |
| `Wn.U = FEATURE_WALL` | Video-call backdrop | panelling |
| Door swing | Desk clearance | rule |

### 8.3 Mandatory scope recommendations

| Requirement type | Product key | Why mandatory |
|---|---|---|
| `STUDY_UNIT` (desk) | `STUDY_UNIT` | A study without a desk unit is a store; rule `STUDY_DESK_FROM_WALL`, `auto: true` |

### 8.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| Overhead storage | `STUDY_UNIT` option → `STUDY_UNIT.STORAGE` | RECOMMENDED |
| `BOOKSHELF` (full-height storage on a second wall) | `STUDY_UNIT.STORAGE` or `STORAGE_BOXES.TALL` | RECOMMENDED for `HOME_OFFICE` |
| `WARDROBE` (study doubling as guest room) | `WARDROBE_HINGED` | OPTIONAL |
| `FALSE_CEILING`, `CEILING_LIGHTING` | — | OPTIONAL |
| `WALL_PANELLING` (backdrop) | `FEATURE_WALL` | OPTIONAL |
| `ELECTRICAL` (extra points) | project-level | RECOMMENDED for `HOME_OFFICE` |
| Glass partition (study carved from living) | `PARTITION` / `GLASS_PARTITION` → **NEW LINE** for glass | OPTIONAL |

### 8.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Desk wall tag → desk width | measurement → rule | `usable_run(clearance 50)`; desk depth 600 (card default); desk height 750 |
| Window on the desk wall → overhead storage | measurement → rule | Storage width = run − window span − 100; if the sill < 900 the desk stops at the window |
| Overhead storage → height | measurement → rule | Height = min(`FL`, 2 134) − desk height − 450 (knee-to-shelf clearance, proposed) |
| Study carved out of living (`parent_space_id` = living) | space → rule | Partition emitted from the sketch; living `OPEN` edge converted in the designer's revision |

### 8.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `STUDY_UNIT.DESK` | (card) | `area_wh` (W × H per ADR-012) | desk width × card height basis | DERIVED |
| `STUDY_UNIT.STORAGE` | (card) | `area_wh` | storage width × storage height | DERIVED |
| `STORAGE_BOXES.TALL` | (card) | `area_wh` | bookshelf wall run × `FL` | DERIVED |
| `WARDROBE.*` | (card) | as bedroom | — | DERIVED |
| `PARTITION.LAMINATE` / `.FLUTED` | (card) | `area_wh` | sketch | MEASURED |
| Glass partition | **NEW LINE** | `area_wh` | sketch | MEASURED |
| `FALSE_CEILING.*`, `ELECTRICAL.SPOTS`, `FEATURE_WALL.*` | (card) | as Living | — | DERIVED |
| `ELECTRICAL.WIRING` | (card, project) | per card driver | points count feeds | MEASURED (count) |

### 8.7 Estimate drivers

| Driver | Study-specific effect |
|---|---|
| Tier / finish | Desk top finish; PREMIUM often requests a solid-surface or veneer top (finish variant) |
| Project-line driver | Floor area; `space_count` +1; electrical points |
| Pricing basis | `MEASURED` with the desk wall tagged |
| Typical medians | Desk width, overhead storage width; sanity: room 2.4–3.6 m × 2.7–3.6 m, desk 1.2–2.4 m |

### 8.8 Survey checklist

CORE list, then:

1. Tag the desk wall; window sill and span on it; switchboard / data point offsets.
2. Overhead storage wanted: lintel and beam bottom.
3. Second wall for bookshelf or wardrobe: tag.
4. Power and data points: count and positions; what the customer needs for work-from-home (monitors, printer).
5. Door swing relative to the desk wall.
6. AC and fan points.
7. Ask and note: one or two seats, printer / CPU space, backdrop wall treatment.

---

## 9. Pooja (`POOJA`)

Template key `POOJA_DEFAULT`; rule group `LIVING_RULES` (pooja subset); zone `INDOOR`. A pooja **room** is a space; a pooja **niche** in the living or dining space is a `NICHE` opening on that space's wall with a `POOJA_UNIT` tag on the wall, and the same rules fire on the parent space. The two are distinguished by whether a door exists.

### 9.1 Required measurements

CORE applies, plus:

| Code | What | Level | Notes |
|---|---|---|---|
| `Wn.U = POOJA_UNIT` | The altar wall, tagged | REQ | Opposite the door by convention; the customer decides |
| Niche (`Wn.Om.T = NICHE`): width, height, depth, sill | Niche | COND: niche form | Depth goes in `NT` (the opening row has no depth; propose `obstructions`-style JSON `depth_mm` on the note, or capture the niche as a `POLYGON` space when it is deep enough to stand in) |
| Door / opening: width, height, type (door, arch, open) | Entry | REQ | A door → `POOJA_UNIT.DOOR` or `.DOOR_CNC` candidate; an arch → `WINDOW_SEATING.ARCH`-style arch line (the card's arch line is under window seating; see drivers) |
| `CH`, `FL` | Heights | REQ | Unit height, loft above the unit |
| Electrical point for lamp / bell (`Wn.OB kind = SWITCHBOARD`) | Electrical | REQ | A point inside the unit |
| Ventilation: window / ventilator / exhaust (`Wn.Om`) | Smoke | REQ when present; `RISK` note when absent | Designer advice, no price |

### 9.2 Optional measurements

| Code | What | Why |
|---|---|---|
| Platform / step height existing | Base | Unit base height |
| Bell / asta-chakra wall position | Decorative | `POOJA_UNIT.ASTA_CHAKRA` |
| Storage below / beside: width | Drawers | unit option |
| Wall treatment wanted (`NT`) | Backdrop | beading / CNC panel |

### 9.3 Mandatory scope recommendations

| Requirement type | Product key | Why mandatory |
|---|---|---|
| `POOJA_UNIT` | `POOJA_UNIT` | A pooja space in scope exists for its unit; ADR-012 D9 names the pooja unit as a recurring underestimation. Rule `POOJA_UNIT_FROM_WALL`, `auto: true` |

### 9.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| Pooja door (plain or CNC-cut) | `POOJA_UNIT` option → `POOJA_UNIT.DOOR` / `.DOOR_CNC` | RECOMMENDED when a door frame exists |
| Beading backdrop | `POOJA_UNIT.BEADING` | OPTIONAL |
| Asta chakra / brass accents | `POOJA_UNIT.ASTA_CHAKRA` | OPTIONAL |
| `FALSE_CEILING` (small, with cove) | `FALSE_CEILING_GYPSUM` | OPTIONAL |
| `CEILING_LIGHTING` (spot / profile) | `ELECTRICAL.SPOTS`, `CEILING_PROFILE_LIGHTING` | RECOMMENDED |
| Drawer storage below | unit option | RECOMMENDED |
| Loft above | `WARDROBE_LOFT`-style loft via `KITCHEN_LOFT_UNIT` formula | OPTIONAL |

### 9.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Altar wall tag → unit width | measurement → rule | `usable_run` (cap 1 500 mm proposed for a niche form) |
| Door frame present → door option | measurement → rule | Door W × H from the opening row |
| Niche form on a living wall → no second space | space → rule | The pooja subset of `LIVING_RULES` fires on the living space; the TV wall and the pooja wall must differ, else a warning |
| No ventilation → risk | measurement → note | `RISK` note surfaced to the designer; no price effect |

### 9.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `POOJA_UNIT.UNIT` | (card) | `area_wh` | width × height (floor to `FL` or customer-stated) | DERIVED |
| `POOJA_UNIT.DOOR` / `.DOOR_CNC` | (card) | `area_wh` | door W × H | MEASURED |
| `POOJA_UNIT.BEADING` | (card) | `run_length` | perimeter of the backdrop | DERIVED |
| `POOJA_UNIT.ASTA_CHAKRA` | (card) | `count` | 1 | — |
| `KITCHEN.LOFT` formula reused for the loft | (card line for kitchens; a pooja loft needs **NEW LINE** or manual) | `area_wh` | width × clearance | DERIVED |
| `FALSE_CEILING.GYPSUM`, `.COVE`, `ELECTRICAL.SPOTS`, `CEILING_PROFILE_LIGHTING.*` | (card) | as Living | — | DERIVED |

### 9.7 Estimate drivers

| Driver | Pooja-specific effect |
|---|---|
| Tier / finish | Essential 1.1 prices the pooja unit in an "approved board" structure, not plywood; PREMIUM / LUXURY veneer or teak-look finishes via variants |
| Allowance | Part of the ADR-012 D9 custom-features set: the allowance band applies |
| Project-line driver | Floor area (small); `space_count` +1 when a room |
| Typical medians | Unit width and height; sanity: niche 600–1 500 mm wide, room 1.2–2.4 m square |

### 9.8 Survey checklist

CORE list (abbreviated for a niche: the parent space's CORE already covers walls), then:

1. Room or niche? Door, arch or open?
2. Tag the altar wall; width available; existing platform height.
3. Niche: width, height, depth, sill; photograph straight on.
4. Door frame: width, height; CNC door wanted?
5. Electrical point inside; bell position.
6. Ventilation: window, ventilator, exhaust; note if none.
7. Ask and note: idol sizes and count (shelf planning), drawer storage, backdrop treatment, lighting (profile / spot).

---

## 10. Balcony (`BALCONY`, `SIT_OUT`)

Template key `BALCONY_DEFAULT`; rule group `OUTDOOR_RULES`; zone `SEMI_OPEN` (enclosed balconies with glazing become `INDOOR` and inherit `LIVING_RULES` for furniture, see dependencies). Balconies are usually painting-and-flooring spaces; furniture is the exception.

### 10.1 Required measurements

CORE applies with relaxations: `FLR` and `CND` REQ; `CH` REQ (slab underside); walls: the parapet / railing edge is a wall row with `Wn.T = OPEN` (railing) or `GLASS` (glazed), and the building-face wall carries the door and window. Plus:

| Code | What | Level | Notes |
|---|---|---|---|
| Railing / parapet: height, type (`NT`), length (`Wn.L`) | Edge | REQ | Safety note; grill / glazing is client scope unless quoted (**NEW LINE**) |
| Door from the adjoining room: `Wn.Om` with swing | Access | REQ | Also recorded on the parent room's wall |
| Drain / tap present (`AT.has_drain`, `AT.has_water_inlet`) | Services | REQ | Wet balcony → utility-type rules |
| Weather exposure (`NT.OBSERVATION`: open / covered / fully enclosed) | Exposure | REQ | Finish selection |
| Zone | `zone_code` | REQ | `SEMI_OPEN` default |

### 10.2 Optional measurements

| Code | What | Why |
|---|---|---|
| Seating / planter wall tag (`Wn.U = CUSTOM` + note) | Built-in seating | `CUSTOM_ITEM` |
| Ceiling for a false ceiling in an enclosed balcony | Ceiling | `FALSE_CEILING.GYPSUM` |
| Flooring change wanted (`NT`) | Deck tiles / artificial turf | **NEW LINE** |
| Light point count | Electrical | project line |
| Washing machine here (`NT`) | Utility use | utility template on this instance |

### 10.3 Mandatory scope recommendations

None.

### 10.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| `PAINTING` (exterior-grade) | project-level painting with an exterior-grade finish variant (**NEW LINE** or variant) | RECOMMENDED when the adjoining room is painted |
| `FLOORING` (deck / turf) | **NEW LINE** | OPTIONAL |
| Built-in seating / planter box | `CUSTOM_ITEM` | OPTIONAL |
| Utility wall unit (when used as utility) | `UTILITY.WALL` via the utility template | OPTIONAL |
| `FALSE_CEILING` (enclosed only) | `FALSE_CEILING_GYPSUM` | OPTIONAL |
| Grill / glazing | client scope, exclusion | — |

### 10.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Fully enclosed → indoor rules | attribute → rules | `zone_code = INDOOR` on this instance; the designer may re-type the space to `LIVING` child space |
| Wet balcony → utility subset | attribute → rules | `has_drain` and a washing machine note select the utility recommendations |
| Exposure → finish | attribute → rule | Any furniture item here gets `finish_code = MEMBRANE` or marine option, listed under assumptions |

### 10.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `PAINTING.*` (exterior variant) | (card family) / **NEW LINE** | `wall_area_net` | building-face wall net area + parapet inner face | DERIVED |
| Deck / turf flooring | **NEW LINE** | `floor_area` | `space.floor_area` | DERIVED |
| `UTILITY.WALL` | (card) | as Utility | — | DERIVED |
| `CUSTOM_ITEM` seating | manual | `area_wd` / `lump` | sketch | MEASURED |

### 10.7 Estimate drivers

Floor area counts toward `floor_area_sqft` only when the balcony is in scope for any line; the preparation package driver excludes balconies (formula record `applies_zone: INDOOR`). `space_count` excludes `SEMI_OPEN` / `OUTDOOR` zones for the package. Pricing basis `MEASURED`.

### 10.8 Survey checklist

1. Label the building-face wall W1 (door wall) and go clockwise; the railing edge is a wall row (OPEN or GLASS).
2. Length, width, slab height; railing height and type.
3. Door and window on the building face with sills.
4. Drain, tap; washing machine use?
5. Flooring type and condition; waterproofing signs (dampness, efflorescence) → `RISK` note.
6. Exposure: open / covered / enclosed.
7. Ask and note: seating, planters, enclosure wish (client scope), lighting.

---

## 11. Terrace (`TERRACE`)

Template key `TERRACE_DEFAULT`; rule group `OUTDOOR_RULES`; zone `OUTDOOR` (open) or `SEMI_OPEN` (pergola / covered part as a child space). Duplexes and villas carry it; apartments rarely do unless a penthouse.

### 11.1 Required measurements

| Code | What | Level | Notes |
|---|---|---|---|
| `SH`, `L`, `W` or `PG` | Outline | REQ | Terraces are often polygonal; use `PG` |
| Parapet walls: `Wn.L`, height (`Wn.H`), type | Edge | REQ | `MASONRY` parapet or `OPEN` railing |
| Covered portion outline (child `POLYGON` space, `zone = SEMI_OPEN`) | Pergola / shade | COND: covered part exists | Furniture only in the covered part |
| `CH` of the covered part | Height | COND | |
| Access: door / staircase head: `Wn.Om` | Access | REQ | Material movement path |
| Drains, water inlet, tap (`AT.*`) | Services | REQ | Outdoor kitchen / bar wet point |
| `FLR`, `CND` | Floor | REQ | Waterproofing state → `RISK` note |
| Headroom under water tank / staircase head | `BB` on the relevant wall | COND | |

### 11.2 Optional measurements

| Code | What | Why |
|---|---|---|
| Bar / outdoor kitchen wall tag (`KITCHEN_RUN`) | Outdoor counter | `KITCHEN.BASE` with membrane / outdoor finish variant |
| Seating / planter footprints (sketch) | Built-ins | `CUSTOM_ITEM` |
| Light point count, power points | Electrical | project line |
| Pergola footprint and height | Pergola | **NEW LINE** / client scope |

### 11.3 Mandatory scope recommendations

None.

### 11.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| `BAR_UNIT` / outdoor counter | `KITCHEN_BASE_UNIT` (outdoor finish) | OPTIONAL |
| Built-in seating / planters | `CUSTOM_ITEM` | OPTIONAL |
| `PAINTING` (exterior) | **NEW LINE** / variant | OPTIONAL |
| Deck flooring / turf | **NEW LINE** | OPTIONAL |
| `ELECTRICAL` (outdoor points) | project-level | OPTIONAL |
| Pergola, waterproofing, railing | client scope, exclusions | — |

### 11.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Covered part exists → furniture allowed | space → rules | Furniture rules fire only on the `SEMI_OPEN` child |
| Duplex / villa → `level_count` | space → driver | A terrace on its own level adds to `derived_level_count` only if a habitable space shares the level; the service counts levels from `level_index` of **indoor** spaces (proposed clarification for §4.1) |
| Access path narrow → site factor | measurement → adjustment | Staff may add `SITE_FACTOR` with reason (material lifting) |

### 11.6 BOQ drivers

As Balcony, with `KITCHEN.BASE` (outdoor variant) by `area_wh` on the tagged wall.

### 11.7 Estimate drivers

Outdoor zone excluded from the preparation-package drivers; `level_count` per the clarification above; `SITE_FACTOR` for access. Pricing basis `MEASURED` when `PG` closes.

### 11.8 Survey checklist

1. Polygon outline with every parapet segment; parapet heights.
2. Covered / pergola part as its own outline with height.
3. Access: door or stair head width and height; path for material.
4. Water tank, solar, antenna positions (obstructions).
5. Drains, tap, power points.
6. Floor type; waterproofing signs; photograph.
7. Ask and note: bar / outdoor kitchen, seating, lighting, planters; pergola wish (client scope).

---

## 12. Toilet (`TOILET`, `POWDER_ROOM`)

Template key `TOILET_DEFAULT`; rule group `TOILET_RULES`; zone `INDOOR`; `counts_as_toilet`, `wet_area`. Usually a child of a bedroom (attached) or of the living/passage (common). Veda's room work in a toilet is the vanity and mirror; civil, tiling and sanitary ware are client scope on Essential 1.1.

### 12.1 Required measurements

CORE applies with: `L`, `W`, `CH` REQ; walls REQ; plus:

| Code | What | Level | Notes |
|---|---|---|---|
| `Wn.U = VANITY` | Wash-basin wall, tagged | REQ | |
| Basin counter: present or not; width, depth, height (`NT.OBSERVATION` + photo) | Counter | REQ | Vanity below a counter vs standalone |
| Basin position: offset along the wall (`Wn.OB kind = PIPE`) | Basin | REQ | Vanity centred on it |
| Water inlet and drain offsets below the basin (`Wn.OB kind = PIPE`) | Services | REQ | Cut-outs |
| Wet / dry split: shower area outline, partition or curtain (`NT` + sketch) | Wet zone | REQ | The vanity must sit in the dry zone |
| Window / ventilator: `Wn.Om` with `S` | Opening | REQ | Mirror height, cabinet height |
| Door: width, height, swing | Access | REQ | Swing must clear the vanity |
| Geyser position and switch (`Wn.OB kind = GEYSER`) | Obstruction | REQ when present | |
| Dado tile height (`NT`) | Tiles | REQ | Mirror / cabinet placement above dado |

### 12.2 Optional measurements

| Code | What | Why |
|---|---|---|
| Niche in the shower wall (`NICHE`) | Shelf | client scope note |
| Tall storage wall tag | Linen / toiletry tall unit | `STORAGE_BOXES.TALL` (marine) |
| Mirror size wanted (`NT`) | Mirror | `VANITY_UNIT.MIRROR` |
| Exhaust fan point | Electrical | project |
| Loft above the door (`FL`, `CH`) | Storage | `KITCHEN.LOFT`-type |

### 12.3 Mandatory scope recommendations

None. The vanity is RECOMMENDED: many customers keep the builder's basin.

### 12.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| `VANITY` | `VANITY_UNIT` (toilet 2×2 lump, or counter-width unit) → `VANITY_UNIT.TOILET` | RECOMMENDED |
| Mirror | `VANITY_UNIT.MIRROR` | RECOMMENDED with the vanity |
| Storage above the basin | `VANITY_UNIT` option (storage above, W × H) | OPTIONAL |
| Tall storage | `STORAGE_BOXES.TALL` (marine finish) | OPTIONAL |
| Loft above the door | **NEW LINE** or manual | OPTIONAL |
| `FALSE_CEILING` (moisture-resistant) | `FALSE_CEILING_GYPSUM` (variant) | OPTIONAL |
| Shower partition (glass) | **NEW LINE** / client scope | OPTIONAL |

### 12.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Counter present → vanity type | observation → rule | Counter → unit below (width − 50, height − 100); no counter → `VANITY_UNIT.TOILET` 2×2 lump |
| Wet zone → placement | sketch → rule | Vanity width limited to the dry-zone wall segment |
| Door swing → clearance | measurement → rule | Vanity depth ≤ 450 when the door arc overlaps |
| Dado height → cabinet above | measurement → rule | Storage above starts at dado height or counter + 450 |
| `counts_as_toilet` → `derived_toilet_count` | space → property | Configuration label and typical medians |

### 12.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `VANITY_UNIT.TOILET` | (card) | `lump` (2×2) or `area_wh` per card | counter width × height when sized | MEASURED |
| `VANITY_UNIT.MIRROR` | (card) | `count` | 1 | — |
| Storage above | (card, vanity "storage above" W × H per ADR-012 §3.1) | `area_wh` | width × height | DERIVED |
| `STORAGE_BOXES.TALL` | (card) | `area_wh` | width × `FL` | DERIVED |
| `FALSE_CEILING.GYPSUM` (moisture-resistant) | (card) + variant | `ceiling_area` | — | DERIVED |
| Glass partition | **NEW LINE** | `area_wh` | sketch | MEASURED |

### 12.7 Estimate drivers

Finish forced to a moisture-resistant option (membrane / marine / PU per tier) and listed under assumptions; `toilet_count` is a derived count available as a project-line driver only if a card declares it (not in §9.3's list; propose adding `toilet_count` to the driver vocabulary only if a card line needs it, which none does today). Pricing basis `MEASURED`.

### 12.8 Survey checklist

1. W1 = door wall; clockwise; tag the basin wall.
2. Counter: present, width, depth, height; basin offset; inlet and drain offsets below.
3. Wet / dry: shower outline, partition present; floor slope direction.
4. Window / ventilator with sill; exhaust point.
5. Geyser position and switch; dado height.
6. Door width, height, swing; clearance to the basin wall.
7. Photograph the basin wall straight on and the under-counter plumbing.
8. Ask and note: vanity wanted, mirror size, storage above, tall unit, shower glass (client scope).

---

## 13. Commercial Space (`RECEPTION`, `CABIN`, `WORKSTATION_AREA`, `CONFERENCE`, `PANTRY`, `RETAIL_FLOOR`, `TRIAL_ROOM`, `BILLING_COUNTER`, `TREATMENT_ROOM`, `BACK_OFFICE`, `SERVER_ROOM`, `WAITING_AREA`)

Template keys `COMMERCIAL_<TYPE>_DEFAULT` (`applies_when: {usage: COMMERCIAL}`); rule group `COMMERCIAL_RULES`; zone `INDOOR`. Commercial sites are measured as **one open shell per level** (a `POLYGON` space of type `CUSTOM` labelled "Shell L0") **plus** one space per functional zone the client wants, each as a child of the shell with `parent_space_id`. Zones without walls are bounded by partition lines captured as `PARTITION`-type walls with `Wn.T = PARTITION` and a note "proposed". This keeps the shell's true walls and openings authoritative and lets the rule engine price partitions from the zone outlines.

### 13.1 Required measurements

Shell (per level): `PG`, `CH`, `BB` (grid beams), every external wall and opening, column positions as `Wn.OB kind = COLUMN` (or as polygon vertices when free-standing: capture as a note with coordinates), entrance door(s), fire exit(s), shaft and duct openings, electrical DB and server-cable entry, water inlet and drain for pantry and toilets, existing flooring and ceiling (`AT.has_false_ceiling_existing`), raised floor presence (`NT`), AC type (`AT.ac_type`: central / cassette / split / none).

Per zone (child space), CORE plus:

| Zone type | Required additions |
|---|---|
| `RECEPTION` | `Wn.U = RECEPTION_DESK` wall tag or free-standing desk footprint sketch (length, depth, height, front and back); `Wn.U = FEATURE_WALL` (branding wall) tag; waiting seating run |
| `CABIN` | Desk wall tag (`STUDY_UNIT`); storage wall tag (`WARDROBE` reused for credenza / tall storage); glass front length and height (`Wn.T = GLASS` wall row); door width and swing; power / data count |
| `WORKSTATION_AREA` | Outline; linear run per workstation row (sketch: rows × seats, module width 1 200 / 1 500 / 1 800); column positions inside; power / data count per seat; AC and lighting grid |
| `CONFERENCE` | Table footprint (L × W); `Wn.U = TV_UNIT` (screen wall); storage / credenza wall; glass front; acoustic wall tag (`FEATURE_WALL`); AV points |
| `PANTRY` | As Kitchen §3.1 (tagged runs, services, chimney if any); seating counter |
| `RETAIL_FLOOR` | Shell outline; display wall tags (`WARDROBE` reused as "display unit" or a proposed tag `DISPLAY_RUN`); window display outline; billing counter footprint; trial room count and sizes; stock-room door; signage band height (`NT`) |
| `TRIAL_ROOM` | L, W, CH; door / curtain opening; mirror wall tag |
| `BILLING_COUNTER` | Footprint sketch (length, depth, height, customer side and staff side); power / data; POS count |
| `TREATMENT_ROOM` (clinic) | L, W, CH; basin wall and services (as Toilet §12.1 basin rows); couch / chair footprint; storage wall tag; medical gas / drain if any (`RISK`); door width (stretcher access ≥ 900 mm, note) |
| `BACK_OFFICE` / `SERVER_ROOM` | Storage wall tags; rack footprint; AC and power (server room: dedicated AC, raised floor, cable entry; `RISK` note) |
| `WAITING_AREA` | Seating run; TV wall; magazine / water-dispenser niche |

### 13.2 Optional measurements

Signage band and façade (client scope unless quoted); carpet / vinyl flooring change wanted (`floor_area`); acoustic ceiling type; fire-sprinkler grid (ceiling cut-outs); access-control door points; existing furniture inventory for reuse (`NT`).

### 13.3 Mandatory scope recommendations

| Zone | Requirement type | Product key | Why mandatory |
|---|---|---|---|
| `RECEPTION` | `RECEPTION_DESK` | `RECEPTION_DESK` (**NEW LINE** family; priced per `area_wd` + front panel `area_wh`) | A reception zone exists for its desk; rule `COMMERCIAL_RECEPTION_DESK`, `auto: true` |
| `WORKSTATION_AREA` | `WORKSTATION` | `WORKSTATION` (**NEW LINE**, `count` × module) | The zone exists for its seats; rule `COMMERCIAL_WORKSTATIONS_FROM_LAYOUT`, `auto: true`, count from the sketch |
| `CABIN` | `STUDY_UNIT` (executive desk) | `STUDY_UNIT` | A cabin without a desk is a store |
| `CONFERENCE` | `CUSTOM` conference table | `CUSTOM_ITEM` (**NEW LINE** `CONFERENCE_TABLE`) | Same |
| Every zone bounded by proposed partitions | `PARTITION` / `GLASS_PARTITION` | `PARTITION` (laminate / fluted) or glass (**NEW LINE**) | Without partitions the zones do not exist; rule `COMMERCIAL_PARTITIONS_FROM_ZONE_EDGES`, `auto: true`, one item per proposed `PARTITION` wall row |

### 13.4 Optional scope recommendations

| Requirement type | Product key | Level |
|---|---|---|
| `STORAGE_CABINET` (credenzas, tall storage, display units) | `STORAGE_BOXES.TALL`, `WARDROBE_HINGED` reused, display **NEW LINE** | RECOMMENDED per tagged wall |
| `FALSE_CEILING` (grid / gypsum) | `FALSE_CEILING_GYPSUM`; grid ceiling **NEW LINE** | RECOMMENDED |
| `CEILING_LIGHTING` | `FALSE_CEILING_LIGHTS`, `ELECTRICAL.SPOTS` | RECOMMENDED |
| `WALL_PANELLING` (branding / acoustic) | `FEATURE_WALL` | OPTIONAL |
| `FLOORING` (carpet / vinyl) | **NEW LINE** | OPTIONAL |
| `ELECTRICAL` (points per seat, data) | project-level with a per-space count | RECOMMENDED |
| `PAINTING` | project-level | RECOMMENDED |
| `SOFT_FURNISHING` (blinds) | **NEW LINE** | OPTIONAL |
| Pantry units | Kitchen template | RECOMMENDED for `PANTRY` |
| Vanity in clinic treatment room | `VANITY_UNIT` | RECOMMENDED |
| Signage, façade, fire systems, HVAC, access control | client scope, exclusions | — |

### 13.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Shell polygon → zones must fit | space → verification | Σ zone floor areas ≤ shell floor area + tolerance; a warning in `generation_run` otherwise |
| Zone edge = proposed `PARTITION` wall → partition item | measurement → rule | Length × `CH` (or ceiling-grid height); glass vs laminate from the designer's preference |
| Workstation sketch → count | sketch → rule | rows × seats; module width validated against the run; mismatch → warning, `ASSUMED` |
| Columns inside a zone → run breaks | obstruction → rule | `usable_run` splits at each column |
| Central AC → no ceiling cassette cut-outs, but duct boxing lowers `Wn.H` | attribute → rule | Ceiling area unchanged; partition height to the slab or to the ceiling (designer's choice, assumption listed) |
| `usage_code = COMMERCIAL` → commercial copy and per-line GST | property → quotation | §8.2 commercial groups, §20 |
| Level count → `level_count` driver | spaces → driver | Multi-floor offices |

### 13.6 BOQ drivers

| Line code | Status | Formula kind | Inputs | Source |
|---|---|---|---|---|
| `PARTITION.LAMINATE` / `.FLUTED` | (card) | `area_wh` | partition length × height | DERIVED |
| Glass partition | **NEW LINE** | `area_wh` | same | DERIVED |
| Workstation | **NEW LINE** | `count` (× module) | seats | DERIVED (sketch) |
| Reception desk | **NEW LINE** | `area_wd` + `area_wh` | desk length × depth; front panel length × height | MEASURED (sketch) |
| Conference table | **NEW LINE** | `area_wd` | L × W | MEASURED |
| `STUDY_UNIT.DESK`, `.STORAGE` | (card) | `area_wh` | as Study | DERIVED |
| `STORAGE_BOXES.TALL`, `WARDROBE.BODY` (credenza / storage) | (card) | `area_wh` | tagged wall run × height | DERIVED |
| Display units | **NEW LINE** | `area_wh` | display wall run × height | DERIVED |
| `TV_UNIT.PANEL` (screen wall) | (card) | `area_wh` | — | DERIVED |
| `FEATURE_WALL.*` | (card) | as Living | — | DERIVED |
| `FALSE_CEILING.GYPSUM` | (card) | `ceiling_area` | zone or shell area − shafts | DERIVED |
| Grid ceiling | **NEW LINE** | `ceiling_area` | — | DERIVED |
| `FALSE_CEILING.PANEL_LIGHTS`, `ELECTRICAL.SPOTS` | (card) | `count` | area ÷ density (commercial density default) | DERIVED |
| `ELECTRICAL.WIRING` | (card, project) | driver | points per seat × seats + fixed | DERIVED |
| Carpet / vinyl flooring | **NEW LINE** | `floor_area` | zone floor area | DERIVED |
| `KITCHEN.*` (pantry) | (card) | as Kitchen | — | DERIVED |
| `VANITY_UNIT.*` (clinic) | (card) | as Toilet | — | DERIVED |
| `PAINTING.*` | (card, project) | `wall_area_net` | shell + partitions both faces (formula record: partition faces count ×2) | DERIVED |

### 13.7 Estimate drivers

| Driver | Commercial-specific effect |
|---|---|
| Tier | Commercial tiers map to the same engine tiers; most commercial work is ESSENTIAL laminate or PREMIUM; LUXURY for hospitality |
| Project-line driver | `floor_area_sqft` (shell), `space_count` (zones), `level_count`; `bedroom_count` = 0 (the preparation package must declare a commercial driver, else a `fixed` amount; OI-MTQ-05 / B3 card content) |
| Adjustments | `SITE_FACTOR` for night-work restrictions, mall rules, lift booking; `TRANSPORT` by distance |
| GST | Per-line rates (OI-MTQ-07) matter more here because flooring, electrical and furniture may differ |
| Pricing basis | `MEASURED` when the shell polygon closes and every zone has its edges; workstation counts from a sketch are `ASSUMED` until the designer's layout is confirmed |
| Typical medians | None from ADR-012 (residential only); commercial typicals are a B5 knowledge-store output. Until then every unmeasured commercial dimension is `ASSUMED` and banded |

### 13.8 Survey checklist

Shell:

1. Polygon of the shell per level, clockwise from the main entrance; every external wall and opening; columns with coordinates.
2. Slab height, beam grid bottoms, existing ceiling and its height, raised floor.
3. Entrances, fire exits, shafts, ducts, DB, cable entry, water and drain points.
4. AC type and distribution; sprinkler grid; existing lighting.
5. Flooring and condition; photograph the whole shell in a sweep.

Per zone (in the client's walk order):

6. Outline; which edges are real walls and which are proposed partitions (height wanted: full / 2 100 / glass).
7. Zone-specific tags and sketches per §13.1.
8. Power and data counts per seat / desk / counter.
9. Ask and note: headcount, growth plan, brand wall, storage needs, pantry appliances, trial-room count, clinic equipment list.

---

## 14. Custom Space (`CUSTOM`)

Template key `CUSTOM_DEFAULT`; rule group `GENERIC_RULES`; zone per instance; `custom_type_label` required. Used for a clubhouse lounge, a home theatre, a gym, a store room, a staircase landing, a garage conversion, a single-room renovation that fits no listed type. The custom template captures everything the generic rules can price and nothing type-specific; the designer adds requirements by hand.

### 14.1 Required measurements

CORE in full (shape, principal dimensions or polygon, `CH`, every wall, every opening with offsets, `FLR`, `CND`, `CF`, photos). Plus: the label (`custom_type_label`) and a `NT.OBSERVATION` of the intended use; every wall the customer wants furniture on tagged with the nearest standard tag (`WARDROBE` for any tall storage, `TV_UNIT` for any media wall, `STUDY_UNIT` for any desk / counter, `KITCHEN_RUN` for any base-cabinet run, `FEATURE_WALL` for any treatment).

### 14.2 Optional measurements

`FL`, `BB`, `Wn.H`, obstructions on tagged walls, `AT.*` as relevant, footprint sketches for free-standing items.

### 14.3 Mandatory scope recommendations

None. A custom space has no automatic items; the designer confirms requirements and the generic rules price what the tags allow.

### 14.4 Optional scope recommendations

Generic rules in `GENERIC_RULES` fire on tags only: `WARDROBE` tag → `WARDROBE_HINGED` (+ loft), `TV_UNIT` tag → `TV_UNIT`, `STUDY_UNIT` tag → `STUDY_UNIT`, `KITCHEN_RUN` tag → `KITCHEN_BASE_UNIT` (+ wall unit when a second tag or the same wall's upper segment is wanted), `FEATURE_WALL` tag → `FEATURE_WALL`; `FALSE_CEILING`, `CEILING_LIGHTING`, `PAINTING` from derived areas; anything else is `CUSTOM_ITEM` with manual dimensions and `override_reason`.

### 14.5 Dependencies

| Dependency | Kind | Effect |
|---|---|---|
| Tag → generic rule | measurement → rule | Each generic rule is the bedroom / living / kitchen rule with `when.space_category` widened to `OTHER`; emitted items are `necessity: OPTIONAL` always |
| No tag → no auto item | — | The space contributes derived areas only |
| `CUSTOM_ITEM` → manual rate | rule → estimate | `rate_source = MANUAL` with reason until a line exists |

### 14.6 BOQ drivers

The driver of whichever generic product the tag selected (see 1, 3, 5, 8), plus `CUSTOM_ITEM` with `area_wh` / `area_wd` / `count` / `lump` chosen by the designer and `formula_inputs` recorded.

### 14.7 Estimate drivers

`space_count` +1 (indoor only); floor area; `ALLOWANCE` applies; pricing basis `MIXED` whenever a `CUSTOM_ITEM` carries an `ASSUMED` dimension; a custom space on a `PARTIAL` project (single-room renovation) sets the project-level lines to `space_count` or `fixed` drivers rather than `bedroom_count`.

### 14.8 Survey checklist

CORE list in full, then:

1. Write the label and intended use; photograph from every corner.
2. Tag every wall the customer wants furniture on with the nearest standard tag and describe the item in a note.
3. Sketch any free-standing item footprint with clearances.
4. Services present (power, water, drain, AC) as attributes.
5. Ask and note: what the customer has seen elsewhere (reference photos as attachments), budget hint, must-have / avoid.
