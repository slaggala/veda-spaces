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
| Cross-customer access | A token resolves server-side, on every request, to one grant and one version; every reference (`L<n>`, `R<n>`) is resolved inside that version only; requests are visible only through the link that sent them (N4) | `test_cqx_security::test_one_customer_never_reaches…`, `test_cqx_requests::…private_to_the_recipient_kind`, `…never_inherits_an_earlier_holders_conversation` |
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

## 4. Findings register (independent certification of PR #95, and earlier review follow-ups)

Severity is as triaged in this remediation; it is not lowered to fit a test. Impact columns say whether the finding
blocks enabling that capability (or real customers, or production) while it is open. "Fixed" names the change.

| # | Finding | Severity | Viewing | Interaction | Acceptance | Real customers | Production | Status / correction or deferred requirement |
|---|---|---|---|---|---|---|---|---|
| N1 | Acceptance total computed from mutable line rows: a line's tax or amount changed after issue changed the accepted total while acceptance succeeded | High | — | — | Blocks | Blocks | Blocks | **Fixed**: the frozen document carries each optional item's price including GST; acceptance uses only frozen values and refuses (SNAPSHOT_INTEGRITY_FAILED) when any printed line, the total or a chosen item's value differs from the frozen document (`projection.frozen_values`) |
| N2 | Decision idempotency evaluated before validation; the page reused one key for Accept and Decline | Medium | — | — | Blocks | Blocks | Blocks | **Fixed**: validation (authority, version, digest, frozen values) first, then idempotency against a canonical request digest stored on the evidence; same key + other content → IDEMPOTENCY_KEY_REUSED; client keys per attempt and type, retired after a definitive answer |
| N3 | A zero line omitted from the frozen document could be chosen and accepted | Medium | — | Blocks | Blocks | Blocks | Blocks | **Fixed**: only lines printed in the verified frozen document are selectable or nameable (`projection.printed`) |
| N4 | A new link of the same recipient kind saw an earlier holder's requests and answers | Medium | — | Blocks | — | Blocks | Blocks | **Fixed**: requests are visible only through the link that sent them; sharing a conversation across links is an owner decision (CQX-owner-decisions §3, CQX-B11) |
| N5 | Choices, acknowledgements and requests checked state before taking the lock and did not re-read it (PostgreSQL race with acceptance, revocation, rotation) | Medium | — | Blocks | Blocks | Blocks | Blocks | **Fixed**: every customer mutation takes the property lock first and re-reads the link and quotation under it (`grants.locked`); forced-interleaving tests on both engines |
| N6 | An image without the template-v2 reader (the previous release) refuses quotations issued with v2 | Low | Pre-enablement: runbook reviewed | same | same | — | Blocks until a production release plan exists | **Documented (MC-2)**: roll-forward only once a v2 quotation exists; `api-runbooks.md` §2.4; compatibility test proves fail-closed refusal and recovery on roll-forward |
| N7 | CQX-D04 `retention_days` is recorded but not enforced: no job removes acceptance network evidence when it lapses | Medium | — | — | Blocks | Blocks | Blocks | **Open**: a retention job (or a decision that evidence follows quotation retention) before acceptance is enabled |
| N8 | The integrity refusal told customers "Veda Spaces has been notified", but no monitored alert exists | Low | — | — | — | Blocks (alarm) | Blocks | **Fixed** (claim removed); deferred: a monitored alarm on `ProposalIntegrityRefused` before real customers |
| N9 | The link token is kept in this tab's `sessionStorage` on the workspace origin: any script running on that origin (an XSS anywhere in the workspace) could read it, and it survives reloads in the tab | Low | — (synthetic staging) | — | — | Blocks | Blocks | **Open**: a dedicated proposal origin, or memory-only handling (re-open from the link after a reload), before real customers |
| N10 | Reference images cannot load on `/proposal`: the workspace CSP `img-src` excludes the API host | Low | Images stay off | — | — | Blocks images | Blocks images | **Open**: a reviewed, path-scoped `img-src` change for `/proposal` (as for V3) and catalogue media activation; until then only placeholders are shown |
| N11 | Customer-page focus and touch targets (history in §4.1): focus fell to the body after actions; small touch targets; nested `main`; offline/5xx/429 without retry; a failed choice stayed checked. Re-review residuals: focus on the body after a slow or retried initial load and after a retried action; error-summary links did not focus their control, which had no `aria-invalid`/`aria-describedby`; the touch-target check measured height only | Medium | Blocks while open | Blocks while open | Blocks while open | Blocks while open | Blocks while open | **Fixed** (§4.1; CI run 38677895154 green, browser journey 128/128): page-entry focus on the proposal title; retry keeps the initiating control; error-summary links focus their exact control, marked invalid and described by its error; touch targets checked for width and height |
| N12 | A request could be linked to an unissued version (named to the customer) | Low | — | Blocks | — | Blocks | Blocks | **Fixed**: only an issued, frozen newer version can be linked (VERSION_NOT_ISSUED) |
| R1 | Subject and cover note are staff text shown to whoever holds the link | Low | Staff guidance | — | — | Blocks | Blocks | Open: keep customer names out of them, or exclude them from the projection (owner choice) |
| R2 | The idempotency replay cache can return a just-created link's token to the same staff user for 24 hours | Low | — | — | — | Blocks | Blocks | Open (process memory only, same user) |
| R3 | A link to a lost or closed lead stays live until it expires or is revoked (no LEAD_CLOSED hook) | Low | — | — | — | Blocks | Blocks | Open |
| R4 | A refused request cannot record its own refusal or EXPIRED event (it rolls back) | Low | — | — | — | — | — | Open: the housekeeping job records expiry once scheduled |
| R5 | `customer-proposal-housekeeping` is **not scheduled** anywhere: link expiry is not recorded and staff are not reminded of expiring proposals | Low | Schedule before viewing | — | — | Blocks | Blocks | Open: schedule with the other maintenance jobs (enablement record prerequisite) |

