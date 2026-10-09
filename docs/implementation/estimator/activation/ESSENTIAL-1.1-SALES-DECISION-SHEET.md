# ESSENTIAL-1.1 sales decision sheet

**Record:** [`essential-1.1-sales-decisions.json`](../../../../api/veda/modules/estimator/approved/essential-1.1-sales-decisions.json), version 1, SHA-256 `4aefa90ae5ab225ad395b9871cf1c97620e8279d5153d1af35542c9ba1283863`.

**Status: no decision recorded.** The owner-decision, owner-name and decision-date fields are empty by design and are
filled only by sales, in a reviewed pull request that edits the JSON record. A decision of **CHANGE** creates a new
specification version (ESSENTIAL-1.2), so a new digest, matrix and owner approval are required before activation.
A decision of **APPROVE** changes nothing else, but the sales record's digest changes, so the owner approval record
must be refreshed.

## S1. Bathroom vanity wet-area material

| Field | Entry |
|---|---|
| Current proposed wording | Room line "Branded plywood furniture · Laminate finish · …"; "Cabinet and furniture bodies in branded plywood"; "Hinged and sliding shutters in branded block board" |
| Technical specification | VANITY_UNIT.TOILET and VANITY_UNIT.DRESSER carry structure (approved-grade plywood, October baseline Sylvan Blu, 18 mm), doors (block board, Sylvan Primo Plus, 18 to 19 mm), surface, edges and hinges and channels; VANITY_UNIT.MIRROR is decorative |
| Customer impact | Customers with bathroom vanities are promised branded plywood and block board in a wet area |
| Operational impact | Every vanity must be built in those boards, or the promise is false |
| Recommended decision | APPROVE only if the same branded plywood and block board are used for bathroom vanities; otherwise CHANGE: move VANITY_UNIT.TOILET to the board category (Approved board structure) |
| If changed | New specification version (ESSENTIAL-1.2) with VANITY_UNIT.TOILET moved from structure/doors to board; new digest and review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |

## S2. Utility wet-area material

| Field | Entry |
|---|---|
| Current proposed wording | "Branded plywood utility unit · Laminate finish · Approved hinges and channels" |
| Technical specification | UTILITY.WALL carries structure, doors, surface, edges, handles and hinges and channels |
| Customer impact | Utility units are promised branded plywood and block board |
| Operational impact | As S1 for utility areas |
| Recommended decision | As S1: APPROVE only if confirmed; otherwise CHANGE: move UTILITY.WALL to the board category |
| If changed | New version with UTILITY.WALL moved to board; new digest and review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |

## S3. Pooja-unit board and shutters

| Field | Entry |
|---|---|
| Current proposed wording | "Approved board structure · Laminate finish · Approved hinges and channels" |
| Technical specification | POOJA_UNIT.UNIT carries board (no plywood promise) and surface; POOJA_UNIT.DOOR (standard doors) carries doors (block board), surface and hinges and channels; DOOR_CNC, BEADING and ASTA_CHAKRA are decorative |
| Customer impact | Standard pooja doors are promised as block board with laminate |
| Operational impact | Standard pooja doors must be block board with laminate |
| Recommended decision | APPROVE if standard pooja doors are block board with laminate |
| If changed | New version moving POOJA_UNIT.DOOR out of doors; new digest and review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |

## S4. Shutter exceptions

| Field | Entry |
|---|---|
| Current proposed wording | "Hinged and sliding shutters in branded block board"; any other board is named in the quotation |
| Technical specification | The doors category applies to the shutter lines of the kitchen, utility, wardrobe and loft, TV box and storage, crockery, study storage, vanities, storage boxes, standard pooja doors and window seats |
| Customer impact | Customers expect block-board shutters on every listed unit |
| Operational impact | Any non-block-board shutter (HDHMR, profile, glass) must be named in the quotation |
| Recommended decision | List the exceptions; CHANGE to remove them from the doors category, or APPROVE if there are none |
| If changed | New version without the excepted lines in doors; new digest and review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |

## S5. TV-unit and wall-panelling material

