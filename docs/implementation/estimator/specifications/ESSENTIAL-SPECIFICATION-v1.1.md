# Essential Specification v1.1 (customer-facing)

**Source of truth:** [`essential-specification-v1.1.json`](essential-specification-v1.1.json), spec code `ESSENTIAL-1.1`, schema `veda.estimator.customer-spec/1` (with the optional room-promise fields), effective 2026-10-08. It supersedes [v1.0](ESSENTIAL-SPECIFICATION-v1.0.md) for new estimates once activated; estimates made under v1.0 keep their snapshot.

**Why a new version:** v1.0 applied every carpentry category to every carpentry room, so a pooja room or a crockery unit could be told it had soft-close hardware the estimate never priced. v1.1 ties every promise to the lines the estimate actually prices in that room (trust finalisation, Phase 3), and turns promises that cannot yet be verified into final-selection statements (Phase 4).

**Status:** awaiting the sales review of the wording and the owner's approval. Load and activate through the controlled procedure (runbook §6.8). The validator refuses amounts, price wording, durations and personal data.

## Package-level wording

| Field | Text |
|---|---|
| Name | Essential Specification |
| Summary | Branded plywood furniture with laminate finishes, soft-close hardware in the kitchen, wardrobes and TV unit, made and installed by Veda Spaces. |
| Equivalent policy | Approved brands such as the named examples, or an approved equivalent of the same grade and specification. |
| Final-selection checkpoint | Final material and brand selections are confirmed in your detailed quotation. |
| Manufacturer warranty | Approved materials and hardware carry the applicable manufacturer warranty for the exact product selected and documented in your final quotation. |

## Categories and the priced lines that carry them

A category applies to a room only when the estimate priced one of its lines there. The room card's one-line promise takes one phrase per line group (structure, surface, hardware, ceiling, lighting, paint, electrical): the first applicable category of the group, worded per product when every priced line agrees, otherwise the category summary.

