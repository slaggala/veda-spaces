# Estimator V2: governance decision sheets (sales and operations)

**Instruction:** `VEDA-SPACES-ESTIMATOR-V2-VALIDATION-AND-GOVERNANCE-EXECUTION`, Track B.

**Status: no decision recorded.** These sheets are for the people who decide. Nothing on them is approved until a
named person fills it in. The decisions are then entered into
[`essential-1.1-promise-matrix.json`](../specifications/essential-1.1-promise-matrix.json) through a reviewed pull request:
- set `status` to `SALES_CONFIRMED`, `OPERATIONALLY_CONFIRMED`, `OWNER_CONFIRMED` or `REMOVED`;
- set `accountable_owner` to a person's name and role;
- adjust any chain field the decision changes.

**Before activation, no visible promise may remain PROPOSED, UNASSIGNED or BLOCKED.**
`veda estimator activation-check` lists what is still open, and `activate-spec` refuses on staging while anything is.

## Sheet 1: Sales decisions

The evidence and recommendation for each item are in [ESSENTIAL-1.1-SALES-DECISIONS.md](../ESSENTIAL-1.1-SALES-DECISIONS.md).
A "Change" decision needs a new specification version (ESSENTIAL-1.2) and then re-approval of its digest.

| # | Decision | Recommended | Decision (Approve / Change to …) | Decided by (name, role) | Date |
|---|---|---|---|---|---|
| 1 | Wet-area material for bathroom vanity units | Approve only if the same branded plywood and block board are used; otherwise change to "Approved board structure" | | | |
| 2 | Wet-area material for utility units | As item 1 | | | |
| 3 | Pooja-unit board and shutter material | Approve (standard doors block board with laminate; CNC and veneer stay decorative) | | | |
| 4 | Shutter exceptions | List the exceptions; remove them from the block-board promise | | | |
| 5 | TV-unit and wall-panelling material promise | Approve the TV panel (laminate on plywood); keep the feature wall as a final selection | | | |
| 6 | TV-unit soft-close-hardware promise | Approve if every TV box and storage has soft-close hinges; otherwise drop the TV-unit lines from soft-close | | | |
| 7 | Kitchen-accessory wording | Approve | | | |
| 8 | Approved brand and equivalent-material wording | Approve after removing any brand not currently bought; equivalents approved by the designer and accepted by the customer | | | |
| 9 | Package-picker wording | Approve | | | |
| 10 | "Designer will contact you within one working day" | Approve only with response-time monitoring; otherwise remove the time commitment | | | |

## Sheet 2: Operations owners and verification, every visible promise

For each promise, operations names **one accountable person** and confirms that the verification path is practical
today. The path covers procurement, material receipt, execution, installation, handover evidence, warranty documents
and exception approval, as set out in the matrix and in
[ESSENTIAL-1.1-OPERATIONS-CONFIRMATION.md](../ESSENTIAL-1.1-OPERATIONS-CONFIRMATION.md). If any step has no practical
path, the promise is rewritten as a final-selection statement or marked `REMOVED`, never confirmed.
Rows waiting on owner wording only need the owner's approval and a named owner.

| Matrix row | Waiting for | Responsible role | Named accountable owner | Path practical? (Y/N, what differs) | New status | Date |
|---|---|---|---|---|---|---|
| `spec.structure` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.board` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.doors` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.surface` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.edges` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.soft_close` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.hardware` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.handles` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.accessories` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.decorative` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.ceiling` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.lighting` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.painting` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.electrical` | sales confirmation of the wording and material; operations confirmation of each check and a named owner | Designer (quotation mapping); project manager (procurement to handover) | | | | |
| `spec.package` | sales confirmation | Sales lead (wording); designer (quotation) | | | | |
| `lead` | owner approval of the wording | Product owner | | | | |
| `availability` | owner approval of the 'coming soon' wording | Product owner | | | | |
| `luxury` | owner-confirmed wording; owner to be named | Sales lead | | | | |
| `rooms_sub` | owner approval of the wording | Product owner | | | | |
| `package_subtitle` | sales decision (checklist item 9) | Sales lead | | | | |
| `includes` | owner-confirmed wording; owner to be named | Product owner | | | | |
| `gst` | owner approval of the wording | Finance | | | | |
| `markers` | owner-confirmed wording; owner to be named | Product owner | | | | |
| `why_range` | owner approval of the wording | Product owner | | | | |
| `build_note` | owner approval of the wording | Product owner | | | | |
| `rooms_note` | sales and owner confirmation that every room amount includes installation | Sales lead | | | | |
| `materials_fallback` | owner approval of the wording | Product owner | | | | |
| `included_badge` | owner-confirmed wording; owner to be named | Product owner | | | | |
| `package_text` | owner-confirmed wording; owner to be named | Project manager | | | | |
| `package_components` | operations confirmation of how each component is carried out and checked | Project manager | | | | |
| `package_other` | owner approval of the wording | Product owner | | | | |
| `allowance_text` | owner-confirmed wording; owner to be named | Designer | | | | |
| `allowance_notes` | owner approval of the wording | Designer | | | | |
| `allowance_examples` | owner-confirmed wording; owner to be named | Designer | | | | |
| `manufacturer_warranty` | operations: warranty documents for each product filed and handed over | Project manager | | | | |
| `service_support` | owner-confirmed wording; owner to be named | Customer care | | | | |
| `service_note` | owner approval of the wording | Customer care | | | | |
| `compare` | owner approval of the wording | Product owner | | | | |
| `supplied` | owner approval of the wording | Sales lead | | | | |
| `assumptions_summary` | owner approval of the wording | Product owner | | | | |
| `next_steps` | operations confirmation of the process and owner approval of the wording | Sales lead | | | | |
| `callback` | sales decision (checklist item 10): the one-working-day commitment | Sales lead | | | | |
| `consultation` | sales approval of the wording | Sales lead | | | | |
| `refine_intro` | owner approval of the wording | Product owner | | | | |
| `consent` | owner confirmation of the consent wording | Data protection lead | | | | |
| `engine_disclaimer` | owner-confirmed wording; owner to be named | Product owner | | | | |
| `engine_assumptions` | owner-confirmed wording; owner to be named | Product owner | | | | |
| `card_exclusions` | owner-confirmed wording; owner to be named | Sales lead | | | | |
| `card_client_scope` | owner-confirmed wording; owner to be named | Sales lead | | | | |

## Sheet 3: Owner approvals

| Approval | Value | Decision | Name | Date |
|---|---|---|---|---|
| ESSENTIAL-1.1 document digest (or the digest of a version changed by sheet 1) | `6f798ef6cd3cea06f491041a4143e35776900107e73e6c953fbed4bd37ad286d` | | | |
| Page wording rows marked "owner approval of the wording" | see sheet 2 | | | |
| Retention rule for validation recordings and the participant code list | 30 days after final synthesis (validation plan §4) | | | |

