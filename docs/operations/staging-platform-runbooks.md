# Staging platform runbooks (AUT-102 … AUT-111)

Operating the staging platform built by `infra/terraform/envs/staging-core`. **Nothing here has been run**: the
platform is not applied, Veda is not deployed and public lead intake is disabled. Every procedure becomes evidence
the first time it runs (§5). Review: [consolidated review package](../implementation/staging/STAGING-PLATFORM-review-package.md).

Roles: **owner session** = the bootstrap owner role (MFA, Mumbai-only session policy, runbook staging-bootstrap §3);
**workflows** = `10-infra-plan`/`11-infra-apply` (`veda-gh-plan`/`-apply`), `12-deploy` (`veda-gh-deploy`),
`13-evidence` (`veda-gh-evidence`), each behind its protected environment and reviewer.

## 0. Gates that keep everything off today

| Gate | Where | Opens when |
|---|---|---|
| Apply gate | `infra/config/apply-gate.json` (OD-B7, N-04-S) | Both decided with a committed record |
| Decision gate | `infra/config/staging-*.json`: no section `PROPOSED` (`stack.sh decisions`) | The owner records every proposed value |
| Deploy gate | `staging-platform.json` `deploy.enabled` | The owner sets it true in a reviewed pull request |
| Anchor retention (D6) | `infra/tests/run.sh` refuses `deploy.enabled: true` unless the application reads `VEDA_ANCHOR_RETENTION_DAYS`, the anchor store locks for it, and `staging-core` plans it from `anchor_retention` (30 days); the API refuses to start in staging without it | Already met by the D6 change; it stays enforced |
| Deployment alarm actions | The same `deploy.enabled`: the alarms fed by the application, the agent or the heartbeat exist but notify no one (review R4) | The plan and apply that follow the `deploy.enabled` change |
| Public path | No tunnel, DNS or Turnstile widget (AUT-201 … 203, out of scope) | Those stories are built |

## 1. Deployment

**First deploy** (after the apply sequence, §7, and the secrets, §6.3):
1. Set `deploy.enabled: true` in `infra/config/staging-platform.json` (reviewed pull request, merged to `main`).
2. Plan and apply `staging-core` (`10-infra-plan` → `11-infra-apply`): the **alarm actions** of the deployment alarms
   turn on (`actions_enabled`, review R4; until then those alarms report missing data silently), and, the first time,
   the parameter `/veda/staging/config/VEDA_ANCHOR_RETENTION_DAYS` = `30` is added (D6). Expect 1 to add, the alarm
   changes, 0 to destroy.
3. Actions → `12-deploy` → Run workflow on `main`. Approve the `staging` environment.
4. The job builds the image of this commit, pushes `veda-api:<12-hex>`, waits for the scan (stops on any HIGH or
   CRITICAL finding not covered by a reviewed staging exception, `infra/config/image-scan-exceptions.json`;
   [policy](image-scan-exceptions.md)), uploads `deploy/<tag>/bundle.tgz` with its SHA-256, and runs `veda-deploy` on the host:
   bundle verified → `host-setup.sh` (mount, Compose, agent, heartbeat) → `render-env.sh` (refuses until every secret
   is seeded) → pull by digest → `api/deploy/deploy.sh <tag>` (floors, snapshot, quiesce, expand-only migration,
   readiness, resume; [api-runbooks §1](api-runbooks.md)). The CloudWatch agent configuration comes from the bundle
   (`infra/host/cloudwatch-agent.json`), not from SSM (review R2).
5. Pass: the job ends `deployed <tag> (<digest>) to staging`; `veda-stg-api-health` is OK within 5 minutes.

**Later deploys:** the same, from the new commit. **Rollback** to N-1 follows [api-runbooks §2](api-runbooks.md)
(`deploy.sh --rollback <n-1-tag>`), run on the host through an owner Session Manager session in
`/opt/veda/releases/<n-1-tag>/api/deploy` (the N-1 bundle and image are still there; ECR keeps 30 tagged images).

**Failure:** `deploy.sh` stops with worker and scheduler paused when readiness fails; the command output is in
`/veda/staging/host` (stream `<instance>/veda`) and `/var/log/veda/deploy.log`. Decide forward fix or rollback
(api-runbooks §2).

## 2. Backup and recovery

