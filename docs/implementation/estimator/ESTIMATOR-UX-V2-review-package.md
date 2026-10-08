# Budgetary Estimate UX V2: independent review package

**Instruction:** `VEDA-SPACES-ESTIMATOR-UX-V2-OWNER-DECISIONS-AND-IMPLEMENTATION` (owner decisions T1–T9).
**Branch:** `feature/estimator-ux-v2-implementation`. **Do not merge without independent review. Do not enable public
intake. Do not deploy to production.**

**Frozen and unchanged:** the pricing engine, rate card, calibration, calculations, the estimate and enquiry API
contracts (one additive response field, below), lead linking, and the staff pricing snapshot. `dist/` (production),
`infra/` and the workflows are untouched.

## 1. What changed, by phase

| Phase | Scope | Main files |
|---|---|---|
| P1 | Customer specification master (T9): versioned, audited, one active per package, per-estimate snapshot | `api/veda/modules/estimator/{models,customer_spec,service}.py`, migration `0102_estimator_spec`, CLI, `test_estimator_spec.py` |
| P2 | Essential Specification v1.0 (T1–T4, T7), reconciled with the historical specifications | `docs/implementation/estimator/specifications/`, `test_customer_spec.py` |
| P3 | The V2 page (Variant B) behind `STAGING_ESTIMATOR_UX=v2`; V1 kept | `app/e2e/site-release/estimate.html`, `assets/estimate-v2.{js,css}`, `app/scripts/staging-build.mjs`, `app/e2e/estimator-v2.e2e.mjs` |
| P4 | Staff panel shows the specification; this package; runbook §6.8; decision log | `app/src/modules/leads/estimate-panel.ts`, docs |

## 2. Final V2 flow

1. Home type (Apartment; others shown only when the card supports them).
2. BHK (3 BHK only on staging; other sizes visible but not selectable).
3. New home or renovation; optional city.
4. Rooms: preselected for the home size, each with its standard inclusions; extras folded behind "Add extras";
   no measurements.
5. Package: Essential; Premium shown as not yet available; Luxury leads to a design consultation without a price.
6. **Instant estimate** (no contact details, no measurements), in the owner's order:
   1. estimate range, GST line and basis;
   2. "Included in this range: your rooms, the Site Execution & Handover Package and the Design Personalisation
      Allowance. GST is extra.";
   3. **What Essential includes**: nine categories from the estimate's specification snapshot, the
      equivalent rule and the final-selection checkpoint, then **View detailed material specification**;
   4. **Your rooms**: room subtotals;
   5. **Site Execution & Handover Package**;
   6. **Design Personalisation Allowance**;
   7. **Why this is a range**, with **Narrow my range**;
   8. **Warranty and service**;
   9. **Not included**;
   10. **How to compare this estimate**;
   11. **Assumptions**;
   12. **Next steps**: CTAs.
7. Lead form (quotation, or consultation for Luxury and "Talk to a designer").
8. Refine: four optional measurements in feet and square feet; a new estimate.
9. Confirmation with the customer reference.
10. Detailed material specification (on demand).

## 3. Essential Specification v1.0 (T1–T4, T7)

- Source of truth: `specifications/essential-specification-v1.0.json`, spec code `ESSENTIAL-1.0`.
- Rendered for review, with the reconciliation of the October and June specifications:
  [`ESSENTIAL-SPECIFICATION-v1.0.md`](specifications/ESSENTIAL-SPECIFICATION-v1.0.md).
- Nine categories: cabinet structure, doors and shutters, surface finish, edges, hardware, handles, kitchen
  accessories, ceiling and lighting, and optional electrical and painting.
