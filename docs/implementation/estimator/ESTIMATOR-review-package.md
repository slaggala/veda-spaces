# Budgetary Estimate: consolidated independent-review package (ADR-012; ADR-011 conditions)

**Instruction:** `VEDA-SPACES-PUBLIC-INTAKE-AND-BUDGET-ESTIMATOR-IMPLEMENTATION` (owner, 2026-10-08).
**Branch:** `feature/budget-estimator`, one workstream with phase commits E1 to E6, plus the frozen business rules
(ADR-012 §11: D1–D9 and the soft-close modification). **E7 (the public-intake hostname) is not implemented**: it waits
for this review, staging validation and the owner's explicit enablement.

**Governance held throughout:**
- public intake disabled, and Cloudflare Access unchanged;
- no commercial rates and no customer data committed;
- production unchanged: the estimator is off and production refuses to enable it;
- no anonymously reachable API deployed;
- no official quotation generated;
- no legal or tax approval claimed.

**Consolidated review:** completed with three independent reviewers. No high-severity finding; the dispositions are in
[ESTIMATOR-consolidated-review.md](ESTIMATOR-consolidated-review.md).

## 1. What a reviewer should check first

| # | Claim | Where to verify |
|---|---|---|
| 1 | Off by default; production refuses it | `veda/config.py` (`estimator_enabled`, the production check); `test_public_endpoints_are_disabled_by_default`; the committed `estimate.html` metas are empty (`test_public_intake_disabled`) |
| 2 | Only two public endpoints, exact paths, default deny | `RBX_REGISTER["RBX-007"]` in `veda/app.py`; `test_no_route_exposes_a_rate_card` (public routes are exactly estimates, enquiries and the existing leads) |
| 3 | No personal data in an estimate | Closed `EstimateRequest`; `test_estimate_takes_no_personal_data`; no estimator table holds personal data |
| 4 | Customer responses never expose rates, lines, internal IDs or workflow state; subtotals are rounded to ₹1,000 | `service.public_view`; `test_public_estimate_is_customer_safe`; `test_customer_view_never_shows_rates_lines_or_quantities`; the enquiry returns `{reference, message}` only |
| 5 | The lead and its estimate link commit atomically | `create_public(on_created=…)`; `test_lead_and_link_commit_together` |
| 6 | An enquiry is never rejected because of its estimate | `usable_for_enquiry`; `test_unusable_estimate_never_rejects_the_enquiry` (unknown, expired, already linked, invalid) |
| 7 | Rates are never inferred | `RateCard._consistent` (an enabled package must price every line); Premium and Luxury off in the private card; `PACKAGE_UNAVAILABLE` |
| 8 | Project costs are honestly grouped | Engine `customer_view` (one value plus inclusions, never hidden from the total); staff view has the components; no "mandatory" label (test) |
| 9 | Reproducibility | Each estimate stores the inputs, the card version and SHA, and the rule version; `test_snapshot_is_complete_and_reproducible` recomputes and compares |
| 10 | The Custom Features Allowance is explicit, never hidden (D9) | Engine `_allowance`; its own customer-view component (label, description, range; no percentage or basis); `test_allowance_is_an_explicit_component_of_the_estimate`; stored as its own columns |
| 11 | No hardware in the package (D5) | `ratecard.PREP_COMPONENTS` (the schema refuses any other component); soft-close lines in the kitchen, wardrobe and TV unit; `test_soft_close_hardware_is_in_the_products_not_the_package` |
| 12 | Luxury has no public price (D2) | Wizard: Luxury leads to a consultation enquiry; `consultation: "LUXURY_DESIGN"` marks the lead; `test_luxury_enquiry_requests_a_design_consultation` |

## 2. Pricing engine (E1)

`veda/modules/estimator/engine.py` is pure: no database, clock or I/O. Its rules version is
`CALCULATION_VERSION = "2026.10.2"`.

```
line      = quantity(inputs, options) × rate[package]  # paise, half-up; quantity in hundredths; hardware in its product
work      = Σ lines of the allowance categories (carpentry, ceiling, finish; never optional items or the package)
allowance = work × [low %, high %]                      # Custom Features Allowance (D9); midpoint in the base
base      = Σ lines (rooms) + allowance midpoint + Project Preparation & Protection Package(home size, property, scope)
            + selected optional items (painting, electrical and lighting)
range     = Σ line × (1 ∓ band) where band = typical-size band if the line used an assumed size, else the measured
            band; preparation uses the measured band; + the allowance band; low rounded down and high rounded up
GST    = range × gst_pct, shown separately
timeline = the band containing the upper estimate;  warranty = summary filtered to the selection
```