| Layer | What | Recovery |
|---|---|---|
| Litestream | WAL to `veda-stg-litestream-<acct>` every second; 7 days of WAL | Point-in-time restore of `veda.db` ([api-runbooks §3](api-runbooks.md)) |
| Nightly snapshot | `VACUUM INTO` snapshot to `veda-stg-snapshots-<acct>`, COMPLIANCE-locked 35 days (application); `snapshot-missing` alarm after 24 h of silence | Disaster rollback (api-runbooks §3) |
| EBS snapshot | DLM, daily 02:00 IST, 7 kept, data volume only | Create a volume from the snapshot in the same AZ, stop the API, swap the attachment on `/dev/sdf` (owner session), start |

**Host loss or rebuild.** EC2 automatic recovery handles a failed system check. A rebuild (new AMI, corrupt root) is
an **owner-session** procedure, because the plan guard refuses a replace in the workflows and the data volume has
`prevent_destroy`. Outline (the exact commands are reviewed as their own change the first time it is needed):
1. Stop the API (`docker compose stop`) through Session Manager; the data volume keeps the database.
2. Owner session: detach the data volume, disable termination protection, terminate the instance.
3. A reviewed change records the new `compute.ami_id`; the plan creates the instance and the attachment again (the
   volume itself is unchanged), applied by the owner session because a replace is outside the workflow guard.
4. `12-deploy` the current release: `host-setup.sh` finds the existing filesystem and does **not** format it.
5. Evidence: `13-evidence` with label `host-rebuild`.

**Never:** delete a locked snapshot or anchor (impossible by design), or format a volume that carries a filesystem
(`host-setup.sh` refuses to).

## 3. Monitoring

Every alarm notifies `veda-stg-alarms` (owner email, after the one-time subscription confirmation) and the drill queue
`veda-stg-alarm-capture`. Dashboard: CloudWatch → `veda-stg-overview`.

**Before deployment** (`deploy.enabled: false`) only the audit-tampering, trail-delivery, EC2 status-check, CPU and SES
alarms notify; the others (application, agent, heartbeat: `actions_enabled = false`) would only report missing data
and stay silent until the apply of §1 step 2 (review R4).

| Alarm | Meaning | First action |
|---|---|---|
| `veda-stg-api-health` | `/health/ready` failing or the heartbeat silent | `docker compose ps`; `deploy.log`; api-runbooks §1 readiness |
| `veda-stg-app-5xx` | ≥ 5 API 5xx in 5 minutes | Dashboard "Recent API errors"; logs `/veda/staging/app` |
| `veda-stg-lead-intake-failures` | Public lead submissions answered 5xx | Same; leads are never half-written (transaction) |
| `veda-stg-notification-failures` | Outbox handlers failing (email) | SES identity verified? recipient verified (sandbox)? The lead is kept (NOTIF-008) |
| `veda-stg-outbox-dead` | Events dead-lettered | api-runbooks outbox section |
| `veda-stg-scheduled-job-failed` | A scheduled job failed | Logs of the scheduler container |
| `veda-stg-snapshot-missing` | No completed snapshot in 24 h | Scheduler; snapshot bucket permissions; disk |
| `veda-stg-chain-anchor-failed` | A security-chain anchor failed (FC-01) | Anchor bucket, Object Lock headers, KMS |
| `veda-stg-audit-tampering` | Trail, key or bucket protection changed | **Incident**: CloudTrail event history, who and what |
| `veda-stg-trail-delivery` | No trail events for an hour | Trail status (owner session); logs-bucket policy |
| `veda-stg-host-status-check` | EC2 status check failed | EC2 recovers automatically; else §2 rebuild |
| `veda-stg-host-cpu` / `-memory` / `-data-disk` / `-root-disk` | Resource pressure | `docker stats`; prune old images; grow the volume (decision) |
| `veda-stg-ses-bounce-rate` / `-ses-rejects` | Sending reputation | Suppression list; recipients; SES console |

**Dead-lettered outbox events (`veda-stg-outbox-dead`).** The alarm stays in ALARM while any event is dead, and
CloudWatch notifies only on a state change, so **clear every dead event**, or the next one will not alert. On the host
(SSM Run Command `AWS-RunShellScript`, or Session Manager), from `/opt/veda/releases/<tag>/api/deploy` with
`VEDA_IMAGE_TAG=<tag>`:
```sh
docker compose -f docker-compose.yml run --rm --no-deps -T api python -m veda.cli outbox dead
docker compose -f docker-compose.yml run --rm --no-deps -T api python -m veda.cli outbox requeue --id <id> --reason "<cause fixed>"
docker compose -f docker-compose.yml run --rm --no-deps -T api python -m veda.cli outbox retire --id <id> --reason "<why it must not run>"
```
Requeue when the cause is fixed and the event should run; retire when it must not (for example an invite already
accepted). The alarm returns to OK within 5 minutes of the last dead event.

