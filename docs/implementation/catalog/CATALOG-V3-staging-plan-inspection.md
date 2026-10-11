# Catalog V3 media: staging-plan inspection checklist (owner)

**No plan result is claimed here.** This is the checklist for when the owner approves the `staging-plan`
environment and runs `10-infra-plan` on `main`, after the pre-plan closure PR is merged. Nobody approves that
environment on the owner's behalf.

**Before approving the run:** approving it lets the code of the run read the `staging-plan` environment's secret.
Approve only a run of reviewed `main`.

## How to read the plan

The workflow summary shows the change counts and the plan's SHA-256; the plan guard has already run. The plan text and
JSON are published only under gate N-04-S. Otherwise inspect them from an owner session with
`infra/scripts/stack.sh`, as the runbook `docs/operations/staging-infra-workflows.md` describes.

## Checklist

Tick each item. **Any unexpected item: do not apply.**

| # | Check | Expected |
|---|---|---|
| 1 | Resource creates | Only the media bucket and its controls: `aws_s3_bucket.this["media"]`, plus ownership controls, public access block, versioning, server-side encryption, lifecycle and policy (7). Also 13 `aws_ssm_parameter.config[...]`, 8 `aws_cloudwatch_log_metric_filter.app[...]`, 8 `aws_cloudwatch_metric_alarm.app["media-..."]` and 1 `aws_cloudwatch_metric_alarm.host["scanner-restarts"]`. |
| 2 | In-place updates | `aws_iam_policy.runtime` (the host policy gains `CatalogMediaObjects` and `CatalogMediaListPrefixes`); `aws_ssm_document.collect` (the capacity facts); monitoring outputs. |
| 3 | SSM values | `VEDA_CATALOG_MEDIA_BACKEND=s3`; `VEDA_CATALOG_MEDIA_BUCKET=veda-stg-media-<account>`; `VEDA_CATALOG_MEDIA_KMS_KEY_ARN=arn:aws:kms:ap-south-1:<account>:alias/veda-stg-data`; prefixes `source/` and `variant/`; `VEDA_CATALOG_MEDIA_SCANNER=none`; `VEDA_CATALOG_CLAMD_IMAGE=none-selected`; `VEDA_CATALOG_CLAMD_ADDRESS=clamd:3310`; and **every flag `false`**: delivery, 3D, video, catalog estimator, catalog admin. No `VEDA_CATALOG_MEDIA_RIGHTS_APPROVER`. |
| 4 | Replacements | **None** (no `delete, create` or `create, delete` pair). |
| 5 | Destroys | **None** (the plan guard refuses any). |
| 6 | Production | **No change.** The stack is staging-only; the provider is pinned to the staging account. |
| 7 | KMS | **No `aws_kms_key` create or change.** The data key is reused by alias. |
| 8 | CloudFront | **None.** |
| 9 | Hostname, DNS | **None.** The edge is unchanged. |
| 10 | Host size | **No `aws_instance` change.** `t4g.small` is unchanged. |
| 11 | Scanner | **No active ClamAV.** The scanner mode is `none`, and the Compose `scanner` profile is not started by any deploy. |
| 12 | Media delivery | **Off** (`VEDA_CATALOG_MEDIA_DELIVERY_ENABLED=false`). |
| 13 | Bucket name | `veda-stg-media-<account>`, with tags `Name` and `purpose=media`. |
| 14 | Bucket encryption | `aws:kms` with `kms_master_key_id` = the data key ARN, and `bucket_key_enabled=true`. The policy denies a `PutObject` that names another KMS key or a non-KMS encryption type (`StringNotEqualsIfExists`); an upload with no encryption header is encrypted by the bucket default with the data key. |
| 15 | Lifecycle | `abort-incomplete-uploads` after 7 days; `noncurrent-media`: noncurrent versions expire after **30** days and expired delete markers are removed. **No Object Lock.** |
| 16 | IAM prefixes | Get, put and delete only on `arn:aws:s3:::veda-stg-media-<account>/source/*` and `.../variant/*`; `ListBucket` only with `s3:prefix` `source/*` or `variant/*`. No KMS statement added. |
| 17 | Metric and alarm count | +8 log metric filters (15 in all), +1 host metric: **+9 custom metrics** (21 with the host). +8 application alarms and +1 host alarm: **+9 alarms**. All on the existing topic `veda-stg-alarms`. |
| 18 | Cost | **An estimate only:** about USD 3 to 4 a month at the standard CloudWatch list price for 9 custom metrics and 9 alarms. There is no fixed charge for the bucket or the standard SSM parameters, and storage is negligible. Confirm against the USD 25 budget (AUT-112) after the first month's bill. |

## After the checklist

1. If every item matches, the owner may approve the apply (`11-infra-apply`, digest-bound) in a separate step.
2. After the apply, the next `12-deploy` passes the media preflight with **"V3 intentionally disabled"** and **"scanner not selected"**.
3. Before the apply, a deploy refuses with **MEDIA INFRASTRUCTURE NOT APPLIED**, and nothing changes.
4. The scanner decision, real-card evidence, smoke tests and approval record remain separate, later steps (runbook §15).

## Status and the next plan

**Applied 2026-10-11** (`11-infra-apply` run 38106639695, plan run 38106264925): 38 added, 3 changed, 0 destroyed.
That plan also created `module.monitoring.aws_sns_topic_subscription.owner`. It recurs while the owner has not
confirmed the alarm-topic email, because AWS drops a pending subscription. A follow-up plan
(run 38106962562) showed no changes.

**After the activation-remediation PR merges**, the next staging-core plan should be exactly:

| # | Check | Expected |
|---|---|---|
| 1 | Creates | `module.ssm.aws_ssm_parameter.config["VEDA_CATALOG_APPROVAL_SHA256"]`, value `none`. Plus the owner email subscription only if it is still unconfirmed. |
| 2 | Updates, replacements, destroys | None. `module.v3_approval` has no resources. |
| 3 | Everything else | As above: no KMS, CloudFront, hostname, host-size or production change; every flag `false`; scanner `none`. |

