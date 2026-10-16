# Project execution delivery: owner decisions (PEX-D01, PEX-D02)

A new register, separate from PLB-OD-01…13, CPP-D01…06 and PCM-D01/D02 (none of which this workstream changes). Only
what the code cannot decide is here. The record is `api/veda/modules/project/fixtures/delivery-policy.json`; both slots
are null. While a slot is null, the code fails closed for that operation only; everything else works.

| Slot | Exact question | Affected operation | Safe default while undecided | Impact while undecided |
|---|---|---|---|---|
| PEX-D01 | May customers, in the Customer Project Portal, (a) report an issue on their project and (b) confirm receipt of a handover summary? Each part is answered separately. | `POST /public/portal/properties/{id}/projects/{id}/reports`; `POST …/handover/acknowledge` | Both refused (`OWNER_DECISION_REQUIRED`); the portal offers neither | Staff record a customer's report on their behalf (`POST /projects/{id}/customer-reports`); the handover needs the reference of the signed handover form, as before |
| PEX-D02 | Must the commercial position meet a condition before handover: NONE, NO_AMOUNT_DUE (a payment schedule exists and nothing requested from the customer is unpaid), or FULLY_PAID (nothing outstanding)? | The moves to READY_FOR_HANDOVER and HANDED_OVER (structural gate `COMMERCIAL_CONDITION`) | Refused (`OWNER_DECISION_REQUIRED`); the position is shown to staff for information | No project can reach handover readiness. In practice nothing changes today: both moves are HIGH-risk and already refused while PLB-OD-01…03 are undecided |

Unless PEX-D02 is NONE, the condition also fails closed when Project Commercials is off, when the project's quotation
chain has no commercial record, when the record does not verify, and (NO_AMOUNT_DUE) when the schedule is missing or
needs revision.

Not new decisions (existing slots, unchanged): customer-visible documents and photographs in the portal and in the
handover package (CPP-D04); rework of a completed stage (PLB-OD-12); customer-promised dates (PLB-OD-13); required QC
categories and who may mark one not applicable (PLB-OD-08); handover evidence (PLB-OD-09).

A decision is recorded by a reviewed change to the record. A record marked SYNTHETIC is refused outside tests.
