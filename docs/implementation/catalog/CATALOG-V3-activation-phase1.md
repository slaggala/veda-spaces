# Catalog V3 activation preparation, phase 1: capacity evidence, scanner decision package, image validation (2026-10-11)

**Nothing is activated by this record.** V3, media delivery, admin V3 and estimator V3 stay off; the scanner mode
stays `none`; public intake stays disabled; production is unchanged. This phase gathers evidence and prepares the
owner's decisions; the decision records themselves are in
[CATALOG-V3-activation-owner-decisions.md](CATALOG-V3-activation-owner-decisions.md) and remain blank where a human
decision is missing. Phase 0 is [CATALOG-V3-activation-preparation.md](CATALOG-V3-activation-preparation.md).

Digests are SHA-256 and are always written in full (64 hex digits); commits are written as full 40-hex SHAs that
the governance allowlist (`api/tests/unit/test_governance_docs.py`, `KNOWN_COMMITS`) names with their subjects. The
only shorter hex strings are literal artifact names (the image tag, the evidence label and the evidence object key,
which the deploy and evidence workflows form from the first 12 hex digits of the commit). The reference matrix is
[CATALOG-V3-activation-phase1-evidence-references.md](CATALOG-V3-activation-phase1-evidence-references.md).
Times are UTC. Nothing here was read with AWS credentials: this machine has none, and the
evidence objects are readable only by the owner. Every figure below comes from GitHub workflow logs, the Docker
registry, the ClamAV sources and documentation, and the validation run on a GitHub arm64 runner.

## 1. Verified baseline

