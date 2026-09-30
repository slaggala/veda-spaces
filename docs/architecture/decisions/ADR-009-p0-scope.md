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

Requirements marked P1 or P2 inside the in-scope areas (for example LEAD-017 export, NOTE-003 pinning, RBAC-007 time-bound grants, AUDIT-013 audit hash chain) are designed but **deferred**. They are reported as deferred in the coverage gate, and their API and UI surfaces are marked P1 and disabled in P0 (F-16).

**Remediation 01 scope adjustments.** These stay within the authorized areas; no roadmap module is added.

| Change | Reason |
|---|---|
| Promoted to P0: AUTH-016 (session list and revoke), RBAC-016 (effective-permission explain), SEVT-007 (external chain anchor), AUDIT-011 (audited anonymization procedure) | Resolves F-16 and F-11, and supports F-15 |
| Added to P0: MFA-012…015, RBAC-018…021, USER-007, LEAD-027…030, DATA-017, OPS-010, OPS-011, UI-016 | Owner Decisions 1–4, and findings F-03, F-05, F-07, F-09 and F-15 |

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

## Approval record

| Item | Value |
|---|---|
| Approver | Veda Spaces owner (repository owner) |
| Approval | 2026-09-29, `VEDA-SPACES-P0-ARCHITECTURE-SIGNOFF-AND-FREEZE`, decision ADR-009; amended by `VEDA-SPACES-P0-ARCHITECTURE-REMEDIATION-01` (scope adjustments above) |
| Evidence | [decision-log.md](decision-log.md). A verifiable owner sign-off (owner approval of the architecture pull request) is tracked gate TG-01 before implementation (F-18). |
