# Catalog V3 activation preparation: baseline, release review, evidence, dependency matrix (2026-10-11)

**Nothing is activated by this record.** V3, media delivery, admin V3 and estimator V3 stay off; the scanner mode
stays `none`; public intake stays disabled; production is unchanged. The owner decision records it refers to are in
[CATALOG-V3-activation-owner-decisions.md](CATALOG-V3-activation-owner-decisions.md) and are blank where a human
decision is missing.

Commit references are given as pull-request merges and workflow run ids. Digests are SHA-256 unless stated.

## 1. Verified baseline (phase 0)

Fetched over HTTPS; not read from a local `origin/main`.

| Item | Verified value | How |
|---|---|---|
| main | The merge commit of PR #73, on top of the merge commit of PR #72 | `git fetch` of `main` from GitHub |
| PR #72 | MERGED (2026-10-11 08:36 UTC) | GitHub API |
| PR #73 | MERGED (2026-10-11 08:54 UTC) | GitHub API |
| Required checks on main's head | api (sqlite), api (postgresql), app, security, browser e2e + axe, infra: all success | GitHub check runs |
| Cloudflare Pages `veda-staging-app` | success | GitHub check runs |
| Cloudflare Pages `veda-staging-site` | **failure on every main commit since the merge of PR #62 (2026-10-09)**; last success at PR #61. Not a required check. See §3. | GitHub check runs, merges of PRs #50–#73 |
| Infrastructure drift | The last `workflow_dispatch` plan on main (run 38106962562, after the PR #71 merge) reported "No changes". The apply before it (run 38106639695) reported 38 added, 3 changed, 0 destroyed. No apply since. | Workflow logs |
| 13 media settings | Planned and applied by run 38106639695 per the plan-inspection checklist; the applied plan's digest is `aa908b3fcc0c7ed328027806ca49eac714b2b0647ebbd7a9687adad21f50da03` | Plan log; checklist |
| Approval digest setting | Not yet in SSM: it is the one create of the next plan (§2), value `none` | staging-core configuration |
| Scanner mode | `none`; option `null`; status UNDECIDED | `infra/config/staging-platform.json` |
| Media delivery, estimator V3, admin V3 | all `false`; `approval_record_sha256` null | same |
| 3D, video | both `"false"` in the planned configuration; the API refuses video anywhere | staging-core `media_config`; `config.validate_environment` |
| Public intake | `deploy.public_intake = "disabled"`; no tunnel, DNS or Turnstile widget; the Cloudflare root `envs/staging-edge` does not exist yet | same; `infra/terraform/envs/staging-edge/README.md` |
| Production | No production Terraform root, workflow environment or configuration file exists in the repository; the API refuses every V3 flag in production | repository search |
| Live SSM and host state | **Not verified directly**: this machine has no AWS credentials. The drift-check plan after the apply is the verification (§2). | `aws sts get-caller-identity` |

**Material differences from the brief's assumptions:** one. The staging **site** build (not the API) has been failing
for every main commit since PR #62, so the staging site currently serves the build of PR #61. The likely cause, from
the build script and the runbook, is that the Pages project `veda-staging-site` has `STAGING_ESTIMATOR_UX=v2` set while
the V2 owner-approval record is still PENDING, which the build refuses by design. The Pages build log (Cloudflare
dashboard) confirms or refutes this; it was not readable from here. It does not block the API deployment, but it is
part of the staging release review (§3) because the site is the surface for the V1 and V2 journeys.

## 2. Approval-digest parameter plan (phase 1) and apply (phase 2)

A fresh plan was dispatched from certified main: **`10-infra-plan` run 38127613791** (`workflow_dispatch`, main at the
PR #73 merge, 2026-10-11 09:13 UTC). It is **waiting for the `staging-plan` environment approval**, which only the
owner gives. It was not approved by this workstream. The two older plan runs still waiting on main (push-triggered
run 38125413262) and on the PR #72 branch (run 38109912944) cannot be applied, because `11-infra-apply` accepts only a
`workflow_dispatch` plan on main; they can be left to expire.

Expected plan text, from the configuration:

| Check | Expected |
|---|---|
| Creates | Exactly one: `module.ssm.aws_ssm_parameter.config["VEDA_CATALOG_APPROVAL_SHA256"]`, value `none` (plus the owner email subscription only if it is still unconfirmed) |
| Updates, replacements, destroys | None. `module.v3_approval` has no resources |
| Bucket, KMS, IAM, host size, scanner, V3 flags, media delivery, DNS, Cloudflare, production | No change |
| Output `catalog_v3` | `scanner_mode none`, `flags_on false`, `approval_record null` |

**Rule:** if the plan shows anything else: **PLAN DEVIATES, DO NOT APPLY.** If it matches exactly, record the run id
and the plan SHA-256 printed in the run summary, and apply through `11-infra-apply` with that run id and digest
(`staging-infra` approval). After the apply, dispatch another `10-infra-plan` on main and require "No changes" (0 add,
0 change, 0 destroy) before anything else.

Status at the time of writing: **plan waiting for owner approval; apply not performed; drift check not performed.**

## 3. Staging release review package (phase 3)

| Item | Value |
|---|---|
| Currently running on staging | The merge commit of PR #58 (`12-deploy` run 37792485980, 2026-10-08 14:26 UTC) |
| Target | The merge commit of PR #73 (certified main) |
| Nature | An application release: 15 merged pull requests, three expand-only migrations, one new dependency (`pillow`). Not a configuration refresh |
| Merged pull requests | #59 V2 customer-trust finalisation; #60 V2 pre-activation closure; #61 V2 validation plan and session stack; #62 V2 final pre-activation closure; #63 V2 owner approval package; #64 V2 Round 1 execution package; #65 session stack 3 BHK only; #66 catalog-driven estimator V3 behind flags; #67 V3 pre-activation closure; #68 V3 customer-safety closure; #69 V3 canonical customer copy; #70 V3 targeted media enablement; #71 V3 media pre-plan closure; #72 V3 activation remediation; #73 docs |
| Migrations, in order | `0103_catalog` (after `0102_estimator_spec`) → `0104_catalog_idempotency` → `0105_catalog_claim_control`. Expand-only; no backfill; downgrades not implemented |
| Rollback image | The PR #58 merge tag, retained in ECR and on the host. Rollback needs `VEDA_SCHEMA_AHEAD_ACCEPTED=0105_catalog_claim_control` in `/etc/veda/api.env` first (deploy.sh step 4, "Rollback") |
| Expected deploy gates | `12-deploy` runs from main only; apply gates OD-B7 and N-04-S are ACCEPTED; no owner decision is PROPOSED (`media_scanner` and `media_rights` are UNDECIDED, which is allowed); `deploy.enabled` is true; the image scan must show no HIGH or CRITICAL finding |
| Expected media preflight lines | `scanner not selected: uploads stay PENDING and nothing is served` and `V3 intentionally disabled: every V3 and media-delivery flag is false`. The approval validation (step 0b) is **skipped** because `VEDA_CATALOG_ESTIMATOR_ENABLED` is false; the preflight does not require `VEDA_CATALOG_APPROVAL_SHA256` while V3 is off, so the deploy passes whether §2 has been applied or not |
| Expected deploy.sh sequence | 0 floors (release ≥ 3, schema knows `0009_mfa_challenge_binding`); 0b absent; 1 pre-flight; 2 snapshot; 3 quiesce; 4 migrate (expand-only); 4b replication; 4c `Scanner: not selected (VEDA_CATALOG_MEDIA_SCANNER=none); media uploads stay PENDING`; 5 deploy with `/health/ready` at migration head `0105_catalog_claim_control`; 6 resume; 7 edge (tunnel with Access) |
| Expected feature-flag state after deploy | `VEDA_CATALOG_ESTIMATOR_ENABLED=false`, `VEDA_CATALOG_ADMIN_ENABLED=false`, `VEDA_CATALOG_MEDIA_DELIVERY_ENABLED=false`, `VEDA_CATALOG_3D_ENABLED=false`, `VEDA_CATALOG_VIDEO_ENABLED=false`, `VEDA_CATALOG_MEDIA_SCANNER=none` |
| Production isolation | No production root, environment or workflow exists; `12-deploy` targets the `staging` environment and the staging account; the API refuses every V3 flag in production |
| V1 and V2 regression scope | V1 and V2 estimator routes and the lead flow are unchanged by the V3 flags. The V2 customer-spec parser is stricter (release-readiness risk 2): run a synthetic V2 estimate after the deploy. The `ESSENTIAL-1.1` approval stays PENDING; the active spec keeps serving |
| Open item for the review | The staging site Pages build has failed since PR #62 (§1). Decide whether to fix the Pages variable first or accept that the site stays at the PR #61 build while the API moves to certified main |

**Deployment status: not performed.** The brief requires an explicit go decision on the complete release first.

## 4. Dormant post-deploy verification (phase 4), to run only after an approved deploy

| Check | Expected | How |
|---|---|---|
| Running SHA | The PR #73 merge | `12-deploy` log; `/health/ready` build info |
| Migrations | head `0105_catalog_claim_control` | readiness |
| V1 and V2 | A synthetic estimate completes on each; the lead flow is unchanged | staging site behind Access (note §1), or the API directly |
| Public V3 routes | 404 (`/api/v1/public/catalog`, `/estimates`, `/events`, `/media/<sha>`) | curl through Access |
| Staff catalog API | 404 before authentication (`/api/v1/catalog/dashboard`, `/catalog/media`) | curl |
| Scanner | `none`; step 4c "not selected"; no clamd container | deploy log; `docker ps` |
| Approval | No record in the image (`approved/` absent); `VEDA_CATALOG_APPROVAL_SHA256` absent or `none` | image contents; rendered env names |
| Public intake | disabled | configuration |
| Alarms | `veda-stg-api-health` OK within 5 minutes; no media alarm | CloudWatch |
| Rollback image | The PR #58 tag present in ECR and in `/opt/veda/releases` | ECR; host |
| Production | unchanged | no production target exists |

Media activation smoke tests (S3–S13) are **not** run at this stage.

## 5. Owner-run real-card evidence (phase 5): DONE

Run on the owner's machine with the existing tool, the card outside Git.

| Field | Value |
|---|---|
| Card | `ESS-2026-10-PRIVATE-DRAFT-4`, in `~/veda-private/estimator-2026-10/rate-cards/` (mode 600) |
| Fingerprint check | The canonical fingerprint `2c7b503c57eefcaa1aa09d895c5e393105ee0e5e2a1eb810a258e74c49248e3d` equals the one recorded in the Round 1 session package; the file hash matches the owner's `SHA256SUMS` |
| Engines | SQLite and PostgreSQL |
| Scenarios | `test_real_card_round_trips_and_every_v2_request_matches` and `test_corrected_slice_on_the_real_card`, on each engine: 4 runs, all passed |
| Equality | **PASS** |
| Application commit | The PR #73 merge (recorded as the full SHA in the artifact) |
| Artifact | `~/veda-private/evidence/real-card-evidence-2026-10-11T091650+0000.json` |
| Artifact digest (`artifact_sha256`) | `e309a8683c28e99bebdcd51eecabf685a62777e5fb92dfd501a99bb1b90ac91b` |
| Verified | `--verify` reports "artifact intact" |
| Contents | card fingerprint, commit SHA, engines, scenario ids with outcomes, equality, timestamp, operator; no rates, values, margins or customer data |

Two notes. First, an earlier run the same day (`…T091528+0000.json`, equality FAIL) hit a local harness fault: the
embedded PostgreSQL scratch directory from an earlier test session was not empty and `initdb` refused. It is not an
application result. The rerun used a fresh scratch directory. The owner may delete the first artifact; it is not
referenced anywhere. Second, the brief asks for an "evidence schema version" field; the tool's artifact has no such
field. Adding one is a small reviewed change to the tool and its `--verify`; it is not needed for the activation record,
which references the artifact by digest.

## 6. Scanner-capacity evidence (phase 6): PREPARED, NOT COLLECTED

Collect only after the certified release has run stably with V3 off (§3), so the figures include the current services.
Do not start clamd on the current host. Option A remains prohibited.

| Item the brief asks for | Source | Status |
|---|---|---|
| Instance type, total RAM, available RAM, swap, `Committed_AS`, memory pressure | `13-evidence` label `scanner-capacity` → `capacity-memory.txt` (`free -m`, `swapon`, `/proc/meminfo`, PSI) | prepared |
| Per-container memory (API, worker, scheduler, cloudflared, Litestream), restart counts, OOM-killed flags, memory limits | same → `capacity-containers.txt` (`docker stats`, `docker inspect`) | prepared |
| Kernel OOM history, 14 days | same → `capacity-oom.txt` | prepared |
| Peak memory over time | CloudWatch dashboard, `CWAgent mem_used_percent`, 14-day maximum | prepared |
| Operating-system reserve | Derived: `MemTotal − MemAvailable − container usage` from the same files | prepared |
| Current CPU utilisation | Not collected by `veda-collect`: read the EC2 `CPUUtilization` metric and the CloudWatch agent's CPU metrics for the same window | **manual, read-only** |
| Storage availability | Not collected by `veda-collect`: `df -h /` and `/var/lib/veda` through a read-only Session Manager command, or the agent's disk metrics | **manual, read-only** |
| Scanner database storage requirement | From the ClamAV documentation for the pinned image: the main, daily and bytecode databases, plus headroom for reloads, on the persistent signature volume; record the figure with the image choice | **from the pinned image's documentation** |
| Evidence timestamp and digest | Printed by the run as `evidence s3://… sha256 <digest>`; goes to `media_scanner.capacity_evidence_sha256` and the record's `scanner_capacity` | prepared |

The `13-evidence` run needs the `staging-evidence` environment approval (owner). It was not dispatched: the certified
release is not yet deployed (§3).

## 7. Option B owner-decision package (phase 7): PREPARED, NO PLAN PRODUCED

A plan for a host resize can only come from a pull request that changes `compute.instance_type`, and its
`10-infra-plan` run needs the owner's `staging-plan` approval. No such pull request was opened, because the size cannot
be chosen before the measured evidence of §6. What follows is what the plan will be judged against.

**Eligible instance types.**

| Type | RAM | Allowed by the compute module today | Monthly uplift over `t4g.small` (list price, ap-south-1) | Passes the §4 rule with a 3 GiB clamd reservation and a 25 % reserve |
|---|---|---|---|---|
| `t4g.small` | 2 GiB | yes (current) | 0 | No (option A; prohibited) |
| `t4g.medium` | 4 GiB | yes | +8.18 USD | Not as written; only under a measured policy with `ConcurrentDatabaseReload no` and the reserve derived from the evidence |
| `t4g.large` | 8 GiB | **no**: requires a reviewed change to the module's validation and the network module's AZ offering check | +24.5 USD | Yes, by the documentation figures; to be confirmed by the evidence |

No instance is claimed sufficient without the measured evidence.

**What the plan must show.** `aws_instance`: an in-place update of `instance_type` only (a stop and start of the host;
Terraform does not replace the instance for this attribute, and the module ignores AMI and user-data changes). A
replacement in the plan text is a stop signal. Together with the scanner decision in the same pull request: SSM updates
in place for `VEDA_CATALOG_MEDIA_SCANNER` (`none` → `clamd`) and `VEDA_CATALOG_CLAMD_IMAGE` (`none-selected` → the
digest), one create for `VEDA_CATALOG_MEDIA_RIGHTS_APPROVER` once AD-4 is decided, the budget limit update, and no
destroy. Output `catalog_v3`: `scanner_mode clamd`, `scanner_option B`, `flags_on false`.

**Downtime.** The stop and start takes a few minutes of API unavailability and one host-health alarm cycle. Take a
manual data-volume snapshot before the apply. The next `12-deploy` after the apply starts clamd (step 4c) and refuses to
continue until clamd answers PING.

**Scanner controls already in the certified tree** (`api/deploy/docker-compose.yml`, `scanner` profile; `deploy.sh`;
`media.py`; alarms): image pinned by digest and refused otherwise; private Compose network, no host port; read-only root,
all capabilities dropped except the entrypoint's user switch, no-new-privileges; a persistent signature volume; a health
check; bounded memory; a signature-age signal with the 48-hour threshold; stream scanning with an error treated as
FAILED (never served) and retried by the `catalog-media-scan` job; `StreamMaxLength 30M` to be set above the 15 MB image
limit. Still to validate for the chosen image (enablement §6): ARM64 support, non-root entrypoint behaviour under
`read_only`, the health-check script, freshclam writing the volume, the scan timeout.

**Fail-closed behaviour.** Scanner down: uploads become FAILED and are retried; nothing non-CLEAN is served. Scanner
`none`: uploads stay PENDING. V3 flags on without clamd: refused at plan, preflight and startup.

**Rollback.** `media_scanner.mode` back to `none`: two SSM values change in place, no parameter is removed, the next
deploy stops the scanner. Instance type back to `t4g.small`: an in-place update (stop and start), only after the mode is
`none` and the V3 flags are off.

**Recommendation.** Keep option B as the path. Choose the size from the evidence: if the measured service peak plus a
measured clamd allocation under serialised reloads leaves the owner's reserve on 4 GiB, `t4g.medium` needs no Terraform
module change; otherwise commission the one-line module change for `t4g.large` and the AZ check, and revise the budget
accordingly (AD-3). Record nothing until AD-2 and AD-3 are decided.

## 8. Media-rights approver record (phase 8)

Record AD-4 in the owner-decisions file: primary `[OWNER TO FILL]`, backup `[OWNER TO FILL]`, independence rules and
responsibilities written out. **Activation is blocked until both names are filled.** No name was populated.

## 9. First activation-record sequencing (phase 9)

The circular dependency: an APPROVED record needs `media_smoke_test` evidence; S3–S13 need the staff media API; that API
is 404 until `VEDA_CATALOG_ADMIN_ENABLED` is true; the flag turns on only with the other two and only with an APPROVED,
bound record.

A bounded pre-activation authorisation record, as the brief describes it (staging only, synthetic media only, a short
explicit window, only the minimum staff-media operations, no public intake, no production, no real customer media,
immediate flags-off rollback, every operation recorded, a referenced rollback drill, not the final record), **cannot be
expressed with the certified gates as they stand**:

- the policy has one scope (`approval_scope`) with no bounded or smoke-test mode, and every gate checks the same scope;
- staging-core refuses any partial activation, so admin-only enablement is impossible;
- the staff media routes are gated by the admin flag and the approval record, not by a scope field;
- public delivery would also be enabled by the same three flags (behind Cloudflare Access).

Therefore: **BOUNDED PRE-ACTIVATION RECORD REQUIRES INDEPENDENTLY REVIEWED ENGINEERING CHANGE.** The change would add
a bounded scope to the policy and have the plan refuse `media_delivery_enabled` for it, the build refuse the V3 page for
it, and the routes honour it; every one of the 39 shared cases and the three implementations would change. The policy
is not weakened here; nothing was created or approved.

The no-code alternative is recorded as AD-7 option (b): a controlled activation window with the first record's smoke
evidence being the pre-activation subset, stated in its reference text, followed by a second record with the full
evidence or a revocation. The owner chooses.

## 10. Activation dependency matrix (phase 10)

Status values: DONE, PREPARED, PENDING (needs an action), UNDECIDED (needs a human decision). "Blocks" columns say
whether the item's absence stops that step as the gates are built today.

| Item | Status | Owner | Evidence location | Prerequisite | Plan | Apply | Deploy | Activation | Production |
|---|---|---|---|---|---|---|---|---|---|
| Certified application SHA | DONE | engineering | main at the PR #73 merge; CI green | PR #72, #73 merged | no | no | no | yes (record's `application_commit`) | n/a |
| Approval-digest parameter | PENDING (plan run 38127613791 waiting) | owner approves; engineering inspects | plan run summary; apply run | §2 | no | no | no (preflight tolerates its absence while V3 is off) | yes | n/a |
| Drift check after apply | PENDING | owner | plan run after the apply | apply | no | no | no | yes (policy) | n/a |
| Staging release with V3 off | PENDING (go decision) | owner | `12-deploy` run | §3 review | no | no | is the deploy | yes (capacity evidence depends on it) | n/a |
| Real-card evidence | DONE | owner | `~/veda-private/evidence/…T091650+0000.json`, digest in §5 | card fingerprint verified | no | no | no | yes (`real_card_evidence`) | n/a |
| Scanner decision (AD-1) | UNDECIDED | owner | `staging-platform.json` | AD-2, AD-3, capacity evidence | no | no | no (UNDECIDED allowed) | yes | n/a |
| Host capacity evidence | PREPARED | engineering runs; owner approves `staging-evidence` | evidence bucket object; digest to `capacity_evidence_sha256` | release deployed | no | no | no | yes (`scanner_capacity`) | n/a |
| Host size and reserve (AD-2) | UNDECIDED | owner | `staging-platform.json`, module change if `t4g.large` | capacity evidence | no | no | no | yes | n/a |
| Budget revision (AD-3) | UNDECIDED | owner | `staging-budget.json` | AD-2 | no | no | no | yes (policy) | n/a |
| Pinned scanner image | PENDING (validation per enablement §6) | engineering | validation note; `clamd_image` | image chosen | no | no | yes once mode is `clamd` (deploy refuses an unpinned image) | yes | n/a |
| Scanner health evidence | PENDING (after the resize deploy and soak) | engineering | `13-evidence` `scanner-validation` | scanner running | no | no | no | yes (`scanner_decision`) | n/a |
| Smoke-test evidence | UNDECIDED how (AD-7), then PENDING | engineering, media-rights approver | `13-evidence` `media-smoke-test` | AD-7; for S3–S13, activation or the reviewed change | no | no | no | yes (`media_smoke_test`) | n/a |
| Media-rights approver (AD-4) | UNDECIDED | owner | `media_rights.approver`; signed acceptance note | none | no (plan runs; output refuses only if a flag is on) | no | no | yes | n/a |
| Promise-owner approval (AD-8) | UNDECIDED | owner | owner document; digest | none | no | no | no | yes (`promise_owner_approval`) | n/a |
| Infrastructure-plan digest | DONE for the media apply (the plan digest in §1, run 38106264925); the activation plan's digest comes later | engineering | plan run summaries | — | no | no | no | yes (`infrastructure_plan`) | n/a |
| Infrastructure-apply evidence | DONE for the media apply (run 38106639695) | engineering | apply log | — | no | no | no | yes (`infrastructure_apply`) | n/a |
| Deployment evidence | PENDING | engineering | `12-deploy` run log, `13-evidence` | deploy | no | no | no | yes (practice; not a record field) | n/a |
| Rollback evidence | PENDING (drill S15 in the window) | engineering | `13-evidence` | activation window | no | no | no | yes for the second record | n/a |
| Approval-record author (AD-6) | UNDECIDED | owner names | the record | none | no | no | no | yes | n/a |
| Approval-record approver (AD-6) | UNDECIDED | owner | the record | differs from author | no | no | no | yes | n/a |
| Approval-record dates (AD-6) | UNDECIDED | approver | the record | approval day | no | no | no | yes (REVIEW_WINDOW, EXPIRY_POLICY) | n/a |
| Activation PR | PENDING (all above) | engineering authors; approver reviews | the pull request | every item above; flips the "no record committed" test | is the plan | is the apply | is the deploy | yes | n/a |
| Feature-flag digest binding | PENDING | engineering | `catalog_v3.approval_record_sha256` = file digest | record final bytes | yes (plan refuses a flag on without it) | yes | yes (preflight: APPROVAL DIGEST NOT BOUND) | yes | n/a |
| Production | BLOCKED by design | owner, separately | — | a production decision and a separate review | n/a | n/a | n/a | n/a | yes: the API refuses every V3 flag in production; no production media bucket, scanner, hostname, CDN or CSP change exists |

No undecided human item is marked complete.

## 11. Rollback validation (phase 11), validated against the code and documents, not executed

| # | Level | Mechanism | Validated | Notes |
|---|---|---|---|---|
| 1 | Emergency environment disable | `VEDA_CATALOG_ESTIMATOR_ENABLED=false` in `/etc/veda/api.env`, restart (incident runbook §4) | yes | Public V3 routes 404 within minutes; V1 and V2 unaffected. Leaves the host out of step with SSM until level 2 |
| 2 | All V3 flags false | PR: three flags false, `approval_record_sha256` null; plan (4 in-place SSM updates); apply; Pages `STAGING_ESTIMATOR_VERSION=v2`; `12-deploy` | yes | The only supported shape: staging-core refuses a partial state |
| 3 | Media-delivery false alone | Not supported standalone: the flags turn on and off together (plan precondition and preflight) | **not available as a separate level** | Use level 2. Serve-time stop without a redeploy comes from withdrawal, rights expiry or a revoked approval (level 4) |
| 4 | Approval-record revocation | Commit `status REVOKED` with `revoked_at` and `revocation_reason`; or change the policy or the record so the digest no longer matches | yes | Build refuses v3 at once; runtime refuses every V3 and media route (503) from the next deploy of that record, and immediately if the bound digest in SSM is changed to a non-matching value. Follow with level 2 |
| 5 | Release deactivation | `POST /api/v1/catalog/rollback` with an approval reference and the expected release (four eyes), restoring the previous release; or deactivate by record governance | yes | Without an ACTIVE release with a rate card, public V3 routes answer 503 |
| 6 | Application-image rollback | Owner session; `VEDA_SCHEMA_AHEAD_ACCEPTED=0105_catalog_claim_control`; `./deploy.sh --rollback <PR #58 tag>`; remove the line after the next forward deploy | yes | Floors: the image must know schema `0009_mfa_challenge_binding`; migrations are expand-only, so N-1 serves on the migrated schema |
| 7 | Scanner none | PR: `media_scanner.mode "none"`; plan shows two in-place SSM updates and no removal; apply; `12-deploy` stops the scanner | yes | V3 flags must be off first (startup validation refuses V3 without clamd) |
| 8 | Host-size rollback | PR reverting `compute.instance_type`; plan shows an in-place update (stop and start) | yes, where the plan shows an update and not a replacement | Only after level 7 |
| 9 | Infrastructure rollback without deleting media evidence | The media bucket has `prevent_destroy`; the evidence bucket holds objects under a COMPLIANCE lock; the plan guard refuses destroys | yes | A rollback of settings never removes stored media or evidence; noncurrent media versions expire by lifecycle only |
| 10 | Production isolation | No production root, environment or workflow; the API refuses V3 in production | yes | Nothing above touches production |

**Cache note.** Public media responses carry `Cache-Control: public, max-age=31536000, immutable` on content-hash URLs.
A browser that has already loaded an image may keep showing it from its own cache after the origin stops serving it;
the origin stops immediately on an invalid or revoked approval, a withdrawal, a rights expiry or the flags going off, and
any new request, new browser or hard reload gets 404 or 503. Cloudflare sits in front of `api-staging` behind Access;
if its cache is configured to honour that header for these paths, an origin stop is followed by a cache purge for the
affected URLs. No purge step exists in the runbooks yet; add one to the activation runbook when the Pages and zone
cache settings are confirmed.

## 12. Remaining blockers and verdict

**Owner decisions (UNDECIDED):** AD-1 scanner recording, AD-2 host size and reserve, AD-3 budget, AD-4 media-rights
approver (primary and backup), AD-5 withdrawal during a lapse, AD-6 record roles and dates, AD-7 smoke-test sequencing,
AD-8 promise-owner approval. Also: the go decision on the staging release (§3), and whether to fix the staging site
Pages variable first.

**Operational (PENDING, no decision needed beyond approvals):** approve and inspect plan run 38127613791; apply;
drift-check; deploy certified main with V3 off; collect scanner-capacity evidence; validate and pin the ClamAV image.

**Activation blockers (as the gates enforce them):** scanner UNDECIDED with mode `none`; rights approver placeholder;
no approval record; digest unbound; the approval-digest parameter not yet applied.

**Production blockers (unchanged):** the API refuses every V3 flag in production; no production media bucket, scanner,
hostname, CDN or CSP change; an owner production decision and a separate review.

**Verdict: READY FOR OWNER SCANNER-AND-ACTIVATION DECISIONS.** Every preparatory step that needs no human decision is
done or dispatched and waiting for the owner's approval; the real-card evidence exists; the decision records are
written with their human fields blank; the dependency matrix and rollback validation are complete. Nothing was
activated, enabled, uploaded, approved or changed in production.
