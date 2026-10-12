# Catalog V3 scanner implementation: option B clamd profile, validation at the configured limit, host plan preparation (2026-10-12)

**Scope.** The scanner-engineering work the phase-1 record left to a separate, independently reviewed pull request
([phase-1 record §5.6](CATALOG-V3-activation-phase1.md)): the Compose profile that can start the validated ARM64
ClamAV image without privilege, the readiness and health probes, the scanner monitoring, the validation harness rerun
at the memory limit the bundle configures, and the reviewed host plan for `t4g.large`. Pull request #76
(`infra/scanner-option-b`: implementation commit `a27a650e029561285505ebf8f05286b0269d52a0`, harness fixes up to
`b5de1d4275d3510dc9d5f6b0096fca6fa7702d9a`, the validated commit) and the stacked plan-only proposal #77
(`infra/host-t4g-large-proposal`, commit `2b4c0cda3027a50cf04bcd00b48aeb0fe48b62dc`).

**Not in scope, not done.** No V3 flag is on, media delivery is off, no approval record exists, `media_scanner` stays
UNDECIDED with mode `none`, the host stays `t4g.small`, the budget stays 25 USD, nothing is applied, deployed or
changed in production. This record approves nothing and decides nothing; AD-1 to AD-8 remain the owner's.

## 1. Verified baseline

