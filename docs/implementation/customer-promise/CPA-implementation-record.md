# Customer Promise administration (CPA): implementation record

Instruction `VEDA-SPACES-CUSTOMER-PROMISE-ADMIN-PORTAL-END-TO-END` (2026-10-15), decision log 37. One branch
(`feature/customer-promise-admin`), one umbrella pull request, logically separated commits, one independent review at
the end. It follows PR #95 (Customer Quotation Experience) and PR #96 (customer completeness, OI-MTQ-18).

**Nothing in this workstream is Veda Spaces policy.** No contact, inclusion, responsibility, readiness rule, warranty,
service promise, duration, handover or care instruction, or payment wording is seeded. The portal holds structure
(sections, categories, states, workflow); people author the content, and other people review, approve and publish it.

## 1. Concept

The **Customer Promise Pack** is the customer information pack of PR #96 (`mtq_commercial/customer_pack.py`), turned
from an engineering-edited JSON slot into governed, versioned content that authorised staff manage in the workspace:

```
AUTHOR ──► REVIEW (per section) ──► APPROVE (four-eyes) ──► PUBLISH (atomic) ──► SUPERSEDE (by the next publication)
```

A published version is immutable. A quotation version freezes the published pack in force when it is drafted, and an
issued quotation never changes: publishing a newer pack changes only quotations drafted afterwards.

```
Pack v1 published → Q1 drafted and issued → Q1 freezes v1 (content_version CPP-1, digest-bound)
Pack v2 published → Q2 drafted and issued → Q2 freezes v2; Q1 renders v1, byte for byte, forever
```

## 2. Data model (migration `0207_customer_promise`, expand-only)

| Table | Holds | Never |
|---|---|---|
| `customer_promise_pack` | One version: `version_no`, `status` (DRAFT, IN_REVIEW, APPROVED, PUBLISHED, SUPERSEDED, DISCARDED), `origin` (NEW, REVISION, ROLLBACK), `based_on_pack_id`, `change_summary`, authoring `content` + `content_sha256`, per-section `contributors`, `review_round`, submitted/approved/published/superseded/discarded people and times, `approved_sha256`, frozen `published_content` + `published_sha256`, `superseded_by_pack_id` | edited after submission; deleted |
| `customer_promise_review` | A reviewer's decision (APPROVED or CHANGES_REQUESTED, comment required for the latter) on one section in one round, bound to the section digest | rewritten (append-only) |
| `customer_promise_event` | The version's history: DRAFT_CREATED, SECTION_UPDATED, SUMMARY_UPDATED, DRAFT_DISCARDED, SUBMITTED, SECTION_APPROVED, CHANGES_REQUESTED, RETURNED_TO_DRAFT, APPROVED, PUBLISHED, SUPERSEDED, PREVIEWED | rewritten (append-only) |

Partial unique indexes: one PUBLISHED version; at most one open version (DRAFT, IN_REVIEW or APPROVED); unique
`version_no`. Every table carries the platform's nine audit columns (identifier, created/updated by and on, soft-delete
columns, optimistic `version`) and is FULL-audited (every field change of a section save is in `audit_log`). The PR #96
content model is reused unchanged as the content schema: the published content *is* a `CustomerPack`, so the issued
document format and template (`mtq-quotation-document/2`, `mtq-quotation-html/3`) are unchanged.

## 3. Sections, areas and content rules

Twelve administration sections own the pack's fields (`customer_promise/sections.py`):

| Section | Pack fields | Edit capability | Sensitive (review needs `review.sensitive`) |
|---|---|---|---|
| Contact and support | `email_domains`, `contacts`, `support_escalation` | `contacts.edit` | no |
| Project inclusions | `project_inclusions` | `edit` | no |
| Customer responsibilities | `client_responsibilities` | `edit` | **yes** |
| Site readiness | `site_readiness` | `edit` | no |
| Site-dependent work | `site_dependent_work` | `edit` | **yes** |
| Warranty and service | `manufacturer_warranty_note` | `warranty.edit` | **yes** |
| Warranty exclusions | `warranty_exclusions` | `warranty.edit` | **yes** |
| Service guidance | `service_guidance` | `contacts.edit` | no |
| Handover | `handover` | `edit` | no |
| Care guidance | `care` | `edit` | no |
| What happens next | `next_steps` | `edit` | no |
| Payment safety | `payment_safety` | `payment_safety.edit` | **yes** |

