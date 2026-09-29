# AM-9: proposed amendment to 06 §7.5

> **Status: PROPOSED, NOT APPROVED.** Baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`; reviewed implementation `6ec2e76f156e963c7363c4ad9ce93d0bccb11f41`; final targeted check review/p0-independent-implementation-review @ 56c20ba992b519daa79aa3802a28343aab8c0b41. This proposal lives outside `docs/architecture/`, changes no certified document, and records no owner decision.

| Field | Value |
|---|---|
| Amendment ID | AM-9 |
| Status | **PROPOSED, NOT APPROVED** |
| Amends | 06 §7.5 |
| Affected requirements | RBAC-021 |
| Related findings | IR-A11, IR-05 |
| Related deviation | None (decision request) |
| Final targeted check classification | INCOMPLETE (no decision; not implemented) — completed as a decision request |
| Certified behavior | Any notified party can cancel a break-glass request through its link. |
| Proposed behavior | Decision request (not implemented). Recommended option R: custodian break-glass requests (the two-custodian path, available only when no Founder is eligible — IR-05) cannot be cancelled by their target; any other notified party, including every notified Founder (P14), can still cancel. Single-Founder requests keep the certified universal veto. Alternatives: (a) accept the residual; (b) cap cancellations per target per 30 days. IR-05 interplay: while any Founder is eligible custodians cannot act, so a hostile eligible Founder is removable only by another Founder; R does not change that (owner-accepted residual). |
| Reason | Architecture residual: availability of recovery against a hostile Founder versus the veto. |
| Implementation at the reviewed SHA and after | Repository-tested behaviour today: every notified party, including the target, can cancel through the link (test_founder_governance.py::test_G12_cancel_link_by_notified_party); custodian requests are refused while a Founder is eligible (test_governance_remediation.py::test_IR05_*). Option R is NOT implemented. |
| Security impact | Recommended option removes the target's veto over its own custodial recovery only. |
| Data impact | None. |
| API impact | cancel-link returns 400 for the target on custodian requests (uniform). |
| UI impact | None. |
| Compatibility impact | Option R changes only who may cancel custodian requests; no data or API shape change. |
| Rollback or forward-fix | Restore the universal veto. |
| Required tests | `api/tests/integration/test_founder_governance.py::test_G12_cancel_link_by_notified_party`<br>`api/tests/integration/test_governance_remediation.py::test_IR05_*`<br>`— (option R tests with its implementation)` |
| Staging evidence | Staging-required: custodian identity rehearsal with two principals and CloudTrail (RR-09, PG-BG), including a cancellation by a notified Founder; if R is chosen, a refused cancellation by the target. |
| Production evidence | Production-required: custodians named (OWNER-INPUT-004), PG-BG passed, the chosen option implemented and tested. |
| Failure behavior | Today: any notified party, including the target, can cancel; the recovery path can be blocked by a hostile target (residual until decided). |
| Owner decision required | Choose R, (a) or (b), and accept the IR-05 residual. |
| Approval readiness | Decision needed before production; not a merge condition. |
| Decision owner | Architecture Owner |
