# MTQ dependency matrix

**Status:** reviewer aid, derived from [MTQ-BLUEPRINT.md](MTQ-BLUEPRINT.md) §16–§18. Nothing here is implemented.

Legend: **Hard** = the block cannot be built without it · **Gate** = the block can be built but not validated or activated without it · **Soft** = additive later; the schema already allows it.

| # | Dependency | Kind | Blocks | Current state (2026-10-13) | Blueprint ref | Owner input |
|---|---|---|---|---|---|---|
| 1 | **Attachments module (ATT)**: polymorphic `attachment` table, S3 storage with pre-signed URLs, malware scan on upload | Hard | B1 (wall photos, sketches, floor plans), B4 (quotation PDF) | Roadmap outline only ([10-future-roadmap.md](../../architecture/10-future-roadmap.md) ATT); the catalogue media scanner path exists and is reusable | §1.3, §4.1, §16 B1, §17 | — |
| 2 | **Catalogue V3 administration active** so `space_template`, `scope_rule`, `quantity_formula` and `pricing.finish_rates` can be authored, reviewed and released | Hard | B2, B3, B4 (governed copy) | `catalog_admin_enabled` is **off** in production; V3 activation governance incomplete (AD-4/6/8 open) | §5.2, §8.1, §8.2, §9.2, §17 | — |
| 3 | **Premium and Luxury rate-card decisions** for staff pricing, plus per-finish variant rates | Hard for B3 pricing of those tiers; Soft for Essential-only | B3 | Public: Premium hidden until validated (ADR-012 D1), Luxury consultation-only (D2). No Premium/Luxury rates loaded for staff use | §9.1, §9.2 | OI-MTQ-05 |
| 4 | **Discount authority**: limits per role, four-eyes threshold, `permission_limit` table (roadmap P3) | Hard | B3 adjustments, B4 approval | No limits mechanism exists; `admin_approval_request` exists for dual control | §4.2 `cost_estimate_adjustment`, §15.2 | OI-MTQ-06 |
| 5 | **GST treatment** on quotations | Hard | B3 totals, B4 document | Estimator shows GST separately at 18 % (ADR-012 §3.3); quotation treatment undecided | §9.4 | OI-MTQ-07 |
| 6 | **Quotation terms** (versioned text, legal review) | Hard | B4 send | No terms document in the repo | §4.3 `terms_version`, §10.1 | OI-MTQ-09 |
| 7 | **Payment milestones** (schedule percentages and triggers) | Hard | B4 document; Soft for PROJ linkage | No payment schedule exists in the repo | §4.3 `payment_schedule` | OI-MTQ-09 |
| 8 | **Customer assumptions and exclusions**: standard exclusion list, assumption disclosure wording | Hard | B4 document | ADR-012 D4/D9 define the public estimator's exclusions and allowance; quotation list undecided | §10.1 items 7 and 9, §4.3 `quotation_exclusion` | OI-MTQ-09, OI-MTQ-10 |
| 9 | Validity, reminders, expiry | Hard | B4 lifecycle | Estimator uses 30 days | §10.2, §12.2 | OI-MTQ-08 |
| 10 | Customer acceptance mechanism and legal standing | Gate | B4 portal activation | Undecided | §10.3 | OI-MTQ-11 |
| 11 | Measurement tolerance, templates, rules, rounding | Gate / Hard | B1, B2 | Proposals only | §5, §6, §8 | OI-MTQ-01…04 |
| 12 | **PostgreSQL release gate** (pgvector, concurrency for batch sync at scale) | Hard for B5; Soft for B1–B4 | B5 | SQLite authoritative; PostgreSQL is a release gate (ADR-008) | §16 B5, §19 | — |
| 13 | CUST and PROJ modules (customer link, execution actuals from close-out) | Soft | B4 knowledge actuals, B5 | Roadmap only; `property.customer_id` and `knowledge_execution_actual` are additive | §4.1, §4.4, §17 | — |
| 14 | Historical quotation set (E6) with recorded measurements for replay | Gate | B2, B3 validation | [E6-historical-validation.md](../../implementation/estimator/E6-historical-validation.md) exists for the estimator; measurement detail per quotation to be confirmed | §16 B2, B3 | — |
| 15 | New roles SURVEYOR, DESIGNER, ESTIMATOR, SALES_MANAGER and the MTQ permission registry | Hard | B1 onward | Existing RBAC tables and registry pattern; seeds are additive | §15 | — |

## Sequencing implied

```
ATT ──► B1 ──► B2 ──► B3 ──► B4 ──► B5
                ▲       ▲      ▲      ▲
   Catalogue V3 admin ──┘      │      │
   OI-05/06/07 ────────────────┘      │
   OI-08/09/10/11 ────────────────────┘
   PostgreSQL gate, OI-12 ────────────────┘
```
