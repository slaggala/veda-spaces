# Budgetary Estimate UX V2: customer-trust finalisation — review package

**Instruction:** `VEDA-SPACES-ESTIMATOR-UX-V2-CUSTOMER-TRUST-FINALIZATION` (owner). PR #58 stays merged.
**Branch:** `feature/estimator-v2-trust-finalization`. **Do not merge without independent review. Do not enable public
intake. Do not deploy to production. V1 is not removed.**

**Unchanged:** the pricing engine (`engine.py`, `ratecard.py`), the private rate card, calibration, the estimate
mathematics, the request contracts, lead linking and the staff pricing snapshot. No migration. Nothing under `dist/`,
`infra/` or `.github/`.

**Additive:**
- the public and staff estimate responses gain `room_details` (no amounts);
- the specification schema gains optional room-promise fields;
- ESSENTIAL-1.1 is added as a new version (1.0 stays loadable for the estimates that point to it);
- the V2 page is reworked;
- the staff panel shows the room promises.

## 1. Product principle: where each customer question is answered

| Customer question | Where it is answered (summary first, detail on demand) |
|---|---|
| What will my home approximately cost? | The range, with GST shown separately in the same format everywhere |
| What is included in the range? | **Your estimate includes**, directly under the range; **How your estimate is built** |
| What materials and hardware will I receive? | Each room's one-line **Essential specification**; **View inclusions & materials**; **View detailed material specification** |
| Why is the range wide? | **Why is this a range?** under the range, then the size and site variation in the build-up |
| What is excluded? | **Not included** |
| What warranty and service apply? | **Warranty and service**, split into manufacturer-backed protection and Veda Spaces service support |
| How can I make it more accurate? | **Personalise and narrow my estimate**, under "Why is this a range?" and in the next steps |
| What happens after I ask for a quotation? | **What happens next?** (six steps); the lead form says the same |

## 2. Result page, top to bottom

1. **Summary:**
   - the range;
   - "GST at 18% is extra: about ₹… – ₹…";
   - the basis line;
   - **Your estimate includes**: your selected rooms and products, the Site Execution & Handover Package and the Design Personalisation Allowance, with "GST is shown separately";
   - the trust markers;
   - **Why is this a range?** (five reasons), followed by the **Personalise and narrow my estimate** button;
   - a "What happens next ↓" link.
2. **How your estimate is built:** your selected rooms, optional items you added (when any), the package, the allowance (low to high), the size and site variation, your estimated range, and GST shown separately.
3. **What Essential includes:** the summary sentence and the equivalent and final-selection rule. "See all 14 material categories" and "View detailed material specification" are on demand.
4. **Your rooms:** each card shows the room name, its rounded subtotal (full rupees, so the rooms visibly add up), what it includes, and the room-specific one-line promise. One **View inclusions & materials** expansion holds four parts: included items, material specification, optional or selected extras, and assumptions.
5. **Site Execution & Handover Package:** the amount and "Included in your estimated range", then the T5 sentence. "What it covers" lists the six components.
6. **Design Personalisation Allowance:** the low-to-high amount and "Included in your estimated range", then the T6 sentence and three clarifications. "What it usually covers" lists the examples.
7. **Warranty and service:** manufacturer-backed protection; Veda Spaces service support; "View full warranty and exclusions".
8. **Not included.**
9. **How to compare this estimate.**
10. **Typical 3 BHK assumptions used.** "View technical assumptions" is collapsed.
11. **What happens next?** Six steps, then the CTAs: primary **Personalise and narrow my estimate**, secondary **Get my detailed quotation**, tertiary **Talk to a designer**.

No personal information is asked before the first estimate (e2e).

Screenshots, using the synthetic card with the ESSENTIAL-1.1 wording, are in [`ux-v2/finalization/`](ux-v2/finalization/):
- rooms;
- result;
- refine;
- confirmation;
- detailed specification.

