# Warranty and after-sales service (WSV): discovery, design and design reviews

Owner instruction `VEDA-SPACES-STAGING-ACTIVATION-AND-WARRANTY-SERVICE` (2026-10-16), track B, decision log 47. One
branch (`feature/warranty-after-sales`), one PR, stacked on track A (decision log 46: PEX-D01, PEX-D02, CPP-D04).

## 1. Discovery: what exists, and its source of truth

| Concern | Existing capability | Source of truth | WSV extension | Customer-safe projection |
|---|---|---|---|---|
| What a customer accepted about warranty | The issued quotation freezes `warranty[]` (OI-MTQ-09 terms text), `service_support[]` (Veda Spaces' own service support, CQX-09, never merged with warranty), `terms_version`, and the information pack: `manufacturer_warranty_note`, `warranty_exclusions[]` (OI-MTQ-18 / Customer Promise) | The accepted quotation's frozen snapshot, verified by its digest | Copied verbatim into a frozen entitlement, per accepted quotation of the handed-over lineage, with number, version, `terms_version` and snapshot digest | The same text, verbatim, labelled by kind |
| Veda Spaces' published policy | The "Warranty, Service & Customer Care Policy" (`VEDA_WARRANTY_POLICY_URL`, linked from every estimate) states one year of free service from handover for workmanship and fitment issues; `docs/implementation/estimator/WARRANTY-RECONCILIATION.md` marks that row Resolved and every manufacturer period unresolved | A public web page; no versioned copy is bound to any customer's accepted document | Not turned into an entitlement automatically (its version at the customer's acceptance is not recorded). WSV-D01 lets the owner adopt its terms as structured classes by policy version and text digest, bound to the quotation `terms_version` values that carried them | The policy link is shown beside the statements; estimator copy is never an entitlement source (it is budgetary) |
| Structured terms (period, trigger) | None in any record bound to a customer | — | Owner register WSV-D01 (null) | While null: "Warranty period: see your accepted quotation and the Veda Spaces Warranty, Service & Customer Care Policy" (status `NOT_RECORDED`, never "covered") |
| What was handed over | PLB/PEX: the HANDOVER transition (`handover_on`, decision time, acknowledgement reference), the handover package and digest (with any portal acknowledgement), the accepted baseline lineage at handover | `project_transition`, `project_handover_package`, `project_baseline` | Read from the completed HANDOVER transition: sources come from its baseline lineage, the start date from its `handover_on` | Project/property reference only |
| Rooms and areas | `property_space` | MTQ | A request may name a space of the property | The space label |
| Customer identity and access | `portal_account`, `portal_access` per enquiry, `X-Veda-Portal`, RBX-010 | Portal | Every customer route resolves the property through the account's ACTIVE access, then the request within that property | — |
| Pre-handover issue reports | PEX `project_customer_report` → snags; the project refuses writes once handed over | PEX | Not reused: routing rule by `project.status` (ACTIVE → PEX report, HANDED_OVER → service request). PEX patterns reused (channel/account CHECK, key and request digests, customer-safe reply) | — |
| Evidence | Attachments (ATT): content-hash keys, scan, re-encode, variants, withdrawal, erasure; staff uploads only; entity bindings | `attachment` | Entity type `service_request` (CHECK widened). Customer photos through portal-owned routes (`attachments.service.create_for_portal`: no RBAC grant to any principal; the route authorises). Customer-visible staff evidence only by an explicit citation row (`customer_visible`, the CPP-D04 pattern) | Variants through a session-authorised route |
| Assignment | PLB team (`project_member`), the `eligible_user` pattern | PLB | Request owner holding `warranty.service.resolve` | Never a staff name |
| Commercial | Project Commercials (bound to the accepted lineage); MTQ variations exist only while a project is active | PCM | None. Chargeable post-handover service has no agreement mechanism: a missing integration; fail closed | "Not covered by your warranty; Veda Spaces will contact you" |
| Audit, outbox, notifications | Audit hook + registry; outbox + worker (one handler per event type); `send(template)`; `notify_in_app` | kernel/platform | Registered tables; new distinct event types; template `service_update` | "There is an update in your portal" |
| Erasure | Lead erasure cascade, `[erased]` redaction, digests kept; MTQ retains terms | per module | Request, note, assessment, resolution and visit free text redacted; frozen statements retained (contract terms, as MTQ retains them); photos erased by ATT; events hold no text | — |
| Flags | `config.Settings`, production refusals, `/auth/me` features | config | `VEDA_WARRANTY_SERVICE_ENABLED`, off, refused in production | — |
| Concurrency | Row lock + re-read, If-Match, unique keys, Idempotency-Key digests, the paused-request (Hold) harness | kernel | The project row lock for submission and registration; the request row lock for every command | — |

Searched for warranty, warranties, service, after sales, support, maintenance, AMC, customer care and complaint. Found
only quotation text, the published policy link, estimator copy and the reconciliation: no registry, ticketing, AMC or
complaint capability exists. Nothing is duplicated.

## 2. Design

### 2.1 Entitlement (`warranty_entitlement`, one per handed-over project)

**Registration** is asynchronous and idempotent, never in the handover transaction:

- the project's `project.handed_over` outbox handler calls the post-handover subscribers registered with the project
  module (`project.hooks`), each in its own savepoint, so a warranty failure never undoes a handover or its staff
  notification (one handler per event type is preserved);
- `POST /warranty/entitlements` (`warranty.manage`) registers a project handed over while the flag was off;
- both lock the project row, return the existing row if any (unique `project_id`; an `IntegrityError` in a savepoint
  returns the winner).

It is refused when the project is not HANDED_OVER or has no completed HANDOVER transition. A `handover_on` before the
handover package was prepared is frozen with a `date_check` flag shown to staff (the staff-entered date is the record;
refusing would leave the warranty unregistrable, since a completed handover cannot be edited).

**Frozen `terms`** (JSON + `terms_sha256`): for each accepted quotation of the HANDOVER transition's baseline lineage
(base and accepted variations): number, version, `terms_version`, the original snapshot digest, and verbatim
`warranty[]`, `service_support[]`, `manufacturer_warranty_note`, `warranty_exclusions[]`; the handover facts (transition
id, `handover_on`, decision time, package id and digest, portal acknowledgement date); `coverage[]` (WSV-D01 classes
that apply, see below); the WSV policy version and digest. Service contacts are not frozen (they go stale): the portal
shows the current published support contacts. Nothing is re-derived later. Erasure keeps the statements (contract
terms) and the original digest.

**WSV-D01 applicability.** A recorded class applies only when the accepted base quotation's `terms_version` is one the
decision lists (`applies_to_terms_versions`): bound to what the customer accepted, never to a date. A class whose
period conflicts with nothing is frozen; any class the owner marks as conflicting with a statement is frozen as
`NOT_RECORDED` with a `CONFLICT` note for staff.

**Status** (computed on read, in India's calendar, for a given date): `NOT_STARTED`, `ACTIVE` (start ≤ date <
start + months), `EXPIRED`, `NOT_RECORDED`. The only trigger is `HANDOVER` (start = `handover_on`), never a creation or
deployment time. The customer words are "Active", "Expired", "Not yet active", "Not recorded in your portal". An
entitlement is never shown as "covered": coverage of a request is a separate decision.

### 2.2 Service request

The customer chooses one of the property's handed-over projects (listed in a fixed order); the request belongs to that
project. Initial meaning: **the customer reported an issue**, nothing more. `reported_on` is frozen at submission and
coverage is judged as of that date.

States: `REPORTED`, `INFORMATION_REQUESTED`, `TRIAGED`, `ASSESSED`, `AWAITING_COMMERCIAL_AGREEMENT`, `IN_PROGRESS`,
`RESOLVED`, `CLOSED`. Every command validates actor, permission and scope, current state, If-Match (staff) or
idempotency (customer), and required fields; writes its rows; appends a text-free `service_event`.

| Command | From → to | Who | Rules |
|---|---|---|---|
| submit | → REPORTED | customer, or staff for them (`warranty.service.triage`) | Project HANDED_OVER; Idempotency-Key (digests); ≤ 10 open per account and project (count under the project lock); optional `related_request_id` (same property) |
| request information | REPORTED, TRIAGED, ASSESSED, IN_PROGRESS → INFORMATION_REQUESTED | triage | Customer-visible question; the state to return to is stored |
| add information | INFORMATION_REQUESTED → stored state | customer, or staff | Customer words; photos allowed |
| triage | REPORTED → TRIAGED | triage | Category, priority, space, internal note |
| assess | TRIAGED, IN_PROGRESS (after an inspection) → ASSESSED, AWAITING_COMMERCIAL_AGREEMENT, INFORMATION_REQUESTED or TRIAGED | `warranty.service.assess` | Needs a registered entitlement. One `service_assessment` row per decision (below) |
| assign | TRIAGED, ASSESSED, IN_PROGRESS, AWAITING_COMMERCIAL_AGREEMENT | `warranty.service.assign` | Owner active, HUMAN, holding `warranty.service.resolve` |
| plan visit | TRIAGED (INSPECTION only), ASSESSED → IN_PROGRESS; IN_PROGRESS | resolve (the owner) | Kind INSPECTION or SERVICE; SERVICE only when the latest assessment is COVERED; planned date entered by staff |
| record visit | IN_PROGRESS | resolve (the owner) | Done date (not future), customer note, internal note, evidence |
| resolve | IN_PROGRESS → RESOLVED | resolve (the owner) | Latest assessment COVERED; a SERVICE visit done; summary for the customer, internal note, evidence; one `service_resolution` row per cycle |
| confirm | RESOLVED → CLOSED (SERVICED, verified by CUSTOMER) | customer | Repeating it is a no-op |
| reject | RESOLVED → IN_PROGRESS | customer, with a reason | At most 2 per request; then refused ("please contact us") and staff verify |
| verify | RESOLVED → CLOSED (SERVICED, verified by STAFF) | `warranty.service.verify`, never the resolver | — |
| withdraw | REPORTED, INFORMATION_REQUESTED, TRIAGED, ASSESSED, AWAITING_COMMERCIAL_AGREEMENT → CLOSED (CUSTOMER_WITHDREW) | customer, or staff for them | — |
| close without service | open, not RESOLVED → CLOSED | assess | DUPLICATE needs `duplicate_of` (same property); NOT_COVERED, REFERRED_TO_MANUFACTURER and CHARGEABLE_NOT_AGREED need a latest assessment that says so; CANNOT_SERVICE needs both an explanation and an internal reason |
| reopen | CLOSED → TRIAGED | `warranty.service.verify` | Reason; cycle + 1; the coverage decision must be made again; reopening an open request is refused (a double click changes nothing) |

**Coverage assessment** (`service_assessment`, never inferred from the customer's words or photos): outcome, basis,
customer explanation, internal reason, assessor, time, as-of date (`reported_on`):

- `COVERED`: basis is an ACTIVE coverage class (as of `reported_on`), **or** a cited statement of `warranty[]` or
  `service_support[]` of the frozen entitlement (path and text digest stored). While no structured class applies, a
  citation also needs a `period_basis` (internal: why the request is within the cited statement's period). A
  manufacturer note, an exclusion or estimator copy is never a basis for COVERED.
- `MANUFACTURER_WARRANTY`: the problem is the manufacturer's to warrant (referral): never COVERED, never resolved as
  Veda work; closed REFERRED_TO_MANUFACTURER with the explanation.
- `NOT_COVERED` (an exclusion may be cited), `OUTSIDE_WARRANTY_PERIOD` (an EXPIRED class as of `reported_on`, or a
  cited statement with its `period_basis`), then the assessor chooses CHARGEABLE (→ AWAITING_COMMERCIAL_AGREEMENT) or
  NOT_SERVICEABLE (closed NOT_COVERED with the explanation).
- `INSPECTION_REQUIRED` (stays reviewable: INSPECTION visit, then a new assessment); `INSUFFICIENT_INFORMATION` (→
  INFORMATION_REQUESTED).

**Chargeable** service fails closed: the repository has no mechanism to agree and price post-handover work (Project
Commercials is bound to the accepted lineage; variations exist only while a project is active). A CHARGEABLE request
waits in AWAITING_COMMERCIAL_AGREEMENT, shown as "Not covered by your warranty; Veda Spaces will contact you about
it"; it can only be withdrawn or closed (CHARGEABLE_NOT_AGREED, or DUPLICATE / CANNOT_SERVICE with their own rules).
No visit can be planned and nothing can be resolved.

### 2.3 Text, history and erasure

`service_event` holds codes, ids, states, dates and digests only, and the database refuses UPDATE and DELETE (triggers
on both engines, as `project_event`). Free text lives in erasable rows referenced by id: `service_request` (customer
description, area), `service_note` (information requests and answers, rejection and reopen reasons, internal notes;
`visibility` CUSTOMER or INTERNAL), `service_assessment` (explanation, internal reason, period basis),
`service_visit` (customer and internal notes), `service_resolution` (summary, internal note). Erasure replaces those
fields with `[erased]`; rows, codes, dates and digests stay. The entitlement's frozen statements are retained.

### 2.4 Evidence

Customer photos: `service_request` attachments created through portal routes only (create, local content, complete,
read), ≤ 6 per request, only while REPORTED or INFORMATION_REQUESTED; recorded with the account on
`service_request_photo` in the same transaction; the attachment's `uploaded_by` is the public principal every portal
write runs as (as PEX reports), never granted any permission. Withdrawal: staff only, with a reason (binding rule
`VERIFIER_WITH_REASON`, `warranty.service.triage`). Staff evidence: staff upload to the request (ATT, normal RBAC) or
cite any available attachment of the lead; it is customer-visible only through a `service_evidence` row marked
`customer_visible` (never INTERNAL). Household visibility: every ACTIVE account of the enquiry sees the property's
requests, their photos and customer-visible evidence (as for PEX reports' delivery view). No URL is public.

### 2.5 Customer experience (existing portal: "Warranty & service")

Per handed-over project: the warranty summary (statements by kind, verbatim, with their quotation reference; coverage
classes and status when recorded; exclusions; the policy link), listed as a document (`WARRANTY_SUMMARY`, a
projection of the frozen entitlement, never called a certificate). Service history with plain status words and who
acts next; "Report a problem" (mobile-first, photos); per request: what we asked and their answer, the coverage
explanation, visits planned, the resolution, confirm or "still not right", withdraw. Before handover: "Warranty
details are confirmed at handover". Manufacturer warranty cards are handed over physically (promise matrix); they are
not in the portal (a limitation).

### 2.6 Staff experience

Navigation "Service" (`warranty.service.view`): queue (open, mine, waiting for the customer, awaiting verification,
awaiting commercial agreement), request page (customer words and photos, entitlement and statements, actions by state,
notes kept apart by visibility, timeline), and a Warranty panel on the project page (entitlement, register, requests).

### 2.7 RBAC

Nine codes, all scoped: `warranty.view`, `warranty.manage`, `warranty.service.view`, `.triage`, `.assess`, `.assign`,
`.resolve`, `.verify`, `.audit`. FOUNDER: all, ALL. No other role (not ACCOUNTANT, not SALES_MANAGER, not ADMIN).
OWN = the request's owner, or an active member of the project's team; triage personas need ALL (a new request has no
owner). Only FOUNDER can administer accounts holding these codes (the escalation guard).

### 2.8 Notifications

Distinct event types, one handler each, enqueued in the transaction of the change, customer ones only while warranty,
portal and lifecycle flags are on; the handler re-reads and sends nothing if the record moved on or access ended.
Customer email (`service_update`, no content) to the submitting account (portal) or the enquiry's primary customers
(staff-recorded): received, information requested, coverage decided, visit planned, resolved (please confirm),
closed. Staff in-app (holders of `warranty.service.view` in scope, and the owner): new customer request, customer
information added, resolution rejected.

### 2.9 Flag, migration, API

`VEDA_WARRANTY_SERVICE_ENABLED`: off, refused in production, not wired to staging, not enabled. Staff routes need it
and the lifecycle flag; customer routes also the portal flag. Migration `0214_warranty_service` (expand-only): eight
tables, immutable-event triggers, the attachment entity-type CHECK widened (SQLite: exact 0106 text guarded, stored
definition rewritten, schema version bumped, integrity check; PostgreSQL: NOT VALID then VALIDATE), sequence `VS-SR-`,
nine codes for FOUNDER. Staff (`present`) and customer (`customer`, allow-listed) projections are separate.

## 3. Design review 1 (self-challenge)

R1 invented promises → WSV-D01; R2 mutable history → frozen terms; R3 activation from creation → `handover_on`; R4
duplicate system → routing by project status; R5 isolation → property first; R6 public evidence → session routes; R7
auto-classification → assessor command; R8 arbitrary eligibility → basis required; R9 status editing → commands; R10
history loss → per-cycle rows; R11 blanket RBAC → FOUNDER only; R12 lifecycle coupling → hooks; R13 commercials →
fail closed; R14 races → locks and keys; R15 ERP creep → no scheduling, stock or billing.

## 4. Design review 2 (independent, fresh context): findings and dispositions

| # | Class | Finding | Disposition |
|---|---|---|---|
| 1 | Blocker | Discovery missed the published policy (one year from handover) and the reconciliation | Fixed: §1 lists them; WSV-D01 adopts the policy by version and digest; estimator copy never a source; customer wording points to the quotation and the policy |
| 2 | Blocker | COVERED by citing any source mixed manufacturer, service-support and exclusions | Fixed: only `warranty[]`, `service_support[]` or a class; MANUFACTURER_WARRANTY referral; exclusions only against coverage; path + text digest stored |
| 3 | Blocker | Portal uploads as ANONYMOUS through staff ATT code | Fixed: `create_for_portal` with no RBAC grant; portal-owned routes; staff-only withdrawal with reason; account on the link row; tests for another account and an unrelated public context |
| 4 | High | Handover-transaction hook | Fixed: subscribers of the existing `project.handed_over` handler in savepoints, plus the register command |
| 5 | High | D01 keyed on a date | Fixed: keyed on `terms_version`; conflicts frozen as NOT_RECORDED |
| 6 | High | "ACTIVE today" and asymmetric OUTSIDE | Fixed: as of `reported_on`; OUTSIDE by citation with basis; `period_basis` required for COVERED by citation |
| 7 | High | Events with text vs erasure | Fixed: text-free events, triggers, erasable text rows; statements retained |
| 8 | High | Close without service bypassed assessment | Fixed: per-code requirements |
| 9 | High | State machine gaps | Fixed: customer withdraw; AWAITING_COMMERCIAL_AGREEMENT; information from more states with return state; 2 rejections max; reopen to TRIAGED; SERVICE visits only after COVERED |
| 10 | Medium | Evidence binding contradictions | Fixed: portal rule in the route, binding open until closed; citation rows with `customer_visible` |
| 11 | Medium | Several projects per property | Fixed: the customer chooses; fixed order |
| 12 | Medium | No entitlement yet | Fixed: submission allowed; assessment refused (`ENTITLEMENT_NOT_REGISTERED`) |
| 13 | Medium | `handover_on` staff-entered | Fixed: decision time and acknowledgement frozen; a date before the package is flagged (`date_check`) rather than refused, because a completed handover cannot be corrected and refusal would make the warranty unregistrable |
| 14 | Medium | Warranty document undefined | Fixed: §2.5 |
| 15 | Medium | Notifications underspecified | Fixed: §2.8 |
| 16 | Medium | Co-owner visibility | Fixed: household (all ACTIVE accounts of the enquiry), tested |
| 17 | Low | Cap race; replay | Fixed: count under the project lock; confirm/withdraw replays are no-ops |
| 18 | Low | Lineage source; stale contacts | Fixed: the transition's baseline lineage; contacts not frozen |
| 19 | Low | RBAC notes | Recorded in §2.7 |
| 20 | Low | Migration guards | Fixed: §2.9 |
| 21–23 | Info | PEX routing; commercials; process | Recorded; decision log 47 added by this branch |
