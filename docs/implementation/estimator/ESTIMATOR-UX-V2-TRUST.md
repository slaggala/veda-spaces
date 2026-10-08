# Budgetary Estimate UX V2: trust and conversion layer

**Instruction:** `VEDA-SPACES-ESTIMATOR-UX-V2-TRUST-AND-CONVERSION-UPGRADE` (owner).

**Frozen:** the pricing engine, rate card, calibration, APIs, database and staff estimate model. This phase changes
the **prototype only** (`app/e2e/site-release/prototype/estimator-v2/`, staging behind Access, never in `dist/`)
and records the design for the build.

## 1. Updated UX brief

**Goal:** be the most trustworthy interior budget estimator customers meet, by being specific, not by claims. No
"No. 1", "best" or "cheapest", and no naming of competitors.

**Principles:**
1. Estimate first.
2. Measurements later.
3. Homes and rooms, not product codes.
4. Customer language first.
5. Specifications on demand.
6. Honest scope over headline price.
7. Explain the range; do not disguise uncertainty.
8. Inclusions before contact details.
9. Never expose commercial rates.
10. Never promise a brand, warranty or feature the quotation may not deliver.

| Customer question | Where the page answers it (Variant B) |
|---|---|
| What materials am I getting? | **What Essential includes** (nine categories). An "Essential specification" line on each room. **View detailed material specification** |
| Why is a room priced at this amount? | The room card shows its inclusions and extras, sized to typical dimensions until measured. **View room details** and **View material details** |
| Why is the range so wide? | **How your range is built** and **Why is this a range?**, with **Narrow my range** |
| Is the package an extra charge? | **Included in your estimated range**, stated twice: under the range and on the package. **Why this is needed**; **View detailed breakdown** |
| Is the allowance a hidden cost? | Shown as its own amount, "Included in your estimated range", "a planning allowance, not an automatic extra charge". **What it usually covers**; **How it gets narrower** |
| What does the warranty cover? | **Warranty**: four lines consistent with the approved policy, and one link to the full policy |
| How do I compare with another quotation? | **How to compare this estimate**: an equal-scope checklist |

## 2. Result page, Variant A

The current result page, plus material summaries:
- an "Essential:" material line under each room;
- **What Essential includes** with the detailed specification link;
- the approved labels: Project Preparation & Protection Package and Custom Features Allowance.

**CTAs:** "Get my detailed quotation" (primary), "Tighten your range (optional)".

## 3. Result page, Variant B (trust-first)

Order, top to bottom:
1. The range, GST, and the basis (home, package, typical sizes).
2. **"Included in this range: your rooms, the Site Execution & Handover Package and the Design Personalisation
   Allowance. GST is extra."**
3. **CTAs:** Personalise and narrow my estimate (primary) · Get a detailed quotation · Talk to a designer.
4. **What Essential includes:** nine categories, each with a promise, and **View detailed material specification**.
5. **Your rooms:** each card shows the room, its subtotal, the standard inclusions, the extras chosen, the
   "Essential specification" line, **View room details** and **View material details**.
6. **Site Execution & Handover Package:** the amount; "Included in your estimated range"; what it is; **Why this is
   needed**; **View detailed breakdown** (the components; amounts appear in the quotation).
7. **Design Personalisation Allowance:** the range; "Included in your estimated range"; what it is; **What it usually
   covers**; **How it gets narrower**.
8. **How your range is built:**
   - your rooms (typical sizes);
   - plus the package;
   - plus the allowance;
   - equals the planning range, allowing for actual sizes and site conditions.

   Then **Why is this a range?** and **Narrow my range**.
9. **More about this estimate (folded):** Warranty, Not included, How to compare this estimate, Assumptions.
10. The disclaimer, the estimate reference and the validity.