## 3. Simplified assumptions (Phase 2)

**Shown by default, built from the rooms the customer kept:**
- "Standard modular kitchen with wall units and loft";
- "Three wardrobes with lofts" (counted from the selection);
- "TV unit and feature-wall scope" (or "TV unit scope");
- "Pooja and utility scope as selected";
- "Whole-home ceiling and lighting based on typical 3 BHK dimensions";
- "Your measurements are used for: …" (once any are given).

**View technical assumptions (collapsed):** the engine's own assumption lines, grouped by room from the stored
assumptions in `room_details`. Examples: kitchen counter length, drawer count, wardrobe width and height, crockery-unit
size, TV-wall width, ceiling area, profile-light length. Every assumption remains inspectable. An e2e check confirms the
section is closed by default.

## 4. Room-specific material mapping (Phase 3)

A specification category now names the priced lines that carry it (`applies_to.lines`). A room shows a promise only
when the estimate priced such a line in that room.

`customer_spec.room_materials` builds the one-line promise from:
- the snapshot;
- the priced lines;
- the package of the snapshot.

It takes one phrase per line group, worded per product when every priced line agrees. The result is deterministic: the same inputs always give the same text.

| Room (3 BHK, typical) | Promise |
|---|---|
| Kitchen | Branded plywood cabinetry · Laminate finish · Soft-close kitchen hardware |
| Bedroom (hinged wardrobe, bed, vanity) | Branded plywood furniture · Laminate finish · Soft-close wardrobe hardware |
| Bedroom (sliding wardrobe, no loft) | Branded plywood furniture · Laminate finish · Approved hinges and channels |
| Living room (TV unit) | Branded plywood TV unit · Laminate finish · Soft-close TV-unit hardware |
| Dining (crockery unit) | Branded plywood crockery unit · Laminate finish · Approved hinges and channels |
| Pooja room | Approved board structure · Laminate finish · Approved hinges and channels |
| Utility | Branded plywood utility unit · Laminate finish · Approved hinges and channels |
| Whole home | Gypsum ceiling on steel channels · Approved lighting specification (+ paint and wiring when added) |

**Rules, each enforced by a test:**
- **No soft-close promise without a priced soft-close line.** Soft-close is priced only in the kitchen, hinged wardrobes and lofts, and the TV unit.
- **No plywood promise for gypsum, glass, veneer or wall finishes.** These carry a final-selection statement instead.
- **Every phrase in a room line belongs to a category that applies in that room.**
- **Every applicability reference exists in the card.**
- **ESSENTIAL-1.0 gives no room line**, because it has no line applicability. This is the safe default.

The owner's living-room example omitted soft-close for a panelled TV unit. The card prices the TV box and side storage
of every TV unit style with soft-close hinges, so the data-driven line keeps it. Sales should confirm this.

Full mapping: [Essential Specification v1.1](specifications/ESSENTIAL-SPECIFICATION-v1.1.md), including the changes
from v1.0 and the sales checklist (vanity and utility boards in wet areas; shutter exceptions).

## 5. Warranty reconciliation (Phase 5)

[WARRANTY-RECONCILIATION.md](WARRANTY-RECONCILIATION.md) covers plywood, shutter board, hinges, channels, kitchen
tandems, electrical items, workmanship and fitment service against the policy, the engine texts and the October and
June specifications.

- **Resolved:** workmanship and fitment, which are Veda Spaces' own one-year service support from handover, per the policy.
- **Unresolved:** every material and hardware period. Plywood 30 against 10 conflicts and exceeds the policy's "up to 10"; the other periods lack product documentation. V2 therefore shows no material duration.
- **Tests:** a staging-build test fails if the V2 copy carries any numeric duration, or any spelled duration other than the service sentence, or the word "free". It also checks that the policy still states the one-year service.

## 6. Customer-promise matrix (Phases 4 and 12)

