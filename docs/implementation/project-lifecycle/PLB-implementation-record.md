# Project Lifecycle Backbone: implementation record

Instruction `VEDA-SPACES-PROJECT-LIFECYCLE-BACKBONE-END-TO-END` (2026-10-15), branch `feature/project-lifecycle-backbone`,
umbrella PR #101. Decision log entry 40. Owner decisions: [PLB-owner-decisions.md](PLB-owner-decisions.md). Capabilities:
[PLB-capability-map.md](PLB-capability-map.md).

The Project Lifecycle Backbone is the internal operational view of a project, from its accepted commercial baseline to
handover. It is not procurement, manufacturing, accounting, payments, workforce scheduling, a customer portal, warranty or
service ticketing, notification channels to customers, or AI. Those are separate workstreams (§17).

Everything is behind `VEDA_PROJECT_LIFECYCLE_ENABLED`. The flag is off everywhere and refused in production, and it is not
wired to staging. Every owner-policy slot is null. Validation used synthetic data only.

## 1. Domain model (migration `0208_project_lifecycle`)

The migration is additive and expand-only, with twelve tables. Every row carries `project_id` and the project's
`lead_id`, so scope and erasure follow the lead as they do for every MTQ row. All twelve tables are FULL-audited.

| Table | Holds |
|---|---|
| `project` | Reference `VS-P-YYYY-NNNNNN` (sequence `PROJECT`), lead, property, the accepted quotation chain it executes (`quotation_number`, `source_quotation_id`), status `ACTIVE` or `HANDED_OVER`, current stage, pinned lifecycle definition version and digest, current baseline sequence |
| `project_baseline` | The commercial-baseline lineage, append-only (§3) |
| `project_stage` | One row per stage of the pinned definition: `NOT_STARTED`, `ACTIVE` or `COMPLETED`, with who and when |
| `project_member` | The team, by responsibility, with at most one active owner per ownership responsibility |
| `project_transition` | Every transition request, with its sealed gate evaluation and outcome, the independent approval, and the handover evidence |
| `project_checklist_item` | Execution of the pinned definition's checklists |
| `project_milestone` | Milestones, with planned, actual and customer-promised dates kept apart |
| `project_blocker` | First-class blockers: `GATING` or `INFORMATIONAL` |
| `project_site_readiness` | The project's observation of each site-readiness item |
| `project_qc_check` | Quality-check results, append-only |
| `project_snag` | Snags (the punch list) |
| `project_event` | The immutable timeline (§11) |

No property, customer, quotation, variation, site-readiness policy, audit, user, role or file is duplicated. Attachments
are referenced, never copied.

## 2. Accepted quotation → project

`POST /api/v1/projects` takes `{quotation_id, property_id}` and needs `project.create_from_acceptance`. Its scope is the
quotation's lead. `creation.eligibility` refuses with every reason named:

- **Not accepted.** The quotation is not `ACCEPTED`: draft, internal review, approved, issued and undecided, rejected,
  expired, or superseded.
- **A variation.** A variation updates its project's baseline; it never starts a project.
- **Wrong context.** A property or customer context other than the quotation's.
- **Missing acceptance record.** The B4 decision fields, the B4 `ACCEPTED` event bound to the frozen-baseline digest and
  method, and for `CUSTOMER_DIGITAL` the CQX acceptance-evidence row.
- **Failed integrity.** The frozen document, its HTML or the frozen accepted baseline no longer match their digests
  (tampering).
- **Erased customer record.**
- **Already booked.** The chain already has a project.

Creation is transaction-safe. It takes the property lock that every commercial transition of the property takes,
re-reads, and checks before it inserts. Unique indexes admit one project per source quotation and one per chain.

Creation is idempotent. A retry with the same `Idempotency-Key` replays the first response. A new request for a booked
chain answers `409 PROJECT_EXISTS` with the project's id.

Booking is explicit. Acceptance creates nothing: whether booking should happen on acceptance is decision PLB-OD-10. The
dashboard lists accepted quotations without a project in a booking queue, each with its eligibility.

## 3. Commercial baseline and variations

