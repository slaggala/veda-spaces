# Sales & Customer Acquisition Experience (SCA): design

**Instruction:** `VEDA-SPACES-SALES-AND-CUSTOMER-ACQUISITION-EXPERIENCE` (owner, 2026-10-17).
**Branch:** `feature/sales-customer-acquisition`, one PR. **Flag:** `VEDA_SALES_EXPERIENCE_ENABLED` (off everywhere; production refuses it).

## 1. What exists (reuse map)

Discovery of `main` found the whole customer lifecycle already built. Nothing below is rebuilt.

| Stage | Existing capability (source of truth) | Reused as |
|---|---|---|
| Public website | `app/e2e/site-release/` (staging site; `dist/` is the frozen production copy, WhatsApp-only) | Edited in place: calls to action, the journey page, the privacy notice, first-party funnel beacons |
| Estimator | ADR-012 engine, `POST /api/v1/public/estimates`, UX V1/V2 pages, ADR-013 catalog V3 | Untouched: the home page links to it; the result page links to the journey page |
| Lead capture | `POST /api/v1/public/leads` and `/public/enquiries` (Turnstile, honeypot, Idempotency-Key, consent, UTM attribution, `budget_estimate_lead_link`) | Untouched |
| CRM | `lead` (NEW → CONTACTED → SITE_VISIT → QUOTATION_SENT → NEGOTIATION → WON/LOST), `lead_activity` (PLANNED follow-ups, reminders every 5 minutes), `LEAD_SOURCE` and `LOST_REASON` lookups, dashboard, notifications | Extended with a derived sales progression; status still changes only through the lead's own service |
| Consultation | No entity. A COMPLETED `MEETING` activity is how a consultation is logged today; the estimator enquiry carries a consultation request | Read as evidence (documented interpretation, §3) |
| Site measurement | MTQ `measurement_visit` (REQUESTED → … → COMPLETED), which already moves the lead to SITE_VISIT | Read as evidence; the lead page links to the property |
| Quotation | MTQ `quotation` (DRAFT → … → ISSUED → ACCEPTED/REJECTED), which already moves the lead to QUOTATION_SENT and records the quoted amount | Read as evidence |
| Viewed, considering | CQX `proposal_access_grant` (`first_viewed_on`, `view_count`), `customer_proposal_request` | Read as evidence; "viewed" is reported as link-possession evidence, never as a decision |
| Accepted | CQX `quotation_acceptance_evidence` and B4 `record_decision` (quotation ACCEPTED) | Read as evidence: the authoritative acceptance; nothing else claims it |
| Won / lost | `lead.status` WON/LOST with `lost_reason` | Kept as the CRM closure; the derived stage shows ACCEPTED until staff close the lead |
| After acceptance | Project Lifecycle, Project Commercials, Project Execution, Customer Project Portal, Warranty and service, Customer Promise | Described to prospects on the journey page; demonstrated through the demo page with a synthetic model rendered by the real portal and proposal views |

## 2. Customer journey

