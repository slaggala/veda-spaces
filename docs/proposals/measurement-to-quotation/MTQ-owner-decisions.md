# MTQ owner-decision register

**Status:** twelve inputs defined, **none resolved**. Decisions are recorded here only as the owner gives them, verbatim, with date and source instruction. Recommendations are the author's and carry no authority.
**Companion:** [MTQ-BLUEPRINT.md §18](MTQ-BLUEPRINT.md#18-owner-inputs-register) · [MTQ-dependency-matrix.md](MTQ-dependency-matrix.md) · [MTQ-implementation-entry-gate.md](MTQ-implementation-entry-gate.md)

| ID | Input | Needed before | Blueprint ref | Author recommendation | Owner decision | Decided on | Source |
|---|---|---|---|---|---|---|---|
| OI-MTQ-01 | Measurement tolerance for B1 validation (agreement between app capture and the current method) | B1 validation gate | §6.2, §16 B1 | ±1 % floor area per space; ±25 mm per wall length | — | — | — |
| OI-MTQ-02 | Space templates and survey checklists per property type (confirm or amend the proposed `SPACE_TYPE` list and template defaults) | B1 implementation | §5.1, §5.2 | Accept the proposed list; author templates for apartment, villa and office first | — | — | — |
| OI-MTQ-03 | Scope rule content per space category; which items are "always" versus "recommended" | B2 implementation | §8.1, §16 B2 | Start from the ADR-012 §3.1 room/line table; everything "recommended" until calibrated | — | — | — |
| OI-MTQ-04 | Quantity rounding, wastage factors and clearances per formula kind | B2 implementation | §8.2 | SFT to 0.1 per line, RFT to 0.1, clearances 50 mm; wastage only where the workbook applies it today | — | — | — |
| OI-MTQ-05 | Premium and Luxury rate sheets for staff pricing, and per-finish variant rates (laminate, acrylic, veneer, PU) | B3 implementation | §9.1, §9.2, §16 B3 | Load as the next rate-card version; public D1/D2 rules unchanged | — | — | — |
| OI-MTQ-06 | Discount authority limits per role and the four-eyes threshold | B3 implementation | §15.2, §16 B3 | Estimator proposes; Sales Manager approves up to a limit; Founder above it | — | — | — |
| OI-MTQ-07 | GST treatment on quotations (single headline rate versus per-line rates; allocation of discounts) | B3 implementation | §9.4 | Per-line `gst_rate_bp` with pro-rata discount allocation; tax advisor to confirm | — | — | — |
| OI-MTQ-08 | Quotation validity days, reminder cadence, expiry behaviour | B4 implementation | §10.2, §12.2 | 30 days (matches the estimator); reminders at 7 and 2 days before expiry | — | — | — |
| OI-MTQ-09 | Commercial terms text, payment-schedule milestones, warranty summary wording (legal review required) | B4 implementation | §4.3 `quotation.payment_schedule`, §10.1 | Terms as versioned catalogue `copy` records; legal review recorded before activation | — | — | — |
| OI-MTQ-10 | Whether unit rates may ever be shown to customers | B4 implementation | §1.2, §4.3 `show_unit_rates` | Default hidden; Sales Manager may expose per quotation | — | — | — |
| OI-MTQ-11 | Customer acceptance mechanism (portal click, signed copy, or both) and its legal standing | B4 activation | §10.3, §4.3 `quotation_decision` | Portal acceptance recorded with terms version and re-typed quotation number; signed copy optional attachment | — | — | — |
| OI-MTQ-12 | Knowledge-store thresholds and the first AI capabilities to enable | B5 | §16 B5 | ≥ 100 quotations with outcomes; rule-calibration reports first | — | — | — |

## Recording rules

- A decision is entered exactly as the owner states it, with the instruction name and date. Interpretations, if any, are listed separately below the table and marked as the author's.
- A blank decision blocks the block named in "Needed before" at the implementation-entry gate ([MTQ-implementation-entry-gate.md](MTQ-implementation-entry-gate.md)). It does not block independent review of the blueprint.
- Changing a recorded decision creates a new row with a new date; earlier rows are never edited.