| Category | Summary (room-line group) | Requirement | Approved examples | Priced lines | Room-line wording |
|---|---|---|---|---|---|
| Cabinet and furniture structure | Branded plywood furniture (structure) | Cabinet and furniture bodies in branded plywood | Sylvan Blu | KITCHEN.BASE, KITCHEN.WALL, KITCHEN.LOFT, UTILITY.WALL, WARDROBE.BODY, WARDROBE.LOFT, TV_UNIT.BOX, TV_UNIT.STORAGE, TV_UNIT.PANEL, CROCKERY_UNIT.BODY, STUDY_UNIT.DESK, STUDY_UNIT.STORAGE, VANITY_UNIT.TOILET, VANITY_UNIT.DRESSER, BED.QUEEN, BED.KING, BED.PANEL, WINDOW_SEATING.SEAT, STORAGE_BOXES.TALL, STORAGE_BOXES.BEDSIDE_BOX, STORAGE_BOXES.BEDSIDE_TABLE, PARTITION.LAMINATE | KITCHEN: Branded plywood cabinetry; UTILITY: Branded plywood utility unit; WARDROBE: Branded plywood wardrobe; TV_UNIT: Branded plywood TV unit; CROCKERY_UNIT: Branded plywood crockery unit; BED: Branded plywood bed; STUDY_UNIT: Branded plywood study unit |
| Pooja unit and arch structure | Approved board structure (structure) | Pooja unit and window-arch structure in an approved board, specified in your detailed quotation | — | POOJA_UNIT.UNIT, WINDOW_SEATING.ARCH | — |
| Doors and shutters | Branded block-board shutters (details only) | Hinged and sliding shutters in branded block board | Sylvan Primo Plus | KITCHEN.BASE, KITCHEN.WALL, KITCHEN.LOFT, UTILITY.WALL, WARDROBE.BODY, WARDROBE.LOFT, TV_UNIT.BOX, TV_UNIT.STORAGE, CROCKERY_UNIT.BODY, STUDY_UNIT.STORAGE, VANITY_UNIT.TOILET, VANITY_UNIT.DRESSER, STORAGE_BOXES.TALL, STORAGE_BOXES.BEDSIDE_BOX, POOJA_UNIT.DOOR, WINDOW_SEATING.SEAT | — |
| Surface finish | Laminate finish (surface) | Laminate on visible surfaces, in colours you choose from the approved range | Merino, Century, Greenlam, Royal Touch, Stylam, Plain Art, Dazzle Berry, Airolam | KITCHEN.BASE, KITCHEN.WALL, KITCHEN.LOFT, UTILITY.WALL, WARDROBE.BODY, WARDROBE.LOFT, TV_UNIT.BOX, TV_UNIT.STORAGE, TV_UNIT.PANEL, CROCKERY_UNIT.BODY, STUDY_UNIT.DESK, STUDY_UNIT.STORAGE, VANITY_UNIT.TOILET, VANITY_UNIT.DRESSER, BED.QUEEN, BED.KING, BED.PANEL, WINDOW_SEATING.SEAT, STORAGE_BOXES.TALL, STORAGE_BOXES.BEDSIDE_BOX, STORAGE_BOXES.BEDSIDE_TABLE, PARTITION.LAMINATE, POOJA_UNIT.UNIT, WINDOW_SEATING.ARCH, POOJA_UNIT.DOOR | — |
| Edges | Sealed edges (details only) | Edge banding on every exposed laminated edge | Solid Edge, E3, URO, Red Star | KITCHEN.BASE, KITCHEN.WALL, KITCHEN.LOFT, UTILITY.WALL, WARDROBE.BODY, WARDROBE.LOFT, TV_UNIT.BOX, TV_UNIT.STORAGE, TV_UNIT.PANEL, CROCKERY_UNIT.BODY, STUDY_UNIT.DESK, STUDY_UNIT.STORAGE, VANITY_UNIT.TOILET, VANITY_UNIT.DRESSER, BED.QUEEN, BED.KING, BED.PANEL, WINDOW_SEATING.SEAT, STORAGE_BOXES.TALL, STORAGE_BOXES.BEDSIDE_BOX, STORAGE_BOXES.BEDSIDE_TABLE, PARTITION.LAMINATE, POOJA_UNIT.UNIT, WINDOW_SEATING.ARCH | — |
| Soft-close hardware | Soft-close hardware (hardware) | Soft-close hinges on the hinged shutters of your kitchen, wardrobes and TV unit, and soft-close drawer systems in your kitchen | Hettich | KITCHEN.SOFT_CLOSE, KITCHEN.SOFT_CLOSE_WALL, KITCHEN.SOFT_CLOSE_LOFT, KITCHEN.TANDEM, WARDROBE.SOFT_CLOSE, WARDROBE.SOFT_CLOSE_LOFT, TV_UNIT.SOFT_CLOSE, TV_UNIT.SOFT_CLOSE_STORAGE | KITCHEN: Soft-close kitchen hardware; WARDROBE: Soft-close wardrobe hardware; TV_UNIT: Soft-close TV-unit hardware |
| Hinges and channels | Approved hinges and channels (hardware) | Hinges, drawer channels and sliding-door channels from approved brands, and a hydraulic lift where your bed has storage | Hettich, Blum, Nimmi, Ebco | WARDROBE.SLIDING, CROCKERY_UNIT.BODY, STUDY_UNIT.DESK, STUDY_UNIT.STORAGE, VANITY_UNIT.TOILET, VANITY_UNIT.DRESSER, UTILITY.WALL, POOJA_UNIT.DOOR, STORAGE_BOXES.TALL, STORAGE_BOXES.BEDSIDE_BOX, STORAGE_BOXES.BEDSIDE_TABLE, WINDOW_SEATING.SEAT, BED.HYDRAULIC | WARDROBE.SLIDING: Branded sliding-door channels; BED.HYDRAULIC: Hydraulic bed-storage fitting |
| Handles | Standard handles (details only) | Handles chosen by you from the standard range | — | KITCHEN.BASE, KITCHEN.WALL, KITCHEN.LOFT, UTILITY.WALL, WARDROBE.BODY, WARDROBE.LOFT, TV_UNIT.BOX, TV_UNIT.STORAGE, CROCKERY_UNIT.BODY, STUDY_UNIT.STORAGE, VANITY_UNIT.TOILET, VANITY_UNIT.DRESSER, STORAGE_BOXES.TALL, STORAGE_BOXES.BEDSIDE_BOX, POOJA_UNIT.DOOR, WINDOW_SEATING.SEAT | — |
| Kitchen accessories | Kitchen accessories, if you choose them (details only) | Kitchen accessories you choose, such as wicker baskets, rolling shutters and pantry pull-outs, come from approved brands. They are planned within your Design Personalisation Allowance, not within the kitchen subtotal | Nimmi, Hettich, Samsung Irex, Olive | KITCHEN.BASE | — |
| Veneer, glass and decorative finishes | Decorative finishes confirmed in your quotation (details only) | Veneer, glass, mirrors, wall panelling, wallpaper, texture paint and cushioned headboards are selected with you during design | — | VENEER_ACCENTS.*, POOJA_UNIT.BEADING, POOJA_UNIT.DOOR_CNC, POOJA_UNIT.ASTA_CHAKRA, PARTITION.FLUTED, WARDROBE.GLASS, CROCKERY_UNIT.GLASS, VANITY_UNIT.MIRROR, FEATURE_WALL.*, BED.CUSHION | — |
| False ceiling | Gypsum ceiling on steel channels (ceiling) | Gypsum false ceiling on steel channels | Saint-Gobain | FALSE_CEILING.GYPSUM, FALSE_CEILING.COVE, FALSE_CEILING.CLOUD | — |
| Lighting | Approved lighting specification (lighting) | LED panel, COB, spot and profile lights from approved brands, installed where your design includes them | Philips, Wipro, Crompton, Avion | FALSE_CEILING.PANEL_LIGHTS, CEILING_PROFILE_LIGHTING.*, ELECTRICAL.SPOTS | — |
| Painting, if added | Premium emulsion paint (paint) | Premium emulsion paint in one wall colour, over putty and primer when your painting includes full preparation | Asian Paints, Birla | PAINTING.* | PAINTING.REPAINT: Premium emulsion repaint |
| Electrical wiring, if added | Branded copper wiring (electrical) | Branded copper wiring for the electrical work you add | Polycab, Finolex | ELECTRICAL.WIRING | — |