- **Quantity kinds:** `area` (width × height input or constant), `direct` (as entered), `count`, `lump`, each with a
  factor. Option conditions (`when`) gate lines.
- **Assumptions:** recorded only for measurements that priced a line.
- **Preparation package:** includes only components applicable to the selected scope (carpentry, ceiling, finish,
  optional), with a villa factor.
- **Supported:** 18 products:
  - the original 13: Kitchen, Wardrobe, TV Unit, Living Room feature wall, Crockery Unit, Partition, False Ceiling,
    Study Unit, Vanity Unit, Bed and Headboard, Utility, optional Painting, optional Electrical and Lighting;
  - the five recurring types (D9): Pooja Unit, Window Seating, Veneer Accents, Storage Boxes, Ceiling Profile Lighting.

  Apartment or Villa, 1–4 BHK or Custom, up to 40 selections.
- **Soft-close hardware (D5):** priced per sq ft of shutter area in the kitchen (base, wall, loft), wardrobe (hinged
  body, loft) and TV unit (box, storage). It is not in the package.

## 3. Rate-card schema (`veda.estimator.rate-card/1`)

`ratecard.py` (pydantic, closed and frozen):
- **Top level:** `version`, `effective_on`, `currency` INR, `packages` {ESSENTIAL: true required, PREMIUM, LUXURY},
  `gst_pct`, `validity_days`.
- **`ranges`:** measured and typical bands, plus a rounding step. The typical band is at least as wide as the measured.
- **`bounds`:** per input kind.
- **`products`:** code, label, category, area, rooms, inputs with typical sizes by home size, options, and lines
  (code, label, UOM, quantity, rates by package, conditions).
- **`project_preparation`:** components with an inclusion text, amounts by home size and a villa factor. Only floor
  protection, plywood protection, freight, debris handling, deep cleaning and pest control are accepted (D5). A home
  size without an approved amount is not offered.
- **`custom_features_allowance`** (required): `low_pct`, `high_pct` (0–50, high ≥ low) and the categories it applies
  to.
- **`timeline`:** ascending bands, the last one open.
- **`exclusions`, `client_scope`.**

**Validation also refuses:** unknown references, duplicate codes, out-of-bounds typical sizes, an enabled package
without rates, and (in the loader) any email address or phone number.

## 4. Data model (E2, migration `0101_estimator`, expand-only)

| Table | Purpose |
|---|---|
| `estimator_rate_card` | The versioned card: document, SHA-256, rule version, status DRAFT/ACTIVE/RETIRED (one ACTIVE, partial unique index), approval reference, activation and retirement |
| `estimator_rate_item` | Flattened lines of a card, for staff review |
| `budget_estimate` | Immutable snapshot: public reference, card and rule versions, origin (PUBLIC/STAFF), source estimate, package, property, home size, kind, city, inputs, staff-view result, base/range/preparation/allowance (midpoint, low, high)/optional/GST amounts, timeline, lookup codes, expiry, site-measurement flag |
| `budget_estimate_line` | Each priced line (quantity in hundredths, rate, amount, typical, optional) |
| `budget_estimate_assumption` | Each assumed measurement (value in hundredths, unit, text) |
| `budget_estimate_project_item` | Preparation components (internal) |
| `budget_estimate_lead_link` | Estimate to lead (unique per estimate), consent policy version, preferred contact, linked on |
| `estimate_event` | Card loaded, activated, retired or rolled back; estimate created, linked, duplicated, revised, consultation copy, site measurement, quotation process started, expired |

All tables carry the contract columns (UUIDv7 id, created/updated/deleted by and on, `is_deleted`, `version`). All are
in the audit registry (FULL; documents and results not snapshotted). Permissions are `estimate.read` and
`estimate.manage`.

## 5. API catalog

