# Catalog V3: targeted media enablement on protected staging

**Status: merged (PR #70), not applied, not deployed. Protected-staging activation remains blocked. Real-card evidence remains pending.** Nothing has been created in AWS. No setting has been turned on.

| Item | State |
|---|---|
| V3 | Off |
| Media delivery | Off |
| Public intake | Disabled |
| Real media, 3D, video | None |
| Production | Unchanged |

The work extends the existing staging platform. It creates no new platform, no CloudFront distribution, no third KMS key and no new hostname. Every change below arrives through the existing reviewed path:

1. 10-infra-plan
2. the plan guard
3. 11-infra-apply, digest-bound
4. 12-deploy

## 1. What changes, by layer

| Layer | Change | Where |
|---|---|---|
| Storage | One more bucket-map entry, `veda-stg-media-<account>`. It inherits every existing control: SSE-KMS under the data key with a bucket key, versioning, all public access blocked, ownership enforced, a TLS-only and account-only policy, `prevent_destroy`. It adds: uploads refused unless SSE-KMS under the data key (key ARN or alias ARN); noncurrent versions expire after `media.noncurrent_days` (30); expired delete markers removed. No Object Lock, so a withdrawal can remove the current version at once; prior noncurrent versions remain until the 30-day window expires them. No website, no allow statement at all. | `infra/terraform/modules/storage` |
| IAM | The host role gains `s3:GetObject`, `s3:PutObject` and `s3:DeleteObject` on `media/source/*` and `media/variant/*`, and `s3:ListBucket` under those prefixes only. No KMS change: the existing data-key grant matches by alias. No version delete, tagging, ACL or bucket permission; the explicit administration deny still covers the bucket. A production media bucket is refused by the module. | `infra/terraform/modules/runtime-iam` |
| SSM | 13 media settings and flags under `/veda/staging/config`. Values are plain and non-secret. The scanner address and image are always present and inactive unless the scanner mode is `clamd` (§17); the rights approver appears only once named. | `infra/terraform/envs/staging-core` |
| Scanner | A pinned `clamd` service in the Compose `scanner` profile: private network only, no host port, read-only root, all capabilities dropped except the entrypoint's user switch, no-new-privileges, bounded memory, a persistent signature volume, a health check. `deploy.sh` starts it only when the configuration selects `clamd`, refuses an image not pinned by digest, and refuses to continue until clamd answers `PING`. **Not running today.** | `api/deploy/docker-compose.yml`, `api/deploy/deploy.sh` |
| Monitoring | Eight log metric filters and alarms on the existing topic. One host metric, the scanner restart count. Signals carry counts and ages only. | `infra/terraform/modules/monitoring`, `infra/host/health.sh` |
| Evidence | `veda-collect` also records the scanner-capacity facts, read-only. | `infra/terraform/modules/deploy` |
| Application | Media prefixes fixed; video refused on; KMS key and an owner-assigned rights approver required once the catalog is on; serve-time rights validity; scanner and storage signals. | `api/veda/config.py`, `api/veda/modules/catalog/media.py` |
| CSP | The approved V3 page only: `img-src 'self' data: https://api-staging.vedaspaces.com`. | `app/scripts/staging-build.mjs` |
| Approval | The V3 staging approval record: schema, validator, DRAFT template, and the build gate. | `api/veda/modules/catalog/staging_approval.py`, `app/scripts/staging-build.mjs` |

Media alarm signals:

| Signal | What it counts |
|---|---|
| Scanner unavailable | The scanner could not be reached |
| Scan failed | A scan did not complete |
| Infected | A file was detected as malware |
| PENDING age | Media waiting for a scan longer than 1 hour |
| Signature age | Signatures older than 48 hours |
| Non-CLEAN delivery attempt | A released object that is not CLEAN was requested |
| S3 access denied | S3 refused the host on the media bucket |
| KMS access denied | KMS refused the host for media |
| Scanner restarts (host) | The scanner keeps restarting |

## 2. Owner decisions (`infra/config/staging-platform.json`)

| Entry | Status | Content |
|---|---|---|
| `media` | DECIDED | The owner defaults of this workstream, as given: bucket, data key, no Object Lock, 30-day noncurrent window, delivery via api-staging behind Access, catalog governance. |
| `media_scanner` | **UNDECIDED** | Option A, B or C, after the capacity evidence (§4). `mode` stays `none`, so uploads stay PENDING and nothing is served. |
| `media_rights` | **UNDECIDED** | `approver: [OWNER TO FILL]`. Never invented. |
| `catalog_v3` | DECIDED: off | Every flag false; `approval_record_sha256` null. |

UNDECIDED blocks V3 activation only. It does not block other applies or deploys; only `PROPOSED` does that.

The staging-core output `catalog_v3` refuses all of the following:
- a scanner other than `none` or `clamd`;
- `clamd` without option A or B and an image pinned by digest;
- a partial activation;
- any flag on without all of these: `media_scanner` DECIDED with `clamd`, `media_rights` DECIDED with a named approver, and `approval_record_sha256` equal to the SHA-256 of the committed approval record.

## 3. Upload, storage, scan and delivery flow

1. Staff with `catalog.media.edit` upload through the authenticated staff API. This needs `VEDA_CATALOG_ADMIN_ENABLED`, which is off. The file is validated and re-encoded (images) or sanitised (3D, which stays disabled), then scanned in the request by clamd.
2. Objects are written under content-hash keys `source/<sha256>` and `variant/<sha256>` with SSE-KMS.
3. Scan states:

   | State | Effect |
   |---|---|
   | CLEAN | May be released |
   | INFECTED | Refused; nothing stored |
   | FAILED | Scanner error or unreachable; never served; retried by the `catalog-media-scan` job |
   | PENDING | No scanner; never served |
   | WITHDRAWN | Withdrawn or purged; never served |

   Release validation refuses media that isn't CLEAN, expired or not-yet-effective rights, and a passed rights review date.
4. Delivery happens only through `GET https://api-staging.vedaspaces.com/api/v1/public/catalog/media/<sha256>`, behind Cloudflare Access. It serves only a CLEAN, unwithdrawn, unpurged image variant that the ACTIVE release references, with rights in effect today. Anything else gets 404: an invalid hash, a non-CLEAN object, withdrawn or rights-expired media, or a 3D object.
   - Responses carry `Cache-Control: public, max-age=31536000, immutable` (content-hash URLs), `nosniff`, `Content-Security-Policy: default-src 'none'; sandbox` and `Cross-Origin-Resource-Policy: cross-origin`.
   - There are no direct S3 URLs and no bucket listing.
   - The site and `api-staging` share a registrable domain, so image requests carry the Access cookie, like the existing credentialed API calls. Smoke test S10 verifies this.
5. Withdrawal: `POST /api/v1/catalog/media/<sha>/withdraw`, with a reason.
   - It deletes the source and every variant at once, leaving delete markers.
   - Old versions expire after 30 days.
   - Manifests keep the hashes, and new releases naming the media fail validation.

## 4. Scanner-capacity evidence (mandatory before any scanner decision)

Do not run a scanner to measure it. Collect facts on the running host:

1. Run `13-evidence` with the label `scanner-capacity`. The `veda-collect` document records:

   | File | Contents |
   |---|---|
   | `capacity-memory.txt` | `free -m`, swap, `MemTotal`, `MemAvailable`, `Committed_AS`, memory pressure (PSI) |
   | `capacity-containers.txt` | `docker stats` per container, restart count, OOM-killed flag, start time, memory limit |
   | `capacity-oom.txt` | 14 days of kernel OOM history |

   The evidence object and its SHA-256 go to the evidence bucket under its COMPLIANCE lock.
2. Read the host memory history on the existing CloudWatch dashboard: `CWAgent mem_used_percent`, 14 days, maximum. Note the peak.
3. Record the projection from the authoritative guidance, the ClamAV documentation "Running ClamAV in Docker", section "Memory (RAM) Requirements" (https://docs.clamav.net/manual/Installing/Docker.html). These figures were read on 2026-10-10; re-read them for the pinned version:
   - **Minimum 3 GiB, preferred 4 GiB** of RAM for the ClamAV container.
   - "upwards of 1.2 GiB of RAM simply to load the signature definitions".
   - During a database reload clamd "will use twice the amount of RAM for a brief period". `ConcurrentDatabaseReload no` avoids this, but scans block until the reload completes.
4. The capacity rule for **option A**:

   `MemTotal − (peak current service memory + projected clamd reservation + projected reload peak) ≥ the approved reserve`

   The reserve is an owner decision; the proposal is 25% of memory, 512 MiB on a 2 GiB host. Also required: no OOM kill and no restart in the window.
5. Record the evidence object's SHA-256 in `media_scanner.capacity_evidence_sha256`, and as `scanner_capacity` in the approval record.

## 5. Scanner options (the owner decides; nothing is chosen here)

| | A: clamd on the current host | B: resize the host, then clamd | C: asynchronous S3 scanning |
|---|---|---|---|
| Security posture | Synchronous scan before storing; unscanned or failed objects are never served | Same as A | Scan after upload; objects quarantined until a verdict; equivalent if the adapter quarantines |
| Operational burden | One container, signature updates, alarms already prepared | Same as A, plus a host change | A managed or isolated service, events, adapter code |
| Memory impact | **Precluded.** The ClamAV minimum (3 GiB) exceeds the whole 2 GiB host, so the §4 reserve rule cannot pass, whatever the measured service memory. Only a deliberate owner change to the capacity policy could reopen it | Removes the pressure: the host must give clamd its 3 to 4 GiB beyond the reserve and the current services (t4g.medium is 4 GiB in total, so the size is to be derived from the §4 evidence) | None on the host |
| Infrastructure changes | Decide `media_scanner` (A, `clamd`, image digest) | A reviewed `compute.instance_type` change in staging-platform.json (a stop and start of the host), then as A | New service resources and an event path |
| Application changes | None | None | A new scanner adapter. The app accepts only `none` or `clamd` today, and staging-core refuses any other mode. |
| Monthly cost (plan evidence) | No new AWS resource (container on the existing host) | The instance-type difference shown by that plan; must fit the $25 budget (AUT-112) | The managed service's per-GB and per-object charges, from its plan |
| Failure mode | Memory pressure can restart services; the scanner fails to FAILED (never served) | Same as A, with headroom | Delayed verdicts; PENDING until scanned |
| Rollback | `mode: none`, redeploy: the scanner stops and uploads stay PENDING | Same as A; the size change reverts by a reviewed plan | Revert the adapter and the mode |
| Requires | Not available under the current policy and host | A reviewed host-resize plan; owner cost approval; a validated, pinned ARM64 ClamAV image; the capacity reserve; a rollout and rollback plan | An approved application adapter; an isolated scan architecture; a security and operational review |

## 6. ClamAV implementation readiness (if A or B is chosen)

**ClamAV is not ready to run, and is not claimed to be.** The image digest is still a placeholder (`scanner-image-not-decided` in Compose, `none-selected` in SSM), and every gate refuses it: the Terraform precondition, the host media preflight and `deploy.sh`. ARM64 support, non-root behaviour, the health check and the configuration all still need validating for whichever image is selected. Before the decision is recorded:

1. Choose the official image and tag, and record it **pinned by digest** (`<name>:<tag>@sha256:<64 hex>`) in `media_scanner.clamd_image`.
2. Validate the image on ARM64: the host is Graviton (t4g).
3. Validate that its entrypoint runs with `read_only: true`, the dropped capabilities and the tmpfs mounts, and that it runs `clamd` as a non-root user.
4. Confirm `clamdcheck.sh` exists in the image, or replace the health check.
5. Set `StreamMaxLength 30M`. That is above the application's largest upload: images up to 15 MB, 3D up to 25 MB, still disabled. Use the clamd defaults otherwise, with `ConcurrentDatabaseReload no` if §4 needs it.
6. Confirm freshclam updates the persistent signature volume, and that `MediaSignatureAgeHours` stays under 48.

## 7. Monitoring

All alarms use the existing topic, `veda-stg-alarms`. Missing data is "not breaching", so with no scanner there are no alarms. They count only real events.

| Alarm | Fires when |
|---|---|
| `media-scanner-unavailable` | The scanner could not be reached |
| `media-scan-failed` | A scan did not complete |
| `media-infected` | A file was detected as malware |
| `media-pending-age` | Media waits for a scan for more than 3600 s |
| `media-signatures-outdated` | Signatures are older than 48 hours |
| `media-non-clean-requested` | A released object that is not CLEAN was requested |
| `media-s3-access-denied` | S3 refused the host on the media bucket |
| `media-kms-access-denied` | KMS refused the host for media |
| `scanner-restarts` (host) | The scanner restarted 3 or more times |

No alert carries a filename, key, customer identifier, rate or content.

## 8. CSP delta

When, and only when, the approved V3 page is in the staging build, `_headers` gains this rule:

```
/estimate-v3*
  ! Content-Security-Policy
  Content-Security-Policy: <the site policy with img-src 'self' data: https://api-staging.vedaspaces.com>
```

Cloudflare Pages combines matching rules, and two policies would only narrow each other. So the rule detaches the site-wide policy and restates it with that one change:
- no wildcard and no `blob:`;
- no `media-src` (video is disabled) and no `worker-src` (3D is disabled);
- no production host.

Builds without V3, and production, are unchanged. The browser journey checks that images from other origins are blocked.

## 9. Media-rights governance

Catalog governance applies; there is no second workflow. A media record carries:

| Requirement | Field |
|---|---|
| Version | `record_version` |
| Uploader | The media object's `created_by` |
| Rights basis | `rights.usage` |
| Consent reference | `rights.consent_reference`, required for client permission |
| Attribution | `attribution`, or the rights owner |
| Applicable products, rooms, styles | `products`, `rooms`, `tags` |
| Effective date | `rights.effective_from` |
| Expiry or review date | `rights.expires`, `rights.review_by` |
| Withdrawal status | The media object's `withdrawn_on` |
| Reviewer, four-eyes approval | Record `reviewed_by`; the author can never approve |

**Media-rights approver: [OWNER TO FILL]** (`media_rights.approver`). With it unassigned, the API refuses the catalog in staging (`VEDA_CATALOG_MEDIA_RIGHTS_APPROVER`), and staging-core refuses the flags.

## 10. The V3 staging approval record

The schema is `veda.catalog.v3-staging-approval/1` (`api/veda/modules/catalog/staging_approval.py`). The template is [`v3-staging-approval.template.json`](v3-staging-approval.template.json), status DRAFT. **No approved record exists, and none is created by this work.**

- **Statuses:** DRAFT, IN_REVIEW, APPROVED, REVOKED. A revocation states when and why.
- **APPROVED requires:**
  - every evidence item: `application_commit` and `pr69_merge` as git SHAs, plus the SHA-256 of each of `application_certification`, `real_card_evidence`, `infrastructure_plan`, `infrastructure_apply`, `scanner_capacity`, `scanner_decision`, `media_bucket`, `iam`, `ssm_settings`, `csp`, `media_smoke_test`, `promise_owner_approval` and `media_rights_approver`;
  - an approver who is not the author, and not a placeholder, with an approval date;
  - a scope of staging only, V3, no public intake, no 3D, no video.
- **Gates:**
  - The record enables nothing on its own.
  - The staging build accepts it only when its file SHA-256 equals `catalog_v3.approval_record_sha256`, and staging-core plans the flags only with the same binding.
- **Check a record:** `python -m veda.modules.catalog.staging_approval <record.json>`.

## 11. Feature-flag plan

The activation delta is a reviewed change to `infra/config/staging-platform.json`, all in one PR:

```json
"catalog_v3": {
  "catalog_estimator_enabled": true,
  "catalog_admin_enabled": true,
  "media_delivery_enabled": true,
  "approval_record_sha256": "<SHA-256 of api/veda/modules/catalog/approved/v3-staging-approval.json>"
}
```

It goes together with `media_scanner` and `media_rights` DECIDED, the committed APPROVED record, and the staging build with `STAGING_ESTIMATOR=on` and `STAGING_ESTIMATOR_VERSION=v3`. There is no partial activation.

**Rollback:** every flag false and `approval_record_sha256` null, applied, then redeployed; the build goes back to `STAGING_ESTIMATOR_VERSION=v2`. Production refuses V3 in the API whatever the configuration says.

## 12. Real-card evidence (owner-run)

The procedure is [`CATALOG-V3-real-card-evidence.md`](CATALOG-V3-real-card-evidence.md), unchanged. On the owner's machine, with the private draft-4 card under `~/veda-private`:

```sh
cd api
.venv/bin/python tools/catalog_real_card_evidence.py \
  --card ~/veda-private/<path>/<draft-4 card>.json \
  --expected-sha256 <the card's known canonical fingerprint> \
  --operator "<the owner's name or role>"
```

The artifact goes to `~/veda-private/evidence/`. It contains only:
- the card fingerprint, the commit SHA and the engines;
- the scenarios with their SQLite and PostgreSQL results;
- the equality result, the timestamp and the operator.

It contains no rates. The approval record references only the artifact's `artifact_sha256`.

**Status: OWNER-RUN REAL-CARD EVIDENCE PENDING.**

## 13. Protected-staging smoke tests (designed; not run)

These run on staging after the apply, the scanner decision and an approved record. They use only synthetic, harmless fixtures: no real or customer media. The infected-path fixture is the industry-standard EICAR test string, never real malware.

| # | Check | Expected |
|---|---|---|
| S1 | Anonymous request to `staging`, `app-staging` and `api-staging` | Access login (no content) |
| S2 | V3 page with no approved record | Not in the build (the build refuses V3) |
| S3 | Staff upload without `catalog.media.edit` | 403 |
| S4 | Upload with scanner mode `none` | Stored PENDING; delivery 404 |
| S5 | Upload a synthetic clean image | CLEAN; variants under `variant/` |
| S6 | Upload the EICAR test string | INFECTED; nothing stored; `media-infected` alarm fires |
| S7 | Stop clamd, upload | FAILED; `media-scanner-unavailable` fires; delivery 404; the retry job rescans after clamd returns |
| S8 | Request a released but not-CLEAN object | 404; `media-non-clean-requested` fires |
| S9 | Request a CLEAN, released image through `api-staging` | 200 with immutable caching, `nosniff`, sandbox CSP |
| S10 | Load that image from the V3 page after the Access login | Loads (the Access cookie is sent); no CSP violation |
| S11 | Inject an image from another origin on the V3 page | Blocked by the CSP |
| S12 | Withdraw the image | Delivery 404 at once |
| S13 | Expire the image's rights (a synthetic record) | Delivery 404 at once; the next release refuses it |
| S14 | Direct S3 URL of an object; `ListBucket` from outside | Refused (no public principal) |
| S15 | Turn every V3 flag off (rollback), apply, redeploy | V3 routes 404; the V3 page absent |
| S16 | V1/V2 estimate and lead flows | Unchanged |
| S17 | Production | No change in any plan or deploy |

The results go to `13-evidence` with the label `media-smoke-test`. That evidence SHA-256 is the record's `media_smoke_test`.

## 14. Plan and cost review

The staging-core plan for this branch is produced by `10-infra-plan` on the pull request. It waits for the `staging-plan` environment approval, which only the owner gives. Approving it lets this pull request's code read that environment's secret, so review the code first (runbook §6).

The expected resource delta, from the configuration:

| Change | Resources |
|---|---|
| Media bucket | 1 bucket, plus ownership, public access block, versioning, encryption, lifecycle and policy (7 creates) |
| Host role | The runtime policy updated in place (2 statements added) |
| SSM | 13 configuration parameters created (11 common media settings and flags, plus the inactive clamd address and image) |
| Monitoring | 8 metric filters, 8 application alarms and 1 host alarm created; the dashboard unchanged |
| Evidence document | `veda-collect` updated in place (capacity facts added) |

There is no replacement and no destroy. There is no KMS key, CloudFront distribution, hostname, host resize, public bucket or Object Lock. The plan guard checks every new bucket's controls.

**Cost:** 9 billed custom metrics and 9 standard alarms are added. The bucket and the SSM standard parameters have no fixed charge. Media storage is per GB, negligible for staging. The monthly amount is the AWS price list for those counts, about $3–4 at current standard pricing. The owner confirms it against the $25 budget; it was not taken from a bill.

## 15. Order of operations once the owner decides

1. Merge.
2. 10-infra-plan on main, then 11-infra-apply, digest-bound. Apply staging-core **before** the next 12-deploy: `render-env.sh` now refuses to render without the media settings.
3. Run the scanner-capacity evidence.
4. Record the scanner and rights decisions (reviewed PR), then plan and apply again.
5. 12-deploy: the scanner runs only if decided.
6. Run the real-card evidence (owner).
7. Run the smoke tests.
8. Fill and approve the record (four eyes).
9. Activation PR (§11), then apply and deploy.

## 16. Emergency disable and production blockers

**Emergency:** set every `catalog_v3` flag false, apply, and redeploy. Or set `VEDA_CATALOG_ESTIMATOR_ENABLED=false` and restart, as in the incident runbook. V1 and V2 are unaffected. A withdrawn claim or media item fails closed on its own.

**Production blockers (unchanged):**
- the API refuses every V3 flag in production;
- no production media bucket, scanner, media hostname or CDN;
- no production CSP change;
- an owner production decision and a separate review.

## 17. Pre-plan closure (follow-up to PR #70)

**Approval record, schema 2.** The record now carries an explicit review and expiry policy:

| Field | Rule |
|---|---|
| `environment` | `staging` only; the schema refuses production |
| `approval_scope.protected` | `true`: behind Cloudflare Access |
| `approved_at` | Required; not in the future |
| `review_by` | Required; within 90 days of approval; the approval lapses on that date |
| `expires_at` | Required unless an explicit `non_expiring_decision` is recorded (exactly one of the two) |
| `revoked_at`, `revocation_reason` | Both required for REVOKED, and only for REVOKED |

The approver must be independent of the author, and every evidence item must carry a SHA or SHA-256. Owner values and dates are never filled in automatically; the template stays DRAFT.

The same rules run at four points:

| Where | How |
|---|---|
| Plan | Terraform parses and judges the record whenever a V3 flag is on, against the plan time (`plantimestamp()`): status, schema, scope, independence, evidence, review and expiry dates, digest binding. Any problem fails the plan before an activation change is computed. With every flag off, no record is needed. |
| Build | `staging-build.mjs` repeats the checks against today's date. |
| Deployment preflight | `deploy.sh` runs `python -m veda.modules.catalog.staging_approval` in the new image when V3 is requested, before any snapshot, migration or restart. |
| Activation | On staging, every public V3 request checks the packaged record. A revoked, expired or past-review approval answers 503 at once, so an existing deployment does not stay eligible after its approval expires. |

Changing the policy (any field) changes the record's SHA-256, so the plan and the build refuse the old binding.

**Scanner rollback model.** The scanner states are `none` and `clamd`; an isolated asynchronous scanner is reserved and refused today. The 13 media parameters are always planned:
- **Common:** backend, bucket, KMS ARN, the two prefixes, and the delivery, 3D, video, estimator and admin flags.
- **Scanner-specific:** the clamd address and image. With `none` they are present and inactive (`none-selected`).

So a scanner rollback (`clamd` → `none`) changes values in place and **removes no SSM parameter**. It needs no destroy and no plan-guard exception. The guard is unchanged: tests prove it still refuses removal of any SSM parameter (scanner-specific, common or unrelated), deletion of the media bucket, and replacement of the data key.

The emergency order is enforced by the plan: V3 flags cannot be on with scanner `none`, so the flags go off in the same change or before. The bucket, its bytes, the KMS key, the media records and their audit trail are untouched, and PENDING media is never served.

**Deployment order.**

1. Merge.
2. Reviewed plan.
3. Approved apply.
4. Deployment preflight (`infra/host/media-preflight.sh`, run by `render-env.sh` before `api.env` is replaced).
5. Deployment.

The preflight prints names, never values, and refuses before anything on the host changes. Its states:

| State | Effect |
|---|---|
| **MEDIA INFRASTRUCTURE NOT APPLIED** | A common setting is missing: apply staging-core first. Refused. |
| **SCANNER SETTINGS INCOMPLETE** | `clamd` without a pinned image. Refused. |
| **PARTIAL ACTIVATION** | Some V3 flags on, others off. Refused. |
| V3 activation without clamd | Refused. |
| scanner not selected | Informational; the deploy continues. |
| V3 intentionally disabled | Informational; the deploy continues. |
| **V3 ACTIVATION REQUESTED** | `deploy.sh` then requires a current APPROVED record; otherwise **APPROVAL RECORD INVALID** is refused. |

An unrelated staging deployment after the merge, but before the apply, therefore fails visibly at the first step, with nothing deployed. Production has no such path.

The staging-plan inspection checklist is [CATALOG-V3-staging-plan-inspection.md](CATALOG-V3-staging-plan-inspection.md).

