# 03 · Measurement Visit Playbook

What a site engineer (the SURVEYOR role, blueprint §15.1) does and captures, in order, so that a measurement set reaches `VERIFIED` on the first submission and the designer can generate scope, BOQ, estimate and quotation without a second visit. Every step names the record it fills. Codes are in [00-conventions.md](00-conventions.md); per-space content in [01-space-type-templates.md](01-space-type-templates.md); property seeds in [02-property-templates.md](02-property-templates.md).

The playbook is written for the capture PWA described in blueprint §13.2 but is usable on paper with the sketch sheets in §11 until the app exists.

## 1. Roles and hand-offs

| Step | Who | Record | Exit condition |
|---|---|---|---|
| Visit requested | Sales / Designer | `measurement_visit REQUESTED` on a `property` under a `lead` | property seeded from a template (02) |
| Scheduled | Ops | `SCHEDULED`, `assigned_to`, `lead_activity SITE_VISIT`; lead moves to `SITE_VISIT` (§12.3) | customer confirmed, access notes filled |
| Pre-visit | Surveyor | plan pre-measure rev 0 (optional), kit check | §2 done |
| On site | Surveyor (+ second surveyor on large sites) | `measurement_set DRAFT` → spaces, walls, openings, notes, photos; `requirement` capture when the designer is present | §3–§7 done; completeness green |
| Submit | Surveyor | `SUBMITTED`; summary computed | §8 self-check passed |
| Verify | Designer / Estimator (not the capturer when four-eyes is on) | `VERIFIED` (snapshot sha256, `measurement.verified` event) or `REJECTED` with notes | §9 verification checklist |
| Discovery (if not done on site) | Designer | `requirement` rows CONFIRMED / DECLINED / DEFERRED | §6 |
| Quotation readiness | Designer | gate in §10 passes | scope generation may start |

## 2. Pre-visit (the day before)

1. **Open the visit** in the app; read `access_notes`, the lead's message and any public `budget_estimate` linked to it (its rooms and products arrive as `PROPOSED / PUBLIC_ESTIMATE` requirements, §7.2).
2. **Confirm the property template** seeded (02): type, usage, project kind, stated areas, floor count. Add or remove spaces you already know about from the floor plan.
3. **Plan pre-measure (recommended for villas, duplexes, commercial):** if a builder's drawing exists, create `measurement_set` rev 0 with `method_code = PLAN_DRAWING`, `confidence = MEDIUM`, entering principal dimensions per space from the plan. On site you create rev 1 by `TAPE` / `LASER`; rev 0 is superseded on verification (§6.2). The pre-measure tells you how many spaces to expect and how long the visit will take.
4. **Call the customer:** confirm the time, who will be present (the decision-maker must be present for discovery), whether the flat is occupied, whether furniture can be moved, lift availability, society permissions for a visit.
5. **Kit check** (§12).
6. **Battery and storage:** phone ≥ 80 %, power bank, at least 2 GB free for photos (expect 150–400 photos per home).
7. **Offline mode:** open the visit while online so the property tree, templates and checklists are cached (§13.2 offline-first).

## 3. Arrival and property-level capture (first 20 minutes)

1. Start the visit (`started_on`; the device records `geo_lat/lng`).
2. Confirm the customer contact on site (`customer_contact_name/phone`).
3. **Walk the whole property once without measuring.** Confirm the space list against the seed: add spaces that exist, mark `is_in_scope = false` for spaces the customer excludes entirely (still measure them if painting or ceiling throughout is possible; ask), set each space's `label` the way the customer names it ("Kids' room", "Mom's room").
4. Agree the walk order with the customer and set `sort_order` (default per 02).
5. Capture the property-level items in 02 §0: main door width and height, lift door size and lift internal depth, staircase width at the narrowest turn, passage widths, floor number, DB location, dampness, occupancy, society hours. Photograph the main door, lift, staircase, DB, meter.
6. Photograph the floor plan on the wall or the builder's drawing if the customer has one; attach to the property (`floor_plan_attachment_id`).
7. Note every property-level `RISK` now (seepage, cracks, exposed wiring, incomplete civil work, no water connection), each with a photo.

## 4. Per-space procedure (repeat for every space in walk order)

Time budget: 8–12 minutes for a bedroom, 15–25 minutes for a kitchen, 5 minutes for a toilet or balcony, 20–40 minutes for a commercial shell.