A project references its baseline as a lineage and never as a copy:

    Original accepted baseline → Variation 1 → Variation 2 → current effective baseline

Each `project_baseline` row records one accepted quotation version:

- its frozen document digest, its frozen accepted-baseline digest (which covers the optional items the customer chose)
  and its estimate digest;
- the measurement, scope, BOQ and estimate revisions;
- the Customer Promise pack reference it froze;
- the accepted value and the cumulative value;
- `baseline_sha256`, a SHA-256 over this reference chained to the previous row's digest.

The B4 decision service gains one extension point, `quotations.ACCEPTANCE_HOOKS`, imported by dotted path when called.
When a variation on a booked chain is accepted through the existing commercial route, the next row is appended in the
same transaction, under the project lock, with a `VARIATION_ACCEPTED` event.

The Project Lifecycle never prices, never issues a variation, never changes a rate card and never adds scope. No project
code writes to a quotation.

`baseline.problems` verifies the chain on every transition (the `BASELINE_VALID` gate). It checks:

- every digest;
- every referenced quotation, which must still be `ACCEPTED` with a verifying frozen document and baseline;
- the current-baseline pointer;
- that every accepted variation of the chain is recorded.

Amounts and digests appear only with `project.view_commercial_baseline`.

## 4. Lifecycle definition and state machine

`lifecycle.py` holds definition `PLB-2026.10.1`. It is reviewed code, not a workflow editor. It has twelve stages:

`BOOKED → DESIGN_FINALISATION → SCOPE_FROZEN → SITE_READINESS → PRODUCTION_READINESS → IN_PRODUCTION →
READY_FOR_INSTALLATION → INSTALLATION → QUALITY_CHECK → SNAGGING → READY_FOR_HANDOVER → HANDED_OVER`

Each stage has an internal label, a description, the Customer Promise stage a future portal may show, the
responsibility that owns its work, and its checklist definition. The last stage is terminal.

Transitions move forward one stage at a time. Each has a risk class. HIGH is used for the moves the instruction names:
scope freeze, production release, start of installation, ready for handover, and handover. Each transition also has the
strictest default gate set. The definition is PROPOSED until the owner approves it (PLB-OD-01).

A project pins the version and digest it was created under and is always interpreted with them. A change is a new
version, and the unit suite pins the digest of every published version, so editing one fails the build.

Progression is never a status picker. Each move is an explicit command:

- `POST /projects/{id}/transitions` with `{to_stage}` and If-Match on the project;
- `POST /projects/{id}/handover` for the last stage.

The gates decide (§5). The request is recorded whatever the outcome: `REFUSED` with its exact blockers, `AWAITING_APPROVAL`,
or `COMPLETED`. A refusal is a committed row, not a 4xx, because a 4xx rolls back the request's writes; this is how
refused transitions are audited. A stage-reaching move completes the current stage row, activates the next and appends
`STAGE_COMPLETED` and `STAGE_ENTERED`.

There are no backward transitions, cancellation or on-hold. Those are PLB-OD-12.

## 5. Stage gates

`gates.evaluate` is read-only. It returns every gate with its source (`STRUCTURAL`, `DEFAULT` or `OWNER_DECISION`), its
result, and each blocker with its code, a message, the responsible party, the entity and what it blocks.

- **Structural (always apply).**
  - `TRANSITION_ALLOWED`: the next stage, an active project, and no other request awaiting approval.
  - `BASELINE_VALID`: the baseline verifies (§3).
  - `NO_GATING_BLOCKERS`: no open gating blocker targets this stage or an earlier one.
  - `POLICY_RECORDED`: for HIGH moves only, PLB-OD-01, PLB-OD-02 and PLB-OD-03 must be recorded. Until they are,
    every HIGH move is refused (fail closed).
- **Configurable.** The owner's list for the transition (PLB-OD-02) is used where recorded; otherwise the defaults:
  - `CHECKLIST_COMPLETE`;
  - `OWNER_ASSIGNED`: the next stage's owning responsibility, or PLB-OD-04;
  - `SITE_READY`;
  - `VARIATIONS_CLOSED`;
  - `MILESTONES_COMPLETE`: milestones of the current stage;
  - `QC_RECORDED` and `QC_PASSED`: the required categories (PLB-OD-08); any failure blocks;
  - `SNAGS_RESOLVED`;
  - `HANDOVER_EVIDENCE` (PLB-OD-09).

