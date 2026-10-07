# Staging frontends, DNS, Turnstile and the end-to-end lead flow: evidence (AUT-202 to AUT-204)

**Result: VALIDATED** on 2026-10-07. The staging site and the staff application run on Cloudflare Pages behind
Cloudflare Access. A lead submitted on the staging site reaches the API through the tunnel, is stored, notifies staff
in the application and by email, and is visible in the staff application. A forged Turnstile token is refused.
`public_intake` stays **disabled**: no anonymous visitor reaches any staging host (runbook §6.6).

| Item | Value |
|---|---|
| Account, region | `veda-staging` (813238078849), ap-south-1 |
| Host | `i-01538ad0e744faaff` |
| Code | `main` at the merge of PR #40 (deployed image: the merge of PR #38) |
| Access | Team `kite-relay`; application "Veda staging"; one Allow policy (owner and staff); login by One-time PIN |
| Runbook | [§6.6 Staging frontends behind Cloudflare Access](../../operations/staging-platform-runbooks.md) |

## 1. Status

| Story | Status | Evidence |
|---|---|---|
| **AUT-202** DNS and SES DKIM | **Done** | §3 |
| **AUT-203** Turnstile | **Done** | Real widget; the site key on the pages, the secret only in SSM; invalid token refused, valid accepted (§4) |
| **AUT-204** Staging frontends on Pages | **Done** | Two Pages projects behind Access; staging builds point at the staging API only (§2, §4) |
| End-to-end lead validation | **Passed** (8 of 8) | §4 |

## 2. Changes and runs

| PR | Change |
|---|---|
| #37 | Staging-only credentialed intake (`VEDA_PUBLIC_SITE_CREDENTIALS`, refused in production); `staging-build.mjs`; runbook §6.6 |
| #38 | `12-deploy` re-run of a commit already pushed reuses its image (immutable tags) |
| #39 | The staging build refuses a Turnstile **secret** key as the site key (incident I1) |
| #40 | The host may send to verified SES sandbox recipients (`identity/*@*`), never naming them |

| Run | Workflow | Result |
|---|---|---|
| 37614935078 / 37615204046 | `10-infra-plan` / `11-infra-apply` | 1 added: `config["VEDA_PUBLIC_SITE_CREDENTIALS"]` |
| 37615544288 | `12-deploy` | Deployed; `api.env` 35 settings |
| 37617854362 | `12-deploy` | **Refused** at the push (immutable tag). Fixed in PR #38 |
| 37620395797, 37633713745 | `12-deploy` | Deployed; the second reused its image (`already pushed (immutable tag): reusing it`) and loaded the rotated Turnstile secret |
| 37656026045 / 37656501460 | `10-infra-plan` / `11-infra-apply` | 1 changed: the host policy gains `identity/*@*` |

Plans were made with `workflow_dispatch`. A plan started by the merge (`push`) was refused by the apply gate once, as
designed, and a `push` plan holding the concurrency slot was cancelled.

## 3. DNS, SES and Access

**DNS (zone `vedaspaces.com`, read 2026-10-07):**

| Record | Content | Proxy |
|---|---|---|
| `api-staging` | Tunnel `veda-staging` | Proxied |
| `staging` | CNAME `veda-staging-site.pages.dev` (Pages custom domain) | Proxied |
| `app-staging` | CNAME `veda-staging-app.pages.dev` (Pages custom domain) | Proxied |
| `<token>._domainkey.staging` ×3 | CNAME `<token>.dkim.amazonses.com` | DNS only |
| `www` | CNAME `veda-spaces.pages.dev` | Proxied (unchanged) |
| `@` | CNAME `veda-spaces.pages.dev`, flattened (restored; incident I3) | Proxied |
| MX ×5, SPF TXT, Google verification TXT | Google Workspace | **Unchanged** (compared before and after) |

**SES:** `staging.vedaspaces.com` identity `SUCCESS`, DKIM `SUCCESS`, sending enabled. The account is in the sandbox
(200 a day, verified recipients only). The owner address is a verified recipient. SES statistics: 3 delivery
attempts, 0 rejects, 0 bounces, 0 complaints (two diagnostic probes and the lead notification).

**Access:** every staging host and both `*.pages.dev` projects require the Access login (checked anonymously and in
fresh browser sessions). The CORS settings of the application allow `https://staging.vedaspaces.com` and
`https://app-staging.vedaspaces.com` with credentials; Access answers the preflight (OPTIONS not bypassed).

