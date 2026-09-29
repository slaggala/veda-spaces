# AM-9: proposed amendment to 06 §7.5

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It lives outside `docs/architecture/`, does not modify the certified documents, and has no effect until the decision owner approves it. Nothing here claims owner approval or implementation authorization.

| Field | Value |
|---|---|
| Amendment ID | AM-9 |
| Amends | 06 §7.5 |
| Related findings | IR-A11, IR-05 |
| Related deviation | — |
| Targeted re-review assessment | Incomplete: options without a decision; option 3 misses the notified-Founder case (P14); ignores IR-05 interplay. |
| Existing certified behavior | Any notified party can cancel a break-glass request through its link. |
| Proposed behavior | Recommended option: custodian break-glass requests (the full two-custodian path, available only when no Founder is eligible — IR-05) cannot be cancelled by their target; they can be cancelled by any other notified party, including every notified Founder (P14). Single-Founder requests keep the certified veto for every notified party. Alternatives for the owner: (a) accept the residual (a hostile sole Founder can cancel recovery indefinitely); (b) cap cancellations per target per 30 days. Interplay with IR-05: while an eligible Founder exists, custodians cannot act, so a hostile *eligible* Founder can only be removed by another Founder; this proposal does not change that and it remains an owner-accepted residual. |
| Reason | Architecture residual: availability of recovery against a hostile Founder versus the veto. |
| Code behavior at this commit | Not implemented: current code lets every notified party, including the target, cancel. |
| Security | Recommended option removes the target's veto over its own custodial recovery only. |
| Data impact | None. |
| API impact | cancel-link returns 400 for the target on custodian requests (uniform). |
| UI impact | None. |
| Compatibility | Behavioural change to cancellation only. |
| Rollback | Restore the universal veto. |
| Tests | `— (to be written with the implementation)` |
| Owner decision requested | Choose the recommended option, (a) or (b). |
| Staging evidence | None. |
| Production evidence | None. |
| Approval readiness | Decision needed before implementation. |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