| Method and path | Auth | Purpose |
|---|---|---|
| `POST /api/v1/public/estimates` | Public, RBX-007, flag, Turnstile, limits: 10/min and 60/h per IP, 120/h per network, 6/min per browser token (`X-Veda-Client`), 600/h aggregate | Create an estimate; customer-safe response with reference and expiry |
| `POST /api/v1/public/enquiries` | Public, RBX-007, flag, Turnstile, consent, Idempotency-Key, limits: 5/min and 30/h per IP, 60/h per network, 3/min per browser token, 300/h aggregate | The website enquiry plus `estimate_reference`, `preferred_contact` and `consultation` (`LUXURY_DESIGN` marks a Luxury design-consultation request on the lead; other values are ignored); returns `{reference, message}` |
| `GET /api/v1/leads/{lead_id}/estimates` | `estimate.read`, lead visibility | The lead's estimates |
| `GET /api/v1/estimates/{estimate_id}` | `estimate.read`, lead visibility (unlinked: ALL leads) | Staff view |
| `POST /api/v1/estimates/{id}/duplicate` | `estimate.manage` | A new estimate, same inputs, active card, linked to the same lead |
| `POST /api/v1/estimates/{id}/revisions` | `estimate.manage` | A new estimate with a changed package and/or selections |
| `POST /api/v1/estimates/{id}/consultation-copy` | `estimate.manage` | Customer-safe copy |
| `POST /api/v1/estimates/{id}/site-measurement` | `estimate.manage` | Flag plus a lead activity |
| `POST /api/v1/estimates/{id}/quotation-process` | `estimate.manage` | Records the start of the official process (lead activity); no quotation, no status change |

`/api/v1/public/leads` is unchanged.

## 6. Public wizard (E4)

`/estimate` (`estimate.html`, `assets/estimate.js`, `assets/estimate.css`). The screens:
1. Home: property type, BHK or custom, city, new or renovation.
2. Rooms and products (bedrooms follow the BHK; a Pooja room).
   - 18 products, including the five recurring types (D9).
   - Painting and electrical are optional and unticked (D6).
3. Measurements: value, unit (ft, in, m, cm; sq ft, sq m; nos), "Use a typical size", and guidance per input.
4. Package and preferences: options per product; Turnstile.
   - Premium shows "pricing coming soon" unless listed (D1).
   - Luxury says "priced after a design consultation" and goes straight to step 6 as a consultation request, with no
     estimate (D2).
5. Estimate: title, disclaimer and "subject to" list; range; GST; room subtotals; the grouped package with its six
   inclusions; the **Custom Features Allowance** as its own range and explanation; optional items; timeline;
   assumptions; exclusions; client scope; warranty summary and policy link; rate-card version and validity (30 days).
6. "Get my detailed quotation": name, phone, email, preferred contact, location, consent, Turnstile.
7. Confirmation: the customer reference, and the estimate reference when there is one (none on the Luxury path).

The page is mobile first, uses the production CSP, builds the DOM with `textContent`, keeps its state in
`sessionStorage`, and holds no rates.

## 7. Staff screens (E5)

The lead detail page has a "Budgetary Estimate" card (`vs-estimate-panel`). It shows the list, then the full view:
- reference, dates, card and rule versions, property;
- rooms, every line with rate and amount, typical-size markers, customer measurements and assumptions;
- package, room totals, range and GST, the package with its components, the allowance (band, basis, midpoint), timeline;
- exclusions and client scope, warranty, linked lead, history.

**Actions:** duplicate; revise measurements or package; consultation copy (printable); mark site measurement required;
start the official quotation process.

## 8. Tests and results

| Suite | Result |
|---|---|
| `tests/unit/test_estimator_engine.py` (E1) | 66 passed: every product (18), units and bounds, invalid input, packages, preparation grouping and scope, customer view without rates, reproducibility, monotonicity, timeline, lookups, warranty, card validation (including hardware in the package and the allowance band), unapproved home sizes, the allowance (explicit, banded, room work only), soft-close in the products, a full home in one request, whole-number counts, bounded computed areas, rounded customer subtotals |
| `tests/integration/test_estimator_api.py` (E2/E3) | 34 scenarios × SQLite and PostgreSQL = 68 passed: flag off, the allowance in the public response, the Luxury consultation enquiry, Luxury never priced publicly, a concurrently linked estimate never rejecting the enquiry, no card, customer-safe response, no personal data, Turnstile, invalid input, snapshot and reproducibility, link, retry, unusable references, atomicity, consent, notification text, staff view and actions, lead scope, unlinked visibility, no card route, card lifecycle and rollback, refusals (tamper, approval, customer data), CLI dry run, retention (90 days from creation, never while valid), rate limits |
| Schema, lint, registry, governance, ops | Updated head and order; module-boundary and seed-file lists; RBX register; committed estimator page is off |
| Full API suite | Pass (SQLite and PostgreSQL); ruff and format clean; mypy ratchet 157 = baseline; OpenAPI snapshot updated; secret scan clean |
| `app/scripts/staging-build.test.mjs` | 7 passed, including the estimator page off by default, on only with `STAGING_ESTIMATOR=on`, Essential only, no rates or `innerHTML` in the page script |
| `app/test/estimates.test.ts`, `app/e2e/estimator.e2e.mjs` | Run in CI (Node 22). **Helper tests:** units of typical inputs in revisions, no Luxury revision. **Browser journey:** off and on; steps 1–7 with axe on each; validation; the allowance and the six package inclusions; confirmation focus; the Luxury consultation path with axe on its screens; 360 px width on step 1; no CSP violations; no page errors |