Recorded evaluations carry codes and ids, never staff text such as blocker titles or milestone labels, so they need no
erasure.

`GET /projects/{id}/readiness` evaluates the next or a named move. Handover readiness (PLB-28) aggregates the handover
gates whatever the current stage.

## 6. Checklists

The definition, meaning what is normally checked, lives in code. Execution, meaning what happened on this project, lives
in `project_checklist_item`. Items are `OPEN`, `DONE` or `NOT_APPLICABLE`, with who, when, a note, a reason and an
evidence reference.

Marking a required item not applicable needs `project.checklist.not_applicable` and a reason of at least 5 characters.
Reopening needs a reason. A completed stage's record is closed (`STAGE_COMPLETED`). Optional items are owner decision
PLB-OD-07; until it is recorded, every item is required.

## 7. Milestones

A milestone has a type, an internal label, an optional customer-safe label, a description and its stage. It also has a
status: `NOT_STARTED`, `PLANNED`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `CANCELLED` or `NOT_APPLICABLE`.

Three dates are kept apart: the planned date (internal, never a commitment), the actual date and the customer-promised
date. A customer-promised date is recorded only when one was already promised; how those dates are governed is PLB-OD-13.

Rules:

- Completion is explicit and needs a past or current actual date. Nothing is inferred from the calendar; "past its
  planned date" is shown but never completes or blocks anything.
- A milestone cannot complete before the milestone it depends on, or while a gating blocker on it is open.
- Cycles in dependencies are refused.
- Cancelled and not-applicable milestones need a reason.

## 8. Blockers

Blockers are first-class. Each has:

- a category, a source and an impact (`GATING` or `INFORMATIONAL`);
- an internal title and description, and a customer action in customer-safe words;
- the responsible party as a code: `CUSTOMER`, `VEDA`, `THIRD_PARTY` or `TO_BE_CONFIRMED`;
- an assignee (who must be able to see the project), a target date, a status (`OPEN`, `IN_PROGRESS`, `WAITING_CUSTOMER`,
  `WAITING_VEDA`, `RESOLVED` or `CANCELLED`), a resolution, and links to a milestone, checklist item, site-readiness item
  or variation.

A gating blocker names the stage it stops. It stops that stage and every later one. An informational issue never stops
anything. When the customer acts, the customer action is required.

The page shows each gating item as: blocked, why, who acts, what is needed, what it blocks, and what can happen when it
is resolved (PLB-41). Blockers never measure people.

## 9. Site readiness (reuse)

The three concepts stay separate:

- **Policy.** The published Customer Promise sets the customer-facing readiness expectations.
- **Frozen content.** The accepted quotation froze that text.
- **Observation.** `project_site_readiness` records whether this site satisfies each item today.

At booking, every readiness item and customer responsibility in the quotation's frozen `customer_information` becomes an
observation. It is referenced by code, pack version and category from the Customer Promise vocabulary, and starts
`TO_BE_CONFIRMED`. The promised text is read from the frozen document and never copied. Staff can add items.

Statuses are the Customer Promise readiness statuses plus `VEDA_ACTION_REQUIRED`. An actionable status needs the matching
responsible party and an action, and a customer action also needs customer-safe wording. Nothing here changes a
quotation.

## 10. QC, snags and handover

**Quality checks** are append-only rows. Each has a category, a result (`PASS`, `FAIL`, `NOT_APPLICABLE` or
`TO_BE_CONFIRMED`), an optional space, an observation (required for `FAIL`), evidence, and an optional link to the check
it rechecks. The latest result per category counts. Checks are recorded from the quality-check stage on.

**Snags** have a project number, an optional space and item reference, a category, a customer-safe title and an internal
description. Each also has a blocking flag, an owner, a responsible party, a target date, evidence and a resolution. They
move `OPEN → IN_PROGRESS → READY_FOR_RECHECK → RESOLVED` (the recheck needs a note) `→ CLOSED`. A recheck can send one
back to `IN_PROGRESS`, and a snag can be closed without a fix only with a reason.

