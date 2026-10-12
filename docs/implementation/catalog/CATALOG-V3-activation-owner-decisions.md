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
record is the direction itself, cited by its title and date. Every other record stays UNDECIDED.

No name below was chosen by engineering. `[OWNER TO FILL]` means exactly that.

## AD-1. Scanner path

| Field | Value |
|---|---|
| Status | **UNDECIDED** |
| Owner direction received | Option B preferred (resize the protected-staging host, run the already-supported clamd integration). Option A prohibited. Option C deferred (needs a new application adapter; would reopen engineering). |
| Repository evidence that conflicts with the direction | None. The application accepts only `none` and `clamd`; startup validation requires clamd when any V3 flag is on in staging; staging-core refuses option A in any mode. |
| What still blocks recording it | The capacity evidence (§6 of the preparation record) and the host-size decision AD-2. `media_scanner.option` may be recorded as `B` with `mode` still `none` only together with a pinned image digest or it will fail the staging-core precondition when the mode becomes `clamd`. |
| Phase 1 update (2026-10-11, engineering, no decision) | Capacity evidence collected: `13-evidence` run 38164988919, digest `ab25630c5f0e8b2934a8181acd9b55dc5a59de21e05c778d8cefc1da05058517`. Image validated on ARM64 and pin value: `clamav/clamav:1.4.6-debian13-slim@sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b` (LTS). The certified Compose `clamd` service cannot start the official image; the validated non-root profile needs an independently reviewed change ([phase-1 record §5](CATALOG-V3-activation-phase1.md)). |
| Scanner implementation update (2026-10-12, engineering, no decision) | The non-root Compose profile for the validated image is implemented and pinned by tests (pull request #76; [CATALOG-V3-scanner-implementation.md](CATALOG-V3-scanner-implementation.md)); the harness ran at the configured 2048 MiB limit (workflow 14 run 38199283652: every check passed, no OOM kill, restart and recovery measured). Recording option B, the pin value and the capacity digest in `media_scanner` remains this decision. |
| Owner direction received again (2026-10-12, VEDA-SPACES-PR77-REBASE-AND-PLAN-CERTIFICATION) | Scanner path option B, host `t4g.large`: the host size is recorded under AD-2 (pull request #77). Recording option B, the pin value and the capacity digest in `media_scanner` (status, option, mode `clamd`) remains this decision and a later reviewed change: the resize pull request enables no scanner (`media_scanner.mode` stays `none`, status UNDECIDED; `infra/tests/run.sh` AUT-108 pins it). |
| Where it is recorded | `infra/config/staging-platform.json` → `media_scanner` (`status`, `option`, `mode`, `clamd_image`, `capacity_evidence_sha256`, `decision`) |
| Decision text | [OWNER TO FILL] |
| Decided by, on | [OWNER TO FILL], [DATE TO FILL] |

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
| Status | **UNDECIDED** (activation blocked until both names are filled) |
| Primary media-rights approver | **[OWNER TO FILL]** |
| Backup approver | **[OWNER TO FILL]** |
| Independence | The approver must not be the uploader of the media they approve, the author of the claim or record they approve, the author of the activation record, or the producer of the evidence they review where four-eyes applies. The code enforces four eyes on catalog records and releases (an approver is never the editor, submitter or release author); the independence from the activation-record author is a policy rule the owner enforces. |
| Responsibilities | Verify ownership or licence; verify consent (and its reference) for client permission; verify attribution; verify usage scope (products, rooms, styles); verify effective, expiry and review dates; approve withdrawal; approve publication eligibility (a record's `reviewed_by`). |
| Effect while blank | `media_rights.approver` stays `[OWNER TO FILL]`: staging-core refuses any V3 flag (output `catalog_v3`), and startup validation refuses `VEDA_CATALOG_MEDIA_RIGHTS_APPROVER` with that text. |
| Where it is recorded | `infra/config/staging-platform.json` → `media_rights.approver`, `media_rights.status`; the backup approver in `media_rights.decision` |
| Phase 1 update (2026-10-11, engineering, no decision) | Acceptance template prepared: [media-rights-approver-acceptance.template.md](media-rights-approver-acceptance.template.md). No name was entered. |
| Written acceptance by the approver | [OWNER TO FILL: location of the signed note; its SHA-256 becomes the activation record's `media_rights_approver` evidence] |
| Decided by, on | [OWNER TO FILL], [DATE TO FILL] |

## AD-5. Withdrawal during an approval lapse

| Field | Value |
|---|---|
| Status | **UNDECIDED** |
| Certified behaviour today | When the staging approval record is missing, revoked, expired, past review, out of window, unbound or mismatched, every media route answers 503 at once: upload, withdraw, list, staff preview and public delivery. Emergency deactivation (`VEDA_CATALOG_ESTIMATOR_ENABLED=false`, restart) is unaffected by the approval state. |
| Owner direction received | Allow only withdrawal and emergency deactivation while an approval is lapsed; keep upload, list, preview, publication, public delivery, new variants and new activation blocked. Preserve withdrawal for privacy, consent, security and rights reasons. |
| Conflict | Yes: certified behaviour blocks withdrawal during a lapse. The direction requires a code change. |
| The change, if the owner decides it | Remove the approval gate from the withdraw route only (`POST /catalog/media/<sha>/withdraw`); keep it on upload, list, preview and public delivery; keep the staff permission `catalog.media.edit` and the admin flag as they are; update the integration test that expects 503 on withdrawal during each lapse mode to expect success; add the case to the policy document (§18 of the enablement document). Withdrawal keeps writing delete markers and the audit note. Estimated size: one line of route code, one test edit, one documentation paragraph. It needs independent review before merge, like every change to the certified tree. |
| Not implemented in this workstream | Correct. Nothing was changed. |
| Where it is recorded | This file (decision), then the reviewed pull request that implements it |
| Decision | [OWNER TO FILL: keep certified behaviour / adopt the direction] |
| Decided by, on | [OWNER TO FILL], [DATE TO FILL] |

## AD-6. Activation record roles and dates

| Field | Value |
|---|---|
| Status | **UNDECIDED** |
| Schema | `veda.catalog.v3-staging-approval/2` (fixed by the certified policy) |
| Release code | `V3-STAGING-1` (owner direction; must equal the catalog release that will be ACTIVE) |
| Author | [OWNER TO FILL] |
| Approver | [OWNER TO FILL] (must differ from the author after trimming, whitespace collapse and lower-casing; no placeholder text) |
| `approved_at` | The UTC day the approver signs |
| `review_by` | After `approved_at` and at most 90 days later. Proposed: 60 days. [OWNER TO FILL] |
| `expires_at` or `non_expiring_decision` | Exactly one. Owner direction: expiry must be explicit unless an independently approved non-expiring policy is recorded. Proposed: `expires_at = review_by`. [OWNER TO FILL] |
| `approval_scope.media_delivery` | Owner direction: `true` for an activation that enables public delivery behind Cloudflare Access (a JSON boolean is required; either value is accepted by the gate). The committed [`v3-staging-approval.template.json`](v3-staging-approval.template.json) is a **preparation-only DRAFT skeleton**, not this record: it keeps `false` (the restrictive default) and does not pre-empt this decision; the record's author sets the field when this decision is recorded. Value for the V3-STAGING-1 record: [OWNER TO FILL] |
| Decided by, on | [OWNER TO FILL], [DATE TO FILL] |

## AD-7. First-activation smoke-test sequencing

| Field | Value |
|---|---|
| Status | **UNDECIDED** |
| The dependency | An APPROVED record needs `media_smoke_test` evidence. Smoke tests S3–S13 need the staff media API, which answers 404 until `VEDA_CATALOG_ADMIN_ENABLED` is true. That flag turns on only together with the other two V3 flags, and only with an APPROVED, digest-bound record. |
| Option (a): bounded pre-activation record | A staging-only record that authorises only the minimum staff-media operations for the smoke tests, with synthetic media only, a short explicit window, immediate flags-off rollback after evidence collection, and every operation logged. **This requires an independently reviewed engineering change:** the certified policy has no bounded scope, staging-core refuses any partial activation, and the staff media routes are gated by the admin flag alone. See the statement in the preparation record §9. |
| Option (b): controlled activation window, no code change | The first record's `media_smoke_test` entry references the pre-activation subset (S1, S2, S14, S16, S17 and the test plan), stated in its reference text. Activation proceeds with all three flags behind Cloudflare Access and synthetic media only. S3–S13 and the S15 rollback drill run inside a stated window. A second record with the full evidence replaces the first, or the first is revoked and the flags go off. |
| Owner decision | [OWNER TO FILL: (a) commission the reviewed change / (b) accept the controlled window / other] |
| Decided by, on | [OWNER TO FILL], [DATE TO FILL] |

## AD-8. Promise-owner approval of customer-facing claims

| Field | Value |
|---|---|
| Status | **UNDECIDED** |
| What it is | The activation record requires `promise_owner_approval` evidence: the owner's written approval of the governed marketing claims and customer text that V3 shows. |
| Where the approval is written | [OWNER TO FILL: document location; its SHA-256 is the evidence digest] |
| Decided by, on | [OWNER TO FILL], [DATE TO FILL] |

**Owner acceptance of AD-2 and AD-3: recorded as given (owner direction of 2026-10-12, pull request #77). Owner acceptance of every other record above: not recorded.** This file is not an approval record and enables nothing: the two recorded decisions act only through the decision files named above, and neither enables a scanner, media delivery or any V3 flag.