| Fact | Value | Read from |
|---|---|---|
| `main` at the start | `368975be67a3090ec6312a9b1fd3df805573f6e6` (PR #75 merge, 2026-10-12 02:30 UTC) | `git ls-remote` over HTTPS |
| Certified `clamd` service on `main` | root `/init`, `cap_drop ALL` + `CHOWN,SETUID,SETGID`, `mem_limit` 1536m; **not deployable** (phase-1 §5.3 A) | `api/deploy/docker-compose.yml` |
| Validated image | `clamav/clamav:1.4.6-debian13-slim@sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b` (arm64 manifest, LTS to 2027-08-15) | phase-1 §5.1 |
| Image's unprivileged init | `/init-unprivileged` (`docker-entrypoint-unprivileged.sh` of `Cisco-Talos/clamav-docker`, `clamav/1.4/debian`): no chown, no config rewrite, `freshclam --daemon` in the background, `clamd --foreground &`, then **`exec tail -f /dev/null` as PID 1** | upstream source, read 2026-10-12; recorded by the harness as `init_unprivileged_pid1` |
| Consequence | a clamd that dies leaves the container running and unhealthy; Docker's restart policy never fires; Compose has no restart-on-unhealthy | design input for §2 |
| Host subnet AZ | `aps1-az1` (`ap-south-1a`), `t4g.small`, instance running | state serial 14 embedded in the plan artifact `core-plan-38160993150` (10-infra-plan run 38160993150 on `main` at `246ffeeddf2b9612c6a55be9aa34ce1366c2f5a6`, "No changes") |
| `t4g.large` on-demand price | 0.0448 USD/h; 32.70 USD per 730 h; +24.52 USD/month against `t4g.small` (0.0112) | public AWS Price List, `AmazonEC2` offer version `20261009203134` (published 2026-10-09), region `ap-south-1`, Linux, shared tenancy, no pre-installed software, rate code `PT79HTD5NPVS84HP.JRTCKXETXF.6YS6EN2CT7`; the CSV read 2026-10-12 has SHA-256 `9c2c77f837ddeada0250c2101ade3564e4939d91842a1c8fa7b4e56c436f5170` |

The price confirms the phase-1 extrapolation (§4.5) to the cent; it is now a recorded figure with provenance, and
still **pending owner acceptance** for AD-3 (the owner records the budget, not engineering).

## 2. Compose changes (`api/deploy/docker-compose.yml`, service `clamd`)

| Requirement | Implementation | Why this way |
|---|---|---|
| Non-root execution, user 1000:1000 | `user: "1000:1000"`, the image's `clamav` uid and gid (`clamav_uid_gid` in the harness) | `/var/lib/clamav` (0700) and `/var/log/clamav` (0755) are owned 1000:1000 in the image |
| init-unprivileged approach | `entrypoint: ["/usr/local/bin/veda-clamd-init"]`, a 50-line POSIX `sh` script bind-mounted read-only from the bundle (`api/deploy/clamd-entrypoint.sh`). It does what `/init-unprivileged` does, step for step: the one-time signature download when the volume has none, `freshclam --checks=N --daemon --foreground --stdout &`, `clamd --foreground &`. One difference: it stays PID 1, `wait`s on clamd and **exits with clamd's status**, forwarding SIGTERM to both daemons | so `restart: unless-stopped` restarts a scanner whose clamd died (ExitOnOOM, a crash, the kernel's OOM killer), the restart count feeds `ScannerRestarts`, and a stop by `deploy.sh` (rollback) stays stopped. The upstream script's `exec tail -f /dev/null` would keep a dead scanner "running" for ever (§1) |
| `cap_drop ALL`, no `cap_add`, no privileged | `cap_drop: ["ALL"]`; no `cap_add` key; no `privileged` key; `security_opt: ["no-new-privileges:true"]`; the harness records `CapEff`/`CapPrm`/`CapBnd` of PID 1 (`compose_capabilities`, expected all zero) and `NoNewPrivs=1` | nothing in the profile needs a capability: no chown, no setuid, no port below 1024 |
| tmpfs mode 1777 | `tmpfs:` short syntax, `/tmp:mode=1777,size=256m,noexec,nosuid,nodev`, `/run/clamav:mode=1777,size=8m,…`, `/var/log/clamav:mode=1777,size=64m,…` (Compose passes the options after the colon to Docker unchanged) | the default tmpfs mode was not writable by uid 1000 (phase-1 run 38165875991); the size bounds matter because tmpfs pages are charged to the container's memory cgroup, and `noexec,nosuid,nodev` cost nothing |
| Read-only `clamd.conf` bind mount | `./clamd.conf:/etc/clamav/clamd.conf:ro`, moved from `infra/scanner-validation/` into the bundle: `StreamMaxLength 30M`, `MaxScanSize 100M`, `MaxFileSize 30M`, `MaxRecursion 10`, `ConcurrentDatabaseReload no`, `ExitOnOOM yes`, `TemporaryDirectory /tmp`, `LogFileMaxSize 5M`, `LogRotate yes`; `TCPSocket 3310`, no `TCPAddr` (binds inside the container only) | the image's `/init` rewrites the file from `CLAMD_CONF_*` variables in place, impossible under `read_only`; the harness confirms the mount is read-only (`compose_conf_readonly`) |
| Persistent signature database | named volume `clamav-db:/var/lib/clamav`; Docker initialises a fresh volume from the image's directory (owner 1000:1000, the shipped `main.cvd`, `daily.cvd`, `bytecode.cvd`); freshclam replaces `daily.cvd` by `daily.cld` in place; kept across restarts and across a scanner rollback until pruned | the harness stops and starts the service on the same volume (`compose_after_start_volume`) |
| Private network only, no public port | `expose: ["3310"]`, no `ports`, no `network_mode`; the API reaches `clamd:3310` by service name; the harness records `port_bindings=map[]` and `published=map[3310/tcp:[]]` | unchanged from the certified profile |
| Readiness probe | `deploy.sh` step 4c (unchanged): `zPING` from the API container, up to 15 minutes, fail-closed. `api/deploy/scanner-check.sh` for operators: container state, rendered hardening, `PONG`, `VERSION` (signature build), cgroup memory, signature files, freshclam log; exit 0 only when running, healthy and answering |  |
| Health probe | the image's `clamdcheck.sh` (`PING` over `nc localhost 3310`), `interval 30s`, `timeout 10s`, `retries 3`, `start_period 300s` (measured 10 s to PONG with preloaded signatures; the image allows 6 minutes) | a faster interval than the certified 60 s so `ScannerHealthy` (§4) follows the container within a minute |
| FreshClam support | the entrypoint's daemon, `FRESHCLAM_CHECKS=2` (two checks a day; the `media-signatures-outdated` alarm is at 48 h), the image's `freshclam.conf` (`UpdateLogFile /var/log/clamav/freshclam.log`, `NotifyClamd /etc/clamav/clamd.conf`, `ScriptedUpdates yes`), writes the volume in place. Known and harmless: the first check can finish before clamd's socket exists ("Clamd was NOT notified" once); `SelfCheck` 600 s picks the database up | phase-1 §5.3 observation |
| Memory | `mem_limit 2048m` (default of `${VEDA_CLAMD_MEM_LIMIT}`), `mem_reservation 1024m`, `pids_limit 256` | measured first-load peak 1.63 GiB, no growth on reload with `ConcurrentDatabaseReload no` (phase-1 §4.1); validated at this exact limit in §5 |
| Rollback to scanner `none` | unchanged: `media_scanner.mode` back to `none` (two in-place SSM updates, no removal), the next `12-deploy` runs `deploy.sh` step 4c with `--profile scanner rm -s -f clamd`; the volume and the pulled image stay until pruned | §6 |