**Drill (RG-5):** `aws cloudwatch set-alarm-state --alarm-name veda-stg-app-5xx --state-value ALARM --state-reason drill`
(deploy role or owner), then read `veda-stg-alarm-capture` and the owner mailbox; record with `13-evidence`.

## 4. SES readiness

1. AUT-202 publishes the three DKIM CNAMEs (`terraform output` of `module.ses.dkim_tokens`:
   `<token>._domainkey.staging.vedaspaces.com CNAME <token>.dkim.amazonses.com`). SES shows the identity verified
   within hours.
2. The owner clicks the verification link AWS mails to the recipient address (sandbox recipient), and confirms the
   alarm-topic subscription (another link).
3. Sandbox limits: 200 messages a day, 1 per second, verified recipients only. Rehearsal recipients (O11) are added as
   identities in a reviewed change.
4. Test: after the first deploy, trigger an email (password reset of a staging user) and check delivery; a failure
   shows in `veda-stg-notification-failures` without touching the lead or the user.
5. Production access (leaving the sandbox) is an owner request to AWS with the use case; it is not needed for
   staging.

## 5. Evidence

`13-evidence` (environment `staging-evidence`) runs `veda-collect` and prints `evidence s3://veda-evidence-<acct>/host/<date>/<instance>/<label>-<ts>.tgz sha256 <hex>`.
The object is COMPLIANCE-locked (30 days, decision). The summary (label, object key, SHA-256, what it shows) goes to
`docs/release-evidence/<gate>/` by pull request. No secrets or personal data are collected; `/etc/veda/api.env` is
never read.

## 6. Owner-session steps

### 6.1 Bootstrap verification (decision C2)
Re-run the bootstrap plan with the controlled procedure of 2026-10-04. Since the flow-log role is gone (C3), the
bootstrap code equals what was applied: the plan must show **No changes**. Any change is a stop condition.

### 6.2 CloudTrail data events (after the first apply)
`veda-boundary` denies every role `PutEventSelectors`; the owner session adds the S3 data events once:
```sh
aws cloudtrail put-event-selectors --region ap-south-1 --trail-name veda-stg-trail --advanced-event-selectors '[
 {"Name":"Management","FieldSelectors":[{"Field":"eventCategory","Equals":["Management"]}]},
 {"Name":"Anchor and evidence objects","FieldSelectors":[{"Field":"eventCategory","Equals":["Data"]},
  {"Field":"resources.type","Equals":["AWS::S3::Object"]},
  {"Field":"resources.ARN","StartsWith":["arn:aws:s3:::veda-stg-anchor-813238078849/","arn:aws:s3:::veda-evidence-813238078849/"]}]}]'
```
Evidence: `aws cloudtrail get-event-selectors --trail-name veda-stg-trail`. Terraform ignores selector changes on the
trail (`ignore_changes`, review R3), so later plans neither show these data events as drift nor try to remove them.

### 6.3 Secrets (AUT-302)
Generate and write, with the owner session, the eight `SecureString` parameters under `/veda/staging/app/`
(`VEDA_JWT_PRIVATE_KEY_PEM` P-256, `VEDA_JWT_KID`, `VEDA_CHAIN_KEY`, `VEDA_CHAIN_KEY_LABEL`,
`VEDA_RECOVERY_CODE_HMAC_KEY`, `VEDA_EMAIL_HASH_HMAC_KEY`, `VEDA_ACTION_TOKEN_KEY` — each key ≥ 32 random bytes,
distinct, labels not `dev-*` — and `VEDA_TURNSTILE_SECRET`, D8). Values never leave the owner's terminal and are never
committed. `render-env.sh` refuses to start the application until all eight exist.