## 4. End-to-end validation

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Browser reaches the staging site | Pass | Access login (email and code), then the site |
| 2 | Turnstile renders | Pass | Real widget (Managed); site key in the page, 24 characters |
| 3 | Lead submission succeeds | Pass | `201`, reference `Z0H9-NY4R`; a second lead at 17:10:48 UTC, `201` |
| 4 | API receives the lead | Pass | Request log: `POST /api/v1/public/leads` `201` |
| 5 | Database stores the lead | Pass | `VS-L-2026-000001`: source Website, created 7 Oct 2026 20:42 IST, consent `2026-09-v1` |
| 6 | Notification generated | Pass | In-app "New enquiry" and the email to the verified owner address, from `no-reply@staging.vedaspaces.com`, after PR #40 |
| 7 | Lead visible in the system | Pass | Staff application (Founder, MFA): lead list, dashboard and lead page |
| 8 | No production dependencies | Pass | Page source names `https://api-staging.vedaspaces.com` only; no `api.vedaspaces.com` (staging builds refuse it); sender is the staging subdomain |
| – | Invalid Turnstile token refused | Pass | `422 CAPTCHA_FAILED` at 17:14:37 UTC, `PUBLIC_INTAKE_BLOCKED` / `BLOCKED`, no lead |

The forged-token request was sent from the host to the API on loopback (SSM Run Command), so it tested the API's
siteverify check directly, without Access.

The first staff account was created with `bootstrap-founder --email-link` (SSM Run Command, `BOOTSTRAP_FOUNDER`
`SUCCESS`) and accepted the same evening.

## 5. Incidents

| # | What happened | Exposure | Remediation |
|---|---|---|---|
| I1 | The Turnstile **secret** key was set as the site key in both Pages projects and published in the staging page | Access-authenticated users only | Secret rotated; new secret in SSM (`alias/veda-stg-data`); site key corrected; deployments with the secret deleted; API redeployed. PR #39 refuses a secret-length key |
| I2 | The Founder invite link was written to `/veda/staging/app`: `bootstrap-founder` prints it, and the container's output is shipped to CloudWatch. The SSM output was redacted, the container log was not. It was also read during diagnosis | Readers of the log group, until used (1 hour, single use) | Accepted within the hour, so the token is spent. Follow-up R2 |
| I3 | The apex `vedaspaces.com` had **no** DNS record: the Pages custom domain was never verified | `vedaspaces.com` did not resolve; `www` was unaffected | Apex CNAME added for the verifying custom domain (now Active, SSL); "Apex to www" 301 rule deployed. Whether it existed before 2026-10-07 is unknown (audit log not checked) |

## 6. Findings and remaining blockers

| # | Item | Follow-up |
|---|---|---|
| R1 | SSM parameter edit, Run Command and the SES probes used `OrganizationAccountAccessRole` (org-admin with MFA), not the runbook's `bootstrap-owner` owner session. The Session Manager plugin cannot be installed on the owner's managed Mac, and the console shell took no input | Record the console route in the runbook, or provide a supported workstation |
| R2 | `bootstrap-founder` prints the invite link to a logged stream (I2) | Print only the user ID, or write the link to a root-only file, when `--email-link` is used |
| R3 | The invite email failed before PR #40 and its outbox event is now dead (`outbox_dead_events count=1`) | Resolve or archive the dead event, so `outbox_dead` returns to 0 |
| R4 | The Cloudflare setup (Pages projects, Access hostnames and CORS, Turnstile widget, Bulk Redirect not used) is manual | Keep runbook §6.6 as the record; re-check after any dashboard change |
| R5 | SES is in the sandbox | Production access is an owner request before any real recipients |
| R6 | AUT-201 A2 (`ss -p` in `veda-collect`) and A3 (stale scan exception); RR-14 F1–F3 | Open |
| R7 | A browser must open the API host once after signing in, so the Access cookie exists for credentialed calls | Documented (§6.6); acceptable for staff-only staging |

**Not done here:** public intake (owner decision: disabled); SES production access; the full lead-flow runbook §8
(SES failure drill, replication, snapshot and anchor checks); `13-evidence` for this change.

**Verdict for a customer staging demo:** ready **for a demo to staff or a customer added to the Access policy**. The
lead flow, notification and staff view work end to end. Anonymous public intake remains intentionally disabled.