Also in the bundle: `scanner-check.sh` (above). `deploy.sh`, `media-preflight.sh`, `render-env.sh` and the API are
unchanged; the bundle digest changes as for any bundle change. `tests/unit/test_deploy_scanner.py` pins every row of
this table; the two PR #75 boundary assertions in `test_activation_phase1_docs.py` now pin the implemented state.

## 3. Security review

| Control | State | Evidence |
|---|---|---|
| Runs as root anywhere | **No.** `user 1000:1000`; PID 1 is the entrypoint as uid 1000; `clamd` and `freshclam` are children as uid 1000 | harness `compose_identity`, `compose_processes` |
| Capabilities | **None.** `cap_drop ALL`, nothing added; `CapEff=CapPrm=CapBnd=0000000000000000`; `NoNewPrivs=1` | `compose_capabilities`, `compose_no_new_privs`; `test_the_scanner_runs_as_the_image_user_without_any_capability` |
| Privileged mode | **No.** No `privileged` key; `privileged=false` in the rendered container | `compose_inspect` |
| Root filesystem | **Read-only**; writes only to the three tmpfs mounts and the signature volume | `compose_root_readonly`, `compose_tmpfs_mounts` |
| Host files reaching the container | two read-only bind mounts from the verified bundle (`clamd.conf`, the entrypoint); nothing else from the host; no secret, no `env_file` (the integration test keeps the scanner away from the application configuration) | `compose_mounts` |
| Network exposure | private Compose network; `expose` only; no published port; no host network | `compose_inspect` (`port_bindings=map[]`) |
| Resource bounds | `mem_limit 2048m`, `mem_reservation 1024m`, `pids_limit 256`, tmpfs sizes 256m + 8m + 64m, `MaxScanSize`/`MaxFileSize`/`StreamMaxLength`/`MaxRecursion` in `clamd.conf` | `compose_inspect`, `compose_effective_conf` |
| Failure mode | fail-closed everywhere: an oversized stream is an error (never CLEAN); a scanner that does not answer leaves uploads FAILED and is never served; `deploy.sh` refuses to continue without PONG; out of memory ends clamd and the container, which restarts | phase-1 §5.3 B; harness `compose_oversize_31MiB_stream`, §5 |
| Supply chain | image pinned by its arm64 manifest digest (a pull on another platform fails); `deploy.sh`, `media-preflight.sh` and the Terraform precondition refuse any unpinned image; the entrypoint and configuration ship in the SHA-256-verified bundle of the reviewed commit | unchanged gates |
| Entrypoint provenance | written for this repository (not a copy of the GPL-2.0 upstream script); its behaviour matches the upstream `docker-entrypoint-unprivileged.sh` step for step except PID 1 | `api/deploy/clamd-entrypoint.sh` header |
| What the image's `/init` would have needed | `CAP_DAC_OVERRIDE`/`CAP_DAC_READ_SEARCH` (for `chown -R` on the 0700 directory) and a writable `/etc/clamav`; **not granted**, as phase-1 §5.6 required | phase-1 §5.3 A |

Residual: the health check and the probes run `nc`/`sh` inside the container (image binaries); the `clamav-db` volume
is writable by uid 1000 (freshclam needs it); a compromised clamd could write signatures only, and `ExitOnOOM`/limits
bound its resources. Nothing in this profile widens the attack surface of the certified one; it narrows it (no
capability, `pids_limit`, bounded tmpfs, `noexec`).

## 4. Scanner monitoring