VISIT (home page, calm hierarchy: one primary action, one secondary) → UNDERSTAND (services, how we work, "what happens after you choose Veda Spaces") → ESTIMATE (existing estimator, linked only when the deployment has it on) → TRUST (journey page; the warranty policy; the privacy notice behind the consent link) → ENQUIRE (existing consented form or the estimator's enquiry) → CONSULT, MEASURE, QUOTE, CONSIDER, FOLLOW-UP, ACCEPT/LOST (staff pipeline over existing records). A referral who calls is created manually by staff and enters the same pipeline with no estimate: every evidence fact is optional.

## 3. Derived sales progression (no second CRM)

`veda.modules.sales.stages` is a pure function of facts read from existing tables. Stages, in order of evidence:

| Stage | Evidence (any of) | Basis reported |
|---|---|---|
| NEW | nothing below | — |
| CONTACTED | lead status ≥ CONTACTED; a COMPLETED, non-system CALL, WHATSAPP, EMAIL or MEETING activity | `LEAD_STATUS` or `ACTIVITY` |
| CONSULTATION | a COMPLETED, non-system MEETING activity; a consultation requested through the estimator enquiry only marks the fact `consultation_requested` | `ACTIVITY` |
| SITE_MEASUREMENT | a measurement visit (any status but CANCELLED); lead status SITE_VISIT | `MEASUREMENT_RECORD` or `LEAD_STATUS` |
| QUOTATION_PREPARATION | a quotation row exists and none is issued | `QUOTATION_RECORD` |
| QUOTATION_ISSUED | an ISSUED, ACCEPTED, REJECTED or EXPIRED quotation; lead status QUOTATION_SENT | `QUOTATION_RECORD` or `LEAD_STATUS` |
| CUSTOMER_CONSIDERING | an issued quotation whose proposal link was opened (`first_viewed_on`), or a customer request; lead status NEGOTIATION | `PROPOSAL_RECORD` or `LEAD_STATUS` |
| QUOTATION_DECLINED | the latest base quotation is REJECTED and the lead is open | `QUOTATION_RECORD` |
| ACCEPTED | a base quotation ACCEPTED (B4 decision, any method) and the lead is still open | `QUOTATION_RECORD` |
| WON | lead status WON | `LEAD_STATUS` |
| LOST | lead status LOST | `LEAD_STATUS` |

Rules: the strongest evidence wins; a lead status can never move a lead past evidence that contradicts it (a WON lead with no acceptance still shows WON, basis `LEAD_STATUS`, so the funnel can tell both apart); nothing here writes to the lead. "Mark as won" and "Mark as lost" are the lead's existing status endpoint, offered from the pipeline when the evidence calls for them. The MEETING-equals-consultation reading is the only interpretation; it is documented in the pipeline's vocabulary and on the page.

Attention facts (deterministic, no inference): follow-up overdue; no planned follow-up on an open lead; last activity older than 14 days with nothing planned ("quiet"); unassigned; customer action pending (open customer requests, a proposal shared and never opened, accepted but not closed, declined but open).

## 4. Acquisition source and channel

The lead keeps its `LEAD_SOURCE` and UTM columns unchanged. `veda.modules.sales.attribution.channel()` derives one reporting channel from them, deterministically: REFERRAL (REFERRAL, ARCHITECT_PARTNER), DIRECT (PHONE, WALK_IN, WHATSAPP), SOCIAL (INSTAGRAM, FACEBOOK, or a website lead whose UTM or referrer names a social network), PAID (GOOGLE_ADS, or a website lead with a paid UTM medium), ORGANIC_SEARCH (a website lead with no UTM and a search-engine referrer), OTHER (any other UTM campaign or external referrer) and UNKNOWN (a website lead with no UTM and no referrer, or source OTHER). The raw source stays visible next to the channel. No marketing-attribution platform: one function, unit-tested.

## 5. Funnel measurement

- **Anonymous stages** (public visit, estimator started, enquiry started, journey viewed): `POST /api/v1/public/acquisition/events` (RBX-011) takes `{event, client, utm_source?, utm_medium?, referrer_host?}` (closed schema, 1 KiB body, per-IP limits, flag-gated). The server stores a daily count per `(day, event, channel)` and a `(day, digest)` row where digest = SHA-256 of client token, event and day, so a retry or a reload never counts twice; digests older than two days are purged on write. No IP, user agent, page URL or personal data is stored. The browser keeps a random token in `sessionStorage`, honours `navigator.doNotTrack`, and sends nothing when the page's `veda-acquisition-analytics` meta is empty (the committed site).
- **Estimates completed**: `budget_estimate` rows of PUBLIC origin (authoritative; the client never reports completion).
- **Lead stages**: counted from the facts of §3 over the cohort of leads created in the period (spam and deleted leads excluded).
- `GET /api/v1/sales/funnel?from&to` reports every stage with `basis` (`CLIENT_EVENT`, `AUTHORITATIVE`) and `tracking` (`TRACKED`, `NOT_TRACKED`: no beacon has ever been received; a tracked zero is `0`). Ratios are computed only when both ends are tracked and the denominator is positive; otherwise they are `null` with a reason. Channels, current open stages, lost reasons (including NOT_PROVIDED), quotation outcomes and "quiet" counts are included.

## 6. Staff workspace

- `GET /api/v1/sales/pipeline` (`sales.pipeline.view`, scope ALL or OWN mirroring the lead's OWN rule): one row per live, non-spam lead: lead, source and channel, stage and basis, facts, quoted amount (only to holders of `quotation.read`; otherwise withheld and marked so), owner, last meaningful activity, next and overdue follow-up, attention, links to the property, visit and quotation. Filters: stage, attention, channel, owner, search.
- `GET /api/v1/sales/leads/{id}/progression`: one lead's derived facts for the lead page's new card, which also links the lead to its property and visits (today the lead page has no such link) and offers "create property for this lead".
- `GET /api/v1/sales/funnel` (`sales.funnel.view`).
- Follow-ups and lost reasons reuse the lead's existing activity and status endpoints. The LOST_REASON lookup gains `NOT_PROVIDED` so staff never invent a reason.

## 7. Trust and the journey page

`/journey` on the site describes consultation → measurement → scope → quotation → acceptance → onboarding → commercial visibility → execution → quality checks → snags → handover → warranty and service, in customer words taken from capabilities that exist. The online portal and its execution views are described as "being introduced", because their flags are off in production. No count, rating, award, testimonial, duration or guarantee is stated; the only warranty statement is the existing policy's service sentence, linked to the policy. `/privacy` states, from the code, what the enquiry form and the beacons collect and how consent is withdrawn (owner legal review is an open item).

## 8. Sales demo

`GET /api/v1/sales/demo` (`sales.demo.view`) returns a deterministic synthetic model built from constants, never from the database: a portal property view and a proposal page model, every name, reference and contact marked DEMO or synthetic, dates relative to today. The staff page `/sales/demo` renders them with the real `<vs-portal-project-page>` content and `<vs-proposal-view preview>` under a persistent DEMO banner. Nothing is written, no customer row is read, and the demo cannot appear in any report because it has no rows.

## 9. RBAC, flag, isolation

- Permissions: `sales.pipeline.view` (FOUNDER, ADMIN, SALES_MANAGER: ALL; SALES: OWN), `sales.funnel.view` (FOUNDER, ADMIN, SALES_MANAGER), `sales.demo.view` (FOUNDER, ADMIN, SALES, SALES_MANAGER). ACCOUNTANT, DESIGNER, SURVEYOR and ESTIMATOR hold none.
- Flag: `sales_experience_enabled`; `/api/v1/sales/*` and `/api/v1/public/acquisition/*` answer 404 before authentication while it is off; `/auth/me` feature `sales_experience`; production refuses it. Not wired to staging infrastructure in this PR (as the warranty feature was not); enabling it is the owner's separate change.
- Customers hold nothing new. Public routes return no identifiers. Staff projections never return margins, costs, rates, internal notes or decision notes.

## 10. Migration

`0215_sales_acquisition` (expand-only, inert while the flag is off): `acquisition_event_daily`, `acquisition_event_seen`, the three `sales.*` codes, lookup value `LOST_REASON/NOT_PROVIDED`.

## 11. Out of scope (kept out)

Ads management, marketing automation, mass email, WhatsApp or SMS automation, payment gateway, AI scoring or profiling, fingerprinting, employee analytics, loyalty or referral rewards, CMS replacement, a customer entity, changes to the estimator engine or the quotation engine.
