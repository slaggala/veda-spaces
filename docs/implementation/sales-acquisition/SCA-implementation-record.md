# Sales & Customer Acquisition Experience: implementation record

**Instruction:** `VEDA-SPACES-SALES-AND-CUSTOMER-ACQUISITION-EXPERIENCE` (owner, 2026-10-17). **Decision log:** 48.
**Branch:** `feature/sales-customer-acquisition` (one PR). **Design:** [SCA-design.md](SCA-design.md). **Owner items:**
[SCA-owner-decisions.md](SCA-owner-decisions.md).

## 1. What was built

| Area | Change | Where |
|---|---|---|
| API module | `veda.modules.sales`: vocabulary, channel attribution, stage derivation (pure), fact gathering (batched reads of lead, estimator, MTQ, quotation, proposal and project records), pipeline projection, funnel report, beacon recorder, synthetic demo, routes | `api/veda/modules/sales/` |
| Flag | `VEDA_SALES_EXPERIENCE_ENABLED` (`sales_experience_enabled`): off everywhere, 404 before authentication on `/api/v1/sales/*` and `/api/v1/public/acquisition/*`, refused in production, exposed to the workspace as feature `sales_experience` | `api/veda/config.py`, `platform/identity/service.py` |
| RBAC | `sales.pipeline.view` (FOUNDER, ADMIN, SALES_MANAGER: ALL; SALES: OWN), `sales.funnel.view` (FOUNDER, ADMIN, SALES_MANAGER), `sales.demo.view` (FOUNDER, ADMIN, SALES, SALES_MANAGER); ACCOUNTANT, DESIGNER, SURVEYOR, ESTIMATOR hold none | `modules/sales/permissions.py`, `platform/rbac/registry.py` |
| Public route | `POST /api/v1/public/acquisition/events` (RBX-011): closed 1 KiB schema, per-IP and aggregate limits, 204, no data | `modules/sales/routes.py`, `app.py` RBX register, `docs/architecture/06-rbac.md` |
| Migration | `0215_sales_acquisition`: `acquisition_event_daily`; the three codes; lookup `LOST_REASON/NOT_PROVIDED` | `api/migrations/versions/` |
| Staff app | `/sales` pipeline, `/sales/funnel`, `/sales/demo`; a sales-progression card on the lead page with links to the property and visits; navigation behind the feature | `app/src/modules/sales/`, `core/router/routes.ts`, `core/authz/permissions.ts` |
| Site | `/journey` ("What happens after you choose Veda Spaces"), `/privacy` (the notice the consent box cites), first-touch attribution and the anonymous beacon (`assets/acquisition.js`), the home page's calls to action and "after you choose" panel, links from the estimator's thank-you screens, sitemap entries | `app/e2e/site-release/` (the production `dist/` is untouched) |
| Build and local stack | `STAGING_SALES_EXPERIENCE=on` fills the beacon meta; the estimator meta on the home and journey pages follows `STAGING_ESTIMATOR`; the local static server fills them in flag-on mode | `app/scripts/staging-build.mjs`, `app/e2e/static-server.mjs`, `app/e2e/run-all.sh` |

Not changed: the estimator engine and pages' scripts, the quotation and acceptance rules, the lead's status machine,
the customer portal and proposal behaviour, every production artefact.

## 2. Reuse map

```
PUBLIC WEBSITE  (site-release: calls to action, journey, privacy, beacons)
      ↓
ESTIMATOR       (ADR-012 engine and pages, unchanged; linked only where on)
      ↓
LEAD / CRM      (public intake, lead, activities, follow-ups, lost reasons; unchanged; +NOT_PROVIDED)
      ↓
CONSULTATION    (a logged MEETING activity)            ┐
MEASUREMENT     (MTQ measurement visits)               │ read by the sales module,
QUOTATION       (MTQ quotation issue, decision)        │ never written
VIEWED / ASKED  (CQX proposal links and requests)      │
ACCEPTED        (B4 decision, CQX acceptance evidence) ┘
      ↓
WON / LOST      (the lead's own status endpoint, offered from the pipeline)
      ↓
DELIVERY        (project, commercials, execution, portal, warranty: shown to prospects on /journey and in the demo)
```

## 3. Evidence

Filled at the end of the workstream (see the PR description for the final run references): targeted suites, the
full API suite on both engines, the app checks, the browser journeys and axe, and the CI run of the PR.

## 4. Independent review and disposition

**Design review (before implementation):** 24 findings, none a blocker. Disposition:

