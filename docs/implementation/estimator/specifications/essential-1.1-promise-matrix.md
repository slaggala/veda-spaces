# Customer-promise matrix: Essential Specification v1.1

**Source:** [`essential-1.1-promise-matrix.json`](essential-1.1-promise-matrix.json) (schema `veda.estimator.promise-matrix/2`).

**Tests:**
- `api/tests/unit/test_promise_matrix.py`: every visible specification statement is listed, every row carries the full chain, and the statuses are valid.
- `app/scripts/staging-build.test.mjs`: every promise in `estimate-v2-copy.js` is in the matrix, and every page statement in the matrix is on the page.
- `veda estimator activation-check` and `activate-spec` (staging and production): activation is refused while any row is not confirmed or has no named accountable owner.

**Statuses:** OPERATIONALLY_CONFIRMED | SALES_CONFIRMED | OWNER_CONFIRMED | BLOCKED | REMOVED; activation needs every row confirmed (or REMOVED) with a named accountable owner. Nothing is inferred: a person changes a status in this file, through review.

## Summary

| Row | Kind | Status | Waiting for | Responsible role |
|---|---|---|---|---|
| `spec.structure` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.board` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.doors` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.surface` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.edges` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.soft_close` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.hardware` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.handles` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.accessories` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.decorative` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.ceiling` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.lighting` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.painting` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.electrical` | category | BLOCKED | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) |
| `spec.package` | package | BLOCKED | sales confirmation | Sales lead (wording); designer (quotation) |
| `lead` | page | BLOCKED | owner approval of the wording | Product owner |
| `availability` | page | BLOCKED | owner approval of the 'coming soon' wording | Product owner |
| `luxury` | page | OWNER_CONFIRMED | — | Sales lead |
| `rooms_sub` | page | BLOCKED | owner approval of the wording | Product owner |
| `package_subtitle` | page | BLOCKED | sales decision (checklist item 9) | Sales lead |
| `includes` | page | OWNER_CONFIRMED | — | Product owner |
| `gst` | page | BLOCKED | owner approval of the wording | Finance |
| `markers` | page | OWNER_CONFIRMED | — | Product owner |
| `why_range` | page | BLOCKED | owner approval of the wording | Product owner |
| `build_note` | page | BLOCKED | owner approval of the wording | Product owner |
| `rooms_note` | page | BLOCKED | sales and owner confirmation that every room amount includes installation | Sales lead |
| `materials_fallback` | page | BLOCKED | owner approval of the wording | Product owner |
| `included_badge` | page | OWNER_CONFIRMED | — | Product owner |
| `package_text` | page | OWNER_CONFIRMED | — | Project manager |
| `package_components` | page | BLOCKED | operations confirmation of how each component is carried out and checked | Project manager |
| `package_other` | page | BLOCKED | owner approval of the wording | Product owner |
| `allowance_text` | page | OWNER_CONFIRMED | — | Designer |
| `allowance_notes` | page | BLOCKED | owner approval of the wording | Designer |
| `allowance_examples` | page | OWNER_CONFIRMED | — | Designer |
| `manufacturer_warranty` | page | BLOCKED | operations: warranty documents for each product filed and handed over | Project manager |
| `service_support` | page | OWNER_CONFIRMED | — | Customer care |
| `service_note` | page | BLOCKED | owner approval of the wording | Customer care |
| `compare` | page | BLOCKED | owner approval of the wording | Product owner |
| `supplied` | page | BLOCKED | owner approval of the wording | Sales lead |
| `assumptions_summary` | page | BLOCKED | owner approval of the wording | Product owner |
| `next_steps` | page | BLOCKED | operations confirmation of the process and owner approval of the wording | Sales lead |
| `callback` | page | BLOCKED | sales decision (checklist item 10): the one-working-day commitment | Sales lead |
| `consultation` | page | BLOCKED | sales approval of the wording | Sales lead |
| `refine_intro` | page | BLOCKED | owner approval of the wording | Product owner |
| `consent` | page | BLOCKED | owner confirmation of the consent wording | Data protection lead |
| `engine_disclaimer` | page | OWNER_CONFIRMED | — | Product owner |
| `engine_assumptions` | page | OWNER_CONFIRMED | — | Product owner |
| `card_exclusions` | page | OWNER_CONFIRMED | — | Sales lead |
| `card_client_scope` | page | OWNER_CONFIRMED | — | Sales lead |

## Rows

### `spec.structure` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - 12 mm behind the TV
  - 18 mm cabinet and furniture bodies
  - 9 mm back panels
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Branded plywood TV unit
  - Branded plywood bed
  - Branded plywood cabinetry
  - Branded plywood crockery unit
  - Branded plywood furniture
  - Branded plywood study unit
  - Branded plywood utility unit
  - Branded plywood wardrobe
  - Cabinet and furniture bodies in branded plywood
  - Cabinet and furniture structure
  - Final material and brand selections are confirmed in your detailed quotation.
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Plywood of the approved grade
  - Sylvan Blu
- **Internal requirement:** Carcass, shelf, back-panel and TV-background boards in plywood of the approved grade (October 2026 baseline: Sylvan Blu): 18 mm bodies, 9 mm backs, 12 mm TV backgrounds
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Every carcass or body line names board brand, grade and thickness
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.board` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Approved board structure
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Final material and brand selections are confirmed in your detailed quotation.
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Pooja unit and arch structure
  - Pooja unit and window-arch structure in an approved board, specified in your detailed quotation
  - The board and its grade are confirmed in your detailed quotation
