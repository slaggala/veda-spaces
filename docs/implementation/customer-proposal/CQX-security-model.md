# Customer Quotation Experience: security and privacy model

Instruction VEDA-SPACES-CUSTOMER-QUOTATION-EXPERIENCE-END-TO-END, step CQX-13. Code: `api/veda/modules/customer_proposal`,
`app/src/modules/proposal`. Every control below has a test; the test file is named in the last column.

## 1. Trust boundary

A customer has **no account and no staff session**. They hold one secure link to one issued quotation version. Staff
RBAC is never used for customers, and customer access never grants a staff permission.

| Actor | Credential | Reaches |
|---|---|---|
| Customer (recipient of a link) | 256-bit opaque token in the link's URL fragment, sent only as the `X-Veda-Proposal` header | The customer-safe projection of exactly one version; their own requests and acknowledgements; **only the PRIMARY_CUSTOMER link** chooses optional items (one shared set per version) and makes a digital decision (`vocab.DECIDING_KINDS`; widening it is an owner decision) |
| Staff | Bearer session (existing auth) + `proposal.*` permissions within lead scope | Sharing, previews, customer activity, evidence, revocation |
| Anyone else | none | `404 PROPOSAL_LINK_INVALID`, rate limited |

## 2. Threats and controls

| Threat | Control | Test |
|---|---|---|
| Token leakage through URLs, logs, proxies, `Referer` | The token lives in the fragment (never sent to a server); the page moves it to this tab's `sessionStorage` and scrubs the address bar at once; it travels only in a header; request logs record the route, never headers; `Referrer-Policy: no-referrer` | `test_cqx_access`, `test_cqx_notifications_audit::…never_hold_a_token`, `proposal.e2e.mjs` |
| Token theft from the database | Only `SHA-256(token)` is stored; the token is shown to staff once | `test_cqx_access::…token_is_never_stored` |
| Brute force / enumeration | 256-bit tokens; strict format check; one refusal for missing, malformed and unknown; refusals count against a per-address budget (20/minute) besides per-address and per-link read/write limits; no identifier is accepted anywhere in the customer API | `test_cqx_security::test_guessing_links_is_rate_limited_per_address`, `test_cqx_access::…same_safe_404` |
| Cross-customer access | A token resolves server-side, on every request, to one grant and one version; every reference (`L<n>`, `R<n>`) is resolved inside that version only; requests are visible only to the same quotation and recipient kind | `test_cqx_security::test_one_customer_never_reaches…`, `test_cqx_requests::…private_to_the_recipient_kind` |
| Stale or forwarded links | Link expiry (1–30 days), immediate revocation, rotation, supersession when a newer version is shared; a forwarded link opens the proposal for whoever holds it, so the projection carries **no customer name** and a digital decision needs the owner's verification decision CQX-D01 | `test_cqx_access`, `test_cqx_projection` |
| Superseded or expired quotation | Shown with its state and no actions; choices, acknowledgements and decisions refuse anything not OPEN | `test_cqx_overview`, `test_cqx_optional_items`, `test_cqx_acceptance` |
| Replay / double submission | `Idempotency-Key` on requests and decisions; choices idempotent by state; one evidence row per version (unique index) | `test_cqx_requests`, `test_cqx_acceptance::test_duplicate…` |
| Unauthorised optional-item changes | Only the link holder, only optional lines of the open version, explicit states; the quotation never changes | `test_cqx_optional_items` |
| Forged acceptance / wrong version / tampered content | Version number and frozen-document digest bound to the request; the document's own digests verified first; choices and displayed total re-derived server-side; fail closed on every undecided owner policy | `test_cqx_acceptance::test_acceptance_is_bound…`, `…tampered_superseded_expired_and_revoked…` |
| XSS through customer text | Closed schemas; control characters stripped; length limits; stored as typed; rendered only through escaping templates (Lit); no server-side HTML from customer text | `test_cqx_requests::…sanitised…`, `app/test/proposal.test.ts` (markup shown as text) |
| CSRF | No cookies are read or set on customer routes (no ambient credential); the custom header forces a CORS preflight, which only the app origin passes | `test_cqx_security::test_cors_csrf_surface_and_headers` |
| Insecure caching | `Cache-Control: no-store, max-age=0`, `Pragma: no-cache`, `X-Robots-Tag: noindex` on every customer response | same |
| PII in logs and notifications | Outbox payloads and proposal events hold ids and codes only; staff notification titles carry the quotation label only; no customer-directed message is sent | `test_cqx_notifications_audit` |
| Media leakage | Images only from the catalogue V3 public view (approved, scanner-clean, rights checked at delivery) and only while V3 media is served; never part of the frozen document | `test_cqx_specifications_media` |
| Denial of service | Rate limits per address and per link; 16 KiB request bodies; at most 50 open requests per link; view events written at most every 15 minutes per link | `test_cqx_security::test_oversized…`, `test_cqx_access::test_access_events…` |
| Internal pricing exposure | Two allow-lists (B4 document model, CQX projection) with a field-classification inventory enforced by tests; unit rates only if OI-MTQ-10 allows; proposal permissions give no rate or lineage access | `test_cqx_projection`, `test_cqx_security::test_staff_permissions_are_least_privilege` |
| Error disclosure | Safe, fixed messages; no identifiers; platform error handler (no stack traces) | `test_cqx_access` |

## 3. Privacy and retention

- Personal data on CQX rows: request text, staff answers, requested quantities, optional recipient labels and, only if
  CQX-D04 permits, the address and device of an acceptance. All are registered as personal data in the audit registry
  and erased with the lead (`customer_proposal.erasure`), which also revokes every live link at once.
- Customer messages are not retained after lead erasure. Commercial evidence (digests, decision, version, totals)
  follows the quotation's retention.
- No email, phone number or name is stored on CQX rows.

## 4. Known limits (owner decisions or later changes)

Independent review follow-ups, tracked before any flag is enabled: the subject and cover note are staff text shown to
whoever holds the link (keep customer names out of them); the idempotency replay cache can return a just-created link
to the same staff user for 24 hours (process memory only); a link to a lost lead stays live until it expires or is
revoked (no LEAD_CLOSED hook yet); a refused request cannot record its own EXPIRED/refusal event (housekeeping records
expiry once it is scheduled).


- **Link possession is the only verification implemented.** Whether that suffices for a digital decision is CQX-D01.
- **Reference images on the proposal page** need the API host in the workspace `img-src` for `/proposal` only (a
  reviewed, path-scoped change like the V3 one, `app/scripts/staging-build.mjs`); until then a referenced image is
  blocked by CSP and the page shows its named placeholder. Catalogue media delivery is off in staging anyway.
- **Customer-directed notifications** need an approved channel and copy (CQX-B05).
