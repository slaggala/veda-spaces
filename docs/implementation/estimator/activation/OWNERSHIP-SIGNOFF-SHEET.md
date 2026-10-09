# Ownership sign-off sheet (sales and operations)

**Status: blank, for human completion.** No decision, person or confirmation has been filled in by anyone else.

**Related sheets:**
- the [suggested ownership structure](OWNERSHIP-STRUCTURE.md), which places each of the 54 promises in a group;
- the [sales decision sheet](ESSENTIAL-1.1-SALES-DECISION-SHEET.md), with the ten decisions;
- the [operations owner sheet](ESSENTIAL-1.1-OPERATIONS-OWNER-SHEET.md), which confirms each promise.

## Activation rule

A customer-facing promise may not be activated while it is `UNASSIGNED`, `PROPOSED`, `BLOCKED`, or `OWNER_CONFIRMED`
(or `SALES_CONFIRMED`) without operational verification. **Only `OPERATIONALLY_CONFIRMED`, with a named accountable
owner, a named backup and a confirmation date, is sufficient for the Part 2 activation approval.** The activation
gate enforces this from the reviewed promise matrix and refuses otherwise.

## Group sign-off

One row per group. The accountable owner and the backup must be different people. The verification method is the
practical check the group actually performs (for example: "goods-received check of board stamp against the PO,
photographed").

| Group | Promises | Accountable owner | Backup owner | Decision date | Verification method | Exception approver | Confirmation status |
|---|---|---|---|---|---|---|---|
| Sales | 26 | | | | | | BLOCKED |
| Procurement | 13 | | | | | | BLOCKED |
| Projects | 6 | | | | | | BLOCKED |
| Customer Support | 6 | | | | | | BLOCKED |
| Site Execution | 3 | | | | | | BLOCKED |

**Confirmation status** moves to `OPERATIONALLY_CONFIRMED` for a group only when every promise in the group is
confirmed in the matrix. A promise with no practical verification is rewritten as a final-selection statement, or
marked `REMOVED` and taken off the page; it is never confirmed.

## Sales decisions (ten items)

| # | Decision | Owner decision (APPROVE / CHANGE) | Owner name | Decision date |
|---|---|---|---|---|
| S1 | Bathroom vanity wet-area material | | | |
| S2 | Utility wet-area material | | | |
| S3 | Pooja-unit board and shutters | | | |
| S4 | Shutter exceptions | | | |
| S5 | TV-unit and wall-panelling material | | | |
| S6 | Living-room soft-close TV-unit hardware | | | |
| S7 | Kitchen-accessory wording | | | |
| S8 | Brand and approved-equivalent wording | | | |
| S9 | Package-picker wording | | | |
| S10 | One-working-day designer callback | | | |

The evidence and the recommendation for each are in the sales decision sheet. A CHANGE creates a new specification
version, which needs a new Part 1 approval of its digest.

## Recording

Completed sheets are entered into the reviewed records (`api/veda/modules/estimator/approved/`) through a reviewed pull
request. `veda estimator activation-check` then shows what remains open. Only after every row is
`OPERATIONALLY_CONFIRMED` can the owner sign Part 2, with the fresh digests `activation-check` prints.
