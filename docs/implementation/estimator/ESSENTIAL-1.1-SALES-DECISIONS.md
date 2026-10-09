# Essential Specification 1.1: sales decision package

**Instruction:** `VEDA-SPACES-ESTIMATOR-V2-PRE-ACTIVATION-CLOSURE`.

**Status of every item: undecided.** Nothing here is approved until sales records a decision. A decision changes the
matrix row's status (`SALES_CONFIRMED`) and names its accountable owner, through a reviewed change. An item decided
"change" needs a new specification version, because loaded versions are never edited.

**What each item gives:**
- the proposed customer wording;
- the exact technical specification;
- the operational implication;
- the decision required;
- the recommendation.

The technical specification refers to the estimate's priced lines (`PRODUCT.LINE`), so the promise appears only where
that line is priced. Wording is from [ESSENTIAL-1.1](specifications/essential-specification-v1.1.json) and
[`estimate-v2-copy.js`](../../../app/e2e/site-release/assets/estimate-v2-copy.js).

| # | Item | Proposed customer wording | Exact technical specification | Operational implication | Decision required | Recommended decision |
|---|---|---|---|---|---|---|
| 1 | Bathroom vanity (wet area) | Room line "Branded plywood furniture · Laminate finish · …"; details "Cabinet and furniture bodies in branded plywood", "Hinged and sliding shutters in branded block board" | `VANITY_UNIT.TOILET`, `VANITY_UNIT.DRESSER` carry *structure* (plywood of the approved grade; October baseline Sylvan Blu; 18 mm bodies), *doors* (block board, Sylvan Primo Plus, 18 to 19 mm), *surface*, *edges* and *hinges and channels*. The mirror (`VANITY_UNIT.MIRROR`) is decorative, with no material promise | Every bathroom vanity must be built in the promised plywood and block board. If wet areas use a different board (BWP or marine grade, HDHMR, PVC or WPC), the promise is wrong | Which board and grade are used for bathroom vanities today? | **Unless sales confirms the same branded plywood and block board, move `VANITY_UNIT.TOILET` to "Approved board structure"** (the *board* category, with no plywood promise) in the version that is approved |
| 2 | Utility unit (wet area) | "Branded plywood utility unit · Laminate finish · Approved hinges and channels" | `UTILITY.WALL` carries *structure*, *doors*, *surface*, *edges*, *handles* and *hinges and channels* | As item 1, for utility areas | Which board and grade are used for utility units? | **As item 1: confirm, or move `UTILITY.WALL` to "Approved board structure"** |
| 3 | Pooja unit board and shutters | "Approved board structure · Laminate finish · Approved hinges and channels" | `POOJA_UNIT.UNIT` carries *board* (no plywood promise; the board is specified in the quotation) and *surface*. `POOJA_UNIT.DOOR` (standard doors) carries *doors* (block board), *surface* and *hinges and channels*. `POOJA_UNIT.DOOR_CNC`, `BEADING` and `ASTA_CHAKRA` are decorative, with no material promise | Standard pooja doors must be block board with laminate. CNC and veneer work is specified at design | Are standard pooja doors block board with laminate? | **Confirm.** If standard doors are another board, move `POOJA_UNIT.DOOR` out of *doors* |
| 4 | Shutter exceptions | "Hinged and sliding shutters in branded block board"; any other board is named in the quotation | *doors* applies to the shutter lines of the kitchen, utility, wardrobe and loft, TV box and storage, crockery, study storage, vanities, storage boxes, standard pooja doors and window seats. The policy mentions HDHMR and engineered-board shutters | Any shutter not in block board must be named in the quotation and excluded from this promise | List every product whose shutters are not block board (for example sliding wardrobe shutters, profile or glass shutters) | **List the exceptions;** remove them from *doors* in the approved version. The default rule stays block board |
| 5 | TV unit and wall panelling | "Branded plywood TV unit · Laminate finish · Soft-close TV-unit hardware". The feature wall carries no material promise (decorative) | `TV_UNIT.PANEL` carries *structure* and *surface* (laminate on plywood). `FEATURE_WALL.PANELLING`, `WALLPAPER` and `TEXTURE` are decorative only | The TV wall panel must be laminate on branded plywood. The feature-wall material is chosen at design | Is TV wall panelling laminate on branded plywood? Should the feature wall keep no material promise? | **Confirm the TV panel; keep the feature wall as a final selection** |
| 6 | Living-room soft-close (TV unit) | "Soft-close TV-unit hardware" | The card prices `TV_UNIT.SOFT_CLOSE` (TV box, every style) and `TV_UNIT.SOFT_CLOSE_STORAGE` (side storage, box-with-storage and panelled styles); the *soft-close* category follows those lines | Every TV box and TV storage shutter must have soft-close hinges, including the panelled style | Do TV units, panelled ones included, get soft-close hinges on the box and storage? | **Confirm.** If not, the card is wrong for that style (an owner decision on the card). Until it is corrected, drop the TV-unit lines from *soft-close* in the approved version |
| 7 | Kitchen accessories | "Kitchen accessories you choose, such as wicker baskets, rolling shutters and pantry pull-outs, come from approved brands. They are planned within your Design Personalisation Allowance, not within the kitchen subtotal" | The card prices no accessory line. The *accessories* category is details-only and appears wherever a kitchen is priced | Accessories are quoted as their own lines and replace part of the allowance | Is that how accessories are sold and quoted? | **Confirm** |
| 8 | Approved brands and equivalent rule | "Approved brands such as the named examples, or an approved equivalent of the same grade and specification. Final material and brand selections are confirmed in your detailed quotation." | Examples: Sylvan Blu; Sylvan Primo Plus; Merino, Century, Greenlam, Royal Touch, Stylam, Plain Art, Dazzle Berry, Airolam; Solid Edge, E3, URO, Red Star; Hettich; Blum; Nimmi; Ebco; Samsung Irex; Olive; Saint-Gobain; Philips; Wipro; Crompton; Avion; Asian Paints; Birla; Polycab; Finolex | Every named brand must be one Veda Spaces can buy today. An equivalent needs a recorded approval (the exception process) | Is every brand currently approved and procurable? Who approves an equivalent? | **Confirm the list and remove any brand not currently bought.** Equivalents are approved by the designer and accepted by the customer in a quotation revision before procurement |
| 9 | Package-picker subtitle | "Branded materials and approved hardware, according to the selected rooms and product configuration." | Shown under Essential on the package screen, replacing the old generic "Branded plywood, laminate finishes and soft-close hardware" | No universal soft-close or plywood promise before rooms are priced | Approve the wording | **Approve** (the owner-suggested safe statement) |
| 10 | "Within one working day" call | "A designer will call you within one working day to arrange a physical site measurement…", plus the two confirmation messages | Shown on the quotation and consultation forms and after submission. Source: ADR-012 | Every V2 lead needs a call within one working day, which requires the lead workflow to track response time | Can sales commit to it, including what counts as a working day (weekends and holidays)? | **Approve only with response-time monitoring in place.** Otherwise change the wording to "A designer will call you to arrange…" without a time commitment |

## Recording a decision

For each item, sales records the following, in a pull request that changes
[`essential-1.1-promise-matrix.json`](../../../api/veda/modules/estimator/approved/essential-1.1-promise-matrix.json) (and the specification when
the decision is "change"):
- the decision: approve, or change with the new wording or technical scope;
- the name of the accountable owner;
- the date.

`veda estimator activation-check` then shows what is still blocked.
