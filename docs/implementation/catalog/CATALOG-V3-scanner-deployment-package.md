# Catalog V3 scanner deployment and activation package (prepared 2026-10-12; nothing deployed)

Prepared under the owner's direction VEDA-SPACES-SCANNER-ACTIVATION-EXECUTION (2026-10-12): review the scanner
decision, the image pin, the capacity evidence, the deployment sequence, the validation evidence, the remaining
governance decisions and the activation-record prerequisites, and return a deployment package. **This file deploys
nothing and approves nothing.** At the time of writing `media_scanner.mode` is `none`, every `catalog_v3` flag is off,
media delivery is off, and no production environment exists. The verdict is in §7: **SCANNER DEPLOYMENT BLOCKED**,
for the three reasons named there, each with the step that clears it.

Related records: [owner decisions](CATALOG-V3-activation-owner-decisions.md) (AD-1 to AD-8 and the activation
checklist), [scanner implementation](CATALOG-V3-scanner-implementation.md) (the certified service, its validation,
monitoring and rollback), [phase-1 evidence](CATALOG-V3-activation-phase1.md) (capacity figures),
[activation preparation](CATALOG-V3-activation-preparation.md) (dependency matrix, release review practice).

## 1. Verified baseline (2026-10-12)

| Item | State | Verified from |
|---|---|---|
| Host | `t4g.large`, in place; `az_id` pinned `aps1-az1` | `11-infra-apply` run 38236441086 (plan run 38229627339, 1 to add, 3 to change, 0 to destroy) |
| Drift | none: 201 no-op, an outputs-only difference (the budget limit's string form) | `10-infra-plan` run 38237704284, artifact `core-plan-38237704284` |
| Deployed release on the host | the phase-0 release (`12-deploy` run 38163064366, 2026-10-11); its bundle has **no scanner service** and the old `health.sh` | run list; `git diff` of the deployed commit against `main` |
| `main` against the deployed release | API code, migrations, dependencies and frontend unchanged; the deploy bundle differs in six files: `api/deploy/clamd-entrypoint.sh`, `clamd.conf`, `docker-compose.yml` (service `clamd`), `scanner-check.sh`, `infra/host/health.sh` (`ScannerHealthy`), `infra/host/README.md` | `git diff --stat` (pull requests #75, #76, #77) |
| Scanner implementation | certified (pull request #76 merged; validation runs 38199283652 and 38204772069 at the 2048 MiB limit) | scanner implementation record §5, §9, §10 |
| Scanner alarms | `scanner-restarts` and `scanner-unhealthy` exist; `ScannerHealthy` is reported only while the container exists | apply run 38236441086 created the `scanner-unhealthy` alarm |
| AD-1 | recorded as given in pull request #78, **open, not merged**: option B, the pin, the capacity digest, approved mode `clamd`, `mode` `none` | #78: CI run 38241276213 green; pull-request plan run 38241276343: 0 to add, 1 to change (the inert `VEDA_CATALOG_CLAMD_IMAGE` parameter), 0 to destroy |
| On `main` today | `media_scanner` still UNDECIDED, `clamd_image` null, `VEDA_CATALOG_CLAMD_IMAGE` planned as `none-selected` | `infra/config/staging-platform.json` on `main` |
| V3, media delivery, production | every `catalog_v3` flag false, `approval_record_sha256` null, delivery off; no production root, workflow or environment; the API refuses every V3 flag in production | decision file; `infra/terraform/envs` (`staging-core`, `staging-edge` only) |

## 2. Review

### 2.1 AD-1 scanner decision

Recorded as given by the owner's direction of 2026-10-12 in pull request #78 (owner-decisions record, AD-1): scanner
path option B; `clamd_image` = the pin in §2.2; `capacity_evidence_sha256` = the digest in §2.3; approved scanner mode
`clamd`; `mode` `none` until the scanner deployment, because `deploy.sh` step 4c starts the scanner Compose profile
whenever the rendered configuration carries `VEDA_CATALOG_MEDIA_SCANNER=clamd`. Until #78 is merged and its one
parameter applied, nothing of AD-1 is on `main` or on the host. **Finding: the decision is complete and consistent
with the evidence; it is not yet effective.**

### 2.2 Image digest pin

| Item | Value |
|---|---|
| Pin | `clamav/clamav:1.4.6-debian13-slim@sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b` |
| Provenance | the default of workflow 14 (`14-scanner-image-validation.yml`); validated on arm64 by runs 38199283652 and 38204772069 (the second on the corrected PID 1 entrypoint); LTS line; the `-debian13-slim` variant is multi-arch (the plain tags are amd64 only) |
| Where it must be identical | `staging-platform.json` → `media_scanner.clamd_image` (pull request #78); the SSM parameter `VEDA_CATALOG_CLAMD_IMAGE` (planned from it); the rendered `/etc/veda/api.env`; `deploy.sh` step 4c exports it as `VEDA_CLAMD_IMAGE` for the Compose service `image: ${VEDA_CLAMD_IMAGE:-scanner-image-not-decided}` |
| Refusals | `deploy.sh` refuses to start the scanner unless the value matches `name[:tag]@sha256:<64 hex>`; `media-preflight.sh` refuses `clamd` without a pinned image; staging-core's `catalog_v3` output refuses `mode` `clamd` without option B and a pinned image; `infra/tests/run.sh` AUT-108 fails if the recorded pin differs from the workflow 14 default |
| Pull | Docker Hub over the host's `tcp/443` egress (the same path cloudflared and Litestream use); the digest makes the pull content-addressed |

**Finding: one pin, four places, every place checked; no other image can start.**

### 2.3 Capacity evidence digest

| Item | Value |
|---|---|
| Digest | `ab25630c5f0e8b2934a8181acd9b55dc5a59de21e05c778d8cefc1da05058517` |
| Object | `scanner-capacity-20261011T184622Z.tgz`, `13-evidence` run 38164988919 (label `scanner-capacity`), evidence bucket, COMPLIANCE-locked |
| What it shows | the host's memory facts on the 2 GiB host before the resize (`free`, `/proc/meminfo`, PSI, container stats, the 14-day kernel OOM history); the clamd figures themselves come from the arm64 harness (steady about 1.05 GiB, first-load peak 1.63 GiB, no reload growth with `ConcurrentDatabaseReload no`) |
| What it does not show | the host after the resize with clamd running; that is the `scanner-validation` collection of §2.5, which becomes the record's `scanner_decision` evidence (the capacity digest is its `scanner_capacity` evidence) |

**Finding: the digest is the one the phase-1 record, the evidence-reference matrix and AD-1 carry; it is pre-resize
evidence by design, and the post-resize confirmation is a separate collection.**

### 2.4 Scanner deployment sequence

The sequence is the checklist in §3. Its shape: merge and apply AD-1 (an inert parameter), then a reviewed change of
`media_scanner.mode` to `clamd` (one more in-place parameter), then one `12-deploy` from `main` whose step 4c starts
the pinned image and waits for `PONG`, then a soak, then the evidence collection. Engineering recommends one extra
step before the mode change: a `12-deploy` of `main` with the mode still `none`, so the new bundle (six files) and the
new `health.sh` are proven on the host without the scanner, and the scanner deploy later changes one thing. The owner
may collapse the two deploys into one; §3 marks the step optional.

### 2.5 Scanner validation evidence requirements

The `13-evidence` collection with the label `scanner-validation` runs the `veda-collect` SSM document; its tarball
digest becomes AD-1's evidence row and the activation record's `scanner_decision` evidence. The document records
facts only (no secrets, no personal data). For the collection to count as scanner validation, its files must show,
after a soak of at least 24 hours (one freshclam cycle: `FRESHCLAM_CHECKS=2` a day, the `media-signatures-outdated`
alarm at 48 h):

| File in the tarball | Requirement |
|---|---|
| `containers.txt` (`docker images --digests`, `docker ps -a`) | the `clamd` image digest equals the pin; `deploy-clamd-1` is `Up` and `(healthy)`; the API, worker, scheduler, Litestream and cloudflared containers are up; no exited scanner container |
| `capacity-*.txt` (`free -m`, `/proc/meminfo`, PSI) | `MemAvailable` at least 1,950 MiB with clamd loaded (the 25 % reserve of AD-2 on an 8 GiB host, phase-1 record §4.3); no swap; memory pressure `some` and `full` averages near zero |
| container stats and inspect | the clamd container's memory below its 2,048 MiB limit; `restarts=0` and `oom_killed=False` for every container |
| kernel OOM history (14 days) | no `out of memory` or `oom-kill` line |
| `deploy-log-tail.txt` | the lines `4c. Scanner: clamd on the private Compose network` and the `5. Deploy` readiness line from the scanner deploy |
| `listeners.txt` | only loopback listeners; no host port for 3310 |
| `storage.txt` | root and data volumes below the 85 % and 80 % alarm thresholds after the image pull and the signature database |
| Outside the tarball, read by the reviewer and cited by run ID or alarm name | `ScannerHealthy` = 1 over the soak and `ScannerRestarts` = 0 (CloudWatch, `Veda/Host`); `scanner-unhealthy`, `scanner-restarts` and `media-signatures-outdated` in OK; a freshclam update line in the `/veda/staging/app` log group; `api/deploy/scanner-check.sh` exit 0 on the host (owner session) |

A collection that misses any row is not scanner validation; the scanner stays deployed or is rolled back (§6 of the
scanner record), and the collection is repeated after the cause is fixed.

### 2.6 Remaining governance decisions

| Record | State (pull request #78) | What the scanner deployment needs from it |
|---|---|---|
| AD-1 | DECIDED, recorded as given; not on `main` | the merge and the apply (§3 steps 1 and 2) |
| AD-4 media-rights approver | UNDECIDED: role, backup rule and workflow defined; both names blank | nothing for the scanner; required before any media approval and before activation |
| AD-5 withdrawal during a lapse | DECIDED, recorded as given; the implementing change is not written | nothing for the scanner; the change is reviewed before the activation pull request |
| AD-6 record roles and dates | UNDECIDED: separation defined; names, dates and the `media_delivery` value blank | nothing for the scanner; the record cannot be written without them |
| AD-7 smoke-test sequencing | DECIDED: option (b); the pre-activation subset not yet run | the subset needs the scanner running (uploads need a scan) and the media-rights approver |
| AD-8 promise-owner approval | UNDECIDED: procedure defined; no document | nothing for the scanner; required for the record |

The scanner deployment depends on AD-1 only. Activation depends on all of them.

### 2.7 Activation-record prerequisites

The record `V3-STAGING-1` (`veda.catalog.v3-staging-approval/2`) needs every evidence item below with a reference of
at least eight characters and the SHA, an approver who is not the author, `approved_at`, `review_by` within 90 days,
exactly one of `expires_at` and `non_expiring_decision`, and then the digest binding in `catalog_v3`.

| Evidence item | Status on 2026-10-12 | Source |
|---|---|---|
| `application_commit` (git SHA) | available: the certified application on `main` (unchanged since the deployed release) | the activation pull request names it |
| `pr69_merge` (git SHA) | available | allowlisted merge commit of pull request #69 |
| `application_certification` | available | the certification record's digest (phase-0 release evidence) |
| `real_card_evidence` | available | owner-run evidence of 2026-10-11 (phase-1 record §5) |
| `infrastructure_plan`, `infrastructure_apply` | available for the media apply and the resize; the activation plan's own digest comes with the activation pull request | plan and apply run summaries |
| `scanner_capacity` | available: §2.3 | `13-evidence` run 38164988919 |
| `scanner_decision` | **missing**: needs the scanner running on the host and the §2.5 collection | `13-evidence` `scanner-validation` |
| `media_bucket`, `iam`, `ssm_settings`, `csp` | available from the media apply evidence and the plan artifacts | pre-plan closure and phase-0 records |
| `media_smoke_test` | **missing**: the pre-activation subset of AD-7 option (b) has not been run | `13-evidence` `media-smoke-test` |
| `promise_owner_approval` | **missing**: AD-8 | owner document outside Git |
| `media_rights_approver` | **missing**: AD-4 | the primary approver's signed acceptance note |
| Author, approver, dates, `media_delivery` | **missing**: AD-6 | the record itself |

## 3. Scanner deployment checklist

Every step is owner-approved or owner-reviewed; engineering prepares and verifies. Steps 1 to 3 are the blockers of
§7. "Plan expectation" is a stop signal when it differs.

| # | Step | Who | Gate or approval | Expected result and evidence |
|---|---|---|---|---|
| 1 | Merge pull request #78 (AD-1 recorded; `mode` `none`) | independent reviewer; the owner merges | reviewed merge | AD-1 on `main`; CI green (run 38241276213 on the head) |
| 2 | `10-infra-plan` on `main` (runs on the push), then `11-infra-apply` of its digest | owner approves `staging-plan`, then `staging-infra` | plan guard; the apply approval names the digest | **0 to add, 1 to change, 0 to destroy**: `module.ssm.aws_ssm_parameter.config["VEDA_CATALOG_CLAMD_IMAGE"]` in place, output `scanner_option` B (the pull-request plan 38241276343 showed exactly this); drift plan afterwards: no resource change |
| 3 | Mode change: a reviewed pull request that sets `media_scanner.mode` to `clamd` and nothing else in the decision file (the decision text gains the date and the deploy run that follows); it updates the committed-decision checks that pin `mode` `none` (`infra/tests/run.sh` AUT-108, `core.tftest.hcl` `media_settings_planned_with_every_flag_off`, `test_activation_phase1_docs.py`) and AD-1's "`mode` in this change" row | engineering authors; independent reviewer; the owner merges | CI green; `stack.sh decisions` still passes (no PROPOSED) | the diff touches no scanner implementation file, no `catalog_v3` flag, no `media_rights` value |
| 4 | Plan and apply of the mode change | owner approves `staging-plan`, then `staging-infra` | plan guard | **0 to add, 1 to change, 0 to destroy**: `VEDA_CATALOG_MEDIA_SCANNER` `none` to `clamd` in place; no parameter removed (the staging-core test `scanner_rollback_removes_no_parameter` covers the reverse) |
| 5 (optional, recommended) | `12-deploy` of `main` **before step 4** with the mode still `none`: a bundle refresh (six files, no application change, no migration) | owner approves `staging` | preflight: gates decided, no PROPOSED; image scan without HIGH or CRITICAL | `deploy.sh` line `4c. Scanner: not selected (VEDA_CATALOG_MEDIA_SCANNER=none); media uploads stay PENDING`; `/health/ready` at the unchanged migration head; `health.sh` keeps reporting `HealthReady` and reports no scanner metric (no container) |
| 6 | Pre-deploy checks for the scanner deploy | engineering reads; owner confirms | — | root volume headroom for the image pull and the signature database (root alarm at 85 %); the rollback change of step 9 prepared; the `scanner-unhealthy` and `scanner-restarts` alarms in OK or INSUFFICIENT_DATA; the deploy's own pre-deploy snapshot (step 2 of `deploy.sh`) will run |
| 7 | `12-deploy` of `main` with the mode `clamd` (the scanner deploy) | owner approves `staging` | preflight: `media-preflight.sh` prints `scanner: clamd (pinned image)` and `V3 intentionally disabled`; image scan clean | `deploy.sh`: `4c. Scanner: clamd on the private Compose network`, the image pulled by digest, `PONG` within 15 minutes (measured 10 s to PONG; `start_period` 300 s), then `5. Deploy` and `/health/ready`; flags after the deploy: every V3 and delivery flag false, `VEDA_CATALOG_MEDIA_SCANNER=clamd`. If step 4c refuses, the deploy stops before the API restart; recovery is step 9 |
| 8 | Soak of at least 24 hours | engineering watches; owner reads the alarms | — | `ScannerHealthy` 1, `ScannerRestarts` 0, the three scanner and signature alarms in OK, one freshclam update observed, memory headroom per §2.5; `scanner-check.sh` exit 0 |
| 9 | Rollback readiness (prepared, not run) | engineering prepares the change | reviewed change | `media_scanner.mode` back to `none`: plan 0 to add, 1 to change, 0 to destroy; the next `12-deploy` runs `--profile scanner rm -s -f clamd`; uploads stay PENDING; the `clamav-db` volume and the image remain until pruned (scanner record §6) |
| 10 | `13-evidence` with the label `scanner-validation` | owner approves `staging-evidence` | `13-evidence` runs from `main` only, gates decided | the tarball meets every row of §2.5; its SHA-256 and S3 key are read from the run log |
| 11 | Record the evidence | engineering authors; independent reviewer; the owner merges | reviewed change | AD-1 gains the `scanner-validation` digest and run ID; the dependency matrix rows "Scanner health evidence" and `scanner_decision` move to DONE; nothing else changes |

Rollback at any step after 7 is step 9. A host size revert is possible only after the mode is `none` again.

## 4. Required evidence

| Evidence | Produced by | Used for |
|---|---|---|
| AD-1 merge: pull request #78, CI run 38241276213, plan run 38241276343 (0/1/0) | done | step 1 |
| Plan and apply run IDs and digests for the AD-1 parameter and for the mode change | steps 2 and 4 | the activation record's `infrastructure_plan` and `infrastructure_apply` references for this stage; AD-1's record |
| `12-deploy` run IDs (the bundle refresh, the scanner deploy), with the `4c` and `5` lines and the preflight lines | steps 5 and 7 | AD-1's record; the release review practice (preparation record §3) |
| Soak readings: `ScannerHealthy`, `ScannerRestarts`, the alarm states, the freshclam log line | step 8 | §2.5 |
| `scanner-validation` tarball: S3 key, SHA-256, run ID | step 10 | the record's `scanner_decision` evidence; AD-1 |
| Rollback change prepared (branch or diff), never applied unless needed | step 9 | step 7's recovery |

## 5. Required approvers

| Approval | Who | Where |
|---|---|---|
| Pull request reviews: #78, the mode change (step 3), the evidence record (step 11), the rollback change if used | an independent reviewer; the owner merges (the reviewed merge is the acceptance in the repository model) | GitHub |
| `staging-plan` | the owner (required reviewer) | `10-infra-plan`, steps 2 and 4 |
| `staging-infra` | the owner (required reviewer), approving the named plan digest | `11-infra-apply`, steps 2 and 4 |
| `staging` | the owner (required reviewer) | `12-deploy`, steps 5 and 7 |
| `staging-evidence` | the owner (required reviewer) | `13-evidence`, step 10 |
| Owner session on the host (read-only probe) | the owner | `api/deploy/scanner-check.sh`, step 8 |
| AD-4, AD-6, AD-8 and the activation record's approver | the owner names them; the record's approver signs | not needed for the scanner deployment; needed for activation |

No step in this package is engineering's to approve. Engineering authors the changes, reads the runs and writes the
records.

## 6. Remaining blockers

For the **scanner deployment** (in order; each clears with the step named):

1. Pull request #78 is open: AD-1 is not on `main` and the pin is not planned (step 1).
2. The AD-1 parameter is not applied (step 2).
3. No reviewed change sets `media_scanner.mode` to `clamd`, and the committed-decision checks pin `none` (steps 3 and 4).

For **activation** (unchanged from the governance pass; owner-decisions record, checklist): AD-4 names and signed
notes; AD-6 names, dates and the `media_delivery` value; AD-8 document; the AD-5 implementing change; the
`scanner-validation` and `media-smoke-test` evidence; the record `V3-STAGING-1` with its approver; the activation pull
request with the digest binding. Production stays blocked by design.

## 7. Verdict

**SCANNER DEPLOYMENT BLOCKED.** The decision, the pin, the capacity evidence, the certified service, the resized host
and the alarms are in place; the three blockers of §6 are governance steps (a merge, an apply, a reviewed one-value
change), not engineering gaps. When steps 1 to 4 of §3 are done, the package of §3 steps 5 to 11 is the scanner
deployment, and this file's verdict is re-stated as READY FOR SCANNER DEPLOYMENT by a reviewed update.

Nothing was activated, enabled, deployed or changed in production by this package as prepared. Every V3 flag is off,
media delivery is off; the scanner mode was `none` when it was written (§8 records what the execution changed).

## 8. Execution record (2026-10-12, owner direction VEDA-SPACES-SCANNER-DEPLOYMENT-EXECUTION)

The three blockers of §6 cleared the same day and the deployment ran. Every run below is an owner-approved
environment run; the pull requests are reviewed merges.

| § 3 step | Run or change | Result |
|---|---|---|
| 1 | Pull request #78 merged (12:04 UTC) | AD-1 on `main` |
| 3 | Pull request #80 merged (12:50 UTC): `media_scanner.mode` `clamd`, one decision value | CI green; the review-only plan showed the mode parameter |
| 2 and 4 (one apply) | `10-infra-plan` run 38251677019 on `main`, digest `b7fd8a72b693cda00bcf3421c5783614d162d40c2edc10c3794b2e8a58805b4b`; `11-infra-apply` run 38252118680 | **0 to add, 2 to change, 0 to destroy**: `VEDA_CATALOG_CLAMD_IMAGE` to the pin and `VEDA_CATALOG_MEDIA_SCANNER` to `clamd`, both in place; apply complete, 0 added, 2 changed, 0 destroyed |
| 7, first attempt | `12-deploy` run 38252332555 | **Refused at step 2, the image scan**: two new HIGH findings in the base image's glibc 2.41-12+deb13u4 (CVE-2026-5435, CVE-2026-19499), unfixed in Debian trixie (no-dsa); nothing reached the host |
| gate exception | Pull request #81 merged (13:31 UTC): two reviewed staging exceptions, each approved by the owner through the review, expiring 2026-12-31; the stale gcc-14 exception retired ([policy](../../operations/image-scan-exceptions.md)) | the API code was unchanged; the findings are not reachable from it |
| 7 | `12-deploy` run 38256345183 (13:37 UTC) on `main` at the merge of pull request #81 | image `veda-api@sha256:5d92f4d3775ddd6cf5443b52df2c28973cb3c8dfdb441a78c4434a552123f986`; scan gate: 3 HIGH findings, all covered; bundle SHA-256 `54f34b072860c3862d180edb22216bfb9186e884de8c2d53ba83cd6b035d2453` verified on the host; media preflight `scanner: clamd (pinned image)` and `V3 intentionally disabled: every V3 and media-delivery flag is false`; `veda-deploy` ended Success, which the deploy script reports only after step 4c received `PONG` from clamd and step 5 passed `/health/ready`. The host-side step lines are truncated in the run output (the SSM plugin's output limit) |
| drift | `10-infra-plan` run 38257133680 on `main` after the apply | **No changes**, 201 no-op |
| post-deploy snapshot | `13-evidence` run 38257129126, label `scanner-deploy-verify` | `s3://veda-evidence-813238078849/host/2026-10-12/i-01538ad0e744faaff/scanner-deploy-verify-20261012T134234Z.tgz`, SHA-256 `270f243d000a309d660e92f7476f5636d73b80db2c6bb919a2079138eaf7e9be`; a snapshot at deploy time, not the validation evidence |
| 8 | Soak | started 13:37 UTC on 2026-10-12; at least 24 hours |
| 10, 11 | `scanner-validation` collection and its record | pending the soak |
| 5 | Bundle-refresh deploy before the mode change | not taken: the owner collapsed the two deploys into one |

Not yet verified from host facts, because the evidence tarball lives in the locked evidence bucket and the SSM
output is truncated: the container's Docker health state, the pulled image digest as Docker reports it, the
FreshClam log line, and the listeners list. They are read from the tarball by the owner (or from
`api/deploy/scanner-check.sh` in an owner session) and from the `scanner-validation` collection after the soak. What
the certified configuration guarantees by construction: user 1000:1000, read-only root, every capability dropped, no
privileged mode, port 3310 on the private Compose network only, the image equal to the SSM parameter (the deploy
script's digest check), and the 2048 MiB limit. EICAR detection, the oversized-stream refusal, restart and recovery
and the absence of OOM kills are proven by the arm64 harness runs 38199283652 and 38204772069 on this image; no
host-level repetition exists yet.

**Re-stated verdict (2026-10-12, 13:45 UTC): the scanner is deployed; the soak and the validation evidence are
pending.** V3 flags, media delivery and production are unchanged.
