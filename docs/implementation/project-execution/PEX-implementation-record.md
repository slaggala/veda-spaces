# Project execution, quality control, snags and handover: implementation record (decision log 45)

Branch `feature/project-execution-delivery`, built on main after PR #107 (Project Commercials). Design, reuse map and the
two reviews of the design: [PEX-design.md](PEX-design.md). Owner decisions: [PEX-owner-decisions.md](PEX-owner-decisions.md).
Capabilities: [PLB-capability-map.md](../project-lifecycle/PLB-capability-map.md).

## What exists now

| Capability | Where |
|---|---|
| Work packages | `project/work.py`; `project_work_package`; staff routes `/projects/{id}/work-packages[/{wp}/start|complete|reopen|cancel]` |
| QC plan and check chains | `project/quality.py`, `service.add_qc_point`, `service.record_qc`; `project_qc_point`; `project_qc_check` (+ point, work package, one recheck per check) |
| Snag verification | `service.snag_status` (fix recorded by the fixer; verification by `project.verify_snag`, never a fixer of any cycle or the owner; closing without a fix needs a code) |
| Customer reports | `project/reports.py`; `project_customer_report`; staff record and triage; portal submission (PEX-D01) |
| Handover package and acknowledgement | `project/handover.py`; `project_handover_package`; `project_transition.handover_package_id/sha256` |
| Commercial condition | `project/commercial.py` (reads `commercials.position`, never writes) |
| Gates | `gates.py`: structural WORK_COMPLETE (every move), CUSTOMER_REPORTS_TRIAGED and COMMERCIAL_CONDITION (handover moves), HANDOVER_PACKAGE (handover); QC gates read chains; `handover_readiness` derived from `evaluate` |
| Customer view | `project/delivery.py` (allow-listed), joined by `portal/projection.property_view` (`delivery`) and Action Required |
| Customer writes | `portal/routes.py` (RBX-010): report an issue; acknowledge a handover summary |
| Notifications | `project/notices.py`: customer email `project_update` (report received; handover summary ready), staff in-app (customer report; acknowledgement) |
| Erasure | `project/erasure.py`: new free text erased; the package redacted with `redacted_sha256`, original digest kept |
| Staff UI | `app/src/modules/project`: tabs Work plan and Customer reports; QC plan and failed checks; verification-aware snag actions; handover package |
| Portal UI | `app/src/modules/portal/portal-project-page.ts`: "Work on your home" |
| PCM-D01 | `platform/rbac/registry.py` (ACCOUNTANT), `commercials/permissions.py`, migration `0211_accountant_role`, `ms.withdraw_role_grants`, `commercials/invoices.py` |
| Migrations | `0211_accountant_role` (data only), `0212_project_execution` (four tables, columns on four 0208 tables, the event-code CHECK widened, one unique index) |
| Flag | `VEDA_PROJECT_DELIVERY_PORTAL_ENABLED` (off, refused in production); staff routes stay behind `VEDA_PROJECT_LIFECYCLE_ENABLED` |

## Rules that hold

- **Activation** is the existing booking of an accepted, digest-verified quotation (`creation.py`): idempotent, one per
  chain, audited. Readiness for each stage is the gate evaluation. Nothing is activated by a status pick.
- **Progress** moves only by command. BLOCKED is derived from open gating blockers; CORRECTION_REQUIRED from a failed
  check chain or an open snag on completed work. Planned dates are internal and never complete anything; a missing date
  is shown as unscheduled; changing a set date is a replan with a reason and a timeline event.
- **Quality**: a failure stays the head of its chain until rechecked; a recheck of a chain that ever failed waits for its
  remediation snags to be verified and is refused to their fixers and owners; a planned check is never waived by
  NOT_APPLICABLE; evidence where the plan requires it.
- **Snags**: identified → being fixed (an owner is needed for a Veda snag) → fixed (the fixer's note) → verified (someone
  else) → closed. Closing without a fix: verifier, reason code, note. Nothing is deleted.
- **Handover**: one readiness computation; a package prepared only when nothing but the policy and evidence gates
  remain; the handover and any approval are bound to that package and digest and refused if it went stale; a portal
  acknowledgement counts only for that digest; repeating it records nothing.
- **Customer view**: only what staff marked customer-visible with customer wording; no internal text, people, planned
  dates, observations, evidence or amounts; never a percentage. Opaque ids of the customer's own project and package are
  used to address their two writes, reached only through their authorised property.

## RBAC (least privilege)