**Three-tier presentation:** "How your range is built" uses only values the **unchanged public API already
returns**: the rounded room subtotals, the package amount, the allowance range and the planning range. It is
reproducible from the approved rate card and calibration, with no engine change. It does not introduce a
"maximum" beyond the planning range's upper end.

## 4. Mobile wireframes (360 px screenshots of the prototype)

| Screen | Screenshot |
|---|---|
| Package, with "What Essential includes" open | [v2-5-package.png](ux-v2/v2-5-package.png) |
| Result, Variant A | [v2-6-result-variant-A.png](ux-v2/v2-6-result-variant-A.png) |
| Result, Variant B | [v2-6-result-variant-B.png](ux-v2/v2-6-result-variant-B.png) |
| Room card with room and material details open | [v2-6b-room-card-details.png](ux-v2/v2-6b-room-card-details.png) |
| Detailed material specification | [v2-10-material-specification.png](ux-v2/v2-10-material-specification.png) |
| Other screens | [ESTIMATOR-UX-V2 §2](ESTIMATOR-UX-V2.md) |

## 5. Materials information architecture

| Level | Where | Content | Depth |
|---|---|---|---|
| L0 | Package screen, "What Essential includes" (folded) | One line per category, for example "Cabinet structure: Branded plywood structure" | Customer words, no numbers |
| L1 | Result, "What Essential includes" | Category and **promise**, for example "Doors and shutters in branded block board" | Customer words |
| L2 | Each room card | **Essential specification** line (structure · finish · hardware; ceiling for the whole home), and **View material details** (the categories that apply to that room, with their details) | The room's own materials |
| L3 | **View detailed material specification** (screen) | Per category: promise, grade or thickness (for example 18 mm cabinet bodies, 9 mm back panels, 1 mm outer laminate, 2 mm outer edge banding), brands, and the "or approved equivalent" policy | Specification, no prices |

**Never at any level:**
- rates, margins, supplier costs, or price ceilings (laminate per sheet, handles, extra paint colours);
- plywood warranty years.

## 6. Customer-facing specification schema (`veda.estimator.customer-spec/1`)

```json
{
  "schema": "veda.estimator.customer-spec/1",
  "id": "ESSENTIAL-2026-10",
  "package": "ESSENTIAL",
  "version": "1",
  "status": "DRAFT | ACTIVE | RETIRED",
  "effective_on": "2026-10-08",
  "title": "Essential specification",
  "or_equivalent": "Named brand or an approved equivalent of the same grade",
  "rate_card_version": "ESS-2026-10-PRIVATE-DRAFT-4",
  "categories": [
    {
      "id": "structure",
      "label": "Cabinet structure",
      "summary": "Branded plywood structure",
      "promise": "Cabinet bodies in branded plywood",
      "grade": "Grade per the approved specification (decision T1)",
      "thickness": ["18 mm cabinet bodies", "9 mm back panels", "12 mm behind the TV"],
      "finish": null,
      "brands": ["Sylvan"],
      "or_equivalent": true,
      "warranty_summary": "Manufacturer’s warranty for the exact product supplied, on the manufacturer’s terms",
      "rooms": ["kitchen", "living", "dining", "master", "bed2", "bed3", "pooja", "utility"],
      "details": ["…customer-facing lines…"]
    }
  ]
}
```

The `grade` value is left open until decision T1.

**Validation (refused on load):**
- any currency symbol or amount;
- any word for a price ceiling ("per sheet", "up to ₹", "credit");
- warranty years in `warranty_summary` unless the exact brand and product are guaranteed (decision T7);
- a category without `promise` or `rooms`;
- an unknown room;
- `ACTIVE` without an approval reference.

The prototype's `proto-spec.js` uses this shape. It holds a **baseline** (only what both historical specifications
agree on) and two **candidates** (October and June) behind `?spec=oct|jun`, so nothing conflicting is promised by
default.

## 7. Admin master data model