Encrypt them with the **data key** (`alias/veda-stg-data`): the host role may decrypt only with that key, so a
parameter under the default `aws/ssm` key would fail to render. Each value goes from `openssl` straight into SSM; none
is printed, and `--no-overwrite` stops a second run from replacing a key:
```sh
put() { aws ssm put-parameter --region ap-south-1 --name "/veda/staging/app/$1" --type SecureString \
          --key-id alias/veda-stg-data --value="$2" --no-overwrite >/dev/null && echo "seeded $1"; }
put VEDA_JWT_PRIVATE_KEY_PEM "$(openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256)"
put VEDA_JWT_KID stg-2026-10
put VEDA_CHAIN_KEY "$(openssl rand -base64 32)"
put VEDA_CHAIN_KEY_LABEL stg-2026-10
put VEDA_RECOVERY_CODE_HMAC_KEY "$(openssl rand -base64 32)"
put VEDA_EMAIL_HASH_HMAC_KEY "$(openssl rand -base64 32)"
put VEDA_ACTION_TOKEN_KEY "$(openssl rand -base64 32)"
put VEDA_TURNSTILE_SECRET 1x0000000000000000000000000000000AA   # Cloudflare's published always-pass test secret (D8)
aws ssm get-parameters-by-path --region ap-south-1 --path /veda/staging/app --query 'Parameters[].[Name,Type]' --output text
```
The check lists names and types only: eight `SecureString` rows. Never read the values back. The test Turnstile secret
accepts every token, so it is allowed only while public intake stays disabled and until AUT-203 provides the real
widget (D8). The anchor retention is configuration, not a secret: Terraform writes it under `config/` (D6).

### 6.4 Pins after the first plan
Record `compute.ami_id` and `az_id` (staging-network.json) from the first real plan, so later plans cannot replace the
host or the subnet.

### 6.5 Cloudflare tunnel behind Cloudflare Access (AUT-201)

**Owner decision (2026-10-06):**
- `public_intake` stays **disabled**.
- Staging is reachable **only through Cloudflare Access**, by the owner and staff.
- **No anonymous internet traffic** reaches it.

**How the tunnel enforces it:**
- **Defined in the repository:** the tunnel is locally managed, and its ingress is in `infra/host/cloudflared.yml`, so
  it is reviewed.
- **Access required on every request:** `cloudflared` itself requires a valid Access token for the team and the
  application. A request without one gets 403 at the origin, even if the Access application were missing or
  misconfigured.
- **One host only:** only `api-staging.vedaspaces.com` is routed; every other host gets 404.
- **Outbound only:** the host keeps no inbound rule.

**Owner steps**, from the workstation. Credentials stay there and the token goes straight into SSM.
1. Install `cloudflared` (for example `brew install cloudflared`). Then run `cloudflared tunnel login`, choosing the
   `vedaspaces.com` zone.
2. Run `cloudflared tunnel create veda-staging`, then
   `cloudflared tunnel route dns veda-staging api-staging.vedaspaces.com`. That creates one proxied CNAME and touches
   no other record.
3. In **Zero Trust**:
   1. Note the **team name**: `<team>` in `<team>.cloudflareaccess.com`.
   2. Create a **self-hosted application**, "Veda staging", for `api-staging.vedaspaces.com`. `staging` and
      `app-staging` are added with AUT-204.
   3. Add an **Allow** policy for the owner's and staff e-mail addresses only.
   4. Copy its **Application Audience (AUD) tag**.
4. In an owner session (MFA, runbook §6.3), seed `/veda/staging/edge` and list it by name only:
   ```sh
   aws ssm put-parameter --region ap-south-1 --name /veda/staging/edge/CLOUDFLARED_TOKEN --type SecureString \
     --key-id alias/veda-stg-data --value="$(cloudflared tunnel token veda-staging)" --no-overwrite >/dev/null
   aws ssm put-parameter --region ap-south-1 --name /veda/staging/edge/ACCESS_TEAM_NAME --type String --value <team> --no-overwrite
   aws ssm put-parameter --region ap-south-1 --name /veda/staging/edge/ACCESS_AUD --type String --value <aud-tag> --no-overwrite
   aws ssm get-parameters-by-path --region ap-south-1 --path /veda/staging/edge --query 'Parameters[].[Name,Type]' --output text
   ```
5. Run `12-deploy`. `render-edge.sh` renders `/etc/veda/cloudflared/` (the token in `tunnel.env`, mode 0600). Then
   `deploy.sh` step 7 starts `cloudflared` and requires at least one edge connection.
6. Delete `~/.cloudflared/cert.pem` and the tunnel credentials JSON from the workstation. They manage the tunnel; the
   host needs only the token.