The fourteen customer-facing areas of PR #96 map onto these sections (`AREAS`); *Veda Spaces service and workmanship
support* is not authored here: Veda Spaces' own commitments are contract terms (OI-MTQ-09 `service_support`, legal
review with that decision), so a manufacturer statement and a Veda commitment can never be merged in this portal. The
completeness view reports that area from OI-MTQ-09.

Content rules, applied server-side on **every save** (inactive entries included):

- the PR #96 copy rules: no money, percentages, durations or time promises (except a next-step stage's own approved
  `duration`), no e-mail or phone outside contact fields, no links, web addresses or QR codes, no bank, IFSC, UPI or
  card details, no unsupported claims. This workstream adds "lifelong" and "decade(s)" to the claim list;
- contacts: business channels only (`business_channel_approved` must be true), free-mail domains refused, and every
  e-mail on a named business domain;
- closed vocabularies for categories, responsibility states (REQUIRED, NOT_REQUIRED, TO_BE_CONFIRMED) and stages;
  stage order fixed; unique codes; a section body has exactly its fields (mass assignment refused).

Publication rules (`customer_promise/rules.py`, CPA-31), checked at submit, approval and publication: some content
exists and differs from the published version; business e-mail domains named before an e-mail is published; an
escalation route or service guidance has a support or service channel; no duplicate active stage or site-work
category; warranty exclusions qualify a warranty statement (the manufacturer note here, or OI-MTQ-09); the
manufacturer note does not describe Veda Spaces' own workmanship or warranty. **No section is required**: OI-MTQ-18
keeps every section optional (an empty section is shown "to be confirmed"); which sections a real-customer launch
needs is the owner's decision (§9).

Authoring conveniences: list order is the display order; an entry may be marked inactive (kept and still checked, not
published). Rich text is not offered: customer copy is plain text, escaped on every surface.

## 4. Workflow (`customer_promise/service.py`)

```
DRAFT ─submit─► IN_REVIEW ─(every changed section approved) approve─► APPROVED ─publish─► PUBLISHED ─► SUPERSEDED
  ▲   │discard        │ request changes on a section              │ return
  │   ▼               │                                           │
  │ DISCARDED         ▼                                           ▼
  └───────────────────┴───────────────────────────────────────────┘
```

- **Authoring.** Only a DRAFT is edited, one section at a time, with an explicit Save (no autosave). A new draft is a
  copy of the published version (REVISION), or of an earlier published version (ROLLBACK), or empty (NEW, first
  version only). One open version at a time.
- **Review.** Only sections that differ from the published version are reviewed. A reviewer approves a section or
  requests changes (section, comment, reviewer, time); a request returns the version to DRAFT and keeps every review.
  A review counts only for its round and only while the section is unchanged (digest).
- **Four-eyes (CPA-16), on every section.** Nobody reviews a section they saved, a version they submitted, or content
  they restored by a rollback; nobody approves a version they contributed to or submitted. Contributors are read from
  the stored list *and* the event trail, so clearing one does not open approval. There is no bypass in the UI or the
  API; emergency changes are new versions through the same path (§7).
- **Approval** binds `approved_sha256` to the content digest. **Publication** re-checks the digest, the reviews and
  every rule, then in one transaction marks the published version SUPERSEDED (row-locked) and the new one PUBLISHED with
  its frozen customer content (`content_version` `CPP-<n>`), its digest, the publisher and the approval references
  (review ids) in the PUBLISHED event.
- **Effective dating (CPA-32): immediate on publication only.** No scheduler exists for safe future activation, and
  none is added; scheduled publication is deferred.
- **Rollback (CPA-22)** never reactivates or edits an old version: start a draft from the earlier version, review,
  approve, publish. The creator counts as the author of every section the rollback restores.
- **No hard delete (CPA-34).** No delete route exists; an unwanted draft is DISCARDED with a reason.

## 5. Concurrency (CPA-28)

Every write sends `If-Match` with the version the user saw; a stale page gets 409 `VERSION_CONFLICT` and nothing
changes (missing `If-Match`: 428). Review, approval, return and publication re-read the version under a row lock on
PostgreSQL; the partial unique indexes make a second open draft or a second PUBLISHED row impossible. Forced
interleavings (`test_customer_promise_races.py`, SQLite and PostgreSQL): two publishers on one version, two
simultaneous new drafts, and conflicting reviews of one section each end with exactly one success.