- **Internal requirement:** Pooja unit and window-arch structure: board and grade chosen at design; no plywood promise until specified
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Pooja unit and window-arch lines name the board, grade and thickness
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.doors` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - 18 to 19 mm shutters
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Block board of the approved grade
  - Branded block-board shutters
  - Doors and shutters
  - Final material and brand selections are confirmed in your detailed quotation.
  - Hinged and sliding shutters in branded block board
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Sylvan Primo Plus
- **Internal requirement:** Hinged and sliding shutters in block board of the approved grade (October 2026 baseline: Sylvan Primo Plus), 18 to 19 mm; any HDHMR or engineered-board shutter named in the quotation instead
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Shutter lines name board brand, grade and thickness, and any non-block-board shutter
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.surface` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - 0.8 mm inner laminate
  - 1.0 mm outer laminate
  - Airolam
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Century
  - Dazzle Berry
  - Final material and brand selections are confirmed in your detailed quotation.
  - Greenlam
  - Laminate finish
  - Laminate on visible surfaces, in colours you choose from the approved range
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Merino
  - Outer: your choice from the approved range; inner: a standard colour selected by Veda Spaces
  - Plain Art
  - Royal Touch
  - Stylam
  - Surface finish
- **Internal requirement:** 1.0 mm outer laminate in the customer’s chosen shades from the approved brands; 0.8 mm inner laminate in a standard shade
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Laminate brand, series, shade code and thickness per room in the finish schedule
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.edges` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - 0.8 mm inner edge banding
  - 2 mm outer edge banding
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - E3
  - Edge banding on every exposed laminated edge
  - Edges
  - Final material and brand selections are confirmed in your detailed quotation.
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Red Star
  - Sealed edges
  - Solid Edge
  - URO
- **Internal requirement:** 2 mm outer and 0.8 mm inner edge banding on every exposed laminated edge, approved brands
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Edge-banding specification in the material schedule
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.soft_close` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Final material and brand selections are confirmed in your detailed quotation.
  - Hettich
  - Kitchen drawer systems: Hettich
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Soft-close TV-unit hardware
  - Soft-close hardware
  - Soft-close hinges and kitchen drawer systems
  - Soft-close hinges on the hinged shutters of your kitchen, wardrobes and TV unit, and soft-close drawer systems in your kitchen
  - Soft-close hinges: Hettich
  - Soft-close kitchen hardware
  - Soft-close wardrobe hardware
