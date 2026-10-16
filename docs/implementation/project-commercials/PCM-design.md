# Project Commercials: implementation map, design and design review (discovery 2026-10-16)

Baseline: main after PR #101, #103 and #104 (the PR #104 merge). Project Lifecycle off; PLB-OD-01…13 null; Customer Project
Portal off and being deployed separately. The workstream adds the commercial source of truth that starts at an accepted
quotation: the baseline, the payment schedule, payments, receipts, invoices, the outstanding balance, and their
customer-safe projection in the existing portal.

## 1. Implementation map: existing source of truth → commercial capability → staff → customer → portal

| Concern | Existing source of truth (proved by reading the code) | Commercial capability | Staff experience | Customer-safe projection | Portal |
|---|---|---|---|---|---|
| Customer | `lead` (CRM): name, email, assigned consultant; erasure `crm/leads/erasure.py` | Account hangs off the lead (`lead_id` on every row, scope and erasure follow it) | Lead scope (`mtq.scope`) | Name on documents as at issue | Reached only through `portal_access` |
| Property | `property` (MTQ B1) | Account names the property | Reference, configuration, city | Same fields the quotation shows | Property page |
| Commercial commitment | `quotation` (B4): ISSUED freezes `snapshot` + `issued_html` with digests; ACCEPTED freezes `accepted_total_minor` and `accepted_baseline` with its digest (`record_decision`, the one decision path for staff and CQX) | **Baseline** = an ACCEPTED quotation version, referenced with its digests; never recomputed | Open from an accepted quotation | Total project value | Summary |
| Change after acceptance | Variations (`mtq_commercial/variations.py`): own quotation rows (`-V01`…), accepted through the same path; "accepted value of the job = base accepted total + every accepted variation's total" | **Adjustment** = an accepted variation, appended to the baseline in the acceptance transaction (`ACCEPTANCE_HOOKS`) | Baseline lineage; schedule flagged for revision | Value includes accepted variations | Summary |
| Payment terms | OI-MTQ-09 `payment_milestones` (label, `share_bp` summing to 10 000, trigger), frozen in `quotation.terms`; `customer_pack.milestone_amounts` (largest remainder, reconciles exactly) | Initial schedule = the frozen milestones of the accepted base, amounts split from the accepted value with the same function | Revise with a reason | Instalments, amounts, "when" (the trigger), due date only if staff set one | Schedule |
| Money | Integer paise (`*_minor`, BigInteger), `currency` CHAR(3) default INR, `customer_pack.money` formatting | Same: integers only, INR only (CHECK) | Amounts entered as rupees, parsed to paise exactly | Server-formatted strings | Never computed in the browser |
| Tax | OI-MTQ-07 single-rate GST per line, frozen in the quotation (`tax_minor`, optional lines' `tax_minor`) | GST of the baseline = frozen quotation GST (+ chosen optional items' GST); apportioned to instalments by largest remainder, never recomputed from a rate | Shown per instalment | "Includes GST of …" | Documents |
| Numbering | `kernel/sequences.next_number` (UPDATE … RETURNING under the row lock; YEAR period); prefixes VS-L, VS-P (property **and** project: pre-existing overlap), VS-M, VS-Q | New sequences INVOICE `VS-I-` and RECEIPT `VS-R-` (padding 5: `VS-I-2026-00001`, 15 characters) | Numbers on documents | Same | Same |
| Audit | `AuditedBase` + `audit_registry` FULL; immutable timelines via `ms.create_immutability_guards` (`project_event`, `portal_event`) | All tables FULL; `commercial_event` immutable (codes, ids, amounts only) | History (permission-gated) | None | None |
| RBAC | `platform/rbac/registry.py`, module `permissions.py` + MATRIX, OWN via lead scope; roles FOUNDER, ADMIN, SALES, DESIGNER, SURVEYOR, ESTIMATOR, SALES_MANAGER (MFA) | Six `commercials.*` codes | Least privilege (§7) | Customer holds no permission | Portal session |
| Concurrency | SQLite `BEGIN IMMEDIATE` per write unit of work; PostgreSQL `SELECT … FOR UPDATE` (`project.access.lock`); re-read under the lock | Account row lock for every financial write | — | — | — |
| Idempotency | In-memory `Idempotency-Key` store (per process, 24 h); CQX acceptance stores key and request digests in its evidence row | **Database-backed** keys on payments (required) and on reversals | Keys generated per dialog | — | — |
| Outbox / email | `kernel/outbox.enqueue` in the business transaction; worker; `@handler`; versioned Jinja templates | Invoice issued, receipt issued → "a document is in your portal" (no amounts, no link to pay) | — | — | Link to the property page |
| Customer portal | `portal_account`/`portal_access`, `X-Veda-Portal`, `projection.property_view`, RBX-010, flag `VEDA_CUSTOMER_PORTAL_ENABLED` | Customer-safe projection (`commercials.customer`) consumed by the portal projection | — | Allow-listed fields only | "Payments" section, Action Required, document pages |
| Project Lifecycle | `project` + `project_baseline` (flag off; a project exists only once booked; PLB-OD-* null) | **Not a dependency.** The commercial baseline has the same shape (accepted chain) but exists without a project | — | — | — |
| Erasure | Redact free text, retain commercial record; frozen quotation documents redacted and re-sealed (`rendering.redact`, SNAPSHOT_REDACTED) | Same policy: redact personal free text and the customer name in frozen documents (re-sealed, previous digests kept in the event), retain amounts, numbers, dates; nothing deleted; account closed to writes | — | — | — |
| Feature flags | `config.Settings` + `validate_environment` production refusals + `/auth/me` features | `VEDA_PROJECT_COMMERCIALS_ENABLED`, off, refused in production | Nav item behind the feature | Commercial data only with both flags on | — |
| Existing payments/invoices | **None** (only the frozen milestone table in the quotation document; roadmap FIN outline: invoice, payment, allocation, immutable after issue, corrections as credit notes) | New | — | — | The frozen milestone table stays as the quotation's own wording |

