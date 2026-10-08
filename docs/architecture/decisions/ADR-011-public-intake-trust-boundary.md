# ADR-011: Public lead intake across the Cloudflare Access trust boundary

- **Status:** **Proposed.** Not accepted, not implemented. It needs an owner decision (§8). `public_intake` stays
  `disabled` until then.
- **Date:** 2026-10-07
- **Follow-up:** R7 of the AUT-202 to AUT-204 evidence
  ([record](../../release-evidence/AUT-202-204-STAGING-FRONTENDS/README.md))

## 1. Context

Today every staging host is behind Cloudflare Access, and Access is enforced twice:
- **At the edge:** the Access application "Veda staging" covers `api-staging`, `staging`, `app-staging` and both
  `*.pages.dev` projects.
- **At the origin:** `cloudflared` requires a valid Access token for the team and application on **every** request
  (`infra/host/cloudflared.yml`, `access.required: true`). Every other hostname gets 404.

The API itself does not check the Access identity. It relies on `cloudflared`, on listening only on `127.0.0.1:8000`,
and on the host having no inbound rule.

The staging site reaches the API with **credentialed CORS** (`VEDA_PUBLIC_SITE_CREDENTIALS`, staging only; production
refuses it). The browser must hold the API host's Access cookie, so after signing in a user opens the API host once.

**Public intake** means an anonymous visitor submits the form, so `POST /api/v1/public/leads` must be reachable without
Access, while everything else stays behind it. That changes the trust boundary.

What already protects the public route, whatever the network path:
- Turnstile with a hostname check;
- idempotency checked before Turnstile;
- a honeypot (a hit stores the lead as spam for review);
- per-IP rate limits (client IP from `CF-Connecting-IP`, trusted only from the configured proxy);
- a body size limit and a closed schema;
- consent recorded with the policy version;
- logs mask personal data and tokens.

## 2. Options

| | Option | How | Pros | Cons |
|---|---|---|---|---|
| **A** | **Dedicated intake hostname** (recommended) | New host `intake[-staging].vedaspaces.com` on the same tunnel, **no** Access application. Its `cloudflared` rule forwards only `POST`-bearing path `^/api/v1/public/leads$` to the API; any other path on that host gets 404. `api[-staging]` keeps Access required on every path | The boundary is a hostname, in the reviewed `cloudflared.yml`, testable offline. An Access misconfiguration cannot open other routes. No Access path-precedence rules | A new DNS name and a site build pointing at it; one more CORS origin pair |
| B | Path bypass on the API host | An Access application for `api…/api/v1/public/` with a **Bypass** policy, plus a `cloudflared` path rule without `access.required` before the host rule | No new hostname | Relies on Access path-specificity and on rule order in two places; a mistake in either opens more than one route; harder to test offline |
| C | Pages Function proxy with an Access service token | The site calls its own `/api/…`; a Function forwards with a service token | No anonymous path at the origin | The API sees the proxy, not the browser: per-IP limits and Turnstile `remoteip` break; a service-token secret in Pages; rejected for staging on 2026-10-07 for the same reasons |

## 3. Decision (proposed)

**Option A.** Concretely:
1. **`cloudflared.yml`:** a rule for the intake host, `path: ^/api/v1/public/leads$`, service `http://127.0.0.1:8000`,
   **without** `access`. Then a rule sending everything else on the intake host to `http_status:404`, placed before
   the existing API-host rule (which keeps `access.required: true`) and the final 404.
2. **API, defence in depth:** a request whose `Host` is the intake host and whose route is not `/api/v1/public/*`
   gets 404 before any handler. Even a future `cloudflared` mistake cannot expose the workspace API through it.
3. **CORS:** the intake host serves only the public route.
   - The public-site origin gets **no credentials** in every environment, because no Access cookie is involved any
     more. Staging then sets `VEDA_PUBLIC_SITE_CREDENTIALS=false`, and the staging site build drops
     `credentials: 'include'`.
   - The staff application is unchanged: Access, credentials, its own origin.
4. **Edge rate limit:** a Cloudflare rate-limiting rule on the intake host path, so a flood is absorbed before the
   origin. The API's per-IP limits stay.
5. **Turnstile:** unchanged widget hostnames (the public site hosts). The API keeps checking the siteverify hostname.
6. **Production intake** additionally needs the production site's `veda-api-base` and site key set, which are
   committed empty today (`test_public_intake_disabled`), plus a new owner decision record.

## 4. Impact assessment

