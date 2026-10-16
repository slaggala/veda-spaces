# Customer Project Portal: implementation record (decision log 41)

Branch `feature/customer-project-portal`. Built on main after PR #101 and PR #103. See the
[implementation map](CPP-implementation-map.md) for the existing capability each part reuses.

## What the customer gets

| Route | What it answers |
|---|---|
| `/portal` | Signed out: "email me a sign-in link". Signed in: each of their homes: what is happening, what comes next, what needs them, their quotation and who to talk to. |
| `/portal/sign-in` | The emailed link lands here; the one-time token is read from the URL fragment, scrubbed and exchanged for a session. |
| `/portal/properties/:id` | One home: status and next step first; what needs the customer; the journey (each step named Completed, In progress, Action required, Upcoming or Not yet available); the quotation; what's included room by room; what Veda Spaces has committed to; the customer's part; documents; contact. |
| `/portal/quotations/:id` | One issued quotation version in the CQX customer view, read-only. |

Every area has loading, empty, signed-out, not-found, unavailable and offline states. Nothing is filled in by the
browser: a value the server has no authoritative data for is shown as not yet available.

## API

Customer routes, RBX-010, `auth="public"`, all `no-store`:

| Route | Behaviour |
|---|---|
| `POST /api/v1/public/portal/sign-in` | 202, the same answer and the same work whether or not the email has access: it queues the keyed email hash. The outbox worker sends a link only to an ACTIVE account with ACTIVE access to a live enquiry, at most one a minute and 10 a day. |
| `POST /api/v1/public/portal/session` | Exchanges a link (single use, 15 minutes; an invitation 72 hours) for a session token returned once. |
| `POST /api/v1/public/portal/sign-out` | Ends the session. |
| `GET /api/v1/public/portal/home`, `/properties/{id}`, `/quotations/{id}` | The customer-authorised projection (`veda.modules.portal.projection`). |

Staff routes (bearer, lead scope):

| Route | Permission |
|---|---|
| `GET /api/v1/leads/{id}/portal-access` | `portal.access.view` |
| `POST /api/v1/leads/{id}/portal-access` | `portal.access.grant` |
| `POST /api/v1/portal-access/{id}/revoke` | `portal.access.revoke` |

Default grants: FOUNDER, ADMIN and SALES_MANAGER have ALL; SALES has OWN. These mirror the CQX sharing codes.

## Authorisation model

- **Who is a customer.** A `portal_account` (normalised email), never an `app_user`. Staff authentication refuses it,
  and the portal never reads a staff token.
- **What a customer reaches.** Only enquiries with an ACTIVE `portal_access` row that staff granted. Properties, then
  quotations, are reached through those enquiries' leads. Anything else answers 404, the same as a row that does not
  exist. Malformed identifiers are refused (422) before any lookup.
- **Every request** re-resolves the session (idle 30 minutes, absolute 12 hours) and re-reads the access rows.
  Revoking an enquiry's access applies from the next request. Revoking the last one ends the account's sessions.
- **No write path** from the portal to any business record. The only rows the portal writes are its own: session,
  sign-in and event.

## Quotation integration

The portal shows only versions issued to the customer: ISSUED, ACCEPTED, REJECTED, EXPIRED or SUPERSEDED, with a
frozen document. It never shows a draft, an internal review or an approval. Each version is rendered through the CQX
projection of the frozen, digest-verified document, the same one the secure link shows, and in the CQX customer state.
A version that no longer verifies is listed as "not available right now" and never shown. Estimates, BOQs, rates,
margins, lineage and staff fields are never read.

## Project progress

Consultation, site measurement, design and scope, quotation and approval come from lead, visit, measurement-set,
scope and quotation states. Execution, quality checks and handover come from the Project Lifecycle only while
`VEDA_PROJECT_LIFECYCLE_ENABLED` is on and a project exists. They use its Customer Promise stage, and the stage wording
frozen in the accepted quotation. Customer actions come through the classification allow-list (`CUSTOMER_ACTION`
fields only). Otherwise those three steps say "not yet available". The portal never reads, sets or bypasses that flag.

## Release

`VEDA_CUSTOMER_PORTAL_ENABLED`:

- off by default, and every portal route, customer or staff, answers 404;
- refused in production at configuration;
- reported in `/auth/me` as `customer_portal`;
- not wired to staging by this change.

## Limitations by design

- **Quotation decisions** (accept, decline, ask, choose optional items) stay on the CQX secure link. Its acceptance
  evidence binds the decision to that link. A portal decision channel needs an evidence change and owner decisions
  (CPP-D02).
- **Execution, quality and handover** are not shown while the Project Lifecycle is off, which it is everywhere today.
- **Attachments.** None is customer-visible unless staff explicitly publish it (CPP-D04, decided 2026-10-16; see
  "Customer documents" below). Site photographs and sketches otherwise stay staff evidence.
- **Payments, invoices, warranty documents and messaging** do not exist in the repository, so the portal has none.

## Owner decisions (none is assumed; the code fails closed while each is open)

| Slot | Decision | While undecided |
|---|---|---|
| CPP-D01 | Staging enablement: an enablement record and the staging wiring for `VEDA_CUSTOMER_PORTAL_ENABLED` | Off; every route 404. Decided for protected staging: owner approval of 2026-10-16 (decision log 43), with the record APPROVED and bound by its SHA-256. Production is not decided. |
| CPP-D02 | Whether customers may decide on a quotation in the portal, and the evidence that binds it | Decisions only on the CQX secure link |
| CPP-D03 | Who may be given access (relationships) and by whom (the default grants above) | The CQX sharing roles; staff choose the relationship |
| CPP-D04 | A customer-visible document class (drawings, design files, handover documents) | **Decided YES 2026-10-16 (decision log 46):** explicit publication only, below |
| CPP-D05 | Session lifetimes and sign-in link lifetimes | 30 min idle / 12 h absolute; 15 min link, 72 h invitation |
| CPP-D06 | Showing the assigned consultant's name when the issued quotation names no business contact | The consultant's name only, no contact channel |

## Independent review (before merge)

A fresh reviewer certified the branch with one merge condition. The findings and how each was handled:

| Finding | Handling |
|---|---|
| F1 (Medium, merge condition): after a lead erasure, the erased enquiry's access list still showed the name and email of a customer who kept access to another enquiry, and the account could keep a name copied from the erased enquiry | Fixed. An erased enquiry's access list shows no account identity. A surviving shared account takes its name from an enquiry it still has, and joins the erasure set so its audit history loses the earlier name. Tested. |
| F2: anyone who knew the email could void the 72-hour invitation, and the email rate limits were per network | Fixed. A sign-in request never cancels an invitation. Each account gets at most 10 sign-in links per 24 hours from any network (DB-backed). Tested. |
| F3: a known email's sign-in request takes measurably longer than an unknown one | Fixed. The request only computes the keyed email hash (the security-event HMAC) and queues one outbox row: the same work for every address, and the outbox holds the hash, never the address. The worker finds the account by `portal_account.email_hash` and applies every check, the one-a-minute gap and the daily cap. Tested. |
| F4: a declined or expired quotation got the headline "Your quotation is ready"; blockers waiting on Veda showed as customer actions; deleted rows were not filtered; a catch-all exception handler | Fixed. Tested. |
| F5: each quotation was verified several times per page | Fixed with a per-request cache. |
| F6: a docstring claimed no digest reaches customers; unused definitions | Fixed. The CQX projection's frozen-document digest is named. Unused definitions removed. |
| F7: access on a soft-deleted lead could not be revoked (it would return on restore) | Fixed. Revocation works within scope while the lead is soft-deleted. Tested. |
| Missing test: a link redeemed twice at once | Added on both engines (one session, one refusal). |
| Re-review N1 (Medium, merge condition): the F1 fix renamed a surviving shared account to the name of another enquiry it held, possibly someone else's | Fixed. The account records which enquiry its name was copied from (`name_source_lead_id`; null when staff chose the name). Only an account named from the erased enquiry is renamed: to the name of an enquiry it holds as primary customer, else the neutral "Customer". A chosen name is never touched. Tested. |
| Final review (Low): rotating `VEDA_EMAIL_HASH_HMAC_KEY` would silently stop sign-in emails for existing accounts | Fixed. `python -m veda.cli portal-rehash-emails` recomputes every account's lookup hash from its stored address (idempotent). Run it right after a rotation; see "Operations". Tested. |
| Final review (Low): the daily-cap test checked the email count loosely | Fixed. Exact again: the worker decides requests in order, and superseded links are never emailed. |
| Final review (Low, accepted): the outbox holds a keyed hash of every requested address, including ones with no account | Accepted. It is not reversible without the key, is bounded by the rate limits, and follows the security-event practice. |
| Final review nit: a fully erased account kept a pointer to the erased enquiry its name came from | Fixed. Erasure clears it, and replaces the email hash with the hash of the placeholder address. |
| Re-review N2: the enquiry's own consultant (OWN scope) still could not revoke on a soft-deleted lead | Fixed. The scope check sees soft-deleted leads. Tested with the consultant. |