**Validation:**

| Check | Pass |
|---|---|
| `12-deploy` log | `7. Edge: Cloudflare tunnel, Cloudflare Access required at the origin`, then `tunnel ready: N edge connection(s)` |
| Anonymous request (`curl -sI https://api-staging.vedaspaces.com/health/live`) | A redirect to `<team>.cloudflareaccess.com` (302), never the API |
| Signed-in browser at the same URL | The live check answers |
| `13-evidence` (label `aut-201-tunnel`) | `deploy-cloudflared-1` up; listeners add only `127.0.0.1:20241`; the security group still has no ingress rule |

**Without the edge parameters:** the tunnel stays stopped (step 7 "not configured") and the API serves on loopback
only.

**A partial or malformed edge configuration refuses the deploy:**
- a missing parameter;
- a token stored as plain `String`;
- a team given as a domain;
- an AUD tag that is not 64 hex.

**To turn the tunnel off:** delete the three parameters and re-run `12-deploy`.

### 6.6 Staging frontends behind Cloudflare Access (AUT-202 to AUT-204)

**Owner decision (2026-10-07):**
- Staging stays behind Cloudflare Access, and `public_intake` stays **disabled**: no anonymous visitor can submit a lead.
- Owner and staff signed in to Access may submit through the staging site. For that, its intake call carries
  credentials (`VEDA_PUBLIC_SITE_CREDENTIALS`, staging only).

**Three frontends:**

| | Production site | Staging site | Staff application (staging) |
|---|---|---|---|
| Host | `www.vedaspaces.com` | `staging.vedaspaces.com` | `app-staging.vedaspaces.com` |
| Source | Committed root `dist/` (Pages project `veda-spaces`) | `app/e2e/site-release/`, staged by `node scripts/staging-build.mjs site` | `app/`, built by `node scripts/staging-build.mjs app` |
| Access | Public | Cloudflare Access | Cloudflare Access |
| Lead intake | Off: the committed `site-release` keeps `veda-api-base`, `veda-turnstile-sitekey` and `veda-api-credentials` empty (`test_public_intake_disabled`) | On, to `https://api-staging.vedaspaces.com`, with the staging widget and `credentials: 'include'` | Not applicable (staff API) |
| CORS from the API | No credentials for public-site origins (production refuses `VEDA_PUBLIC_SITE_CREDENTIALS`) | Credentials for `https://staging.vedaspaces.com` on `/api/v1/public/*` only | Credentials for `VEDA_APP_ORIGIN` on every route (unchanged) |
| Indexed | Yes | No (`X-Robots-Tag: noindex`, `robots.txt` disallows all, no sitemap) | No (`X-Robots-Tag: noindex`) |

**The staging build never targets production.** `staging-build.mjs` writes `https://api-staging.vedaspaces.com` into
the page or bundle, rewrites the CSP `connect-src` to it, and **refuses**:
- any output that still names `https://api.vedaspaces.com`;
- a `VITE_API_BASE` other than the staging API;
- a Turnstile test key (`1x…`, `2x…`, `3x…`) instead of the staging widget key.

**Owner steps** (Cloudflare dashboard; no Cloudflare API token is used):
1. **Turnstile (AUT-203).**
   - Create a widget "Veda staging" for `staging.vedaspaces.com` and `app-staging.vedaspaces.com` (Managed).
   - Its **site key** is public: it goes in the Pages variable `STAGING_TURNSTILE_SITE_KEY` below.
   - Its **secret key** replaces the D8 test secret. The parameter was seeded with `--no-overwrite`, so in an owner
     session, delete it first, then put the new one:
     `aws ssm delete-parameter --region ap-south-1 --name /veda/staging/app/VEDA_TURNSTILE_SECRET`, then the §6.3
     `put` line with `--value="$(pbpaste)"` straight from the clipboard (or edit it in the console, keeping
     `alias/veda-stg-data`). Re-run `12-deploy`: a commit already pushed reuses its image.
   - The API accepts a token only when siteverify succeeds **for one of these hosts** (`kernel/turnstile.py`).
