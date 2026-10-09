# Estimator V2: governance decision sheets

These sheets were finalised in the final pre-activation closure. The decisions themselves are recorded in the reviewed
JSON records packaged with the API (`api/veda/modules/estimator/approved/`), which the activation gate reads.

| Decision | Sheet | Record |
|---|---|---|
| Sales: the ten decisions | [ESSENTIAL-1.1-SALES-DECISION-SHEET.md](../activation/ESSENTIAL-1.1-SALES-DECISION-SHEET.md) | `essential-1.1-sales-decisions.json` |
| Operations: named accountable and backup owners, and verification, for every visible promise | [ESSENTIAL-1.1-OPERATIONS-OWNER-SHEET.md](../activation/ESSENTIAL-1.1-OPERATIONS-OWNER-SHEET.md) | `essential-1.1-promise-matrix.json` |
| Owner: approval of the complete record (digests, scope, identity) | [ESSENTIAL-1.1-OWNER-APPROVAL-RECORD.md](../activation/ESSENTIAL-1.1-OWNER-APPROVAL-RECORD.md) | `essential-1.1-approval.json` |
| Owner: retention of the validation recordings and code list | Approval record, scope notes; validation plan §4 (30 days after the final synthesis) | — |

Nothing is decided until a named person records it through a reviewed pull request. `veda estimator activation-check`
lists what is still open.