### 4.1 N11 history (customer page focus and accessibility)

- **Original finding (independent certification of PR #95 before remediation):** focus fell to the body after customer actions;
  next-steps links, radios and the decision checkbox were under 44 px; the view nested a `main` inside the shell's
  `main`; an offline, 5xx or 429 failure (initial load or action) offered no retry; a choice that failed stayed checked.
- **First correction (PR #95 remediation, N11 commit):** focus returned to the initiating control, else its section heading; 44 px targets;
  one main landmark; retry for transient failures; radios re-synced with the server's state.
- **Focused re-review residuals (after the first remediation):** (1) after a slow initial load, or a retry after 500, 429 or a network
  failure, focus stayed on the body; (2) after a failed action's Try again, focus could fall to the body (the retry
  button replaced the remembered control and then disappeared); (3) error-summary links did not move focus to the
  invalid control, and the textarea exposed no `aria-invalid`/`aria-describedby`; (4) the browser touch-target check
  measured height only.
- **Final corrections:** (1) the proposal title (`h1#proposal-title`, `tabindex="-1"`, named by the proposal's subject)
  is the page-entry target: focus moves there only when the page as a whole changes to the proposal (initial, slow or
  retried load), never on the refresh after an action; (2) a retry keeps the original action's control; the Try again
  control stays on screen (aria-disabled, "Trying again…") while the retry runs, a failed retry focuses the error
  summary, a successful one returns focus to the initiating control or, when it is gone, its section heading (else the
  title); busy controls are `aria-disabled` or read-only instead of `disabled`, so a focused control keeps focus while a
  slow request runs, and a second action is refused until the first answers; (3) every field error links to its control
  (`data-field`), the control carries `aria-invalid="true"` and `aria-describedby="err-<field>"` (before any hint) with
  a unique inline error, editing the field clears its invalid state without moving focus, and an error about the
  request as a whole is plain text (no link that goes nowhere); summary links are 44 × 44 px; (4) the browser check
  measures width and height separately for every visible button, link, input (text, radio, checkbox), select,
  textarea, summary, acknowledgement, Try again and error-summary link, in three page states, and fails if any of these
  kinds was not measured.
- **Validation evidence:** frontend unit tests 143 passed (four new); browser journey `app/e2e/proposal.e2e.mjs`
  128/128 at 360, 390, 768 and 1280 px (page-entry focus after normal, slow, 500, 429 and offline loads; action retry
  after offline, 500 and 429; slow retry; error-summary navigation for textarea, text input, radio, acknowledgement and
  checkbox; axe in each error state; width and height separately); a mutation probe (next-steps links narrowed to
  30 px wide, 44 px tall) failed only the width check.
- **CI verification:** run 38677895154 (all six jobs green, including `browser e2e + axe` with the proposal journey
  128/128 and `app` with the unit tests) on the commit that carried these corrections with N11 still marked open.
- **Status:** **Fixed.** While it was open it blocked viewing, interaction, acceptance, real customers and production
  (Medium); it no longer blocks any of them. Remaining customer-page gates are other findings (N9 real customers,
  N10 images).

## 5. Accurate statements of current behaviour

- **Token storage:** the token is **not** held only in application memory. The page moves it from the URL fragment
  into this tab's `sessionStorage` (cleared when the tab closes; not shared with other tabs) and scrubs the address
  bar. Any script on the workspace origin could read it while the tab is open (N9).
- **No customer is notified** of anything, and no alarm is attached to integrity refusals yet: the customer is told
  only to contact their Veda Spaces representative (N8).
- **Link housekeeping is unscheduled** (R5): expiry is still enforced on every request against the clock.
- **Proposal images are unavailable** until N10 is resolved and catalogue media is activated; the page shows named
  placeholders.
- **Link possession is the only verification implemented.** Whether that suffices for a digital decision is CQX-D01.
- **Customer-directed notifications** need an approved channel and copy (CQX-B05).
