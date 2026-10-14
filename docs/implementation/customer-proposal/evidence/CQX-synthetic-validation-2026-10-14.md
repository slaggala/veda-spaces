# CQX synthetic end-to-end validation — 2026-10-14

**Label: SYNTHETIC_VALIDATED.** Synthetic sites (B1 ten-site harness S41–S45), the SYNTHETIC rate card, the SYNTHETIC
commercial policy and the SYNTHETIC customer-proposal policy (both refused outside the test environment). No real
customer, rate, decision or policy is involved, and nothing here measures customer behaviour or conversion.

Suite: `api/tests/integration/test_cqx_end_to_end.py::test_customer_quotation_journey[<config>]` (one journey per
configuration, all twenty scenarios in order) and `::test_production_refusal…` (scenario 20), through the real API:
B1 measurement and verification → B2 scope and BOQ → B3 estimate → B4 quotation issue → CQX link, view, interaction and
acceptance. Engines: SQLite and PostgreSQL (results below).

| # | Scenario | How it is checked | 2 BHK | 3 BHK | 4 BHK | 5 BHK | IH |
|---|---|---|---|---|---|---|---|
| 1 | View active proposal | link opens; state OPEN; version 1 | ✔ | ✔ | ✔ | ✔ | ✔ |
| 2 | Room-by-room scope | room sections with lines; generic structure for every configuration | ✔ | ✔ | ✔ | ✔ | ✔ |
| 3 | Specifications and media | pinned specification per line; no unchecked image (media not served) | ✔ | ✔ | ✔ | ✔ | ✔ |
| 4 | Select optional item | SELECTED recorded; quotation unchanged | ✔ | ✔ | ✔ | ✔ | ✔ |
| 5 | Deselect optional item | DESELECTED; no selection left | ✔ | ✔ | ✔ | ✔ | ✔ |
| 6 | Submit question | LINE_QUESTION accepted (idempotency key) | ✔ | ✔ | ✔ | ✔ | ✔ |
| 7 | Submit change request | CHANGE_FINISH on a line | ✔ | ✔ | ✔ | ✔ | ✔ |
| 8 | Staff convert request to revision | version 2 created, request linked (ACCEPTED_FOR_REVISION), issued, shared | ✔ | ✔ | ✔ | ✔ | ✔ |
| 9 | Customer views revised version | version 2 with history and comparison; request shows "Version 2" | ✔ | ✔ | ✔ | ✔ | ✔ |
| 10 | Superseded link | v1 link → 410 PROPOSAL_SUPERSEDED | ✔ | ✔ | ✔ | ✔ | ✔ |
| 11 | Expired link | link past its own expiry → 410 PROPOSAL_LINK_EXPIRED | ✔ | ✔ | ✔ | ✔ | ✔ |
| 12 | Revoked link | revoked → 410 PROPOSAL_LINK_REVOKED | ✔ | ✔ | ✔ | ✔ | ✔ |
| 13 | Unauthorised access | no link, guessed link, staff session → 404 | ✔ | ✔ | ✔ | ✔ | ✔ |
| 14 | Cross-customer attempt | another lead's link shows only its own proposal | ✔ | ✔ | ✔ | ✔ | ✔ |
| 15 | Tampered frozen document | 409 SNAPSHOT_INTEGRITY_FAILED; nothing shown | ✔ | ✔ | ✔ | ✔ | ✔ |
| 16 | Duplicate acceptance | same key twice → same decision; one evidence row | ✔ | ✔ | ✔ | ✔ | ✔ |
| 17 | Acceptance of wrong version | version 1 named on the v2 link → 409 VERSION_MISMATCH | ✔ | ✔ | ✔ | ✔ | ✔ |
| 18 | Optional selection in accepted baseline | chosen item is the baseline's only selected optional entry | ✔ | ✔ | ✔ | ✔ | ✔ |
| 19 | Variation does not double count | no ADD for the chosen item; listed as kept | ✔ | ✔ | ✔ | ✔ | ✔ |
| 20 | Production refusal | each CQX flag refused in production | ✔ (configuration-independent) |

Other configurations: 5 BHK and the independent house use the SYNTHETIC preparation drivers of the MTQ end-to-end
suite (OI-MTQ-15 is the owner's and stays null), as B4 cannot issue them otherwise.

## Results

| Engine | Run | Result |
|---|---|---|
| SQLite | local, 2026-10-14, head of CQX-14 | 6 passed (5 journeys + production refusal), 0 skipped |
| PostgreSQL 16 | local (embedded), 2026-10-14, head of CQX-14 | 19 passed, 0 skipped (this suite with `test_cqx_acceptance` and `test_cqx_comparison`) |
| CI | the umbrella PR's `ci` run on the final head | see the PR description |

Browser (CQX-12): `app/e2e/proposal.e2e.mjs`, 48/48 checks at 360, 390, 768 and 1280 px (SYNTHETIC page models).