## 2. Domain

Module `veda.modules.commercials`, migration `0210_project_commercials`, eight tables.

```
accepted base quotation ──open──► commercial_account (one per quotation chain)
                                     │
                                     ├── commercial_baseline  (append-only: base, then each accepted variation; digest chain)
                                     ├── payment_schedule ──► payment_instalment   (revisions; one CURRENT)
                                     ├── commercial_payment ──► commercial_receipt  (frozen document, issued with the payment)
                                     │          └── commercial_payment_reversal     (the correction; the payment is never changed)
                                     ├── commercial_invoice   (DRAFT → ISSUED (frozen) → CANCELLED; one live per instalment)
                                     └── commercial_event     (immutable timeline)
```

### 2.1 Baseline

`commercial_account` is opened explicitly by staff from an ACCEPTED base quotation (as a project is booked: nothing is
created by acceptance alone). Opening records the whole accepted chain at that moment (base, then any accepted
variations) as `commercial_baseline` rows. Each row references one ACCEPTED quotation version: id, number, variation and
version, `snapshot_sha256`, `accepted_baseline_sha256`, `accepted_total_minor`, the accepted GST, the cumulative value
and cumulative GST, and `baseline_sha256` over that reference plus the previous row's digest. Rows are immutable
(database triggers). A later variation acceptance appends the next row in the acceptance transaction (an
`ACCEPTANCE_HOOKS` listener, as the Project Lifecycle does); a listener failure refuses the acceptance, so the account
can never silently miss an accepted change.

Accepted GST of a version = frozen `tax_minor` + the GST of the optional lines the customer chose (`QuotationLine.tax_minor`,
frozen with the version). If the version has no recorded GST the baseline's GST is unknown (null), never computed.

The authoritative **current commercial value** is the latest baseline row's cumulative value. Historical values never
change: quotations are immutable once accepted, and the row stores the accepted total it was built from. Verification
(`baseline.problems`) re-checks each row's digest chain and the referenced quotation's digests, and reports any accepted
version of the chain that is not recorded (fail closed: problems are shown to staff and block new financial documents).

### 2.2 Schedule

A schedule revision is a set of instalments whose amounts add up **exactly** to the current value (validated under the
account lock; a revision is the only way to change instalments). Revision 1 is built at opening from the base
quotation's frozen milestones: amounts = `milestone_amounts(value, shares)` (the quotation's own function: floors, then
the remaining paise to the largest remainders, earlier first), labels and "when" text copied from the frozen terms. If
the quotation froze no milestones, no schedule exists until staff create one.

When an accepted variation changes the value, the current schedule no longer adds up: the position shows
`REVISION_REQUIRED` with the exact difference, and staff revise (with a reason). Payments are never touched by a
revision. A revision may not drop or change an instalment that carries an ISSUED invoice; identical instalments
(same label and amount) carry over with their request and due date, and the invoice follows them.

