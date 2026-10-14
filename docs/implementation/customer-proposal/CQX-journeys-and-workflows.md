# Customer Quotation Experience: journeys, lifecycles and the audit map

## 1. Customer journey

1. **Receives a link** from their Veda Spaces representative (`https://<app>/proposal#t=<token>`). The token is in the
   fragment: the browser never sends it to a server. On opening, the page moves it into this tab's storage and removes
   it from the address bar.
2. **Overview**: proposal value, rooms, version, validity, earlier versions, next steps, the state (open, replaced by a
   newer version, past validity, accepted, declined) and notices (for example, the link expiring soon).
3. **Room by room**: room cards (included and optional counts, subtotal, an approved reference image or a named
   placeholder), then each room's lines with quantity, finish and amount; each line's approved material specification
   (pinned to the version issued) and labelled reference images.
4. **Optional items**: for each, *Add to my proposal*, *Not for me* or *I would like to discuss it*. The choice is sent
   to Veda Spaces; it changes nothing by itself. The total with the choices is shown only if the owner allows it
   (CQX-D02); otherwise "PRICE CONFIRMATION REQUIRED".
5. **Price and payment**: room subtotals, GST, total, payment milestones (approved shares and triggers), validity,
   other packages shared with the same person.
6. **Terms**: each section as frozen; a section without approved content reads "to be confirmed by Veda Spaces".
   Required sections (CQX-D03) are acknowledged one by one.
7. **What changed**: for a revised version, the differences from the version issued before.
8. **Questions and changes**: structured questions and change requests, with answers and the revision that answered them.
9. **Decision**: accept (after an explicit confirmation of the exact version, total and choices) or decline. Available
   only when every owner decision it needs is recorded; otherwise the page says it is not available yet.
10. **After a decision**: the proposal shows the outcome and a record reference; later changes come as a variation.

Refusals (link not valid, revoked, expired, superseded, document integrity failure, offline) each have one safe message.

## 2. Staff journey (workspace → property → Scope and quotation → Customer proposal)

1. Issue the quotation (B4, unchanged). 2. **Create a link** for a recipient kind (primary customer, co-owner, family
member, other), with an expiry of 1–30 days; copy it (shown once) and send it yourself. 3. Watch **opened** state and
views. 4. **Preview** exactly what the customer sees. 5. Review **customer choices**, **questions and change
requests**: answer (under review, needs clarification, declined, resolved) or, after revising scope and price through
B2-B4, **link the new version or variation** that answers a request. 6. Share the revised version (earlier links to the
same recipient kind retire automatically). 7. Read the **customer decision** and its verified evidence, or what still
blocks digital acceptance. 8. Revoke or replace a link at any time.

## 3. Access-link lifecycle

```
CREATED ──first view──► ACTIVE ──(own expiry)──► EXPIRED
   │                      │
   └──────────────────────┴──► REVOKED  reason: STAFF_REVOKED | ROTATED | SUPERSEDED | LEAD_ERASED | LEAD_CLOSED
```

One live link per version and recipient kind. Rotation issues a new token and revokes the old one (ROTATED). Sharing a
newer version to the same recipient kind revokes the older version's link (SUPERSEDED: the old link says a newer
proposal was shared). The quotation's own state is separate: a live link to a version that later expires, is accepted
or declined still opens and shows that state without actions.

## 4. Optional-item workflow

`NOT_SELECTED → SELECTED | DESELECTED | REQUESTED_FOR_DISCUSSION` (any to any, by the customer, while the proposal is
open). Only priced optional lines can be SELECTED. Repeating a state is a no-op. Each change: an event, FULL audit, a
staff notification. The quotation never changes. At acceptance exactly the SELECTED lines join the effective accepted
baseline (B4), and a later variation keeps them without adding them again.

## 5. Change-request workflow

```
OPEN ─► UNDER_REVIEW ─► NEEDS_CLARIFICATION
  └───────┴──────────────► ACCEPTED_FOR_REVISION (only by linking a newer version or variation) ─► RESOLVED
  └───────┴──────────────► DECLINED | RESOLVED (final)
```

Customer text never becomes scope. Staff revise requirements and scope themselves (B2), price (B3), create the new
version or variation (B4), then link it to the request; the customer sees "answered in version n".

## 6. Acceptance evidence model (`quotation_acceptance_evidence`, one row per version)

| Field | Content |
|---|---|
| decision, method, verification_method | ACCEPTED/DECLINED, CUSTOMER_DIGITAL, the CQX-D01 method |
| quotation_number, variation_no, version_no | the exact version |
| snapshot_sha256, issued_html_sha256 | the frozen document and HTML digests the decision is bound to |
| displayed_total_minor | the total the page displayed (server-derived and compared) |
| selected_line_refs | the optional items chosen (customer references) |
| acknowledgements | each acknowledged section with its digest and time |
| decided_on, request_trace, client_key_sha256 | time, request id, idempotency-key digest |
| network | only what CQX-D04 permits (erased with the lead) |
| evidence, evidence_sha256 | the canonical evidence document (also: baseline digest, policy versions, grant, recipient kind) and its digest; staff reads verify it |

## 7. Audit map

| Action | Rows written | Audit | Event / outbox |
|---|---|---|---|
| Share | proposal_access_grant (+ older versions' grants revoked SUPERSEDED) | FULL (parent quotation) | SHARED; `proposal.shared` (+ `proposal.revised_available`) |
| Rotate / revoke | grant(s) | FULL | ROTATED / REVOKED; `proposal.access_revoked` |
| View | grant counters; event at most every 15 minutes | FULL | VIEWED; `proposal.viewed` (first view) |
| Expiry (housekeeping) | grant status | FULL | EXPIRED |
| Choice | customer_optional_selection | FULL | SELECTION_CHANGED; `proposal.optional_selected` |
| Question / change request | customer_proposal_request | FULL (text registered PII) | QUESTION_SUBMITTED / CHANGE_REQUESTED; `proposal.question_submitted` / `proposal.change_requested` |
| Staff answer / link | request | FULL | REQUEST_UPDATED / REQUEST_LINKED |
| Acknowledgement | quotation_acknowledgement | FULL | ACKNOWLEDGED |
| Decision | quotation (B4 decision fields, accepted baseline), quotation_event, quotation_acceptance_evidence, lead_activity | FULL (evidence document excluded, its digest kept) | ACCEPTED / DECLINED; `quotation.accepted` (booking hand-off) / `quotation.declined` |
| Nearing expiry (housekeeping) | outbox | — | `proposal.nearing_expiry` |
| Lead erasure | grants revoked; texts erased; network evidence removed | FULL (payloads rewritten) | REVOKED (LEAD_ERASED) |