| Item | Value | How |
|---|---|---|
| main | `c9b1ba35db33328a7d769dba9d1bad483274d63c` (the merge commit of PR #74, "Merge pull request #74 from slaggala/docs/v3-activation-preparation"; docs only on top of the PR #73 merge `246ffeeddf2b9612c6a55be9aa34ce1366c2f5a6`) | `git fetch` over HTTPS; `ls-remote` agrees |
| Approval-digest parameter | Applied: `11-infra-apply` run 38128798960 bound plan run 38127613791 ("1 to add, 0 to change, 0 to destroy"; the one create is `VEDA_CATALOG_APPROVAL_SHA256 = none`) | run logs |
| Drift after the apply | `10-infra-plan` run 38160993150 (dispatch, main): "No changes. Your infrastructure matches the configuration." | run log |
| Staging release | `12-deploy` run 38163064366 (main `c9b1ba35db33328a7d769dba9d1bad483274d63c`), deploy job 18:27:59 to 18:30:08: image `veda-api:c9b1ba35db33` (the literal ECR tag: the first 12 hex digits of that commit) digest `sha256:b9a55479db3c32df3c8e677d67e1bc5d3d1d9940cc6ea265ea039787241162fe`; bundle `9c8728447dc12c573d777572982844867c20a8261c3181449823ef93d71e056d`; preflight printed `scanner not selected` and `V3 intentionally disabled`; host `i-01538ad0e744faaff` | run log |
| Previous release (rollback tag) | PR #58 merge `3e9cbca46a00` (run 37792485980) | run log |
| Release evidence | `13-evidence` run 38164329788, label `phase0-release-c9b1ba35db33`, approved by the owner, collected 18:42:52: `s3://veda-evidence-813238078849/host/2026-10-11/i-01538ad0e744faaff/phase0-release-c9b1ba35db33-20261011T184252Z.tgz` sha256 `47977a7f647d8532e6cc59d029fac01a03c5436796fb25cec525ff94cc56580c` | run log |
| Scanner mode, option, status | `none`, `null`, UNDECIDED | `infra/config/staging-platform.json` |
| V3 flags, media delivery, bound digest | all false; null | same |
| Media-rights approver | `[OWNER TO FILL]` | same |
| Budget | 25 USD/month (O16) | `infra/config/staging-budget.json` |
| Compute | `t4g.small`; the module accepts only `t4g.small` and `t4g.medium` | same; `infra/terraform/modules/compute/variables.tf` |
| Production | No production root, environment, workflow or configuration; the API refuses every V3 flag in production | repository |
| Staging site Pages build | still failing on every main commit since PR #62 (not required; the API is unaffected) | check runs on the PR #74 merge commit (the `main` row) |

## 2. Scanner-capacity evidence (brief item 1): COLLECTED, FIGURES WITH THE OWNER

`13-evidence` was dispatched from main with the label `scanner-capacity` (run 38164988919). The owner approved the
`staging-evidence` environment and `veda-collect` ran on the host:

| Field | Value |
|---|---|
| Evidence object | `s3://veda-evidence-813238078849/host/2026-10-11/i-01538ad0e744faaff/scanner-capacity-20261011T184622Z.tgz` |
| Digest (`media_scanner.capacity_evidence_sha256`; the record's `scanner_capacity`) | `ab25630c5f0e8b2934a8181acd9b55dc5a59de21e05c778d8cefc1da05058517` |
| Collected | 2026-10-11 18:46:22, 16 minutes after the certified release finished deploying |
| Contents (the `veda-collect` document) | `capacity-memory.txt` (`free -m`, swap, `MemTotal`, `MemAvailable`, `Committed_AS`, PSI); `capacity-containers.txt` (`docker stats`, restart counts, OOM-killed flags, start times, memory limits); `capacity-oom.txt` (14 days of kernel OOM history); plus `host.txt`, `containers.txt`, `ready.json`, `schema.json`, `listeners.txt`, `storage.txt` (`df -h`, `findmnt /var/lib/veda`), `services.txt`, `deploy-log-tail.txt`, `MANIFEST.sha256` |
| Readable by | the owner only (evidence bucket, COMPLIANCE lock). The workflow log prints the key and the digest, not the files |

The release-evidence object of §1 (collected four minutes earlier) holds the same files and is a second sample.

**What the owner reads from it, and records in AD-2.** From `capacity-memory.txt`: `MemTotal` (expected 1,9xx MiB on
`t4g.small`), `MemAvailable`, swap (expected none), `Committed_AS`, and the PSI `some`/`full` averages (expected near
zero). From `capacity-containers.txt`: the memory of `api`, `worker`, `scheduler`, `litestream` and `cloudflared`
(their sum is the "current service memory"), every restart count (expected 0 since the deploy) and every OOM flag
(expected false). From `capacity-oom.txt`: no OOM line (the last line is the end marker). From `storage.txt`: free
space on `/` (12 GB) and `/var/lib/veda` (20 GB). The operating-system reserve is `MemTotal − MemAvailable − sum of
container memory`.

**Still manual and read-only (not collected by `veda-collect`):** the 14-day maximum of `CWAgent mem_used_percent`
and the EC2 `CPUUtilization` for the same window, on the `veda-stg-overview` dashboard. Both need the owner's console
session.

**Caveat on timing.** Both samples were taken within 16 minutes of a fresh deploy: the containers had just started, so
their figures are a floor, not a peak. The 14-day CloudWatch maximum covers the previous release (PR #58) and is the
better peak figure for the services that did not change. If the owner wants a measured peak of the certified release,
dispatch `13-evidence` with the label `scanner-capacity` again after a week of soak; the digest of that object then
replaces the one above in AD-1.

## 3. Real-card evidence (brief item 5): DONE AGAIN ON THE DEPLOYED COMMIT

The phase-0 artifact recorded the PR #73 merge (`246ffeeddf2b9612c6a55be9aa34ce1366c2f5a6`). Because the deployed commit is the PR #74 merge, the
procedure ([CATALOG-V3-real-card-evidence.md](CATALOG-V3-real-card-evidence.md)) was run again on the owner's machine,
on a clean checkout of `c9b1ba35db33328a7d769dba9d1bad483274d63c`, with the card read in place outside Git and a fresh embedded-PostgreSQL
directory (the harness fault of phase 0 did not recur).

| Field | Value |
|---|---|
| Card fingerprint | `2c7b503c57eefcaa1aa09d895c5e393105ee0e5e2a1eb810a258e74c49248e3d` (equals the phase-0 and Round 1 fingerprint) |
| Commit | `c9b1ba35db33328a7d769dba9d1bad483274d63c` (clean; no `-dirty` suffix) |
| Engines, scenarios | SQLite and PostgreSQL; `test_real_card_round_trips_and_every_v2_request_matches` and `test_corrected_slice_on_the_real_card` on each: 4 runs, all passed |
| Equality | **PASS** |
| Artifact | `~/veda-private/evidence/real-card-evidence-2026-10-11T184922+0000.json` (mode 600) |
| `artifact_sha256` (the record's `real_card_evidence`) | `0e4e1b11fac8ce4da38df31546ccc05f96dff1c454fdeb101fbe19642f04f9f7` |
| `--verify` | "artifact intact" |

The phase-0 artifact (`artifact_sha256` `e309a8683c28e99bebdcd51eecabf685a62777e5fb92dfd501a99bb1b90ac91b`) stays valid for the PR #73 merge; the record should reference the artifact of the
commit it names in `application_commit`. Note: the tool truncates the `operator` field at 80 characters; it is a
display field, not evidence.

## 4. Option B decision package (brief item 2): PREPARED FOR AD-1, AD-2, AD-3

Option B is the path: the API accepts only `none` and `clamd`, staging-core refuses option A, option C needs an
adapter. What follows gives the owner the measured scanner figures; the host-side figures are in the §2 evidence.

### 4.1 Measured clamd figures (ClamAV on a GitHub `ubuntu-24.04-arm` runner, §5 runs)

| Figure | 1.4.6 LTS (recommended) | 1.5.4 |
|---|---|---|
| Time from start to PONG (signatures preloaded in the image) | 10 s | 10 s |
| Steady memory after load: cgroup `memory.current` / anonymous | 1,052 / 964 MiB | 1,077 / 988 MiB |
| cgroup peak during the first load (includes the signature file cache) | 1,632 MiB | 1,787 MiB |
| RELOAD with `ConcurrentDatabaseReload no`: sampled maximum | 1,052 MiB (no growth) | 1,086 MiB |
| RELOAD with `ConcurrentDatabaseReload yes`: sampled maximum / cgroup peak | 2,006 / 2,009 MiB | 2,032 / 2,036 MiB |
| Reload duration on the runner (scans wait this long under `no`) | 7 s | similar |
| OOM killed under the harness limit of 3 GiB (profiles B and C; **not** the proposed 2,048 MiB) | no | no |
| Signature database in the image / after the first freshclam update | 108 MiB (`main.cvd` 85, `daily.cvd` 22, `bytecode.cvd` 0.3) / 168 MiB (`daily.cld` 82) | same shape |

The ClamAV documentation's figures (minimum 3 GiB, "upwards of 1.2 GiB to load", double during a concurrent reload)
are confirmed in shape: steady use is about 1 GiB anonymous memory, and a concurrent reload doubles it.

### 4.2 Capacity rule with these figures

Enablement §4: `MemTotal − (peak current service memory + clamd reservation + reload peak) ≥ approved reserve`, no OOM
kill and no restart in the window. Let **S** be the owner's figure from `capacity-containers.txt` (sum of the five
service containers at their peak) plus the operating-system reserve (`MemTotal − MemAvailable − containers`). The
clamd term is the Compose `mem_limit` proposed below (the kernel enforces it, so it is the planning figure).

| Host | `MemTotal` (about) | clamd limit | Reserve (a) 25 % | Rule passes when |
|---|---|---|---|---|
| `t4g.medium`, 4 GiB | 3,900 MiB | 2,048 MiB (`ConcurrentDatabaseReload no`) | 975 MiB | **S ≤ 877 MiB** |
| `t4g.medium`, 4 GiB | 3,900 MiB | 3,072 MiB (concurrent reload) | 975 MiB | S ≤ −147 MiB: **never** |
| `t4g.large`, 8 GiB | 7,800 MiB | 2,048 MiB (`no`) | 1,950 MiB | S ≤ 3,802 MiB |
| `t4g.large`, 8 GiB | 7,800 MiB | 3,072 MiB (concurrent reload) | 1,950 MiB | S ≤ 2,778 MiB |

Under reserve policy (b) (a fixed, measured reserve R with the measured first-load peak 1,632 MiB instead of the
limit) `t4g.medium` passes when `3,900 − S − 1,632 ≥ R`.

### 4.3 Recommendation to the owner

| Item | Recommendation | Why |
|---|---|---|
| Instance size (AD-2) | **`t4g.large`** under reserve policy (a) | Passes with more than 2 GiB to spare for any plausible S; a concurrent reload would still fit. `t4g.medium` passes only if S ≤ 877 MiB and only with `ConcurrentDatabaseReload no`; the owner decides it from the §2 figures, with the +8.18 USD saving against a reserve that one extra container or a signature-set growth erases |
| Reserve policy (AD-2) | (a) 25 % of memory on `t4g.large`; (b) only if `t4g.medium` is chosen | as above |
| clamd settings | `ConcurrentDatabaseReload no`, `StreamMaxLength 30M`, `MaxScanSize 100M`, `MaxFileSize 30M`, `MaxRecursion 10` (`infra/scanner-validation/clamd.conf`); Compose `mem_limit` **2048m** (3072m only with concurrent reloads), `mem_reservation` 1024m. **PROPOSED 2048 MiB LIMIT NOT YET VALIDATED**: the harness ran profiles B and C with `--memory 3g`; no run has yet started clamd under a 2,048 MiB cgroup limit | measured peaks 1.63 GiB (first load) and no reload growth, both under a 3 GiB limit; the certified default `mem_limit` 1536m is below the measured first-load peak. The scanner-engineering pull request (§5.6) reruns the harness at the limit it configures before the limit is called validated |
| Monthly cost delta (AD-3) | **Estimated cost pending owner verification** (see §4.5 for the provenance of every figure). `t4g.medium`: +8.17 USD/month compute (recorded rate). `t4g.large`: +24.52 USD/month compute (**extrapolated**, no recorded price). Estimated total staging run rate: about 33–34 USD/month on `t4g.medium`, about 49–50 USD/month on `t4g.large`. No other new cost is expected: the image comes from Docker Hub (not ECR), signature updates are small daily downloads, no new storage | The 25 USD limit must be revised before any resize. Proposed for the owner to accept or change, not approved: 60 USD for `t4g.large`, 40 USD for `t4g.medium`, forecast alerts unchanged at 80 % and 100 %. AD-3 stays UNDECIDED |
| ARM64 ClamAV feasibility | **Feasible**: validated on arm64 for both candidates (§5). Only the `-debian` / `-debian13-slim` image variants are multi-arch; the plain tags are amd64 only | registry manifests; validation runs |
| Rollback | Scanner: `media_scanner.mode` back to `none`; plan shows two in-place SSM updates and no removal; the next `12-deploy` stops the container (step 4c). Host: `compute.instance_type` back to `t4g.small` as an in-place update (stop and start), only after the mode is `none` and the V3 flags are off. The `clamav-db` volume and the pulled image stay on the host until pruned; nothing else is created | preparation record §7 and §11, unchanged |
| Capacity reserve after the resize | `t4g.large`: at least 1,950 MiB free after S and the clamd limit, by construction; confirmed by a `13-evidence` `scanner-validation` collection once clamd runs on the host | §4.2 |

### 4.4 What the resize pull request must contain, and one prerequisite

1. `infra/terraform/modules/compute/variables.tf`: the `instance_type` validation becomes `^t4g\.(small|medium|large)$` (one line) if `t4g.large` is chosen.
2. `infra/config/staging-platform.json` → `compute.instance_type` and `compute.decision`; `infra/config/staging-network.json` → `host_instance_type` (the network module's AZ offering check reads it).
3. `infra/config/staging-budget.json` → `monthly_limit_usd`, `decision` (AD-3).
4. Together or after: `media_scanner` (`status DECIDED`, `option B`, `mode clamd`, `clamd_image` pinned, `capacity_evidence_sha256`, `decision`).
5. **Prerequisite:** `staging-network.json` → `az_id` is still `null` (unpinned). A plan that re-evaluates the AZ preference for a new instance type could move the subnet, which is a replacement; the plan guard refuses the destroy, so nothing would apply, but the plan would be refused. Pin `az_id` to the current subnet's AZ ID (from the state or the console) in the same or an earlier pull request.
6. The plan must show `aws_instance` with an in-place update of `instance_type` only, SSM updates in place, no destroy. Any replacement is a stop signal. Take a data-volume snapshot before the apply; expect a few minutes of API unavailability and one host-health alarm cycle.

### 4.5 Price provenance (correction of 2026-10-12; estimated cost pending owner verification)

The independent review of this record found that the `t4g.large` price was derived, not recorded in any owner
evidence package. The first revision's figure (32.68 USD) is withdrawn: it had no recorded source. What is and is not
recorded:

| Item | Value | Provenance |
|---|---|---|
| Currency, region, pricing model | USD; `ap-south-1` (Mumbai); EC2 on-demand Linux, `standard` credit mode, 730 hours per month | AUT-101 review package §7; staging cost report |
| Price date | AWS Price List API, `AmazonEC2` offer version `20260925174521`, read 2026-10-05 | [STAGING-PLATFORM-cost-report.md](../staging/STAGING-PLATFORM-cost-report.md) |
| `t4g.small` | 0.0112 USD/h; 8.18 USD/month compute | **recorded** in AUT-101 and the cost report |
| `t4g.medium` | 0.0224 USD/h; 16.35 USD/month compute (0.0224 × 730; AUT-101 records the delta against `t4g.small` as +8.18) | **recorded** in AUT-101 (hourly rate) |
| `t4g.large` | **not recorded** in AUT-101, the cost report or any owner evidence package | — |
| `t4g.large`, figure used in this record | 32.70 USD/month compute, delta +24.52 against `t4g.small` | **extrapolation**: 2 × the recorded `t4g.medium` hourly rate (the T4g family doubles per size step) = 0.0448 USD/h × 730 h. Not a price quote. **Estimated cost pending owner verification** against the Price List API or the console before AD-3 is decided |
| Scope of every figure above | compute only (the instance's hourly rate); monthly estimate, not a billed amount; excludes tax, data transfer, EBS, IPv4, KMS, CloudWatch and every other line of the cost report | this table |
| Estimated total staging run rate | cost report list-price total 24.5–25.5 USD/month, minus the `t4g.small` 8.18, plus the new compute figure: about 33–34 USD on `t4g.medium`; about 49–50 USD on `t4g.large` (the `t4g.large` term is the extrapolation above) | arithmetic on the cost report; the CloudWatch always-free allowance would lower it by about 5 USD |
| Billed cost | none exists for either size; staging has never run on them | — |
| Owner budget decision (AD-3) | **UNDECIDED**; the proposed limits (60 / 40 USD) are engineering proposals, not approved amounts | owner-decisions file |

The owner records the verified `t4g.large` price (or a reviewed plan's cost estimate) with AD-3; until then every
`t4g.large` amount in this record and in the owner-decisions file is an estimate.

## 5. ARM64 ClamAV image validation and pin (brief item 3): VALIDATED; ONE REVIEWED CHANGE REQUIRED

### 5.1 Candidates, from the Docker registry (read without credentials)

| | `clamav/clamav:1.4.6-debian13-slim` (**recommended**) | `clamav/clamav:1.5.4-debian13-slim` |
|---|---|---|
| Multi-arch index digest | `sha256:6d0680780fd29855cb7018f68272cb520821f614259e2066f8ec669069ac91b3` | `sha256:9bb8712a50f0e75166e936c452cd82dd5e5be0b85586598930b5bbb84a99a578` |
| **linux/arm64 manifest digest (the value to pin)** | **`sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b`** | `sha256:459a48c390c4e4e7278f730290a244e462fd70419261de171dee3c15fbcb1361` |
| Image id (config digest) | `sha256:2b9aaa241269f3dbb7254c88a1912387d74ad5381bf1f90b15a7504bb8e83dfa` | `sha256:109425c4a8041ea1841e4e210598c5546cb5a9efd0e9d141dd1f716aca6b6f47` |
| Built; size on disk | 2026-09-28; 351 MB | 2026-09-28; 363 MB |
| ClamAV version; signatures in the image | 1.4.6, `daily` build 27 Sep 2026 | 1.5.4, `daily` build 28 Sep 2026 |
| Support (ClamAV EOL policy) | **LTS**: patch versions until 2027-08-15, signature downloads until 2028-08-15 | regular release: patches until four months after 1.6, or 1.7 |
| Base | Debian 13 slim (`debian:13-slim`) | same |

Pin value for `media_scanner.clamd_image` (the `deploy.sh` and preflight pattern `name:tag@sha256:<64 hex>`):

`clamav/clamav:1.4.6-debian13-slim@sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b`

Pinning the arm64 manifest rather than the index means a pull on any other platform fails instead of silently taking
another architecture. The registry also shows that every plain tag (`1.4.6`, `1.5.4`, `stable`, `latest`) is amd64
only; arm64 exists only in the `-debian` and `-debian13-slim` variants.

### 5.2 Image anatomy (upstream Dockerfile and the pulled layers)

| Fact | Value | Consequence for the Compose profile |
|---|---|---|
| Entrypoint | `/init`, runs as root: creates `/run/clamav`, runs `chown -R clamav:clamav /var/lib/clamav`, rewrites `/etc/clamav/*.conf` from `CLAMD_CONF_*` and `FRESHCLAM_CONF_*` variables (`sed -i`), starts `freshclam -d` and `clamd` as user `clamav`, then `tail -f /dev/null` as root | `chown -R` needs to read the directory; `sed -i` needs a writable `/etc/clamav` |
| Unprivileged entrypoint | `/init-unprivileged`: no chown, no config rewrite, starts the daemons as the invoking user; documented by ClamAV for `--user clamav` | needs no capability at all |
| User | `clamav`, uid 1000, gid 1000 | |
| `/var/lib/clamav` | **mode 0700**, owner 1000:1000, holds the signatures | root without `CAP_DAC_OVERRIDE`/`CAP_DAC_READ_SEARCH` cannot read it |
| `/var/log/clamav` | mode 0755, owner 1000:1000; `clamd.conf` sets `LogFile` and `freshclam.conf` sets `UpdateLogFile` there | must be writable, or clamd and freshclam refuse to start ("Can't initialize the internal logger") |
| `/etc/clamav/clamd.conf` as shipped | `LogFile`, `LogTime yes`, `LocalSocket /tmp/clamd.sock`, `TCPSocket 3310`, `User clamav`; defaults otherwise: `StreamMaxLength 25M`, `MaxScanSize 1000M`, `MaxFileSize 400M`, `ConcurrentDatabaseReload` not set (concurrent) | enablement §6 wants `StreamMaxLength 30M`; it cannot be injected by environment under `read_only` |
| Health check | `/usr/local/bin/clamdcheck.sh` (`PING` over `nc localhost 3310`), start period 6 minutes in the image | the Compose test `clamdcheck.sh` is valid |

### 5.3 Measured on arm64 (workflow `14-scanner-image-validation`, branch `activation/phase1-evidence`)

| Profile | 1.4.6 LTS (run 38168217482) | 1.5.4 (run 38168231883) |
|---|---|---|
| **A: the certified Compose profile as it stands** (`/init` as root, `cap_drop ALL` + `CHOWN,SETUID,SETGID`, `read_only`, tmpfs `/tmp` `/run/clamav`, limit 1536m) | **exits at once, code 1: `chown: cannot read directory '/var/lib/clamav': Permission denied`** | same |
| **B: proposed non-root profile** (`user 1000:1000`, `entrypoint /init-unprivileged`, `cap_drop ALL` and nothing added, `read_only`, tmpfs mode 1777 for `/tmp` `/run/clamav` `/var/log/clamav`, `clamd.conf` bind-mounted read-only, `ConcurrentDatabaseReload no`, **limit 3g, not the proposed 2048m**) | ready after 10 s; `healthy`; processes `clamd`, `freshclam`, `tail` all uid 1000; EICAR stream `FOUND` (exit 1); 1 MiB and 20 MiB streams `OK`; 31 MiB stream refused `INSTREAM size limit exceeded` (exit 2, an error, never CLEAN); freshclam replaced `daily.cvd` by `daily.cld` on the volume within two minutes; memory as in §4.1; still answering after the reload | same outcomes; memory as in §4.1 |
| C: profile B with `ConcurrentDatabaseReload yes` | same outcomes; reload peak 2,006 MiB | same; 2,032 MiB |
| Summary digests | `bf5d5a8341a77d087f7771308b860aa376a47a0f4d916291554cb774e33359a9` | `f1c7d89561e72173c1f1b7ca5b7af9c36820d0e147f0786c448f577b6fd87156` |

A first run (38165875991) with the harness mounting tmpfs without an explicit mode showed profile B failing on the
log files with "Permission denied": Docker's default tmpfs mount was not writable by uid 1000. The explicit
`mode=1777` is therefore part of the proposed profile, not an option. One observation for the runbook: the first
freshclam check at start-up finished before clamd had its socket, so the "Clamd was NOT notified" warning appeared
once; clamd's `SelfCheck` (600 s) picks the new database up, and later notifications work.

### 5.4 Enablement §6 checklist, status

| § | Step | Status |
|---|---|---|
| 1 | Choose the image and record it pinned by digest | **CANDIDATE VALIDATED**; recorded in `media_scanner.clamd_image` only by the owner's AD-1 pull request |
| 2 | Validate on ARM64 | **DONE** (both candidates) |
| 3 | Entrypoint under `read_only`, dropped capabilities, tmpfs; clamd as non-root | **DONE for the proposed profile; the certified profile FAILS** (5.3 A) |
| 4 | `clamdcheck.sh` exists | **DONE**: present, used, reports `healthy` |
| 5 | `StreamMaxLength 30M` | **DONE by a bind-mounted `clamd.conf`**: 20 MiB passes, 31 MiB is an error; cannot be set by environment under `read_only` |
| 6 | freshclam updates the persistent volume; signature age under 48 h | **DONE**: `daily.cld` written within two minutes of start; the image's signatures were two weeks old, so the first update is what brings `MediaSignatureAgeHours` under the threshold; the volume keeps it across restarts |

### 5.5 Required reviewed change (not made here)

**SCANNER COMPOSE PROFILE REQUIRES INDEPENDENTLY REVIEWED ENGINEERING CHANGE.** The certified `clamd` service in
`api/deploy/docker-compose.yml` cannot start the official image: `deploy.sh` step 4c would wait 15 minutes for PONG
and refuse the deploy (fail-closed; nothing is served; no harm, no progress). The activation pull request changes the
service to the validated profile:

- `user: "1000:1000"` and `entrypoint: ["/init-unprivileged"]`;
- `cap_drop: ["ALL"]` with **no** `cap_add`;
- tmpfs with an explicit mode for `/tmp`, `/run/clamav` and `/var/log/clamav` (Compose long syntax, `tmpfs.mode: 01777`);
- `./clamd.conf:/etc/clamav/clamd.conf:ro` with the file moved from `infra/scanner-validation/clamd.conf` into `api/deploy/`;
- `mem_limit` 2048m (3072m if concurrent reloads are wanted); `mem_reservation` 1024m unchanged. **PROPOSED 2048 MiB LIMIT NOT YET VALIDATED**: every measurement in §5.3 was taken under a 3 GiB harness limit; the pull request that sets the limit reruns `infra/scanner-validation/validate.sh` with that exact limit and records the result;
- `image`, `profiles`, `expose`, `read_only`, `security_opt`, the volume, the health check and `restart` unchanged.

`deploy.sh`, `media-preflight.sh`, `render-env.sh` and the API need no change. The deploy bundle digest changes with
the file, as for any bundle change. The validation workflow and harness stay available to re-run against the final
profile and against any later image digest.

### 5.6 Scanner-engineering scope: a separate, independently reviewed pull request (NOT this one)

**Boundary.** PR #75 is an evidence and preparation package. It changes no file under `api/deploy/`, no Terraform, no
configuration and nothing on the host; it must not be read as the scanner implementation. The finding, stated exactly:

| Subject | Finding |
|---|---|
| The validated ARM64 image (`clamav/clamav:1.4.6-debian13-slim`, arm64 manifest `sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b`) | **VALID.** Resolves by immutable digest to `linux/arm64`; starts on an arm64 host; answers `PING`; becomes `healthy`; detects the EICAR stream (`FOUND`, exit 1); refuses a 31 MiB stream under `StreamMaxLength 30M` (`INSTREAM size limit exceeded`, exit 2, never CLEAN); freshclam updates the signature volume (`daily.cld` written within two minutes) |
| The current (certified) Compose `clamd` profile in `api/deploy/docker-compose.yml` | **NOT DEPLOYABLE.** Cannot start the image safely: its root entrypoint `/init` attempts `chown -R` on the 0700 uid-1000 signature directory and exits at once without `CAP_DAC_OVERRIDE`/`CAP_DAC_READ_SEARCH`. It **must not** be fixed by adding those or any broad capability, by `privileged`, or by relaxing `read_only` |
| The proposed 2,048 MiB `mem_limit` | **NOT YET VALIDATED** at that limit (§4.3, §5.3) |

**Required scope of the scanner-engineering pull request** (each item independently reviewed; nothing here is done in
PR #75):

1. Image-supported non-root initialisation: `entrypoint: ["/init-unprivileged"]` (the ClamAV-documented unprivileged
   entrypoint; no `chown`, no config rewrite).
2. `user: "1000:1000"`, the image's `clamav` uid and gid, confirmed from the image (`/var/lib/clamav` and
   `/var/log/clamav` are owned 1000:1000); re-confirm against any later image digest.
3. `cap_drop: ["ALL"]` with **no `cap_add`** and **no `privileged`**; `security_opt: no-new-privileges:true` and
   `read_only: true` kept.
4. tmpfs with explicit `mode: 01777` for `/tmp`, `/run/clamav` and `/var/log/clamav` (the default tmpfs mode was not
   writable by uid 1000: run 38165875991).
5. `clamd.conf` as a read-only bind mount (`StreamMaxLength 30M`, `MaxScanSize 100M`, `MaxFileSize 30M`,
   `MaxRecursion 10`, `ConcurrentDatabaseReload no`), moved from `infra/scanner-validation/clamd.conf` into the
   deploy bundle; environment injection is impossible under `read_only`.
6. Persistent signature-database volume (`clamav-db`) owned 1000:1000; the first-start ownership of a fresh volume
   confirmed (the harness used a fresh Docker volume, which Docker initialises from the image's directory ownership;
   the host's existing volume, if any, is inspected before the deploy).
7. Private Compose network only: `expose` 3310 to the API container, **no published host port**, no public scanner
   endpoint; the API reaches clamd by service name.
8. Health and readiness: the image's `clamdcheck.sh` health check, the start period measured (10 s to PONG with
   preloaded signatures; the image allows six minutes), `deploy.sh` step 4c's PONG wait and fail-closed refusal
   unchanged.
9. FreshClam behaviour documented: daemon mode, `UpdateLogFile` under the tmpfs log directory, the one-time "Clamd was
   NOT notified" warning at start-up, `SelfCheck` 600 s pick-up, signature-age alarm threshold 48 h.
10. Rollback to scanner `none`: `media_scanner.mode` back to `none` (two in-place SSM updates, no removal), the next
    `12-deploy` stops the container; the volume and image stay until pruned; validated in the plan output.
11. Validation at the actual proposed memory limit: rerun `infra/scanner-validation/validate.sh` (and workflow
    `14-scanner-image-validation`) with the harness limit set to the configured `mem_limit` (2048m, or 3072m if
    concurrent reloads are chosen); record readiness, EICAR, the stream limit, the reload peak and `OOMKilled` under
    that limit. Until then: **PROPOSED 2048 MiB LIMIT NOT YET VALIDATED**.
12. Reviewed host-resize Terraform plan (§4.4): `instance_type` as an in-place update only, SSM updates in place, no
    destroy, no replacement; data-volume snapshot before the apply; the plan digest recorded for the record's
    `infrastructure_plan`.
13. Availability Zone handling if required: pin `staging-network.json` → `az_id` to the current subnet's AZ ID before
    any instance-type change, so the network module's offering check cannot propose a subnet replacement.
14. Deploy-time evidence: `13-evidence` with the label `scanner-validation` once clamd runs on the host, its digest
    becoming the record's `scanner_decision` evidence (with AD-1).

What is **not** in that scope: enabling any V3 flag, media delivery, public intake, the approval record, the
media-rights approver, or any production change.

## 6. Media-rights approver assignment record (brief item 4): PREPARED, NO NAME

AD-4 in the owner-decisions file is the assignment record; both names are still `[OWNER TO FILL]`. This phase adds
the written acceptance each approver signs:
[media-rights-approver-acceptance.template.md](media-rights-approver-acceptance.template.md). The signed copies live
outside Git; the SHA-256 of the primary approver's signed note is the record's `media_rights_approver` evidence. Until
the primary name is in `infra/config/staging-platform.json` → `media_rights.approver` (reviewed pull request, status
`DECIDED`), staging-core refuses every V3 flag and startup validation refuses the placeholder.

## 7. Approval-record template readiness (brief item 6): READY, THREE NOTES

| Check | Result |
|---|---|
| Template | `docs/implementation/catalog/v3-staging-approval.template.json`, status `DRAFT`, `evidence: {}`, no approver, no dates; digest `fb7000a528cc8e8cda2638ef2bacbd687796e3bbcd9f2ecd26f2e7cf3a3e135d` |
| Policy | `veda.catalog.v3-staging-approval/2`; 15 evidence keys (2 git, 13 digest); review at most 90 days; exactly one of `expires_at` and `non_expiring_decision` |
| Evaluation of the template today (`staging_approval.evaluate`, unbound) | `STATUS, APPROVER, APPROVAL_DATE, REVIEW_WINDOW, EXPIRY_POLICY, EVIDENCE, DIGEST_MISMATCH`: exactly the codes a draft must fail, in policy order |
| No record committed | `api/veda/modules/catalog/approved/` does not exist (the integration test asserts it) |
| Note 1: CLI | `python -m veda.modules.catalog.staging_approval <record>` needs `VEDA_ENV` set (it reads the bound digest from settings); run it with `VEDA_ENV=test` to check a draft |
| Note 2: scope (**resolved as a labelling matter, 2026-10-12**) | The committed file is a **preparation-only DRAFT skeleton**, not the V3-STAGING-1 activation record: status `DRAFT`, `author` `[AUTHOR TO FILL]`, no approver, no dates, `evidence: {}`. It keeps `approval_scope.media_delivery: false`, the restrictive default that can enable nothing. AD-6 records the owner's direction that the activation record sets `media_delivery` to `true` for an activation that enables public delivery behind Cloudflare Access; AD-6 is **UNDECIDED**, so the skeleton does not pre-empt it: the record's author sets the field when AD-6 is recorded ([OWNER TO FILL] in AD-6). The gate accepts either boolean. `test_activation_phase1_docs.py` pins the skeleton's labels and value |
| Note 3: schema version (**fixed in this pull request, 2026-10-12**) | Enablement §10 said schema `/1`; the certified policy (`api/veda/modules/catalog/v3_approval_policy.json`), the template, every fixture and AD-6 say `veda.catalog.v3-staging-approval/2`. The sentence now reads `/2`, and `test_activation_phase1_docs.py` fails if any activation or enablement document names a schema version other than the policy's |

**Evidence already in hand for the record** (reference and digest), to be copied by the record's author:

| Key | Reference | Value |
|---|---|---|
| `application_commit` | main, PR #74 merge | `c9b1ba35db33328a7d769dba9d1bad483274d63c` |
| `pr69_merge` | PR #69 merge | `bb4cbf6405610269d9f23e58e4c6c97dbd30b5ce` |
| `real_card_evidence` | §3 artifact | `0e4e1b11fac8ce4da38df31546ccc05f96dff1c454fdeb101fbe19642f04f9f7` |
| `scanner_capacity` | §2 evidence object | `ab25630c5f0e8b2934a8181acd9b55dc5a59de21e05c778d8cefc1da05058517` |
| `infrastructure_plan` | the media plan (run 38106264925, 38 add / 3 change / 0 destroy) | `aa908b3fcc0c7ed328027806ca49eac714b2b0647ebbd7a9687adad21f50da03`; the activation plan's digest replaces it once that plan exists |
| `infrastructure_apply` | apply runs 38106639695 (media) and 38128798960 (approval digest; plan `9d7a13a65808be962d62a30b0e6ca0c526f70f998068653fb096551453a37a85`) | the author digests the apply log they attach |
| `application_certification`, `media_bucket`, `iam`, `ssm_settings`, `csp` | the certified review and plan-inspection documents on main | the author digests the document bytes they attach |
| `scanner_decision`, `media_smoke_test`, `promise_owner_approval`, `media_rights_approver` | **not available yet** | AD-1 (after the scanner runs), AD-7, AD-8, AD-4 |

The activation PR must also change `api/tests/integration/test_catalog_media_enablement.py` (the test that asserts no
approval record is committed) and bind `catalog_v3.approval_record_sha256` to the final record bytes.

## 8. Activation dependency matrix (brief item 7)

Status words: **COMPLETE** (done and verified), **PENDING** (an action or approval is still needed, no decision),
**BLOCKED** (needs a human decision or an independently reviewed engineering change first). "Blocks" says whether the
item's absence stops activation as the gates are built today.

| Item | Status | Evidence or location | What unblocks it | Blocks activation |
|---|---|---|---|---|
| Certified application on main | COMPLETE | `c9b1ba35db33328a7d769dba9d1bad483274d63c` (PR #74 merge); CI green | — | — |
| Approval-digest parameter applied | COMPLETE | apply run 38128798960 (plan 38127613791, plan digest `9d7a13a65808be962d62a30b0e6ca0c526f70f998068653fb096551453a37a85`) | — | — |
| Drift check after the apply | COMPLETE | plan run 38160993150, "No changes" | — | — |
| Certified release deployed to staging, V3 off | COMPLETE | `12-deploy` run 38163064366; image digest `sha256:b9a55479db3c32df3c8e677d67e1bc5d3d1d9940cc6ea265ea039787241162fe`; preflight lines as expected | — | — |
| Release evidence | COMPLETE | `13-evidence` run 38164329788, object digest `47977a7f647d8532e6cc59d029fac01a03c5436796fb25cec525ff94cc56580c` | — | — |
| Real-card evidence on the deployed commit | COMPLETE | artifact `real-card-evidence-2026-10-11T184922+0000.json`, `artifact_sha256` `0e4e1b11fac8ce4da38df31546ccc05f96dff1c454fdeb101fbe19642f04f9f7`, PASS, intact | — | — |
| Scanner-capacity evidence collected | COMPLETE | `13-evidence` run 38164988919, object digest `ab25630c5f0e8b2934a8181acd9b55dc5a59de21e05c778d8cefc1da05058517` | — | — |
| Scanner-capacity figures read and recorded | PENDING (owner) | the tarball (owner-only); CloudWatch 14-day memory maximum and CPU | the owner reads them into AD-2 | yes (`scanner_capacity` needs the decision it supports) |
| ClamAV image validated on ARM64 and pin value | COMPLETE | §5; runs 38168217482, 38168231883 | — | — |
| Pin recorded in `media_scanner.clamd_image` | BLOCKED (owner decision AD-1) | `infra/config/staging-platform.json` | AD-1 pull request | yes |
| Scanner Compose profile able to start the image | **BLOCKED (reviewed engineering change; not in PR #75)** | §5.5, §5.6 | a separate scanner-engineering pull request, independently reviewed | yes (deploy refuses when the scanner does not answer) |
| Proposed 2,048 MiB clamd limit validated at that limit | **PENDING (PROPOSED 2048 MiB LIMIT NOT YET VALIDATED)** | §4.3, §5.3: the harness ran at 3 GiB | the scanner-engineering pull request reruns the harness at the configured limit (§5.6 item 11) | yes (the limit is the planning figure of the capacity rule) |
| `t4g.large` price verified | **PENDING (owner)**: estimated cost pending owner verification | §4.5: extrapolated from the recorded `t4g.medium` rate; no recorded `t4g.large` price | the owner verifies the price (or a reviewed plan's cost estimate) with AD-3 | yes (AD-3 policy) |
| Host size and reserve (AD-2) | BLOCKED (owner decision) | §4 (`t4g.medium` not recommended; `t4g.large` recommended, pending a reviewed plan and owner cost approval) | owner decision; module and network changes if `t4g.large`; `az_id` pin | yes |
| Budget revision (AD-3) | BLOCKED (owner decision) | `infra/config/staging-budget.json` | owner decision | yes (policy) |
| Resize plan and apply | PENDING (after AD-2, AD-3) | future `10-infra-plan`/`11-infra-apply` runs | in-place update of `instance_type` only | yes |
| Scanner running on the host; scanner health evidence | PENDING (after the Compose change, the resize and a deploy) | `13-evidence` `scanner-validation` | the above | yes (`scanner_decision`) |
| Media-rights approver (AD-4) and signed acceptance | BLOCKED (owner decision) | `media_rights.approver`; acceptance template §6 | the owner names both approvers; the primary signs | yes (plan output, startup validation) |
| Withdrawal during a lapse (AD-5) | BLOCKED (owner decision; a reviewed change if adopted) | owner-decisions file | decision | no (policy clarity only) |
| Record roles and dates (AD-6) | BLOCKED (owner decision) | the record | author and approver named | yes |
| Smoke-test sequencing (AD-7) | BLOCKED (owner decision) | owner-decisions file | option (a) reviewed change, or option (b) controlled window | yes (`media_smoke_test`) |
| Promise-owner approval (AD-8) | BLOCKED (owner decision) | owner document and digest | the owner writes and digests it | yes (`promise_owner_approval`) |
| Approval record template | COMPLETE (ready; three notes in §7) | `v3-staging-approval.template.json` | — | — |
| Approval record authored, approved, bound | PENDING (after every item above) | `api/veda/modules/catalog/approved/v3-staging-approval.json`; `catalog_v3.approval_record_sha256` | the activation pull request | is the activation |
| No-record integration test flipped | PENDING (activation PR) | `test_catalog_media_enablement.py` | same pull request | yes (CI) |
| Staging site Pages build | PENDING (not required) | Cloudflare dashboard | fix the `STAGING_ESTIMATOR_UX` variable or accept | no |
| Production | BLOCKED by design | no root, environment, workflow or configuration; the API refuses V3 in production | a separate owner decision and review | n/a |

No undecided human item is marked complete.

## 9. Remaining owner decisions

AD-1 scanner recording (option B, mode `clamd`, the §5.1 pin, the §2 digest), AD-2 host size and reserve policy (§4.3
recommends `t4g.large` under 25 %), AD-3 budget (proposed 60 USD for `t4g.large`, 40 for `t4g.medium`; every `t4g.large` amount is an estimate pending owner verification, §4.5), AD-4
media-rights approver and backup with the signed acceptance (§6), AD-5 withdrawal during a lapse, AD-6 record author,
approver and dates, AD-7 smoke-test sequencing (option (b) needs no code), AD-8 promise-owner approval. Also: whether
to fix the staging site Pages variable, and whether a second capacity sample after a week of soak is wanted (§2).

## 10. Remaining activation blockers and verdict

**Engineering (one, independently reviewed, in a separate pull request):** the `clamd` Compose service cannot start
the official image under the certified profile (§5.3 A, §5.5). The validated replacement profile is specified and its
full scope is in §5.6; nothing in the certified tree was changed by this phase or by this pull request. If `t4g.large`
is chosen, the one-line compute-module validation and the `az_id` pin come with it (§4.4). The proposed 2,048 MiB
limit is **NOT YET VALIDATED** at that limit (§4.3); the `t4g.large` price is an **estimate pending owner
verification** (§4.5).

**Owner (eight decisions, AD-1 to AD-8), plus** the reading of the capacity figures into AD-2.

**Gates as they enforce today:** scanner UNDECIDED with mode `none`; `media_rights.approver` placeholder; no approval
record; digest unbound. Production: unchanged and refused by the API.

**Verdict: ACTIVATION PREPARATION BLOCKED.** Every piece of evidence this phase could gather without a human decision
has been gathered and digested: host capacity (two objects), the real-card artifact on the deployed commit, the
ARM64 image validation with a pin value, the acceptance template and the record readiness. Activation record
preparation cannot start because two of the record's evidence items (`scanner_decision`, `media_smoke_test`) need a
running scanner, the scanner needs the reviewed Compose change and the owner's AD-1 to AD-3, and the record itself
needs AD-4 to AD-8. The shortest path: the owner reads the §2 figures and records AD-1 to AD-3; engineering opens the
separate, independently reviewed scanner pull request (§5.6) with the Compose profile, the harness rerun at the
configured limit, the module line, the `az_id` pin and the configuration changes; after
the plan, apply and deploy, `13-evidence` collects `scanner-validation`; then AD-4 to AD-8 and the record.

Nothing was activated, enabled, uploaded, approved or changed in production. V3 is off, media delivery is off, the
scanner mode is `none`, public intake is disabled.
