# Essential Specification 1.1: operations confirmation package

**Instruction:** `VEDA-SPACES-ESTIMATOR-V2-PRE-ACTIVATION-CLOSURE`.

**Rule:** a promise moves to `OPERATIONALLY_CONFIRMED` only when operations names an accountable person and confirms that
each verification step below is how Veda Spaces works today, with the evidence it produces. If any step has no
practical verification path, the promise is not confirmed. It is rewritten as a final-selection statement, or marked
`REMOVED` and taken off the page. Nothing here is confirmed yet.

The proposed steps for each promise are recorded in the matrix
([JSON](../../../api/veda/modules/estimator/approved/essential-1.1-promise-matrix.json), [rendered](specifications/essential-1.1-promise-matrix.md)).
This page is the sign-off sheet.

## The verification path every material promise needs

| Step | What is checked | Evidence kept |
|---|---|---|
| Procurement | The purchase order and supplier invoice name the brand, grade or model and size stated in the quotation | PO and invoice, filed against the project |
| Warehouse or site receipt | On receipt, the board stamp, grade, thickness or model is checked against the PO | Goods-received note, photograph of the stamp or label |
| Site execution | Before fabrication or fitting, the site supervisor checks the material against the quotation | Supervisor checklist, photographs |
| Installation | The installed item is the specified one and works (for example soft closing) | Installation checklist |
| Handover | The handover record lists the material or product with the invoice reference | Signed handover record |
| Warranty documents | The manufacturer's warranty card or terms for the exact product are handed over where the manufacturer issues them | Copy filed with the handover record |
| Exception approval | Any substitution or deviation is recorded as a quotation revision approved by the designer and accepted by the customer before procurement | Approved quotation revision |

## Sign-off sheet

Operations fills in the named owner, then confirms (yes or no, with what differs) for each step.

| Matrix row | Promise | Procurement | Receipt | Execution | Installation | Handover | Warranty documents | Exception | Named owner | Confirmed (date) |
|---|---|---|---|---|---|---|---|---|---|---|
| `spec.structure` | Branded plywood bodies (Sylvan Blu baseline, 18/9/12 mm) | | | | | | | | | |
| `spec.board` | Approved board for pooja units and arches | | | | | | | | | |
| `spec.doors` | Block-board shutters (Primo Plus baseline, 18 to 19 mm) | | | | | | | | | |
| `spec.surface` | 1.0 mm outer and 0.8 mm inner laminate, approved brands, customer shades | | | | | | | | | |
| `spec.edges` | 2 mm and 0.8 mm edge banding | | | | | | | | | |
| `spec.soft_close` | Soft-close hinges (kitchen, wardrobes, TV unit), kitchen soft-close drawers | | | | | | | | | |
| `spec.hardware` | Approved hinges and channels; hydraulic bed fitting | | | | | | | | | |
| `spec.handles` | Handles from the standard range | | | | | | | | | |
| `spec.accessories` | Kitchen accessories as chosen, within the allowance | | | | | | | | | |
| `spec.decorative` | Decorative items specified at design (final-selection statement) | | | | | | | | | |
| `spec.ceiling` | Gypsum board on Bright 04/06 channels | | | | | | | | | |
| `spec.lighting` | Approved lighting brands and specification | | | | | | | | | |
| `spec.painting` | Premium emulsion, putty and primer where included | | | | | | | | | |
| `spec.electrical` | Branded copper wiring | | | | | | | | | |
| `package_components` | Site and floor protection, plywood or material protection, freight and handling, debris handling, completion deep cleaning, pest-control preparation (each only when priced) | not applicable | not applicable | Supervisor records each activity as done | not applicable | Completion checklist: cleaning and debris | not applicable | Quotation revision | | |
| `manufacturer_warranty` | The manufacturer warranty for the exact documented product | Product named on the PO | Label or model checked | — | — | Product listed at handover | Card or terms handed over | Quotation revision | | |
| `next_steps` | Consultation → site measurement → design and materials confirmed → detailed quotation → scope approved before work | Lead workflow stages | — | Site measurement recorded | — | — | — | — | | |
| `callback` | Call within one working day (if sales keeps the commitment) | Response time tracked in the lead workflow | — | — | — | — | — | — | | |
| `rooms_note` | Room amounts include installation | Quotation lines include installation | — | Installation crew scheduled for every quoted item | — | — | — | — | | |

The page-wording rows (`lead`, `why_range`, `build_note`, `compare` and the others) need the owner's approval of the
wording, not operations. They are listed in the matrix with `blocked_on: owner approval of the wording`.
