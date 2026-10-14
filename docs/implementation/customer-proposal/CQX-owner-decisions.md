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

## 3. Blockers outside the two policy files

| Code | Blocker | Why it is not decided here |
|---|---|---|
| CQX-B05 | Customer-directed notifications (proposal shared, revised, nearing expiry, decision confirmation) | No approved channel (email/WhatsApp) or approved customer copy exists; staff send the link themselves |
| CQX-B06 | Reference images on the proposal page | Needs catalogue V3 media activation (media_rights UNDECIDED in staging) and a reviewed, path-scoped workspace `img-src` change for `/proposal` |
| CQX-B07 | The lead's pipeline status on a digital acceptance | B4 does not move a lead to WON on a staff-recorded acceptance either; the hand-off event and lead activity are emitted, the status stays a staff action |
| CQX-B08 | Link lifetime | Engineering bound 1–30 days chosen by staff per link; the owner may set another bound |
| CQX-B09 | Housekeeping schedule and reminder window (3 days) | Operational; scheduled by the staging enablement record |
| CQX-B10 | Legal status of a digital acceptance | Not a contract signature; the page says so. Any e-signature or contract treatment needs legal review and an approved vendor (out of scope) |

## 4. Production

Production refuses every CQX flag at API start. A production decision would need, at least: every row above, the staging
validation of the enablement record, legal review of the customer-facing text, and a production enablement record.