| Code | FOUNDER | ACCOUNTANT | SALES_MANAGER | Others |
|---|---|---|---|---|
| `commercials.view` | ALL | ALL | ALL | — |
| `commercials.schedule.manage`, `.payment.record`, `.payment.reverse`, `.invoice.issue`, `.audit.view` | ALL | ALL | — | — |
| `project.manage_work`, `project.verify_snag` | ALL | — | — | granted individually (operations, quality) |

Customers hold no permission: their portal session reaches only their authorised enquiries.

## Concurrency and idempotency

Every staff write takes the project row lock and re-reads (PostgreSQL `FOR UPDATE`, SQLite `BEGIN IMMEDIATE`); every
customer write takes the same lock through its own path. Guards: one recheck per check (unique index), one PREPARED
package (partial unique), one report per account key (unique, digests only), If-Match on every row change, an
acknowledgement that is a no-op once recorded. Races tested on both engines with the paused-request harness: two
rechecks, verify against recheck-failed, two package preparations, completion against a gating blocker, a double
acknowledgement, a retried report.

## Validation (SYNTHETIC)

| Suite | Result |
|---|---|
| `test_project_execution.py`, `test_project_delivery_portal.py`, `test_project_execution_integrity.py` (new) | 26 tests, pass on SQLite and PostgreSQL |
| Existing PLB, CPP and PCM suites, updated where the rules became stricter | pass on both engines |
| `test_accountant_role.py` (0211 upgrade from a pre-0211 database), schema and conformance | pass on both engines |
| App unit (web-test-runner) | 205 of 205 |
| Browser journeys | `delivery.e2e.mjs` 76/76, `project.e2e.mjs` 97/97, `portal.e2e.mjs` 64/64, `commercials.e2e.mjs` 123/123 (360, 390, 768, 1280 px; keyboard; 44 px; axe) |

The full CI result is on the PR.

## Independent review (fresh context, before merge)

No merge blocker or HIGH finding. Regression tests: `test_project_execution_review_fixes.py` (both engines).

| Finding | Handling |
|---|---|
| M1 (Medium): a snag accepted from a customer report through "existing snag" could be hidden again (only `source = CUSTOMER` was protected) | Fixed: a snag any customer report points at cannot be hidden (`CUSTOMER_REPORTED`). Tested |
| M2 (Medium): a report could be accepted against a closed snag, telling the customer "being fixed" | Fixed: refused (`SNAG_CLOSED`); raise a new snag or decline with a reply. Tested |
| M3 (Medium): the commercial condition's money branches were untested, and D3 said PARTIALLY_PAID where the code says "after a request" | Fixed: D3 amended to the implemented, stricter-meaning rule (a part payment towards an unrequested instalment is not due); tests for FULLY_PAID, NO_AMOUNT_DUE (request, part payment, payment), the project's own chain versus a second project with no record, an unsound record and an unbalanced schedule |
| L1 (Low): work could be added to the terminal stage and escape the gates | Fixed: refused (`TERMINAL_STAGE`). Tested |
| L2 (Low): the CPP rule "no project id reaches the customer" now holds only with the delivery flag off | Accepted and recorded: the delivery view carries exactly the customer's own project id and package id (the addresses of their two writes, reached only through their authorised property); no other internal id and never the project number. Tested with the flag on; CPP record updated |
| L3 (Low): an unchanged package preparation answered 201 | Fixed: 200 with the same package. Tested |
| I1: the 0211 withdrawal bumps every human's authorisation version | Accepted (same as `grant_new_codes`); docstring corrected |
| I2: a failure with no snag raised from it may be rechecked by the person who recorded the failure | Accepted as designed: segregation is between fixing and verifying; requiring a different inspector is an owner rule, not invented here |
| I3: with PEX-D02 null no project can reach handover readiness | Intended (fail closed); staging handover validation needs PEX-D02 recorded |
| Note: the delivery view (and its readiness computation) runs on every portal property read | Accepted: bounded per project; only with the delivery flag on |

## Limitations

- Customer-visible documents and photographs (handover documents, QC evidence) wait on CPP-D04; the package lists none.
- Keys, assets and handed-over items are not represented by business data, so the package does not list them.
- Rework of a completed stage's work is through snags and rechecks; reopening is for the open stage only (PLB-OD-12).
- No QC template library: checks are planned per project from the PLB categories.
- Customer emails for the two events only; no reminders (no scheduler is enabled).
- Project Commercials staging wiring (PCM-D02) is a separate infrastructure change with the owner's plan and apply.

## Release

Nothing is enabled anywhere. Project Lifecycle, the delivery view and Project Commercials stay off and refused in
production. PLB-OD-01…13 untouched. No warranty term is written: the package points at the accepted quotation's own
warranty section.