Each instalment: position, label ("what this payment is for"), when (the contractual trigger text), amount, its GST
share (apportioned, null if unknown), share of the original milestones (null after a revision), and a payment request
(`requested_on`, optional `due_on`). No due date is ever invented: an instalment without a request is UPCOMING ("when:
before production"), a request without a date is DUE ("due now, no date set").

### 2.3 Payments, allocation and status

A payment is staff's record that money reached Veda Spaces outside the system (bank transfer, UPI, cheque, cash, other).
It is **not** a bank or gateway confirmation, and the UI says so. Fields: amount (> 0, ≤ outstanding), received date
(not in the future), method, external reference (optional; unique per method among live payments), customer-safe note,
staff-only note, recorder and time (audit contract), a digest over its financial facts, and the client key and request
digests (database idempotency). A payment row is never updated; a correction is a `commercial_payment_reversal` row
(reason code, note, actor, time; one per payment; never by the person who recorded the payment).

Allocation is derived, never stored: valid payments are applied to the current schedule in order (the earliest
instalment with a balance first). Instalment status is computed from those facts:

| Status | Rule |
|---|---|
| PAID | applied = amount |
| OVERDUE | balance > 0 and a due date before today |
| PARTIALLY_PAID | 0 < applied < amount |
| DUE | requested, balance > 0 |
| UPCOMING | not requested, balance > 0 |

### 2.4 Outstanding balance: one calculation

`commercials.position.compute(session, account)` is the only place money is summed:

```
value       = latest baseline cumulative value          (accepted base + accepted variations)
paid        = Σ amount of payments without a reversal
outstanding = max(value − paid, 0)
credit      = max(paid − value, 0)                      (only if a variation reduced the value; shown, never negative)
unscheduled = value − schedule total                    (≠ 0 → REVISION_REQUIRED)
```

Staff API, portal projection, invoice snapshot and receipt snapshot all read this object; the browser formats nothing.

### 2.5 Invoices

An invoice requests one instalment of the current schedule. DRAFT (staff only, previewable, discardable) → ISSUED
(number allocated under the sequence row lock, customer document frozen with its SHA-256 and HTML, the instalment marked
requested) → CANCELLED (reason; the frozen document stays and is shown as cancelled). One live (DRAFT or ISSUED) invoice
per instalment. Issued invoices never change except by lead erasure (redact and re-seal, previous digests recorded).
The document states the instalment, its amount and the GST it includes (from the baseline, apportioned), what has
been paid towards it and what is due, the contractual reference (quotation and version), and the project position at
issue. Invoices do not change the balance; payments do.

Issuing is gated by owner decision **PCM-D01** (invoice issuer particulars): whether the document is a GST tax invoice
and the issuer's legal name, address, GSTIN, SAC and invoice series. Nothing in the repository holds them. Until
recorded, invoices can be drafted and previewed but not issued; payments, receipts, schedules and the portal work.

### 2.6 Receipts

Recording a payment issues its receipt in the same transaction (number, frozen document with digest and HTML): amount,
date, method, reference, what it was applied to and the position after it, all derived from the payment and the position.
A receipt has no editable amount. When its payment is reversed the receipt stays and is shown as cancelled with the
customer-safe reason.

### 2.7 Customer projection and portal

`commercials.customer.for_property` returns, only for an opened account on a property the portal already authorised:
summary (total value, paid, outstanding, next payment), schedule, payment history (amount, date, method label, customer
note, reference, receipt), issued invoices and receipts (status), and attention items for DUE/OVERDUE instalments. It is
built from an allow-list; staff notes, actor identities, digests other than the document's own, internal states and
anything of the estimate are never read into it. Documents are fetched by id through the same access check as the
property (404 for anything else) and downloaded with the portal session header (never a public URL).

## 3. Design review (before implementation)

| Risk | Finding | Resolution in the design |
|---|---|---|
| Duplicate source of truth | `project_baseline` already records an accepted chain | It exists only for a booked project behind the PLB flag; payments must not depend on PLB. The commercial baseline references the same immutable quotation rows and copies only the frozen accepted total; both use the same acceptance hook, so they cannot diverge. Value is never computed elsewhere. |
| Mutable financial history | Payments, receipts, invoices | No update path for a payment; reversal is a separate row; receipts and issued invoices frozen with digests; events immutable at the database. |
| Incorrect quotation linkage | A DRAFT/ISSUED version or a variation opened as a base | Opening accepts only an ACCEPTED base version of a live lead, verifies its frozen digests, one account per chain (unique). |
| Frozen milestone amounts use the total without optional items | Splitting the issued document's amounts would not add up to the accepted value | Instalments split the **accepted** value by the frozen shares; the issued document is not changed and keeps its own wording. |
| Floating point | — | Integers (paise) end to end; rupee input parsed as a string; no float in Python or TypeScript money paths. |
| Broken tax semantics | Recomputing GST from a rate | Never: GST is the frozen quotation GST, apportioned by largest remainder; unknown stays unknown. |
| Duplicate payments | Double click, retry, two staff recording one transfer | Required Idempotency-Key stored in the row (unique per account) with the request digest; same method + reference refused while live; all under the account lock. |
| Race conditions | Two payments exceeding the balance; two issues of one invoice | Account row lock and re-read for every financial write; sequence allocation under its own row lock; tests with the paused-request harness on both engines. |
| Invoice-number collisions | VS-P overlap precedent | New prefixes VS-I/VS-R checked against every seeded prefix; unique indexes; the VS-P overlap is recorded, not changed. |
| Customer data leakage | Portal projection | Allow-list projection; reached only through `portal_access`; documents by id re-check access; tests for A/B isolation, guessed ids and field suppression. |
| Overly broad RBAC | — | Seven codes, defaults FOUNDER and SALES_MANAGER only; reversal four-eyes. |
| Accidental PLB dependency | — | No import of PLB tables; the portal's project steps are unchanged. |
| Unsafe deletion | Erasure | No delete anywhere; erasure redacts text and re-seals; drafts are soft-deleted only. |
| Portal exposing internal data | — | No estimate, BOQ, rate, margin, staff note or actor identity is read by the customer projection. |
| Unnecessary complexity | Allocation table, credit notes, payment requests table | Allocation derived (waterfall); cancellation instead of credit notes (decision PCM-D01 may add a credit-note form); the request lives on the instalment. |

Owner decisions are kept to two (PCM-D01 invoice particulars, PCM-D02 staging enablement). Everything else is an
engineering choice recorded here.
