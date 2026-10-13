# MTQ B1-T11 — attachment storage on staging

**Status: PLANNED, AWAITING CONTROLLED APPLY.** This change adds the private attachments bucket, the host's access to it, two alarms and seven inert SSM settings. It applies nothing by itself. The site measurement flag `VEDA_MTQ_SITE_ENABLED` is planned as `false` and staging-core refuses any other value in this change. Production has no attachment storage and the API refuses the flag in production.

**Sources:** blocker closure §6.4 (bucket shape, frozen and merged by the owner with pull request #86), §6.3 (scanning), §6.5 (visibility); B1-SCOPE §2.8; the media infrastructure of pull request #70, reused as the pattern.

## 1. What is planned

| Area | Change | Control |
|---|---|---|
| Bucket | `veda-stg-attachments-<account>` from the existing storage module | SSE-KMS with the existing data key and a bucket key; versioning; all four public-access blocks; ACLs disabled (BucketOwnerEnforced); TLS only; this account only; `prevent_destroy`; no Object Lock, so a withdrawal or an erasure removes the current version at once |
| Bucket policy | Deny uploads without `aws:kms` and without the data key (by key ARN or alias ARN) | Same statements as the media bucket. The policy grants nothing; access comes from the host role only |
| Lifecycle | Noncurrent versions expire after 30 days, with expired delete markers removed; current objects move to Intelligent-Tiering after 90 days; uploads under `upload/` that were never completed expire after 2 days; incomplete multipart uploads abort after 7 days | Closure §6.4 for the first two; the abandoned-upload rule is a B1-T11 addition (the API deletes completed uploads itself) |
| Host role | Get, Put and Delete on `upload/*` and `att/*`; List only with those prefixes | No version delete, tagging, ACL or bucket action; the explicit administration deny is unchanged; no new KMS permission (the existing data-key grant by alias covers it). A pre-signed POST acts with these permissions, so a browser can write only under `upload/` |
| SSM settings | `VEDA_MTQ_SITE_ENABLED=false`, `VEDA_ATTACHMENT_BACKEND=s3`, `VEDA_ATTACHMENT_BUCKET`, `VEDA_ATTACHMENT_KMS_KEY_ARN` (data key alias), `VEDA_ATTACHMENT_SCANNER` (the media scanner mode, clamd), `VEDA_ATTACHMENT_CLAMD_ADDRESS=clamd:3310`, `VEDA_ATTACHMENT_UPLOAD_TTL_SECONDS=300` | Inert while the flag is false: every site and attachment route answers 404. The running image ignores unknown variables, so the parameters may be applied before a deploy |
| Monitoring | Log metric filters `AttachmentInfected` and `AttachmentObjectMissing`; alarms `attachment-infected` and `attachment-object-missing` on the existing topic | Counts only. The scanner-unavailable, scan-failed, S3-denied and KMS-denied signals are shared with media (the kernel media module emits them for both); the two S3 and KMS alarm descriptions now say "media or attachments" |
| Host preflight | `infra/host/attachment-preflight.sh`, run by `render-env.sh` before `api.env` is replaced | Flag off: nothing required. Flag on: every attachment setting present, backend `s3`, scanner `clamd`, or the render is refused. Prints names, never values |
| Staging workspace CSP | `connect-src` adds exactly `https://veda-stg-attachments-<account>.s3.ap-south-1.amazonaws.com` | Built from the reviewed account manifest; a wildcard or another bucket is refused; the production `_headers` names no bucket |
| API | The attachment store uses a regional, virtual-hosted S3 client with SigV4, so pre-signed POSTs go to the origin the CSP names | Catalog media keeps its existing client |
| Browser upload | The pre-signed POST is sent with `mode: 'no-cors'` and no credentials | See §2 |

## 2. Upload without CORS

The closure froze "the API never proxies bytes in staging or production". The plan guard refuses bucket CORS outright, because CORS bypasses the S3 endpoint policy (AUT-103). Both rules hold:

1. The browser sends the multipart POST as a simple request. S3 stores the object if the signed conditions hold: key, exact length, content type, KMS headers and expiry.
2. The browser cannot read S3's answer. It does not need to. It calls `POST /attachments/{id}/complete`, and the server reads the object back and checks length, SHA-256 and image type before anything else.
3. If the object has not arrived, completion answers `409 UPLOAD_NOT_RECEIVED` and the photo stays queued as UPLOADING. A retry first asks `GET /attachments/{id}` for fresh instructions, because a signature lives five minutes.

No CORS rule, no plan-guard exception and no API byte relay are needed.

## 3. Expected plan

Pull-request plans of `10-infra-plan` run in the `staging-plan` environment and wait for its required reviewer. The expected change set, assuming the rest of `main` is applied (a drift run shows no changes):

| Module | Create | Update in place | Destroy |
|---|---|---|---|
| storage: the bucket and its six companion resources | 7 | 0 | 0 |
| ssm: the seven attachment parameters | 7 | 0 | 0 |
| monitoring: two filters, two alarms; two alarm descriptions | 4 | 2 | 0 |
| runtime-iam: the host policy | 0 | 1 | 0 |
| **Total** | **18** | **3** | **0** |

B1-T12 adds one more parameter, `VEDA_MTQ_SITE_ENABLEMENT_SHA256` (value `none`), so the merged pull request plans 19 to add. Anything else in the plan is unexpected and blocks the apply. The real counts and the plan SHA-256 come from the plan run's summary.

### 3.1 Pull-request plans (review only)

| Run | Head | Result | Plan digest |
|---|---|---|---|
| 38349670906 | B1-T11 | 19 to add, 4 to change, 0 to destroy; plan guard passed | `sha256:3338a3ae7eb13a209a803ae3b4739e90508bb3528d373e535f38bdd2541eee78` |
| 38352456157 | B1-T12 | 20 to add, 4 to change, 0 to destroy; plan guard passed | `sha256:4081bcf057289e36bbcdb3e9af61620f3cbfc45a270bc7a56e1549f56f3c9138` |

Against §3 (with B1-T12's parameter, 19 / 3 / 0) the B1-T12 plan has two more items:

- **`module.monitoring.aws_cloudwatch_dashboard.staging` updated in place.** Caused by this change: the dashboard lists every alarm, so the two attachment alarms join it. The estimate in §3 missed it. Expected.
- **`module.monitoring.aws_sns_topic_subscription.owner` created.** Not caused by this change: the subscription code is unchanged, and the plan of `main` on 2026-10-12 (run 38257133680) showed no changes. The owner's email subscription to `veda-stg-alarms` has gone from AWS since then. Applying recreates it and AWS sends a confirmation email the owner must accept. **Owner decision:** accept it in this apply, or restore it separately first.

Nothing else differs. Pull-request plans are for review; the apply needs a `workflow_dispatch` plan on `main` and its own digest.

## 4. Cost

An estimate from list prices, not a bill. Two custom metrics and two standard alarms add about USD 0.80 a month. Storage for ten survey sites is a few hundred photos at about 1 MB each, well under 1 GB. Intelligent-Tiering monitoring applies only to objects over 128 KB and costs a fraction of a cent here. The owner confirms against the staging budget (AUT-112) after the first bill.

## 5. Controlled apply

The apply is the owner's, through the existing gates. Nothing here is applied by the implementation session.

1. Independent review of this change and merge to `main`.
2. `10-infra-plan` by `workflow_dispatch` on `main`; the owner approves the `staging-plan` environment.
3. The plan matches §3 exactly: 18 to add, 3 to change, 0 to destroy, nothing outside the four modules, and the plan guard passes.
4. The owner dispatches `11-infra-apply` with that plan run and its SHA-256, and approves `staging-infra`.
5. A drift run shows no changes.

## 6. Rollback

- Before any photo is stored: revert this change and plan again. The bucket has `prevent_destroy`, so removing it needs a separate, owner-approved change that first lifts that protection. An empty bucket costs nothing.
- After photos exist: keep the bucket. Set `VEDA_MTQ_SITE_ENABLED` false, which is the planned value, and every route answers 404. The objects follow their lifecycle and the lead-retention job.
- The SSM parameters are never removed. The plan guard refuses parameter deletions, so a rollback changes values in place.

## 7. Tests

| Suite | Result |
|---|---|
| `make -C infra check`: format, validate, Terraform tests of every root and module, 872 script and plan-guard tests, tflint, checkov, shellcheck, actionlint | pass |
| storage module: the bucket, its policy, lifecycle and bounds | 12 runs pass |
| runtime-iam: prefixes, actions, no new KMS grant, a production bucket refused | 10 runs pass |
| monitoring: counts (17 filters; 18 and 24 custom metrics), the topic, missing data | 10 runs pass |
| staging-core: settings planned and inert, the flag false, an undecided policy or an over-long upload refused | 30 runs pass |
| API: regional pre-signed URL (offline botocore), the S3 store built with the region | pass |
| app: no-cors upload, completion as proof of arrival, fresh instructions on retry, the staging CSP | pass |