| # | Action | Record | Rule |
|---|---|---|---|
| 1 | Stand in the entry door, back to it. The door wall is **W1**. Walk clockwise and stick a label on each wall: W1, W2, … | — | Conventions §3 |
| 2 | Choose the shape. Four walls, all corners square: `RECTANGULAR`. Six walls or an open edge: `L_SHAPE` / `POLYGON`. Cannot be measured (occupied, cluttered, unsafe): `FREEFORM` with a stated area and a `RISK` note | `SH`, `SA` | A `FREEFORM` space forces a range on every line in it; use it only when there is no alternative |
| 3 | Principal dimensions: `L` and `W` at floor level, plaster to plaster, at the longest clear line; for polygons enter every vertex in order | `L`, `W`, `PG` | Laser to the nearest 5 mm; both ends of a long wall if the room is not square (note the difference as a `RISK` if > 25 mm) |
| 4 | Ceiling height at the centre and at the lowest point; beam bottom if a beam crosses; floor to lintel at the tallest door | `CH`, `BB`, `FL` | `CH` is the slab underside; if a false ceiling exists, record its height as `CH` and set `AT.has_false_ceiling_existing = true` with the slab height in a note |
| 5 | Each wall in order: length at floor level corner to corner; type; external or not; height if it differs from `CH` | `Wn.L`, `Wn.T`, `Wn.X`, `Wn.H` | An open edge is a wall row with type `OPEN` and its length |
| 6 | Each opening on that wall, left to right from the wall's start corner: type, width, height (frame outer), sill height, offset from the start corner, swing | `Wn.Om.*` | Every door, window, ventilator, AC sleeve, duct, shaft, niche, arch. Missing offsets are the commonest rejection reason |
| 7 | Tag the wall with what it will carry, per the space template's checklist (wardrobe, bed head, TV, kitchen run, study, vanity, crockery, pooja, feature) | `Wn.U` | Ask the customer; if undecided, tag the template's default and add a `CUSTOMER_REQUEST` note "undecided" |
| 8 | Every obstruction on a tagged wall: kind, offset from the start corner, width, height from floor, projection | `Wn.OB` | Switchboards, AC indoor units and their pipe drops, DB boxes, columns, geysers, pipes, window grills |
| 9 | Space attributes: AC type and point count, fan points, services (gas, water, drain) where the template asks | `AT.*` | |
| 10 | Flooring, existing condition, confidence | `FLR`, `CND`, `CF` | Lower `CF` to `MEDIUM` if plaster is incomplete or the room is cluttered; to `LOW` for `FREEFORM` |
| 11 | Photos (§5) | `PH.*` | |
| 12 | Notes: risks, customer requests heard here, anything the designer must know | `NT.*` | Voice notes allowed (`VOICE_TRANSCRIPT`) |
| 13 | Run the space's template checklist (01 §n.8) item by item | — | The app shows it; on paper, tick the sheet |
| 14 | Mark complete | `is_complete = true` | Only when the app's completeness check is green: every REQ captured, every COND satisfied, photo minimums met |

**Child spaces** (attached toilet, dressing, walk-in): measure immediately after the parent, from the parent's door; the shared door is already on the parent's wall.

**Re-measure rule:** if any measurement is changed after the wall was photographed, photograph the laser reading again.

## 5. Photo protocol

Every photo attaches to the record it documents (`attachment.entity_type`): the space (`property_space`), a wall (`space_wall`), an opening (`space_opening`) or a note. Name on paper as `<space label>-<W#>-<what>` when the app is not available.

| Subject | Minimum | Composition |
|---|---|---|
| Space, from the entry door | 1 | Whole room, label stickers visible |
| Each wall | 1 per wall | Straight on, full height, label visible, tape or laser not in frame |
| Ceiling | 1 | From the centre, upward; beams and existing ceiling visible |
| Floor | 1 | Showing the flooring type and condition |
| Each opening | 1 | Straight on, whole frame, sill visible |
| Each obstruction | 1 | Close enough to read labels (AC model, DB rating) |
| Each tagged wall with the laser reading | 1 | Laser display readable; proves the number |
| Each risk | 1–3 | Context plus close-up |
| Kitchen services | 1 each | Inlet, drain, gas, chimney outlet, with the tape showing the height |
| Toilet basin wall | 1 + 1 | Straight on and under-counter plumbing |
| Property-level | 6+ | Main door, lift, staircase, DB, meter, parking / access |
| Floor plan | 1+ | Flat, readable, every page |

