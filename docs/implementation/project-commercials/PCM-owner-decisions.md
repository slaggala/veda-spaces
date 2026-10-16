# Project Commercials: owner decisions (PCM-D01, PCM-D02)

A new register, separate from PLB-OD-01…13, CPP-D01…06 and the OI-MTQ rows (none of which this workstream changes).
Only what the code cannot decide is here. While a slot is open the code fails closed for that one capability.

| Slot | Decision | Why the code cannot decide | While undecided |
|---|---|---|---|
| PCM-D01 | Invoice issuer particulars: whether a Veda Spaces invoice is a GST tax invoice; the issuer's legal name, address, GSTIN, SAC code; the invoice series (calendar or financial year); whether a cancelled tax invoice needs a credit note | Legal and tax facts the repository does not hold (no GSTIN, legal entity or address exists anywhere in it) | Invoices can be drafted and previewed by staff; issuing is refused (`OWNER_DECISION_REQUIRED`). Schedules, payment requests, payments, receipts and the portal work. Recorded in `api/veda/modules/commercials/fixtures/commercials-policy.json` (`InvoiceParticulars`). |
| PCM-D02 | Staging enablement of `VEDA_PROJECT_COMMERCIALS_ENABLED` (an enablement record and the staging wiring, as CPP-D01) | A deployment decision | Off everywhere; every staff route answers 404 and the portal shows no commercial data. Production refuses the flag at configuration. |

Engineering choices recorded instead of asked (see the [design](PCM-design.md)): the record is opened explicitly;
instalments split the accepted value by the frozen milestone shares; allocation is a waterfall in schedule order;
receipts are issued with the payment; reversal is four-eyes; FOUNDER and SALES_MANAGER hold the codes; email goes to
the primary customer only and says only that a document is in the portal; erasure follows the existing commercial
policy (redact text and re-seal documents, keep amounts, delete nothing).
