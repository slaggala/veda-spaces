# Project Commercials: owner decisions (PCM-D01, PCM-D02)

A new register, separate from PLB-OD-01…13, CPP-D01…06 and the OI-MTQ rows (none of which this workstream changes).
Only what the code cannot decide is here. While a slot is open the code fails closed for that one capability.

| Slot | Decision | Why the code cannot decide | While undecided |
|---|---|---|---|
| PCM-D01 | **Decided 2026-10-16 (decision log 45).** Role ACCOUNTANT operates commercials; invoice particulars come from the business configuration. Was: invoice issuer particulars: whether a Veda Spaces invoice is a GST tax invoice; the issuer's legal name, address, GSTIN, SAC code; the invoice series (calendar or financial year); whether a cancelled tax invoice needs a credit note | Legal and tax facts the repository does not hold (no GSTIN, legal entity or address exists anywhere in it) | Invoices can be drafted and previewed by staff; issuing is refused (`OWNER_DECISION_REQUIRED`). Schedules, payment requests, payments, receipts and the portal work. Recorded in `api/veda/modules/commercials/fixtures/commercials-policy.json` (`InvoiceParticulars`). |
| PCM-D02 | **Decided 2026-10-16 (decision log 45): staging only.** Staging enablement of `VEDA_PROJECT_COMMERCIALS_ENABLED` (an enablement record and the staging wiring, as CPP-D01) | A deployment decision | Production stays refused at configuration. Staging is enabled through the existing mechanism (decision logs 42/43): a reviewed infrastructure change wires the flag to staging-core planned false with a DRAFT enablement record, the owner approves the record, then a reviewed change flips it. Not done in this code change (it needs an infrastructure plan and apply by the owner); until then the flag stays off in staging too. |

Engineering choices recorded instead of asked (see the [design](PCM-design.md)): the record is opened explicitly;
instalments split the accepted value by the frozen milestone shares; allocation is a waterfall in schedule order;
receipts are issued with the payment; reversal is four-eyes; FOUNDER and SALES_MANAGER hold the codes; email goes to
the primary customer only and says only that a document is in the portal; erasure follows the existing commercial
policy (redact text and re-seal documents, keep amounts, delete nothing).

## PCM-D01 as decided (2026-10-16)

- **ACCOUNTANT** (system role, MFA required): every `commercials.*` code at ALL scope, plus the workspace shell's
  self-service codes. No `project.*`, quotation, lead or customer-data code.
- **FOUNDER**: every code (oversight). **SALES_MANAGER**: `commercials.view` only; migration `0211_accountant_role`
  withdrew `schedule.manage`, `payment.record`, `payment.reverse`, `invoice.issue` and `audit.view` (each an audited soft
  delete, and every session's authorisation refreshed). Reversal stays four-eyes.
- **Invoice particulars** are read only from the business configuration (`commercials-policy.json`, slot `PCM-D01`).
  None is configured: the repository holds no legal name, address, GSTIN or SAC code and none is invented. Issuing fails
  closed with `INVOICE_PARTICULARS_NOT_CONFIGURED`, naming the missing fields and what to do; drafts and previews work and
  nothing incomplete reaches a customer. Supplying the particulars is a reviewed change to that record.