[essential-1.1-promise-matrix.md](specifications/essential-1.1-promise-matrix.md) (source JSON beside it) records,
for each of the 14 categories:
- customer wording;
- internal requirement;
- brand examples;
- equivalent rule;
- quotation mapping;
- procurement verification;
- execution verification;
- handover evidence;
- warranty source;
- accountable role.

It also lists 21 fixed page statements with their source, verification and owner.

**Tests:**
- `test_promise_matrix.py` fails when a visible specification statement is missing from the matrix, or when any link of the chain is empty.
- The staging-build test fails when a matrix statement is not on the page, or when a fixed page promise is not in the matrix.

**Status:**
- The operational chain is **PROPOSED**. Operations must confirm it before ESSENTIAL-1.1 is activated.
- The staff estimate panel lists what each room was promised and the specification code. This is the start of the chain into the detailed quotation.

## 7. How your estimate is built (Phase 8)

All values come from the estimate response:
- **Rooms:** the sum of the rounded room subtotals.
- **Optional items:** rounded to ₹1,000, like the rooms.
- **Package:** its amount.
- **Allowance:** low to high.
- **Size and site variation:** the displayed range minus the sum of the displayed components, so the build-up adds up exactly by construction. The engine applies a size band to each line (wider while sizes are typical) and to the package; the variation line shows that band, plus rounding.

No percentages are shown and no "most likely" value is invented.

**Tests:**
- The build-up sums to the displayed range, low and high, on the synthetic card and on draft 4.
- Its rooms row equals the response's rooms.
- The room cards as displayed add up to the rooms row.
- The package and allowance rows equal the response.
- With painting added, the optional-items row appears and the build-up still reconciles. This fixes the earlier V2 build-up, which left optional items out.

## 8. Trust markers (Phase 9)

- No contact details required for your first estimate
- Room-wise estimate shown
- Material specification available (only when a specification is active)
- Warranty and exclusions disclosed
- GST shown separately

Each marker is backed by behaviour that an e2e check verifies. There are no "No. 1", "best", "cheapest", "lowest",
"most accurate" or "guarantee" claims (e2e).

## 9. Package and allowance copy (Phases 6 and 7)

**Package:** "This covers the preparation, protection, material handling, completion and handover activities required
to execute the selected project scope professionally." It is shown with its value and "Included in your estimated
range". The expansion lists the six components. Soft-close stays in the product pricing. Nothing is called free.

**Allowance:** "This planning allowance protects your budget for commonly selected design additions. It is not an
automatic extra charge. Your detailed quotation replaces it with only the items you approve." Then:
- "The upper amount is not charged automatically."
- "The allowance is a share of your room work, so it moves when your room sizes change. Adding measurements does not remove it." This is true to the engine: the allowance is the card's band applied to room work.
- "In your detailed quotation, the items you actually approve replace it."

Kitchen accessories in ESSENTIAL-1.1 now say they are planned within this allowance. v1.0 implied they were included.

## 10. Tests and results (local, this branch)

| Gate | Result |
|---|---|
| pytest (SQLite and PostgreSQL) | 1,405 tests, 0 failures, 11 skipped (the skips predate this branch) |
| New: `test_customer_spec.py` room-promise tests, `test_promise_matrix.py`, `room_details` integration tests | pass |
| ruff check and format, mypy ratchet (157 against a baseline of 157), OpenAPI snapshot, secret scan | clean |
| app lint, typecheck, tokens, contrast, unit tests | pass |
| staging-build tests | 9/9, including no durations, no "free", the policy tie and the two-way matrix check |
| e2e: workspace | 7/7 |
| e2e: access | 16/16 |
| e2e: site | 34/34 |
| e2e: V1 estimator | 33/33 |
| e2e: **V2 estimator** | **45/45** |
| e2e: prototype | 47/47 |
| e2e: axe | 26/26 |

## 11. Rate-card equivalence (Phase 11.11)

