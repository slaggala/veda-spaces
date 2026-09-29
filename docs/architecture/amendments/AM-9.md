# AM-9: proposed amendment to 06 §7.5

> **Status: PROPOSED, NOT APPROVED.** This document proposes a change to the certified architecture (baseline `778aa8fdd918da48340319696ada3ff673e9fb8e`). It does not modify the certified documents and has no effect until the decision owner approves it.

| Field | Value |
|---|---|
| Amendment ID | AM-9 |
| Related finding | IR-A11 |
| Related deviation | — |
| Amends | 06 §7.5 |
| Existing certified behavior | Any notified party can cancel a break-glass request through its link. |
| Proposed behavior | Owner decision required: a hostile sole Founder can cancel custodian break-glass repeatedly. Options: accept, cap cancellations per window, or require the custodians' re-request to be uncancellable by the target. |
| Reason | Architecture residual. |
| Security impact | Availability of recovery vs. veto. |
| Data impact | None. |
| API impact | Possibly none. |
| UI impact | None. |
| Compatibility impact | — |
| Tests | — |
| Rollback | n/a |
| Decision owner | Architecture Owner |
| Status | **PROPOSED, NOT APPROVED** |