## 6. Quotation binding and OI-MTQ-18 (CPA-23, CPA-24)

OI-MTQ-18 stays the governance boundary. It is recorded, by the owner through the register and a reviewed pull request
to `commercial-policy.json`, in one of two forms:

| OI-MTQ-18 | A quotation drafted now carries | Gate satisfied by |
|---|---|---|
| null (today) | no pack: every section "to be confirmed" | nothing |
| a `CustomerPack` (PR #96 form; tests) | that pack | the recorded pack |
| `{"source": "CUSTOMER_PROMISE_ADMIN", "register_reference": …, "decided_on": …}` | the **published** Customer Promise Pack, verified against its digest (`CUSTOMER_PROMISE_INTEGRITY_FAILED` otherwise) | only a published version; never a draft, submitted or approved one |

`quotations.terms_snapshot` copies the pack and a reference (`customer_promise`: pack id, version, digest, register
reference) into the version's terms; issue freezes it into the document (`content_version`, sealed by the snapshot
digest) and records the reference on the ISSUED event. Issue is refused with `CUSTOMER_PROMISE_SUPERSEDED` while a newer
pack is published than the one the version carries: revising the version takes the current pack and keeps staff's
choices whose codes still exist. Usage counts (quotation versions per pack, by status) are shown to staff; no customer
or quotation content is exposed in the portal.

## 7. Audit, emergency and recovery

- **Audit (CPA-27):** the event table (actor, action, version, section, time, reason or comment, digests; never copy,
  tokens or secrets), FULL `audit_log` rows for every insert and update of the three tables, and a `PERMISSION_DENIED`
  security event for every refused capability. The event history is shown to holders of `customer_promise.audit.read`.
- **Wrong content published:** publish a corrected version (or a rollback version) through the normal path. Issued
  quotations keep what they froze; drafts must be revised to pick up the correction (the issue blocker enforces it).
- **Integrity failure** of the published content: quotation drafting fails closed (`CUSTOMER_PROMISE_INTEGRITY_FAILED`);
  publish a new version. Investigate as a security incident (api-runbooks §8).
- **Switching the portal off:** `VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED=false` (every route 404). Quotations keep binding
  to the published pack while OI-MTQ-18 delegates to it; to stop that, the owner records OI-MTQ-18 otherwise.
- **Application rollback:** an image without migration 0207 cannot read the tables but never needs them; quotations
  carry their pack in their own terms and documents. Roll forward only (api-runbooks §2.4).

## 8. API and UI

Staff routes under `/api/v1/customer-promise` (404 unless the flag is on; production refuses the flag): landing,
vocabulary, versions (list, create, read, change summary), section save, submit, section review, approve, return,
discard, publish, preview (`PREVIEW / NOT PUBLISHED`, through the CQX customer projection; creates no quotation, link,
acceptance or commitment; recorded as PREVIEWED), and semantic changes (`/changes`: added, removed, changed field by
field, deactivated, reactivated, reordered, in words). Workspace: Commercial → Customer Promise (`/commercial/customer-promise`),
structured editors per section, review and approval screens, the diff, the customer preview at mobile, tablet and
desktop widths, completeness and history.

## 9. Deviations and deferred items

| Item | Status | Why |
|---|---|---|
| Customer-facing titles, applicability, acknowledgement flags per entry (CPA-03/04/09) | Not added | The issued document and template 3 have no slots for them; adding customer-visible fields is a template change (new template version, new golden digests) with no owner decision behind it. Category, order and active state are supported. |
| Separate Veda service/workmanship editor (CPA-08) | Governed by OI-MTQ-09 | Contract terms with legal review; duplicating them here would create two sources of truth |
| Manufacturer warranty facts from the catalogue (CPA-07) | Referenced, not duplicated | The CQX page already shows the frozen catalogue specification's warranty summary beside the note |
| Scheduled (future-effective) publication (CPA-32) | Deferred | No safe activation scheduler exists; publication is immediate |
| Standalone "supersede" capability | Folded into publish | Superseding without a replacement would leave no current pack |
