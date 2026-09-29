# AM-5: proposed amendment to 08 §1, 06 §11 (RBX-003), 06 §7.5, 09

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It lives outside `docs/architecture/`, does not modify the certified documents, and has no effect until the decision owner approves it. Nothing here claims owner approval or implementation authorization.

| Field | Value |
|---|---|
| Amendment ID | AM-5 |
| Amends | 08 §1, 06 §11 (RBX-003), 06 §7.5, 09 |
| Related findings | IR-07, IR-A10, RR-A11 |
| Related deviation | DEV-005 |
| Targeted re-review assessment | Technically sound; incomplete: rollback text contradicts 06 §7.5; outbox retention not enforced; in-app deny vs link cancel undocumented. |
| Existing certified behavior | 06 §7.5 step 5 requires a signed cancel link; no endpoint or page is named; RBX-003 does not list one. |
| Proposed behavior | Add POST /api/v1/approvals/cancel-link {token} → 204 (RBX-003, public) to the 08 index and the RBX-003 register, and a public SPA page /approvals/cancel that cancels only after an explicit confirmation. Condition: outbox_event rows that bind a link to its request are retained at least as long as the break-glass window (break_glass_delay × 3). Veto semantics: a PENDING custodian or single-Founder break-glass request can be denied in the app by any eligible Founder, and cancelled by any notified party through the link; an APPROVED request awaiting its delay can be cancelled only through the link. |
| Reason | Makes the certified veto of 06 §7.5 usable. |
| Code behavior at this commit | Endpoint, page, token binding and events implemented; OpenAPI now documents 204 (RR-A09 fixed). The outbox retention condition is not enforced by code (IR-A10, staging gate). |
| Security | 256-bit HMAC token, only the hash stored, single use, sibling links invalidated, uniform 400. |
| Data impact | None. |
| API impact | One public endpoint. |
| UI impact | New page. |
| Compatibility | Additive. |
| Rollback | No functional rollback: removing the endpoint makes 06 §7.5 step 5 unimplementable, so the certified design would be violated. A defect is forward-fixed; the release as a whole rolls back only within the rollback floor (runbook §2). |
| Tests | `api/tests/integration/test_founder_governance.py::test_G12_cancel_link_by_notified_party`<br>`app/e2e/access.e2e.mjs (break-glass cancel link from the email)` |
| Owner decision requested | Approve the endpoint, the veto semantics and the retention condition. |
| Staging evidence | Staging check that outbox retention ≥ break-glass window (IR-A10). |
| Production evidence | Retention configuration evidence. |
| Approval readiness | Wording complete; submit after IR-A10 has a configuration check or an accepted operational control. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