| Requirement | Design |
|---|---|
| Versioned, linked to the rate card and package | `estimator_spec_version`: `package`, `version`, `status` (DRAFT/ACTIVE/RETIRED), `effective_on`, `document` (the JSON in §6), `document_sha256`, `rate_card_version`, `approval_reference`, `activated_on/by`, `retired_on`. A partial unique index enforces one ACTIVE per package. Contract columns as every table |
| Older estimates never rewritten | The estimate records `spec_version_id` and `spec_sha256` when created. Customer and staff views render from that stored version |
| Activation audited, rollback | Events `SPEC_LOADED`, `SPEC_ACTIVATED`, `SPEC_RETIRED`, `SPEC_ROLLED_BACK`. The audit registry is FULL (the document excluded from snapshots, as for rate cards). `rollback-spec` re-activates the last retired version |
| Public text separate from rates | A separate table and document. The validator refuses amounts. The rate card stays private; the specification is publishable |
| Committed content | Synthetic and test specifications may be committed. The live specification is loaded like a card (CLI, owner approval) |
| Admin | Staff permission `estimate_spec.manage` (Founder, Admin), with an admin screen to view, load, activate and roll back. Read-only for Sales |

**Freeze note:** this needs **additive** database and API changes:
- a new table;
- two columns on `budget_estimate`;
- specification text in the public estimate response;
- staff routes.

The engine and calculations are untouched. The database and APIs are frozen, so this is an **owner exception**
(decision T9).

**Alternative without schema changes:** embed the specification in the rate-card document. Every estimate already
snapshots its card version and SHA, so the specification would be frozen per estimate. But the rate-card schema
would change, and a specification edit would need a new card version.

**Recommendation:** the separate table (T9).

## 8. Room-level copy

| Room | Standard inclusions (customer words) | Essential specification line | Extras |
|---|---|---|---|
| Kitchen | Modular kitchen with wall units and loft | Branded plywood structure · Laminate finish · Soft-close hardware | Tall pantry storage |
| Living room | TV unit with wall panelling | (same) | Feature wall · Sofa-back beading · Partition · Window seating |
| Dining | Crockery unit | (same) | Wash-basin unit · Feature wall · Veneer arch |
| Master bedroom | Wardrobe with loft, King bed with storage, Bathroom vanity | (same) | Dressing unit · Study desk · TV unit · Window seating · Feature wall · Bedside tables |
| Bedrooms 2 and 3 | Wardrobe with loft, Queen bed with storage, Bathroom vanity | (same) | As the master bedroom |
| Pooja room | Pooja unit with doors | (same) | Ceiling asta chakra |
| Utility | Utility unit | (same) | — |
| Whole home | False ceiling with lights, Profile lighting | Gypsum ceiling, LED lights | Painting (optional) · Electrical work (optional) |

**Rules:**
- The room details say each item is "sized to typical 3 BHK dimensions until measured".
- Each room shows one rounded subtotal (lakh with two decimals from ₹1 lakh, rupees below).
- Each room card says "Rates are never shown on this page; your detailed quotation lists every item".

## 9. Package and allowance copy

**Site Execution & Handover Package** (Variant B; internal identifier unchanged):
- "Included in your estimated range."
- "The execution and handover work that protects your home during the project and completes it professionally."
- **Why this is needed:** "Interiors work brings materials, cutting and dust into a finished home. Protecting floors
  and materials, moving and clearing materials and debris, and a final deep clean are part of doing the work
  properly, so they are planned and shown rather than added later."
- **View detailed breakdown:** site and floor protection; plywood and material protection; freight and material
  handling; debris handling; completion deep cleaning; pest-control preparation where applicable. "Your detailed
  quotation shows the amount for each item." Itemised amounts stay out of the public page, because the public API
  returns the grouped amount only.
- Soft-close hardware stays in the kitchen, wardrobe and TV-unit pricing.
- Never "optional", "free" or "complimentary".

