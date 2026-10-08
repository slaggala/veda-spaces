# Budgetary Estimate: consolidated review record

**Scope:** PR #47 (`feature/budget-estimator`) after the owner froze the business rules (ADR-012 §11, decision log
18).

**Method:** three independent reviewers. Each worked from a fresh context and only read the code. Each area got its
own reviewer:
1. Security and the public surface.
2. Pricing and data integrity. This reviewer also ran a fuzz test of about 1,200 random requests over three cards; it
   found no mis-pricing, no failed amount constraint and no failed recompute.
3. The customer and staff interfaces and the review documents.

Each finding below was checked against the code before it was given a disposition. Fixes are on the branch, with
tests.

**Result:** no high-severity finding. Every medium finding is fixed or mitigated, except S4, which is assigned to E7.

## Findings and dispositions

### Security and the public surface

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| S1 | Low | `POST /public/estimates` has no idempotency key, so a retry stores a second estimate | **Accepted.** An estimate holds no personal data and creates no lead. The per-IP, per-network, per-browser-token and aggregate limits apply, and unlinked estimates are removed after 90 days |
| S2 | Medium | Exact room subtotals plus the typical size in the assumption text let one response reveal a line rate and the allowance percentage | **Mitigated.** Customer subtotals are rounded to ₹1,000, and the allowance range outward to ₹1,000. Exact amounts are in the staff view only (`test_one_public_response_does_not_reveal_an_exact_rate`). **Residual:** approximate rates can always be inferred from any public calculator by varying inputs. This is inherent to D4 Level 2 |
| S3 | Medium | Two simultaneous enquiries on one reference: on PostgreSQL the second could fail with 409, losing that lead | **Fixed.** The link is made under a savepoint. A lost race records `ALREADY_LINKED` on the lead and the enquiry is still taken (`test_a_concurrently_linked_estimate_never_rejects_the_enquiry`, both databases) |
| S4 | Medium (availability) | The aggregate limits count requests before Turnstile, so a few networks could exhaust them for everyone | **Open, assigned to E7.** The edge rate limit on the dedicated intake hostname (ADR-011) is the control. The same pattern already applies to the existing public lead endpoint. Listed as a public-intake blocker |
| S5 | Low | Luxury could be priced publicly if a card enabled it | **Fixed.** The public endpoint refuses Luxury whatever the card says (D2; `test_luxury_is_never_priced_publicly`) |
| S6 | Low | The allowance band (5–15 %) is in the public repository | **Accepted.** It is an owner-approved rule (ADR-012 §11), not a rate |
| S7 | Low | The Luxury note was dropped from the notification when an estimate was also linked | **Fixed.** Both appear |

### Pricing and data integrity

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| P1 | Low | A computed area (width × height) was not bounded | **Fixed.** It is bounded like an entered area (`test_a_computed_area_is_bounded_like_an_entered_one`) |
| P2 | Low | A count could not be 0 but could be fractional | **Fixed.** Counts are whole numbers, and 0 is allowed (`test_counts_are_whole_and_may_be_zero`) |
| P3 | Low | Stored hundredths rounded half-even while the engine rounds half-up | **Fixed.** Both round half-up |
| P4 | Owner question | Soft-close is priced on kitchen, wardrobe and TV-unit shutters only, as approved, and on hinged wardrobe lofts. Crockery, study, storage and utility shutters have none | **Owner to confirm.** The engine supports any product; this is rate-card content |

### Customer and staff interfaces, and documents

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| U1 | Medium | A staff revision of a typical area or count sent `ft`, which was refused | **Fixed.** Typical inputs keep their unit kind (helper test) |
| U2 | Medium | A failed revision closed the form and hid its error | **Fixed.** The form stays open and shows the problem. The detail dialog shows problems too |
| U3 | Medium | On staging the default 2 BHK cannot be priced (the card prices 3 BHK only), and the customer learned this only at step 4 | **Mitigated.** A clear message says to choose another size. The runbook validation uses 3 BHK. **The full fix is owner data:** preparation amounts for the other sizes |
| U4 | Low | The confirmation heading could not take focus | **Fixed** (e2e check) |
| U5 | Low | A reload lost step 1 and the Luxury step 6, and could restore an expired estimate | **Fixed.** Step 1 is refilled, Luxury step 6 is restored, and only a valid estimate is restored |
| U6 | Low | The Luxury path still said "quotation" | **Fixed.** The heading, button and confirmation say design consultation (e2e check) |
| U7 | Low | The error summary has plain-text items; no `aria-invalid` or per-field messages | **Open.** An accessibility follow-up before public intake. axe passes on every screen checked |
| U8 | Low | Staff revision offered Luxury. The panel is empty for a Luxury-only lead | **Fixed** (Luxury removed). **Accepted:** the Luxury request is on the lead's activity timeline |
| U9 | Suspected | A Turnstile widget rendered while hidden (Luxury chosen first) might not complete | **Fixed defensively.** The widget restarts when shown again. Not reproduced |
| D1 | Docs | E6 said C was not in the first run but showed a first-run figure for it | **Fixed.** The column is now "old model", computed during the re-run |
| D2 | Docs | The browser-test coverage was overstated | **Fixed.** axe now runs on step 7 and the Luxury screens. The 360 px check runs on step 1, as now stated |
| D3 | Docs | E6 did not say that A's typical-size base (+10.1 %) misses the ±10 % criterion | **Fixed** |

## What remains before public intake

These are carried into the review package §11:
- **S4:** edge rate limiting on the E7 intake hostname.
- **U7:** the error-summary accessibility follow-up.
- **U3, owner data:** preparation amounts and typical sizes for the other home sizes.
- **P4:** the owner's confirmation of the soft-close scope.
- A fourth, independent historical quotation.
- E7 itself, and the owner's explicit enablement.
