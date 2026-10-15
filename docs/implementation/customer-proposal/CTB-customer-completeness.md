# CQX customer completeness and trust baseline (CTB)

Instruction `VEDA-SPACES-CQX-CUSTOMER-COMPLETENESS-AND-TRUST-BASELINE` (2026-10-15), decision log 36. One branch
(`feature/cqx-customer-completeness`), one umbrella pull request. It follows the coverage-gap review, which found that
the Customer Quotation Experience lacked customer **content and fields**, not architecture.

A mature competitor quotation was used only as a completeness benchmark. Nothing of it is copied: no wording, layout,
claims, warranty durations, payment terms, policies, statistics, legal language or branding. Everything a customer sees
comes from Veda Spaces-controlled content, and where the owner has not approved that content the page says
**"to be confirmed by Veda Spaces"**.

## 1. What a customer can now answer, and from where

| Question | Answered by | While the owner content is missing |
|---|---|---|
| Who is my Veda contact? Who do I contact if there is a problem? | Summary: "Your Veda Spaces contact" (quotation contact chosen per version); "Other ways to reach Veda Spaces" (support contacts, escalation); "Need help after handover?" (service contact) | "Contact details to be confirmed" |
| What exactly am I buying? What is included? | Rooms (frozen lines); "What's included" (rooms plus approved project inclusions) | Rooms always shown; project inclusions to be confirmed |
| What size is each item? | Each line: verified sizes (width, height, run, area…) | "Dimension to be confirmed" for an assumed or missing size |
| Which materials and hardware am I getting? | "Materials and hardware" (approved specification grouped into materials and hardware) and each line's specification | "Specification to be confirmed" |
| What is excluded? | "What is not included" (OI-MTQ-09 exclusions and scope exclusions) | To be confirmed |
| What must I arrange? Is my site ready? What happens before installation? | "What you arrange" and "Before we start", each item with its status in words | To be confirmed |
| What is optional? | Optional items (unchanged) | — |
| When and how much do I pay? | Price and payment: milestones with their share, trigger and amount; payment-safety statement | "Payment plan to be confirmed", "How to pay will be confirmed" |
| What warranty applies, and what is excluded? How do I request service? | "Warranty and service": manufacturer-backed warranty kept apart from Veda Spaces' service support, warranty exclusions, service guidance, care | To be confirmed |
| What happens if site-dependent work is discovered? | "Site-dependent work": why, and the approval rule (agreed as a variation first) | To be confirmed |
| What happens after I approve, and at handover? | "What happens after you approve": stages (durations only where approved) and "At handover" | To be confirmed |

## 2. Implementation

- **OI-MTQ-18 customer information pack** (`api/veda/modules/mtq_commercial/customer_pack.py`): a new slot in the
  commercial-policy register, **null**. Sections: contacts (QUOTATION, SUPPORT, SERVICE; business channels confirmed
  by the owner; phone or e-mail), support escalation, project inclusions, client responsibilities (closed categories,
  default status REQUIRED / NOT_REQUIRED / TO_BE_CONFIRMED), site readiness (closed categories), site-dependent work
  (intro, approval rule, categories), manufacturer-warranty note, warranty exclusions, service guidance, handover, care,
  next steps (stage order fixed; optional approved duration), payment safety. It is not an issuance blocker.
- **Copy rules** (a safety net; the owner's review of every text stays the control): free text refuses money (currency
  words and symbols, grouped or long figures, percentages), durations and time promises in figures or words ("3 days",
  "ten years", "45d", "same-day", "next day", "within a week"), e-mail and phone outside contact fields, links, web
  addresses and QR codes, bank, IFSC, UPI or card details, and unsupported claims ("lifetime", "guaranteed",
  "100 %", "free service", superlatives). Contact e-mails refuse free-mail domains and, when the pack lists
  `email_domains`, must use one of them; a contact's display name is a desk or role name, or a staff name the person
  agreed to publish.
- **Per-version choices** (migration `0206_customer_completeness`, expand-only: `quotation.customer_inputs`): the
  quotation contact and each responsibility and readiness status, set on a draft through the existing PATCH, validated
  against the pack frozen in the version's terms (`CUSTOMER_PACK_NOT_DECIDED` when none). Staff panel: a Customer
  information form, read-only once the version leaves draft.
- **Frozen document** (format 2, template `mtq-quotation-html/3`): line dimensions (CTB-02), milestone amounts
  (CTB-09), and the customer information block. The pack is copied into the terms snapshot when the version is
  drafted and frozen at issue; a later pack change never changes an issued version (test-proved).
- **Dimensions** follow quotation line → estimate line → BOQ line → its resolved measurement inputs and quantity basis.
  Only MEASURED, DERIVED or STAFF (recorded with a reason) values are shown; an ASSUMED input, or a size input the basis
  needs that the measurement did not give, makes the line "dimension to be confirmed". A line whose quantity staff
  overrode in the BOQ shows **no** size, only "dimension to be confirmed" (its measured inputs may no longer describe the
  priced quantity). Counts (drawers, points) stay quantities. Nothing is recalculated in CQX.