| Finding | Disposition |
|---|---|
| Dedupe table vs in-memory (1, 2) | In-memory de-duplication kept and documented with its weaknesses; counts reported as CLIENT_EVENT, indicative |
| Beacon duplicates the catalog analytics (3) | The browser reuses the estimator's `veda-client` session token; the catalog's release-scoped analytics stay separate (different scope) |
| Dashboard vs funnel conversion (4) | Funnel ratios are cohort ratios with definitions in the response; the difference is documented |
| Misleading ratios (5) | Site-visit ratio uses website enquiries; estimator ratio defined as able to exceed one; DUPLICATE and SPAM closures excluded from lost; tracking starts at the first beacon day, with `partial` |
| Latest-version selection (6) | `quotation_issued` is true for any base version ever issued; the current quotation is the accepted one, else the issued one, else the latest |
| Status-vs-record gaps (7) | REQUESTED and NO_SHOW visits stated; a staff-logged SITE_VISIT activity counts as measurement evidence (basis ACTIVITY); the funnel no longer infers a measurement from QUOTATION_SENT |
| `consultation_requested` (8) | Dropped; the MEETING reading documented as broader than ADR-012 D2 |
| Consent withdrawal and erasure (9) | No follow-up facts on a do-not-contact lead; anonymised leads excluded from the pipeline |
| Scan limit (10) | Documented; owner and search filters in SQL |
| Attribution mis-mappings (11) | `referral` medium → OTHER, `organic` medium → ORGANIC_SEARCH, WhatsApp referrer → DIRECT; first-touch attribution kept per session and sent with beacons and the home-page enquiry |
| Demo rendering (12) | The portal project page's content is driven by the supplied view; proposal rendered in preview mode; money as labelled text |
| Governance records (13, 14, 15) | Decision log 48, RBX-011 row, pinned public-route list, feature maps, governance and build tests, reference-content guard (pages link to the contact section) all updated |
| Pricing leakage (16) | None found; confirmed by tests |
| Public hardening (17, 18) | Aggregate limit added; Global Privacy Control honoured; staging credentials sent |
| Path, coupling, performance, a11y, copy (19-24) | Path corrected; coupling and performance addressed (lookup cache, one derivation per lead); mobile and a11y stated and tested; the existing "within one working day" sentence kept; booking-never-closes-the-lead stated |

**Implementation review (fresh context, after implementation):** 12 findings, no merge blocker. Disposition:

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | HIGH | The day's first beacon per (event, channel) created an audited row carrying the request's IP address and user agent, against the privacy notice | Fixed: the row is written as the web-intake actor without IP or user agent; a test asserts no audit row of the table carries either |
| 2 | MEDIUM | Pipeline search bypassed the CRM's tokenised, escaped search | Fixed: the pipeline reuses the lead repository's search condition; tests for multi-word and wildcard input |
| 3 | MEDIUM | Counter insert and increment could race across worker threads and answer 409 | Fixed: the database step runs under the module lock with a savepoint and one retry; the session digest is remembered only after a successful flush |
| 4 | LOW | Privacy notice silent on the catalog estimator's own staging counts | Fixed: a sentence in section 3 |
| 5 | LOW | A `whatsapp` campaign source was SOCIAL while a WhatsApp referrer or source is DIRECT | Fixed, with a test case |
| 6 | LOW | First-touch attribution was merged field by field with the current page | Fixed: the stored touch is used whole and replaced only when it had no campaign and a later page has one |
| 7 | LOW | Funnel definition said anonymised leads are excluded; the query did not | Fixed in the query |
| 8 | LOW | The lead page requested the progression where the feature is off | Fixed: the card stays silent unless the session's feature map says the feature is on |
| 9 | LOW | The demo page nests the proposal's and portal's own h1 inside its own | Not changed: the embedded views are the real customer screens rendered unchanged; recorded as a known limitation |
| 10 | LOW | Two journey sentences described portal-only or staging-only capabilities as universal | Fixed: snags are raised through your contact; payments are invoiced and receipted |
| 11 | INFO | "No obligation" and the unnamed retention period are owner legal items | Recorded under SCA-OD-01 |
| 12 | INFO | Memory bound of the de-duplication set | Commented in code |

**Focused re-review of the fixes (fresh context):** the audit-actor, lock, savepoint and retry paths were verified (including a forced insert race on SQLite); four follow-ups, all applied: the privacy notice now states exactly what the catalog estimator's own counts do (not one per session; Do Not Track only), a paid campaign tag outranks a WhatsApp source, the insert-race retry has a repository test, and the pipeline search test exercises escaping and the every-word rule. Not changed, recorded for the catalog module's owners: the catalog's staging-only analytics write their first daily count per subject under the request actor, so that audit row carries the request's IP address and user agent (staging only; production refuses the flag).
