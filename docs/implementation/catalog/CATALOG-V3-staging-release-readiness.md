# Staging release readiness: current main with V3 disabled

**Not deployed.** This report assesses whether a `12-deploy` of current main can run with V3 off, media off and the
scanner `none`, without activating anything. It was prepared from the repository (main `e089903`, plus this branch's
changes) and the applied staging-core state of 2026-10-11. It claims no deployment result.

**Verdict: DEPLOYABLE WITH V3 DISABLED.** No code-level blocker was found. Two things can only be confirmed during the
run: the image scan result, and the post-deploy smoke checks below.

## What a deploy ships

Staging last ran `3e9cbca` (`12-deploy`, 2026-10-08). A deploy of main ships PRs #59–#71: the estimator V2 work, the
V3 catalog, the media enablement and its closures. It is an application release, not a configuration refresh.

## Gate by gate

| Gate | Result with V3 off |
|---|---|
| `12-deploy` preflight | Passes: dispatched from `main`; apply gates OD-B7 and N-04-S ACCEPTED; no PROPOSED owner decision (`media_scanner` and `media_rights` are UNDECIDED, which is allowed); `deploy.enabled` is true |
| `render-env.sh` secrets | Unchanged since `3e9cbca` |
| Media preflight | The 13 media settings exist in SSM (applied). It prints **"scanner not selected"** and **"V3 intentionally disabled"** and passes. `VEDA_CATALOG_APPROVAL_SHA256` (this branch) is not required while V3 is off |
| `deploy.sh` step 0b | Skipped: `VEDA_CATALOG_ESTIMATOR_ENABLED` is `false` |
| Startup validation (`config.validate_environment`) | Passes: scanner `none`, backend `s3`, prefixes exactly `source/` and `variant/`, video `false`. The bucket, clamd, KMS and rights-approver checks run only when a V3 flag is on. Nothing required at startup is missing from SSM |
| Migrations | `0103_catalog`, `0104_catalog_idempotency`, `0105_catalog_claim_control`: expand-only, no backfill, no change to existing tables. Their downgrades are not implemented (forward-only) |
| Compose | The new `clamd` service is in the `scanner` profile, so a default `up` does not start it. Step 4c prints "Scanner: not selected" |
| Readiness | `/health/ready` with migrations at head; no catalog readiness check was added |

## Behaviour with the flags off

- **Staff catalog API:** 404 before authentication.
- **Public catalog routes** (catalog, estimates, events, media): 404. Media is also gated by the delivery flag.
- **New scheduler jobs:** `catalog-activation`, `catalog-media-scan` and `catalog-media-retention` skip while admin is off.
- **V2 estimator:** stays on, and the active spec keeps serving. The `ESSENTIAL-1.1` approval is PENDING, so 1.1
  cannot be activated, but no owner decision is needed to keep the current spec serving.

## Risks

1. The image scan may stop the deploy on a HIGH or CRITICAL finding in a new dependency (`pillow` was added).
2. The V2 customer-spec parser is stricter. Run a V2 smoke estimate after the deploy.
3. If any live SSM media value differs from the plan (the prefixes especially), startup is refused and readiness fails.
4. The migrations are forward-only. Rolling back the image is safe because the schema change is additive.

## Owner steps (when the owner decides to release)

1. Confirm CI is green on the commit.
2. Run `12-deploy` on `main` and approve the `staging` environment.
3. In the log, confirm:
   - the scan passed;
   - both media-preflight lines appear;
   - step 0b is absent;
   - step 4c says "not selected";
   - readiness reports migrations at head.
4. Smoke checks:
   - `/api/v1/public/catalog` and `/api/v1/catalog/dashboard` return 404;
   - a V2 estimate works;
   - `veda-stg-api-health` is OK within 5 minutes.

## Rollback

**Normal:**
1. Open an owner Session Manager session in `/opt/veda/releases/<3e9cbca…>/api/deploy`.
2. Add `VEDA_SCHEMA_AHEAD_ACCEPTED=0105_catalog_claim_control` to `/etc/veda/api.env`.
3. Run `./deploy.sh --rollback <3e9cbca tag>`. The image is retained in ECR and on the host.
4. Remove the line after the next forward deploy.

See `docs/operations/staging-platform-runbooks.md` and `api-runbooks.md` §2.3 and §3.

**Disaster** (data corruption only): restore the pre-deploy snapshot or Litestream, run `restore-verify`, then serve
a forward-fixed image.