**Handover** goes through the same gates. It needs a past or current date and, while PLB-OD-09 is undecided, both an
acknowledgement reference and an evidence attachment. It may record non-blocking observations. It closes the project:
`HANDED_OVER`, all stages completed, and further writes refused.

Handover emits `project.handed_over`, an outbox event carrying ids only (project, lead, property, source quotation,
baseline, transition) for a future warranty/service workstream (PLB-30). It creates no warranty case, service ticket,
feedback request or payment.

## 11. Timeline and audit

`project_event` is append-only. Each event records its actor, time, code, stage, states and a detail of codes, ids,
digests and dates. `events._check` refuses free text, and database triggers refuse `UPDATE` and `DELETE`. The events are
`PROJECT_CREATED`, `BASELINE_RECORDED`, `VARIATION_ACCEPTED`, owner and member events, the transition outcomes,
`STAGE_COMPLETED` and `STAGE_ENTERED`, checklist, milestone, blocker, site-readiness, QC and snag events, `HANDOVER_READY`
and `HANDED_OVER`.

Every table is FULL-audited, with the parent project, and free text is registered as personal data. With
`project.view_audit`, `GET /projects/{id}/history` lists the audit entries of the project's records. It shows the
fields changed, never their values.

## 12. Ownership, team and scope

The responsibilities are `COMMERCIAL`, `DESIGN`, `PROJECT`, `SITE`, `QUALITY`, `HANDOVER` and `MEMBER`. Each ownership
responsibility has one active holder. The holder must be an active person with `project.view` and the responsibility's
capability ([capability map](PLB-capability-map.md)).

Replacing an owner needs a reason, and ending an assignment needs a reason. Every change is audited and on the timeline.

OWN scope means an active team member. Visibility needs both the capability and the scope. A project outside read scope
answers 404, including for a guessed id. An out-of-scope action on a visible project answers 403. Child-row ids are
resolved through their project, so there is no cross-project update. Team membership grants nothing by itself.

## 13. Concurrency

Every write takes the project row lock (`SELECT … FOR UPDATE` on PostgreSQL; SQLite runs under `BEGIN IMMEDIATE`). It
then re-reads and checks If-Match against the re-read version: the project's version for moves and handover, the row's
version for row edits.

Every child change moves the project's version. A transition decided on a stale screen therefore conflicts, and an
approval re-evaluates every gate on committed state.

Booking serialises on the property lock. The variation hook takes the project lock.

Forced interleavings are tested on both engines: duplicate booking, simultaneous transitions, a checklist reopened
mid-move, a gating blocker raised mid-move, a variation accepted mid-move, a duplicate handover, and a snag raised
mid-handover. None produced an IntegrityError, an HTTP 500 or a lost update.

## 14. Customer-safe classification (preparation only)

`classification.py` classifies every column of every project table as `INTERNAL_ONLY`, `POTENTIALLY_CUSTOMER_SAFE` or
`CUSTOMER_ACTION`. A unit test refuses any unclassified column.

Nothing reads the classification to publish anything. There is no customer route, projection or notification. The page
labels customer-safe and internal fields.

## 15. Notifications and evidence

**Notifications.** Outbox handlers send in-app notifications to staff only, resolved by permission and team, for: a
blocker assigned, a customer action required, a transition awaiting approval, a stage entered, ready for handover, and
handed over. No customer is notified and no channel is added.

**Evidence** references an existing attachment of the project's customer record. The attachment must be scanned
`CLEAN` and available, which reuses the attachment module's malware scanning, image-only policy, access control,
retention and erasure. There is no new upload path, no public URL and no new file type.

## 16. Erasure, flag and API

**Erasure.** Lead erasure (cascade `veda.modules.project.erasure`) replaces every staff free-text field with
`[erased]` and closes the project to writes. Codes, dates, statuses, digests and the timeline are kept.

