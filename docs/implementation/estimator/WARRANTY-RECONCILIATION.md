# Warranty reconciliation: estimator, specification and policy

**Instruction:** `VEDA-SPACES-ESTIMATOR-UX-V2-CUSTOMER-TRUST-FINALIZATION`, Phase 5.

**Rule applied:** the estimator shows no material or hardware duration until the exact product's manufacturer
documentation, the detailed quotation and the policy agree (Phase 5, requirement 6). It shows one duration, Veda Spaces'
own service support, because the published policy states it.

## What the customer sees in UX V2

> **Manufacturer-backed protection.** Approved materials and hardware carry the applicable manufacturer warranty for
> the exact product selected and documented in your final quotation.
>
> **Veda Spaces service support.** Veda Spaces provides one year of applicable workmanship and fitment service support
> from handover, subject to the Warranty, Service & Customer Care Policy. A longer manufacturer warranty is the
> manufacturer's own. It does not extend Veda Spaces workmanship or service support.
>
> View full warranty and exclusions (the policy URL configured for the API, `VEDA_WARRANTY_POLICY_URL`).

The manufacturer sentence is the `warranty_summary` of ESSENTIAL-1.1, so it is versioned and snapshotted with each
estimate. The service sentence is fixed page copy, and a staging-build test ties it to the policy text: "one year of
free service from the project handover date for fitment-related or workmanship issues". The page avoids the word
"free" (the package and allowance rules forbid calling required work free), but the period and scope match the policy.

## Matrix

**Sources:**
- **Policy:** the published Warranty, Service & Customer Care Policy (`/warranty`).
- **Engine:** the warranty texts in the estimate response, which V1 shows.
- **October 2026 and June 2026:** the source quotations' specifications, as reconciled in [Essential Specification v1.0](specifications/ESSENTIAL-SPECIFICATION-v1.0.md). The workbooks stay private and are not reproduced here.

| Item | Policy | Engine (V1 shows) | October 2026 | June 2026 | UX V2 shows | Status |
|---|---|---|---|---|---|---|
| Plywood | Up to 10 years, depending on the plywood selected and the manufacturer's warranty | "Warranty depends on the selected material and the manufacturer's terms" | Sylvan Blu, 30-year manufacturer warranty | Sylvan ply, 10-year | Manufacturer sentence, no duration | **Unresolved.** The two sources conflict (30 against 10), and 30 years exceeds the policy's "up to 10". A duration needs Sylvan's documented terms for the exact product in the quotation, presented as the manufacturer's, never as Veda Spaces' |
| Shutter board (block board, Primo Plus) | Not stated separately. The policy also notes that HDHMR and engineered-board shutters may move | None | Brand stated; period not carried into v1.0 | Brand stated | Manufacturer sentence, no duration | **Unresolved.** No documented period. The quotation must name any non-block-board shutter |
| Hinges | 5 years against manufacturing defects | "Channels and hinges: up to 5 years" | Brand Hettich; a period was stated in the workbook (not reproduced) | Period stated (not reproduced) | Manufacturer sentence, no duration | **Partly resolved.** Policy and engine agree on the period, but the engine says "up to" where the policy states it flatly. Manufacturer documentation for the exact hinge is still needed before V2 shows a period |
| Channels | 5 years against manufacturing defects | As for hinges | Blum (drawers), Nimmi or Hettich (sliding), Ebco or Hettich (folding) | Hettich | Manufacturer sentence, no duration | **Partly resolved**, as for hinges |
| Kitchen tandems | 3 years against manufacturing defects | "Up to 3 years" | Hettich; a period was stated (not reproduced) | Period stated (not reproduced) | Manufacturer sentence, no duration | **Partly resolved**, as for hinges |
| Electrical items | 1 year, or the period the manufacturer documents | "Up to 1 year, or the documented manufacturer period" | Polycab or Finolex wiring; Philips, Wipro, Crompton, Avion lights | Wipro, Philips | Manufacturer sentence, no duration | **Partly resolved**, as for hinges |
| Workmanship | One year of free service from the handover date, for workmanship issues within the completed scope | "One year of free service after handover for applicable workmanship or fitment issues" | — | — | "One year of applicable workmanship and fitment service support from handover, subject to the policy" | **Resolved.** This is Veda Spaces' own policy; a test ties the page to the policy text |
| Fitment service | As for workmanship (fitment-related issues) | As for workmanship | — | — | As for workmanship | **Resolved** |

## Pre-activation closure: what must agree before any material duration is published

A plywood or hardware duration may appear in V2 only when all four of these agree for the exact product:
1. the manufacturer's product certificate or documented warranty terms;
2. Essential Specification 1.1, or the version then active (which today states no duration, and the validator refuses one);
3. the detailed quotation wording;
4. the Warranty, Service & Customer Care Policy.

Until then, V2 shows no material duration. A staging-build test fails if any numeric duration appears in the V2 copy,
or any spelled duration other than the Veda Spaces service sentence. The separation stays as approved:
manufacturer-backed protection applies to the exact selected and documented product, and Veda Spaces workmanship and
fitment support lasts one year from handover, subject to the policy. In the matrix, the `manufacturer_warranty` row
stays BLOCKED until operations confirms that the warranty documents are handed over.

## To close before any material duration is shown

1. For each "partly resolved" row, attach the manufacturer's documented terms for the product named in the quotation
   (model and period). Then decide whether the engine's "up to N years" or the policy's "N years" is the approved
   wording, and align the two.
2. For plywood, either document the exact Sylvan product and its period and show it as the manufacturer's warranty, or
   keep the current sentence. Do not show 30 years while the policy says "up to 10".
3. V1 (the staging control) still shows the engine texts with "up to" periods. They match the policy's periods, and
   V1 stays unchanged during the comparison, as instructed. Decide their wording when the engine texts are reconciled;
   that is a pricing-engine file and is out of scope here.
