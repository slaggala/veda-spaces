# Budgetary Estimate: owner sign-off package (ADR-012)

**Owner:** the repository owner (2026-10-08).

**What is signed off:** the Veda Spaces Preliminary Budgetary Estimate, rules `2026.10.2`, for **validation on staging
behind Cloudflare Access**.

**Not signed off:**
- public intake (ADR-011 E7);
- public or anonymous use of the estimator;
- production.

All three stay disabled. Production refuses `VEDA_ESTIMATOR_ENABLED`.

## 1. Delivery

| Item | Where |
|---|---|
| Implementation E1–E6, the frozen rules D1–D9 and the consolidated-review fixes | PR #47, merged to `main` by the owner. CI green on the merge commit |
| D3 scope (only supported sizes and property types offered), confirmation record, staging validation plan, this package | The follow-up PR from `feature/estimator-signoff` |
| Frozen business rules | [ADR-012 §11](../../architecture/decisions/ADR-012-budget-estimator.md); decision log 16–19 |
| Consolidated review | [ESTIMATOR-consolidated-review.md](ESTIMATOR-consolidated-review.md) |
| Historical validation | [E6-historical-validation.md](E6-historical-validation.md) |
| Technical review package | [ESTIMATOR-review-package.md](ESTIMATOR-review-package.md) |
| Staging validation plan | [ESTIMATOR-staging-validation-plan.md](ESTIMATOR-staging-validation-plan.md) |

## 2. Frozen business rules (as signed off)

| # | Rule |
|---|---|
| D1 | Premium disabled until validated against real Premium quotations |
| D2 | Luxury consultation-only, with no public estimate. The page, the build and the public endpoint all refuse to price it |
| D3 | 3 BHK medians as typical sizes. Unsupported sizes and property types are not offered: staging offers 3 BHK apartments only |
| D4 | Level 2 detail: range, GST separate, room subtotals (rounded to ₹1,000), the package as one value, the allowance as its own range. No rates, lines or quantities |
| D5 | The package holds exactly floor protection, plywood protection, freight, debris handling, deep cleaning and pest control. Soft-close hardware is in the kitchen, wardrobe and TV-unit pricing |
| D6 | Painting and electrical optional and unticked |
| D7 | 30-day validity. Unlinked estimates removed 90 days after creation, never while valid |
| D8 | Short warranty summary plus the policy link. Legal and tax review of the policy is **not claimed** |
| D9 | Five recurring product types and the disclosed Custom Features Allowance (5–15 % of room work), calibrated on past quotations |

## 3. Evidence

| Evidence | Result |
|---|---|
| CI on the PR #47 head (`e2c9936`) and on `main` after the merge | All checks pass: api (SQLite, PostgreSQL), app, browser e2e + axe, infra, security, Pages |
| API suite | 1,327 tests (11 skipped) on SQLite and PostgreSQL, run locally on the follow-up branch (CI re-runs them on its PR). Estimator engine: 67 tests. Estimator API: 34 scenarios on each database |
| Browser journey | 27/27 estimator checks on the PR #47 head: <ul><li>axe on steps 1–7 and the Luxury screens;</li><li>the allowance and the six package inclusions;</li><li>the Luxury path;</li><li>360 px;</li><li>no CSP violation, no page error.</li></ul> The follow-up PR adds the D3 offered-scope check |
| Staff app | 77 tests pass |
| Static gates | Lint and formatting, type-check ratchet at baseline, API contract snapshot, secret scan: all clean |
| Historical validation (E6, measured inputs) | Base vs actual +4.6 %, −3.8 %, −0.5 %. Each actual total lies inside its range (the old model missed all three by −14.5 % to −32.2 %) |
| Consolidated review | Three independent reviewers (AI agents with no shared context and read-only access). No high-severity finding; all medium findings fixed or mitigated, except S4, which is assigned to E7 |

## 4. Owner constraints: status

| Constraint | Status |
|---|---|
| Do not enable public intake | **Held.** Off by default. The committed pages are off |
| Do not enable the estimator publicly | **Held.** Off by default and refused in production. Staging stays behind Access |
| Do not remove Cloudflare Access from staging | **Held.** Unchanged |
| Do not expose commercial rates | **Held.** No rate in the repository, and the customer view has none. A residual risk is accepted: approximate rates can be inferred from any public calculator (review S2) |
| Do not alter production | **Held.** No production change; no deploy ran after the merge |
| Do not generate official quotations | **Held.** "Start the quotation process" only records an activity |
| Do not claim legal or tax approval | **Held.** D8 states that the review is pending |
| No customer data in fixtures; the private card never committed | **Held.** The fixture is synthetic, and the E6 document has percentages only |
| Do not merge without independent review | The owner merged PR #47 after the consolidated review. The reviewers were AI agents; a human review is the owner's call |

## 5. Open items

| # | Item | Needed for | Owner |
|---|---|---|---|
| 1 | Save the private card `ESS-2026-10-PRIVATE-DRAFT-4` and the comparison scripts outside the repository | Staging validation | Owner |
| 2 | Infra PR adding `VEDA_ESTIMATOR_ENABLED=true` (staging only) | Staging validation | Prepared on request; owner approves the apply |
| 3 | Warranty policy page URL, and its legal and tax review | Staging (URL); public use (review) | Owner |
| 4 | Two real Premium quotations | Enabling Premium (D1) | Owner |
| 5 | Preparation amounts, typical sizes and villa factors for other sizes and types | Offering them (D3) | Owner |
| 6 | A fourth, independent historical quotation | Public use | Owner |
| 7 | E7: dedicated intake hostname with an edge rate limit (review S4) | Public use | Engineering, after owner enablement |
| 8 | Error-summary accessibility follow-up (review U7) | Public use | Engineering |

## 6. Sign-off checklist

- [ ] Rules D1–D9 as in §2 (recorded: decision log 19)
- [ ] Merge the follow-up PR (D3 scope, plan and this package) after its CI passes
- [ ] Staging validation plan approved, including the infra PR (item 2)
- [ ] Private card draft 4 saved privately (item 1)
- [ ] Public intake and public estimator use remain disabled until a separate, recorded decision
