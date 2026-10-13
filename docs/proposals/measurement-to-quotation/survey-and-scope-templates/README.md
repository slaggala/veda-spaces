# MTQ survey and scope-template system

**Status:** Documentation only. Operational templates proposed under the published blueprint ([MTQ-BLUEPRINT.md](../MTQ-BLUEPRINT.md), PR #83). No code, no migrations, no schema change, no flag change, no pricing change. Nothing here alters the architecture; everything here is **content** for records the blueprint already defines (`space_template`, `scope_rule`, `quantity_formula`, lookups) and **procedure** for the people who will use them.
**Instruction:** `VEDA-SPACES-MTQ-SURVEY-AND-SCOPE-TEMPLATE-SYSTEM` (2026-10-13).
**Authority:** none until the owner records OI-MTQ-02 (templates and checklists) and OI-MTQ-03 (scope-rule content) in [MTQ-owner-decisions.md](../MTQ-owner-decisions.md). This package is the author's proposed content for those two inputs and is written so that the owner can accept it as-is, amend it, or reject it line by line.

| Document | Purpose | Blueprint records it feeds |
|---|---|---|
| [00-conventions.md](00-conventions.md) | Measurement codes, wall and opening labelling, requiredness levels, recommendation levels, driver vocabulary, line-code status legend | `space_measurement`, `space_wall`, `space_opening` capture contract |
| [01-space-type-templates.md](01-space-type-templates.md) | The fourteen space-type templates: required and optional measurements, mandatory and optional scope recommendations, dependencies, BOQ drivers, estimate drivers, survey checklist | `space_template` (one per type), `scope_rule` groups, `quantity_formula` inputs |
| [02-property-templates.md](02-property-templates.md) | Property-level templates: 2/3/4/5 BHK apartment, duplex, villa, independent house, commercial (office, retail, clinic), custom | `property` + `property_space` tree seeds, project-level requirements, estimate drivers |
| [03-measurement-visit-playbook.md](03-measurement-visit-playbook.md) | What a site engineer must do and capture, in order, before a quotation can be generated; the quotation-readiness gate | `measurement_visit`, `measurement_set` verification rules (§6.2) |
| [04-catalogue-record-content.md](04-catalogue-record-content.md) | The same templates expressed in the blueprint's catalogue-record notation, ready to be keyed into Catalogue V3 once it is active | `space_template`, `scope_rule`, `quantity_formula` records |

## How the pieces fit

```
property template (02) ──seeds──► property_space tree (one row per space, instance_no, level_index, walk order)
                                        │
space-type template (01) ──per space──► survey checklist shown to the surveyor (03 playbook per-space procedure)
                                        │  required / optional measurements → space_measurement, space_wall, space_opening
                                        ▼
                               measurement_set SUBMITTED → VERIFIED (03 §8 readiness gate)
                                        │
space-type template (01) ──per space──► recommended_requirements → requirement rows (PROPOSED / RECOMMENDED)
                                        │  designer confirms with the customer (03 §6 discovery)
                                        ▼
scope-rule groups (01 §"scope", 04) ──► scope_item rows (AUTO_RULE), dimensions DERIVED from tagged walls
                                        │
BOQ drivers (01 §"BOQ drivers") ──────► boq_line via quantity_formula kinds (§8.2)
                                        │
estimate drivers (01, 02) ────────────► cost_estimate lines, project lines by driver, adjustments
```

## What this package does not do

- It does not decide tolerances, rounding, wastage or clearances (OI-MTQ-01, OI-MTQ-04). Where a number is needed to make a template usable, the blueprint's proposed value is used and marked **proposed**.
- It does not load typical dimensions. `typical_dimensions` must come from Veda's past-project medians (ADR-012 D3). Sanity-check ranges are given for verification only and are never pricing defaults.
- It does not add rate-card lines. BOQ drivers that need a line the Essential 1.1 card does not carry are marked **NEW LINE** and are a B3 / OI-MTQ-05 dependency.
- It does not change `SPACE_TYPE`, `REQUIREMENT_TYPE` or `OPENING_TYPE`. Where a template needs a value the blueprint does not list, it is marked **lookup addition proposed** (a lookup insert, no migration, per §5.1).

## Reading order

Conventions → space-type templates (Living first, then Kitchen and Master Bedroom, which carry the most rules) → property templates → playbook → catalogue-record content.
