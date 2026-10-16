# Project Commercials: implementation record (decision log 42)

Branch `feature/project-commercials`, built on main after PR #104. Design, implementation map and the pre-implementation
design review: [PCM-design.md](PCM-design.md). Owner decisions: [PCM-owner-decisions.md](PCM-owner-decisions.md).

## What exists now

| Capability | Where |
|---|---|
| Commercial record of an accepted chain, opened by staff | `commercials/baseline.py` (`open_account`), `POST /api/v1/commercials` |
| Baseline lineage (base + accepted variations), immutable, digest-chained | `commercial_baseline`; `ACCEPTANCE_HOOKS` → `baseline.on_quotation_accepted`; `baseline.sync` under the lock |
| One position calculation | `commercials/position.py` (`compute`, `figures`) |
| Payment schedule revisions, payment requests | `commercials/schedule.py` |
| Recorded payments, receipts, reversals | `commercials/payments.py`, `documents.py` |
| Invoices (draft, issue, cancel, abandon) | `commercials/invoices.py`, `documents.py` |
| Customer projection | `commercials/customer.py`, consumed by `portal/projection.py` and the portal routes |
| Staff API | `commercials/routes.py` (16 routes, OpenAPI snapshot) |
| Staff UI | `/commercials`, `/commercials/:id` (`app/src/modules/commercials`) |
| Portal UI | Payments section, home-card balance, Action Required `PAYMENT_DUE`, `/portal/invoices/:id`, `/portal/receipts/:id` |
| Email | `commercials.invoice_issued`, `commercials.receipt_issued` → template `commercial_document` (no amounts, no way to pay) |
| Erasure | `commercials/erasure.py` in the lead cascade |
| Migration | `0210_project_commercials` (expand-only; triggers on baseline and event; sequences INVOICE `VS-I-`, RECEIPT `VS-R-`) |

## Money

Integer paise end to end (BigInteger columns, strict-integer request fields refusing floats, strings and booleans;
rupee input parsed from text in the browser). Splits use the largest-remainder method of the quotation's milestone
amounts and always reconcile: instalments add up exactly to the value (enforced at every revision); instalment GST adds
up exactly to the baseline GST. GST is never computed from a rate here.

## API

Staff (bearer, `commercials.*`, lead scope; 404 unless the flag is on):

| Route | Permission |
|---|---|
| `GET /commercials`, `GET /commercials/{id}` | `commercials.view` |
| `GET /commercials/candidates`, `POST /commercials`, `POST /commercials/{id}/schedule`, `POST /commercials/{id}/instalments/{iid}/request` | `commercials.schedule.manage` |
| `POST /commercials/{id}/payments` (Idempotency-Key required) | `commercials.payment.record` |
| `POST /commercials/{id}/payments/{pid}/reverse` | `commercials.payment.reverse` |
| `POST /commercials/{id}/invoices`, `POST /commercial-invoices/{id}/issue`, `/cancel`, `/abandon` | `commercials.invoice.issue` |
| `GET /commercial-invoices/{id}`, `GET /commercial-receipts/{id}` | `commercials.view` |
| `GET /commercials/{id}/history` | `commercials.audit.view` |

Customer (RBX-010, portal session): `GET /public/portal/invoices/{id}`, `GET /public/portal/receipts/{id}`, and the
`commercials` block of `GET /public/portal/properties/{id}`.

## RBAC

FOUNDER and SALES_MANAGER: all six codes (SALES_MANAGER already releases the quotations these records start from and
is the only working role with mandatory MFA). No other role holds any. A consultant or an accounts person is granted a
code individually at OWN or ALL scope. Reversal is never by the recorder.

## Concurrency and idempotency

Every financial write takes the account row lock (PostgreSQL `FOR UPDATE`; SQLite `BEGIN IMMEDIATE`) and re-reads.
Payments: required Idempotency-Key stored as a digest with the request digest (same → the same payment; different →
refused), duplicate method + reference refused, overpayment refused under the lock. Invoice issue: one number from the
sequence row lock, If-Match on the invoice, one live invoice per instalment (unique index). Tests race each case on
both engines with the paused-request harness.

## Test evidence