- **Internal requirement:** Soft-close hinges on hinged shutters of the kitchen, wardrobes and TV unit; soft-close tandem drawers in the kitchen (October 2026 baseline: Hettich); priced in those products, never in the package
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Kitchen, wardrobe and TV-unit soft-close lines name brand and model
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.hardware` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Approved hinges and channels
  - Blum
  - Branded sliding-door channels
  - Drawer channels: Blum
  - Ebco
  - Final material and brand selections are confirmed in your detailed quotation.
  - Folding-door channels: Ebco or Hettich
  - Hettich
  - Hinges and channels
  - Hinges, channels and fittings
  - Hinges, drawer channels and sliding-door channels from approved brands, and a hydraulic lift where your bed has storage
  - Hinges: Hettich
  - Hydraulic bed-storage fitting
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Nimmi
  - Sliding-door channels: Nimmi or Hettich
- **Internal requirement:** Hinges, drawer, sliding and folding channels from approved brands (Hettich hinges, Blum channels, Nimmi or Hettich sliding, Ebco or Hettich folding); hydraulic lift for storage beds; no soft-close promise
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Hardware lines name brand and type per unit
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.handles` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Final material and brand selections are confirmed in your detailed quotation.
  - Handles
  - Handles chosen by you from the standard range
  - Lengths of 1 ft, 1.5 ft or 2 ft
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Standard handles
- **Internal requirement:** Handles from the standard range chosen by the customer, 1 ft, 1.5 ft or 2 ft
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Handle model per room in the finish schedule
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.accessories` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Final material and brand selections are confirmed in your detailed quotation.
  - Hettich
  - Kitchen accessories
  - Kitchen accessories you choose, such as wicker baskets, rolling shutters and pantry pull-outs, come from approved brands. They are planned within your Design Personalisation Allowance, not within the kitchen subtotal
  - Kitchen accessories, if you choose them
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Nimmi
  - Olive
  - Samsung Irex
- **Internal requirement:** Kitchen accessories only as the customer selects them, from approved brands, within the Design Personalisation Allowance
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Each chosen accessory is its own quotation line, replacing part of the allowance
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.decorative` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Decorative finishes confirmed in your quotation
  - Each item is specified by material and finish in your detailed quotation.
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - No material is promised for these items until your design is final; each one is specified in your detailed quotation.
  - Veneer, glass and decorative finishes
  - Veneer, glass, mirrors, wall panelling, wallpaper, texture paint and cushioned headboards are selected with you during design
- **Internal requirement:** Veneer, glass, mirrors, wall panelling, wallpaper, texture paint and cushioned headboards: specified at design, no material promised in the estimate
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Each decorative item is its own quotation line with material, finish and supplier
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Each item is specified by material and finish in your detailed quotation.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.ceiling` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Ceiling channels: Bright 04/06
  - False ceiling
  - Final material and brand selections are confirmed in your detailed quotation.
  - Gypsum board on Bright 04/06 channels
  - Gypsum board: Saint-Gobain
  - Gypsum ceiling on steel channels
  - Gypsum false ceiling on steel channels
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Saint-Gobain
- **Internal requirement:** Gypsum board (Saint-Gobain baseline) on Bright 04/06 steel channels
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** False-ceiling lines name board brand and channel series
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.lighting` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Approved lighting specification
  - Avion
  - COB and spot lights: Wipro
  - Crompton
  - Final material and brand selections are confirmed in your detailed quotation.
  - LED panel, COB, spot and profile lights from approved brands, installed where your design includes them
  - Lighting
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Panel lights: Philips
  - Philips
  - Profile lights: Crompton or Avion
  - Wipro
- **Internal requirement:** Panel lights (Philips), COB and spot lights (Wipro), profile lights (Crompton or Avion) or approved equivalents of the same specification
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Lighting lines name brand, wattage and colour temperature
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.painting` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Asian Paints
  - Birla
  - Final material and brand selections are confirmed in your detailed quotation.
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Paint: Asian Paints Premium emulsion, one wall colour
  - Painting, if added
  - Premium emulsion paint
  - Premium emulsion paint in one wall colour, over putty and primer when your painting includes full preparation
  - Premium emulsion repaint
  - Putty: Birla or Asian
- **Internal requirement:** Asian Paints Premium emulsion in one wall colour; Birla or Asian putty and primer where full preparation is included
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Painting line names system, brand and product
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.electrical` — BLOCKED

- **Shown:** Room promise, room details and detailed specification
- **Statements:**
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Branded copper wiring
  - Branded copper wiring for the electrical work you add
  - Electrical wiring, if added
  - Final material and brand selections are confirmed in your detailed quotation.
  - Finolex
  - Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms.
  - Polycab
  - Wiring: Polycab or Finolex
- **Internal requirement:** Branded copper wiring (Polycab or Finolex) for the electrical scope the customer adds
- **Source of truth:** ESSENTIAL-1.1 (essential-specification-v1.1.json), October 2026 baseline
- **Responsible role:** Designer (quotation mapping); project manager (procurement to handover)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Electrical line names wiring brand and gauge
- **Procurement check:** Purchase order and supplier invoice name the brand, grade or model and size stated in the quotation
- **Receipt check:** Material receipt at the warehouse or site checks brand stamp, grade, thickness or model against the purchase order
- **Execution check:** Site supervisor checks the material against the quotation before fabrication or fitting
- **Installation check:** Installation checklist confirms the specified item is fitted and works
- **Handover evidence:** Handover record lists the material or product with the invoice reference; photographs kept
- **Warranty document check:** Manufacturer warranty card or terms for the exact product, where the manufacturer issues them, handed over and filed
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation of the wording and material; operations confirmation of each check and a named owner