**Design Personalisation Allowance** (Variant B):
- "Included in your estimated range: ₹X – ₹Y."
- "This protects your planning budget for design additions most homeowners choose once the design takes shape. It
  is a planning allowance, not an automatic extra charge: your detailed quotation replaces it with only the items
  you approve."
- **What it usually covers:** extra drawers, mirrors, pelmets, **additional** profile lighting (the standard profile
  lighting is already in the whole-home scope), lighting sensors, extra internal storage, selected accessories.
- **How it gets narrower:** "Deciding these details with your designer turns the allowance into specific items.
  Sharing measurements narrows the rest of your range."
- **Honesty note:** the frozen engine sets the allowance as a percentage band of room work. Measurements change its
  basis but do not narrow the band, so the copy does not claim that refinement narrows the allowance itself.

**Variant A** keeps the approved labels (Project Preparation & Protection Package, Custom Features Allowance) for
comparison.

## 10. Warranty copy (one source: the approved policy)

- Materials: the manufacturer’s warranty for the exact product supplied, on the manufacturer’s terms.
- Hardware: hinges and channels up to 5 years and kitchen drawers up to 3 years against manufacturing defects, as set
  out in our policy.
- Electrical items: 1 year, or the period the manufacturer documents for the item.
- Service: one year of free service from handover for fitment or workmanship issues within our scope.
- One link: "Read the full Warranty, Service & Customer Care Policy, including exclusions" (`/warranty`).

**Reconciliation:**
- The estimate shows **no plywood warranty years**. The historical specifications say 10 or 30 years, and the
  published policy says "up to 10 years, depending on the plywood selected".
- The hardware periods are the policy's own (clauses 1.2–1.3).
- The prototype test fails if "10 years", "30 years" or "30-year" appear on the result page.

## 11. CTA experiment

| Arm | Primary | Secondary | Tertiary |
|---|---|---|---|
| A | Get my detailed quotation | Tighten your range (optional) | — |
| B | Personalise and narrow my estimate | Get a detailed quotation | Talk to a designer |

- **Hypothesis:** B raises confidence (fewer drop-offs, more refinement) without lowering quotation requests per
  estimate. **Risk:** a personalise-first page may delay or reduce lead capture.
- **Measures:** CTA clicks per estimate (prototype event log `cta`), refinement completion, quotation and designer
  requests, time to the first CTA.
- **Decision rule:** adopt B if quotation and designer requests per estimate are not lower than A's and confidence
  measures are higher. Otherwise keep B's content with A's CTA order.

Assignment:
- The prototype assigns an arm at random when no `?variant=` is given.
- Facilitators fix it with `?variant=A|B`.
- The arm and the specification are shown in facilitator mode and recorded in the exported log.

## 12. Validation plan

| Item | Plan |
|---|---|
| Participants | Six Hyderabad 3 BHK homeowners: three see Variant A, three see Variant B (between-subject). At the end each sees the other variant for a preference question |
| Tasks | 1) What will the kitchen and wardrobe be made from? 2) Is the ₹70,000 package already included? 3) Why is there a ₹46,000–₹1,40,000 allowance? 4) What changes the estimate range? 5) What is excluded? 6) What warranty applies? 7) How would you compare this estimate with another provider? 8) Get to the first estimate (no contact details asked). 9) Make the estimate closer to your home without technical knowledge |
| Success criteria | Explains the material promise unaided. Understands that the package and the allowance are **included** in the range. Does **not** read the allowance as an automatic extra. Finds exclusions and warranty. Names the next action. No contact details before the first estimate. No internal rate visible. No accessibility regression. Mobile behaviour passes |
| Automated evidence (CI, `estimator-v2-prototype.e2e.mjs`, 47 checks) | Tasks 1–9 as checkable, both variants: CTA order, the "included" wording (twice), "not an automatic extra charge", range explanation, exclusions, warranty link, comparison checklist, no rates or price ceilings or conflicting warranty years, no conflicting specification by default, detailed specification screen, Talk to a designer (no amount), axe on every screen and both variants, 360 px, the production CSP, no network calls |