See the PR description for the run of record. Suites: `test_commercials_baseline`, `_payments`, `_invoices`,
`_portal`, `_security`, `_concurrency`, `_erasure` (dual engine), `tests/unit/test_commercials_money.py`,
`app/test/commercials.test.ts`, `app/e2e/commercials.e2e.mjs` (123 checks: journeys, axe, 360/390/768/1280 px).

## Independent review (fresh context, before merge)

No merge blocker or HIGH finding. Every finding and how it was handled (regression tests in
`test_commercials_review_fixes.py`):

| Finding | Handling |
|---|---|
| M1 (Medium): a property could hold two commercial records; the portal showed only the newest, hiding the other's requests | Fixed: one record per property (unique index, `PROPERTY_HAS_COMMERCIAL_RECORD`, not offered as a candidate). A change of agreed work is a variation of the record. Tested. |
| M2 (Medium): after a reducing variation, a stale instalment could be shown and invoiced as due while nothing was outstanding | Fixed: while the schedule does not add up to the value, nothing is asked (no due lines, no Action Required, no next payment) and requests and invoices are refused (`SCHEDULE_REVISION_REQUIRED`) until staff revise; payments are still recorded, bounded by the outstanding. Tested. |
| M3 (Medium): date rules used the UTC date (a payment received "today" refused 00:00-05:30 IST) | Fixed: every business date (received, due, overdue, document dates) is the Asia/Kolkata date, as the number sequences. Tested at 02:00 IST. |
| M4 (Medium): PCM-D01 could label a document "Tax invoice" without the fields a GST tax invoice needs | Fixed: only "Invoice" is accepted; a tax-invoice form (customer GSTIN and address, place of supply, rate, CGST/SGST/IGST) is a later code change with PCM-D01. Tested. |
| LOW 1: cancelling an invoice left its due date on the instalment | Fixed: the request stays, the cancelled invoice's date is dropped. Tested. |
| LOW 2: a request could change a due date an issued invoice states | Fixed: refused (`INVOICE_FIXES_DUE_DATE`) until the invoice is cancelled. Tested. |
| LOW 3: carrying over two identical instalments could pick the uninvoiced one | Fixed: the invoiced one is matched first. Tested. |
| LOW 4: one reference could be recorded under two methods | Fixed: a reference is unique among live payments whatever the method. Tested. |
| LOW 5: an accepted variation not yet in the baseline hid every staff control | Fixed: that problem no longer locks the page; the next write records the variation (`sync`). |
| LOW 6: request and draft did not check integrity | Fixed: both fail closed like payment, issue and revision. Reversal deliberately stays available as a correction. |
| LOW 7: erasure kept a plain digest over the erased text | Fixed: erasure replaces the request digest. Tested. |
| Info: the commercials policy override was not reset between tests | Fixed in `tests/conftest.py`. |
| Info: every portal relationship sees payments (emails go only to the primary customer) | Accepted: it follows the portal's access model (who is given access is CPP-D03). |
| Info: allocation is a waterfall; an invoice row's instalment pointer moves when carried; `commercial_payment` has no database trigger | Accepted by design (design §2.3, §2.2); payments are sealed by `record_sha256`, and erasure needs to redact their text. |

## Limitations

- No online payment, by design; refunds of a credit balance are not recorded (shown as a credit, to be handled offline).
- Invoices cannot be issued until PCM-D01; the series resets by calendar year (`VS-I-2026-00001`), unique as a string;
  a financial-year series is part of PCM-D01.
- Payment-due reminders are not sent (no scheduler is enabled and none was invented).
- A schedule revision cannot drop an instalment that carries an issued invoice; cancel the invoice first.

## Found during this work (outside this change)

- PROPERTY and PROJECT numbers share the prefix `VS-P-` (recorded by CPP). Untouched: invoice and receipt numbers use
  their own prefixes.
- The OpenAPI generator names request bodies by class name; five pairs of classes already share a name (`DeleteIn`,
  `NoteIn`, `ReasonIn`, `DecisionIn`, `GrantIn`), so the committed contract describes some routes with another route's
  body. A guard test keeps the set from growing; fixing the five is a separate change.
- `tests/unit/test_deploy_scanner.py::test_entrypoint_propagates_a_clean_clamd_exit` failed once under load locally and
  passed on rerun (timing; no deploy file changed here).