### `spec.package` — BLOCKED

- **Shown:** What Essential includes; detailed specification
- **Statements:**
  - Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
  - Approved materials and hardware carry the applicable manufacturer warranty for the exact product selected and documented in your final quotation.
  - Branded plywood furniture with laminate finishes, soft-close hardware in the kitchen, wardrobes and TV unit, made and installed by Veda Spaces.
  - Essential Specification
  - Final material and brand selections are confirmed in your detailed quotation.
- **Source of truth:** ESSENTIAL-1.1 package-level fields
- **Responsible role:** Sales lead (wording); designer (quotation)
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** The quotation’s material schedule follows the package summary and the equivalent rule
- **Procurement check:** As for each material category
- **Receipt check:** As for each material category
- **Execution check:** As for each material category
- **Installation check:** As for each material category
- **Handover evidence:** As for each material category
- **Warranty document check:** Manufacturer documentation for the exact products, filed at handover
- **Warranty source:** Manufacturer’s documented terms for the exact product named in the quotation; Veda Spaces workmanship and fitment service per the policy (one year from handover).
- **Equivalent rule:** Approved brands such as the named examples, or an approved equivalent of the same grade and specification.
- **Exception process:** Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement
- **Blocked on:** sales confirmation

### `lead` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Answer a few questions about your home and see a preliminary budget range in about a minute. No measurements or contact details needed.
- **Source of truth:** V2 behaviour (e2e: no contact details or measurements before the first estimate)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `availability` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Online estimates coming soon. Use “Talk to us instead” above.
  - {sizes}: online estimates coming soon.
  - Pricing coming soon
- **Source of truth:** Owner decisions D1 and D3 (Premium disabled; 3 BHK only)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the 'coming soon' wording

### `luxury` — OWNER_CONFIRMED

- **Shown:** V2 page
- **Statements:**
  - Priced after a design consultation
- **Source of truth:** Owner decision (ADR-012 decision log 20): Luxury only as 'Priced after a design consultation'
- **Responsible role:** Sales lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Luxury quotations follow a design consultation
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `rooms_sub` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - We’ve selected what most {size} homes include. Turn rooms on or off and add extras.
- **Source of truth:** Room bundles in estimate-v2.js (typical rooms per home size)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `package_subtitle` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Branded materials and approved hardware, according to the selected rooms and product configuration.
- **Source of truth:** Pre-activation closure instruction (suggested safe statement); ESSENTIAL-1.1
- **Responsible role:** Sales lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** The quotation names materials and hardware per room
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** sales decision (checklist item 9)

### `includes` — OWNER_CONFIRMED

- **Shown:** V2 page
- **Statements:**
  - Your selected rooms and products
  - Site Execution & Handover Package
  - Design Personalisation Allowance
- **Source of truth:** Trust finalisation Phase 1 (owner wording)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** The quotation itemises rooms, the package components and the items that replace the allowance
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `gst` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - GST is shown separately.
- **Source of truth:** Engine: GST computed separately (ADR-012)
- **Responsible role:** Finance
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Quotation shows GST separately
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `markers` — OWNER_CONFIRMED

- **Shown:** V2 page
- **Statements:**
  - No contact details required for your first estimate
  - Room-wise estimate shown
  - Material specification available
  - Warranty and exclusions disclosed
  - GST shown separately
- **Source of truth:** Trust finalisation Phase 9 (owner wording); each backed by e2e-tested behaviour
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `why_range` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Typical sizes are used until you share measurements
  - Room configurations may change during design
  - Finishes and accessories affect the final value
  - The physical site measurement sets the final quantities
  - Site conditions may change what the work requires
- **Source of truth:** Engine bands (typical wider than measured); trust finalisation Phase 1
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `build_note` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - The size and site variation allows for actual sizes and site conditions. It is wider while typical sizes are used and narrows for the items you measure. Amounts are rounded, and the variation includes the rounding.
- **Source of truth:** Engine: per-line size band, rounding (ADR-012 §3)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `rooms_note` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Room amounts are rounded and include installation. Rates are never shown on this page; your detailed quotation lists every item.
- **Source of truth:** Rate card: room amounts include installation
- **Responsible role:** Sales lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Quotation lines include installation, or list it as its own line
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Installation is within the quoted scope for every room
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** sales and owner confirmation that every room amount includes installation

