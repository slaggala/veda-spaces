# Post-validation hardening A2: Cloudflare runbook hardening and the stale scan exception (R4, R6-A3)

**Scope:** follow-ups R4 and R6-A3 of the AUT-202 to AUT-204 evidence. Documentation and one scan-gate configuration
change. No infrastructure, no Cloudflare change, no change to public intake or the trust boundary.

## 1. R4: runbook §6.6 hardening

Every incident and stumble of the 2026-10-07 setup is now a step or a check:

| Lesson | Runbook change |
|---|---|
| A staging page could be briefly public between the first build and Access | Create each Pages project **without** the site key, so the first build fails; add Access, then the domain, then the key, then **Retry deployment** |
| Access hostnames for `*.pages.dev`: the domain list shows only existing projects; `veda-spaces.pages.dev` (production) was nearly chosen | Two rows per project (empty and `*` subdomain) on its own `<project>.pages.dev`; **never `veda-spaces.pages.dev`**; "Switch to custom input" |
| "Preview deployments" is not where the dashboard puts it | Settings → Build → Branch control → Preview branch: None |
| Access CORS: credentials were off by default; the browser error was cryptic | Allow-Credentials **on** (with the exact browser error), explicit origins, OPTIONS not listed, Bypass OPTIONS off |
| I1: the Turnstile secret was used as the site key | Site key (about 24 characters, public) vs secret (about 35 characters, SSM only); the build refuses a secret-length value (PR #39); the rotation procedure, including deleting old deployments |
| I3: the apex record was missing; the custom domain stayed "Verifying" | Add exactly the CNAME the verifying domain shows (empty name = `@`), proxied; validation of the apex and its 301 |
| DKIM: the DNS records are in the main dashboard, not Zero Trust | Path and record format; `dig` MX/TXT before and after |
| A managed workstation cannot install the Session Manager plugin; the console shell took no input | Owner route: console as `org-admin` → switch role; Parameter Store edit keeping `alias/veda-stg-data`; SSM Run Command; `aws login` troubleshooting; CloudTrail names `OrganizationAccountAccessRole`, so note it in the evidence |
| Shared private-window sessions made a protected host look open; a corporate network reset TLS | Validation in a fresh private session; network caveat |
| The Cloudflare setup is not in the repository | Re-run the validation table after any dashboard change |

New validation rows: the site key in the page, the Access login on every host including `pages.dev`, the apex and its
redirect, and the SES identity.

## 2. R6-A3: stale scan exception removed

`12-deploy` warned that the staging exception for CVE-2026-102010 (`gcc-14` 14.2.0-19) matched no finding: the image
no longer reports it (AUT-201 evidence, A3). A stale exception widens the gate for nothing, so it is removed.

| File | Change |
|---|---|
| `infra/config/image-scan-exceptions.json` | Two exceptions remain: CVE-2026-95619 (`gcc-14`) and CVE-2026-85091 (`zlib`) |
| `docs/operations/image-scan-exceptions.md` | Table updated; removal noted |
| `infra/tests/run.sh` | The committed set is exactly the two; coverage and production refusal counts adjusted; **new check:** CVE-2026-102010 is refused if it reappears |

## 3. Validation

- `make -C infra check`: 828 passed, 0 failed.
- Mutation: with the old exceptions file restored, the committed-set check and the new R6-A3 check fail.
- Docs governance test: pass. Secret scan: no new candidates.

## 4. Residual risk

- If a rebuilt image reports CVE-2026-102010 again, `12-deploy` stops until it is re-reviewed. That is intended.
- The Cloudflare configuration stays manual (owner decision: no Cloudflare API token). The runbook is the record;
  drift is caught only by re-running its validation table.
