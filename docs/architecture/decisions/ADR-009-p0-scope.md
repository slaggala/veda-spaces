# ADR-009: Scope of the P0 architecture freeze

- **Status:** Accepted
- **Date:** 2026-09-29

## Context

The architecture package describes a long-term platform (10). Without an explicit boundary, roadmap designs could be mistaken for authorized P0 work.

## Decision

This freeze covers, and authorizes for subsequent implementation planning:

- Authentication
- MFA
- RBAC
- User management
- Audit logging
- Security-event logging
- Lead capture
- Lead notes
- Lead activities
- Lead administration
- The notification foundation
- PostgreSQL migration readiness

It does **not** authorize implementation of:

- vendor management;
- inventory;
- payroll;
- procurement;
- full project management;
- the other roadmap modules in 10: customer, quotation, design, employee, onboarding, portal, warranty, finance, attachments, org units, AI.

Those remain roadmap items. Each needs its own requirements, ADRs and review.

Requirements marked P1 or P2 inside the in-scope areas (for example LEAD-017 export, NOTE-003 pinning, SEVT-007 external anchoring, AUDIT-013 audit hash chain) are designed but **deferred**. They are reported as deferred in the coverage gate.

## Alternatives considered

| Option | Why rejected |
|---|---|
| No explicit scope | Risk of scope creep |
| Include Customer conversion | Not approved |

## Consequences

- 10-future-roadmap carries a "not authorized" banner.
- Deferred requirements are tracked, not dropped.
- PLAT-012 makes the boundary a traceable requirement.

## Risks

| Risk | Mitigation |
|---|---|
| Roadmap tables slipping into P0 migrations | Migration review against this ADR. The coverage gate lists deferred items. |

## Affected requirement IDs

PLAT-012, PLAT-011, and all deferred (P1/P2) requirements

## Affected documents

README, 01, 04 (§1), 10, 11 (§8), coverage-gate

## Future review triggers

- Completion of P0 implementation
- An owner request to start any roadmap module
