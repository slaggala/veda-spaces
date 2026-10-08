# E6: Historical quotation validation of the Budgetary Estimate engine

**Purpose:** check the pricing engine (E1) against real Veda Spaces quotations before any customer sees an estimate.
**Rule:** no customer names, addresses, project names or quotation totals appear here. The repository is public. Only
relative results are recorded. The private rate card and the comparison script stay with the owner.

## 1. Sources

| Ref | Source (private) | Home | Date | Rates vs the private card |
|---|---|---|---|---|
| A | Veda Spaces quotation workbook | 3 BHK apartment | October 2026 | Same rates (the card was built from it) |
| B | Veda Spaces quotation workbook | 3 BHK apartment | June 2026 | Older rates: carcass about 7 % higher, profile glass about 15 % lower, tandems about 12 % higher |

**Only two suitable quotations exist.** The instruction asks for at least three, so a third (ideally 2 BHK) is an
open owner input. A third document found locally was not a quotation and was not used.

## 2. Method

1. **Private card:** an Essential rate card (version `ESS-2026-10-PRIVATE-DRAFT`) built from quotation A's rates.
   Project preparation is priced for **3 BHK only**: the workbooks give no other size.
2. **Selections:** each quotation re-expressed as estimator selections (rooms, products, measurements, options), as a
   customer with the drawings would enter them.
3. **Comparison:** engine base and range against the quotation's pre-GST total.

## 3. Results

| Ref | Engine base vs actual | Actual inside the estimate range |
|---|---|---|
| A | **−14.5 %** | No (actual about 1.5 % above the upper bound) |
| B | **−32 %** | No |

**Causes, in order of size:**
1. **Work outside the 13 supported products.**
   - **Items:** veneer arches and accents, pooja units and doors, window seating and arches, sofa-back beading,
     bedside and storage boxes, ceiling profile lighting and fan points, additional mirrors, a block-board upgrade.
   - **Share:** about 9–10 % of A's total; well over 20 % of B's.
2. **Rate drift** between quotation dates (B).
3. **Simplified geometry:**
   - the loft run is assumed equal to the base run;
   - TV side storage uses a fixed height;
   - a profile-glass band is assumed;
   - the LED mirror is priced as a standard mirror.

## 4. Assessment

The engine computes exactly what its rate card and products describe. Tests prove that for every product.

As scoped, though, it **under-represents typical Veda Spaces projects**. A customer would see a range below what the
final quotation is likely to be. That undermines the purpose of reducing objections, and it must not go to customers
as is.

## 5. Owner decisions needed before customer use

1. **Add product types** for the recurring items above. Each is a rate-card entry plus wizard options; no engine
   change.
2. **Or approve a disclosed "custom features allowance"**, a percentage band for bespoke work, shown as its own line.
   No hidden uplift.
3. **Re-baseline** the private card on the current rates and confirm the range bands. The proposal: a typical-size
   upper band of at least +25 %, and a measured upper band reviewed after (1) or (2).
4. **Provide a third historical quotation** (2 BHK preferred) and project-preparation amounts for 1, 2 and 4 BHK.

**Re-run:** E6 is repeated after these inputs. **Acceptance:** each historical total lies within the estimate range,
and the base is within ±10 % of the actual.
