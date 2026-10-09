# ESSENTIAL-1.1 operations owner sheet

**Record:** [`essential-1.1-promise-matrix.json`](../../../../api/veda/modules/estimator/approved/essential-1.1-promise-matrix.json), version 1, SHA-256 `ed3b14e0afadecfbb350d022f3bbd028407f7b3f790ff4ec85f0aacf53bbcb3b`. 54 visible promises.

**Status: every promise is BLOCKED and every owner is UNASSIGNED.** For staging activation, every promise must be
`OPERATIONALLY_CONFIRMED` with a named accountable person, a named backup and a confirmation date. A promise is
`REMOVED` only if it is also taken off the page, which the tests enforce. SALES_CONFIRMED and OWNER_CONFIRMED do not
satisfy activation. A promise without a practical verification path is never confirmed: it is rewritten or removed.

Operations records each confirmation in the JSON row through a reviewed pull request: `status`, `accountable_owner`,
`backup_owner`, `confirmed_on`, and any check it changes. The proposed checks for each promise are in the rendered
[matrix](../specifications/essential-1.1-promise-matrix.md).

| Promise | Responsible role | Accountable person | Backup person | Procurement | Receipt | Execution | Installation | Handover | Warranty documents | Exception path | Confirmation date | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `spec.structure` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.board` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.doors` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.surface` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.edges` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.soft_close` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.hardware` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.handles` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.accessories` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.decorative` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.ceiling` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.lighting` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.painting` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.electrical` | Designer (quotation mapping); project manager (procurement to handover) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `spec.package` | Sales lead (wording); designer (quotation) | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `lead` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `availability` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `luxury` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `rooms_sub` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `package_subtitle` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `includes` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `gst` | Finance | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `markers` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `why_range` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `build_note` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `rooms_note` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `materials_fallback` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `included_badge` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `package_text` | Project manager | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `package_components` | Project manager | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `package_other` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `allowance_text` | Designer | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `allowance_notes` | Designer | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `allowance_examples` | Designer | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `manufacturer_warranty` | Project manager | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `service_support` | Customer care | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `service_note` | Customer care | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `compare` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `supplied` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `assumptions_summary` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `next_steps` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `callback` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `consultation` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `refine_intro` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `consent` | Data protection lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `engine_disclaimer` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `engine_assumptions` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `card_exclusions` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `card_client_scope` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `room_inclusions` | Designer | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `approved_examples` | Sales lead | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `gst_line` | Finance | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `basis` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
| `fallbacks` | Product owner | &nbsp; | &nbsp; | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | &nbsp; | BLOCKED |