| Signal | Source | Alarm | Threshold |
|---|---|---|---|
| `Veda/Host ScannerRestarts` (existing) | `health.sh` every minute, `RestartCount` of `deploy-clamd-1`, only while the container exists | `scanner-restarts` | ≥ 3 in 15 minutes |
| `Veda/Host ScannerHealthy` (**new**) | `health.sh`: 1 when the container is `running` and Docker health is `healthy`, else 0; only while the container exists | `scanner-unhealthy` (**new**) | `Minimum < 1` in **two consecutive** 5-minute periods (the heartbeat reports 0 while Docker's health is `starting` after any start or restart, which must not page); missing data not breaching (a stopped scanner reports nothing) |
| `Veda/App MediaScannerUnavailable`, `MediaScanFailed`, `MediaInfected`, `MediaPendingMaxAgeSeconds`, `MediaSignatureAgeHours` (existing) | the API's structured signals | `media-*` | unchanged (enablement §7) |

The monitoring module plans 22 custom metrics with the host (21 before); `staging-platform.json` → `monitoring.decision`
carries the implementation note. Container stdout and stderr (clamd and freshclam print to both; `--stdout`) reach
`/veda/staging/app` through Docker's `awslogs` driver, retained 30 days.

## 5. Validation at the configured limit (2048 MiB)

Workflow `14-scanner-image-validation`, three runs on `ubuntu-24.04-arm` (no credentials), `SCANNER_VALIDATION_MEMORY=2048m`,
image as in §1: run 38198186152 on `a27a650e029561285505ebf8f05286b0269d52a0` (the profile passed every functional check;
the harness stopped at its own Compose-restart step because its stand-in `/etc/veda/api.env` was unreadable), run
38198629083 on `7b9c74b52223cf20ea5fcc5befce7f58b871c22c` (complete; showed that `docker kill` through the Docker API
is recorded as a manual stop and is not restarted, so a host-signal kill of PID 1 was added), and the final run below.
The Compose service, `clamd.conf` and the entrypoint are byte-identical across the three runs (`bundle_*_sha256`:
`ebfe97de92718b126aa50346256a1f1af13b7c450c29bd2575d2d93cc2289841`, `43566d40c8cd531ed8338b8ebb3701724b46cdd16181c713df6ce9bb21dd1725`,
`812696e19088904063603f66e40722f2c0b852f315d7dc1088cdafb5426b7e09`); only the harness changed.

Run **38199283652** on `b5de1d4275d3510dc9d5f6b0096fca6fa7702d9a`; `summary.json` SHA-256 `d05b72f1d701e7009b0de9b003fdbb7d8b31acf84f01c45a3461f41646483bd7` (artifact `scanner-validation-38199283652`; validated at 2026-10-12T03:28:03Z; runner `aarch64 6.17.0-1022-azure`, Docker `28.0.4 compose 2.38.2`).

| Profile (Compose, the bundle) | Result |
|---|---|
| Image, platform | `clamav/clamav:1.4.6-debian13-slim@sha256:fe182632e3f8de585c539fb22d84144dd6a7e2bf7d9470607b86ad8c368d1e3b`; `linux/arm64`; clamd `ClamAV 1.4.6/28136/Sun Sep 27 06:26:12 2026`; daily signatures built 27 Sep 2026 06:26 +0000 |
| Memory limit used | `2048m` (Compose default `2048m`); rendered `HostConfig.Memory` in `compose_inspect` |
| Rendered hardening (`docker inspect`; `7357/tcp` in `published` is the image's `EXPOSE` metadata for a milter that this profile never starts, with no binding) | `user=1000:1000 entrypoint=/usr/local/bin/veda-clamd-init cap_add=[] cap_drop=[ALL] privileged=false read_only=true security_opt=[no-new-privileges:true] tmpfs=map[/run/clamav:mode=1777,size=8m,noexec,nosuid,nodev /tmp:mode=1777,size=256m,noexec,nosuid,nodev /var/log/clamav:mode=1777,size=64m,noexec,nosuid,nodev] memory=2147483648 memory_reservation=1073741824 pids_limit=256 restart=unless-stopped network_mode=deploy_default port_bindings=map[] published=map[3310/tcp:[] 7357/tcp:[]]` |
| Mounts | `bind:<repo>/api/deploy/clamd.conf->/etc/clamav/clamd.conf:rw=false bind:<repo>/api/deploy/clamd-entrypoint.sh->/usr/local/bin/veda-clamd-init:rw=false volume:/var/lib/docker/volumes/deploy_clamav-db/_data->/var/lib/clamav:rw=true ` |
| Identity and directory modes | `uid=1000(clamav) gid=1000(clamav) groups=1000(clamav)`; `/tmp=1777:0:0 /run/clamav=1777:0:0 /var/log/clamav=1777:0:0 /var/lib/clamav=700:1000:1000 ` |
| tmpfs mounts as mounted | `/tmp(rw,nosuid,nodev,noexec,relatime,size=262144k,inode64) /run/clamav(rw,nosuid,nodev,noexec,relatime,size=8192k,inode64) /var/log/clamav(rw,nosuid,nodev,noexec,relatime,size=65536k,inode64) ` |
| Root and configuration writable? | read-only root; clamd.conf: read-only |
| Effective clamd settings | `LogFileMaxSize 5M;LogRotate yes;TemporaryDirectory /tmp;StreamMaxLength 30M;MaxScanSize 100M;MaxFileSize 30M;MaxRecursion 10;ConcurrentDatabaseReload no;ExitOnOOM yes;` |
| Capabilities of PID 1 | `CapPrm:=0000000000000000 CapEff:=0000000000000000 CapBnd:=0000000000000000 `; `NoNewPrivs:=1` |
| Start | ready after 10s |
| Processes (user:command) | `packer:veda-clamd-init packer:freshclam packer:clamd ` |
| Health | healthy |
| EICAR stream | `rc=1 /tmp/f: Eicar-Test-Signature FOUND` |
| Clean 1 MiB / 20 MiB streams | `rc=0 /tmp/f: OK` / `rc=0 /tmp/f: OK` |
| Oversized 31 MiB stream | `rc=2 Failed to parse reply: "INSTREAM size limit exceeded. ERROR"` |
| Memory after load (MiB) | current=1053 peak=1537 anon=964 |
| RELOAD: sampled maximum (MiB) / after | 1052 / current=1050 peak=1537 anon=961 |
| OOM killed / restart count after the checks | false / 0 |
| Signature update (freshclam log) | `bytecode.cvd database is up-to-date (version: 339, sigs: 80, f-level: 90, builder: nrandolp) WARNING: Clamd was NOT notified: Can't connect to clamd through /tmp/clamd.sock: No such file or directory -------------------------------------- ` |
| Volume after the update | `bytecode.cvd=281702 daily.cld=86201856 main.cvd=89072577 ` |
| Still ready after the reload | `Clamd is up ` |
| Restart: `docker compose restart clamd` | ready after 10s; 11 s wall clock; restart count 0 |
| Recovery: clamd killed inside the container | ready after 0s; 15 s wall clock; `before=0 after=1 status=running`; log `veda-clamd-init: starting clamd (foreground; configuration /etc/clamav/clamd.conf)\|veda-clamd-init: clamd exited with status 137; exiting so that Docker's restart policy applies\|veda-clamd-init: starting clamd (foreground; configuration /etc/clamav/clamd.conf)\|` |
| Recovery: PID 1 killed from the host (SIGKILL; an OOM kill or crash of the entrypoint as Docker sees it) | ready after 0s; 10 s wall clock; `before=1 after=2 status=running` |
| Operator `docker kill` (Docker API) | `status=exited exit_code=137 restart_count before=2 after=2`: Docker records an API kill as a manual stop, so the restart policy does not apply (as for `docker stop`); `ScannerHealthy` reports 0 and `scanner-unhealthy` alarms; started again: ready after 10s |
| Stop stays stopped (`docker compose stop`) | `status=exited exit_code=0`; volume `deploy_clamav-db local` |
| Start again on the same volume | ready after 10s; 10 s; volume `bytecode.cvd=281702 daily.cld=86201856 main.cvd=89072577 ` |
| Final state | health healthy; OOM killed false; memory current=960 peak=963 anon=956 |

Comparison profiles at the same limit (`docker run`, the image's `/init-unprivileged`, the bundle's `clamd.conf`):

| Figure | B (`ConcurrentDatabaseReload no`) | C (`ConcurrentDatabaseReload yes`) |
|---|---|---|
| Start | ready after 10s | ready after 10s |
| Health | healthy | healthy |
| EICAR stream | rc=1 /tmp/f: Eicar-Test-Signature FOUND | rc=1 /tmp/f: Eicar-Test-Signature FOUND |
| Oversized 31 MiB stream | rc=2 Failed to parse reply: "INSTREAM size limit exceeded. ERROR" | rc=2 Failed to parse reply: "INSTREAM size limit exceeded. ERROR" |
| Memory after load (MiB) | current=1049 peak=1599 anon=961 | current=1052 peak=1556 anon=964 |
| RELOAD sampled maximum (MiB) | 1050 | 2006 |
| After the reload (MiB) | current=1050 peak=1599 anon=961 | current=1050 peak=2009 anon=961 |
| OOM killed | false | false |
| Still ready after the reload | Clamd is up  | Clamd is up  |
| Signature update | bytecode.cvd=281702 daily.cld=86201856 main.cvd=89072577  | bytecode.cvd=281702 daily.cld=86201856 main.cvd=89072577  |

**Reading.** Under the 2,048 MiB limit the Compose service starts in 10 s, is `healthy`, detects EICAR (exit 1), passes
1 MiB and 20 MiB streams, refuses a 31 MiB stream as an error (exit 2, never CLEAN), peaks at about 1.54 GiB during the
first load (file cache included; anonymous memory 964 MiB), does not grow on a RELOAD (`ConcurrentDatabaseReload no`),
is never OOM-killed, and freshclam replaces `daily.cvd` by `daily.cld` on the volume within the run. A Compose restart
returns it in 11 s. A killed clamd ends the container (the entrypoint logs `clamd exited with status 137`), Docker
restarts it (restart count +1) and it answers again within 15 s of the kill; PID 1 killed from the host is restarted
the same way within 10 s. An operator `docker kill` or `docker compose stop` stays stopped (restart count unchanged),
which is the rollback behaviour `deploy.sh` relies on; `ScannerHealthy` then reports 0. Started again on the same
volume the updated signatures are still there. Profile C (concurrent reload) reaches about 2,006 MiB sampled at this
limit, 42 MiB below it, without an OOM kill: the margin confirms that `ConcurrentDatabaseReload no` is load-bearing.

RERUN_ADDENDUM_PENDING

**PROPOSED 2048 MiB LIMIT: VALIDATED** at that limit for the Compose profile the bundle deploys (this section); the
phase-1 record's statement that its own measurements were taken under 3 GiB remains true of those runs.

## 6. Rollback review

| Step | Mechanism | Verified by |
|---|---|---|
| Scanner off (`clamd` → `none`) | reviewed change of `media_scanner.mode`; plan: two in-place SSM updates (`VEDA_CATALOG_MEDIA_SCANNER`, and `VEDA_CATALOG_CLAMD_IMAGE` if cleared), **no parameter removed**, no destroy; next `12-deploy`: `deploy.sh` step 4c `--profile scanner rm -s -f clamd`; uploads stay PENDING, nothing is served | staging-core tests `scanner_rollback_removes_no_parameter`, `scanner_none_keeps_the_same_parameter_names_as_clamd`; `test_no_scanner_unless_the_configuration_selects_it`; harness `compose_after_stop` (a stopped service stays stopped under `unless-stopped`) |
| Scanner profile revert | revert the Compose service, `clamd.conf` and the entrypoint by a reviewed change; the volume `deploy_clamav-db` and the pulled image remain until pruned (`docker volume rm deploy_clamav-db`, `docker image rm`) | bundle semantics (git archive of the reviewed commit) |
| Host size revert (`t4g.large` → `t4g.small`) | `compute.instance_type` back, `host_instance_type` back; an in-place update (stop and start); only after the scanner mode is `none` and every V3 flag is off (a 2 GiB host cannot carry clamd) | the plan guard refuses any replace; `az_id` pinned so the subnet never moves |
| Monitoring revert | removing the `scanner-unhealthy` alarm is a plan destroy of one alarm: a reviewed change with the owner's apply, as for any alarm | plan guard |
| Nothing to roll back today | the scanner mode is `none`, the host is `t4g.small`; merging #76 changes one alarm and the AZ pin (no infrastructure change: the subnet is already in `aps1-az1`) | #76 plan run (owner-approved) |

## 7. Host plan for `t4g.large` (AD-2; proposal #77, plan only)

| Item | Finding |
|---|---|
| Eligibility | `modules/compute/variables.tf` accepts `t4g.small`, `t4g.medium`, `t4g.large` (test `t4g_large_is_an_in_place_change_of_the_type_only`) |
| AZ behaviour | `az_id` pinned to `aps1-az1` in #76 (§1). The network module now evaluates that AZ only: if `aps1-az1` offers `t4g.large` the subnet is unchanged; if not, the subnet precondition **refuses the plan** (test `pinned_az_without_the_type_refused`). A subnet replacement can no longer be proposed. The AZ cannot be checked without credentials: the #77 plan run is the check |
| Expected plan (#77) | `module.compute.aws_instance.host`: update in place, `instance_type` `t4g.small` → `t4g.large`; `module.monitoring.aws_cloudwatch_metric_alarm.host["scanner-unhealthy"]`: add (from #76); no SSM change (the type is not a parameter); 0 to destroy. Any replace is a stop signal (the guard refuses it) |
| Restart behaviour at apply | an in-place type change stops the instance, modifies it and starts it: a few minutes of API unavailability, one `host-status-check`/`api-health` alarm cycle, Litestream resumes, `deploy.sh` is not involved. A data-volume snapshot before the apply (phase-1 §4.4 item 6). The AMI is pinned by `ignore_changes`, so no rebuild |
| Cost | verified on-demand rate (§1): 32.70 USD/month compute, +24.52 against today; estimated staging total about 49–50 USD/month; the 25 USD budget must be revised first (AD-3, owner). No other new cost: Docker Hub image, small daily signature downloads, one custom metric (about 0.30 USD) |
| Rollback | §6: `t4g.small` again, in place, after the scanner is `none` |
| Guards while PROPOSED | `stack.sh apply` and `stack.sh decisions` (hence `12-deploy`) refuse; `infra/tests/run.sh` fails by design on #77; the owner records AD-2 (and AD-3) or reverts before merging |

**Plan runs.** `10-infra-plan` run **38200171272** for #76 ran with the owner's approval of the `staging-plan`
environment on the pull request's GitHub merge commit (`refs/pull/76/merge`, a synthetic commit outside the branch
history; its SHA is in the artifact's `core-plan.meta.json`), passed
the plan guard ("no destroy, everything in ap-south-1 …") and planned **1 to add, 1 to change, 0 to destroy** (artifact
`core-plan-38200171272`; plan SHA-256 `2ccf7620dd24e0af96ebf10982e8d97783adc98b1f9bff0a344976d510f230d3`, plan text
SHA-256 `10ade82e510fea487be790d4055a0ad0c8c97893f61556257e26fbbd8870f409`; 199 no-op):

| Resource | Action | Why |
|---|---|---|
| `module.monitoring.aws_cloudwatch_metric_alarm.host["scanner-unhealthy"]` | create | `veda-stg-scanner-unhealthy`: `Veda/Host ScannerHealthy`, `Minimum`, `LessThanThreshold 1`, period 300, `treat_missing_data notBreaching`, `actions_enabled true`, dimension `InstanceId` of the host (§4). That run planned the alarm with one evaluation period; the independent review (§9, finding 1) changed it to two, so the next plan shows the same create with `evaluation_periods = 2` |
| `module.monitoring.aws_cloudwatch_dashboard.staging` | update in place | the alarm widget lists every alarm, so the new alarm's ARN joins `dashboard_body`; the forecast in the first version of this record (1 to add, 0 to change) missed this consequence |
| everything else, including `module.network.aws_subnet.public` | no-op | the `az_id` pin names the AZ the subnet already has |

The pull-request plan is review-only by design; an applicable plan is a `workflow_dispatch` run on `main` after the
merge. Run 38198329902 for #77 (the resize) still **waits for the owner's approval**; until it runs, the expected delta
in the table above is a forecast, not a plan.

## 8. Remaining risks

1. **`aps1-az1` offering of `t4g.large` unverified** until the #77 plan runs (owner approval of `staging-plan`; still waiting at the time of this record); a refusal means a different host size or a subnet move, which is a redesign, not an apply.
2. **Budget**: the verified `t4g.large` rate puts staging at about 49–50 USD/month against a 25 USD limit; AD-3 is the owner's; the forecast alert would fire every month until revised.
3. **Concurrent reload headroom**: `ConcurrentDatabaseReload no` is load-bearing at 2048 MiB (phase-1 measured about 2.0 GiB with `yes`); profile C in §5 shows what happens at this limit if that setting ever changes.
4. **Signature growth**: the first-load peak (1.63 GiB) includes the signature file cache; a materially larger signature set narrows the margin to the limit; `ScannerRestarts`/`scanner-unhealthy` would show it; the limit is one Compose variable.
5. **The deploy bundle executes a host-mounted script in the container**: the entrypoint ships in the SHA-256-verified bundle, mounted read-only; a reviewer should read its 50 lines (§2) rather than trust this record.
6. **Owner-only steps remain**: AD-1 (record option B, the pin, the capacity digest), AD-2, AD-3, the approvals of the #76 and #77 plan runs, the `13-evidence` `scanner-validation` collection once clamd runs on the host, AD-4 to AD-8 and the approval record. None is engineering's to take.
7. **No live run on the staging host yet**: every measurement here is from a GitHub arm64 runner (same architecture, different kernel and Docker version, recorded in `docker_version` and `host`); the first host run happens only after AD-1 to AD-3 and the owner's apply and deploy.

## 9. Independent review of the pull request (fresh context, 2026-10-12)

A reviewer with no prior context read the 24-file diff with the security and platform lenses (POSIX `sh` semantics,
Compose v2 behaviour, CloudWatch alarm design, Terraform validation). Result: **no blocker, no major defect**; four minor
findings and three nits, all addressed in this pull request before merge:

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | MINOR | `scanner-unhealthy` would page on every start or restart: the heartbeat reports 0 while Docker's health is `starting`, and one 0 in a 5-minute `Minimum` window with one evaluation period alarms | `evaluation_periods = 2` for this alarm (every host alarm now states its period count; the others keep 1); test asserts both |
| 2 | MINOR | `ready_wait` tolerated `restarting`, so a crash-looping container would spin for the whole limit during the initial start | three or more restarts during one wait record a crash loop and fail at once |
| 3 | MINOR | the summary JSON escaped only `\` and `"`; a future multi-line value would corrupt `summary.json` silently | `rec` folds newlines and tabs into spaces at record time, so the TSV and the JSON stay valid |
| 4 | MINOR | `CLAMAV_NO_MILTERD` was vestigial: only the image's own init scripts read it, and the bundle's entrypoint never starts a milter | removed; the environment carries `FRESHCLAM_CHECKS` only (test updated) |
| 5 | NIT | `User clamav` in `clamd.conf` is ignored when clamd does not start as root (log noise) | removed, with a comment saying why |
| 6 | NIT | freshclam received SIGTERM twice on `docker stop` (trap, then cleanup) | the cleanup signals freshclam only when clamd ended on its own; after a trapped signal it only reaps |
| 7 | NIT | the rendered-hardening row shows `7357/tcp` without saying it is `EXPOSE` metadata, not a listening milter | noted in §5 |

Verified clean by that review: entrypoint signal handling and exit-code propagation, zombie reaping, the initial
database download, tmpfs option passing, the `noexec` tmpfs versus the bind-mounted entrypoint, the health check,
every `clamd.conf` directive for ClamAV 1.4, the heartbeat parsing, the alarm semantics, the compute regex, the
`az_id` pin, the metric count, and that the unit tests cannot pass on a regressed profile.

Findings 4, 5 and 6 change bytes in the deploy bundle (Compose service, `clamd.conf`, entrypoint), so the harness ran
once more on the final bytes: see the addendum at the end of §5.

## 10. Verdict

**SCANNER IMPLEMENTATION CERTIFIED** (after the independent review of §9; the first version of this record said
"ready for independent review").

What that means and does not mean: the Compose profile, the entrypoint, the configuration, the probes, the monitoring,
the harness and the host-plan preparation are implemented, tested offline (Terraform module and root tests, 850 script
checks, the API unit tests that pin the profile) and validated on arm64 at the configured limit (§5), with every
owner-gated step named (§8). Nothing was applied, deployed or activated; V3 is off, media delivery is off, the scanner
mode is `none`, the host is `t4g.small`, production is unchanged.