## 9. Historical quotation comparison

See [E6-historical-validation.md](E6-historical-validation.md). Three 3 BHK quotations (A, B, and C in the same
building as B).

**Result on rules `2026.10.2`:**
- **Old model:** none of the three actual totals fell inside the range (base −14.5 %, −32.2 %, −31.2 %).
- **New model, measured inputs:** base +4.6 %, −3.8 % and −0.5 %; all three totals inside the range.
- **New model, typical sizes:** all three still inside (base +10.1 %, −8.8 %, +2.9 %).
- **Leave-one-out:** the allowance band still covers each quotation when sized on the other two.

**Not ready for customers** until a fourth, independent quotation is run and the other home sizes have approved
typical sizes and preparation amounts.

## 10. Open owner inputs

The business rules are frozen (ADR-012 §11, decision log 18). Still open, as data:

1. **Premium rates** and two real Premium quotations to check them (D1). Premium stays disabled; Luxury is
   consultation-only (D2).
2. **Preparation amounts** for 1, 2 and 4 BHK and villas, and the villa factors. Only 3 BHK is known, so the engine
   refuses the other sizes.
3. **Typical sizes** beyond 3 BHK (D3). 3 BHK uses the median of the three quotations.
4. **The soft-close basis:** per sq ft of shutter area, calibrated to A. Owner confirmation of the basis.
5. **A fourth, independent historical quotation** (2 BHK preferred).
6. **The warranty policy URL**, and the legal and tax review of the policy text (D8; not claimed).

## 11. Blockers for public intake (ADR-011)

- **E7 is not built:**
  - the dedicated intake hostname and its `cloudflared` rule exposing exactly the two endpoints;
  - an API Host guard;
  - no credentials on the public route;
  - an edge rate limit.
- **The owner inputs** in §10 (2, 3 and 5 at least, for the home sizes offered), and the soft-close scope (review P4).
- **From the consolidated review** ([record](ESTIMATOR-consolidated-review.md)):
  - S4: edge rate limiting on the intake hostname (the aggregate application limits count requests before
    Turnstile);
  - U7: the error-summary accessibility follow-up.
- **Independent review** of this package, then staging validation behind Access.
- **The owner's explicit enablement**, recorded as a decision.
- **Still open from earlier:** the deploy replica-safety order (R6-F1), and SES recipients verified or production
  access granted.

## 12. Blockers for production

All of §11, plus:
- the production configuration change: the production check refuses the estimator today, and lifting it is a reviewed
  change;
- the production rate card loaded and activated with approval;
- the production site build with the estimator metas;
- SES production access and DMARC;
- the earlier production items (host hardening batch, owner workstation).

## 13. Deployment plan (staging, after review)

1. Merge after independent review (CI green).
2. `10-infra-plan` / `11-infra-apply` only if the SSM flag change is included (a separate reviewed PR adds
   `VEDA_ESTIMATOR_ENABLED`, false at first). Then `12-deploy`, which runs migration `0101_estimator`.
3. Load the private Essential card (draft 3: the five product types, the allowance, soft-close in the products) and activate it with the owner's approval reference (runbook §6.8).
4. Flip the flag to true (reviewed change, then apply and deploy).
5. Pages `veda-staging-site`: `STAGING_ESTIMATOR=on`, retry.
6. Validate behind Access (runbook §6.8), then `13-evidence` with label `estimator-staging`.
7. **Do not proceed to E7 or production** without the owner's explicit approval.