## Operations

- **Rotating `VEDA_EMAIL_HASH_HMAC_KEY`:** deploy the new key to every process (API, worker, scheduler) first, then
  run `python -m veda.cli portal-rehash-emails`. Until then, sign-in requests for existing portal accounts still
  answer 202, but no email is sent.
  - A process still on the old key during a rolling restart can create an account with an old-key hash. Running the
    command again after the rollout corrects it; the command is idempotent.
  - Sign-in requests already queued in the outbox carry old-key hashes and match nothing. Those customers simply ask
    again.
- **The outbox worker** sends every sign-in email and also decides each sign-in request. If it is down, customers get
  no email until it recovers. Nothing is lost: requests and links wait in the outbox.

## Found during this work (outside this change)

The PROPERTY and PROJECT number sequences share the prefix `VS-P-` (migrations 0200 and 0208). A property and a project
can therefore both be `VS-P-2026-000001`. The portal does not show project numbers, so it is unaffected, but staff
screens can show both. A separate change should give one of the two sequences its own prefix.

## Project delivery (decision log 45)

With `VEDA_PROJECT_DELIVERY_PORTAL_ENABLED` on, the property page gains a `delivery` block (`project.delivery`). It
carries exactly two internal identifiers, the customer's own project id and handover-package id, because the
customer's two writes (report an issue; acknowledge a handover summary, both owner decision PEX-D01) are addressed by
them; both are reached only through the account's authorised property. No other internal id and never the project
number (the VS-P overlap above) reach the customer. With the flag off, the earlier rule (no project id at all) holds.

## Customer documents (CPP-D04, decision log 46)

The owner decided that the portal may show customer-visible project documents. Visibility is explicit, never inferred
from "the file belongs to the project":

- **Publication** (`project.publish_document`, FOUNDER by default; others individually): one site photograph of the
  project's own property (attached to the property or one of its spaces) that is scanned clean, available and not
  INTERNAL, as one class (progress photograph or handover photograph) with a title in customer words. Sketches, laser
  readings and floor plans are survey working material and are refused; no "approved drawing" class exists because no
  approval record exists for a drawing (it would present a draft as approved). Repeating the same
  publication changes nothing; the same file in another class must be withdrawn first. Withdrawal needs a reason and
  keeps the row (`project_customer_document`, migration `0213_customer_documents`); erasure redacts the title.
- **Customer view:** `documents` on the property page lists published, still available documents (class, title, date,
  size); never a file name, uploader, attachment id or lead. The bytes come only from
  `GET /public/portal/properties/{id}/documents/{id}/content` (RBX-010, variant `thumb`, `mobile` or `desktop`),
  which re-checks on every request the session, the account's access to the property, that the publication belongs to
  a project of that property and is still PUBLISHED, and that the attachment is still clean and available; anything
  else is 404, the same as an unknown id. Responses are `no-store`, `nosniff`, sandboxed.
- **Gate:** shown only while the delivery view (`VEDA_PROJECT_DELIVERY_PORTAL_ENABLED`, with the lifecycle) is on.
- **Other documents** stay their own modules' customer-safe projections: issued quotations (CQX), invoices and receipts
  (Project Commercials), the handover summary (PEX). Nothing internal (drafts, internal review versions, estimates,
  costs, supplier material, staff notes, QC discussion, audit exports) has a publication path.