### `materials_fallback` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Materials are confirmed in your detailed quotation.
  - Your measurements are used for this room.
  - {item} (shown separately under optional items)
- **Source of truth:** V2 behaviour
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `included_badge` — OWNER_CONFIRMED

- **Shown:** V2 page
- **Statements:**
  - Included in your estimated range
- **Source of truth:** Owner decisions T5 and T6; engine (package and allowance inside the range)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Quotation shows the package breakdown and the items replacing the allowance
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `package_text` — OWNER_CONFIRMED

- **Shown:** V2 page
- **Statements:**
  - This covers the preparation, protection, material handling, completion and handover activities required to execute the selected project scope professionally.
- **Source of truth:** Owner decision T5 / Phase 6 (owner wording)
- **Responsible role:** Project manager
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Quotation itemises each package component
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `package_components` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Site and floor protection
  - Plywood or material protection
  - Material freight and handling
  - Debris handling
  - Completion deep cleaning
  - Pest-control preparation where applicable
- **Source of truth:** Owner decision T5 / Phase 6 (owner wording); engine prices each component only for its scope
- **Responsible role:** Project manager
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Each component is a quotation line
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Site supervisor records floor and material protection, debris removal, freight, cleaning and pest-control preparation as they are done
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Completion checklist confirms cleaning and debris removal
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** operations confirmation of how each component is carried out and checked

### `package_other` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Other preparation and handover activities, listed in your detailed quotation
  - Your detailed quotation shows the amount for each item.
- **Source of truth:** V2 behaviour (unknown component codes)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `allowance_text` — OWNER_CONFIRMED

- **Shown:** V2 page
- **Statements:**
  - This planning allowance protects your budget for commonly selected design additions. It is not an automatic extra charge. Your detailed quotation replaces it with only the items you approve.
- **Source of truth:** Owner decision T6 / Phase 7 (owner wording)
- **Responsible role:** Designer
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Quotation replaces the allowance with the approved items
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `allowance_notes` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - The upper amount is not charged automatically.
  - The allowance is a share of your room work, so it moves when your room sizes change. Adding measurements does not remove it.
  - In your detailed quotation, the items you actually approve replace it.
- **Source of truth:** Engine: allowance = card band × room work (ADR-012 §3); Phase 7 clarifications
- **Responsible role:** Designer
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Quotation replaces the allowance with the approved items
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `allowance_examples` — OWNER_CONFIRMED

- **Shown:** V2 page
- **Statements:**
  - Extra drawers
  - Mirrors
  - Pelmets
  - Profile lighting
  - Sensors
  - Additional internal storage
  - Selected accessories
- **Source of truth:** Phase 7 (owner list)
- **Responsible role:** Designer
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Each chosen addition is its own quotation line
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `manufacturer_warranty` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Approved materials and hardware carry the applicable manufacturer warranty for the exact product selected and documented in your final quotation.
- **Source of truth:** Warranty policy; Phase 5 (owner wording); ESSENTIAL-1.1 warranty summary
- **Responsible role:** Project manager
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Quotation names the exact product
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Manufacturer warranty card or terms handed over at completion
- **Warranty source:** Manufacturer’s documented terms
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** operations: warranty documents for each product filed and handed over

### `service_support` — OWNER_CONFIRMED

- **Shown:** V2 page
- **Statements:**
  - Veda Spaces provides one year of applicable workmanship and fitment service support from handover, subject to the Warranty, Service & Customer Care Policy.
- **Source of truth:** Warranty, Service & Customer Care Policy (one year of free service from handover); Phase 5 (owner wording)
- **Responsible role:** Customer care
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Handover date recorded; service requests logged against it
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Veda Spaces policy
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `service_note` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - A longer manufacturer warranty is the manufacturer’s own. It does not extend Veda Spaces workmanship or service support.
- **Source of truth:** Warranty policy (manufacturer warranties do not extend Veda Spaces obligations)
- **Responsible role:** Customer care
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Veda Spaces policy
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `compare` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Estimates only compare fairly when the scope is the same. Check each provider’s:
  - Product sizes
  - Cabinet material
  - Door material and finish
  - Hardware brand and type
  - What each room includes
  - Installation
  - Freight and handling
  - Protection and cleaning
  - Taxes (GST)
  - Items you supply
  - What is excluded