Every category also carries the equivalent rule, the final-selection checkpoint and the manufacturer warranty summary ("Manufacturer’s warranty for the supplied product, on the manufacturer’s documented terms."). The decorative category uses its own: "Each item is specified by material and finish in your detailed quotation."

## Room promises this produces (3 BHK, typical sizes)

| Room | One-line promise |
|---|---|
| Kitchen | Branded plywood cabinetry · Laminate finish · Soft-close kitchen hardware |
| Master bedroom, bedrooms 2 and 3 (hinged wardrobe, bed, vanity) | Branded plywood furniture · Laminate finish · Soft-close wardrobe hardware |
| Bedroom with a sliding wardrobe and no loft | Branded plywood furniture · Laminate finish · Approved hinges and channels (no soft-close) |
| Living room (TV unit, any style) | Branded plywood TV unit · Laminate finish · Soft-close TV-unit hardware |
| Dining (crockery unit) | Branded plywood crockery unit · Laminate finish · Approved hinges and channels |
| Pooja room | Approved board structure · Laminate finish · Approved hinges and channels |
| Utility | Branded plywood utility unit · Laminate finish · Approved hinges and channels |
| Whole home | Gypsum ceiling on steel channels · Approved lighting specification (+ Premium emulsion paint, Branded copper wiring if added) |

A panelled TV unit still has its TV box and side storage, which the card prices with soft-close hinges, so the living-room line keeps soft-close. Wall panelling, wallpaper, texture, veneer, fluted glass and mirrors carry no material promise; they appear under "Veneer, glass and decorative finishes" as a final-selection statement.

## Changes from v1.0

| v1.0 | v1.1 | Reason |
|---|---|---|
| Hardware: "Soft-close hinges and kitchen drawers" for every carpentry room | Split: **Soft-close hardware** only where a soft-close line is priced (kitchen, hinged wardrobes and lofts, TV unit); **Hinges and channels** elsewhere | The card prices soft-close only in the kitchen, wardrobe and TV unit (owner decision, ADR-012 decision log 20) |
| Cabinet structure: branded plywood in every carpentry room | Only on carcass and body lines; pooja unit and window arch: **Approved board structure** | The board for CNC and jaali work is chosen at design |
| No category for veneer, glass, mirrors or wall finishes (laminate was implied) | **Veneer, glass and decorative finishes**: a final-selection statement, no material promised | Unsupported promise removed (Phase 4) |
| Kitchen accessories "where your kitchen design includes them" | Accessories you choose come from approved brands and are planned within the **Design Personalisation Allowance**, not the kitchen subtotal | The card prices no accessory line; the old wording implied they were included |
| Ceiling and lighting in one category | **False ceiling** and **Lighting** | Separate room-line phrases |
| Optional electrical and painting in one category | **Painting, if added** and **Electrical wiring, if added** (repaint worded separately) | A repaint has no putty or primer |
| Warranty summary: the T7 combined sentence | Manufacturer-backed sentence only; Veda Spaces service support is shown separately on the page | Phase 5 separation |
| Doors: "Door shutters in branded block board" | "Hinged and sliding shutters in branded block board"; any HDHMR or other engineered-board shutter must be named in the quotation | The policy mentions HDHMR shutters |

Brands, thicknesses and the October 2026 baseline are unchanged; see the v1.0 reconciliation table.

## Review checklist (sales and owner)

- [ ] Each room promise above matches what Veda Spaces builds for that item.
- [ ] Vanity and utility boards: confirm branded plywood is used in these wet areas, or move them to *Approved board structure*.
- [ ] Shutters: confirm block board for every shutter line, or name the exceptions.
- [ ] The operational chain for each category in the [customer-promise matrix](essential-1.1-promise-matrix.md) is how the team works, with a named owner.
- [ ] No amount, price limit or warranty duration (validator-enforced).