- **T3:** every category holds its material requirement, brand examples, the equivalent rule ("Approved brands such as
  the named examples, or an approved equivalent of the same grade and specification.") and the final-selection
  checkpoint ("Final material and brand selections are confirmed in your detailed quotation."). The detailed screen
  shows the four parts separately for each category; an e2e check enforces it.
- **T4 and T7:** the validator refuses any amount, price word, price limit, rate, margin, duration, email address or
  phone number, so a specification that states one cannot be loaded.

## 4. Specification master (T9)

| Table | Purpose |
|---|---|
| `estimator_customer_spec` | `spec_code` (unique, e.g. `ESSENTIAL-1.0`), `spec_version`, `package`, `name`, `summary`, `status` (DRAFT, ACTIVE, RETIRED), `effective_on`, `document` (the validated JSON), `document_sha256`, `approval_reference`, `activated_on`/`activated_by`, `retired_on`, plus audit fields. A partial unique index allows **one ACTIVE per package**; each environment has its own database, so this is per package and environment |
| `estimator_customer_spec_item` | One row per category: `category_code`, `label`, `summary`, `requirement`, `grade`, `thickness`, `finish`, `brand_examples`, `equivalent_rule`, `final_selection`, `hardware_category`, `warranty_summary`, `applicability` (rooms and products) |
| `estimator_spec_event` | SPEC_LOADED, SPEC_ACTIVATED, SPEC_RETIRED, SPEC_ROLLED_BACK, with the approval reference |
| `budget_estimate` (+2 nullable columns) | `customer_spec_id` (FK, RESTRICT) and `customer_spec_sha256`: the snapshot |

**Rules:**
- **Immutable:** a loaded version is never edited. A change is a new version.
- **Activation and rollback:** both need an owner approval reference of at least 10 characters and a SHA-256 match. Activation retires the previous version. Rollback re-activates the last retired one.
- **Snapshot:** a new estimate records the active version and its SHA-256. Activating v2 later leaves earlier estimates showing v1. Tested in `test_estimator_spec.py::test_each_estimate_snapshots_the_specification_and_history_never_changes`.
- **Separate from rates:** no amount can be loaded (validator). Rate cards stay in their own tables and are never public.

**Data and API:**
- **Committed data:** only the synthetic test specification (`tests/fixtures/estimator/synthetic-customer-spec.json`) and the customer-facing ESSENTIAL-1.0, which holds no rates. Live loading follows the controlled procedure (runbook §6.8).
- **Additive API field:** the public estimate response gains `specification` (the customer view of the snapshot, or `null`). The request schemas are unchanged, and the OpenAPI snapshot is unchanged: it does not describe response bodies. The staff estimate view gains `specification` (code, version, SHA-256, document), and the staff panel shows the code.
- **Migration:** `0102_estimator_spec` is expand-only. It adds three tables and two nullable columns, and needs no backfill. Earlier estimates show "specification confirmed in your quotation". Downgrade is not supported, as for the other migrations. Rollback is operational: set `STAGING_ESTIMATOR_UX=v1`, or roll back the specification.

## 5. Customer copy

**Room card (T8):** the room name and subtotal (rounded), then:
- the standard inclusions;
- "Your extras: …";
- "**Essential specification:** Branded plywood structure · Laminate finish · Soft-close hardware" (from the snapshot; the whole home shows "Gypsum ceiling, LED lights");
- **View room details**: each item "sized to typical dimensions until measured";
- **View material details**: the categories that apply to that room, with their requirement and thicknesses.

**Material summaries:** each category's `summary` (for example "Branded plywood structure", "Sealed edges",
"Soft-close hardware"). **Detailed material view:** per category, the requirement, grade, thickness, finish, approved
brand examples, approved equivalent, final selection and warranty.

**Site Execution & Handover Package (T5):** "Included in your estimated range". "This covers the preparation,
protection, material handling, completion and handover activities required to execute your project professionally."
Detailed breakdown: site and floor protection; plywood and material protection; material freight and handling;
debris handling; completion deep cleaning; pest-control preparation where applicable. Soft-close stays in the
kitchen, wardrobe and TV-unit prices, not in the package.

**Design Personalisation Allowance (T6):** "Included in your estimated range". "This planning allowance protects your
budget for design additions homeowners commonly choose. It is not an automatic extra charge: your detailed
quotation replaces it with only the items you approve." Examples: additional drawers, mirrors, pelmets, profile
lighting beyond your selection, lighting sensors, additional internal storage, selected accessories.

**Warranty (T7):** "Material and hardware warranties depend on the selected manufacturer, product and documented
warranty terms. Applicable workmanship and fitment service is provided according to the Veda Spaces Warranty, Service
& Customer Care Policy." There is one link, to the policy URL from the API (`VEDA_WARRANTY_POLICY_URL`), and no durations.

**CTAs:**
- **Personalise and narrow my estimate** (primary): goes to refine, then a new estimate, then the quotation.
- **Get my detailed quotation** (secondary): the lead form, linked to the latest estimate.
- **Talk to a designer** (tertiary): a consultation form. It sends a normal enquiry linked to the estimate, with the message "Asked to talk to a designer".

Luxury sends a consultation request (`LUXURY_DESIGN`) without a price.

## 6. Owner validation criteria 1–14

