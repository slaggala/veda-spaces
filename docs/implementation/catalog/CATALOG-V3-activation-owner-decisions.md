# Catalog V3 activation: owner decision records (UNDECIDED until the owner fills them)

Prepared 2026-10-11 during the activation-preparation workstream
([CATALOG-V3-activation-preparation.md](CATALOG-V3-activation-preparation.md)). Every record below was prepared as a
**proposal with the human fields left blank**. Nothing in the code reads this file. A decision takes effect only when
it is recorded in the file named under "Where it is recorded", through a reviewed pull request, with status `DECIDED`
(a `PROPOSED` status in `infra/config/staging-platform.json` stops every 12-deploy until it is resolved).

Update 2026-10-12 (pull request #77): AD-2 and AD-3 are recorded, as given by the owner's direction
VEDA-SPACES-PR77-REBASE-AND-PLAN-CERTIFICATION (option B, `t4g.large`, the documented reserve policy, a 60 USD
ceiling), in `infra/config/staging-platform.json`, `staging-network.json` and `staging-budget.json`; they take effect
at the merge of that pull request. The direction named no person, so no "Decided by" field carries a name: the
record is the direction itself, cited by its title and date.

Update 2026-10-12 (governance pass, pull request #78): the owner's direction VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION
asked for AD-1 and AD-4 to AD-8 to be resolved and documented, with V3, media delivery, the scanner deployment and
production all unchanged. AD-1 is recorded as given (option B, the validated image pin, the capacity evidence digest,
approved scanner mode `clamd`) in `media_scanner`, with `mode` still `none`: a governance record deploys no scanner.
AD-5 is recorded as given (the owner's direction on withdrawal is the final behaviour; the implementing change is
still to be reviewed). AD-7 is resolved as option (b) under the direction to resolve it. AD-4, AD-6 and AD-8 now carry
their defined role, workflow, separation rule and procedure, but the direction named no person, no date and no
document, so their human fields stay blank and they stay UNDECIDED. The verdict of that pass is at the end of this
file: **ACTIVATION GOVERNANCE INCOMPLETE**.

Update 2026-10-12 (scanner deployment, pull request #80): the owner's direction VEDA-SPACES-SCANNER-DEPLOYMENT-EXECUTION
asked for the scanner deployment to be executed and verified, after the merge of #78. The one decision-file value it
changes is `media_scanner.mode`, `none` to `clamd` (AD-1, recorded as given); the plan, the apply, the deploy, the
soak and the evidence are owner-approved runs recorded in the scanner deployment package record. V3, media delivery
and production are unchanged by it.

No name below was chosen by engineering. `[OWNER TO FILL]` means exactly that.

## AD-1. Scanner path

| Field | Value |
|---|---|
| Status | **DECIDED** (2026-10-12, owner direction recorded as given; effective at the merge of pull request #78; the scanner is **not deployed** by this record, see "`mode` in this change"; the rows below it are the history that led here) |
| Owner direction received | Option B preferred (resize the protected-staging host, run the already-supported clamd integration). Option A prohibited. Option C deferred (needs a new application adapter; would reopen engineering). |
| Repository evidence that conflicts with the direction | None. The application accepts only `none` and `clamd`; startup validation requires clamd when any V3 flag is on in staging; staging-core refuses option A in any mode. |
| What blocked recording it (resolved) | The capacity evidence (§6 of the preparation record) and the host-size decision AD-2. `media_scanner.option` may be recorded as `B` with `mode` still `none` only together with a pinned image digest or it will fail the staging-core precondition when the mode becomes `clamd`. Both are now in place (the rows below). |
| Phase 1 update (2026-10-11, engineering, no decision) | Capacity evidence collected: `13-evidence` run 38164988919, digest `ab25630c5f0e8b2934a8181acd9b55dc5a59de21e05c778d8cefc1da05058517`. Image validated on ARM64 and pin value: `clamav/clamav:1.4.6-debian13-slim@sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b` (LTS). The certified Compose `clamd` service cannot start the official image; the validated non-root profile needs an independently reviewed change ([phase-1 record §5](CATALOG-V3-activation-phase1.md)). |
| Scanner implementation update (2026-10-12, engineering, no decision) | The non-root Compose profile for the validated image is implemented and pinned by tests (pull request #76; [CATALOG-V3-scanner-implementation.md](CATALOG-V3-scanner-implementation.md)); the harness ran at the configured 2048 MiB limit (workflow 14 run 38199283652: every check passed, no OOM kill, restart and recovery measured). Recording option B, the pin value and the capacity digest in `media_scanner` remains this decision. |
| Owner direction received again (2026-10-12, VEDA-SPACES-PR77-REBASE-AND-PLAN-CERTIFICATION) | Scanner path option B, host `t4g.large`: the host size is recorded under AD-2 (pull request #77). Recording option B, the pin value and the capacity digest in `media_scanner` (status, option, mode `clamd`) remains this decision and a later reviewed change: the resize pull request enables no scanner (`media_scanner.mode` stays `none`, status UNDECIDED; `infra/tests/run.sh` AUT-108 pins it). |
| Owner direction (2026-10-12, VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION), recorded as given | Scanner decision: option B, including the pinned image digest, the capacity evidence digest and the approved scanner mode. The same direction states: do not activate V3, do not enable media delivery, do not deploy the scanner, do not change production. The values recorded are the only candidates the repository evidence carries (the validated pin, the collected capacity evidence, the one scanner mode the application supports); no value was chosen by engineering. |
| Scanner path | Option B |
| Pinned image (`clamd_image`) | `clamav/clamav:1.4.6-debian13-slim@sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b` |
| Capacity evidence (`capacity_evidence_sha256`) | `ab25630c5f0e8b2934a8181acd9b55dc5a59de21e05c778d8cefc1da05058517` |
| Approved scanner mode | `clamd` (recorded in `media_scanner.decision`; it is the value `mode` takes at the scanner deployment) |
| `mode` in the recording change (pull request #78) | `none`. `deploy.sh` step 4c starts the scanner Compose profile whenever the rendered configuration carries `VEDA_CATALOG_MEDIA_SCANNER=clamd`, so a `mode` of `clamd` in the decision file deploys the scanner at the next 12-deploy; the governance direction forbade that. With `mode` `none` the recorded pin was planned as the SSM parameter `VEDA_CATALOG_CLAMD_IMAGE` (from `none-selected` to the pin, one in-place change, inert). |
| Owner direction (2026-10-12, VEDA-SPACES-SCANNER-DEPLOYMENT-EXECUTION), recorded as given | Execute and verify the scanner deployment: AD-1 merged, the image-pin parameter applied, the mode changed from `none` to `clamd`, the deployment completed and verified (container running and healthy, PING, FreshClam, the exact digest, non-root, no privileged mode, no public port), validated (EICAR, oversized stream, restart, recovery, no OOM) and soaked (24 hours, restart count, memory headroom). V3, media delivery and production unchanged. |
| `mode` after the scanner deployment change | `clamd` (pull request #80, 2026-10-12, owner direction VEDA-SPACES-SCANNER-DEPLOYMENT-EXECUTION, recorded as given): the one value that change touches in the decision file. It plans one in-place SSM parameter change (`VEDA_CATALOG_MEDIA_SCANNER`), applied only by an owner-approved `11-infra-apply`; the next `12-deploy` then starts the pinned image (`infra/terraform/envs/staging-core/tests/core.tftest.hcl` and `infra/tests/run.sh` AUT-108 pin this state). The deployment runs, the soak and the evidence are recorded in the scanner deployment package record (pull request #79) and below once they exist. |
| Scanner deployment (owner-run; the sequence of the package record) | 1. A reviewed change sets `media_scanner.mode` to `clamd` (one SSM parameter, `VEDA_CATALOG_MEDIA_SCANNER`, in place): pull request #80. 2. `10-infra-plan` on `main`, then an owner-approved `11-infra-apply` of its digest. 3. A `12-deploy` of a `main` build that carries pull request #76 (the host still runs the phase-0 release of `12-deploy` run 38163064366, which has no scanner service); `deploy.sh` step 4c starts the profile, the media preflight requires the pinned image. 4. A soak with the `scanner-unhealthy` alarm and the `ScannerRestarts` metric. 5. `13-evidence` with the label `scanner-validation`: its digest is the activation record's `scanner_decision` evidence. Rollback at any step: `mode` `none`, one parameter in place, no destroy. |
| Where it is recorded | `infra/config/staging-platform.json` → `media_scanner` (`status`, `option`, `mode`, `clamd_image`, `capacity_evidence_sha256`, `decision`) |
| Scanner deployment runs (2026-10-12, engineering note; owner-approved runs) | Plan run 38251677019 on `main` (0 to add, 2 to change, 0 to destroy: `VEDA_CATALOG_CLAMD_IMAGE` to the pin, `VEDA_CATALOG_MEDIA_SCANNER` to `clamd`), apply run 38252118680 (0 added, 2 changed, 0 destroyed). `12-deploy` run 38252332555 was refused at its image scan (two new HIGH findings in the base image's glibc, unfixed in Debian; nothing reached the host); pull request #81 recorded the two reviewed staging exceptions and retired the stale gcc-14 one. `12-deploy` run 38256345183 (13:37 UTC) deployed `main` after #81: image scan gate passed with the three covered findings, bundle verified on the host, media preflight `scanner: clamd (pinned image)` and `V3 intentionally disabled`, `veda-deploy` ended Success (the deploy script fails closed unless step 4c gets `PONG` from clamd and step 5 passes `/health/ready`). Drift plan run 38257133680 afterwards: no changes (201 no-op). Post-deploy snapshot: `13-evidence` run 38257129126, `scanner-deploy-verify-20261012T134234Z.tgz`, SHA-256 `270f243d000a309d660e92f7476f5636d73b80db2c6bb919a2079138eaf7e9be` (not the validation evidence: that is the `scanner-validation` collection after the 24-hour soak). V3 flags, media delivery and production unchanged. |
| Decision text | Option B; image pinned by digest as above; capacity evidence digest as above; approved scanner mode `clamd`; `mode` `clamd` since the scanner deployment change (pull request #80). |
| Decided by, on | The owner, by the direction VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION of 2026-10-12, recorded as given (no person is named in this file; the reviewed merge of pull request #78 is the acceptance in the repository model) |

## AD-2. Host size and capacity reserve for clamd

| Field | Value |
|---|---|
| Status | **DECIDED** (2026-10-12, owner direction recorded as given; effective at the merge of pull request #77; the rows below it are the history that led here) |
| Eligible today without a Terraform change | `t4g.small` (current, 2 GiB; precluded for clamd) and `t4g.medium` (4 GiB). The compute module's validation accepts only these two. |
| Eligible only with a reviewed module change | `t4g.large` (8 GiB) or any other size: one validation line in `infra/terraform/modules/compute/variables.tf`, plus the network module's availability-zone offering check for the new type. |
| Capacity rule (enablement §4) | `MemTotal − (peak current service memory + clamd reservation + reload peak) ≥ approved reserve`, with no OOM kill and no restart in the window. |
| Reserve policy options | (a) 25 % of memory, as proposed in the enablement document. (b) A measured policy: the reserve is a fixed amount derived from the evidence, with `ConcurrentDatabaseReload no` so the reload peak is not doubled and scans block briefly during reloads. |
| Preliminary arithmetic (documentation figures, not a recommendation) | ClamAV documents a 3 GiB minimum and about 1.2 GiB to load signatures. On 4 GiB, a 3 GiB reservation plus the current services cannot leave a 1 GiB reserve, so `t4g.medium` passes rule (a) only if the measured figures are used under (b). On 8 GiB the rule passes under (a) with margin. |
| Cost (**estimated cost pending owner verification**; USD, `ap-south-1`, EC2 on-demand Linux, compute only, monthly estimate, excludes tax and data transfer) | `t4g.small` 8.18 USD/month (0.0112 USD/h **recorded** in AUT-101, Price List API read 2026-10-05); `t4g.medium` +8.17 (0.0224 USD/h **recorded** in AUT-101); `t4g.large` +24.52 (**extrapolated**: 2 × the recorded `t4g.medium` rate = 0.0448 USD/h × 730 h = 32.70; no `t4g.large` price is recorded in any owner evidence package; [phase-1 record §4.5](CATALOG-V3-activation-phase1.md)). Staging today runs at about 25 USD/month including the media alarms, against the 25 USD budget (AD-3). |
| Phase 1 update (2026-10-11, engineering, no decision) | Measured on ARM64: clamd steady about 1.05 GiB, first-load peak 1.63 GiB, no growth on reload with `ConcurrentDatabaseReload no`, about 2.0 GiB with concurrent reloads. With a 2,048 MiB clamd limit, `t4g.medium` passes the 25 % rule only if services plus operating system stay at or under 877 MiB; `t4g.large` passes with more than 2 GiB to spare. Engineering recommends `t4g.large` under policy (a); the owner reads the host figures from the capacity evidence. **PROPOSED 2048 MiB LIMIT NOT YET VALIDATED**: the measurements were taken under a 3 GiB harness limit; the scanner-engineering pull request reruns the harness at the configured limit ([phase-1 record §5.6](CATALOG-V3-activation-phase1.md)). Prerequisite for any resize: pin `az_id` in `infra/config/staging-network.json` ([phase-1 record §4](CATALOG-V3-activation-phase1.md)). |
| Scanner implementation update (2026-10-12, engineering, no decision) | `t4g.large` is eligible in the compute module (one validation line, tested); `az_id` is pinned to `aps1-az1`, the existing subnet's AZ ID read from the state in plan artifact `core-plan-38160993150` (pull request #76). The reviewed `t4g.large` plan comes from the stacked plan-only proposal #77 (`compute.status` PROPOSED, so no apply and no deploy can run from it); expected: `aws_instance` in-place `instance_type` update only, no destroy, no replacement ([scanner implementation record §7](CATALOG-V3-scanner-implementation.md)). The `t4g.large` on-demand price is now a **recorded** figure: 0.0448 USD/h, 32.70 USD per 730 h (public AWS Price List offer `20261009203134`, ap-south-1), the same value as the extrapolation; the owner's acceptance of it belongs to AD-3. |
| Owner direction (2026-10-12, VEDA-SPACES-PR77-REBASE-AND-PLAN-CERTIFICATION), recorded as given | Scanner path option B; host type `t4g.large`; reserve policy: the documented scanner reserve policy, which is policy (a), 25 % of memory (enablement record §4), met with more than 2 GiB to spare by the measured figures and the validated 2048 MiB limit. Pricing evidence used: `t4g.small` 0.0112 USD/h, `t4g.large` 0.0448 USD/h, 32.70 USD per 730 h, +24.53 USD per month (the hourly delta × 730; the earlier +24.52 was the rounded monthly figures subtracted), verified against the public AWS Price List offer `20261009203134` by two independent reads. The staging total of about 49–50 USD/month remains an **estimated cost pending owner verification** against a bill. |
| Rebuild of pull request #77 (2026-10-12, engineering) | Rebuilt on `main` after the merge of #76, so its diff is only the three decision files, these records, the committed-decision checks of `infra/tests/run.sh` and the activation-document tests. `compute.status` is `DECIDED` (no deploy freeze at the merge). The plan evidence is a `10-infra-plan` run on the pull request, review-only by design; the applicable plan is the run on `main` after the merge ([scanner implementation record §7](CATALOG-V3-scanner-implementation.md)). The expected delta is unchanged: `aws_instance.host` `instance_type` in place, the budget limit in place, 0 to destroy, 0 to replace; any replacement is a stop signal. |
| Applied (2026-10-12, engineering note, no decision) | `10-infra-plan` run 38229627339 on `main` after the merge, `11-infra-apply` run 38236441086 (owner-approved): the host is `t4g.large`; the drift plan run 38237704284 that followed planned no resource change (201 no-op; an outputs-only difference in the budget limit's string form). |
| Where it is recorded | `infra/config/staging-platform.json` → `compute.instance_type` and `compute.decision` (status `DECIDED`; the reserve policy is in `compute.decision`, since `media_scanner` is untouched until AD-1); `infra/config/staging-network.json` → `host_instance_type` (the AZ offering check) |
| Chosen size | `t4g.large` (8 GiB), every other host setting unchanged; `az_id` stays pinned to `aps1-az1` |
| Reserve policy | (a) 25 % of memory, the documented scanner reserve policy |
| Decided by, on | The owner, by the direction VEDA-SPACES-PR77-REBASE-AND-PLAN-CERTIFICATION of 2026-10-12, recorded as given (no person is named in this file; the reviewed merge of pull request #77 is the acceptance in the repository model) |

## AD-3. Budget revision (O16)

| Field | Value |
|---|---|
| Status | **DECIDED** (2026-10-12, owner direction recorded as given; effective at the merge of pull request #77; the rows below it are the history that led here) |
| Limit before this decision | 25 USD/month, forecast alerts at 80 % and 100 % (`infra/config/staging-budget.json`, O16). |
| Why it is needed | Option B on any eligible size exceeds the current limit (estimated total staging run rate about 33–34 USD/month on `t4g.medium`, about 49–50 USD/month on `t4g.large`; both are **estimated cost pending owner verification**, the `t4g.large` term extrapolated, [phase-1 record §4.5](CATALOG-V3-activation-phase1.md)). The budget resource only alerts; it does not stop spend, but the owner decided the limit and the forecast alert would fire every month. |
| Phase 1 update (2026-10-11, engineering, no decision; corrected 2026-10-12) | Proposed limits for the owner to accept or change, **not approved**: 60 USD with `t4g.large` (estimated total about 49–50 USD), 40 USD with `t4g.medium` (estimated total about 33–34 USD); forecast alerts unchanged at 80 % and 100 %. No other new cost from the scanner is expected. The `t4g.large` figure is an estimate pending owner verification; no billed cost exists for either size ([phase-1 record §4.3 and §4.5](CATALOG-V3-activation-phase1.md)). |
| Scanner implementation update (2026-10-12, engineering, no decision) | Price provenance for `t4g.large` upgraded from extrapolation to a recorded Price List rate (0.0448 USD/h; offer `20261009203134`; [scanner implementation record §1](CATALOG-V3-scanner-implementation.md)); the estimated staging total of about 49–50 USD/month on `t4g.large` stands. One more custom metric (`ScannerHealthy`, about 0.30 USD/month). The limit is still the owner's to set; nothing in `staging-budget.json` changed. |
| Owner direction (2026-10-12, VEDA-SPACES-PR77-REBASE-AND-PLAN-CERTIFICATION), recorded as given | Ceiling 60 USD/month for the `t4g.large` host, on the verified pricing evidence of AD-2 (0.0448 USD/h, 32.70 USD per 730 h, +24.53 USD per month); forecast alerts unchanged at 80 % and 100 %. The budget resource alerts and never stops spend. The staging total of about 49–50 USD/month stays an **estimated cost pending owner verification** against a bill; the direction set no review date for the limit. |
| Where it is recorded | `infra/config/staging-budget.json` → `monthly_limit_usd` (60), `decision` (pull request #77; a change of this file is planned on `main` by `10-infra-plan` and applied only by an approved `11-infra-apply`) |
| New limit | 60 USD/month, forecast alerts at 80 % and 100 % |
| Review date for the limit | [OWNER TO FILL] |
| Decided by, on | The owner, by the direction VEDA-SPACES-PR77-REBASE-AND-PLAN-CERTIFICATION of 2026-10-12, recorded as given (no person is named in this file; the reviewed merge of pull request #77 is the acceptance in the repository model) |

## AD-4. Media-rights approver

| Field | Value |
|---|---|
| Status | **UNDECIDED** (activation blocked until both names are filled; the role, the backup rule and the workflow are defined below) |
| Primary media-rights approver | **[OWNER TO FILL]** |
| Backup approver | **[OWNER TO FILL]** |
| Independence | The approver must not be the uploader of the media they approve, the author of the claim or record they approve, the author of the activation record, or the producer of the evidence they review where four-eyes applies. The code enforces four eyes on catalog records and releases (an approver is never the editor, submitter or release author); the independence from the activation-record author is a policy rule the owner enforces. |
| Responsibilities | Verify ownership or licence; verify consent (and its reference) for client permission; verify attribution; verify usage scope (products, rooms, styles); verify effective, expiry and review dates; approve withdrawal; approve publication eligibility (a record's `reviewed_by`). |
| Effect while blank | `media_rights.approver` stays `[OWNER TO FILL]`: staging-core refuses any V3 flag (output `catalog_v3`), and startup validation refuses `VEDA_CATALOG_MEDIA_RIGHTS_APPROVER` with that text. |
| Where it is recorded | `infra/config/staging-platform.json` → `media_rights.approver`, `media_rights.status`; the backup approver in `media_rights.decision` |
| Phase 1 update (2026-10-11, engineering, no decision) | Acceptance template prepared: [media-rights-approver-acceptance.template.md](media-rights-approver-acceptance.template.md). No name was entered. |
| Owner direction (2026-10-12, VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION), recorded as given | Define the approver role, the backup approver and the approval workflow. The direction named no person and no role title; the decision file says the approver is "a person or role they choose; never invented", so the two name fields above stay blank and nothing was entered in `media_rights`. |
| Approver role (defined) | The accountable media-rights approver for catalog V3 media on protected staging: one person, or one role title the owner chooses, whose name the application reads from `VEDA_CATALOG_MEDIA_RIGHTS_APPROVER` and shows in audit output. The role carries the responsibilities and the independence rules above, accepted in writing on the acceptance template. No production scope exists for it. |
| Backup approver (defined) | Acts only while the primary is unavailable, under the same responsibilities, the same independence rules and the same signed acceptance note. Recorded in this file and in `media_rights.decision`, not in the application setting (the application reads one approver; a hand-over to the backup is a reviewed change of `media_rights.approver`). |
| Approval workflow (defined) | 1. The owner names the primary and the backup in this record and sets `media_rights.approver` to the primary with `media_rights.status` `DECIDED`, through a reviewed pull request (the decision tests then flip from "placeholder" to "named"). 2. Each approver signs a copy of the acceptance template; the owner keeps the signed copies outside Git. 3. The SHA-256 of the primary's signed note, and where it is kept, become the activation record's `media_rights_approver` evidence. 4. `10-infra-plan` on `main`, then an owner-approved `11-infra-apply`: the apply creates the `VEDA_CATALOG_MEDIA_RIGHTS_APPROVER` parameter (staging-core plans it only while `media_rights.status` is `DECIDED`). 5. In operation, every media approval is the record's `reviewed_by` under the four-eyes rule the application enforces, and the approver approves withdrawals. 6. A change of approver repeats steps 1 to 4 and notes the replaced acceptance here. |
| Written acceptance by the approver | [OWNER TO FILL: location of the signed note; its SHA-256 becomes the activation record's `media_rights_approver` evidence] |
| Decided by, on | [OWNER TO FILL], [DATE TO FILL] |

## AD-5. Withdrawal during an approval lapse

| Field | Value |
|---|---|
| Status | **DECIDED** (2026-10-12, owner direction recorded as given; **not implemented**: the certified behaviour stands until the reviewed change below is merged) |
| Certified behaviour today | When the staging approval record is missing, revoked, expired, past review, out of window, unbound or mismatched, every media route answers 503 at once: upload, withdraw, list, staff preview and public delivery. Emergency deactivation (`VEDA_CATALOG_ESTIMATOR_ENABLED=false`, restart) is unaffected by the approval state. |
| Owner direction received | Allow only withdrawal and emergency deactivation while an approval is lapsed; keep upload, list, preview, publication, public delivery, new variants and new activation blocked. Preserve withdrawal for privacy, consent, security and rights reasons. |
| Conflict | Yes: certified behaviour blocks withdrawal during a lapse. The direction requires a code change. |
| The change, if the owner decides it | Remove the approval gate from the withdraw route only (`POST /catalog/media/<sha>/withdraw`); keep it on upload, list, preview and public delivery; keep the staff permission `catalog.media.edit` and the admin flag as they are; update the integration test that expects 503 on withdrawal during each lapse mode to expect success; add the case to the policy document (§18 of the enablement document). Withdrawal keeps writing delete markers and the audit note. Estimated size: one line of route code, one test edit, one documentation paragraph. It needs independent review before merge, like every change to the certified tree. |
| Not implemented in this workstream | Correct. Nothing was changed. |
| Owner direction (2026-10-12, VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION), recorded as given | "Define final approved behavior." The direction named no other behaviour, and the direction above is the only owner direction on withdrawal on record, so it is recorded as the final behaviour. If the owner intended the certified behaviour instead, this row is corrected by a reviewed change before any implementing pull request. |
| Final behaviour | While the approval is lapsed (missing, revoked, expired, past review, out of window, unbound or mismatched): withdrawal (`POST /catalog/media/<sha>/withdraw`, staff permission `catalog.media.edit`, admin flag on) and emergency deactivation stay available; upload, list, staff preview, publication, public delivery, new variants and any new activation stay blocked (503 or flags off). A withdrawal during a lapse writes the delete marker and the audit note as it does today. Nothing is served during a lapse in either case. |
| Implementation | The change described above, as an independently reviewed pull request to the certified tree, merged before the activation pull request. It is not part of the governance change that recorded this decision. Until it is merged, a lapse blocks withdrawal, as certified. |
| Where it is recorded | This file (decision), then the reviewed pull request that implements it |
| Decision | Adopt the direction (recorded as given): withdrawal and emergency deactivation stay available during a lapse; everything else stays blocked. |
| Decided by, on | The owner, by the direction VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION of 2026-10-12, recorded as given (no person is named in this file; the reviewed merge of pull request #78 is the acceptance in the repository model) |

## AD-6. Activation record roles and dates

| Field | Value |
|---|---|
| Status | **UNDECIDED** |
| What is still the owner's | The author's and the approver's names, `review_by`, the expiry choice and the `media_delivery` scope value. The separation rule is defined below; no name, date or value was entered. |
| Schema | `veda.catalog.v3-staging-approval/2` (fixed by the certified policy) |
| Release code | `V3-STAGING-1` (owner direction; must equal the catalog release that will be ACTIVE) |
| Author | [OWNER TO FILL] |
| Approver | [OWNER TO FILL] (must differ from the author after trimming, whitespace collapse and lower-casing; no placeholder text) |
| Owner direction (2026-10-12, VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION), recorded as given | "Approval-record author and approver separation." The direction named nobody. |
| Separation (defined) | The author is the person who prepares the record and opens the activation pull request (engineering may author). The approver is a different person who signs `approved_at`; the policy's `APPROVER` rule refuses a record whose approver equals its author after normalisation, or carries a placeholder, at the plan, the build, the deployment check and at runtime. The approver is not the uploader, author or evidence producer of what they approve where four eyes apply, and the activation pull request is merged by someone other than its author (the reviewed merge). The media-rights approver (AD-4) is never the record's author; whether the same person may also approve the record is the owner's call when naming, not pre-empted here. Proposed, not decided: author = the engineer who opens the activation pull request; approver = the owner. |
| `approved_at` | The UTC day the approver signs |
| `review_by` | After `approved_at` and at most 90 days later. Proposed: 60 days. [OWNER TO FILL] |
| `expires_at` or `non_expiring_decision` | Exactly one. Owner direction: expiry must be explicit unless an independently approved non-expiring policy is recorded. Proposed: `expires_at = review_by`. [OWNER TO FILL] |
| `approval_scope.media_delivery` | Owner direction: `true` for an activation that enables public delivery behind Cloudflare Access (a JSON boolean is required; either value is accepted by the gate). The committed [`v3-staging-approval.template.json`](v3-staging-approval.template.json) is a **preparation-only DRAFT skeleton**, not this record: it keeps `false` (the restrictive default) and does not pre-empt this decision; the record's author sets the field when this decision is recorded. Value for the V3-STAGING-1 record: [OWNER TO FILL] |
| Decided by, on | [OWNER TO FILL], [DATE TO FILL] |

## AD-7. First-activation smoke-test sequencing

| Field | Value |
|---|---|
| Status | **DECIDED** (2026-10-12, resolved under the owner's direction to resolve the dependency; option (b), no code change; effective at the merge of pull request #78) |
| The dependency | An APPROVED record needs `media_smoke_test` evidence. Smoke tests S3–S13 need the staff media API, which answers 404 until `VEDA_CATALOG_ADMIN_ENABLED` is true. That flag turns on only together with the other two V3 flags, and only with an APPROVED, digest-bound record. |
| Option (a): bounded pre-activation record | A staging-only record that authorises only the minimum staff-media operations for the smoke tests, with synthetic media only, a short explicit window, immediate flags-off rollback after evidence collection, and every operation logged. **This requires an independently reviewed engineering change:** the certified policy has no bounded scope, staging-core refuses any partial activation, and the staff media routes are gated by the admin flag alone. See the statement in the preparation record §9. |
| Option (b): controlled activation window, no code change | The first record's `media_smoke_test` entry references the pre-activation subset (S1, S2, S14, S16, S17 and the test plan), stated in its reference text. Activation proceeds with all three flags behind Cloudflare Access and synthetic media only. S3–S13 and the S15 rollback drill run inside a stated window. A second record with the full evidence replaces the first, or the first is revoked and the flags go off. |
| Owner direction (2026-10-12, VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION) | "Resolve the activation dependency." The direction chose no option. Engineering resolved it as option (b) under that direction, because (b) changes no certified gate and no code, while (a) changes the policy, the 39 shared conformance cases and all three implementations and would reopen certification. The owner's acceptance of this resolution is the reviewed merge of pull request #78; a different choice is a reviewed change of this row. |
| Owner decision | Option (b), the controlled activation window, with these conditions: 1. the pre-activation subset (S1, S2, S14, S16, S17 and the test plan) runs before activation and is collected by `13-evidence` with the label `media-smoke-test`; its digest is the first record's `media_smoke_test` evidence and the reference text says it is the subset. 2. The first activation runs with all three flags behind Cloudflare Access and synthetic media only; no real customer media is uploaded in the window. 3. The window is the record's own validity (`review_by` and `expires_at`, AD-6; at most 90 days), and S3–S13 and the S15 rollback drill run inside it. 4. A second record carrying the full evidence replaces the first (a new digest binding, a reviewed change), or the first is revoked and the flags go off. |
| Still pending for this option | No `13-evidence` run with the label `media-smoke-test` exists as of 2026-10-12; the pre-activation subset has not been run. It needs a deployed build that carries the current `main` (the host runs the phase-0 release) and the media-rights approver for the steps that approve media. |
| Decided by, on | Engineering, by the resolution recorded above under the owner's direction VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION of 2026-10-12 (no person is named in this file; the reviewed merge of pull request #78 is the acceptance in the repository model) |

## AD-8. Promise-owner approval of customer-facing claims

| Field | Value |
|---|---|
| Status | **UNDECIDED** |
| What it is | The activation record requires `promise_owner_approval` evidence: the owner's written approval of the governed marketing claims and customer text that V3 shows. |
| Owner direction (2026-10-12, VEDA-SPACES-ACTIVATION-GOVERNANCE-EXECUTION), recorded as given | "Promise-owner approval." The direction provided no document and no digest; there is nothing to record. |
| Procedure (defined) | 1. The owner, as promise owner, writes and signs the approval of the governed claim records and the customer text of release `V3-STAGING-1` (the claims the V3 pages and estimates show), stating the release code and the date. 2. The signed document is kept outside Git, beside the other owner evidence. 3. Its location and SHA-256 become the activation record's `promise_owner_approval` evidence. 4. The record's author does not produce it; the promise owner does. A later change of the claims needs a new approval and a new digest. |
| Where the approval is written | [OWNER TO FILL: document location; its SHA-256 is the evidence digest] |
| Decided by, on | [OWNER TO FILL], [DATE TO FILL] |

**Owner acceptance of AD-1, AD-2, AD-3 and AD-5: recorded as given (owner directions of 2026-10-12, pull requests #77 and #78). AD-7: resolved under the owner's direction of 2026-10-12 (pull request #78). Owner acceptance of every other record above: not recorded.** This file is not an approval record and enables nothing: the recorded decisions act only through the decision files named above, and none of them deploys a scanner, enables media delivery or turns on any V3 flag.

## Activation checklist (governance pass of 2026-10-12)

Status values: DONE (verified in the repository or a run), PENDING (a named action is still to happen), UNDECIDED
(a human decision is missing), BLOCKED (waits on an earlier row). No row that needs the owner is DONE.

| # | Step | Status | Who | Evidence or blocker |
|---|---|---|---|---|
| 1 | Host `t4g.large` applied, drift clean | DONE | engineering (owner-approved runs) | `11-infra-apply` run 38236441086; drift plan run 38237704284, 201 no-op |
| 2 | Scanner implementation certified | DONE | engineering | pull request #76 merged; [scanner implementation record](CATALOG-V3-scanner-implementation.md) |
| 3 | AD-1 recorded (option B, pin, capacity digest, approved mode) | DONE at the merge of pull request #78 | the owner's reviewed merge | `media_scanner` in `staging-platform.json`; `mode` `none` |
| 4 | Plan and apply of the AD-1 parameter (`VEDA_CATALOG_CLAMD_IMAGE`, inert) | DONE (2026-10-12, together with the mode parameter: plan run 38251677019, apply run 38252118680, 0 added, 2 changed, 0 destroyed; drift plan run 38257133680 afterwards: no changes) | owner approved | `10-infra-plan` on `main`, then `11-infra-apply` |
| 5 | AD-5 implementing change (withdrawal during a lapse) | PENDING | engineering authors; independent review | one route line, one test, §18 paragraph; before step 13 |
| 6 | Scanner deployment: `mode` `clamd`, plan, apply, 12-deploy of a build with #76, soak | IN PROGRESS: deployed 2026-10-12 13:37 UTC (`12-deploy` run 38256345183 on `main` after pull requests #80 and #81; the first attempt, run 38252332555, was refused by the image scan gate); the 24-hour soak is running | owner (reviewed changes, approvals) | AD-1 "Scanner deployment runs" row; post-deploy snapshot evidence run 38257129126 |
| 7 | `13-evidence` `scanner-validation` (record evidence `scanner_decision`) | PENDING (after the 24-hour soak of step 6) | engineering runs; owner approves | the tarball must meet §2.5 of the package record |
| 8 | AD-4: approver and backup named, acceptance notes signed, `media_rights` DECIDED, parameter applied | UNDECIDED | owner | both names blank; evidence `media_rights_approver` |
| 9 | Pre-activation smoke subset (S1, S2, S14, S16, S17), `13-evidence` `media-smoke-test` | BLOCKED | engineering, media-rights approver | needs steps 6 and 8; evidence `media_smoke_test` (AD-7 option (b)) |
| 10 | AD-8: promise-owner approval document and digest | UNDECIDED | owner | evidence `promise_owner_approval` |
| 11 | AD-6: author, approver, `review_by`, expiry, `media_delivery` value | UNDECIDED | owner names; approver signs | the record's human fields |
| 12 | Record `V3-STAGING-1` filled with every evidence digest (git SHAs, 13 digests) and APPROVED by its approver | BLOCKED | author, then approver | needs steps 7 to 11, the activation plan digest and apply evidence |
| 13 | Activation pull request: record committed, `catalog_v3` flags on together, `approval_record_sha256` bound, the "no record committed" test flipped | BLOCKED | engineering authors; reviewed merge | needs step 12 and step 5 |
| 14 | Plan, apply, deploy of the activation; S3–S13 and the S15 drill in the window; second record or revocation | BLOCKED | owner approvals | AD-7 option (b) conditions |
| 15 | Production | BLOCKED by design | owner, separately | the API refuses every V3 flag in production; no production change exists |

**Verdict: ACTIVATION GOVERNANCE INCOMPLETE.** Three records (AD-4, AD-6, AD-8) still need a name, a date or a
document that only the owner can supply, the scanner has not been deployed (AD-1 is recorded, step 6 is not run),
and three of the activation record's evidence items (`scanner_decision`, `media_smoke_test`,
`promise_owner_approval`) and the `media_rights_approver` note do not exist yet. Nothing was activated, enabled,
deployed or changed in production by this pass.
