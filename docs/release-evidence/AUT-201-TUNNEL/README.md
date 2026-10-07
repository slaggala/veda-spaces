# Cloudflare tunnel behind Cloudflare Access: evidence (AUT-201)

**Result: LIVE** on 2026-10-07. `api-staging.vedaspaces.com` reaches the staging API only through the Cloudflare
tunnel, and only for a signed-in Access user. `cloudflared` requires the Access token at the origin. Anonymous
requests are redirected to the Access login. The host still accepts no inbound traffic, and public intake stays
disabled (owner decision 2026-10-06, runbook §6.5).

| Item | Value |
|---|---|
| Account, region | `veda-staging` (813238078849), ap-south-1 |
| Host | `i-01538ad0e744faaff`, Amazon Linux 2023.12.20260930, aarch64 |
| Code deployed | `main` at the merge of PR #35, which includes PR #34; the image tag is the first 12 characters of that commit |
| Tunnel | `veda-staging`, locally managed; one proxied CNAME, `api-staging.vedaspaces.com` |
| Access | Team `kite-relay`; self-hosted application "Veda staging" for `api-staging.vedaspaces.com`; one Allow policy (owner and staff e-mail addresses); login by One-time PIN |
| Raw evidence | `s3://veda-evidence-813238078849/host/2026-10-07/i-01538ad0e744faaff/aut-201-tunnel-20261007T102054Z.tgz` |
| Raw evidence SHA-256 | `f8701575c43f3bc6fdf9b657965fe4ddcf599c7263d702b0181b47856077ab98` |

- **Where the raw evidence lives:** in the evidence bucket, under its COMPLIANCE lock, and in the owner's download.
- **Why it isn't committed:** the repository is public, and the files contain the host's private address and
  container IDs. This follows the AUT-002 and RR-14 evidence.
- **How it was checked:**
  - The download's SHA-256 equals the value the collection printed.
  - Every file matches the manifest inside the archive (§6).
  - `detect-secrets scan --all-files` of the files found one candidate: the pre-deploy snapshot's SHA-256 in
    `deploy-log-tail.txt` (a hex digest, not a secret).
  - A pattern scan for tunnel tokens, AWS keys and private keys found nothing.
- **No secrets were displayed:** the edge parameters were seeded by the owner session. The tunnel token went straight
  from `cloudflared tunnel token` into SSM and was never displayed.

## 1. Runs

