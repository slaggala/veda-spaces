# Deploy-enable change package (staging)

- **Date:** 2026-10-06
- **Depends on:** D6 (PR #26), merged first.
- **This package:** sets `deploy.enabled: true`. Public intake stays `disabled`.
- **Not done here:** no apply, no deployment, no secret seeding.
- **What enabling deploy causes:** `12-deploy` may run, and the 11 deployment alarms notify (review R4). The first
  plan after the merge also adds the D6 parameter.

## 1. Order (owner)

| # | Step | Who | Where |
|---|---|---|---|
| 1 | Merge PR #26 (D6) | Owner | GitHub |
| 2 | Owner session: CloudTrail data events (§2) and the eight secrets (§3), then their validation (§4) | Owner | Own terminal, `bootstrap-owner` with MFA |
| 3 | Merge this pull request | Owner | GitHub |
| 4 | `10-infra-plan` on `main`, then approve `staging-plan` | Owner (approval) | Actions |
| 5 | Review the plan against §5. Stop on any difference | Owner, with Claude | Run summary and artifact |
| 6 | `11-infra-apply` with that run ID and digest, then approve `staging-infra` | Owner | Actions |
| 7 | Verify the apply (§7) | Owner, with Claude | Run log, drift plan |
| 8 | `12-deploy`, then approve `staging` | Owner | Actions |

- **Steps 6 to 8 run back to back.** Some deployment alarms already sit in `ALARM` because they have no data (§7). The
  first deploy is what gives them data.
- **The merge itself applies nothing.** `10-infra-plan` does not start automatically on a change to
  `staging-platform.json`, so it has to be started by hand.

## 2. CloudTrail data events (owner session, once)

`veda-boundary` denies every workflow role `cloudtrail:PutEventSelectors`; Terraform ignores selector changes
(review R3).

```sh
aws cloudtrail put-event-selectors --region ap-south-1 --trail-name veda-stg-trail --advanced-event-selectors '[
 {"Name":"Management","FieldSelectors":[{"Field":"eventCategory","Equals":["Management"]}]},
 {"Name":"Anchor and evidence objects","FieldSelectors":[{"Field":"eventCategory","Equals":["Data"]},
  {"Field":"resources.type","Equals":["AWS::S3::Object"]},
  {"Field":"resources.ARN","StartsWith":["arn:aws:s3:::veda-stg-anchor-813238078849/","arn:aws:s3:::veda-evidence-813238078849/"]}]}]'
aws cloudtrail get-event-selectors --region ap-south-1 --trail-name veda-stg-trail \
  --query 'AdvancedEventSelectors[].Name' --output text
```

- **Pass:** the second command prints `Management	Anchor and evidence objects`.
- **Management events stay on.** The first selector keeps them. Replacing the trail's default selector without it
  would stop the management events.
- **Scope:** object-level reads and writes on the two buckets only, at USD 0.10 per 100,000 events (negligible in
  staging).
- **To undo:** run the same command with only the `Management` selector.

## 3. The eight secrets (owner session; runbook §6.3)

All eight are `SecureString` under `/veda/staging/app/`, encrypted with **`alias/veda-stg-data`**. The host role may
decrypt only with that key. Values go from `openssl` straight into SSM and are never printed.

- **`--value="$2"` (with the `=`) is required.** A PEM starts with `-----BEGIN`, which the AWS CLI would otherwise read
  as an option.
- **`--no-overwrite`** stops a second run from replacing a key.

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
put VEDA_TURNSTILE_SECRET 1x0000000000000000000000000000000AA
```

| # | Name | Content | The API refuses to start when |
|---|---|---|---|
| 1 | `VEDA_JWT_PRIVATE_KEY_PEM` | Unencrypted PKCS#8 P-256 private key | It is missing, encrypted, or not P-256 |
| 2 | `VEDA_JWT_KID` | `stg-2026-10` | It is empty or `dev-1` |
| 3 | `VEDA_CHAIN_KEY` | 32 random bytes, base64 | It is shorter than 32 bytes, not random, a development key, or equal to another key |
| 4 | `VEDA_CHAIN_KEY_LABEL` | `stg-2026-10` | It starts with `dev-` |
| 5 | `VEDA_RECOVERY_CODE_HMAC_KEY` | 32 random bytes, base64 | As 3 |
| 6 | `VEDA_EMAIL_HASH_HMAC_KEY` | 32 random bytes, base64 | As 3 |
| 7 | `VEDA_ACTION_TOKEN_KEY` | 32 random bytes, base64 | As 3 |
| 8 | `VEDA_TURNSTILE_SECRET` | Cloudflare's published always-pass test secret (D8) | It is missing (`VEDA_TURNSTILE_MODE=cloudflare` is already configured) |

`render-env.sh` refuses to render until all eight exist.

## 4. Secret validation (owner session; prints properties only, never values)

```sh
aws ssm describe-parameters --region ap-south-1 \
  --parameter-filters Key=Path,Option=Recursive,Values=/veda/staging/app \
  --query 'Parameters[].[Name,Type,KeyId]' --output text            # 8 rows: SecureString alias/veda-stg-data
v() { aws ssm get-parameter --region ap-south-1 --name "/veda/staging/app/$1" --with-decryption \
        --query Parameter.Value --output text; }
for k in VEDA_CHAIN_KEY VEDA_RECOVERY_CODE_HMAC_KEY VEDA_EMAIL_HASH_HMAC_KEY VEDA_ACTION_TOKEN_KEY; do
  echo "$k $(v $k | base64 -d | wc -c | tr -d ' ') bytes"; done                     # each: 32 bytes
for k in VEDA_CHAIN_KEY VEDA_RECOVERY_CODE_HMAC_KEY VEDA_EMAIL_HASH_HMAC_KEY VEDA_ACTION_TOKEN_KEY; do
  v $k | shasum -a 256; done | sort -u | wc -l                                       # 4 (all distinct)
v VEDA_JWT_PRIVATE_KEY_PEM | openssl pkey -noout -text | grep 'NIST CURVE'          # NIST CURVE: P-256
echo "$(v VEDA_JWT_KID) $(v VEDA_CHAIN_KEY_LABEL)"                                  # stg-2026-10 stg-2026-10
v VEDA_TURNSTILE_SECRET | grep -c '^1x0000000000000000000000000000000AA$'           # 1
```

| Check | Pass |
|---|---|
| Names, types, key | 8 rows, all `SecureString`, `KeyId` `alias/veda-stg-data` |
| Four keys | 32 bytes each, 4 distinct digests |
| JWT key | `NIST CURVE: P-256` |
| Labels | `stg-2026-10 stg-2026-10` (labels are not secrets) |
| Turnstile | `1` (the test secret, D8) |

The only thing that can confirm the whole configuration is the API's own start-up validation during `12-deploy`. If
a value is wrong, `deploy.sh` stops before serving and the release is not promoted.

## 5. Expected plan delta (`10-infra-plan` after the merge)

**`Plan: 1 to add, 11 to change, 0 to destroy.`**

The sandbox plans of this tree with `deploy.enabled` false and true differ **only** in these 11 `actions_enabled`
values. The one addition comes from D6.

| Action | Resource | Change |
|---|---|---|
| Add | `module.ssm.aws_ssm_parameter.config["VEDA_ANCHOR_RETENTION_DAYS"]` | `/veda/staging/config/VEDA_ANCHOR_RETENTION_DAYS` = `30` (String) |
| Update in place | `module.monitoring.aws_cloudwatch_metric_alarm.app["app-5xx"]` | `actions_enabled` false → true |
| Update in place | `…app["chain-anchor-failed"]` | Same |
| Update in place | `…app["lead-intake-failures"]` | Same |
| Update in place | `…app["notification-failures"]` | Same |
| Update in place | `…app["outbox-dead"]` | Same |
| Update in place | `…app["scheduled-job-failed"]` | Same |
| Update in place | `…app["snapshot-missing"]` | Same |
| Update in place | `module.monitoring.aws_cloudwatch_metric_alarm.host["api-health"]` | Same |
| Update in place | `…host["host-data-disk"]` | Same |
| Update in place | `…host["host-memory"]` | Same |
| Update in place | `…host["host-root-disk"]` | Same |

- **Also expected:** the output-only `budget` difference (`"25.00"` → `"25.0"`) seen in the drift check. It changes
  no resource.
- **Anything else is a stop condition:** another resource, another attribute, a replacement or a destroy.

## 6. Expected apply delta

`Apply complete! Resources: 1 added, 11 changed, 0 destroyed.` Nothing is created on the host, nothing is deployed,
and no inbound path opens.

## 7. Verification after the apply

1. **Apply log:** the approved digest is verified, the plan guard passes, and the result is `1 added, 11 changed,
   0 destroyed`.
2. **Drift plan:** a new `10-infra-plan` on `main` shows 159 resources with no change. The only difference is the
   cosmetic `budget` output.
3. **Alarms:** run
   `aws cloudwatch describe-alarms --region ap-south-1 --alarm-name-prefix veda-stg- --query 'MetricAlarms[].[AlarmName,ActionsEnabled,StateValue]' --output text`
   (owner session, or the console). It should list all 17 alarms with `ActionsEnabled` `True`.
   - **No alarm email is expected at the apply.** Alarms notify only when their state changes, and changing an
     alarm's configuration leaves its state as it is.
   - **Five alarms treat missing data as breaching** (`api-health`, `snapshot-missing`, `host-memory`,
     `host-data-disk`, `host-root-disk`). With no agent or heartbeat yet, they are already in `ALARM` and stay there
     silently.
   - **After `12-deploy`,** the agent and the heartbeat report, and those alarms move to `OK`. Each sends one **OK**
     email.
   - **`snapshot-missing`** stays in `ALARM` until the first nightly snapshot (20:30 UTC), then sends OK.
   - **An ALARM email after the deploy is a real signal.**
4. **Parameter:** `/veda/staging/config/VEDA_ANCHOR_RETENTION_DAYS` = `30`, visible in the plan artifact. The plan
   role may read `config/`.

## 8. Rollback conditions

| Condition | Action |
|---|---|
| The plan differs from §5 in any way | Do not approve `staging-infra`. Report the difference |
| The apply fails partway | Do not rerun it. Make a fresh plan; it should show only what is left |
| Alarm noise is unacceptable before the deploy can run | Revert this change (`deploy.enabled: false`), then plan and apply: 11 changes back. The D6 parameter stays, which is harmless |
| A secret is wrong (found in §4, or `12-deploy` stops at start-up validation) | Fix it in the owner session: `put-parameter --overwrite` for that one name. The release is not promoted while validation fails |
| `12-deploy` fails after the image starts | `deploy.sh` stops with the worker and scheduler paused. There is no N-1 on a first deploy: leave the host stopped, and keep or revert `deploy.enabled` while the cause is found (runbook §1, api-runbooks §3) |
| Data events need removing | `put-event-selectors` with only the `Management` selector |

## 9. Readiness for `12-deploy`

The preflight refuses unless:
- the run is on `main`;
- both apply gates are decided;
- no section is `PROPOSED`;
- `deploy.enabled` is true.

The deploy job then proves the `staging` approval and assumes `veda-gh-deploy`. Before you run it:
- [ ] §7 passed (apply verified, drift clean).
- [ ] The eight secrets validated (§4).
- [ ] The data events show the two selectors (§2).
- [ ] The host shows as **Online** in Systems Manager → Fleet Manager (`veda-stg-host`).
- [ ] D6 is in `main` (`VEDA_ANCHOR_RETENTION_DAYS` is required in staging; the API refuses to start without it).
- [ ] Public intake is still disabled (no tunnel, DNS or widget).
