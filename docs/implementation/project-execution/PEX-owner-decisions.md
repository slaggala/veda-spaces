# Project execution delivery: owner decisions (PEX-D01, PEX-D02)

A register separate from PLB-OD-01…13, CPP-D01…06 and PCM-D01/D02. Only what the code cannot decide is here. The record
is `api/veda/modules/project/fixtures/delivery-policy.json`.

**Both decided on 2026-10-16 (decision log 46), record version `PEX-POLICY-1`:**

- **PEX-D01 = YES.** Authorised customers may (a) report an issue on their project and (b) acknowledge the prepared
  handover package in the Customer Project Portal. Nothing else changes: the portal session, property-scoped isolation,
  the Idempotency-Key, the per-session and per-network rate limits and the per-account cap on reports waiting for
  review, the audit trail, staff triage of every report (a report is a customer report, never a verified defect by
  itself) and the acknowledgement bound to the current package's digest.
- **PEX-D02 = commercial obligation gate** (`COMMERCIAL_OBLIGATION_SATISFIED`). Normal handover needs the project's
  commercial obligation satisfied as Project Commercials states it: `commercials.obligation.evaluate` (the record of
  this project's quotation chain verifies, and the one position calculation leaves nothing outstanding after accepted
  variations, reversals and any credit). Project Execution sums no money. There is no exception or override: a
  legitimate exception would need its own explicit, authorised, reasoned and audited mechanism, which no owner policy
  defines, so the gate fails closed (missing record, record that does not verify, Project Commercials off, amount
  outstanding). The earlier conditions (NONE, NO_AMOUNT_DUE, FULLY_PAID) remain only for tests.

The table below is the original register text (what each slot governs and its fail-closed default).

| Slot | Exact question | Affected operation | Safe default while undecided | Impact while undecided |
|---|---|---|---|---|
| PEX-D01 | May customers, in the Customer Project Portal, (a) report an issue on their project and (b) confirm receipt of a handover summary? Each part is answered separately. | `POST /public/portal/properties/{id}/projects/{id}/reports`; `POST …/handover/acknowledge` | Both refused (`OWNER_DECISION_REQUIRED`); the portal offers neither | Staff record a customer's report on their behalf (`POST /projects/{id}/customer-reports`); the handover needs the reference of the signed handover form, as before |
| PEX-D02 | Must the commercial position meet a condition before handover: NONE, NO_AMOUNT_DUE (a payment schedule exists and nothing requested from the customer is unpaid), or FULLY_PAID (nothing outstanding)? | The moves to READY_FOR_HANDOVER and HANDED_OVER (structural gate `COMMERCIAL_CONDITION`) | Refused (`OWNER_DECISION_REQUIRED`); the position is shown to staff for information | No project can reach handover readiness. In practice nothing changes today: both moves are HIGH-risk and already refused while PLB-OD-01…03 are undecided |

Unless PEX-D02 is NONE, the condition also fails closed when Project Commercials is off, when the project's quotation
chain has no commercial record, when the record does not verify, and (NO_AMOUNT_DUE) when the schedule is missing or
needs revision.

Not new decisions (existing slots): customer-visible documents (CPP-D04, decided YES on 2026-10-16: explicit
publication, see the CPP record); rework of a completed stage (PLB-OD-12); customer-promised dates (PLB-OD-13); required QC
categories and who may mark one not applicable (PLB-OD-08); handover evidence (PLB-OD-09).

A decision is recorded by a reviewed change to the record. A record marked SYNTHETIC is refused outside tests.
