# Warranty and after-sales service (WSV): implementation record (decision log 47)

Branch `feature/warranty-after-sales`, stacked on track A (decision log 46). Design, discovery and the two design
reviews: [WSV-design.md](WSV-design.md). Owner decisions: [WSV-owner-decisions.md](WSV-owner-decisions.md).

## What exists now

| Capability | Where |
|---|---|
| Warranty entitlement (frozen at handover) | `warranty/entitlement.py`; `warranty_entitlement`; registered by the post-handover subscriber (`project/hooks.py`, called by the project's own `project.handed_over` handler in a savepoint) or `POST /warranty/entitlements` (`warranty.manage`); read `GET /warranty/projects/{id}`, `GET /warranty/entitlements/{id}` |
| Coverage status | Computed on read from the handover date and WSV-D01 classes (none while null): ACTIVE, EXPIRED, NOT_STARTED, NOT_RECORDED |
| Service requests and workflow | `warranty/requests.py`; `service_request`, `service_assessment`, `service_visit`, `service_resolution`, `service_evidence`, `service_note`; staff routes under `/service-requests` |
| Timeline | `service_event` (codes, ids, states, digests; UPDATE/DELETE refused by triggers on both engines) |
| Customer photos | `warranty/photos.py` + `attachments.service.create_for_portal`; entity type `service_request`; portal routes declare / upload (local) / complete / read; at most 6 per request, only while the customer is describing it |
| Customer view | `warranty/customer.py`, joined by `portal/projection.property_view` (`warranty`, documents `WARRANTY_SUMMARY`, Action Required) |
| Customer writes | `portal/routes.py` (RBX-010): submit, answer, confirm, still not right, withdraw, photos |
| Notifications | `warranty/events.py`: customer email `service_update` (six events, content-free), staff in-app (three events) |
| Erasure | `warranty/erasure.py` (redaction; rows, codes, digests and the frozen statements kept) |
| RBAC | `warranty/permissions.py`: nine codes, FOUNDER only |
| Flag | `VEDA_WARRANTY_SERVICE_ENABLED` (off, refused in production; effective only with the lifecycle flag, the portal flag for customers) |
| Staff UI | `app/src/modules/service`: "Service" navigation, queue and request page |
| Portal UI | `app/src/modules/portal/portal-service.ts`: "Warranty & service" |
| Migration | `0214_warranty_service` |

## Rules that hold

- **No invented promise.** The entitlement copies the accepted quotation's warranty and service-support statements,
  manufacturer note and exclusions verbatim, per accepted quotation of the handed-over lineage, with the snapshot
  digest. A period exists only from WSV-D01, and only for quotations whose `terms_version` the decision lists. With
  WSV-D01 null the customer reads "Not recorded in your portal" and "as stated in your accepted quotation and the
  Policy"; nothing is ever shown as covered as such.
- **History is never rewritten.** The terms are frozen with a digest at registration; a later policy never changes
  them; registration is idempotent; the start is the handover's own date.
- **A request is only a report** until an assessor decides coverage, as of the reported date, with a basis: an
  ACTIVE class, or a cited warranty or service-support statement with a recorded period basis. A manufacturer note
  or an exclusion never supports COVERED; a manufacturer's warranty is a referral.
- **Chargeable work fails closed** (no commercial agreement mechanism): AWAITING_COMMERCIAL_AGREEMENT, then withdrawn
  or closed; never a visit, never a resolution.
- **Commands only.** Each checks permission and scope, state, If-Match (staff) or idempotency (customer), and its own
  rules; every change appends a timeline event; nothing is deleted.
- **Verification** is the customer's confirmation or a staff verification by someone other than the resolver. Two
  customer rejections at most; then staff verify. Reopening needs a reason, starts a new cycle and a new decision.
- **Isolation.** Every customer route resolves the property through the account's access, then the request within
  it; an unknown, another customer's and a well-formed id of something else all answer 404. Images only through the
  session; no URL is public.

## Concurrency and idempotency

Submission takes the project's row lock (the open-request cap is counted under it) and an Idempotency-Key (digests
only; a different body with the same key is refused). Every request command takes the request's row lock and
re-reads; staff commands compare If-Match; confirm and withdraw replays are no-ops. Registration is unique per
project (a lost race returns the winner). Races tested with the paused-request harness on both engines: a retried
submission, staff verification against the customer's confirmation, a coverage decision against a withdrawal, two
registrations.

## Validation (SYNTHETIC)