The illustrative package (₹70,000) and allowance (₹46,000–₹1,40,000) in the tasks come from the synthetic card on
the default 3 BHK scope.

## 13. Open owner decisions

| # | Decision | Options | Recommendation |
|---|---|---|---|
| T1 | Which historical specification is the Essential standard | October (Sylvan Blu plywood; 0.8 mm inner edge and laminate; Blum channels; Philips panels, Wipro COB) or June (Sylvan plywood; 1.3 mm inner edge; 0.72 mm inner laminate; Hettich channels; Wipro panels, Philips COB), or a stated hybrid. **Both agree on:** 18/9/12 mm plywood thicknesses, Sylvan Primo Plus block board, 1 mm outer laminate, 2 mm outer edge, laminate brands, Hettich hinges and drawers, accessories, Saint-Gobain ceiling, wiring and paint | Owner choice. **Not chosen silently:** the prototype shows only the agreed baseline |
| T2 | May public text name brands | Yes / No | **Yes**, at L1–L3; brands are trust signals customers recognise |
| T3 | Brand wording | Named brand · Named brand or approved equivalent · Approved branded material only | **Named brand or an approved equivalent of the same grade**: specific and deliverable |
| T4 | Show material price ceilings | Yes / No | **No.** They expose pricing detail; keep them in the quotation |
| T5 | Package name | Project Preparation & Protection Package (approved in ADR-012) or Site Execution & Handover Package | Decide **after the test**. A change is recorded as an ADR-012 amendment; the internal identifier is unchanged |
| T6 | Allowance name | Custom Features Allowance (approved) or Design Personalisation Allowance | Decide **after the test**; same recording |
| T7 | Warranty sentence | The four lines in §10 | **Approve §10**: no plywood years in the estimate; hardware periods from the policy |
| T8 | Room subtotals by default or on expansion | Visible (current) or folded | **Visible.** They answer "why is this room priced at this amount"; test confirms |
| T9 | Specification master data | Separate versioned table plus additive API and database (§7), or embedded in the rate card | **Separate table:** an owner exception to the freeze, additive only, no engine change |

## 14. Implementation migration plan

| Phase | Work | Gate |
|---|---|---|
| R0 (now) | Prototype with Variants A and B, specification candidates, trust copy; this document | CI green; owner review |
| R1 | Owner decisions T1–T4, T7, T8; specification text finalised (customer copy reviewed by sales) | Recorded decisions |
| R2 | Usability test (§12), six participants | Success criteria met, or findings accepted |
| R3 | T5 and T6 names decided from the test; ADR-012 amendment if the names change | Owner decision |
| R4 | If T9 is approved: specification master data (§7). Additive migration, CLI and admin screen; the estimate stores `spec_version_id`; the public response includes the stored specification. **Engine untouched** | CI; schema conformance; staff review |
| R5 | Build V2 with the winning result variant (ESTIMATOR-UX-V2 §9, P2), reading the specification from the API (R4) or from a versioned site file if T9 is declined (then estimates do not snapshot it; a documented limitation). **Customer labels:** the page renders its own copy, so the engine's text constants need not change | CI: equivalence test, e2e, axe |
| R6 | Staging validation (V1–V12 plus the §12 measures), then V1 retired | Owner sign-off |
| R7 | Public: ADR-011 E7, legal review of the policy, owner enablement | Separate decision |

**No pricing, calibration or engine change in any phase.**

## 15. Recommendation

1. **Run the test.** Take Variant B (trust-first) into the usability test as the leading design, with Variant A as
   the control.
2. **Decide T1, T2, T3, T4 and T7 first,** so both arms show the real specification rather than the baseline.
3. **Approve T9,** so every estimate records exactly which specification it promised. That is what makes "never
   promise what the quotation may not deliver" checkable afterwards.