| Run | Workflow | Result |
|---|---|---|
| 37596536660 | `12-deploy` (merge of PR #34) | Failed on the host after rendering `api.env`: `sed: can't read /opt/veda/host/cloudflared.yml`. The `veda-deploy` document did not install the template. Fixed in PR #35 (finding A1) |
| 37603423362 | `10-infra-plan` on `main` (`push`, the merge of PR #35) | 0 to add, 1 to change, 0 to destroy |
| 37604060821 | `11-infra-apply` | Refused at preflight, as designed: the plan run was triggered by `push`, not `workflow_dispatch` |
| 37604228732 | `10-infra-plan` on `main` (`workflow_dispatch`) | 0 to add, 1 to change, 0 to destroy. The only change is the install line of `module.deploy.aws_ssm_document.deploy`. Plan SHA-256 `151c4c9323ee606a629e9e116486c0e9b37faf0af72fb3a744166b2374479703` |
| 37605128953 | `11-infra-apply` | 0 added, 1 changed, 0 destroyed |
| **37605327200** | **`12-deploy`** | **`deployed <tag> (sha256:97ea7274adff614bdf608317c23ab093fb4b8dfd0f1a3320605068c8dee41247) to staging`** |
| **37606639922** | **`13-evidence`** (`aut-201-tunnel`) | Approved by `slaggala`; evidence object above |

The failed run stopped before `deploy.sh`. It changed no container or database and served no traffic.

## 2. Image and bundle

| Item | Value |
|---|---|
| Image | `veda-api:<tag>` → `sha256:97ea7274adff614bdf608317c23ab093fb4b8dfd0f1a3320605068c8dee41247` |
| Scan gate | 2 HIGH findings, each covered by a reviewed staging exception: CVE-2026-95619 (`gcc-14` 14.2.0-19) and CVE-2026-85091 (`zlib` 1.3.dfsg+really1.3.1-1). No other HIGH or CRITICAL finding. The exception for CVE-2026-102010 no longer matches a finding (A3) |
| Bundle | `s3://veda-stg-artifacts-813238078849/deploy/<tag>/bundle.tgz`, SHA-256 `cef22587cd04853f734f332c6534549102b9c61e9b59863e61b4585f37e9a30c`, verified on the host before use |
| `cloudflared` | `cloudflare/cloudflared:2026.9.3@sha256:072c067d25ccbe61d46e18f0d0723255f2bb5304f7317caa95b27031520ff92c` (pinned in `api/deploy/docker-compose.yml`) |
| Pre-deploy snapshot | `veda-20261007T100954Z.db`, 991,232 bytes, SHA-256 `9548ff779168b7338cab0c14a72dce19c2de207220bcab8d0f73e42395921c7a` |

## 3. Tunnel and Access

| Check (runbook §6.5) | Evidence | Pass |
|---|---|---|
| `12-deploy` log | `rendered the tunnel for api-staging.vedaspaces.com (Access required: team kite-relay)`; then `7. Edge: Cloudflare tunnel, Cloudflare Access required at the origin`; then `tunnel ready: 2 edge connection(s)` and `done: <tag>` | Yes |
| Anonymous request (`curl -sI https://api-staging.vedaspaces.com/health/live`) | `HTTP/2 302` to `https://kite-relay.cloudflareaccess.com/…`. The API never answered | Yes |
| Signed-in browser at the same URL | `{"status":"ok"}`, after the One-time PIN login | Yes |
| Edge parameters | `/veda/staging/edge/CLOUDFLARED_TOKEN` (`SecureString`, `alias/veda-stg-data`), `ACCESS_TEAM_NAME` = `kite-relay`, `ACCESS_AUD` equal to the application's AUD tag (compared by the owner) | Yes |
| `13-evidence` | `deploy-cloudflared-1` up; the only new TCP listener is `127.0.0.1:20241`; the security group has no ingress rule (§4) | Yes, with A2 |

Before the deploy, the tunnel had no connector, and a signed-in request got Cloudflare error 1033. That error proved
the Access application and policy worked before the origin existed.

## 4. Application, containers, listeners, network (collected at 10:20:54 UTC)

| Check | Evidence |
|---|---|
| Readiness | `{"status":"ok","checks":{"db":"ok","migrations":"head","foreign_keys":"on","immutability_guards":"present","outbox_lag_s":null,"outbox_dead":0}}` |
| Schema | `{"current": "0010_consent_evidence_guard", "image_head": "0010_consent_evidence_guard", "state": "head", "release": 3}` |

| Container | Image | State | Port |
|---|---|---|---|
| `deploy-api-1` | `veda-api:<tag>` | Up | `127.0.0.1:8000` |
| `deploy-worker-1` | `veda-api:<tag>` | Up | None |
| `deploy-scheduler-1` | `veda-api:<tag>` | Up | None |
| `deploy-litestream-1` | `litestream/litestream:0.3.13` | Up | `127.0.0.1:9090` |
| `deploy-cloudflared-1` | `cloudflare/cloudflared:2026.9.3` | Up | None (host network, outbound only) |

**Listening sockets.** Compared with RR-14:

| Address | Service | Change |
|---|---|---|
| `127.0.0.1:20241` | `cloudflared` metrics | **New**, loopback only |
| UDP `*:42197`, `*:46465`, `*:51633`, `*:59891` | Unconnected UDP sockets on ephemeral ports | **New**; see A2 |
| `127.0.0.1:8000`, `127.0.0.1:9090`, `127.0.0.1:45443` | API, Litestream metrics, a local agent | Unchanged |
| `0.0.0.0:22` and `[::]:22` | `sshd`; RR-14 finding F2 | Unchanged |
| UDP `127.0.0.1:323`, `[::1]:323`, 68, 546 | chrony, DHCP client | Unchanged |

**Security group `veda-stg-host` (`sg-0e2f313a22d110ef3`), read in the console by the owner on 2026-10-07:**
- **Inbound:** no rules.
- **Outbound:** six rules, exactly those in `infra/terraform/modules/network/main.tf`:
  - TCP 443 to `0.0.0.0/0`;
  - TCP 443 to the S3 prefix list `pl-78a54011`;
  - TCP 7844 and UDP 7844 to each of `198.41.192.0/24` and `198.41.200.0/24`.

**Volume:** `/var/lib/veda` on `/dev/nvme1n1` (xfs, encrypted data volume), 20G, 182M used (1%). `/` is 12G with 3.3G
used (27%).

## 5. Findings

| # | Finding | Effect | Follow-up |
|---|---|---|---|
| A1 | The `veda-deploy` SSM document installed only `infra/host/*.sh` and `cloudwatch-agent.json`. `render-edge.sh` reads `cloudflared.yml` from beside itself. The edge test copied the template there, so the tests passed while the deploy failed | One failed deploy (run 37596536660), stopped before any container changed | **Fixed** in PR #35: the document installs the template, and a check requires every non-script host file to be installed. Applied by run 37605128953 |
| A2 | Four unconnected UDP sockets on ephemeral ports appeared with the tunnel. The runbook expects the listeners to add only `127.0.0.1:20241`. `veda-collect` records `ss` without process names, so their owner is not proven | Not reachable: the security group has no ingress, and outbound UDP is allowed only to the two tunnel ranges on 7844. They are consistent with `cloudflared`'s QUIC connections | Add process names (`ss -p`) to `veda-collect`. Update runbook §6.5 to expect the QUIC client sockets. Together with RR-14 F2, have the evidence flag any unexpected non-loopback listener |
| A3 | The scan exception for CVE-2026-102010 matches no finding (`12-deploy` warning) | None. A stale exception widens the gate for nothing | Remove it from the staging exceptions ([policy](../../operations/image-scan-exceptions.md)) |

RR-14 findings F1, F2 and F3 are still open and unchanged by AUT-201.

## 6. Raw evidence files (SHA-256, from the archive's `MANIFEST.sha256`; all verified)

| File | SHA-256 |
|---|---|
| `containers.txt` | `0d097a549edaed088a08efd9ab9d83000c885b41c597202bddf232eb1b49ae95` |
| `deploy-log-tail.txt` | `2d646646168a269609e7ff4adfb21ea6cfcf24b305152f6c01435b0f614d6c1a` |
| `host.txt` | `233b01c5641da8b81df0334eefbcd3668da6c1bc274a33ac74950387918eb746` |
| `listeners.txt` | `1e5f8cce6c8813c20df1250071d039ba09f0347d96932c7672470f4a4f1626c1` |
| `services.txt` | `9d8c281c03470bd0c19b71f623d370213808b91a995df350e015853bf90b3e72` |
| `storage.txt` | `3766e2962a247e54fc1a95238b9a86e93eb1ead90054e813f28ac90e114056d4` |
| `ready.json` | `50f382273472f7641759eba21360349e7b1deadee7463bf77712be42baed202d` |
| `schema.json` | `383e29b48e4deb520d000e36717c4bb6917a1c4f10a953a78a7d79e127aabbb2` |
