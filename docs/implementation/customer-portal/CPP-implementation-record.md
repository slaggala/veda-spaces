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
| `POST /api/v1/public/portal/sign-in` | 202, the same answer whether or not the email has access. Sends a link only to an ACTIVE account with ACTIVE access to a live enquiry, at most one a minute. |
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
- **Attachments.** None is customer-visible. The repository has no customer-visible attachment class, and site
  photographs and sketches are staff evidence (CPP-D04).
- **Payments, invoices, warranty documents and messaging** do not exist in the repository, so the portal has none.

## Owner decisions (none is assumed; the code fails closed while each is open)

| Slot | Decision | While undecided |
|---|---|---|
| CPP-D01 | Staging enablement: an enablement record and the staging wiring for `VEDA_CUSTOMER_PORTAL_ENABLED` | Off; every route 404 |
| CPP-D02 | Whether customers may decide on a quotation in the portal, and the evidence that binds it | Decisions only on the CQX secure link |
| CPP-D03 | Who may be given access (relationships) and by whom (the default grants above) | The CQX sharing roles; staff choose the relationship |
| CPP-D04 | A customer-visible document class (drawings, design files, handover documents) | No attachment is shown |
| CPP-D05 | Session lifetimes and sign-in link lifetimes | 30 min idle / 12 h absolute; 15 min link, 72 h invitation |
| CPP-D06 | Showing the assigned consultant's name when the issued quotation names no business contact | The consultant's name only, no contact channel |

## Found during this work (outside this change)

The PROPERTY and PROJECT number sequences share the prefix `VS-P-` (migrations 0200 and 0208). A property and a project
can therefore both be `VS-P-2026-000001`. The portal does not show project numbers, so it is unaffected, but staff
screens can show both. A separate change should give one of the two sequences its own prefix.