2. **Pages (AUT-204): two projects** from this repository, production branch `main`, root directory `app`:

   | Project | Build command | Output | Variables |
   |---|---|---|---|
   | `veda-staging-site` | `node scripts/staging-build.mjs site` | `dist-staging-site` | `STAGING_TURNSTILE_SITE_KEY` |
   | `veda-staging-app` | `npm ci && node scripts/staging-build.mjs app` | `dist` | `STAGING_TURNSTILE_SITE_KEY` |

   - **Order, so nothing is ever public:** create each project **without** `STAGING_TURNSTILE_SITE_KEY`. Its first
     build then fails on purpose and publishes nothing. Add the Access hostnames (step 3), attach the custom domain,
     then add the variable and **Retry deployment**.
   - Attach the custom domains `staging.vedaspaces.com` and `app-staging.vedaspaces.com`. Pages creates the proxied
     CNAMEs (AUT-202); don't create them by hand. A domain stuck in **Verifying** asks for the CNAME itself: add
     exactly what it shows (an empty name means `@`), proxied, then **Check DNS records**.
   - **Preview branches:** project **Settings → Build → Branch control → Preview branch: None**. The
     `*.<project>.pages.dev` row in Access covers any preview that exists anyway.
3. **Access.** In the "Veda staging" application:
   - **Hostnames (Destinations → Public hostnames):** `staging` and `app-staging` on `vedaspaces.com`, and for each
     project two rows on its own domain `<project>.pages.dev`: subdomain empty, and subdomain `*`. The domain list
     shows only projects that already exist; otherwise use **Switch to custom input**. **Never pick
     `veda-spaces.pages.dev`:** that is the public production site's project. Keep the same Allow policy.
   - **CORS settings** (search the application page for "CORS"):
     - **Access-Control-Allow-Credentials: on.** Off is the default and gives the browser error "the value of
       Access-Control-Allow-Credentials is '' … must be 'true'".
     - Allowed origins: `https://staging.vedaspaces.com` and `https://app-staging.vedaspaces.com`, listed (not "Allow
       all origins": credentials need explicit origins).
     - Methods: `GET, POST, PUT, PATCH, DELETE` (OPTIONS is not in the list: it is the preflight itself).
     - Headers: `Content-Type, Idempotency-Key, If-Match, X-Request-ID, X-Requested-With, Authorization,
       X-Veda-Client` (the estimator wizard's browser token; without it the browser refuses the estimate request and
       the wizard says "You appear to be offline").
     - **Bypass options requests to origin: off.** Access answers the preflight itself; `cloudflared` would refuse an
       `OPTIONS` without an Access token.
   - **The browser needs the API host's own Access cookie.** After signing in, open
     `https://api-staging.vedaspaces.com/health/live` once in the same browser, so `CF_Authorization` exists for that
     host. Without it, a credentialed call is redirected to the login and fails as a CORS error.
4. **SES DKIM (AUT-202).** In the main dashboard (`dash.cloudflare.com`, not Zero Trust): `vedaspaces.com` → **DNS →
   Records**. Publish the three CNAMEs of §4 as **DNS only** (grey cloud). Name `<token>._domainkey.staging`;
   Cloudflare adds the zone. Change no other record: `@`, `www`, MX, the apex SPF and the Google verification record
   stay as they are. Record `dig` of MX and TXT **before** and compare after.

**Turnstile keys: two values, one public.** The widget page shows a **Site Key** (about 24 characters, public: Pages
variable, in the page) and a **Secret Key** (about 35 characters: SSM only). Both start with `0x4AAAA`. The staging
build refuses a secret-length value (incident I1 of the AUT-202 to AUT-204 evidence). If the secret ever reaches a
page or a Pages variable: **rotate it** (widget → Rotate secret key), put the new one in SSM, fix the variable,
retry the deployments, **delete every older deployment**, and re-run `12-deploy`.

**Owner tasks from a managed workstation** (no Session Manager plugin, no admin rights): sign in to the console as
`org-admin` with MFA and switch role into the staging account (`OrganizationAccountAccessRole`):
- **SSM parameters:** Systems Manager → Parameter Store → Edit; keep **SecureString** and the KMS key
  `alias/veda-stg-data` (the host decrypts with no other key). Never "Show decrypted value".
- **Commands on the host:** SSM **Run Command** (`AWS-RunShellScript`), from the console or
  `aws ssm send-command --profile veda-owner`. The console Session Manager shell may not take keyboard input.
  **Anything a command prints is kept** in the command history, and the container's output also goes to the log
  group: never run a command that prints a secret.
- **CLI login:** `aws login --profile veda-owner` reuses that console sign-in. "Invalid request" means a stale URL:
  stop it, close old sign-in tabs, and run it once again.
- CloudTrail records these actions as `OrganizationAccountAccessRole/org-admin`, not `bootstrap-owner`: note it in the
  evidence of the change.

**Validation:**

| Check | Pass |
|---|---|
| `dig +short staging.vedaspaces.com`, `app-staging…`, `api-staging…` | Cloudflare addresses (proxied) |
| `dig +short CNAME <token>._domainkey.staging.vedaspaces.com` (×3) | `<token>.dkim.amazonses.com.` |
| `dig +short MX vedaspaces.com`, `dig +short TXT vedaspaces.com` | Unchanged (Google MX, SPF, verification) |
| Anonymous `curl -sI` of each staging host | `302` to `kite-relay.cloudflareaccess.com` |
| Signed in, `staging.vedaspaces.com` | The form shows the consent block and the Turnstile widget |
| A submission with the widget solved | `201` and a reference |
| The same request with a forged token | `422 CAPTCHA_FAILED`, no lead, a `PUBLIC_INTAKE_BLOCKED` event |
| The page source of both staging hosts | No `api.vedaspaces.com`; `veda-turnstile-sitekey` is the 24-character site key |
| A fresh private window (close every private window first: they share cookies) at each staging host and each `<project>.pages.dev` | The Access login before any page |
| `dig +short vedaspaces.com` (apex) | Cloudflare addresses; the browser lands on `https://www.vedaspaces.com` (301, path and query kept) |
| `aws sesv2 get-email-identity --email-identity staging.vedaspaces.com` | `VerificationStatus` and DKIM `SUCCESS` |

Some corporate networks reset TLS to `*.vedaspaces.com` hosts: a `curl` failing with "connection reset" there is the
network, not the site. Check in a browser instead.

**After any dashboard change** (Pages, Access, Turnstile, DNS), run this table again: none of the Cloudflare setup is
in the repository.

Then run the end-to-end lead flow of §8.

### 6.7 First staff account (Founder)

Once per environment (AUTH-014), after SES can deliver to the address (§4, §6.6):
```sh
docker compose -f docker-compose.yml run --rm --no-deps -T api python -m veda.cli bootstrap-founder \
  --email <verified address> --name "<name>" --email-link
```
- **The invite link is a credential and is never printed in staging or production.** The container's output goes to
  the log group. `--email-link` emails it; `--link-file <new path>` writes it to a new file, mode 0600, never
  overwriting one. Without either, the command refuses before creating anything.
- Accept it within the hour. Then MFA enrolment is required.
- Run it with SSM Run Command if Session Manager is not available on the workstation.

### 6.8 Budgetary Estimate (ADR-012)

**State after merge:** off everywhere.
- `VEDA_ESTIMATOR_ENABLED` defaults to false, so both public routes answer 404. Production refuses `true`.
- The committed `estimate.html` shows "coming soon".
- `public_intake` stays **disabled**, and the anonymous intake hostname (ADR-011, phase E7) is **not** built.

**Rate cards** (operator only; no API exposes a card):
1. Prepare the private card: Essential rates only until Premium and Luxury are approved. Never commit it.
2. Dry run: `veda estimator validate-card <file>`. It prints the version and SHA-256 only, and refuses customer data.
3. Load it on the host with SSM Run Command (or Session Manager): write the file to a root-only temporary path,
   mount it read-only into a one-off container, run `veda estimator load-card /card.json`, then delete the file.
   Run Command keeps what a command prints, so print the version and SHA-256 only.
4. Activate it with the owner's approval reference:
   `veda estimator activate-card --version <v> --approval "<owner approval, date>"`. The previous card is retired.
5. To go back: `veda estimator rollback-card --approval "<reason>"` re-activates the last retired card.
6. To check: `veda estimator list-cards` shows versions, states and SHA-256, never rates.

**Enable on staging (behind Cloudflare Access), after independent review and owner approval:**
1. **API:** set `VEDA_ESTIMATOR_ENABLED=true` (and `VEDA_WARRANTY_POLICY_URL`) through the staging SSM
   configuration: a reviewed Terraform change, then plan, apply and `12-deploy`.
2. **Site:** in the Pages project `veda-staging-site`, set `STAGING_ESTIMATOR=on` and leave
   `STAGING_ESTIMATOR_PACKAGES=ESSENTIAL`, `STAGING_ESTIMATOR_HOME_SIZES=3BHK` and
   `STAGING_ESTIMATOR_PROPERTY_TYPES=APARTMENT` (the defaults: only what the card supports, ADR-012 D3), then retry
   the deployment. The full test list is in the
   [staging validation plan](../implementation/estimator/ESTIMATOR-staging-validation-plan.md).
3. **Validate:**
   - signed in, open `https://staging.vedaspaces.com/estimate`, choose **3 BHK, Apartment** (the only home size
     the draft card prices; others answer "not available for this home size yet"), create an estimate, then request a
     quotation;
   - the estimate shows the Custom Features Allowance as its own range and the package with six inclusions;
   - the lead shows the Budgetary Estimate panel;
   - the notification carries the estimate summary;
   - choose **Luxury**: no price, a design-consultation request; the lead shows "Luxury design consultation
     requested";
   - a forged Turnstile token gets `422`;
   - an anonymous request gets a `302` to Access.

**Retention:** the daily `estimate-retention` job soft-deletes estimates never linked to a lead
`VEDA_ESTIMATE_RETENTION_DAYS` after creation (90, owner decision D7), and never while an estimate is still valid
(30 days). A linked estimate stays with its lead.

## 7. Staging apply sequence

Every apply: `10-infra-plan` on `main` → review the plan text and the guard → approve the digest → `11-infra-apply`.
Prerequisites: OD-B7 and N-04-S decided; every `PROPOSED` decision recorded; §6.1 shows No changes.

| Step | Scope | Check after |
|---|---|---|
| 1 | AUT-112 budget, AUT-102 keys, AUT-103 buckets, AUT-101 network, AUT-104 trail (one plan, dependency order is Terraform's) | Keys rotate; buckets private (S3 console "Access: Bucket and objects not public"); trail logging; flow logs arriving under `vpc-flow/` |
| 2 | Owner session §6.2 (data events) | `get-event-selectors` |
| 3 | AUT-105, AUT-106, AUT-107, AUT-110, AUT-108, AUT-111 (same plan if applied together) | Host `Online` in Systems Manager; agent metrics; alarms OK or INSUFFICIENT_DATA; SES identity pending until AUT-202 |
| 4 | Owner session §6.3 (secrets), §6.4 (pins) | Parameters exist (names only) |
| 5 | `12-deploy` (after `deploy.enabled`) | §1 pass criteria |
| 6 | `13-evidence` label `staging-platform-first-apply` | Evidence PR |

Single-plan apply is possible (Terraform orders the 158 resources); the steps above split it where an owner action
sits between resources. Zero destroys; any destroy or replace is refused by the plan guard.

## 8. End-to-end lead-flow validation plan

**Goal:** a public enquiry travels browser → Cloudflare → tunnel → API → SQLite → Litestream → outbox → SES → staff
inbox, with every control observed.

**Prerequisites (not in this workstream):** AUT-201 tunnel, AUT-202 DNS (D7 host names and DKIM), AUT-203 Turnstile
widget (D8), AUT-204 the staging SPA; secrets seeded (§6.3); a deployed release (§1); SES recipient verified (§4).

| # | Step | Pass criterion | Evidence |
|---|---|---|---|
| 1 | Submit the public form on the staging site with a valid Turnstile | `201`, a lead number | Browser capture; request log line (route `/api/v1/public/leads`, status 201) |
| 2 | Submit with a failed Turnstile | Refused; no lead | Log line; lead count unchanged |
| 3 | Duplicate submission (same idempotency key) | One lead | Lead list |
| 4 | Staff login with MFA; open the lead | Lead visible with source and consent | Screenshot; audit log entry |
| 5 | Notification email | Delivered to the verified mailbox | Mailbox; `AWS/SES Delivery` |
| 6 | SES failure drill: unverify the recipient, submit | Lead committed; outbox event FAILED then retried; `notification-failures` alarm | Lead list; outbox status; alarm history |
| 7 | Replication | Litestream lag < 5 s; WAL objects in the bucket | `13-evidence` |
| 8 | Snapshot | Next nightly snapshot locked 35 days | Object retention in the console |
| 9 | Chain anchor | Anchor object locked; trail data event | CloudTrail event |
| 10 | No public inbound | `ss -lntu` shows only loopback and the agent; the security group has no inbound rule | `13-evidence` |

Record the run with `13-evidence` label `e2e-lead-flow` and a summary in `docs/release-evidence/E2E-LEAD-FLOW/`.