No faces of occupants; no documents other than the floor plan; no photos of valuables. The customer must be told photos are taken for measurement records (the lead's consent covers the visit).

## 6. Discovery with the customer (designer present, or surveyor with the discovery script)

Blueprint §7.2 seeds `PROPOSED / RECOMMENDED` requirements from each space template and `PROPOSED / PUBLIC_ESTIMATE` from a linked public estimate. On site, walk every space again with the customer and for each proposed requirement record **confirm / decline / defer**, plus:

| Capture | Record |
|---|---|
| Necessity as the customer sees it | `necessity_code` MANDATORY / OPTIONAL / WISHLIST |
| Preferences per item: finish family, shutter type (hinged / sliding), storage type, colour family, style, brand, must-have, avoid | `preferences` JSON |
| Size wishes ("a 10-ft wardrobe") | `target_dimensions` (never authoritative) |
| Budget ceiling per item or overall | `budget_hint_minor` |
| Items the customer adds that no template proposed | new `requirement` with `source = CUSTOMER`, `CUSTOM` type if needed |
| Items declined | `DECLINED` (become quotation exclusions automatically, §7.2 (5)) |
| Project-level: painting (which rooms, full preparation or repaint), electrical (points, rewiring), false ceiling throughout, deep cleaning | project-level requirements (`space_id = NULL`) |
| Tier preference and finish references the customer shows | note + `preferences.finish_code` |
| Timeline, possession date, move-in date | property `possession_on`; note |

If the designer is not on site, the surveyor records only confirm / decline / defer and free-text preferences; the designer completes discovery by call and records it with `source = DESIGNER`.

## 7. Closing the visit on site (last 15 minutes)

1. Open the summary screen: list of incomplete spaces, verification warnings (§6.2 rules run client-side as far as possible: missing `CH`, openings wider than walls, polygon not closing, floor-area total vs stated built-up outside ±25 %).
2. Fix what can be fixed on site. Walk back to any space with a warning.
3. Read the key numbers back to the customer: number of spaces, which are in scope, the tagged walls for wardrobe / kitchen / TV, anything excluded. Record their acknowledgement as a note (`CUSTOMER_REQUEST`: "walk-through summary confirmed by <name>").
4. Sync (`pending sync` badge clears) before leaving if there is connectivity; otherwise sync from the vehicle or office the same day. Never start a second visit on the same device before the first has synced.
5. Set `completed_on`; the visit moves to `COMPLETED`.

## 8. Submit self-check (before `SUBMITTED`)

The surveyor confirms every line; the app blocks submit on the REQ rows.

| # | Check | Level |
|---|---|---|
| 1 | Every in-scope space has a measurement row and `is_complete = true` | REQ (§6.2) |
| 2 | Every non-`FREEFORM` space has `CH` | REQ (§6.2) |
| 3 | Every `POLYGON` closes within tolerance | REQ (§6.2) |
| 4 | Every opening fits inside its wall (`offset + width ≤ wall length`, `sill + height ≤ wall height`) | REQ (§6.2) |
| 5 | No negative derived area | REQ (§6.2) |
| 6 | Σ floor area within ±25 % of stated built-up, or the warning is acknowledged with a reason | REQ (§6.2) |
| 7 | Every wall carrying a product tag has its obstructions captured (possibly "none") and a laser-reading photo | REQ (proposed) |
| 8 | Kitchen: every tagged run has inlet, drain, gas / hob position and chimney outlet, or a `RISK` note saying the service does not exist | REQ (proposed) |
| 9 | Every bedroom in scope has a wardrobe wall tag or a `CUSTOMER_REQUEST` note "no wardrobe" | REQ (proposed) |
| 10 | Every space has the photo minimums | REQ (proposed) |
| 11 | Every `FREEFORM` space has a `RISK` note and `CF = LOW` | REQ (proposed) |
| 12 | Property-level items in 02 §0 captured | REQ (proposed) |
| 13 | Every `RISK` has a photo | REQ (proposed) |
| 14 | `FL` captured in every space where a loft or tall unit is wanted | COND |
| 15 | Discovery recorded (confirm / decline / defer on every proposed requirement) or explicitly deferred to the designer with a note | COND |
| 16 | `unit_system_code` matches what was actually read (ft-in entries not typed as mm) | REQ: spot-check three walls against the photos |

## 9. Verification checklist (designer or estimator, within one working day)

The verifier is not the capturer when four-eyes is on (§4.1 `verified_by`). Verification is **fail-closed**: anything unresolved is `REJECTED` with notes, and a new DRAFT rev is created; the surveyor fixes from photos where possible and re-visits only when a number is missing.

| # | Check | On fail |
|---|---|---|
| 1 | §6.2 server rules all pass (the service runs them; the verifier reads the report) | REJECT |
| 2 | Three random walls per space: the photo of the laser reading matches the stored value (unit conversion correct) | REJECT, note "unit / reading mismatch W<n>" |
| 3 | Per space: the sanity range in the template (01 §n.7) is not violated; violations have a note explaining | REJECT or accept with an `OBSERVATION` note |
| 4 | Each tagged wall: the photo shows no obstruction that is not in `Wn.OB` | REJECT |
| 5 | Kitchen services complete; chimney and hob aligned or noted | REJECT |
| 6 | Openings: every door in the floor plan appears on exactly one parent wall; attached-space doors are not duplicated | REJECT |
| 7 | Derived counts (`derived_bedroom_count`, `derived_toilet_count`, `derived_level_count`) match what the customer said; mismatch explained | Accept with note; the configuration label is display-only |
| 8 | Every `RISK` acknowledged by the verifier (a note "ack" per risk) | Blocks VERIFIED until done |
| 9 | Second surveyor's DRAFT set (large sites): merged per the interim policy in 02 §4 | Blocks VERIFIED |
| 10 | Confidence: any `LOW` space is either accepted (range pricing) or scheduled for re-measure (`RE_MEASURE` visit) | Decide and note |
| 11 | Snapshot: on VERIFIED the service sets `snapshot_sha256`; the verifier records nothing else | — |

## 10. Quotation-readiness gate

A quotation cannot be generated until every row below holds. Rows 1–6 are enforced by the blueprint's state machines; rows 7–12 are template-level checks this package proposes for the scope-generation service to evaluate and list in `scope.generation_run.warnings` (fail) before `scope` may reach `CONFIRMED`.

| # | Condition | Where it is checked | Blueprint ref |
|---|---|---|---|
| 1 | A `measurement_set` is `VERIFIED` and not superseded for the property | `scope.measurement_set_id` FK + status rule | §4.2 `scope` |
| 2 | Every space with `is_in_scope = true` has a measurement with `is_complete = true` | §6.2 verification | §6.2 |
| 3 | Every `CONFIRMED` requirement that is space-level points at an in-scope, measured space | requirement service | §7.2 |
| 4 | Every scope item has dimensions with a `dimension_source`, and `ASSUMED` / `TYPICAL` ones are listed as assumptions | scope service; quotation §10.1 item 9 | §4.2 `scope_item` |
| 5 | The catalogue release pinned by the scope is `ACTIVE` and contains every product, rule and formula referenced | release validation | §8.1, §14 |
| 6 | A BOQ is `REVIEWED` and a cost estimate `APPROVED` on that scope revision; nothing is `is_stale` | state machines | §9.5, §10.2 |
| 7 | **Every MANDATORY-level recommendation of every in-scope space is either INCLUDED or carries a DECLINED requirement** (so the quotation can list it as an exclusion "as discussed") | proposed generation-run check | 01 §n.3 |
| 8 | **Every tagged wall that a rule used has its obstructions captured** (so DERIVED widths are real) | proposed check: rule records `anchor_wall_id`; a wall with no obstruction row and no "none" marker fails | §4.2 `dimensions.anchor_wall_id` |
| 9 | **No in-scope space has `confidence_code = LOW` unless the estimate's `pricing_basis_code` is `MIXED` / `TYPICAL`** and the customer-facing range is enabled | proposed check | §9.4 |
| 10 | **Kitchen: base run, wall run, loft decision, sink and hob positions resolved** (no kitchen rule emitted a warning) | proposed check | 01 §3.5 |
| 11 | **Project-level lines have a resolvable driver** (`bedroom_count` > 0 for residential, or `floor_area_sqft` / `space_count` / `fixed` declared on the card for commercial and partial projects) | proposed check | §9.3 |
| 12 | **Every property-level `RISK` and every space `RISK` is acknowledged**, and any that affects price has a `SITE_FACTOR` or an exclusion recorded | proposed check | §4.2 adjustments, §10.1 item 7 |
| 13 | Discovery complete: no requirement left `PROPOSED` for an in-scope space (each is CONFIRMED, DECLINED or DEFERRED) | proposed check | §7.2 |
| 14 | Owner inputs that the quotation needs are recorded: terms version (OI-MTQ-09), validity (OI-MTQ-08), GST treatment (OI-MTQ-07), discount limits if an adjustment exists (OI-MTQ-06) | implementation-entry gate and B4 | [MTQ-owner-decisions.md](../MTQ-owner-decisions.md) |

In one sentence for the site engineer: **a quotation needs every in-scope room measured wall by wall with openings and obstructions, every furniture wall tagged, the kitchen's services located, the customer's yes / no on every recommended item, and every risk photographed and noted; anything less produces a range or a rejection, never a quotation.**

## 11. Paper fallback (until the PWA exists)

One sheet per space, in this order: header (property number, space label, type, level, zone, surveyor, date, unit system); shape box; `L`, `W`, `CH`, `BB`, `FL`; wall table (W#, length, type, external, height-if-different, tags, obstructions with offsets); opening table (W#, O#, type, W, H, sill, offset, swing); attributes; flooring / condition / confidence; checklist ticks; notes; photo count. One property sheet for 02 §0. Sheets are photographed and attached to the `measurement_set` as `attachment` rows with `entity_type = 'measurement_set'`, and transcribed into the set by the surveyor the same day; the transcriber is `captured_by`, the sheet photo is the evidence the verifier checks against.

## 12. Kit

Laser distance meter (±2 mm class, with a tilt sensor), 5 m and 8 m steel tapes, 1 m spirit level, masking tape and marker for wall labels, chalk, torch, phone with the PWA and a spare power bank, camera or phone with ≥ 12 MP, clipboard and sheets (§11), pen, A4 graph paper for sketches, a small scale ruler, gloves, shoe covers (occupied homes), ID card, visiting card, a copy of the appointment message.

## 13. Timing and staffing

| Property | Surveyors | On-site time | Photos (typical) |
|---|---|---|---|
| 2 BHK | 1 | 2.0–2.5 h | 120–180 |
| 3 BHK | 1 | 2.5–3.5 h | 160–240 |
| 4 BHK | 1–2 | 3.5–4.5 h | 220–320 |
| 5 BHK | 2 | 4.5–6 h | 300–400 |
| Duplex | 2 | 4–6 h | 300–400 |
| Villa / independent house | 2–3 | 6–10 h (two days above 4 000 sq ft) | 400–700 |
| Office (per 1 000 sq ft) | 1 (+1 above 3 000) | 1 h shell + 15 min per zone | 60–100 |
| Retail / clinic | 1–2 | 2–4 h | 120–250 |
| Custom / partial | 1 | 1 h per space + 30 min property | per space |

These are the baselines the B1 validation gate records ("surveyor time per site recorded as the baseline", §16 B1); they are estimates until measured.

## 14. Common errors the verifier rejects, and how to avoid them

| Error | Prevention |
|---|---|
| Walls numbered from the wrong starting point | Always W1 = entry door wall; stick the label before measuring |
| Opening offsets missing or measured from the wrong corner | Offsets from the wall's clockwise start corner; the app draws the wall and shows the opening where you put it |
| Feet-inches typed as millimetres | Choose the unit system once; the app converts; spot-check three walls before submit |
| AC indoor unit not recorded on the wardrobe wall | Obstructions row is mandatory on every tagged wall; "none" must be explicit |
| Kitchen chimney outlet not located | Photograph the sleeve with a tape showing its height and offset |
| Attached toilet's door captured twice | Doors live on the parent's wall; the child space starts from that door |
| Ceiling height taken below an existing false ceiling without saying so | `AT.has_false_ceiling_existing` and the slab height in a note |
| Stated built-up taken from the sale deed (super built-up) | Record what the customer says and the source; the ±25 % check is a warning you acknowledge with the reason |
| Two surveyors editing one set | One DRAFT set per surveyor; the verifier merges |
| Discovery skipped because the customer was busy | Mark every proposed requirement DEFERRED with a note; the designer calls; the quotation waits (gate row 13) |