| Field | Entry |
|---|---|
| Current proposed wording | "Branded plywood TV unit · Laminate finish · Soft-close TV-unit hardware"; feature walls carry no material promise |
| Technical specification | TV_UNIT.PANEL carries structure and surface (laminate on plywood); FEATURE_WALL.* is decorative only |
| Customer impact | TV wall panels are promised as laminate on branded plywood |
| Operational impact | TV panels must be laminate on branded plywood |
| Recommended decision | APPROVE the TV panel; keep the feature wall as a final selection |
| If changed | New version adjusting TV_UNIT.PANEL; new digest and review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |

## S6. Living-room soft-close TV-unit hardware

| Field | Entry |
|---|---|
| Current proposed wording | "Soft-close TV-unit hardware" |
| Technical specification | The card prices TV_UNIT.SOFT_CLOSE (TV box, every style) and TV_UNIT.SOFT_CLOSE_STORAGE (side storage for box-with-storage and panelled styles) |
| Customer impact | Every TV unit, panelled included, is promised soft-close hinges |
| Operational impact | Every TV box and storage shutter must have soft-close hinges |
| Recommended decision | APPROVE if every TV box and storage has soft-close hinges; otherwise CHANGE: drop the TV-unit lines from soft-close (and the owner decides the card) |
| If changed | New version without TV_UNIT soft-close lines; new digest and review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |

## S7. Kitchen-accessory wording

| Field | Entry |
|---|---|
| Current proposed wording | "Kitchen accessories you choose, such as wicker baskets, rolling shutters and pantry pull-outs, come from approved brands. They are planned within your Design Personalisation Allowance, not within the kitchen subtotal" |
| Technical specification | The card prices no accessory line; the accessories category is details-only wherever a kitchen is priced |
| Customer impact | Customers learn accessories are drawn from the allowance, not included in the kitchen |
| Operational impact | Accessories are quoted as their own lines and replace part of the allowance |
| Recommended decision | APPROVE |
| If changed | New version with revised accessory wording; new digest and review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |

## S8. Brand and approved-equivalent wording

| Field | Entry |
|---|---|
| Current proposed wording | "Approved brands such as the named examples, or an approved equivalent of the same grade and specification. Final material and brand selections are confirmed in your detailed quotation." |
| Technical specification | Brand examples per category in ESSENTIAL-1.1 (Sylvan Blu; Sylvan Primo Plus; Merino, Century, Greenlam, Royal Touch, Stylam, Plain Art, Dazzle Berry, Airolam; Solid Edge, E3, URO, Red Star; Hettich; Blum; Nimmi; Ebco; Samsung Irex; Olive; Saint-Gobain; Philips; Wipro; Crompton; Avion; Asian Paints; Birla; Polycab; Finolex) |
| Customer impact | Named brands become expectations; equivalents need a clear rule |
| Operational impact | Every named brand must be currently procurable; equivalents need a recorded approval |
| Recommended decision | APPROVE after removing any brand not currently bought; equivalents approved by the designer and accepted by the customer in a quotation revision |
| If changed | New version with the revised brand list; new digest and review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |

## S9. Package-picker wording

| Field | Entry |
|---|---|
| Current proposed wording | "Branded materials and approved hardware, according to the selected rooms and product configuration." |
| Technical specification | Shown under Essential on the package screen (estimate-v2-copy.js promise.packageSubtitle) |
| Customer impact | No universal plywood or soft-close promise before rooms are priced |
| Operational impact | None |
| Recommended decision | APPROVE |
| If changed | Customer-copy change (no specification change); matrix and approval record updated; review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |

## S10. One-working-day designer callback

| Field | Entry |
|---|---|
| Current proposed wording | "A designer will call you within one working day …" and the two confirmation messages |
| Technical specification | estimate-v2-copy.js promise.leadQuote, doneQuote and doneConsult; source ADR-012 |
| Customer impact | Customers expect a call within one working day |
| Operational impact | Every V2 lead needs a call within one working day, with response-time monitoring |
| Recommended decision | APPROVE only with response-time monitoring in place; otherwise CHANGE to "A designer will call you to …" without a time commitment |
| If changed | Customer-copy change; matrix and approval record updated; review |
| **Owner decision** (APPROVE / CHANGE) | &nbsp; |
| **Owner name** | &nbsp; |
| **Decision date** | &nbsp; |
| Resulting specification change | &nbsp; |
| New digest and review required? | &nbsp; |
