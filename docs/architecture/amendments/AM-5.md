# AM-5: proposed amendment to 08 §1, 06 §11 (RBX-003), 09

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It does not modify the certified documents and has no effect until the decision owner approves it.

| Field | Value |
|---|---|
| Amendment ID | AM-5 |
| Related finding | IR-07, IR-A10 |
| Related deviation | DEV-005 |
| Amends | 08 §1, 06 §11 (RBX-003), 09 |
| Existing certified behavior | 06 §7.5 step 5 requires a signed cancel link; no endpoint or page is named; RBX-003 does not list one. |
| Proposed behavior | Add POST /api/v1/approvals/cancel-link {token} (RBX-003, public) to the 08 index and the RBX-003 register, and a public SPA page /approvals/cancel that cancels only after an explicit confirmation. Retention of outbox_event must exceed the break-glass window (the link binding relies on those rows, IR-A10). |
| Reason | Makes the certified veto usable. |
| Security impact | 256-bit HMAC token, hash stored, single use, sibling links invalidated, uniform 400. |
| Data impact | None. |
| API impact | One public endpoint (already implemented at 9236aa3). |
| UI impact | New page. |
| Compatibility impact | Additive. |
| Tests | `api/tests/integration/test_founder_governance.py::test_G12_cancel_link_by_notified_party`<br>`app/e2e/access.e2e.mjs: break-glass cancel link works end to end from the email` |
| Rollback | Remove the endpoint and page; the veto becomes unusable again. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