**Flag.** `VEDA_PROJECT_LIFECYCLE_ENABLED` is off by default. Every `/api/v1/projects` route answers 404 before
authentication while it is off. Production refuses it. It is coupled to no other flag. `/auth/me` reports it as
`features.project_lifecycle`, and the Projects navigation item needs both that feature and `project.view`. Turning it
off hides projects and changes no commercial behaviour; the acceptance hook only appends lineage for booked chains.

**API.** The API adds 29 routes under `/api/v1/projects`; OpenAPI shows nothing else changed.

## 17. Explicitly deferred workstreams

The following are not built here, and were not needed:

- procurement, purchase orders and supplier or vendor management;
- inventory, warehouse, BOM explosion, factory scheduling and machine planning;
- accounting, invoicing and payment collection or reconciliation (milestones are not payment milestones);
- workforce scheduling and timesheets;
- the customer project portal;
- warranty and service ticketing, feedback and review solicitation;
- WhatsApp or e-mail to customers;
- AI (B5) and 3D;
- a general workflow engine;
- employee performance analytics: lifecycle timestamps are stored reliably, and no person is ranked.

Documents other than images, as handover evidence, wait on the attachment policy.

## 18. Validation (SYNTHETIC)

| Suite | Coverage | Result |
|---|---|---|
| API integration (both engines) | Booking (all PLB-46 refusals); lifecycle, gates, four-eyes, scope; operations; seven concurrency interleavings; the PLB-47/48 scenario | Pass on SQLite and PostgreSQL |
| API unit | Pinned definition, undecided policy, classification coverage, vocabulary lengths, matrix invariants, erasure coverage | Pass |
| App unit (web-test-runner) | 13 project tests | Pass; full app suite 169 of 169 |
| Browser (Playwright) | `e2e/project.e2e.mjs`: the journey and every width (360, 390, 768, 1280 px), keyboard, focus, validation, overflow, 44 px targets, axe | 95 of 95 checks |

The full CI result is on PR #101.

## 19. Staging-validation plan (not started; nothing is enabled)

1. Merge after independent review. The next deploy of `main` applies migration `0208`, which is inert while the flag is
   off. Verify the migration head and conformance.
2. Owner records the policy decisions needed for validation (PLB-OD-01 to 04, 07 to 09) in a reviewed change to
   `fixtures/lifecycle-policy.json`, or explicitly accepts the strict defaults with HIGH moves refused.
3. A reviewed infrastructure change wires `VEDA_PROJECT_LIFECYCLE_ENABLED` to staging, false, with a DRAFT enablement
   record, following the pattern of decision log 33 and 38. The owner then approves the record (author and approver
   differ) and flips the flag.
4. Grant the operations, project-lead and quality personas individually.
5. Run the synthetic journey on staging, from an accepted synthetic quotation to handover, with screenshots and the
   API trail.
6. Rollback: set the flag false and redeploy. Projects stay in the database, inert.

## 20. Blockers

**Before staging enablement:**

- independent review of PR #101;
- the owner's lifecycle policy (PLB-OD-01 to 04 and 07 to 09), or explicit acceptance of the strict defaults;
- a reviewed staging wiring change with an approved enablement record;
- quotations must exist in staging as `ACCEPTED`, which needs OI-MTQ-11 (acceptance mechanism) and the issuance
  decisions.

**Before real operation:**

- every PLB-OD slot decided, including PLB-OD-10 (booking trigger and acceptance evidence, for example whether a signed
  copy must be attached), PLB-OD-11 (`THIRD_PARTY`), PLB-OD-12 (rework, cancellation, on-hold) and PLB-OD-13
  (customer-promised dates);
- the personas granted;
- the decisions behind real accepted quotations (OI-MTQ-07 to 11, 18);
- staff training on gates and evidence;
- handover evidence in PDF form needs the attachment policy.

**Before production:**

- a production decision for the flag (the API refuses it today);
- every staging blocker above, closed with evidence;
- the P0 production gates (RPO, RTO and retention values, OWNER-INPUT-001 to 003);
- the commercial flags (`VEDA_MTQ_*`, CQX), which are production-refused today: without accepted quotations there is
  nothing to book.
