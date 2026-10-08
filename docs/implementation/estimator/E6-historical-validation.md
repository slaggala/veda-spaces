# E6: Historical quotation validation of the Budgetary Estimate engine

**Purpose:** check the pricing engine against real Veda Spaces quotations before any customer sees an estimate.
**Rule:** no customer names, addresses, project names or quotation totals appear here. The repository is public. Only
relative results are recorded. The private rate card and the comparison scripts stay with the owner.

**Runs:**
1. The first run, on rules `2026.10.1`, found the engine underestimating real projects.
2. The owner approved D9 ([ADR-012 §11](../../architecture/decisions/ADR-012-budget-estimator.md)).
3. The re-run below is on rules `2026.10.2`, with the private card `ESS-2026-10-PRIVATE-DRAFT-3`.

## 1. Sources

| Ref | Source (private) | Home | Date | Rates vs the private card |
|---|---|---|---|---|
| A | Veda Spaces quotation workbook | 3 BHK apartment | October 2026 | Same rates (the card was built from it) |
| B | Veda Spaces quotation workbook | 3 BHK apartment | June 2026 | Older rates: carcass about 7 % higher, profile glass about 15 % lower, tandems about 12 % higher |
| C | Veda Spaces quotation workbook | 3 BHK apartment, same building and layout as B | August 2026 revision | Carcass about 7 % lower; a revision made during execution (it carries execution-stage additions) |

C was not used in the first run.

**The evidence is thin:** three quotations, all 3 BHK apartments, two of them in one building. A fourth, independent
quotation (2 BHK preferred, another project) is an open owner input.

## 2. Method

1. **Private card (draft 3), Essential only:**
   - **Rates for the five new product types:** from A where A has the item. Otherwise from B and C, scaled to A's
     carcass rate level (B down about 7 %, C up about 8 %) and averaged when both have it. Lump and hardware amounts are taken
     as quoted.
   - **Soft-close hardware (D5):** out of the package. Priced per sq ft of shutter area in the kitchen, wardrobe and
     TV unit, at the rate that reproduces A's project-wide soft-close amount exactly.
   - **Custom Features Allowance (D9):** 5–15 % of room work. The band was sized from what the products left
     uncovered (§3) and checked by leaving one quotation out.
   - **3 BHK typical sizes (D3):** the median of the three quotations' measurements.
   - **Validity:** 30 days (D7).
2. **Selections:** each quotation re-expressed as estimator selections (rooms, products, measurements, options), as a
   customer with the drawings would enter them. A full 3 BHK needs 24–37 selections, hence the new limit of 40.
3. **Comparison:** the engine's base and range against the quotation's pre-GST total, in two modes:
   - **measured:** the quotation's measurements are entered;
   - **typical:** the same selections, with every measurement left to the typical size.

## 3. Results

| Ref | First run: base vs actual | Re-run, measured: base | Range | Actual in range | Re-run, typical sizes: base | Range | Actual in range |
|---|---|---|---|---|---|---|---|
| A | −14.5 % (outside the range) | **+4.6 %** | −9.4 % … +23.3 % | **Yes** | +10.1 % | −8.6 % … +37.8 % | Yes |
| B | −32.2 % (outside) | **−3.8 %** | −16.6 % … +13.6 % | **Yes** | −8.8 % | −25.0 % … +15.4 % | Yes |
| C | −31.2 % (outside) | **−0.5 %** | −13.9 % … +17.3 % | **Yes** | +2.9 % | −14.6 % … +28.7 % | Yes |

**Overall:**
- **Average gap, measured:** 3.0 % (first run: 26.0 %).
- **Range width:** about 31 % measured, up from 25 % in the first run, because the allowance band adds width. Wider
  with typical sizes.

**Where the gap closed:**
1. **The five new product types:** about 10 % (A), 22 % (B) and 23 % (C) of the actual totals.
2. **The allowance midpoint:** 8–9 % of the actual totals. What the products left uncovered was 4.8 %, 15.4 % and
   10.8 % of room work. It is mostly:
   - extra drawers, mirrors, pelmets and lighting sensors;
   - the block-board upgrade, electrical shifting and profile glass;
   - in C, execution-stage additions.
3. **Soft-close hardware:** within 0.3–7.4 % of the project-wide amount each quotation charged, so the per-sq-ft basis
   holds.
4. **Leave-one-out:** the allowance band sized on two quotations still covers the third. Base gaps +7.1 %, −5.8 % and
   −0.6 %, all in range.

## 4. Assessment

**Measured inputs meet the acceptance criteria** (every historical total inside its range, base within ±10 %) for all
three quotations. **Typical sizes** keep every total in range; A's base is at +10.1 %.

**Limits:**
- The new product rates, the allowance band and the 3 BHK typical sizes come from these same three quotations. The
  leave-one-out check covers the allowance only.
- B and C share a layout, and C is a revision made during execution.
- 1, 2 and 4 BHK and villas cannot be priced until their preparation amounts are approved (the engine refuses them).

**Not ready for customers until:**
- a fourth, independent quotation is run;
- typical sizes and preparation amounts are approved for the other home sizes;
- independent review, ADR-011 E7 and the owner's enablement are complete.

## 5. Re-run

E6 is repeated whenever the private card changes. The acceptance criteria stay the same: every historical total
inside its estimate range, and the base within ±10 %.
