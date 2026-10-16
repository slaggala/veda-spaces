# Project execution, quality control, snags and handover: discovery, design and design review

Instruction `VEDA-SPACES-PROJECT-EXECUTION-QC-SNAGS-HANDOVER` (2026-10-16), branch `feature/project-execution-delivery`,
based on main at the merge of PR #107 (Project Commercials). Prefix **PEX**.

## 1. What already exists (proved by reading the code)

The Project Lifecycle Backbone (PR #101, decision log 40) is already the operational backbone after acceptance. It is
behind `VEDA_PROJECT_LIFECYCLE_ENABLED` (off everywhere, refused in production) and every PLB-OD slot is null.

| Concern | Existing source of truth | Gap this workstream closes |
|---|---|---|
| Activation | `POST /projects` books an ACCEPTED, digest-verified base quotation (`creation.py`): idempotent, one per chain, property lock, every refusal named | None. Booking **is** activation; it is not rebuilt. Readiness to start each stage is the gate evaluation |
| Lifecycle | `lifecycle.py` definition PLB-2026.10.1 (12 stages, pinned version and digest), `gates.py`, `service.request_transition`, four-eyes approval, refusals recorded as rows | Two structural gates added (work complete; commercial condition for handover). The definition document and its digest are unchanged |
| Milestones | `project_milestone`: planned/actual/customer-promised dates kept apart, explicit completion, dependencies | Milestones are points in time. There is no body of work with an owner, a room, a start and a finish |
| Blockers | `project_blocker`: GATING/INFORMATIONAL, responsible party, customer action | No link to a unit of work; no customer-safe wording for "paused" that is not an action |
| QC | `project_qc_check`: append-only, category, optional space, recheck link | "Latest per category" lets a PASS in one room hide a FAIL in another; no plan of what must be checked; a check can be rechecked twice; no evidence requirement; no link to work |
| Snags | `project_snag`: OPEN → IN_PROGRESS → READY_FOR_RECHECK → RESOLVED → CLOSED | The fixer can verify their own fix; a snag can be closed from OPEN with any note; no source, priority, customer visibility or fix evidence |
| Handover | `complete_handover`: same gates, acknowledgement reference + evidence attachment (PLB-OD-09 default), emits `project.handed_over` | No handover package of what is handed over; no customer acknowledgement bound to it; the commercial position is never consulted |
| Evidence | `service.evidence`: an existing CLEAN attachment of the project's lead (attachments module: scanning, image policy, access control) | Reused as is. No customer-visible document class exists (CPP-D04, open), so evidence stays staff-only |
| Customer portal | `portal/projection.py`: execution, quality and handover steps from the stage only, customer actions through the classification allow-list | No work, quality, snag or handover detail; no write path |
| Commercials | `commercials.position.compute` (one calculation), customer projection in the portal | Read (never written) by the handover commercial condition |
| Audit | `AuditedBase` + `audit_registry` FULL; `project_event` immutable (triggers) | New tables registered FULL with their project parent and personal-data fields |
| Notifications | Outbox + `notify_in_app` (staff); commercials email `commercial_document` to the primary customer | Customer emails for material, customer-safe events only |
| Erasure | `project/erasure.py`: free text → `[erased]`, codes and dates kept, project closed to writes | Extended to the new text fields; the handover package is redacted and re-sealed |
| RBAC | 16 `project.*` codes, scoped ALL/OWN by team membership; commercials codes FOUNDER + SALES_MANAGER | PCM-D01 ACCOUNTANT role; two new project codes |

Reuse map (capability → authoritative source → execution extension → staff workflow → customer projection):

| Capability | Source | Extension | Staff | Customer |
|---|---|---|---|---|
| Readiness | `gates.evaluate`, `creation.eligibility` | `WORK_COMPLETE`, `COMMERCIAL_CONDITION` | Readiness panel (exists), work and handover sections | Stage step + "what happens next" |
| Plan | `project_milestone` | `project_work_package` | Work plan section | Customer-visible work, by state |
| Blockers | `project_blocker` | work-package link, `customer_summary` | Blocker form | "Paused" (summary) or "Action required" |
| QC | `project_qc_check` | `project_qc_point`, chains, evidence requirement | QC plan + results | Counts: checked, being corrected |
| Snags | `project_snag` | fixer/verifier, closure codes, visibility | Snag list + verify | Customer-visible snags and their state |
| Customer issues | — | `project_customer_report` | Triage queue | Report form (PEX-D01), report list |
| Handover | `complete_handover`, `handover_readiness` | `project_handover_package` | Prepare, complete | Package summary, acknowledgement (PEX-D01) |

## 2. Domain (migration `0212_project_execution`; `0211_accountant_role` is PCM-D01)

Every new row carries `project_id` and `lead_id` (scope and erasure follow the lead). Every new table is FULL-audited.

### 2.1 Work packages (`project_work_package`)

A body of work in one stage: number (`WP-n`), stage, optional space of the property, internal title and description,
optional customer label and `customer_visible`, owner (an active person holding `project.manage_work` in scope),
optional predecessor (finish-to-start), planned start/finish (internal; may be absent: **unscheduled**), actual
start/finish, plan revision, evidence, status.

| Command | Rule |
|---|---|
| Add | Into the current or a later stage; dates only if genuinely supplied (start ≤ finish) |
| Plan (PATCH) | Changing a planned date that was already set needs a reason: `WORK_PACKAGE_REPLANNED` (previous and new dates, revision + 1). Setting the first date is planning, not a revision |
| Start | Only in its own stage (the project's current stage); predecessor completed or cancelled; no open GATING blocker on it; actual start not in the future |
| Complete | Started; predecessor closed; no open GATING blocker on it; actual finish not in the future and not before the start; optional evidence |
| Reopen | A completed package (rework), with a reason, while its stage is open |
| Cancel | Not completed, with a reason |

`BLOCKED` is **derived** (an open GATING blocker linked to it), never stored or picked. Completion is never inferred from
a date. A completed package whose quality check failed is reported as `CORRECTION_REQUIRED`, not completed.

### 2.2 Quality control

- **QC plan** (`project_qc_point`): what must be checked: category, optional space and work package, internal label,
  `evidence_required`. Withdrawn only before any result, with a reason.
- **Checks** (`project_qc_check`, extended): optional `qc_point_id` (category must match; space and package come from
  the point) and `work_package_id`. A check of a work package can be recorded once the package is completed; other
  checks from the quality-check stage on (unchanged).
- **Chains**: a check without `recheck_of_id` starts a chain; a recheck targets the chain's head only, at most once
  (unique index on `recheck_of_id`): two simultaneous rechecks cannot both succeed. The **head** decides.
- **Evidence**: a PASS on a point with `evidence_required` needs a CLEAN attachment.
- **Remediation**: a PASS (or NOT_APPLICABLE) recheck of a FAIL is refused while a snag raised from any check of the
  chain is open (`REMEDIATION_OPEN`), and refused to anyone who fixed one of those snags (`SEGREGATION_REQUIRED`).
- **Gates** (`QC_RECORDED`, `QC_PASSED`): each required category (PLB-OD-08; undecided: all but OTHER) has a chain
  whose head has a result; no chain head is FAIL (any category, any room); every active plan point has a head PASS or
  NOT_APPLICABLE. This replaces "latest per category", which let a PASS in one room hide a FAIL in another.

### 2.3 Snags (extended `project_snag`)

New: `work_package_id`, `source` (STAFF, QUALITY_CHECK, CUSTOMER), `priority` (HIGH, NORMAL, LOW), `customer_visible`,
`fixed_by`/`fixed_on`/`fix_note`, `resolution_evidence_attachment_id`, `closure_code`, `customer_report_id`.
Statuses are unchanged; their meaning in the instruction's terms:

| Instruction | Repository status | Rule |
|---|---|---|
| IDENTIFIED | OPEN | Raised (staff, from a QC failure, or accepted from a customer report) |
| TRIAGED/ASSIGNED → IN_PROGRESS | IN_PROGRESS | A Veda-responsible snag needs an owner first (`SNAG_UNASSIGNED`) |
| RESOLVED | READY_FOR_RECHECK | The fixer records the fix (note required; evidence optional): `fixed_by` |
| VERIFIED | RESOLVED | `project.verify_snag`, never the fixer (`SEGREGATION_REQUIRED`), note required; or back to IN_PROGRESS with a note |
| CLOSED | CLOSED | From RESOLVED (`closure_code` FIXED); otherwise only with `project.verify_snag`, a closure code (DUPLICATE, NOT_A_DEFECT, RAISED_IN_ERROR) and a note |

Nothing is deleted. A customer-reported snag cannot be hidden from its customer.

### 2.4 Customer reports (`project_customer_report`)

A customer's report of an issue, in the customer's words, never a defect by itself: SUBMITTED → triaged by staff with
`project.manage_snag` to ACCEPTED (a new snag, customer-visible, or an existing snag) or DECLINED (a code and a
customer-safe response). Submitted through the portal (when PEX-D01 allows it) or recorded by staff on the customer's
behalf. Portal submission: the authenticated account's authorised property only, an active project, per-session rate
limits, at most 10 untriaged reports per project, and a required Idempotency-Key stored as a digest with the request
digest (same key and body: the same report; a different body: refused). An untriaged report stops handover readiness.

### 2.5 Handover package (`project_handover_package`) and acknowledgement

Prepared by `project.complete_handover` in READY_FOR_HANDOVER when handover readiness has no blocker. Its content is
frozen with a SHA-256: the handed-over scope (quotation chain, baseline sequence and digest), customer-visible work
completed, the quality summary, the snag summary (open non-blocking ones listed by their customer title), documents
(none until CPP-D04) and a warranty reference that points at the accepted quotation's own warranty section (no
warranty term is written here). One PREPARED package per project; preparing again supersedes it.

The customer acknowledges a package (by id and digest) in the portal when PEX-D01 allows it; repeating it returns the
same acknowledgement. Completing the handover needs a current package: the content is recomputed and must still match
(`HANDOVER_PACKAGE_STALE` otherwise). A portal acknowledgement satisfies the acknowledgement requirement of PLB-OD-09;
otherwise staff give the reference of the signed form as today. The package is marked COMPLETED with the transition,
and `project.handed_over` carries its id and digest for the future warranty workstream.

### 2.6 Handover readiness: one computation

`gates.handover_readiness` remains the only computation; staff detail, the readiness route, the package and the portal
all read it. It now covers: the handover transitions' configurable gates (QC, snags and untriaged reports, variations),
open gating blockers, baseline integrity, every work package closed with no failed check, and the commercial
condition (PEX-D02). Each blocker is explicit (code, message, responsible party, entity).

### 2.7 Customer portal

New flag `VEDA_PROJECT_DELIVERY_PORTAL_ENABLED` (off by default, refused in production, effective only with the
portal and lifecycle flags). With it, the property page gains a `delivery` block, built from an allow-list:

- the current phase (Customer Promise stage), customer-visible work grouped COMPLETED / IN PROGRESS / ACTION REQUIRED
  / BLOCKED / UPCOMING, counts (never a percentage);
- the next customer-promised date only (planned dates are internal and never shown);
- quality: checks passed and being corrected (counts only);
- customer-visible snags and their state; the customer's own reports and their outcome;
- handover readiness in customer words ("not yet: N items remaining", by customer-safe category) and the package with
  its acknowledgement.

Internal titles, descriptions, notes, people, evidence, QC observations and costs are never read into it.

### 2.8 RBAC

| Code | Allows | Default |
|---|---|---|
| `project.manage_work` | Work packages | FOUNDER (ALL); operations persona granted individually |
| `project.verify_snag` | Verify or close a snag without a fix | FOUNDER (ALL); quality persona granted individually |

QC plan points use `project.manage_qc`, customer-report triage `project.manage_snag`, the package
`project.complete_handover`. ACCOUNTANT holds no `project.*` code.

PCM-D01: role ACCOUNTANT (MFA required) holds the six `commercials.*` codes (ALL) and the shell's self-service codes.
SALES_MANAGER keeps `commercials.view` only; its five mutation codes are withdrawn by migration (audited). FOUNDER keeps
everything. ADMIN holds no commercial code, so the escalation guard keeps an accountant's account under FOUNDER.

### 2.9 Concurrency and idempotency

Every write takes the project row lock and re-reads (unchanged mechanism). New creates take `Idempotency-Key`; row
changes take If-Match on the row. Specific guards: one recheck per check (unique), one PREPARED package (partial
unique), one report per account key (unique), an acknowledgement is a no-op once recorded, start/complete/verify
re-check state under the lock.

### 2.10 Decisions (new register PEX-D01, PEX-D02)

| Slot | Question | While undecided |
|---|---|---|
| PEX-D01 | May customers, in the portal, (a) report an issue and (b) acknowledge a handover package? | Both portal mutations refused (`OWNER_DECISION_REQUIRED`); the portal shows neither form. Staff record reports on the customer's behalf and the signed-form reference at handover |
| PEX-D02 | Must the commercial position meet a condition before handover: NONE, NO_AMOUNT_DUE (nothing requested and unpaid) or FULLY_PAID? | `COMMERCIAL_CONDITION` fails closed for READY_FOR_HANDOVER and the handover; the position is shown for information |

Not new decisions: customer-visible documents and photographs (CPP-D04, open), rework of completed stages (PLB-OD-12),
promised dates (PLB-OD-13), required QC categories (PLB-OD-08).

## 3. Design review (before implementation)

| Risk | Finding | Resolution |
|---|---|---|
| Duplicate lifecycle | A second state machine for execution | None: work packages, QC points, reports and packages are rows of the existing project, gated by the existing evaluation; two structural gates join it; the definition and its digest are unchanged |
| Manual progress | A status picker on work | Explicit commands only; BLOCKED derived; no percentage anywhere |
| False customer progress | Showing planned dates or completion before QC | Only customer-promised dates; completed work with a failed check shows "being corrected"; nothing is shown unless staff marked it customer-visible with customer wording |
| QC bypass | PASS in one room hiding a FAIL in another; double recheck; recheck by the fixer | Chains and heads; unique recheck; segregation; evidence where required |
| Snag closure without verification | Close from OPEN with any note; self-verification | Verification by `project.verify_snag`, never the fixer; closing without a fix needs a code and the same capability |
| Unclear handover gates | Several places computing readiness | One `handover_readiness`; the package is prepared only when it is empty and checked again at completion |
| Customer data leakage | New customer surfaces | Allow-list projection; 404 for anything outside the account's access; reports return only the customer's own words and the staff response |
| Evidence URLs | Customer photographs | None exposed (CPP-D04); staff evidence stays the attachments module's |
| RBAC breadth | — | Two codes, FOUNDER only by default; ACCOUNTANT has no project code; SALES_MANAGER loses financial mutations |
| Commercials conflict | Execution depending on payments | Only the handover condition reads the position, and only as the owner decides (PEX-D02) |
| History edits | — | Append-only checks; rows never deleted; reopen and replan need reasons and are events; erasure redacts text only |
| Concurrency | Double recheck, double package, duplicate report, ack retry | Unique indexes plus the project lock; races tested on both engines |
| Invented rules | Severity scales, warranty, payment gates | Priority is a triage aid only; warranty is a pointer to the quotation; payment gating is PEX-D02 |
| Complexity | Templates of QC checklists | No template engine: QC points are per project; categories stay the PLB vocabulary |

Design defects found and fixed before implementation: (1) the first draft stored BLOCKED on work packages, which would
be a manual status; it is derived. (2) The first draft let a new PASS in a category clear a FAIL; chains replace it.
(3) The first draft put the commercial condition into a configurable gate, which an owner's PLB-OD-02 list could
silently drop; it is structural and governed by its own decision. (4) Customer-visible evidence was dropped: no
document class is approved (CPP-D04).

## 4. Independent design review (fresh context) and how each finding changed the design

| # | Severity | Finding | Change to the design (binding on the implementation) |
|---|---|---|---|
| D1 | Merge blocker | FAIL → recheck TO_BE_CONFIRMED → recheck PASS escapes remediation and segregation | TO_BE_CONFIRMED is never a recheck of a FAIL; remediation and segregation apply to every recheck in a chain that has ever held a FAIL |
| D2 | Merge blocker | NOT_APPLICABLE satisfies an evidence-required plan point | NOT_APPLICABLE is refused on a plan point; withdrawal (before any result, with a reason) is the only way out of a point |
| D3 | High | Commercial condition undefined at the edges (several projects per property, no schedule, flag off, unsound record) | The project's commercial record is the one of its quotation chain (`quotation_number`). Unless PEX-D02 is NONE, the condition fails closed when the commercials flag is off, there is no record, the record does not verify, or the schedule needs revision. NO_AMOUNT_DUE = a schedule exists, is in balance, and nothing requested from the customer is unpaid (no line DUE or OVERDUE, and no line PARTIALLY_PAID after a request: a part payment towards an instalment never requested is not an amount due; amended after the implementation review, M3) |
| D4 | High | Work packages of a completed stage can deadlock | `WORK_COMPLETE` is structural on **every** transition, for the packages of the current and earlier stages, so a stage cannot complete with open work. A failed check on a package of a completed stage is remediated through a snag and a recheck (the chain head decides); reopening is only for an open stage |
| D5 | High | Package staleness not checked at four-eyes approval | The handover transition stores `handover_package_id` and the package digest; `HANDOVER_EVIDENCE` re-verifies, in `gates.evaluate`, that this package is the current one and unchanged, so an approval checks it again. A portal acknowledgement counts only for that id and digest |
| D6 | Medium | Untriaged reports inside a configurable gate | Structural gate `CUSTOMER_REPORTS_TRIAGED` on the moves to READY_FOR_HANDOVER and HANDED_OVER |
| D7 | Medium | Two readiness computations | `handover_readiness` is derived from `gates.evaluate` of the handover move (all gates but the evidence given at completion); before READY_FOR_HANDOVER it aggregates the handover gates as before and says the stage is not reached. Package preparation requires that evaluation to have no blocker other than the owner-policy gate and the evidence gate |
| D8 | Medium | Segregation keyed to one overwritable `fixed_by` | Every fix is an immutable `SNAG_FIXED` event; the verifier must be none of the snag's fixers (all cycles) and not its owner. A QC recheck after a FAIL is refused to any fixer or owner of a snag raised from the chain |
| D9 | Medium | Package lists snags that are not customer-visible | Only customer-visible snags by title; the rest as a count |
| D10 | Medium | Erasure re-seal breaks digest provenance | The original digest is never replaced; erasure redacts the content, records `redacted_sha256` and marks the package redacted |
| D11 | Medium | Customer emails unspecified | Two customer emails only, gated by `VEDA_PROJECT_DELIVERY_PORTAL_ENABLED`, to the account concerned, saying only that there is an update in the portal: "report received" and "handover package ready". Staff in-app notifications for a new customer report |
| D12 | Low | Migration and consistency details | Pre-check refuses the migration if a check was rechecked twice; new NOT NULL columns have server defaults; `closure_code` has no CHECK coupling to old CLOSED rows; event codes ≤ 32 characters; a recheck inherits point, package and space from the chain; predecessors are acyclic and in the same or an earlier stage; `customer_visible` needs a customer label (CHECK); the portal lists each project of the property and every customer write names the project id (authorised through the property); report limits are per account; portal writes take the project lock through their own path |