- **Milestone amounts**: the frozen total split by the approved shares in whole paise; leftover paise go to the largest
  remainders (earlier milestone first), so the amounts always add up to the total exactly (2,000 random cases tested).
  A variation carries no amounts; a document issued before template 3 shows the shares only.
- **Materials and hardware** (CTB-03): the approved specification's categories with their hardware category, grouped
  data-driven (a category naming a hardware category is hardware). A brand is shown only as the specification's own
  approved examples with its equivalence rule.
- **Customer page** (CTB IA): summary (overview, contact, next steps) → rooms → included / not / you arrange /
  site-dependent work → materials and hardware → price and payment → optional items → before we start → warranty and
  service → terms → questions and changes → decision → what happens after you approve. Secondary detail is collapsed
  (opened for print). Each acknowledgement sits beside what it is about (same ids, buttons and semantics).
- **Trust checklist** (CTB-18, `customer_proposal/trust.py`): sixteen customer questions, ANSWERED or
  TO_BE_CONFIRMED with what is missing, returned with the staff proposal preview and shown in the staff panel. It never
  blocks synthetic viewing; real customers need `customer_ready`.

## 3. Compatibility, rollback, erasure

- Templates 1 and 2 render byte for byte as before (golden digests from the PR #95 code). A document issued with
  template 2 keeps rendering, and its page shows the new sections as to be confirmed (never filled from today's pack).
- Rollback across this release is **roll-forward only** once any quotation is issued with template 3
  ([api-runbooks §2.4](../../operations/api-runbooks.md)); the compatibility test pins version 3.
- Lead erasure redacts the customer's name, subject and cover note and re-seals with template 3; business contacts and
  the information block stay (commercial record, not customer data).

## 4. Flags and production

No new flag: the sections are part of the existing CQX viewing page and the B4 quotation document, behind the existing
flags. Production refuses every CQX flag and the MTQ commercial flags; nothing here enables anything.

## 5. Owner content still required (OI-MTQ-18; see [CQX-owner-decisions.md](CQX-owner-decisions.md) §2a)

Contacts approved for publication; support escalation; project inclusions; customer responsibilities; site-readiness
items; site-dependent-work explanation and approval rule; manufacturer-warranty note and warranty exclusions (legal
review); service guidance; handover expectations; care guidance; next-step stages (and any durations); payment-safety
statement. The existing OI-MTQ-07/08/09/11 decisions (GST, validity, terms and payment milestones, acceptance) and an
approved customer specification remain prerequisites for a complete proposal.

## 6. Independent review and remediation

A fresh-context review of the first complete head found the baseline **certified with merge conditions**:

| # | Finding | Severity | Correction |
|---|---|---|---|
| 1 | A BOQ quantity override left the measured inputs in place, so a line could show a size contradicting its priced quantity; a size input missing from the measurement did not mark the line "to be confirmed" | Medium | Overridden lines show no size ("to be confirmed"); the quantity basis's missing size inputs mark the line "to be confirmed"; integration test through a real BOQ override |
| 2 | Copy rules caught durations and money only in digit forms, and not links, QR codes or percentages | Medium | Words and abbreviations for durations and time promises, grouped and long figures, percentages, links, web addresses and QR codes refused; the docstring states what is enforced and that the owner's review stays the control |
| 3 | A contact's "business channel" was only a self-asserted flag | Low | Free-mail domains refused; optional `email_domains` enforced; display-name and frozen-name handling documented |
| 4 | Template 3 printed milestone amounts without a currency | Low | "amount ₹ …" (before any template-3 document is issued) |
| 5 | Two engineering sentences read like policy | Low | Removed or made neutral |
| 6 | The edit event recorded only the field name | Low | The event records the stored choices (codes only) |
| 7 | A new version dropped the staff choices | Low | Carried over where the new pack still has the codes |

A focused re-review closed findings 1–7 and found one defect introduced by the remediation: a next-step stage's
`duration` no longer refused money (Medium). It is restored (only the duration rule itself is exempt there) with a test,
and two false positives it noted ("scan the site", "2 m height") and a missing free-mail domain are corrected. The
copy rules remain a safety net: phrasings such as an amount in words still depend on the owner's review.

## 7. Evidence (SYNTHETIC_VALIDATED)

API: `tests/unit/test_customer_pack.py`, `tests/integration/test_cqx_completeness.py` and the updated pricing,
template and compatibility tests; app: `test/proposal.test.ts`, `test/proposal-staff.test.ts`; browser:
`app/e2e/proposal.e2e.mjs` (360, 390, 768 and 1280 px; axe; print; keyboard; nothing-approved state). Full-suite and
CI results are recorded in the pull request.