| Suite | Result |
|---|---|
| `test_warranty_service.py`, `test_warranty_coverage.py`, `test_warranty_security.py`, `test_warranty_integrity.py` | Pass on SQLite and PostgreSQL |
| Schema, public-route register, config (production refusal) | Pass |
| App unit (web-test-runner) | 209 of 209 |
| Browser journey `warranty.e2e.mjs` | 50 of 50 (360, 390, 768, 1280 px; keyboard; 44 px; axe) |

The full CI result is on the PR.

## Independent review (fresh context, before merge)

No merge blocker. Regression tests: `test_warranty_review_fixes.py` (both engines).

| Finding | Handling |
|---|---|
| H1 (High): a statement citation could decide COVERED (or OUTSIDE) while a recorded class said otherwise | Fixed: whenever a structured class is recorded for the reported date, decisions must use the class (`CLASS_REQUIRED`); a statement citation always needs its period basis. Tested |
| H2 (High): visits were not tied to a cycle, so earlier work satisfied a new decision or a rejected resolution, and one inspection allowed repeated re-assessments | Fixed: `service_visit.cycle`; resolve needs a SERVICE visit of the cycle planned after the latest decision and the latest rejection; re-assessment needs an inspection planned after the decision that asked for it; earlier-cycle visits cannot be recorded or cancelled. Tested |
| M1: closing left planned visits | Fixed: closure cancels them (timeline event); `cancel_visit` needs an in-progress request. Tested |
| M2: staff could not see the customer's photos | Fixed: thumbnails on the request page through the staff attachment route (needs `attachment.read` on the customer's record; otherwise a "no preview" note) |
| M3: races untested for several operations | Fixed: confirmation against rejection, two reopens, the post-handover subscriber against the staff command, a failing subscriber isolated; the 6-photo limit is decided under the request lock (sequential test) |
| L1: a photo declared earlier could be completed after the request closed | Fixed: the portal upload and completion routes refuse a request the customer is no longer describing. Tested |
| L2: non-canonical citation paths | Fixed: one canonical spelling (digits, no leading zeros). Tested |
| L3: date defaults used the UTC date | Fixed: India's date in both UIs |
| L4: a photo upload error disappeared; excess photos dropped silently | Fixed: the error stays; the confirmation says how many were sent |
| L5: the home card's attention count missed service actions | Fixed |
| L6: an inactive owner could be notified | Fixed: only an active owner still holding `warranty.service.view` |
| L7: a repeated citation with a different visibility was ignored silently | Fixed: `EVIDENCE_ALREADY_CITED`. Tested |
| L8, L9: documentation | Fixed (closure exits from AWAITING_COMMERCIAL_AGREEMENT documented) |
| Informational: content-addressed upload keys reachable by the public principal | Accepted: the same keying as staff uploads; completion verifies length and digest and re-encodes; knowing another upload's SHA-256 is required |
| Informational: `request_sha256` kept after erasure | Accepted: a digest, not text (as PEX reports) |
| Informational: rejections count across cycles; WSV-D01 read at registration time | Accepted as designed; recorded here |

### Focused re-review (fresh context)

Every finding above CLOSED, verified also by reverting each fix and seeing its test fail (the cycle filter in
`done_since` duplicates the timestamp rule). Verdict: certified for merge. New items:

| Finding | Handling |
|---|---|
| Medium: the tests used the UTC date while visits and reports use India's date (red between 18:30 and 24:00 UTC) | Fixed: `tests.support.warranty.india_today` |
| Medium (pre-existing): an inspection planned before the first decision left the request unassessable | Fixed: assessment follows such an inspection once it is done. Tested |
| Low: a leftover planned visit could be cancelled only while in progress | Fixed: cancellable in any open state but RESOLVED |
| Low: the project handover checks "future" against the UTC date | Recorded: a project-module inconsistency outside this workstream |
| Low: the home card computes the warranty view per property | Accepted: bounded by the account's properties; only with the flag on |

## Limitations

- WSV-D01 is null: no warranty period is recorded or computed anywhere; staff cite statements with a period basis.
- Chargeable post-handover service has no agreement mechanism (a missing integration with Project Commercials /
  quotations): it fails closed.
- Manufacturer warranty cards are handed over physically; they are not in the portal.
- No scheduling: a visit is a planned date agreed with the customer and its outcome.
- No reminders (no scheduler is enabled); six customer emails only.
- The flag is not wired to staging and is not enabled anywhere; staging validation needs an owner instruction, and a
  handover on staging needs PLB-OD-01…03.

## Release

Nothing is enabled. Production refuses the flag. PLB-OD-01…13, PEX-D01/D02, CPP-D04 and PCM-D01/D02 are unchanged.