| Area | Change | Pipeline | Size |
|---|---|---|---|
| `infra/host/cloudflared.yml`, `render-edge.sh` | Intake rules (host from a new SSM config value); offline tests | Deploy bundle; `12-deploy` | Small |
| SSM config (`staging-platform.json`, `staging-core` `main.tf`) | `VEDA_INTAKE_HOST`; `VEDA_PUBLIC_SITE_CREDENTIALS=false` | **One** plan/apply | Small |
| DNS | `cloudflared tunnel route dns veda-staging intake-staging.vedaspaces.com` (one proxied CNAME); no Access application for it | Owner | Tiny |
| API | Host guard middleware; config validation (an intake host must be public HTTPS; production requires it when intake is enabled); tests | CI; `12-deploy` | Small |
| Staging site build (`staging-build.mjs`) | `veda-api-base` → the intake host; no credentials meta | CI; Pages | Tiny |
| Cloudflare | Edge rate-limit rule on the intake path | Owner (dashboard) | Tiny |
| Runbook | §6.5/§6.6 updated; validation rows (anonymous POST works on the intake path, 404 elsewhere, Access still on the API host) | Docs | Small |
| Monitoring | Existing intake metrics and `PUBLIC_INTAKE_BLOCKED`; add an alarm on intake 429/422 spikes | Plan/apply (same batch) | Small |

**Not affected:** the staff application, Access on `api`, `staging`, `app-staging`, data model, SES, and backups.

## 5. Security implications

| Threat | Before | After (Option A) | Control |
|---|---|---|---|
| Anonymous access to workspace routes | Blocked at the edge and the origin | Still blocked: the intake host forwards one path only; the API host keeps Access | `cloudflared` path rule plus 404; **API Host guard** (second layer); offline tests of both |
| Spam and bot submissions | Only Access users | Anyone can try | Turnstile (hostname-checked), honeypot to spam review, idempotency, per-IP and edge rate limits |
| Volumetric abuse / worker exhaustion (siteverify waits up to 5 s) | n/a | New | Edge rate limit before the origin; per-IP limits; body limit; gunicorn worker count and timeout; alarm on intake errors |
| Client IP spoofing (limits, evidence) | n/a | Attempted through headers | `CF-Connecting-IP` honoured only from the trusted proxy (`kernel/net.py`); Cloudflare overwrites the client-supplied value |
| Cross-site request with staff cookies | Credentialed CORS on public routes in staging | Removed: the public route never takes credentials | `VEDA_PUBLIC_SITE_CREDENTIALS=false`; production already refuses it |
| Host-header confusion | n/a | Requests to other routes via the intake host | Edge routing by hostname; API Host guard returns 404 |
| Personal data in logs | Masked | Unchanged; more volume | Existing masking (emails, phones, tokens) |
| Configuration regression | n/a | A future edit could widen the path | Offline tests pin the exact path and the 404; plan guard extended to the intake rule |

**Residual risk:** the API process is reachable anonymously on one route, so a parser or framework bug on that route
is exposed. Mitigations: the closed schema, the size limit, and the dependency audit and image scan gates.

## 6. Implementation proposal (when accepted)

1. **PR-1 (code, no behaviour change while disabled):**
   - API Host guard and config validation;
   - `cloudflared.yml` intake rules, rendered only when `VEDA_INTAKE_HOST` is set;
   - staging build switch;
   - tests: offline `cloudflared` rule tests; Host guard (public route allowed, every other route 404 on the intake
     host); CORS without credentials; production config checks.
2. **PR-2 (infra, one plan/apply):** `VEDA_INTAKE_HOST`, `VEDA_PUBLIC_SITE_CREDENTIALS=false`, and the intake alarm.
3. **Owner:**
   - DNS route for the intake host;
   - edge rate-limit rule;
   - confirm that **no** Access application covers the intake host, and that `api-staging` still requires Access.
4. **Validation (staging):**
   - anonymous POST to the intake path gets 201 with a real token, 422 with a forged one;
   - anonymous requests to any other path on the intake host get 404;
   - anonymous requests to `api-staging` get a 302 to Access;
   - the staff app is unchanged;
   - an edge rate-limit test;
   - `13-evidence`.
5. **Owner decision record:** enable public intake (staging first; production separately), then the production site
   change.

**Rollback:** remove `VEDA_INTAKE_HOST` and re-run `12-deploy`. The intake rules are not rendered, and the host
returns 404 from `cloudflared`.

## 7. Consequences

- The trust boundary becomes "Access everywhere except one path on one dedicated host", enforced in the repository
  (`cloudflared.yml`), at the origin (the API Host guard), and at the edge (no Access application on that host, plus
  the rate limit).
- Staging stops needing credentialed CORS for the form, which also removes the cookie warm-up for it.

## 8. Owner decisions needed

1. Accept Option A (or B or C).
2. Intake hostnames (`intake-staging`, `intake`).
3. Scope: staging rehearsal first, production later (recommended), each with its own decision record.
4. Edge rate-limit thresholds.
5. The lead retention period (OWNER-INPUT-002) before real public data is collected.