**Setup:**
- The private draft-4 card was loaded into the local, throwaway e2e database. Its SHA-256 is identical to the one `list-cards` reports for the card active on staging.
- ESSENTIAL-1.1 was activated in the same database.
- The V2 suite ran with `E2E_CARD` and `E2E_QUIET=1`, so no amounts were printed and nothing was committed.

**Result:**
- **V1/V2 equivalence PASS:** the same range, rooms, package and allowance.
- Both reconciliations pass.
- The room promises match the table above.

The committed CI run repeats the check on the synthetic card.

## 12. Accessibility

- axe (WCAG 2.0, 2.1 and 2.2 A/AA tags) on all 10 V2 screens: 0 violations, with every disclosure opened.
- At 360 px: no horizontal scroll.
- **Keyboard:** Tab from the range reaches a room's "View inclusions & materials", and Enter opens it (e2e).
- **Screen reader:**
  - the range heading is announced (`aria-live`);
  - every result section is named and has a heading;
  - headings are nested (sections h3, rooms h4, expansion parts h5);
  - disclosures use native `details` and `summary`.

## 13. Production isolation and intake

- Nothing under `dist/`, `infra/` or `.github/` changed.
- The committed site keeps the estimator off (staging-build test).
- `public_intake` stays `disabled` in the staging configuration.
- V2 runs only on the staging build behind Cloudflare Access.
- **No rate leakage:** room details carry no amounts, the matrix test refuses ₹, and the page checks refuse per-unit wording.
- **No customer data:** the estimate takes none, and the room details hold room codes and assumption text only.
- **Historical snapshots:** estimates keep their specification row and SHA-256 (the integration test from #58). Room promises are derived from that snapshot and the stored lines.

## 14. Open conditions

**Current staging state (owner decision needed now):**
- ESSENTIAL-1.0 is active on staging and `STAGING_ESTIMATOR_UX=v2` is set (2026-10-08, behind Access). 1.0 shows the generic room promises this pass removes. The deployed V2 (from #58) shows its room line on every carpentry room.
- **Recommended:** set `STAGING_ESTIMATOR_UX=v1` and retry the Pages deployment until this branch is merged and ESSENTIAL-1.1 is active.

**Before V2 is activated on staging (Phase 11):**
1. Independent review of this branch, and of merged #58 in its current `main` state, then merge.
2. `12-deploy`. There is no migration, and the API change only adds a field.
3. Sales review of ESSENTIAL-1.1, using the checklist in the specification document.
4. Operations confirms the promise matrix; each row moves from PROPOSED to CONFIRMED with a named owner.
5. Warranty: the reconciliation is complete for what V2 shows (no material durations). The open rows block only the showing of a material duration.
6. Load and activate ESSENTIAL-1.1 (runbook §6.8), checking the document SHA-256 `b9a5ea24d249cc4b9a6fb4b0ee513a5f27f2b321a39c066654007bfc59091902` on the host before activation.
7. Set `STAGING_ESTIMATOR_UX=v2`. V1 stays available as `v1`.
8. Keep `public_intake` disabled and staging behind Access.
9. Optionally repeat the equivalence on staging. It is proven locally against the same card fingerprint.
10. Confirm production is unchanged.

**Comprehension validation (Phase 12):** moderated sessions with homeowners covering the range explanation,
package-included, allowance-not-extra and warranty separation. Behaviour is tested; comprehension needs people.

**Before public intake (unchanged, all open):**
- the ADR-011 intake hostname;
- production estimator flag approval;
- Premium rates;
- sizes other than 3 BHK;
- material warranty durations;
- a confirmed promise matrix;
- comprehension results;
- the owner's explicit decision.

## 15. Recommendation

Review and merge this branch. Meanwhile, set staging back to V1. After merge, deploy, complete the sales and operations
reviews, then activate ESSENTIAL-1.1 and V2 together on staging behind Access. Run the comprehension sessions there
with V1 available for comparison.
