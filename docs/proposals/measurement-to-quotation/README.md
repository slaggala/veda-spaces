# Measurement-to-Quotation Intelligence Platform (MTQ) — proposal package

**Status:** Documentation only, submitted for independent architectural review. No code, no migrations, no tables, no flag changes, no pricing changes. V1, V2 and V3 behaviour is untouched.
**Instructions:** `VEDA-SPACES-MEASUREMENT-TO-QUOTATION-INTELLIGENCE-PLATFORM` (blueprint, 2026-10-13) · `VEDA-SPACES-MTQ-BLUEPRINT-PUBLISH-AND-REVIEW` (this package, 2026-10-13) · `VEDA-SPACES-MTQ-SURVEY-AND-SCOPE-TEMPLATE-SYSTEM` (survey and scope templates, 2026-10-13).

| Document | Purpose |
|---|---|
| [MTQ-BLUEPRINT.md](MTQ-BLUEPRINT.md) | The complete Phase 1–3 blueprint: business architecture, domain and entity models, schema, API, workflow, UX, versioning, RBAC, roadmap B1–B5 |
| [MTQ-owner-decisions.md](MTQ-owner-decisions.md) | Owner-decision register for the twelve unresolved owner inputs (OI-MTQ-01 … OI-MTQ-12). All blank |
| [MTQ-dependency-matrix.md](MTQ-dependency-matrix.md) | What each block depends on: platform modules, catalogue administration, rate-card decisions, commercial decisions |
| [MTQ-coverage-matrix.md](MTQ-coverage-matrix.md) | Reviewer traceability: property-type coverage, the BHK-as-label check, and the reuse-of-existing-mechanisms check, each with blueprint section references |
| [MTQ-implementation-entry-gate.md](MTQ-implementation-entry-gate.md) | The gate that must pass before any code generation for MTQ begins |
| [MTQ-B1-SCOPE.md](MTQ-B1-SCOPE.md) | B1 Measurement Foundation final scope (proposed freeze): supported configurations, included and deferred entities, Lite/Full survey, staircase, electrical and sensor capture, kitchen tall units, variation quotation model, attachment scaling, migration strategy |
| [survey-and-scope-templates/](survey-and-scope-templates/README.md) | Survey and scope-template system (2026-10-13): conventions, fourteen space-type templates, property templates, the measurement-visit playbook with the quotation-readiness gate, and catalogue-record content; proposed content for OI-MTQ-02 and OI-MTQ-03 |

Review order suggested: coverage matrix → blueprint §0–§4 → §5–§10 → §11–§15 → §16–§20 → dependency matrix → owner-decision register → entry gate.