| # | Criterion | Evidence |
|---|---|---|
| 1 | Same selections, same range in V1 and V2 | e2e `V1/V2 equivalence`. V1 is driven with exactly the selections V2 sent (options set to the same effective values). The range, each room, the package and the allowance are identical |
| 2 | No contact details before the first estimate | e2e `estimate before any contact details` (the lead screen is not shown) |
| 3 | No measurements before the first estimate | e2e: no number inputs on the rooms screen, and every selection is sent with empty `measurements` |
| 4 | The customer can explain the materials | "What Essential includes", room specification lines, the detailed view. e2e `material promise from the specification snapshot` |
| 5 | The package is understood as included | "Included in your estimated range", the build-up in "Why this is a range". e2e `package and allowance included` |
| 6 | The allowance is understood as included and not automatic | the same, plus "not an automatic extra charge" (e2e) |
| 7 | Warranty and exclusions are findable | "Warranty and service" with one policy link, and "Not included". e2e `warranty wording (T7) and policy link` |
| 8 | Refinement without engineering terms | e2e: no RUN, WIDTH, AREA, carcass or uom. Labels in ft and sq ft |
| 9 | No rate exposed | e2e `no rates, price limits or warranty durations shown`. staging-build test: the V2 script has no rate table, "per sq" or "per sheet". The validator blocks money in specifications |
| 10 | No conflicting specifications | one source (the snapshot); reconciliation table in Essential Specification v1.0; one ACTIVE per package (unique index) |
| 11 | Historical estimates keep their snapshot | `test_estimator_spec.py` snapshot test (SQLite and PostgreSQL) |
| 12 | Mobile and accessibility | e2e at 360 px. axe (WCAG 2.2 AA tags) on all 10 V2 screens: 0 violations. No horizontal scroll. Errors linked to fields |
| 13 | Production unchanged | no change under `dist/`, `infra/` or `.github/`. The committed page keeps the estimator off (staging-build test) |
| 14 | Public intake disabled | no intake setting changed. V2 runs only on the staging build behind Cloudflare Access |

## 7. Tests and results (local, this branch)

| Gate | Result |
|---|---|
| pytest (SQLite and PostgreSQL) | 1,374 tests, 0 failures, 11 skipped (pre-existing environment skips) |
| ruff check, ruff format | clean |
| mypy ratchet | 157 (baseline 157) |
| OpenAPI snapshot | matches |
| Secret scan | clean (baseline line numbers refreshed) |
| app lint, typecheck, unit tests (77), contrast, tokens | pass |
| staging-build tests | 9/9 (UX switch: default V1, `v2`, invalid refused; the V2 script holds no rates or durations) |
| e2e `run-all.sh` | workspace 7/7, access 16/16, site 34/34, estimator V1 33/33, **estimator V2 35/35**, prototype 47/47, axe 26/26 |

The V2 e2e also passes with the real ESSENTIAL-1.0 specification active on a local database (`E2E_SPEC=ESSENTIAL-1.0`).
The screenshots below come from that run with the **synthetic** rate card, so the amounts are synthetic:
- [`ux-v2/build/v2-build-4-rooms.png`](ux-v2/build/v2-build-4-rooms.png)
- [`v2-build-6-result.png`](ux-v2/build/v2-build-6-result.png)
- [`v2-build-8-refine.png`](ux-v2/build/v2-build-8-refine.png)
- [`v2-build-9-confirmation.png`](ux-v2/build/v2-build-9-confirmation.png)
- [`v2-build-10-specification.png`](ux-v2/build/v2-build-10-specification.png)

In full-page captures the fixed skip link is drawn mid-page. In the browser it stays off-screen until focused.

## 8. Open conditions

**Before staging use (owner):**
1. Independent review of this branch, then merge.
2. `12-deploy` to apply migration `0102_estimator_spec` on staging.
3. Sales review of the ESSENTIAL-1.0 customer wording (the checklist in the specification).
4. Load and activate ESSENTIAL-1.0 with the owner's approval reference (runbook §6.8). Until then, staging estimates show "specification confirmed in your quotation" and no material promise.
5. Set `STAGING_ESTIMATOR_UX=v2` in the Pages project `veda-staging-site` and retry the deployment.
6. A staging run of the V1/V2 equivalence and the result-page checks against draft card 4. The e2e proves equivalence on the synthetic card; the private card uses the same code path.

**Before V1 is removed:** moderated usability sessions with homeowners (the criteria 4–8 questions), and a comparison
with Variant A, which stays in the prototype only as the control.

**Before public intake (unchanged, all open):**
- ADR-011 intake hostname (E7) built and reviewed;
- production estimator flag approval;
- Premium rates validated against real quotations;
- sizes other than 3 BHK priced;
- the warranty policy and specification durations reconciled (T7) before any duration is shown;
- the owner's explicit enablement decision.

## 9. Recommendation

Review and merge. Then enable V2 on staging (behind Access) with ESSENTIAL-1.0 active, and run usability sessions
while V1 remains available through `STAGING_ESTIMATOR_UX=v1`. Keep public intake disabled.
