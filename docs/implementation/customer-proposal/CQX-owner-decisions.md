# Customer Quotation Experience: owner decisions and blockers

Nothing below is decided by this workstream. Each item keeps its customer action disabled (fail closed) until the owner
records it through a reviewed pull request; viewing never depends on any of them beyond B4's own issuance rules.

## 1. Customer-proposal decisions (new): `api/veda/modules/customer_proposal/fixtures/proposal-policy.json`

All four slots are `null`. A SYNTHETIC copy exists only in tests (the loader refuses it anywhere else).

| Code | Decision needed | Shape when recorded | While null |
|---|---|---|---|
| CQX-D01 | How the recipient of a link is verified before a digital decision | `{"method": "LINK_POSSESSION" \| "EMAIL_OTP" \| "SMS_OTP"}` — only LINK_POSSESSION is built; choosing a one-time code keeps decisions blocked until it is built and reviewed | No digital acceptance or decline |
| CQX-D02 | Whether a customer sees a live total recalculated with their optional choices (the optional-item policy) | `{"live_total": true \| false}` | The page says PRICE CONFIRMATION REQUIRED; acceptance with chosen items is blocked |
| CQX-D03 | Which sections must be acknowledged separately before acceptance | `{"required_sections": ["SCOPE", "ASSUMPTIONS", "EXCLUSIONS", "PAYMENT_MILESTONES", "VALIDITY", "WARRANTY", "SERVICE_SUPPORT", "TERMS"]}` (a subset) | Acknowledgements are optional; acceptance blocked |
| CQX-D04 | Which network and device evidence an acceptance keeps, and for how long | `{"record_ip": bool, "record_user_agent": bool, "retention_days": 1..3650}` | No digital decision |

## 2. Commercial decisions the proposal depends on (existing register, `mtq_commercial/fixtures/commercial-policy.json`)

| Code | Effect on the customer experience |
|---|---|
| OI-MTQ-03 / 04 | Scope rules approved; without them B4 does not issue, so nothing can be shared |
| OI-MTQ-05 | Premium/Luxury rates: package comparison can only list packages that were issued (so never without approved rates) |
| OI-MTQ-07 | GST treatment: no final total, B4 does not issue |
| OI-MTQ-08 | Quotation validity: B4 does not issue; digital acceptance blocked |
| OI-MTQ-09 | Terms, payment milestones, warranty, assumptions, exclusions, change-order and cancellation terms. **New optional field** `service_support` (Veda Spaces' own service text, shown apart from warranty); if CQX-D03 requires SERVICE_SUPPORT, it must be recorded |
| OI-MTQ-10 | Unit rates shown to customers: hidden while null (not blocking) |
| OI-MTQ-11 | Acceptance mechanism. **New allowed method** `CUSTOMER_DIGITAL`; digital acceptance needs it listed |
| OI-MTQ-13 | Variation policy: variations are previewed (staff only) but not issued, so a customer never receives one |
| OI-MTQ-15 | 5 BHK and independent-house preparation drivers: B4 does not issue those configurations |

## 2a. Customer information pack (new register row OI-MTQ-18, `mtq_commercial/fixtures/commercial-policy.json`)

Null. While null, every section below shows "to be confirmed by Veda Spaces" (never a default); issuance is not
blocked; real customers need it (with the staff trust checklist complete). Shape and copy rules:
`mtq_commercial/customer_pack.py`; per-version staff choices: the quotation contact and each item's status.

Since decision log 37 the owner may record OI-MTQ-18 as the Customer Promise portal being the source: the sections are
then authored, reviewed, approved and published in the workspace, and quotations freeze the published pack
([CPA implementation record](../customer-promise/CPA-implementation-record.md) §6).

| Section | What the owner records |
|---|---|
| Contacts | Veda Spaces business channels approved for publication (quotation, support, service): name, role, business phone and/or e-mail, hours; never personal contact data |
| Support escalation | The escalation route a customer can use |
| Project inclusions | Project-level inclusions (e.g. installation) that Veda Spaces confirms for every proposal |
| Customer responsibilities | What a customer arranges (appliance models and sizes, access, power, water, permissions, readiness), each with a default status |
| Site readiness | What must be ready before installation (flooring, painting stage, doors, power, water, access, lift, clearance, approvals, dependencies) |
| Site-dependent work | Why some needs show only on site, and the approval rule (priced and agreed as a variation before any work) |
| Manufacturer warranty note, warranty exclusions | How manufacturer-backed warranty is presented, and what it does not cover (legal review) |
| Service guidance | How to request service after handover: channel, what to provide, reference process, escalation (no response-time promise unless approved) |
| Handover, care | Handover expectations (protection, cleaning, joint inspection, snags, evidence) and care guidance |
| Next steps | The stages after acceptance (blueprint terminology); a duration only where the owner approves one |
| Payment safety | Which payment channels Veda Spaces recognises (no account, IFSC, UPI or card details) |

## 3. Blockers outside the two policy files

| Code | Blocker | Why it is not decided here |
|---|---|---|
| CQX-B05 | Customer-directed notifications (proposal shared, revised, nearing expiry, decision confirmation) | No approved channel (email/WhatsApp) or approved customer copy exists; staff send the link themselves |
| CQX-B06 | Reference images on the proposal page | Needs catalogue V3 media activation (media_rights UNDECIDED in staging) and a reviewed, path-scoped workspace `img-src` change for `/proposal` |
| CQX-B07 | The lead's pipeline status on a digital acceptance | B4 does not move a lead to WON on a staff-recorded acceptance either; the hand-off event and lead activity are emitted, the status stays a staff action |
| CQX-B08 | Link lifetime | Engineering bound 1–30 days chosen by staff per link; the owner may set another bound |
| CQX-B09 | Housekeeping schedule and reminder window (3 days) | Operational; scheduled by the staging enablement record |
| CQX-B11 | Sharing a question/change-request conversation across links (a rotated link, a newer version's link, co-owners) | No shared-recipient policy exists; requests are visible only through the link that sent them (N4) |
| CQX-B12 | Retention period of acceptance network/device evidence, and its enforcement (N7) | CQX-D04 records a period but no job enforces it; acceptance stays blocked until it is enforced or decided otherwise |
| CQX-B10 | Legal status of a digital acceptance | Not a contract signature; the page says so. Any e-signature or contract treatment needs legal review and an approved vendor (out of scope) |

## 3a. Engineering findings that gate enablement (not owner decisions; CQX-security-model §4)

| Finding | Gates | Does not gate |
|---|---|---|
| N7 (acceptance-evidence retention not enforced; CQX-B12) | Acceptance, real customers, production | Viewing, interaction |
| N9 (link token in `sessionStorage` on the workspace origin) | Real customers, production | Synthetic staging viewing, interaction and acceptance testing |
| N10 (proposal image policy) | Images (they stay off) | Viewing without images |
| N8 (no monitored alarm behind an integrity refusal) | Real customers, production | Synthetic staging |

## 4. Production

Production refuses every CQX flag at API start. A production decision would need, at least: every row above, the staging
validation of the enablement record, legal review of the customer-facing text, and a production enablement record.