- **Source of truth:** Trust layer (#57)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `supplied` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Supplied by you: {items}
- **Source of truth:** Rate card client scope
- **Responsible role:** Sales lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `assumptions_summary` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Standard modular kitchen with wall units and loft
  - One wardrobe with loft
  - {count} wardrobes with lofts
  - TV unit and feature-wall scope
  - TV unit scope
  - {rooms} scope as selected
  - Whole-home ceiling and lighting based on typical {size} dimensions
  - Your measurements are used for: {items}
- **Source of truth:** Room bundles and engine typical sizes (ADR-012 D3)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `next_steps` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Personalise and narrow your estimate. No contact details are needed for this.
  - Request a designer consultation.
  - We complete a physical site measurement.
  - You confirm the design, materials and brands.
  - You receive your detailed final quotation.
  - You approve the scope before any work starts.
- **Source of truth:** Phase 10 (owner list); the sales process
- **Responsible role:** Sales lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Lead workflow: consultation, site measurement, design confirmation, quotation, scope approval
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** operations confirmation of the process and owner approval of the wording

### `callback` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - A designer will call you within one working day to arrange a physical site measurement. You then confirm the design, materials and brands, receive your detailed final quotation, and approve the scope before any work starts.
  - Our designer will call you within one working day to go through your estimate and arrange a site measurement.
  - Our designer will call you within one working day to arrange your design consultation.
- **Source of truth:** ADR-012 (call within one working day)
- **Responsible role:** Sales lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Lead response time monitored in the lead workflow
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** sales decision (checklist item 10): the one-working-day commitment

### `consultation` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Luxury is priced after a design consultation. A designer will call you to understand your home.
  - A designer will call you to talk through your home, your estimate and your ideas.
  - Keep your estimate reference {ref} handy.
- **Source of truth:** V2 behaviour; Luxury decision
- **Responsible role:** Sales lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** sales approval of the wording

### `refine_intro` — BLOCKED

- **Shown:** V2 page
- **Statements:**
  - Add what you know and leave the rest. We keep typical sizes for anything you skip.
- **Source of truth:** V2 behaviour (typical sizes kept for skipped measurements)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner approval of the wording

### `consent` — BLOCKED

- **Shown:** V2 markup (estimate.html)
- **Statements:**
  - I agree to be contacted by Veda Spaces about my enquiry, as described in the Privacy Notice
- **Source of truth:** Privacy Notice v2026-09-v1 (estimate.html)
- **Responsible role:** Data protection lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable
- **Blocked on:** owner confirmation of the consent wording

### `engine_disclaimer` — OWNER_CONFIRMED

- **Shown:** Estimate response
- **Statements:**
  - This is a preliminary budgetary estimate for planning purposes and is not a final quotation or contractual offer.
- **Source of truth:** Engine DISCLAIMER (ADR-012, owner-approved)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `engine_assumptions` — OWNER_CONFIRMED

- **Shown:** Estimate response (technical assumptions)
- **Statements:**
  - {room} – {product}: {input} assumed {value} {unit} (typical for {size}).
- **Source of truth:** Engine assumption text (ADR-012 D3 typical sizes)
- **Responsible role:** Product owner
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Not applicable: wording about the estimate itself, with no material supplied
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `card_exclusions` — OWNER_CONFIRMED

- **Shown:** Estimate response (Not included)
- **Statements:**
  - Civil, plumbing-line and structural changes
  - Appliances, loose furniture and décor
  - Work outside the selected rooms and products
- **Source of truth:** Rate card exclusions (draft 4, owner approval 2026-10-08)
- **Responsible role:** Sales lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Quotation states the same exclusions
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

### `card_client_scope` — OWNER_CONFIRMED

- **Shown:** Estimate response (Supplied by you)
- **Statements:**
  - Sink
  - Tiles
  - Granite
  - Taps
- **Source of truth:** Rate card client scope (draft 4, owner approval 2026-10-08)
- **Responsible role:** Sales lead
- **Accountable owner:** UNASSIGNED
- **Quotation mapping:** Quotation lists client-supplied items
- **Procurement check:** Not applicable: wording about the estimate itself, with no material supplied
- **Receipt check:** Not applicable: wording about the estimate itself, with no material supplied
- **Execution check:** Not applicable: wording about the estimate itself, with no material supplied
- **Installation check:** Not applicable: wording about the estimate itself, with no material supplied
- **Handover evidence:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty document check:** Not applicable: wording about the estimate itself, with no material supplied
- **Warranty source:** Not applicable
- **Equivalent rule:** Not applicable
- **Exception process:** Not applicable

